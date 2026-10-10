"""Design tokens copied from the HideIt Studio web design (Tailwind slate/emerald/cyan/violet)."""
from __future__ import annotations

import sys
from pathlib import Path

BG, CARD = "#0a0d14", "#121824"
S50, S100, S200, S300, S400 = "#f8fafc", "#f1f5f9", "#e2e8f0", "#cbd5e1", "#94a3b8"
S500, S600, S700, S800, S900, S950 = "#64748b", "#475569", "#334155", "#1e293b", "#0f172a", "#020617"
EMERALD300, EMERALD400, EMERALD500 = "#6ee7b7", "#34d399", "#10b981"
CYAN300, CYAN400, CYAN500 = "#67e8f9", "#22d3ee", "#06b6d4"
SKY400, SKY500, INDIGO500 = "#38bdf8", "#0ea5e9", "#6366f1"
VIOLET300, VIOLET400, VIOLET500 = "#c4b5fd", "#a78bfa", "#8b5cf6"
RED300, RED400, RED500 = "#fca5a5", "#f87171", "#ef4444"
AMBER400, AMBER500 = "#fbbf24", "#f59e0b"
BORDER = "rgba(30,41,59,0.8)"   # slate-800/80

SANS = "Segoe UI"                 # replaced by Inter when available
MONO = "Consolas"                 # replaced by JetBrains Mono when available


def assets_dir() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "frontend" / "assets"


def load_fonts() -> None:
    """Register bundled fonts (JetBrains Mono; drop Inter-*.ttf into assets/fonts to use Inter)."""
    global SANS, MONO
    from PySide6.QtGui import QFontDatabase
    for f in sorted((assets_dir() / "fonts").glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(f))
    fams = set(QFontDatabase.families())
    SANS = next((f for f in ("Inter", "Segoe UI", "SF Pro Text", "Helvetica Neue", "Arial") if f in fams), SANS)
    MONO = next((f for f in ("JetBrains Mono", "Cascadia Mono", "Consolas", "Menlo", "Courier New") if f in fams), MONO)


def sans() -> str:
    return f"'{SANS}', sans-serif"


def mono() -> str:
    return f"'{MONO}', monospace"


def app_qss() -> str:
    return f"""
    QToolTip {{ background:{S900}; color:{S200}; border:1px solid {S700}; padding:4px 8px; font-size:11px; }}
    QScrollArea {{ background:transparent; border:none; }}
    QScrollBar:vertical {{ background:{BG}; width:8px; margin:0; }}
    QScrollBar::handle:vertical {{ background:{S800}; border-radius:4px; min-height:30px; }}
    QScrollBar::handle:vertical:hover {{ background:{S700}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:transparent; }}
    QScrollBar:horizontal {{ background:{BG}; height:8px; margin:0; }}
    QScrollBar::handle:horizontal {{ background:{S800}; border-radius:4px; min-width:30px; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; }}
    QComboBox QAbstractItemView {{ background:{S900}; color:{S200}; border:1px solid {S800};
        selection-background-color:rgba(16,185,129,0.2); selection-color:{EMERALD300}; outline:0; padding:4px; }}
    """
