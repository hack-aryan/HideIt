"""
HideIt steganography engine (backend). Pure Python, no UI.
  Carriers : Image (PNG/BMP/TIFF/JPG/WEBP -> lossless PNG out), Audio (8/16-bit PCM WAV),
             Video (MP4/M4V/MOV/WEBM/MKV/AVI via appended trailer)
  Payloads : text message or any secret file
  Security : optional AES-256-GCM (PBKDF2-HMAC-SHA256 key) + optional passphrase-scrambled bit order
  Needs    : Pillow, cryptography
"""
from __future__ import annotations

import array
import hashlib
import math
import os
import shutil
import sys
import wave
from collections import Counter
from pathlib import Path

try:
    from PIL import Image
except ImportError as exc:
    raise SystemExit("HideIt backend requires Pillow: python -m pip install Pillow cryptography flask") from exc

# ============================================================== ENGINE
MAGIC = b"HIDEIT3"                  # 7 bytes
FOOT = b"HIDEITV3"                  # 8 bytes, video trailer footer
HEADER_SIZE = 4 + len(MAGIC) + 1    # 32-bit length + magic + flags = 12
FLAG_AES = 0x01
AES_OVERHEAD = 16 + 12 + 16         # salt + nonce + GCM tag
KDF_ITERATIONS = 200_000
MAX_BODY = 2**32 - 1

IMAGE_EXT = {".png", ".bmp", ".tif", ".tiff", ".jpg", ".jpeg", ".webp"}
AUDIO_EXT = {".wav"}
VIDEO_EXT = {".mp4", ".m4v", ".mov", ".webm", ".mkv", ".avi"}
LOSSY_EXT = {".jpg", ".jpeg", ".webp"}
FILETYPES = {
    "image": [("Images", "*.png *.bmp *.tif *.tiff *.jpg *.jpeg *.webp")],
    "audio": [("WAV audio", "*.wav")],
    "video": [("Video", "*.mp4 *.m4v *.mov *.webm *.mkv *.avi")],
}
LSB_TABLE = bytes(i & 1 for i in range(256))


def kind_of(path) -> str:
    ext = Path(path).suffix.lower()
    if ext in IMAGE_EXT:
        return "image"
    if ext in AUDIO_EXT:
        return "audio"
    if ext in VIDEO_EXT:
        return "video"
    raise ValueError("Unsupported file type. Use an image, a WAV audio file or an MP4/WEBM/MKV video.")


# ---- AES-256-GCM -------------------------------------------------------
def _crypto():
    try:
        from cryptography.exceptions import InvalidTag
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    except ImportError as exc:
        raise ValueError("AES-256 needs the 'cryptography' package:\npython -m pip install cryptography") from exc
    return InvalidTag, hashes, AESGCM, PBKDF2HMAC


def _derive_key(password: str, salt: bytes) -> bytes:
    _, hashes, _, PBKDF2HMAC = _crypto()
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=KDF_ITERATIONS)
    return kdf.derive(password.encode("utf-8"))


def encrypt_blob(data: bytes, password: str) -> bytes:
    _, _, AESGCM, _ = _crypto()
    salt, nonce = os.urandom(16), os.urandom(12)
    return salt + nonce + AESGCM(_derive_key(password, salt)).encrypt(nonce, data, MAGIC)


def decrypt_blob(blob: bytes, password: str) -> bytes:
    InvalidTag, _, AESGCM, _ = _crypto()
    if len(blob) < AES_OVERHEAD:
        raise ValueError("Encrypted payload is truncated.")
    salt, nonce, ct = blob[:16], blob[16:28], blob[28:]
    try:
        return AESGCM(_derive_key(password, salt)).decrypt(nonce, ct, MAGIC)
    except InvalidTag as exc:
        raise ValueError("Wrong passphrase, or the payload is corrupted.") from exc


# ---- payload container -------------------------------------------------
def build_inner(is_file: bool, name: str, data: bytes) -> bytes:
    nb = name.encode("utf-8")[:65535]
    return bytes([1 if is_file else 0]) + len(nb).to_bytes(2, "big") + nb + data


def parse_inner(b: bytes) -> dict:
    if len(b) < 3:
        raise ValueError("Payload is malformed.")
    nl = int.from_bytes(b[1:3], "big")
    return {"is_file": b[0] == 1, "name": b[3:3 + nl].decode("utf-8", "replace"), "data": b[3 + nl:]}


# ---- LSB primitives ----------------------------------------------------
def _bits(data: bytes):
    for byte in data:
        for shift in range(7, -1, -1):
            yield (byte >> shift) & 1


def _channel_indices(total: int, password: str):
    """Sequential order, or a passphrase-keyed full-cycle modular traversal."""
    start, step = 0, 1
    if password:
        d = hashlib.sha256(password.encode("utf-8")).digest()
        start = int.from_bytes(d[:8], "big") % total
        step = (int.from_bytes(d[8:16], "big") % total) or 1
        while math.gcd(step, total) != 1:
            step += 1
            if step >= total:
                step = 1
    i = start
    for _ in range(total):
        yield i
        i = (i + step) % total


def _lsb_write(data: bytearray, nslots: int, pos, header: bytes, body: bytes, password: str, depth: int):
    """Header always uses 1 bit/slot so it can be read without knowing the depth;
    the body then uses `depth` bits per slot (flags bits 1-2 store depth-1)."""
    order = _channel_indices(nslots, password)
    for bit, ci in zip(_bits(header), order):
        p = pos(ci)
        data[p] = (data[p] & 0xFE) | bit
    keep = (0xFF << depth) & 0xFF
    gen, total, done = _bits(body), len(body) * 8, 0
    for ci in order:
        if done >= total:
            break
        n = min(depth, total - done)
        v = 0
        for _ in range(n):
            v = (v << 1) | next(gen)
        v <<= depth - n
        p = pos(ci)
        data[p] = (data[p] & keep) | v
        done += n


def _reader(data, nslots, pos, password):
    it = _channel_indices(nslots, password)

    def read(n: int, depth: int = 1) -> bytes:
        out, acc, have, mask = bytearray(), 0, 0, (1 << depth) - 1
        try:
            while len(out) < n:
                while have < 8:
                    acc = (acc << depth) | (data[pos(next(it))] & mask)
                    have += depth
                out.append((acc >> (have - 8)) & 0xFF)
                have -= 8
                acc &= (1 << have) - 1
        except StopIteration:
            raise ValueError("Carrier ended before the payload was complete.")
        return bytes(out)
    return read


def _lsb_read(data, nslots, pos, password):
    if nslots < HEADER_SIZE * 8:
        raise ValueError("This carrier is too small to contain a HideIt header.")
    for pw in ([password] if password else []) + [""]:
        read = _reader(data, nslots, pos, pw)
        hdr = read(HEADER_SIZE)
        if hdr[4:4 + len(MAGIC)] != MAGIC:
            continue
        length, flags = int.from_bytes(hdr[:4], "big"), hdr[-1]
        depth = ((flags >> 1) & 3) + 1
        if depth > 3 or HEADER_SIZE * 8 + -(-length * 8 // depth) > nslots:
            raise ValueError("Invalid stored length. The file may be corrupted or modified.")
        return flags, read(length, depth)
    raise ValueError("No HideIt payload was found. Check the file, and the passphrase if bit "
                     "locations were scrambled.")


# ---- carriers ----------------------------------------------------------
def _read_wav(p: Path):
    try:
        with wave.open(str(p), "rb") as w:
            params, frames = w.getparams(), w.readframes(w.getnframes())
    except (wave.Error, EOFError) as exc:
        raise ValueError("Not a readable PCM WAV file (compressed or float WAV is unsupported).") from exc
    if params.sampwidth not in (1, 2):
        raise ValueError("Only 8-bit and 16-bit PCM WAV files are supported.")
    return params, frames


def _audio_view(frames: bytes, sw: int, nch: int, width=480):
    if sw == 2:
        arr = array.array("h")
        arr.frombytes(frames[:len(frames) // 2 * 2])
        if sys.byteorder == "big":
            arr.byteswap()
        mid, scale, low = 0, 32768.0, frames[0::2]
    else:
        arr, mid, scale, low = array.array("B", frames), 128, 128.0, frames
    ch = arr[0::nch]
    peaks, step = [], max(1, len(ch) // width)
    for i in range(min(width, len(ch) // step)):
        seg = ch[i * step:(i + 1) * step]
        peaks.append(((min(seg) - mid) / scale, (max(seg) - mid) / scale))
    dens, step2 = [], max(1, len(low) // 200)
    for i in range(min(200, len(low) // step2)):
        seg = low[i * step2:(i + 1) * step2]
        dens.append(sum(seg.translate(LSB_TABLE)) / len(seg))
    hist = Counter(low[:4_000_000])
    return peaks, dens, [hist.get(i, 0) for i in range(256)]


def load_carrier(path) -> dict:
    p = Path(path)
    if not p.exists():
        raise ValueError("The selected file does not exist.")
    kind = kind_of(p)
    info = {"kind": kind, "path": str(p), "name": p.name, "ext": p.suffix.lower(), "size": p.stat().st_size}
    if kind == "image":
        try:
            img = Image.open(p)
            img.load()
        except Exception as exc:
            raise ValueError("The selected file is not a readable image.") from exc
        alpha = img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info
        work = img.convert("RGBA" if alpha else "RGB")
        img.close()
        stride = 4 if alpha else 3
        info.update(w=work.width, h=work.height, stride=stride, work=work, nslots=work.width * work.height * 3,
                    rgb=work.convert("RGB") if alpha else work,
                    pos=lambda ci, s=stride: (ci // 3) * s + ci % 3)
    elif kind == "audio":
        params, frames = _read_wav(p)
        sw = params.sampwidth
        peaks, dens, hist = _audio_view(frames, sw, params.nchannels)
        info.update(params=params, frames=frames, nslots=len(frames) // sw, peaks=peaks, dens=dens, hist=hist,
                    pos=(lambda ci: 2 * ci) if sw == 2 else (lambda ci: ci),
                    rate=params.framerate, bits=sw * 8, channels=params.nchannels)
    else:
        info.update(nslots=0)
    return info


def lsb_capacity(info: dict, depth: int = 1) -> int:
    """Max body bytes an LSB carrier can hold at the given bit depth."""
    return max(0, ((info["nslots"] - HEADER_SIZE * 8) * depth) // 8)


def embed(info: dict, out_path, inner: bytes, password: str = "", aes: bool = False, scramble: bool = True,
          depth: int = 1):
    out = Path(out_path).resolve()
    if out == Path(info["path"]).resolve():
        raise ValueError("Output must be a new file. HideIt never overwrites the original carrier.")
    if aes:
        if not password:
            raise ValueError("Enter an AES-256 passphrase.")
        body = encrypt_blob(inner, password)
    else:
        body = inner
    if len(body) > MAX_BODY:
        raise ValueError("Payload is too large (4 GB limit).")
    kind = info["kind"]
    depth = depth if kind != "video" and depth in (1, 2, 3) else 1
    header = len(body).to_bytes(4, "big") + MAGIC + bytes([(FLAG_AES if aes else 0) | ((depth - 1) << 1)])
    stream = header + body
    order_pw = password if (aes and scramble) else ""
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")

    if kind == "video":
        with open(info["path"], "rb") as s, open(tmp, "wb") as d:
            shutil.copyfileobj(s, d, 1 << 20)
            d.write(stream)
            d.write(len(stream).to_bytes(8, "big") + FOOT)
    else:
        if len(body) > lsb_capacity(info, depth):
            raise ValueError(
                "Insufficient carrier capacity.\n"
                f"Needed: {len(body):,} bytes (incl. encryption overhead)  |  "
                f"Available at {depth} bit(s): {lsb_capacity(info, depth):,} bytes")
        if kind == "image":
            data = bytearray(info["work"].tobytes())
            _lsb_write(data, info["nslots"], info["pos"], header, body, order_pw, depth)
            Image.frombytes(info["work"].mode, info["work"].size, bytes(data)).save(tmp, format="PNG")
        else:
            data = bytearray(info["frames"])
            _lsb_write(data, info["nslots"], info["pos"], header, body, order_pw, depth)
            with wave.open(str(tmp), "wb") as w:
                w.setparams(info["params"])
                w.writeframes(bytes(data))
    tmp.replace(out)
    return {"stream_bytes": len(stream), "encrypted": aes, "kind": kind, "depth": depth}


def _read_trailer(path):
    with open(path, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        if size < 16 + HEADER_SIZE:
            raise ValueError("No HideIt payload was found in this video.")
        f.seek(size - 16)
        foot = f.read(16)
        if foot[8:] != FOOT:
            raise ValueError("No HideIt payload was found in this video.")
        sl = int.from_bytes(foot[:8], "big")
        if sl < HEADER_SIZE or sl > size - 16:
            raise ValueError("Invalid trailer length. The file may be corrupted.")
        f.seek(size - 16 - sl)
        stream = f.read(sl)
    if stream[4:4 + len(MAGIC)] != MAGIC or int.from_bytes(stream[:4], "big") != sl - HEADER_SIZE:
        raise ValueError("The video trailer is not a valid HideIt payload.")
    return stream[HEADER_SIZE - 1], stream[HEADER_SIZE:]


def extract(info: dict, password: str = "") -> dict:
    kind = info["kind"]
    if kind == "video":
        flags, body = _read_trailer(info["path"])
    else:
        data = info["work"].tobytes() if kind == "image" else info["frames"]
        try:
            flags, body = _lsb_read(data, info["nslots"], info["pos"], password)
        except ValueError as exc:
            if info["ext"] in LOSSY_EXT:
                raise ValueError(str(exc) + "\nNote: JPEG/WEBP are lossy; hidden data does not survive them.")
            raise
    if flags & FLAG_AES:
        if not password:
            raise ValueError("This payload is AES-256 encrypted. Enter the passphrase.")
        body = decrypt_blob(body, password)
    return parse_inner(body)


def detect(info: dict):
    """Cheap header scan (unscrambled LSB / video trailer). Returns dict or None."""
    try:
        if info["kind"] == "video":
            flags, body = _read_trailer(info["path"])
            return {"aes": bool(flags & FLAG_AES), "bytes": len(body)}
        data = info["work"].tobytes() if info["kind"] == "image" else info["frames"]
        if info["nslots"] < HEADER_SIZE * 8:
            return None
        hdr = _reader(data, info["nslots"], info["pos"], "")(HEADER_SIZE)
        if hdr[4:4 + len(MAGIC)] == MAGIC:
            return {"aes": bool(hdr[-1] & FLAG_AES), "bytes": int.from_bytes(hdr[:4], "big"),
                    "depth": ((hdr[-1] >> 1) & 3) + 1}
    except ValueError:
        pass
    return None


def chi_square(hist256):
    chi2, df = 0.0, 0
    for k in range(128):
        a, b = hist256[2 * k], hist256[2 * k + 1]
        e = (a + b) / 2
        if e > 4:
            chi2 += (a - e) ** 2 / e
            df += 1
    if df < 2:
        return chi2, 0.0
    z = ((chi2 / df) ** (1 / 3) - (1 - 2 / (9 * df))) / math.sqrt(2 / (9 * df))
    return chi2, 1 - 0.5 * (1 + math.erf(z / math.sqrt(2)))



