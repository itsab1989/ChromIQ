"""Interactive chart layout editor (Tools → Edit / create chart layout).

Loads any RGB ``.ti2`` (or starts a new chart), lets the user reorder patches,
recolour patches and spacers, preview the rendered chart, and save a new valid
``.ti2`` + page TIFF(s). All chart logic lives in :mod:`workflow.ti2_relayout`;
this module is purely the Qt front-end driving it.

The editor mutates a *device-value program* (an ordered list of 0..100 RGB
tuples). Reordering permutes it, recolouring a patch replaces an entry — exactly
the core's model. Spacers are handled two ways: a native palette (written into
the regenerated chart so printtarg renders it, contrast-optimised and readable)
and an optional per-spacer paint applied to the rendered TIFF.
"""
from __future__ import annotations

import copy
import sys
import tempfile
from dataclasses import astuple, dataclass, field
from pathlib import Path

from core.stem_paths import artefact, without_ext

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QPoint, QRect, QTimer
from PyQt6.QtGui import (
    QColor, QFont, QFontMetrics, QIcon, QKeySequence, QPainter, QPen, QPixmap,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QColorDialog,
    QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit,
    QPushButton, QRadioButton, QScrollArea, QSizePolicy, QSlider, QSplitter,
    QStyle, QStyledItemDelegate, QVBoxLayout, QWidget,
)

from core.logger import get_logger
from core.strip_utils import parse_passes_per_page
from ui.styles import SPEC_AMBER, SPEC_MAGENTA, TAB_COLORS, combo_popup_qss
from ui.fade_scroll import FadeScrollArea
from ui.gradient_overlay import GradientOverlay
from ui.tab_header import SpectrumStripe as _SpectrumStripe, TabHeader
from ui.tooltip_button import TooltipButton
from ui.widgets import (
    NoScrollComboBox, NoScrollDoubleSpinBox, NoScrollSpinBox,
    PrefixLockedLineEdit, load_magenta_folder_icon, open_dir_dialog,
    open_file_dialog, save_file_dialog,
)


def _magenta_tip(title: str, body: str, parent: QWidget | None = None,
                 min_width: int = 480) -> TooltipButton:
    """A TooltipButton drawn in the editor's magenta accent."""
    return TooltipButton(title, body, parent, min_width=min_width, color=SPEC_MAGENTA)


def _toggle_locked_prefix(edit: "PrefixLockedLineEdit", on: bool, prefix: str) -> None:
    """Flip a name field between locked-prefix and free modes (#68, Knut's
    model). ON: descriptive head locked + greyed with a trailing '-' and an
    empty editable tail. OFF: the descriptive name shown as a plain, fully
    editable field (no dash, no lock). Mirrors tab_chart's ``_toggle_name_prefix``."""
    if on:
        edit.set_prefix("")
        edit.setText("")
        edit.set_prefix(prefix)
    else:
        edit.set_prefix("")
        edit.setText(prefix)


# The "Generate colour sets" help, shared verbatim by the New-chart dialog's ⓘ
# and the Add-patches dialog's ⓘ (#66 follow-up: the generator info must be in
# the Add window too). Kept as one constant so the two tips can't drift; a test
# asserts it equals the matching paragraphs of the New-chart tooltip. The leading
# string passed to tr() is a module constant, which i18n_extract resolves like a
# literal — so this is a single catalog key reused in both places.
_GEN_SETS_HELP = (
    "About “Generate colour sets”:\n\n"
    "Tick any combination of these sets and ChromIQ lays them down "
    "one after another. Each set shows how many patches it adds, and a "
    "running total appears underneath, so you always know how big the "
    "chart will get before you create it. Which sets can be used depends "
    "on the device the chart is for — the sets for RGB charts come first, "
    "then the extra sets for multi-ink (CMYK and CMYK + extra inks) "
    "charts, then an overview of what is available when:\n\n"
    "• 3D RGB cube — an even grid of colours across the whole range. You "
    "pick how many steps each of red, green and blue is split into, and "
    "the chart then holds every combination (for example 6 steps makes "
    "6×6×6 = 216 patches). A solid, neutral foundation for almost any "
    "profile.\n\n"
    "• Saturated edges — the most vivid colours the printer can manage. "
    "'Per edge' traces the twelve edges of the colour cube — the gamut "
    "wireframe (black up to each pure colour and on to white, plus the "
    "colourful edges between); 'per face' goes further and also fills the "
    "six cube faces — the full gamut surface — with that many patches per "
    "side, or leave it at 0 for edges only. This outer boundary is exactly "
    "where profiles tend to go wrong, so it pays to sample it well.\n\n"
    "• Gamut-corner emphasis — a few extra patches right on the gamut "
    "edge lines next to each of the eight corners of the colour cube, "
    "where the deepest colours live and profiles err most. 'Edge' is how "
    "many to add per edge near each corner; they slot into the gaps so "
    "they never repeat what the 3D cube or Saturated edges already "
    "placed.\n\n"
    "• Skin tones (Fitzpatrick) — lifelike skin colours running light to "
    "dark through each of the six Fitzpatrick skin types, now reaching "
    "from porcelain-pale highlights down to very deep, faintly cool "
    "shadows. 'Per type' sets how many shades each type gets from light "
    "to dark; 'Ranges' adds that many parallel ramps, each nudged a "
    "little in hue, so a single skin type is covered by a small spread of "
    "tones rather than one straight line — handy because real faces vary. "
    "Worth adding whenever faces and portraits matter most.\n\n"
    "• Oceans (blues) — extra colours packed into the green-turquoise "
    "to deep-blue part of the range, where wide-gamut papers and inks "
    "reach furthest (it now dips into the greenish turquoise too). "
    "'Per layer' is how many patches each sheet holds and 'Layers' is how "
    "many sheets, so the two multiply (24 per layer × 3 layers = 72). The "
    "sheets are gently angled rather than one flat blanket, so the whole "
    "turquoise corner is filled in depth. Helpful for skies, water and "
    "deep blues.\n\n"
    "• Foliage (greens) — a spread of forest, jungle and leaf greens, for "
    "landscapes and nature shots where the greens carry the picture. As "
    "with the blues, 'Per layer' × 'Layers' patches are spread across "
    "angled sheets so the green part of the range is covered with more "
    "depth.\n\n"
    "• Sunrises (warm) — golden yellows, oranges, reds and pinks: the "
    "warm 'sunrise' side of the colour range that the blues and greens "
    "sets leave out, for skies, flowers and skin highlights. As with "
    "those sets, 'per layer' × 'layers' patches are spread across gently "
    "angled sheets.\n\n"
    "• Flamingos (pinks) — pinks, magentas and indigos: the band between "
    "where Oceans (blues) ends and Sunrises begins, the big gap the other "
    "colour-band sets leave in the middle. Great for flowers, fabrics, "
    "sunsets and skin. Again 'per layer' × 'layers' patches on angled "
    "sheets.\n\n"
    "• Neutral grey ramp — a plain ramp of pure greys from black to white, "
    "with no tints at all (a black-and-white wedge). This is the most "
    "important region for a clean profile. 'Steps' is how many greys span "
    "black to white. It is independent of Near-neutral greys below, so you "
    "can choose the number of pure neutrals separately from the tinted "
    "ones — more pure greys than tinted, or either on its own.\n\n"
    "• Near-neutral greys — rings of gentle tints just off the neutral axis "
    "at each grey level, which is what helps greys print cleanly without an "
    "unwanted colour cast. This adds only the tints; the pure grey centres "
    "come from Neutral grey ramp above. 'Steps' is how many levels get "
    "rings, 'rings' is how many rings circle each grey (one ring is six "
    "tints, each extra ring a wider, denser one — 12, then 18), and "
    "'offset' is how far the tints stray from neutral.\n\n"
    "• Colour extremes — extra detail just inside the six most saturated "
    "colour corners of the printer's range: red, green, blue, cyan, "
    "magenta and yellow at their most vivid, which are the trickiest "
    "colours to reproduce. It works like Highlights & shadows, but "
    "spiralling in from each colour corner. 'Per end' is how many patches "
    "at each corner; 'reach' how far in they spiral.\n\n"
    "• Highlights & shadows — extra detail at the two ends where printers "
    "struggle most: pale tints just below paper white, and deep tones just "
    "above black, spread across every hue. These ends often band or block "
    "up, and the cube alone samples them thinly. 'Per end' is how many "
    "patches go at each end (so the set adds twice that many), and 'depth' "
    "is how far in from white and black the tones reach.\n\n"
    "• Pastels — soft, muted colours all around the hue wheel: dusty blues, "
    "sages, soft pinks, taupes. This is where a great deal of real "
    "photography actually lives — the gentle region between the clean greys "
    "and the vivid sets. Each of the 'layers' is a chroma shell — from "
    "barely-tinted near-greys out to fuller pastels — of 'per layer' "
    "patches, so the two multiply.\n\n"
    "• From image — load one of your own photos and ChromIQ finds its most "
    "representative colours and adds them to the chart, so the profile is "
    "tuned to the kind of pictures you really print. Click 'Load image…', "
    "pick a file, and set how many 'Colours' to pull out. Lovely combined "
    "with a cube for all-round coverage plus your image's own palette on "
    "top.\n\n"
    "• Pure white & black — extra copies of pure paper white and the "
    "deepest black, the two anchor colours of every profile. 'Each' is "
    "how many of each the finished chart should hold — and any white or "
    "black the other ticked sets already contribute counts toward that "
    "number. A 3D cube, Saturated edges or Gamut-corner emphasis includes "
    "one of each, and so does a Neutral grey ramp with 2 or more steps. "
    "So with one of those ticked, 'each: 1' adds 0 extra patches and "
    "'each: 3' adds 4 (2 more whites and 2 more blacks) — that's "
    "deliberate: the chart ends up with exactly the number you asked "
    "for, never more. The copies are kept identical on purpose (they're "
    "exempt from 'Ensure unique colours'), so several readings of the "
    "same white and black can be averaged.\n\n"
    "• Fill remaining gaps — a tidy-up that comes last. After the sets you "
    "picked are laid down, it scatters extra patches into the empty parts "
    "of colour space — evenly and without repeating — until the chart "
    "reaches the size you ask for. 'Fill to' is that target total, so the "
    "whole chart lands on a round number with nothing left clumped or "
    "bare.\n\n"
    "Mix them freely — say a 3D cube for overall coverage plus "
    "a neutral grey ramp for clean neutrals, or skin tones plus greens for "
    "portraits out in nature.\n\n"
    "• Ensure unique colours — when this is ticked and your sets happen to "
    "share a colour (for example a 3D cube and a grey ramp both include "
    "black and white), ChromIQ keeps one and nudges the duplicates apart "
    "by a tiny amount, so no colour is printed and measured twice. The "
    "patch total stays the same. Leave it on unless you have a reason not "
    "to.\n\n"
    "Multi-ink devices (Device set to CMYK or CMYK + extra inks):\n\n"
    "A multi-ink chart is designed ink by ink, so the panel gains five "
    "ink-based sets:\n\n"
    "• Even coverage (targen) — patches spread evenly across every ink "
    "combination your printer can mix, always inside the ink limit. This "
    "is the backbone of a multi-ink chart and the replacement for the 3D "
    "cube family: a cube of every ink combination would explode (a 9-step "
    "cube in 7 inks is nearly 5 million patches), so Argyll's targen "
    "picks a smart, even selection instead.\n\n"
    "• Per-ink ramps — a tone ramp of every ink on its own, from a light "
    "tint to full coverage, so the profile learns each ink's own "
    "character: how fast it darkens, where it saturates, its pure colour "
    "on your paper.\n\n"
    "• Ink-pair overprints — two inks printed on top of each other, "
    "stepped up together, for every pair of your inks — how ink pairs "
    "really combine on paper. Each ink in a pair stays at or below half "
    "the ink limit, so no patch can exceed it.\n\n"
    "• Ink-triple overprints — three inks on top of each other for every "
    "trio: the home of the deep, rich composite colours profiles get "
    "their dark shadows from. Each ink stays at or below a third of the "
    "ink limit.\n\n"
    "• Rich-black ramp — dark neutral greys built from colour ink plus "
    "increasing amounts of black: real measurements for the profile's "
    "black generation instead of guesswork. Needs a black ink.\n\n"
    "Which of the sets above still work on a multi-ink chart: Neutral "
    "grey ramp, Near-neutral greys, Pure white & black and Fill remaining "
    "gaps always do — they are built natively for any ink set. The "
    "cube-shaped sets (3D RGB cube, Saturated edges, Gamut-corner "
    "emphasis, Colour extremes) never apply: they trace the corners and "
    "edges of the RGB colour cube, which a multi-ink device simply "
    "doesn't have — Even coverage is their replacement, so they stay "
    "greyed out as a reminder rather than disappearing. The look-based "
    "sets (Skin tones, Oceans, Foliage, Sunrises, Flamingos, Highlights "
    "& shadows, Pastels, From image) describe how colours look, not "
    "which inks to use — they unlock as soon as you set a preconditioning "
    "profile that matches the chart's ink set, because only a profile can "
    "tell ChromIQ which ink mix produces each look. The same profile "
    "also re-centres the Near-neutral grey rings on your printer's true "
    "neutral, and brings the 3D preview back (as a view of the patches' "
    "real colours) — without a profile there is no honest colour model "
    "for a multi-ink chart, so the preview stays hidden rather than "
    "showing a guess.\n\n"
    "Why the finished chart can hold a few more patches than the total "
    "shown here: measuring instruments read whole strips, so when the "
    "page layout is built, a partial last strip is topped up with "
    "paper-white filler patches (Argyll's printtarg does exactly the "
    "same). If you design 896 patches and each strip holds 13, the "
    "printed chart becomes 910 — the 14 extras are plain paper white, "
    "are measured like everything else, and simply give the profile a "
    "few more readings of the paper. Nothing is lost or changed."
)

# Intro + closing for the New-chart dialog's ⓘ, around the shared generator
# help — the full tooltip is built as tr(intro) + tr(_GEN_SETS_HELP) +
# tr(closing), so the generator paragraphs exist exactly once (#124: the old
# duplicated copy had drifted badly out of date).
_NEW_CHART_TIP_INTRO = (
    "Let's start a brand-new chart. You only need to make a few quick "
    "choices here — once you're done, the chart opens in the editor where "
    "you can arrange and fine-tune everything.\n\n"
    "What each choice means:\n\n"
    "• Device — what kind of printer the chart is for. Print RGB is the "
    "standard choice: any printer you print to through a normal driver, "
    "which is how ChromIQ profiles are usually made. CMYK and CMYK + "
    "extra inks are for printers you address ink-by-ink (typically "
    "through a RIP): the chart is then designed in ink values, you can "
    "add your printer's extra inks (orange, green, violet, light "
    "inks, …), set an ink limit, and optionally point to a "
    "preconditioning profile. The colour-set list below adapts to the "
    "device — the overview at the end explains which sets are available "
    "when.\n\n"
    "• Instrument & Paper — which measuring device you'll use and what "
    "paper you'll print on. ChromIQ uses these to lay the patches out in a "
    "way your device can read, at the right page size.\n\n"
    "• Patches — how to fill the chart to begin with. There are three ways:\n"
    "    – Seed from targen — enter a number and let ChromIQ spread that "
    "many colours evenly across the whole colour range. A great all-round "
    "starting point you can then rearrange.\n"
    "    – Paste colour values — paste, or load from a file, your own list "
    "of hex or RGB colours.\n"
    "    – Generate colour sets — build the chart from one or more "
    "ready-made colour spreads (described below).\n\n"
    "• Layout options — the finer print settings (spacer squares, sizing, "
    "page margin, resolution). The defaults are sensible, so feel free to "
    "leave these alone until you need them."
)
_NEW_CHART_TIP_CLOSING = (
    "When you confirm, your new chart opens in the editor — there you can "
    "drag patches around, recolour them, add or remove some, and save when "
    "it's ready."
)

# Short intro for the Add-patches dialog's ⓘ, ahead of the shared generator help.
_ADD_TIP_INTRO = (
    "Add more patches to the chart you're editing. Two ways:\n\n"
    "• Add a single colour — dial in one colour and append it as a single "
    "patch.\n\n"
    "• Generate colour sets — lay down one or more of the ready-made colour "
    "spreads described below; a running total shows how many patches you'll "
    "add, and “Fill remaining gaps” tops the whole chart up to a target size "
    "rather than adding that many.\n\n"
    "The new patches are appended after the chart's existing ones — rearrange "
    "them however you like back in the editor."
)


def _padding_note(n: int) -> str:
    """Friendly one-liner for strip fill-up patches, or "" when none (#124).

    Shown in the Save/Apply summaries so a chart growing from e.g. 896 to 910
    patches is explained instead of silent. Explicit singular/plural (i18n
    rule: never "(s)")."""
    if n <= 0:
        return ""
    if n == 1:
        return tr("The layout added 1 paper-white patch to fill the last "
                  "strip — instruments read whole strips, and printtarg does "
                  "the same. It is measured like any other patch.")
    return tr("The layout added {n} paper-white patches to fill the last "
              "strip — instruments read whole strips, and printtarg does "
              "the same. They are measured like any other patch.").format(n=n)


class _AutoHideLabel(QLabel):
    """Status line that clears itself a few seconds after its last message, so
    the bottom bar is normally empty instead of holding stale text. Every
    ``setText`` (re)starts the clear timer; setting empty text cancels it."""

    HIDE_MS = 4000

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("", parent)
        # The status line lives in the left pane of a horizontal QSplitter. A
        # plain QLabel reports its full (unwrapped) text width as its minimum,
        # so a long message would force the splitter to widen this pane and
        # shrink the preview — then snap back when the text auto-clears 4 s
        # later (a Windows-only jitter, where the system font renders the text
        # wider than the pane's share). Ignored horizontal policy means the
        # text never dictates the pane width; the label just takes whatever the
        # layout gives it and clips an over-long message.
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._clear_timer = QTimer(self)
        self._clear_timer.setSingleShot(True)
        self._clear_timer.setInterval(self.HIDE_MS)
        # Clear via the base setText so the timeout doesn't re-arm itself.
        self._clear_timer.timeout.connect(lambda: QLabel.setText(self, ""))

    def setText(self, text: str) -> None:  # noqa: N802
        super().setText(text)
        if text:
            self._clear_timer.start()
        else:
            self._clear_timer.stop()


def _uniform_button_width(buttons, *, pad: int = 0) -> None:
    """Give every button in ``buttons`` one minimum width = the widest
    ``sizeHint`` + ``pad``, so their labels never clip (macOS's Fusion style
    under-sizes button hints by a few px) and the buttons line up. Derived from
    the rendered sizeHints, so it adapts to the active language."""
    buttons = [b for b in buttons if b is not None]
    if not buttons:
        return
    w = max(b.sizeHint().width() for b in buttons) + pad
    for b in buttons:
        b.setMinimumWidth(w)


def _hint_count_inactive(label: QLabel, active: bool) -> None:
    """Strike through a generator row's count when the row won't contribute
    (unticked, or gated off by the device state) — the number stays readable
    for planning, but it's visually 'not counted' (#72, Basti). Works in both
    light and dark mode (the strike inherits the label's own colour)."""
    f = label.font()
    if f.strikeOut() != (not active):
        f.setStrikeOut(not active)
        label.setFont(f)


def _as_compact(*widgets) -> None:
    """Mark inputs as ``#compact_input`` so the app-wide stylesheets
    (ui/styles.py + ui/light_styles.py) apply the short / small-arrow
    rules to them. Used in this dialog so the spinboxes don't display
    the bulky default native arrows."""
    for w in widgets:
        w.setObjectName("compact_input")


def _wire_spacer_mutex(boxes: tuple) -> None:
    """Make a set of QCheckBoxes behave like a radio group that also
    permits the all-off state.

    Clicking a box that's already on leaves it on (no-op uncheck-then-
    -check loop); clicking a different box switches the active selection;
    the user may explicitly uncheck the active one to land in the all-off
    state. Mirrors the spacer-mode picker behaviour the editor uses in
    both the printtarg section and the New-chart dialog.
    """
    def _make(cb_idx: int):
        def _on_toggled(on: bool) -> None:
            if not on:
                return
            for j, other in enumerate(boxes):
                if j == cb_idx or not other.isChecked():
                    continue
                other.blockSignals(True)
                other.setChecked(False)
                other.blockSignals(False)
        return _on_toggled
    for i, cb in enumerate(boxes):
        cb.toggled.connect(_make(i))
from workflow import ti2_relayout as R
from workflow import patch_generators as G
from workflow import patch_generators_nd as NDG

log = get_logger(__name__)


def _patches_label(n: int) -> str:
    """Count-bearing patch label with explicit singular / plural (no "(s)")."""
    return (tr("{n} patch") if n == 1 else tr("{n} patches")).format(n=n)


_SWATCH = 46  # grid swatch px

# Minimum spacing (device units, 0..100) that "Ensure unique colours" keeps
# between any two patches when sets are combined. A touch above the old 0.5 grid
# so generators that land near a 3D-cube dot are nudged a little clearer of it,
# not just de-duplicated when they coincide exactly (Knut, #78).
_GEN_MIN_DIST = 2.0

# On-screen preview render resolution (#44). The preview never needs print DPI;
# rendering it low-res makes printtarg far faster and shrinks every image
# read / diff / segmentation. The saved chart still uses the user's full DPI.
_PREVIEW_DPI = 100

_IS_MAC = sys.platform == "darwin"

# printtarg -i codes the editor offers, with friendly labels. The codes are
# passed straight through to printtarg (see workflow.ti2_relayout.regenerate),
# so they must be printtarg's own -i values: "i1" (i1Pro family), "3p"
# (i1Pro 3 Plus — larger aperture, far fewer patches per sheet, so its strip
# layout differs), "CM" (ColorMunki / i1Studio).
_INSTRUMENTS = [
    ("i1", "i1Pro / i1Pro2 / i1Pro3"),
    ("3p", "i1Pro3 Plus"),
    ("CM", "ColorMunki / i1Studio"),
]

# Strip readers (i1Pro family + 3 Plus) — the instruments for which printtarg's
# -L (suppress left clip) and -P (no per-strip patch limit) apply.
_STRIP_INSTRUMENTS = frozenset({"i1", "3p"})

# Paper sizes the new-chart dropdown offers — matches the Create Chart tab.
from data.patch_db import PAPER_LABELS, PAPER_PRINTTARG_ARG, paper_name_token
from core.i18n import count_phrase, tr
from ui.keyboard_help import with_shortcut


def _mod_keys() -> dict[str, str]:
    """Platform- and language-aware modifier-key names for the editor's
    selection hints (#45): macOS shows ⌘/⌥, every other platform the localized
    Ctrl / Alt. Built at call time so the language (restart-applied) is set."""
    shift = tr("Shift")
    if _IS_MAC:
        return {"ext": "⌘", "add": f"⌘/{shift}", "remove": "⌥"}
    ctrl = tr("Ctrl")
    return {"ext": ctrl, "add": f"{ctrl}/{shift}", "remove": tr("Alt")}
_PAPER_ORDER = ("A2", "594x420", "329x483", "483x329", "A3", "420x297",
                "11x17", "Legal", "A4", "A4R", "Letter", "LetterR",
                "203x254", "127x178", "4x6", "custom")
_PAPER_LABELS_WITH_CUSTOM = {**PAPER_LABELS,
                              "custom": "Custom (enter dimensions)"}


def _paper_code_known(code: str) -> bool:
    """True iff *code* is one of the printtarg named paper sizes — i.e. not
    a custom ``WxH`` form. Used by the editor UI to decide whether to fall
    back to the "custom" combo entry + W/H spinboxes when syncing a loaded
    chart whose paper_flag was emitted as ``WxH`` by
    :func:`workflow.ti2_relayout.paper_to_flag`.
    """
    return code in PAPER_LABELS


def _unchecked_indicator_css(settings) -> str:
    """Border + fill for an UNCHECKED radio indicator, as explicit per-theme
    colours. The editor's scoped stylesheets used palette(mid)/palette(base),
    which renders the ring nearly invisible in dark mode — the checkboxes
    stay readable because they keep the app-wide QSS's indicator border, so
    match those tokens exactly (dark: styles.BORDER_HI on BG_INPUT; light:
    light_styles.LM_BORDER_HI on LM_BG_INPUT)."""
    from ui.theme import resolve_mode
    light = resolve_mode(
        settings.get("appearance", "auto") if settings else "auto") == "light"
    return ("border: 1px solid #b0aba4; background: #ffffff;" if light
            else "border: 1px solid #4a4a4a; background: #1f1f1f;")


def _qcolor(rgb: tuple[float, float, float]) -> QColor:
    return QColor(*(max(0, min(255, round(v / 100 * 255))) for v in rgb))


def _to100(c: QColor) -> tuple[float, float, float]:
    return (c.red() / 255 * 100, c.green() / 255 * 100, c.blue() / 255 * 100)


def _display100(vals: tuple, color_rep: str = "iRGB") -> tuple[float, float, float]:
    """Device tuple (0..100, any channel count) → display RGB 0..100 (#72).

    RGB programs pass through untouched (swatches stay pixel-identical for
    RGB charts); anything else goes through the engine's display
    approximation — the same colours the rendered chart preview shows.
    """
    rep = color_rep.lstrip("i").upper()
    if len(vals) == 3 and rep == "RGB":
        return vals  # type: ignore[return-value]
    from workflow.layout_engine.colorants import to_display_rgb
    r, g, b = to_display_rgb(tuple(vals), color_rep)
    return (r / 255 * 100, g / 255 * 100, b / 255 * 100)


def _swatch_icon(rgb: tuple[float, float, float], size: int = _SWATCH) -> QIcon:
    """Colour-filled swatch with a 1-px luminance-adaptive border so dark
    patches stay visible against the dark grid background and light patches
    still get a subtle frame."""
    pm = QPixmap(size, size)
    qc = _qcolor(rgb)
    pm.fill(qc)
    # BT.601 luminance — light grey border on dark swatches, darker grey on
    # light ones. Both are visible against the dark grid background.
    y = 0.30 * qc.red() + 0.59 * qc.green() + 0.11 * qc.blue()
    border = QColor(160, 160, 160) if y < 90 else QColor(90, 90, 90)
    p = QPainter(pm)
    p.setPen(QPen(border, 1))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(0, 0, size - 1, size - 1)
    p.end()
    return QIcon(pm)


def _ghost_swatch_icon(rgb: tuple[float, float, float], size: int = _SWATCH) -> QIcon:
    """Faded swatch used while an item is being dragged — the cursor's drag
    pixmap stays crisp, the original slot looks washed-out + dashed so it's
    obvious the patch is in motion."""
    r, g, b = (max(0, min(255, round(v / 100 * 255))) for v in rgb)
    # Blend 70 % white + 30 % colour
    fr = round(255 * 0.7 + r * 0.3)
    fg = round(255 * 0.7 + g * 0.3)
    fb = round(255 * 0.7 + b * 0.3)
    pm = QPixmap(size, size)
    pm.fill(QColor(fr, fg, fb))
    p = QPainter(pm)
    p.setPen(QPen(QColor(128, 128, 128), 1, Qt.PenStyle.DashLine))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(0, 0, size - 1, size - 1)
    p.end()
    return QIcon(pm)


# ---------------------------------------------------------------------------
# Background regeneration (printtarg runs off the GUI thread)
# ---------------------------------------------------------------------------
class _RegenWorker(QThread):
    done = pyqtSignal(object)  # RegenResult | Exception

    def __init__(self, spec, program, out_dir, bin_dir, palette,
                 *, options=None, basename="chart", with_twin=True,
                 dpi_override=None):
        super().__init__()
        self._args = (spec, program, out_dir, bin_dir, palette, options,
                      basename, with_twin, dpi_override)

    def run(self) -> None:
        (spec, program, out_dir, bin_dir, palette, options, basename,
         with_twin, dpi_override) = self._args
        try:
            self.done.emit(R.regenerate(spec, program, out_dir, bin_dir,
                                        spacer_palette=palette,
                                        options=options,
                                        basename=basename,
                                        with_twin=with_twin,
                                        dpi_override=dpi_override))
        except Exception as exc:  # surfaced to the user, not swallowed
            log.exception("relayout regenerate failed")
            self.done.emit(exc)


# ---------------------------------------------------------------------------
# Patch grid — ListMode + wrapping flow with an icon-above-label delegate.
#
# We use ListMode (not IconMode) because Qt's reorder via DragDropMode.InternalMove
# is genuinely reliable there — IconMode's drop-target resolution is finicky
# (items would either snap back to their slot or land at a free grid intersection
# depending on movement mode). The custom delegate paints each item with its
# colour swatch on top and the patch number underneath, so we keep the
# IconMode-style visual without giving up reliable drag-reorder.
# ---------------------------------------------------------------------------


class _SwatchDelegate(QStyledItemDelegate):
    """Paint a swatch (icon) above a Menlo-styled patch number, inside the
    grid cell sized by :meth:`sizeHint`.

    The gap between swatches is independently settable per axis (h_gap / v_gap,
    px) and is the cell's trailing margin, so the grid's own spacing stays 0 and
    horizontal == vertical when both are equal (Knut #93). Selection is shown as a
    pink border around the swatch so it's visible even with numbers + gaps off.
    """

    LABEL_H = 16
    _SEL = QColor(255, 69, 115)         # SPEC_MAGENTA-ish selection pink

    def __init__(self, parent=None, swatch_size: int = _SWATCH) -> None:
        super().__init__(parent)
        self.swatch_size = swatch_size
        self.show_label = True          # "Show patch number" (Knut #93)
        self.h_gap = 3                  # px between swatches across / down
        self.v_gap = 3

    def paint(self, painter, opt, idx) -> None:
        painter.save()
        icon = idx.data(Qt.ItemDataRole.DecorationRole)
        text = idx.data(Qt.ItemDataRole.DisplayRole) or ""
        rect = opt.rect
        size = self.swatch_size
        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        # Swatch sits at the cell's top-left; the gap is the trailing margin.
        sx, sy = rect.x(), rect.y()
        swatch = QRect(sx, sy, size, size)
        if isinstance(icon, QIcon) and not icon.isNull():
            icon.paint(painter, swatch)
        if selected:
            # A pink border (and a faint pink wash) marks selection — visible even
            # when numbers + gaps are off and the swatches touch (Knut #93).
            painter.fillRect(swatch, QColor(255, 69, 115, 70))
            from PyQt6.QtGui import QPen
            pen = QPen(self._SEL)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(swatch.adjusted(1, 1, -1, -1))
        if self.show_label:
            f = QFont("Menlo")
            f.setPixelSize(10)
            painter.setFont(f)
            text_color = (opt.palette.color(opt.palette.ColorRole.HighlightedText)
                          if selected
                          else opt.palette.color(opt.palette.ColorRole.Text))
            painter.setPen(text_color)
            text_rect = QRect(sx, sy + size + 2, size, self.LABEL_H)
            painter.drawText(
                text_rect,
                int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                text,
            )
        painter.restore()

    def sizeHint(self, opt, idx) -> QSize:
        # Cell = swatch + trailing gap (+ label row when numbers are shown). The
        # grid's spacing is 0, so the gap here IS the visible inter-swatch gap.
        label = (self.LABEL_H + 2) if self.show_label else 0
        return QSize(self.swatch_size + self.h_gap,
                     self.swatch_size + label + self.v_gap)


# ---------------------------------------------------------------------------
class _ReorderListWidget(QListWidget):
    """QListWidget with drag-reorder UX tweaks.

    Drop handling is Qt's default (Snap + InternalMove) — that combo is what
    QListView's reorder logic actually targets, and the previous custom
    dropEvent fought with it (items snapping back was the symptom).

    Two visual tweaks on top of Qt's behaviour:

    1. While a drag is active, the source items get a washed-out / dashed
       icon so the source slot stays visible alongside the drag pixmap.
    2. The drop indicator is painted by us at the **gap midpoint** between
       the two items around the cursor — Qt's built-in indicator otherwise
       snaps to either side of the gap depending on cursor position, which
       reads as visual flicker even though the resulting reorder is the
       same. We hide the built-in one and draw a single mid-gap line.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._drag_originals: list[tuple[QListWidgetItem, QIcon]] = []
        self._drop_line: tuple[int, int, int] | None = None  # (x, y0, y1)
        # Device tuple → display RGB (0..100) for swatch/ghost icons. The
        # hosting dialog points this at its chart-aware converter when a
        # non-RGB chart is loaded (#72); the default handles plain RGB.
        self.display_rgb = _display100

    def startDrag(self, supported_actions) -> None:  # noqa: N802
        selected = self.selectedItems()
        size = self.iconSize().width() or _SWATCH
        self._drag_originals = [(it, it.icon()) for it in selected]
        for it, _ in self._drag_originals:
            dev = it.data(Qt.ItemDataRole.UserRole)
            if dev is not None:
                it.setIcon(_ghost_swatch_icon(self.display_rgb(dev), size))
        try:
            super().startDrag(supported_actions)
        finally:
            for it, icon in self._drag_originals:
                it.setIcon(icon)
            self._drag_originals = []
            self._drop_line = None
            self.viewport().update()

    def dragMoveEvent(self, ev) -> None:  # noqa: N802
        """Compute the gap midpoint between the items around the cursor.

        Qt's hit logic gives us the item *under* the cursor; we then decide
        whether the drop goes *before* or *after* that item by the cursor's
        position within its rect, and pin the indicator to the centre of the
        gap to the chosen neighbour. The actual insert position is left to
        Qt's dropEvent so the InternalMove reorder still does the right
        thing.
        """
        super().dragMoveEvent(ev)
        pos = ev.position().toPoint()
        idx = self.indexAt(pos)
        if not idx.isValid():
            self._drop_line = None
            self.viewport().update()
            return
        rect = self.visualRect(idx)
        # Drop-before-this-item if cursor is in its left half, else drop-after.
        before = pos.x() < rect.center().x()
        if before:
            other_idx = self.model().index(idx.row() - 1, 0) if idx.row() > 0 else None
            if other_idx is not None and other_idx.isValid():
                left_rect  = self.visualRect(other_idx)
                right_rect = rect
                # Only stack horizontally when items are on the same row.
                if abs(left_rect.center().y() - right_rect.center().y()) < rect.height() / 2:
                    x = (left_rect.right() + right_rect.left()) // 2
                    y0 = min(left_rect.top(), right_rect.top())
                    y1 = max(left_rect.bottom(), right_rect.bottom())
                    self._drop_line = (x, y0, y1)
                else:
                    self._drop_line = (rect.left() - 2, rect.top(), rect.bottom())
            else:
                self._drop_line = (rect.left() - 2, rect.top(), rect.bottom())
        else:
            other_idx = self.model().index(idx.row() + 1, 0)
            if other_idx is not None and other_idx.isValid():
                left_rect  = rect
                right_rect = self.visualRect(other_idx)
                if abs(left_rect.center().y() - right_rect.center().y()) < rect.height() / 2:
                    x = (left_rect.right() + right_rect.left()) // 2
                    y0 = min(left_rect.top(), right_rect.top())
                    y1 = max(left_rect.bottom(), right_rect.bottom())
                    self._drop_line = (x, y0, y1)
                else:
                    self._drop_line = (rect.right() + 2, rect.top(), rect.bottom())
            else:
                self._drop_line = (rect.right() + 2, rect.top(), rect.bottom())
        self.viewport().update()

    def dragLeaveEvent(self, ev) -> None:  # noqa: N802
        self._drop_line = None
        self.viewport().update()
        super().dragLeaveEvent(ev)

    def dropEvent(self, ev) -> None:  # noqa: N802
        self._drop_line = None
        super().dropEvent(ev)
        self.viewport().update()

    def paintEvent(self, ev) -> None:  # noqa: N802
        super().paintEvent(ev)
        if self._drop_line is None:
            return
        x, y0, y1 = self._drop_line
        p = QPainter(self.viewport())
        # Magenta accent — matches the app's drag/active highlight family.
        p.setPen(QPen(QColor(SPEC_MAGENTA), 2))
        p.drawLine(x, y0, x, y1)
        p.end()


# ---------------------------------------------------------------------------
# Clickable preview (for per-spacer selection in spacer mode)
# ---------------------------------------------------------------------------
class _PreviewLabel(QLabel):
    """Preview QLabel supporting single click + click-drag marquee.

    ``clicked`` fires on a release where the mouse barely moved (treated as a
    plain click). ``marquee_finished`` fires when the press-and-drag covered
    more than a few pixels (treated as a selection rectangle). Both positions
    are in label coordinates; the dialog maps them to image pixels.
    """

    clicked = pyqtSignal(QPoint, object)            # pos, keyboard modifiers
    marquee_finished = pyqtSignal(QRect, object)    # rect, keyboard modifiers
    resized = pyqtSignal()                           # geometry change
    _CLICK_PX = 4               # movement under this is still a click

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._press: QPoint | None = None
        self._drag_rect: QRect | None = None

    def set_base_pixmap(self, pm: QPixmap | None) -> None:
        """Show the given pixmap. QLabel draws DPR-aware pixmaps at logical
        size with full retina resolution — no compositing needed here; the
        marquee is painted on top in :meth:`paintEvent`."""
        if pm is not None:
            self.setPixmap(pm)

    def resizeEvent(self, ev) -> None:  # noqa: N802
        super().resizeEvent(ev)
        self.resized.emit()

    def mousePressEvent(self, ev) -> None:  # noqa: N802
        if ev.button() == Qt.MouseButton.LeftButton:
            self._press = ev.position().toPoint()
            self._drag_rect = None
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev) -> None:  # noqa: N802
        if self._press is not None:
            cur = ev.position().toPoint()
            self._drag_rect = QRect(self._press, cur).normalized()
            self.update()
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev) -> None:  # noqa: N802
        if ev.button() == Qt.MouseButton.LeftButton and self._press is not None:
            end = ev.position().toPoint()
            mods = ev.modifiers()
            dx = abs(end.x() - self._press.x())
            dy = abs(end.y() - self._press.y())
            if dx <= self._CLICK_PX and dy <= self._CLICK_PX:
                self.clicked.emit(self._press, mods)
            else:
                self.marquee_finished.emit(
                    QRect(self._press, end).normalized(), mods)
            self._press = None
            self._drag_rect = None
            self.update()
        super().mouseReleaseEvent(ev)

    def paintEvent(self, ev) -> None:  # noqa: N802
        super().paintEvent(ev)        # QLabel renders the pixmap centred
        if self._drag_rect is not None:
            p = QPainter(self)
            p.setPen(QPen(QColor(SPEC_MAGENTA), 1, Qt.PenStyle.DashLine))
            p.setBrush(QColor(255, 69, 115, 60))
            p.drawRect(self._drag_rect)
            p.end()


# ---------------------------------------------------------------------------
# Right-panel scroll area with a top/bottom fade gradient.
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# New-chart setup
# ---------------------------------------------------------------------------
class _NewChartDialog(QDialog):
    """New-chart setup: source (targen seed / pasted colours / generated
    sets) plus the printtarg layout knobs that affect rendering."""

    def __init__(self, bin_dir: Path, settings=None,
                 parent: QWidget | None = None,
                 initial_recipe: dict | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("New patch set"))
        self.setMinimumWidth(620)
        self._bin_dir = bin_dir
        self._settings = settings
        # The chart's stored creation recipe, if reopened from a chart that has
        # one — applied instead of the app-wide last-used state (see the restore
        # in __init__ below). The window reports its own recipe back via
        # result_recipe so the editor can persist it.
        self._initial_recipe = initial_recipe
        self.result_recipe: dict | None = None
        self.result_spec: R.ChartSpec | None = None
        self.result_program: list[tuple] | None = None
        self.result_options: R.LayoutOptions | None = None
        self.result_basename: str = "chart"
        # Honest OOG note from the perceptual bridge (#72, appendix B) — set
        # by _build_generated_program_nch, surfaced by the editor's status.
        self.nch_moved_note: str = ""
        # Engine layout-mode the user picked in the Chart section (only
        # meaningful when the engine is on); the editor applies these to the
        # new chart's recipe (#93).
        self.result_engine_clip: bool = True
        self.result_engine_nocap: bool = False
        self.result_engine_density: int = 1
        # Magenta accents on checked / focused state — same scoped rules
        # as the parent dialog so the New-chart dialog matches it instead
        # of falling back to the app-wide cyan.
        self._install_magenta_accents()

        # Content lives in a scroll area so the dialog fits small screens even
        # with every colour set expanded (the panel can get tall).
        content = QWidget(self)
        lay = QVBoxLayout(content)
        lay.setSpacing(10)

        head = QHBoxLayout()
        # Tab-style heading (uppercase eyebrow + large serif title), matching
        # the main-window tab headers, in the editor's magenta accent. Lives at
        # the top of the dialog above a full-width spectrum stripe (added to
        # ``outer`` below), so the 3D-cube preview starts beneath it.
        head.setContentsMargins(16, 12, 16, 0)
        head.addWidget(TabHeader(
            tr("NEW PATCH SET · SETUP"), tr("Set up your patch set"),
            SPEC_MAGENTA, self), 0, Qt.AlignmentFlag.AlignVCenter)
        GradientOverlay(SPEC_MAGENTA, parent=self, alpha=15, height=95, on_top=False)
        head.addStretch(1)
        head.addWidget(_magenta_tip(
            tr("New patch set"),
            tr(_NEW_CHART_TIP_INTRO) + "\n\n" + tr(_GEN_SETS_HELP)
            + "\n\n" + tr(_NEW_CHART_TIP_CLOSING),
            self, min_width=520))
        # NB: ``head`` is added to the dialog's ``outer`` layout (above the
        # full-width spectrum stripe), not to the scrolled content, so the
        # heading spans the window and the cube preview sits below it.

        # --- Load setup from preset (#55) ------------------------------------
        # Create Chart presets that were saved carrying a creation recipe
        # (Set B) can be reloaded here in one go — colour sets, instrument /
        # paper and layout. The row is ALWAYS shown (even with no qualifying
        # presets) so the layout stays consistent and users know it's there
        # (Knut's request); the list is just "None" until a preset with a saved
        # setup exists. Selecting one applies its recipe to the whole window.
        self._preset_recipes = self._available_preset_recipes()
        pr_row = QHBoxLayout()
        pr_row.addWidget(QLabel(tr("Load setup from preset:")))
        self._preset_setup_combo = NoScrollComboBox(self)
        self._preset_setup_combo.addItem(tr("None"), None)
        for pname in self._preset_recipes:
            self._preset_setup_combo.addItem(pname, pname)
        _as_compact(self._preset_setup_combo)
        self._preset_setup_combo.activated.connect(
            self._on_preset_setup_selected)
        pr_row.addWidget(self._preset_setup_combo, 1)
        pr_row.addWidget(_magenta_tip(
            tr("Load setup from preset"),
            tr("Load the full New-chart setup — colour sets, instrument, "
               "paper and layout — that was saved with a preset, so you can "
               "reuse or tweak an existing design instead of setting "
               "everything by hand.\n\nOnly presets saved with such a setup "
               "show up here, so the list stays empty (just \"None\") until "
               "you save one.\n\nThe ready-made \u201cby Pharmacist\u201d "
               "charts are not in this list. Each of those is a finished chart "
               "that is already laid out and ready to print, so there is no "
               "setup behind it to load \u2014 pick one straight from the "
               "\u201cPresets\u201d list in Create Chart instead.")))
        lay.addLayout(pr_row)

        # --- Chart identity --------------------------------------------------
        # The chart name is no longer asked for here — it's chosen later when
        # the chart is saved (Save & apply), which is what becomes the folder
        # and file names. The basename stays a neutral "chart" placeholder
        # until then (see _on_ok / result_basename).
        chart_box = QGroupBox(tr("Chart"), self)
        cg = QGridLayout(chart_box)
        cg.addWidget(QLabel(tr("Instrument:")), 0, 0)
        self._instr = NoScrollComboBox(chart_box)
        for code, label in _INSTRUMENTS:
            self._instr.addItem(label, code)
        cg.addWidget(self._instr, 0, 1)
        # Breathing room between the instrument combo and the Paper label so the
        # two controls don't read as one run-on field.
        _paper_lbl = QLabel(tr("Paper:"))
        _paper_lbl.setContentsMargins(20, 0, 0, 0)
        cg.addWidget(_paper_lbl, 0, 2)
        self._paper = NoScrollComboBox(chart_box)
        for code in _PAPER_ORDER:
            self._paper.addItem(
                _PAPER_LABELS_WITH_CUSTOM.get(code, code), code)
        _as_compact(self._instr, self._paper)
        # The compact closed combo (max-height 22px) otherwise yields cramped
        # dropdown rows; give each popup view a comfortable row height so the
        # open list is easy to read. Scoped to these two combos' views only.
        for _cb in (self._instr, self._paper):
            _cb.view().setStyleSheet(
                "QAbstractItemView::item { min-height: 28px; padding: 3px 8px; }")
        # Default to A4 portrait
        ix = self._paper.findData("A4")
        if ix >= 0:
            self._paper.setCurrentIndex(ix)
        cg.addWidget(self._paper, 0, 3)
        # Custom W/H row appears under the paper combo when "Custom" is
        # selected — same UX as the Create Chart tab.
        self._paper_custom_row = QWidget(chart_box)
        cust_l = QHBoxLayout(self._paper_custom_row)
        cust_l.setContentsMargins(0, 0, 0, 0)
        cust_l.setSpacing(6)
        cust_l.addWidget(QLabel(tr("W (mm):")))
        self._paper_w = NoScrollSpinBox(self._paper_custom_row)
        self._paper_w.setRange(10, 9999)
        self._paper_w.setValue(210)
        cust_l.addWidget(self._paper_w)
        cust_l.addWidget(QLabel(tr("H (mm):")))
        self._paper_h = NoScrollSpinBox(self._paper_custom_row)
        self._paper_h.setRange(10, 9999)
        self._paper_h.setValue(297)
        cust_l.addWidget(self._paper_h)
        cust_l.addStretch(1)
        _as_compact(self._paper_w, self._paper_h)
        self._paper_custom_row.setVisible(False)
        # Sit the W/H row directly under the Paper combo it belongs to (cols 2–3)
        # instead of stranded on the far left under "Instrument".
        cg.addWidget(self._paper_custom_row, 1, 2, 1, 2)
        # Keep the two control columns balanced so the Instrument/Paper combos
        # get equal width and the row doesn't crowd the label gap.
        cg.setColumnStretch(1, 1)
        cg.setColumnStretch(3, 1)
        self._paper.currentIndexChanged.connect(self._on_paper_changed)

        # --- Engine layout mode (Chart section) -----------------------------
        # When the ChromIQ engine is on, a few layout choices that change how
        # many patches fit a page belong here in the Chart section (the
        # printtarg "Layout options" group below is hidden). Strip readers get
        # clip-border on/off + uncapped strip length; the ColorMunki gets the
        # density dropdown (freehand / rig / highest) (#93).
        self._engine_on = bool(
            self._settings is not None
            and self._settings.get("use_chromiq_layout_engine", False))
        self._engine_mode_row = QWidget(chart_box)
        em = QHBoxLayout(self._engine_mode_row)
        em.setContentsMargins(0, 0, 0, 0)
        em.setSpacing(12)
        self._eng_clip = QCheckBox(tr("Clip border"), self._engine_mode_row)
        self._eng_clip.setChecked(True)
        self._eng_clip.setToolTip(tr("i1Pro / 3+ only. Reserve the left edge of "
                                     "each strip for the clip-on border the "
                                     "instrument needs to find the strip. Turn "
                                     "off to free that space for patches."))
        self._eng_nocap = QCheckBox(tr("Don't cap strip length"), self._engine_mode_row)
        self._eng_nocap.setToolTip(tr("i1Pro / 3+ only. Let a strip run the full "
                                      "height of the page instead of being "
                                      "limited to one instrument pass."))
        self._eng_density_lbl = QLabel(tr("Density:"), self._engine_mode_row)
        self._eng_density = NoScrollComboBox(self._engine_mode_row)
        self._eng_density.addItem(tr("Freehand"), 1)
        self._eng_density.addItem(tr("Rig (high density)"), 2)
        self._eng_density.addItem(tr("Highest density"), 3)
        self._eng_density.setToolTip(tr("ColorMunki only. Freehand spaces strips "
                                        "for hand-held reading; the higher "
                                        "densities pack more strips per page for "
                                        "use with a guide rig."))
        _as_compact(self._eng_density)
        em.addWidget(self._eng_clip)
        em.addWidget(self._eng_nocap)
        em.addWidget(self._eng_density_lbl)
        em.addWidget(self._eng_density)
        em.addStretch(1)
        cg.addWidget(self._engine_mode_row, 2, 0, 1, 4)
        # How many patches fit one page with the current instrument / paper /
        # mode. Lives in the Chart section and uses a theme-aware colour so it
        # reads in both light and dark mode.
        self._engine_cap_hint = QLabel("", chart_box)
        self._engine_cap_hint.setStyleSheet(
            "color: palette(text); font-size: 11px; font-style: italic;")
        cg.addWidget(self._engine_cap_hint, 3, 0, 1, 4)
        self._engine_mode_row.setVisible(self._engine_on)
        self._engine_cap_hint.setVisible(self._engine_on)
        self._eng_clip.toggled.connect(self._update_engine_cap_hint)
        self._eng_nocap.toggled.connect(self._update_engine_cap_hint)
        self._eng_density.currentIndexChanged.connect(self._update_engine_cap_hint)
        # The whole "Chart" (layout) frame is removed from the New Patch Set
        # window (Knut #93): instrument / paper / clip / density / pages are layout
        # concerns owned by the Create Chart tab. The widgets stay constructed
        # (hidden, defaulting to i1 / A4) so the patch-set result still carries a
        # placeholder spec — Create Chart applies the real layout on apply.
        chart_box.setVisible(False)

        # --- Device (multi-ink patch data, #72) -------------------------------
        # Which inks the chart's device values address. Print RGB (default)
        # keeps the dialog exactly as it always was; CMYK / CMYK + extra inks
        # reveal the ink limit + optional preconditioning profile and re-gate
        # the colour sets (the three-state model). This is a patch-data
        # concern, so it lives here — layout stays with the Create Chart tab.
        dev_box = QGroupBox(tr("Device"), self)
        dvg = QGridLayout(dev_box)
        dvg.addWidget(QLabel(tr("Device type:")), 0, 0)
        self._device_type = NoScrollComboBox(dev_box)
        self._device_type.addItem(tr("Print RGB"), "rgb")
        self._device_type.addItem(tr("CMYK"), "cmyk")
        self._device_type.addItem(tr("CMYK + extra inks"), "cmykplus")
        _as_compact(self._device_type)
        dvg.addWidget(self._device_type, 0, 1)
        dvg.addWidget(_magenta_tip(
            tr("Device type"),
            tr("Tells the chart which inks your printer actually uses, so "
               "every patch is a colour your printer can really put on "
               "paper.\n\n"
               "  • Print RGB — standard photo inkjets driven as RGB (the "
               "usual choice). Everything works with no extra setup, exactly "
               "as before.\n"
               "  • CMYK — four-ink printers and presses driven through a "
               "RIP.\n"
               "  • CMYK + extra inks — wide-gamut devices with orange, "
               "green, violet or light inks. Add each extra ink below; the "
               "chart then carries one value per ink, per patch.\n\n"
               "Two things appear for anything other than RGB:\n"
               "  • Ink limit — stops patches from laying down more total ink "
               "than the paper can take (see its own ⓘ).\n"
               "  • Preconditioning profile — optional; unlocks the "
               "look-based colour sets. Its tooltip walks you through the "
               "whole two-pass workflow.\n\n"
               "Heads-up: multi-ink charts are saved as press-ready files for "
               "your RIP — ChromIQ's own Print button is for RGB charts.")), 0, 2)
        dvg.setColumnStretch(1, 1)

        # Extra-ink slots — inline progressive reveal like the Manual tab's -D
        # stacking: pick an ink to add it as a removable chip, no pop-ups.
        self._nch_inks_row = QWidget(dev_box)
        self._nch_inks_row.setObjectName("nch_inks_row")
        irow = QHBoxLayout(self._nch_inks_row)
        irow.setContentsMargins(0, 0, 0, 0)
        irow.setSpacing(6)
        irow.addWidget(QLabel(tr("Extra inks:")))
        self._nch_chip_bar = QHBoxLayout()
        self._nch_chip_bar.setSpacing(4)
        irow.addLayout(self._nch_chip_bar)
        self._nch_add_ink = NoScrollComboBox(self._nch_inks_row)
        self._nch_add_ink.addItem(tr("Add ink…"), "")
        for code, label in self._extra_ink_labels().items():
            self._nch_add_ink.addItem(label, code)
        _as_compact(self._nch_add_ink)
        self._nch_add_ink.activated.connect(self._on_add_ink)
        irow.addWidget(self._nch_add_ink)
        self._nch_inkset_lbl = QLabel("", self._nch_inks_row)
        self._nch_inkset_lbl.setStyleSheet(
            "color: palette(text); font-style: italic;")
        irow.addWidget(self._nch_inkset_lbl)
        irow.addStretch(1)
        dvg.addWidget(self._nch_inks_row, 1, 0, 1, 3)

        # Ink limit — first-class and always visible for multi-ink devices.
        self._nch_limit_row = QWidget(dev_box)
        self._nch_limit_row.setObjectName("nch_limit_row")
        lrow = QHBoxLayout(self._nch_limit_row)
        lrow.setContentsMargins(0, 0, 0, 0)
        lrow.setSpacing(6)
        lrow.addWidget(QLabel(tr("Ink limit:")))
        self._ink_limit = NoScrollSpinBox(self._nch_limit_row)
        self._ink_limit.setRange(40, 400)
        self._ink_limit.setValue(300)
        self._ink_limit.setSuffix(" %")
        self._ink_limit.setObjectName("compact_input")
        _as_compact(self._ink_limit)
        lrow.addWidget(self._ink_limit)
        self._limit_tip = _magenta_tip(
            tr("Ink limit"),
            tr("The most total ink one patch may lay down, as a percentage. "
               "100 % per ink — so a four-ink printer could in theory reach "
               "400 %, but real paper can't hold that: it soaks, warps and "
               "dries slowly, and the measurement gets unreliable.\n\n"
               "A safe starting point is 300 % for coated inkjet papers (many "
               "presses use 260–330 %). Your RIP or paper vendor often states "
               "the right value — if so, use theirs.\n\n"
               "Why it matters twice:\n"
               "  • Chart time (here): patches over the limit are never "
               "printed, so the chart only contains colours your paper can "
               "actually hold.\n"
               "  • Profile time: the same limit is passed to the profile "
               "builder, so the finished profile never asks the printer for "
               "more ink than the chart tested. ChromIQ keeps the two in "
               "sync for you."))
        lrow.addStretch(1)
        # Limit row spans the content columns; its ⓘ sits in the shared
        # right-edge icon column, aligned under the other ⓘs (Basti).
        dvg.addWidget(self._nch_limit_row, 2, 0, 1, 2)
        # The ⓘ lives in the shared right-edge icon column (not inside the row),
        # so it must be hidden explicitly alongside the row for RGB devices.
        dvg.addWidget(self._limit_tip, 2, 2)

        # Preconditioning profile — optional; unlocks the look-based sets.
        self._nch_prof_row = QWidget(dev_box)
        self._nch_prof_row.setObjectName("nch_prof_row")
        prow = QGridLayout(self._nch_prof_row)
        prow.setContentsMargins(0, 0, 0, 0)
        prow.setHorizontalSpacing(6)
        _prof_lbl = QLabel(tr("Preconditioning profile (optional):"),
                           self._nch_prof_row)
        prow.addWidget(_prof_lbl, 0, 0, 1, 4)
        prow.addWidget(_magenta_tip(
            tr("Preconditioning profile (optional)"),
            tr("A profile here turns on the \"look-based\" colour sets — skin "
               "tones, blues, greens, sunrises, pastels and From image — for "
               "multi-ink printers (CMYK and CMYK + extra inks). You don't "
               "need one to make a chart; it only adds these extra sets. "
               "Here's the full picture, and why each step makes a better "
               "profile.\n\n"
               "The catch with multi-ink printers: a colour like \"skin\" or "
               "\"sky blue\" can be mixed from many different ink "
               "combinations, and the app can't know which inks make which "
               "colour until it has measured your printer at least once. So "
               "the recommended path is a two-pass loop:\n\n"
               "  Pass 1 — Even coverage (no profile yet)\n"
               "    • Leave this box empty and build the chart from \"Even "
               "coverage\".\n"
               "    • This spreads patches evenly across all your inks, so "
               "the first profile learns the whole printer, not just one "
               "area.\n"
               "    • Print it with colour management OFF, measure it, and "
               "build your first profile. It won't be perfect — that's "
               "expected.\n\n"
               "  Pass 2 — Refine where it matters (with this profile)\n"
               "    • Come back here and choose that first profile (or any "
               "profile built for this exact printer and ink set).\n"
               "    • The app now knows, roughly, which ink mix makes which "
               "colour — so the look-based sets light up. Tick the ones you "
               "care about: skin tones for portraits, blues and greens for "
               "landscapes, pastels for soft photo tones, or From image to "
               "match a specific picture.\n"
               "    • The app places extra patches exactly in those colours, "
               "plus wherever the first profile was weakest. Print, measure "
               "and rebuild.\n"
               "    • The second profile is sharpened where your eyes are "
               "most critical — without wasting patches on colours you "
               "rarely print.\n\n"
               "Good to know:\n"
               "  • The profile must match the device type you picked (same "
               "inks, same number of channels). A mismatch is flagged right "
               "here, before you build.\n"
               "  • The look-based patches are best guesses from your first "
               "profile about where each colour sits. The real measurement "
               "is what defines the final profile, so a slightly-off guess "
               "still gives a solid result.\n"
               "  • Prefer a profile built on the same paper and settings "
               "you'll profile with.")), 0, 4)
        self._nch_prof_edit = QLineEdit(self._nch_prof_row)
        self._nch_prof_edit.setReadOnly(True)
        self._nch_prof_edit.setPlaceholderText(
            tr("(none — look-based sets need one)"))
        _as_compact(self._nch_prof_edit)
        prow.addWidget(self._nch_prof_edit, 1, 0)
        # Square icon-sized buttons matching the compact field height —
        # QPushButton otherwise pads to a wide default (Basti's live review).
        self._nch_prof_browse = QPushButton(self._nch_prof_row)
        self._nch_prof_browse.setIcon(load_magenta_folder_icon())
        self._nch_prof_browse.setToolTip(tr("Choose an ICC profile…"))
        self._nch_prof_browse.setObjectName("compact_input")
        # The app-wide QPushButton QSS sets min-width: 72px, which overrides
        # setFixedWidth (stylesheet minimums win over widget constraints) —
        # relax it per-widget so these stay icon-sized square buttons.
        self._nch_prof_browse.setStyleSheet(
            "min-width: 20px; max-width: 20px; padding: 1px 4px;")
        self._nch_prof_browse.clicked.connect(self._browse_precond)
        prow.addWidget(self._nch_prof_browse, 1, 1)
        self._nch_prof_clear = QPushButton("×", self._nch_prof_row)
        self._nch_prof_clear.setToolTip(tr("Clear the profile"))
        self._nch_prof_clear.setObjectName("compact_input")
        self._nch_prof_clear.setStyleSheet(
            "min-width: 20px; max-width: 20px; padding: 1px 4px;")
        self._nch_prof_clear.clicked.connect(self._clear_precond)
        prow.addWidget(self._nch_prof_clear, 1, 2)
        self._nch_prof_status = QLabel("", self._nch_prof_row)
        self._nch_prof_status.setWordWrap(True)
        prow.addWidget(self._nch_prof_status, 2, 0, 1, 5)
        prow.setColumnStretch(0, 1)
        dvg.addWidget(self._nch_prof_row, 3, 0, 1, 3)

        self._precond_path: str = ""
        self._extra_inks: list[str] = []
        self._device_type.currentIndexChanged.connect(self._refresh_nch_state)
        lay.addWidget(dev_box)

        # --- Source ---------------------------------------------------------
        src_box = QGroupBox(tr("Patches"), self)
        sl = QVBoxLayout(src_box)
        self._mode_seed = QRadioButton(tr("Seed from targen (optimised patch set)"), src_box)
        self._mode_paste = QRadioButton(tr("Paste colour values (or load a file)"), src_box)
        self._mode_seed.setChecked(True)
        sl.addWidget(self._mode_seed)
        seed_row = QHBoxLayout()
        seed_row.addSpacing(22)
        seed_row.addWidget(QLabel(tr("Patches:")))
        self._count = NoScrollSpinBox(src_box)
        self._count.setRange(8, 4000)
        self._count.setValue(200)
        self._count.setObjectName("compact_input")
        seed_row.addWidget(self._count)
        seed_row.addStretch(1)
        sl.addLayout(seed_row)
        sl.addWidget(self._mode_paste)
        paste_indent = QVBoxLayout()
        paste_indent.setContentsMargins(22, 0, 0, 0)
        self._paste_edit = QPlainTextEdit(src_box)
        self._paste_edit.setPlaceholderText(
            tr("One colour per line — hex (#ff00aa or ff00aa) or RGB "
            "(255,0,170 / 1.0 0 0.67). Scale auto-detected.")
        )
        self._paste_edit.setFixedHeight(110)
        paste_indent.addWidget(self._paste_edit)
        paste_btns = QHBoxLayout()
        load_btn = QPushButton(tr("Load from file…"), src_box)
        load_btn.setObjectName("compact_input")  # match the compact "Load image…" button
        load_btn.clicked.connect(self._load_paste_file)
        self._paste_status = QLabel("", src_box)
        self._paste_status.setStyleSheet("color: #888;")
        paste_btns.addWidget(load_btn)
        paste_btns.addStretch(1)
        paste_btns.addWidget(self._paste_status)
        paste_indent.addLayout(paste_btns)
        sl.addLayout(paste_indent)
        self._paste_edit.textChanged.connect(self._update_paste_count)
        self._paste_edit.textChanged.connect(self._do_push_live_preview)  # cube (#96)

        # Generate colour sets — combinable generators (#37). Each ticked set
        # contributes its patches, concatenated top-to-bottom into the program.
        self._mode_generate = QRadioButton(tr("Generate colour sets"), src_box)
        sl.addWidget(self._mode_generate)
        sl.addLayout(self._build_generate_panel(src_box))

        # Enable/disable subcontrols by mode
        self._mode_seed.toggled.connect(lambda on: self._count.setEnabled(on))
        for r in (self._mode_seed, self._mode_paste,
                  self._mode_generate):
            r.toggled.connect(self._refresh_source_widgets)
        self._refresh_source_widgets()
        lay.addWidget(src_box)

        # --- Layout options -------------------------------------------------
        opt_box = QGroupBox(tr("Layout options (printtarg)"), self)
        og = QGridLayout(opt_box)
        # Spacer-mode checkboxes wired as a mutex group, with the all-off
        # state permitted. "None" disables Spacer scale (-A) since there
        # are no spacers to scale.
        og.addWidget(QLabel(tr("Spacers:")), 0, 0)
        self._sp_colored = QCheckBox(tr("Coloured"), opt_box)
        self._sp_bw      = QCheckBox(tr("B&&W"), opt_box)
        self._sp_none    = QCheckBox(tr("None"), opt_box)
        self._sp_colored.setChecked(True)
        _wire_spacer_mutex((self._sp_colored, self._sp_bw, self._sp_none))
        sp_row = QHBoxLayout()
        for cb in (self._sp_colored, self._sp_bw, self._sp_none):
            sp_row.addWidget(cb)
        sp_row.addStretch(1)
        og.addLayout(sp_row, 0, 1, 1, 3)
        self._sp_none.toggled.connect(self._refresh_spacer_scale_enabled)

        og.addWidget(QLabel(tr("Patch scale (-a):")), 1, 0)
        self._patch_scale = NoScrollDoubleSpinBox(opt_box)
        self._patch_scale.setRange(0.3, 3.0)
        self._patch_scale.setSingleStep(0.05)
        self._patch_scale.setValue(1.0)
        og.addWidget(self._patch_scale, 1, 1)
        og.addWidget(QLabel(tr("Spacer scale (-A):")), 1, 2)
        self._spacer_scale = NoScrollDoubleSpinBox(opt_box)
        self._spacer_scale.setRange(0.3, 3.0)
        self._spacer_scale.setSingleStep(0.05)
        self._spacer_scale.setValue(1.0)
        og.addWidget(self._spacer_scale, 1, 3)

        # Margin / DPI / bit depth — match the Create Chart tab so the
        # editor offers the same printtarg knobs.
        og.addWidget(QLabel(tr("Margin (-m / -M, mm):")), 2, 0)
        self._margin = NoScrollSpinBox(opt_box)
        self._margin.setRange(0, 50)
        self._margin.setValue(6)
        self._margin.setToolTip(tr("Inter-strip and outer page margin in mm. "
                                "printtarg's default is 6."))
        og.addWidget(self._margin, 2, 1)
        og.addWidget(QLabel(tr("DPI:")), 2, 2)
        self._dpi = NoScrollSpinBox(opt_box)
        self._dpi.setRange(72, 1200)
        self._dpi.setSingleStep(50)
        self._dpi.setValue(300)
        og.addWidget(self._dpi, 2, 3)
        _as_compact(self._patch_scale, self._spacer_scale,
                    self._margin, self._dpi)

        og.addWidget(QLabel(tr("Bit depth:")), 3, 0)
        self._bd_8 = QRadioButton(tr("8-bit"), opt_box)
        self._bd_16 = QRadioButton(tr("16-bit"), opt_box)
        self._bd_8.setChecked(True)
        bd_grp = QButtonGroup(opt_box)
        bd_grp.addButton(self._bd_8)
        bd_grp.addButton(self._bd_16)
        bd_row = QHBoxLayout()
        bd_row.addWidget(self._bd_8)
        bd_row.addWidget(self._bd_16)
        bd_row.addStretch(1)
        og.addLayout(bd_row, 3, 1, 1, 3)

        # Instrument-conditional knobs — laid out in a self-contained 2-col
        # grid below the always-visible options. We toggle the *whole row*
        # visibility from the instrument signal so the dialog stays compact.
        self._cb_L = QCheckBox(tr("Suppress left clip border (-L)"), opt_box)
        self._cb_L.setToolTip(tr("i1Pro / 3+ only. Frees the strip for patches."))
        self._cb_P = QCheckBox(tr("Don't limit strip length (-P)"), opt_box)
        self._cb_P.setToolTip(tr("i1Pro / 3+ only. Lets a long strip span multiple "
                              "physical strokes for very tall charts."))
        self._cb_h = QCheckBox(tr("Double density (-h)"), opt_box)
        self._cb_h.setToolTip(tr("ColorMunki only. Tighter strip layout for the "
                              "ColorMunki rig. Mutually exclusive with Triple."))
        self._cb_td = QCheckBox(tr("Triple density (i1Pro layout emulation)"), opt_box)
        self._cb_td.setToolTip(
            tr("ColorMunki + rig only. Renders the chart with the i1Pro strip "
            "layout (printtarg -ii1) at the tuned scale (1.3) / margin (5) / "
            "strip-limit-off / left-border-suppressed preset, then patches "
            "TARGET_INSTRUMENT back to ColorMunki so chartread still drives "
            "your meter. Mutually exclusive with Double density.")
        )
        og.addWidget(self._cb_L,  4, 0, 1, 2)
        og.addWidget(self._cb_P,  4, 2, 1, 2)
        og.addWidget(self._cb_h,  5, 0, 1, 2)
        og.addWidget(self._cb_td, 5, 2, 1, 2)
        # Triple ↔ Double mutual exclusion + triple-density preset apply
        self._cb_td.toggled.connect(self._on_td_toggled)
        self._cb_h.toggled.connect(self._on_dd_toggled)
        self._cb_L.toggled.connect(self._update_engine_cap_hint)  # clip affects capacity
        # Initial visibility for the conditional rows
        self._instr.currentIndexChanged.connect(self._refresh_instr_widgets)
        self._refresh_instr_widgets()
        # The printtarg "Layout options" are removed too (Knut #93): this window
        # builds a PATCH SET only; the page layout is set in the Create Chart tab.
        # Kept constructed (hidden) so the result still carries placeholder values.
        opt_box.setVisible(False)
        _eng_note = QLabel(tr("This window builds a patch set. The page layout "
                              "(instrument, paper, margins, spacers…) is set in "
                              "the Create Chart tab."), self)
        _eng_note.setWordWrap(True)
        _eng_note.setStyleSheet("color: palette(mid); font-size: 11px;")
        lay.addWidget(_eng_note)

        btns = QHBoxLayout()
        restore = QPushButton(tr("Restore defaults"), self)
        restore.setToolTip(tr("Reset every setting on this window — instrument, "
                           "paper, layout options and colour sets — back to "
                           "their defaults."))
        restore.clicked.connect(self._restore_factory_defaults)
        btns.addWidget(restore)
        btns.addWidget(self._make_fold_button())
        btns.addStretch(1)
        ok = QPushButton(tr("Create"), self)
        ok.setDefault(True)
        ok.clicked.connect(self._on_ok)
        cancel = QPushButton(tr("Cancel"), self)
        cancel.clicked.connect(self.reject)
        btns.addWidget(ok)
        btns.addWidget(cancel)

        scroll = FadeScrollArea(self, surface="dialog")
        from ui.theme import resolve_mode
        scroll.set_appearance(resolve_mode(
            (self._settings.get("appearance", "auto") if self._settings else "auto")))
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        # Controls on the left (kept at their natural width so the options are
        # never clipped), the foldable live 3D cube on the right.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(head)
        outer.addWidget(_SpectrumStripe(self))
        outer.addLayout(self._build_body(scroll, content.sizeHint().width()), 1)
        btns.setContentsMargins(12, 4, 12, 10)
        outer.addLayout(btns)
        # Height fits common laptop screens; width follows the fold state.
        self._init_fold_state(760)

        # Initial device state (#72): default Print RGB hides the multi-ink
        # rows; a restored state below may re-reveal them.
        self._refresh_nch_state()

        # Prefer the chart's own creation recipe (reopened to tweak/recreate it);
        # otherwise restore the app-wide last-used state so creating another chart
        # doesn't start from scratch.
        if isinstance(self._initial_recipe, dict):
            self._apply_gen_state(self._initial_recipe)
        else:
            self._restore_gen_state()
        self._do_push_live_preview()   # seed the cube with the restored state

    # -- last-used settings persistence -----------------------------------
    # The widget suffixes whose checked/value state is remembered between
    # New-chart sessions (attribute = "_gen_<name>").
    _GEN_CHECKS = ("cube", "corners", "spirals", "skin", "blues", "greens",
                   "sunrises", "flamingos", "neutral", "nearneutral", "edges",
                   "hs", "pastel", "image", "whiteblack", "fill", "unique",
                   "fill_unit_pages")

    # Extra inks a CMYK device can add (#72) — ChromIQ ink codes (the
    # ui.tiff_preview convention); labels follow targen's own colorant list
    # and are translated at build time (literal tr() calls so the extractor
    # sees them). Order = Argyll's canonical colorant order.
    @staticmethod
    def _extra_ink_labels() -> dict[str, str]:
        return {
            "o": tr("Orange"), "r": tr("Red"), "g": tr("Green"),
            "b": tr("Blue"), "v": tr("Violet"), "w": tr("White"),
            "lc": tr("Light cyan"), "lm": tr("Light magenta"),
            "ly": tr("Light yellow"), "lk": tr("Light black"),
            "mc": tr("Medium cyan"), "mm": tr("Medium magenta"),
            "my": tr("Medium yellow"), "mk": tr("Medium black"),
            "llk": tr("Light-light black"),
        }

    _INK_DFLAG: dict[str, int] = {
        "c": 1, "m": 2, "y": 3, "k": 4, "o": 5, "r": 6, "g": 7, "b": 8,
        "v": 9, "w": 10, "lc": 11, "lm": 12, "ly": 13, "lk": 14,
        "mc": 15, "mm": 16, "my": 17, "mk": 18, "llk": 19,
    }

    # ---- Device / three-state model (#72) --------------------------------

    def _nch_device_type(self) -> str:
        """targen ``-d`` value for the chosen device type ("2" RGB, "4" CMYK…).

        The Add-patches dialog shares the generate panel but has no Device box
        (it always extends the loaded chart, whose colorspace is fixed) — it
        reports RGB here so all state-2/3 gating stays off.
        """
        if getattr(self, "_device_type", None) is None:
            return "2"
        return "2" if (self._device_type.currentData() in (None, "rgb")) else "4"

    def _nch_ink_codes(self) -> list[str]:
        """The effective ink set as ChromIQ ink codes (RGB → r/g/b)."""
        if self._nch_device_type() == "2":
            return ["r", "g", "b"]
        codes = ["c", "m", "y", "k"]
        if self._device_type.currentData() == "cmykplus":
            codes += [c for c in self._extra_inks if c not in codes]
        return codes

    def _nch_state(self) -> int:
        """1 = RGB (everything as today), 2 = multi-ink without a usable
        profile, 3 = multi-ink + channel-matching preconditioning profile."""
        if self._nch_device_type() == "2":
            return 1
        return 3 if (self._precond_path
                     and self._validate_precond(quiet=True)) else 2

    def _on_add_ink(self, index: int) -> None:
        code = self._nch_add_ink.itemData(index)
        self._nch_add_ink.setCurrentIndex(0)
        if not code or code in self._extra_inks:
            return
        self._extra_inks.append(code)
        self._refresh_nch_state()

    def _remove_ink(self, code: str) -> None:
        if code in self._extra_inks:
            self._extra_inks.remove(code)
            self._refresh_nch_state()

    def _rebuild_ink_chips(self) -> None:
        while self._nch_chip_bar.count():
            it = self._nch_chip_bar.takeAt(0)
            if it.widget() is not None:
                it.widget().deleteLater()
        labels = self._extra_ink_labels()
        for code in self._extra_inks:
            chip = QPushButton(f"{labels.get(code, code)} ×",
                               self._nch_inks_row)
            chip.setObjectName("compact_input")
            chip.setToolTip(tr("Remove this ink"))
            chip.clicked.connect(lambda _=False, c=code: self._remove_ink(c))
            self._nch_chip_bar.addWidget(chip)
        try:
            rep, _fields = R.color_rep_for_inks(self._nch_ink_codes())
            self._nch_inkset_lbl.setText(
                tr("→ ink set: {rep}").format(rep=rep)
                if self._nch_device_type() != "2" else "")
        except ValueError:
            self._nch_inkset_lbl.setText("")

    def _browse_precond(self) -> None:
        from ui.widgets import icc_profile_paths
        start = (self._settings.get("custom_output_path", "")
                 if self._settings else "") or str(Path.home() / "ChromIQ")
        path = open_file_dialog(
            self, tr("Choose preconditioning profile"),
            "ICC profiles (*.icc *.icm)", start_dir=start,
            extra_paths=icc_profile_paths())
        # macOS can hand focus to the editor window underneath when the file
        # dialog closes over two stacked modals — bring this window back on
        # top either way (picked or cancelled) (#72, Basti's live review).
        self.raise_()
        self.activateWindow()
        if not path:
            return
        self._precond_path = path
        self._refresh_nch_state()

    def _clear_precond(self) -> None:
        self._precond_path = ""
        self._refresh_nch_state()

    @staticmethod
    def _icc_channel_count(color_space: str) -> int | None:
        """Channel count for an ICC colour-space signature ('CMYK', '6CLR'…)."""
        cs = color_space.strip().upper()
        fixed = {"GRAY": 1, "RGB": 3, "CMY": 3, "CMYK": 4, "LAB": 3, "XYZ": 3}
        if cs in fixed:
            return fixed[cs]
        if cs.endswith("CLR") and len(cs) == 4:
            try:
                return int(cs[0], 16)
            except ValueError:
                return None
        return None

    def _validate_precond(self, quiet: bool = False) -> bool:
        """Inline profile-matches-device check (#72): the profile's colour
        space must carry exactly the chart's channel count. Updates the status
        label unless *quiet*."""
        if not self._precond_path:
            if not quiet:
                self._nch_prof_status.setText("")
            return False
        n_chart = len(self._nch_ink_codes())
        try:
            from workflow.icc_info import read_icc
            info = read_icc(self._precond_path)
        except Exception as exc:  # noqa: BLE001 — unreadable/foreign file
            if not quiet:
                self._nch_prof_status.setText(
                    tr("✗ Not a readable ICC profile: {err}").format(err=exc))
                self._nch_prof_status.setStyleSheet("color: #d9534f;")
            return False
        n_prof = self._icc_channel_count(info.color_space)
        rep, _ = R.color_rep_for_inks(self._nch_ink_codes())
        if n_prof != n_chart:
            if not quiet:
                self._nch_prof_status.setText(
                    tr("✗ Profile is {cs} ({np} channels) — this chart uses "
                       "{rep} ({nc} channels). Pick a profile made for this "
                       "exact printer and ink set.").format(
                        cs=info.color_space.strip(), np=n_prof or "?",
                        rep=rep, nc=n_chart))
                self._nch_prof_status.setStyleSheet("color: #d9534f;")
            return False
        if not quiet:
            desc = info.description or Path(self._precond_path).name
            self._nch_prof_status.setText(
                tr("✓ {desc} — {cs}, {n} channels — matches").format(
                    desc=desc, cs=info.color_space.strip(), n=n_chart))
            self._nch_prof_status.setStyleSheet("color: #5cb85c;")
        return True

    def _refresh_nch_state(self) -> None:
        """Show/hide the multi-ink rows and re-gate the source modes for the
        current state (1 RGB / 2 no-profile / 3 profile) — #72."""
        dt = self._device_type.currentData() or "rgb"
        multi = dt != "rgb"
        self._nch_inks_row.setVisible(dt == "cmykplus")
        self._nch_limit_row.setVisible(multi)
        self._limit_tip.setVisible(multi)   # ⓘ is in the grid, not the row
        self._nch_prof_row.setVisible(multi)
        self._rebuild_ink_chips()
        self._nch_prof_edit.setText(self._precond_path)
        if multi:
            self._validate_precond()
        self._apply_gen_state_gating(self._nch_state())
        self._update_gen_counts()
        self._do_push_live_preview()

    # Generator-row classification for the three-state model (#72): RGB-cube
    # constructs never generalise (a 9-step factorial in 7 channels is ~4.8 M
    # patches); look-based sets need the preconditioning profile; the rest is
    # N-native via the device adapters in workflow.patch_generators_nd.
    _GEN_CUBE_BOUND = ("cube", "edges", "corners", "spirals")
    _GEN_PERCEPTUAL = ("skin", "blues", "greens", "sunrises", "flamingos",
                       "hs", "pastel", "image")

    def _apply_gen_state_gating(self, state: int) -> None:
        """Gate the source modes + generator rows for the three-state model.

        State 1 (RGB): everything enabled, exactly as before #72. States 2/3:
        hex/RGB pasting is meaningless; the RGB-cube rows stay greyed forever
        (Even coverage is their replacement), the look-based rows unlock with
        a channel-matching profile (state 3), the N-native rows (neutral
        ramp, near-neutral rings, white/black, fill, unique) work in both.
        The 3D cube preview is an RGB-cube projection — hidden for multi-ink.
        """
        rgb = state == 1
        self._mode_paste.setEnabled(rgb)
        if not rgb and self._mode_paste.isChecked():
            self._mode_seed.setChecked(True)
        # Per-row gating + honest tooltips. Original RGB tooltips are stashed
        # once and restored on the way back to state 1.
        if not self._gen_orig_tooltips:
            for name in self._GEN_CUBE_BOUND + self._GEN_PERCEPTUAL + (
                    "nearneutral",):
                cb = getattr(self, f"_gen_{name}")
                self._gen_orig_tooltips[name] = cb.toolTip()
        tip_cube = tr(
            "These sets trace the corners and edges of the RGB colour cube, "
            "which only exists on RGB printers. \"Even coverage\" does the "
            "same job for multi-ink printers — it spreads patches across "
            "every ink combination your device can print.")
        tip_profile = tr(
            "This set places patches by how colours look (skin, sky, "
            "foliage…). On a multi-ink printer the app first needs a "
            "preconditioning profile, so it knows which ink mix produces "
            "each colour. Add one in the Preconditioning profile field above "
            "— its tooltip walks through the two-pass workflow, and the "
            "field accepts any profile made for this exact printer and ink "
            "set. On RGB printers this set is always available.")
        tip_rings_nch = tr(
            "Greys are where your eyes are pickiest, and where a printer "
            "drifts first. This set places rings of patches around the grey "
            "axis, so the profile learns exactly how much cyan, magenta and "
            "yellow your printer needs for a clean, cast-free neutral — the "
            "classic \"grey balance\" chart, built in.\n\n"
            "Without a preconditioning profile the rings are centred on "
            "equal amounts of C, M and Y. On a real printer that mix "
            "usually looks slightly warm or green — that's expected, and "
            "it's exactly why the rings exist: they bracket the neutral "
            "region generously, and the measurement finds the true neutral "
            "inside them. Tip: keep the ring offset at its default or "
            "larger here.\n\n"
            "With a preconditioning profile (see the field above) the same "
            "rings are re-centred on your printer's actual neutral, so "
            "every patch lands closer to where it matters most. Same "
            "checkbox — the app simply aims better once it knows your "
            "printer.")
        for name in self._GEN_CUBE_BOUND:
            cb = getattr(self, f"_gen_{name}")
            cb.setEnabled(rgb)
            cb.setToolTip(self._gen_orig_tooltips[name] if rgb else tip_cube)
        for name in self._GEN_PERCEPTUAL:
            cb = getattr(self, f"_gen_{name}")
            cb.setEnabled(rgb or state == 3)
            cb.setToolTip(self._gen_orig_tooltips[name] if rgb else
                          (tip_profile if state == 2 else
                           self._gen_orig_tooltips[name]))
        self._gen_nearneutral.setToolTip(
            self._gen_orig_tooltips["nearneutral"] if rgb else tip_rings_nch)
        for w in self._nch_gen_widgets:
            w.setVisible(not rgb)
        # The fold button lives next to the cube; hide both in state 2 (no
        # colour model — nothing honest to draw). State 3 keeps the panel:
        # it shows the Lab-space scatter via the profile (#72). Track the
        # intent with an explicit flag — widget isVisible() is always False
        # before the window is shown, so guarding on it made a RESTORED
        # multi-ink state keep the cube visible (Basti's live review). The
        # flag only acts on real transitions, so refreshes don't resize the
        # window through _on_fold_toggled.
        if getattr(self, "_cube_panel", None) is not None:
            hidden = getattr(self, "_nch_cube_hidden", False)
            want_hidden = state == 2
            if not want_hidden and hidden:
                self._nch_cube_hidden = False
                self._fold_btn.setVisible(True)
                self._on_fold_toggled(self._cube_shown)
            elif want_hidden and not hidden:
                self._nch_cube_hidden = True
                self._cube_panel.setVisible(False)
                self._fold_btn.setVisible(False)
    _GEN_SPINS = ("cube_n", "corners_edge", "spirals_end", "spirals_reach",
                  "skin_n", "skin_ranges", "blues_n", "blues_layers",
                  "greens_n", "greens_layers", "sunrises_n", "sunrises_layers",
                  "flamingos_n", "flamingos_layers",
                  "neutral_n", "nearneutral_n", "nearneutral_rings",
                  "nearneutral_off",
                  "edges_n", "edges_faces", "hs_n", "hs_reach",
                  "pastel_n", "pastel_layers", "image_n", "whiteblack_n",
                  "fill_to", "fill_pages")
    # Factory defaults — what "Restore defaults" resets the whole window to
    # (also the fresh-install state). Must mirror the inline widget defaults.
    # Covers the source mode, chart instrument/paper, the seed count, every
    # Layout-options knob and the colour sets, so one click puts every
    # parameter back to a known-good baseline.
    _GEN_FACTORY = {
        "mode": "seed",
        "instr": "i1",
        "paper": "A4",
        "paper_w": 210, "paper_h": 297,
        "count": 200,
        "layout": {"spacer_mode": "colored", "patch_scale": 1.0,
                   "spacer_scale": 1.0, "margin": 6, "dpi": 300,
                   "bit16": False, "L": False, "P": False, "h": False,
                   "td": False},
        "cb": {"cube": True, "corners": False, "spirals": False, "skin": True,
               "blues": True, "greens": True, "sunrises": True,
               "flamingos": True, "neutral": True, "nearneutral": True,
               "edges": False, "hs": False,
               "pastel": False, "image": False, "whiteblack": False,
               "fill": False, "unique": True, "fill_unit_pages": False},
        "sp": {"cube_n": 8, "corners_edge": 2, "spirals_end": 8,
               "spirals_reach": 16,
               "skin_n": 8, "skin_ranges": 3, "blues_n": 64,
               "blues_layers": 3, "greens_n": 64, "greens_layers": 3,
               "sunrises_n": 64, "sunrises_layers": 3,
               "flamingos_n": 64, "flamingos_layers": 3,
               "neutral_n": 16, "nearneutral_n": 16, "nearneutral_rings": 1,
               "nearneutral_off": 4,
               "edges_n": 1,
               "edges_faces": 0, "hs_n": 24, "hs_reach": 16, "pastel_n": 24,
               "pastel_layers": 2, "image_n": 24, "whiteblack_n": 1,
               "fill_to": 1000, "fill_pages": 1},
    }

    def _spacer_mode(self) -> str:
        """Current spacer-mode mutex selection (matches _on_ok's mapping)."""
        if self._sp_bw.isChecked():
            return "bw"
        if self._sp_none.isChecked():
            return "none"
        return "colored"

    def _collect_gen_sets(self) -> dict:
        """The colour-set checkboxes + size spins as a {"cb":…, "sp":…} dict.
        Shared by the New-chart persistence and the editor's Add dialog."""
        return {
            "cb": {n: getattr(self, f"_gen_{n}").isChecked()
                   for n in self._GEN_CHECKS},
            "sp": {n: getattr(self, f"_gen_{n}").value()
                   for n in self._GEN_SPINS},
        }

    @staticmethod
    def _migrate_legacy_gen_sets(st: dict) -> dict:
        """Translate a pre-split saved state into the new neutral generators.

        Before the split there was one combined **Near-neutral greys** (steps,
        rings, offset) plus the short-lived **More greys in between**. Map the
        combined set to **Neutral grey ramp** + **Near-neutral greys** by Knut's
        rule (same steps for both; near-neutrals carries the rings/offset, and is
        off when the old set had no rings), so old charts/recipes load forward
        with their settings intact instead of resetting to defaults. A no-op for
        states already in the new format. 'More greys in between' was transient,
        so it is dropped."""
        cb = st.get("cb") or {}
        sp = st.get("sp") or {}
        legacy_greys = "greys" in cb or "greys_n" in sp
        # Old Saturated-edges format carried an 'edges_auto' flag and used
        # 'edges_n' as a per-edge density (5, 7, …). The set was reworked (#78)
        # so 'edges_n' now means 'between' (1 = one patch midway), so an old
        # number over-generates massively — detect the old flag and reset.
        legacy_edges = "edges_auto" in cb or "edges_auto" in sp
        if not legacy_greys and not legacy_edges:
            return st                       # already new format
        cb = dict(cb)
        sp = dict(sp)
        if legacy_greys:
            steps = int(sp.get("greys_n", 16))
            rings = int(sp.get("greys_rings", 1))
            offset = int(sp.get("greys_off", 4))
            greys_on = bool(cb.get("greys", False))
            cb.setdefault("neutral", greys_on)
            cb.setdefault("nearneutral", greys_on and rings >= 1)
            sp.setdefault("neutral_n", steps)
            sp.setdefault("nearneutral_n", steps)
            sp.setdefault("nearneutral_rings", max(1, rings))
            sp.setdefault("nearneutral_off", offset)
            cb.pop("greys", None)
            cb.pop("greysmid", None)
            for k in ("greys_n", "greys_off", "greys_rings",
                      "greysmid_n", "greysmid_rings", "greysmid_off"):
                sp.pop(k, None)
        if legacy_edges:
            sp["edges_n"] = 1               # Knut: the new field should read 1
            sp.setdefault("edges_faces", 0)
            cb.pop("edges_auto", None)
            sp.pop("edges_auto", None)
        out = dict(st)
        out["cb"], out["sp"] = cb, sp
        return out

    def _apply_gen_sets(self, st: dict) -> None:
        """Set every colour-set checkbox + size spin from a {"cb":…, "sp":…} dict.

        An absent **checkbox** loads **off** (a preset is a complete spec, so a
        set the author didn't include must come up unticked — not enabled from
        the factory default, which is *on* for several sets). Absent **spin**
        values fall back to the factory baseline (a sensible number for an off
        control). Old states are migrated first: pre-split greys → ramp +
        near-neutrals, and the old per-edge 'edges_auto' format → the new
        'between' default (Knut). The factory-reset path passes a complete dict,
        so it is unaffected.

        Does not touch the source mode or any chart/layout widget, so subclasses
        without those can reuse it."""
        st = self._migrate_legacy_gen_sets(st)
        sp = st.get("sp") or {}
        for n in self._GEN_SPINS:
            w = getattr(self, f"_gen_{n}", None)
            val = sp.get(n, self._GEN_FACTORY["sp"].get(n))
            if w is not None and val is not None:
                try:
                    w.setValue(int(val))
                except (TypeError, ValueError):
                    pass
        cb = st.get("cb") or {}
        for n in self._GEN_CHECKS:
            w = getattr(self, f"_gen_{n}", None)
            if w is not None:
                # Absent → OFF. A preset is a complete spec, so a set the author
                # didn't include (e.g. saved before Flamingos existed) must load
                # unticked — never enabled from the factory default, which is *on*
                # for several sets (Knut). Factory-reset passes a full dict.
                w.setChecked(bool(cb.get(n, False)))
        # fill_unit_pages is one radio of a mutex: unchecking it above leaves
        # neither unit selected, so set its "patches" sibling to the complement
        # (absent in old recipes → patches, the pre-#100 behaviour).
        pages_w = getattr(self, "_gen_fill_unit_pages", None)
        patches_w = getattr(self, "_gen_fill_unit_patches", None)
        if pages_w is not None and patches_w is not None:
            patches_w.setChecked(not pages_w.isChecked())

    def _collect_gen_state(self) -> dict:
        mode = ("generate" if self._mode_generate.isChecked() else
                "paste" if self._mode_paste.isChecked() else "seed")
        # Multi-ink device settings (#72) ride along ONLY when a non-RGB
        # device type is chosen — the RGB state dict stays byte-identical to
        # pre-#72 (state-1 identity: old versions + old presets keep
        # round-tripping; see tests/test_gen_state1_identity.py).
        device = {}
        if self._nch_device_type() != "2":
            device = {"device": {
                "type": self._device_type.currentData(),
                "extra_inks": list(self._extra_inks),
                "ink_limit": int(self._ink_limit.value()),
                "precond": self._precond_path,
                # The device-gated generator rows persist WITH the device
                # (generator-requirements checklist: every row must survive
                # save/load, presets and the editor recipe) — inside this
                # sub-dict so the RGB state dict stays byte-identical (R1).
                "gen": {
                    "targen": self._nch_targen.isChecked(),
                    "targen_n": self._nch_targen_n.value(),
                    "perink": self._nch_perink.isChecked(),
                    "perink_n": self._nch_perink_n.value(),
                    "pairs": self._nch_pairs.isChecked(),
                    "pairs_n": self._nch_pairs_n.value(),
                    "triples": self._nch_triples.isChecked(),
                    "triples_n": self._nch_triples_n.value(),
                    "richblack": self._nch_richblack.isChecked(),
                    "richblack_n": self._nch_richblack_n.value(),
                    "richblack_k": self._nch_richblack_k.value(),
                },
            }}
        return {
            "mode": mode,
            **device,
            **self._collect_gen_sets(),
            "instr": self._instr.currentData(),
            "paper": self._paper.currentData(),
            "paper_w": self._paper_w.value(),
            "paper_h": self._paper_h.value(),
            "count": self._count.value(),
            "layout": {
                "spacer_mode": self._spacer_mode(),
                "patch_scale": self._patch_scale.value(),
                "spacer_scale": self._spacer_scale.value(),
                "margin": self._margin.value(),
                "dpi": self._dpi.value(),
                "bit16": self._bd_16.isChecked(),
                "L": self._cb_L.isChecked(),
                "P": self._cb_P.isChecked(),
                "h": self._cb_h.isChecked(),
                "td": self._cb_td.isChecked(),
            },
        }

    def _apply_gen_state(self, st: dict) -> None:
        """Set every window widget from a saved/factory state dict. Unknown /
        missing keys are skipped, so old saved states load forward-compatibly.

        Order matters: the instrument combo is set first (its change handler
        hides + clears the strip-only -L / -P knobs for non-strip readers), and
        within the layout block the density toggles run before the values they
        overwrite, so a restored triple-density preset doesn't get clobbered."""
        # Chart identity — instrument + paper (+ custom dimensions).
        instr = st.get("instr")
        if instr is not None:
            ix = self._instr.findData(instr)
            if ix >= 0:
                self._instr.setCurrentIndex(ix)
        paper = st.get("paper")
        if paper is not None:
            ix = self._paper.findData(paper)
            if ix >= 0:
                self._paper.setCurrentIndex(ix)
        for key, w in (("paper_w", self._paper_w), ("paper_h", self._paper_h),
                       ("count", self._count)):
            if key in st:
                try:
                    w.setValue(int(st[key]))
                except (TypeError, ValueError):
                    pass

        # Layout options. Spacer mode + density toggles first; their signal
        # handlers (mutex, triple-density preset) settle before we restore the
        # exact scale / margin / -L / -P values the user had saved.
        lo = st.get("layout") or {}
        sm = lo.get("spacer_mode")
        if sm == "bw":
            self._sp_bw.setChecked(True)
        elif sm == "none":
            self._sp_none.setChecked(True)
        elif sm == "colored":
            self._sp_colored.setChecked(True)
        if "h" in lo:
            self._cb_h.setChecked(bool(lo["h"]))
        if "td" in lo:
            self._cb_td.setChecked(bool(lo["td"]))
        if "L" in lo:
            self._cb_L.setChecked(bool(lo["L"]))
        if "P" in lo:
            self._cb_P.setChecked(bool(lo["P"]))
        if "patch_scale" in lo:
            self._patch_scale.setValue(float(lo["patch_scale"]))
        if "spacer_scale" in lo:
            self._spacer_scale.setValue(float(lo["spacer_scale"]))
        if "margin" in lo:
            self._margin.setValue(int(lo["margin"]))
        if "dpi" in lo:
            self._dpi.setValue(int(lo["dpi"]))
        if "bit16" in lo:
            (self._bd_16 if lo["bit16"] else self._bd_8).setChecked(True)

        # Multi-ink device settings (#72): absent key = RGB, matching every
        # pre-#72 saved state/preset (get()-with-default, R1 rule).
        dev = st.get("device") or {}
        dt = dev.get("type", "rgb")
        ix = self._device_type.findData(dt)
        self._device_type.setCurrentIndex(ix if ix >= 0 else 0)
        self._extra_inks = [c for c in dev.get("extra_inks", [])
                            if c in self._INK_DFLAG]
        try:
            self._ink_limit.setValue(int(dev.get("ink_limit", 300)))
        except (TypeError, ValueError):
            pass
        self._precond_path = str(dev.get("precond", "") or "")
        # Device-gated generator rows: restore with get()-defaults, and reset
        # to the factory baseline when no device state rides along (RGB state
        # or Restore-defaults) — the checklist's default-when-absent rule.
        gen = dev.get("gen") or {}
        self._nch_targen.setChecked(bool(gen.get("targen", True)))
        self._nch_perink.setChecked(bool(gen.get("perink", True)))
        self._nch_pairs.setChecked(bool(gen.get("pairs", True)))
        self._nch_triples.setChecked(bool(gen.get("triples", False)))
        self._nch_richblack.setChecked(bool(gen.get("richblack", False)))
        for key, spin, default in (("targen_n", self._nch_targen_n, 800),
                                   ("perink_n", self._nch_perink_n, 8),
                                   ("pairs_n", self._nch_pairs_n, 4),
                                   ("triples_n", self._nch_triples_n, 2),
                                   ("richblack_n", self._nch_richblack_n, 6),
                                   ("richblack_k", self._nch_richblack_k, 3)):
            try:
                spin.setValue(int(gen.get(key, default)))
            except (TypeError, ValueError):
                spin.setValue(default)
        self._refresh_nch_state()

        self._apply_gen_sets(st)
        # "blank" (the removed Blank-canvas mode) is deliberately absent: a
        # saved state or preset that carries it keeps the current selection.
        radio = {"generate": self._mode_generate, "paste": self._mode_paste,
                 "seed": self._mode_seed}.get(
                     st.get("mode"))
        if radio is not None and radio.isEnabled():
            # A disabled radio means the current device state gates that mode
            # (#72: paste/generate are RGB-only until Tier C) — keep the
            # gating's choice instead of re-checking it programmatically.
            radio.setChecked(True)
        self._refresh_source_widgets()

    # -- "Load setup from preset" (#55) -----------------------------------
    def _available_preset_recipes(self) -> dict:
        """Presets that carry a populated creation recipe (Set B), as
        ``{display_name: recipe_dict}``.

        Built-in Full-layout-setup presets (bundled recipes, shown with a ★) come first,
        then the user's Create Chart presets. Name collisions (#55): a custom
        preset identical to a built-in of the same name is dropped (the built-in
        already represents it); a custom that differs keeps its own name (the ★
        distinguishes the built-in)."""
        out: dict = {}
        builtin: dict = {}
        try:
            # Registry-driven: every built-in preset that carries a recipe, not a
            # single hardcoded file — so any preset holding settings shows up,
            # built-in or local (Knut).
            from ui.tabs.tab_chart import builtin_recipe_choices
            builtin = {k: v for k, v in builtin_recipe_choices().items()
                       if isinstance(v, dict) and v}
        except Exception:  # noqa: BLE001 — never block opening the window
            pass
        for name, rec in builtin.items():
            out[f"★ {name}"] = rec
        if self._settings is None:
            return out
        try:
            from core.preset_store import load_presets
            for name, payload in load_presets("create_chart", self._settings).items():
                rec = payload.get("editor_recipe") if isinstance(payload, dict) else None
                if not (isinstance(rec, dict) and rec):
                    continue
                if builtin.get(name) == rec:
                    continue  # identical to a built-in → already listed
                disp, n = name, 2
                while disp in out:        # keep every distinct recipe visible
                    disp, n = f"{name} ({n})", n + 1
                out[disp] = rec
        except Exception:  # noqa: BLE001
            pass
        return out

    def _on_preset_setup_selected(self, idx: int) -> None:
        name = self._preset_setup_combo.itemData(idx)
        rec = self._preset_recipes.get(name) if name else None
        if isinstance(rec, dict):
            self._apply_gen_state(rec)
            self._do_push_live_preview()

    def _save_gen_state(self) -> None:
        if self._settings is not None:
            self._settings.set("new_chart_gen", self._collect_gen_state())

    def _restore_gen_state(self) -> None:
        st = self._settings.get("new_chart_gen", None) if self._settings else None
        if isinstance(st, dict):
            self._apply_gen_state(st)

    def _restore_factory_defaults(self) -> None:
        """Reset every parameter in the window — source mode, instrument,
        paper, seed count, Layout options and the colour sets — back to its
        factory default."""
        self._apply_gen_state(self._GEN_FACTORY)

    # -- generate-colour-sets panel ---------------------------------------
    def _build_generate_panel(self, parent: QWidget) -> QVBoxLayout:
        """Build the combinable colour-set generators (#37) under the
        "Generate colour sets" radio: a checkbox + size control(s) + live
        count per generator, and a running total."""
        # Patches already on the chart we're adding to (empty for New-chart);
        # "Fill remaining gaps" counts these toward its target so it tops the
        # whole chart up rather than appending that many patches (#51).
        if not hasattr(self, "_existing_patches"):
            self._existing_patches = []
        indent = QVBoxLayout()
        indent.setContentsMargins(22, 0, 0, 0)
        self._gen_panel = QWidget(parent)
        gg = QGridLayout(self._gen_panel)
        gg.setContentsMargins(0, 0, 0, 0)
        gg.setHorizontalSpacing(8)
        gg.setVerticalSpacing(4)

        def _spin(lo: int, hi: int, val: int) -> NoScrollSpinBox:
            s = NoScrollSpinBox(self._gen_panel)
            s.setRange(lo, hi)
            s.setValue(val)
            s.setObjectName("compact_input")
            s.valueChanged.connect(self._update_gen_counts)
            return s

        def _count_label() -> QLabel:
            lb = QLabel("", self._gen_panel)
            lb.setStyleSheet("color: #888;")
            return lb

        # 3D RGB cube — N per axis ⇒ N³ patches.
        self._gen_cube = QCheckBox(tr("3D RGB cube"), self._gen_panel)
        self._gen_cube.setChecked(True)
        self._gen_cube.setToolTip(tr("An even N×N×N grid across the whole RGB "
                                  "range. N is the steps per axis."))
        self._gen_cube_n = _spin(2, 30, 8)
        self._gen_cube_count = _count_label()
        gg.addWidget(self._gen_cube, 5, 0)
        gg.addWidget(QLabel(tr("per axis:")), 5, 1)
        gg.addWidget(self._gen_cube_n, 5, 2)
        gg.addWidget(self._gen_cube_count, 5, 7)

        # Gamut-corner emphasis — extra patches ON the gamut edge lines near each
        # corner tip (TC9.18/TC9.24 style), slotted into the gaps the cube /
        # Saturated edges leave there. Grid row 2, right after the cube + edges.
        self._gen_corners = QCheckBox(tr("Gamut-corner emphasis"), self._gen_panel)
        self._gen_corners.setToolTip(tr("Adds a few extra patches right on the gamut "
                                     "edge lines next to each of the eight corners — "
                                     "the most saturated edges, where the deepest "
                                     "colours live and profiles err most. 'Edge' is "
                                     "how many to add per edge near each corner; "
                                     "they're slotted into the gaps so they never land "
                                     "on the patches the 3D cube or Saturated edges "
                                     "already place there. The exact corner tips come "
                                     "from the cube or Saturated edges when those are "
                                     "on, and from this set when they aren't, so a tip "
                                     "is never missing."))
        self._gen_corners_edge = _spin(1, 8, 2)
        self._gen_corners_count = _count_label()
        gg.addWidget(self._gen_corners, 7, 0)
        gg.addWidget(QLabel(tr("edge:")), 7, 1)
        gg.addWidget(self._gen_corners_edge, 7, 2)
        gg.addWidget(self._gen_corners_count, 7, 7)

        # Colour extremes — Highlights-&-shadows-style spiral cones just inside the
        # six chromatic corners. Placed directly above Highlights & shadows (grid
        # row 10): the two are the tonal/chromatic "extremes" pair, and the de-dup
        # then spaces this set against everything above it. White/black are left to
        # Highlights & shadows. 'per end' / 'reach' mirror H&S (reuses 'per end:').
        self._gen_spirals = QCheckBox(tr("Colour extremes"), self._gen_panel)
        self._gen_spirals.setToolTip(tr("Adds detail just inside the six most "
                                     "saturated colour corners of the printer's range "
                                     "— red, green, blue, cyan, magenta and yellow at "
                                     "their most vivid, which are the trickiest to "
                                     "reproduce. It works like Highlights & shadows, "
                                     "but spiralling in from each colour corner; white "
                                     "and black are left to Highlights & shadows, which "
                                     "already covers them. 'Per end' is how many "
                                     "patches at each corner; 'reach' how far in they "
                                     "spiral."))
        self._gen_spirals_end = _spin(1, 200, 8)   # max matches Pastels/H&S (Knut)
        self._gen_spirals_reach = _spin(2, 45, 16)
        self._gen_spirals_count = _count_label()
        gg.addWidget(self._gen_spirals, 15, 0)
        gg.addWidget(QLabel(tr("per end:")), 15, 1)
        gg.addWidget(self._gen_spirals_end, 15, 2)
        gg.addWidget(QLabel(tr("reach:")), 15, 3)
        gg.addWidget(self._gen_spirals_reach, 15, 4)
        gg.addWidget(self._gen_spirals_count, 15, 7)

        # Fitzpatrick skin tones — per-type ramp × parallel hue ranges.
        self._gen_skin = QCheckBox(tr("Skin tones (Fitzpatrick)"), self._gen_panel)
        self._gen_skin.setChecked(True)
        self._gen_skin.setToolTip(tr("Light→dark ramps through each of the six "
                                  "Fitzpatrick skin phototypes. 'Ranges' adds "
                                  "parallel ramps offset in hue for broader "
                                  "coverage."))
        self._gen_skin_n = _spin(1, 36, 8)
        self._gen_skin_ranges = _spin(1, 5, 3)
        self._gen_skin_count = _count_label()
        gg.addWidget(self._gen_skin, 8, 0)
        gg.addWidget(QLabel(tr("per type:")), 8, 1)
        gg.addWidget(self._gen_skin_n, 8, 2)
        gg.addWidget(QLabel(tr("ranges:")), 8, 3)
        gg.addWidget(self._gen_skin_ranges, 8, 4)
        gg.addWidget(self._gen_skin_count, 8, 7)

        # Enhanced blues / turquoise.
        self._gen_blues = QCheckBox(tr("Oceans (blues)"), self._gen_panel)
        self._gen_blues.setChecked(True)
        self._gen_blues.setToolTip(tr("Denser sampling of the green-turquoise→blue "
                                   "band wide-gamut spaces stretch furthest. "
                                   "Each of the 'layers' is a non-parallel sheet "
                                   "of 'per layer' patches, so the two multiply."))
        self._gen_blues_n = _spin(1, 200, 64)
        self._gen_blues_layers = _spin(1, 10, 3)
        self._gen_blues_count = _count_label()
        gg.addWidget(self._gen_blues, 9, 0)
        gg.addWidget(QLabel(tr("per layer:")), 9, 1)
        gg.addWidget(self._gen_blues_n, 9, 2)
        gg.addWidget(QLabel(tr("layers:")), 9, 3)
        gg.addWidget(self._gen_blues_layers, 9, 4)
        gg.addWidget(self._gen_blues_count, 9, 7)

        # Enhanced greens (foliage).
        self._gen_greens = QCheckBox(tr("Foliage (greens)"), self._gen_panel)
        self._gen_greens.setChecked(True)
        self._gen_greens.setToolTip(tr("Forest, jungle and foliage greens for "
                                    "nature images. Each of the 'layers' is a "
                                    "non-parallel sheet of 'per layer' patches, "
                                    "so the two multiply."))
        self._gen_greens_n = _spin(1, 200, 64)
        self._gen_greens_layers = _spin(1, 10, 3)
        self._gen_greens_count = _count_label()
        gg.addWidget(self._gen_greens, 10, 0)
        gg.addWidget(QLabel(tr("per layer:")), 10, 1)
        gg.addWidget(self._gen_greens_n, 10, 2)
        gg.addWidget(QLabel(tr("layers:")), 10, 3)
        gg.addWidget(self._gen_greens_layers, 10, 4)
        gg.addWidget(self._gen_greens_count, 10, 7)

        # Sunrises — the warm band (yellows, oranges, reds, pinks).
        self._gen_sunrises = QCheckBox(tr("Sunrises (warm)"), self._gen_panel)
        self._gen_sunrises.setChecked(True)
        self._gen_sunrises.setToolTip(tr("Golden yellows, oranges, reds and pinks "
                                      "— the warm 'sunrise' side of the gamut the "
                                      "blues and greens sets leave out, for skies, "
                                      "flowers and skin highlights. Each of the "
                                      "'layers' is a non-parallel sheet of 'per "
                                      "layer' patches, so the two multiply."))
        self._gen_sunrises_n = _spin(1, 200, 64)
        self._gen_sunrises_layers = _spin(1, 10, 3)
        self._gen_sunrises_count = _count_label()
        gg.addWidget(self._gen_sunrises, 11, 0)
        gg.addWidget(QLabel(tr("per layer:")), 11, 1)
        gg.addWidget(self._gen_sunrises_n, 11, 2)
        gg.addWidget(QLabel(tr("layers:")), 11, 3)
        gg.addWidget(self._gen_sunrises_layers, 11, 4)
        gg.addWidget(self._gen_sunrises_count, 11, 7)

        # Flamingos — the pink / magenta / indigo band the other bands leave out.
        self._gen_flamingos = QCheckBox(tr("Flamingos (pinks)"), self._gen_panel)
        self._gen_flamingos.setChecked(True)
        self._gen_flamingos.setToolTip(tr("Pinks, magentas and indigos — the band "
                                       "between where Oceans (blues) ends and "
                                       "Sunrises begins, the big gap the other "
                                       "colour-band sets leave in the middle. Great "
                                       "for flowers, fabrics, sunsets and skin. Each "
                                       "of the 'layers' is a non-parallel sheet of "
                                       "'per layer' patches, so the two multiply."))
        self._gen_flamingos_n = _spin(1, 200, 64)
        self._gen_flamingos_layers = _spin(1, 10, 3)
        self._gen_flamingos_count = _count_label()
        gg.addWidget(self._gen_flamingos, 12, 0)
        gg.addWidget(QLabel(tr("per layer:")), 12, 1)
        gg.addWidget(self._gen_flamingos_n, 12, 2)
        gg.addWidget(QLabel(tr("layers:")), 12, 3)
        gg.addWidget(self._gen_flamingos_layers, 12, 4)
        gg.addWidget(self._gen_flamingos_count, 12, 7)

        # Neutral grey ramp — pure greys black→white, no tints (a B&W wedge).
        # Independent of Near-neutral greys below, so the count of pure neutrals
        # is chosen separately from the near-neutral hue coverage.
        self._gen_neutral = QCheckBox(tr("Neutral grey ramp"), self._gen_panel)
        self._gen_neutral.setChecked(True)
        self._gen_neutral.setToolTip(tr("A plain neutral grey ramp from black to "
                                     "white — pure greys with no hue tints (a "
                                     "black-and-white wedge). This is the most "
                                     "important region for a clean profile. "
                                     "'Steps' is how many greys span black to "
                                     "white. Pair it with 'Near-neutral greys' "
                                     "below when you also want the gentle "
                                     "off-neutral tints; the two are independent, "
                                     "so you can have more pure greys than tinted "
                                     "ones, or either on its own."))
        self._gen_neutral_n = _spin(1, 64, 16)
        self._gen_neutral_count = _count_label()
        gg.addWidget(self._gen_neutral, 13, 0)
        gg.addWidget(QLabel(tr("steps:")), 13, 1)
        gg.addWidget(self._gen_neutral_n, 13, 2)
        gg.addWidget(self._gen_neutral_count, 13, 7)

        # Near-neutral greys — ONLY the rings of gentle hue tints around each
        # neutral level (no pure centre — that's the ramp's job above).
        self._gen_nearneutral = QCheckBox(tr("Near-neutral greys"),
                                          self._gen_panel)
        self._gen_nearneutral.setChecked(True)
        self._gen_nearneutral.setToolTip(tr("Rings of small hue tints just off the "
                                         "neutral axis at each grey level — what "
                                         "helps greys print cleanly without an "
                                         "unwanted colour cast. This adds only the "
                                         "tints (the pure grey centres come from "
                                         "'Neutral grey ramp' above). 'Steps' is "
                                         "how many levels from black to white get "
                                         "rings, 'rings' is how many rings circle "
                                         "each (6, 12, 18 tints) for a denser "
                                         "near-neutral cluster, and 'offset' sets "
                                         "the first ring's distance from neutral."))
        self._gen_nearneutral_n = _spin(1, 64, 16)
        self._gen_nearneutral_rings = _spin(1, 3, 1)
        self._gen_nearneutral_off = _spin(1, 50, 4)
        self._gen_nearneutral_count = _count_label()
        self._gen_nearneutral_off_label = QLabel(tr("offset:"))
        gg.addWidget(self._gen_nearneutral, 14, 0)
        gg.addWidget(QLabel(tr("steps:")), 14, 1)
        gg.addWidget(self._gen_nearneutral_n, 14, 2)
        gg.addWidget(QLabel(tr("rings:")), 14, 3)
        gg.addWidget(self._gen_nearneutral_rings, 14, 4)
        gg.addWidget(self._gen_nearneutral_off_label, 14, 5)
        gg.addWidget(self._gen_nearneutral_off, 14, 6)
        gg.addWidget(self._gen_nearneutral_count, 14, 7)

        # Saturated edges — the gamut boundary, locked to the 3D cube's grid so
        # the infill stays even at any density (Knut, #78). Placed directly under
        # the 3D cube (grid row 1) since the two are interdependent — the widgets
        # are built here but the grid row puts the controls right below the cube.
        self._gen_edges = QCheckBox(tr("Saturated edges"), self._gen_panel)
        self._gen_edges.setToolTip(tr("The most saturated colours the printer can "
                                   "reach — the boundary of the RGB cube, where "
                                   "profiles err most. This set works hand in hand "
                                   "with the 3D cube: 'between' drops that many "
                                   "patches evenly between each pair of neighbouring "
                                   "cube dots along the 12 cube edges (the gamut "
                                   "wireframe), and 'faces' does the same inside each "
                                   "square of the cube's 6 faces (the gamut surface), "
                                   "or 0 for edges only. Because the spacing is tied "
                                   "to the cube, the fill stays even at any setting "
                                   "(1 is one patch midway between each cube dot)."))
        self._gen_edges_n = _spin(0, 5, 1)
        self._gen_edges_faces = _spin(0, 5, 0)
        self._gen_edges_count = _count_label()
        gg.addWidget(self._gen_edges, 6, 0)
        gg.addWidget(QLabel(tr("between:")), 6, 1)
        gg.addWidget(self._gen_edges_n, 6, 2)
        gg.addWidget(QLabel(tr("faces:")), 6, 3)
        gg.addWidget(self._gen_edges_faces, 6, 4)
        gg.addWidget(self._gen_edges_count, 6, 7)

        # Highlights & shadows — detail at the two tonal ends. The label's "&"
        # is doubled so Qt shows it literally instead of eating it as a mnemonic;
        # the tr() key stays the plain text (and the fix covers translations
        # whose names also contain "&", e.g. de "Lichter & Schatten").
        self._gen_hs = QCheckBox(tr("Highlights & shadows").replace("&", "&&"),
                                 self._gen_panel)
        self._gen_hs.setToolTip(tr("Extra detail at the two ends where printers "
                                "struggle: pale tints just below paper white and "
                                "deep tones just above black, spread across every "
                                "hue. 'Per end' is the patches at each end (so the "
                                "total is twice that); 'depth' is how far in from "
                                "white and black the tones reach. The two ends are "
                                "built as mirror images, so they match. This set "
                                "works together with 'Near-neutral greys': when "
                                "that set is on, these patches stay just outside "
                                "its grey rings so no colour is printed twice; "
                                "when it is off, they also fill in the "
                                "near-neutral light and dark tones themselves."))
        self._gen_hs_n = _spin(1, 200, 24)
        self._gen_hs_reach = _spin(2, 45, 16)
        self._gen_hs_count = _count_label()
        gg.addWidget(self._gen_hs, 16, 0)
        gg.addWidget(QLabel(tr("per end:")), 16, 1)
        gg.addWidget(self._gen_hs_n, 16, 2)
        gg.addWidget(QLabel(tr("depth:")), 16, 3)
        gg.addWidget(self._gen_hs_reach, 16, 4)
        gg.addWidget(self._gen_hs_count, 16, 7)

        # Pastels — low-chroma midtones.
        self._gen_pastel = QCheckBox(tr("Pastels"), self._gen_panel)
        self._gen_pastel.setToolTip(tr("Soft, muted colours across every hue — "
                                    "dusty blues, sages, soft pinks and taupes. "
                                    "This is where most photos actually live, "
                                    "between the near-neutral greys and the vivid "
                                    "sets. Each of the 'layers' is a chroma shell "
                                    "of 'per layer' patches, so the two multiply."))
        self._gen_pastel_n = _spin(1, 200, 24)
        self._gen_pastel_layers = _spin(1, 4, 2)
        self._gen_pastel_count = _count_label()
        gg.addWidget(self._gen_pastel, 17, 0)
        gg.addWidget(QLabel(tr("per layer:")), 17, 1)
        gg.addWidget(self._gen_pastel_n, 17, 2)
        gg.addWidget(QLabel(tr("layers:")), 17, 3)
        gg.addWidget(self._gen_pastel_layers, 17, 4)
        gg.addWidget(self._gen_pastel_count, 17, 7)

        # From image — the most representative colours of a chosen photo.
        self._gen_image = QCheckBox(tr("From image"), self._gen_panel)
        self._gen_image.setToolTip(tr("Load a photo and ChromIQ picks out its most "
                                   "representative colours and adds them, so the "
                                   "profile is tuned to the kind of images you "
                                   "actually print. 'Colours' is how many to "
                                   "extract."))
        self._gen_image_px = None        # decoded (N,3) pixels, or None
        self._gen_image_name = ""
        self._gen_image_btn = QPushButton(tr("Load image…"), self._gen_panel)
        self._gen_image_btn.setObjectName("compact_input")
        self._gen_image_btn.clicked.connect(self._load_gen_image)
        self._gen_image_n = _spin(1, 500, 24)
        self._gen_image_count = _count_label()
        gg.addWidget(self._gen_image, 18, 0)
        gg.addWidget(self._gen_image_btn, 18, 1, 1, 2)
        gg.addWidget(QLabel(tr("colours:")), 18, 3)
        gg.addWidget(self._gen_image_n, 18, 4)
        gg.addWidget(self._gen_image_count, 18, 7)

        # Pure white & black — the two tonal anchors, N of each, kept verbatim.
        self._gen_whiteblack = QCheckBox(
            tr("Pure white & black").replace("&", "&&"), self._gen_panel)
        self._gen_whiteblack.setToolTip(tr("Adds pure paper white and the "
                                        "deepest black the printer can lay — two "
                                        "anchors that matter for a good profile. "
                                        "'Each' is how many of white and of black "
                                        "the finished chart should hold — and any "
                                        "white or black the other ticked sets "
                                        "already contribute counts toward that "
                                        "number. A 3D cube, Saturated edges or "
                                        "Gamut-corner emphasis includes one of "
                                        "each, and so does a Neutral grey ramp "
                                        "with 2 or more steps. So with one of "
                                        "those ticked, 'each: 1' adds 0 extra "
                                        "patches and 'each: 3' adds 4 (2 more "
                                        "whites and 2 more blacks) — deliberate, "
                                        "so the chart ends up with exactly the "
                                        "number you asked for, never more. The "
                                        "copies are kept identical even when "
                                        "'Ensure unique colours' is on, which is "
                                        "handy for averaging repeats."))
        self._gen_whiteblack_n = _spin(1, 50, 1)
        self._gen_whiteblack_count = _count_label()
        gg.addWidget(self._gen_whiteblack, 19, 0)
        gg.addWidget(QLabel(tr("each:")), 19, 1)
        gg.addWidget(self._gen_whiteblack_n, 19, 2)
        gg.addWidget(self._gen_whiteblack_count, 19, 7)

        # Fill remaining gaps — blue-noise top-up of whatever's left sparse.
        # Special: its count depends on the combined total of the sets above.
        self._gen_fill = QCheckBox(tr("Fill remaining gaps"), self._gen_panel)
        self._gen_fill.setToolTip(tr("After the sets above, scatter extra patches "
                                  "into the empty parts of colour space until the "
                                  "chart reaches the size you set, evenly and "
                                  "without repeating. 'Fill to' is the target "
                                  "total patch count."))
        # Fill target: to a patch count OR (with the engine) to a page count —
        # two mutually exclusive toggles, each with its OWN spinbox, because a
        # patch target is a much bigger number than a page target (#93, user).
        from PyQt6.QtWidgets import QButtonGroup, QRadioButton
        self._gen_fill_to = _spin(1, 30000, 1000)        # patches target
        # The fill box sits in a free row, not the grid column, so its wide range
        # (up to 30000) would make it stick out past the first-column spinboxes
        # above it. Cap it to the widest of those (the 1..500 image box) so it
        # lines up (Knut). The count still fits typical fill targets.
        self._gen_fill_to.setMaximumWidth(self._gen_image_n.sizeHint().width())
        self._gen_fill_pages = _spin(1, 99, 1)           # pages target
        self._gen_fill_unit_patches = QRadioButton(tr("patches:"), self._gen_panel)
        self._gen_fill_unit_pages = QRadioButton(tr("pages:"), self._gen_panel)
        self._gen_fill_unit_patches.setChecked(True)
        self._gen_fill_unit_grp = QButtonGroup(self._gen_panel)
        self._gen_fill_unit_grp.setExclusive(True)
        self._gen_fill_unit_grp.addButton(self._gen_fill_unit_patches)
        self._gen_fill_unit_grp.addButton(self._gen_fill_unit_pages)
        self._gen_fill_unit_grp.buttonToggled.connect(self._update_gen_counts)
        self._gen_fill_pages.valueChanged.connect(self._update_gen_counts)
        # "Fill to pages" is removed from the generator (Knut #93): pages are a
        # layout concern owned by the Create Chart tab, so the patch-set generator
        # only fills to a PATCH COUNT. The pages widgets stay constructed (hidden,
        # patches unit forced on) so the count plumbing keeps working.
        self._gen_fill_unit_pages.setVisible(False)
        self._gen_fill_pages.setVisible(False)
        # The patches/pages radio pair is gone (pages removed); the generator only
        # fills to a patch count. Keep the "patches" radio object (hidden, forced
        # on) so the count plumbing below still reads it as checked, but show just
        # the spinbox with a plain "patches" label to its right (Knut).
        self._gen_fill_unit_patches.setChecked(True)
        self._gen_fill_unit_patches.setVisible(False)
        _fill_row = QHBoxLayout(); _fill_row.setContentsMargins(0, 0, 0, 0)
        _fill_row.setSpacing(6)
        _fill_row.addWidget(self._gen_fill_to)
        _fill_row.addWidget(QLabel(tr("patches"), self._gen_panel))
        _fill_row.addStretch()
        _fill_w = QWidget(self._gen_panel); _fill_w.setLayout(_fill_row)
        self._gen_fill_count = _count_label()
        gg.addWidget(self._gen_fill, 20, 0)
        gg.addWidget(QLabel(tr("fill to:")), 20, 1)
        gg.addWidget(_fill_w, 20, 2, 1, 5)
        gg.addWidget(self._gen_fill_count, 20, 7)

        # A per-set ⓘ icon (col 8) opens the set's explanation in its own little
        # window — more discoverable than a hover tooltip. The body reuses each
        # checkbox's tooltip (already written + translated), the title is the set
        # name, so this adds no new strings. Titles use the plain name (the "&"
        # in "Highlights & shadows" is fine here — the icon has no mnemonic).
        row_tips = (
            (5, self._gen_cube,   tr("3D RGB cube")),
            (6, self._gen_edges,  tr("Saturated edges")),
            (7, self._gen_corners, tr("Gamut-corner emphasis")),
            (8, self._gen_skin,   tr("Skin tones (Fitzpatrick)")),
            (9, self._gen_blues,  tr("Oceans (blues)")),
            (10, self._gen_greens, tr("Foliage (greens)")),
            (11, self._gen_sunrises, tr("Sunrises (warm)")),
            (12, self._gen_flamingos, tr("Flamingos (pinks)")),
            (13, self._gen_neutral, tr("Neutral grey ramp")),
            (14, self._gen_nearneutral, tr("Near-neutral greys")),
            (15, self._gen_spirals, tr("Colour extremes")),
            (16, self._gen_hs,     tr("Highlights & shadows")),
            (17, self._gen_pastel, tr("Pastels")),
            (18, self._gen_image,  tr("From image")),
            (19, self._gen_whiteblack, tr("Pure white & black")),
            (20, self._gen_fill,  tr("Fill remaining gaps")),
        )
        for row, cb, title in row_tips:
            # Top-align the ⓘ so every set's icon lines up on the first row even
            # when a row is taller (the "From image" row has a Load-image button) —
            # AlignCenter put the From-image ⓘ lower than the rest (Knut #93).
            gg.addWidget(
                _magenta_tip(title, cb.toolTip(), self._gen_panel, min_width=360),
                row, 8, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        # The counts all live in one column (7), so they stay left-aligned in a
        # tidy column for every set. Greys' extra "offset:" control sits in cols
        # 5/6 *before* the count (those columns are empty — but reserved at full
        # width by the grid — for the other rows, so every count lines up). Per-set
        # ⓘ icons sit in col 8; a stretchy trailing column (9) soaks up spare width.
        gg.setColumnMinimumWidth(7, 124)
        gg.setColumnStretch(9, 1)

        # Cross-set de-duplication — keep combined patches unique (#37 follow-up).
        self._gen_unique = QCheckBox(tr("Ensure unique colours"), self._gen_panel)
        self._gen_unique.setChecked(True)
        self._gen_unique.setToolTip(tr("When sets are combined, nudge any "
                                    "repeated colours apart by a small offset "
                                    "so no patch is printed twice."))
        self._gen_unique.toggled.connect(self._update_gen_counts)
        gg.addWidget(self._gen_unique, 21, 0, 1, 8)

        self._gen_total = QLabel("", self._gen_panel)
        self._gen_total.setStyleSheet("font-weight: bold;")
        gg.addWidget(self._gen_total, 22, 0, 1, 8)

        # In the Add dialog (a chart already has patches), also show the chart's
        # resulting size — existing patches + the additions — since this is the
        # Add flow, not a fresh layout (#60, Knut). Hidden when there are no
        # existing patches (the New-chart dialog), where it would just repeat.
        self._gen_after_total = QLabel("", self._gen_panel)
        self._gen_after_total.setStyleSheet("color: #909090;")
        self._gen_after_total.setVisible(bool(self._existing_patches))
        gg.addWidget(self._gen_after_total, 21, 0, 1, 8)

        for cb in (self._gen_cube, self._gen_corners, self._gen_spirals,
                   self._gen_skin, self._gen_blues, self._gen_greens,
                   self._gen_sunrises, self._gen_flamingos, self._gen_neutral,
                   self._gen_nearneutral, self._gen_edges, self._gen_hs,
                   self._gen_pastel, self._gen_image, self._gen_whiteblack,
                   self._gen_fill):
            cb.toggled.connect(self._update_gen_counts)

        # Saturated edges no longer needs to track the cube via a coupled value:
        # its 'between' control places patches *between* the cube's own steps, so
        # it reads the cube's steps-per-axis directly at build time and stays even
        # at any setting (Knut, #78). The old edges↔cube auto-sync is gone (the
        # cube spin already refreshes the counts, which now drive the edges total).
        # --- Multi-ink rows (#72 Tier C) — shown only in states 2/3 ---------
        # Grid rows 0–2 of the SAME grid as the RGB sets (which start at row
        # 3), so counts and ⓘ icons share one column geometry; every widget
        # here starts hidden and _apply_gen_state_gating reveals them for
        # multi-ink devices. State-1 stays pixel-identical (hidden grid rows
        # collapse to zero height).
        self._nch_gen_widgets: list = []   # every widget of the 3 rows

        def _nch_add(w, row: int, col: int):
            gg.addWidget(w, row, col)
            self._nch_gen_widgets.append(w)

        self._nch_targen = QCheckBox(tr("Even coverage (targen)"),
                                     self._gen_panel)
        self._nch_targen.setChecked(True)
        self._nch_targen.setToolTip(
            tr("Spreads patches evenly across every ink combination your "
               "printer can mix — the backbone of a good multi-ink profile, "
               "and the multi-ink replacement for the RGB cube sets.\n\n"
               "Argyll's targen places each patch so the whole ink space is "
               "covered without wasteful clumps, always staying inside the "
               "ink limit above. \"Patches\" is simply how many you want — "
               "more patches, finer coverage, longer measuring.\n\n"
               "With a preconditioning profile set, the spread follows your "
               "printer's real response instead of the theoretical ink "
               "space, so patches land where the printer actually needs "
               "them. For a first-ever chart (no profile yet), this set plus "
               "the ramps below is exactly the right starting point."))
        self._nch_targen.toggled.connect(self._update_gen_counts)
        self._nch_targen_n = _spin(8, 4000, 800)
        self._nch_targen_count = _count_label()
        _nch_add(self._nch_targen, 0, 0)
        _nch_add(QLabel(tr("patches:")), 0, 1)
        _nch_add(self._nch_targen_n, 0, 2)
        _nch_add(self._nch_targen_count, 0, 7)
        self._nch_perink = QCheckBox(tr("Per-ink ramps"), self._gen_panel)
        self._nch_perink.setChecked(True)
        self._nch_perink.setToolTip(
            tr("A tone ramp of every ink on its own — from a light tint up "
               "to 100 % coverage, in the number of steps you choose here.\n\n"
               "This shows the profile how each ink behaves by itself: how "
               "fast it darkens, where it saturates, what its pure colour "
               "looks like on your paper. Without these single-ink patches "
               "the profile only ever sees inks mixed together and has to "
               "guess each one's own character.\n\n"
               "\"Steps/ink\" is the number of tones per ink — 8 is a solid "
               "default; use more for inks with strong tonal behaviour "
               "(e.g. black on matte papers)."))
        self._nch_perink.toggled.connect(self._update_gen_counts)
        self._nch_perink_n = _spin(2, 64, 8)
        self._nch_perink_count = _count_label()
        _nch_add(self._nch_perink, 1, 0)
        _nch_add(QLabel(tr("steps/ink:")), 1, 1)
        _nch_add(self._nch_perink_n, 1, 2)
        _nch_add(self._nch_perink_count, 1, 7)
        self._nch_pairs = QCheckBox(tr("Ink-pair overprints"), self._gen_panel)
        self._nch_pairs.setChecked(True)
        self._nch_pairs.setToolTip(
            tr("Two inks printed on top of each other, stepped up together, "
               "for every possible pair of your inks.\n\n"
               "Mixing on paper is where printers surprise you: cyan over "
               "yellow doesn't just add up — the inks bleed, trap and darken "
               "differently on every paper. These patches show the profile "
               "exactly how each pair really combines, which sharpens all "
               "the mixed colours in between.\n\n"
               "Safe by design: each ink in a pair stays at or below half "
               "the ink limit, so no overprint patch can ever exceed it. "
               "\"Steps/pair\" is the number of tones per pair — with many "
               "inks the pair count grows quickly, so a small number of "
               "steps is usually plenty."))
        self._nch_pairs.toggled.connect(self._update_gen_counts)
        self._nch_pairs_n = _spin(1, 32, 4)
        self._nch_pairs_count = _count_label()
        _nch_add(self._nch_pairs, 2, 0)
        _nch_add(QLabel(tr("steps/pair:")), 2, 1)
        _nch_add(self._nch_pairs_n, 2, 2)
        _nch_add(self._nch_pairs_count, 2, 7)
        self._nch_triples = QCheckBox(tr("Ink-triple overprints"),
                                      self._gen_panel)
        self._nch_triples.setChecked(False)
        self._nch_triples.setToolTip(
            tr("Three inks printed on top of each other, stepped up "
               "together, for every possible trio of your inks.\n\n"
               "This is where the dark, rich mixtures live — the deep "
               "composite colours that two-ink pairs never reach and even "
               "coverage only samples by chance. Profiles get their deep "
               "shadows and dark saturated colours from exactly this "
               "region, so a few systematic steps here noticeably steady "
               "the dark end.\n\n"
               "Safe by design: each ink in a trio stays at or below a "
               "third of the ink limit, so no patch can ever exceed it. "
               "\"Steps/trio\" is the number of tones per trio — the trio "
               "count grows quickly with many inks (4 inks → 4 trios, "
               "6 inks → 20), so one or two steps is usually plenty."))
        self._nch_triples.toggled.connect(self._update_gen_counts)
        self._nch_triples_n = _spin(1, 16, 2)
        self._nch_triples_count = _count_label()
        _nch_add(self._nch_triples, 3, 0)
        _nch_add(QLabel(tr("steps/trio:")), 3, 1)
        _nch_add(self._nch_triples_n, 3, 2)
        _nch_add(self._nch_triples_count, 3, 7)
        self._nch_richblack = QCheckBox(tr("Rich-black ramp"),
                                        self._gen_panel)
        self._nch_richblack.setChecked(False)
        self._nch_richblack.setToolTip(
            tr("Dark neutral greys built from colour ink PLUS increasing "
               "amounts of black — the \"rich black\" region.\n\n"
               "A printer can make the same dark grey in many ways: mostly "
               "from cyan, magenta and yellow, mostly from black ink, or "
               "anything in between. Which mix the profile chooses is its "
               "black generation — and this set gives the profile real "
               "measurements of those mixes instead of leaving it to "
               "interpolate. If you use the Black generation option when "
               "building profiles, these are precisely the patches that "
               "teach it.\n\n"
               "\"Steps\" is the number of grey tones per black level, "
               "\"K levels\" how many amounts of black are tried. Inside "
               "the ink limit by construction. Needs a black ink — on the "
               "rare ink set without one, the set simply adds nothing."))
        self._nch_richblack.toggled.connect(self._update_gen_counts)
        self._nch_richblack_n = _spin(2, 32, 6)
        self._nch_richblack_k = _spin(1, 8, 3)
        self._nch_richblack_count = _count_label()
        _nch_add(self._nch_richblack, 4, 0)
        _nch_add(QLabel(tr("steps:")), 4, 1)
        _nch_add(self._nch_richblack_n, 4, 2)
        _nch_add(QLabel(tr("K levels:")), 4, 3)
        _nch_add(self._nch_richblack_k, 4, 4)
        _nch_add(self._nch_richblack_count, 4, 7)
        # ⓘ per row in col 8, counts in col 7 — shared grid, aligned for free.
        for row, cb, title in (
                (0, self._nch_targen, tr("Even coverage (targen)")),
                (1, self._nch_perink, tr("Per-ink ramps")),
                (2, self._nch_pairs, tr("Ink-pair overprints")),
                (3, self._nch_triples, tr("Ink-triple overprints")),
                (4, self._nch_richblack, tr("Rich-black ramp"))):
            tip = _magenta_tip(title, cb.toolTip(), self._gen_panel,
                               min_width=360)
            gg.addWidget(tip, row, 8,
                         Qt.AlignmentFlag.AlignTop
                         | Qt.AlignmentFlag.AlignHCenter)
            self._nch_gen_widgets.append(tip)
        for w in self._nch_gen_widgets:
            w.setVisible(False)
        # Original RGB tooltips, restored when the device returns to state 1
        # (the gating swaps in the greyed-explanation texts, #72).
        self._gen_orig_tooltips: dict = {}

        indent.addWidget(self._gen_panel)
        return indent

    def _edges_cube_n(self) -> int:
        """Steps-per-axis the saturated-edges 'between' fill is keyed to: the 3D
        cube's value when that set is on, else 2 (fill between the corners only),
        so edges/faces stay even and locked to the cube it sits with (Knut, #78)."""
        return self._gen_cube_n.value() if self._gen_cube.isChecked() else 2

    def _edges_need_corners(self) -> bool:
        """Saturated edges should include the 8 corner tips when the 3D cube
        isn't on to supply them — restoring the old behaviour Nelson relied on
        (the between-only fill drops the tips otherwise) (#78)."""
        return not self._gen_cube.isChecked()

    def _corner_tips_present(self) -> bool:
        """Whether the 3D cube or Saturated edges already supplies the 8 tips."""
        return self._gen_cube.isChecked() or self._gen_edges.isChecked()

    def _corners_need_tips(self) -> bool:
        """The corner-EDGES set owns the exact tips when nothing above it (cube /
        edges) does, so a tip is never missing yet never duplicated (Knut Q1)."""
        return (self._gen_corners.isChecked() and not self._corner_tips_present())

    def _spirals_need_tips(self) -> bool:
        """The spiral set owns the tips only when neither the cube, the edges nor
        the corner-edges set does — the bottom of the priority chain."""
        return (self._gen_spirals.isChecked() and not self._corner_tips_present()
                and not self._gen_corners.isChecked())

    # The generators in fixed concatenation order: (checkbox, builder, counter).
    def _gen_specs(self):
        return (
            (self._gen_cube,
             lambda: G.rgb_cube(self._gen_cube_n.value()),
             lambda: G.rgb_cube_count(self._gen_cube_n.value()),
             self._gen_cube_count),
            # Saturated edges sits right after the cube — matching its panel row
            # (#78) — so the de-dup, which walks this list top-to-bottom keeping
            # earlier patches and nudging later ones clear, processes the sets in
            # the order the user sees them.
            (self._gen_edges,
             lambda: (G.gamut_edges_between(self._edges_cube_n(),
                                            self._gen_edges_n.value(),
                                            self._edges_need_corners())
                      + G.gamut_faces_between(self._edges_cube_n(),
                                              self._gen_edges_faces.value())),
             lambda: (G.gamut_edges_between_count(self._edges_cube_n(),
                                                  self._gen_edges_n.value(),
                                                  self._edges_need_corners())
                      + G.gamut_faces_between_count(self._edges_cube_n(),
                                                    self._gen_edges_faces.value())),
             self._gen_edges_count),
            # Gamut-corner emphasis (edge patches) sits third — matching its panel
            # row — so the de-dup spaces it against the cube/edges boundary above.
            # Corner edges are slotted into the gaps on the edge lines, so they need
            # the patches placed so far (cube + edges) — _build_generated_program
            # special-cases that; this builder is the no-existing fallback. (Colour
            # extremes now sits lower, just above Highlights & shadows.)
            (self._gen_corners,
             lambda: G.gamut_corner_edges(self._gen_corners_edge.value(),
                                          None, self._corners_need_tips()),
             lambda: G.gamut_corner_edges_count(self._gen_corners_edge.value(),
                                                self._corners_need_tips()),
             self._gen_corners_count),
            (self._gen_skin,
             lambda: G.skin_tones(self._gen_skin_n.value(),
                                  self._gen_skin_ranges.value()),
             lambda: G.skin_tones_count(self._gen_skin_n.value(),
                                        self._gen_skin_ranges.value()),
             self._gen_skin_count),
            (self._gen_blues,
             lambda: G.blues(self._gen_blues_n.value()
                             * self._gen_blues_layers.value(),
                             self._gen_blues_layers.value()),
             lambda: G.blues_count(self._gen_blues_n.value()
                                   * self._gen_blues_layers.value()),
             self._gen_blues_count),
            (self._gen_greens,
             lambda: G.greens(self._gen_greens_n.value()
                              * self._gen_greens_layers.value(),
                              self._gen_greens_layers.value()),
             lambda: G.greens_count(self._gen_greens_n.value()
                                    * self._gen_greens_layers.value()),
             self._gen_greens_count),
            (self._gen_sunrises,
             lambda: G.sunrises(self._gen_sunrises_n.value()
                                * self._gen_sunrises_layers.value(),
                                self._gen_sunrises_layers.value()),
             lambda: G.sunrises_count(self._gen_sunrises_n.value()
                                      * self._gen_sunrises_layers.value()),
             self._gen_sunrises_count),
            (self._gen_flamingos,
             lambda: G.flamingos(self._gen_flamingos_n.value()
                                 * self._gen_flamingos_layers.value(),
                                 self._gen_flamingos_layers.value()),
             lambda: G.flamingos_count(self._gen_flamingos_n.value()
                                       * self._gen_flamingos_layers.value()),
             self._gen_flamingos_count),
            # Neutral grey ramp (pure greys) then Near-neutral greys (the rings),
            # adjacent and independent. Together they reproduce the old combined
            # near-neutral set; split so their densities are chosen separately.
            (self._gen_neutral,
             lambda: G.neutral_ramp(self._gen_neutral_n.value()),
             lambda: G.neutral_ramp_count(self._gen_neutral_n.value()),
             self._gen_neutral_count),
            (self._gen_nearneutral,
             lambda: G.near_neutrals(self._gen_nearneutral_n.value(),
                                     float(self._gen_nearneutral_off.value()),
                                     self._gen_nearneutral_rings.value()),
             lambda: G.near_neutrals_count(self._gen_nearneutral_n.value(),
                                           self._gen_nearneutral_rings.value()),
             self._gen_nearneutral_count),
            # Colour extremes sits just above Highlights & shadows (its panel row):
            # the chromatic-corner counterpart to H&S's tonal ends. By now the cube,
            # edges and Gamut-corner emphasis are already placed, so the tip-owner
            # chain (checkbox-based) is unaffected and the de-dup spaces these spiral
            # patches against everything above — one generator at a time, top-down.
            (self._gen_spirals,
             lambda: G.gamut_corners(self._gen_spirals_end.value(),
                                     float(self._gen_spirals_reach.value()),
                                     self._spirals_need_tips()),
             lambda: G.gamut_corners_count(self._gen_spirals_end.value(),
                                           self._spirals_need_tips()),
             self._gen_spirals_count),
            (self._gen_hs,
             # Highlights & shadows interlocks with Near-neutral greys (the rings):
             # when that set is on, H&S stays just outside its rings (no colour
             # printed twice); when off, H&S also fills the near-neutral light/dark
             # tones. It keys off the near-neutral rings, not the pure ramp.
             lambda: G.highlight_shadow_detail(
                 self._gen_hs_n.value(),
                 float(self._gen_hs_reach.value()),
                 greys_enabled=self._gen_nearneutral.isChecked(),
                 greys_steps=self._gen_nearneutral_n.value(),
                 greys_offset=float(self._gen_nearneutral_off.value()),
                 greys_rings=self._gen_nearneutral_rings.value()),
             lambda: G.highlight_shadow_detail_count(self._gen_hs_n.value()),
             self._gen_hs_count),
            (self._gen_pastel,
             lambda: G.pastels(self._gen_pastel_n.value()
                               * self._gen_pastel_layers.value(),
                               self._gen_pastel_layers.value()),
             lambda: G.pastels_count(self._gen_pastel_n.value()
                                     * self._gen_pastel_layers.value()),
             self._gen_pastel_count),
            (self._gen_image,
             lambda: (G.image_palette(self._gen_image_px, self._gen_image_n.value())
                      if self._gen_image_px is not None else []),
             lambda: G.image_palette_count(self._gen_image_n.value(),
                                           self._gen_image_px is not None),
             self._gen_image_count),
        )
        # NB: "Pure white & black" is deliberately *not* a _gen_specs entry — it
        # tops up to N of each *after* de-duplication (so its repeats survive) and
        # counts whatever the other sets already contributed. Built/counted in
        # _build_generated_program / _update_gen_counts instead.

    def _install_magenta_accents(self) -> None:
        """Scope the editor's magenta accent onto this dialog's checked /
        focused controls (shared by the New-chart dialog and the Add dialog)
        so they don't fall back to the app-wide cyan."""
        self.setStyleSheet(f"""
            QCheckBox::indicator:checked {{
                background: {SPEC_MAGENTA}; border-color: {SPEC_MAGENTA};
            }}
            QCheckBox::indicator:hover {{ border-color: {SPEC_MAGENTA}; }}
            /* This dialog sets its own stylesheet, which drops the app-wide
               round radio geometry — so re-declare the base indicator round
               (border-radius = half ⇒ circle), else a checked radio draws as a
               magenta square. Checkboxes keep their square tick. Explicit
               per-theme colours, not palette(mid): see _unchecked_indicator_css. */
            QRadioButton::indicator {{
                width: 14px; height: 14px;
                {_unchecked_indicator_css(self._settings)}
                border-radius: 8px;
            }}
            QRadioButton::indicator:checked {{
                background: {SPEC_MAGENTA}; border-color: {SPEC_MAGENTA};
            }}
            /* A ticked-but-disabled box must read as off — without this the
               magenta :checked fill wins over Qt's disabled greying, so an
               unselected panel (e.g. "Generate colour sets") still showed bright
               ticks. The two-state selector outranks the single :checked rule. */
            QCheckBox::indicator:checked:disabled {{
                background: #4a4a4a; border-color: #4a4a4a;
            }}
            QRadioButton::indicator:checked:disabled {{
                background: #4a4a4a; border-color: #4a4a4a; border-radius: 8px;
            }}
            QLineEdit:focus, QComboBox:focus,
            QSpinBox:focus, QDoubleSpinBox:focus {{
                border-color: {SPEC_MAGENTA};
            }}
        """ + combo_popup_qss(SPEC_MAGENTA))
        # The dropdown's hovered row defaulted to the app-wide cyan. It needs
        # BOTH of combo_popup_qss's rules: a `selection-background-color` alone
        # (all this used to set) leaves the native menu-drawn popup rendering
        # exactly as before while the view's palette reports the new colour —
        # measured on screen, in both themes.

    def _gen_sets_active(self) -> bool:
        """Whether the generate-colour-sets panel is the active source.

        In the New-chart dialog that's the "Generate colour sets" radio;
        subclasses that reuse the panel under a different control (e.g. the
        editor's Add dialog) override this."""
        return self._mode_generate.isChecked()

    def _engine_cap_per_page(self) -> int:
        """Patches the engine fits on one sheet for this dialog's layout, or 0
        when the engine is off / not resolvable. Bases the layout on the main
        editor's recipe (``_initial_recipe`` — the user's "settings from the main
        editor") and applies this dialog's instrument/paper/mode when present.
        Shared by the capacity hint and the 'fill to N pages' target (#93)."""
        if not (self._settings is not None
                and bool(self._settings.get("use_chromiq_layout_engine", False))):
            return 0
        try:
            from workflow.layout_engine import geometry, instruments, papers
            from workflow.layout_engine.presets import default_recipe, LayoutRecipe
            rec = (LayoutRecipe.from_dict(self._initial_recipe)
                   if isinstance(self._initial_recipe, dict) else None)
            instr_w = getattr(self, "_instr", None)
            paper_w = getattr(self, "_paper", None)
            if instr_w is not None and paper_w is not None:
                eng = {"i1": "i1", "3p": "p3", "CM": "CM"}.get(instr_w.currentData())
                paper = paper_w.currentData()
            elif rec is not None:
                eng, paper = rec.instrument, rec.paper
            else:
                return 0
            if eng is None or paper in (None, "custom"):
                return 0
            if rec is None:
                rec = default_recipe(eng, paper)
            rec.instrument, rec.paper = eng, paper
            if eng == "CM" and getattr(self, "_eng_density", None) is not None:
                rec.cm_density = int(self._eng_density.currentData() or 1)
            elif eng in ("i1", "p3") and getattr(self, "_eng_clip", None) is not None:
                rec.clip_border = self._eng_clip.isChecked()
                rec.nolimit = self._eng_nocap.isChecked()
            geom = instruments.geom_from_build_kwargs(rec.build_kwargs())
            w_mm, h_mm = papers.dimensions_mm(paper)
            return geometry.patches_per_sheet(geom, w_mm, h_mm)
        except Exception:
            return 0

    def _effective_fill_target(self) -> int:
        """The fill target as a patch count: the patches spin in 'patches' mode,
        or the pages spin × engine capacity-per-page in 'pages' mode (#93)."""
        if self._gen_fill_unit_pages.isChecked():
            per = self._engine_cap_per_page()
            if per > 0:
                return int(self._gen_fill_pages.value()) * per
        return int(self._gen_fill_to.value())

    def _sync_fill_unit(self) -> None:
        """'pages' fill only makes sense with the engine — disable the 'pages'
        toggle (falling back to 'patches') when the engine can't size a page;
        grey the spinbox of whichever unit isn't active."""
        can_pages = self._engine_cap_per_page() > 0
        self._gen_fill_unit_pages.setEnabled(can_pages)
        if not can_pages and self._gen_fill_unit_pages.isChecked():
            self._gen_fill_unit_patches.setChecked(True)
        pages_on = self._gen_fill_unit_pages.isChecked()
        fill_on = self._gen_fill.isChecked()
        self._gen_fill_pages.setEnabled(can_pages and pages_on and fill_on)
        # Also gate on the "Fill remaining gaps" checkbox — this runs after the
        # per-row enable pass in _update_gen_counts, so without the check it would
        # re-enable the spinbox even when the row is off (Knut).
        self._gen_fill_to.setEnabled(not pages_on and fill_on)

    def _update_gen_counts(self, *_a) -> None:
        """Refresh each generator's patch count + the running total, and gate
        the per-row spin boxes on their checkbox."""
        on = self._gen_sets_active()
        self._gen_panel.setEnabled(on)
        state = self._nch_state()
        if getattr(self, "_nch_targen", None) is not None:
            for cb, spin, lbl, count in (
                (self._nch_targen, self._nch_targen_n, self._nch_targen_count,
                 lambda: self._nch_targen_n.value()),
                (self._nch_perink, self._nch_perink_n, self._nch_perink_count,
                 lambda: NDG.per_ink_ramps_count(
                     len(self._nch_ink_codes()), self._nch_perink_n.value())),
                (self._nch_pairs, self._nch_pairs_n, self._nch_pairs_count,
                 lambda: NDG.ink_pair_overprints_count(
                     len(self._nch_ink_codes()), self._nch_pairs_n.value())),
                (self._nch_triples, self._nch_triples_n,
                 self._nch_triples_count,
                 lambda: NDG.ink_triple_overprints_count(
                     len(self._nch_ink_codes()),
                     self._nch_triples_n.value())),
                (self._nch_richblack, self._nch_richblack_n,
                 self._nch_richblack_count,
                 lambda: NDG.rich_black_ramp_count(
                     self._nch_richblack_n.value(),
                     self._nch_richblack_k.value(),
                     len(self._nch_ink_codes()),
                     3 if "k" in self._nch_ink_codes() else None)),
            ):
                spin.setEnabled(cb.isChecked())
                # Even coverage runs Argyll targen live at build time, so its
                # number is the request, not a guaranteed outcome — the "≈"
                # keeps the label honest (every other count is exact).
                approx = "≈ " if cb is self._nch_targen else ""
                lbl.setText((approx + _patches_label(count()))
                            if state != 1 else "")
                _hint_count_inactive(lbl, cb.isChecked())
            self._nch_richblack_k.setEnabled(self._nch_richblack.isChecked())
        # Grey each row's size control(s) when its set is unticked.
        for cb, spins in (
            (self._gen_cube, (self._gen_cube_n,)),
            (self._gen_corners, (self._gen_corners_edge,)),
            (self._gen_spirals, (self._gen_spirals_end, self._gen_spirals_reach)),
            (self._gen_skin, (self._gen_skin_n, self._gen_skin_ranges)),
            (self._gen_blues, (self._gen_blues_n, self._gen_blues_layers)),
            (self._gen_greens, (self._gen_greens_n, self._gen_greens_layers)),
            (self._gen_sunrises, (self._gen_sunrises_n,
                                  self._gen_sunrises_layers)),
            (self._gen_flamingos, (self._gen_flamingos_n,
                                   self._gen_flamingos_layers)),
            (self._gen_neutral, (self._gen_neutral_n,)),
            (self._gen_nearneutral, (self._gen_nearneutral_n,
                                     self._gen_nearneutral_off,
                                     self._gen_nearneutral_rings)),
            (self._gen_edges, (self._gen_edges_n, self._gen_edges_faces)),
            (self._gen_hs, (self._gen_hs_n, self._gen_hs_reach)),
            (self._gen_pastel, (self._gen_pastel_n, self._gen_pastel_layers)),
            (self._gen_image, (self._gen_image_btn, self._gen_image_n)),
            (self._gen_whiteblack, (self._gen_whiteblack_n,)),
            (self._gen_fill, (self._gen_fill_to,)),
        ):
            for s in spins:
                # Checked AND enabled: a ticked RGB-cube row on a CMYK
                # device is greyed by the state gating but stays ticked
                # (so returning to RGB restores it) — its size controls
                # must grey out with it, not sit there looking active
                # (Basti's live screenshot).
                s.setEnabled(cb.isChecked() and cb.isEnabled())
        # Near-neutral greys always has at least one ring, so its offset is always
        # meaningful — grey the offset label alongside the spin (set on/off only).
        self._gen_nearneutral_off_label.setEnabled(self._gen_nearneutral.isChecked())
        total = 0
        for cb, _build, count, label in self._gen_specs():
            n = count()
            label.setText(_patches_label(n))
            # Disabled rows never contribute (#72 states 2/3: a ticked but
            # greyed RGB-cube/look-based row must not count or build); the
            # strike-through marks any non-contributing row's count (Basti).
            active = cb.isChecked() and cb.isEnabled()
            _hint_count_inactive(label, active)
            if active:
                total += n
        if state != 1:
            for cb, count in (
                (self._nch_targen, lambda: self._nch_targen_n.value()),
                (self._nch_perink, lambda: NDG.per_ink_ramps_count(
                    len(self._nch_ink_codes()), self._nch_perink_n.value())),
                (self._nch_pairs, lambda: NDG.ink_pair_overprints_count(
                    len(self._nch_ink_codes()), self._nch_pairs_n.value())),
                (self._nch_triples, lambda: NDG.ink_triple_overprints_count(
                    len(self._nch_ink_codes()),
                    self._nch_triples_n.value())),
                (self._nch_richblack, lambda: NDG.rich_black_ramp_count(
                    self._nch_richblack_n.value(),
                    self._nch_richblack_k.value(),
                    len(self._nch_ink_codes()),
                    3 if "k" in self._nch_ink_codes() else None)),
            ):
                if cb.isChecked():
                    total += count()
        # "From image" shows a hint until a photo is loaded.
        if self._gen_image.isChecked() and self._gen_image_px is None:
            self._gen_image_count.setText(tr("load an image"))
        # Pure white & black is part of the chart *before* fill, so it's counted
        # before the fill top-up. These are deliberate anchor patches (e.g. extra
        # paper-white / max-black readings to average), so they're added on top
        # of whatever the chart already holds — only the corners the *other
        # ticked sets* contribute in this same batch count toward N, never the
        # existing chart's own white/black (#76, Knut). The white/black tips come
        # from the boundary tip-owner chain (3D cube → Saturated edges → Gamut-
        # corner emphasis — whichever is on supplies them, incl. white/black), and
        # from the Neutral grey ramp with ≥2 steps (its endpoints are pure black
        # and white). Near-neutral greys is only off-axis tints, never pure
        # white/black; Colour extremes never lands on white/black either (six
        # chromatic corners only), so neither counts here (Knut, #78).
        corner = ((1 if ((self._gen_cube.isChecked() and self._gen_cube.isEnabled())
                         or (self._gen_edges.isChecked() and self._gen_edges.isEnabled())
                         or (self._gen_corners.isChecked()
                             and self._gen_corners.isEnabled())) else 0)
                  + (1 if (self._gen_neutral.isChecked()
                           and self._gen_neutral_n.value() >= 2) else 0))
        sets_have = (1 if corner else 0) if self._gen_unique.isChecked() else corner
        wb_n = G.white_black_count(self._gen_whiteblack_n.value(),
                                   sets_have, sets_have)
        self._gen_whiteblack_count.setText(_patches_label(wb_n))
        _hint_count_inactive(self._gen_whiteblack_count,
                             self._gen_whiteblack.isChecked())
        if self._gen_whiteblack.isChecked():
            total += wb_n
        # Fill remaining gaps tops the whole chart (existing + sets + white/black)
        # up to its target, so it's counted last.
        self._sync_fill_unit()
        fill_n = G.fill_gaps_count(total + len(self._existing_patches),
                                   self._effective_fill_target())
        self._gen_fill_count.setText(_patches_label(fill_n))
        _hint_count_inactive(self._gen_fill_count, self._gen_fill.isChecked())
        if self._gen_fill.isChecked():
            total += fill_n
        # Total = the patches the current set selection produces (the additions:
        # the ticked sets + white/black + fill) — NOT the existing chart, and
        # shown even when the master Generate toggle is off, exactly like the
        # per-set counts beside each option (#60, Knut's clarification). This
        # estimate shows instantly; _do_push_live_preview refreshes it from the
        # real built program ~300 ms later (which catches any cross-set de-dup
        # the per-set estimate can't see).
        self._gen_total.setText(tr("Total: {label}").format(
            label=_patches_label(total)))
        if self._existing_patches:
            self._gen_after_total.setText(tr("Chart after adding: {label}").format(
                label=_patches_label(len(self._existing_patches) + total)))
        # Keep the embedded live cube in step with the colour-set controls.
        self._push_live_preview()

    def _build_generated_program_nch(self, state: int) -> list[tuple]:
        """Build the device-value program for a multi-ink chart (#72 Tier C).

        Panel order: targen coverage → per-ink ramps → ink-pair overprints →
        neutral ramp → near-neutral grey-balance rings → (state 3) the
        look-based sets through the perceptual bridge — then min-distance
        spacing, white/black anchors and the gap fill, mirroring the RGB
        build. The honest out-of-gamut displacement note lands in
        ``self.nch_moved_note`` for the caller to surface.
        """
        codes = self._nch_ink_codes()
        n = len(codes)
        k_ix = codes.index("k") if "k" in codes else None
        limit = float(self._ink_limit.value())
        program: list[tuple] = []
        self.nch_moved_note = ""
        if self._nch_targen.isChecked():
            extra_args = [f"-D{self._INK_DFLAG[c]}" for c in codes[4:]]
            extra_args.append(f"-l{int(limit)}")
            if state == 3:
                extra_args += ["-c", self._precond_path]
            program.extend(R.seed_from_targen(
                self._bin_dir, self._nch_targen_n.value(), device="4",
                extra_args=extra_args))
        if self._nch_perink.isChecked():
            program.extend(NDG.per_ink_ramps(n, self._nch_perink_n.value(),
                                             ink_limit=limit))
        if self._nch_pairs.isChecked():
            program.extend(NDG.ink_pair_overprints(
                n, self._nch_pairs_n.value(), ink_limit=limit))
        if self._nch_triples.isChecked():
            program.extend(NDG.ink_triple_overprints(
                n, self._nch_triples_n.value(), ink_limit=limit))
        if self._nch_richblack.isChecked():
            program.extend(NDG.rich_black_ramp(
                self._nch_richblack_n.value(),
                self._nch_richblack_k.value(), n, k_index=k_ix,
                ink_limit=limit))
        # Look-based sets BEFORE the grey sets — matching the panel's row
        # order, which is the de-dup priority contract everywhere else
        # (the cross-set nudge keeps earlier sets and moves later ones).
        if state == 3:
            from workflow.xicclu_runner import to_device_via_profile
            moved_total = requested = 0
            for name in self._GEN_PERCEPTUAL:
                cb = getattr(self, f"_gen_{name}")
                if not (cb.isChecked() and cb.isEnabled()):
                    continue
                build = next(b for c, b, _cnt, _lbl in self._gen_specs()
                             if c is cb)
                rgb = build()
                if not rgb:
                    continue
                dev, moved = to_device_via_profile(
                    rgb, self._precond_path, self._bin_dir, ink_limit=limit)
                program.extend(dev)
                moved_total += moved
                requested += len(rgb)
            if moved_total:
                self.nch_moved_note = tr(
                    "{moved} of {req} look-based colours lie outside this "
                    "printer's gamut and were moved to the nearest printable "
                    "colour.").format(moved=moved_total, req=requested)
        if self._gen_neutral.isChecked():
            program.extend(NDG.neutral_ramp_device(
                self._gen_neutral_n.value(), n, ink_limit=limit))
        if self._gen_nearneutral.isChecked():
            steps = self._gen_nearneutral_n.value()
            off = float(self._gen_nearneutral_off.value())
            rings = self._gen_nearneutral_rings.value()
            centers: dict = {}
            if state == 3:
                # Re-centre the grey-balance rings on the printer's ACTUAL
                # neutral (what the row's tooltip promises): one xicclu run
                # maps the distinct grey levels through the preconditioning
                # profile; the ring offsets stay in device space, so the
                # bracket geometry is untouched. Any failure just keeps the
                # equal-CMY centring — never a build error.
                try:
                    from workflow.xicclu_runner import to_device_via_profile
                    greys = NDG.ring_grey_levels(steps, off, rings)
                    dev_c, _moved = to_device_via_profile(
                        [(g, g, g) for g in greys], self._precond_path,
                        self._bin_dir, ink_limit=limit)
                    centers = {g: d for g, d in zip(greys, dev_c)}
                except Exception:      # noqa: BLE001 — graceful fallback
                    centers = {}
            if centers:
                program.extend(NDG.near_neutrals_device_recentred(
                    steps, off, rings, n, centers, ink_limit=limit))
            else:
                program.extend(NDG.near_neutrals_device(
                    steps, off, rings, n, ink_limit=limit))
        if self._gen_unique.isChecked():
            program = NDG.enforce_min_distance_nd(
                program, _GEN_MIN_DIST, existing=self._existing_patches)
        if self._gen_whiteblack.isChecked():
            have_w, have_b = NDG.count_white_black_device(
                program, n, k_index=k_ix, ink_limit=limit)
            program.extend(NDG.white_black_device(
                self._gen_whiteblack_n.value(), n, k_index=k_ix,
                have_white=have_w, have_black=have_b, ink_limit=limit))
        if self._gen_fill.isChecked():
            seed = list(self._existing_patches) + program
            program.extend(NDG.fill_gaps_nd(
                seed, self._effective_fill_target(), n_channels=n,
                ink_limit=limit))
        return program

    def _build_generated_program(self) -> list[tuple]:
        """Concatenate every ticked generator's patches, in panel order,
        de-duplicating across sets when 'Ensure unique colours' is on."""
        state = self._nch_state()
        if state != 1:
            return self._build_generated_program_nch(state)
        program: list[tuple] = []
        for cb, build, _count, _label in self._gen_specs():
            if not cb.isChecked():
                continue
            if cb is self._gen_corners:
                # Corner-edge patches slot into the gaps the cube / Saturated edges
                # left on the edge lines, so they need the patches placed so far
                # (the existing chart + everything above this set) to interleave
                # cleanly without landing on them (Nelson via Knut, #78).
                program.extend(G.gamut_corner_edges(
                    self._gen_corners_edge.value(),
                    self._existing_patches + program,
                    self._corners_need_tips()))
            else:
                program.extend(build())
        if self._gen_unique.isChecked():
            # Assure a real minimum spacing, walking the sets top-to-bottom (the
            # order above) so each set's patches are spaced against the ones above
            # — not just landed on distinct grid cells (Knut, #78). Seed the
            # chart's EXISTING patches first so even the topmost generator avoids
            # overlapping them, not just the other generators (Knut, #89). In the
            # New Chart flow there are none, so this is unchanged there.
            program = G.enforce_min_distance(
                program, _GEN_MIN_DIST, existing=self._existing_patches)
        # Pure white & black goes in *after* de-dup (so its deliberate repeats
        # survive) but *before* fill, so it's part of the chart fill tops up to —
        # not stacked on top of it. These are deliberate anchor patches, so they
        # add N of each on top of the existing chart; only the corners the other
        # sets contribute in *this* batch count toward N (#76, Knut).
        if self._gen_whiteblack.isChecked():
            have_w, have_b = G.count_white_black(program)
            program.extend(G.white_black(
                self._gen_whiteblack_n.value(), have_w, have_b))
        # Fill runs last so it tops the *whole* chart (patches already on it, the
        # chosen sets and the white/black anchors) up to the target, placed where
        # it's sparse and avoiding everything already chosen (#51).
        if self._gen_fill.isChecked():
            seed = self._existing_patches + program
            program.extend(G.fill_gaps(seed, self._effective_fill_target()))
        return program

    # -- live 3D-cube preview (embedded panel) ----------------------------
    # An always-visible cube panel docked beside the colour-set controls that
    # mirrors the generator in real time: it shows exactly what the ticked sets
    # would produce (plus the chart's existing patches, dimmed, in the Add flow),
    # redrawing whenever a setting changes. Embedded — not a separate window —
    # so it can't fight the dialog's modal session (which on macOS broke Create/
    # Add and left the editor unclosable). Shared by New-chart and Add dialogs.
    # Extra dialog width the cube adds when unfolded (controls keep their own
    # natural width; the cube takes this much beside them).
    _CUBE_WIDTH = 460

    def _make_cube_panel(self) -> QWidget:
        from ui.patch_cube_panel import PatchCubePanel
        from ui.theme import resolve_mode
        mode = resolve_mode(self._settings.get("appearance", "auto")
                            if self._settings else "auto")
        self._cube_panel = PatchCubePanel(mode=mode, parent=self)
        self._cube_panel.setMinimumWidth(360)
        self._cube_shown = True
        # Coalesce bursts of control changes into one redraw ~300 ms after the
        # last change — a full Plotly.react on every spinbox tick would thrash.
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(300)
        self._preview_timer.timeout.connect(self._do_push_live_preview)
        return self._cube_panel

    def _build_body(self, scroll: QScrollArea, content_w: int) -> "QHBoxLayout":
        """Lay the controls (`scroll`, kept at their natural width) beside the
        embedded cube (which takes the remaining space). Records the widths the
        fold toggle needs."""
        # +room for the vertical scrollbar so the options are never clipped.
        self._controls_w = content_w + 22
        scroll.setMinimumWidth(self._controls_w)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(scroll, 0)              # controls: keep their width
        body.addWidget(self._make_cube_panel(), 1)  # cube: take the rest
        return body

    def _make_fold_button(self) -> QPushButton:
        btn = QPushButton(self)
        btn.setCheckable(True)
        btn.setToolTip(tr("Show or hide the live 3D-cube preview."))
        btn.toggled.connect(self._on_fold_toggled)
        self._fold_btn = btn
        return btn

    def _init_fold_state(self, base_height: int) -> None:
        """Apply the remembered fold state and size the dialog accordingly.
        The cube starts folded away by default — opt in per session."""
        shown = (bool(self._settings.get("new_chart_show_cube", False))
                 if self._settings else False)
        self.resize(self._controls_w, base_height)   # set the height once
        self._fold_btn.blockSignals(True)
        self._fold_btn.setChecked(shown)
        self._fold_btn.blockSignals(False)
        self._on_fold_toggled(shown)

    def _on_fold_toggled(self, shown: bool) -> None:
        self._cube_shown = shown
        # Unfolding in state 3 renders the Lab cloud on demand (#72) — it is
        # only computed while the panel is actually visible.
        if shown and self._nch_state() == 3:
            self._push_live_preview()
        # Capture the centre *first*: when unfolding, raising the minimum width
        # below makes Qt resize the window immediately (and rightward, top-left
        # fixed), so a centre read after that already reflects the grown, shifted
        # geometry. Remembering it up front lets us recentre symmetrically.
        was_visible = self.isVisible()
        center = self.frameGeometry().center()
        self._cube_panel.setVisible(shown)
        # Cube sits on the right: hiding collapses it inward (◂), showing
        # expands it outward (▸).
        self._fold_btn.setText(tr("◂ Hide 3D preview") if shown
                               else tr("Show 3D preview ▸"))
        if self._settings is not None:
            self._settings.set("new_chart_show_cube", shown)
        # Clamp the minimum width to fit both panes when shown, so the window
        # can't be dragged narrow enough for the cube to overrun the options.
        cube_min = self._cube_panel.minimumWidth() if shown else 0
        self.setMinimumWidth(self._controls_w + cube_min)
        new_w = self._controls_w + (self._CUBE_WIDTH if shown else 0)
        self.resize(new_w, self.height())
        if was_visible:
            # Grow / shrink symmetrically about the pre-toggle centre so the
            # dialog extends to both sides equally instead of only to the right.
            fg = self.frameGeometry()
            fg.moveCenter(center)
            self.move(fg.topLeft())
        # (Not shown yet → construction; showEvent centres it over the parent.)
        if shown:
            self._do_push_live_preview()   # refresh after being hidden

    def exec(self) -> int:  # noqa: A003 - intentional QDialog.exec override
        """Enter the modal loop, but first realize the cube's web view while the
        dialog is still non-modal — even when it opens folded.

        Creating a ``QWebEngineView``'s native child surface *inside* an
        application-modal dialog wedges the modal grab on Windows and freezes
        the whole app (issue #38 follow-up). The startup warm-up keeps Chromium
        alive but each view still spawns its own surface. So we show the dialog
        non-modally, build the view off the modal path, let the surface settle,
        then enter the modal loop with it already in place — whether the cube
        starts unfolded (the view stays visible) or folded (a later unfold just
        re-shows the existing surface instead of creating one while modal). A
        folded-open cube must be momentarily shown to realize the surface; we
        hide that behind window-opacity 0 so there's no flash."""
        panel = getattr(self, "_cube_panel", None)
        if panel is not None:
            folded = not getattr(self, "_cube_shown", False)
            if folded:
                self.setWindowOpacity(0.0)   # hide the brief realize-unfold
            self.show()                      # non-modal: realize the dialog
            if folded:
                panel.setVisible(True)       # must be visible to realize the surface
            panel.ensure_view()              # build the web view off the grab
            QApplication.processEvents()     # let the native surface settle
            if folded:
                panel.setVisible(False)      # restore folded; the surface persists
                self.setWindowOpacity(1.0)
        self._fit_content_min_height()
        return super().exec()

    def _fit_content_min_height(self) -> None:
        """Pin a minimum height that fully shows the scrolled left column.

        The controls live in a ``QScrollArea`` whose own sizeHint is small, so
        the dialog could open (or be dragged) shorter than the column needs and
        clip it. The column's realized height is only known once shown, so do
        this from exec() after the window has settled: needed dialog height =
        the content's natural height + the chrome around the scroll viewport
        (masthead, buttons, margins). Capped at 92 % of the screen."""
        if not getattr(self, "_fit_content_height", False):
            return
        sc = getattr(self, "_scroll", None)
        if sc is None or sc.widget() is None:
            return
        self.layout().activate()
        QApplication.processEvents()
        viewport_h = sc.viewport().height()
        if viewport_h <= 0:
            return  # geometry not settled — leave the initial sizing in place
        chrome = self.height() - viewport_h
        need = sc.widget().sizeHint().height() + chrome
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            need = min(need, int(screen.availableGeometry().height() * 0.92))
        self.setMinimumHeight(need)
        if self.height() < need:
            self.resize(self.width(), need)

    def _push_live_preview(self) -> None:
        """Schedule a debounced rebuild — refreshes the exact total (and the cube
        if it's unfolded). Runs even while folded so the total stays correct."""
        if getattr(self, "_preview_timer", None) is not None:
            self._preview_timer.start()

    def _do_push_live_preview(self) -> None:
        if getattr(self, "_gen_total", None) is None:
            return
        state = self._nch_state()
        if state == 2:
            # No colour model: building the real program shells targen — too
            # heavy for a live keystroke path (#72 R5), and the cube is
            # hidden in state 2 anyway. The per-row estimates stand.
            return
        if state == 3:
            self._push_lab_cloud()
            return
        # The generated additions for the current set selection. Built even when
        # the master Generate toggle is off, so the Total previews them like the
        # per-set counts do; using the real built program also catches the
        # white/black de-dup against existing patches the estimate can't see (the
        # original 921-vs-924 drift in #60).
        additions = self._build_generated_program()
        # Total = the additions only (not the existing chart), shown always (#60).
        self._gen_total.setText(tr("Total: {label}").format(
            label=_patches_label(len(additions))))
        # In the Add flow, also the chart's resulting size (existing + additions).
        if self._existing_patches:
            self._gen_after_total.setText(tr("Chart after adding: {label}").format(
                label=_patches_label(len(self._existing_patches) + len(additions))))
        # The cube shows whatever the *active* source mode would contribute —
        # pasted/loaded colours and the single Add colour too, not only the
        # generated sets (#96).
        program = self._live_preview_program(additions)
        if getattr(self, "_cube_panel", None) is not None and self._cube_shown:
            self._cube_panel.set_program(program, self._existing_patches)

    def _push_lab_cloud(self) -> None:
        """State-3 3D preview (#72): the generated ink patches as a Lab-space
        scatter, positions from the preconditioning profile (``xicclu -ff``),
        each point painted its display-approximation colour.

        Heavy (targen + xicclu subprocesses), so it only runs when the cube
        is actually unfolded, sits behind the existing debounce, and caches
        by the full generator state — spinbox bursts reuse the cache (R5).
        """
        if (getattr(self, "_cube_panel", None) is None or not self._cube_shown
                or getattr(self, "_nch_cube_hidden", False)):
            return
        if not self._gen_sets_active():
            return
        import json as _json
        key = _json.dumps(self._collect_gen_state(), sort_keys=True,
                          default=str)
        cached = getattr(self, "_lab_cloud_cache", None)
        if cached is not None and cached[0] == key:
            labs, colors = cached[1], cached[2]
        else:
            try:
                from workflow.xicclu_runner import forward_lab
                program = self._build_generated_program()
                if not program:
                    return
                bin_dir = self._bin_dir
                labs = forward_lab(program, self._precond_path, bin_dir)
                rep = ("CMYK" if not self._extra_inks
                       else R.color_rep_for_inks(self._nch_ink_codes())[0])
                colors = []
                for dev in program:
                    r, g, b = _display100(dev, rep)
                    colors.append((round(r * 2.55), round(g * 2.55),
                                   round(b * 2.55)))
                self._lab_cloud_cache = (key, labs, colors)
            except Exception as exc:  # noqa: BLE001 — preview is best-effort
                log.warning("Lab cloud preview failed: %s", exc)
                return
        self._cube_panel.set_lab_cloud(labs, colors)
        self._gen_total.setText(tr("Total: {label}").format(
            label=_patches_label(len(labs))))

    def _live_preview_program(self, additions: list) -> list:
        """The colours the current source mode would add, for the live 3D cube.

        Paste / "load from file" → the parsed colours; Add's single colour or
        loaded file → those; generated sets → the additions. Seed-from-targen
        isn't previewed (it needs a targen run, too slow to do live). (#96)
        """
        pm = getattr(self, "_mode_paste", None)
        if pm is not None and pm.isChecked():
            return R.parse_color_values(self._paste_edit.toPlainText())
        sm = getattr(self, "_add_mode_single", None)
        if sm is not None and sm.isChecked():
            return [self._single_rgb]
        fm = getattr(self, "_add_mode_file", None)
        if fm is not None and fm.isChecked():
            return list(getattr(self, "_loaded_add_program", []))
        return additions if self._gen_sets_active() else []

    def _ensure_cube_shown(self) -> None:
        """Unfold the live 3D cube if it's collapsed — called after loading
        colours from a file so the distribution is visible immediately, not
        hidden behind the fold (#96)."""
        btn = getattr(self, "_fold_btn", None)
        if btn is not None and not btn.isChecked():
            btn.setChecked(True)   # fires _on_fold_toggled → re-pushes the cube

    def showEvent(self, ev) -> None:  # noqa: N802
        super().showEvent(ev)
        # Centre over the parent window on first show. The dialog used to settle
        # its size early because the cube's QWebEngineView forced a layout pass
        # in __init__; now that the cube is built lazily, exec() can drop the
        # window at the screen's top-left, so recentre once the size is known.
        if getattr(self, "_centred_once", False):
            return
        self._centred_once = True
        par = self.parentWidget()
        ref = (par.window().frameGeometry()
               if par is not None and par.window() is not None
               else self.screen().availableGeometry())
        fg = self.frameGeometry()
        fg.moveCenter(ref.center())
        self.move(fg.topLeft())

    def done(self, result: int) -> None:  # noqa: N802
        # done() is the chokepoint for accept (Create / Add), reject (Cancel)
        # and the window's X — drain the embedded cube's web view while the loop
        # is still alive (issue #38) before the dialog goes away.
        if getattr(self, "_cube_panel", None) is not None:
            self._cube_panel.teardown()
        super().done(result)

    def _load_gen_image(self) -> None:
        """Load + decode an image for the 'From image' colour set.

        Decoding (Pillow) and down-sampling happen here; the pure
        :func:`patch_generators.image_palette` does the clustering. The image is
        shrunk to a small thumbnail first — plenty for finding representative
        colours and keeps k-means fast.
        """
        start = (self._settings.get("custom_output_path", "")
                 or str(Path.home()))
        from ui.widgets import open_file_dialog
        path = open_file_dialog(
            self, tr("Load image"),
            name_filter="Images (*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.webp)",
            start_dir=start, preview=True)
        if not path:
            return
        try:
            from PIL import Image
            import numpy as np
            im = Image.open(path).convert("RGB")
            im.thumbnail((200, 200))
            self._gen_image_px = np.asarray(im).reshape(-1, 3)
        except Exception as exc:  # noqa: BLE001 — surface any decode failure
            QMessageBox.warning(self, tr("Load failed"), str(exc))
            return
        self._gen_image_name = Path(path).name
        self._gen_image_btn.setText(self._gen_image_name)
        self._gen_image.setChecked(True)
        self._update_gen_counts()

    # -- helpers -----------------------------------------------------------
    def _refresh_source_widgets(self) -> None:
        self._count.setEnabled(self._mode_seed.isChecked())
        self._paste_edit.setEnabled(self._mode_paste.isChecked())
        self._update_gen_counts()
        self._do_push_live_preview()   # the cube follows the active mode (#96)

    def _refresh_spacer_scale_enabled(self, *_a) -> None:
        """Disable Spacer scale (-A) when "None" is the spacer choice —
        there's nothing for the scale to apply to in that case."""
        self._spacer_scale.setEnabled(not self._sp_none.isChecked())

    def _on_paper_changed(self) -> None:
        """Show the custom W/H row only when "Custom" is the selection."""
        self._paper_custom_row.setVisible(
            self._paper.currentData() == "custom")
        self._update_engine_cap_hint()

    def _update_engine_cap_hint(self, *_a) -> None:
        """Show how many patches fit one page (engine layout) for the current
        instrument/paper/mode — only when the engine is active (#93)."""
        hint = getattr(self, "_engine_cap_hint", None)
        if hint is None:
            return
        cap = self._engine_cap_per_page()
        hint.setText(tr("≈ {n} fit one page").format(n=cap) if cap > 0 else "")

    def _refresh_instr_widgets(self) -> None:
        """Show/hide instrument-conditional options.

        Strip readers (i1Pro family + i1Pro 3 Plus): ``-L`` (suppress left
        clip) + ``-P`` (no strip limit) — both layout flags Argyll documents
        as strip-reader-only.
        ColorMunki: ``-h`` (double density) + Triple density — the rig-only
        layout tweaks. Hidden controls also reset to off so a hidden value
        can't leak through into the printtarg command on Create.
        """
        code = self._instr.currentData()
        is_strip = code in _STRIP_INSTRUMENTS
        is_cm = code == "CM"
        self._cb_L.setVisible(is_strip)
        self._cb_P.setVisible(is_strip)
        self._cb_h.setVisible(is_cm)
        self._cb_td.setVisible(is_cm)
        if not is_strip:
            self._cb_L.setChecked(False)
            self._cb_P.setChecked(False)
        if not is_cm:
            self._cb_h.setChecked(False)
            self._cb_td.setChecked(False)
        # Engine layout-mode controls (Chart section): clip / no-cap for strip
        # readers, density dropdown for the ColorMunki.
        if getattr(self, "_engine_on", False):
            self._eng_clip.setVisible(is_strip)
            self._eng_nocap.setVisible(is_strip)
            self._eng_density_lbl.setVisible(is_cm)
            self._eng_density.setVisible(is_cm)
        self._update_engine_cap_hint()

    def _on_dd_toggled(self, on: bool) -> None:
        """Toggling double density off triple density (mutual exclusion)."""
        if on and self._cb_td.isChecked():
            self._cb_td.setChecked(False)
        self._update_engine_cap_hint()

    def _on_td_toggled(self, on: bool) -> None:
        """Apply / undo the triple-density preset on the layout widgets.

        Mirrors the manual triple-density toggle in
        ``ui/tabs/tab_chart.py`` (``_on_manual_td_toggled``): when enabled,
        stash the user's -a / -m / -L / -P values and overwrite them with the
        preset (1.3 / 5 / on / on); restore on untoggle. Also keeps Double
        density mutually exclusive.
        """
        if on and self._cb_h.isChecked():
            self._cb_h.setChecked(False)
        self._cb_h.setEnabled(not on)
        if on:
            self._td_stash = {
                "a": self._patch_scale.value(),
                "m": self._margin.value(),
                "L": self._cb_L.isChecked(),
                "P": self._cb_P.isChecked(),
            }
            self._patch_scale.setValue(1.3)
            self._margin.setValue(5)
            self._cb_L.setChecked(True)
            self._cb_P.setChecked(True)
        else:
            stash = getattr(self, "_td_stash", None) or {}
            if "a" in stash:
                self._patch_scale.setValue(stash["a"])
            if "m" in stash:
                self._margin.setValue(stash["m"])
            if "L" in stash:
                self._cb_L.setChecked(bool(stash["L"]))
            if "P" in stash:
                self._cb_P.setChecked(bool(stash["P"]))
            self._td_stash = None
        self._update_engine_cap_hint()

    def _update_paste_count(self) -> None:
        parsed = R.parse_color_values(self._paste_edit.toPlainText())
        self._paste_status.setText(f"{len(parsed)} colour(s) parsed"
                                    if parsed else "")

    def _load_paste_file(self) -> None:
        path = open_file_dialog(
            self, "Load colour values",
            "Colour files (*.txt *.ti1 *.ti2 *.ti3 *.cgats *.csv *.tsv);;"
            "All files (*)", start_dir=str(Path.home()))
        if not path:
            return
        self.raise_(); self.activateWindow()   # keep above the editor (#96)
        # Parse device-RGB CGATS files (ti1/ti2/ti3/cgats) and plain hex/RGB
        # lists. CIE reference files (XYZ/LAB) aren't supported (#96).
        try:
            prog = R.load_colour_file(Path(path))
        except Exception as exc:  # noqa: BLE001 — surface the parser's message
            QMessageBox.warning(self, tr("Could not read file"), str(exc))
            return
        if not prog:
            QMessageBox.warning(self, tr("No colours"),
                                tr("No colour values were found in that file."))
            return
        # Write the parsed 0..100 RGB into the paste box (its parser reads them
        # back unchanged — a white patch pins the 0..100 scale).
        self._paste_edit.setPlainText(
            "\n".join(f"{r:.4f} {g:.4f} {b:.4f}" for r, g, b in prog))
        self._mode_paste.setChecked(True)
        self._ensure_cube_shown()   # reveal the distribution right away (#96)

    def _on_ok(self) -> None:
        paper_code = self._paper.currentData() or self._paper.currentText()
        if paper_code == "custom":
            paper_code = f"{self._paper_w.value()}x{self._paper_h.value()}"
        dt = self._nch_device_type()
        extras = (tuple(self._extra_inks)
                  if self._device_type.currentData() == "cmykplus" else ())
        spec = R.ChartSpec.new(self._instr.currentData(), paper_code,
                               device_type=dt, extra_inks=extras)
        if dt != "2":
            spec.ink_limit = float(self._ink_limit.value())
        # ChartSpec.new only knows the named-paper inverse map; patch
        # paper_mm explicitly for custom sizes so the editor knows the
        # canvas dimensions for downstream code (preview scaling etc.).
        if self._paper.currentData() == "custom":
            spec.paper_mm = (float(self._paper_w.value()),
                              float(self._paper_h.value()))
        program: list[tuple] = []
        if self._mode_seed.isChecked():
            # Multi-ink seeding rides targen natively (#72): -D per extra ink,
            # -l ink limit, -c preconditioning profile (state 3 — also
            # improves the OFPS distribution).
            extra_args = [f"-D{self._INK_DFLAG[c]}" for c in extras]
            if dt != "2":
                extra_args.append(f"-l{int(self._ink_limit.value())}")
                if self._precond_path and self._validate_precond(quiet=True):
                    extra_args += ["-c", self._precond_path]
            try:
                program = R.seed_from_targen(self._bin_dir, self._count.value(),
                                             device=dt, extra_args=extra_args)
            except Exception as exc:
                QMessageBox.warning(self, tr("targen failed"), str(exc))
                return
        elif self._mode_paste.isChecked():
            program = R.parse_color_values(self._paste_edit.toPlainText())
            if not program:
                QMessageBox.warning(self, tr("No values"),
                                    tr("Couldn't parse any RGB / hex values "
                                    "from the pasted text."))
                return
        elif self._mode_generate.isChecked():
            try:
                program = self._build_generated_program()
            except Exception as exc:  # noqa: BLE001 — targen/xicclu failure
                QMessageBox.warning(self, tr("Generation failed"), str(exc))
                return
            if not program:
                QMessageBox.warning(self, tr("No colour sets"),
                                    tr("Tick at least one colour set to "
                                    "generate patches from."))
                return

        # Mutex-checkbox group: at most one is on; all-off falls through
        # to printtarg's coloured default.
        if self._sp_bw.isChecked():
            sm = "bw"
        elif self._sp_none.isChecked():
            sm = "none"
        else:
            sm = "colored"
        opts = R.LayoutOptions(
            spacer_mode=sm,
            patch_scale=self._patch_scale.value(),
            spacer_scale=self._spacer_scale.value(),
            margin_mm=self._margin.value(),
            suppress_left_clip=self._cb_L.isChecked(),
            no_strip_limit=self._cb_P.isChecked(),
            double_density=self._cb_h.isChecked(),
            triple_density=self._cb_td.isChecked(),
            tiff_16bit=self._bd_16.isChecked(),
            dpi=self._dpi.value(),
        )

        self.result_spec = spec
        self.result_program = program
        self.result_options = opts
        # The full creation recipe, so the editor can persist it on the chart
        # (reloaded into New chart / Add later to tweak/recreate the design).
        self.result_recipe = self._collect_gen_state()
        # No name is asked for here any more — the real name is chosen at
        # Save & apply time. Keep the neutral "chart" placeholder basename.
        self.result_basename = "chart"
        self.result_engine_clip = self._eng_clip.isChecked()
        self.result_engine_nocap = self._eng_nocap.isChecked()
        self.result_engine_density = int(self._eng_density.currentData() or 1)
        self._save_gen_state()   # remember these choices for next time
        self.accept()


class _AddPatchesDialog(_NewChartDialog):
    """The editor's "Add…" dialog: add a single chosen colour, or generate one
    or more colour sets (the New-chart generate panel — 3D cube, skin tones,
    blues, greens, sunrises, greys, edges, highlights/shadows, pastels, from
    image, fill) to append to the loaded chart.

    Reuses :class:`_NewChartDialog`'s generate panel + program builder, but the
    surrounding chrome is different (no chart-identity / layout frames, no
    source-mode radios), so it deliberately bypasses the full New-chart
    ``__init__`` and builds only what it needs. On accept, ``result_program``
    holds the RGB triples to splice into the grid.
    """

    def __init__(self, settings=None, parent: QWidget | None = None,
                 existing_patches=None, initial_recipe=None) -> None:
        QDialog.__init__(self, parent)
        self.setWindowTitle(tr("Add patches"))
        self.setMinimumWidth(620)
        self._settings = settings
        # The chart's creation recipe, if reopened from a chart that has one —
        # its colour-set choices pre-fill the generate panel instead of the
        # app-wide last-used ones (Add only has the generate panel, so just the
        # cb/sp portion applies).
        self._initial_recipe = initial_recipe
        self.result_program: list[tuple] | None = None
        # State the inherited generate-panel methods expect. The chart's current
        # patches let "Fill remaining gaps" top the whole chart up to its target
        # instead of appending that many (#51); set before _build_generate_panel.
        self._existing_patches = list(existing_patches or [])
        self._gen_image_px = None
        self._gen_image_name = ""
        self._single_rgb: tuple[float, float, float] = (50.0, 50.0, 50.0)
        self._install_magenta_accents()

        content = QWidget(self)
        lay = QVBoxLayout(content)
        lay.setSpacing(10)

        # NB: the tab-style heading + full-width spectrum stripe are added to the
        # dialog's ``outer`` layout (above the body), not here, so they span the
        # window and the 3D-cube preview sits below them.

        # Mode: a single colour, or generated colour sets.
        self._add_mode_single = QRadioButton(
            tr("Add a single colour"), self)
        self._add_mode_gen = QRadioButton(tr("Generate colour sets"), self)
        self._add_mode_single.setChecked(True)
        grp = QButtonGroup(self)
        grp.addButton(self._add_mode_single)
        grp.addButton(self._add_mode_gen)
        lay.addWidget(self._add_mode_single)

        # Single-colour row: a swatch + colour picker.
        single_row = QHBoxLayout()
        single_row.setContentsMargins(22, 0, 0, 0)
        self._single_swatch = QLabel(self)
        self._single_swatch.setFixedSize(28, 22)
        self._single_swatch.setFrameShape(QFrame.Shape.StyledPanel)
        self._paint_single_swatch()
        single_btn = QPushButton(tr("Choose colour…"), self)
        single_btn.setObjectName("compact_input")
        single_btn.clicked.connect(self._pick_single_colour)
        single_row.addWidget(self._single_swatch)
        single_row.addWidget(single_btn)
        single_row.addStretch(1)
        lay.addLayout(single_row)

        # Load colours from a file — CGATS (ti1/ti2/ti3/cgats), CIE reference
        # (XYZ/LAB) or a plain hex/RGB list — so a set can be added from a file
        # without having to create a whole new chart (#96).
        self._add_mode_file = QRadioButton(tr("Load colours from a file"), self)
        grp.addButton(self._add_mode_file)
        lay.addWidget(self._add_mode_file)
        self._loaded_add_program: list = []
        file_row = QHBoxLayout()
        file_row.setContentsMargins(22, 0, 0, 0)
        self._add_file_btn = QPushButton(tr("Choose file…"), self)
        self._add_file_btn.setObjectName("compact_input")
        self._add_file_btn.clicked.connect(self._load_add_file)
        self._add_file_status = QLabel("", self)
        self._add_file_status.setStyleSheet("color: #888;")
        file_row.addWidget(self._add_file_btn)
        file_row.addWidget(self._add_file_status)
        file_row.addStretch(1)
        file_row.addWidget(_magenta_tip(
            tr("Load colours from a file"),
            tr("Add the colours from an existing file to this chart. Works with "
               "Argyll measurement / target files (.ti1, .ti2, .ti3, .cgats) that "
               "carry device-RGB values, and plain lists of hex or RGB values. "
               "Near-duplicate colours are automatically spaced apart so the "
               "chart still reads reliably."), self))
        lay.addLayout(file_row)
        self._add_mode_file.toggled.connect(self._refresh_add_mode)

        lay.addWidget(self._add_mode_gen)
        lay.addLayout(self._build_generate_panel(content))
        self._add_mode_single.toggled.connect(self._refresh_add_mode)
        self._refresh_add_mode()
        # Soak up any extra height at the bottom so the controls stay packed at
        # the top instead of drifting apart when the dialog is taller than its
        # content (single-colour mode is short).
        lay.addStretch(1)

        btns = QHBoxLayout()
        restore = QPushButton(tr("Restore defaults"), self)
        restore.setToolTip(tr("Reset the colour sets back to their defaults."))
        restore.clicked.connect(lambda: self._apply_gen_sets_and_refresh(
            self._GEN_FACTORY))
        btns.addWidget(restore)
        btns.addWidget(self._make_fold_button())
        btns.addStretch(1)
        ok = QPushButton(tr("Add to chart"), self)
        ok.setDefault(True)
        ok.clicked.connect(self._on_add)
        cancel = QPushButton(tr("Cancel"), self)
        cancel.clicked.connect(self.reject)
        btns.addWidget(ok)
        btns.addWidget(cancel)

        scroll = FadeScrollArea(self, surface="dialog")
        from ui.theme import resolve_mode
        scroll.set_appearance(resolve_mode(
            (self._settings.get("appearance", "auto") if self._settings else "auto")))
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        # Kept for exec()'s content-fit pass: the left column lives in this
        # scroll area, and its realized height is only known once shown.
        self._scroll = scroll
        self._fit_content_height = True
        # Controls on the left (kept at their natural width), the foldable live
        # 3D cube on the right.
        hint = content.sizeHint()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        head = QHBoxLayout()
        head.setContentsMargins(16, 12, 16, 0)
        head.addWidget(TabHeader(
            tr("EXTEND THE CHART"), tr("Add patches"), SPEC_MAGENTA, self),
            0, Qt.AlignmentFlag.AlignVCenter)
        GradientOverlay(SPEC_MAGENTA, parent=self, alpha=15, height=95, on_top=False)
        head.addStretch(1)
        # ⓘ with the same generator-sets help the New-chart dialog carries, so
        # the Add window explains the colour sets too (#66 follow-up).
        head.addWidget(_magenta_tip(
            tr("Add patches"),
            tr(_ADD_TIP_INTRO) + "\n\n" + tr(_GEN_SETS_HELP),
            self, min_width=520))
        outer.addLayout(head)
        outer.addWidget(_SpectrumStripe(self))
        outer.addLayout(self._build_body(scroll, hint.width()), 1)
        btns.setContentsMargins(12, 4, 12, 10)
        outer.addLayout(btns)
        # Height tracks the content (capped) so the dialog isn't mostly empty
        # space; width follows the fold state. exec() pins a proper minimum
        # height once the left column's realized size is known (see
        # _fit_content_height / the exec override).
        self._init_fold_state(min(760, hint.height() + 72))

        # Prefer the chart's own recipe (reopened to extend that design);
        # otherwise share the New-chart dialog's last-used colour-set choices.
        st = self._initial_recipe if isinstance(self._initial_recipe, dict) else (
            self._settings.get("new_chart_gen", None) if self._settings else None)
        if isinstance(st, dict):
            self._apply_gen_sets(st)
        self._update_gen_counts()
        self._do_push_live_preview()   # seed the cube (existing patches + sets)

    # The generate panel is the active source only in "Generate colour sets"
    # mode — drives the panel-enable in the inherited _update_gen_counts.
    def _gen_sets_active(self) -> bool:
        return self._add_mode_gen.isChecked()

    def _refresh_add_mode(self, *_a) -> None:
        self._update_gen_counts()
        self._do_push_live_preview()   # the cube follows the active mode (#96)

    def _load_add_file(self) -> None:
        path = open_file_dialog(
            self, "Load colours",
            "Colour files (*.txt *.ti1 *.ti2 *.ti3 *.cgats *.csv *.tsv);;"
            "All files (*)", start_dir=str(Path.home()))
        if not path:
            return
        self.raise_(); self.activateWindow()   # keep above the editor (#96)
        try:
            prog = R.load_colour_file(Path(path))
        except Exception as exc:  # noqa: BLE001 — surface the parser's message
            QMessageBox.warning(self, tr("Could not read file"), str(exc))
            return
        if not prog:
            QMessageBox.warning(self, tr("No colours"),
                                tr("No colour values were found in that file."))
            return
        # Space out near-duplicate colours so the chart still reads — a loaded
        # set can repeat or run similar colours together (#96).
        try:
            prog = G.deduplicate(prog)
        except Exception as exc:  # noqa: BLE001 — keep the raw set if dedupe fails
            log.warning("deduplicate loaded colours failed: %s", exc)
        self._loaded_add_program = prog
        self._add_mode_file.setChecked(True)
        self._add_file_status.setText(
            tr("1 colour loaded") if len(prog) == 1
            else tr("{n} colours loaded").format(n=len(prog)))
        self._ensure_cube_shown()      # reveal the distribution right away (#96)
        self._do_push_live_preview()   # show the loaded colours in the cube (#96)

    def _paint_single_swatch(self) -> None:
        r, g, b = (max(0, min(255, round(c / 100 * 255)))
                   for c in self._single_rgb)
        self._single_swatch.setStyleSheet(
            f"background:#{r:02x}{g:02x}{b:02x}; border:1px solid #888;")

    def _pick_single_colour(self) -> None:
        r, g, b = (max(0, min(255, round(c / 100 * 255)))
                   for c in self._single_rgb)
        # Non-native picker (same as the editor's _pick_color) so the hex field
        # + RGB/HSV spinners are available, matching the rest of the editor.
        c = QColorDialog.getColor(
            QColor(r, g, b), self, tr("Pick colour"),
            QColorDialog.ColorDialogOption.DontUseNativeDialog)
        if not c.isValid():
            return
        self._single_rgb = (c.red() / 255 * 100, c.green() / 255 * 100,
                            c.blue() / 255 * 100)
        self._paint_single_swatch()
        self._add_mode_single.setChecked(True)
        self._do_push_live_preview()   # show the picked colour in the cube (#96)

    def _apply_gen_sets_and_refresh(self, st: dict) -> None:
        self._apply_gen_sets(st)
        self._update_gen_counts()

    def _on_add(self) -> None:
        if self._add_mode_file.isChecked():
            if not self._loaded_add_program:
                QMessageBox.warning(self, tr("No file"),
                                    tr("Choose a colour file to add first."))
                return
            self.result_program = list(self._loaded_add_program)
            self.accept()
            return
        if self._add_mode_gen.isChecked():
            program = self._build_generated_program()
            if not program:
                QMessageBox.warning(self, tr("No colour sets"),
                                    tr("Tick at least one colour set to "
                                    "generate patches from."))
                return
            # Remember the colour-set choices for next time (shared with the
            # New-chart dialog), without disturbing its chart/layout state —
            # this window has no chart or layout frames of its own, so only the
            # generator half is ours to speak for.
            if self._settings is not None:
                cur = self._settings.get("new_chart_gen", None)
                cur = dict(cur) if isinstance(cur, dict) else {}
                cur.update(self._collect_gen_sets())
                self._settings.set("new_chart_gen", cur)
        else:
            program = [self._single_rgb]
        self.result_program = program
        self.accept()


# ---------------------------------------------------------------------------
# Main editor
# ---------------------------------------------------------------------------
# How many editing steps the undo/redo history keeps. Edits here are coarse
# (recolour a selection, reorder, add/remove a batch, paint spacers, one layout
# tweak), not fine brush strokes, so 20 is generous. Each snapshot is a cheap
# in-memory copy of the editable state (a few hundred KB for a huge chart, tens
# of KB typically) — the history never touches disk and is dropped when the
# dialog closes.
_UNDO_DEPTH = 20


@dataclass
class _EditorSnapshot:
    """A point-in-time copy of everything the user can edit in one chart: the
    patch program (colours + order), the spacer palette + per-spacer paint, the
    printtarg layout knobs, and the instrument/paper (which live on the spec).

    Captured by :meth:`Ti2RelayoutDialog._make_snapshot` and re-applied by
    :meth:`Ti2RelayoutDialog._restore_snapshot`. ``key`` is a hashable digest
    used only to skip capturing a step that didn't actually change anything."""
    program: list = field(default_factory=list)
    palette: "list | None" = None
    paint: dict = field(default_factory=dict)
    options: "R.LayoutOptions | None" = None
    instr: str = ""
    paper: str = ""
    paper_mm: tuple = (0.0, 0.0)

    @property
    def key(self) -> tuple:
        return (
            tuple(self.program),
            tuple(self.palette) if self.palette else None,
            tuple(sorted(self.paint.items())),
            astuple(self.options) if self.options is not None else None,
            self.instr, self.paper, tuple(self.paper_mm),
        )


class Ti2RelayoutDialog(QDialog):
    def __init__(self, runner, settings, parent: QWidget | None = None,
                 on_apply: "Callable[[Path, str], bool | None] | None" = None,
                 initial_chart: "Path | None" = None) -> None:
        super().__init__(parent)
        self._settings = settings
        # Callback that hands a freshly-saved chart folder to the Create Chart
        # tab (set by the main window). When present, the action footer offers
        # "Save & apply" instead of the plain colour-export button.
        self._on_apply = on_apply
        # Chart to pre-load when the editor opens — the Create Chart tab's
        # current generated chart, so it's ready to edit (#45). Loaded after
        # the UI is built (end of __init__).
        self._initial_chart = initial_chart
        self._bin_dir = Path(settings.get("argyll_bin_path", "/Applications/Argyll/bin"))
        self.setWindowTitle(tr("Edit / create chart patch set"))
        # Wider default so the printtarg-options column doesn't clip its
        # row labels ("Margin (mm):", "Spacer -A:") or its combo content
        # ("A4 (210 × 297 mm) Portrait") on first open.
        self.resize(1280, 820)
        self.setMinimumSize(1000, 620)

        self._spec: R.ChartSpec | None = None
        # The chart's creation recipe (New chart / Add window state) when known —
        # threaded from the New chart dialog, or loaded from meta.json — so it
        # can be re-persisted on save and reloaded into New chart / Add.
        self._chart_recipe: dict | None = None
        # The chart's ChromIQ-engine recipe (from channels.json) when it was
        # built by the engine — drives the engine layout panel (#93).
        self._engine_recipe = None
        self._engine_panel = None
        self._engine_panel_grp = None
        # True only when a chart was LOADED from disk without an engine recipe
        # (a printtarg chart) — then the editor stays printtarg even if the
        # engine setting is on. A new/from-scratch chart follows the setting.
        self._loaded_printtarg_chart = False
        self._engine_ti1: "Path | None" = None     # patch data for engine preview
        # Guards the live "Pages" spin against re-entrancy while we sync its
        # value to the rendered page count (#93).
        self._syncing_pages = False
        self._engine_spacer_rects: list = []        # spacer hit-boxes (preview dpi)
        self._engine_patch_rects: dict = {}         # (page,slot) -> rect dict
        self._engine_slots: list = []               # grid index -> slot
        # Debounced engine preview: re-render via the engine after the last edit.
        self._engine_preview_timer = QTimer(self)
        self._engine_preview_timer.setSingleShot(True)
        self._engine_preview_timer.setInterval(450)
        self._engine_preview_timer.timeout.connect(self._do_engine_preview)
        # Snapshot of the chart's content (patches + spacers + layout knobs) as
        # last saved / loaded-from-disk. Compared against the live signature to
        # tell whether there are unsaved edits to warn about on Close (#49). A
        # fresh sentinel means "never saved" (a created chart is dirty at once).
        self._saved_sig: object = object()
        self._palette: list[tuple] | None = None       # native spacer palette
        self._regen: R.RegenResult | None = None
        self._engine_tiffs: list = []                   # engine-rendered pages
        self._page = 0                                  # previewed page index
        self._spacers: list = []                        # current-page Spacer list
        # Per-page spacer segmentation cache (page -> Spacer list). Filled
        # lazily on first visit to a page and reused on every later visit, so
        # flipping back and forth between pages doesn't re-run the (expensive)
        # twin-diff + segmentation each time. Cleared on every fresh regen.
        self._spacer_cache: dict[int, list] = {}
        self._sel_spacers: set[int] = set()             # current-page selection
        self._paint: dict[tuple[int, int], tuple] = {}  # (page, spacer idx) -> rgb
        self._preview_tmp = tempfile.TemporaryDirectory()
        self._worker: _RegenWorker | None = None
        self._preview_scale = 1.0
        self._preview_pending_save: Path | None = None
        self._swatch_size = _SWATCH                     # current grid icon size
        self._base_pixmap: QPixmap | None = None        # preview without overlay
        self._full_pixmap: QPixmap | None = None        # full-res render (pre-scale)
        self._options = R.LayoutOptions()               # printtarg layout knobs
        self._basename = "chart"                        # used for preview + save
        self._strips_per_page: list[int] = []           # PASSES_IN_STRIPS2 per page
        # Per-page {sample_id: (x0,y0,x1,y1)} pixel boxes, computed once
        # after each regen and used by the "highlight selected patches"
        # overlay + the preview's patch-click/marquee handlers.
        # Per-page patch geometry (sample-id → pixel bbox), computed lazily for
        # the visited page only and cached; cleared on each fresh render (#44).
        self._patch_geom_cache: dict[int, dict[int, tuple[int, int, int, int]]] = {}

        # Debounced auto-preview: fire 1.8s after the last edit.
        self._auto_timer = QTimer(self)
        self._auto_timer.setSingleShot(True)
        self._auto_timer.setInterval(1800)
        self._auto_timer.timeout.connect(
            lambda: self._regenerate(save_to=None) if self._spec else None
        )

        # Undo/redo history (in-memory only; see _UNDO_DEPTH). _undo_stack holds
        # _EditorSnapshots with the live state at _undo_index as its tail-or-
        # earlier entry; the baseline (index 0) is the chart as loaded/created.
        # _suppress_undo blocks capture while we ourselves repopulate the grid
        # (load / restore), so programmatic changes never land on the stack.
        self._undo_stack: list[_EditorSnapshot] = []
        self._undo_index: int = -1
        self._suppress_undo: bool = False
        # Capture is debounced so spinbox scrubbing or a multi-patch recolour
        # coalesce into one undo step rather than dozens.
        self._undo_timer = QTimer(self)
        self._undo_timer.setSingleShot(True)
        self._undo_timer.setInterval(500)
        self._undo_timer.timeout.connect(self._capture_undo)

        self._build_ui()
        self._refresh_enabled()
        self._refresh_engine_panel_visible()   # initial engine-vs-printtarg state

        # Pre-load the Create Chart tab's current chart, ready to edit (#45).
        # Deferred to the event loop so the window is shown first and the
        # initial preview render doesn't block the open. is_saved=True (set in
        # _load_chart_from) means a clean open — closing without edits won't warn.
        if self._initial_chart is not None and Path(self._initial_chart).is_file():
            QTimer.singleShot(0, lambda: self._load_chart_from(Path(self._initial_chart)))

    # -- UI -----------------------------------------------------------------
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        # Zero side margins so the spectrum stripe under the source row can run
        # edge-to-edge (full window width), like the masthead stripe. The three
        # real content rows re-add the 16 px side inset themselves.
        outer.setContentsMargins(0, 14, 0, 12)
        outer.setSpacing(10)

        # Source row
        src = QHBoxLayout()
        src.setContentsMargins(16, 0, 16, 0)
        # Tab-style heading at the far left, mirroring the main-window tab
        # headers (uppercase eyebrow + large serif title), in the editor's
        # magenta accent.
        src.addWidget(TabHeader(
            tr("CHART PATCH SET · EDITOR"), tr("Arrange and recolour your patches"),
            SPEC_MAGENTA, self), 0, Qt.AlignmentFlag.AlignVCenter)
        GradientOverlay(SPEC_MAGENTA, parent=self, alpha=15, height=95, on_top=False)
        src.addSpacing(16)
        load_btn = QPushButton(tr("Load patch set…"), self)
        load_btn.setToolTip(tr("Load a patch set from a .ti2 / .ti1 file."))
        load_btn.clicked.connect(self._load_ti2)
        new_btn = QPushButton(tr("New patch set…"), self)
        new_btn.clicked.connect(self._new_chart)
        src.addWidget(new_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        src.addWidget(load_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        src.addStretch(1)
        # Undo / redo, centred between the source buttons and the info readout.
        self._undo_btn = QPushButton(tr("↶ Undo"), self)
        self._undo_btn.setToolTip(with_shortcut(tr("Undo the last edit."), "undo"))
        self._undo_btn.clicked.connect(self._undo)
        self._redo_btn = QPushButton(tr("Redo ↷"), self)
        self._redo_btn.setToolTip(with_shortcut(tr("Redo the last undone edit."), "redo"))
        self._redo_btn.clicked.connect(self._redo)
        src.addWidget(self._undo_btn)
        src.addWidget(self._redo_btn)
        src.addStretch(1)
        # Give each pair of source-row buttons one uniform width sized to its
        # widest label plus padding, so the text never clips — macOS's Fusion
        # button metrics under-size the hint by a few px, which cut "New chart…"
        # on both sides (Knut). Derived from the rendered sizeHints, so it holds
        # in any language; uniform widths also line the buttons up neatly.
        _uniform_button_width((new_btn, load_btn), pad=24)
        _uniform_button_width((self._undo_btn, self._redo_btn), pad=18)
        # Ctrl+Z / Ctrl+Shift+Z (and Ctrl+Y) work anywhere in the dialog.
        QShortcut(QKeySequence.StandardKey.Undo, self, activated=self._undo)
        QShortcut(QKeySequence.StandardKey.Redo, self, activated=self._redo)
        QShortcut(QKeySequence("Ctrl+Y"), self, activated=self._redo)
        self._info = QLabel(tr("No chart loaded."), self)
        # A long chart name makes this readout's text long; with the default
        # Preferred policy its minimumSizeHint forced the whole source row wider
        # than the window, which clipped the New chart / Load .ti2 buttons.
        # Ignored horizontal policy lets the label shrink (clipping its own text)
        # so it can never dictate the row width — the buttons keep their natural
        # size. The full readout stays available as a tooltip (see _refresh_info).
        self._info.setSizePolicy(QSizePolicy.Policy.Ignored,
                                 QSizePolicy.Policy.Preferred)
        src.addWidget(self._info)
        src.addWidget(_magenta_tip(
            tr("Chart patch set editor"),
            tr("Welcome! This is where you build the PATCH SET for your chart — the "
            "collection of little colour squares (we call each one a \"patch\") that "
            "will be measured. You choose which colours are in the set, what order "
            "they're in, and you can recolour, add or remove them.\n\n"
            "The page LAYOUT — which instrument and paper, the strips, spacers, "
            "margins and sizing — is set over in the Create Chart tab. Here you only "
            "shape the patch set itself; when you apply it, Create Chart lays it out "
            "for you. That keeps layout in one place and this window simple.\n\n"
            "Don't worry — you can't break anything here. Nothing is printed or "
            "measured until you choose to.\n\n"
            "Two areas to know about:\n\n"
            "• The patch grid fills most of the window: every colour is a small "
            "square. This is your workbench — drag squares around to reorder them, "
            "click to select, and recolour or add and remove patches. The order you "
            "see here is the order they'll be measured in. Use the controls above "
            "the grid to show or hide the patch numbers and the gaps between "
            "swatches.\n\n"
            "• The controls on the right let you add or remove patches, generate "
            "whole colour sets, recolour a selection, and save.\n\n"
            "A typical session goes: load a patch set or start a new one, arrange "
            "and recolour the patches, then Apply / Save to send the set back to "
            "the Create Chart tab (or Save As to export it).\n\n"
            "One handy thing happens automatically: when you save, ChromIQ checks "
            "whether your colours are well mixed and, if they are, marks the set "
            "so your instrument may read each strip in either direction. You only "
            "have to get involved for tricky, structured sets — see the "
            "force-randomised-tag option in the controls for more."),
            self, min_width=560))
        outer.addLayout(src)

        # Full-width spectrum stripe — a visual separator between the source /
        # undo-redo controls and the editing area, mirroring the masthead.
        outer.addWidget(_SpectrumStripe(self))

        split = QSplitter(Qt.Orientation.Horizontal, self)

        # Left: swatch-size slider + patch grid
        left = QWidget(self)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(6)
        # Swatch chrome — the size slider, the show-number / show-gap toggles and
        # the patch-grid ⓘ. Built here but placed at the TOP of the RIGHT column
        # (below), so the Patches frame lines up with the top of the swatch grid
        # and the ⓘ sits in the right-most corner (Knut #93). Two compact rows so
        # it fits the narrow controls column. Widgets are parented to the dialog
        # so they reparent cleanly when the layout is added to the right column.
        self._swatch_chrome = QVBoxLayout()
        self._swatch_chrome.setContentsMargins(0, 0, 0, 0)
        self._swatch_chrome.setSpacing(4)
        _crow1 = QHBoxLayout()
        _crow1.setSpacing(8)
        _crow1.addWidget(QLabel(tr("Swatch size:"), self))
        self._size_slider = QSlider(Qt.Orientation.Horizontal, self)
        # Min lowered to 8 px so the whole patch set fits on screen at once (Knut).
        self._size_slider.setRange(8, 96)
        self._size_slider.setValue(_SWATCH)
        self._size_slider.valueChanged.connect(self._set_swatch_size)
        # Same recipe as the Gamut viewer's opacity / saturation sliders
        # (slim groove, filled sub-page, round handle) but with the magenta
        # accent so it harmonises with the rest of this dialog's accent.
        from ui.theme import resolve_mode
        _mode = resolve_mode(self._settings.get("appearance", "auto"))
        _groove = "#1c1b18" if _mode == "light" else "#333333"
        self._size_slider.setStyleSheet(
            f"QSlider::groove:horizontal {{ height: 4px; background: {_groove};"
            " border-radius: 2px; }"
            f"QSlider::handle:horizontal {{ background: {SPEC_MAGENTA};"
            " border: none; width: 12px; height: 12px; margin: -4px 0;"
            " border-radius: 6px; }"
            f"QSlider::sub-page:horizontal {{ background: {SPEC_MAGENTA};"
            " border-radius: 2px; }"
        )
        _crow1.addWidget(self._size_slider, 1)
        _crow1.addWidget(_magenta_tip(
            "Patch grid",
            "This is your main workspace. Every little square is one colour patch "
            "in your set, and the order you see — reading left to right, top to "
            "bottom — is exactly the order they'll be measured in.\n\n"
            "Here's everything you can do:\n\n"
            "• Move patches around. Just drag a square (or several at once) to a "
            "new spot — a magenta line shows where it will land when you let go. "
            "Prefer the keyboard? Select some patches and nudge them with Alt and "
            "the arrow keys, or press F to send them to the very front and L to the "
            "very end.\n\n"
            "• Pick patches. Click a square to select it, hold Shift or Ctrl to "
            "select more, or drag a box around several.\n\n"
            "• Change a colour. Select one or more patches, then use \"Set colour "
            "of selection…\" over in the Patches controls to give them a new "
            "colour.\n\n"
            "• Add or remove. The Patches controls also let you add fresh patches "
            "or delete the ones you've selected.\n\n"
            "The controls above adjust how the grid looks — the swatch size, and "
            "whether the patch numbers and the gaps between swatches are shown. "
            "None of that changes the printed chart; the page layout is set in the "
            "Create Chart tab.",
            self, min_width=520))
        self._swatch_chrome.addLayout(_crow1)
        # Show/hide the patch number under each swatch, and the gaps between them,
        # so the set can be viewed as a whole like in i1Profiler (Knut #93).
        _crow2 = QHBoxLayout()
        _crow2.setSpacing(12)
        # These two live in the swatch-grid chrome, outside the magenta-scoped
        # controls panel, so they'd fall back to the app-wide cyan indicator —
        # give them the editor's magenta accent to match the rest of the dialog.
        _cb_magenta = (
            f"QCheckBox::indicator:checked {{ background: {SPEC_MAGENTA};"
            f" border-color: {SPEC_MAGENTA}; }}"
            f"QCheckBox::indicator:hover {{ border-color: {SPEC_MAGENTA}; }}")
        self._show_numbers_check = QCheckBox(tr("Show patch number"), self)
        self._show_numbers_check.setChecked(True)
        self._show_numbers_check.setStyleSheet(_cb_magenta)
        self._show_numbers_check.toggled.connect(self._set_show_numbers)
        _crow2.addWidget(self._show_numbers_check)
        self._show_gap_check = QCheckBox(tr("Show gap between patches"), self)
        self._show_gap_check.setChecked(True)
        self._show_gap_check.setStyleSheet(_cb_magenta)
        self._show_gap_check.toggled.connect(self._set_show_gap)
        _crow2.addWidget(self._show_gap_check)
        _crow2.addStretch(1)
        self._swatch_chrome.addLayout(_crow2)
        # Gap size row: independent H / V, editable only while "Show gap between
        # patches" is on (Knut #93). 1–30 px, default 3 each. The unit ("px") is
        # in the row label so the spinboxes can stay narrow and not overflow /
        # overlap the row (Knut beta.38).
        from ui.widgets import NoScrollSpinBox as _NSpin
        _crow3 = QHBoxLayout()
        _crow3.setSpacing(6)
        self._gap_lbl = QLabel(tr("Gap (px):"), self)
        _crow3.addWidget(self._gap_lbl)
        self._gap_h_lbl = QLabel(tr("H"), self)
        _crow3.addWidget(self._gap_h_lbl)
        self._gap_h_spin = _NSpin(self)
        self._gap_h_spin.setRange(1, 30)
        self._gap_h_spin.setValue(3)
        self._gap_h_spin.setMinimumWidth(70)        # 2 digits + arrows, no suffix
        self._gap_h_spin.valueChanged.connect(self._set_gap_sizes)
        _crow3.addWidget(self._gap_h_spin)
        self._gap_v_lbl = QLabel(tr("V"), self)
        _crow3.addWidget(self._gap_v_lbl)
        self._gap_v_spin = _NSpin(self)
        self._gap_v_spin.setRange(1, 30)
        self._gap_v_spin.setValue(3)
        self._gap_v_spin.setMinimumWidth(70)
        self._gap_v_spin.valueChanged.connect(self._set_gap_sizes)
        _crow3.addWidget(self._gap_v_spin)
        _crow3.addStretch(1)
        self._swatch_chrome.addLayout(_crow3)
        # It isn't obvious the swatches can be rearranged, so spell it out right
        # above the grid (Knut's suggestion) where it's always visible — the full
        # story stays in the ⓘ. (Below the grid it gets squeezed by the list.)
        grid_hint = QLabel(
            tr("Tip: drag a swatch to move it. Shift- or {ext}-click to pick "
               "several, then drag — or use the First / Up / Down / Last buttons."
               ).format(ext=_mod_keys()["ext"]),
            left)
        grid_hint.setWordWrap(True)
        # palette(mid) was nearly invisible on the dark grid background; use an
        # explicit readable grey with a little breathing room.
        grid_hint.setStyleSheet(
            "color: #b0b0b0; font-size: 11px; font-style: italic; padding: 2px 0;")
        lv.addWidget(grid_hint, 0)

        self._grid = _ReorderListWidget(left)
        # ListMode + LeftToRight + Wrapping is the canonical Qt pattern for a
        # wrap-list reorder. The custom delegate puts the icon ABOVE the label
        # so the visual still looks IconMode-style.
        self._grid.setViewMode(QListWidget.ViewMode.ListMode)
        self._grid.setFlow(QListWidget.Flow.LeftToRight)
        self._grid.setWrapping(True)
        self._grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._grid.setMovement(QListWidget.Movement.Static)
        self._grid.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._grid.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._grid.setDragEnabled(True)
        self._grid.setAcceptDrops(True)
        # Built-in indicator hidden — _ReorderListWidget paints a mid-gap
        # magenta line in dragMoveEvent / paintEvent instead.
        self._grid.setDropIndicatorShown(False)
        self._grid.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._grid.setIconSize(QSize(_SWATCH, _SWATCH))
        self._grid.setSpacing(0)        # gap is the delegate's per-cell trailing margin
        # Drag-ghost icons follow the chart's colorspace (N-tuple aware, #72).
        self._grid.display_rgb = self._display_rgb
        self._delegate = _SwatchDelegate(self._grid, _SWATCH)
        self._grid.setItemDelegate(self._delegate)
        self._grid.setGridSize(self._delegate.sizeHint(None, None))
        # Qt's default InternalMove reorder may emit either rowsMoved (when
        # the model implements moveRows) or rowsRemoved/rowsInserted (the
        # remove-then-insert fallback path). Connect to both so the drag is
        # always picked up. _schedule_auto_refresh is debounced, so double
        # firing during a single drop is harmless.
        def _after_drag(*_a):
            self._renumber()
            self._schedule_auto_refresh()
        self._grid.model().rowsMoved.connect(_after_drag)
        self._grid.model().rowsRemoved.connect(_after_drag)
        # Re-render the preview overlay when the grid selection changes —
        # only matters when "Highlight selected in preview" is on, but the
        # connection is harmless either way (_refresh_preview no-ops if the
        # toggle is off).
        self._grid.itemSelectionChanged.connect(self._on_grid_selection_changed)
        # Keyboard reorder for the selection. Alt + arrows nudge / jump,
        # plain F/L jump to first/last (mnemonic for "front" / "last").
        for keys, fn in (
            (("Alt+Up", "Alt+Left"),    self._move_up),
            (("Alt+Down", "Alt+Right"), self._move_down),
            (("Alt+Home", "F"),         self._move_front),
            (("Alt+End",  "L"),         self._move_back),
        ):
            for k in keys:
                QShortcut(QKeySequence(k), self._grid, activated=fn)
        lv.addWidget(self._grid, 1)
        # Total patch count, right under the grid — so you can read it at a glance
        # without turning on patch numbers and shrinking the swatches to find the
        # last one (Knut). Updated from the live grid on every change.
        self._grid_count_lbl = QLabel("", left)
        self._grid_count_lbl.setStyleSheet(
            "color: #b0b0b0; font-size: 11px; padding: 2px 2px;")
        self._grid_count_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        lv.addWidget(self._grid_count_lbl, 0)
        # Status / info line sits under the patch grid (left column only), not
        # spanning the whole window. Auto-hides a few seconds after each message.
        self._status = _AutoHideLabel(left)
        self._status.setStyleSheet("color: #888;")
        # The status line moves to a full-width row UNDER the body (added after
        # the body, below) so the swatch grid fills the left column to its bottom
        # edge — letting the right column's action buttons line up with the bottom
        # of the swatch grid (Knut #93).
        split.addWidget(left)

        # Middle: preview + page navigation
        mid = QWidget(self)
        midv = QVBoxLayout(mid)
        midv.setContentsMargins(0, 0, 0, 0)
        midv.setSpacing(6)
        self._preview = _PreviewLabel(self)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setText(tr("Preview will appear here."))
        self._preview.clicked.connect(self._on_preview_click)
        self._preview.marquee_finished.connect(self._on_marquee)
        # Re-scale the preview from the full-res cache when the label resizes,
        # so the displayed image stays sharp at any pane width.
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(120)
        self._resize_timer.timeout.connect(self._rescale_preview)
        self._preview.resized.connect(self._resize_timer.start)
        # Plain layout (no QScrollArea): the canvas-with-white-border
        # pattern in _rescale_preview already paints the visible chart on a
        # white background. We give the label a small minimum size so it
        # always shows the border even with no chart loaded.
        self._preview.setMinimumSize(200, 200)
        self._preview.setSizePolicy(
            self._preview.sizePolicy().Policy.Expanding,
            self._preview.sizePolicy().Policy.Expanding,
        )
        midv.addWidget(self._preview, 1)
        self._page_bar = QWidget(mid)
        pbl = QHBoxLayout(self._page_bar)
        pbl.setContentsMargins(0, 0, 0, 0)
        self._prev_btn = QPushButton(tr("◀ Page"), self._page_bar)
        self._next_btn = QPushButton(tr("Page ▶"), self._page_bar)
        self._page_label = QLabel("", self._page_bar)
        self._prev_btn.clicked.connect(lambda: self._show_page(self._page - 1))
        self._next_btn.clicked.connect(lambda: self._show_page(self._page + 1))
        pbl.addStretch(1)
        pbl.addWidget(self._prev_btn)
        pbl.addWidget(self._page_label)
        pbl.addWidget(self._next_btn)
        pbl.addStretch(1)
        self._page_bar.setVisible(False)
        midv.addWidget(self._page_bar)
        # The middle layout preview is GONE from the editor (Knut #93): layout is
        # done in Create Chart, so the editor is a pure patch-set tool and the
        # swatch grid fills the whole left/middle area. `mid` + self._preview are
        # still constructed (kept off-screen) so the chart still renders for
        # save/apply and the many methods that reference the preview keep working.
        mid.setParent(self)
        mid.setVisible(False)
        split.setStretchFactor(0, 1)

        # Right: controls — OUTSIDE the splitter so it sits flush at the right
        # edge with no jumpy "phantom" pane between it and the window border.
        # The controls panel is wrapped in a scroll area so a stack of
        # printtarg knobs + Patches/Spacers + What-a-mess + actions never
        # falls off the bottom on smaller window heights. _FadeScroll paints
        # a top/bottom fade so the user can tell content continues above /
        # below the visible band.
        body = QHBoxLayout()
        # 16 px side inset (outer layout now has zero side margins so the
        # spectrum stripe can be full-bleed).
        body.setContentsMargins(16, 0, 16, 0)
        body.setSpacing(8)
        body.addWidget(split, 1)
        controls = self._build_controls()
        ctrl_scroll = FadeScrollArea(self, surface="dialog")
        from ui.theme import resolve_mode
        ctrl_scroll.set_appearance(
            resolve_mode(self._settings.get("appearance", "auto")))
        ctrl_scroll.setWidget(controls)
        ctrl_scroll.setWidgetResizable(True)
        ctrl_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        ctrl_scroll.setFrameShape(QFrame.Shape.NoFrame)
        ctrl_scroll.setStyleSheet(
            "QScrollArea { background: transparent; }"
            " QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        # Right side: scrollable controls on top, fixed action footer below.
        # Only the controls scroll; "Update preview / Export / Save As" stay
        # pinned so they're always reachable on short windows.
        right = QWidget(self)
        # Match the panel's fixed width (+ scrollbar gutter) so the column
        # sits flush at the window edge without overflow. Stored so the engine
        # panel (wider than the printtarg knobs) can widen the whole column,
        # not just the inner panel — otherwise the scroll area stays narrow and
        # the engine panel scrolls horizontally (#93).
        self._right_pane = right
        right.setFixedWidth(controls.width() + 4)   # tight scrollbar gutter (symmetric margins)
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(6)
        # Swatch chrome (size slider + toggles + ⓘ) sits at the TOP of the right
        # column so the Patches frame below it lines up with the top of the swatch
        # grid and the ⓘ is in the right-most corner (Knut #93).
        rv.addLayout(self._swatch_chrome, 0)
        rv.addWidget(ctrl_scroll, 1)
        rv.addWidget(self._build_action_bar(right), 0)
        body.addWidget(right, 0)
        outer.addLayout(body, 1)
        # Full-width status line under the body (moved out of the left column so the
        # swatch grid reaches the bottom edge — see split.addWidget(left)).
        outer.addWidget(self._status)

    def _build_controls(self) -> QWidget:
        panel = QWidget(self)
        # Widened so the printtarg paper combo ("A4 (210 × 297 mm)
        # Portrait") and the per-locale spinboxes don't clip on first
        # open. Bump beyond 320 also gives custom-paper W/H spinboxes
        # room to breathe.
        panel.setFixedWidth(360)
        self._controls_panel = panel
        # Container stylesheet — the only reliable way to shrink button
        # height ([[feedback_qt_button_sizing]]: setMinimumHeight on the
        # button itself is overridden by Qt's compound-widget CSS). Magenta
        # accents on checked/focused state to match the dialog's magenta
        # drop-indicator + "What a mess!" bang, scoped to the dialog so
        # the app-wide cyan accent isn't touched.
        panel.setStyleSheet(f"""
            QPushButton {{ padding: 4px 8px; min-height: 26px; font-size: 11px; }}
            QGroupBox  {{ font-size: 12px; }}
            QLabel     {{ font-size: 11px; }}
            QRadioButton {{ font-size: 12px; }}
            QCheckBox  {{ font-size: 11px; }}
            QCheckBox::indicator:checked {{
                background: {SPEC_MAGENTA}; border-color: {SPEC_MAGENTA};
            }}
            QCheckBox::indicator:hover {{ border-color: {SPEC_MAGENTA}; }}
            /* This dialog sets its own stylesheet, which drops the app-wide
               round radio geometry — so re-declare the base indicator round
               (border-radius = half ⇒ circle), else a checked radio draws as a
               magenta square. Checkboxes keep their square tick. Explicit
               per-theme colours, not palette(mid): see _unchecked_indicator_css. */
            QRadioButton::indicator {{
                width: 14px; height: 14px;
                {_unchecked_indicator_css(self._settings)}
                border-radius: 8px;
            }}
            QRadioButton::indicator:checked {{
                background: {SPEC_MAGENTA}; border-color: {SPEC_MAGENTA};
            }}
            /* A ticked-but-disabled box must read as off — without this the
               magenta :checked fill wins over Qt's disabled greying, so an
               unselected panel (e.g. "Generate colour sets") still showed bright
               ticks. The two-state selector outranks the single :checked rule. */
            QCheckBox::indicator:checked:disabled {{
                background: #4a4a4a; border-color: #4a4a4a;
            }}
            QRadioButton::indicator:checked:disabled {{
                background: #4a4a4a; border-color: #4a4a4a; border-radius: 8px;
            }}
            QLineEdit:focus, QComboBox:focus,
            QSpinBox:focus, QDoubleSpinBox:focus {{
                border-color: {SPEC_MAGENTA};
            }}
        """ + combo_popup_qss(SPEC_MAGENTA))
        # The dropdown's hovered row defaulted to the app-wide cyan. It needs
        # BOTH of combo_popup_qss's rules: a `selection-background-color` alone
        # (all this used to set) leaves the native menu-drawn popup rendering
        # exactly as before while the view's palette reports the new colour —
        # measured on screen, in both themes.
        v = QVBoxLayout(panel)
        v.setContentsMargins(4, 0, 0, 0)
        v.setSpacing(8)

        # Target mode
        mode_box = QGroupBox(tr("Edit chart"), panel)
        mb = QVBoxLayout(mode_box)
        self._mode_patches = QRadioButton(tr("Patches"), mode_box)
        self._mode_spacers = QRadioButton(tr("Spacers"), mode_box)
        self._mode_patches.setChecked(True)
        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self._mode_patches)
        self._mode_group.addButton(self._mode_spacers)
        self._mode_patches.toggled.connect(self._on_mode_change)
        mb.addWidget(self._mode_patches)
        mb.addWidget(self._mode_spacers)
        # The Patches/Spacers mode frame is removed from the editor (Knut #93):
        # with layout done in Create Chart there are no editor spacers to edit, so
        # the editor is always in patches mode. Kept constructed (hidden) so the
        # patches-mode logic that reads these radios keeps working.
        mode_box.setVisible(False)

        # printtarg options — all the knobs the New chart dialog exposes,
        # editable on an already-loaded chart. Mirrors LayoutOptions; each
        # widget pushes back to self._options + schedules an auto-preview.
        pt_box = QGroupBox(tr("printtarg"), panel)
        ptg = QGridLayout(pt_box)
        ptg.setHorizontalSpacing(4)
        ptg.setVerticalSpacing(4)
        # Instrument + Paper rows — affect ChartSpec, not LayoutOptions
        # (printtarg reads them as -i / -p), but they live here so the
        # editor has the same coverage as the New chart dialog.
        ptg.addWidget(QLabel(tr("Instrument:")), 0, 0)
        self._pt_instr = NoScrollComboBox(pt_box)
        for code, label in _INSTRUMENTS:
            self._pt_instr.addItem(label, code)
        self._pt_instr.currentIndexChanged.connect(self._on_pt_instr_changed)
        ptg.addWidget(self._pt_instr, 0, 1, 1, 3)
        ptg.addWidget(QLabel(tr("Paper:")), 1, 0)
        # Vertical container: paper combo on top, custom W/H row below
        # (hidden unless "Custom" is the selection). Keeps the rest of
        # the grid's row indices untouched.
        paper_container = QWidget(pt_box)
        paper_v = QVBoxLayout(paper_container)
        paper_v.setContentsMargins(0, 0, 0, 0)
        paper_v.setSpacing(4)
        self._pt_paper = NoScrollComboBox(paper_container)
        for code in _PAPER_ORDER:
            self._pt_paper.addItem(
                _PAPER_LABELS_WITH_CUSTOM.get(code, code), code)
        self._pt_paper.currentIndexChanged.connect(self._on_pt_paper_changed)
        paper_v.addWidget(self._pt_paper)
        self._pt_paper_custom_row = QWidget(paper_container)
        cust_l = QHBoxLayout(self._pt_paper_custom_row)
        cust_l.setContentsMargins(0, 0, 0, 0)
        cust_l.setSpacing(6)
        cust_l.addWidget(QLabel(tr("W (mm):")))
        self._pt_paper_w = NoScrollSpinBox(self._pt_paper_custom_row)
        self._pt_paper_w.setRange(10, 9999)
        self._pt_paper_w.setValue(210)
        self._pt_paper_w.setMinimumWidth(76)
        cust_l.addWidget(self._pt_paper_w)
        cust_l.addWidget(QLabel(tr("H (mm):")))
        self._pt_paper_h = NoScrollSpinBox(self._pt_paper_custom_row)
        self._pt_paper_h.setRange(10, 9999)
        self._pt_paper_h.setValue(297)
        self._pt_paper_h.setMinimumWidth(76)
        cust_l.addWidget(self._pt_paper_h)
        cust_l.addStretch(1)
        self._pt_paper_w.valueChanged.connect(self._on_pt_paper_custom_changed)
        self._pt_paper_h.valueChanged.connect(self._on_pt_paper_custom_changed)
        _as_compact(self._pt_paper_w, self._pt_paper_h)
        self._pt_paper_custom_row.setVisible(False)
        paper_v.addWidget(self._pt_paper_custom_row)
        ptg.addWidget(paper_container, 1, 1, 1, 3)
        _as_compact(self._pt_instr, self._pt_paper)
        # Spacers row — checkboxes wired as a mutex group, with the
        # all-off state permitted (printtarg's default = coloured, so an
        # all-off picker just falls back to that). Picking "None" also
        # disables the Spacer -A field since there are no spacers to
        # scale.
        ptg.addWidget(QLabel(tr("Spacers:")), 2, 0)
        sp_row = QHBoxLayout()
        sp_row.setSpacing(6)
        self._pt_sp_col  = QCheckBox(tr("Coloured"), pt_box)
        self._pt_sp_bw   = QCheckBox(tr("B&&W"), pt_box)
        self._pt_sp_none = QCheckBox(tr("None"), pt_box)
        self._pt_sp_col.setChecked(True)
        _wire_spacer_mutex(
            (self._pt_sp_col, self._pt_sp_bw, self._pt_sp_none)
        )
        for cb in (self._pt_sp_col, self._pt_sp_bw, self._pt_sp_none):
            cb.toggled.connect(self._on_printtarg_changed)
            sp_row.addWidget(cb)
        sp_row.addStretch(1)
        ptg.addLayout(sp_row, 2, 1, 1, 3)
        # Scales row. Min-width on every spinbox so 3-digit / decimal
        # values don't truncate to "30" / "1.0" inside the panel.
        SPIN_W = 76
        ptg.addWidget(QLabel(tr("Patch -a:")), 3, 0)
        self._pt_a = NoScrollDoubleSpinBox(pt_box)
        self._pt_a.setRange(0.3, 3.0)
        self._pt_a.setSingleStep(0.05)
        self._pt_a.setValue(1.0)
        self._pt_a.setMinimumWidth(SPIN_W)
        self._pt_a.valueChanged.connect(self._on_printtarg_changed)
        ptg.addWidget(self._pt_a, 3, 1)
        ptg.addWidget(QLabel(tr("Spacer -A:")), 3, 2)
        self._pt_A = NoScrollDoubleSpinBox(pt_box)
        self._pt_A.setRange(0.3, 3.0)
        self._pt_A.setSingleStep(0.05)
        self._pt_A.setValue(1.0)
        self._pt_A.setMinimumWidth(SPIN_W)
        self._pt_A.valueChanged.connect(self._on_printtarg_changed)
        ptg.addWidget(self._pt_A, 3, 3)
        # Margin + DPI row
        ptg.addWidget(QLabel(tr("Margin (mm):")), 4, 0)
        self._pt_m = NoScrollSpinBox(pt_box)
        self._pt_m.setRange(0, 50)
        self._pt_m.setValue(6)
        self._pt_m.setMinimumWidth(SPIN_W)
        self._pt_m.valueChanged.connect(self._on_printtarg_changed)
        ptg.addWidget(self._pt_m, 4, 1)
        ptg.addWidget(QLabel(tr("DPI:")), 4, 2)
        self._pt_dpi = NoScrollSpinBox(pt_box)
        self._pt_dpi.setRange(72, 1200)
        self._pt_dpi.setSingleStep(50)
        self._pt_dpi.setValue(300)
        self._pt_dpi.setMinimumWidth(SPIN_W)
        self._pt_dpi.valueChanged.connect(self._on_printtarg_changed)
        ptg.addWidget(self._pt_dpi, 4, 3)
        _as_compact(self._pt_a, self._pt_A, self._pt_m, self._pt_dpi)
        # Bit depth row
        ptg.addWidget(QLabel(tr("Bit depth:")), 5, 0)
        bd_row = QHBoxLayout()
        self._pt_bd8  = QRadioButton(tr("8-bit"), pt_box)
        self._pt_bd16 = QRadioButton(tr("16-bit"), pt_box)
        self._pt_bd8.setChecked(True)
        bd_grp = QButtonGroup(pt_box)
        bd_grp.addButton(self._pt_bd8)
        bd_grp.addButton(self._pt_bd16)
        self._pt_bd8.toggled.connect(self._on_printtarg_changed)
        self._pt_bd16.toggled.connect(self._on_printtarg_changed)
        bd_row.addWidget(self._pt_bd8)
        bd_row.addWidget(self._pt_bd16)
        bd_row.addStretch(1)
        ptg.addLayout(bd_row, 5, 1, 1, 3)
        # Instrument-conditional checkboxes (visibility flipped from
        # self._spec.instrument_flag in _sync_printtarg_widgets).
        self._pt_L = QCheckBox(tr("Suppress left clip border (-L)"), pt_box)
        self._pt_L.setToolTip(tr("i1Pro / 3+ only. Frees the strip for patches."))
        self._pt_L.toggled.connect(self._on_printtarg_changed)
        self._pt_P = QCheckBox(tr("Don't limit strip length (-P)"), pt_box)
        self._pt_P.setToolTip(tr("i1Pro / 3+ only. Lets a long strip span "
                              "multiple strokes."))
        self._pt_P.toggled.connect(self._on_printtarg_changed)
        self._pt_dd = QCheckBox(tr("Double density (-h)"), pt_box)
        self._pt_dd.setToolTip(tr("ColorMunki only. Tighter strip layout for "
                               "the ColorMunki rig. Mutually exclusive "
                               "with Triple."))
        self._pt_dd.toggled.connect(self._on_dd_toggled)
        self._pt_td = QCheckBox(tr("Triple density (i1Pro layout)"), pt_box)
        self._pt_td.setToolTip(
            tr("ColorMunki + rig only. Renders with the i1Pro strip layout at "
            "scale 1.3 / margin 5 / strip-limit off / left-border suppressed, "
            "then patches TARGET_INSTRUMENT back to ColorMunki so chartread "
            "still drives your meter. Mutually exclusive with Double."))
        self._pt_td.toggled.connect(self._on_td_toggled)
        self._pt_force_tag = QCheckBox(tr("Force “randomised” tag"), pt_box)
        self._pt_force_tag.setChecked(bool(
            self._settings.get("ti2_editor_force_tag", False)))
        self._pt_force_tag.setEnabled(False)   # enabled only on an unsafe layout
        self._pt_force_tag.setToolTip(
            tr("Only needed for risky layouts (click the ⓘ for details). Charts that "
            "are already well mixed get tagged as randomised automatically."))
        self._pt_force_tag.toggled.connect(self._on_force_tag_toggled)
        ptg.addWidget(self._pt_L,  6, 0, 1, 4)
        ptg.addWidget(self._pt_P,  7, 0, 1, 4)
        ptg.addWidget(self._pt_dd, 8, 0, 1, 4)
        ptg.addWidget(self._pt_td, 9, 0, 1, 4)
        tag_row = QHBoxLayout()
        tag_row.setContentsMargins(0, 0, 0, 0)
        tag_row.addWidget(self._pt_force_tag)
        tag_row.addStretch(1)
        tag_row.addWidget(_magenta_tip(
            "Force “randomised” tag",
            "Good news first: you usually don't need to touch this. It stays "
            "greyed-out and only wakes up when a chart needs your attention.\n\n"
            "Here's the background. When you measure a chart, you slide your "
            "instrument along each row of patches (a row is called a \"strip\"). "
            "Many instruments can read a strip in either direction — but only when "
            "the chart is marked as having its colours in a shuffled order. So when "
            "you save, ChromIQ takes a quick look at your layout:\n\n"
            "• If the colours are nicely mixed up, it adds that \"randomised\" mark "
            "for you automatically. Nothing to do — bidirectional measuring just "
            "works, and this checkbox stays greyed-out.\n\n"
            "• If the colours sit in a tidy pattern instead — a smooth fade from "
            "light to dark, or a neat colour grid, especially on a big chart — then "
            "neighbouring strips look too alike. Marking such a chart as randomised "
            "is risky: your instrument can mix the strips up and quietly record the "
            "wrong readings, giving you a profile with colour casts and no obvious "
            "warning. So ChromIQ does NOT mark it automatically, and instead "
            "switches this checkbox on so the choice is yours.\n\n"
            "Ticking it then says \"I understand the risk — mark it as randomised "
            "anyway.\" That's only sensible if you happen to know the order is "
            "genuinely fine, or you'd rather re-shuffle the chart. Either way, "
            "nothing on the printed page moves — only a note inside the file "
            "changes.\n\n"
            "If you're unsure, leave it unticked and the chart is simply measured "
            "in one direction, which is always safe.",
            pt_box, min_width=560))
        ptg.addLayout(tag_row, 10, 0, 1, 4)
        # NOTE: pt_box is added to the panel layout *after* the Patches and
        # Spacers boxes below, so the on-paper order is Patches → Spacers →
        # printtarg (the chart-content controls users edit most often stay
        # at the top; printtarg's render knobs are set-once-then-forget).
        self._pt_box = pt_box

        # Patch controls
        self._patch_box = QGroupBox(tr("Patches"), panel)
        pb = QVBoxLayout(self._patch_box)
        self._hl_patches = QCheckBox(
            tr("Highlight selected in preview"), self._patch_box)
        self._hl_patches.setToolTip(
            tr("Two-way link between the swatch grid and the preview:\n"
            "• selecting patches on the left highlights them in the preview\n"
            "• clicking or marquee-dragging on the preview selects them on "
            "the left"))
        self._hl_patches.toggled.connect(self._on_patch_highlight_toggled)
        # "Highlight selected in preview" is gone — there's no preview to
        # highlight into now (Knut #93). Kept unchecked + hidden so the highlight
        # branches that read it simply stay off.
        self._hl_patches.setChecked(False)
        self._hl_patches.setVisible(False)
        set_col = QPushButton(tr("Set colour of selection…"), self._patch_box)
        set_col.clicked.connect(self._set_patch_colour)
        pb.addWidget(set_col)
        tone_row = QHBoxLayout()
        dark = QPushButton(tr("Darken 10%"), self._patch_box)
        light = QPushButton(tr("Lighten 10%"), self._patch_box)
        dark.clicked.connect(lambda: self._transform_selection(0.9))
        light.clicked.connect(lambda: self._transform_selection(1.0 / 0.9))
        tone_row.addWidget(dark)
        tone_row.addWidget(light)
        pb.addLayout(tone_row)
        addrem = QHBoxLayout()
        add_b = QPushButton(tr("Add…"), self._patch_box)
        add_b.setToolTip(tr("Add a single chosen colour, or generate colour "
                            "sets (3D cube, skin tones, blues, greens, …) and "
                            "add them to the chart"))
        add_b.clicked.connect(self._add_patch)
        rem_b = QPushButton(tr("Remove"), self._patch_box)
        rem_b.setToolTip(tr("Remove the selected patches"))
        rem_b.clicked.connect(self._remove_selected_patches)
        addrem.addWidget(add_b)
        addrem.addWidget(rem_b)
        pb.addLayout(addrem)
        combine = QHBoxLayout()
        view3d_b = QPushButton(tr("3D distribution…"), self._patch_box)
        view3d_b.setToolTip(
            tr("Show the patch set as a rotatable 3D RGB cube so you can see how "
            "evenly the colours cover the gamut and where they bunch up."))
        view3d_b.clicked.connect(self._show_3d_distribution)
        combine.addWidget(view3d_b)
        pb.addLayout(combine)
        reorder_lbl = QLabel(
            tr("Reorder (drag, Alt+arrows, F/L, or):"), self._patch_box)
        reorder_lbl.setWordWrap(True)
        pb.addWidget(reorder_lbl)
        order = QGridLayout()
        order.setHorizontalSpacing(6)
        order.setVerticalSpacing(4)
        # 2×2 grid — "FRONT/UP/DOWN/BACK" in caps doesn't fit a 4-wide row at
        # 230 px panel width, so split into two rows of two.
        btns = ((tr("First"), self._move_front, 0, 0), (tr("Up"),   self._move_up,    0, 1),
                (tr("Last"),  self._move_back,  1, 0), (tr("Down"), self._move_down,  1, 1))
        for label, fn, r, c in btns:
            b = QPushButton(label, self._patch_box)
            b.clicked.connect(fn)
            order.addWidget(b, r, c)
        pb.addLayout(order)
        v.addWidget(self._patch_box)

        # Spacer controls
        self._spacer_box = QGroupBox(tr("Spacers"), panel)
        sb = QVBoxLayout(self._spacer_box)
        pal_lbl = QLabel(
            tr("Spacer palette — the colours printtarg can put in the gaps "
            "between strips (it auto-picks the best-contrast one for each gap). "
            "Click a swatch to change a palette colour:"),
            self._spacer_box)
        pal_lbl.setWordWrap(True)
        sb.addWidget(pal_lbl)
        self._palette_row = QHBoxLayout()
        sb.addLayout(self._palette_row)
        sb.addSpacing(10)
        reset = QPushButton(tr("Reset palette"), self._spacer_box)
        reset.setToolTip(tr("Reset the spacer palette to printtarg's defaults"))
        reset.clicked.connect(self._reset_palette)
        sb.addWidget(reset)
        sb.addWidget(self._hline())
        paint_lbl = QLabel(
            tr("Recolour individual spacers (overrides the palette for those "
            "gaps): on the page preview in the centre, click a spacer to "
            "select it, or drag a box to select several. {add} adds to the "
            "selection, {remove} removes. Selected spacers get a magenta outline "
            "— then click “Paint…”.").format(**{k: _mod_keys()[k]
                                                 for k in ("add", "remove")}),
            self._spacer_box)
        paint_lbl.setWordWrap(True)
        sb.addWidget(paint_lbl)
        paint_row = QHBoxLayout()
        paint = QPushButton(tr("Paint…"), self._spacer_box)
        paint.setToolTip(tr("Recolour the spacers you selected on the page "
                            "preview in the centre."))
        paint.clicked.connect(self._paint_spacers)
        clear = QPushButton(tr("Clear"), self._spacer_box)
        clear.setToolTip(tr("Clear the spacer selection"))
        clear.clicked.connect(self._clear_spacer_selection)
        paint_row.addWidget(paint)
        paint_row.addWidget(clear)
        sb.addLayout(paint_row)
        self._spacer_box.setVisible(False)
        v.addWidget(self._spacer_box)

        # printtarg knobs section sits below Patches + Spacers — it's
        # always visible (the chart's printtarg config applies regardless
        # of the "Patches / Spacers" target mode above).
        v.addWidget(self._pt_box)

        # ChromIQ layout engine: the full engine layout panel, shown in place of
        # the printtarg knobs when the chart was built by the engine (or the
        # engine is active). Seeded from the chart's recipe on load (#93).
        from ui.dialogs.layout_options_panel import LayoutOptionsPanel
        self._engine_panel = LayoutOptionsPanel(
            panel, with_selectors=True, with_calibration=True)
        self._engine_panel.changed.connect(self._engine_preview_timer.start)
        # Live "Pages": editing it fills patches (via the generator) up to that
        # many full pages, so the new page isn't left empty (#93, Knut).
        if self._engine_panel.pages is not None:
            self._engine_panel.pages.valueChanged.connect(
                self._on_engine_pages_changed)
        self._engine_panel_grp = QGroupBox(tr("ChromIQ layout"), panel)
        _eg = QVBoxLayout(self._engine_panel_grp)
        _eg.setContentsMargins(8, 8, 8, 8)
        _eg.addWidget(self._engine_panel)
        v.addWidget(self._engine_panel_grp)
        self._engine_panel_grp.setVisible(False)

        # Actions
        v.addStretch(1)

        # "What a mess!" flourish — same recipe as tab_print.py's "Feed the
        # beast" block (no-title groupbox, Georgia headline with amber italic
        # bang, Menlo subtext, 5-colour bar).
        mess_box = QGroupBox(panel)
        mess_box.setStyleSheet(
            "QGroupBox { margin-top: 0px; padding: 12px 6px 10px 6px; }"
        )
        ml = QVBoxLayout(mess_box)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(4)
        mess_head = QLabel(
            tr("What a mess<span style=\"color: {SPEC_MAGENTA}; font-style: italic;\">!</span>").format(SPEC_MAGENTA=SPEC_MAGENTA),
            mess_box,
        )
        mess_head.setTextFormat(Qt.TextFormat.RichText)
        mess_head.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mess_head.setStyleSheet(
            "background: transparent;"
            " font-family: Georgia; font-size: 22px;"
        )
        ml.addWidget(mess_head)
        mess_sub = QLabel(tr("Time to tidy up."), mess_box)
        mess_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mess_sub.setStyleSheet(
            "color: #808080; background: transparent;"
            " font-family: Menlo; font-size: 9px; font-weight: 300;"
        )
        ml.addWidget(mess_sub)
        mess_bar = QHBoxLayout()
        mess_bar.setContentsMargins(0, 6, 0, 0)
        mess_bar.setSpacing(0)
        mess_bar.addStretch()
        for _color in TAB_COLORS:
            seg = QFrame(mess_box)
            seg.setFixedSize(22, 2)
            seg.setStyleSheet(f"background-color: {_color}; border: none;")
            mess_bar.addWidget(seg)
        mess_bar.addStretch()
        ml.addLayout(mess_bar)
        v.addWidget(mess_box)

        # NOTE: the action buttons (Update preview / Export / Save As) used to
        # live here at the bottom of the scrollable panel, which meant they
        # scrolled off-screen on short windows. They now sit in a fixed
        # footer built by _build_action_bar() and pinned below the scroll
        # area in _build_ui(), so they're always reachable.
        return panel

    def _build_action_bar(self, parent: QWidget) -> QWidget:
        """The always-visible action footer (Update preview / Export / Save).

        Built outside the scroll area so these primary actions never scroll
        out of view. Carries the same compact-button stylesheet the controls
        panel uses (per [[feedback_qt_button_sizing]] a container stylesheet is
        the reliable way to shrink button height)."""
        bar = QWidget(parent)
        bar.setStyleSheet(
            "QPushButton { padding: 4px 8px; min-height: 26px; font-size: 11px; }"
        )
        bv = QVBoxLayout(bar)
        bv.setContentsMargins(4, 4, 0, 0)
        bv.setSpacing(8)
        # "Update preview" shares its row with "Shuffle" — each takes half the
        # width so the preview button is a little smaller and the randomiser
        # sits right beside it.
        # "Update preview" and "Shuffle" are gone from the editor (Knut #93): there
        # is no preview to update, and randomisation is handled in the Create Chart
        # Manual tab. Kept constructed (hidden) so the busy/enable plumbing that
        # references them keeps working.
        self._preview_btn = QPushButton(tr("Update preview"), bar)
        self._preview_btn.clicked.connect(lambda: self._regenerate(save_to=None))
        self._preview_btn.setVisible(False)
        self._shuffle_btn = QPushButton(tr("Shuffle"), bar)
        self._shuffle_btn.clicked.connect(self._randomise_patches)
        self._shuffle_btn.setVisible(False)
        save_row = QHBoxLayout()
        save_row.setSpacing(6)
        # "Apply / Save" is the headline action (#70, Knut). It opens a small
        # window offering to *overwrite* the chart currently loaded in the Create
        # Chart tab with this layout, or to *Save As* (export the full deliverable
        # to a folder you pick) — folding the old standalone "Save As" button in.
        # ".replace" doubles the ampersand so Qt shows a literal "&" instead of
        # eating it as a mnemonic; the tr() key stays plain (translations carry a
        # single "&"). Styled in the scheme's magenta to mark it the lead action.
        self._apply_btn = QPushButton(tr("Apply / Save…").replace("&", "&&"), bar)
        self._apply_btn.setStyleSheet(
            f"QPushButton {{ background: {SPEC_MAGENTA}; color: white; "
            f"border: none; border-radius: 4px; padding: 4px 10px; "
            f"min-height: 26px; font-size: 11px; font-weight: 600; }}"
            f"QPushButton:hover {{ background: #ff6690; }}"
            f"QPushButton:disabled {{ background: #4a4a4a; color: #9a9a9a; }}"
        )
        self._apply_btn.setToolTip(
            tr("Overwrite sends this patch set to the Create Chart tab, which "
            "lays it out with the page layout set there (not the one shown "
            "here) — or Save As exports the full chart, this layout included, "
            "to a folder you pick without leaving the editor."))
        self._apply_btn.clicked.connect(self._save_and_apply)
        self._close_btn = QPushButton(tr("Close"), bar)
        self._close_btn.setToolTip(
            tr("Close the editor without saving. If the layout has unsaved "
            "changes you'll be asked to confirm first; “Apply / Save…” "
            "keeps your work."))
        self._close_btn.clicked.connect(self._on_close_clicked)
        # Both buttons share the column width equally so Close doesn't spill past
        # the controls' right edge (Knut #93).
        for _b in (self._apply_btn, self._close_btn):
            _b.setSizePolicy(QSizePolicy.Policy.Expanding,
                             _b.sizePolicy().verticalPolicy())
        save_row.addWidget(self._apply_btn, 1)
        save_row.addWidget(self._close_btn, 1)
        bv.addLayout(save_row)
        return bar

    def _pick_color(self, initial: QColor, title: str) -> QColor:
        """Use Qt's non-native colour dialog so the HTML/hex field, RGB / HSV
        spinners and the basic-colour swatches are all available (the macOS
        native picker hides the hex field on older systems)."""
        return QColorDialog.getColor(
            initial, self, title,
            QColorDialog.ColorDialogOption.DontUseNativeDialog,
        )

    @staticmethod
    def _hline() -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setFrameShadow(QFrame.Shadow.Sunken)
        return f

    # -- source -------------------------------------------------------------
    def _refresh_engine_panel_visible(self) -> None:
        """Show the engine layout panel when the chart was built by the engine
        (or the engine is active), hiding the printtarg layout group.

        The panel UI is built in a later stage; until then this is a guarded
        no-op so the engine-recipe load path is safe. The loaded recipe lives in
        ``self._engine_recipe`` either way (#93).
        """
        # Layout editing is removed from the editor (Knut #93): it's a pure
        # patch-set tool, so BOTH layout groups (the printtarg knobs and the
        # ChromIQ engine panel) stay hidden. The chart keeps whatever layout it
        # was opened with — Create Chart owns the layout — and the hidden widgets
        # still hold those values so the chart renders and saves unchanged through
        # the round-trip.
        if self._engine_panel_grp is not None:
            self._engine_panel_grp.setVisible(False)
        if getattr(self, "_pt_box", None) is not None:
            self._pt_box.setVisible(False)
        # Narrower controls column now that the wide engine panel never shows.
        if getattr(self, "_controls_panel", None) is not None:
            self._controls_panel.setFixedWidth(360)
        if getattr(self, "_right_pane", None) is not None:
            # Tight scrollbar gutter so the right column's content sits the same
            # small distance from the window edge as the swatch frame on the left
            # (Knut #93 — symmetric margins).
            self._right_pane.setFixedWidth(360 + 4)

    def _load_ti2(self) -> None:
        start = (self._settings.get("custom_output_path", "")
                 or str(Path.home() / "ChromIQ"))
        path = open_file_dialog(
            self, "Load chart",
            "Charts & colour files (*.ti2 *.ti1 *.ti3 *.cgats *.txt);;"
            "All files (*)", start_dir=start)
        if not path:
            return
        self._load_chart_from(Path(path))

    def _load_chart_from(self, path: Path) -> bool:
        """Load a ``.ti2`` (+ its sibling ``meta.json`` layout knobs, if any)
        into the editor. Shared by the Load chart button and the open-time
        pre-load from the Create Chart tab (#45). Returns True on success.

        A non-``.ti2`` device-RGB file (ti1 / ti3 / cgats / list) loads its
        colours into a new editable chart instead. CIE reference files are not
        accepted here — load them via New chart / Add (#96)."""
        if path.suffix.lower() != ".ti2":
            return self._load_colour_chart_from(path)
        try:
            spec = R.ChartSpec.from_ti2(path)
            program = R.default_program(spec)
        except Exception as exc:  # noqa: BLE001 — surface the parser's message
            QMessageBox.warning(self, tr("Could not load chart"), str(exc))
            return False
        # Restore the printtarg layout knobs from the chart folder's meta.json
        # if this chart was saved by ChromIQ (the .ti2 itself only carries
        # instrument / paper / spacer palette). Foreign charts have no editor
        # meta: reset to defaults and take the basename from the file stem.
        saved = R.load_editor_meta(path)
        if saved is not None:
            self._options, self._basename = saved
            note = f"Loaded {path.name} (restored saved settings)"
        else:
            self._options = R.LayoutOptions()
            self._basename = path.stem or "chart"
            note = f"Loaded {path.name}"
        # The chart's creation recipe (if it carries one) — so New chart / Add
        # reopen with this design rather than the app-wide last-used state.
        self._chart_recipe = R.load_editor_recipe(path)
        # If this chart was built by the ChromIQ layout engine, load the exact
        # engine recipe from its channels.json so the engine panel can show all
        # the settings it was created with (#93).
        from workflow.layout_engine.presets import LayoutRecipe
        self._engine_recipe = LayoutRecipe.from_channels_json(
            path.with_suffix(".channels.json"))
        _t1 = path.with_suffix(".ti1")
        self._engine_ti1 = _t1 if _t1.is_file() else None
        # A loaded chart with no engine recipe is a printtarg chart → stay
        # printtarg even if the engine setting is on (preserve its real layout).
        self._loaded_printtarg_chart = self._engine_recipe is None
        # …except multi-ink charts, which are engine-only (#72 decision 0):
        # a non-RGB .ti2 without a recipe (e.g. a foreign CMYK chart) gets a
        # fresh engine recipe seeded from its instrument/paper — friendly
        # note, not an error.
        if (self._engine_recipe is None
                and spec.color_rep.lstrip("i").upper() != "RGB"):
            from workflow.chart_creator import ENGINE_INSTRUMENTS
            self._engine_recipe = LayoutRecipe(
                instrument=(spec.instrument_flag
                            if spec.instrument_flag in ENGINE_INSTRUMENTS
                            else "i1"),
                paper=spec.paper_flag)
            self._loaded_printtarg_chart = False
            note += tr(" — multi-ink chart, laid out by the ChromIQ engine")
        if self._engine_recipe is not None and self._engine_panel is not None:
            # The grid is loaded in the chart's final SHEET order (ChartSpec.
            # from_ti2 sorts by SAMPLE_LOC), i.e. it already IS the randomised
            # layout. So the preview must render it as-is — re-applying the
            # original seed would randomise a second time, showing a different
            # layout than the printed chart and than the grid (#93). Mark the
            # working recipe un-randomised; the grid preserves the randomisation,
            # and Shuffle re-randomises on demand.
            self._engine_recipe.randomize = False
            self._engine_panel.set_recipe(self._engine_recipe)
        self._refresh_engine_panel_visible()
        self._set_chart(spec, program, note, is_saved=True)
        return True

    def _load_colour_chart_from(self, path: Path) -> bool:
        """Load a device-RGB colours file (ti1 / ti3 / cgats / hex list) as a new
        editable chart — default instrument/paper, following the engine setting
        like a from-scratch chart, so the colours can be relaid out and analysed
        in the 3D cube. CIE reference files (XYZ/LAB only) aren't supported (#96)."""
        try:
            program = R.load_colour_file(path)
        except Exception as exc:  # noqa: BLE001 — surface the parser's message
            QMessageBox.warning(self, tr("Could not load chart"), str(exc))
            return False
        if not program:
            QMessageBox.warning(self, tr("Could not load chart"),
                                tr("No colour values were found in that file."))
            return False
        self._options = R.LayoutOptions()
        self._basename = path.stem or "chart"
        self._chart_recipe = None
        self._engine_recipe = None
        self._engine_ti1 = None
        self._loaded_printtarg_chart = False   # follow the engine setting
        spec = R.ChartSpec.new("i1", "A4")
        if (bool(self._settings.get("use_chromiq_layout_engine", False))
                and self._engine_panel is not None):
            from workflow.layout_engine.presets import default_recipe
            try:
                rec = default_recipe("i1", spec.paper_flag)
                rec.randomize = False
                self._engine_panel.set_recipe(rec)
            except Exception as exc:  # noqa: BLE001
                log.warning("seed engine panel for loaded colours failed: %s", exc)
        self._refresh_engine_panel_visible()
        # Say how many patches arrived (#150). Knut, on being offered a note
        # about the reference tables as well: *"No, it is enough that the editor
        # says how many patches loaded. The user does not need to know about the
        # other tables."* So the count alone — it is what he checked the file
        # against, and it is the number that was wrong.
        self._set_chart(spec, program, tr(
            "Loaded {name} — {n} patches.").format(name=path.name,
                                                   n=len(program))
            if len(program) != 1 else tr(
            "Loaded {name} — 1 patch.").format(name=path.name))
        return True

    def _new_chart(self) -> None:
        # Pre-load the current chart's recipe (if any) so the design can be
        # tweaked/recreated; capture the recipe the dialog reports back.
        dlg = _NewChartDialog(self._bin_dir, self._settings, self,
                              initial_recipe=self._chart_recipe)
        if dlg.exec() != QDialog.DialogCode.Accepted or dlg.result_spec is None:
            return
        if dlg.result_options is not None:
            self._options = dlg.result_options
        self._basename = dlg.result_basename or "chart"
        self._chart_recipe = dlg.result_recipe
        # A new from-scratch chart follows the engine setting (not a loaded
        # printtarg chart). Seed the engine panel's instrument/paper from it.
        self._engine_recipe = None
        self._engine_ti1 = None
        self._loaded_printtarg_chart = False
        spec = dlg.result_spec
        if (bool(self._settings.get("use_chromiq_layout_engine", False))
                and self._engine_panel is not None):
            from workflow.layout_engine.presets import default_recipe
            inst = "i1" if spec.instrument_flag in ("i1", "3p") else spec.instrument_flag
            try:
                rec = default_recipe(inst, spec.paper_flag)
                rec.randomize = False   # editor charts start un-randomised; Shuffle randomises
                # Carry the layout mode chosen in the New chart window's Chart
                # section into the recipe so the editor opens with it (#93).
                if inst == "CM":
                    rec.cm_density = int(getattr(dlg, "result_engine_density", 1))
                else:
                    rec.clip_border = bool(getattr(dlg, "result_engine_clip", True))
                    rec.nolimit = bool(getattr(dlg, "result_engine_nocap", False))
                self._engine_panel.set_recipe(rec)
            except Exception as exc:  # noqa: BLE001
                log.warning("seed engine panel for new chart failed: %s", exc)
        self._refresh_engine_panel_visible()
        # Honest out-of-gamut note from the perceptual bridge (#72): tell the
        # user how many look-based colours were moved to the gamut surface.
        note = "New chart"
        moved = getattr(dlg, "nch_moved_note", "")
        if moved:
            note += " — " + moved
        self._set_chart(spec, dlg.result_program or [], note)

    def _set_chart(self, spec: R.ChartSpec, program: list[tuple], note: str,
                   *, is_saved: bool = False) -> None:
        # Loading/creating a chart replaces the document: suppress capture while
        # we repopulate, then start a fresh history with this chart as baseline.
        self._suppress_undo = True
        self._undo_timer.stop()
        self._spec = spec
        # Seed the spacer palette from the source chart's own .ti1 (if its
        # sibling was found by ChartSpec.from_ti2), so loaded charts render
        # with the palette they were originally made with instead of
        # snapping to printtarg's defaults.
        self._palette = (list(spec.density_extremes)
                         if spec.density_extremes else None)
        self._paint.clear()
        self._sel_spacers.clear()
        self._populate_grid(program)
        self._build_palette_row()
        # Mirror the live printtarg-options widgets to the chart we just
        # loaded (so loading after a new-chart create reflects whatever the
        # user picked, and loading a file resets to defaults).
        self._sync_printtarg_widgets()
        self._chart_note = note
        # Baseline for unsaved-change detection (#49): a chart loaded from disk
        # starts clean; a freshly created / generated one is dirty until saved
        # (the sentinel _saved_sig never matches the live signature).
        if is_saved:
            self._saved_sig = self._current_signature()
        self._refresh_info()
        self._refresh_enabled()
        self._suppress_undo = False
        self._reset_undo()
        # Auto-render the initial preview so the user sees the chart
        # immediately instead of having to click "Update preview" first. Use the
        # engine when it's active (a from-scratch / engine chart), else printtarg
        # — mirroring _schedule_auto_refresh, so a new engine chart previews via
        # the engine instead of silently doing nothing (#93).
        if program:
            self._status.setText(tr("Rendering initial preview…"))
            if self._engine_active():
                self._engine_preview_timer.start()
            else:
                self._regenerate(save_to=None)
        else:
            # Blank canvas: drop any preview left over from a previous chart so
            # the empty grid and the preview agree (#96).
            self._clear_preview()
            self._status.setText(tr("Empty chart — add patches, then preview."))

    # -- unsaved-change tracking (#49) -------------------------------------
    def _current_signature(self) -> tuple:
        """A hashable snapshot of everything the user can edit: the patch
        program (colours + order), the spacer palette + per-spacer paint, and
        the printtarg layout knobs. Compared against _saved_sig to detect
        unsaved edits — so any change (re-colour, reorder, add/remove, spacer
        paint, layout tweak) flips the dialog dirty without per-edit hooks."""
        return (
            tuple(self._program_from_grid()),
            tuple(self._palette) if self._palette else None,
            tuple(sorted(self._paint.items())),
            astuple(self._options) if self._options is not None else None,
        )

    def _is_dirty(self) -> bool:
        """True when a chart is open and differs from its last saved state."""
        return (self._spec is not None
                and self._current_signature() != self._saved_sig)

    def _mark_saved(self) -> None:
        """Record the current content as the saved baseline (clean)."""
        self._saved_sig = self._current_signature()

    # -- undo / redo --------------------------------------------------------
    def _make_snapshot(self) -> _EditorSnapshot:
        """Deep-copy the current editable state into a history snapshot."""
        return _EditorSnapshot(
            program=self._program_from_grid(),       # tuples → immutable items
            palette=list(self._palette) if self._palette else None,
            paint=dict(self._paint),
            options=copy.deepcopy(self._options),
            instr=self._spec.instrument_flag if self._spec else "",
            paper=self._spec.paper_flag if self._spec else "",
            paper_mm=tuple(self._spec.paper_mm) if self._spec else (0.0, 0.0),
        )

    def _reset_undo(self) -> None:
        """Start a fresh history with the current chart as the baseline. Called
        whenever a different chart is loaded/created — undo never crosses charts."""
        if self._spec is None:
            self._undo_stack = []
            self._undo_index = -1
        else:
            self._undo_stack = [self._make_snapshot()]
            self._undo_index = 0
        self._refresh_undo_enabled()

    def _clear_undo_history(self) -> None:
        """Drop the entire in-memory history (on close). Nothing is persisted —
        this just frees the snapshots a touch sooner than garbage collection."""
        self._undo_timer.stop()
        self._undo_stack = []
        self._undo_index = -1

    def _note_edit(self) -> None:
        """Mark that the user changed something; (re)arm the debounced capture.
        No-op while we're repopulating the grid ourselves (load / undo / redo)."""
        if self._suppress_undo or self._spec is None:
            return
        self._undo_timer.start()

    def _capture_undo(self) -> None:
        """Push the current state as a new history step, unless it matches the
        step we're already sitting on. Pushing past an undone branch discards
        the redo tail, and the stack is capped at _UNDO_DEPTH steps."""
        if self._suppress_undo or self._spec is None:
            return
        snap = self._make_snapshot()
        if (0 <= self._undo_index < len(self._undo_stack)
                and snap.key == self._undo_stack[self._undo_index].key):
            return  # nothing actually changed
        del self._undo_stack[self._undo_index + 1:]   # drop the redo branch
        self._undo_stack.append(snap)
        # Keep baseline + _UNDO_DEPTH steps; drop the oldest beyond that.
        excess = len(self._undo_stack) - (_UNDO_DEPTH + 1)
        if excess > 0:
            del self._undo_stack[:excess]
        self._undo_index = len(self._undo_stack) - 1
        self._refresh_undo_enabled()

    def _undo(self) -> None:
        # A pending capture would otherwise fire mid-undo and corrupt the index.
        if self._undo_timer.isActive():
            self._undo_timer.stop()
            self._capture_undo()
        if self._undo_index <= 0:
            return
        self._undo_index -= 1
        self._restore_snapshot(self._undo_stack[self._undo_index])
        self._status.setText(tr("Undid one step."))
        self._refresh_undo_enabled()

    def _redo(self) -> None:
        if self._undo_index >= len(self._undo_stack) - 1:
            return
        self._undo_index += 1
        self._restore_snapshot(self._undo_stack[self._undo_index])
        self._status.setText(tr("Redid one step."))
        self._refresh_undo_enabled()

    def _restore_snapshot(self, snap: _EditorSnapshot) -> None:
        """Re-apply a history snapshot to the live editor, then re-render."""
        if self._spec is None:
            return
        self._suppress_undo = True
        try:
            self._spec.instrument_flag = snap.instr
            self._spec.paper_flag = snap.paper
            self._spec.paper_mm = tuple(snap.paper_mm)
            self._options = copy.deepcopy(snap.options) if snap.options else R.LayoutOptions()
            self._palette = list(snap.palette) if snap.palette else None
            self._paint = dict(snap.paint)
            self._sel_spacers.clear()
            self._populate_grid(snap.program)
            self._renumber()
            self._build_palette_row()
            self._sync_printtarg_widgets()
            self._refresh_info()
            self._refresh_enabled()
        finally:
            self._suppress_undo = False
        if snap.program:
            self._regenerate(save_to=None)

    def _refresh_undo_enabled(self) -> None:
        self._undo_btn.setEnabled(self._undo_index > 0)
        self._redo_btn.setEnabled(
            0 <= self._undo_index < len(self._undo_stack) - 1)

    def _confirm_discard(self) -> bool:
        """Ask before throwing away unsaved edits. Returns True to proceed
        (close), False to stay. No prompt when there's nothing unsaved."""
        if not self._is_dirty():
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(tr("Discard changes?"))
        box.setText(tr("This chart has unsaved changes."))
        box.setInformativeText(
            tr("If you close now they'll be lost. Use “Save As…” or "
               "“Apply / Save…” first to keep them."))
        discard = box.addButton(tr("Discard changes"),
                                QMessageBox.ButtonRole.DestructiveRole)
        keep = box.addButton(tr("Keep editing"),
                             QMessageBox.ButtonRole.RejectRole)
        # The app's button stylesheet keeps buttons short, which clips these
        # longer labels; give each room for its full text plus the stylesheet's
        # padding + Fusion frame (same fix as the Append-from-file prompt).
        for b in (discard, keep):
            b.setMinimumWidth(b.fontMetrics().horizontalAdvance(b.text()) + 64)
        box.setDefaultButton(keep)
        box.exec()
        return box.clickedButton() is discard

    def _on_close_clicked(self) -> None:
        # Just close — the confirmation lives in closeEvent so the Close button
        # and the window-corner X share one prompt. (Confirming here *and*
        # letting closeEvent re-confirm asked twice — Knut's #49 report.)
        self.close()

    def _schedule_auto_refresh(self) -> None:
        """Restart the debounced preview timer (called from user edit hooks)."""
        if self._spec is not None and self._grid.count() > 0:
            # Engine charts re-render via the engine (from the edited grid),
            # not printtarg — so grid edits update the engine preview (#93).
            if self._engine_active():
                self._engine_preview_timer.start()
            else:
                self._auto_timer.start()
        # Nearly every edit funnels through here (reorder/remove via _after_drag,
        # add/recolour/options/paper/palette directly), so it's the natural place
        # to note an undo step. Spacer paint and palette-reset bypass it and call
        # _note_edit themselves.
        self._note_edit()

    # -- patch grid ---------------------------------------------------------
    def _display_rgb(self, dev: tuple) -> tuple[float, float, float]:
        """Device tuple → display RGB (0..100) for this chart's colorspace (#72)."""
        return _display100(dev, self._spec.color_rep if self._spec else "iRGB")

    def _patch_tooltip(self, n: int, dev: tuple) -> str:
        """Grid tooltip: exact RGB format for RGB charts (unchanged), per-ink
        values for multi-ink charts, e.g. ``#7  C 40 · M 10 · Y 0 · K 5`` (#72)."""
        if self._spec is None or (len(dev) == 3
                                  and self._spec.color_rep.lstrip("i") == "RGB"):
            return f"#{n}  RGB {tuple(round(v) for v in dev)}"
        inks = [f.split("_")[-1] for f in self._spec.dev_fields]
        return f"#{n}  " + " · ".join(
            f"{ink} {round(v)}" for ink, v in zip(inks, dev))

    def _populate_grid(self, program: list[tuple]) -> None:
        self._grid.clear()
        for i, dev in enumerate(program, start=1):
            it = QListWidgetItem(
                _swatch_icon(self._display_rgb(dev), self._swatch_size), str(i))
            it.setData(Qt.ItemDataRole.UserRole, tuple(dev))
            it.setToolTip(self._patch_tooltip(i, dev))
            self._grid.addItem(it)
        self._update_grid_count()

    def _renumber(self) -> None:
        """Refresh #1..#N labels + tooltips (after drag-reorder or add/remove)."""
        for i in range(self._grid.count()):
            it = self._grid.item(i)
            dev = it.data(Qt.ItemDataRole.UserRole)
            it.setText(str(i + 1))
            it.setToolTip(self._patch_tooltip(i + 1, dev))
        # Keep the top-right "… N patches …" readout in step with the grid:
        # _renumber runs after every add / remove / append / reorder.
        self._refresh_info()

    def _update_grid_count(self) -> None:
        """Show the live total patch count under the swatch grid (Knut)."""
        lbl = getattr(self, "_grid_count_lbl", None)
        if lbl is None:
            return
        n = self._grid.count()
        lbl.setText(tr("1 patch total") if n == 1
                    else tr("{n} patches total").format(n=n))

    def _refresh_info(self) -> None:
        """Rewrite the header readout from the live grid count + chart flags."""
        self._update_grid_count()
        if self._spec is None:
            return
        note = getattr(self, "_chart_note", "")
        text = tr("{note} — {n} patches, -i{instr} -p{paper}").format(
            note=note, n=self._grid.count(),
            instr=self._spec.instrument_flag,
            paper=self._spec.paper_flag)
        self._info.setText(text)
        # The label may be clipped (Ignored width policy keeps long names from
        # pushing the source-row buttons off-screen), so keep the full readout
        # reachable on hover.
        self._info.setToolTip(text)

    def _set_swatch_size(self, size: int) -> None:
        """Resize the grid swatches; rebuild icons + delegate cell so the
        layout stays crisp and items keep their icon-above-label proportions."""
        self._swatch_size = size
        self._grid.setIconSize(QSize(size, size))
        self._delegate.swatch_size = size
        self._grid.setGridSize(self._delegate.sizeHint(None, None))
        for i in range(self._grid.count()):
            it = self._grid.item(i)
            it.setIcon(_swatch_icon(
                self._display_rgb(it.data(Qt.ItemDataRole.UserRole)), size))
        self._grid.scheduleDelayedItemsLayout()

    def _set_show_numbers(self, on: bool) -> None:
        """Toggle the patch-number label under each swatch (Knut #93)."""
        self._delegate.show_label = bool(on)
        self._reflow_grid()

    def _set_show_gap(self, on: bool) -> None:
        """Toggle the gaps between swatches; the H/V spinboxes drive the size when
        on, and they're greyed when off (Knut #93)."""
        for w in (getattr(self, "_gap_lbl", None), getattr(self, "_gap_h_lbl", None),
                  getattr(self, "_gap_h_spin", None), getattr(self, "_gap_v_lbl", None),
                  getattr(self, "_gap_v_spin", None)):
            if w is not None:
                w.setEnabled(bool(on))
        self._set_gap_sizes()

    def _set_gap_sizes(self, *_a) -> None:
        """Apply the Horizontal / Vertical gap (px) to the swatch grid — 0 when
        "Show gap between patches" is off (Knut #93)."""
        on = (getattr(self, "_show_gap_check", None) is not None
              and self._show_gap_check.isChecked())
        self._delegate.h_gap = self._gap_h_spin.value() if on else 0
        self._delegate.v_gap = self._gap_v_spin.value() if on else 0
        self._reflow_grid()

    def _reflow_grid(self) -> None:
        self._grid.setGridSize(self._delegate.sizeHint(None, None))
        self._grid.scheduleDelayedItemsLayout()
        self._grid.viewport().update()

    def _grid_item(self, dev: tuple) -> QListWidgetItem:
        """Build a grid item for one patch (icon + UserRole device payload)."""
        it = QListWidgetItem(_swatch_icon(self._display_rgb(dev),
                                          self._swatch_size), "")
        it.setData(Qt.ItemDataRole.UserRole, tuple(dev))
        return it

    def _add_patch(self) -> None:
        """Open the Add dialog — a single chosen colour, or one or more
        generated colour sets (3D cube, skin tones, blues, greens, greys, …) —
        and splice the result into the chart."""
        if (self._spec is not None
                and self._spec.color_rep.lstrip("i").upper() != "RGB"):
            # The Add dialog's sources (colour picker, RGB colour sets, hex
            # files) all produce RGB triples — splicing them into a multi-ink
            # program would corrupt it (#72; the multi-ink generators arrive
            # with the even-coverage / grey-balance sets).
            self._status.setText(
                tr("Adding patches to a multi-ink chart isn't available yet — "
                   "the colour sets here are RGB-only."))
            return
        dlg = _AddPatchesDialog(self._settings, self,
                                existing_patches=self._program_from_grid(),
                                initial_recipe=self._chart_recipe)
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.result_program:
            return
        # The chart's stored design is NOT touched here. Knut's rule (#130,
        # 2026-07-27): the settings a chart carries are the ones the New-patch-set
        # window was used with, and they change only when that window is used
        # again. Add has its own colour-set choices, which follow the last
        # New-patch-set settings — it does not speak for the chart's design.
        # (An earlier version of this folded Add's sets into the chart recipe;
        # that broke the rule above and was removed.)
        extra = dlg.result_program
        if self._spec is None:
            # Nothing loaded yet — seed a fresh blank chart from the added
            # patches (there's nothing to append to). Set up the engine panel the
            # way a from-scratch chart does (mirroring _load_colour_chart_from),
            # so when the engine is on _set_chart renders the initial preview via
            # the engine instead of leaving the right pane blank (#93).
            spec = R.ChartSpec.new("i1", "A4")
            self._options = R.LayoutOptions()
            self._basename = "chart"
            self._chart_recipe = None
            self._engine_recipe = None
            self._engine_ti1 = None
            self._loaded_printtarg_chart = False   # follow the engine setting
            if (bool(self._settings.get("use_chromiq_layout_engine", False))
                    and self._engine_panel is not None):
                from workflow.layout_engine.presets import default_recipe
                try:
                    rec = default_recipe("i1", spec.paper_flag)
                    rec.randomize = False
                    self._engine_panel.set_recipe(rec)
                except Exception as exc:  # noqa: BLE001
                    log.warning("seed engine panel for added patches failed: %s", exc)
            self._refresh_engine_panel_visible()
            self._set_chart(spec, list(extra), tr("New chart"))
            return
        if len(extra) == 1:
            # A single hand-picked colour goes straight on the end (no prompt).
            self._grid.addItem(self._grid_item(extra[0]))
            self._renumber()
            self._status.setText(tr("Patch added. Updating preview…"))
            self._schedule_auto_refresh()
            return
        extra = self._resolve_existing_overlap(extra)
        if extra is None:
            return
        if not extra:
            self._status.setText(
                tr("Those colours are all already in the chart, or too close to "
                   "ones in it — nothing new to add."))
            return
        self._place_patches_into_grid(
            extra, tr("{n} colours are ready to add.").format(n=len(extra)))

    def _resolve_existing_overlap(self, extra: list[tuple]) -> list[tuple] | None:
        """If any generated colour already sits in the loaded chart, explain it
        in plain language and let the user nudge the repeats unique, add only the
        new ones, add everything as-is, or cancel. Returns the patches to add
        (possibly relocated or filtered), or ``None`` to cancel. No overlap ⇒
        returns ``extra`` unchanged."""
        existing = self._program_from_grid()
        dup = G.count_too_close(existing, extra, _GEN_MIN_DIST)
        if dup == 0:
            return extra
        total = len(extra)
        kept = total - dup                       # how many "Add only the new ones" keeps
        box = QMessageBox(self)
        box.setWindowTitle(tr("Some of these colours are too close to ones "
                              "already in your chart"))
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setText(
            tr("1 of the {total} colours you're about to add lands on — or right "
               "next to — a colour already in this chart.").format(
                   total=total) if dup == 1
            else tr("{dup} of the {total} colours you're about to add land on — "
                    "or right next to — colours already in this chart.").format(
                        dup=dup, total=total))
        # Each choice now states its count impact (#78, Knut): how many it adds,
        # so the running total you saw is clearly affected by what you pick.
        box.setInformativeText(tr(
            "Two patches that are almost the same colour measure almost the same "
            "thing, so a duplicate mostly wastes paper, ink and measuring time "
            "without making your profile any more accurate.\n\n"
            "Here's what each choice does:\n\n"
            "• Make them unique (recommended) — keeps every colour you're adding "
            "(all {total}), but gently nudges each crowded one to the nearest free "
            "spot so it keeps a small gap from the colours already in your chart. "
            "None end up sitting on top of an existing one.\n\n"
            "• Add only the new ones — adds just the {kept} colours that are clear "
            "of the chart and drops the {dup} that would crowd one, so you add "
            "fewer than the {total} you planned.\n\n"
            "• Add new ones and fill the gaps — drops those {dup} too, then fills "
            "their place with {dup} fresh, non-overlapping colours, so you still "
            "add the full {total} with nothing printed almost twice.\n\n"
            "• Add anyway — adds all {total} exactly as generated, the {dup} "
            "overlaps included. Pick this only if you deliberately want "
            "near-identical colours, for example to average several readings of "
            "the same patch.\n\n"
            "• Cancel — go back without adding anything, so you can adjust the "
            "generator options first.").format(total=total, dup=dup, kept=kept))
        unique_btn = box.addButton(tr("Make them unique"),
                                   QMessageBox.ButtonRole.AcceptRole)
        onlynew_btn = box.addButton(tr("Add only the new ones"),
                                    QMessageBox.ButtonRole.AcceptRole)
        newfill_btn = box.addButton(tr("Add new ones and fill the gaps"),
                                    QMessageBox.ButtonRole.AcceptRole)
        anyway_btn = box.addButton(tr("Add anyway"),
                                   QMessageBox.ButtonRole.AcceptRole)
        cancel_btn = box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
        # Buttons render in the app's Menlo (monospace, uppercase) font, which is
        # wider than the default — measure with THAT font so a long label like
        # "Add new ones and fill the gaps" gets enough width and never overflows
        # onto its neighbour (Knut: an offscreen check missed this). Monospace, so
        # case doesn't change the width.
        mono = QFont(self.font())
        mono.setFamilies(["Menlo", "Consolas", "Courier New", "monospace"])
        fm = QFontMetrics(mono)
        for b in (unique_btn, onlynew_btn, newfill_btn, anyway_btn, cancel_btn):
            b.setMinimumWidth(fm.horizontalAdvance(b.text()) + 40)
        # Correct min-widths make the button row wide enough on its own (no clip),
        # and the long informative text keeps the box full-width. Just centre the
        # row and give it generous breathing room below the text — no grid-column
        # surgery (that shoved the text into half the window) (Knut).
        from PyQt6.QtWidgets import QDialogButtonBox
        bbox = box.findChild(QDialogButtonBox)
        if bbox is not None:
            bbox.setCenterButtons(True)
            cm = bbox.contentsMargins()
            bbox.setContentsMargins(cm.left(), cm.top() + 28, cm.right(),
                                    cm.bottom())
        box.setDefaultButton(unique_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked is unique_btn:
            return G.enforce_min_distance(extra, _GEN_MIN_DIST, existing=existing)
        if clicked is onlynew_btn:
            return G.drop_too_close(existing, extra, _GEN_MIN_DIST)
        if clicked is newfill_btn:
            # Drop the crowding ones, then top back up to the original count with
            # fresh patches that avoid the existing chart and the kept ones, so the
            # total stays as first calculated but nothing is printed almost twice.
            keep = G.drop_too_close(existing, extra, _GEN_MIN_DIST)
            fresh = G.fill_gaps(existing + keep, len(existing) + total)
            return keep + fresh
        if clicked is anyway_btn:
            return extra
        return None

    def _place_patches_into_grid(self, extra: list[tuple], ready: str) -> None:
        """Ask whether to add *extra* RGB patches at the start or the end of the
        chart, splice them in, and re-preview. ``ready`` is the lead sentence of
        the prompt (it names where the colours came from). Used by "Add…"
        (generated sets)."""
        box = QMessageBox(self)
        box.setWindowTitle(tr("Add the new colours"))
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setText(tr("Where would you like the new colours?"))
        box.setInformativeText(
            ready + " "
            + tr("You can place them right at the beginning of the chart or "
                 "tack them on at the end — whichever makes the combined set "
                 "easier to work with."))
        start_btn = box.addButton(tr("Add to the beginning"),
                                   QMessageBox.ButtonRole.AcceptRole)
        end_btn = box.addButton(tr("Add to the end"),
                                QMessageBox.ButtonRole.AcceptRole)
        cancel_btn = box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
        # The app's button stylesheet keeps buttons short, so the longer
        # "Add to the beginning"/"end" labels clip at the default width. Give
        # each button room for its full label plus the stylesheet's own
        # horizontal padding + Fusion frame (this also widens the dialog).
        for b in (start_btn, end_btn, cancel_btn):
            b.setMinimumWidth(b.fontMetrics().horizontalAdvance(b.text()) + 64)
        box.setDefaultButton(end_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked is start_btn:
            for i, rgb in enumerate(extra):
                self._grid.insertItem(i, self._grid_item(rgb))
            where = "start"
        elif clicked is end_btn:
            for rgb in extra:
                self._grid.addItem(self._grid_item(rgb))
            where = "end"
        else:
            return
        self._renumber()
        if where == "start":
            added = tr("Added {n} patches at the beginning.").format(n=len(extra))
        else:
            added = tr("Added {n} patches at the end.").format(n=len(extra))
        self._status.setText(added + " " + tr("Updating preview…"))
        self._schedule_auto_refresh()

    def _show_3d_distribution(self) -> None:
        """Open the rotatable 3D RGB-cube view of the current patch set."""
        program = self._program_from_grid()
        if not program:
            self._status.setText(tr("Add patches first to see their distribution."))
            return
        from ui.dialogs.patch_cube_dialog import PatchCubeDialog
        from ui.theme import resolve_mode
        from ui.tabs.tab_chart import comparable_presets
        mode = resolve_mode(self._settings.get("appearance", "auto"))
        # Same "Compare with profile" dropdown as the Tools 3D viewer (#66);
        # rebuilt each open so newly saved / deleted presets track automatically.
        try:
            presets = comparable_presets(self._settings)
        except Exception as exc:  # noqa: BLE001 — never block the viewer on this
            log.warning("comparable_presets failed: %s", exc)
            presets = []
        # No target_name: self._basename is the printer-profile name, which post-#70
        # doesn't describe the layout — show the neutral "Current chart" label
        # rather than a misleading profile name (Knut, #70 follow-up).
        PatchCubeDialog(program, mode=mode,
                        compare_presets=presets, numbered=True,  # patch # in hover (#67)
                        parent=self).exec()

    def _randomise_patches(self) -> None:
        """Shuffle the patch order into a random permutation, then re-preview.

        A pure reorder — no colour changes — so it's lossless: every patch
        stays, only its position moves. Useful for breaking up a structured
        set so each strip reads distinctly (see the "tag as randomised" gate).
        """
        # Engine chart: keep the same patches (.ti1) and randomise via the engine
        # seed — turn randomisation on, draw a fresh fixed seed (so it's shown and
        # reproducible), and re-render. No grid reorder (#93).
        if self._engine_active():
            from workflow.layout_engine.permutation import pick_seed
            seed = pick_seed()
            p = self._engine_panel
            p.randomize_cb.setChecked(True)
            p.fixed_seed_cb.setChecked(True)
            p.seed_spin.setValue(seed)        # emits changed → engine re-renders
            self._status.setText(
                tr("Shuffled with seed {s}.").format(s=seed))
            self._note_edit()
            return
        import random
        program = self._program_from_grid()
        if len(program) < 2:
            self._status.setText(tr("Need at least two patches to shuffle."))
            return
        random.shuffle(program)
        self._populate_grid(program)
        self._renumber()
        self._status.setText(
            tr("Shuffled {n} patches.").format(n=len(program))
            + " " + tr("Updating preview…"))
        self._schedule_auto_refresh()

    def _remove_selected_patches(self) -> None:
        rows = sorted((self._grid.row(it) for it in self._grid.selectedItems()),
                      reverse=True)
        if not rows:
            self._status.setText(tr("Select one or more patches first."))
            return
        for r in rows:
            self._grid.takeItem(r)
        self._renumber()
        n_removed = len(rows)
        self._status.setText(
            tr("Removed 1 patch.") if n_removed == 1
            else tr("Removed {n} patches.").format(n=n_removed))

    def _program_from_grid(self) -> list[tuple]:
        return [self._grid.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self._grid.count())]

    def _reconcile_recipe_with_chart(self) -> None:
        """Refresh the stored creation recipe (Set B) from the chart that was
        actually built (Set A), so saving can't persist a stale recipe.

        Edits made in the editor's own printtarg panel *after* New chart —
        patch scale, margin, density, DPI, … — update ``self._options`` but
        never ``self._chart_recipe`` (only New chart / Add / Load set that).
        Without this, a chart whose -a the user dialled back from 1.15 to 1.0
        to fit the page would still carry 1.15 in its recipe, so reloading the
        preset as a basis (or exporting it) resurrects the wrong scale (Knut).
        Layout knobs come from the live options; ``fill_to`` is refreshed to
        the realised patch count so a regenerate reproduces this chart's size.
        """
        rec = self._chart_recipe
        if not isinstance(rec, dict) or self._options is None:
            return
        o = self._options
        # Engine charts skip the layout/identity sync: their real layout is the
        # engine recipe (channels.json), while self._options / self._spec mirror
        # printtarg-era knobs that didn't produce the chart — syncing from those
        # would overwrite the design's own values (#100). The realised-patch-count
        # refresh below still applies.
        if not self._engine_active():
            # Shared Set-A → Set-B layout mapping (#92), so the editor and the
            # Create Chart tab keep a recipe's layout in step the exact same way.
            rec["layout"] = R.recipe_layout_from_options(o)
            if self._spec is not None:
                rec["instr"] = self._spec.instrument_flag
                rec["paper"] = self._spec.paper_flag
        if rec.get("mode") == "generate" and isinstance(rec.get("sp"), dict):
            try:
                n = len(self._program_from_grid())
            except Exception:  # noqa: BLE001 — count is best-effort
                n = 0
            if n > 0:
                rec["sp"]["fill_to"] = n

    def _export_patch_colours(self) -> None:
        """Save the current patch program as a text file (hex or 0..255 RGB).

        Format mirrors what :func:`workflow.ti2_relayout.parse_color_values`
        accepts so the file round-trips through the New chart dialog's
        "Paste colour values" mode. The hex/RGB list formats are RGB-only by
        definition; a multi-ink chart offers the i1Profiler pair instead
        (#72 — a "50 40 30 10" ink line would silently misparse as RGB on
        re-import, so it is not offered).
        """
        if self._grid.count() == 0:
            self._status.setText(tr("No patches to export."))
            return
        if self._spec is not None and \
                self._spec.color_rep.lstrip("i").upper() != "RGB":
            self._export_i1profiler()
            return
        from PyQt6.QtWidgets import QInputDialog
        fmt, ok = QInputDialog.getItem(
            self, tr("Export patch colours"), tr("Format:"),
            ["Hex (#rrggbb)", "RGB 0..255 (R G B)",
             "i1Profiler (.txt + .pxf)"], 0, False,
        )
        if not ok:
            return
        if fmt.startswith("i1Profiler"):
            self._export_i1profiler()
            return
        as_hex = fmt.startswith("Hex")
        start = (self._settings.get("custom_output_path", "")
                 or str(Path.home() / "ChromIQ"))
        default_name = f"{self._basename or 'chart'}-colours.txt"
        path = save_file_dialog(
            self, "Save patch colours",
            "Text files (*.txt)",
            start_path=str(Path(start) / default_name),
        )
        if not path:
            return
        out_path = Path(path)
        # NOT `if not out_path.suffix` — a typed name like "chart-w10.0mm" has
        # a truthy "suffix" of ".0mm", so the guard never fired and the file
        # was saved with no .txt at all (core/stem_paths.py).
        if not out_path.name.lower().endswith(".txt"):
            out_path = artefact(out_path, ".txt")
        lines: list[str] = []
        for r100, g100, b100 in self._program_from_grid():
            r = max(0, min(255, round(r100 / 100 * 255)))
            g = max(0, min(255, round(g100 / 100 * 255)))
            b = max(0, min(255, round(b100 / 100 * 255)))
            lines.append(f"#{r:02x}{g:02x}{b:02x}" if as_hex
                          else f"{r} {g} {b}")
        try:
            out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, tr("Save failed"), str(exc))
            return
        n_exp = len(lines)
        self._status.setText(
            tr("Exported 1 colour to {name}.").format(name=out_path.name)
            if n_exp == 1 else
            tr("Exported {n} colours to {name}.").format(n=n_exp, name=out_path.name))

    def _export_i1profiler(self) -> None:
        """Export the current patch program as i1Profiler-ready files.

        Writes the same ``<base>.txt`` (CGATS) + ``<base>.pxf`` (CxF3) pair the
        Create Chart tab produces, so the layout the user designed here can be
        handed straight to i1Profiler. Channel-generic since #72: the program
        goes via a temp .ti1 the exporter reads — RGB/CMYK sets get the
        ``.txt`` + ``.pxf`` pair, CMYK+N sets the ``.pxf`` only (i1Profiler
        accepts +N sets only as CxF; ``export_from_ti1`` decides).
        """
        import tempfile
        from workflow import i1profiler_export as X

        prog = self._program_from_grid()
        start = (self._settings.get("custom_output_path", "")
                 or str(Path.home() / "ChromIQ"))
        default_name = f"{self._basename or 'chart'}-i1profiler"
        path = save_file_dialog(
            self, "Export i1Profiler files",
            "i1Profiler (*.pxf)",
            start_path=str(Path(start) / default_name),
        )
        if not path:
            return
        out_path = Path(path)
        # By name, not by `.stem`: the default is "<chart>-i1profiler" with no
        # extension, and `.stem` of "X-w10.0mm-i1profiler" is "X-w10" — the
        # pair was exported as "X-w10.txt"/"X-w10.pxf", losing both the
        # patch width and the "-i1profiler" marker (core/stem_paths.py).
        base = without_ext(without_ext(out_path, ".pxf"), ".txt").name or "i1profiler"
        out_dir = out_path.parent
        try:
            with tempfile.TemporaryDirectory() as td:
                ti1 = Path(td) / f"{base}.ti1"
                if self._spec is not None:
                    R.write_ti1(self._spec, prog, ti1)
                else:
                    from workflow.i1profiler_import import RgbPatch, \
                        write_ti1 as _write_ti1
                    _write_ti1([RgbPatch(*rgb) for rgb in prog], ti1)
                txt_out, pxf_out = X.export_from_ti1(
                    ti1, out_dir, base_name=base, descriptor=base,
                    also_shuffled=bool(self._settings and self._settings.get(
                        "export_shuffled_pxf", False)))
        except Exception as exc:  # noqa: BLE001 — surface any writer failure
            QMessageBox.warning(self, tr("Save failed"), str(exc))
            return
        name = (f"{txt_out.name} + {pxf_out.name}" if txt_out else pxf_out.name)
        n_exp = len(prog)
        self._status.setText(
            tr("Exported 1 colour to {name}.").format(name=name)
            if n_exp == 1 else
            tr("Exported {n} colours to {name}.").format(n=n_exp, name=name))

    def _rgb_edit_allowed(self) -> bool:
        """Colour-pick / lighten / darken act on RGB values — on a multi-ink
        chart they would corrupt the ink tuples, so they are disabled until a
        per-ink editor exists (#72, v1 limitation)."""
        if self._spec is None or self._spec.color_rep.lstrip("i").upper() == "RGB":
            return True
        self._status.setText(
            tr("Patch colours can only be edited on RGB charts — this chart "
               "stores multi-ink values."))
        return False

    def _set_patch_colour(self) -> None:
        if not self._rgb_edit_allowed():
            return
        items = self._grid.selectedItems()
        if not items:
            self._status.setText(tr("Select one or more patches first."))
            return
        start = _qcolor(items[0].data(Qt.ItemDataRole.UserRole))
        c = self._pick_color(start, "Patch colour")
        if not c.isValid():
            return
        rgb = _to100(c)
        for it in items:
            it.setData(Qt.ItemDataRole.UserRole, rgb)
            it.setIcon(_swatch_icon(rgb))
        n_set = len(items)
        self._status.setText(
            tr("Set 1 patch.") if n_set == 1
            else tr("Set {n} patches.").format(n=n_set))
        self._schedule_auto_refresh()

    def _transform_selection(self, factor: float) -> None:
        if not self._rgb_edit_allowed():
            return
        items = self._grid.selectedItems()
        if not items:
            self._status.setText(tr("Select one or more patches first."))
            return
        for it in items:
            rgb = it.data(Qt.ItemDataRole.UserRole)
            new = tuple(max(0.0, min(100.0, v * factor)) for v in rgb)
            it.setData(Qt.ItemDataRole.UserRole, new)
            it.setIcon(_swatch_icon(new))
        self._schedule_auto_refresh()

    def _selected_rows(self) -> list[int]:
        return sorted(self._grid.row(it) for it in self._grid.selectedItems())

    def _move(self, rows: list[int], dest: int) -> None:
        if not rows:
            return
        taken = [self._grid.takeItem(r) for r in reversed(rows)][::-1]
        for off, it in enumerate(taken):
            self._grid.insertItem(dest + off, it)
        for off in range(len(taken)):
            self._grid.item(dest + off).setSelected(True)

    def _move_up(self) -> None:
        rows = self._selected_rows()
        if rows and rows[0] > 0:
            self._move(rows, rows[0] - 1)

    def _move_down(self) -> None:
        rows = self._selected_rows()
        if rows and rows[-1] < self._grid.count() - 1:
            self._move(rows, rows[0] + 1)

    def _move_front(self) -> None:
        self._move(self._selected_rows(), 0)

    def _move_back(self) -> None:
        rows = self._selected_rows()
        self._move(rows, self._grid.count() - len(rows))

    # -- mode + spacer palette ---------------------------------------------
    def _on_mode_change(self) -> None:
        patches = self._mode_patches.isChecked()
        self._patch_box.setVisible(patches)
        self._spacer_box.setVisible(not patches)
        # Entering Spacers mode needs the B&W spacer twin (for the per-spacer
        # masks), which the Patches-mode fast preview skips (#44). Render it now
        # if it's missing; otherwise just redraw (selection outlines only show
        # in Spacers mode).
        if (not patches and self._needs_twin() and self._regen is not None
                and not any(self._regen.bw_tiffs)):
            self._regenerate(save_to=None)
            return
        self._refresh_preview()

    def _build_palette_row(self) -> None:
        while self._palette_row.count():
            w = self._palette_row.takeAt(0).widget()
            if w:
                w.deleteLater()
        pal = self._current_palette()
        # entries 1..6 are the editable colour spacers (0=white, 7=black fixed)
        self._palette_row.setSpacing(4)
        for idx in range(1, 7):
            btn = QPushButton(self._spacer_box)
            # 6×30 + 5×4 = 200 px — fills the spacer groupbox content width
            # (~210 px) without overflowing.
            btn.setFixedSize(30, 30)
            # Defensive: cancel the panel-wide QPushButton padding/min-height
            # so each swatch is exactly 22×22 (else the panel CSS makes them
            # wider than their fixed size and they overlap their neighbours).
            btn.setStyleSheet(
                f"background:{_qcolor(pal[idx]).name()};"
                " border: 1px solid #888; border-radius: 2px;"
                " padding: 0; margin: 0;"
                " min-width: 0; min-height: 0;"
            )
            btn.setToolTip(tr("Spacer palette colour #{idx} — click to edit").format(idx=idx))
            btn.clicked.connect(lambda _=False, i=idx: self._edit_palette(i))
            self._palette_row.addWidget(btn)
        self._palette_row.addStretch(1)

    def _current_palette(self) -> list[tuple]:
        from workflow.i1profiler_import import _DENSITY_EXTREMES
        return list(self._palette) if self._palette else [tuple(c) for c in _DENSITY_EXTREMES]

    def _edit_palette(self, idx: int) -> None:
        pal = self._current_palette()
        c = self._pick_color(_qcolor(pal[idx]), "Spacer palette colour")
        if not c.isValid():
            return
        pal[idx] = _to100(c)
        self._palette = pal
        self._build_palette_row()
        self._status.setText(tr("Palette changed."))
        self._schedule_auto_refresh()

    def _reset_palette(self) -> None:
        self._palette = None
        self._build_palette_row()
        self._note_edit()
        self._status.setText(tr("Palette reset to default."))

    # -- printtarg-options panel -------------------------------------------
    def _on_printtarg_changed(self, *_a) -> None:
        """Pull the printtarg panel widgets into self._options and schedule
        a re-render. The mutual-exclusion + triple-density preset live in
        _on_dd_toggled / _on_td_toggled (which delegate back here)."""
        if getattr(self, "_pt_syncing", False):
            return
        # Spacer mode — checkbox group: at most one is on. All-off falls
        # through to printtarg's coloured default.
        if self._pt_sp_bw.isChecked():
            mode = "bw"
        elif self._pt_sp_none.isChecked():
            mode = "none"
        else:
            mode = "colored"
        # "None" means no spacers — disable the spacer-scale spinbox so
        # the user can't dial a -A that has nothing to apply to.
        self._pt_A.setEnabled(mode != "none")
        new = R.LayoutOptions(
            spacer_mode=mode,
            patch_scale=self._pt_a.value(),
            spacer_scale=self._pt_A.value(),
            margin_mm=self._pt_m.value(),
            suppress_left_clip=self._pt_L.isChecked(),
            no_strip_limit=self._pt_P.isChecked(),
            double_density=self._pt_dd.isChecked(),
            triple_density=self._pt_td.isChecked(),
            tiff_16bit=self._pt_bd16.isChecked(),
            dpi=self._pt_dpi.value(),
        )
        if new == self._options:
            return
        self._options = new
        self._schedule_auto_refresh()

    def _on_dd_toggled(self, on: bool) -> None:
        if on and self._pt_td.isChecked():
            self._pt_td.setChecked(False)
        self._on_printtarg_changed()

    def _on_force_tag_toggled(self, on: bool) -> None:
        # Affects only the saved .ti2's keyword, not the render — no re-preview.
        self._settings.set("ti2_editor_force_tag", bool(on))

    def _update_force_tag_state(self) -> None:
        """Enable the 'Force randomised tag' checkbox only when the current
        layout is judged unsafe to tag automatically.

        A well-mixed chart is tagged as randomised for us on save, so forcing is
        pointless and the box is greyed out; a structured one is left untagged
        unless the user forces it, so the box is offered. Driven by analysing the
        latest preview .ti2 (see _on_regen_done)."""
        safe = True
        if self._regen is not None:
            safe = R.analyze_randomisation(self._regen.ti2).safe
        self._pt_force_tag.setEnabled(not safe)
        self._pt_force_tag.setToolTip(
            "This chart is already well mixed, so it's tagged as randomised "
            "automatically — nothing to force here."
            if safe else
            "This chart's layout looks structured. Tick to mark it as randomised "
            "anyway (risky — click the ⓘ for details).")

    def _on_td_toggled(self, on: bool) -> None:
        """Triple-density mutual exclusion + preset application — mirrors
        the manual triple-density toggle in tab_chart."""
        if on and self._pt_dd.isChecked():
            self._pt_dd.setChecked(False)
        self._pt_dd.setEnabled(not on)
        # When this fires while syncing a freshly-loaded chart's options, that
        # chart already carries its own -a / -m — applying the TD preset here
        # would clobber them with 1.3 / 5 (Knut's #68 "editor shows 1.30/5"
        # bug, where a 1.04 / 6 triple-density preset came back wrong). Leave
        # the loaded values untouched; the sync sets the TD checkbox last.
        if self._pt_syncing:
            return
        # Block while applying the preset so we coalesce one re-render at
        # the end of this method instead of one per widget edit.
        self._pt_syncing = True
        try:
            if on:
                self._td_stash = {
                    "a": self._pt_a.value(),
                    "m": self._pt_m.value(),
                    "L": self._pt_L.isChecked(),
                    "P": self._pt_P.isChecked(),
                }
                self._pt_a.setValue(1.3)
                self._pt_m.setValue(5)
                self._pt_L.setChecked(True)
                self._pt_P.setChecked(True)
            else:
                stash = getattr(self, "_td_stash", None) or {}
                if "a" in stash:
                    self._pt_a.setValue(stash["a"])
                if "m" in stash:
                    self._pt_m.setValue(stash["m"])
                if "L" in stash:
                    self._pt_L.setChecked(bool(stash["L"]))
                if "P" in stash:
                    self._pt_P.setChecked(bool(stash["P"]))
                self._td_stash = None
        finally:
            self._pt_syncing = False
        self._on_printtarg_changed()

    def _sync_printtarg_widgets(self) -> None:
        """Push self._options + spec into the printtarg-section widgets.

        Called when a new chart is loaded / created so the widgets reflect
        whatever options came with it. Visibility of instrument-conditional
        rows is flipped from the loaded chart's instrument flag.
        """
        self._pt_syncing = True
        try:
            o = self._options
            # Instrument + Paper come from spec; everything else from
            # LayoutOptions.
            if self._spec is not None:
                ix = self._pt_instr.findData(self._spec.instrument_flag)
                if ix >= 0:
                    self._pt_instr.setCurrentIndex(ix)
                if _paper_code_known(self._spec.paper_flag):
                    ix = self._pt_paper.findData(self._spec.paper_flag)
                    if ix >= 0:
                        self._pt_paper.setCurrentIndex(ix)
                    self._pt_paper_custom_row.setVisible(False)
                else:
                    # paper_flag is a "WxH" custom size — point the combo
                    # at "Custom" and seed the W/H spinboxes from paper_mm.
                    ix = self._pt_paper.findData("custom")
                    if ix >= 0:
                        self._pt_paper.setCurrentIndex(ix)
                    w, h = self._spec.paper_mm
                    self._pt_paper_w.setValue(int(round(w)))
                    self._pt_paper_h.setValue(int(round(h)))
                    self._pt_paper_custom_row.setVisible(True)
            self._pt_sp_col.setChecked(o.spacer_mode == "colored")
            self._pt_sp_bw.setChecked(o.spacer_mode == "bw")
            self._pt_sp_none.setChecked(o.spacer_mode == "none")
            self._pt_A.setEnabled(o.spacer_mode != "none")
            self._pt_a.setValue(o.patch_scale)
            self._pt_A.setValue(o.spacer_scale)
            self._pt_m.setValue(o.margin_mm)
            self._pt_dpi.setValue(o.dpi)
            self._pt_bd8.setChecked(not o.tiff_16bit)
            self._pt_bd16.setChecked(o.tiff_16bit)
            self._pt_L.setChecked(o.suppress_left_clip)
            self._pt_P.setChecked(o.no_strip_limit)
            self._pt_dd.setChecked(o.double_density)
            self._pt_td.setChecked(o.triple_density)
            self._pt_dd.setEnabled(not o.triple_density)
            self._refresh_pt_instr_visibility()
        finally:
            self._pt_syncing = False

    def _refresh_pt_instr_visibility(self) -> None:
        """Show/hide -L / -P / -h / triple-density rows based on the
        currently-selected instrument — same rule as the New chart dialog."""
        code = self._pt_instr.currentData()
        is_strip = code in _STRIP_INSTRUMENTS
        is_cm = code == "CM"
        self._pt_L.setVisible(is_strip)
        self._pt_P.setVisible(is_strip)
        self._pt_dd.setVisible(is_cm)
        self._pt_td.setVisible(is_cm)
        # Hidden controls reset to off so they can't leak into the
        # printtarg flag list after an instrument switch. We block their
        # toggled signals here so the per-widget callbacks don't each
        # kick off a re-render — _on_pt_instr_changed schedules one at
        # the end.
        for w, on in ((self._pt_L, is_strip), (self._pt_P, is_strip),
                       (self._pt_dd, is_cm), (self._pt_td, is_cm)):
            if not on and w.isChecked():
                w.blockSignals(True)
                w.setChecked(False)
                w.blockSignals(False)

    def _on_pt_instr_changed(self) -> None:
        """User flipped the instrument combo. Visibility always follows
        the combo (so the conditional rows track the user's pick even
        before a chart is loaded). Spec + re-render only fire when a
        chart is open."""
        if getattr(self, "_pt_syncing", False):
            return
        self._refresh_pt_instr_visibility()
        if self._spec is None:
            return
        code = self._pt_instr.currentData()
        if code is None or code == self._spec.instrument_flag:
            return
        self._spec.instrument_flag = code
        self._on_printtarg_changed()
        self._refresh_info()   # keep the -i/-p readout in step (Knut)

    def _on_pt_paper_changed(self) -> None:
        """User flipped the paper combo — update spec.paper_flag + paper_mm
        + re-render. The paper change rewires printtarg's -p so we need a
        full regenerate, not just a redraw. "Custom" reveals W/H spinboxes
        and the actual paper_flag comes from those (see
        :meth:`_on_pt_paper_custom_changed`)."""
        is_custom = self._pt_paper.currentData() == "custom"
        self._pt_paper_custom_row.setVisible(is_custom)
        if getattr(self, "_pt_syncing", False) or self._spec is None:
            return
        if is_custom:
            self._on_pt_paper_custom_changed()
            return
        code = self._pt_paper.currentData()
        if code is None or code == self._spec.paper_flag:
            return
        self._spec.paper_flag = code
        # Update paper_mm too, looking up the named-papers reverse map.
        from workflow.ti2_relayout import _NAMED_PAPERS
        inv = {v: k for k, v in _NAMED_PAPERS.items()}
        self._spec.paper_mm = inv.get(code, self._spec.paper_mm)
        self._schedule_auto_refresh()
        self._refresh_info()   # keep the -i/-p readout in step (Knut)

    def _on_pt_paper_custom_changed(self) -> None:
        """Apply the W/H spinbox values to spec.paper_flag + paper_mm and
        schedule a re-render. Only meaningful when the paper combo is set
        to "Custom"."""
        if getattr(self, "_pt_syncing", False) or self._spec is None:
            return
        if self._pt_paper.currentData() != "custom":
            return
        w, h = self._pt_paper_w.value(), self._pt_paper_h.value()
        flag = f"{w}x{h}"
        if flag == self._spec.paper_flag:
            return
        self._spec.paper_flag = flag
        self._spec.paper_mm = (float(w), float(h))
        self._schedule_auto_refresh()
        self._refresh_info()   # keep the -i/-p readout in step (Knut)


    # -- regeneration / preview --------------------------------------------
    def _clear_preview(self) -> None:
        """Drop any shown preview (e.g. when the chart becomes empty) so a stale
        image doesn't linger over an empty grid (#96)."""
        self._full_pixmap = None
        self._base_pixmap = None
        self._engine_tiffs = []
        self._regen = None
        self._page = 0
        self._spacers = []
        self._sel_spacers.clear()
        if hasattr(self, "_spacer_cache"):
            self._spacer_cache.clear()
        self._update_page_nav()
        self._preview.clear()
        self._preview.setText(tr("Preview will appear here."))

    def _regenerate(self, save_to: Path | None) -> None:
        if self._spec is None or self._grid.count() == 0:
            # Empty chart: clear any leftover preview rather than leaving a stale
            # image (Update preview must "take" even with nothing to draw) (#96).
            self._clear_preview()
            self._status.setText(
                tr("Empty chart — add patches, then preview.")
                if self._spec is not None else tr("Load or create a chart first."))
            return
        if self._worker is not None and self._worker.isRunning():
            return
        # Multi-ink charts never touch printtarg (#72 decision 0): its
        # relayout path is RGB-only and would fail loudly. RGB engine charts
        # still run the printtarg pass first (it seeds page nav / geometry;
        # _on_regen_done then swaps in the engine render), but for non-RGB the
        # engine render IS the preview, directly.
        if (self._spec is not None
                and self._spec.color_rep.lstrip("i").upper() != "RGB"):
            self._do_engine_preview()
            return
        out_dir = save_to or Path(self._preview_tmp.name)
        # fresh dir for each preview render
        if save_to is None:
            for p in Path(self._preview_tmp.name).glob("*"):
                if p.is_file():
                    p.unlink()
        self._preview_pending_save = save_to
        self._set_busy(True)
        self._status.setText(tr("Rendering with printtarg…"))
        # Fast preview (#44): low DPI, and only render the B&W spacer twin when
        # we're actually in Spacers mode (it exists only for spacer selection).
        full_dpi = self._options.dpi if self._options else 300
        self._worker = _RegenWorker(
            self._spec, self._program_from_grid(), out_dir, self._bin_dir,
            tuple(self._palette) if self._palette else None,
            options=self._options, basename=self._basename,
            with_twin=self._needs_twin(),
            dpi_override=min(full_dpi, _PREVIEW_DPI))
        self._worker.done.connect(self._on_regen_done)
        self._worker.start()

    def _needs_twin(self) -> bool:
        """Whether to render the B&W twin (a second printtarg run, #44).

        Needed when something requires the pixel masks it provides:
          • "Highlight selected in preview" is on — patch geometry (the outline
            overlay + click-a-patch-to-select) is derived from the twin diff and
            is empty without it (would otherwise silently do nothing — #48 note);
          • Spacers mode — the per-spacer selection masks;
          • painted spacers — so those colours still show in the preview.
        The common Patches-mode browse (highlight off, unpainted) skips it — the
        big speed win."""
        if self._hl_patches.isChecked():
            return True
        if self._options is None or self._options.spacer_mode == "none":
            return bool(self._paint)
        return self._mode_spacers.isChecked() or bool(self._paint)

    def _on_regen_done(self, result) -> None:
        self._set_busy(False)
        if isinstance(result, Exception):
            QMessageBox.warning(self, tr("Render failed"), str(result))
            self._status.setText(tr("Render failed."))
            return
        self._regen = result
        # Engine charts: the printtarg regen seeds page nav / save, but the
        # accurate picture is the engine's own render — show that instead (#93).
        if self._engine_active():
            self._do_engine_preview()
            return
        # New render → previous per-page spacer segmentations + patch geometry
        # are stale. Both are now recomputed lazily for the visited page (#44).
        self._spacer_cache.clear()
        self._patch_geom_cache.clear()
        # Authoritative per-page strip count from the regenerated .ti2.
        self._strips_per_page = parse_passes_per_page(result.ti2)
        if self._page >= len(result.tiffs):
            self._page = 0
        self._show_page(self._page)
        # Refresh the 'Force randomised tag' affordance for this fresh layout.
        self._update_force_tag_state()
        if self._preview_pending_save is not None:
            self._status.setText(
                tr("Saved to {path}").format(path=self._preview_pending_save))
        else:
            pages = len(result.tiffs)
            extra = (tr(" across {pages} pages").format(pages=pages)
                     if pages > 1 else "")
            self._status.setText(
                tr("{n} spacers on this page{extra}.").format(
                    n=len(self._spacers), extra=extra)
                + " " + tr("Spacers mode → click a spacer on the page preview "
                           "to select it, then “Paint…”."))

    def _show_page(self, page: int) -> None:
        """Switch the preview to ``page``: detect its spacers (cached), redraw."""
        # Engine chart: flip between the rendered engine pages. The patch
        # highlight overlay is already keyed by (page, slot), so re-showing the
        # page's TIFF and refreshing redraws the right outlines (#93).
        if self._engine_active():
            tiffs = getattr(self, "_engine_tiffs", [])
            n = len(tiffs)
            if n == 0:
                return
            self._page = max(0, min(page, n - 1))
            self._sel_spacers.clear()
            self._update_page_nav()
            self._show_image(tiffs[self._page])
            return
        if self._regen is None:
            return
        n = len(self._regen.tiffs)
        self._page = max(0, min(page, n - 1))
        self._spacers = self._spacers_for_page(self._page)
        self._sel_spacers.clear()
        self._update_page_nav()
        self._apply_paint_and_show()

    def _spacers_for_page(self, page: int) -> list:
        """Spacer list for ``page`` — computed once and cached.

        The twin-diff + segmentation is the slow part of switching pages, so we
        memoise it per page. Cache is cleared on every fresh regen
        (:meth:`_on_regen_done`)."""
        cached = self._spacer_cache.get(page)
        if cached is not None:
            return cached
        spacers: list = []
        try:
            tif = self._regen.tiffs[page]
            bw  = self._regen.bw_tiffs[page]
            if bw is None:
                # No twin page for this deliverable page (page-break skew) —
                # render it without per-spacer selection rather than erroring.
                raise ValueError("no B&W twin for this page")
            mask = R.spacer_mask(tif, bw)
            ref_arr = R._imread_rgb(tif)
            # Authoritative split by strip count from PASSES_IN_STRIPS2 —
            # this handles the case where two adjacent strips happened to
            # pick the same spacer colour, which colour-jump detection
            # alone can't separate.
            strip_xs = self._compute_strip_xs(ref_arr, page)
            spacers = R.segment_spacers(
                mask, page=page, ref_arr=ref_arr, strip_xs=strip_xs)
        except Exception:
            spacers = []
        self._spacer_cache[page] = spacers
        return spacers

    def _compute_strip_xs(self, ref_arr, page: int) -> list[int] | None:
        """Return the inter-strip x-boundaries on ``page``, or None.

        Uses the page's strip count from PASSES_IN_STRIPS2 (parsed in
        :meth:`_on_regen_done`) and the patch-grid bbox to divide the block
        into equal-width strip cells.
        """
        if (page >= len(self._strips_per_page)
                or self._strips_per_page[page] <= 1):
            return None
        bbox = R._patch_grid_bbox(ref_arr)
        if bbox is None:
            return None
        y0, y1, x0, x1 = bbox
        n = self._strips_per_page[page]
        col_w = (x1 - x0 + 1) / n
        return [int(x0 + i * col_w) for i in range(1, n)]

    def _update_page_nav(self) -> None:
        if self._engine_active():
            n = len(getattr(self, "_engine_tiffs", []))
        else:
            n = len(self._regen.tiffs) if self._regen else 0
        self._page_bar.setVisible(n > 1)
        if n > 1:
            self._page_label.setText(
                tr("Page {page}/{total}").format(page=self._page + 1, total=n))
            self._prev_btn.setEnabled(self._page > 0)
            self._next_btn.setEnabled(self._page < n - 1)

    def _apply_paint_and_show(self) -> None:
        if self._regen is None:
            return
        tif = self._regen.tiffs[self._page]
        show_path = tif
        page_paint = {idx: rgb for (pg, idx), rgb in self._paint.items()
                      if pg == self._page}
        if page_paint and self._spacers:
            from collections import defaultdict
            groups: dict[tuple, list] = defaultdict(list)
            for idx, rgb in page_paint.items():
                if idx < len(self._spacers):
                    groups[tuple(round(v) for v in rgb)].append(self._spacers[idx])
            painted = Path(self._preview_tmp.name) / "_painted.tif"
            src = tif
            for rgb, sps in groups.items():
                R.recolor_spacers(src, sps, rgb, painted)
                src = painted
            show_path = painted
        self._show_image(show_path)

    def _engine_active(self) -> bool:
        # Active when the engine panel is showing (engine chart loaded, or the
        # engine setting is on for a new/from-scratch chart) and there's a chart
        # to render. The .ti1 is derived from the grid, so _engine_ti1 isn't
        # required. A loaded printtarg chart keeps printtarg (handled in
        # _refresh_engine_panel_visible) so its real no-clip layout shows.
        #
        # Multi-ink charts are engine-only, ALWAYS (#72 decision 0): printtarg
        # relayout is RGB-only by design (R.regenerate hard-fails), so a
        # non-RGB chart forces the engine path regardless of the Manual toggle
        # or where the chart came from.
        if (self._spec is not None
                and self._spec.color_rep.lstrip("i").upper() != "RGB"):
            return True
        return (self._engine_panel_grp is not None
                and not self._engine_panel_grp.isHidden()
                and self._spec is not None)

    def _engine_grid_ti1(self, out_path: Path) -> Path:
        """Write the current grid program as a .ti1 at *out_path* for the engine.

        Falls back to the loaded chart's .ti1 if the grid isn't usable. Lets the
        engine render/save reflect patch edits made in the grid (#93)."""
        try:
            if self._spec is not None and self._grid.count() > 0:
                R.write_ti1(self._spec, self._program_from_grid(), out_path)
                return out_path
        except Exception as exc:  # noqa: BLE001 — fall back to the original .ti1
            log.warning("engine grid .ti1 synth failed: %s", exc)
        import shutil
        if self._engine_ti1 is not None and Path(self._engine_ti1).is_file():
            shutil.copy(self._engine_ti1, out_path)
        return out_path

    @staticmethod
    def _engine_geom_from_recipe(recipe):
        """Build the engine Geom + paper mm for *recipe* (for spacer geometry)."""
        from workflow.layout_engine import instruments, papers
        geom = instruments.geom_from_build_kwargs(recipe.build_kwargs())
        w_mm, h_mm = papers.dimensions_mm(recipe.paper)
        return geom, w_mm, h_mm

    def _engine_cap_per_page(self) -> int:
        """Patches the engine fits on one sheet for the editor's current recipe,
        or 0 when not resolvable. Used by the live "Pages" fill (#93)."""
        try:
            from workflow.layout_engine import geometry
            recipe = self._engine_panel.get_recipe()
            geom, w_mm, h_mm = self._engine_geom_from_recipe(recipe)
            return geometry.patches_per_sheet(geom, w_mm, h_mm)
        except Exception:  # noqa: BLE001 — best-effort
            return 0

    def _on_engine_pages_changed(self, value: int) -> None:
        """The editor's live "Pages" spin: top the chart up with generated
        patches so it fills *value* whole pages, then re-render. Only grows the
        chart (lowering Pages never deletes patches); fires only for real user
        edits of an engine chart (#93, Knut)."""
        if self._syncing_pages or not self._engine_active():
            return
        cap = self._engine_cap_per_page()
        if cap <= 0:
            self._engine_preview_timer.start()
            return
        existing = self._program_from_grid()
        target = max(1, int(value)) * cap
        n_add = target - len(existing)
        if n_add > 0:
            fresh = G.fill_gaps(existing, target)
            # Same hard minimum-distance guarantee the New-chart generator and the
            # Add-patches "fill the gaps" flow apply: nudge any added patch that
            # still lands within _GEN_MIN_DIST of an existing one so every filled
            # patch is meaningfully distinct, not just spread (Knut, #93/#78).
            fresh = G.enforce_min_distance(fresh, _GEN_MIN_DIST, existing=existing)
            for rgb in fresh:
                self._grid.addItem(self._grid_item(rgb))
            self._renumber()
            self._status.setText(
                tr("Filled to {p} pages — added {n} patches. Updating preview…")
                .format(p=int(value), n=len(fresh)))
        self._engine_preview_timer.start()

    def _sync_pages_spin(self, pages: int) -> None:
        """Show the actually-rendered page count in the Pages spin without
        re-triggering the fill (#93)."""
        sp = getattr(self._engine_panel, "pages", None)
        if sp is None or sp.value() == pages or pages < 1:
            return
        self._syncing_pages = True
        sp.blockSignals(True)
        sp.setValue(min(pages, sp.maximum()))
        sp.blockSignals(False)
        self._syncing_pages = False

    def _do_engine_preview(self) -> None:
        """Render the current engine recipe to a temp page and show it as the
        preview — the live, engine-accurate picture for an engine chart (#93)."""
        if not self._engine_active():
            return
        try:
            from workflow.layout_engine import chart as le_chart
            recipe = self._engine_panel.get_recipe()
            kw = recipe.build_kwargs()
            kw["dpi"] = min(int(kw.get("dpi") or 150), 150)   # fast preview
            stem = Path(self._preview_tmp.name) / "_engine_preview"
            # Render from a .ti1 derived from the CURRENT grid, so reordering /
            # recolouring / adding patches updates the engine preview live (#93).
            ti1 = self._engine_grid_ti1(stem.with_suffix(".ti1"))
            result = le_chart.build_chart(str(ti1), stem, **kw)
            tiffs = result.tiff_paths or []
            if tiffs:
                # Keep the rendered pages so Page ◀ ▶ can flip between them, the
                # same as the printtarg preview does (#93).
                self._engine_tiffs = list(tiffs)
                if self._page >= len(tiffs):
                    self._page = 0
                self._show_image(tiffs[self._page])
                self._update_page_nav()
                self._sync_pages_spin(len(tiffs))   # keep "Pages" truthful (#93)
                # Cache spacer rects at the preview DPI so a preview click maps
                # to the spacer the engine will recolour (#93).
                from workflow.layout_engine import geometry, permutation
                geom, w_mm, h_mm = self._engine_geom_from_recipe(recipe)
                self._engine_spacer_rects = geometry.spacer_rects_px(
                    geom, w_mm, h_mm, result.layout, kw["dpi"])
                # Patch rects (per slot) + the grid-index→slot permutation, so
                # the "Highlight selected" overlay can outline the right patches.
                pr = geometry.patch_rects_px(geom, w_mm, h_mm, result.layout,
                                             kw["dpi"], recipe.strip_pattern,
                                             recipe.patch_pattern)
                self._engine_patch_rects = {(d["page"], d["slot"]): d for d in pr}
                self._engine_slots = permutation.location_permutation(
                    result.layout.total_patches, result.seed, recipe.randomize)
                self._status.setText(tr("Engine preview · {n} patches · seed {s}")
                                     .format(n=result.layout.total_patches,
                                             s=result.seed))
        except Exception as exc:  # noqa: BLE001 — preview is best-effort
            log.warning("engine preview failed: %s", exc)

    def _show_image(self, path: Path) -> None:
        pm = QPixmap(str(path))
        if pm.isNull():
            return
        self._full_pixmap = pm
        self._rescale_preview()

    def _rescale_preview(self) -> None:
        """Scale + compose the cached full-res pixmap onto a white canvas
        with a 15-px margin, the same canvas-with-white-border pattern
        ui.tiff_preview uses (see ``_repaint_label``). Painting the margin
        INTO the pixmap (instead of via QLabel QSS) sidesteps the
        sizeHint feedback loop that grows the label every refresh."""
        if self._full_pixmap is None:
            return
        dpr = self._preview.devicePixelRatioF() or 1.0
        lw, lh = self._preview.width(), self._preview.height()
        if lw <= 0 or lh <= 0:
            return
        B = 15  # white display border, all sides (logical px)
        avail = QSize(
            max(1, int((lw - 2 * B) * dpr)),
            max(1, int((lh - 2 * B) * dpr)),
        )
        scaled = self._full_pixmap.scaled(
            avail,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(dpr)
        canvas = QPixmap(scaled.width() + int(2 * B * dpr),
                         scaled.height() + int(2 * B * dpr))
        canvas.setDevicePixelRatio(dpr)
        canvas.fill(Qt.GlobalColor.white)
        p = QPainter(canvas)
        p.drawPixmap(B, B, scaled)
        p.end()
        # Logical scale (label coords → image px) — divides out the dpr.
        logical_w = scaled.width() / dpr
        self._preview_scale = (logical_w / self._full_pixmap.width()
                               if self._full_pixmap.width() else 1.0)
        # Origin of the patch raster inside the canvas, in label-logical
        # coords (used by _label_to_image when mapping clicks).
        self._preview_border = B
        self._preview_orig = self._full_pixmap.size()
        self._base_pixmap = canvas
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        """Redraw the preview from the cached base pixmap, overlaying yellow
        outlines on the currently-selected spacers (Spacers mode) or patches
        (Patches mode + Highlight toggle on). Hands the composited pixmap to
        the preview label so the marquee can repaint on top of it during
        drag.

        Overlay coordinates are shifted by ``_preview_border`` (the white
        margin baked into the canvas by :meth:`_rescale_preview`) so the
        rects align with the chart pixels inside the border.
        """
        if self._base_pixmap is None:
            return
        pm = QPixmap(self._base_pixmap)
        B = getattr(self, "_preview_border", 0)
        dpr = pm.devicePixelRatio() or 1.0
        # Painter coords are logical, but the canvas was created at device
        # pixels with DPR baked in — so logical scale = self._preview_scale
        # and the border offset is just B (logical px).
        if (self._mode_spacers.isChecked()
                and self._sel_spacers and self._spacers):
            # Fill + outline (à la ui.scan_highlighter) — a translucent yellow
            # wash makes thin bars visible at a glance, the 2px outline keeps
            # the boundary crisp.
            p = QPainter(pm)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            p.setBrush(QColor(255, 69, 115, 120))
            p.setPen(QPen(QColor(SPEC_MAGENTA), 2))
            s = self._preview_scale
            for i in self._sel_spacers:
                if 0 <= i < len(self._spacers):
                    x0, y0, x1, y1 = self._spacers[i].bbox
                    p.drawRect(int(x0 * s) + B - 1, int(y0 * s) + B - 1,
                               int((x1 - x0 + 1) * s) + 2,
                               int((y1 - y0 + 1) * s) + 2)
            p.end()
        elif (self._mode_patches.isChecked() and self._hl_patches.isChecked()
                and self._engine_active()):
            # Engine chart: outline selected grid patches using the engine's own
            # patch rects, mapping grid index → slot via the seeded permutation.
            sel = [self._grid.row(it) for it in self._grid.selectedItems()]
            p = QPainter(pm)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            p.setBrush(QColor(255, 69, 115, 120))
            p.setPen(QPen(QColor(SPEC_MAGENTA), 2))
            s = self._preview_scale
            for i in sel:
                if i < 0 or i >= len(self._engine_slots):
                    continue
                d = self._engine_patch_rects.get((self._page, self._engine_slots[i]))
                if d is None:
                    continue
                p.drawRect(int(d["x"] * s) + B - 1, int(d["y"] * s) + B - 1,
                           int(d["w"] * s) + 2, int(d["h"] * s) + 2)
            p.end()
        elif (self._mode_patches.isChecked()
                and self._hl_patches.isChecked()
                and self._regen is not None):
            geom = self._patch_geom_for_page(self._page)
            sel = {self._grid.row(it) + 1 for it in self._grid.selectedItems()}
            if sel and geom:
                p = QPainter(pm)
                p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
                p.setBrush(QColor(255, 69, 115, 120))
                p.setPen(QPen(QColor(SPEC_MAGENTA), 2))
                s = self._preview_scale
                for sid in sel:
                    box = geom.get(sid)
                    if box is None:
                        continue
                    x0, y0, x1, y1 = box
                    p.drawRect(int(x0 * s) + B - 1, int(y0 * s) + B - 1,
                               int((x1 - x0 + 1) * s) + 2,
                               int((y1 - y0 + 1) * s) + 2)
                p.end()
        self._preview.set_base_pixmap(pm)

    def _on_patch_highlight_toggled(self, on: bool) -> None:
        # Engine charts have exact patch geometry already — just redraw.
        if self._engine_active():
            self._refresh_preview()
            return
        # Turning highlight on needs the B&W twin for patch geometry, which the
        # fast Patches-mode preview skips (#44); render it now if it's missing.
        # Otherwise just redraw to show / clear the overlay.
        if (on and self._regen is not None and not any(self._regen.bw_tiffs)):
            self._regenerate(save_to=None)
            return
        self._refresh_preview()

    def _on_grid_selection_changed(self) -> None:
        # Cheap no-op unless we're showing the patch overlay; otherwise just
        # repaint with the new selection.
        if (self._mode_patches.isChecked() and self._hl_patches.isChecked()
                and (self._regen is not None or self._engine_active())):
            self._refresh_preview()

    def _patch_geom_for_page(self, page: int) -> dict:
        """Patch sample-id → pixel bbox for a page, computed once and cached.

        Lazy (visited page only) so a fresh render doesn't scan every page up
        front (#44). The B&W twin refines the y-bands when present; without it
        (Patches-mode fast preview) geometry falls back to the coarser bbox,
        which patch_geometry_for_page tolerates."""
        if self._regen is None or page >= len(self._regen.tiffs):
            return {}
        cached = self._patch_geom_cache.get(page)
        if cached is not None:
            return cached
        bw = (self._regen.bw_tiffs[page]
              if page < len(self._regen.bw_tiffs) else None)
        geom = R.patch_geometry_for_page(
            self._regen.ti2, self._regen.tiffs[page], page, bw_tif_path=bw)
        self._patch_geom_cache[page] = geom
        return geom

    def _patch_at(self, ix: float, iy: float) -> int | None:
        """Return the SAMPLE_ID under (ix, iy) on the current page, or None."""
        for sid, (x0, y0, x1, y1) in self._patch_geom_for_page(self._page).items():
            if x0 <= ix <= x1 and y0 <= iy <= y1:
                return sid
        return None

    def _engine_slot_to_grid(self) -> dict:
        """slot → grid-row index (inverse of the seeded permutation), so a
        preview hit on a patch maps back to its row in the editor grid (#93)."""
        return {slot: i for i, slot in enumerate(self._engine_slots)}

    def _engine_patch_at(self, ix: float, iy: float) -> int | None:
        """Grid row of the engine patch under (ix, iy) on the current page."""
        if not self._engine_patch_rects or not self._engine_slots:
            return None
        s2g = self._engine_slot_to_grid()
        for (pg, slot), d in self._engine_patch_rects.items():
            if pg != self._page:
                continue
            if (d["x"] <= ix <= d["x"] + d["w"]
                    and d["y"] <= iy <= d["y"] + d["h"]):
                gi = s2g.get(slot)
                if gi is not None and 0 <= gi < self._grid.count():
                    return gi
        return None

    def _engine_patches_in_rect(self, ix0, iy0, ix1, iy1) -> list[int]:
        """Grid rows of every engine patch the rectangle touches (current page)."""
        if not self._engine_patch_rects or not self._engine_slots:
            return []
        s2g = self._engine_slot_to_grid()
        out: list[int] = []
        for (pg, slot), d in self._engine_patch_rects.items():
            if pg != self._page:
                continue
            x0, y0, x1, y1 = d["x"], d["y"], d["x"] + d["w"], d["y"] + d["h"]
            if not (x1 < ix0 or x0 > ix1 or y1 < iy0 or y0 > iy1):
                gi = s2g.get(slot)
                if gi is not None and 0 <= gi < self._grid.count():
                    out.append(gi)
        return out

    def _select_patches_by_ids(
        self, sids: list[int], *, extend: bool, remove: bool = False,
    ) -> None:
        """Select grid rows for the given SAMPLE_IDs (1-based; row = id - 1).

        ``extend`` keeps the existing selection (Ctrl-style additive). ``remove``
        removes the given ids from the selection (Alt-style subtractive).
        """
        if not extend and not remove:
            self._grid.clearSelection()
        for sid in sids:
            row = sid - 1
            if 0 <= row < self._grid.count():
                self._grid.item(row).setSelected(not remove)

    def _engine_spacer_click(self, ix: float, iy: float, mods) -> None:
        """Recolour (or, with Alt, reset) the engine spacer under the click."""
        hit = None
        for r in self._engine_spacer_rects:
            if (r["page"] == self._page and r["x"] <= ix <= r["x"] + r["w"]
                    and r["y"] <= iy <= r["y"] + r["h"]):
                hit = r
                break
        if hit is None:
            return
        if mods & Qt.KeyboardModifier.AltModifier:        # Alt-click clears it
            self._engine_panel.set_spacer_override(hit["flat"], None)
            return
        col = QColorDialog.getColor(
            QColor("#000000"), self, tr("Spacer colour"),
            QColorDialog.ColorDialogOption.DontUseNativeDialog)
        if col.isValid():
            self._engine_panel.set_spacer_override(hit["flat"], col.name())

    def _label_to_image(self, p: QPoint) -> tuple[float, float] | None:
        """Map a label-coord click to deliverable image pixels (or None).

        ``_base_pixmap`` is DPR-aware; its ``width()`` is physical, so we
        divide by DPR to compare against the label's logical width. The
        white border baked into the canvas (``_preview_border``) is also
        subtracted before scaling back to original-image coordinates.
        """
        if self._base_pixmap is None or self._preview_scale <= 0:
            return None
        dpr = self._base_pixmap.devicePixelRatio() or 1.0
        pm_logical_w = self._base_pixmap.width() / dpr
        pm_logical_h = self._base_pixmap.height() / dpr
        off_x = (self._preview.width() - pm_logical_w) / 2
        off_y = (self._preview.height() - pm_logical_h) / 2
        B = getattr(self, "_preview_border", 0)
        return ((p.x() - off_x - B) / self._preview_scale,
                (p.y() - off_y - B) / self._preview_scale)

    def _on_marquee(self, rect, mods) -> None:
        """Marquee selection — same semantics as :meth:`_on_preview_click`.

            * plain marquee  → replace (everything hit by the rectangle)
            * Shift+marquee  → add hits to existing selection
            * Alt+marquee    → remove hits from selection
            * marquee hitting nothing + no modifiers → clear
        """
        tl = self._label_to_image(rect.topLeft())
        br = self._label_to_image(rect.bottomRight())
        if tl is None or br is None:
            return
        ix0, iy0 = tl
        ix1, iy1 = br
        is_alt   = bool(mods & Qt.KeyboardModifier.AltModifier)
        is_shift = bool(mods & (Qt.KeyboardModifier.ShiftModifier
                                | Qt.KeyboardModifier.ControlModifier
                                | Qt.KeyboardModifier.MetaModifier))

        if self._mode_spacers.isChecked():
            if not self._spacers:
                return
            touched = [
                i for i, sp in enumerate(self._spacers)
                if not (sp.bbox[2] < ix0 or sp.bbox[0] > ix1
                        or sp.bbox[3] < iy0 or sp.bbox[1] > iy1)
            ]
            if is_alt:
                self._sel_spacers.difference_update(touched)
            elif is_shift:
                self._sel_spacers.update(touched)
            else:
                # Empty marquee clears (no modifiers means a replace, so
                # selecting nothing should mean "clear").
                self._sel_spacers = set(touched)
            self._refresh_preview()
            n_sp = len(self._sel_spacers)
            self._status.setText(
                tr("1 spacer selected.") if n_sp == 1
                else tr("{n} spacers selected.").format(n=n_sp))
            return

        # Patches mode (+ highlight): marquee picks patches into the grid — for
        # printtarg charts and engine charts alike (#93).
        if not self._hl_patches.isChecked():
            return
        if self._engine_active():
            touched_p = [gi + 1 for gi in
                         self._engine_patches_in_rect(ix0, iy0, ix1, iy1)]
        elif self._regen is not None:
            geom = self._patch_geom_for_page(self._page)
            if not geom:
                return
            touched_p = [
                sid for sid, (x0, y0, x1, y1) in geom.items()
                if not (x1 < ix0 or x0 > ix1 or y1 < iy0 or y0 > iy1)
            ]
        else:
            return
        if is_alt:
            if touched_p:
                self._select_patches_by_ids(touched_p, extend=True, remove=True)
        elif is_shift:
            if touched_p:
                self._select_patches_by_ids(touched_p, extend=True)
        else:
            # Plain marquee replaces — clear first so an empty marquee is a
            # clear, and a non-empty one becomes exactly the touched set.
            self._grid.clearSelection()
            if touched_p:
                self._select_patches_by_ids(touched_p, extend=True)
        if touched_p and not is_alt:
            row = min(touched_p) - 1
            if 0 <= row < self._grid.count():
                self._grid.scrollToItem(self._grid.item(row))
        n_pat = len(self._grid.selectedItems())
        self._status.setText(
            tr("1 patch selected.") if n_pat == 1
            else tr("{n} patches selected.").format(n=n_pat))

    def _clear_spacer_selection(self) -> None:
        if not self._sel_spacers:
            return
        self._sel_spacers.clear()
        self._refresh_preview()
        self._status.setText(tr("Spacer selection cleared."))

    def _on_preview_click(self, pos: QPoint, mods) -> None:
        """Click in the preview — standard select semantics for both modes.

            * plain click on a target  → replace selection (clear + add hit)
            * plain click on empty     → clear selection
            * Shift+click              → add hit
            * Alt+click                → remove hit
        """
        mapped = self._label_to_image(pos)
        if mapped is None:
            return
        ix, iy = mapped
        # Engine chart + Spacers mode: click a spacer to recolour it (#93).
        if self._engine_active() and self._mode_spacers.isChecked():
            self._engine_spacer_click(ix, iy, mods)
            return
        is_alt   = bool(mods & Qt.KeyboardModifier.AltModifier)
        is_shift = bool(mods & (Qt.KeyboardModifier.ShiftModifier
                                | Qt.KeyboardModifier.ControlModifier
                                | Qt.KeyboardModifier.MetaModifier))

        if self._mode_spacers.isChecked():
            if not self._spacers:
                return
            hit = self._spacer_at(ix, iy)
            if hit is None:
                # Empty area + no modifiers clears; with modifiers it's a
                # no-op (a missed Shift-click shouldn't drop the selection).
                if not (is_alt or is_shift):
                    self._sel_spacers.clear()
                    self._refresh_preview()
                    self._status.setText(tr("Spacer selection cleared."))
                return
            if is_alt:
                self._sel_spacers.discard(hit)
            elif is_shift:
                self._sel_spacers.add(hit)
            else:
                self._sel_spacers = {hit}
            self._refresh_preview()
            n_sp = len(self._sel_spacers)
            self._status.setText(
                tr("1 spacer selected.") if n_sp == 1
                else tr("{n} spacers selected.").format(n=n_sp))
            return

        # Patches mode (+ highlight): click maps to the grid selection — for both
        # printtarg charts (_regen geometry) and engine charts (_engine_patch
        # rects via the seeded permutation) (#93).
        if not self._hl_patches.isChecked():
            return
        if self._engine_active():
            gi = self._engine_patch_at(ix, iy)
            sid = (gi + 1) if gi is not None else None
        elif self._regen is not None:
            sid = self._patch_at(ix, iy)
        else:
            return
        if sid is None:
            if not (is_alt or is_shift):
                self._grid.clearSelection()
                self._status.setText(tr("Patch selection cleared."))
            return
        row = sid - 1
        if not (0 <= row < self._grid.count()):
            return
        if is_alt:
            self._select_patches_by_ids([sid], extend=True, remove=True)
        elif is_shift:
            self._select_patches_by_ids([sid], extend=True)
        else:
            self._select_patches_by_ids([sid], extend=False)
        if not is_alt:
            self._grid.scrollToItem(self._grid.item(row))
        n_pat = len(self._grid.selectedItems())
        self._status.setText(
            tr("1 patch selected.") if n_pat == 1
            else tr("{n} patches selected.").format(n=n_pat))

    def _spacer_at(self, ix: float, iy: float) -> int | None:
        for i, sp in enumerate(self._spacers):
            x0, y0, x1, y1 = sp.bbox
            if x0 <= ix <= x1 and y0 <= iy <= y1:
                return i
        return None

    def _paint_spacers(self) -> None:
        if not self._sel_spacers:
            self._status.setText(tr("Click spacers in the preview to select them first."))
            return
        c = self._pick_color(QColor(128, 128, 128), "Spacer colour")
        if not c.isValid():
            return
        rgb = (c.red(), c.green(), c.blue())
        for i in self._sel_spacers:
            self._paint[(self._page, i)] = rgb
        self._apply_paint_and_show()
        self._note_edit()
        n_painted = len(self._sel_spacers)
        self._status.setText(
            tr("Painted 1 spacer on page {page}.").format(page=self._page + 1)
            if n_painted == 1 else
            tr("Painted {n} spacers on page {page}.").format(
                n=n_painted, page=self._page + 1))

    # -- save ---------------------------------------------------------------
    def _save_as(self) -> None:
        if self._spec is None or self._grid.count() == 0:
            return
        res = self._prompt_save_as_name()
        if res is None:
            return
        name, location = res
        target = Path(location) / name
        try:
            msg = self._write_chart_into(target, name)
        except Exception as exc:  # noqa: BLE001 — surface any writer failure
            QMessageBox.warning(self, tr("Save failed"), str(exc))
            return
        QMessageBox.information(self, tr("Saved"), msg)
        self._status.setText(msg.splitlines()[0])
        self._mark_saved()   # Save As clears the unsaved-changes flag (#49)

    def _prompt_save_as_name(self) -> "tuple[str, str] | None":
        """Custom Save-As prompt: a locked descriptive-prefix name field + the
        "Add a descriptive prefix" checkbox (same as Save & apply, #68) plus a
        location row. Returns ``(name, parent_dir)`` or None if cancelled. The
        chart is written as ``<parent_dir>/<name>/<name>.*``."""
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Save chart as…"))
        dlg.setMinimumWidth(580)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 20, 24, 16)
        lay.setSpacing(10)
        heading = QLabel(tr("Save this chart to a folder"), dlg)
        heading.setStyleSheet("font-weight: 600; font-size: 14px;")
        lay.addWidget(heading)
        lay.addWidget(QLabel(
            tr("The name becomes both the folder and the chart's file names."), dlg))

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel(tr("Chart name:"), dlg))
        name_edit = PrefixLockedLineEdit(dlg)
        name_row.addWidget(name_edit, 1)
        lay.addLayout(name_row)
        prefix_cb = QCheckBox(tr("Add a descriptive prefix"), dlg)
        prefix_cb.setChecked(bool(self._settings.get("create_chart_auto_suffix", True)))
        prefix_cb.toggled.connect(
            lambda on: _toggle_locked_prefix(name_edit, on, self._dialog_name_prefix()))
        lay.addWidget(prefix_cb)
        self._seed_save_name(name_edit, prefix_cb.isChecked())

        loc_row = QHBoxLayout()
        loc_row.addWidget(QLabel(tr("Location:"), dlg))
        start = (self._settings.get("custom_output_path", "")
                 or str(Path.home() / "ChromIQ"))
        loc_edit = QLineEdit(start, dlg)
        loc_row.addWidget(loc_edit, 1)
        browse = QPushButton(tr("Browse…"), dlg)
        browse.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        browse.clicked.connect(lambda: (
            (lambda d: loc_edit.setText(d) if d else None)(
                open_dir_dialog(self, tr("Choose a folder"),
                                start_dir=loc_edit.text() or start))))
        loc_row.addWidget(browse)
        lay.addLayout(loc_row)

        bb = QDialogButtonBox(dlg)
        ok_btn = bb.addButton(tr("Save"), QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn = bb.addButton(tr("Cancel"), QDialogButtonBox.ButtonRole.RejectRole)
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(dlg.accept)
        cancel_btn.clicked.connect(dlg.reject)
        lay.addWidget(bb)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        import re
        raw = name_edit.text().strip()
        clean = re.sub(r"\s+", "-", raw)
        clean = re.sub(r"[^\w\-.]", "_", clean).strip("._-") or "chart"
        location = loc_edit.text().strip() or start
        return clean, location

    def _write_chart_into(self, target: Path, name: str) -> str:
        """Write the complete chart deliverable into ``target`` and return a note.

        Shared by "Save As" and "Save & apply". Produces the same set of files a
        Create Chart build leaves in a run folder, plus the editor extras:
        ``<name>.ti1`` / ``.ti2`` / ``<name>_NN.tif`` (+ B&W spacer twin),
        ``meta.json`` (full layout), ``<name>-i1profiler.txt/.pxf`` and
        ``<name>-colours.txt`` (the colour list the old Export button wrote).
        Raises on a hard failure (regenerate / integrity); the extras are
        best-effort and never abort the save.
        """
        target.mkdir(parents=True, exist_ok=True)
        # Engine charts: render the deliverable with the ChromIQ engine using the
        # current panel recipe, so the saved chart matches the engine layout and
        # carries its recipe (in channels.json) for the carry-back to Create
        # Chart. Grid patch edits aren't re-fed to the engine — engine charts are
        # laid out from their .ti1 (#93).
        if self._engine_active():
            return self._write_engine_chart_into(target, name)
        # regenerate straight into the target, then bake per-spacer paint into pages
        res = R.regenerate(self._spec, self._program_from_grid(), target,
                           self._bin_dir,
                           spacer_palette=tuple(self._palette) if self._palette else None,
                           basename=name, options=self._options)
        pad = R.assert_data_integrity(self._program_from_grid(), res.ti2)
        self._bake_paint_into_saved(res)
        # Keep the stored creation recipe (Set B) in step with the chart we just
        # built (Set A) before persisting it — see _reconcile_recipe_with_chart.
        self._reconcile_recipe_with_chart()
        # Write meta.json (the same RunMeta the main app uses) into the chart
        # folder so reopening restores the printtarg knobs exactly as saved, and
        # the folder reads like a main-app chart.
        R.save_editor_meta(res.ti2, self._spec, self._options, name,
                           recipe=self._chart_recipe)
        # …and remember the same design as the app-wide last-used state, so the
        # next "New patch set…" opens on the settings you just applied rather
        # than on factory defaults (Knut, #130 2026-07-27). The chart's own copy
        # above still wins when that chart is reopened; this is the fallback for
        # every other case, which is exactly the one he hit.
        self._remember_gen_state()
        # Colour list (<name>-colours.txt) — what the old Export button wrote, so
        # the design can be pasted back into the New chart dialog later.
        colour_note = ""
        try:
            cpath = target / f"{name}-colours.txt"
            self._write_colour_values_file(cpath)
            colour_note = f"Colour list: {cpath.name}"
        except OSError as exc:
            log.warning("colour-list export during save failed: %s", exc)
        # i1Profiler-ready pair (<name>-i1profiler.txt/.pxf) so the saved chart
        # can be handed straight to i1Profiler (best-effort).
        i1_note = ""
        try:
            from workflow import i1profiler_export as X
            ti1 = res.ti2.with_suffix(".ti1")
            if ti1.exists():
                _txt, pxf = X.export_from_ti1(
                    ti1, target, base_name=f"{name}-i1profiler", descriptor=name,
                    also_shuffled=bool(self._settings and self._settings.get(
                        "export_shuffled_pxf", False)))
                i1_note = f"i1Profiler files: {pxf.stem}.txt/.pxf"
        except Exception as exc:  # noqa: BLE001
            log.warning("i1Profiler export during save failed: %s", exc)
        tag_note = self._maybe_tag_randomised(res.ti2)
        msg = (f"Saved {res.ti2.name} + "
               f"{count_phrase(len(res.tiffs), tr('1 page'), tr('{n} pages'))} "
               f"to {target}")
        if colour_note:
            msg += f"\n{colour_note}"
        if i1_note:
            msg += f"\n{i1_note}"
        if pad:
            msg += "\n" + _padding_note(pad)
        if tag_note:
            msg += "\n" + tag_note
        return msg

    def _write_engine_chart_into(self, target: Path, name: str) -> str:
        """Render the deliverable via the ChromIQ engine into *target* and embed
        the recipe in channels.json (so Create Chart can adopt it) (#93)."""
        import json
        from workflow.layout_engine import chart as le_chart
        recipe = self._engine_panel.get_recipe()
        # Write the (possibly edited) grid as the chart's .ti1 into the target,
        # so the saved chart reflects edits AND _import_applied_chart finds a
        # .ti1 to adopt (#93).
        self._engine_grid_ti1(target / f"{name}.ti1")
        result = le_chart.build_chart(str(target / f"{name}.ti1"), target / name,
                                      project=name,
                                      **recipe.build_kwargs())
        # Fold the strip geometry + recipe into channels.json, mirroring the
        # Create Chart build (workflow.chart_creator._embed_layout_geometry).
        sidecar = target / f"{name}.channels.json"
        strips = target / f"{name}.strips.json"
        layout = json.loads(strips.read_text()) if strips.exists() else {}
        layout["engine"] = "chromiq"
        layout["engine_version"] = 1
        layout["seed"] = result.seed
        layout["color_rep"] = result.color_rep
        layout["recipe"] = recipe.to_dict()
        # Top-level ``ink_channels`` so the preview can identify a multi-ink
        # chart's inks (the printtarg sidecar carries it too). Without it the
        # applied chart's preview could not decode a >4-channel TIFF and fell
        # back to an approximate render with a floating badge that overlapped
        # the Next button (#125). RGB (3-channel) charts still carry it; the
        # preview only shows the ink row / badge for ≥4-channel charts.
        from workflow.layout_engine.colorants import rep_ink_codes
        doc: dict = {"layout": layout}
        _codes = rep_ink_codes(result.color_rep)
        if _codes:
            doc["ink_channels"] = _codes
        sidecar.write_text(json.dumps(doc))
        if strips.exists():
            strips.unlink()
        # Hand-off sidecars (colour list + i1Profiler pair) — the same set the
        # printtarg save path writes, so an engine chart saved from the editor is
        # just as self-contained (#93 regression fix). No .cht here: the scanner
        # target (.cht + .cie) is produced from the *measured* .ti3 after
        # measurement (workflow.scanin_target, #97). Best-effort.
        from workflow.chart_exports import write_sidecars
        extras = write_sidecars(
            target / f"{name}.ti1", target, name,
            also_shuffled=bool(self._settings and self._settings.get(
                "export_shuffled_pxf", False)))
        # Write meta.json with the creation recipe (Set B), like the printtarg
        # save path does — without it an engine chart saved or applied from
        # here loses its New-patch-set design, so the Create Chart tab can't
        # carry it into presets and the editor can't reload it (#100). The
        # recipe stays as created (sync_layout=False): the chart's real layout
        # is the engine recipe in channels.json, not self._options.
        self._reconcile_recipe_with_chart()
        R.save_editor_meta(target / f"{name}.ti2", self._spec,
                           self._options or R.LayoutOptions(), name,
                           recipe=self._chart_recipe, sync_layout=False)
        pages = len(result.tiff_paths or [])
        msg = (f"Saved engine chart {name}.ti2 + "
               f"{count_phrase(pages, tr('1 page'), tr('{n} pages'))} to {target}\n"
               f"ChromIQ layout engine · {recipe.instrument} · {recipe.paper} · "
               f"seed {result.seed}")
        if extras:
            msg += "\nAlso wrote: " + ", ".join(sorted(e.name for e in extras))
        # The engine tops up a partial last strip with paper-white patches,
        # exactly like printtarg — say so, or the patch count silently grows
        # from the designed total (#124 report 6: 896 → 910).
        pad = getattr(result.layout, "padding", 0)
        if pad:
            msg += "\n" + _padding_note(pad)
        return msg

    def _write_colour_values_file(self, path: Path, as_hex: bool = True) -> None:
        """Write the current patch program as a colour list (hex by default).

        Same format :func:`workflow.ti2_relayout.parse_color_values` accepts, so
        the file round-trips through the New chart dialog's "Paste colour values".
        RGB charts only — for a multi-ink chart nothing is written (the format
        cannot carry ink values; matches ``chart_exports.write_colours_txt``).
        """
        if self._spec is not None and \
                self._spec.color_rep.lstrip("i").upper() != "RGB":
            log.debug("colour-list export skipped: %s chart is not RGB",
                      self._spec.color_rep)
            return
        lines: list[str] = []
        for r100, g100, b100 in self._program_from_grid():
            r = max(0, min(255, round(r100 / 100 * 255)))
            g = max(0, min(255, round(g100 / 100 * 255)))
            b = max(0, min(255, round(b100 / 100 * 255)))
            lines.append(f"#{r:02x}{g:02x}{b:02x}" if as_hex else f"{r} {g} {b}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _remember_gen_state(self) -> None:
        """Persist the design just applied as the app-wide last-used one.

        "All the last used settings should be saved when applying, and then
        reloaded into the editor when opened, so I can go back to it and change
        it" (Knut, #130 2026-07-27). Applying is the moment the user commits to
        a design, so it is the moment worth remembering — the sub-dialogs only
        remembered when they were OK'd, and a design that reached the chart by
        any other route was forgotten.
        """
        if self._settings is None or not isinstance(self._chart_recipe, dict):
            return
        try:
            self._settings.set("new_chart_gen", dict(self._chart_recipe))
        except Exception:      # noqa: BLE001 — never fail an apply over this
            log.warning("could not remember the patch-set settings",
                        exc_info=True)

    def _save_and_apply(self) -> None:
        """The "Apply / Save" action (#70, Knut's model).

        Offers three choices: **Overwrite** the chart currently loaded in the
        Create Chart tab with this layout (the profile name there is *not*
        changed); **Save As** to export the full deliverable to a folder you
        pick; or **Cancel** back to the editor. Falls back to a plain Save As
        when opened without a host to apply into.
        """
        if self._spec is None or self._grid.count() == 0:
            return
        if self._on_apply is None:
            # No host to apply into (e.g. dialog opened standalone) — save only.
            self._save_as()
            return
        action = self._prompt_apply_action()
        if action == "cancel":
            return                       # Cancel → back to the editor
        if action == "saveas":
            self._save_as()              # export to a folder, editor stays open
            return
        # Overwrite: the layout's own descriptive name is only the staging file
        # stem; the host imports it into the *current* Create Chart profile under
        # that profile's name, leaving the profile name untouched.
        name = self._default_apply_name()
        import shutil
        import tempfile
        # STAGING IS TEMPORARY AND MUST BE REMOVED ON EVERY PATH.
        # `_write_chart_into` lays out the whole deliverable here — .ti1, .ti2
        # and every page TIFF — and the host takes only the .ti1 out of it
        # (tab_chart.py::apply_external_chart), copying it into the project. So
        # nothing needs this folder once `_on_apply` has returned, and the async
        # build that follows reads the project's copy, not this one. It used to
        # be left behind on all five exits, leaking a full multi-page chart's
        # TIFFs into $TMPDIR every time Apply was pressed.
        staging = Path(tempfile.mkdtemp(prefix="chromiq_apply_"))
        try:
            try:
                self._write_chart_into(staging, name)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, tr("Could not prepare chart"), str(exc))
                return
            self._status.setText(
                tr("Applying this chart to the Create Chart tab…"))
            try:
                applied = self._on_apply(staging, name)
            except Exception as exc:  # noqa: BLE001
                log.exception("apply callback failed")
                QMessageBox.warning(self, tr("Could not apply chart"), str(exc))
                return
            # The host returns False when the user backed out of a prompt — keep
            # the editor open so they can try again.
            if applied is False:
                self._status.setText(
                    tr("Apply cancelled — the editor is still open."))
                return
            self._mark_saved()   # applied + saved — closing must not warn (#49)
            self._clear_undo_history()
            self.accept()
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def _suggest_chart_name(self) -> str:
        """A descriptive default name from the chart's printtarg settings, e.g.
        ``i1Pro-A4-480p-2pages-Landscape`` (#62). Used when no target name was
        carried into the editor. Tokens are kept as fixed ASCII identifiers (not
        translated) so the suggested name is a stable, filename-safe handle."""
        if self._spec is None:
            return "chart"
        instr = {"i1": "i1Pro", "CM": "ColorMunki", "3p": "i1Pro3Plus",
                 "SS": "SpectroScan", "CR30": "CR30"}.get(self._spec.instrument_flag,
                                          self._spec.instrument_flag or "chart")
        # Named papers contribute their NAME (e.g. "A3+"), not their millimetre
        # code ("483x329"); only a truly custom size falls back to the W×H code
        # (#68, Knut). PAPER_LABELS keys both named sizes and the WxH aliases for
        # named ones, so a known code resolves to its short label here.
        paper = paper_name_token(self._spec.paper_flag or "paper")
        parts = [instr, paper, f"{self._grid.count()}p"]
        pages = len(self._regen.tiffs) if self._regen is not None else 0
        if pages:
            parts.append("1page" if pages == 1 else f"{pages}pages")
        w, h = self._spec.paper_mm
        if w and h:
            parts.append("Landscape" if w > h else "Portrait")
        return "-".join(parts)

    def _dialog_name_prefix(self) -> str:
        """The locked descriptive prefix for the Save dialogs — the suggested
        name, or empty when no real chart is loaded (so the bare ``chart``
        placeholder never becomes a prefix)."""
        return self._suggest_chart_name() if self._spec is not None else ""

    def _seed_save_name(self, name_edit: "PrefixLockedLineEdit", on: bool) -> None:
        """Initial contents of a Save dialog's name field (#68, Knut's model).
        ON shows the locked suggested name + ``-`` with an empty editable tail
        (cursor ready to type); OFF shows the suggested name as a plain, fully
        editable field (no dash, no lock)."""
        _toggle_locked_prefix(name_edit, on, self._dialog_name_prefix())

    def _default_apply_name(self) -> str:
        """The pre-filled Save & apply name: the target name carried through the
        editor when there is one, else a suggestion from the settings (#62)."""
        base = (self._basename or "").strip()
        if base and base != "chart":
            return base
        return self._suggest_chart_name()

    def _prompt_apply_action(self) -> str:
        """The "Apply / Save" window (#70, Knut's model).

        Returns ``"overwrite"`` (replace the chart currently loaded in the Create
        Chart tab with this layout), ``"saveas"`` (export the full chart to a
        folder you pick), or ``"cancel"`` (back to the editor). No name is asked
        for — the profile name lives in the Create Chart tab and is never changed
        from here.
        """
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Apply or save this patch set"))
        dlg.setMinimumWidth(580)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 20, 24, 16)
        lay.setSpacing(12)

        heading = QLabel(
            tr("What would you like to do with this chart layout?"), dlg)
        heading.setWordWrap(True)
        heading.setStyleSheet("font-weight: 600; font-size: 14px;")
        lay.addWidget(heading)

        body = QLabel(
            tr("  •  Overwrite — send this patch set to the Create Chart tab "
               "and lay it out there. The page layout comes from that tab, not "
               "from here: your instrument, paper, margins and patch size are "
               "used exactly as they are set there, so the arrangement you see "
               "in this editor is not carried across. The patch recipe is then "
               "locked so it can't be rebuilt by accident, while the page "
               "layout stays editable. Your printer profile project name is "
               "not changed. If the run it builds into already holds a "
               "measurement or a profile, ChromIQ asks you first and moves "
               "them into that run's “old” folder — nothing is deleted.\n"
               "  •  Save As — export the full chart (the patch list, the "
               "layout and the printable pages, plus the i1Profiler files and a "
               "colour list) to a folder you pick, without leaving the editor.\n"
               "  •  Cancel — go back to the editor and change nothing."), dlg)
        body.setWordWrap(True)
        lay.addWidget(body)

        # Nelson: opt-in "also save a shuffled i1Profiler copy". It lives here in
        # the Apply/Save window (Knut) because this is where the export happens;
        # it shares the single export_shuffled_pxf setting with the Tools ▸
        # Convert TI1 → i1Profiler dialog, so ticking it persists and the
        # Overwrite/Save As export below picks it up. Far-right magenta ⓘ.
        shuf_row = QHBoxLayout()
        shuf_row.setSpacing(6)
        shuffle_check = QCheckBox(
            tr("Also save a shuffled copy for i1Profiler"), dlg)
        shuffle_check.setChecked(
            bool(self._settings and self._settings.get("export_shuffled_pxf", False)))
        shuffle_check.setStyleSheet(
            f"QCheckBox::indicator:checked {{ background: {SPEC_MAGENTA};"
            f" border-color: {SPEC_MAGENTA}; }}"
            f"QCheckBox::indicator:hover {{ border-color: {SPEC_MAGENTA}; }}")
        if self._settings is not None:
            shuffle_check.toggled.connect(
                lambda on: self._settings.set("export_shuffled_pxf", bool(on)))
        shuf_row.addWidget(shuffle_check)
        shuf_row.addStretch(1)
        shuf_row.addWidget(
            _magenta_tip(
                tr("Keep your chart layout in i1Profiler"),
                tr("When you load a patch set into i1Profiler, it arranges the "
                "patches on the page in the order they appear in the file. A "
                "chart straight out of ChromIQ lists its colours in a tidy, "
                "systematic order — which can put very similar colours right "
                "next to each other on the printed strip. That is a little "
                "harder to read by eye and slightly less ideal for the "
                "instrument.\n\n"
                "Tick this box and ChromIQ saves a second copy whose patches "
                "are shuffled into a mixed-up order, with “-shuffled” "
                "added to the file name. Hand that shuffled copy to i1Profiler "
                "and it keeps exactly this mixed order instead of lining the "
                "colours back up — so similar colours end up spread apart "
                "across the chart.\n\n"
                "Both copies are always written, so you can pick whichever you "
                "prefer. If you are unsure, the shuffled copy is the safer one "
                "to print and measure."),
                dlg),
            0, Qt.AlignmentFlag.AlignVCenter)
        lay.addLayout(shuf_row)

        bb = QDialogButtonBox(dlg)
        overwrite_btn = bb.addButton(tr("Overwrite"),
                                     QDialogButtonBox.ButtonRole.AcceptRole)
        saveas_btn = bb.addButton(tr("Save As…"),
                                  QDialogButtonBox.ButtonRole.ActionRole)
        cancel_btn = bb.addButton(tr("Cancel"),
                                  QDialogButtonBox.ButtonRole.RejectRole)
        overwrite_btn.setDefault(True)
        lay.addWidget(bb)

        result = {"v": "cancel"}
        overwrite_btn.clicked.connect(lambda: (result.__setitem__("v", "overwrite"), dlg.accept()))
        saveas_btn.clicked.connect(lambda: (result.__setitem__("v", "saveas"), dlg.accept()))
        cancel_btn.clicked.connect(dlg.reject)
        dlg.exec()
        return result["v"]

    def _maybe_tag_randomised(self, ti2: Path) -> str:
        """Decide how the just-saved .ti2 is tagged as randomised, and do it.

        - Well-mixed layout → tagged automatically (CHART_ID → RANDOM_START).
        - Structured layout + 'Force' ticked → tagged after a risk warning the
          user can suppress ('never show again'), or silently if suppressed.
        - Structured layout + 'Force' unticked → left untagged.

        Returns a short note for the save confirmation (empty if nothing to say).
        """
        report = R.analyze_randomisation(ti2)
        if report.safe:
            R.tag_ti2_randomised(ti2)
            return "Tagged as randomised — bidirectional measuring is available."
        if not self._pt_force_tag.isChecked():
            return ("Left untagged — the layout looks structured, so it will be "
                    "measured one direction only. Tick “Force randomised tag” to "
                    "override.")
        if not self._confirm_force_tag(report):
            return ("Left untagged — the layout looks structured, so it will be "
                    "measured one direction only.")
        R.tag_ti2_randomised(ti2)
        return ("Tagged as randomised (forced) — take care: this layout may be "
                "read unreliably (see the warning).")

    def _confirm_force_tag(self, report: "R.RandomisationReport") -> bool:
        """Risk warning shown when the user forces the tag on an unsafe layout.

        Returns True to go ahead and tag. Honours a 'never show this again'
        preference, after which forcing tags without prompting."""
        if bool(self._settings.get("ti2_editor_force_tag_hide_warning", False)):
            return True

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Force “randomised” tag?"))
        dlg.setMinimumWidth(560)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 20, 24, 16)
        lay.setSpacing(12)

        heading = QLabel(
            tr("You're about to mark a structured chart as randomised. Please read "
            "this first."), dlg)
        heading.setWordWrap(True)
        heading.setStyleSheet("font-weight: 600;")
        lay.addWidget(heading)

        body = QLabel(
            tr("When you measure a chart, your instrument has to work out which strip "
               "it's looking at and which way round you scanned it. It does that by "
               "matching the colours it reads against what it expects — and that only "
               "works reliably when the colours are well shuffled, so every strip has "
               "its own distinctive look.\n\n"
               "ChromIQ checked this chart and it looks structured instead: "
               "{reason} On a layout like this "
               "the strips can look alike, so the instrument may lock onto the wrong "
               "strip or read it backwards. The frustrating part is that you usually "
               "get no error at all — just measurements that are quietly wrong, which "
               "then build a profile with colour casts.\n\n"
               "Marking it as randomised anyway tells your instrument it's free to "
               "read strips in either direction, which is exactly where this goes "
               "wrong. It's only a sensible choice if you happen to know the order is "
               "genuinely well mixed despite how it looks.\n\n"
               "The safer alternatives: leave it untagged and simply scan every strip "
               "the same way, or rebuild the chart so its colours are shuffled.\n\n"
               "Would you like to mark it as randomised anyway?").format(
                reason=report.reason[0].lower() + report.reason[1:]), dlg)
        body.setWordWrap(True)
        lay.addWidget(body)

        hide_cb = QCheckBox(tr("Don't show this again"), dlg)
        lay.addWidget(hide_cb)

        bb = QDialogButtonBox(dlg)
        tag_btn = bb.addButton(tr("Tag anyway"), QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn = bb.addButton(tr("Leave untagged"), QDialogButtonBox.ButtonRole.RejectRole)
        cancel_btn.setDefault(True)
        tag_btn.clicked.connect(dlg.accept)
        cancel_btn.clicked.connect(dlg.reject)
        lay.addWidget(bb)

        proceed = dlg.exec() == QDialog.DialogCode.Accepted
        if hide_cb.isChecked():
            self._settings.set("ti2_editor_force_tag_hide_warning", True)
        return proceed

    def _bake_paint_into_saved(self, res: R.RegenResult) -> None:
        """Apply per-spacer paint to every saved page in place.

        Spacer indices are deterministic per page (same program + ``-r``), so the
        ``(page, idx)`` keys collected while previewing each page map straight
        onto the freshly regenerated pages here.
        """
        if not self._paint:
            return
        from collections import defaultdict
        for page, (tif, bw) in enumerate(zip(res.tiffs, res.bw_tiffs)):
            page_paint = {idx: rgb for (pg, idx), rgb in self._paint.items()
                          if pg == page}
            if not page_paint or bw is None:
                # bw is None when the twin render skipped this page (page-break
                # skew) — no spacer mask, so this page's paint can't be located.
                continue
            spacers = R.segment_spacers(R.spacer_mask(tif, bw), page=page,
                                        ref_arr=R._imread_rgb(tif))
            groups: dict[tuple, list] = defaultdict(list)
            for idx, rgb in page_paint.items():
                if idx < len(spacers):
                    groups[tuple(round(v) for v in rgb)].append(spacers[idx])
            src = tif
            for rgb, sps in groups.items():
                R.recolor_spacers(src, sps, rgb, tif)
                src = tif

    # -- misc ---------------------------------------------------------------
    def _set_busy(self, busy: bool) -> None:
        self._preview_btn.setEnabled(not busy)
        self._shuffle_btn.setEnabled(not busy)
        self._apply_btn.setEnabled(not busy)

    def _refresh_enabled(self) -> None:
        has = self._spec is not None
        self._preview_btn.setEnabled(has)
        self._shuffle_btn.setEnabled(has)
        self._apply_btn.setEnabled(has)
        self._refresh_undo_enabled()
        # Initial pass for the conditional checkboxes — without this the
        # default Qt state shows ALL four (L, P, double, triple) at
        # startup before any chart is loaded.
        self._refresh_pt_instr_visibility()

    def closeEvent(self, ev) -> None:  # noqa: N802
        # The window-corner X gets the same unsaved-changes guard as the
        # Close button (#49). Saves clear the flag first, so closing right
        # after Save As / Save & apply doesn't prompt.
        if not self._confirm_discard():
            ev.ignore()
            return
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(3000)
        self._clear_undo_history()
        self._preview_tmp.cleanup()
        super().closeEvent(ev)
