"""Light mode palette and stylesheet for ChromIQ.

Counterpart to ui/styles.py (dark). Selected at runtime by ui/theme.py based
on the user's appearance setting ("light" / "dark" / "auto").
"""
from __future__ import annotations

from PyQt6.QtGui import QColor, QPalette

from core.resource_path import resource_path

_ARROW_DOWN_DARK = str(resource_path("assets/arrow_down_dark.svg")).replace("\\", "/")
_ARROW_UP_DARK   = str(resource_path("assets/arrow_up_dark.svg")).replace("\\", "/")

# -----------------------------------------------------------------------
# Colour tokens — v2 (fully-light theme, including header & terminal)
# -----------------------------------------------------------------------

# Backgrounds
LM_BG_WINDOW   = "#eeece8"   # window background, tab-bar fill
LM_BG_PANEL    = "#ffffff"   # main content panels (tab pane)
LM_BG_SURFACE  = "#f7f4ef"   # GroupBox fill, footer strips, patches card
LM_BG_WIDGET   = "#edebe6"   # QPushButton default bg, ComboBox drop-down
LM_BG_INPUT    = "#ffffff"   # QLineEdit / QSpinBox / QComboBox bg
LM_BG_VIEWER   = "#efebe6"   # TIFF preview / 3D gamut viewer fill

# Tab bar (per design spec)
LM_TAB_INACTIVE_BG     = "#e5e2dd"
LM_TAB_INACTIVE_TEXT   = "#989490"
LM_TAB_ACTIVE_BG       = "#ffffff"
LM_TAB_ACTIVE_TEXT     = "#22211f"

# Borders
LM_BORDER      = "#d0ccc6"   # standard border
LM_BORDER_HI   = "#b0aba4"   # hover / focus border

# Text
LM_TEXT_MAIN   = "#22211f"   # primary text (matches design spec)
LM_TEXT_DIM    = "#7a7570"   # secondary labels, GroupBox titles
LM_TEXT_FAINT  = "#a8a4a0"   # placeholder, disabled text

# Mode buttons (segmented switch — Guided / Manual / Expert)
LM_MODE_BG     = "#eeeae5"
LM_MODE_BORDER = "#ccc9c3"
LM_MODE_TEXT   = "#989490"

# Info-box (magenta-themed — matches the magenta accent of dark mode)
LM_INFO_BG     = "#fff0f4"
LM_INFO_TEXT   = "#c2185b"
LM_INFO_BORDER = "#ff4573"

# Semantic accents — darkened for legibility on white backgrounds
LM_ACCENT_WARN  = "#e65100"
LM_ACCENT_ERROR = "#c62828"
LM_ACCENT_OK    = "#2e7d32"

# Warning / info-box tokens (shared so the print-tab airprintInfoBox can
# match the global QLabel#warning chrome).
LM_WARN_BG       = "#fff8e1"   # pale cream
LM_WARN_BORDER   = "#f9c940"   # amber
LM_WARN_TEXT     = "#2a2000"   # very dark olive — primary body text
LM_WARN_TITLE    = "#8a6500"   # darker amber — bold titles inside warning boxes

# Unchanged accents
ACCENT_BLUE  = "#2979ff"
ACCENT_HOVER = "#448aff"
ACCENT_CYAN  = "#00bcd4"

# v2 terminal (light)
LM_LOG_BG    = "#f4f8f5"
LM_LOG_TEXT  = "#2a6e2a"
LM_LOG_BORDER = "#d8e0d8"


# -----------------------------------------------------------------------
# QPalette
# -----------------------------------------------------------------------

def make_light_palette() -> QPalette:
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,          QColor(LM_BG_WINDOW))
    pal.setColor(QPalette.ColorRole.WindowText,      QColor(LM_TEXT_MAIN))
    pal.setColor(QPalette.ColorRole.Base,            QColor(LM_BG_INPUT))
    pal.setColor(QPalette.ColorRole.AlternateBase,   QColor(LM_BG_SURFACE))
    pal.setColor(QPalette.ColorRole.Text,            QColor(LM_TEXT_MAIN))
    pal.setColor(QPalette.ColorRole.BrightText,      QColor("#000000"))
    pal.setColor(QPalette.ColorRole.Button,          QColor(LM_BG_WIDGET))
    pal.setColor(QPalette.ColorRole.ButtonText,      QColor(LM_TEXT_MAIN))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor(ACCENT_BLUE))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.Link,            QColor(ACCENT_CYAN))
    pal.setColor(QPalette.ColorRole.ToolTipBase,     QColor("#fffbe6"))
    pal.setColor(QPalette.ColorRole.ToolTipText,     QColor(LM_TEXT_MAIN))
    # Fusion uses Light/Midlight/Mid/Dark/Shadow for frame highlights.
    # Keep them in the warm-gray range so borders and splitter handles
    # stay subtle rather than mapping to near-black (dark-mode behaviour).
    pal.setColor(QPalette.ColorRole.Light,           QColor("#f8f5f0"))
    pal.setColor(QPalette.ColorRole.Midlight,        QColor("#f0ece6"))
    pal.setColor(QPalette.ColorRole.Mid,             QColor("#d8d4ce"))
    pal.setColor(QPalette.ColorRole.Dark,            QColor("#c0bcb6"))
    pal.setColor(QPalette.ColorRole.Shadow,          QColor("#a0a09a"))
    pal.setColor(QPalette.ColorGroup.Disabled,
                 QPalette.ColorRole.Text,       QColor(LM_TEXT_FAINT))
    pal.setColor(QPalette.ColorGroup.Disabled,
                 QPalette.ColorRole.ButtonText, QColor(LM_TEXT_FAINT))
    return pal


# -----------------------------------------------------------------------
# QSS stylesheet
# -----------------------------------------------------------------------

LIGHT_STYLESHEET = f"""
/* -- Base ---------------------------------------------------------- */
/* No `background` on QWidget — that would paint over each GroupBox's
 * surface color when its children draw. Children stay transparent and
 * inherit visually from whichever container they sit in (tab pane,
 * GroupBox, etc.). The top-level containers below set explicit bgs. */
QWidget {{
    color: {LM_TEXT_MAIN};
    font-family: "Inter";
    font-size: 13px;
}}
QMainWindow, QDialog {{
    background: {LM_BG_WINDOW};
}}
QDialog QLabel {{ background: transparent; }}

/* -- Tabs ---------------------------------------------------------- */
QTabWidget::pane {{
    border: 1px solid {LM_BORDER};
    border-top: 1px solid {LM_BORDER};
    background: {LM_BG_PANEL};
}}
QTabWidget {{
    background: {LM_BG_WINDOW};
    border-top: none;
}}
QTabBar {{
    background: {LM_BG_WINDOW};
}}
QTabBar::tab {{
    background: {LM_TAB_INACTIVE_BG};
    color: {LM_TAB_INACTIVE_TEXT};
    padding: 9px 20px;
    border: 1px solid {LM_BORDER};
    border-bottom: 2px solid transparent;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    min-width: 130px;
}}
QTabBar::tab:selected {{
    background: {LM_TAB_ACTIVE_BG};
    color: {LM_TAB_ACTIVE_TEXT};
}}
QTabBar::tab:hover:!selected {{
    background: #dedad4;
    color: {LM_TAB_ACTIVE_TEXT};
}}
QTabBar::scroller {{
    background: {LM_BG_WINDOW};
}}

/* -- Buttons ------------------------------------------------------- */
QPushButton {{
    background: {LM_BG_WIDGET};
    color: {LM_TEXT_MAIN};
    border: 1px solid {LM_BORDER_HI};
    border-radius: 4px;
    padding: 6px 18px;
    min-height: 28px;
    min-width: 72px;
}}
QPushButton:hover {{
    background: #e4e0da;
    border-color: #a0a09a;
}}
QPushButton:pressed {{
    background: #d8d4ce;
}}
QPushButton:disabled {{
    color: {LM_TEXT_FAINT};
    border-color: {LM_BORDER};
}}
QPushButton#primary {{
    background: {ACCENT_BLUE};
    color: #ffffff;
    border: 1px solid {ACCENT_BLUE};
    font-weight: bold;
}}
QPushButton#primary:hover {{
    background: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}
QPushButton#primary:disabled {{
    background: #b8cef8;
    border-color: #b8cef8;
    color: #7890c0;
}}
QPushButton#danger {{
    background: #fde8e8;
    color: {LM_ACCENT_ERROR};
    border-color: #f0b0b0;
}}
QPushButton#danger:hover {{
    background: #fbd4d4;
}}

/* -- Inputs -------------------------------------------------------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {LM_BG_INPUT};
    color: {LM_TEXT_MAIN};
    border: 1px solid {LM_BORDER};
    border-radius: 3px;
    padding: 4px 6px;
    min-height: 26px;
}}
QLineEdit:focus, QComboBox:focus {{
    border-color: {ACCENT_BLUE};
}}
/* Disabled inputs — dim text + slightly warmer chrome to signal "off".
   QPlainTextEdit / QTextEdit belong here too — see the note in ui/styles.py:
   without them a disabled text box is indistinguishable from a live one. */
QLineEdit:disabled,
QSpinBox:disabled, QDoubleSpinBox:disabled,
QComboBox:disabled,
QPlainTextEdit:disabled, QTextEdit:disabled {{
    color: {LM_TEXT_FAINT};
    background: {LM_BG_SURFACE};
    border-color: {LM_BORDER};
}}
QSpinBox:disabled::up-button,   QSpinBox:disabled::down-button,
QDoubleSpinBox:disabled::up-button, QDoubleSpinBox:disabled::down-button {{
    background: {LM_BG_SURFACE};
}}
QComboBox:disabled::drop-down {{ background: {LM_BG_SURFACE}; }}
QComboBox {{
    padding-right: 28px;
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 24px;
    border-left: 1px solid {LM_BORDER};
    border-top-right-radius: 3px;
    border-bottom-right-radius: 3px;
    background: {LM_BG_WIDGET};
}}
QComboBox::drop-down:hover {{
    background: #e4e0da;
}}
QComboBox::down-arrow {{
    image: url({_ARROW_DOWN_DARK});
    width: 10px;
    height: 6px;
}}
QComboBox QAbstractItemView {{
    background: {LM_BG_PANEL};
    border: 1px solid {LM_BORDER_HI};
    selection-background-color: {ACCENT_BLUE};
    selection-color: #ffffff;
    outline: none;
}}
/* The row inside a combo POPUP — see styles.py for the full reasoning. macOS
   draws the popup as a menu, which puts a tick on the current entry and (once
   the accent gives the row a background) shifts the highlighted row's text
   right. Any box property on ::item:selected makes QStyleSheetStyle draw every
   row itself: no tick, one inset. It must carry a background too, or the
   highlight vanishes. DELETE THIS RULE TO REVERT. */
QComboBox::item:selected {{
    background: {ACCENT_BLUE};
    color: #ffffff;
    padding-left: 0px;
}}
/* Buttons mirror the QComboBox drop-down: subcontrol-origin PADDING keeps them
   INSIDE the 1px border, so the focus ring stays a clean continuous rounded
   rectangle (origin: border made the buttons sit on the frame, leaving messy
   seam/corner artefacts). Zero VERTICAL padding so the two buttons fill the
   inner height and meet at a single 1px divider (the down-button's top border);
   border-left is the divider from the text. */
QSpinBox, QDoubleSpinBox {{
    padding: 0 24px 0 6px;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 22px;
    border: none;
    border-left: 1px solid {LM_BORDER};
    border-top-right-radius: 3px;
    background: {LM_BG_WIDGET};
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {{
    background: #e4e0da;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: padding;
    subcontrol-position: bottom right;
    width: 22px;
    border: none;
    border-left: 1px solid {LM_BORDER};
    border-top: 1px solid {LM_BORDER};
    border-bottom-right-radius: 3px;
    background: {LM_BG_WIDGET};
}}
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background: #e4e0da;
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url({_ARROW_UP_DARK});
    width: 10px;
    height: 6px;
    top: -1px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url({_ARROW_DOWN_DARK});
    width: 10px;
    height: 6px;
    top: 1px;
}}

/* -- CheckBox ------------------------------------------------------ */
QCheckBox {{
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {LM_BORDER_HI};
    border-radius: 3px;
    background: {LM_BG_INPUT};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT_BLUE};
    border-color: {ACCENT_BLUE};
}}
QCheckBox::indicator:hover {{
    border-color: {ACCENT_HOVER};
}}
QCheckBox:disabled {{
    color: {LM_TEXT_FAINT};
}}
QCheckBox::indicator:disabled {{
    background: {LM_BG_WINDOW};
    border-color: {LM_BORDER};
}}
/* …EXCEPT when the box is disabled BECAUSE it is forced on. The rule above
   makes a ticked-and-disabled box look identical to an unticked one — right
   for "this whole group is off", wrong for "this is on and not yours to
   change", where the user then cannot see the mode they are actually in
   (Basti, 2026-08-28, on the CR30 patch-by-patch lock). The tab accent is not
   known here, so this uses a neutral mid tone that reads as a tick in the
   light theme; the dark sheet in main_window.py tints its own with the accent. */
QCheckBox#locked_on::indicator:checked:disabled {{
    background: {LM_TEXT_FAINT};
    border-color: {LM_BORDER_HI};
}}
QRadioButton {{
    spacing: 6px;
}}
QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {LM_BORDER_HI};
    border-radius: 7px;
    background: {LM_BG_INPUT};
}}
QRadioButton::indicator:checked {{
    background: {ACCENT_BLUE};
    border-color: {ACCENT_BLUE};
}}
QRadioButton::indicator:hover {{
    border-color: {ACCENT_HOVER};
}}
QRadioButton:disabled {{
    color: {LM_TEXT_FAINT};
}}
QRadioButton::indicator:disabled {{
    background: {LM_BG_WINDOW};
    border-color: {LM_BORDER};
}}

/* -- Log / terminal output — v2 light variant --------------------- */
QPlainTextEdit#log {{
    background: {LM_LOG_BG};
    color: {LM_LOG_TEXT};
    font-family: "JetBrains Mono", "Menlo", "SF Mono", "Courier New", monospace;
    font-size: 12px;
    font-weight: 800;
    border: 1px solid {LM_LOG_BORDER};
    border-radius: 3px;
}}

/* -- GroupBox ------------------------------------------------------ */
/* Surface colour applied via QPalette + autoFillBackground in
 * ui/widgets.py (GroupBoxSurfaceFilter) — using QSS `background:` here
 * propagates the colour into descendants' palette.Base, making
 * QComboBox / QSpinBox bodies render the cream surface instead of
 * the input QSS rule's white. */
QGroupBox {{
    border: 1px solid {LM_BORDER};
    border-radius: 4px;
    margin-top: 14px;
    padding-top: 4px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    top: 2px;
    color: {LM_TEXT_FAINT};
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

/* -- ScrollBar ----------------------------------------------------- */
QScrollBar:vertical {{
    background: {LM_BG_WINDOW};
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {LM_BORDER_HI};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background: #908d88; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {LM_BG_WINDOW};
    height: 8px;
}}
QScrollBar::handle:horizontal {{
    background: {LM_BORDER_HI};
    border-radius: 4px;
    min-width: 20px;
}}
QScrollBar::handle:horizontal:hover {{ background: #908d88; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* -- Splitter ------------------------------------------------------ */
QSplitter::handle {{
    background: {LM_BORDER};
}}

/* -- Labels -------------------------------------------------------- */
QLabel#warning {{
    background: {LM_WARN_BG};
    color: {LM_WARN_TEXT};
    border: 1px solid {LM_WARN_BORDER};
    border-radius: 4px;
    padding: 6px 10px;
}}
QLabel#info {{
    background: {LM_INFO_BG};
    color: {LM_INFO_TEXT};
    border: 1px solid {LM_INFO_BORDER};
    border-radius: 4px;
    padding: 6px 10px;
}}
/* Measure-tab information box: the #info shape in this tab's green. */
QLabel#info_measure {{
    background: #eefaf5;
    color: #0f7a5a;
    border: 1px solid #56d6a5;
    border-radius: 4px;
    padding: 6px 10px;
}}
QLabel#error {{
    background: #ffebee;
    color: {LM_ACCENT_ERROR};
    border: 1px solid #ef9a9a;
    border-radius: 4px;
    padding: 6px 10px;
}}
QLabel#patch_count {{
    font-size: 24px;
    font-weight: bold;
    color: {LM_TEXT_MAIN};
}}
QLabel#section_title {{
    font-size: 14px;
    font-weight: bold;
    color: {LM_TEXT_MAIN};
}}
QLabel#param_label, QCheckBox#param_label, QRadioButton#param_label {{ color: {LM_TEXT_MAIN}; }}
QLabel#param_label:disabled, QCheckBox#param_label:disabled, QRadioButton#param_label:disabled {{ color: {LM_TEXT_FAINT}; }}
/* Scoped indicator styling for param_label radios (the 8-/16-bit pair) only,
 * so they grey when a preset locks the panel; other radios stay native. */
QRadioButton#param_label::indicator {{
    width: 14px; height: 14px;
    border: 1px solid {LM_BORDER_HI};
    border-radius: 7px;
    background: {LM_BG_INPUT};
}}
QRadioButton#param_label::indicator:checked {{ background: {ACCENT_BLUE}; border-color: {ACCENT_BLUE}; }}
QRadioButton#param_label::indicator:disabled {{ background: {LM_BG_WINDOW}; border-color: {LM_BORDER}; }}

/* -- Mode buttons (Guided / Manual / Expert) --------------------- */
/* Default appearance. The per-tab QSS injection in main_window also
 * targets QPushButton#mode_btn and re-tints the :checked state with
 * the active tab's spectrum color. */
QPushButton#mode_btn {{
    background: {LM_MODE_BG};
    border: 1px solid {LM_MODE_BORDER};
    color: {LM_MODE_TEXT};
    font-size: 13px;
    font-weight: 700;
    padding: 6px 22px;
}}
QPushButton#mode_btn:hover {{
    background: #e4e0da;
    border-color: {LM_BORDER_HI};
    color: {LM_TEXT_MAIN};
}}

/* -- Browse / file-picker buttons --------------------------------- */
QPushButton#browse {{
    background: {LM_BG_WIDGET};
    color: {LM_TEXT_MAIN};
    border: 1px solid {LM_BORDER_HI};
    border-radius: 3px;
    padding: 4px 8px;
    min-width: 32px;
    font-size: 14px;
}}
QPushButton#browse:hover {{
    background: #e4e0da;
}}
QPushButton#browse_compact {{
    background: {LM_BG_WIDGET};
    color: {LM_TEXT_MAIN};
    border: 1px solid {LM_BORDER_HI};
    border-radius: 3px;
    padding: 1px 4px;
    min-width: 32px;
    min-height: 0;
    max-height: 22px;
    font-size: 14px;
}}
QPushButton#browse_compact:hover {{
    background: #e4e0da;
}}

/* -- Settings dialog: Restore Factory Defaults (dark button, bright text) */
QPushButton#reset_defaults {{
    background: #121212;
    color: #f4f4f4;
    border: 1px solid #2a2a2a;
}}
QPushButton#reset_defaults:hover {{
    background: #1f1f1f;
    border-color: #3a3a3a;
}}

/* -- Icon-only square buttons ------------------------------------- */
QPushButton#icon_btn {{
    padding: 0;
    min-height: 0;
    min-width: 0;
}}

/* -- ToolButton (tooltip icon) ------------------------------------ */
QToolButton#tooltip_btn {{
    background: transparent;
    border: none;
    padding: 0;
}}
QToolButton#tooltip_btn:hover {{
    background: rgba(0,0,0,8);
    border-radius: 10px;
}}

/* -- Compact inputs (Measure tab: Additional Options) ------------- */
QLineEdit#compact_input, QPushButton#compact_input,
QSpinBox#compact_input, QDoubleSpinBox#compact_input, QComboBox#compact_input {{
    min-height: 0;
    max-height: 22px;
    padding: 1px 6px;
}}
QSpinBox#compact_input, QDoubleSpinBox#compact_input {{
    padding: 0 20px 0 6px;
    min-height: 0;
    max-height: 22px;
}}
/* combobox-popup: 0 — see styles.py: a styled combobox this short makes Qt
   miscompute the scrollable-popup height and clip to ~1.5 rows. Non-scrollable
   popup sizes to content; the QListView stays QSS-styled (light dropdown). */
QComboBox#compact_input {{
    padding-right: 28px;
    combobox-popup: 0;
}}
QLineEdit#compact_path {{
    min-height: 22px;
    max-height: 22px;
    padding: 1px 6px;
}}

/* Preferences dialog — the combo popup's hover highlight. The tabs get theirs
   from MainWindow._apply_tab_widget_styling; this dialog is not inside a tab,
   so its accent lives here. DELETE THESE TWO RULES TO REVERT. */
SettingsDialog QComboBox::item:selected {{
    background: #3a3a3a;
    color: #ffffff;
}}
SettingsDialog QComboBox QAbstractItemView {{
    selection-background-color: #3a3a3a;
    selection-color: #ffffff;
}}
"""
