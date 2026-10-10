<h1># HideIt</h1>
A Multi-Media Steganography Studio

HideIt is a Python desktop application for hiding secret text messages and files inside ordinary media. It supports image carriers (PNG, JPG, BMP, WEBP), uncompressed WAV audio and video containers (MP4, WEBM, MKV), so confidential data stays invisible in plain sight.

Features include adjustable 1–3 bit LSB embedding, automatic bit-depth detection when decoding, capacity validation, and safe lossless output that never overwrites the original file. Optional AES-256-GCM encryption with PBKDF2 key derivation, plus passphrase-scrambled bit placement, protects payloads even if the hidden data is found.

A built-in inspector visualizes bit planes, noise heatmaps and chi-square steganalysis. The project is split into a Python backend (engine and local REST API) and a PySide6 frontend with a modern dark cybersecurity interface. Everything runs fully offline.

Built for cybersecurity learners, researchers and privacy-minded users, it can be packaged into a standalone Windows executable with PyInstaller. For educational and lawful use only.


# HideIt Studio: Setup & Run Guide

HideIt hides text messages and secret files inside **images, WAV audio and video**, with optional **AES-256-GCM** encryption and adjustable **LSB bit depth**.

The whole app is just **two files** that must sit in the same folder:

| File | Role |
|---|---|
| `backend.py` | Python backend: steganography engine, AES-256, file dialogs, and the desktop window |
| `hideit_ui.html` | The user interface (frontend), shown inside the desktop window |

Plus `requirements.txt` (Python packages) and this guide.

---

## 1. Requirements

| Item | Details |
|---|---|
| Python | 3.9 or newer (3.11/3.12 recommended) |
| Packages | `Pillow`, `cryptography`, `pywebview` (from `requirements.txt`) |
| Internet | **Required each time you run the app.** The interface loads Tailwind CSS, the Lucide icons and the Inter / JetBrains Mono fonts from the web. Without internet the window opens unstyled. |
| Windows | Windows 10/11 with the *Microsoft Edge WebView2 Runtime* (already installed on up-to-date systems; otherwise get it from Microsoft) |
| macOS | 11 or newer (uses the built-in WebKit) |
| Linux | A GTK or Qt web engine (see Troubleshooting) |

Check Python:
```
python --version
```
On macOS/Linux use `python3` and `pip3` if `python` is not found.

---

## 2. Install (one time)

Put `backend.py`, `hideit_ui.html` and `requirements.txt` in one folder, open a terminal there, then:

**Windows**
```
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

**macOS / Linux**
```
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```
If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process Bypass` and try again.

---

## 3. Run

```
python backend.py
```
The HideIt window opens. Close the window to quit.

> Opening `hideit_ui.html` directly in a browser only gives a **preview** of loaded files. Encoding, decoding and the inspector need `backend.py`.

---

## 4. How to use

**Encode (hide data)**
1. Choose the carrier type at the top: *Image*, *Audio* or *Video*.
2. Click the drop zone (or drag a file onto it). The preview appears: thumbnail, waveform with player, or video player.
3. Pick **Text Message** or **Secret File** and enter or choose the payload.
4. Optional: switch on **AES passphrase encryption** and type a passphrase.
5. Pick the **LSB bit depth**. 1 bit gives the best quality; 3 bits gives the most capacity.
6. Watch the **Payload Usage** bar, then press **Encode** and choose where to save. The original file is never overwritten.

**Decode (extract data)**
1. Open the *Decode* tab and load the stego file.
2. Enter the passphrase if one was used. The bit depth is detected automatically.
3. Press **Extract Payload**. Text is shown on screen (with Copy); files are saved with **Download**.

**Inspector**
Load an image or WAV and choose *Standard*, *LSB Plane 0/1* or *Noise Heatmap* to look for hidden-data patterns.

### Carrier types

| Carrier | Method | Output | Notes |
|---|---|---|---|
| Image (PNG, JPG, BMP, WEBP, TIFF) | LSB in the R, G, B bytes | new **PNG** | Never re-save the result as JPG: it destroys the data |
| Audio (8/16-bit PCM WAV) | LSB in the PCM samples | new **WAV** | MP3/FLAC are not supported; converting to MP3 destroys the data |
| Video (MP4, M4V, MOV, WEBM, MKV, AVI) | hidden trailer appended to the file | same container | Video still plays normally; re-encoding or re-uploading removes the data |

### Security notes
- AES-256-GCM key = PBKDF2-HMAC-SHA256 (200,000 rounds) with a random salt and nonce. Any tampering is detected. **A lost passphrase cannot be recovered.**
- With AES on, bit positions are also scrambled using the passphrase, so the same passphrase is needed to find the data.
- Without AES the message is stored in plain text; bit depth only changes how visible the changes are.
- Higher bit depth changes pixel/sample values more (1 bit: up to 1, 2 bits: up to 3, 3 bits: up to 7) and is easier to detect.
- Use only on files you own and for lawful, educational purposes.

---

## 5. Build a Windows .exe (optional)

```
python -m pip install pyinstaller
pyinstaller --onefile --windowed --name HideIt --add-data "hideit_ui.html;." backend.py
```
The program appears in `dist/HideIt.exe`. On macOS/Linux use `:` instead of `;` in `--add-data`.
The exe still needs internet for the interface styling (see section 1).

---

## 6. Troubleshooting

| Problem | Fix |
|---|---|
| `Missing hideit_ui.html next to backend.py` | Keep both files in the same folder and run from there |
| `ModuleNotFoundError: webview / PIL / cryptography` | Activate the virtual environment, then `python -m pip install -r requirements.txt` |
| Window opens but looks plain/unstyled, no icons | No internet; connect and restart (the UI loads its styling from the web) |
| Blank white window on Windows | Install the Microsoft Edge **WebView2 Runtime** |
| Linux: window does not open | Install a web engine: `python -m pip install "pywebview[qt]"` (or `sudo apt install python3-gi gir1.2-webkit2-4.1`) |
| "Desktop engine is still starting" | Wait a second and click again |
| Drag and drop does nothing | Click the drop zone to browse instead |
| Audio/video preview has no picture or sound | Your system lacks the codec for that file; encoding and decoding still work |
| "Only 8-bit and 16-bit PCM WAV files are supported" | Convert the audio to 16-bit PCM WAV (for example in Audacity) |
| "No HideIt payload was found" | Wrong file, wrong passphrase, or the file was re-compressed (JPG/MP3/re-encoded video) |
| "Wrong passphrase, or the payload is corrupted" | Check the passphrase (case-sensitive) |
| "Insufficient image capacity" | Use a bigger carrier, a higher bit depth, or a smaller payload |
| "That file does not match the selected ... format" | Switch the carrier-format buttons at the top first |