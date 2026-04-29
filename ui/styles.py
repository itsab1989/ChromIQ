"""ChromIQ v2 styles — corrected body font (system default) + all fixes."""
from __future__ import annotations

from PyQt6.QtGui import QColor, QPalette
from core.resource_path import resource_path

_ARROW_DOWN = str(resource_path("assets/arrow_down.svg")).replace("\\", "/")
_ARROW_UP   = str(resource_path("assets/arrow_up.svg")).replace("\\", "/")

# Spectrum
SPEC_MAGENTA = "#ff4573"
SPEC_AMBER   = "#ffb42d"
SPEC_GREEN   = "#56d6a5"
SPEC_CYAN    = "#37bcd6"
SPEC_VIOLET  = "#9f82ff"
TAB_COLORS   = (SPEC_MAGENTA, SPEC_AMBER, SPEC_GREEN, SPEC_CYAN, SPEC_VIOLET)

# Neutrals
BG_DARK   = "#101010"
BG_PANEL  = "#181818"
BG_WIDGET = "#262626"
BG_INPUT  = "#1f1f1f"
BORDER    = "#333333"
BORDER_HI = "#4a4a4a"
TEXT_MAIN = "#e6e6e6"
TEXT_DIM  = "#8a8a8a"
TEXT_MONO = "#a8e6a8"

ACCENT       = SPEC_CYAN
ACCENT_HOVER = "#3ec9d8"
ACCENT_WARN  = SPEC_AMBER
ACCENT_ERROR = "#e34d4d"
ACCENT_OK    = SPEC_GREEN
NEUTRAL_BTN       = "#3a3a3a"
NEUTRAL_BTN_HOVER = "#484848"


def make_dark_palette() -> QPalette:
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,          QColor(BG_PANEL))
    pal.setColor(QPalette.ColorRole.WindowText,      QColor(TEXT_MAIN))
    pal.setColor(QPalette.ColorRole.Base,            QColor(BG_INPUT))
    pal.setColor(QPalette.ColorRole.AlternateBase,   QColor(BG_WIDGET))
    pal.setColor(QPalette.ColorRole.Text,            QColor(TEXT_MAIN))
    pal.setColor(QPalette.ColorRole.BrightText,      QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.Button,          QColor(BG_WIDGET))
    pal.setColor(QPalette.ColorRole.ButtonText,      QColor(TEXT_MAIN))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor(ACCENT))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.Link,            QColor(SPEC_CYAN))
    pal.setColor(QPalette.ColorRole.ToolTipBase,     QColor("#262626"))
    pal.setColor(QPalette.ColorRole.ToolTipText,     QColor(TEXT_MAIN))
    pal.setColor(QPalette.ColorRole.Light,           QColor("#1c1c1c"))
    pal.setColor(QPalette.ColorRole.Midlight,        QColor("#1e1e1e"))
    pal.setColor(QPalette.ColorRole.Mid,             QColor("#161616"))
    pal.setColor(QPalette.ColorRole.Dark,            QColor("#0c0c0c"))
    pal.setColor(QPalette.ColorRole.Shadow,          QColor("#050505"))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,       QColor("#505050"))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#505050"))
    return pal


APP_STYLESHEET = f"""
/* ---- Base --------------------------------------------------------- */
QWidget {{
    background: {BG_PANEL};
    color: {TEXT_MAIN};
    font-family: "Inter", system-ui, -apple-system, sans-serif;
    font-size: 13px;
}}
QMainWindow, QDialog {{
    background: {BG_DARK};
}}
QDialog QLabel {{
    background: transparent;
}}

/* ---- Tabs --------------------------------------------------------- */
QTabWidget::pane {{
    border: none;
    border-top: 1px solid #000000;
    background: {BG_PANEL};
}}
QTabWidget {{
    background: {BG_DARK};
}}
/* SpectrumTabBar paints itself — only override the leftover area */
QTabBar {{
    background: {BG_DARK};
}}

/* ---- Buttons ------------------------------------------------------ */
QPushButton {{
    background: {NEUTRAL_BTN};
    color: {TEXT_MAIN};
    border: 1px solid {BORDER_HI};
    border-radius: 4px;
    padding: 6px 18px;
    min-height: 28px;
    min-width: 72px;
    font-family: "Menlo";
}}
QPushButton:hover {{
    background: {NEUTRAL_BTN_HOVER};
    border-color: #606060;
}}
QPushButton:pressed  {{ background: #2a2a2a; }}
QPushButton:disabled {{
    color: #505050;
    border-color: {BORDER};
    background: #222222;
}}
/* #primary color is overridden per-tab via setStyleSheet in main_window */
QPushButton#primary {{
    background: {ACCENT};
    color: #0a0a0a;
    border: 1px solid {ACCENT};
    font-weight: 700;
}}
QPushButton#primary:hover    {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
QPushButton#primary:disabled {{ background: #1e1e1e; border-color: #383838; color: #484848; }}
QPushButton#danger           {{ background: #4a1818; color: #ff9090; border-color: #7a2424; }}
QPushButton#danger:hover     {{ background: #5a1e1e; }}

/* ---- Inputs ------------------------------------------------------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {BG_INPUT};
    color: {TEXT_MAIN};
    border: 1px solid {BORDER};
    border-radius: 3px;
    padding: 4px 6px;
    min-height: 26px;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {ACCENT};
}}
QComboBox {{ padding-right: 28px; }}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 24px;
    border-left: 1px solid {BORDER};
    border-top-right-radius: 3px;
    border-bottom-right-radius: 3px;
    background: #2c2c2c;
}}
QComboBox::drop-down:hover {{ background: #3a3a3a; }}
QComboBox::down-arrow  {{ image: url({_ARROW_DOWN}); width: 10px; height: 6px; }}
QComboBox QAbstractItemView {{
    background: #262626;
    border: 1px solid {BORDER_HI};
    selection-background-color: {ACCENT};
    selection-color: #0a0a0a;
    outline: none;
}}
QSpinBox, QDoubleSpinBox {{ padding-right: 20px; min-height: 28px; }}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border; subcontrol-position: top right;
    width: 18px; height: 14px;
    border-left: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    border-top-right-radius: 3px;
    background: #2c2c2c;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {{ background: #3a3a3a; }}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border; subcontrol-position: bottom right;
    width: 18px; height: 14px;
    border-left: 1px solid {BORDER};
    border-top: 1px solid {BORDER};
    border-bottom-right-radius: 3px;
    background: #2c2c2c;
}}
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{ background: #3a3a3a; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow   {{ image: url({_ARROW_UP});   width: 10px; height: 6px; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: url({_ARROW_DOWN}); width: 10px; height: 6px; }}

/* ---- CheckBox / RadioButton --------------------------------------- */
QCheckBox {{ spacing: 6px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {BORDER_HI};
    border-radius: 3px;
    background: {BG_INPUT};
}}
/* :checked color is overridden per-tab via setStyleSheet */
QCheckBox::indicator:checked  {{ background: {ACCENT}; border-color: {ACCENT}; }}
QCheckBox::indicator:hover    {{ border-color: {ACCENT_HOVER}; }}
QRadioButton {{ spacing: 6px; }}
QRadioButton::indicator {{
    width: 14px; height: 14px;
    border: 1px solid {BORDER_HI};
    border-radius: 7px;
    background: {BG_INPUT};
}}
QRadioButton::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}

/* ---- Log ---------------------------------------------------------- */
QPlainTextEdit#log {{
    background: #0a0a0a;
    color: {TEXT_MONO};
    font-family: "JetBrains Mono", "Menlo", "SF Mono", "Courier New", monospace;
    font-size: 12px;
    border: 1px solid {BORDER};
    border-radius: 3px;
}}

/* ---- GroupBox ----------------------------------------------------- */
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 4px;
    margin-top: 14px;
    padding-top: 4px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px; top: 2px;
    color: {TEXT_DIM};
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

/* ---- ScrollBar ---------------------------------------------------- */
QScrollBar:vertical {{ background: {BG_DARK}; width: 8px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #404040; border-radius: 4px; min-height: 20px; }}
QScrollBar::handle:vertical:hover {{ background: #565656; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: {BG_DARK}; height: 8px; }}
QScrollBar::handle:horizontal {{ background: #404040; border-radius: 4px; min-width: 20px; }}
QScrollBar::handle:horizontal:hover {{ background: #565656; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ---- Splitter ----------------------------------------------------- */
QSplitter::handle {{ background: {BORDER}; }}

/* ---- Status labels ------------------------------------------------ */
QLabel#warning {{
    background: #3a2a00; color: {ACCENT_WARN};
    border: 1px solid {ACCENT_WARN}; border-radius: 4px; padding: 6px 10px;
}}
QLabel#info {{
    background: #25060f; color: {SPEC_MAGENTA};
    border: 1px solid {SPEC_MAGENTA}; border-radius: 4px; padding: 6px 10px;
}}
QLabel#error {{
    background: #3a0a0a; color: {ACCENT_ERROR};
    border: 1px solid {ACCENT_ERROR}; border-radius: 4px; padding: 6px 10px;
}}
QLabel#patch_count {{ font-size: 24px; font-weight: bold; color: {SPEC_MAGENTA}; }}
QLabel#section_title {{ font-size: 14px; font-weight: bold; color: #ffffff; }}

/* ---- Browse buttons ----------------------------------------------- */
QPushButton#browse {{
    background: #2c2c2c; color: {TEXT_MAIN};
    border: 1px solid {BORDER_HI}; border-radius: 3px;
    padding: 4px 8px; min-width: 32px; font-size: 14px;
}}
QPushButton#browse:hover {{ background: #3a3a3a; }}

/* ---- Icon-only buttons ------------------------------------------- */
QPushButton#icon_btn {{ padding: 0; min-height: 0; min-width: 0; }}

/* ---- ToolButton (settings / tooltip) ------------------------------ */
QToolButton#tooltip_btn {{ background: transparent; border: none; padding: 0; }}
QToolButton#tooltip_btn:hover {{
    background: rgba(255,255,255,18); border-radius: 10px;
}}

/* ---- Compact inputs (Measure tab) --------------------------------- */
QSpinBox#compact_input, QDoubleSpinBox#compact_input, QComboBox#compact_input {{
    min-height: 0; max-height: 22px; padding: 1px 6px;
}}
QSpinBox#compact_input, QDoubleSpinBox#compact_input {{ padding-right: 20px; }}
QSpinBox#compact_input::up-button,   QDoubleSpinBox#compact_input::up-button   {{ height: 10px; }}
QSpinBox#compact_input::down-button, QDoubleSpinBox#compact_input::down-button {{ height: 10px; }}
QComboBox#compact_input {{ padding-right: 28px; }}

/* ---- Fallback QProgressBar (used if SpectrumSegmentsBar missing) -- */
QProgressBar {{
    border: 1px solid {BORDER}; border-radius: 3px;
    background: {BG_INPUT}; text-align: center; color: {TEXT_MAIN}; height: 18px;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 2px; }}
"""
