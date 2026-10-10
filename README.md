<h1># HideIt</h1>
A Multi-Media Steganography Studio

HideIt is a Python desktop application for hiding secret text messages and files inside ordinary media. It supports image carriers (PNG, JPG, BMP, WEBP), uncompressed WAV audio and video containers (MP4, WEBM, MKV), so confidential data stays invisible in plain sight.

Features include adjustable 1–3 bit LSB embedding, automatic bit-depth detection when decoding, capacity validation, and safe lossless output that never overwrites the original file. Optional AES-256-GCM encryption with PBKDF2 key derivation, plus passphrase-scrambled bit placement, protects payloads even if the hidden data is found.

A built-in inspector visualizes bit planes, noise heatmaps and chi-square steganalysis. The project is split into a Python backend (engine and local REST API) and a PySide6 frontend with a modern dark cybersecurity interface. Everything runs fully offline.

Built for cybersecurity learners, researchers and privacy-minded users, it can be packaged into a standalone Windows executable with PyInstaller. For educational and lawful use only.



# HideIt Studio: Setup & Run Guide

HideIt hides text messages and secret files inside **images, WAV audio and video**, with optional **AES-256-GCM** encryption and adjustable **LSB bit depth**. It is split into a Python **backend** (engine + local REST API) and a **PySide6 frontend** (the desktop UI).

---

## 1. Requirements

| Item | Version |
|---|---|
| Python | 3.10 or newer (3.11/3.12 recommended) |
| OS | Windows 10/11, macOS 12+, or Linux with a desktop |
| Disk | about 400 MB (PySide6 is large) |
| Internet | only for the one-time `pip install` |

Check Python:

```
python --version
```

On macOS/Linux use `python3` and `pip3` if `python`/`pip` are not found.

---

## 2. Install (one time)

### Windows (PowerShell or CMD)
```
cd hideit_studio
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### macOS / Linux
```
cd hideit_studio
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process Bypass` first.

---

## 3. Run

### Option A: everything in one command (easiest)
```
python run.py
```
This starts the backend on a random local port (127.0.0.1) with a one-time secret token, then opens the window.

### Option B: backend and frontend separately
Terminal 1 (backend):
```
python -m backend --port 8765 --token mysecret
```
Terminal 2 (frontend):
```
python -m frontend --url http://127.0.0.1:8765 --token mysecret
```
The backend prints the exact frontend command when it starts. It only listens on `127.0.0.1` and rejects any request without the token.

---

## 4. How to use

**Encode (hide data)**
1. Pick the carrier type at the top: *Image*, *Audio (WAV)* or *Video*.
2. Click the drop zone (or drag a file in). A preview appears: thumbnail, waveform + player, or video player.
3. Choose **Text Message** or **Secret File** and enter/select the payload.
4. Optional: tick **AES-256 Passphrase Encryption** and type a passphrase.
5. Pick the **LSB bit depth** (1 = best quality, 3 = most capacity).
6. Watch the **Payload Usage** bar (it turns full at capacity), then press **Encode & Save Modified Media** and choose where to save. The original file is never overwritten.

**Decode (extract data)**
1. Switch to the *Decode* tab and load the stego file.
2. Enter the passphrase if you used one. The bit depth is detected automatically.
3. Press **Extract Payload**. Text appears on screen (with Copy); files are saved with **Download**.

**Inspector**
Load an image or WAV and choose *Standard*, *LSB Plane 0/1* or *Noise Heatmap*. The caption shows whether an unscrambled HideIt header was found plus a chi-square score.

### What each carrier does

| Carrier | Method | Output | Notes |
|---|---|---|---|
| Image (PNG/JPG/BMP/WEBP/TIFF) | LSB in R,G,B bytes | new **PNG** | Never re-save as JPG, it destroys the data |
| Audio (8/16-bit PCM WAV) | LSB in PCM samples | new **WAV** | MP3/FLAC not supported; converting to MP3 destroys the data |
| Video (MP4/M4V/MOV/WEBM/MKV/AVI) | hidden trailer appended to the file | same container | Video plays normally; re-encoding or re-uploading removes it |

### Security notes
- AES-256-GCM key = PBKDF2-HMAC-SHA256 (200,000 rounds) with a random salt and nonce. Tampering is detected. **A lost passphrase cannot be recovered.**
- With AES on, bit positions are also scrambled using the passphrase, so the decoder needs the same passphrase to find the data.
- Without AES the message is stored in plain text; the bit-depth/scramble options only make it harder to spot, not unreadable.
- Higher bit depth means larger pixel/sample changes (1 bit: +/-1, 2 bits: up to 3, 3 bits: up to 7) and is easier to detect.
- Use only on files you own, for lawful and educational purposes.

---

## 5. Project layout

```
hideit_studio/
├── run.py                  # launcher: backend thread + UI
├── requirements.txt
├── SETUP.md
├── backend/
│   ├── engine.py           # LSB / trailer engine, AES-256-GCM
│   ├── service.py          # session state, previews, inspector images
│   ├── server.py           # Flask REST API (token protected)
│   └── __main__.py         # python -m backend
└── frontend/
    ├── app.py              # main window and logic
    ├── widgets.py          # custom styled widgets
    ├── theme.py            # colours, fonts, QSS
    ├── icons.py            # SVG icon set
    ├── client.py           # HTTP client for the backend
    ├── __main__.py         # python -m frontend
    └── assets/fonts/       # JetBrains Mono (bundled)
```

### REST API (all JSON, header `X-HideIt-Token` required)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | liveness check |
| POST | `/api/carrier/load` | `{path, kind}` load a carrier, returns preview data and capacity |
| POST | `/api/carrier/clear` | `{id}` free a loaded carrier |
| POST | `/api/encode` | `{id, output_path, is_file, text, secret_path, aes, passphrase, depth}` |
| POST | `/api/decode` | `{id, passphrase}` returns text or file info |
| POST | `/api/decode/save` | `{result_id, output_path}` write extracted file |
| POST | `/api/inspect` | `{id, mode}` mode: `rgb`, `lsb1`, `lsb2`, `noise` |

---

## 6. Optional: match the original font

The design uses **Inter**. It is not bundled. Download it from Google Fonts and copy `Inter-Regular.ttf`, `Inter-Medium.ttf`, `Inter-SemiBold.ttf`, `Inter-Bold.ttf` into `frontend/assets/fonts/`. It is picked up automatically. Without it, the app falls back to Segoe UI / system sans. JetBrains Mono (SIL OFL license) is already included.

---

## 7. Build a Windows .exe (optional)

```
python -m pip install pyinstaller
pyinstaller --onefile --windowed --name HideIt ^
  --add-data "frontend/assets;frontend/assets" run.py
```
On macOS/Linux replace `^` with `\` and `;` with `:`. The result is in `dist/HideIt.exe` (`dist/HideIt` on macOS/Linux).

---

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: PySide6` / `flask` / `PIL` | Activate the venv, then `python -m pip install -r requirements.txt` |
| `pip` is not recognised | Use `python -m pip ...` |
| Linux: *could not load the Qt platform plugin "xcb"* | `sudo apt install libxcb-cursor0 libxkbcommon-x11-0 libegl1` |
| Video/audio preview shows no picture or sound | Qt uses the OS codecs: install the *Media Feature Pack* on Windows N editions, or `sudo apt install gstreamer1.0-plugins-good gstreamer1.0-libav` on Linux. Encoding and decoding work without the preview. |
| "Only 8-bit and 16-bit PCM WAV files are supported" | Convert the audio to 16-bit PCM WAV (for example in Audacity) |
| "No HideIt payload was found" | Wrong file, wrong passphrase, or the file was re-compressed (JPG/MP3/re-encoded video) |
| "Wrong passphrase, or the payload is corrupted" | Check the passphrase (case-sensitive) |
| "Insufficient carrier capacity" | Use a larger carrier, a higher bit depth, or a smaller payload |
| "That file does not match the selected ... format" | Switch the carrier-format buttons at the top first |
| Window text looks different from the web design | Install the Inter font (section 6) |
| Port already in use (Option B) | Pick another `--port` |

---

## 9. Quick self-test of the backend (no UI)

```
python -m backend --port 8765 --token t
curl -H "X-HideIt-Token: t" http://127.0.0.1:8765/api/health
```
Expected: `{"ok":true,"version":1}`.
