"""Reusable styled widgets that reproduce the HideIt web design in Qt."""
from __future__ import annotations

import itertools

from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath,
                           QPalette, QPen, QPixmap)
from PySide6.QtWidgets import (QAbstractButton, QFrame, QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton, QSlider, QVBoxLayout, QWidget)

from . import theme as T
from .icons import icon, pixmap

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtMultimediaWidgets import QVideoWidget
    HAVE_MM = True
except Exception:  # Qt Multimedia missing: previews fall back to a static note
    HAVE_MM = False

_ids = itertools.count()
AlignCenter = Qt.AlignmentFlag.AlignCenter


# ------------------------------------------------------------------ helpers
def frame(css: str) -> QFrame:
    """QFrame whose stylesheet is scoped to itself only (never leaks to children)."""
    f = QFrame()
    name = f"f{next(_ids)}"
    f.setObjectName(name)
    f.setStyleSheet(f"#{name}{{{css}}}")
    return f


def vbox(parent=None, spacing=0, margins=(0, 0, 0, 0)) -> QVBoxLayout:
    lay = QVBoxLayout(parent) if parent is not None else QVBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(*margins)
    return lay


def hbox(parent=None, spacing=0, margins=(0, 0, 0, 0)) -> QHBoxLayout:
    lay = QHBoxLayout(parent) if parent is not None else QHBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(*margins)
    return lay


def lbl(text="", size=12, color=T.S400, weight=400, mono=False, wrap=False, align=None) -> QLabel:
    w = QLabel(text)
    fam = T.mono() if mono else T.sans()
    w.setStyleSheet(f"background:transparent;border:none;color:{color};font-family:{fam};"
                    f"font-size:{size}px;font-weight:{weight};")
    w.setWordWrap(wrap)
    if align is not None:
        w.setAlignment(align)
    return w


def icon_label(name: str, color: str, size: int = 16) -> QLabel:
    w = QLabel()
    w.setPixmap(pixmap(name, color, size))
    w.setFixedSize(size, size)
    w.setStyleSheet("background:transparent;border:none;")
    return w


def set_icon_label(w: QLabel, name: str, color: str, size: int = 16) -> None:
    w.setPixmap(pixmap(name, color, size))


def pill_button(text: str, icon_name: str | None, icon_color: str, css: str, hover_css: str = "",
                size: int = 12, weight: int = 500, icon_px: int = 16) -> QPushButton:
    b = QPushButton((" " + text) if icon_name else text)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(f"QPushButton{{font-family:{T.sans()};font-size:{size}px;font-weight:{weight};{css}}}"
                    f"QPushButton:hover{{{hover_css}}}")
    if icon_name:
        b.setIcon(icon(icon_name, icon_color, icon_px))
        b.setIconSize(QSize(icon_px, icon_px))
    return b


def gradient_css(stops: list[str], hover: list[str] | None = None) -> tuple[str, str]:
    def g(cols):
        n = len(cols) - 1
        parts = ",".join(f"stop:{i / n:.2f} {c}" for i, c in enumerate(cols))
        return f"qlineargradient(x1:0,y1:0,x2:1,y2:0,{parts})"
    return f"background:{g(stops)};", f"background:{g(hover or stops)};"


def style_edit(le: QLineEdit, bg: str, border: str, radius: int, pv: int, ph: int, focus: str,
               size: int = 12, color: str = T.S200) -> None:
    le.setStyleSheet(
        f"QLineEdit{{background:{bg};border:1px solid {border};border-radius:{radius}px;"
        f"padding:{pv}px {ph}px;color:{color};font-family:{T.mono()};font-size:{size}px;"
        f"selection-background-color:{T.CYAN500};selection-color:{T.S900};}}"
        f"QLineEdit:focus{{border:1px solid {focus};}}")


def set_placeholder(w, color: str = T.S600) -> None:
    pal = w.palette()
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(color))
    w.setPalette(pal)


# ------------------------------------------------------------ painted widgets
class GradientLabel(QWidget):
    """Text filled with a horizontal gradient (CSS bg-clip-text equivalent)."""

    def __init__(self, text: str, px: int, colors: list[str]):
        super().__init__()
        self._text, self._colors = text, colors
        self._font = QFont(T.SANS)
        self._font.setPixelSize(px)
        self._font.setWeight(QFont.Weight.Bold)
        fm = QFontMetrics(self._font)
        self.setFixedSize(fm.horizontalAdvance(text) + 6, fm.height() + 2)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setFont(self._font)
        g = QLinearGradient(0, 0, self.width(), 0)
        n = len(self._colors) - 1
        for i, c in enumerate(self._colors):
            g.setColorAt(i / n, QColor(c))
        p.setPen(QPen(QBrush(g), 1))
        p.drawText(0, p.fontMetrics().ascent() + 1, self._text)


class LogoBadge(QWidget):
    """Gradient rounded square with the shield-lock mark (header logo)."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(40, 40)
        fx = QGraphicsDropShadowEffect(self)
        fx.setBlurRadius(18)
        fx.setOffset(0, 4)
        fx.setColor(QColor(6, 182, 212, 70))
        self.setGraphicsEffect(fx)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        g = QLinearGradient(0, 40, 40, 0)  # to top-right
        g.setColorAt(0, QColor(T.EMERALD500))
        g.setColorAt(0.5, QColor(T.CYAN500))
        g.setColorAt(1, QColor(T.VIOLET500))
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, 40, 40), 8, 8)
        p.fillPath(path, QBrush(g))
        p.drawPixmap(8, 8, pixmap("shield-lock", T.S950, 24))


class ProgressBar(QWidget):
    """Rounded track with a gradient fill (capacity gauge / strength meter)."""

    def __init__(self, height: int, track: str, border: str | None, colors: list[str]):
        super().__init__()
        self.setFixedHeight(height)
        self._track, self._border, self._colors, self._v = track, border, colors, 0.0

    def set_value(self, pct: float, colors: list[str] | None = None):
        self._v = max(0.0, min(100.0, pct))
        if colors:
            self._colors = colors
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        rad = r.height() / 2
        path = QPainterPath()
        path.addRoundedRect(r, rad, rad)
        p.fillPath(path, QColor(self._track))
        if self._v > 0:
            p.save()
            p.setClipPath(path)
            w = r.width() * self._v / 100
            g = QLinearGradient(r.left(), 0, r.left() + max(w, 1), 0)
            n = max(1, len(self._colors) - 1)
            for i, c in enumerate(self._colors):
                g.setColorAt(i / n, QColor(c))
            p.fillRect(QRectF(r.left(), r.top(), w, r.height()), QBrush(g))
            p.restore()
        if self._border:
            p.setPen(QPen(QColor(self._border), 1))
            p.drawRoundedRect(r, rad, rad)


class Check(QAbstractButton):
    """16px rounded checkbox (slate-950 box, emerald when checked)."""

    def __init__(self):
        super().__init__()
        self.setCheckable(True)
        self.setFixedSize(16, 16)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        on = self.isChecked()
        p.setBrush(QColor(T.EMERALD500 if on else T.S950))
        p.setPen(QPen(QColor(T.EMERALD500 if on else T.S700), 1))
        p.drawRoundedRect(QRectF(0.5, 0.5, 15, 15), 4, 4)
        if on:
            p.setPen(QPen(QColor(T.S950), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPolyline([QPointF(4, 8.5), QPointF(7, 11.5), QPointF(12, 5)])


class RoundedImage(QWidget):
    """Image shown at natural size (max height), rounded corners + slate-800 border."""

    def __init__(self, max_h: int):
        super().__init__()
        self._pm, self._max_h = None, max_h
        self.setFixedHeight(max_h)

    def set_pixmap(self, pm: QPixmap | None):
        self._pm = pm
        if pm is not None and not pm.isNull():
            self.setFixedHeight(int(min(self._max_h, pm.height() / max(pm.devicePixelRatio(), 1))) + 2)
        self.update()

    def paintEvent(self, _e):
        if self._pm is None or self._pm.isNull():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        pw, ph = self._pm.width(), self._pm.height()
        scale = min(1.0, (self.width() - 2) / pw, (self.height() - 2) / ph)
        w, h = pw * scale, ph * scale
        r = QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)
        path = QPainterPath()
        path.addRoundedRect(r, 8, 8)
        p.setClipPath(path)
        p.drawPixmap(r, self._pm, QRectF(self._pm.rect()))
        p.setClipping(False)
        p.setPen(QPen(QColor(T.S800), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, 8, 8)


class Waveform(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(64)
        self._peaks = []

    def set_peaks(self, peaks):
        self._peaks = peaks or []
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        p.setBrush(QColor(T.S900))
        p.setPen(QPen(QColor(T.S800), 1))
        p.drawRoundedRect(r, 8, 8)
        n = len(self._peaks)
        if not n:
            return
        p.setPen(QPen(QColor(T.VIOLET500), 1.5))
        mid, amp = self.height() / 2, self.height() / 2 - 4
        for i, (lo, hi) in enumerate(self._peaks):
            x = 4 + (self.width() - 8) * i / max(1, n - 1)
            p.drawLine(QPointF(x, mid - hi * amp), QPointF(x, mid - lo * amp + 1))


# --------------------------------------------------------------- composites
class PasswordEdit(QLineEdit):
    """Password field with the eye toggle on the right."""

    def __init__(self, placeholder: str):
        super().__init__()
        self.setEchoMode(QLineEdit.EchoMode.Password)
        self.setPlaceholderText(placeholder)
        set_placeholder(self)
        self._act = self.addAction(icon("eye", T.S500, 16), QLineEdit.ActionPosition.TrailingPosition)
        self._act.triggered.connect(self._toggle)

    def _toggle(self):
        hidden = self.echoMode() == QLineEdit.EchoMode.Password
        self.setEchoMode(QLineEdit.EchoMode.Normal if hidden else QLineEdit.EchoMode.Password)
        self._act.setIcon(icon("eye-off" if hidden else "eye", T.S500, 16))


class DropZone(QFrame):
    """Dashed drag-and-drop area; emits clicked() and dropped(path)."""
    clicked = Signal()
    dropped = Signal(str)
    cleared = Signal()

    _BASE = "border:2px dashed #334155;border-radius:12px;background:rgba(15,23,42,0.4);"

    def __init__(self):
        super().__init__()
        self.setObjectName("dropzone")
        self.setMinimumHeight(260)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._style(False)
        self.trash = QPushButton(self)
        self.trash.setFixedSize(30, 30)
        self.trash.setIcon(icon("trash-2", "#ffffff", 16))
        self.trash.setIconSize(QSize(16, 16))
        self.trash.setCursor(Qt.CursorShape.PointingHandCursor)
        self.trash.setStyleSheet(f"QPushButton{{background:rgba(2,6,23,0.8);border:1px solid {T.S700};"
                                 "border-radius:8px;}QPushButton:hover{background:rgba(239,68,68,0.8);}")
        self.trash.clicked.connect(self.cleared.emit)
        self.trash.hide()

    def _style(self, hot: bool):
        hover = "border:2px dashed rgba(6,182,212,0.5);background:rgba(15,23,42,0.7);"
        self.setStyleSheet(f"#dropzone{{{hover if hot else self._BASE}}}#dropzone:hover{{{hover}}}")

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._style(True)

    def dragLeaveEvent(self, _e):
        self._style(False)

    def dropEvent(self, e):
        self._style(False)
        urls = e.mimeData().urls()
        if urls:
            self.dropped.emit(urls[0].toLocalFile())

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.trash.move(self.width() - 38, 8)
        self.trash.raise_()


def _fmt_time(ms: int) -> str:
    s = max(0, int(ms // 1000))
    return f"{s // 60}:{s % 60:02d}"


class MediaPlayerBox(QWidget):
    """Audio/video preview with play/pause, seek bar and time (QtMultimedia)."""

    def __init__(self, video: bool):
        super().__init__()
        self.player = None
        lay = vbox(self, 8)
        if not HAVE_MM:
            lay.addWidget(lbl("Media playback is unavailable in this build.", 11, T.S500))
            return
        self.player = QMediaPlayer(self)
        self._out = QAudioOutput(self)
        self.player.setAudioOutput(self._out)
        if video:
            self.view = QVideoWidget()
            self.view.setMinimumHeight(170)
            self.view.setMaximumHeight(220)
            self.view.setStyleSheet(f"background:{T.S950};")
            self.player.setVideoOutput(self.view)
            lay.addWidget(self.view)
        row = hbox(spacing=8)
        self.btn = QPushButton()
        self.btn.setFixedSize(28, 28)
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn.setIconSize(QSize(14, 14))
        self.btn.setStyleSheet(f"QPushButton{{background:{T.S900};border:1px solid {T.S700};border-radius:14px;}}"
                               f"QPushButton:hover{{background:{T.S800};}}")
        self._set_play_icon(False)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setStyleSheet(
            f"QSlider::groove:horizontal{{height:4px;background:{T.S800};border-radius:2px;}}"
            f"QSlider::sub-page:horizontal{{background:{T.CYAN500};border-radius:2px;}}"
            f"QSlider::handle:horizontal{{width:12px;height:12px;margin:-4px 0;border-radius:6px;background:{T.CYAN400};}}")
        self.time = lbl("0:00 / 0:00", 10, T.S500, mono=True)
        row.addWidget(self.btn)
        row.addWidget(self.slider, 1)
        row.addWidget(self.time)
        lay.addLayout(row)
        self.btn.clicked.connect(self._toggle)
        self.slider.sliderMoved.connect(self.player.setPosition)
        self.player.positionChanged.connect(self._on_pos)
        self.player.durationChanged.connect(self._on_dur)
        self.player.playbackStateChanged.connect(
            lambda st: self._set_play_icon(st == QMediaPlayer.PlaybackState.PlayingState))

    def _set_play_icon(self, playing: bool):
        self.btn.setIcon(icon("pause" if playing else "play", T.CYAN400, 14))

    def _toggle(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _on_pos(self, pos: int):
        if not self.slider.isSliderDown():
            self.slider.setValue(pos)
        self.time.setText(f"{_fmt_time(pos)} / {_fmt_time(self.player.duration())}")

    def _on_dur(self, dur: int):
        self.slider.setRange(0, max(0, dur))

    def load(self, path: str):
        if self.player is not None:
            self.player.setSource(QUrl.fromLocalFile(path))

    def stop(self):
        if self.player is not None:
            self.player.stop()
            self.player.setSource(QUrl())


# ------------------------------------------------------------------ toasts
class ToastHost:
    COLORS = {"success": (T.EMERALD300, "rgba(16,185,129,0.5)", "check-circle"),
              "error": (T.RED300, "rgba(239,68,68,0.5)", "alert-triangle"),
              "info": (T.CYAN300, "rgba(6,182,212,0.5)", "info")}

    def __init__(self, parent: QWidget):
        self.parent, self.toasts = parent, []

    def show(self, message: str, kind: str = "info", ms: int | None = None):
        color, border, ico = self.COLORS.get(kind, self.COLORS["info"])
        t = frame(f"background:rgba(15,23,42,0.95);border:1px solid {border};border-radius:12px;")
        t.setParent(self.parent)
        row = hbox(t, 12, (16, 12, 16, 12))
        row.addWidget(icon_label(ico, color, 16), 0, Qt.AlignmentFlag.AlignTop)
        text = lbl(message, 12, color, 500, wrap=True)
        fm = QFontMetrics(text.font())
        width = min(380, max(fm.horizontalAdvance(line) for line in message.split("\n")) + 24)
        text.setFixedWidth(width)
        text.setMinimumHeight(text.heightForWidth(width))
        row.addWidget(text)
        t.adjustSize()
        t.show()
        t.raise_()
        self.toasts.append(t)
        self.relayout()
        QTimer.singleShot(ms or (6500 if kind == "error" else 3500), lambda: self._fade(t))

    def _fade(self, t: QFrame):
        if t not in self.toasts:
            return
        fx = QGraphicsOpacityEffect(t)
        t.setGraphicsEffect(fx)
        anim = QPropertyAnimation(fx, b"opacity", t)
        anim.setDuration(300)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda: self._remove(t))
        anim.start()
        t._anim = anim  # keep a reference alive

    def _remove(self, t: QFrame):
        if t in self.toasts:
            self.toasts.remove(t)
        t.hide()
        t.deleteLater()
        self.relayout()

    def relayout(self):
        y = self.parent.height() - 24
        for t in reversed(self.toasts):
            y -= t.height()
            t.move(self.parent.width() - 24 - t.width(), y)
            t.raise_()
            y -= 8
