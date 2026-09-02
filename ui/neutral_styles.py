"""Neutral mode palette and stylesheet for ChromIQ — the third appearance.

Sibling of ``ui/styles.py`` (dark) and ``ui/light_styles.py`` (light), selected
at runtime by ``ui/theme.py`` from the user's appearance setting.

WHAT THIS IS. A light-grey working environment with **no colour anywhere in the
interface**. It is a designed third theme, not the light theme with the colour
turned off: every value below is a true neutral (R = G = B), because the chrome
sits on screen beside the TIFF preview and the 3D gamut viewer and a tinted
chrome biases the judgement of coloured content.

THE VALUES ARE NOT DERIVED HERE. They are the approved design handoff's token
table verbatim — *Register: Balanced, Surface logic: Stacked*, the delivered
state — and the accent is Draft 1 "Index": ONE accent value, :data:`NM_ACTION`,
on every accent surface, with tab identity carried by a five-cell rule that is
a separate job. Do not re-derive, scale or "improve" a value here: the handoff
computed every contrast ratio from these constants and the owner signed them
off. If a different Register is ever chosen, re-read the handoff's table rather
than moving these by hand.

THREE RULES COME OUT OF THE MEASUREMENTS, and the second is the one this file
exists to keep:

1. **Nothing is ever lighter than its ground.** On a panel at L* 90 there is no
   headroom above — white on the panel reaches 1.3:1. Every accent, rule, ring
   and indicator is *darker* than what it sits on, without exception.
2. **All text is dark. There is no inverted text anywhere.** Nothing here is
   copied across from ``ui/styles.py``: a light constant painted onto a surface
   that is now light gives 1.78:1. The single sanctioned light-on-dark pairing
   is :data:`NM_ON_ACTION` on :data:`NM_ACTION` (15.53:1), which is a fill, not
   an inversion of the theme.
3. **Low contrast means "disabled" and nothing else.** Enabled controls carry a
   fill and a solid 1px edge; disabled controls LOSE THE FILL and their edge
   drops to :data:`NM_DISABLED` (1.35:1 — deliberately low). Nothing that works
   is allowed to be faint.

   THE EDGE IS SOLID, NOT DASHED. The handoff's shape for "disabled" was a
   dashed edge, and it shipped that way; the owner looked at it on screen and
   ruled it out (2026-09-02): *"checkboxes and comboboxes (probably also
   spinboxes) from deactivated options have dotted lines in neutral mode -
   should be continuous"*. His call, over the handoff. Do not put the dash
   back. What says "disabled" without it: the fill is GONE (a live field is
   white, a dead one is the ground), the label and the edge drop to
   NM_DISABLED, and a ticked box loses its ACTION fill — three signals, none
   of them a hue and none of them a dash.
"""
from __future__ import annotations

from PyQt6.QtGui import QColor, QPalette

from core.resource_path import resource_path

# The dark-ink arrows, the same pair the light theme uses: this is a light
# ground, so the glyph must be dark (rule 2). No new asset is needed.
_ARROW_DOWN_DARK = str(resource_path("assets/arrow_down_dark.svg")).replace("\\", "/")
_ARROW_UP_DARK   = str(resource_path("assets/arrow_up_dark.svg")).replace("\\", "/")

# -----------------------------------------------------------------------
# Design tokens — the handoff's table, verbatim.
#
#   token          hex        L*    use
#   BG_WINDOW      #e2e2e2    90    outer chrome, tab trough, masthead, gutters
#   BG_PANEL       #e2e2e2    90    the main working panel — the reading surface
#   BG_SURFACE     #e2e2e2    90    group boxes and cards
#
# BG_PANEL and BG_SURFACE were #ebebeb (L* 93) and #f5f5f5 (L* 97). The owner
# collapsed them onto the window value on 2026-09-02 — see the note beside the
# constants. Every ratio in this file's comments is recomputed against #e2e2e2.
#   BG_INPUT       #ffffff   100    fields, combo boxes, spin boxes
#   BG_VIEWER      #d4d4d4    85    preview and gamut wells
#   BORDER         #b6b6b6    74    ordinary separation
#   BORDER_HI      #2f2f2f    19    active / focused edge
#   TEXT_MAIN      #101010     5    body, values, labels
#   TEXT_DIM       #232323    14    secondary labels, units, help
#   TEXT_FAINT     #3f3f3f    27    tertiary
#   ACTION         #101010     5    the single accent value
#   ON_ACTION      #e8e8e8     —    text/glyph on an ACTION fill
#   DISABLED       #c4c4c4    79    disabled text and edges
# -----------------------------------------------------------------------

# Backgrounds
NM_BG_WINDOW   = "#e2e2e2"   # window background, tab-bar trough, masthead
# ONE GROUND, NOT THREE. The handoff stacked three surfaces — window #e2e2e2,
# panel #ebebeb, raised surface #f5f5f5 — and the owner looked at the shipped
# build and ruled the stack out (2026-09-02):
#
#     "it looks like every section in every tab is a little lighter than the
#      background of the main window. should be the same color."
#
# So the two names below now resolve to the window value. THE NAMES STAY:
# roughly forty sites say which surface they mean, and reading "the panel" or
# "the raised card" at the point of use is worth more than the one value they
# share. What tells a section from its ground is its 1px BORDER edge, which is
# rule 3's own answer — a thing that works carries a solid edge — and here the
# edge carries all of it.
#
# Anything that stepped DOWN from these (hover, pressed, the popups' hover row)
# had to move down with them; see the derived block below.
NM_BG_PANEL    = NM_BG_WINDOW   # main content panels (tab pane)
NM_BG_SURFACE  = NM_BG_WINDOW   # GroupBox fill, footer strips, cards
NM_BG_INPUT    = "#ffffff"   # QLineEdit / QSpinBox / QComboBox bg
NM_BG_VIEWER   = "#d4d4d4"   # TIFF preview / 3D gamut viewer fill

# Borders
NM_BORDER      = "#b6b6b6"   # ordinary separation                  1.57:1 on panel
NM_BORDER_HI   = "#2f2f2f"   # active / focused edge               10.33:1 on panel

# Text — all of it dark, see rule 2
NM_TEXT_MAIN   = "#101010"   # body, values, labels                14.69:1 on panel
NM_TEXT_DIM    = "#232323"   # secondary labels, units, help       12.13:1 on panel
NM_TEXT_FAINT  = "#3f3f3f"   # tertiary                             8.13:1 on panel

# The accent. ONE value, on every accent surface — Draft 1, "Index". Focus
# rings, checkboxes, primary buttons and dropdown highlights are IDENTICAL
# across all five tabs, deliberately: those controls say "here" and "on", and
# were never where the user learns which tab they are in. Tab identity is
# carried by a five-cell rule, which is a separate component and not built yet.
NM_ACTION      = "#101010"   # rule, ring, tick, fill              14.69:1 on panel
NM_ON_ACTION   = "#e8e8e8"   # the ONLY light-on-dark pairing      15.53:1 on ACTION

# Disabled. The one place low contrast is allowed, and it means nothing else.
NM_DISABLED    = "#c4c4c4"   # disabled text and edges              1.35:1 on panel

# --- derived, and derived only from the table above ----------------------
# A control's own fill is the ground it sits on; its hover and pressed states
# step DOWN from there (rule 1 — a control never brightens under the pointer).
# No new hue is introduced: every one of these is a token.
#
# THE LADDER MOVED DOWN WITH THE GROUND. Hover was BG_WINDOW and pressed
# BG_VIEWER, one and two steps under a raised BG_SURFACE fill. With the surface
# collapsed onto the window, hover would have BEEN the fill and every hover in
# the app would have done nothing — a drop-down arrow, a spin button and a
# browse button change nothing but their background under the pointer. They
# keep their meaning by stepping down from the single ground instead.
NM_BG_WIDGET   = NM_BG_SURFACE   # QPushButton / drop-down body — the ground
NM_BG_HOVER    = NM_BG_VIEWER    # one step down                 1.14:1 step
NM_BG_PRESSED  = NM_BORDER       # two steps down                1.57:1 step

# Tab bar (the QSS tabs — the main window's SpectrumTabBar paints its own).
# Active connects to the panel below it; inactive sits on the window trough —
# and with one ground those are now the SAME VALUE. The selected tab is told
# apart by its edge and its weight instead: BORDER_HI all round and a bold
# label, in the ``QTabBar::tab:selected`` rule below. A lighter fill is not
# available to it any more, and that is the point.
NM_TAB_INACTIVE_BG   = NM_BG_WINDOW
NM_TAB_INACTIVE_TEXT = NM_TEXT_DIM
NM_TAB_ACTIVE_BG     = NM_BG_PANEL
NM_TAB_ACTIVE_TEXT   = NM_TEXT_MAIN

# Mode buttons (segmented switch — Guided / Manual / Expert)
NM_MODE_BG     = NM_BG_SURFACE
NM_MODE_BORDER = NM_BORDER
NM_MODE_TEXT   = NM_TEXT_DIM

# Log / terminal. The log's TEXT COLOUR under a per-tab accent is one of the
# two decisions the owner still owns (`_darken_for_light_log`); what is set
# here is the theme's own answer — body text on a raised surface.
# WHITE. The owner's instruction, 2026-09-02: *"the log output field in
# neutral mode should have a white background"*. It reuses BG_INPUT rather
# than inventing a value — the log IS a field you read into, it is the only
# other place in the theme that is white, and with the three grounds collapsed
# onto one it is now the single surface on screen that differs from its
# surround, which is exactly what he was asking for. NM_LOG_TEXT is 19.03:1 on
# it (it was 14.69:1 on the ground), so the readout got MORE legible, not less.
NM_LOG_BG      = NM_BG_INPUT
NM_LOG_TEXT    = NM_TEXT_MAIN    # 19.03:1 on the white well
# The border does LESS work than it did, not more: the well used to sit a hair
# off its surround (#f5f5f5 on #ebebeb, 1.19:1) and now stands off it at
# 1.29:1 by its own fill. BORDER stays for the edge, unchanged.
NM_LOG_BORDER  = NM_BORDER

# Good / warning / bad. In this theme the verdict is carried by SHAPE, not by
# hue — solid disc / triangle / square, with a 1px underline for a warning and
# a 3px left bar for a failure. The glyphs are a component job; what the
# stylesheet can carry is the row treatment, below. There is no green, no amber
# and no red in this theme: the three states share one ink and differ in
# weight and rule.
NM_ACCENT_OK    = NM_TEXT_MAIN
NM_ACCENT_WARN  = NM_TEXT_MAIN
NM_ACCENT_ERROR = NM_TEXT_MAIN


# -----------------------------------------------------------------------
# QPalette
# -----------------------------------------------------------------------

def make_neutral_palette() -> QPalette:
    """The palette ``apply_appearance`` installs for the Neutral appearance.

    Its ``Window`` / ``WindowText`` pair is also Neutral's FINGERPRINT in
    ``ui.theme._FINGERPRINTS`` — that is how every site in the app tells this
    appearance from Light, which it matches at every lightness threshold the
    code ever used (L* 90 reads "light" to 127, 128 and 150 alike).
    """
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,          QColor(NM_BG_WINDOW))
    pal.setColor(QPalette.ColorRole.WindowText,      QColor(NM_TEXT_MAIN))
    pal.setColor(QPalette.ColorRole.Base,            QColor(NM_BG_INPUT))
    pal.setColor(QPalette.ColorRole.AlternateBase,   QColor(NM_BG_SURFACE))
    pal.setColor(QPalette.ColorRole.Text,            QColor(NM_TEXT_MAIN))
    # DARK, not white. On a light ground BrightText is still ink (rule 2).
    pal.setColor(QPalette.ColorRole.BrightText,      QColor("#000000"))
    pal.setColor(QPalette.ColorRole.Button,          QColor(NM_BG_WIDGET))
    pal.setColor(QPalette.ColorRole.ButtonText,      QColor(NM_TEXT_MAIN))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor(NM_ACTION))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(NM_ON_ACTION))
    pal.setColor(QPalette.ColorRole.Link,            QColor(NM_ACTION))
    pal.setColor(QPalette.ColorRole.ToolTipBase,     QColor(NM_BG_SURFACE))
    pal.setColor(QPalette.ColorRole.ToolTipText,     QColor(NM_TEXT_MAIN))
    # Fusion uses Light/Midlight/Mid/Dark/Shadow for frame highlights. Kept on
    # the token ladder, monotonically descending, so a frame Qt draws for
    # itself lands on a value this theme actually owns.
    pal.setColor(QPalette.ColorRole.Light,           QColor(NM_BG_SURFACE))
    pal.setColor(QPalette.ColorRole.Midlight,        QColor(NM_BG_PANEL))
    pal.setColor(QPalette.ColorRole.Mid,             QColor(NM_BG_VIEWER))
    pal.setColor(QPalette.ColorRole.Dark,            QColor(NM_DISABLED))
    pal.setColor(QPalette.ColorRole.Shadow,          QColor(NM_BORDER))
    pal.setColor(QPalette.ColorGroup.Disabled,
                 QPalette.ColorRole.Text,       QColor(NM_DISABLED))
    pal.setColor(QPalette.ColorGroup.Disabled,
                 QPalette.ColorRole.ButtonText, QColor(NM_DISABLED))
    return pal


# -----------------------------------------------------------------------
# QSS stylesheet
# -----------------------------------------------------------------------

NEUTRAL_STYLESHEET = f"""
/* -- Base ---------------------------------------------------------- */
/* No `background` on QWidget — that would paint over each GroupBox's
 * surface color when its children draw, and it is also what put a pale block
 * across the masthead rail in the dark theme (tests/test_bar_sits_on_the_
 * masthead_rail.py pins the invariant for light; it holds here for the same
 * reason). Children stay transparent and inherit visually from whichever
 * container they sit in. The top-level containers below set explicit bgs. */
QWidget {{
    color: {NM_TEXT_MAIN};
    font-family: "Inter";
    font-size: 13px;
}}
QMainWindow, QDialog {{
    background: {NM_BG_WINDOW};
}}
QDialog QLabel {{ background: transparent; }}

/* -- Tabs ---------------------------------------------------------- */
QTabWidget::pane {{
    border: 1px solid {NM_BORDER};
    border-top: 1px solid {NM_BORDER};
    background: {NM_BG_PANEL};
}}
QTabWidget {{
    background: {NM_BG_WINDOW};
    border-top: none;
}}
QTabBar {{
    background: {NM_BG_WINDOW};
}}
QTabBar::tab {{
    background: {NM_TAB_INACTIVE_BG};
    color: {NM_TAB_INACTIVE_TEXT};
    padding: 9px 20px;
    border: 1px solid {NM_BORDER};
    border-bottom: 2px solid transparent;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    min-width: 130px;
}}
/* THE SELECTED TAB HAS NO LIGHTER FILL LEFT. With one ground, active and
 * inactive are the same value, so the mark is the EDGE and the WEIGHT: the
 * active-focused border and a bold label. That pairing is the theme's own
 * escalation everywhere else (a warning gains a rule, a failure a bar), and it
 * is what rule 1 leaves available when brightening is not. */
QTabBar::tab:selected {{
    background: {NM_TAB_ACTIVE_BG};
    color: {NM_TAB_ACTIVE_TEXT};
    border-color: {NM_BORDER_HI};
    font-weight: bold;
}}
QTabBar::tab:hover:!selected {{
    background: {NM_BG_VIEWER};
    color: {NM_TAB_ACTIVE_TEXT};
}}
QTabBar::scroller {{
    background: {NM_BG_WINDOW};
}}

/* -- Buttons ------------------------------------------------------- */
/* Enabled: a fill and a SOLID 1px edge. Disabled: no fill, a DASHED edge.
 * That pairing is rule 3 — low contrast means disabled and nothing else. */
QPushButton {{
    background: {NM_BG_WIDGET};
    color: {NM_TEXT_MAIN};
    border: 1px solid {NM_BORDER};
    border-radius: 4px;
    padding: 6px 18px;
    min-height: 28px;
    min-width: 72px;
}}
QPushButton:hover {{
    background: {NM_BG_HOVER};
    border-color: {NM_BORDER_HI};
}}
QPushButton:pressed {{
    background: {NM_BG_PRESSED};
}}
QPushButton:disabled {{
    background: transparent;
    color: {NM_DISABLED};
    border: 1px solid {NM_DISABLED};
}}
QPushButton#primary {{
    background: {NM_ACTION};
    color: {NM_ON_ACTION};
    border: 1px solid {NM_ACTION};
    font-weight: bold;
}}
QPushButton#primary:hover {{
    background: {NM_BORDER_HI};
    border-color: {NM_BORDER_HI};
}}
QPushButton#primary:disabled {{
    background: transparent;
    border: 1px solid {NM_DISABLED};
    color: {NM_DISABLED};
}}
/* No red. A destructive button is the heavier edge and the bolder label — the
 * same escalation the verdict glyphs use, one channel up from ordinary. */
QPushButton#danger {{
    background: {NM_BG_WIDGET};
    color: {NM_TEXT_MAIN};
    border: 1px solid {NM_BORDER_HI};
    font-weight: bold;
}}
QPushButton#danger:hover {{
    background: {NM_BG_HOVER};
}}

/* -- Inputs -------------------------------------------------------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {NM_BG_INPUT};
    color: {NM_TEXT_MAIN};
    border: 1px solid {NM_BORDER};
    border-radius: 3px;
    padding: 4px 6px;
    min-height: 26px;
}}
/* The focus ring is ACTION — 19.03:1 on the field. It is the same ring in
 * every tab, on purpose (Draft 1: it says "here", not "which tab"). */
QLineEdit:focus, QComboBox:focus {{
    border-color: {NM_ACTION};
}}
/* Disabled inputs — the fill goes and the edge drops to DISABLED, so an off
 * field cannot be mistaken for a live one: a live field is WHITE and a dead
 * one is the ground. The edge is solid (see rule 3 — the dash was the
 * handoff's and the owner removed it on 2026-09-02). QPlainTextEdit /
 * QTextEdit belong here too — see the note in ui/styles.py: without them a
 * disabled text box is indistinguishable from a live one. */
QLineEdit:disabled,
QSpinBox:disabled, QDoubleSpinBox:disabled,
QComboBox:disabled,
QPlainTextEdit:disabled, QTextEdit:disabled {{
    color: {NM_DISABLED};
    background: {NM_BG_PANEL};
    border: 1px solid {NM_DISABLED};
}}
QSpinBox:disabled::up-button,   QSpinBox:disabled::down-button,
QDoubleSpinBox:disabled::up-button, QDoubleSpinBox:disabled::down-button {{
    background: {NM_BG_PANEL};
}}
QComboBox:disabled::drop-down {{ background: {NM_BG_PANEL}; }}
QComboBox {{
    padding-right: 28px;
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 24px;
    border-left: 1px solid {NM_BORDER};
    border-top-right-radius: 3px;
    border-bottom-right-radius: 3px;
    background: {NM_BG_WIDGET};
}}
QComboBox::drop-down:hover {{
    background: {NM_BG_HOVER};
}}
QComboBox::down-arrow {{
    image: url({_ARROW_DOWN_DARK});
    width: 10px;
    height: 6px;
}}
QComboBox QAbstractItemView {{
    background: {NM_BG_INPUT};
    border: 1px solid {NM_BORDER_HI};
    selection-background-color: {NM_ACTION};
    selection-color: {NM_ON_ACTION};
    outline: none;
}}
/* The row inside a combo POPUP — see ui/styles.py::combo_popup_qss for the
   full reasoning. macOS draws the popup as a menu, which puts a tick on the
   current entry and (once the accent gives the row a background) shifts the
   highlighted row's text right. Any box property on ::item:selected makes
   QStyleSheetStyle draw every row itself: no tick, one inset. It must carry a
   background too, or the highlight vanishes. */
QComboBox::item:selected {{
    background: {NM_ACTION};
    color: {NM_ON_ACTION};
    padding-left: 0px;
}}
/* Buttons mirror the QComboBox drop-down: subcontrol-origin PADDING keeps them
   INSIDE the 1px border, so the focus ring stays a clean continuous rounded
   rectangle. Zero VERTICAL padding so the two buttons fill the inner height
   and meet at a single 1px divider. */
QSpinBox, QDoubleSpinBox {{
    padding: 0 24px 0 6px;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 22px;
    border: none;
    border-left: 1px solid {NM_BORDER};
    border-top-right-radius: 3px;
    background: {NM_BG_WIDGET};
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {{
    background: {NM_BG_HOVER};
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: padding;
    subcontrol-position: bottom right;
    width: 22px;
    border: none;
    border-left: 1px solid {NM_BORDER};
    border-top: 1px solid {NM_BORDER};
    border-bottom-right-radius: 3px;
    background: {NM_BG_WIDGET};
}}
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {NM_BG_HOVER};
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
    border: 1px solid {NM_BORDER_HI};
    border-radius: 3px;
    background: {NM_BG_INPUT};
}}
QCheckBox::indicator:checked {{
    background: {NM_ACTION};
    border-color: {NM_ACTION};
}}
QCheckBox::indicator:hover {{
    border-color: {NM_ACTION};
}}
QCheckBox:disabled {{
    color: {NM_DISABLED};
}}
QCheckBox::indicator:disabled {{
    background: transparent;
    border: 1px solid {NM_DISABLED};
}}
/* …EXCEPT when the box is disabled BECAUSE it is forced on. The rule above
   makes a ticked-and-disabled box look identical to an unticked one — right
   for "this whole group is off", wrong for "this is on and not yours to
   change", where the user then cannot see the mode they are actually in
   (Basti, 2026-08-28, on the CR30 patch-by-patch lock). A muted-but-still-dark
   fill keeps the tick readable while the solid edge is gone. */
QCheckBox#locked_on::indicator:checked:disabled {{
    background: {NM_TEXT_FAINT};
    border: 1px solid {NM_DISABLED};
}}
QRadioButton {{
    spacing: 6px;
}}
QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {NM_BORDER_HI};
    border-radius: 7px;
    background: {NM_BG_INPUT};
}}
QRadioButton::indicator:checked {{
    background: {NM_ACTION};
    border-color: {NM_ACTION};
}}
QRadioButton::indicator:hover {{
    border-color: {NM_ACTION};
}}
QRadioButton:disabled {{
    color: {NM_DISABLED};
}}
QRadioButton::indicator:disabled {{
    background: transparent;
    border: 1px solid {NM_DISABLED};
}}

/* -- Log / terminal output ---------------------------------------- */
QPlainTextEdit#log {{
    background: {NM_LOG_BG};
    color: {NM_LOG_TEXT};
    font-family: "JetBrains Mono", "Menlo", "SF Mono", "Courier New", monospace;
    font-size: 12px;
    font-weight: 800;
    border: 1px solid {NM_LOG_BORDER};
    border-radius: 3px;
}}

/* -- GroupBox ------------------------------------------------------ */
/* Surface colour applied via QPalette + autoFillBackground in
 * ui/widgets.py (GroupBoxSurfaceFilter) — using QSS `background:` here
 * propagates the colour into descendants' palette.Base, making
 * QComboBox / QSpinBox bodies render the surface instead of the input QSS
 * rule's white. */
QGroupBox {{
    border: 1px solid {NM_BORDER};
    border-radius: 4px;
    margin-top: 14px;
    padding-top: 4px;
}}
/* TERTIARY, NOT FAINT. The light theme's group titles use its own TEXT_FAINT,
   which is a pale grey; this theme's tertiary value is dark ink at 8.13:1,
   because a title that works may not be faint (rule 3). */
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    top: 2px;
    color: {NM_TEXT_FAINT};
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

/* -- ScrollBar ----------------------------------------------------- */
QScrollBar:vertical {{
    background: {NM_BG_WINDOW};
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {NM_BORDER};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background: {NM_TEXT_FAINT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {NM_BG_WINDOW};
    height: 8px;
}}
QScrollBar::handle:horizontal {{
    background: {NM_BORDER};
    border-radius: 4px;
    min-width: 20px;
}}
QScrollBar::handle:horizontal:hover {{ background: {NM_TEXT_FAINT}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* -- Splitter ------------------------------------------------------ */
QSplitter::handle {{
    background: {NM_BORDER};
}}

/* -- Labels -------------------------------------------------------- */
/* The verdict boxes. No amber, no red: the escalation is a RULE, deliberately
   uneven so a failing row is findable while scrolling without reading —
   nothing for a pass, the ⚠ the message itself carries for a warning (the
   heavier bottom edge went — see the note on QLabel#warning), a 3px left bar and
   a bold label for a failure. The glyphs (disc / triangle / square) are a
   component job and are not in the stylesheet. */
/* THE WARNING BOX HAS FOUR EQUAL EDGES. It had a 2px BORDER_HI bottom — the
   escalation above — and on the Print Chart notice, which is thirty lines
   tall, that did not read as "this is a warning": it read as a lopsided
   frame. The owner, 2026-09-02: *"the lower margin of this info box in print
   chart tab is thicker than the others"*. Measured on that box: top edge 1px
   #b6b6b6, bottom edge 2px #2f2f2f, and the white space above the first line
   and below the last is 8.5 px on both sides — so it was the EDGE he saw, not
   a margin. An underline works next to the text it qualifies; half a metre
   below it, it is just an uneven box.
   The escalation is not lost: every one of these messages opens with a ⚠, and
   `banner_qss` (the one-line banners in the tool dialogs, where the underline
   IS next to its text) keeps it. */
QLabel#warning {{
    background: {NM_BG_SURFACE};
    color: {NM_TEXT_MAIN};
    border: 1px solid {NM_BORDER};
    border-radius: 4px;
    padding: 6px 10px;
}}
QLabel#info {{
    background: {NM_BG_SURFACE};
    color: {NM_TEXT_MAIN};
    border: 1px solid {NM_BORDER};
    border-radius: 4px;
    padding: 6px 10px;
}}
/* The Measure tab's information box: the #info shape, and in this theme it is
   the SAME shape — there is one accent, so a per-tab variant would differ in
   nothing. */
QLabel#info_measure {{
    background: {NM_BG_SURFACE};
    color: {NM_TEXT_MAIN};
    border: 1px solid {NM_BORDER};
    border-radius: 4px;
    padding: 6px 10px;
}}
QLabel#error {{
    background: {NM_BG_SURFACE};
    color: {NM_TEXT_MAIN};
    border: 1px solid {NM_BORDER};
    border-left: 3px solid {NM_ACTION};
    border-radius: 4px;
    padding: 6px 10px;
    font-weight: bold;
}}
QLabel#patch_count {{
    font-size: 24px;
    font-weight: bold;
    color: {NM_TEXT_MAIN};
}}
QLabel#section_title {{
    font-size: 14px;
    font-weight: bold;
    color: {NM_TEXT_MAIN};
}}
QLabel#param_label, QCheckBox#param_label, QRadioButton#param_label {{ color: {NM_TEXT_MAIN}; }}
QLabel#param_label:disabled, QCheckBox#param_label:disabled, QRadioButton#param_label:disabled {{ color: {NM_DISABLED}; }}
/* Scoped indicator styling for param_label radios (the 8-/16-bit pair) only,
 * so they grey when a preset locks the panel; other radios stay native. */
QRadioButton#param_label::indicator {{
    width: 14px; height: 14px;
    border: 1px solid {NM_BORDER_HI};
    border-radius: 7px;
    background: {NM_BG_INPUT};
}}
QRadioButton#param_label::indicator:checked {{ background: {NM_ACTION}; border-color: {NM_ACTION}; }}
QRadioButton#param_label::indicator:disabled {{ background: transparent; border: 1px solid {NM_DISABLED}; }}

/* -- Mode buttons (Guided / Manual / Expert) --------------------- */
/* Default appearance. The per-tab QSS injection in main_window also targets
 * QPushButton#mode_btn and re-tints the :checked state; under this theme that
 * tint is the single ACTION value, so all five tabs agree. */
QPushButton#mode_btn {{
    background: {NM_MODE_BG};
    border: 1px solid {NM_MODE_BORDER};
    color: {NM_MODE_TEXT};
    font-size: 13px;
    font-weight: 700;
    padding: 6px 22px;
}}
QPushButton#mode_btn:hover {{
    background: {NM_BG_HOVER};
    border-color: {NM_BORDER_HI};
    color: {NM_TEXT_MAIN};
}}

/* -- Browse / file-picker buttons --------------------------------- */
QPushButton#browse {{
    background: {NM_BG_WIDGET};
    color: {NM_TEXT_MAIN};
    border: 1px solid {NM_BORDER};
    border-radius: 3px;
    padding: 4px 8px;
    min-width: 32px;
    font-size: 14px;
}}
QPushButton#browse:hover {{
    background: {NM_BG_HOVER};
}}
QPushButton#browse_compact {{
    background: {NM_BG_WIDGET};
    color: {NM_TEXT_MAIN};
    border: 1px solid {NM_BORDER};
    border-radius: 3px;
    padding: 1px 4px;
    min-width: 32px;
    min-height: 0;
    max-height: 22px;
    font-size: 14px;
}}
QPushButton#browse_compact:hover {{
    background: {NM_BG_HOVER};
}}

/* -- Settings dialog: Restore Factory Defaults -------------------- */
/* An ACTION fill with ON_ACTION on it: 15.53:1, and the one sanctioned
   light-on-dark pairing in this theme (rule 2). It is a FILL, not an
   inversion — the label belongs to the button, not to the page. */
QPushButton#reset_defaults {{
    background: {NM_ACTION};
    color: {NM_ON_ACTION};
    border: 1px solid {NM_ACTION};
}}
QPushButton#reset_defaults:hover {{
    background: {NM_BORDER_HI};
    border-color: {NM_BORDER_HI};
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
   miscompute the scrollable-popup height and clip to ~1.5 rows. */
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
   so its accent lives here. */
SettingsDialog QComboBox::item:selected {{
    background: {NM_ACTION};
    color: {NM_ON_ACTION};
    /* Not cosmetic — see ui.styles.combo_popup_qss. Without it the highlighted
       row alone is laid out through the stylesheet's menu-item path and its
       text jumps 26 px right as the mouse passes over. */
    padding-left: 0px;
}}
SettingsDialog QComboBox QAbstractItemView {{
    selection-background-color: {NM_ACTION};
    selection-color: {NM_ON_ACTION};
}}
"""
