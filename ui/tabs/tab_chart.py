"""Tab 1: Chart Creation — Guided and Manual modes."""
from __future__ import annotations

import json
import re
import shlex
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QPalette
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from core.logger import get_logger
from core.preset_store import (
    load_presets as _load_tab_presets,
    reveal_in_file_manager,
    save_presets as _save_tab_presets,
    sidecar_path as _preset_sidecar_path,
    tab_dir,
)
from core.resource_path import resource_path
from data.patch_db import (
    EXCLUDED_PAPERS,
    EXTERNAL_INSTRUMENTS,
    I1PRO_DEFAULT_PRESET_KEY,
    INSTRUMENT_DEFAULT_MARGIN,
    INSTRUMENT_LABELS,
    PAPER_FALLBACK,
    PAPER_LABELS,
    PAPER_SIZES,
    i1_defaults_from_preset,
    query_patches,
)
from ui.dialogs.target_change_dialog import TargetChangeAction, TargetChangeDialog
from ui.fade_scroll import FadeScrollArea
from ui.parameter_widget import ParameterWidget
from ui.styles import SPEC_AMBER, SPEC_CYAN, SPEC_GREEN, SPEC_MAGENTA, SPEC_VIOLET
from ui.tab_header import TabHeader
from ui.builtin_preset_popup import BuiltinPresetButton, BuiltinPresetPopup
from ui.tiff_preview import TiffPreview
from ui.tooltip_button import InfoDialog, TooltipButton
from ui.widgets import NoScrollComboBox, NoScrollSpinBox, icc_profile_paths, make_browse_button, open_file_dialog, set_folder_icon, set_preset_icon
from workflow.i1profiler_export import EXTRA_INK, export_from_ti1, parse_ti1
from workflow.i1profiler_import import import_to_ti1
from workflow.chart_creator import (
    ChartCreator, ChartParams, guided_neutrals, GUIDED_NEUTRAL_BASE, REF_BUDGET,
)
from workflow.tiff_metadata import ALLOWED_LEFT_CLIP_PAPERS

if TYPE_CHECKING:
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings

log = get_logger(__name__)

# Built-in, read-only preset for the Create Chart → Manual presets dropdown.
# Unlike user presets (one .json file each under presets_dir()), this one is
# baked into the app: it can't be deleted, and selecting it loads a fixed
# patch set and lays it out with a fixed set of printtarg options. The combo
# entry is identified by its sentinel userData (TC918_PRESET_KEY) rather than
# its display text. Bundled charts are filed under
# assets/charts/<creator>/<colorspace>/<instrument>/<paper>/<target>/.
TC918_PRESET_KEY = "__chromiq_tc918_builtin__"
TC918_PRESET_LABEL = "★  i1Pro TC9.18 by Pharmacist  ·  built-in"
TC918_TI1_ASSET = "assets/charts/pharmacist/rgb/i1pro/a4/tc918/tc918.ti1"
TC918_TARGET_NAME = "tc918"
# Fixed printtarg layout for the TC9.18 preset (matches the Pharmacist recipe
# printtarg -ii1 -pA4 -t300 -L -m12 -M12 -b). -m drives both -m and -M in the
# UI; -t is the TIFF DPI; -b forces black & white (uncolored) spacers. -a is
# pinned to 1.0 *after* -i so it overrides the i1 instrument-default scale
# (0.95) the recipe doesn't want — a patch scale of 1.0 emits no -a flag.
TC918_PRINTTARG = {
    "-i": "i1",
    "-a": 1.0,
    "-p": "A4",
    "-t": 300,
    "-L": True,
    "-m": 12,
    "-b": True,
}

# ColorMunki built-in presets: plain parameter presets (normal targen→printtarg,
# no bundled .ti1). Each selects the ColorMunki and turns on Triple density, so
# printtarg lays the chart out with the denser i1Pro geometry (-ii1) and
# chart_creator rewrites the .ti2 TARGET_INSTRUMENT back to "X-Rite ColorMunki".
# They share one printtarg recipe and differ only in the targen patch counts
# below: (patches -f, white -e, black -B, grey-axis steps -g). Selecting one only
# loads the settings — the user reviews them and clicks Generate.
MUNKI324_PRESET_KEY = "__chromiq_munki324_builtin__"
MUNKI324_PRESET_LABEL = "★  ColorMunki 324 patch standard quality target by Pharmacist  ·  built-in"
MUNKI648_PRESET_KEY = "__chromiq_munki648_builtin__"
MUNKI648_PRESET_LABEL = "★  ColorMunki 648 patch high quality target by Pharmacist  ·  built-in"

# key -> (patches, white, black, grey_steps) for the shared ColorMunki recipe.
MUNKI_TARGEN = {
    MUNKI324_PRESET_KEY: (324, 2, 2, 16),
    MUNKI648_PRESET_KEY: (648, 4, 4, 64),
}

# Prebuilt-files built-in presets: a complete, pre-generated target (ti1 + ti2 +
# TIFFs) bundled in assets/. Selecting one prompts for a name, copies the bundled
# files into a fresh ~/ChromIQ/<name> folder (renamed to <name>…) and loads them.
# targen AND printtarg are skipped entirely — the param panels are greyed out
# while such a preset is active, because none of those options apply.
# The four "by Pharmacist" targets below are the full built-in line-up
# (two i1Pro, two ColorMunki) — every one a prebuilt-files preset.
# Labels follow the same convention as Knut's presets — instrument · paper +
# patch count + page count, then the set name + "by Pharmacist". (Patch width and
# orientation, which Knut's names carry, aren't stored for these pre-rendered
# charts, so they're omitted here.) The *_KEY is the stable identity — labels can
# change freely, keys must not.
TC924_PRESET_KEY = "__chromiq_tc924_builtin__"
TC924_PRESET_LABEL = "★  i1Pro · A4-924p-2pages TC9.24 by Pharmacist  ·  built-in"
ABW1110_PRESET_KEY = "__chromiq_abw1110_builtin__"
ABW1110_PRESET_LABEL = "★  i1Pro · A4-1110p-2pages ABW-optimized by Pharmacist  ·  built-in"
# TC9.18 extended-greys 1160-patch target, in A4 and US-Letter layouts. Same
# patch set, two page sizes — the paper is carried in the label so the pair is
# distinguishable in the dropdown and the overlay.
TC918EG_A4_PRESET_KEY = "__chromiq_tc918eg_a4_builtin__"
TC918EG_A4_PRESET_LABEL = "★  i1Pro · A4-1160p-2pages TC9.18 extended greys by Pharmacist  ·  built-in"
TC918EG_LETTER_PRESET_KEY = "__chromiq_tc918eg_letter_builtin__"
TC918EG_LETTER_PRESET_LABEL = "★  i1Pro · Letter-1160p-2pages TC9.18 extended greys by Pharmacist  ·  built-in"
TC300_PRESET_KEY = "__chromiq_tc300_builtin__"
TC300_PRESET_LABEL = "★  ColorMunki · A4-300p-1page TC3.00 by Pharmacist  ·  built-in"
ABW702_PRESET_KEY = "__chromiq_abw702_builtin__"
ABW702_PRESET_LABEL = "★  ColorMunki · A4-702p-2pages ABW-optimized by Pharmacist  ·  built-in"
# TC9.24 target laid out for the ColorMunki on A3 (single page, 924 patches).
TC924_CM_A3_PRESET_KEY = "__chromiq_tc924_cm_a3_builtin__"
TC924_CM_A3_PRESET_LABEL = "★  ColorMunki · A3-924p-1page TC9.24 by Pharmacist  ·  built-in"
# TC9.18 extended greys laid out for the ColorMunki on A3+ (single page, 1160 patches).
TC918EG_CM_A3_PRESET_KEY = "__chromiq_tc918eg_cm_a3_builtin__"
TC918EG_CM_A3_PRESET_LABEL = "★  ColorMunki · A3+-1160p-1page TC9.18 extended greys by Pharmacist  ·  built-in"

# key -> (asset stem under assets/charts, default target name). Charts are filed
# by creator/colorspace/instrument/paper/target; the stem locates <stem>.ti1,
# <stem>.ti2 and the <stem>_NN.tif page TIFFs inside that leaf folder.
PREBUILT_PRESETS = {
    TC924_PRESET_KEY:          ("assets/charts/pharmacist/rgb/i1pro/a4/tc924/tc924",            "tc924"),
    ABW1110_PRESET_KEY:        ("assets/charts/pharmacist/rgb/i1pro/a4/abw1110/abw1110",        "abw1110"),
    TC918EG_A4_PRESET_KEY:     ("assets/charts/pharmacist/rgb/i1pro/a4/tc918eg/tc918eg",        "tc918eg"),
    TC918EG_LETTER_PRESET_KEY: ("assets/charts/pharmacist/rgb/i1pro/letter/tc918eg/tc918eg",    "tc918eg-letter"),
    TC300_PRESET_KEY:          ("assets/charts/pharmacist/rgb/colormunki/a4/tc300/tc300",       "tc300"),
    ABW702_PRESET_KEY:         ("assets/charts/pharmacist/rgb/colormunki/a4/abw702/abw702",     "abw702"),
    TC924_CM_A3_PRESET_KEY:    ("assets/charts/pharmacist/rgb/colormunki/a3/tc924/tc924",       "tc924-a3"),
    TC918EG_CM_A3_PRESET_KEY:  ("assets/charts/pharmacist/rgb/colormunki/a3plus/tc918eg/tc918eg", "tc918eg-cm-a3"),
}


def _prebuilt_paper(key: str) -> str:
    """Page size a prebuilt preset is laid out for, read from its asset path.

    The asset stem is ``.../<instrument>/<paper>/<target>/<target>``, so the
    paper folder is the third path component from the end. Returned as a display
    label for the tooltip; unknown sizes fall through upper-cased."""
    stem = PREBUILT_PRESETS.get(key, ("",))[0]
    parts = stem.split("/")
    paper = parts[-3] if len(parts) >= 3 else ""
    return {"a4": "A4", "a3": "A3", "a3plus": "A3+", "letter": "US Letter"}.get(paper, paper.upper() or "A4")

# --- Knut's TC9.18 + Spyderprint-greys presets -----------------------------
# A family of built-in presets that all share ONE bundled 1168-patch .ti1
# (TC9.18 colour set + Spyderprint neutral ramp) and differ only in their
# printtarg layout — instrument, page size, patch scale, margin, spacer scale
# and random seed. Unlike the prebuilt-files presets, nothing is pre-rendered:
# picking one seeds the Manual printtarg panel and runs printtarg on the bundled
# .ti1 (the same ti1→printtarg path the "attach a .ti1" user presets use, via
# _preset_ti1_path), so the panels stay editable and only one small .ti1 ships.
KNUT_TI1_ASSET = "assets/charts/knut/rgb/tc918-spyderprint-1168p/1168p.ti1"
KNUT_PATCHES, KNUT_WHITE, KNUT_BLACK = 1168, 9, 8   # from the .ti1 header
KNUT_DPI = 200                                        # -T200 (16-bit) on every one
KNUT_SUFFIX = " TC9.18+Spyderprint Grays"             # common name tail
_KNUT_I1, _KNUT_CM = "i1", "CM"


@dataclass(frozen=True)
class _Ti1Preset:
    """One TC9.18+Spyderprint preset: a printtarg layout over the shared .ti1."""
    slug: str            # stable identity component (never change once shipped)
    name: str            # Knut's full chart name (display + default target name)
    instrument: str      # printtarg -i ("i1" | "CM")
    paper: str           # printtarg -p (named size or "WxH" in mm)
    patch_scale: float   # printtarg -a
    margin: int          # printtarg -m / -M
    pages: int           # informational (the page count in the name)
    double_density: bool = False        # printtarg -h (ColorMunki)
    spacer_scale: float | None = None   # printtarg -A (None → leave at default)
    seed: int | None = None             # printtarg -R (None → default randomise)

    @property
    def key(self) -> str:
        return f"__chromiq_knut_{self.slug}__"

    @property
    def combo_label(self) -> str:
        instr = "i1Pro" if self.instrument == _KNUT_I1 else "ColorMunki"
        return f"★  {instr} · {self.name}  ·  built-in"

    @property
    def overlay_label(self) -> str:
        return self.name  # the overlay already groups by instrument

    @property
    def default_target_name(self) -> str:
        if self.name.endswith(KNUT_SUFFIX):
            return self.name[: -len(KNUT_SUFFIX)]
        return self.name


# Named printtarg page sizes in mm (only those the presets use); custom sizes are
# given as "WxH" and parsed directly. Used to order the presets by paper size.
_PAPER_MM = {
    "A4": (210.0, 297.0), "A4R": (297.0, 210.0),
    "Letter": (215.9, 279.4), "LetterR": (279.4, 215.9),
    "A3": (297.0, 420.0), "A2": (420.0, 594.0),
}


def _paper_area_mm2(paper: str) -> float:
    """Sheet area in mm² for a printtarg -p value (named size or 'WxH')."""
    if "x" in paper:
        try:
            w, h = paper.split("x", 1)
            return float(w) * float(h)
        except ValueError:
            return 0.0
    dims = _PAPER_MM.get(paper)
    return dims[0] * dims[1] if dims else 0.0


def _paper_sort_key(paper: str) -> float:
    """Ordering key for "smallest sheet first".

    Area-based, except US Letter is nudged to sort *just after* A4. The two are
    within ~3% (Letter is marginally smaller), but the conventional order — and
    the one the Pharmacist presets already use — lists A4 first, so we match it
    rather than letting Letter jump ahead on raw area."""
    if paper in ("Letter", "LetterR"):
        return _paper_area_mm2("A4") + 1.0
    return _paper_area_mm2(paper)


# Knut's commands, transcribed (the trailing common suffix is added above):
#   i1Pro:      printtarg -v -P -ii1  -T200 -p<paper> -M8 -R<seed> -a<scale> -A0.6
#   ColorMunki: printtarg -v -P -iCM -h -T200 -p<paper> -a<scale> -M6
# ChromIQ emits -m<m> -M<m> together (functionally == Knut's lone -M, since
# printtarg's -m/-M write the same margin) and keeps the left clip border (no -L).
KNUT_PRESETS: list[_Ti1Preset] = [
    # i1Pro group — margin 8, spacer scale 0.6, seeded randomisation.
    _Ti1Preset("i1_a3_land_1p",  "A3-1168p-1page-w8.0mm-Landscape"     + KNUT_SUFFIX, _KNUT_I1, "420x297", 0.98,  8, 1, spacer_scale=0.6, seed=161),
    _Ti1Preset("i1_a4_2p",       "A4-1168p-2pages-w7.5mm-Portrait"     + KNUT_SUFFIX, _KNUT_I1, "A4",      0.929, 8, 2, spacer_scale=0.6, seed=161),
    _Ti1Preset("i1_a4_3p",       "A4-1168p-3pages-w8.5mm-Portrait"     + KNUT_SUFFIX, _KNUT_I1, "A4",      1.125, 8, 3, spacer_scale=0.6, seed=367),
    _Ti1Preset("i1_letter_2p",   "Letter-1168p-2pages-w7.0mm-Portrait" + KNUT_SUFFIX, _KNUT_I1, "Letter",  0.92,  8, 2, spacer_scale=0.6, seed=161),
    _Ti1Preset("i1_letter_3p",   "Letter-1168p-3pages-w8.5mm-Portrait" + KNUT_SUFFIX, _KNUT_I1, "Letter",  1.105, 8, 3, spacer_scale=0.6, seed=367),
    # ColorMunki Photo group — margin 6, double density (-h), default randomise.
    _Ti1Preset("cm_a4_5p",       "A4-1168p-5pages-w12.5mm-Portrait"      + KNUT_SUFFIX, _KNUT_CM, "A4",      0.93,  6, 5, double_density=True),
    _Ti1Preset("cm_letter_5p",   "Letter-1168p-5pages-w12.0mm-Portrait"  + KNUT_SUFFIX, _KNUT_CM, "Letter",  0.9,   6, 5, double_density=True),
    _Ti1Preset("cm_a3_port_2p",  "A3-1168p-2pages-w11.5mm-Portrait"      + KNUT_SUFFIX, _KNUT_CM, "297x420", 0.88,  6, 2, double_density=True),
    _Ti1Preset("cm_a3_land_2p",  "A3-1168p-2pages-w11.5mm-Landscape"     + KNUT_SUFFIX, _KNUT_CM, "420x297", 0.85,  6, 2, double_density=True),
    _Ti1Preset("cm_a3_port_3p",  "A3-1168p-3pages-w14.0mm-Portrait"      + KNUT_SUFFIX, _KNUT_CM, "297x420", 1.07,  6, 3, double_density=True),
    _Ti1Preset("cm_a3_land_3p",  "A3-1168p-3pages-w14.0mm-Landscape"     + KNUT_SUFFIX, _KNUT_CM, "420x297", 1.05,  6, 3, double_density=True),
    _Ti1Preset("cm_ledger_3p",   "Ledger-1168p-3pages-w13.5mm-Landscape" + KNUT_SUFFIX, _KNUT_CM, "432x279", 1.013, 6, 3, double_density=True),
    # -a1.06 (Knut's corrected value; the 1.076 he first sent overflowed to 4 pages).
    _Ti1Preset("cm_tabloid_3p",  "Tabloid-1168p-3pages-w14.0mm-Portrait" + KNUT_SUFFIX, _KNUT_CM, "279x432", 1.06,  6, 3, double_density=True),
    _Ti1Preset("cm_a2_port_1p",  "A2-1168p-1page-w12.5mm-Portrait"       + KNUT_SUFFIX, _KNUT_CM, "420x594", 0.92,  6, 1, double_density=True),
    _Ti1Preset("cm_a2_land_1p",  "A2-1168p-1page-w12.5mm-Landscape"      + KNUT_SUFFIX, _KNUT_CM, "594x420", 0.90,  6, 1, double_density=True),
    # -a1.29 (Knut's corrected value; the 1.4 he first sent overflowed to 3 pages).
    _Ti1Preset("cm_a2_port_2p",  "A2-1168p-2pages-w17.0mm-Portrait"      + KNUT_SUFFIX, _KNUT_CM, "420x594", 1.29,  6, 2, double_density=True),
    _Ti1Preset("cm_a2_land_2p",  "A2-1168p-2pages-w17.0mm-Landscape"     + KNUT_SUFFIX, _KNUT_CM, "594x420", 1.27,  6, 2, double_density=True),
]
KNUT_PRESETS_BY_KEY: dict[str, _Ti1Preset] = {p.key: p for p in KNUT_PRESETS}
KNUT_PRESET_KEYS = frozenset(KNUT_PRESETS_BY_KEY)


# Built-in presets can be parked here (shown greyed-out, non-selectable) pending
# a fix from their author; none are parked at the moment.
DISABLED_BUILTIN_PRESET_KEYS = frozenset()

# Every built-in (non-deletable) preset key — all four are prebuilt-files. Used
# to protect them from the delete button and to keep disk presets from shadowing
# them.
BUILTIN_PRESET_KEYS = frozenset(PREBUILT_PRESETS) | KNUT_PRESET_KEYS
BUILTIN_PRESET_LABELS = frozenset({
    TC924_PRESET_LABEL, ABW1110_PRESET_LABEL,
    TC918EG_A4_PRESET_LABEL, TC918EG_LETTER_PRESET_LABEL,
    TC300_PRESET_LABEL, ABW702_PRESET_LABEL,
    TC924_CM_A3_PRESET_LABEL, TC918EG_CM_A3_PRESET_LABEL,
}) | {p.combo_label for p in KNUT_PRESETS}

# Built-in presets grouped by the instrument they target — the single source of
# truth shared by the Manual presets dropdown (_populate_preset_combo) and the
# "Built-in presets" overlay (BuiltinPresetPopup). Each group is
# (instrument, [(combo_label, overlay_label, key), …]). The combo label is the
# full "★ … · built-in" string; the overlay groups by instrument so it shows the
# shorter label with the instrument prefix dropped.
# Order here is the single source of truth for BOTH the dropdown and the overlay
# (neither re-sorts) — ColorMunki first, then i1Pro.
# Knut's presets merged into their instrument group, below the Pharmacist ones,
# ordered by paper size (smallest sheet first). sorted() is stable, so presets on
# the same paper keep their registry order (e.g. 2-page before 3-page).
_KNUT_GROUP_ENTRIES = {
    grp: [(p.combo_label, p.overlay_label, p.key)
          for p in sorted((q for q in KNUT_PRESETS if q.instrument == instr),
                          key=lambda q: _paper_sort_key(q.paper))]
    for grp, instr in (("ColorMunki", _KNUT_CM), ("i1Pro", _KNUT_I1))
}
BUILTIN_PRESET_GROUPS: list[tuple[str, list[tuple[str, str, str]]]] = [
    ("ColorMunki", [
        (TC300_PRESET_LABEL,   "A4-300p-1page TC3.00 by Pharmacist",          TC300_PRESET_KEY),
        (ABW702_PRESET_LABEL,  "A4-702p-2pages ABW-optimized by Pharmacist",   ABW702_PRESET_KEY),
        (TC924_CM_A3_PRESET_LABEL, "A3-924p-1page TC9.24 by Pharmacist",       TC924_CM_A3_PRESET_KEY),
        (TC918EG_CM_A3_PRESET_LABEL, "A3+-1160p-1page TC9.18 extended greys by Pharmacist", TC918EG_CM_A3_PRESET_KEY),
        *_KNUT_GROUP_ENTRIES["ColorMunki"],
    ]),
    ("i1Pro", [
        (TC924_PRESET_LABEL,   "A4-924p-2pages TC9.24 by Pharmacist",          TC924_PRESET_KEY),
        (ABW1110_PRESET_LABEL, "A4-1110p-2pages ABW-optimized by Pharmacist",  ABW1110_PRESET_KEY),
        (TC918EG_A4_PRESET_LABEL,     "A4-1160p-2pages TC9.18 extended greys by Pharmacist",     TC918EG_A4_PRESET_KEY),
        (TC918EG_LETTER_PRESET_LABEL, "Letter-1160p-2pages TC9.18 extended greys by Pharmacist", TC918EG_LETTER_PRESET_KEY),
        *_KNUT_GROUP_ENTRIES["i1Pro"],
    ]),
]


# --- Override-checkbox copy (preset panels) --------------------------------
# Shown next to the "Edit patch recipe / page layout" checkboxes that unlock a
# preset's otherwise-greyed panels. Written for beginners: lead with the plain
# outcome, then the consequence of changing it.
_OVERRIDE_TARGEN_TIP = (
    "Edit the patch recipe (targen settings)\n\n"
    "This preset comes with a ready-made set of colour patches, so the targen "
    "settings above are locked. Tick this box only if you really want to change "
    "which colours get printed.\n\n"
    "Important: targen decides WHICH colours are on the chart. The moment you "
    "change anything here, ChromIQ can no longer reuse the preset's carefully "
    "chosen patches — it will build a brand-new set of colours from scratch. The "
    "chart is still perfectly valid, but it will NOT be the same as the preset, "
    "and the preset's hand-tuning no longer applies.\n\n"
    "Leave this unticked unless you specifically need a different patch set."
)
_OVERRIDE_PRINTTARG_TIP = (
    "Edit the page layout (printtarg settings)\n\n"
    "This preset is already arranged on the page for you, so the printtarg "
    "settings above are locked. Tick this box if you'd like to re-arrange the "
    "same patches differently — for example a different paper size, margin or "
    "patch size.\n\n"
    "Good news: changing only these layout settings keeps the preset's exact "
    "colour patches. ChromIQ simply re-lays that same set of colours onto the "
    "page using your new settings.\n\n"
    "(To change the colours themselves, use the \"Edit patch recipe\" box on the "
    "targen panel instead — but note that produces a different, non-matching set "
    "of patches.)"
)
# Pop-up shown the moment the user ticks an override box.
_OVERRIDE_TARGEN_POPUP_TITLE = "Editing the patch recipe"
_OVERRIDE_TARGEN_POPUP_BODY = (
    "You've unlocked the patch-recipe (targen) settings for this preset.\n\n"
    "What this means:\n"
    "The preset includes a carefully prepared set of colour patches. As long as "
    "you don't touch the targen settings, ChromIQ keeps using that exact set.\n\n"
    "The moment you change a targen value, ChromIQ can no longer reuse the "
    "preset's patches — when you click \"Generate Chart\" it will create a "
    "completely new set of colours from scratch. The new chart is perfectly "
    "valid, but it will be DIFFERENT from the preset, and the preset's careful "
    "tuning no longer applies.\n\n"
    "If that's what you want, go right ahead. If not, simply untick the box to "
    "keep the preset's original patches."
)
_OVERRIDE_PRINTTARG_POPUP_TITLE = "Editing the page layout"
_OVERRIDE_PRINTTARG_POPUP_BODY = (
    "You've unlocked the page-layout (printtarg) settings.\n\n"
    "Changing these re-arranges the SAME colour patches on the page — a "
    "different paper size, margins, patch size and so on. The colours "
    "themselves stay exactly as the preset intended, so this is safe to do.\n\n"
    "When you click \"Generate Chart\", ChromIQ re-lays the preset's patch set "
    "onto the page using your new layout settings.\n\n"
    "(If you also unlock and change the patch-recipe settings, that's different "
    "— it produces a new set of colours that won't match the preset.)"
)


def _value_compatible_with_pw(v: Any, pw: "ParameterWidget") -> bool:
    """True if v can be set on the widget without raising / warning.

    Used to suppress the noisy "set_value(-g, 'true')" warning that would
    otherwise fire while migrating a Windows-registry-corrupted legacy key.
    """
    t = getattr(pw, "_param", {}).get("type", "string")
    try:
        if t == "boolean":
            return v is not None
        if t in ("int",):
            int(v)
            return True
        if t in ("float",):
            float(v)
            return True
        return True
    except (TypeError, ValueError):
        return False


def _pw_settings_key(tool: str, flag: str) -> str:
    """Storage key for a tool parameter, case-disambiguated for Windows.

    QSettings on Windows uses HKCU which is case-insensitive, so the bare
    keys for -g (Grey Axis Steps, int) and -G (Good Mode, bool) collide and
    last-write-wins corrupts whichever was written first. Appending a one-char
    case marker after single-letter alpha flags eliminates the collision while
    leaving multi-character / non-alpha flags unchanged.
    """
    if len(flag) == 2 and flag.startswith("-") and flag[1].isalpha():
        return f"manual_{tool}_{flag}_{'u' if flag[1].isupper() else 'l'}"
    return f"manual_{tool}_{flag}"


def _extra_args_have_patch_source(extra: str) -> bool:
    """True if extra targen args contain a flag that produces patches on its own.

    targen needs at least one of -f, -g, -s, -c (preconditioning profile) or
    -m to produce a valid output. The first three live on dedicated widgets;
    this guard handles -c / -m / -V / -D buried in extra_targen_args.
    """
    if not extra:
        return False
    try:
        toks = shlex.split(extra)
    except ValueError:
        return False
    for tok in toks:
        if tok.startswith(("-c", "-V", "-D", "-m")):
            return True
    return False


class _ComboSeparatorDelegate(QStyledItemDelegate):
    """Paint insertSeparator() rows as a clear horizontal divider line.

    The default combo-popup separator is nearly invisible on ChromIQ's dark
    theme, and QSS ``::separator`` isn't honoured for combo views, so the line is
    drawn here. Its colour is derived from the active palette, so it stays
    visible in both the light and dark themes. Non-separator rows fall through to
    the default delegate, preserving bold/tooltip rendering of the built-ins."""

    _SEP_ROLE = Qt.ItemDataRole.AccessibleDescriptionRole

    def _is_separator(self, index) -> bool:
        return index.data(self._SEP_ROLE) == "separator"

    def paint(self, painter, option, index) -> None:
        if self._is_separator(index):
            line = QColor(option.palette.color(QPalette.ColorRole.Text))
            line.setAlpha(70)
            painter.save()
            painter.setPen(line)
            y = option.rect.center().y()
            painter.drawLine(option.rect.left() + 10, y, option.rect.right() - 10, y)
            painter.restore()
            return
        super().paint(painter, option, index)

    def sizeHint(self, option, index) -> QSize:
        if self._is_separator(index):
            return QSize(0, 11)
        return super().sizeHint(option, index)


class TabChart(QWidget):
    """Step 1: create targen/printtarg test chart."""

    # (list[Path] tiffs, Path ti2, bool is_external_workflow)
    # is_external_workflow is True for i1iSis (i1Profiler hand-off); main_window
    # uses it to skip routing TIFFs/TI2 to the Print and Measure tabs.
    chart_finished  = pyqtSignal(object, object, bool)
    target_started  = pyqtSignal()

    def __init__(
        self,
        runner: "ArgyllRunner",
        file_mgr: "FileManager",
        settings: "AppSettings",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._runner  = runner
        self._file_mgr = file_mgr
        self._settings = settings
        self._creator  = ChartCreator(runner, file_mgr, settings)
        self._params   = self._load_yaml_params()
        # Sanitised target name of the most recent generate. Lets _on_generate
        # detect a name change (rename) away from an already-created target.
        self._last_target_name = ""
        self._preconditioning_from_dialog = False
        # Run that produced the profile the user clicked "Use as pre-conditioning"
        # on. Captured at apply_preconditioning time; consumed at Generate-click
        # to seed a fresh run (Project.new_run) from it.
        self._precond_parent_run_id: str | None = None
        # TC9.18 built-in preset state. While active, "Generate Chart" reproduces
        # the bundled patch set (printtarg-only) instead of running targen, unless
        # the user has since changed a targen-affecting setting (see
        # _targen_signature). Cleared when another preset / Default is
        # chosen, or a different .ti1 is loaded.
        self._tc918_active = False
        self._tc918_targen_sig: list | None = None
        # True while one of Knut's TC9.18+Spyderprint presets is the active source.
        # While active and the targen settings are untouched (see _knut_targen_sig),
        # "Generate" re-lays-out the bundled 1168-patch .ti1 with printtarg only;
        # changing a targen setting opts into a fresh targen run. Tracked so the
        # forced printtarg overrides (-a/-m/-A/-R/-P/-L/-h) revert on leave, exactly
        # like _tc918_active, so they don't bleed into the next preset.
        self._knut_active = False
        self._knut_targen_sig: list | None = None
        # Prebuilt-files built-in preset state. While active the targen/printtarg
        # panels are greyed out and "Generate Chart" re-copies the bundled files
        # instead of running any tool. Cleared when another preset / Default is
        # chosen or a .ti1 is loaded.
        self._prebuilt_active = False
        self._prebuilt_key: str | None = None
        # Snapshots of the targen / printtarg controls taken when a prebuilt-files
        # preset is selected. While active, "Generate Chart" decides what to do by
        # comparing the live controls against these: targen changed → fresh targen
        # run (different patches); else printtarg changed → re-lay-out the bundled
        # .ti1 (same patches, new layout); else copy the bundled files verbatim.
        self._prebuilt_targen_sig: list | None = None
        self._prebuilt_printtarg_sig: list | None = None
        # Absolute path of the .ti1 backing the chart currently shown (set after a
        # successful generate / load). Offered for attachment in the Save Preset
        # dialog.
        self._current_ti1_path: Path | None = None
        # When a user preset that bundles a .ti1 is selected, this points at that
        # preset's sidecar .ti1 so "Generate Chart" skips targen and lays it out
        # with printtarg only. Cleared for presets without an attached patch set.
        # _preset_ti1_targen_sig snapshots the targen controls at selection so the
        # targen-override checkbox can opt into a fresh targen run, like the
        # built-in ti1 presets.
        self._preset_ti1_path: Path | None = None
        self._preset_ti1_targen_sig: list | None = None
        # Override-checkbox widgets (created in _make_manual_panel). Shown only
        # while a preset that supplies a fixed patch set / layout is active; ticking
        # one re-enables the otherwise-greyed targen / printtarg panel.
        self._override_targen_check: QCheckBox | None = None
        self._override_printtarg_check: QCheckBox | None = None
        self._override_targen_row: QWidget | None = None
        self._override_printtarg_row: QWidget | None = None
        self._manual_targen_content: list[QWidget] = []
        self._manual_printtarg_content: list[QWidget] = []
        # Last committed preset-combo index. Lets a cancelled built-in prompt
        # revert the dropdown to the prior selection.
        self._last_preset_index = 0

        self._build_ui()
        self._restore_defaults()

    # ------------------------------------------------------------------
    # UI build
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setHandleWidth(4)

        # Left: controls
        left = QWidget(self)
        self._left_panel = left
        left.setFixedWidth(580)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 12, 16, 12)
        left_layout.setSpacing(8)

        left_layout.addWidget(TabHeader(
            "STEP 01 · GENERATE TARGET", "Create test chart", "#ff4573", left,
            tooltip_title="Step 1 — Make a test chart",
            tooltip_body=(
                "This is where you design the sheet of colour patches your printer "
                "will print. The patches are how ChromIQ later \"learns\" how your "
                "printer reproduces colour.\n\n"
                "Before you start:\n"
                "• Pick the printer and paper you actually want to profile — the "
                "profile will only be accurate for that exact combination.\n"
                "• Have a rough idea of how careful you want to be. More patches = "
                "more accuracy, but also more ink and paper.\n\n"
                "You have three ways to make a chart — from quickest to most "
                "hands-on:\n\n"
                "★  Built-in presets — the star button at the right end of the "
                "Guided / Manual switch.\n"
                "Click it to open a little menu of ready-made, professionally tuned "
                "charts, grouped by the measuring instrument they're made for "
                "(i1Pro or ColorMunki). Pick one and ChromIQ simply asks you for a "
                "name, then drops the finished chart straight in — there are no "
                "settings to understand and nothing to get wrong. This is the "
                "fastest way to a known-good target, and a great choice if you just "
                "want a reliable chart without thinking about the details. (The very "
                "same presets also live at the bottom of Manual mode's \"Presets\" "
                "dropdown, in case you'd rather find them there.)\n\n"
                "• Guided mode picks sensible patch counts for you based on your "
                "paper size and instrument. Recommended if you're new but still want "
                "to choose your own paper, instrument and quality level.\n\n"
                "• Manual mode exposes every option. Use it once you know what each "
                "setting does and want full control.\n\n"
                "Whichever route you take, click \"Generate\" (or pick a built-in "
                "preset) to create the test chart. You'll get a TIFF image (the "
                "printable chart) and a .ti2 file (the recipe ChromIQ uses later to "
                "read it back).\n\n"
                "Next step: print the TIFF on tab 2."
            ),
        ))

        # Mode switcher (wrapped in a widget so it can be hidden in calibration mode)
        self._mode_row_widget = QWidget(left)
        mode_row = QHBoxLayout(self._mode_row_widget)
        # The panels below sit in a scroll area, so their group boxes are inset on
        # the right by the (Fusion) scrollbar width + the inner 4px margin. Inset
        # the mode row by roughly the same so the built-in-presets button lines up
        # with the section outlines below — less 14px so it sits a touch right.
        from PyQt6.QtWidgets import QStyle
        _sb = self.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
        mode_row.setContentsMargins(0, 0, max(0, _sb - 10), 0)
        _mode_font = QFont()
        _mode_font.setFamilies(["Menlo", "Consolas", "Courier New", "monospace"])
        _mode_font.setPointSize(11)
        _mode_font.setWeight(QFont.Weight.Bold)
        self._guided_btn = QPushButton("GUIDED", self)
        self._guided_btn.setCheckable(True)
        self._guided_btn.setChecked(True)
        self._guided_btn.setObjectName("mode_btn")
        self._guided_btn.setFont(_mode_font)
        self._manual_btn = QPushButton("MANUAL", self)
        self._manual_btn.setCheckable(True)
        self._manual_btn.setObjectName("mode_btn")
        self._manual_btn.setFont(_mode_font)
        self._guided_btn.clicked.connect(lambda: self._switch_mode("guided"))
        self._manual_btn.clicked.connect(lambda: self._switch_mode("manual"))
        mode_row.addWidget(self._guided_btn)
        mode_row.addWidget(self._manual_btn)
        mode_row.addStretch()
        # Far-right star button: opens the Built-in presets overlay, listing the
        # bundled prebuilt charts grouped by instrument. Picking one runs the
        # exact same flow as choosing it in the Manual presets dropdown.
        self._builtin_preset_btn = BuiltinPresetButton(self._mode_row_widget)
        self._builtin_preset_btn.clicked.connect(self._open_builtin_preset_overlay)
        mode_row.addWidget(self._builtin_preset_btn)
        left_layout.addWidget(self._mode_row_widget)

        # Stacked panel
        self._stack = QStackedWidget(self)
        self._guided_panel = self._make_guided_panel()
        self._manual_panel = self._make_manual_panel()
        self._stack.addWidget(self._guided_panel)
        self._stack.addWidget(self._manual_panel)
        left_layout.addWidget(self._stack, stretch=1)

        # Bottom buttons
        btn_row = QHBoxLayout()
        self._generate_btn = QPushButton("Generate Chart", self)
        self._generate_btn.setObjectName("primary")
        self._generate_btn.setFixedHeight(36)
        self._generate_btn.clicked.connect(self._on_generate)

        self._load_ti1_btn = QPushButton("Load patch set…", self)
        self._load_ti1_btn.setFixedHeight(36)
        self._load_ti1_btn.setToolTip(
            "Load an existing patch set and lay it out (targen is skipped).\n"
            "Accepts an Argyll .ti1, or an i1Profiler RGB patch set "
            "(.pxf or a CGATS .txt) — i1Profiler files are converted to .ti1 "
            "automatically."
        )
        set_folder_icon(self._load_ti1_btn, "folder_create")
        self._load_ti1_btn.clicked.connect(self._on_load_ti1)

        self._save_defaults_btn = QPushButton("Save as Defaults", self)
        self._save_defaults_btn.setFixedHeight(36)
        self._save_defaults_btn.clicked.connect(self._on_save_defaults)

        btn_row.addWidget(self._generate_btn)
        btn_row.addWidget(self._load_ti1_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._save_defaults_btn)
        left_layout.addLayout(btn_row)

        # Log output
        from PyQt6.QtWidgets import QPlainTextEdit
        self._log = QPlainTextEdit(self)
        self._log.setObjectName("log")
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(67)
        self._log.setPlaceholderText("Output will appear here…")
        left_layout.addWidget(self._log)

        # Status bar (replaces main-window status bar)
        self._status_bar_lbl = QLabel("", left)
        self._status_bar_lbl.setWordWrap(True)
        self._status_bar_lbl.setVisible(False)
        left_layout.addWidget(self._status_bar_lbl)

        splitter.addWidget(left)

        # Right: TIFF preview
        right = QWidget(self)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 12)
        right_layout.setSpacing(0)
        self._preview = TiffPreview(right)
        self._preview.set_caption("CHART PREVIEW")
        right_layout.addWidget(self._preview, stretch=1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter)

    # ------------------------------------------------------------------
    # Guided panel
    # ------------------------------------------------------------------

    def _make_guided_panel(self) -> QWidget:
        outer = QWidget(self)
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = FadeScrollArea(outer)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(8)

        # Working folder / target name
        folder_grp = QGroupBox("Output", inner)
        folder_layout = QVBoxLayout(folder_grp)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Target name:", inner))
        self._target_name_edit = self._make_lineedit("", inner)
        # Live-update the guided command preview as the user types.
        self._target_name_edit.textChanged.connect(self._update_patch_count)
        name_row.addWidget(self._target_name_edit, stretch=1)
        name_row.addWidget(TooltipButton(
            "Target Name",
            "A short, descriptive name for this profiling session.\n\n"
            "This name is used for the output folder and all generated files "
            "(chart, TIFF, measurements, ICC profile) throughout the entire workflow. "
            "Choose a name that lets you identify the correct files for your printer "
            "and paper combination at a glance.\n\n"
            "Tip: combine your printer model, paper type, and instrument — "
            "e.g. Canon_Pro1000_Baryta_i1Pro3. Use underscores or dashes instead of spaces.",
            inner,
            min_width=540,
        ))
        folder_layout.addLayout(name_row)
        self._target_name_hint = QLabel("", inner)
        self._target_name_hint.setWordWrap(True)
        self._target_name_hint.setStyleSheet("color: #d08a3a; font-size: 11px;")
        self._target_name_hint.setVisible(False)
        folder_layout.addWidget(self._target_name_hint)
        self._target_name_edit.editingFinished.connect(
            lambda: self._clean_target_name_field(
                self._target_name_edit, self._target_name_hint
            )
        )
        layout.addWidget(folder_grp)

        # Instrument
        instr_grp = QGroupBox("Measurement Instrument", inner)
        instr_layout = QVBoxLayout(instr_grp)
        instr_layout.setSpacing(6)
        row = QHBoxLayout()
        instr_label = QLabel("Instrument:", inner)
        row.addWidget(instr_label)
        self._instr_combo = NoScrollComboBox(inner)
        # External-workflow instruments (i1iSis) are intentionally absent from
        # Guided mode: Guided's job is to optimise the chart layout for the
        # instrument, but for these devices the layout is recomputed by an
        # external tool (i1Profiler) — so there's nothing to optimise here.
        for code, label in INSTRUMENT_LABELS.items():
            if code in EXTERNAL_INSTRUMENTS:
                continue
            self._instr_combo.addItem(label, code)
        self._instr_combo.currentIndexChanged.connect(self._update_patch_count)
        self._instr_combo.currentIndexChanged.connect(self._update_dd_visibility)
        self._instr_combo.currentIndexChanged.connect(self._rebuild_paper_combo)
        row.addWidget(self._instr_combo, stretch=1)
        row.addWidget(TooltipButton(
            "Measurement Instrument",
            "Tells the chart generator which spectrophotometer you will use to read "
            "the printed chart. The patch grid is built around that instrument's "
            "strip width, patch size and spacing — so getting this right is "
            "essential.\n\n"
            "  •  i1Pro / i1Pro 2 / i1Pro 3 — handheld strip reader, the most "
            "common choice. Reads a column of patches in one sweep.\n\n"
            "  •  i1Pro 3 Plus — larger-aperture version of the i1Pro 3. Reads "
            "bigger patches, so far fewer fit per sheet (~5× less than the "
            "regular i1Pro).\n\n"
            "  •  ColorMunki / i1Studio / ColorChecker Studio — entry-level "
            "device. Reads one patch at a time on its own; with the optional "
            "measuring rig it pairs them up (see the Double Density option).\n\n"
            "  •  SpectroScan — flatbed XY scanner. A motorised arm reads each "
            "patch individually, so it packs far more colours per sheet than any "
            "strip reader.\n\n"
            "Picking the wrong instrument produces a chart your device cannot "
            "align to or read reliably — you'll see \"patches not found\" or "
            "alignment errors when measuring.\n\n"
            "In Guided mode the layout adapts to this choice automatically.",
            inner,
            min_width=600,
        ))
        instr_layout.addLayout(row)

        # Double density / Triple density (CM only — mutually exclusive)
        dd_row = QHBoxLayout()
        # "For rig:" prefix aligns the dd checkbox with the combobox above —
        # both density options require the ColorMunki measuring rig accessory.
        # Shown only when ColorMunki is selected (hidden for SpectroScan's
        # hexagon-patches reuse of the same checkbox).
        self._for_rig_label = QLabel("For rig:", inner)
        self._for_rig_label.setMinimumWidth(instr_label.sizeHint().width())
        dd_row.addWidget(self._for_rig_label)
        self._dd_check = QCheckBox("Double density", inner)
        self._dd_check.toggled.connect(self._update_patch_count)
        self._dd_check.toggled.connect(self._on_guided_dd_toggled)
        self._dd_tooltip = TooltipButton(
            "Double Density (-h)",
            "Doubles the number of patches that fit in each measurement strip when "
            "using a ColorMunki / i1Studio / ColorChecker Studio.\n\n"
            "REQUIRES the physical measuring rig accessory — a clear plastic guide "
            "that mounts the instrument over the chart. Without the rig the device "
            "cannot align to the tighter patch spacing and will misread.\n\n"
            "With the rig you get roughly twice as many patches per page, which "
            "means either a more detailed profile from the same number of sheets, "
            "or the same profile quality on fewer sheets. Recommended for anyone "
            "with the rig — it's a strict upgrade on patch density.\n\n"
            "Has no effect on i1Pro, i1Pro 3 Plus or SpectroScan — the option is "
            "hidden when those are selected.",
            inner,
            min_width=600,
        )
        self._td_check = QCheckBox("Triple density", inner)
        self._td_check.toggled.connect(self._update_patch_count)
        self._td_check.toggled.connect(self._on_guided_td_toggled)
        self._td_tooltip = TooltipButton(
            "Triple Density (i1Pro layout emulation)",
            "ColorMunki + rig only. The chart is generated with the i1Pro strip "
            "layout (tighter, smaller patches than a native ColorMunki chart), "
            "then the produced .ti2 is rewritten so chartread still talks to "
            "your ColorMunki. Result: roughly 3× the patch count of a plain "
            "ColorMunki chart at the same paper size — a more detailed profile "
            "from the same number of sheets, or the same profile quality on far "
            "fewer sheets.\n\n"
            "REQUIRES the physical measuring rig accessory. Without the rig the "
            "ColorMunki cannot track the tighter i1-style strips.\n\n"
            "Mutually exclusive with Double density — pick one or the other.\n\n"
            "Has no effect on i1Pro, i1Pro 3 Plus or SpectroScan — the option is "
            "hidden when those are selected.",
            inner,
            min_width=600,
        )
        dd_row.addWidget(self._dd_check)
        dd_row.addWidget(self._dd_tooltip)
        dd_row.addSpacing(20)
        dd_row.addWidget(self._td_check)
        dd_row.addWidget(self._td_tooltip)
        dd_row.addStretch()
        instr_layout.addLayout(dd_row)
        layout.addWidget(instr_grp)

        # Paper
        paper_grp = QGroupBox("Paper", inner)
        paper_layout = QVBoxLayout(paper_grp)
        paper_row = QHBoxLayout()
        paper_row.addWidget(QLabel("Paper size:", inner))
        self._paper_combo = NoScrollComboBox(inner)
        self._paper_combo.currentIndexChanged.connect(self._update_patch_count)
        # Paper changes also affect ChromIQ-style gating, which decides whether
        # the guided -L checkbox is visible.
        self._paper_combo.currentIndexChanged.connect(self._update_dd_visibility)
        paper_row.addWidget(self._paper_combo, stretch=1)
        paper_row.addWidget(TooltipButton(
            "Paper Size",
            "Sets the dimensions of each sheet in the printed chart. The chart "
            "always fills the page edge to edge — bigger paper fits more "
            "patches, which means a more detailed profile from fewer sheets.\n\n"
            "Pick the same size you will actually print on, including its "
            "orientation. Strip readers (i1Pro family) read top-to-bottom, so:\n\n"
            "  •  Portrait — longer strips, fewer of them. Standard choice.\n\n"
            "  •  Landscape — shorter strips, more of them. Use this when your "
            "printer feeds landscape more reliably, or when a portrait sheet "
            "would leave the last strip too close to the paper edge.\n\n"
            "Some paper sizes are hidden depending on the selected instrument:\n\n"
            "  •  A3 Portrait is hidden for i1Pro — the landscape variant fits "
            "~43% more patches.\n\n"
            "  •  Small photo formats (5×7\", 4×6\") are hidden for i1Pro 3 "
            "Plus — its large patches don't leave a usable profile on those.\n\n"
            "If you change paper size mid-workflow, the recommended patch count "
            "and page count update automatically.",
            inner,
            min_width=600,
        ))
        paper_layout.addLayout(paper_row)
        layout.addWidget(paper_grp)

        # Pages + left border
        pages_grp = QGroupBox("Chart Size", inner)
        pages_layout = QVBoxLayout(pages_grp)
        pages_layout.setSpacing(6)

        pages_row = QHBoxLayout()
        pages_row.addWidget(QLabel("Number of pages:", inner))
        self._pages_spin = NoScrollSpinBox(inner)
        self._pages_spin.setRange(1, 20)
        self._pages_spin.setValue(1)
        self._pages_spin.valueChanged.connect(self._update_patch_count)
        pages_row.addWidget(self._pages_spin)
        pages_row.addStretch()
        pages_row.addWidget(TooltipButton(
            "Number of Pages",
            "How many physical sheets the chart spans. Each sheet is filled with "
            "as many patches as fit for the selected paper, instrument and layout "
            "— so total patches = patches-per-page × pages.\n\n"
            "More pages means more colour samples, which produces a more accurate "
            "profile. The trade-off is more ink, more paper and a longer reading "
            "session. Rough guide:\n\n"
            "  •  1 page — quick check or single-sheet workflows (~500 patches on "
            "A4 with an i1Pro). Fine for casual profiling.\n\n"
            "  •  2-3 pages — recommended for everyday photo printing. Good "
            "balance of accuracy versus effort.\n\n"
            "  •  4-5+ pages — professional or fine-art workflows where the "
            "profile needs to nail tricky tonal transitions and out-of-gamut "
            "colours.\n\n"
            "How many patches you actually need depends on your printer's colour "
            "gamut, ink set and how non-linear it behaves. When in doubt, more is "
            "better.",
            inner,
            min_width=600,
        ))
        pages_layout.addLayout(pages_row)

        lb_row = QHBoxLayout()
        self._lb_check = QCheckBox("Suppress left clip border (-L)", inner)
        self._lb_check.setChecked(True)
        self._lb_check.toggled.connect(self._update_patch_count)
        self._lb_tooltip = TooltipButton(
            "Suppress Left Clip Border (-L)",
            "Removes the left-edge paper-clip border, gaining ~15 mm for extra patches.\n"
            "Enable unless you use a physical page-clamp jig.  Recommended: ON.",
            inner,
        )
        self._nsl_check = QCheckBox("Don't limit strip length (-P)", inner)
        self._nsl_check.toggled.connect(self._update_patch_count)
        self._nsl_tooltip = TooltipButton(
            "Don't Limit Strip Length (-P)",
            "Removes printtarg's built-in strip-length cap (~250 mm) so each "
            "measurement strip runs full-bleed across the paper.\n\n"
            "Why it helps:\n"
            "On larger papers (A2, A3+, 11×17, Legal, A3-landscape) the cap "
            "ends strips early — well before the page edge — and printtarg "
            "rebalances the layout to keep strips equal-length. With -P the "
            "strips can use the full paper width/height, so noticeably more "
            "patches fit per sheet — up to ~2.5× more on A2, smaller gains "
            "on A4 (where the cap barely bit anyway).\n\n"
            "Trade-off:\n"
            "Long strips take longer to read in one sweep. Most i1Pro / "
            "i1Pro 3 / i1Pro 3 Plus users will be fine — modern hardware "
            "tracks long strips reliably. If you have an older instrument "
            "that struggles with strips near the paper edge, leave this off.\n\n"
            "Only affects i1Pro family strip readers. Hidden for ColorMunki "
            "(per-patch reader) and SpectroScan (XY flatbed) — -P has no "
            "effect on either layout.",
            inner,
            min_width=600,
        )
        lb_row.addWidget(self._lb_check)
        lb_row.addSpacing(10)
        lb_row.addWidget(self._lb_tooltip)
        # Push the -P option to the right edge so its tooltip icon lines up
        # directly under the "Number of pages" tooltip in the row above.
        lb_row.addStretch()
        lb_row.addWidget(self._nsl_check)
        lb_row.addSpacing(10)
        lb_row.addWidget(self._nsl_tooltip)
        pages_layout.addLayout(lb_row)
        layout.addWidget(pages_grp)

        # Refinement / pre-conditioning (optional second-pass profile)
        precond_grp = QGroupBox("Refinement (Optional)", inner)
        precond_row = QHBoxLayout(precond_grp)
        precond_row.setSpacing(6)

        self._guided_precond_check = QCheckBox("Refinement profile", inner)
        self._guided_precond_check.toggled.connect(self._on_guided_precond_toggled)
        precond_row.addWidget(self._guided_precond_check)

        self._guided_precond_path = QLineEdit(inner)
        self._guided_precond_path.setReadOnly(True)
        self._guided_precond_path.setPlaceholderText("No profile selected")
        self._guided_precond_path.setEnabled(False)
        precond_row.addWidget(self._guided_precond_path, stretch=1)

        self._guided_precond_browse = make_browse_button(
            inner, "Select pre-conditioning profile", icon="folder_create",
        )
        self._guided_precond_browse.setEnabled(False)
        self._guided_precond_browse.clicked.connect(self._on_guided_precond_browse)
        precond_row.addWidget(self._guided_precond_browse)

        precond_row.addWidget(TooltipButton(
            "Refinement Profile (Pre-conditioning)",
            "Use this to make a second, noticeably better profile after you have "
            "already built and confirmed a working one for the same printer + paper.\n\n"
            "How it helps:\n"
            "Your first profile tells ChromIQ which colours your printer gets right "
            "and which it struggles with. When you turn this option on, ChromIQ uses "
            "that knowledge to place the new test patches more cleverly — sampling "
            "more in the regions your printer reproduces least accurately, and fewer "
            "in the regions it already nails. The end result is a profile that is "
            "more accurate where it matters, without needing more patches overall.\n\n"
            "When to use it:\n"
            "• You already have a first ICC profile (.icc or .icm) built from this "
            "same printer + paper combination.\n"
            "• You want to invest one more round of printing and measuring to get a "
            "noticeably better profile, especially for tricky papers (matte, baryta, "
            "fine-art).\n\n"
            "When NOT to use it:\n"
            "• On a first-ever profile for this paper — leave this off and just "
            "build the normal way.\n"
            "• If you don't have a working profile yet for this exact paper/printer.\n\n"
            "Tip: the more pages you print on the refinement pass, the more benefit "
            "the cleverer patch placement gives you.",
            inner,
            min_width=580,
        ))

        layout.addWidget(precond_grp)

        # Patch count display
        count_grp = QGroupBox("Calculated Patches", inner)
        # Only override what differs from the global QGroupBox QSS (zero top-padding
        # so the big number sits tight under the title). Border + title color come
        # from the active theme.
        count_grp.setStyleSheet("QGroupBox { padding-top: 0px; }")
        count_layout = QVBoxLayout(count_grp)
        count_layout.setContentsMargins(8, 0, 8, 12)
        count_layout.setSpacing(4)

        self._patch_count_lbl = QLabel("—", inner)
        self._patch_count_lbl.setObjectName("patch_count")
        self._patch_count_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._patch_count_lbl.setStyleSheet(
            "background: transparent;"
            " font-family: Georgia; font-size: 56px;"
        )
        count_font = QFont()
        count_font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 85)
        self._patch_count_lbl.setFont(count_font)
        count_layout.addWidget(self._patch_count_lbl)

        self._patch_detail_lbl = QLabel("", inner)
        self._patch_detail_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._patch_detail_lbl.setStyleSheet(
            "color: #808080; background: transparent;"
            " font-family: Menlo; font-size: 9px; font-weight: 300;"
        )
        count_layout.addWidget(self._patch_detail_lbl)

        # 5-segment spectrum bar, centered
        bar_row = QHBoxLayout()
        bar_row.setContentsMargins(0, 6, 0, 0)
        bar_row.setSpacing(0)
        bar_row.addStretch()
        for _color in (SPEC_MAGENTA, SPEC_AMBER, SPEC_GREEN, SPEC_CYAN, SPEC_VIOLET):
            _seg = QFrame(inner)
            _seg.setFixedSize(22, 2)
            _seg.setStyleSheet(f"background-color: {_color}; border: none;")
            bar_row.addWidget(_seg)
        bar_row.addStretch()
        count_layout.addLayout(bar_row)

        layout.addWidget(count_grp)

        # Hidden-defaults info box
        self._guided_info_lbl = QLabel("", inner)
        self._guided_info_lbl.setObjectName("info")
        self._guided_info_lbl.setWordWrap(True)
        layout.addWidget(self._guided_info_lbl)

        layout.addStretch()
        scroll.setWidget(inner)
        outer_layout.addWidget(scroll)
        return outer

    # ------------------------------------------------------------------
    # Manual panel
    # ------------------------------------------------------------------

    def _make_manual_panel(self) -> QWidget:
        w = QWidget(self)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Calibration target option (hidden until calibration mode is enabled)
        self._cal_target_grp = QGroupBox("Calibration Target", w)
        cal_tgt_layout = QVBoxLayout(self._cal_target_grp)
        cal_tgt_row = QHBoxLayout()
        self._cal_target_check = QCheckBox("Create target for calibration", w)
        cal_tgt_row.addWidget(self._cal_target_check)
        cal_tgt_row.addStretch()
        cal_tgt_row.addWidget(TooltipButton(
            "Create Target for Calibration",
            "Use this before running printcal to create a printer linearisation curve.\n\n"
            "When enabled:\n"
            "  • Output files are prefixed with 'cal_' (e.g. cal_MyChart.ti1)\n"
            "  • Patch count is set to 0 (auto), white and black patches set to 0\n"
            "  • Single channel steps set to 20, randomisation disabled\n"
            "  • Good distribution (-G) is disabled\n\n"
            "Generate the chart, print it, and measure it. The resulting cal_*.ti3\n"
            "file is automatically routed to the Create Calibration File module\n"
            "in the Calibration & Profiling tab.\n\n"
            "Existing cal_* files in your working folder are preserved when this\n"
            "option is OFF, so your .cal file survives the next chart generation.",
            w,
            min_width=560,
        ))
        cal_tgt_layout.addLayout(cal_tgt_row)

        self._cal_status_lbl = QLabel("", w)
        self._cal_status_lbl.setWordWrap(True)
        self._cal_status_lbl.setStyleSheet("color: #56d6a5; font-size: 11px;")
        self._cal_status_lbl.setVisible(False)
        cal_tgt_layout.addWidget(self._cal_status_lbl)

        self._cal_target_grp.setVisible(False)
        layout.addWidget(self._cal_target_grp)

        # Output (target name)
        output_grp = QGroupBox("Output", w)
        output_layout = QVBoxLayout(output_grp)
        # Shared label width keeps the "Target name:" and "Chart notes:"
        # input fields aligned vertically.
        _OUTPUT_LBL_W = 96
        name_row = QHBoxLayout()
        _name_lbl = QLabel("Target name:", w)
        _name_lbl.setFixedWidth(_OUTPUT_LBL_W)
        name_row.addWidget(_name_lbl)
        self._manual_target_name_edit = self._make_lineedit("", w)
        # Live-update the manual command preview as the user types.
        self._manual_target_name_edit.textChanged.connect(
            self._refresh_manual_command_preview
        )
        name_row.addWidget(self._manual_target_name_edit, stretch=1)
        name_row.addWidget(TooltipButton(
            "Target Name",
            "A short, descriptive name for this profiling session.\n\n"
            "This name is used for the output folder and all generated files "
            "(chart, TIFF, measurements, ICC profile) throughout the entire workflow. "
            "Choose a name that lets you identify the correct files for your printer "
            "and paper combination at a glance.\n\n"
            "Tip: combine your printer model, paper type, and instrument — "
            "e.g. Canon_Pro1000_Baryta_i1Pro3. Use underscores or dashes instead of spaces.",
            w,
            min_width=540,
        ))
        output_layout.addLayout(name_row)
        self._manual_target_name_hint = QLabel("", w)
        self._manual_target_name_hint.setWordWrap(True)
        self._manual_target_name_hint.setStyleSheet("color: #d08a3a; font-size: 11px;")
        self._manual_target_name_hint.setVisible(False)
        output_layout.addWidget(self._manual_target_name_hint)
        self._manual_target_name_edit.editingFinished.connect(
            lambda: self._clean_target_name_field(
                self._manual_target_name_edit, self._manual_target_name_hint
            )
        )

        # Chart notes row — wrapped in a QWidget so it can be hidden when
        # ChromIQ-style clipping border is on (the right margin it targets
        # gets pushed off-page by the patch shift).
        self._manual_chart_notes_row = QWidget(w)
        m_notes_row = QHBoxLayout(self._manual_chart_notes_row)
        m_notes_row.setContentsMargins(0, 0, 0, 0)
        _notes_lbl = QLabel("Chart notes:", self._manual_chart_notes_row)
        _notes_lbl.setFixedWidth(_OUTPUT_LBL_W)
        m_notes_row.addWidget(_notes_lbl)
        self._manual_chart_notes_edit = self._make_lineedit("", self._manual_chart_notes_row)
        self._manual_chart_notes_edit.setPlaceholderText("e.g. Canon Pro-1000 / Hahnemühle Photo Rag 308")
        m_notes_row.addWidget(self._manual_chart_notes_edit, stretch=1)
        m_notes_row.addWidget(TooltipButton(
            "Chart Notes",
            "Optional free-text label stamped onto the right edge of the chart "
            "TIFFs alongside the targen and printtarg commands that produced them. "
            "Useful for recording the exact printer/paper combination this chart "
            "was made for, so you can match it to the right ICC profile months "
            "later. Patch pixels are not modified — only the white margin to the "
            "right of the patches is stamped.",
            self._manual_chart_notes_row,
            min_width=540,
        ))
        output_layout.addWidget(self._manual_chart_notes_row)

        # Stamp-commands row — also wrapped for ChromIQ-style hiding.
        self._manual_stamp_cmd_row = QWidget(w)
        stamp_row = QHBoxLayout(self._manual_stamp_cmd_row)
        stamp_row.setContentsMargins(0, 0, 0, 0)
        _stamp_lbl_spacer = QLabel("", self._manual_stamp_cmd_row)
        _stamp_lbl_spacer.setFixedWidth(_OUTPUT_LBL_W)
        stamp_row.addWidget(_stamp_lbl_spacer)
        self._manual_stamp_cmd_check = QCheckBox(
            "Stamp targen and printtarg commands on the chart", self._manual_stamp_cmd_row
        )
        self._manual_stamp_cmd_check.setChecked(True)
        stamp_row.addWidget(self._manual_stamp_cmd_check)
        stamp_row.addStretch()
        stamp_row.addWidget(TooltipButton(
            "Stamp Commands",
            "When enabled, the exact targen and printtarg commands used to "
            "produce the chart — plus the ChromIQ version — are stamped onto "
            "the right edge of the generated TIFF (alongside Argyll's own "
            "vertical ID line). This makes the chart self-documenting: months "
            "later you can read the printed sheet and recreate the same chart "
            "exactly. Disable if you'd rather keep the right margin clean and "
            "only stamp your own notes (or leave the chart fully unstamped if "
            "you also clear the notes field).",
            self._manual_stamp_cmd_row,
            min_width=540,
        ))
        output_layout.addWidget(self._manual_stamp_cmd_row)

        # Left-clip info row: only meaningful when -L is off on an i1Pro chart
        # with a large-enough paper. Wrap in a QWidget so setVisible(False)
        # collapses the empty space when the gating conditions aren't met.
        self._manual_left_clip_row = QWidget(w)
        left_clip_row = QHBoxLayout(self._manual_left_clip_row)
        left_clip_row.setContentsMargins(0, 0, 0, 0)
        _left_clip_lbl_spacer = QLabel("", self._manual_left_clip_row)
        _left_clip_lbl_spacer.setFixedWidth(_OUTPUT_LBL_W)
        left_clip_row.addWidget(_left_clip_lbl_spacer)
        self._manual_left_clip_check = QCheckBox(
            "Print info in left clip area", self._manual_left_clip_row
        )
        left_clip_row.addWidget(self._manual_left_clip_check)
        left_clip_row.addStretch()
        left_clip_row.addWidget(TooltipButton(
            "Left Clip Info",
            "Fills the wide blank strip on the LEFT side of the chart — the "
            "space printtarg reserves for the i1Pro 2 / i1Pro 3 Plus scanning-"
            "table clip — with two rotated text columns:\n\n"
            "• Outer column: a one-line chart summary (patch count + paper "
            "size), a print-driver reminder (borderless, no expansion, retain "
            "size, color management off), and a fill-in-the-blank form line "
            "for date, printer, ink set, profile name, paper and driver "
            "settings.\n"
            "• Inner column: orientation instructions for the i1Pro scanning "
            "table — which edge faces up and how to seat the sheet in the "
            "clip.\n\n"
            "This option is only available when:\n"
            "  • The instrument is i1Pro / i1Pro 2 or i1Pro 3 Plus.\n"
            "  • 'Suppress left clip border' is OFF (so the clip strip is "
            "actually reserved).\n"
            "  • The paper size is A4 / Letter or larger — smaller sheets "
            "have no room for legible rotated text.\n\n"
            "The row hides automatically when these conditions aren't met. "
            "Patch pixels are never modified — only the otherwise-empty left "
            "clip strip is stamped.",
            self._manual_left_clip_row,
            min_width=560,
        ))
        output_layout.addWidget(self._manual_left_clip_row)
        self._manual_left_clip_row.setVisible(False)

        layout.addWidget(output_grp)

        # Presets
        presets_grp = QGroupBox("Presets", w)
        presets_row = QHBoxLayout(presets_grp)
        presets_row.setContentsMargins(8, 4, 8, 8)
        presets_row.addWidget(QLabel("Select preset:", w))
        self._preset_combo = NoScrollComboBox(w)
        # Long built-in preset names must not stretch the row and squeeze the
        # +/−/folder buttons: ignore the combo's content width, let it take only
        # the leftover space (stretch=1) and elide the closed text. The full
        # name still shows in the open dropdown and as a hover tooltip.
        self._preset_combo.setSizeAdjustPolicy(
            NoScrollComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._preset_combo.setMinimumContentsLength(8)
        self._preset_combo.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        # Draw the group-divider separators ourselves (the default ones are
        # nearly invisible on the dark theme).
        self._preset_combo.setItemDelegate(
            _ComboSeparatorDelegate(self._preset_combo)
        )
        self._preset_combo.addItem("none", userData=None)
        presets_row.addWidget(self._preset_combo, stretch=1)
        self._preset_add_btn = QPushButton(w)
        self._preset_add_btn.setObjectName("icon_btn")
        self._preset_add_btn.setFixedSize(28, 28)
        set_preset_icon(self._preset_add_btn, "plus")
        self._preset_add_btn.setIconSize(QSize(14, 14))
        self._preset_add_btn.setToolTip("Save current settings as a new preset")
        self._preset_del_btn = QPushButton(w)
        self._preset_del_btn.setObjectName("icon_btn")
        self._preset_del_btn.setFixedSize(28, 28)
        set_preset_icon(self._preset_del_btn, "minus")
        self._preset_del_btn.setIconSize(QSize(14, 14))
        self._preset_del_btn.setToolTip("Delete selected preset")
        self._preset_del_btn.setEnabled(False)
        self._preset_reveal_btn = QPushButton(w)
        self._preset_reveal_btn.setObjectName("icon_btn")
        self._preset_reveal_btn.setFixedSize(28, 28)
        set_folder_icon(self._preset_reveal_btn, "folder")
        self._preset_reveal_btn.setIconSize(QSize(14, 14))
        self._preset_reveal_btn.setToolTip(
            "Open this tab's presets folder in Finder/Explorer.\n"
            "Each preset is a plain .json file — copy one to a colleague\n"
            "and they can drop it into their own folder to share."
        )
        self._preset_reveal_btn.clicked.connect(
            lambda: reveal_in_file_manager(tab_dir("create_chart"))
        )
        presets_row.addWidget(self._preset_add_btn)
        presets_row.addWidget(self._preset_del_btn)
        presets_row.addWidget(self._preset_reveal_btn)
        presets_row.addWidget(TooltipButton(
            "Manual Presets",
            "Save and recall named snapshots of all Manual mode settings.\n\n"
            "  +  Save current parameter values as a new named preset.\n"
            "  −  Delete the currently selected preset.\n"
            "  ▢  Open this tab's presets folder in Finder/Explorer.\n\n"
            "Select a preset from the dropdown to instantly restore all\n"
            "values. The Default entry always resets to built-in defaults.\n\n"
            "Presets are stored as plain .json files — one per preset —\n"
            "in a ChromIQ folder under your system's Preferences / AppData\n"
            "/ config location. Use the folder button (▢) on the right of\n"
            "the preset row to open it. To share a preset, copy the .json\n"
            "out of that folder and send it to a colleague; to install a\n"
            "shared preset, drop the .json into the matching folder on the\n"
            "target machine and ChromIQ will pick it up on the next launch.\n\n"
            "The target name field is not saved with presets.\n"
            "Presets persist between sessions.",
            w,
            min_width=600,
        ))
        layout.addWidget(presets_grp)

        scroll = FadeScrollArea(w)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        # Without this the word-wrapped command-preview label reports its full
        # single-line sizeHint, so a long printtarg line widens the inner widget
        # and triggers a horizontal scrollbar instead of wrapping. Match the
        # other tabs (tab_print etc.) and pin the horizontal bar off.
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(4)
        inner_layout.setContentsMargins(4, 4, 4, 4)

        self._manual_widgets: dict[str, list[ParameterWidget]] = {
            "targen": [], "printtarg": [],
        }
        self._manual_lb_pw: ParameterWidget | None = None
        self._manual_dd_pw: ParameterWidget | None = None
        self._manual_instr_pw: ParameterWidget | None = None
        self._manual_paper_pw: ParameterWidget | None = None
        self._manual_f_pw: ParameterWidget | None = None
        self._manual_a_pw: ParameterWidget | None = None
        self._manual_m_pw: ParameterWidget | None = None
        self._manual_P_pw: ParameterWidget | None = None
        self._manual_cal_k_pw: ParameterWidget | None = None
        self._manual_cal_i_pw: ParameterWidget | None = None
        self._manual_n_pw: ParameterWidget | None = None
        self._manual_b_pw: ParameterWidget | None = None
        self._manual_c_pw: ParameterWidget | None = None
        self._manual_A_pw: ParameterWidget | None = None
        # Top-level targen/printtarg group boxes. Their inner content (basic +
        # expert sub-groups, tracked in _manual_targen_content /
        # _manual_printtarg_content) is greyed while a preset locks the panel;
        # the override row stays enabled because it sits outside that content.
        self._manual_targen_grp: QGroupBox | None = None
        self._manual_printtarg_grp: QGroupBox | None = None
        # targen -c / -n: -n (Neutral Axis Steps) only does anything when a
        # pre-conditioning profile (-c) is supplied, so -n tracks -c's state.
        self._manual_targen_c_pw: ParameterWidget | None = None
        self._manual_targen_n_pw: ParameterWidget | None = None
        self._manual_auto_patches_check: QCheckBox | None = None
        # Auto checkboxes for -e/-B/-g: when on, the value is auto-computed
        # from the chart's total patch count via manual_neutrals() at submit
        # and preview time. Mirrors the -f Auto pattern.
        self._manual_e_pw: ParameterWidget | None = None
        self._manual_B_pw: ParameterWidget | None = None
        self._manual_g_pw: ParameterWidget | None = None
        self._manual_auto_white_check: QCheckBox | None = None
        self._manual_auto_black_check: QCheckBox | None = None
        self._manual_auto_grey_check:  QCheckBox | None = None
        self._manual_pages_spin: NoScrollSpinBox | None = None
        self._manual_pages_row: QWidget | None = None
        self._bit8_radio: QRadioButton | None = None
        self._bit16_radio: QRadioButton | None = None
        self._pre_cal_snapshot: dict | None = None
        self._d_cascade_widgets: list[ParameterWidget] = []
        # Triple-density mode (CM-only synthetic option; no Argyll flag of its
        # own). The checkbox lives below the -h ParameterWidget in basic_layout
        # and stashes/restores -a / -m / -P widget values across toggles.
        self._manual_td_check: QCheckBox | None = None
        self._manual_td_row: QWidget | None = None
        self._td_saved_layout: dict | None = None

        for tool, params in [
            ("targen",    self._params.get("targen", [])),
            ("printtarg", self._params.get("printtarg", [])),
        ]:
            grp = QGroupBox(f"{tool} parameters", inner)
            # Keep a handle to the outer group (its inner content is greyed via
            # _manual_*_content while a preset locks the panel).
            if tool == "targen":
                self._manual_targen_grp = grp
            else:
                self._manual_printtarg_grp = grp
            grp_layout = QVBoxLayout(grp)

            # Override row — pinned at the top of the panel, hidden until a preset
            # that supplies a fixed patch set (ti1) or a fixed layout (prebuilt)
            # is active. Ticking it re-enables the greyed controls below. The
            # checkbox stays enabled while its content is greyed because it lives
            # outside the disabled content widgets (basic_grp / expert_grp).
            override_row = QWidget(grp)
            override_l = QHBoxLayout(override_row)
            override_l.setContentsMargins(0, 0, 0, 2)
            if tool == "targen":
                ov_check = QCheckBox("Edit patch recipe (override preset)", override_row)
                ov_tip = TooltipButton("Edit patch recipe", _OVERRIDE_TARGEN_TIP,
                                       override_row, min_width=600)
                self._override_targen_check = ov_check
                self._override_targen_row = override_row
            else:
                ov_check = QCheckBox("Edit page layout (override preset)", override_row)
                ov_tip = TooltipButton("Edit page layout", _OVERRIDE_PRINTTARG_TIP,
                                       override_row, min_width=600)
                self._override_printtarg_check = ov_check
                self._override_printtarg_row = override_row
            override_l.addWidget(ov_check)
            override_l.addStretch()
            override_l.addWidget(ov_tip)
            override_row.setVisible(False)
            grp_layout.addWidget(override_row)
            ov_check.toggled.connect(self._update_preset_locks)
            ov_check.toggled.connect(self._refresh_manual_command_preview)
            ov_check.clicked.connect(
                lambda checked, t=tool: self._on_override_clicked(t, checked)
            )

            basic_grp = QGroupBox("Basic", grp)
            basic_layout = QVBoxLayout(basic_grp)
            expert_grp = QGroupBox("Expert Options", grp)
            expert_layout = QVBoxLayout(expert_grp)
            # Content widgets greyed out (not the override row) while locked.
            if tool == "targen":
                self._manual_targen_content = [basic_grp, expert_grp]
            else:
                self._manual_printtarg_content = [basic_grp, expert_grp]

            for p in params:
                pw = ParameterWidget(p, inner, browse_icon="folder_create")
                pw.make_compact()
                flag = p.get("flag", "")

                if tool == "printtarg" and flag == "-t":
                    # Shrink the DPI spinbox and add 8-bit/16-bit radio buttons
                    pw._control.setMaximumWidth(90)
                    bg = QButtonGroup(pw)
                    self._bit8_radio = QRadioButton("8-bit", pw)
                    self._bit16_radio = QRadioButton("16-bit", pw)
                    # Tag as param_label so the disabled QSS rule greys text +
                    # indicator when a preset locks the printtarg panel.
                    self._bit8_radio.setObjectName("param_label")
                    self._bit16_radio.setObjectName("param_label")
                    self._bit8_radio.setChecked(True)
                    bg.addButton(self._bit8_radio)
                    bg.addButton(self._bit16_radio)
                    # Insert before the last item (tooltip button)
                    insert_at = pw.layout().count() - 1
                    pw.layout().insertWidget(insert_at,     self._bit8_radio)
                    pw.layout().insertWidget(insert_at + 1, self._bit16_radio)

                if tool == "targen" and flag == "-f":
                    # Shrink the patch-count spinbox and add an "Auto" checkbox
                    # that drives live estimation from current paper/layout settings.
                    self._manual_f_pw = pw
                    pw._control.setMaximumWidth(90)
                    self._manual_auto_patches_check = QCheckBox("Auto", pw)
                    self._manual_auto_patches_check.setToolTip(
                        "Auto-compute the patch count to fill exactly the number of\n"
                        "pages set under printtarg → Pages, using the current paper,\n"
                        "instrument, double-density, left-border, patch scale and margin."
                    )
                    insert_at = pw.layout().count() - 1
                    pw.layout().insertWidget(insert_at, self._manual_auto_patches_check)
                    self._manual_auto_patches_check.toggled.connect(
                        self._on_auto_patches_toggled
                    )

                # White / Black / Grey-steps Auto checkboxes — mirror the -f
                # pattern. When checked, the value is auto-computed from the
                # chart's total patch count (whether user-set or itself auto).
                if tool == "targen" and flag == "-e":
                    self._manual_e_pw = pw
                    pw._control.setMaximumWidth(90)
                    self._manual_auto_white_check = QCheckBox("Auto", pw)
                    self._manual_auto_white_check.setToolTip(
                        "Auto-compute white patches (-e) from the chart's total\n"
                        "patch count. Anchor: 560 patches → 4 whites. Doubling the\n"
                        "total adds 50 % to the count, capped at 8 (min 2)."
                    )
                    insert_at = pw.layout().count() - 1
                    pw.layout().insertWidget(insert_at, self._manual_auto_white_check)
                    self._manual_auto_white_check.toggled.connect(
                        lambda v: self._on_auto_neutral_toggled("white", v)
                    )

                if tool == "targen" and flag == "-B":
                    self._manual_B_pw = pw
                    pw._control.setMaximumWidth(90)
                    self._manual_auto_black_check = QCheckBox("Auto", pw)
                    self._manual_auto_black_check.setToolTip(
                        "Auto-compute black patches (-B) from the chart's total\n"
                        "patch count. Anchor: 560 patches → 4 blacks. Doubling the\n"
                        "total adds 50 % to the count, capped at 8 (min 2)."
                    )
                    insert_at = pw.layout().count() - 1
                    pw.layout().insertWidget(insert_at, self._manual_auto_black_check)
                    self._manual_auto_black_check.toggled.connect(
                        lambda v: self._on_auto_neutral_toggled("black", v)
                    )

                if tool == "targen" and flag == "-g":
                    self._manual_g_pw = pw
                    pw._control.setMaximumWidth(90)
                    self._manual_auto_grey_check = QCheckBox("Auto", pw)
                    self._manual_auto_grey_check.setToolTip(
                        "Auto-compute grey-axis steps (-g) from the chart's total\n"
                        "patch count. Anchor: 560 patches → 32 steps. Doubling the\n"
                        "total doubles the steps, capped at 128 (min 8)."
                    )
                    insert_at = pw.layout().count() - 1
                    pw.layout().insertWidget(insert_at, self._manual_auto_grey_check)
                    self._manual_auto_grey_check.toggled.connect(
                        lambda v: self._on_auto_neutral_toggled("grey", v)
                    )

                # targen -c / -n dependency: -n (Neutral Axis Steps) samples
                # the profile-defined neutral axis and is a no-op unless -c
                # (Pre-conditioning Profile) is set.  Capture both so -n can
                # track -c's state (see _connect_neutral_dep).
                if tool == "targen" and flag == "-c":
                    self._manual_targen_c_pw = pw
                if tool == "targen" and flag == "-n":
                    self._manual_targen_n_pw = pw

                if tool == "printtarg" and flag == "-L":
                    self._manual_lb_pw = pw
                    pw.value_changed.connect(self._update_manual_lb_visibility)
                if tool == "printtarg" and flag == "-h":
                    self._manual_dd_pw = pw
                    pw.value_changed.connect(self._on_manual_dd_toggled)
                if tool == "printtarg" and flag == "-i":
                    self._manual_instr_pw = pw
                    pw.value_changed.connect(self._update_manual_lb_visibility)
                    pw.value_changed.connect(self._apply_instrument_default_margin)
                    pw.value_changed.connect(self._update_isis_preview_banner)
                if tool == "printtarg" and flag == "-p":
                    self._manual_paper_pw = pw
                    pw.value_changed.connect(self._update_manual_lb_visibility)
                if tool == "printtarg" and flag == "-a":
                    self._manual_a_pw = pw
                if tool == "printtarg" and flag == "-m":
                    self._manual_m_pw = pw
                if tool == "printtarg" and flag == "-P":
                    self._manual_P_pw = pw
                if tool == "printtarg" and flag == "-K":
                    self._manual_cal_k_pw = pw
                if tool == "printtarg" and flag == "-I":
                    self._manual_cal_i_pw = pw
                if tool == "printtarg" and flag == "-n":
                    self._manual_n_pw = pw
                if tool == "printtarg" and flag == "-b":
                    self._manual_b_pw = pw
                if tool == "printtarg" and flag == "-c":
                    self._manual_c_pw = pw
                if tool == "printtarg" and flag == "-A":
                    self._manual_A_pw = pw

                if tool == "targen" and flag == "-D":
                    self._d_cascade_widgets.append(pw)
                    expert_layout.addWidget(pw)
                    self._manual_widgets[tool].append(pw)
                    for _ in range(10):
                        extra_pw = ParameterWidget(p, inner)
                        extra_pw.make_compact()
                        extra_pw.setVisible(False)
                        self._d_cascade_widgets.append(extra_pw)
                        expert_layout.addWidget(extra_pw)
                        self._manual_widgets[tool].append(extra_pw)
                elif p.get("expert_only", False):
                    expert_layout.addWidget(pw)
                    self._manual_widgets[tool].append(pw)
                else:
                    basic_layout.addWidget(pw)
                    self._manual_widgets[tool].append(pw)

                # Immediately below the -h ParameterWidget, drop in the
                # Triple-density row. Same parent layout (basic_layout, since
                # -h is not expert_only) so it sits visually under the
                # Double density row in both light and dark layouts.
                if tool == "printtarg" and flag == "-h":
                    self._manual_td_row = self._make_manual_td_row(inner)
                    basic_layout.addWidget(self._manual_td_row)

            # Insert the Pages row right under printtarg -p (paper size).
            # Drives the Auto patch-count estimate; greyed out unless Auto is on.
            if tool == "printtarg" and self._manual_paper_pw is not None:
                pages_row_w = QWidget(basic_grp)
                pages_row_l = QHBoxLayout(pages_row_w)
                pages_row_l.setContentsMargins(0, 2, 0, 2)
                pages_row_l.setSpacing(8)
                pages_lbl = QLabel("Pages:", pages_row_w)
                pages_lbl.setFixedWidth(190)
                # param_label carries the right per-theme colour AND a :disabled
                # rule, so it greys when a preset locks the printtarg panel.
                pages_lbl.setObjectName("param_label")
                pages_row_l.addWidget(pages_lbl)
                self._manual_pages_spin = NoScrollSpinBox(pages_row_w)
                self._manual_pages_spin.setObjectName("compact_input")
                self._manual_pages_spin.setRange(1, 20)
                self._manual_pages_spin.setValue(1)
                self._manual_pages_spin.setMaximumWidth(90)
                self._manual_pages_spin.setEnabled(False)
                pages_row_l.addWidget(self._manual_pages_spin)
                pages_row_l.addStretch()
                pages_row_l.addWidget(TooltipButton(
                    "Pages (Auto patch count)",
                    "How many physical sheets the chart should span. This control "
                    "drives the Auto checkbox next to targen → Total Patch Count "
                    "above: when Auto is on, ChromIQ picks the patch count that "
                    "fills exactly this many sheets — using the current paper, "
                    "instrument, double-density / hexagon, left-border, patch "
                    "scale and margin settings. Total patches = patches-per-page "
                    "× pages.\n\n"
                    "More pages means more colour samples, which produces a more "
                    "accurate profile. The trade-off is more ink, more paper and "
                    "a longer reading session. Rough guide:\n\n"
                    "  •  1 page — quick check or single-sheet workflows "
                    "(~500 patches on A4 with an i1Pro). Fine for casual "
                    "profiling.\n\n"
                    "  •  2-3 pages — recommended for everyday photo printing. "
                    "Good balance of accuracy versus effort.\n\n"
                    "  •  4-5+ pages — professional or fine-art workflows where "
                    "the profile needs to nail tricky tonal transitions and "
                    "out-of-gamut colours.\n\n"
                    "This control is greyed out when Auto is off — without Auto, "
                    "printtarg just uses as many sheets as the explicit Total "
                    "Patch Count requires.",
                    pages_row_w,
                    min_width=600,
                ))
                idx = basic_layout.indexOf(self._manual_paper_pw)
                basic_layout.insertWidget(idx + 1 if idx >= 0 else basic_layout.count(),
                                          pages_row_w)
                self._manual_pages_row = pages_row_w

            grp_layout.addWidget(basic_grp)
            grp_layout.addWidget(expert_grp)
            inner_layout.addWidget(grp)

        self._update_manual_lb_visibility()
        self._apply_instrument_default_margin()
        # Note: _update_isis_preview_banner() is NOT called here — self._preview
        # doesn't exist yet during _make_manual_panel(). It's wired to the
        # instrument-selector signal and called once more after settings load.
        self._connect_cal_mutex()
        self._connect_spacer_mutex()
        self._connect_neutral_dep()
        self._connect_d_cascade()
        self._preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        self._preset_add_btn.clicked.connect(self._on_preset_save)
        self._preset_del_btn.clicked.connect(self._on_preset_delete)
        self._manual_target_name_edit.textChanged.connect(self._check_for_cal_file)
        self._cal_target_check.toggled.connect(self._on_cal_target_toggled)
        # Cal-target prefix changes the displayed name — refresh the preview too.
        self._cal_target_check.toggled.connect(self._refresh_manual_command_preview)

        # Live command preview — mirrors the guided info box but reflects the
        # actual targen / printtarg args the workflow will build from the
        # current ParameterWidget state.  Sits at the bottom of the scrollable
        # area so it follows the last parameter group.
        self._manual_info_lbl = QLabel("", inner)
        self._manual_info_lbl.setObjectName("info")
        self._manual_info_lbl.setWordWrap(True)
        inner_layout.addWidget(self._manual_info_lbl)

        # Wire every parameter widget to refresh the live command preview.
        for tool in ("targen", "printtarg"):
            for pw in self._manual_widgets.get(tool, []):
                pw.value_changed.connect(self._refresh_manual_command_preview)
        if self._manual_pages_spin is not None:
            self._manual_pages_spin.valueChanged.connect(
                self._refresh_manual_command_preview
            )
        if self._manual_auto_patches_check is not None:
            self._manual_auto_patches_check.toggled.connect(
                self._refresh_manual_command_preview
            )
        if self._bit16_radio is not None:
            self._bit16_radio.toggled.connect(self._refresh_manual_command_preview)
        self._refresh_manual_command_preview()
        self._update_preset_locks()

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)
        return w

    def _refresh_manual_command_preview(self) -> None:
        """Rebuild the manual info label from the current ParameterWidget state.

        Mirrors workflow/chart_creator.py:_build_targen_args /
        _build_printtarg_args so the preview matches exactly what runs."""
        if getattr(self, "_manual_info_lbl", None) is None:
            return
        try:
            p = self._collect_manual()
        except Exception:
            self._manual_info_lbl.setText("Manual mode — preview unavailable.")
            return

        # targen
        targen_args: list[str] = [f"-d{p.device_type}"]
        patches = int(p.patches)
        if self._manual_auto_patches_check is not None \
                and self._manual_auto_patches_check.isChecked() \
                and self._manual_f_pw is not None:
            try:
                patches = int(self._manual_f_pw.get_raw_value() or 0)
            except (TypeError, ValueError):
                pass
        targen_args += [f"-f{patches}"]
        targen_args += [f"-e{p.white_patches}", f"-B{p.black_patches}"]
        if p.good_mode:
            targen_args.append("-G")
        if p.grey_steps > 0:
            targen_args += [f"-g{p.grey_steps}"]
        if p.single_channel_steps > 0:
            targen_args += [f"-s{p.single_channel_steps}"]
        if p.extra_targen_args:
            _extra = shlex.split(p.extra_targen_args)
            # Render -c <picked path> as the staged filename — chart_creator
            # imports the pick into the run as preconditioning.icc — and avoids
            # burying the rest of the args under a long absolute path.
            for _i, _tok in enumerate(_extra):
                if _tok == "-c" and _i + 1 < len(_extra) and _extra[_i + 1]:
                    _extra[_i + 1] = "preconditioning.icc"
            targen_args += _extra
        targen_args.append(self._preview_target_name("manual"))

        # printtarg
        pt_args: list[str] = []
        # Triple density emulates the i1Pro layout — mirror the override path
        # in chart_creator._build_printtarg_args.
        triple = p.triple_density and p.instrument == "CM"
        if triple:
            pt_instr = "i1"
        else:
            pt_instr = "3p" if p.instrument == "p3" else p.instrument
        pt_args.append(f"-i{pt_instr}")
        pt_args.append(f"-p{p.paper}")
        dpi_flag = "-T" if p.tiff_16bit else "-t"
        pt_args.append(f"{dpi_flag}{p.tiff_dpi}")
        if not triple and p.double_density and p.instrument in {"CM", "SS"}:
            pt_args.append("-h")
        # Mirror chart_creator._build_printtarg_args: ChromIQ-style clipping
        # border forces -L regardless of the per-chart toggle, so the preview
        # has to reflect that too. Triple density also forces -L (suppress
        # widget is hidden in that mode).
        from workflow.chart_creator import _chromiq_clip_active
        force_l = _chromiq_clip_active(p) or triple
        l_applies = p.instrument in {"i1", "p3"} or triple
        if (p.disable_left_border or force_l) and l_applies:
            pt_args.append("-L")
        # Triple density seeds -a 1.3 / -m 5 / -P on toggle but the user can
        # still override those widgets — mirror chart_creator and pass the
        # ChartParams values through verbatim.
        if abs(p.patch_scale - 1.0) > 0.01:
            pt_args.append(f"-a{p.patch_scale:.2f}")
        if p.margin_mm != 6:
            pt_args.append(f"-m{p.margin_mm}")
        pt_args.append(f"-M{p.margin_mm}")
        if p.no_randomise:
            pt_args.append("-r")
        if p.bw_spacers:
            pt_args.append("-b")
        if p.no_strip_limit:
            pt_args.append("-P")
        if p.extra_printtarg_args:
            pt_args += shlex.split(p.extra_printtarg_args)
        pt_args.append(self._preview_target_name("manual"))

        pages = (
            self._manual_pages_spin.value()
            if self._manual_pages_spin is not None else 1
        )
        notes = [f"{pages} page{'s' if pages != 1 else ''}"]
        if self._manual_auto_patches_check is not None \
                and self._manual_auto_patches_check.isChecked():
            notes.append("Auto patch count")
        auto_neutrals = [
            lbl for lbl, chk in (
                ("grey",  self._manual_auto_grey_check),
                ("white", self._manual_auto_white_check),
                ("black", self._manual_auto_black_check),
            ) if chk is not None and chk.isChecked()
        ]
        if auto_neutrals:
            notes.append("Auto " + "/".join(auto_neutrals))
        if p.tiff_16bit:
            notes.append("16-bit TIFF")

        # While the TC9.18 built-in chart is the active patch source, "Generate"
        # runs printtarg only on the bundled .ti1 — targen is skipped. Say so,
        # unless the user has changed a targen setting (which re-enables targen).
        tc918_repro = (
            getattr(self, "_tc918_active", False)
            and self._tc918_targen_sig is not None
            and self._targen_signature() == self._tc918_targen_sig
        )
        knut_repro = (
            getattr(self, "_knut_active", False)
            and self._knut_targen_sig is not None
            and self._targen_signature() == self._knut_targen_sig
        )
        # A prebuilt-files preset normally copies its bundled files. Unlocking a
        # panel changes that: editing the layout re-lays the bundled patches;
        # editing the recipe builds a fresh chart. Reflect whichever applies.
        prebuilt_active = getattr(self, "_prebuilt_active", False)
        if prebuilt_active:
            targen_changed = (self._prebuilt_targen_sig is not None
                              and self._targen_signature() != self._prebuilt_targen_sig)
            printtarg_changed = (self._prebuilt_printtarg_sig is not None
                                 and self._printtarg_signature() != self._prebuilt_printtarg_sig)
            if targen_changed:
                info = (
                    f"Built-in preset — patch recipe changed ({' · '.join(notes)}):\n"
                    "Builds a fresh chart from your settings — the patches will "
                    "NOT match the preset.\n"
                    f"targen {' '.join(targen_args)}\n"
                    f"printtarg {' '.join(pt_args)}"
                )
            elif printtarg_changed:
                info = (
                    f"Built-in preset — re-laid out ({' · '.join(notes)}):\n"
                    "Re-arranges the preset's exact patches on the page (targen "
                    "skipped).\n"
                    f"printtarg {' '.join(pt_args)}"
                )
            else:
                info = (
                    "Built-in preset — ready-made chart:\n"
                    "Copies the bundled patch set as-is (targen and printtarg "
                    "skipped).\n"
                    "Unlock \"Edit page layout\" to re-arrange the same patches, "
                    "or \"Edit patch recipe\" to build a different chart."
                )
            self._manual_info_lbl.setText(info)
            return
        if tc918_repro:
            info = (
                f"i1Pro TC9.18 by Pharmacist — fixed patch set ({' · '.join(notes)}):\n"
                f"Uses the bundled tc918.ti1 (targen skipped).\n"
                f"printtarg {' '.join(pt_args)}\n"
                "Change a targen setting above to build a fresh chart instead."
            )
        elif knut_repro:
            info = (
                f"TC9.18+Spyderprint preset — fixed patch set ({' · '.join(notes)}):\n"
                "Uses the bundled 1168-patch .ti1 (targen skipped).\n"
                f"printtarg {' '.join(pt_args)}\n"
                "Change a targen setting above to build a fresh chart instead."
            )
        else:
            info = (
                f"Manual mode — your current configuration ({' · '.join(notes)}):\n"
                f"targen {' '.join(targen_args)}\n"
                f"printtarg {' '.join(pt_args)}"
            )
        self._manual_info_lbl.setText(info)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def set_calibration_mode(self, enabled: bool) -> None:
        """Show/hide calibration-specific UI and lock to manual mode when enabled."""
        self._mode_row_widget.setVisible(not enabled)
        self._cal_target_grp.setVisible(enabled)
        if enabled:
            self._switch_mode("manual")
            if not self._cal_target_check.isChecked():
                self._check_for_cal_file(self._manual_target_name_edit.text())
        else:
            self._cal_target_check.setChecked(False)

    def set_cal_file_paths(self, cal_path: "Path") -> None:
        """Pre-fill the -I and -K parameter widgets with the given .cal path."""
        from pathlib import Path
        cal_str = str(cal_path)
        if self._manual_cal_k_pw is not None:
            self._manual_cal_k_pw.set_value(cal_str)
        if self._manual_cal_i_pw is not None:
            self._manual_cal_i_pw.set_value(cal_str)
        self._cal_target_check.setChecked(False)

    def _check_for_cal_file(self, name: str) -> None:
        """Live check: if this project already has a calibration, prefill -I and -K.

        Calibration lives at ``<project>/cal/<project>-cal.cal`` (one per
        project, shared across runs) — see ``Calibration.cal_path``.
        """
        name = name.strip()
        if not name:
            self._cal_status_lbl.setVisible(False)
            return
        from core.file_manager import Calibration
        proj_root = self._file_mgr.preview_project_root(name)
        if proj_root is None:
            self._cal_status_lbl.setVisible(False)
            return
        cal_file = Calibration(proj_root).cal_path
        if cal_file.exists():
            cal_str = str(cal_file)
            if self._manual_cal_k_pw is not None:
                self._manual_cal_k_pw.set_value(cal_str)
            if self._manual_cal_i_pw is not None:
                self._manual_cal_i_pw.set_value(cal_str)
            self._cal_status_lbl.setText(
                f"Calibration file found: {cal_file.name} — auto-filled into -I and -K fields below."
            )
            self._cal_status_lbl.setVisible(True)
        else:
            self._cal_status_lbl.setVisible(False)

    _PREVIEW_NAME_MAX_LEN = 23

    @classmethod
    def _shorten_for_preview(cls, name: str, max_len: int | None = None) -> str:
        """Shorten a long file/target name for the command-preview info boxes.

        Uses a *middle* ellipsis so both the meaningful start and the tail stay
        visible — the tail carries the extension (.icc/.icm) for profiles and
        the date-like suffix that usually distinguishes one chart from the next,
        both of which an end-ellipsis would hide. Only the displayed text is
        affected; the real name used at Generate-click is read from the input
        field, not from here.
        """
        limit = cls._PREVIEW_NAME_MAX_LEN if max_len is None else max_len
        if len(name) <= limit:
            return name
        keep = limit - 1  # room for the ellipsis
        head = keep // 2
        tail = keep - head
        return f"{name[:head]}…{name[-tail:]}"

    def _preview_target_name(self, mode: str) -> str:
        """Return the file stem as it will appear in the targen/printtarg
        command preview.

        Under the per-run folder layout the file stem is fixed: ``calibration``
        when the Calibration Target checkbox is active (manual mode only),
        otherwise ``chart``. The user's project name is the *folder* name, not
        the file stem, so it no longer appears on the command line.
        """
        if mode == "manual" and getattr(self, "_cal_target_check", None) is not None:
            grp = getattr(self, "_cal_target_grp", None)
            if (self._cal_target_check.isChecked()
                    and grp is not None and grp.isVisible()):
                return "calibration"
        return "chart"

    def _on_cal_target_toggled(self, checked: bool) -> None:
        _CAL_VALUES: list[tuple[str, str, Any]] = [
            ("targen",    "-f",  0),
            ("targen",    "-e",  0),
            ("targen",    "-B",  0),
            ("targen",    "-s",  20),
            ("targen",    "-G",  False),
            ("printtarg", "-r",  True),
        ]
        if checked:
            self._pre_cal_snapshot = {}
            for tool, flag, val in _CAL_VALUES:
                for pw in self._manual_widgets.get(tool, []):
                    if pw.flag == flag:
                        self._pre_cal_snapshot[(tool, flag)] = pw.get_raw_value()
                        pw.set_value(val)
        else:
            if self._pre_cal_snapshot:
                for tool, flag, _ in _CAL_VALUES:
                    saved = self._pre_cal_snapshot.get((tool, flag))
                    if saved is not None:
                        for pw in self._manual_widgets.get(tool, []):
                            if pw.flag == flag:
                                pw.set_value(saved)
            self._pre_cal_snapshot = None

    def _make_lineedit(self, text: str, parent: QWidget) -> Any:
        from PyQt6.QtWidgets import QLineEdit
        le = QLineEdit(parent)
        le.setText(text)
        return le

    def _clean_target_name_field(self, edit: Any, hint: QLabel) -> None:
        """Strip a stray work-file extension from a target-name field on edit.

        The name is reused verbatim as the working-folder name and the stem of
        every generated file, so an extension (e.g. a pasted ".icm" profile
        name) would contaminate the whole session. Remove it and tell the user
        why so the correction isn't silent.
        """
        raw     = edit.text().strip()
        cleaned = self._file_mgr.strip_workfile_ext(raw)
        if cleaned == raw:
            hint.setVisible(False)
            return
        removed = raw[len(cleaned):]
        edit.setText(cleaned)
        hint.setText(
            f"Removed “{removed}” — the target name is used for the output "
            f"folder and every generated file, so it shouldn't include a file "
            f"extension."
        )
        hint.setVisible(True)

    def _load_yaml_params(self) -> dict:
        path = resource_path("data/parameters.yaml")
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return data.get("parameters", {})
        except Exception as exc:
            log.error("Cannot load parameters.yaml: %s", exc)
            return {}

    def _switch_mode(self, mode: str) -> None:
        if mode == "guided":
            self._stack.setCurrentIndex(0)
            self._guided_btn.setChecked(True)
            self._manual_btn.setChecked(False)
        else:
            self._stack.setCurrentIndex(1)
            self._guided_btn.setChecked(False)
            self._manual_btn.setChecked(True)
        self._update_isis_preview_banner()

    def _on_guided_precond_toggled(self, checked: bool) -> None:
        self._guided_precond_path.setEnabled(checked)
        self._guided_precond_browse.setEnabled(checked)
        if not checked:
            # Forget the "came from a result dialog" hint — only honor it while the
            # checkbox is actively ticked so that toggling off and back on doesn't
            # silently re-arm the rename-instead-of-wipe behavior.
            self._preconditioning_from_dialog = False
        self._update_patch_count()

    def _on_guided_precond_browse(self) -> None:
        start = self._guided_precond_path.text().strip()
        if start:
            start = str(Path(start).parent)
        path = open_file_dialog(
            self, "Select pre-conditioning profile",
            "ICC / MPP profiles (*.icc *.icm *.mpp)",
            start_dir=start,
            extra_path=self._settings.get("custom_output_path", ""),
            extra_paths=icc_profile_paths(),
        )
        if path:
            self._guided_precond_path.setText(path)
            self._update_patch_count()

    def apply_preconditioning(self, profile_path: Path | str) -> None:
        """Programmatically pre-fill pre-conditioning from a result dialog.

        Called by the main window when the user clicks "Use as pre-conditioning
        profile" in the Build Profile or Check/Refine result dialog. Switches to
        guided mode, ticks the checkbox, fills the path picker, and remembers
        the current run so the next Generate Chart click seeds a fresh run
        (Project.new_run) from it.
        """
        self._switch_mode("guided")
        self._guided_precond_path.setText(str(profile_path))
        self._guided_precond_check.setChecked(True)
        self._preconditioning_from_dialog = True
        try:
            self._precond_parent_run_id = self._file_mgr.project().current_run().id
        except Exception as exc:  # noqa: BLE001 — never block the UI on this
            log.warning("Could not capture parent run for preconditioning: %s", exc)
            self._precond_parent_run_id = None

    def _current_mode(self) -> str:
        return "guided" if self._stack.currentIndex() == 0 else "manual"

    def refresh_chromiq_clip_visibility(self) -> None:
        """Re-evaluate ChromIQ-style-driven UI visibility.

        Called by MainWindow after the Settings dialog closes so toggling the
        'Use ChromIQ-style clipping border' preference takes effect on the
        Create Chart tab without needing the user to bump instrument or paper.
        """
        if hasattr(self, "_update_dd_visibility"):
            self._update_dd_visibility()
        self._update_manual_lb_visibility()

    def _chromiq_force_l(self, instr: str, paper: str) -> bool:
        """True iff ChromIQ-style clipping border forces -L for this instr+paper.

        Mirrors workflow.chart_creator._chromiq_clip_active gating so patch-
        count lookups and command previews agree with what actually runs.
        """
        return (
            bool(self._settings.get("i1pro_chromiq_clip_style", False))
            and instr in {"i1", "p3"}
            and paper in ALLOWED_LEFT_CLIP_PAPERS
        )

    def _chromiq_clip_active_in_ui(self) -> bool:
        """True iff the ChromIQ-style clipping border WILL be applied.

        Mirrors `workflow.chart_creator._chromiq_clip_active`: setting on AND
        instrument is i1Pro family AND paper >= A4 AND the user did NOT
        suppress the left clip border. Checking the suppress toggle disables
        the ChromIQ branded strip even when the setting is on, so the per-
        chart toggle remains the user's escape hatch.
        """
        if self._current_mode() == "guided":
            instr = self._instr_combo.currentData() or "i1"
            paper = self._paper_combo.currentData() or "A4"
            suppress = self._lb_check.isChecked()
        else:
            instr = (self._manual_instr_pw.get_raw_value()
                     if self._manual_instr_pw is not None else "i1") or "i1"
            paper = (self._manual_paper_pw.get_raw_value()
                     if self._manual_paper_pw is not None else "A4") or "A4"
            suppress = (bool(self._manual_lb_pw.get_raw_value())
                        if self._manual_lb_pw is not None else False)
        return self._chromiq_force_l(instr, paper) and not suppress

    def _update_manual_lb_visibility(self) -> None:
        if self._manual_instr_pw is None:
            return
        instr = self._manual_instr_pw.get_raw_value() or "i1"
        chromiq_clip = self._chromiq_clip_active_in_ui()

        # -L only matters for strip instruments. Even with ChromIQ-style on,
        # the row stays visible: unchecked = branded strip, checked = no
        # border (commands/notes route to the right margin as usual).
        # Triple density forces -L internally — hide the row in that mode.
        td_on = (self._manual_td_check is not None
                 and self._manual_td_check.isChecked())
        if self._manual_lb_pw is not None:
            self._manual_lb_pw.setVisible(instr in {"i1", "p3"} and not td_on)

        # Chart notes + stamp-commands rows stay available in all modes. Under
        # ChromIQ-style their content is routed into a clip-border column
        # instead of the right margin (handled in chart_creator).
        if getattr(self, "_manual_chart_notes_row", None) is not None:
            self._manual_chart_notes_row.setVisible(True)
        if getattr(self, "_manual_stamp_cmd_row", None) is not None:
            self._manual_stamp_cmd_row.setVisible(True)

        # Left clip info row: hidden under ChromIQ-style (the stamp always
        # runs there, no opt-in needed). Otherwise visible only when -L is
        # OFF on a suitable i1Pro chart.
        if getattr(self, "_manual_left_clip_row", None) is not None:
            paper = (self._manual_paper_pw.get_raw_value()
                     if self._manual_paper_pw is not None else "A4") or "A4"
            lb_on = (bool(self._manual_lb_pw.get_raw_value())
                     if self._manual_lb_pw is not None else False)
            show_left_clip = (
                not chromiq_clip
                and instr in {"i1", "p3"}
                and not lb_on
                and paper in ALLOWED_LEFT_CLIP_PAPERS
            )
            self._manual_left_clip_row.setVisible(show_left_clip)
        # -h is offered on CM (double density) and SS (hexagon patches);
        # relabel per instrument so the meaning is clear.
        if self._manual_dd_pw is not None:
            if instr == "CM":
                self._manual_dd_pw.setVisible(True)
                self._manual_dd_pw.set_display_text(
                    "Double density",
                    "Double Density (-h)",
                    "Doubles the number of patches that fit in each measurement "
                    "strip when using a ColorMunki / i1Studio / ColorChecker "
                    "Studio.\n\n"
                    "REQUIRES the physical measuring rig accessory — a clear "
                    "plastic guide that mounts the instrument over the chart. "
                    "Without the rig the device cannot align to the tighter "
                    "patch spacing and will misread.\n\n"
                    "With the rig you get roughly twice as many patches per "
                    "page, which means either a more detailed profile from the "
                    "same number of sheets, or the same profile quality on "
                    "fewer sheets. Recommended for anyone with the rig — it's "
                    "a strict upgrade on patch density.\n\n"
                    "Has no effect on i1Pro, i1Pro 3 Plus or SpectroScan — the "
                    "option is hidden when those are selected.",
                    tooltip_min_width=600,
                )
            elif instr == "SS":
                self._manual_dd_pw.setVisible(True)
                self._manual_dd_pw.set_display_text(
                    "Hexagon patches",
                    "Hexagon Patches (-h)",
                    "Switches the SpectroScan chart layout from rectangular to "
                    "hexagonal patches. Hexagons tessellate more tightly than "
                    "rectangles, so roughly 14% more patches fit on the same "
                    "sheet — useful for squeezing extra colour samples out of "
                    "large papers.\n\n"
                    "No extra hardware is required. The SpectroScan's XY scanner "
                    "reads each patch individually under a motorised arm, so it "
                    "doesn't care whether the patch is square or hexagonal.\n\n"
                    "Has no effect on i1Pro, i1Pro 3 Plus or ColorMunki — the "
                    "option is hidden when those are selected.",
                    tooltip_min_width=600,
                )
            else:
                self._manual_dd_pw.setVisible(False)
                # Clear hidden -h so it can't leak into printtarg the next time
                # the user switches back to CM/SS. Mirror of guided mode.
                if self._manual_dd_pw.get_raw_value():
                    self._manual_dd_pw.set_value(False)

        # Triple density: CM-only synthetic option. Hide on every other
        # instrument and force it off (restoring any stashed layout values)
        # so it can't leak across an instrument switch.
        if self._manual_td_row is not None and self._manual_td_check is not None:
            td_visible = instr == "CM"
            self._manual_td_row.setVisible(td_visible)
            if not td_visible and self._manual_td_check.isChecked():
                self._manual_td_check.setChecked(False)

    def _make_manual_td_row(self, parent: QWidget) -> QWidget:
        """Build the Triple-density row that sits below the -h widget.

        It's a plain QCheckBox + tooltip rather than a ParameterWidget because
        there's no underlying Argyll flag — triple-density is ChromIQ-internal
        and rewrites -i / -a / -m / -P at command-build time.
        """
        row_w = QWidget(parent)
        row = QHBoxLayout(row_w)
        # Match the ParameterWidget compact layout so the checkbox aligns
        # under "Double density (for measuring rig)" above it.
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(8)
        lbl = QLabel("Triple density", row_w)
        lbl.setFixedWidth(190)
        # param_label gives it the standard label colour plus the :disabled
        # rule, so it greys when a preset locks the printtarg panel.
        lbl.setObjectName("param_label")
        self._manual_td_check = QCheckBox(row_w)
        self._manual_td_check.toggled.connect(self._on_manual_td_toggled)
        self._manual_td_check.toggled.connect(self._refresh_manual_command_preview)
        row.addWidget(lbl)
        row.addWidget(self._manual_td_check)
        row.addStretch()
        row.addWidget(TooltipButton(
            "Triple Density (i1Pro layout emulation)",
            "ColorMunki + rig only. Generates the chart with the i1Pro strip "
            "layout (printtarg -ii1) plus the tuned scale / margin / strip-"
            "limit overrides needed for the ColorMunki to read it, then "
            "rewrites the produced .ti2 so chartread still talks to your "
            "ColorMunki. Result: roughly 3× the patch count of a plain "
            "ColorMunki chart at the same paper size.\n\n"
            "REQUIRES the physical measuring rig accessory.\n\n"
            "Mutually exclusive with Double density. Ticking this stashes "
            "the current -a / -m / -P widget values and sets them to the "
            "triple-density preset (1.3 / 5 / on); unticking restores the "
            "stashed values.\n\n"
            "Has no effect on i1Pro, i1Pro 3 Plus or SpectroScan — the option "
            "is hidden when those are selected.",
            row_w,
            min_width=600,
        ))
        return row_w

    def _on_manual_dd_toggled(self) -> None:
        """Mutual exclusion: toggling manual -h must grey out the Triple-density row."""
        if self._manual_dd_pw is None:
            return
        dd_on = bool(self._manual_dd_pw.get_raw_value())
        if (dd_on and self._manual_td_check is not None
                and self._manual_td_check.isChecked()):
            self._manual_td_check.setChecked(False)
        if self._manual_td_row is not None:
            self._manual_td_row.setEnabled(not dd_on)

    def _on_manual_td_toggled(self, checked: bool) -> None:
        """Apply / undo the triple-density layout overrides on the -a / -m / -P widgets."""
        # Mutual exclusion with the manual Double density widget.
        if self._manual_dd_pw is not None:
            if checked and self._manual_dd_pw.get_raw_value():
                self._manual_dd_pw.set_value(False)
            self._manual_dd_pw.setEnabled(not checked)

        if checked:
            stash: dict = {}
            if self._manual_a_pw is not None:
                stash["-a"] = self._manual_a_pw.get_raw_value()
                self._manual_a_pw.set_value(1.3)
            if self._manual_m_pw is not None:
                stash["-m"] = self._manual_m_pw.get_raw_value()
                self._manual_m_pw.set_value(5)
            if self._manual_P_pw is not None:
                stash["-P"] = self._manual_P_pw.get_raw_value()
                self._manual_P_pw.set_value(True)
            if self._manual_lb_pw is not None:
                stash["-L"] = self._manual_lb_pw.get_raw_value()
                self._manual_lb_pw.set_value(True)
            self._td_saved_layout = stash
        else:
            stash = self._td_saved_layout or {}
            if self._manual_a_pw is not None and "-a" in stash:
                self._manual_a_pw.set_value(stash["-a"] if stash["-a"] is not None else 1.0)
            if self._manual_m_pw is not None and "-m" in stash:
                self._manual_m_pw.set_value(stash["-m"] if stash["-m"] is not None else 6)
            if self._manual_P_pw is not None and "-P" in stash:
                self._manual_P_pw.set_value(bool(stash["-P"]))
            if self._manual_lb_pw is not None and "-L" in stash:
                self._manual_lb_pw.set_value(bool(stash["-L"]))
            self._td_saved_layout = None

        # Hide/show the suppress-LB row in sync with the toggle.
        self._update_manual_lb_visibility()

    def _apply_instrument_default_margin(self) -> None:
        """Auto-update -m (and -a, for i1) widgets to the per-instrument default
        on instrument change.

        Only overwrites known preset values so a user who deliberately set a
        custom margin (e.g. 12) or scale (e.g. 0.85) keeps their value when
        flipping instruments.

        For instrument == "i1" the (margin, scale) pair comes from the
        Preferences → i1Pro Chart Defaults setting. For other instruments only
        the margin is touched (legacy behaviour).
        """
        if self._manual_instr_pw is None or self._manual_m_pw is None:
            return
        instr = self._manual_instr_pw.get_raw_value() or "i1"

        if instr == "i1":
            preset_key = str(self._settings.get(
                "i1pro_default_preset", I1PRO_DEFAULT_PRESET_KEY
            ))
            target_margin, target_scale = i1_defaults_from_preset(preset_key)
        else:
            target_margin = INSTRUMENT_DEFAULT_MARGIN.get(instr, 6)
            # Non-i1 instruments use the printtarg native default (-a 1.0).
            # Switching away from i1 must undo any 0.95 the i1pro preset set.
            target_scale = 1.0

        try:
            current_m = int(self._manual_m_pw.get_raw_value() or 6)
        except (TypeError, ValueError):
            current_m = None
        if current_m in (6, 10) and current_m != target_margin:
            self._manual_m_pw.set_value(target_margin)

        if self._manual_a_pw is not None:
            try:
                current_a = float(self._manual_a_pw.get_raw_value() or 1.0)
            except (TypeError, ValueError):
                current_a = None
            # Only override if the current scale is one of the known preset
            # values — leave custom scales (e.g. 0.85, 1.1) intact.
            if current_a is not None and any(
                abs(current_a - known) <= 0.01 for known in (1.0, 0.95)
            ) and abs(current_a - target_scale) > 0.01:
                self._manual_a_pw.set_value(target_scale)

        # i1iSis: default to A3+ portrait, no spacers, and unlimited strip
        # length — i1Profiler re-lays-out the chart anyway, so the values
        # printtarg ends up using only affect the layout preview. The
        # matched-default guards mirror the margin logic above so a user
        # who picked different values keeps their choice when flipping
        # instruments.
        if self._manual_paper_pw is not None:
            current_paper = self._manual_paper_pw.get_raw_value() or ""
            if instr == "isis" and current_paper == "A4":
                self._manual_paper_pw.set_value("329x483")
            elif instr != "isis" and current_paper == "329x483":
                self._manual_paper_pw.set_value("A4")

        for pw_attr in ("_manual_n_pw", "_manual_P_pw"):
            pw = getattr(self, pw_attr, None)
            if pw is None:
                continue
            current = bool(pw.get_raw_value())
            if instr == "isis" and not current:
                pw.set_value(True)
            elif instr != "isis" and current:
                pw.set_value(False)

    # ------------------------------------------------------------------
    # Auto patch-count (Manual mode)
    # ------------------------------------------------------------------

    def _on_auto_patches_toggled(self, checked: bool) -> None:
        """Enable/disable -f and Pages spinboxes; show 'Auto' placeholder in -f.

        The actual patch-count estimate runs at Generate-click — see
        _on_generate — so this handler is purely UI state.
        """
        if self._manual_pages_spin is not None:
            self._manual_pages_spin.setEnabled(checked)
        if self._manual_f_pw is None or self._manual_f_pw._control is None:
            return
        spin = self._manual_f_pw._control
        self._manual_f_pw.set_control_enabled(not checked, include_label=False)
        spin.blockSignals(True)
        if checked:
            # QSpinBox shows specialValueText whenever value == minimum.
            # -f's min is 0 (see data/parameters.yaml), so set 0 here.
            spin.setSpecialValueText("Auto")
            spin.setValue(0)
        else:
            spin.setSpecialValueText("")
        spin.blockSignals(False)
        self._refresh_manual_command_preview()

    # -- Auto -e / -B / -g checkboxes ----------------------------------
    _AUTO_NEUTRAL_MAP = {
        "white": ("_manual_e_pw", "_manual_auto_white_check"),
        "black": ("_manual_B_pw", "_manual_auto_black_check"),
        "grey":  ("_manual_g_pw", "_manual_auto_grey_check"),
    }

    def _on_auto_neutral_toggled(self, which: str, checked: bool) -> None:
        """Grey out the matching -e/-B/-g spinbox and show 'Auto' in it.

        The auto value itself is computed in _collect_manual /
        _refresh_manual_command_preview from the chart's total patch
        count via workflow.chart_creator.manual_neutrals.
        """
        pw_attr, _ = self._AUTO_NEUTRAL_MAP[which]
        pw = getattr(self, pw_attr, None)
        if pw is None or pw._control is None:
            return
        spin = pw._control
        pw.set_control_enabled(not checked, include_label=False)
        spin.blockSignals(True)
        if checked:
            # All three params have min 0 (see data/parameters.yaml), so
            # setting value to 0 lets specialValueText display "Auto".
            spin.setSpecialValueText("Auto")
            spin.setValue(0)
        else:
            spin.setSpecialValueText("")
        spin.blockSignals(False)
        self._refresh_manual_command_preview()

    def _load_auto_neutral_states(self, grey: bool, white: bool,
                                  black: bool) -> None:
        """Restore the three Auto checkbox states (settings or preset)."""
        for which, on in (("grey", grey), ("white", white), ("black", black)):
            _, chk_attr = self._AUTO_NEUTRAL_MAP[which]
            chk = getattr(self, chk_attr, None)
            if chk is not None:
                chk.setChecked(on)
                self._on_auto_neutral_toggled(which, on)

    def _connect_cal_mutex(self) -> None:
        k, i = self._manual_cal_k_pw, self._manual_cal_i_pw
        if k is None or i is None:
            return
        k.value_changed.connect(lambda: i.set_user_enabled(False) if k.is_enabled_by_user else None)
        i.value_changed.connect(lambda: k.set_user_enabled(False) if i.is_enabled_by_user else None)

    def _connect_spacer_mutex(self) -> None:
        n = self._manual_n_pw
        if n is None:
            return
        n.value_changed.connect(self._apply_spacer_mutex)
        if self._manual_b_pw is not None:
            self._manual_b_pw.value_changed.connect(self._apply_spacer_mutex)
        if self._manual_c_pw is not None:
            self._manual_c_pw.value_changed.connect(self._apply_spacer_mutex)
        self._apply_spacer_mutex()

    def _apply_spacer_mutex(self) -> None:
        n = self._manual_n_pw
        if n is None:
            return
        suppress = n.is_enabled_by_user
        b, c, A = self._manual_b_pw, self._manual_c_pw, self._manual_A_pw

        if suppress:
            for dep in (b, c, A):
                if dep is None:
                    continue
                if dep.is_enabled_by_user:
                    dep.set_user_enabled(False)
                dep.setEnabled(False)
            return

        if A is not None:
            A.setEnabled(True)

        b_on = b is not None and b.is_enabled_by_user
        c_on = c is not None and c.is_enabled_by_user
        if b is not None:
            b.setEnabled(not c_on)
        if c is not None:
            c.setEnabled(not b_on)

    def _connect_neutral_dep(self) -> None:
        """Grey out targen -n (Neutral Axis Steps) unless -c is supplied.

        targen's -n samples the profile-defined neutral axis and has no
        effect without a pre-conditioning profile (-c), so we disable the
        widget — and uncheck it — whenever -c is empty."""
        c, n = self._manual_targen_c_pw, self._manual_targen_n_pw
        if c is None or n is None:
            return
        c.value_changed.connect(self._apply_neutral_dep)
        self._apply_neutral_dep()

    def _apply_neutral_dep(self) -> None:
        c, n = self._manual_targen_c_pw, self._manual_targen_n_pw
        if c is None or n is None:
            return
        c_active = c.is_enabled_by_user and bool(c.get_value())
        if c_active:
            n.setEnabled(True)
        else:
            if n.is_enabled_by_user:
                n.set_user_enabled(False)
            n.setEnabled(False)

    def _connect_d_cascade(self) -> None:
        for i, pw in enumerate(self._d_cascade_widgets):
            pw.value_changed.connect(lambda _=None, idx=i: self._on_d_cascade(idx))

    def _rebuild_d_cascade_visibility(self) -> None:
        for i, pw in enumerate(self._d_cascade_widgets):
            if i == 0:
                pw.setVisible(True)
            else:
                pw.setVisible(self._d_cascade_widgets[i - 1].is_enabled_by_user)

    def _on_d_cascade(self, index: int) -> None:
        pw = self._d_cascade_widgets[index]
        nxt = index + 1
        if pw.is_enabled_by_user:
            if nxt < len(self._d_cascade_widgets):
                self._d_cascade_widgets[nxt].setVisible(True)
        else:
            for i in range(nxt, len(self._d_cascade_widgets)):
                w = self._d_cascade_widgets[i]
                w.set_user_enabled(False)
                w.setVisible(False)

    # ------------------------------------------------------------------
    # Preset helpers
    # ------------------------------------------------------------------

    def _load_presets_from_settings(self) -> dict:
        return _load_tab_presets("create_chart", self._settings)

    def _save_presets_to_settings(self, presets: dict) -> None:
        _save_tab_presets("create_chart", presets)

    def _is_deletable_preset(self, index: int) -> bool:
        """True only for user presets (Default and built-ins can't be deleted)."""
        data = self._preset_combo.itemData(index)
        return data is not None and data not in BUILTIN_PRESET_KEYS

    def _add_builtin_preset_item(
        self, label: str, key: str, tooltip: str, *, disabled: bool = False
    ) -> None:
        """Append a pinned, non-deletable preset entry (bold + tooltip).

        ``disabled`` greys the item out and makes it non-selectable while leaving
        it visible (see DISABLED_BUILTIN_PRESET_KEYS) — used to park a built-in
        that needs fixing without deleting its wiring.
        """
        if disabled:
            label = f"{label}  (temporarily unavailable)"
            tooltip = (
                "Temporarily unavailable — this built-in chart is being fixed and "
                "has been disabled for now. It will return in a later update."
            )
        self._preset_combo.addItem(label, userData=key)
        bi = self._preset_combo.count() - 1
        bi_font = self._preset_combo.font()
        bi_font.setBold(True)
        self._preset_combo.setItemData(bi, bi_font, Qt.ItemDataRole.FontRole)
        self._preset_combo.setItemData(bi, tooltip, Qt.ItemDataRole.ToolTipRole)
        if disabled:
            # Grey out + block selection via the underlying model item (the combo
            # uses a QStandardItemModel by default).
            item = self._preset_combo.model().item(bi)
            if item is not None:
                item.setEnabled(False)

    def _tc918_tooltip(self) -> str:
        """Tooltip text for the ti1-based TC9.18 built-in preset."""
        return (
            "Built-in chart — cannot be deleted.\n"
            "Loads the fixed TC9.18 patch set and lays it out with\n"
            "printtarg -ii1 -pA4 -t300 -L -m12 -M12 -b, then creates the\n"
            "target right away. You can adjust any setting afterwards and\n"
            "regenerate."
        )

    def _tc918_tooltip(self) -> str:
        """Tooltip text for the ti1-based TC9.18 built-in preset."""
        return (
            "Built-in chart — cannot be deleted.\n"
            "Loads the fixed TC9.18 patch set and lays it out with\n"
            "printtarg -ii1 -pA4 -t300 -L -m12 -M12 -b, then creates the\n"
            "target right away. You can adjust any setting afterwards and\n"
            "regenerate."
        )

    def _munki_tooltip(self, patches: int, white: int, black: int, grey: int) -> str:
        """Tooltip text for a ColorMunki built-in preset."""
        return (
            "Built-in preset — cannot be deleted.\n"
            f"Loads a {patches}-patch ColorMunki recipe with Triple density on:\n"
            f"targen -d2 -f{patches} -e{white} -B{black} -G -g{grey}\n"
            "printtarg -ii1 -pA4R -T300 -L -a1.30 -m5 -M5 -b -P\n"
            "printtarg lays it out with the denser i1Pro geometry and the\n"
            ".ti2 instrument is rewritten back to ColorMunki. Creates the\n"
            "target right away; you can adjust any setting and regenerate."
        )

    def _prebuilt_tooltip(self, paper: str) -> str:
        """Tooltip text for a prebuilt-files built-in preset."""
        return (
            "Built-in chart — cannot be deleted.\n"
            f"A complete, ready-made target laid out for {paper}.\n"
            "Picking it asks for a name, then copies the bundled patch set\n"
            "(.ti1 / .ti2 / TIFF pages) into a new folder under that name —\n"
            "no targen or printtarg is run, so those panels are greyed out.\n"
            "The copied TIFFs are loaded straight into the preview."
        )

    def _populate_preset_combo(self, presets: dict, select_name: str | None = None) -> None:
        self._preset_combo.blockSignals(True)
        self._preset_combo.clear()
        self._preset_combo.addItem("none", userData=None)
        # User presets first, then the built-ins below them. A preset saved with
        # "generate on select" gets a ▶ prefix so the user knows picking it
        # starts the chart, not just loads values. userData stays the bare name.
        for name in presets:
            if name in BUILTIN_PRESET_LABELS or name in BUILTIN_PRESET_KEYS:
                continue  # never let a user file shadow a built-in entry
            label = f"▶  {name}" if (isinstance(presets[name], dict)
                                     and presets[name].get("auto_run")) else name
            self._preset_combo.addItem(label, userData=name)
        # Built-in presets, pinned below the user's own and grouped by the
        # instrument they target. Groups (and the order within each) follow the
        # shared BUILTIN_PRESET_GROUPS registry verbatim — no re-sorting — so the
        # dropdown and the Built-in presets overlay show the instruments in the
        # exact same order. A separator line is drawn before the whole built-in
        # block (dividing it from the user presets) and again before each new
        # instrument group.
        # (instrument, label, key, tooltip)
        builtins = [
            (instr, combo_label, key, self._builtin_tooltip(key))
            for instr, entries in BUILTIN_PRESET_GROUPS
            for (combo_label, _overlay_label, key) in entries
        ]
        prev_instr: str | None = None
        for instr, label, key, tip in builtins:
            if instr != prev_instr:
                self._preset_combo.insertSeparator(self._preset_combo.count())
                prev_instr = instr
            self._add_builtin_preset_item(
                label, key, tip, disabled=key in DISABLED_BUILTIN_PRESET_KEYS
            )
        if select_name is not None:
            # Match by userData (the bare name), not the shown text, which may
            # carry a ▶ prefix for auto-run presets.
            idx = self._preset_combo.findData(select_name)
            if idx >= 0:
                self._preset_combo.setCurrentIndex(idx)
        self._preset_combo.blockSignals(False)
        self._last_preset_index = self._preset_combo.currentIndex()
        self._preset_del_btn.setEnabled(
            self._is_deletable_preset(self._preset_combo.currentIndex())
        )

    @staticmethod
    def _builtin_default_name(key: str) -> str:
        """Default target name suggested in the prompt for a built-in preset."""
        if key == TC918_PRESET_KEY:
            return TC918_TARGET_NAME
        if key in KNUT_PRESET_KEYS:
            return KNUT_PRESETS_BY_KEY[key].default_target_name
        if key in MUNKI_TARGEN:
            return f"ColorMunki-{MUNKI_TARGEN[key][0]}"
        if key in PREBUILT_PRESETS:
            return PREBUILT_PRESETS[key][1]
        return "chart"

    def _builtin_tooltip(self, key: str) -> str:
        """Combo/overlay tooltip for any built-in preset (per its kind)."""
        if key in KNUT_PRESET_KEYS:
            return self._knut_tooltip(key)
        return self._prebuilt_tooltip(_prebuilt_paper(key))

    @staticmethod
    def _knut_tooltip(key: str) -> str:
        """Tooltip for a TC9.18+Spyderprint (ti1 → printtarg) built-in preset."""
        p = KNUT_PRESETS_BY_KEY[key]
        instr = "i1Pro" if p.instrument == _KNUT_I1 else "ColorMunki (double density)"
        bits = [f"-p{p.paper}", f"-a{p.patch_scale:g}", f"-M{p.margin}"]
        if p.spacer_scale is not None:
            bits.append(f"-A{p.spacer_scale:g}")
        if p.seed is not None:
            bits.append(f"-R{p.seed}")
        return (
            "Built-in chart — cannot be deleted.\n"
            f"Loads the bundled 1168-patch TC9.18 + Spyderprint-greys set and\n"
            f"lays it out for the {instr} ({p.pages}-page):\n"
            f"printtarg -i{p.instrument} -T200 {' '.join(bits)}\n"
            "Creates the target right away; the patch set stays fixed but you\n"
            "can adjust any printtarg setting and regenerate."
        )

    def _prompt_target_name(self, default_name: str) -> str | None:
        """Ask for a target name before generating a built-in preset.

        Returns the chosen name, or None if the user cancelled. An empty entry
        falls back to `default_name`."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Name this target")
        dlg.setMinimumWidth(540)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(22, 20, 22, 16)
        lay.setSpacing(10)

        heading = QLabel("Name this target", dlg)
        heading.setStyleSheet("font-weight: bold;")
        lay.addWidget(heading)

        info = QLabel(
            "ChromIQ creates a folder with this name and reuses it for everything "
            "that follows — the printed chart, the measurements, and the finished "
            "ICC profile. Choose a name you'll still recognise weeks from now.\n\n"
            "A good name usually combines the things that make this profile unique:\n"
            "  •  the printer (e.g. EpsonP900)\n"
            "  •  the paper or media (e.g. CansonPlatine)\n"
            "  •  and the date or quality level (e.g. 2026-05 or HighQ)\n\n"
            "Example:  EpsonP900-CansonPlatine-2026-05\n\n"
            "Stick to letters, numbers, spaces and hyphens — avoid slashes and "
            "other punctuation so the folder name stays valid.",
            dlg,
        )
        info.setWordWrap(True)
        lay.addWidget(info)

        lay.addSpacing(8)               # breathing room above the field
        edit = QLineEdit(default_name, dlg)
        edit.setMinimumHeight(28)
        edit.selectAll()
        lay.addWidget(edit)
        lay.addSpacing(8)               # breathing room below the field

        bb = QDialogButtonBox(dlg)
        bb.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        bb.addButton("Generate", QDialogButtonBox.ButtonRole.AcceptRole)
        bb.rejected.connect(dlg.reject)
        bb.accepted.connect(dlg.accept)
        lay.addWidget(bb)

        edit.returnPressed.connect(dlg.accept)
        edit.setFocus()
        dlg.adjustSize()                # size to fit the wrapped content

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return self._file_mgr.strip_workfile_ext(edit.text().strip()) or default_name

    def _revert_preset_combo(self) -> None:
        """Restore the dropdown to the last committed selection (no re-apply)."""
        self._preset_combo.blockSignals(True)
        self._preset_combo.setCurrentIndex(self._last_preset_index)
        self._preset_combo.blockSignals(False)
        self._preset_del_btn.setEnabled(
            self._is_deletable_preset(self._last_preset_index)
        )

    def _open_builtin_preset_overlay(self) -> None:
        """Show the speech-bubble overlay of built-in presets under the star button."""
        from ui.theme import resolve_mode
        groups = [
            (instr, [(overlay_label, key) for (_combo, overlay_label, key) in entries])
            for instr, entries in BUILTIN_PRESET_GROUPS
        ]
        popup = BuiltinPresetPopup(groups, self)
        popup.set_appearance(resolve_mode(self._settings.get("appearance", "auto")))
        popup.selected.connect(self._activate_builtin_preset)
        # Keep a reference so the popup isn't garbage-collected while shown.
        self._builtin_preset_popup = popup
        popup.show_under(self._builtin_preset_btn)

    def _activate_builtin_preset(self, key: str) -> None:
        """Pick a built-in from the overlay — identical to choosing it in the dropdown.

        The built-ins live in the Manual presets dropdown, so route through it:
        switch to Manual (so the dropdown and greyed panels are visible), then
        select the matching entry, which fires _on_preset_selected — the name
        prompt + generate flow. Re-picking the current entry won't emit
        currentIndexChanged, so call the handler directly in that case."""
        idx = self._preset_combo.findData(key)
        if idx < 0:
            log.warning("Built-in preset overlay: key %r not in dropdown", key)
            return
        if self._current_mode() != "manual":
            self._switch_mode("manual")
        if idx == self._preset_combo.currentIndex():
            self._on_preset_selected(idx)
        else:
            self._preset_combo.setCurrentIndex(idx)

    def _on_preset_selected(self, index: int) -> None:
        # Group-divider separators aren't real choices. The combo skips them on
        # mouse/keyboard interaction, but guard anyway so one can never be
        # treated as a selection — restore the prior pick instead.
        if index > 0 and self._preset_combo.itemData(index) is None \
                and not self._preset_combo.itemText(index):
            self._revert_preset_combo()
            return
        data = self._preset_combo.itemData(index)

        # Temporarily-disabled built-ins are greyed out and unselectable in the
        # UI, but guard anyway so a programmatic selection can never apply one.
        if data in DISABLED_BUILTIN_PRESET_KEYS:
            self._revert_preset_combo()
            return

        # Built-in presets generate immediately, so prompt for a target name
        # first — otherwise the output folder is created under the preset's
        # default name. Cancel reverts the dropdown to the previous selection
        # and leaves everything (values, target name) untouched.
        if data in BUILTIN_PRESET_KEYS:
            if self._runner.is_running:
                log.warning("Built-in preset: a process is already running")
                self._revert_preset_combo()
                return
            name = self._prompt_target_name(self._builtin_default_name(data))
            if name is None:
                self._revert_preset_combo()
                return
            # Switching from the TC9.18 chart to another built-in clears the
            # expert printtarg overrides it forced on (margins, spacers, etc.).
            if self._tc918_active and data != TC918_PRESET_KEY:
                self._reset_tc918_overrides()
                self._tc918_active = False
                self._tc918_targen_sig = None
            # Switching away from a TC9.18+Spyderprint preset clears its printtarg
            # overrides; picking another one of them re-seeds cleanly, so only
            # reset when the new pick isn't itself one of them.
            if self._knut_active and data not in KNUT_PRESET_KEYS:
                self._reset_knut_overrides()
                self._knut_active = False
                self._knut_targen_sig = None
            # Leaving a prebuilt-files preset for a params-based built-in
            # (TC9.18 / ColorMunki) must re-enable the greyed param panels.
            if self._prebuilt_active and data not in PREBUILT_PRESETS:
                self._leave_prebuilt()
            self._preset_ti1_path = None  # built-ins are not ti1-user-presets
            self._preset_ti1_targen_sig = None
            # Start the freshly-picked built-in with its panels locked again.
            self._reset_override_checks()
            self._preset_del_btn.setEnabled(False)
            self._last_preset_index = index
            if data == TC918_PRESET_KEY:
                self._apply_tc918_preset(name)
            elif data in KNUT_PRESET_KEYS:
                self._apply_knut_preset(data, name)
            elif data in PREBUILT_PRESETS:
                self._apply_prebuilt_preset(data, name)
            else:
                self._apply_colormunki_td_preset(*MUNKI_TARGEN[data], target_name=name)
            # Final lock pass: covers the params-based ColorMunki presets (which
            # set no ti1/prebuilt flag, so their panels stay fully editable) and
            # re-asserts state after leaving a previous tc918/knut preset.
            self._update_preset_locks()
            return

        # Leaving the TC9.18 built-in chart for Default or a user preset clears
        # the expert printtarg overrides it forced on (margins -m/-M, black &
        # white spacers -b, …). The restores below only *set* flags the target
        # preset stores, so without this they would bleed through.
        if self._tc918_active:
            self._reset_tc918_overrides()
            self._tc918_active = False
            self._tc918_targen_sig = None
        # Same for a TC9.18+Spyderprint preset → Default / a user preset.
        if self._knut_active:
            self._reset_knut_overrides()
            self._knut_active = False
            self._knut_targen_sig = None
        # Leaving a prebuilt-files preset re-enables the greyed param panels.
        if self._prebuilt_active:
            self._leave_prebuilt()

        self._last_preset_index = index
        self._preset_del_btn.setEnabled(self._is_deletable_preset(index))
        s = self._settings
        if index == 0:
            for tool, widgets in self._manual_widgets.items():
                for pw in widgets:
                    if pw in self._d_cascade_widgets:
                        continue
                    # Use the same case-disambiguated key that _on_save_defaults
                    # writes, so single-char flags (-l, -g, …) round-trip here too.
                    key = _pw_settings_key(tool, pw.flag)
                    v = s.get(key)
                    if v is None:
                        # No saved default for this row → revert to its factory
                        # default (and clear any expert enable-checkbox). Without
                        # this, picking "Default" would leave a row the user
                        # changed but never saved untouched — the reported bug.
                        pw.reset_to_default()
                        continue
                    pw.set_value(v)
                    if pw.has_separate_enable:
                        pw.set_user_enabled(bool(s.get(f"{key}_enabled", False)))
            for idx, pw in enumerate(self._d_cascade_widgets):
                v = s.get(f"manual_targen_-D_{idx}")
                if v is not None:
                    pw.set_value(v)
                pw.set_user_enabled(bool(s.get(f"manual_targen_-D_{idx}_enabled", False)))
            self._rebuild_d_cascade_visibility()
            if self._bit8_radio is not None and self._bit16_radio is not None:
                is_16bit = bool(s.get("manual_printtarg_tiff_16bit", False))
                self._bit16_radio.setChecked(is_16bit)
                self._bit8_radio.setChecked(not is_16bit)
            if self._manual_pages_spin is not None:
                self._manual_pages_spin.setValue(int(s.get("manual_pages", 1)))
            if self._manual_auto_patches_check is not None:
                auto_on = bool(s.get("manual_auto_patches", False))
                self._manual_auto_patches_check.setChecked(auto_on)
                self._on_auto_patches_toggled(auto_on)
            self._load_auto_neutral_states(
                grey  = bool(s.get("manual_auto_grey",  False)),
                white = bool(s.get("manual_auto_white", False)),
                black = bool(s.get("manual_auto_black", False)),
            )
            self._manual_left_clip_check.setChecked(
                bool(s.get("chart_left_clip_info", False))
            )
            if self._manual_td_check is not None:
                self._manual_td_check.setChecked(
                    bool(s.get("manual_printtarg__triple_density", False))
                )
            self._preset_ti1_path = None      # Default builds via targen
        else:
            name = self._preset_combo.currentData()
            presets = self._load_presets_from_settings()
            pdata = presets.get(name, {})
            self._restore_user_preset(pdata)
            # A user preset that bundled a .ti1 builds from it (skip targen). Point
            # Generate at the sidecar file if it's present; otherwise fall back to
            # the normal targen path.
            self._preset_ti1_path = None
            self._preset_ti1_targen_sig = None
            if isinstance(pdata, dict) and pdata.get("attached_ti1"):
                p = _preset_sidecar_path("create_chart", str(name), ".ti1")
                if p.is_file():
                    self._preset_ti1_path = p
                    # Snapshot targen so the override box can opt into a fresh
                    # targen run (changed → different patches), like the built-ins.
                    self._preset_ti1_targen_sig = self._targen_signature()
                else:
                    log.warning("preset '%s' marked attached_ti1 but %s is missing",
                                name, p)
        # Every Default / user-preset selection re-establishes the lock state:
        # untick any leftover override and grey the panels a ti1 preset needs.
        self._reset_override_checks()
        self._update_preset_locks()
        self._update_manual_lb_visibility()

        # A user preset flagged "generate on select" (▶) prompts for a target
        # name and then generates — same prompt as the built-ins. The values are
        # already loaded above, so cancel just leaves the preset selected without
        # generating (keeping it selectable for delete / re-save).
        if data is not None and data not in BUILTIN_PRESET_KEYS:
            presets = self._load_presets_from_settings()
            pdata = presets.get(data, {})
            if isinstance(pdata, dict) and pdata.get("auto_run"):
                if self._runner.is_running:
                    return
                tname = self._prompt_target_name(str(data))
                if tname is None:
                    return
                if self._manual_target_name_edit is not None:
                    self._manual_target_name_edit.setText(tname)
                self._on_generate()

    def _restore_user_preset(self, data: dict) -> None:
        """Apply a saved user preset's stored values to the manual widgets."""
        for tool, widgets in self._manual_widgets.items():
            for pw in widgets:
                if pw in self._d_cascade_widgets:
                    continue
                v = data.get(f"{tool}_{pw.flag}")
                if v is not None:
                    pw.set_value(v)
                # Re-arm expert non-boolean rows from the stored enable state.
                # Only act when the key was persisted, so presets saved before
                # this fix (which stored a value regardless of the checkbox)
                # don't suddenly turn their flag on.
                if pw.has_separate_enable:
                    en = data.get(f"{tool}_{pw.flag}_enabled")
                    if en is not None:
                        pw.set_user_enabled(bool(en))
        for idx, pw in enumerate(self._d_cascade_widgets):
            v = data.get(f"targen_-D_{idx}")
            if v is not None:
                pw.set_value(v)
            pw.set_user_enabled(bool(data.get(f"targen_-D_{idx}_enabled", False)))
        self._rebuild_d_cascade_visibility()
        if self._bit8_radio is not None and self._bit16_radio is not None:
            is_16bit = bool(data.get("tiff_16bit", False))
            self._bit16_radio.setChecked(is_16bit)
            self._bit8_radio.setChecked(not is_16bit)
        if self._manual_pages_spin is not None:
            self._manual_pages_spin.setValue(int(data.get("pages", 1)))
        if self._manual_auto_patches_check is not None:
            auto_on = bool(data.get("auto_patches", False))
            self._manual_auto_patches_check.setChecked(auto_on)
            self._on_auto_patches_toggled(auto_on)
        self._load_auto_neutral_states(
            grey  = bool(data.get("auto_grey",  False)),
            white = bool(data.get("auto_white", False)),
            black = bool(data.get("auto_black", False)),
        )
        self._manual_left_clip_check.setChecked(bool(data.get("left_clip_info", False)))
        # Apply triple-density last so its toggle handler sees the restored
        # -a / -m / -P values and stashes them correctly.
        if self._manual_td_check is not None:
            self._manual_td_check.setChecked(bool(data.get("triple_density", False)))

    def _on_preset_save(self) -> None:
        capture: dict = {}
        # When Triple density is active the four widgets it owns currently
        # show the i1Pro-emulation overrides; persisting those into the
        # preset would corrupt the stash on load and trap the preset in
        # TD-shaped values. Use the stashed pre-TD values for those flags.
        td_stash = (self._td_saved_layout
                    if (self._manual_td_check is not None
                        and self._manual_td_check.isChecked()
                        and self._td_saved_layout)
                    else None)
        for tool, widgets in self._manual_widgets.items():
            for pw in widgets:
                if pw in self._d_cascade_widgets:
                    continue
                if td_stash is not None and tool == "printtarg" and pw.flag in td_stash:
                    v = td_stash[pw.flag]
                else:
                    v = pw.get_raw_value()
                if v is not None:
                    capture[f"{tool}_{pw.flag}"] = v
                # Persist the enable-checkbox state for expert non-boolean rows
                # so the flag is re-armed when the preset is recalled.
                if pw.has_separate_enable:
                    capture[f"{tool}_{pw.flag}_enabled"] = pw.is_enabled_by_user
        for idx, pw in enumerate(self._d_cascade_widgets):
            capture[f"targen_-D_{idx}"] = pw.get_raw_value()
            capture[f"targen_-D_{idx}_enabled"] = pw.is_enabled_by_user
        capture["tiff_16bit"] = (
            self._bit16_radio.isChecked() if self._bit16_radio is not None else False
        )
        capture["auto_patches"] = (
            self._manual_auto_patches_check.isChecked()
            if self._manual_auto_patches_check is not None else False
        )
        capture["auto_grey"] = (
            self._manual_auto_grey_check.isChecked()
            if self._manual_auto_grey_check is not None else False
        )
        capture["auto_white"] = (
            self._manual_auto_white_check.isChecked()
            if self._manual_auto_white_check is not None else False
        )
        capture["auto_black"] = (
            self._manual_auto_black_check.isChecked()
            if self._manual_auto_black_check is not None else False
        )
        capture["pages"] = (
            int(self._manual_pages_spin.value())
            if self._manual_pages_spin is not None else 1
        )
        capture["left_clip_info"] = bool(self._manual_left_clip_check.isChecked())
        capture["triple_density"] = bool(
            self._manual_td_check is not None and self._manual_td_check.isChecked()
        )
        # Pre-fill name + checkbox from the currently-selected user preset, so
        # re-saving to tweak it (e.g. just toggling auto-run) is one step.
        cur_key = self._preset_combo.currentData()
        prefill_name, prefill_run, prefill_attach = "", False, False
        if cur_key is not None and cur_key not in BUILTIN_PRESET_KEYS:
            prefill_name = str(cur_key)
            existing = self._load_presets_from_settings().get(cur_key, {})
            prefill_run = bool(isinstance(existing, dict) and existing.get("auto_run"))
            prefill_attach = bool(isinstance(existing, dict) and existing.get("attached_ti1"))
        # A patch set can only be attached if one is currently loaded.
        have_ti1 = (self._current_ti1_path is not None
                    and self._current_ti1_path.is_file())

        dlg = QDialog(self)
        dlg.setWindowTitle("Save Preset")
        dlg.setMinimumWidth(500)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(22, 20, 22, 16)
        lay.setSpacing(10)

        heading = QLabel("Save preset", dlg)
        heading.setStyleSheet("font-weight: bold;")
        lay.addWidget(heading)
        info = QLabel(
            "Give this preset a name. All current Manual-mode parameter values are "
            "saved under it and can be recalled any time from the preset list. "
            "Re-saving with an existing name overwrites it.",
            dlg,
        )
        info.setWordWrap(True)
        lay.addWidget(info)

        lay.addSpacing(6)
        edit = QLineEdit(prefill_name, dlg)
        edit.setMinimumHeight(28)
        edit.setPlaceholderText("Preset name")
        edit.selectAll()
        lay.addWidget(edit)

        run_chk = QCheckBox(
            "Generate the chart immediately when this preset is selected", dlg)
        run_chk.setChecked(prefill_run)
        lay.addWidget(run_chk)
        run_note = QLabel(
            "When on, picking this preset asks for a target name and then creates "
            "the chart straight away (it's shown with a ▶ in the list), instead of "
            "only loading the values. This is saved inside the preset file, so it "
            "travels with a shared preset.",
            dlg,
        )
        run_note.setWordWrap(True)
        run_note.setObjectName("info")
        lay.addWidget(run_note)

        lay.addSpacing(6)
        attach_chk = QCheckBox(
            "Build from the currently loaded patch set (attach its .ti1)", dlg)
        attach_chk.setChecked(prefill_attach and have_ti1)
        attach_chk.setEnabled(have_ti1)
        lay.addWidget(attach_chk)
        if have_ti1:
            attach_text = (
                "When on, the patch set currently loaded (its .ti1) is saved next to "
                "this preset. Selecting the preset then builds the chart straight from "
                "that .ti1 — targen is skipped and printtarg just lays it out, exactly "
                "like the built-in presets. The .ti1 is stored inside the preset folder "
                "under the preset's name, so it travels with a shared preset."
            )
        else:
            attach_text = (
                "Generate or load a chart first to enable this — there's no patch set "
                "(.ti1) loaded right now to attach. When a set is loaded, you can save "
                "it with the preset so selecting it skips targen and builds from that "
                "exact .ti1."
            )
        attach_note = QLabel(attach_text, dlg)
        attach_note.setWordWrap(True)
        attach_note.setObjectName("info")
        lay.addWidget(attach_note)

        lay.addSpacing(4)
        bb = QDialogButtonBox(dlg)
        bb.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        bb.addButton("Save", QDialogButtonBox.ButtonRole.AcceptRole)
        bb.rejected.connect(dlg.reject)
        bb.accepted.connect(dlg.accept)
        lay.addWidget(bb)
        edit.returnPressed.connect(dlg.accept)
        edit.setFocus()
        dlg.adjustSize()

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        name = edit.text().strip()
        if not name:
            return
        capture["auto_run"] = bool(run_chk.isChecked())
        attach = bool(attach_chk.isChecked() and have_ti1)
        capture["attached_ti1"] = attach
        # Manage the .ti1 sidecar next to the preset .json. Copy the loaded set in
        # when attaching; remove any stale one when the option is turned off.
        sidecar = _preset_sidecar_path("create_chart", name, ".ti1")
        try:
            if attach:
                import shutil
                sidecar.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(self._current_ti1_path, sidecar)
            elif sidecar.is_file():
                sidecar.unlink()
        except OSError as exc:
            log.warning("preset .ti1 sidecar update failed for '%s': %s", name, exc)
            if attach:
                capture["attached_ti1"] = False
        presets = self._load_presets_from_settings()
        presets[name] = capture
        self._save_presets_to_settings(presets)
        self._populate_preset_combo(presets, select_name=name)

    def _on_preset_delete(self) -> None:
        if not self._is_deletable_preset(self._preset_combo.currentIndex()):
            return  # Default and the built-in presets are protected
        # Use userData (bare name), not the shown text which may carry a ▶ prefix.
        name = self._preset_combo.currentData()
        dlg = QDialog(self)
        dlg.setWindowTitle("Delete Preset")
        dlg.setMinimumWidth(460)
        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setSpacing(10)
        dlg_layout.setContentsMargins(20, 20, 20, 16)
        heading = QLabel(f'Delete the preset "{name}"?', dlg)
        heading.setStyleSheet("font-weight: bold;")
        heading.setWordWrap(True)
        dlg_layout.addWidget(heading)
        info = QLabel(
            "All parameter values saved in this preset will be permanently removed. "
            "This cannot be undone.",
            dlg,
        )
        info.setWordWrap(True)
        dlg_layout.addWidget(info)
        bb = QDialogButtonBox(dlg)
        bb.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        bb.addButton("Delete", QDialogButtonBox.ButtonRole.AcceptRole)
        bb.rejected.connect(dlg.reject)
        bb.accepted.connect(dlg.accept)
        dlg_layout.addWidget(bb)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        presets = self._load_presets_from_settings()
        presets.pop(name, None)
        self._save_presets_to_settings(presets)
        # Remove the attached .ti1 sidecar, if any, so it doesn't orphan.
        sidecar = _preset_sidecar_path("create_chart", str(name), ".ti1")
        if sidecar.is_file():
            try:
                sidecar.unlink()
            except OSError as exc:
                log.warning("could not remove preset .ti1 sidecar %s: %s", sidecar, exc)
        self._populate_preset_combo(presets)

    # ------------------------------------------------------------------
    # TC9.18 built-in preset
    # ------------------------------------------------------------------

    @staticmethod
    def _tc918_ti1_path() -> Path:
        """Absolute path to the bundled TC9.18 patch set (dev + frozen)."""
        return resource_path(TC918_TI1_ASSET)

    def _reset_tc918_overrides(self) -> None:
        """Revert the printtarg flags the TC9.18 preset forces to YAML defaults.

        Run when the user switches away from the built-in chart so its expert
        overrides (notably -m margins and -b black-and-white spacers) don't
        carry into Default or another preset.

        The recipe pins -a to 1.0; resetting it to the YAML default (also 1.0)
        would leave it at 1.0 even on i1, where the instrument default is 0.95.
        So after reverting, re-apply the per-instrument margin/scale defaults —
        the last word, since the -i reset earlier in the loop would otherwise be
        undone by -a's own reset."""
        for flag in TC918_PRINTTARG:
            for pw in self._manual_widgets.get("printtarg", []):
                if pw.flag == flag:
                    pw.reset_to_default()
        self._apply_instrument_default_margin()

    def _set_manual_value(self, tool: str, flag: str, value: Any) -> None:
        """Set the value of a single manual ParameterWidget, if present."""
        for pw in self._manual_widgets.get(tool, []):
            if pw.flag == flag:
                pw.set_value(value)
                # Expert non-boolean rows (e.g. -m, -A) only emit their flag
                # when their enable-checkbox is ticked; turn it on for any
                # value we deliberately set so it reaches the command.
                if value not in (None, False):
                    pw.set_user_enabled(True)
                return

    def _reset_manual_value(self, tool: str, flag: str) -> None:
        """Revert a single manual widget to its YAML default and disable it.

        For expert non-boolean rows (-A, -R, …) this also unticks the enable
        checkbox, so a flag a previously-selected preset turned on can't leak
        into the next one."""
        for pw in self._manual_widgets.get(tool, []):
            if pw.flag == flag:
                pw.reset_to_default()
                return

    def _targen_signature(self) -> list:
        """Snapshot of every targen-affecting control.

        printtarg controls are excluded on purpose: changing the *layout*
        (patch size, margins, spacers…) should still re-lay-out the same
        bundled patches, while changing anything that would alter the patch
        *set* means the user wants a fresh targen-generated chart.
        """
        sig: list = []
        for pw in self._manual_widgets.get("targen", []):
            sig.append((pw.flag, pw.get_raw_value(), pw.is_enabled_by_user))
        for label, chk in (
            ("auto_patches", self._manual_auto_patches_check),
            ("auto_grey",    self._manual_auto_grey_check),
            ("auto_white",   self._manual_auto_white_check),
            ("auto_black",   self._manual_auto_black_check),
        ):
            if chk is not None:
                sig.append((label, chk.isChecked()))
        if self._manual_pages_spin is not None:
            sig.append(("pages", int(self._manual_pages_spin.value())))
        return sig

    def _printtarg_signature(self) -> list:
        """Snapshot of every printtarg (layout) control.

        Used by the prebuilt-files presets to tell a pure layout change (re-run
        printtarg on the bundled .ti1, keeping the patches) from no change at all
        (copy the bundled files verbatim)."""
        sig: list = []
        for pw in self._manual_widgets.get("printtarg", []):
            sig.append((pw.flag, pw.get_raw_value(), pw.is_enabled_by_user))
        if self._bit16_radio is not None:
            sig.append(("bit16", self._bit16_radio.isChecked()))
        if self._manual_td_check is not None:
            sig.append(("triple", self._manual_td_check.isChecked()))
        return sig

    # ------------------------------------------------------------------
    # Preset panel locks (greying targen / printtarg while a preset is active)
    # ------------------------------------------------------------------

    def _ti1_preset_active(self) -> bool:
        """True while a preset that supplies a fixed patch set (.ti1) is active.

        Covers the TC9.18 built-in, Knut's TC9.18+Spyderprint presets, and any
        user preset that bundled a .ti1 — for all of these targen is skipped, so
        its panel is greyed unless the user opts in."""
        return bool(
            self._tc918_active
            or self._knut_active
            or self._preset_ti1_path is not None
        )

    def _update_preset_locks(self) -> None:
        """Show/hide the override rows and grey the panels they guard.

        • A ti1 preset greys only targen (printtarg stays editable).
        • A prebuilt-files preset greys both targen and printtarg.
        • No preset → both override rows hidden, both panels editable.
        Each panel is enabled when no lock applies, or when its override box is
        ticked."""
        ti1 = self._ti1_preset_active()
        prebuilt = self._prebuilt_active
        show_targen_cb = ti1 or prebuilt
        show_printtarg_cb = prebuilt

        if self._override_targen_row is not None:
            self._override_targen_row.setVisible(show_targen_cb)
        if self._override_printtarg_row is not None:
            self._override_printtarg_row.setVisible(show_printtarg_cb)

        targen_unlocked = (
            not show_targen_cb
            or (self._override_targen_check is not None
                and self._override_targen_check.isChecked())
        )
        printtarg_unlocked = (
            not show_printtarg_cb
            or (self._override_printtarg_check is not None
                and self._override_printtarg_check.isChecked())
        )
        for w in self._manual_targen_content:
            w.setEnabled(targen_unlocked)
        for w in self._manual_printtarg_content:
            w.setEnabled(printtarg_unlocked)

    def _reset_override_checks(self) -> None:
        """Untick both override boxes without firing their pop-up.

        Called on every preset selection so a freshly chosen preset always starts
        locked. blockSignals keeps the toggle from thrashing _update_preset_locks
        mid-selection (the caller re-applies the lock state afterwards)."""
        for cb in (self._override_targen_check, self._override_printtarg_check):
            if cb is not None and cb.isChecked():
                cb.blockSignals(True)
                cb.setChecked(False)
                cb.blockSignals(False)

    def _on_override_clicked(self, tool: str, checked: bool) -> None:
        """User ticked/unticked an override box — warn (once) when unlocking.

        Fires only on real clicks (not programmatic setChecked), so the warning
        pop-up appears exactly when the user themselves unlocks a panel."""
        if not checked:
            return
        if tool == "targen":
            InfoDialog(_OVERRIDE_TARGEN_POPUP_TITLE, _OVERRIDE_TARGEN_POPUP_BODY,
                       self, min_width=560).exec()
        else:
            InfoDialog(_OVERRIDE_PRINTTARG_POPUP_TITLE, _OVERRIDE_PRINTTARG_POPUP_BODY,
                       self, min_width=560).exec()

    def _apply_tc918_preset(self, target_name: str | None = None) -> None:
        """Seed the fixed TC9.18 layout and create the target from the bundled .ti1."""
        if self._runner.is_running:
            log.warning("TC9.18 preset: a process is already running")
            return
        ti1 = self._tc918_ti1_path()
        if not ti1.is_file():
            InfoDialog(
                "TC9.18 chart not found",
                "The built-in TC9.18 patch set could not be located:\n\n"
                f"{ti1}\n\nThe app bundle may be incomplete.",
                self, min_width=520,
            ).exec()
            return

        # Triple density / Auto patch count must be off before seeding values,
        # otherwise they hijack the -a / -m / -e / -B widgets we set below.
        if self._manual_td_check is not None:
            self._manual_td_check.setChecked(False)
        if self._manual_auto_patches_check is not None:
            self._manual_auto_patches_check.setChecked(False)
            self._on_auto_patches_toggled(False)
        self._load_auto_neutral_states(grey=False, white=False, black=False)

        # Fixed printtarg layout (the Pharmacist recipe).
        for flag, value in TC918_PRINTTARG.items():
            self._set_manual_value("printtarg", flag, value)

        # Best-effort targen description of the bundled chart (white/black
        # patches and total set size read straight from the .ti1 header). The
        # chart is built from the .ti1 itself, so these are descriptive only —
        # but they make the panel reflect what was loaded, and changing any of
        # them is what tells "Generate Chart" to switch to a fresh targen run.
        self._set_manual_value("targen", "-f", 918)
        self._set_manual_value("targen", "-e", 4)
        self._set_manual_value("targen", "-B", 4)

        # 8-bit output (the recipe doesn't ask for 16-bit).
        if self._bit8_radio is not None:
            self._bit8_radio.setChecked(True)

        # Output name: the one the user typed in the prompt (falls back to the
        # default). Stays editable in the Target name field for a regenerate.
        if self._manual_target_name_edit is not None:
            self._manual_target_name_edit.setText(target_name or TC918_TARGET_NAME)

        self._tc918_active = True
        self._tc918_targen_sig = self._targen_signature()
        self._update_preset_locks()      # grey targen (printtarg stays editable)
        self._refresh_manual_command_preview()
        self._generate_from_ti1(ti1)

    def _apply_colormunki_td_preset(
        self, patches: int, white: int, black: int, grey: int,
        target_name: str | None = None,
    ) -> None:
        """Load a ColorMunki + Triple-density recipe and generate it immediately.

        Produces (example for 324 / 2 / 2 / 16):
            targen   -d2 -f324 -e2 -B2 -G -g16
            printtarg -ii1 -pA4R -T300 -L -a1.30 -m5 -M5 -b -P
        Triple density makes printtarg use the denser i1Pro geometry (-ii1) while
        chart_creator rewrites the .ti2 TARGET_INSTRUMENT back to ColorMunki.
        Like TC9.18, selecting the preset creates the target right away; all
        settings stay editable for a regenerate afterwards."""
        if self._runner.is_running:
            log.warning("ColorMunki preset: a process is already running")
            return
        # Clear modes that would otherwise hijack the seeded -f / -e / -B / -g.
        if self._manual_auto_patches_check is not None:
            self._manual_auto_patches_check.setChecked(False)
            self._on_auto_patches_toggled(False)
        self._load_auto_neutral_states(grey=False, white=False, black=False)

        # Instrument must be ColorMunki *before* Triple density is enabled — TD
        # is gated to CM and the TD row is hidden (and force-unchecked) otherwise.
        self._set_manual_value("printtarg", "-i", "CM")
        self._set_manual_value("printtarg", "-p", "A4R")
        if self._bit16_radio is not None:
            self._bit16_radio.setChecked(True)          # 16-bit TIFF (→ -T300)
        self._set_manual_value("printtarg", "-b", True)  # B&W spacers

        # targen recipe.
        self._set_manual_value("targen", "-d", "2")
        self._set_manual_value("targen", "-f", patches)
        self._set_manual_value("targen", "-e", white)
        self._set_manual_value("targen", "-B", black)
        self._set_manual_value("targen", "-G", True)
        self._set_manual_value("targen", "-g", grey)

        if self._manual_pages_spin is not None:
            self._manual_pages_spin.setValue(1)

        # Enable Triple density LAST: its toggle handler seeds -a1.3 / -m5 / -P /
        # -L and arms the .ti2 ColorMunki rewrite. Seeding it after the values
        # above means those four are deliberately TD-driven (matching the recipe).
        if self._manual_td_check is not None:
            self._manual_td_check.setChecked(True)

        # Output name: the one the user typed in the prompt (falls back to the
        # default). Stays editable in the Target name field for a regenerate.
        if self._manual_target_name_edit is not None:
            self._manual_target_name_edit.setText(target_name or f"ColorMunki-{patches}")

        self._refresh_manual_command_preview()
        # Auto-generate immediately, like the TC9.18 preset.
        self._on_generate()

        self._refresh_manual_command_preview()

    # ------------------------------------------------------------------
    # TC9.18 + Spyderprint-greys presets (shared .ti1 → printtarg)
    # ------------------------------------------------------------------

    @staticmethod
    def _knut_ti1_path() -> Path:
        """Absolute path to the bundled 1168-patch TC9.18+Spyderprint .ti1."""
        return resource_path(KNUT_TI1_ASSET)

    def _seed_knut_preset(self, key: str, target_name: str | None = None) -> None:
        """Load a TC9.18+Spyderprint preset's fixed printtarg layout into the panel.

        Sets every printtarg control the recipe touches (and resets the optional
        -A / -R rows when it doesn't), so the layout is fully determined no matter
        which preset was selected before. Split from _apply_knut_preset so it can
        be unit-tested without running printtarg."""
        p = KNUT_PRESETS_BY_KEY[key]

        # Clear modes that would otherwise hijack the seeded printtarg values.
        if self._manual_td_check is not None:
            self._manual_td_check.setChecked(False)
        if self._manual_auto_patches_check is not None:
            self._manual_auto_patches_check.setChecked(False)
            self._on_auto_patches_toggled(False)
        self._load_auto_neutral_states(grey=False, white=False, black=False)

        # Instrument first — it drives -h visibility and the per-instrument
        # default margin; we set the margin explicitly afterwards so ours wins.
        self._set_manual_value("printtarg", "-i", p.instrument)
        self._set_manual_value("printtarg", "-p", p.paper)
        self._set_manual_value("printtarg", "-t", KNUT_DPI)        # dpi (with -T)
        if self._bit16_radio is not None:
            self._bit16_radio.setChecked(True)                     # 16-bit → -T200
        self._set_manual_value("printtarg", "-a", p.patch_scale)
        self._set_manual_value("printtarg", "-P", True)            # don't limit strips
        self._set_manual_value("printtarg", "-m", p.margin)        # → -m/-M
        self._set_manual_value("printtarg", "-L", False)           # keep left clip border
        self._set_manual_value("printtarg", "-r", False)           # randomise (default)
        self._set_manual_value("printtarg", "-b", False)           # coloured spacers
        self._set_manual_value("printtarg", "-h", p.double_density)  # CM double density
        if p.spacer_scale is not None:
            self._set_manual_value("printtarg", "-A", p.spacer_scale)
        else:
            self._reset_manual_value("printtarg", "-A")
        if p.seed is not None:
            self._set_manual_value("printtarg", "-R", p.seed)
        else:
            self._reset_manual_value("printtarg", "-R")

        # Descriptive targen values (the bundled patch set; .ti1 is the real
        # source, so these only make the panel reflect what was loaded).
        self._set_manual_value("targen", "-f", KNUT_PATCHES)
        self._set_manual_value("targen", "-e", KNUT_WHITE)
        self._set_manual_value("targen", "-B", KNUT_BLACK)

        if self._manual_pages_spin is not None:
            self._manual_pages_spin.setValue(p.pages)
        if self._manual_target_name_edit is not None:
            self._manual_target_name_edit.setText(target_name or p.default_target_name)

    def _apply_knut_preset(self, key: str, target_name: str | None = None) -> None:
        """Seed a TC9.18+Spyderprint preset and build it from the bundled .ti1."""
        if self._runner.is_running:
            log.warning("TC9.18+Spyderprint preset: a process is already running")
            return
        ti1 = self._knut_ti1_path()
        if not ti1.is_file():
            InfoDialog(
                "Patch set not found",
                "The bundled TC9.18 + Spyderprint-greys patch set could not be "
                f"located:\n\n{ti1}\n\nThe app bundle may be incomplete.",
                self, min_width=520,
            ).exec()
            return
        self._seed_knut_preset(key, target_name)
        self._knut_active = True
        # Snapshot the targen controls so later "Generate" clicks know whether to
        # re-lay-out the bundled .ti1 (printtarg only, targen untouched) or build a
        # fresh targen chart (the user changed a targen setting) — mirrors the
        # TC9.18 mechanism in _on_generate. The .ti1 is the fixed OFPS patch set,
        # so it can't be recreated by re-running targen.
        self._knut_targen_sig = self._targen_signature()
        self._update_preset_locks()      # grey targen (printtarg stays editable)
        self._refresh_manual_command_preview()
        self._generate_from_ti1(ti1)

    def _reset_knut_overrides(self) -> None:
        """Revert the printtarg flags a TC9.18+Spyderprint preset forced on.

        Run when the user switches away from one (to Default / a user preset / a
        different built-in) so its layout overrides don't carry over. Mirrors
        _reset_tc918_overrides: revert to YAML defaults, then re-apply the
        per-instrument margin (the last word, after -i resets to its default)."""
        for flag in ("-i", "-p", "-t", "-a", "-P", "-m", "-L", "-r", "-b",
                     "-h", "-A", "-R"):
            self._reset_manual_value("printtarg", flag)
        self._apply_instrument_default_margin()

    # ------------------------------------------------------------------
    # Prebuilt-files built-in presets (TC9.24 A4 / Letter)
    # ------------------------------------------------------------------

    @staticmethod
    def _prebuilt_instrument(key: str) -> str:
        """printtarg -i code a prebuilt preset is laid out for, from its asset path.

        The asset stem is ``.../<instrument>/<paper>/<target>/<target>``; the
        instrument folder is the fourth component from the end. Used to seed the
        printtarg panel so an override re-layout starts from the right device."""
        stem = PREBUILT_PRESETS.get(key, ("",))[0]
        parts = stem.split("/")
        instr = parts[-4] if len(parts) >= 4 else ""
        return {"i1pro": "i1", "colormunki": "CM"}.get(instr, "i1")

    @staticmethod
    def _prebuilt_paper_code(key: str) -> str:
        """printtarg -p code a prebuilt preset is laid out for, from its asset path."""
        stem = PREBUILT_PRESETS.get(key, ("",))[0]
        parts = stem.split("/")
        paper = parts[-3] if len(parts) >= 3 else ""
        # Map the asset folder name to a valid printtarg -p code (see PAPER_SIZES).
        return {"a4": "A4", "a3": "A3", "a3plus": "329x483",
                "letter": "Letter"}.get(paper, "A4")

    def _leave_prebuilt(self) -> None:
        """Clear prebuilt-files state and re-enable the param panels."""
        self._prebuilt_active = False
        self._prebuilt_key = None
        self._prebuilt_targen_sig = None
        self._prebuilt_printtarg_sig = None
        self._reset_override_checks()
        self._update_preset_locks()

    def _apply_prebuilt_preset(self, key: str, target_name: str) -> None:
        """Select a prebuilt-files preset: grey the panels and copy the bundle.

        Both panels start locked. The instrument and paper the bundle was made
        for are seeded so that, if the user unlocks the layout and changes it,
        a printtarg re-run starts from the right device/page — and so the
        "did the layout change?" check has a sensible baseline."""
        self._prebuilt_active = True
        self._prebuilt_key = key
        self._reset_override_checks()
        # Seed the device + page the bundle was made for. printtarg is re-run from
        # the bundled .ti1 only if the user unlocks the layout and edits it.
        self._set_manual_value("printtarg", "-i", self._prebuilt_instrument(key))
        self._set_manual_value("printtarg", "-p", self._prebuilt_paper_code(key))
        if self._manual_target_name_edit is not None:
            self._manual_target_name_edit.setText(target_name)
        # Baselines for the Generate-time change detection, taken after seeding.
        self._prebuilt_targen_sig = self._targen_signature()
        self._prebuilt_printtarg_sig = self._printtarg_signature()
        self._update_preset_locks()      # grey both panels
        self._create_prebuilt_target(key, target_name)

    def _create_prebuilt_target(self, key: str, target_name: str) -> None:
        """Copy a bundled prebuilt target into the project's current run and load it.

        No targen/printtarg is run: the bundled .ti1/.ti2 and TIFF pages are
        copied into runs/<current>/ under the fixed ``chart`` stem and the TIFFs
        are loaded into the preview, then routed downstream like a normal chart."""
        import shutil
        if self._runner.is_running:
            log.warning("Prebuilt preset: a process is already running")
            return
        stem_rel, default_name = PREBUILT_PRESETS[key]
        src_ti1 = resource_path(f"{stem_rel}.ti1")
        src_ti2 = resource_path(f"{stem_rel}.ti2")
        src_dir = src_ti1.parent
        src_stem = src_ti1.stem
        src_tiffs = sorted(src_dir.glob(f"{src_stem}_*.tif"))
        if not src_ti1.is_file() or not src_tiffs:
            InfoDialog(
                "Prebuilt chart not found",
                "The bundled patch set could not be located:\n\n"
                f"{src_dir}\n\nThe app bundle may be incomplete.",
                self, min_width=520,
            ).exec()
            return

        self.target_started.emit()
        name = (self._manual_target_name_edit.text().strip()
                if self._manual_target_name_edit is not None else "") or target_name
        self._file_mgr.set_target_name(name)
        run = self._file_mgr.project().current_run()
        # Start from a clean slate so stale pages from a prior copy can't linger.
        run.reset_chart_artefacts()
        work_dir = run.ensure_dir()

        self._log.clear()
        self._preview.clear()
        try:
            shutil.copy(src_ti1, run.chart_ti1)
            if src_ti2.is_file():
                shutil.copy(src_ti2, run.chart_ti2)
            tiffs: list[Path] = []
            for i, src_tif in enumerate(src_tiffs, start=1):
                dest = work_dir / f"{run.stem}_{i:02d}.tif"
                shutil.copy(src_tif, dest)
                tiffs.append(dest)
        except OSError as exc:
            log.error("Prebuilt copy failed: %s", exc)
            InfoDialog(
                "Could not create target",
                f"Copying the bundled chart into\n\n{work_dir}\n\nfailed:\n{exc}",
                self, min_width=520,
            ).exec()
            return

        self._last_target_name = name
        self._log.appendPlainText(
            f"Copied prebuilt patch set into {work_dir} ({len(tiffs)} page(s)). "
            "targen and printtarg skipped."
        )
        # Prebuilt sets aren't generated from ChartParams — clear any stale
        # params so _stamp_chart_meta falls back to instrument/paper only
        # (read from the bundled .ti2) rather than a previous chart's knobs.
        self._last_params = None
        self._on_generate_finished(tiffs)

    def _generate_from_ti1(self, ti1_path: Path) -> None:
        """Create the target by running printtarg only on an existing .ti1.

        Used by the TC9.18 preset both for its initial creation and for every
        later "Generate Chart" click while the bundled patch set is still the
        active source. Shares _on_generate_finished with the normal path.
        """
        if self._runner.is_running:
            log.warning("A process is already running")
            return
        if not ti1_path.is_file():
            InfoDialog(
                "Patch set not found",
                f"The .ti1 patch set could not be located:\n\n{ti1_path}",
                self, min_width=520,
            ).exec()
            return
        self.target_started.emit()
        name = (self._manual_target_name_edit.text().strip()
                if self._manual_target_name_edit is not None else "")
        if name:
            self._file_mgr.set_target_name(name)
        base_name = self._file_mgr.get_target_name() or TC918_TARGET_NAME
        params = self._collect_params()
        self._last_params = params  # for _stamp_chart_meta (see _on_generate)
        params.target_name = base_name
        self._last_target_name = base_name
        self._log.clear()
        self._preview.clear()
        self._generate_btn.setEnabled(False)
        self._creator.load_ti1_and_generate_preview(
            ti1_path, params,
            on_line=self._on_log_line,
            on_finish=self._on_generate_finished,
        )

    # ------------------------------------------------------------------
    # Patch count display
    # ------------------------------------------------------------------

    def _update_patch_count(self) -> None:
        instr  = self._instr_combo.currentData() or "i1"
        paper  = self._paper_combo.currentData() or "A4"
        dd     = self._dd_check.isChecked()
        td     = self._td_check.isChecked() and instr == "CM"
        pages  = self._pages_spin.value()
        has_lb = self._lb_check.isChecked()  # True = -L active (left border suppressed)
        # -P only matters for strip instruments; for CM/SS the layout
        # is fixed and the checkbox is hidden anyway.
        nsl    = (self._nsl_check.isChecked()
                  and instr in {"i1", "p3"}
                  and not td)
        # ChromIQ-style forces -L, so capacity must be computed at -L-enabled
        # values even when the user left the checkbox unchecked. Triple
        # density also forces -L (and the suppress widget is hidden).
        chromiq_force_l = self._chromiq_force_l(instr, paper)
        eff_lb = has_lb or chromiq_force_l or td
        # Triple density forces -P; reflect that in the lookup so the
        # patch counter agrees with what printtarg will actually do.
        nsl_eff = nsl or td
        dpi    = int(self._settings.get("printtarg_dpi", 300))
        if td:
            # Triple density bypasses the per-instrument defaults and locks
            # the layout to the i1Pro emulation preset.
            eff_margin = 5
            eff_scale = 1.3
        elif instr == "i1":
            preset_key = str(self._settings.get(
                "i1pro_default_preset", I1PRO_DEFAULT_PRESET_KEY
            ))
            eff_margin, eff_scale = i1_defaults_from_preset(preset_key)
        else:
            eff_margin = INSTRUMENT_DEFAULT_MARGIN.get(instr, 6)
            eff_scale = 1.0

        per_sheet = query_patches(instr, paper, dd, suppress_lb=eff_lb,
                                  margin_mm=eff_margin, patch_scale=eff_scale,
                                  triple_density=td, no_strip_limit=nsl_eff)
        if per_sheet is not None:
            total = per_sheet * pages
            self._patch_count_lbl.setText(str(total))
            self._patch_detail_lbl.setText(
                f"PATCHES · {pages} PAGES · {paper.upper()}"
            )
        else:
            self._patch_count_lbl.setText("?")
            self._patch_detail_lbl.setText("CUSTOM LAYOUT")

        # Hidden-defaults info label (values mirror _collect_guided logic).
        # The base is fixed (no settings UI exposes it); reading it from settings
        # used to round-trip the auto-computed result back into the base via
        # "Save as defaults", which collapsed -e/-B toward the floor of 2.
        grey_steps, wp, bp = guided_neutrals(
            instr, paper, pages, GUIDED_NEUTRAL_BASE, GUIDED_NEUTRAL_BASE, eff_lb,
            double_density=dd, triple_density=td, no_strip_limit=nsl_eff,
            ref_budget=int(self._settings.get("grey_ramp_reference", REF_BUDGET)),
        )
        # -L only matters for strip instruments; -h only for CM/SS. Hide
        # both from the command preview when not applicable so the user
        # sees exactly what printtarg will run. ChromIQ-style clipping
        # border forces -L regardless of the per-chart toggle (eff_lb).
        # Triple density: emulate the i1Pro layout with -ii1, force -L,
        # and append -P (strip-limit removal); the -h flag is gated off.
        preview_instr = "i1" if td else instr
        lb_flag = "-L " if eff_lb and (preview_instr in {"i1", "p3"}) else ""
        dd_flag = "-h " if (dd and not td) and instr in {"CM", "SS"} else ""
        margin_flag = f"-m{eff_margin} -M{eff_margin} " if eff_margin != 6 else ""
        scale_flag = f"-a{eff_scale:.2f} " if abs(eff_scale - 1.0) > 0.01 else ""
        strip_flag = "-P " if nsl_eff else ""
        precond_path = (
            self._guided_precond_path.text().strip()
            if hasattr(self, "_guided_precond_path") else ""
        )
        precond_active = (
            hasattr(self, "_guided_precond_check")
            and self._guided_precond_check.isChecked()
        )
        precond_line = ""
        recommendation = ""
        if precond_active:
            if precond_path:
                # chart_creator imports the pick into the run as
                # preconditioning.icc; show that staged name in the preview.
                precond_line = " -c preconditioning.icc"
                recommendation = (
                    "\nTip: use at least as many pages as the original profile."
                )
            else:
                recommendation = (
                    "\nPick a profile to refine from (Browse… above)."
                )

        # With a refinement profile (-c) the neutral ramp samples the profile-
        # defined neutral axis (-n) rather than naïve device grey (-g).
        grey_flag = "-n" if (precond_active and precond_path) else "-g"

        target_name = self._preview_target_name("guided")
        info = (
            f"Guided mode applies these fixed settings:\n"
            f"targen -d2 -G -e{wp} -B{bp} {grey_flag}{grey_steps}{precond_line} {target_name}\n"
            f"printtarg -i{preview_instr} -p{paper} -t{dpi} {scale_flag}{lb_flag}{dd_flag}{margin_flag}{strip_flag}{target_name}"
            f"{recommendation}"
        )
        if hasattr(self, "_guided_info_lbl"):
            self._guided_info_lbl.setText(info)

    def _rebuild_paper_combo(self) -> None:
        instr    = self._instr_combo.currentData() or "i1"
        excluded = EXCLUDED_PAPERS.get(instr, set())
        current  = self._paper_combo.currentData()

        self._paper_combo.blockSignals(True)
        self._paper_combo.clear()
        for size in PAPER_SIZES:
            if size not in excluded:
                self._paper_combo.addItem(PAPER_LABELS.get(size, size), size)
        self._paper_combo.blockSignals(False)

        target = current if current not in excluded else PAPER_FALLBACK.get(current, "A4")
        idx = self._paper_combo.findData(target)
        self._paper_combo.setCurrentIndex(max(idx, 0))
        self._update_patch_count()

    def _update_dd_visibility(self) -> None:
        instr = self._instr_combo.currentData() or "i1"
        # -h is meaningful on CM (double density via rig) and SS (hexagon
        # patches), but has different semantics → relabel and retitle.
        if instr == "CM":
            self._dd_check.setVisible(True)
            self._dd_tooltip.setVisible(True)
            self._dd_check.setText("Double density")
            self._dd_tooltip._title = "Double Density (-h)"
            self._dd_tooltip._body = (
                "Doubles the number of patches that fit in each measurement strip "
                "when using a ColorMunki / i1Studio / ColorChecker Studio.\n\n"
                "REQUIRES the physical measuring rig accessory — a clear plastic "
                "guide that mounts the instrument over the chart. Without the rig "
                "the device cannot align to the tighter patch spacing and will "
                "misread.\n\n"
                "With the rig you get roughly twice as many patches per page, "
                "which means either a more detailed profile from the same number "
                "of sheets, or the same profile quality on fewer sheets. "
                "Recommended for anyone with the rig — it's a strict upgrade on "
                "patch density.\n\n"
                "Has no effect on i1Pro, i1Pro 3 Plus or SpectroScan — the option "
                "is hidden when those are selected."
            )
            self._dd_tooltip._min_width = 600
            self._dd_tooltip.setToolTip("Double Density (-h)\n\nClick for details")
        elif instr == "SS":
            self._dd_check.setVisible(True)
            self._dd_tooltip.setVisible(True)
            self._dd_check.setText("Hexagon patches (packs ~15% more per sheet)")
            self._dd_tooltip._title = "Hexagon Patches (-h)"
            self._dd_tooltip._body = (
                "Switches the SpectroScan chart layout from rectangular to "
                "hexagonal patches. Hexagons tessellate more tightly than "
                "rectangles, so roughly 14% more patches fit on the same sheet — "
                "useful for squeezing extra colour samples out of large papers.\n\n"
                "No extra hardware is required. The SpectroScan's XY scanner "
                "reads each patch individually under a motorised arm, so it "
                "doesn't care whether the patch is square or hexagonal.\n\n"
                "Has no effect on i1Pro, i1Pro 3 Plus or ColorMunki — the option "
                "is hidden when those are selected."
            )
            self._dd_tooltip._min_width = 600
            self._dd_tooltip.setToolTip("Hexagon Patches (-h)\n\nClick for details")
        else:
            self._dd_check.setVisible(False)
            self._dd_tooltip.setVisible(False)
            # Force-uncheck when hidden so the state can't leak into printtarg
            # the next time the user goes back to CM/SS without re-touching it.
            if self._dd_check.isChecked():
                self._dd_check.setChecked(False)
        # Triple density: CM-only, hidden everywhere else.
        td_visible = instr == "CM"
        self._td_check.setVisible(td_visible)
        self._td_tooltip.setVisible(td_visible)
        # "For rig:" prefix is meaningful only when both density options
        # represent the ColorMunki rig accessory. For SS the dd checkbox
        # is hexagon-patches (no rig involved) so we hide the label.
        self._for_rig_label.setVisible(instr == "CM")
        if not td_visible and self._td_check.isChecked():
            self._td_check.setChecked(False)
        # -L only affects strip instruments (i1, p3). CM reads patches
        # individually and SS is an XY flatbed — both ignore -L. Even with
        # the ChromIQ-style clipping border on, the toggle stays visible:
        # leaving it unchecked yields the branded strip; checking it
        # suppresses the border entirely and routes commands/notes to the
        # right margin as usual.
        # Triple density forces -L internally and the user can't influence
        # it — hide the row entirely in that mode.
        lb_visible = instr in {"i1", "p3"} and not self._td_check.isChecked()
        self._lb_check.setVisible(lb_visible)
        self._lb_tooltip.setVisible(lb_visible)
        # -P (no strip-length limit) is only meaningful on strip readers.
        # CM reads patches individually and SS is an XY flatbed — both
        # ignore -P. Triple density forces -P internally and the
        # checkbox would be confusing, so hide it in that mode too.
        nsl_visible = instr in {"i1", "p3"} and not self._td_check.isChecked()
        self._nsl_check.setVisible(nsl_visible)
        self._nsl_tooltip.setVisible(nsl_visible)
        if not nsl_visible and self._nsl_check.isChecked():
            self._nsl_check.setChecked(False)

    def _on_guided_dd_toggled(self, checked: bool) -> None:
        if checked and self._td_check.isChecked():
            self._td_check.setChecked(False)
        self._td_check.setEnabled(not checked)
        self._td_tooltip.setEnabled(not checked)

    def _on_guided_td_toggled(self, checked: bool) -> None:
        if checked and self._dd_check.isChecked():
            self._dd_check.setChecked(False)
        self._dd_check.setEnabled(not checked)
        self._dd_tooltip.setEnabled(not checked)
        # Triple density forces -L internally — stash the user's lb_check
        # value and force it on; restore on untoggle.
        if checked:
            self._td_saved_lb_check = self._lb_check.isChecked()
            self._lb_check.setChecked(True)
        else:
            saved = getattr(self, "_td_saved_lb_check", None)
            if saved is not None:
                self._lb_check.setChecked(bool(saved))
            self._td_saved_lb_check = None
        # -L visibility depends on td state now — refresh.
        self._update_dd_visibility()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _handle_target_rename(self, new_name: str) -> bool:
        """Reconcile a name change away from an already-created target.

        Returns True to proceed with generation, False only when the user
        cancels. When the user has previously generated a target this session
        and now asks for a different (not-yet-existing) folder, pops the
        rename/keep/delete chooser and performs the chosen file operation.
        """
        old_name = getattr(self, "_last_target_name", "")
        if not old_name or not new_name:
            return True
        new_root = self._file_mgr.preview_project_root(new_name)
        if new_root is None:
            return True
        old_root = self._file_mgr.root_dir() / old_name
        # Same destination (e.g. only spacing/case-equivalent edit), or the old
        # target was never written to disk — nothing to reconcile.
        if new_root == old_root or not (old_root / "project.json").exists():
            return True
        # A project already occupying the new name is a different situation
        # (merge/overwrite) that this dialog doesn't cover — let the normal flow
        # handle it rather than offering a misleading "rename onto it".
        if new_root.exists():
            return True

        dlg = TargetChangeDialog(old_name, new_root.name, old_root, new_root, self)
        dlg.exec()
        action = dlg.result_action()
        if action == TargetChangeAction.CANCEL:
            return False
        if action == TargetChangeAction.RENAME:
            try:
                self._file_mgr.rename_existing_project(old_name, new_name)
            except (OSError, FileExistsError, FileNotFoundError) as exc:
                # Fall back to a fresh target rather than blocking the user.
                log.warning("Project rename failed (%s); creating fresh instead", exc)
        elif action == TargetChangeAction.DELETE:
            self._file_mgr.delete_project_folder(old_name)
        # KEEP: leave the old folder; set_target_name creates the fresh one.
        return True

    def _on_generate(self) -> None:
        if self._runner.is_running:
            log.warning("A process is already running")
            return
        # Prebuilt-files preset. By default nothing is computed — the bundled
        # files are copied verbatim. But the user can unlock the panels:
        #   • targen changed   → fresh targen run (different patches): fall through
        #   • else printtarg changed → re-lay-out the bundled .ti1 (same patches)
        #   • else                   → copy the bundled files (exact original)
        if self._prebuilt_active and self._prebuilt_key is not None \
                and self._current_mode() == "manual":
            targen_changed = (self._prebuilt_targen_sig is not None
                              and self._targen_signature() != self._prebuilt_targen_sig)
            printtarg_changed = (self._prebuilt_printtarg_sig is not None
                                 and self._printtarg_signature() != self._prebuilt_printtarg_sig)
            if targen_changed:
                # User unlocked the patch recipe and changed it — build a fresh
                # chart from the current settings (fall through to the normal
                # targen→printtarg path below). The preset stays selected.
                pass
            elif printtarg_changed:
                stem_rel = PREBUILT_PRESETS[self._prebuilt_key][0]
                bundled_ti1 = resource_path(f"{stem_rel}.ti1")
                self._generate_from_ti1(bundled_ti1)
                return
            else:
                name = (self._manual_target_name_edit.text().strip()
                        if self._manual_target_name_edit is not None else "")
                self._create_prebuilt_target(
                    self._prebuilt_key,
                    name or self._builtin_default_name(self._prebuilt_key))
                return
        # User preset with a bundled .ti1: build from that patch set (skip targen,
        # lay it out with printtarg) — same path as the TC9.18 built-in. If the
        # user unlocked the targen panel and changed it, fall through to a fresh
        # targen run instead (different patches, like the built-in ti1 presets).
        if self._preset_ti1_path is not None and self._current_mode() == "manual":
            targen_changed = (self._preset_ti1_targen_sig is not None
                              and self._targen_signature() != self._preset_ti1_targen_sig)
            if not targen_changed:
                if self._preset_ti1_path.is_file():
                    self._generate_from_ti1(self._preset_ti1_path)
                    return
                log.warning("attached preset .ti1 vanished: %s", self._preset_ti1_path)
                self._preset_ti1_path = None
            else:
                self._preset_ti1_path = None
                self._preset_ti1_targen_sig = None
        # TC9.18 built-in preset: while it's active and the user hasn't touched
        # any targen setting, reproduce the exact bundled chart (printtarg only).
        # The OFPS patch set can't be recreated reliably by re-running targen, so
        # this is the only way to guarantee an identical target. Once a targen
        # setting changes the user has opted into a fresh chart, so fall through.
        if self._tc918_active and self._current_mode() == "manual":
            if self._targen_signature() == self._tc918_targen_sig:
                self._generate_from_ti1(self._tc918_ti1_path())
                return
            self._tc918_active = False
            self._tc918_targen_sig = None
        # Same for Knut's TC9.18+Spyderprint presets: while active and the targen
        # settings are untouched, re-lay-out the bundled 1168-patch .ti1 (printtarg
        # only). Changing a targen setting opts into a fresh targen chart.
        if self._knut_active and self._current_mode() == "manual":
            if self._targen_signature() == self._knut_targen_sig:
                self._generate_from_ti1(self._knut_ti1_path())
                return
            self._knut_active = False
            self._knut_targen_sig = None
        name = (
            self._target_name_edit.text().strip()
            if self._current_mode() == "guided"
            else self._manual_target_name_edit.text().strip()
        )
        # If a target was already created this session and the user has now typed
        # a different name, switching folders would orphan the old one. Ask first
        # (rename / keep both / delete old); Cancel aborts before anything clears.
        if not self._handle_target_rename(name):
            return

        self.target_started.emit()

        params = self._collect_params()
        # Remembered for _stamp_chart_meta so the run's meta.json can carry the
        # full printtarg layout knobs (not just instrument/paper), letting the
        # TI2 editor restore a main-app chart exactly like an editor-saved one.
        self._last_params = params
        if name:
            self._file_mgr.set_target_name(name)
        base_name = self._file_mgr.get_target_name()

        # Calibration vs. normal run is now expressed by params.cal_target
        # alone — it routes chart_creator to cal/ (stem "calibration") vs the
        # current run folder (stem "chart"). The project folder is always
        # base_name; the file stem no longer carries a cal_ prefix.
        cal_target_active = (
            hasattr(self, "_cal_target_check")
            and self._cal_target_check.isChecked()
            and self._cal_target_grp.isVisible()
        )
        params.cal_target = cal_target_active
        params.target_name = base_name
        self._last_target_name = base_name

        # "Use as pre-conditioning profile" → seed a fresh run from the parent
        # before generating the refined chart. new_run() copies the parent's
        # profile.icc / measurement.ti3 into the new run as preconditioning.*
        # and makes it current, so the chart generated below lands in the new
        # run and chart_creator's external-import becomes a no-op.
        if (not cal_target_active
                and self._preconditioning_from_dialog
                and self._precond_parent_run_id):
            proj = self._file_mgr.project()
            if proj.has_run(self._precond_parent_run_id):
                parent = proj.run(self._precond_parent_run_id)
                try:
                    new_run = proj.new_run(preconditioning_from=parent)
                    params.extra_targen_args = shlex.join(
                        ["-c", str(new_run.preconditioning_icc)]
                    )
                    params.neutral_axis_from_profile = True
                except FileNotFoundError as exc:
                    log.warning("Could not seed pre-conditioning run: %s", exc)

        self._log.clear()
        self._preview.clear()
        self._generate_btn.setEnabled(False)

        # Auto patch count (manual mode only): estimate now, then proceed.
        # Live re-estimation on every settings change blocks the UI for
        # custom layouts (binary search shells out to targen/printtarg
        # via subprocess.run), so we defer to the click.
        if (self._current_mode() == "manual"
                and self._manual_auto_patches_check is not None
                and self._manual_auto_patches_check.isChecked()):
            self._log.appendPlainText("Calculating patch count…")
            self._log.ensureCursorVisible()
            from PyQt6.QtCore import QEventLoop
            from PyQt6.QtWidgets import QApplication

            # The binary-search path (custom layouts not in the patch DB)
            # shells out to targen/printtarg synchronously per step, blocking
            # this thread. Repaint the log after each progress line so the user
            # sees step-by-step progress instead of a frozen window / beach
            # ball. ExcludeUserInputEvents stops queued clicks/keys from
            # re-entering generation mid-search.
            def _estimate_progress(line: str) -> None:
                self._on_log_line(line)
                QApplication.processEvents(
                    QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents
                )

            QApplication.processEvents()
            try:
                params.patches = self._creator.estimate_patches(
                    params, progress_cb=_estimate_progress
                )
            except Exception as exc:
                log.error("Auto patch estimation failed: %s", exc)
                self._log.appendPlainText(f"Auto patch estimation failed: {exc}")
                self._generate_btn.setEnabled(True)
                return
            self._log.appendPlainText(f"Auto patch count: {params.patches}")
            # Now that the real patch count is known, recompute any Auto
            # -e/-B/-g from it (the preview used a cheap patch_db estimate).
            self._apply_auto_neutrals(params, use_estimate=True)

        # Pre-flight: targen exits with code 1 ("Must have some single or multi
        # dimensional RGB or CMY steps") if -f is 0 and no -g / -s / -c steps
        # provide patches either. Catch this before launching the subprocess so
        # the user sees an actionable message instead of a cryptic exit code.
        if (self._current_mode() == "manual"
                and params.patches <= 0
                and params.grey_steps <= 0
                and params.single_channel_steps <= 0
                and not _extra_args_have_patch_source(params.extra_targen_args)):
            self._log.appendPlainText(
                "[ERROR] Nothing for targen to generate.\n"
                "        Set a non-zero Total Patch Count (-f), enable the Auto checkbox,\n"
                "        or set Grey Axis Steps (-g) / Single Channel Steps (-s) to a positive value."
            )
            self._log.ensureCursorVisible()
            self._generate_btn.setEnabled(True)
            return

        self._creator.generate(
            params,
            on_line=self._on_log_line,
            on_finish=self._on_generate_finished,
        )

    def _on_load_ti1(self) -> None:
        path = open_file_dialog(
            self, "Load patch set",
            "Patch sets (*.ti1 *.pxf *.cgats *.txt)",
            extra_path=self._settings.get("custom_output_path", ""),
        )
        if not path:
            return
        src = Path(path)
        self._log.clear()

        # A native Argyll .ti1 already carries real colorimetry, so it's used
        # as-is. Anything else is treated as an i1Profiler RGB patch set
        # (.pxf / CGATS .txt) and converted to a .ti1 first — reconstructing
        # approximate XYZ so printtarg can lay it out (see
        # workflow/i1profiler_import). CMYK / parse errors raise ValueError.
        if src.suffix.lower() == ".ti1":
            ti1 = src
        else:
            try:
                tmp_dir = Path(tempfile.mkdtemp(prefix="chromiq_import_"))
                ti1, n = import_to_ti1(src, tmp_dir / f"{src.stem}.ti1")
            except ValueError as exc:
                InfoDialog(
                    "Couldn't read that patch set",
                    f"{exc}\n\nLoad an Argyll .ti1, or an i1Profiler RGB patch "
                    "set (a .pxf or a CGATS .txt). CMYK and extended-gamut "
                    "sets aren't supported.",
                    self, min_width=520,
                ).exec()
                return
            self._log.appendPlainText(
                f"Converted {src.name} to .ti1 ({n} patches)."
            )

        # Loading a different patch set means we're no longer on the TC9.18 chart
        # or any preset-bound patch set; re-enable panels if a prebuilt was active.
        self._tc918_active = False
        self._tc918_targen_sig = None
        self._preset_ti1_path = None
        if self._prebuilt_active:
            self._leave_prebuilt()
        self._file_mgr.set_target_name(src.stem)
        params = self._collect_params()
        self._preview.clear()
        self._generate_btn.setEnabled(False)
        self._creator.load_ti1_and_generate_preview(
            ti1, params,
            on_line=self._on_log_line,
            on_finish=self._on_generate_finished,
        )

    def _on_log_line(self, line: str) -> None:
        self._log.appendPlainText(line)
        self._log.ensureCursorVisible()

    def _is_isis_selected(self) -> bool:
        """Read the instrument from the *active* mode's selector.

        i1iSis is intentionally absent from the Guided combo, so this only
        returns True from Manual mode in practice — but consulting the active
        selector keeps the check robust if that ever changes.
        """
        if self._current_mode() == "guided":
            code = (self._instr_combo.currentData() or "") if hasattr(self, "_instr_combo") else ""
        else:
            code = (self._manual_instr_pw.get_raw_value() or "") if self._manual_instr_pw else ""
        return code == "isis"

    def _update_isis_preview_banner(self) -> None:
        # The instrument signal can fire before _build_ui finishes constructing
        # the preview pane (during _make_manual_panel). Guard accordingly.
        if getattr(self, "_preview", None) is None:
            return
        if self._is_isis_selected():
            self._preview.set_banner(
                "Layout preview only — i1Profiler will lay out the actual chart "
                "from the patch list when you load the .pxf, so the printed "
                "chart will look different from what's shown here."
            )
        else:
            self._preview.set_banner(None)

    def _export_for_i1profiler_and_notify(
        self, work_dir: Path, stem: str, preview_available: bool
    ) -> bool:
        """Convert the TI1 to .txt + .pxf and show the i1Profiler hand-off popup.

        Returns True if the export succeeded (so the caller can suppress the
        generic "chart generation failed" path when printtarg crashed but the
        TI1 from targen is still usable).
        """
        ti1 = work_dir / f"{stem}.ti1"
        if not ti1.is_file():
            self._log.appendPlainText(
                f"[i1iSis] expected TI1 not found: {ti1}; skipping i1Profiler export."
            )
            return False
        try:
            target = parse_ti1(ti1)
            project = self._file_mgr.project()
            exports_dir = project.ensure_exports_dir()
            # Project-named export so the file is self-identifying when handed
            # to i1Profiler (e.g. printer-test-file-i1profiler.pxf).
            base_name = f"{project.current_run().stem}-i1profiler"
            txt_path, pxf_path = export_from_ti1(ti1, exports_dir, base_name=base_name)
        except Exception as exc:  # noqa: BLE001
            log.exception("i1Profiler export failed")
            self._log.appendPlainText(f"[i1iSis] export failed: {exc}")
            InfoDialog(
                "i1Profiler export failed",
                f"ChromIQ could not write the i1Profiler patch-set files:\n\n{exc}",
                self,
                min_width=520,
            ).exec()
            return False

        if txt_path is not None:
            self._log.appendPlainText(f"[i1iSis] wrote {txt_path.name}")
        self._log.appendPlainText(f"[i1iSis] wrote {pxf_path.name}")

        # Colorspace label for the popup. i1Profiler does not read the colour
        # space from the patch set — the user must select it in the workflow —
        # so spell out which one this chart is for.
        if target.kind == "RGB":
            cs_label = "RGB"
        elif target.kind == "CMYK":
            cs_label = "CMYK"
        else:
            cs_label = f"CMYK + {len(target.extras)}"

        files_lines = [
            f"  • {pxf_path.name}   (recommended — i1Profiler's native format)"
        ]
        if txt_path is not None:
            files_lines.append(f"  • {txt_path.name}   (CGATS text, as a fallback)")
        files_block = "\n".join(files_lines)

        steps = [
            "Connect your i1iSis and open i1Profiler.",
            "On the start screen, choose Advanced User Mode.",
            "In the menu on the left, under Printer, click Profiling.",
        ]
        if target.kind != "RGB":
            ink_note = ""
            if target.extras:
                inks = ", ".join(EXTRA_INK[c][0] for c in target.extras)
                ink_note = f", and define the {len(target.extras)} extra inks ({inks})"
            steps.append(
                f'Set the printer colour space to "{cs_label}" first — i1Profiler '
                f"does not read it from the file, so you must choose it here"
                f"{ink_note}."
            )
        steps.append(
            "In the Patch Set window, click Load and select the .pxf file above. "
            "Leave i1Profiler's Smart patch generator alone afterwards — changing "
            "its patch count or Scramble option replaces the loaded patches with "
            "freshly generated ones."
        )
        steps.append(
            "Continue through i1Profiler's wizard — it will lay out and print the "
            "chart, then ask you to scan it on the i1iSis and build the ICC profile."
        )
        steps_block = "\n".join(f"  {i}. {s}" for i, s in enumerate(steps, 1))

        preview_note = (
            "\n\nNote on the preview shown to the right: it is ChromIQ's own "
            "layout, meant only as a sanity check of the patches. The actual "
            "chart that gets printed will be laid out by i1Profiler and will "
            "look different."
            if preview_available else
            "\n\nNote: ChromIQ couldn't render a layout preview for this run, "
            "but the patch-set files above are still valid — i1Profiler builds "
            "its own layout from them, so the missing preview doesn't affect "
            "the workflow."
        )
        file_word = "file was" if txt_path is None else "files were"
        body = (
            f"Your {cs_label} chart is ready for i1Profiler. The following "
            f"{file_word} saved next to the chart:\n\n"
            f"{files_block}\n\n"
            f"Folder:  {work_dir}\n\n"
            f"Next steps in i1Profiler:\n"
            f"{steps_block}\n\n"
            f"ChromIQ's Print, Measure and Profile tabs are not used for this "
            f"instrument — the rest of the workflow happens entirely in i1Profiler."
            f"{preview_note}"
        )
        InfoDialog(
            "Next steps in i1Profiler",
            body,
            self,
            min_width=620,
        ).exec()
        return True

    def _on_generate_finished(self, tiffs: list[Path]) -> None:
        self._generate_btn.setEnabled(True)
        # One-shot flag: consumed by this run, don't carry over to the next.
        self._preconditioning_from_dialog = False
        self._precond_parent_run_id = None
        is_isis = self._is_isis_selected()
        # File stem is fixed by the folder layout ("chart" / "calibration").
        # Derive it from the actual page bitmaps so it's correct regardless of
        # which flow produced them; fall back to "chart" when none exist.
        if tiffs:
            m = re.match(r"(.+?)_\d+$", tiffs[0].stem)
            stem = m.group(1) if m else tiffs[0].stem
        else:
            stem = "chart"
        # For i1iSis the load-bearing artifact is the TI1 from targen, not the
        # printtarg TIFF. Run the export off the TI1 so users still get their
        # patch-set files even if printtarg fails for an unrelated reason
        # (e.g. paper-size validation crash). work_dir is wherever the TI1 lives
        # — derive from tiffs when present, else from the current run folder.
        isis_export_ok = False
        if is_isis:
            work_dir = tiffs[0].parent if tiffs else self._file_mgr.project().current_run().dir
            isis_export_ok = self._export_for_i1profiler_and_notify(
                work_dir, stem, preview_available=bool(tiffs),
            )

        if tiffs:
            self._preview.load_tiff(tiffs)
            log.info("Preview loaded: %d TIFF(s)", len(tiffs))
            ti2 = tiffs[0].parent / f"{stem}.ti2"
            # Record the chart's instrument + paper in the run's meta.json,
            # mirroring what the TI2 layout editor writes (see
            # workflow.ti2_relayout.save_editor_meta). The .ti2 carries these
            # too, but stamping them in meta.json keeps the run folder
            # self-describing. Read straight from the just-written .ti2 so it's
            # correct for every creation path (normal / prebuilt / from-.ti1).
            self._stamp_chart_meta(ti2)
            # Remember the .ti1 backing this chart so the Save Preset dialog can
            # offer to attach it.
            ti1 = tiffs[0].parent / f"{stem}.ti1"
            self._current_ti1_path = ti1 if ti1.is_file() else None
            self.chart_finished.emit(tiffs, ti2, is_isis)
        else:
            self._log.appendPlainText("[ERROR] Chart generation failed.")
            self._log.ensureCursorVisible()
            # When the i1iSis hand-off already succeeded the user doesn't need
            # a second failure dialog telling them printtarg crashed — the
            # popup we already showed explained that the preview is optional
            # and the workflow continues in i1Profiler.
            if not isis_export_ok:
                failure = self._creator.primary_failure()
                if failure is not None:
                    tool, _key, friendly = failure
                    title = (
                        "Chart Generation Failed (targen)"
                        if tool == "targen"
                        else "Chart Layout Failed (printtarg)"
                    )
                    InfoDialog(title, friendly, self, min_width=520).exec()

    def _stamp_chart_meta(self, ti2: Path) -> None:
        """Record instrument / paper AND the printtarg layout knobs in the run's
        meta.json, so a main-app chart opened in the TI2 layout editor restores
        exactly like an editor-saved one.

        Reuses :func:`workflow.ti2_relayout.save_editor_meta` (the same writer
        the editor uses), feeding it a LayoutOptions built from the params this
        chart was generated with. The chart's instrument/paper come from the
        just-written .ti2 (authoritative for every creation path). Only runs for
        charts in a ``runs/runN/`` folder — calibration targets live in ``cal/``
        and aren't RunMeta-backed. Best-effort: never block chart creation.
        """
        try:
            run_dir = ti2.parent
            if run_dir.parent.name != "runs":   # cal/ or some other folder
                return
            from core.file_manager import Run
            from workflow.ti2_relayout import ChartSpec, LayoutOptions, save_editor_meta
            spec = ChartSpec.from_ti2(ti2)
            run = Run.for_dir(run_dir)
            # Build the editor's LayoutOptions from the params this chart was
            # generated with (stored at generate time). Without params we can
            # still stamp instrument/paper but not the layout knobs.
            params = getattr(self, "_last_params", None)
            if params is not None:
                opts = LayoutOptions(
                    spacer_mode=("none" if params.no_spacers
                                 else "bw" if params.bw_spacers
                                 else "colored"),
                    patch_scale=params.patch_scale,
                    spacer_scale=params.spacer_scale,
                    margin_mm=params.margin_mm,
                    suppress_left_clip=params.disable_left_border,
                    no_strip_limit=params.no_strip_limit,
                    double_density=params.double_density,
                    triple_density=params.triple_density,
                    tiff_16bit=params.tiff_16bit,
                    dpi=params.tiff_dpi,
                )
                save_editor_meta(ti2, spec, opts, run.stem)
            else:
                meta = run.load_meta()
                meta.instrument = spec.instrument_flag
                meta.paper = spec.paper_flag
                run.save_meta(meta)
        except Exception:  # noqa: BLE001 — metadata is non-essential
            log.exception("could not stamp chart meta.json")

    def _on_save_defaults(self) -> None:
        params = self._collect_params()
        s = self._settings
        name = self._file_mgr.strip_workfile_ext(
            self._target_name_edit.text().strip()
            if self._current_mode() == "guided"
            else self._manual_target_name_edit.text().strip()
        )
        s.set("chart_target_name",         name or "ChromIQ Test Chart")
        s.set("chart_stamp_commands",      bool(params.stamp_commands))
        s.set("chart_left_clip_info",      bool(params.left_clip_info))
        s.set("chart_instrument",          params.instrument)
        s.set("chart_paper",               params.paper)
        s.set("chart_pages",               params.pages)
        s.set("chart_double_density",      params.double_density)
        s.set("chart_triple_density",      params.triple_density)
        # If Triple density is on, the lb_check shows TD's forced True;
        # save the stashed pre-TD value so the user's preference round-trips.
        guided_lb_save = params.disable_left_border
        if (params.triple_density
                and getattr(self, "_td_saved_lb_check", None) is not None):
            guided_lb_save = bool(self._td_saved_lb_check)
        s.set("chart_disable_left_border", guided_lb_save)
        # Triple density forces -P internally; persist the user's standalone
        # -P preference rather than the TD-derived True.
        guided_nsl_save = (False if params.triple_density
                           else bool(self._nsl_check.isChecked()
                                     and (params.instrument in {"i1", "p3"})))
        s.set("chart_no_strip_limit", guided_nsl_save)
        s.set("targen_device_type",        params.device_type)
        s.set("targen_good_mode",          params.good_mode)
        s.set("printtarg_dpi",             params.tiff_dpi)
        # Save all manual widget values individually. When Triple density is
        # active the four widgets it owns (-a / -m / -P / -L) currently show
        # the i1Pro-emulation overrides; persisting those would clobber the
        # user's pre-TD preferences and trap the next session in TD-shaped
        # values that no longer round-trip through the stash. Save the
        # stashed pre-TD values instead for those four flags.
        td_stash = (self._td_saved_layout
                    if (self._manual_td_check is not None
                        and self._manual_td_check.isChecked()
                        and self._td_saved_layout)
                    else None)
        for tool, widgets in self._manual_widgets.items():
            for pw in widgets:
                if pw in self._d_cascade_widgets:
                    continue
                if td_stash is not None and tool == "printtarg" and pw.flag in td_stash:
                    v = td_stash[pw.flag]
                else:
                    v = pw.get_raw_value()
                key = _pw_settings_key(tool, pw.flag)
                if v is not None:
                    s.set(key, v)
                # Expert non-boolean rows carry their enable-checkbox state
                # separately from the value; persist it so the flag is re-armed
                # on restore (otherwise build_args drops it).
                if pw.has_separate_enable:
                    s.set(f"{key}_enabled", pw.is_enabled_by_user)
        for idx, pw in enumerate(self._d_cascade_widgets):
            s.set(f"manual_targen_-D_{idx}", pw.get_raw_value())
            s.set(f"manual_targen_-D_{idx}_enabled", pw.is_enabled_by_user)
        if self._bit16_radio is not None:
            s.set("manual_printtarg_tiff_16bit", self._bit16_radio.isChecked())
        if self._manual_auto_patches_check is not None:
            s.set("manual_auto_patches", self._manual_auto_patches_check.isChecked())
        if self._manual_auto_grey_check is not None:
            s.set("manual_auto_grey", self._manual_auto_grey_check.isChecked())
        if self._manual_auto_white_check is not None:
            s.set("manual_auto_white", self._manual_auto_white_check.isChecked())
        if self._manual_auto_black_check is not None:
            s.set("manual_auto_black", self._manual_auto_black_check.isChecked())
        if self._manual_pages_spin is not None:
            s.set("manual_pages", int(self._manual_pages_spin.value()))
        if self._manual_td_check is not None:
            s.set("manual_printtarg__triple_density",
                  self._manual_td_check.isChecked())
        log.info("Chart defaults saved")
        self._log.appendPlainText("Current settings saved as defaults.")
        self._log.ensureCursorVisible()

    # ------------------------------------------------------------------
    # Param collection
    # ------------------------------------------------------------------

    def _collect_params(self) -> ChartParams:
        if self._current_mode() == "guided":
            return self._collect_guided()
        return self._collect_manual()

    def _collect_guided(self) -> ChartParams:
        pages   = self._pages_spin.value()
        instr   = self._instr_combo.currentData() or "i1"
        paper   = self._paper_combo.currentData() or "A4"
        dd      = self._dd_check.isChecked()
        td      = self._td_check.isChecked() and instr == "CM"
        has_lb  = self._lb_check.isChecked()
        nsl_ui  = (self._nsl_check.isChecked()
                   and instr in {"i1", "p3"}
                   and not td)
        if td:
            # Triple-density forces i1Pro layout params; the arg builder also
            # applies these, but we set them on ChartParams so patch-count
            # lookup, command preview and TIFF metadata stay consistent.
            margin = 5
            patch_scale = 1.3
            no_strip_limit = True
            dd = False  # mutual exclusion (UI also enforces)
        elif instr == "i1":
            preset_key = str(self._settings.get(
                "i1pro_default_preset", I1PRO_DEFAULT_PRESET_KEY
            ))
            margin, patch_scale = i1_defaults_from_preset(preset_key)
            no_strip_limit = nsl_ui
        else:
            margin = INSTRUMENT_DEFAULT_MARGIN.get(instr, 6)
            patch_scale = 1.0
            no_strip_limit = nsl_ui
        # ChromIQ-style and triple-density both force -L; mirror the chart's
        # effective suppress_lb state so guided_neutrals sees what targen/
        # printtarg will actually run.
        eff_lb = has_lb or self._chromiq_force_l(instr, paper) or td
        grey_steps, white_patches, black_patches = guided_neutrals(
            instr, paper, pages, GUIDED_NEUTRAL_BASE, GUIDED_NEUTRAL_BASE, eff_lb,
            double_density=dd, triple_density=td,
            no_strip_limit=no_strip_limit,
            ref_budget=int(self._settings.get("grey_ramp_reference", REF_BUDGET)),
        )

        precond_path = self._guided_precond_path.text().strip()
        precond_active = self._guided_precond_check.isChecked() and bool(precond_path)
        extra_targen = shlex.join(["-c", precond_path]) if precond_active else ""

        return ChartParams(
            instrument           = instr,
            paper                = paper,
            pages                = pages,
            double_density       = dd,
            triple_density       = td,
            disable_left_border  = has_lb,
            device_type          = self._settings.get("targen_device_type", "2"),
            patches              = 0,
            white_patches        = white_patches,
            black_patches        = black_patches,
            good_mode            = bool(self._settings.get("targen_good_mode", True)),
            grey_steps           = grey_steps,
            # When a refinement profile is supplied, the corrected neutral axis
            # is known, so sample it with targen -n instead of device-grey -g.
            neutral_axis_from_profile = precond_active,
            extra_targen_args    = extra_targen,
            tiff_dpi             = int(self._settings.get("printtarg_dpi", 300)),
            patch_scale          = patch_scale,
            margin_mm            = margin,
            no_strip_limit       = no_strip_limit,
            left_clip_info       = bool(self._settings.get("chart_left_clip_info", False)),
            chromiq_clip_style   = bool(self._settings.get("i1pro_chromiq_clip_style", False)),
        )

    def _collect_manual(self) -> ChartParams:
        p = ChartParams()

        if self._manual_pages_spin is not None:
            p.pages = int(self._manual_pages_spin.value())

        def _get(tool: str, flag: str, default: Any) -> Any:
            for pw in self._manual_widgets.get(tool, []):
                if pw.flag == flag:
                    v = pw.get_raw_value()
                    return v if v is not None else default
            return default

        p.device_type          = str(_get("targen",    "-d",  "2"))
        p.patches              = int(_get("targen",    "-f",  0))
        # -e / -B / -g read the raw widget value; Auto-checked rows return
        # 0 from the spinbox (specialValueText "Auto"), and we substitute
        # the manual_neutrals() value at the end of _collect_manual once
        # the rest of ChartParams is populated.
        p.white_patches        = int(_get("targen",    "-e",  4))
        p.black_patches        = int(_get("targen",    "-B",  4))
        p.good_mode            = bool(_get("targen",   "-G",  True))
        p.grey_steps           = int(_get("targen",    "-g",  0))
        p.single_channel_steps = int(_get("targen",    "-s",  0))

        # Emit extras in an explicit order rather than widget order so -n
        # (Neutral Axis Steps) reads ahead of -c (pre-conditioning profile)
        # in the command. targen parses options order-independently and the
        # -c path-staging/rewrite logic scans for the "-c" token wherever it
        # sits, so the order is purely cosmetic.
        # ``__targen_distribution__`` is the pseudo-id for the mutex
        # distribution-selector row (flag_choice); its value is the actual
        # token (-r, -t, …) and is emitted by ParameterWidget.build_args.
        extra = []
        for flag in (
            "-n", "-c", "-A", "-C", "-N", "-V", "-D",
            "-l", "-m", "-M", "-b", "__targen_distribution__",
        ):
            for pw in self._manual_widgets.get("targen", []):
                if pw.flag == flag:
                    extra.extend(pw.build_args())
        if extra:
            p.extra_targen_args = shlex.join(extra)

        p.instrument           = str(_get("printtarg", "-i",  "i1"))
        p.paper                = str(_get("printtarg", "-p",  "A4"))
        p.tiff_dpi             = int(_get("printtarg", "-t",  300))
        p.tiff_16bit           = self._bit16_radio is not None and self._bit16_radio.isChecked()
        p.double_density       = bool(_get("printtarg", "-h", False))
        p.disable_left_border  = bool(_get("printtarg", "-L", True))
        p.patch_scale          = float(_get("printtarg", "-a", 1.0))
        # -A (spacer scale) and -n (no spacers) reach printtarg via the manual
        # widget build_args path; captured here for metadata (the editor's
        # LayoutOptions) only — see ChartParams.spacer_scale / no_spacers.
        p.spacer_scale         = float(_get("printtarg", "-A", 1.0) or 1.0)
        p.no_spacers           = bool(_get("printtarg", "-n",  False))
        p.margin_mm            = int(_get("printtarg",  "-m",  6))
        p.no_randomise         = bool(_get("printtarg", "-r",  False))
        p.bw_spacers           = bool(_get("printtarg", "-b",  False))
        p.no_strip_limit       = bool(_get("printtarg", "-P",  False))
        # Triple density is a ChromIQ-internal flag (no Argyll mapping); the
        # arg builder substitutes -i / -a / -m / -P at command time. UI also
        # already stashes the prior layout values, so reading the widget
        # state here is enough.
        p.triple_density = (
            self._manual_td_check is not None
            and self._manual_td_check.isChecked()
            and p.instrument == "CM"
        )

        # All remaining printtarg params (e.g. -N, -K, -I, -C, -D, -U, -R, -Q, -A, -n, -c)
        # are collected here and passed through extra_printtarg_args, which
        # _build_printtarg_args() already appends verbatim before the target name.
        _pt_mapped = {"-i", "-p", "-t", "-h", "-L", "-a", "-m", "-r", "-b", "-P"}
        extra_pt: list[str] = []
        for pw in self._manual_widgets.get("printtarg", []):
            if pw.flag not in _pt_mapped:
                extra_pt.extend(pw.build_args())
        if extra_pt:
            p.extra_printtarg_args = shlex.join(extra_pt)

        p.chart_notes          = self._manual_chart_notes_edit.text().strip()
        p.stamp_commands       = self._manual_stamp_cmd_check.isChecked()
        p.left_clip_info       = self._manual_left_clip_check.isChecked()
        p.chromiq_clip_style   = bool(self._settings.get("i1pro_chromiq_clip_style", False))
        p.is_manual            = True

        # Auto -e / -B / -g substitution. For the live preview we use a
        # cheap patch_db estimate when -f itself is auto; the real
        # estimate_patches() value is re-applied in _on_generate.
        self._apply_auto_neutrals(p, use_estimate=False)
        return p

    def _resolve_total_patches(self, p: ChartParams, use_estimate: bool) -> int:
        """Return the total patch count to feed manual_neutrals().

        When -f is set manually, use it. When -f is on Auto, fall back to
        a cheap patch_db lookup for the live preview (use_estimate=False)
        or the real targen-driven estimate at Generate-click
        (use_estimate=True; caller is responsible for having already
        called estimate_patches and updated p.patches).
        """
        if not (self._manual_auto_patches_check is not None
                and self._manual_auto_patches_check.isChecked()):
            return int(p.patches)
        if use_estimate:
            return int(p.patches)
        # Cheap preview path: patch_db lookup × pages. Returns 0 when the
        # combination isn't in the lookup tables (custom patch_scale/margin,
        # or layout-affecting extras like -A / -n) — _apply_auto_neutrals
        # then falls back to default neutrals for the live preview; the
        # real estimate at Generate-click reruns this via estimate_patches
        # which routes such cases to a binary search.
        from workflow.chart_creator import _chromiq_clip_active
        triple = p.triple_density and p.instrument == "CM"
        force_l = _chromiq_clip_active(p) or triple
        eff_lb = p.disable_left_border or force_l
        nominal = query_patches(p.instrument, p.paper,
                                double_density=p.double_density,
                                suppress_lb=eff_lb,
                                margin_mm=p.margin_mm,
                                patch_scale=p.patch_scale,
                                triple_density=triple,
                                no_strip_limit=p.no_strip_limit)
        if nominal is None:
            return 0
        return int(nominal * max(1, p.pages))

    def _apply_auto_neutrals(self, p: ChartParams, use_estimate: bool) -> None:
        """Overwrite -e / -B / -g on `p` for any Auto checkbox that's on."""
        from workflow.chart_creator import manual_neutrals
        if not any((
            self._manual_auto_grey_check  is not None and self._manual_auto_grey_check.isChecked(),
            self._manual_auto_white_check is not None and self._manual_auto_white_check.isChecked(),
            self._manual_auto_black_check is not None and self._manual_auto_black_check.isChecked(),
        )):
            return
        total = self._resolve_total_patches(p, use_estimate=use_estimate)
        # Pull bases from any user-set values (so an Auto checkbox respects
        # a non-default starting base if the user typed one before checking
        # Auto). Falls back to 4 / 4 — same as targen's default.
        base_w = p.white_patches if p.white_patches > 0 else 4
        base_b = p.black_patches if p.black_patches > 0 else 4
        g, w, b = manual_neutrals(
            total, base_w, base_b,
            ref_budget=int(self._settings.get("grey_ramp_reference", REF_BUDGET)),
        )
        if self._manual_auto_grey_check is not None and self._manual_auto_grey_check.isChecked():
            p.grey_steps    = g
        if self._manual_auto_white_check is not None and self._manual_auto_white_check.isChecked():
            p.white_patches = w
        if self._manual_auto_black_check is not None and self._manual_auto_black_check.isChecked():
            p.black_patches = b

    # ------------------------------------------------------------------
    # Restore saved defaults
    # ------------------------------------------------------------------

    def _restore_defaults(self) -> None:
        s = self._settings

        # Strip any stray extension a pre-fix session may have persisted, so a
        # contaminated default (e.g. "…_target.icm") doesn't reappear on launch.
        default_name = self._file_mgr.strip_workfile_ext(
            s.get("chart_target_name", "ChromIQ Test Chart")
        )
        self._target_name_edit.setText(default_name)
        self._manual_target_name_edit.setText(default_name)

        # Chart notes are per-chart, not a session default — always start empty.
        # Also evict any stale value that an older session may have persisted
        # under the now-unused "chart_notes" key.
        try:
            if s._qs.contains("chart_notes"):
                s._qs.remove("chart_notes")
        except AttributeError:
            pass
        if hasattr(self, "_manual_chart_notes_edit"):
            self._manual_chart_notes_edit.setText("")
        if hasattr(self, "_manual_stamp_cmd_check"):
            self._manual_stamp_cmd_check.setChecked(bool(s.get("chart_stamp_commands", True)))
        if hasattr(self, "_manual_left_clip_check"):
            self._manual_left_clip_check.setChecked(bool(s.get("chart_left_clip_info", False)))

        instr = s.get("chart_instrument", "i1")
        idx = self._instr_combo.findData(instr)
        if idx >= 0:
            self._instr_combo.setCurrentIndex(idx)
        self._rebuild_paper_combo()  # populate/filter even if instrument index didn't change

        paper = s.get("chart_paper", "A4")
        idx = self._paper_combo.findData(paper)
        if idx >= 0:
            self._paper_combo.setCurrentIndex(idx)

        self._pages_spin.setValue(int(s.get("chart_pages", 1)))
        self._dd_check.setChecked(bool(s.get("chart_double_density", False)))
        self._td_check.setChecked(bool(s.get("chart_triple_density", False)))
        self._lb_check.setChecked(bool(s.get("chart_disable_left_border", True)))
        self._nsl_check.setChecked(bool(s.get("chart_no_strip_limit", False)))
        self._update_dd_visibility()
        self._update_patch_count()

        # Restore manual widget values. Prefer the case-disambiguated key;
        # fall through to the legacy bare key for backward compatibility, then
        # evict the bare key so it can't keep colliding with its case-twin in
        # the Windows registry (HKCU is case-insensitive). Legacy values that
        # don't type-coerce to the widget's expected type are discarded
        # silently — they are leftover bytes from a clobbering case-twin.
        for tool, widgets in self._manual_widgets.items():
            for pw in widgets:
                if pw in self._d_cascade_widgets:
                    continue
                new_key = _pw_settings_key(tool, pw.flag)
                v = s.get(new_key)
                if v is None:
                    legacy_key = f"manual_{tool}_{pw.flag}"
                    if legacy_key != new_key:
                        v = s.get(legacy_key)
                        try:
                            if s._qs.contains(legacy_key):
                                s._qs.remove(legacy_key)
                        except AttributeError:
                            pass
                        if v is not None and not _value_compatible_with_pw(v, pw):
                            v = None
                if v is not None:
                    pw.set_value(v)
                # Re-arm the enable-checkbox for expert non-boolean rows; without
                # this the value is restored but the flag stays off (and is
                # dropped by build_args). Only act when the key was persisted, so
                # presets/defaults from before this fix don't force rows off.
                if pw.has_separate_enable:
                    en = s.get(f"{new_key}_enabled")
                    if en is not None:
                        pw.set_user_enabled(bool(en))
        for idx, pw in enumerate(self._d_cascade_widgets):
            v = s.get(f"manual_targen_-D_{idx}")
            if v is not None:
                pw.set_value(v)
            pw.set_user_enabled(bool(s.get(f"manual_targen_-D_{idx}_enabled", False)))
        self._rebuild_d_cascade_visibility()
        if self._bit8_radio is not None and self._bit16_radio is not None:
            is_16bit = bool(s.get("manual_printtarg_tiff_16bit", False))
            self._bit16_radio.setChecked(is_16bit)
            self._bit8_radio.setChecked(not is_16bit)
        if self._manual_pages_spin is not None:
            self._manual_pages_spin.setValue(int(s.get("manual_pages", 1)))
        if self._manual_auto_patches_check is not None:
            auto_on = bool(s.get("manual_auto_patches", False))
            self._manual_auto_patches_check.setChecked(auto_on)
            self._on_auto_patches_toggled(auto_on)
        self._load_auto_neutral_states(
            grey  = bool(s.get("manual_auto_grey",  False)),
            white = bool(s.get("manual_auto_white", False)),
            black = bool(s.get("manual_auto_black", False)),
        )
        # Restore manual triple-density. The toggle handler stashes the
        # current -a / -m / -P / -L widget values, so they need to reflect
        # the user's pre-TD preferences at this point — not the TD overrides
        # themselves. Older builds (and the very first 3.7.9 build, before
        # the save-time fix) persisted the override values directly when
        # defaults were saved while TD was on; heal that on the way in by
        # detecting the TD-override fingerprint and substituting sane
        # defaults for the stash.
        td_saved = bool(s.get("manual_printtarg__triple_density", False))
        if td_saved and self._manual_td_check is not None:
            def _approx(a, b, eps=0.01) -> bool:
                try:
                    return abs(float(a) - float(b)) <= eps
                except (TypeError, ValueError):
                    return False
            looks_overridden = (
                self._manual_a_pw is not None and _approx(self._manual_a_pw.get_raw_value(), 1.3)
                and self._manual_m_pw is not None and int(self._manual_m_pw.get_raw_value() or 0) == 5
                and self._manual_P_pw is not None and bool(self._manual_P_pw.get_raw_value())
                and self._manual_lb_pw is not None and bool(self._manual_lb_pw.get_raw_value())
            )
            if looks_overridden:
                # Pretend the user had Argyll defaults pre-TD. Anything more
                # specific is unrecoverable — the override values clobbered
                # the original on save.
                self._manual_a_pw.set_value(1.0)
                self._manual_m_pw.set_value(6)
                self._manual_P_pw.set_value(False)
                self._manual_lb_pw.set_value(True)
        if self._manual_td_check is not None:
            self._manual_td_check.setChecked(td_saved)
        self._update_manual_lb_visibility()
        self._apply_instrument_default_margin()
        self._update_isis_preview_banner()

        presets = self._load_presets_from_settings()
        self._populate_preset_combo(presets)

        mode = s.get("chart_mode", "guided")
        self._switch_mode(mode)
