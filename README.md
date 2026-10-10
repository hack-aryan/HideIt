<h1># HideIt</h1>
A Multi-Media Steganography Studio

HideIt is a Python desktop application for hiding secret text messages and files inside ordinary media. It supports image carriers (PNG, JPG, BMP, WEBP), uncompressed WAV audio and video containers (MP4, WEBM, MKV), so confidential data stays invisible in plain sight.

Features include adjustable 1–3 bit LSB embedding, automatic bit-depth detection when decoding, capacity validation, and safe lossless output that never overwrites the original file. Optional AES-256-GCM encryption with PBKDF2 key derivation, plus passphrase-scrambled bit placement, protects payloads even if the hidden data is found.

A built-in inspector visualizes bit planes, noise heatmaps and chi-square steganalysis. The project is split into a Python backend (engine and local REST API) and a PySide6 frontend with a modern dark cybersecurity interface. Everything runs fully offline.

Built for cybersecurity learners, researchers and privacy-minded users, it can be packaged into a standalone Windows executable with PyInstaller. For educational and lawful use only.
