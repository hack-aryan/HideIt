"""Main window: HideIt Studio UI (PySide6) driven by the backend REST API."""
from __future__ import annotations

import base64
import itertools
import sys
import tempfile
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QSize, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QMainWindow,
                               QPushButton, QScrollArea, QTextEdit, QVBoxLayout, QWidget)

from . import theme as T
from .client import Client
from .icons import icon, pixmap
from .widgets import (AlignCenter, Check, DropZone, GradientLabel, LogoBadge, MediaPlayerBox, PasswordEdit,
                      ProgressBar, RoundedImage, ToastHost, Waveform, frame, gradient_css, hbox, icon_label,
                      lbl, pill_button, set_placeholder, style_edit, vbox)

KIND_TEXT = {
    "image": ("Supports PNG, JPG, WEBP, BMP", "LSB Spatial Embedding (PNG Output)", "PNG (Lossless)",
              "For Images, HideIt uses LSB pixel embedding. It alters the lowest bits of RGB pixel values to "
              "store bits of the secret payload without perceptible visual changes.",
              "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)"),
    "audio": ("Supports uncompressed 8/16-bit WAV audio files", "PCM Sample LSB Embedding",
              "WAV (Uncompressed PCM)",
              "For Audio, HideIt embeds bits into the least significant bits of PCM audio samples. The "
              "modifications are practically unnoticeable to human hearing.",
              "WAV audio (*.wav)"),
    "video": ("Supports MP4, WEBM, MKV, MOV video files", "Video Container Trailer Injection",
              "MP4 / WEBM Container",
              "For Video, HideIt appends the payload as a hidden trailer after the container data, leaving "
              "video and audio playback completely intact. Re-encoding the video removes it.",
              "Video (*.mp4 *.m4v *.mov *.webm *.mkv *.avi)"),
}
AES_OVERHEAD = 44
_chevron_file = None


def chevron_url() -> str:
    """Render the combo-box chevron once to a temp PNG for QSS image:url()."""
    global _chevron_file
    if _chevron_file is None:
        path = Path(tempfile.gettempdir()) / "hideit_chevron.png"
        pixmap("chevron-down", T.S400, 12).save(str(path), "PNG")
        _chevron_file = path.as_posix()
    return _chevron_file


class Bridge(QObject):
    done = Signal(int, object, object)


class Page(QWidget):
    """Window background: slate-950-ish base with the 24px dot grid."""

    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(T.BG))
        p.setPen(QPen(QColor(56, 189, 248, 26), 1))
        for x in range(0, self.width(), 24):
            for y in range(0, self.height(), 24):
                p.drawPoint(x, y)


def centered(w: QWidget, max_w: int = 1280) -> QWidget:
    holder = QWidget()
    lay = hbox(holder)
    lay.addStretch(1)
    w.setMaximumWidth(max_w)
    lay.addWidget(w, 100)
    lay.addStretch(1)
    return holder


def style_seg(btn: QPushButton, icon_name: str, active: bool, on_css: str, on_color: str,
              off_color: str = T.S400, pad: str = "8px 16px", size: int = 12, radius: int = 8):
    css = on_css if active else "background:transparent;border:1px solid transparent;"
    color = on_color if active else off_color
    hover = "" if active else f"QPushButton:hover{{color:{T.S200};}}"
    btn.setStyleSheet(f"QPushButton{{{css}color:{color};border-radius:{radius}px;padding:{pad};"
                      f"font-family:{T.sans()};font-size:{size}px;font-weight:500;}}{hover}")
    btn.setIcon(icon(icon_name, color, 16))
    btn.setIconSize(QSize(16, 16))


class MainWindow(QMainWindow):
    def __init__(self, client: Client):
        super().__init__()
        self.client = client
        self.setWindowTitle("HideIt - Multi-Media Steganography Studio")
        self.resize(1320, 940)
        self.setMinimumSize(1020, 700)
        self.kind, self.mode, self.ptype = "image", "encode", "text"
        self.carrier, self.secret, self.decoded = None, None, None
        self._cbs, self._tok = {}, itertools.count()
        self.bridge = Bridge()
        self.bridge.done.connect(self._on_done)
        self._build()
        self.toasts = ToastHost(self.centralWidget())
        self.set_media_type("image")
        self.switch_mode("encode")

    # ----------------------------------------------------------- async helper
    def run_async(self, fn, cb):
        tok = next(self._tok)
        self._cbs[tok] = cb

        def work():
            try:
                self.bridge.done.emit(tok, fn(), None)
            except Exception as exc:  # delivered to the UI thread
                self.bridge.done.emit(tok, None, exc)
        threading.Thread(target=work, daemon=True).start()

    def _on_done(self, tok, res, err):
        cb = self._cbs.pop(tok, None)
        if cb:
            cb(res, err)

    def toast(self, msg, kind="info", ms=None):
        self.toasts.show(msg, kind, ms)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "toasts"):
            self.toasts.relayout()

    # ------------------------------------------------------------------ build
    def _build(self):
        page = Page()
        self.setCentralWidget(page)
        root = vbox(page)
        root.addWidget(self._build_header())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)
        scroll.viewport().setStyleSheet("background:transparent;")
        content = QWidget()
        content.setStyleSheet("background:transparent;")
        main = QWidget()
        main.setStyleSheet("background:transparent;")
        mlay = vbox(main, 0, (32, 32, 32, 32))
        mlay.addWidget(self._build_format_bar())
        mlay.addSpacing(24)
        grid = hbox(spacing=32)
        left, right = vbox(spacing=24), vbox(spacing=24)
        left.setAlignment(Qt.AlignmentFlag.AlignTop)
        right.setAlignment(Qt.AlignmentFlag.AlignTop)
        left.addWidget(self._build_carrier_card())
        left.addWidget(self._build_info_card())
        self.p_encode, self.p_decode, self.p_inspect = (self._build_encode(), self._build_decode(),
                                                        self._build_inspector())
        for p in (self.p_encode, self.p_decode, self.p_inspect):
            right.addWidget(p)
        grid.addLayout(left, 5)
        grid.addLayout(right, 7)
        mlay.addLayout(grid)
        mlay.addStretch(1)
        clay = vbox(content)
        clay.addWidget(centered(main))
        scroll.setWidget(content)
        content.setAutoFillBackground(False)
        root.addWidget(scroll, 1)
        root.addWidget(self._build_footer())

    def _build_header(self) -> QWidget:
        hdr = frame(f"background:rgba(10,13,20,0.9);border:none;border-bottom:1px solid {T.BORDER};")
        hdr.setFixedHeight(65)
        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        row = hbox(inner, 12, (32, 0, 32, 0))
        row.addWidget(LogoBadge())
        col = vbox(spacing=0)
        col.addWidget(GradientLabel("HideIt", 20, [T.EMERALD400, T.CYAN400, T.VIOLET400]))
        col.addWidget(lbl("Image, Audio & Video Steganography Workspace", 12, T.S400))
        row.addLayout(col)
        row.addStretch(1)
        tabs = frame(f"background:rgba(15,23,42,0.8);border:1px solid {T.S800};border-radius:12px;")
        trow = hbox(tabs, 0, (4, 4, 4, 4))
        self.tabs = {}
        for key, text, ico in (("encode", "Encode (Hide)", "lock"), ("decode", "Decode (Extract)", "unlock"),
                               ("inspector", "Inspector", "scan-eye")):
            b = QPushButton(" " + text)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.switch_mode(k))
            trow.addWidget(b)
            self.tabs[key] = (b, ico)
        row.addWidget(tabs)
        lay = vbox(hdr)
        lay.addWidget(centered(inner))
        return hdr

    def _build_format_bar(self) -> QWidget:
        bar = frame(f"background:{T.CARD};border:1px solid {T.BORDER};border-radius:16px;")
        row = hbox(bar, 8, (8, 8, 8, 8))
        row.addSpacing(4)
        row.addWidget(lbl("CARRIER MEDIA FORMAT:", 12, T.S400, 600))
        seg = frame(f"background:{T.S950};border:1px solid {T.BORDER};border-radius:12px;")
        srow = hbox(seg, 0, (4, 4, 4, 4))
        self.kind_btns = {}
        for key, text, ico in (("image", "Image (PNG/JPG)", "image"), ("audio", "Audio (WAV)", "music"),
                               ("video", "Video (MP4/WEBM)", "video")):
            b = QPushButton(" " + text)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.set_media_type(k))
            srow.addWidget(b)
            self.kind_btns[key] = (b, ico)
        row.addWidget(seg)
        row.addStretch(1)
        row.addWidget(icon_label("cpu", T.EMERALD400, 16))
        self.tech_label = lbl("", 12, T.S500, mono=True)
        row.addWidget(self.tech_label)
        row.addSpacing(8)
        return bar

    def _build_carrier_card(self) -> QWidget:
        card = frame(f"background:{T.CARD};border:1px solid {T.BORDER};border-radius:16px;")
        lay = vbox(card, 0, (20, 20, 20, 20))
        head = hbox(spacing=8)
        head.addWidget(icon_label("file-box", T.CYAN400, 20))
        self.zone_title = lbl("Carrier File Source", 16, T.S200, 600)
        head.addWidget(self.zone_title)
        head.addStretch(1)
        self.badge = lbl("PNG", 12, T.S300, mono=True)
        self.badge.setStyleSheet(self.badge.styleSheet() + f"background:{T.S800};border:1px solid {T.S700};"
                                 "border-radius:4px;padding:2px 8px;")
        self.badge.hide()
        head.addWidget(self.badge)
        lay.addLayout(head)
        lay.addSpacing(16)

        self.drop = DropZone()
        self.drop.clicked.connect(self.on_zone_click)
        self.drop.dropped.connect(self.load_path)
        self.drop.cleared.connect(self.reset_media)
        dl = vbox(self.drop, 12, (24, 24, 24, 24))
        dl.setAlignment(AlignCenter)

        self.prompt = QWidget()
        self.prompt.setStyleSheet("background:transparent;")
        pl = vbox(self.prompt, 12)
        circle = frame(f"background:rgba(30,41,59,0.8);border:1px solid {T.S700};border-radius:28px;")
        circle.setFixedSize(56, 56)
        cl = vbox(circle)
        cl.setAlignment(AlignCenter)
        cl.addWidget(icon_label("upload-cloud", T.CYAN400, 28))
        pl.addWidget(circle, 0, AlignCenter)
        txt = hbox(spacing=0)
        txt.addStretch(1)
        txt.addWidget(lbl("Drag & drop carrier or ", 14, T.S200, 500))
        txt.addWidget(lbl("browse", 14, T.CYAN400, 500))
        txt.addStretch(1)
        pl.addLayout(txt)
        self.formats_label = lbl("", 12, T.S500, align=AlignCenter)
        pl.addWidget(self.formats_label)
        dl.addWidget(self.prompt)

        self.preview = QWidget()
        self.preview.setStyleSheet("background:transparent;")
        vl = vbox(self.preview, 12)
        self.img_view = RoundedImage(220)
        vl.addWidget(self.img_view)
        self.audio_group = QWidget()
        al = vbox(self.audio_group, 12)
        info = frame(f"background:{T.S950};border:1px solid {T.S800};border-radius:12px;")
        irow = hbox(info, 12, (12, 12, 12, 12))
        ibox = frame("background:rgba(139,92,246,0.2);border:none;border-radius:8px;")
        ibox.setFixedSize(46, 46)
        ibl = vbox(ibox)
        ibl.setAlignment(AlignCenter)
        ibl.addWidget(icon_label("music-4", T.VIOLET400, 24))
        irow.addWidget(ibox)
        itx = vbox(spacing=2)
        self.audio_name = lbl("", 12, T.S200, 600)
        self.audio_meta = lbl("", 10, T.S500, mono=True)
        itx.addWidget(self.audio_name)
        itx.addWidget(self.audio_meta)
        irow.addLayout(itx, 1)
        al.addWidget(info)
        self.wave = Waveform()
        al.addWidget(self.wave)
        self.audio_player = MediaPlayerBox(video=False)
        al.addWidget(self.audio_player)
        vl.addWidget(self.audio_group)
        self.video_player = MediaPlayerBox(video=True)
        vl.addWidget(self.video_player)
        dl.addWidget(self.preview)
        lay.addWidget(self.drop)

        specs = frame(f"border:none;border-top:1px solid {T.BORDER};background:transparent;")
        sl = hbox(specs, 8, (0, 16, 0, 0))
        self.spec = {}
        for key, title, color in (("dim", "Attributes", T.S300), ("size", "File Size", T.S300),
                                  ("cap", "Est. Capacity", T.EMERALD400)):
            tile = frame(f"background:rgba(15,23,42,0.6);border:1px solid {T.S800};border-radius:8px;")
            tl = vbox(tile, 2, (8, 8, 8, 8))
            tl.addWidget(lbl(title.upper(), 10, T.S500, align=AlignCenter))
            v = lbl("--", 12, color, 500, mono=True, align=AlignCenter)
            tl.addWidget(v)
            sl.addWidget(tile, 1)
            self.spec[key] = v
        lay.addSpacing(16)
        lay.addWidget(specs)

        lay.addSpacing(16)
        grow = hbox()
        grow.addWidget(lbl("Payload Usage", 12, T.S400))
        grow.addSpacing(4)
        info_ico = icon_label("info", T.S500, 12)
        info_ico.setToolTip("Proportion of total carrier storage used")
        grow.addWidget(info_ico)
        grow.addStretch(1)
        self.cap_pct = lbl("0%", 12, T.CYAN400, mono=True)
        grow.addWidget(self.cap_pct)
        lay.addLayout(grow)
        lay.addSpacing(4)
        self.gauge = ProgressBar(10, T.S900, T.S800, [T.CYAN500, T.EMERALD400])
        lay.addWidget(self.gauge)
        return card

    def _build_info_card(self) -> QWidget:
        card = frame(f"background:rgba(18,24,36,0.6);border:1px solid {T.BORDER};border-radius:16px;")
        row = hbox(card, 12, (16, 16, 16, 16))
        row.addWidget(icon_label("cpu", T.CYAN400, 20), 0, Qt.AlignmentFlag.AlignTop)
        col = vbox(spacing=2)
        col.addWidget(lbl("Multi-Media Steganography Guide", 12, T.S200, 600))
        self.tech_desc = lbl("", 12, T.S400, wrap=True)
        col.addWidget(self.tech_desc)
        row.addLayout(col, 1)
        return card

    # ---- panels
    def _panel(self, ico, ico_color, title, sub, extra=None):
        panel = frame(f"background:{T.CARD};border:1px solid {T.BORDER};border-radius:16px;")
        lay = vbox(panel, 24, (24, 24, 24, 24))
        head = frame(f"border:none;border-bottom:1px solid {T.BORDER};background:transparent;")
        hl = hbox(head, 0, (0, 0, 0, 16))
        col = vbox(spacing=2)
        trow = hbox(spacing=8)
        trow.addWidget(icon_label(ico, ico_color, 20))
        trow.addWidget(lbl(title, 18, T.S100, 700))
        trow.addStretch(1)
        col.addLayout(trow)
        col.addWidget(lbl(sub, 12, T.S400))
        hl.addLayout(col, 1)
        if extra is not None:
            hl.addWidget(extra, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(head)
        return panel, lay

    def _combo(self, items, focus):
        c = QComboBox()
        c.addItems(items)
        c.setCursor(Qt.CursorShape.PointingHandCursor)
        c.setStyleSheet(
            f"QComboBox{{background:{T.S900};border:1px solid {T.S800};border-radius:8px;padding:8px 10px;"
            f"color:{T.S200};font-family:{T.sans()};font-size:12px;}}"
            f"QComboBox:focus,QComboBox:on{{border:1px solid {focus};}}"
            f"QComboBox:disabled{{color:{T.S600};}}"
            "QComboBox::drop-down{border:none;width:26px;}"
            f"QComboBox::down-arrow{{image:url({chevron_url()});width:12px;height:12px;}}")
        return c

    def _build_encode(self) -> QWidget:
        toggle = frame(f"background:{T.S900};border:1px solid {T.S800};border-radius:8px;")
        trow = hbox(toggle, 0, (4, 4, 4, 4))
        self.ptype_btns = {}
        for key, text in (("text", "Text Message"), ("file", "Secret File")):
            b = QPushButton(text)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.set_payload_type(k))
            trow.addWidget(b)
            self.ptype_btns[key] = b
        panel, lay = self._panel("file-plus", T.EMERALD400, "Embed Secret Payload",
                                 "Hide text messages or confidential files inside carrier media", toggle)

        # text payload
        self.g_text = QWidget()
        gl = vbox(self.g_text, 8)
        top = hbox()
        top.addWidget(lbl("Secret Text Message", 12, T.S300, 500))
        top.addStretch(1)
        self.char_count = lbl("0 chars", 12, T.S500, mono=True)
        top.addWidget(self.char_count)
        gl.addLayout(top)
        self.secret_text = QTextEdit()
        self.secret_text.setAcceptRichText(False)
        self.secret_text.setPlaceholderText("Type your confidential message here...")
        set_placeholder(self.secret_text)
        self.secret_text.setFixedHeight(112)
        self.secret_text.setStyleSheet(
            f"QTextEdit{{background:rgba(15,23,42,0.9);border:1px solid {T.S800};border-radius:12px;"
            f"padding:8px;color:{T.S200};font-family:{T.mono()};font-size:14px;"
            f"selection-background-color:{T.CYAN500};selection-color:{T.S900};}}"
            "QTextEdit:focus{border:1px solid rgba(16,185,129,0.6);}")
        self.secret_text.textChanged.connect(self.update_gauge)
        gl.addWidget(self.secret_text)
        lay.addWidget(self.g_text)

        # file payload
        self.g_file = QWidget()
        fl = vbox(self.g_file, 8)
        fl.addWidget(lbl("Select Secret File (PDF, TXT, ZIP, Audio, etc.)", 12, T.S300, 500))
        frow = hbox(spacing=12)
        css, _ = ("background:%s;border:1px solid %s;border-radius:12px;padding:8px 16px;color:%s;" % (
            T.S900, T.S700, T.S200), "")
        choose = pill_button("Choose Payload File", "paperclip", T.CYAN400, css, f"background:{T.S800};")
        choose.clicked.connect(self.pick_secret)
        frow.addWidget(choose)
        self.secret_name = lbl("No file chosen", 12, T.S400, mono=True)
        frow.addWidget(self.secret_name, 1)
        fl.addLayout(frow)
        self.g_file.hide()
        lay.addWidget(self.g_file)

        # AES
        aes = frame(f"background:rgba(15,23,42,0.5);border:1px solid {T.S800};border-radius:12px;")
        al = vbox(aes, 12, (16, 16, 16, 16))
        arow = hbox(spacing=8)
        self.aes_check = Check()
        self.aes_check.toggled.connect(self.toggle_aes)
        arow.addWidget(self.aes_check)
        arow.addWidget(icon_label("key-round", T.EMERALD400, 16))
        arow.addWidget(lbl("AES-256 Passphrase Encryption", 12, T.S200, 600))
        arow.addStretch(1)
        arow.addWidget(lbl("OPTIONAL", 10, T.S500, mono=True))
        al.addLayout(arow)
        self.aes_fields = QWidget()
        afl = vbox(self.aes_fields, 12, (0, 8, 0, 0))
        self.enc_pass = PasswordEdit("Enter strong encryption passphrase")
        style_edit(self.enc_pass, T.S950, T.S800, 8, 8, 12, T.EMERALD500)
        self.enc_pass.textChanged.connect(self.check_strength)
        afl.addWidget(self.enc_pass)
        srow = hbox()
        srow.addWidget(lbl("Strength", 10, T.S400))
        srow.addStretch(1)
        self.strength_label = lbl("None", 10, T.S500, mono=True)
        srow.addWidget(self.strength_label)
        afl.addLayout(srow)
        self.strength_bar = ProgressBar(4, T.S950, None, [T.S700])
        afl.addWidget(self.strength_bar)
        self.aes_fields.hide()
        al.addWidget(self.aes_fields)
        lay.addWidget(aes)

        # bit depth + container
        two = hbox(spacing=16)
        c1 = vbox(spacing=4)
        r1 = hbox(spacing=4)
        r1.addWidget(lbl("Carrier LSB Bit Depth", 12, T.S300, 500))
        r1.addWidget(icon_label("layers", T.S500, 12))
        r1.addStretch(1)
        c1.addLayout(r1)
        self.depth = self._combo(["1 Bit per sample/channel (Maximum Quality)",
                                  "2 Bits per sample/channel (High Capacity)",
                                  "3 Bits per sample/channel (Max Storage)"], T.EMERALD500)
        self.depth.currentIndexChanged.connect(self.update_gauge)
        c1.addWidget(self.depth)
        c2 = vbox(spacing=4)
        c2.addWidget(lbl("Output Target Container", 12, T.S300, 500))
        self.container = _readonly_field()
        c2.addWidget(self.container)
        two.addLayout(c1, 1)
        two.addLayout(c2, 1)
        lay.addLayout(two)

        css, hover = gradient_css([T.EMERALD500, T.CYAN500, T.SKY500], [T.EMERALD400, T.CYAN400, T.SKY400])
        go = pill_button("Encode & Save Modified Media", "lock", T.S950, css + f"color:{T.S950};border:none;"
                         "border-radius:12px;padding:13px 16px;", hover, size=16, weight=700, icon_px=20)
        go.clicked.connect(self.do_encode)
        lay.addWidget(go)
        return panel

    def _build_decode(self) -> QWidget:
        panel, lay = self._panel("unlock", T.CYAN400, "Extract Embedded Data",
                                 "Scan modified carrier file and extract hidden message or file payload")
        col = vbox(spacing=4)
        col.addWidget(lbl("Decryption Passphrase (If Passphrase Protected)", 12, T.S300, 500))
        self.dec_pass = PasswordEdit("Enter encryption passphrase")
        style_edit(self.dec_pass, T.S900, T.S800, 12, 10, 12, T.CYAN500)
        col.addWidget(self.dec_pass)
        lay.addLayout(col)
        col2 = vbox(spacing=4)
        col2.addWidget(lbl("Carrier Extraction Bit Depth", 12, T.S300, 500))
        self.dec_depth = self._combo(["Auto-detect from payload header (Default)"], T.CYAN500)
        col2.addWidget(self.dec_depth)
        lay.addLayout(col2)
        css, hover = gradient_css([T.CYAN500, T.SKY500], [T.CYAN400, T.SKY400])
        go = pill_button("Extract Payload", "scan-text", T.S950, css + f"color:{T.S950};border:none;"
                         "border-radius:12px;padding:13px 16px;", hover, size=16, weight=700, icon_px=20)
        go.clicked.connect(self.do_decode)
        lay.addWidget(go)

        self.result_box = frame(f"border:none;border-top:1px solid {T.BORDER};background:transparent;")
        rl = vbox(self.result_box, 12, (0, 16, 0, 0))
        top = hbox(spacing=6)
        top.addWidget(icon_label("check-circle", T.EMERALD400, 16))
        top.addWidget(lbl("Payload Extracted Successfully", 12, T.EMERALD400, 600))
        top.addStretch(1)
        self.type_badge = lbl("TEXT MESSAGE", 10, T.EMERALD400, mono=True)
        self.type_badge.setStyleSheet(self.type_badge.styleSheet() + "background:rgba(16,185,129,0.1);"
                                      "border:1px solid rgba(16,185,129,0.2);border-radius:4px;padding:2px 8px;")
        top.addWidget(self.type_badge)
        rl.addLayout(top)

        self.res_text = QWidget()
        tl = vbox(self.res_text, 8)
        self.out_text = QTextEdit()
        self.out_text.setReadOnly(True)
        self.out_text.setMaximumHeight(192)
        self.out_text.setMinimumHeight(80)
        self.out_text.setStyleSheet(
            f"QTextEdit{{background:{T.S950};border:1px solid {T.S800};border-radius:12px;padding:8px;"
            f"color:{T.S200};font-family:{T.mono()};font-size:12px;}}")
        tl.addWidget(self.out_text)
        copy = pill_button("Copy Text", "copy", T.CYAN400, f"background:{T.S900};border:1px solid {T.S700};"
                           f"border-radius:8px;padding:6px 12px;color:{T.S200};", f"background:{T.S800};")
        copy.clicked.connect(self.copy_text)
        tl.addWidget(copy, 0, Qt.AlignmentFlag.AlignLeft)
        rl.addWidget(self.res_text)

        self.res_file = frame(f"background:{T.S950};border:1px solid {T.S800};border-radius:12px;")
        fl = hbox(self.res_file, 12, (16, 16, 16, 16))
        ib = frame("background:rgba(6,182,212,0.1);border:1px solid rgba(6,182,212,0.2);border-radius:8px;")
        ib.setFixedSize(42, 42)
        ibl = vbox(ib)
        ibl.setAlignment(AlignCenter)
        ibl.addWidget(icon_label("file-down", T.CYAN400, 24))
        fl.addWidget(ib)
        nl = vbox(spacing=2)
        self.file_name = lbl("extracted_file.bin", 12, T.S200, 500)
        self.file_size = lbl("0 KB", 10, T.S500)
        nl.addWidget(self.file_name)
        nl.addWidget(self.file_size)
        fl.addLayout(nl, 1)
        dl = pill_button("Download", "download", T.S950, f"background:{T.EMERALD500};border:none;color:{T.S950};"
                         "border-radius:8px;padding:8px 16px;", f"background:{T.EMERALD400};",
                         weight=700)
        dl.clicked.connect(self.save_extracted)
        fl.addWidget(dl)
        rl.addWidget(self.res_file)
        self.result_box.hide()
        lay.addWidget(self.result_box)
        return panel

    def _build_inspector(self) -> QWidget:
        panel, lay = self._panel("scan-eye", T.SKY400, "Stego Artifact & Bit Analysis",
                                 "Visualize bit planes for images or audio frequency noise density")
        col = vbox(spacing=8)
        col.addWidget(lbl("Visualization Filter", 12, T.S300, 500))
        grid = hbox(spacing=8)
        for mode, text, color in (("rgb", "Standard View", T.S300), ("lsb1", "LSB Plane 0", T.CYAN400),
                                  ("lsb2", "LSB Plane 1", T.CYAN400), ("noise", "Noise Heatmap", T.EMERALD400)):
            b = QPushButton(text)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(f"QPushButton{{background:{T.S900};border:1px solid {T.S800};border-radius:8px;"
                            f"padding:8px;color:{color};font-family:{T.mono()};font-size:12px;}}"
                            f"QPushButton:hover{{border:1px solid {T.S700};}}")
            b.clicked.connect(lambda _=False, m=mode: self.render_inspector(m))
            grid.addWidget(b, 1)
        col.addLayout(grid)
        lay.addLayout(col)

        area = frame(f"background:{T.S950};border:1px solid {T.S800};border-radius:12px;")
        area.setMinimumHeight(250)
        al = vbox(area, 8, (12, 12, 12, 12))
        al.setAlignment(AlignCenter)
        self.insp_img = RoundedImage(300)
        self.insp_img.hide()
        al.addWidget(self.insp_img)
        self.insp_hint = lbl("Upload carrier media to analyze artifacts", 12, T.S600, align=AlignCenter)
        al.addWidget(self.insp_hint)
        self.insp_stats = lbl("", 10, T.S500, mono=True, align=AlignCenter)
        al.addWidget(self.insp_stats)
        lay.addWidget(area)
        return panel

    def _build_footer(self) -> QWidget:
        foot = frame(f"background:rgba(10,13,20,0.9);border:none;border-top:1px solid rgba(30,41,59,0.6);")
        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        row = hbox(inner, 8, (32, 16, 32, 16))
        row.addWidget(icon_label("shield", T.EMERALD400, 16))
        row.addWidget(lbl("HideIt Steganography Studio \u2022 Image, Audio & Video Secure Workspace", 12, T.S500))
        row.addStretch(1)
        row.addWidget(lbl("100% Local Desktop Operations \u2022 No Data Leaves This Machine", 12, T.S500))
        lay = vbox(foot)
        lay.addWidget(centered(inner))
        return foot

    # ------------------------------------------------------------ navigation
    def switch_mode(self, mode: str):
        self.mode = mode
        styles = {
            "encode": ([T.EMERALD500, T.CYAN500], "Carrier File Source"),
            "decode": ([T.CYAN500, T.SKY500], "Stego Media Source"),
            "inspector": ([T.SKY500, T.INDIGO500], "Inspection Carrier Source"),
        }
        for key, (btn, ico) in self.tabs.items():
            grad, _ = gradient_css(styles[key][0])
            style_seg(btn, ico, key == mode, grad + "border:none;", T.S950, pad="6px 14px", size=14)
        self.zone_title.setText(styles[mode][1])
        self.p_encode.setVisible(mode == "encode")
        self.p_decode.setVisible(mode == "decode")
        self.p_inspect.setVisible(mode == "inspector")
        if mode == "inspector":
            self.render_inspector("rgb", silent=True)

    def set_media_type(self, kind: str):
        self.kind = kind
        colors = {"image": ("rgba(6,182,212,0.2)", T.CYAN300, "rgba(6,182,212,0.4)"),
                  "audio": ("rgba(139,92,246,0.2)", T.VIOLET300, "rgba(139,92,246,0.4)"),
                  "video": ("rgba(16,185,129,0.2)", T.EMERALD300, "rgba(16,185,129,0.4)")}
        for key, (btn, ico) in self.kind_btns.items():
            bg, fg, bd = colors[key]
            style_seg(btn, ico, key == kind, f"background:{bg};border:1px solid {bd};", fg,
                      pad="8px 16px", size=12)
        formats, tech, container, desc, _ = KIND_TEXT[kind]
        self.formats_label.setText(formats)
        self.tech_label.setText(tech)
        self.container.setText(container)
        self.tech_desc.setText(desc)
        self.depth.setEnabled(kind != "video")
        self.reset_media()

    def set_payload_type(self, ptype: str):
        self.ptype = ptype
        on = (f"background:rgba(16,185,129,0.2);border:1px solid rgba(16,185,129,0.3);color:{T.EMERALD300};"
              "border-radius:6px;padding:4px 12px;")
        off = f"background:transparent;border:1px solid transparent;color:{T.S400};border-radius:6px;padding:4px 12px;"
        for key, b in self.ptype_btns.items():
            b.setStyleSheet(f"QPushButton{{{on if key == ptype else off}font-family:{T.sans()};font-size:12px;"
                            f"font-weight:500;}}" + ("" if key == ptype else f"QPushButton:hover{{color:{T.S200};}}"))
        self.g_text.setVisible(ptype == "text")
        self.g_file.setVisible(ptype == "file")
        self.update_gauge()

    # --------------------------------------------------------------- carrier
    def on_zone_click(self):
        if not self.carrier:
            self.browse_carrier()

    def browse_carrier(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select carrier file", "", KIND_TEXT[self.kind][4] +
                                              ";;All files (*.*)")
        if path:
            self.load_path(path)

    def load_path(self, path: str):
        self.toast("Loading carrier\u2026", "info", 20000)
        self.run_async(lambda: self.client.load_carrier(path, self.kind), self._carrier_loaded)

    def _carrier_loaded(self, res, err):
        if err:
            return self.toast(str(err), "error")
        self.apply_carrier(res)

    def apply_carrier(self, r: dict):
        self.carrier = r
        kind = r["kind"]
        self.prompt.hide()
        self.preview.show()
        self.img_view.setVisible(kind == "image")
        self.audio_group.setVisible(kind == "audio")
        self.video_player.setVisible(kind == "video")
        self.drop.trash.show()
        self.drop.trash.raise_()
        self.drop.setCursor(Qt.CursorShape.ArrowCursor)
        if kind == "image":
            pm = QPixmap()
            pm.loadFromData(base64.b64decode(r["preview_png"]))
            self.img_view.set_pixmap(pm)
        elif kind == "audio":
            self.audio_name.setText(r["name"])
            self.audio_meta.setText(f"{r['meta']} \u2022 {r['size'] / 1024:.1f} KB")
            self.wave.set_peaks(r["peaks"])
            self.audio_player.load(r["path"])
        else:
            self.video_player.load(r["path"])
        self.spec["dim"].setText(r["dim"])
        self.spec["size"].setText(f"{r['size'] / 1024:.1f} KB")
        self.badge.setText(r["ext"])
        self.badge.show()
        self.update_gauge()
        self.toast(f"{kind.capitalize()} carrier loaded", "success")
        if self.mode == "inspector":
            self.render_inspector("rgb", silent=True)

    def reset_media(self):
        if self.carrier:
            cid = self.carrier["id"]
            self.run_async(lambda: self.client.clear_carrier(cid), lambda *_: None)
        self.carrier = None
        self.audio_player.stop()
        self.video_player.stop()
        self.preview.hide()
        self.prompt.show()
        self.drop.trash.hide()
        self.drop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.badge.hide()
        self.spec["dim"].setText("--")
        self.spec["size"].setText("-- KB")
        self.spec["cap"].setText("0 KB")
        self.cap_pct.setText("0%")
        self.gauge.set_value(0)
        self.insp_img.hide()
        self.insp_stats.setText("")
        self.insp_hint.show()

    def pick_secret(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select secret file", "", "All files (*.*)")
        if not path:
            return
        size = Path(path).stat().st_size
        self.secret = {"path": path, "name": Path(path).name, "size": size}
        self.secret_name.setText(f"{self.secret['name']} ({size / 1024:.1f} KB)")
        self.update_gauge()

    # ---------------------------------------------------------- live widgets
    def toggle_aes(self, on: bool):
        self.aes_fields.setVisible(on)
        self.update_gauge()

    def check_strength(self, text: str):
        score = 0
        score += 25 if len(text) > 5 else 0
        score += 25 if len(text) > 9 else 0
        score += 25 if any(c.isupper() for c in text) else 0
        score += 25 if any(c.isdigit() or c in "!@#$%^&*" for c in text) else 0
        if score == 0:
            label, col = "None", T.S500
            bar = T.S700
        elif score <= 50:
            label, col, bar = "Weak", T.RED400, T.RED500
        elif score <= 75:
            label, col, bar = "Medium", T.AMBER400, T.AMBER500
        else:
            label, col, bar = "Strong", T.EMERALD400, T.EMERALD500
        self.strength_label.setText(label)
        self.strength_label.setStyleSheet(f"background:transparent;border:none;color:{col};"
                                          f"font-family:{T.mono()};font-size:10px;")
        self.strength_bar.set_value(score, [bar])

    def update_gauge(self, *_):
        cap, unlimited = 0, False
        depth = self.depth.currentIndex() + 1
        if self.carrier:
            if self.carrier["kind"] == "video":
                unlimited = True
            else:
                cap = self.carrier["cap"].get(str(depth), 0)
        self.spec["cap"].setText("Unlimited" if unlimited else f"{cap / 1024:.1f} KB")
        text = self.secret_text.toPlainText()
        self.char_count.setText(f"{len(text)} chars")
        payload = 0
        if self.ptype == "text":
            n = len(text.encode("utf-8"))
            payload = n + 3 if n else 0
        elif self.secret:
            payload = self.secret["size"] + 3 + len(self.secret["name"].encode("utf-8"))
        if payload and self.aes_check.isChecked():
            payload += AES_OVERHEAD
        usage = min(100.0, payload * 100 / cap) if cap > 0 else 0.0
        self.gauge.set_value(usage)
        self.cap_pct.setText(f"{usage:.1f}%")

    # --------------------------------------------------------------- actions
    def do_encode(self):
        is_file = self.ptype == "file"
        text = self.secret_text.toPlainText()
        if not is_file and not text:
            return self.toast("Please enter a secret message!", "error")
        if is_file and not self.secret:
            return self.toast("Please select a payload file!", "error")
        if not self.carrier:
            return self.toast(f"Please upload a {self.kind} carrier first!", "error")
        aes, pw = self.aes_check.isChecked(), self.enc_pass.text()
        if aes and not pw:
            return self.toast("Please enter an encryption passphrase!", "error")
        c = self.carrier
        ext = ".png" if c["kind"] == "image" else Path(c["path"]).suffix
        default = str(Path(c["path"]).with_name(f"{Path(c['path']).stem}_hideit{ext}"))
        out, _ = QFileDialog.getSaveFileName(self, "Save modified media", default,
                                             f"{ext[1:].upper()} (*{ext})")
        if not out:
            return
        self.toast("Encoding\u2026 deriving AES-256 key" if aes else "Encoding\u2026", "info", 60000)
        args = dict(id=c["id"], output_path=out, is_file=is_file, text=text,
                    secret_path=self.secret["path"] if self.secret else "", aes=aes, passphrase=pw,
                    depth=self.depth.currentIndex() + 1)
        self.run_async(lambda: self.client.encode(**args), self._encoded)

    def _encoded(self, res, err):
        if err:
            return self.toast(str(err), "error")
        extra = (" \u2022 AES-256-GCM" if res["encrypted"] else "") + (
            f" \u2022 {res['depth']}-bit LSB" if res["kind"] != "video" else "")
        self.toast(f"Stego {res['kind']} saved: {res['name']}{extra}", "success")

    def do_decode(self):
        if not self.carrier:
            return self.toast(f"Upload a stego {self.kind} file first!", "error")
        cid, pw = self.carrier["id"], self.dec_pass.text()
        self.toast("Scanning carrier\u2026", "info", 60000)
        self.run_async(lambda: self.client.decode(cid, pw), self._decoded)

    def _decoded(self, res, err):
        if err:
            self.result_box.hide()
            return self.toast(str(err), "error")
        self.decoded = res
        self.result_box.show()
        if res["is_file"]:
            self.type_badge.setText("FILE PAYLOAD")
            self.file_name.setText(res["name"])
            self.file_size.setText(f"{res['size'] / 1024:.1f} KB")
            self.res_text.hide()
            self.res_file.show()
        else:
            self.type_badge.setText("TEXT MESSAGE")
            self.out_text.setPlainText(res["text"])
            self.res_file.hide()
            self.res_text.show()
        self.toast("Payload successfully extracted!", "success")

    def copy_text(self):
        text = self.out_text.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.toast("Copied to clipboard!", "success")

    def save_extracted(self):
        if not self.decoded:
            return
        out, _ = QFileDialog.getSaveFileName(self, "Save extracted file", self.decoded.get("name", "payload.bin"))
        if not out:
            return
        rid = self.decoded["result_id"]
        self.run_async(lambda: self.client.save_result(rid, out),
                       lambda r, e: self.toast(str(e), "error") if e else self.toast(f"Saved {r['name']}", "success"))

    def render_inspector(self, mode: str, silent: bool = False):
        if not self.carrier or self.carrier["kind"] == "video":
            if not silent:
                self.toast("Upload an image or audio carrier to analyze", "error")
            return
        cid = self.carrier["id"]

        def done(res, err):
            if err:
                return None if silent else self.toast(str(err), "error")
            pm = QPixmap()
            pm.loadFromData(base64.b64decode(res["png"]))
            self.insp_img.set_pixmap(pm)
            self.insp_img.show()
            self.insp_hint.hide()
            self.insp_stats.setText(f"{res['header']}  \u2022  chi\u00b2 {res['chi2']}  \u2022  "
                                    f"LSB embedding likelihood {res['likelihood']}%")
        self.run_async(lambda: self.client.inspect(cid, mode), done)


def _readonly_field():
    from PySide6.QtWidgets import QLineEdit
    le = QLineEdit()
    le.setReadOnly(True)
    style_edit(le, "rgba(15,23,42,0.6)", T.S800, 8, 8, 8, T.S800, color=T.S400)
    return le


def run(url: str | None = None, token: str | None = None) -> int:
    app = QApplication(sys.argv)
    T.load_fonts()
    app.setStyleSheet(T.app_qss())
    app.setFont(QFont(T.SANS))
    if url is None:  # embedded backend (same process, separate thread)
        import secrets as _s
        from backend.server import start_in_thread
        token = _s.token_urlsafe(16)
        _srv, port = start_in_thread(token)
        url = f"http://127.0.0.1:{port}"
    client = Client(url, token or "")
    win = MainWindow(client)
    win.show()
    return app.exec()
