"""Service layer: keeps loaded carriers in memory and exposes UI-neutral operations."""
from __future__ import annotations

import base64
import io
import secrets
import threading
from collections import OrderedDict
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from . import engine as eng

MAX_CARRIERS = 4
PLANE0 = [(i & 1) * 255 for i in range(256)]
PLANE1 = [((i >> 1) & 1) * 255 for i in range(256)]


def _b64_png(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _heat(lsb: Image.Image) -> Image.Image:
    """Noise heat colouring used by the UI: (0, v, v*200/255)."""
    return Image.merge("RGB", (Image.new("L", lsb.size, 0), lsb,
                               lsb.point([i * 200 // 255 for i in range(256)])))


def render_inspection(info: dict, mode: str) -> Image.Image:
    if info["kind"] == "image":
        im = info["rgb"].copy()
        im.thumbnail((1200, 1200), Image.NEAREST)
        if mode == "lsb1":
            return im.point(PLANE0 * 3)
        if mode == "lsb2":
            return im.point(PLANE1 * 3)
        if mode == "noise":
            r, g, _ = im.split()
            return _heat(ImageChops.difference(r.point(PLANE0), g.point(PLANE1)))
        return im
    w = 640
    low = info["frames"][0::2] if info["bits"] == 16 else info["frames"]
    h = min(300, len(low) // w)
    if h < 1:
        raise ValueError("Audio file is too short to visualise.")
    data = low[: w * h]
    if mode == "rgb":
        img = Image.new("RGB", (w, 160), "#0f172a")
        d = ImageDraw.Draw(img)
        d.line([(0, 80), (w, 80)], fill="#1e293b")
        n = max(1, len(info["peaks"]))
        for i, (a, b) in enumerate(info["peaks"]):
            x = int(i * w / n)
            d.line([(x, 80 - b * 76), (x, 80 - a * 76 + 1)], fill="#8b5cf6")
        return img
    table = {"lsb1": PLANE0, "lsb2": PLANE1}.get(mode) or [((i & 1) ^ ((i >> 1) & 1)) * 255 for i in range(256)]
    gray = Image.frombytes("L", (w, h), data.translate(bytes(table)))
    return _heat(gray) if mode == "noise" else gray.convert("RGB")


class HideItService:
    def __init__(self):
        self._carriers: "OrderedDict[str, dict]" = OrderedDict()
        self._results: dict[str, dict] = {}
        self._lock = threading.Lock()

    # ---- carriers
    def _get(self, cid: str) -> dict:
        with self._lock:
            info = self._carriers.get(cid)
        if info is None:
            raise ValueError("Carrier session expired. Please load the file again.")
        return info

    def load_carrier(self, path: str, kind: str) -> dict:
        if not path:
            raise ValueError("No file selected.")
        if eng.kind_of(path) != kind:
            raise ValueError(f"That file does not match the selected {kind} format. "
                             "Switch the carrier format above first.")
        info = eng.load_carrier(path)
        cid = secrets.token_hex(8)
        with self._lock:
            self._carriers[cid] = info
            while len(self._carriers) > MAX_CARRIERS:
                self._carriers.popitem(last=False)
        out = {"id": cid, "kind": kind, "name": info["name"], "path": info["path"],
               "ext": info["ext"][1:].upper(), "size": info["size"], "cap": {}}
        if kind != "video":
            out["cap"] = {str(d): eng.lsb_capacity(info, d) for d in (1, 2, 3)}
        if kind == "image":
            thumb = info["rgb"].copy()
            thumb.thumbnail((900, 900))
            out.update(dim=f"{info['w']}x{info['h']}", preview_png=_b64_png(thumb))
        elif kind == "audio":
            out.update(dim=f"{info['rate']/1000:g}k • {info['bits']}b", peaks=info["peaks"],
                       meta=f"{info['rate']/1000:g} kHz • {info['bits']}-bit PCM • {info['channels']} ch")
        else:
            out.update(dim="Video Stream")
        return out

    def clear_carrier(self, cid: str) -> bool:
        with self._lock:
            return self._carriers.pop(cid, None) is not None

    # ---- encode / decode
    def encode(self, cid: str, output_path: str, is_file: bool, text: str = "", secret_path: str = "",
               aes: bool = False, passphrase: str = "", depth: int = 1) -> dict:
        info = self._get(cid)
        if is_file:
            if not secret_path:
                raise ValueError("Please select a payload file!")
            sp = Path(secret_path)
            if not sp.is_file():
                raise ValueError("The payload file no longer exists.")
            inner = eng.build_inner(True, sp.name, sp.read_bytes())
        else:
            if not text:
                raise ValueError("Please enter a secret message!")
            inner = eng.build_inner(False, "", text.encode("utf-8"))
        ext = ".png" if info["kind"] == "image" else info["ext"]
        out = str(output_path)
        if not out.lower().endswith(ext):
            out += ext
        res = eng.embed(info, out, inner, passphrase, aes, True, int(depth))
        return {"name": Path(out).name, "path": out, "encrypted": res["encrypted"],
                "depth": res["depth"], "kind": res["kind"], "stream_bytes": res["stream_bytes"]}

    def decode(self, cid: str, passphrase: str = "") -> dict:
        res = eng.extract(self._get(cid), passphrase)
        rid = secrets.token_hex(8)
        with self._lock:
            self._results = {rid: res}  # keep only the latest result
        out = {"result_id": rid, "is_file": res["is_file"], "size": len(res["data"])}
        if res["is_file"]:
            out["name"] = Path(res["name"]).name or "extracted_payload.bin"
        else:
            try:
                out["text"] = res["data"].decode("utf-8")
            except UnicodeDecodeError:
                raise ValueError("Payload is not valid UTF-8 text (wrong passphrase or corrupted data).")
        return out

    def save_result(self, rid: str, output_path: str) -> dict:
        with self._lock:
            res = self._results.get(rid)
        if res is None:
            raise ValueError("Nothing to save. Extract a payload first.")
        Path(output_path).write_bytes(res["data"])
        return {"name": Path(output_path).name, "path": str(output_path)}

    # ---- inspector
    def inspect(self, cid: str, mode: str) -> dict:
        info = self._get(cid)
        if info["kind"] == "video":
            raise ValueError("The inspector supports image and audio carriers.")
        det = eng.detect(info)
        if info["kind"] == "image":
            h = info["rgb"].histogram()
            hist = [h[i] + h[256 + i] + h[512 + i] for i in range(256)]
        else:
            hist = info["hist"]
        chi2, p = eng.chi_square(hist)
        header = ("HideIt header detected" + (f" • {det['bytes']:,} B" if det else "")
                  + (" • AES-256" if det and det["aes"] else "")
                  + (f" • {det['depth']}-bit LSB" if det else "")) if det else "No unscrambled HideIt header found"
        return {"png": _b64_png(render_inspection(info, mode)), "header": header,
                "chi2": round(chi2, 1), "likelihood": round(p * 100, 1)}
