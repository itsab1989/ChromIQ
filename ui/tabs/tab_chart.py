"""Tab 1: Chart Creation — Guided and Manual modes."""
from __future__ import annotations

import json
import re
import shlex
import shutil
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
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
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStyledItemDelegate,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.logger import get_logger
from core.platform_paths import file_manager_name
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
    paper_name_token,
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
from ui.widgets import fit_log_height, CollapsibleGroupBox, NoScrollComboBox, NoScrollSpinBox, PatchGridButton, PrefixLockedLineEdit, icc_profile_paths, load_magenta_folder_icon, make_browse_button, open_file_dialog, set_folder_icon, set_preset_icon
from core.i18n import count_phrase, tr
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

# How long a chart generate may run before the slow-chart watchdog offers the
# user a way out. A healthy targen finishes in ~1-2 s; the OFPS-cliff case
# never finishes. 30 s comfortably clears legitimately large charts (even on
# slow machines) while still rescuing the pathological ones quickly.
_SLOW_CHART_WATCHDOG_MS = 30_000

# targen -v reports its (slow) patch-placement seeding as "Added N/M". We
# collapse those into a single in-place percentage line so the log shows
# meaningful progress instead of a wall of numbers. Take the LAST match in a
# chunk — targen emits these with carriage returns, so several can arrive at
# once.
_TARGEN_ADDED_RE = re.compile(r"Added (\d+)/(\d+)")


def _number_of_sets(path) -> int | None:
    """``NUMBER_OF_SETS`` from a CGATS .ti1/.ti2, or None if unreadable."""
    try:
        for line in Path(path).read_text(errors="ignore").splitlines():
            if line.startswith("NUMBER_OF_SETS"):
                return int(line.split()[-1])
    except (OSError, ValueError):
        return None
    return None


def _clean_preset_name(name: str) -> str:
    """Normalise a preset name for storage / comparison (#59).

    NFC-normalises and drops Unicode control & format characters — most
    importantly the zero-width space (U+200B) and other invisible code points
    a pasted name can carry, which ``str.strip()`` leaves in place. Without
    this, two names that look identical but differ by an invisible character
    don't match, so the overwrite prompt never fires and a duplicate preset is
    created. Ordinary whitespace is still trimmed at the ends.
    """
    name = unicodedata.normalize("NFC", name or "")
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C")
    return name.strip()


def _preset_match_key(name: str) -> str:
    """A normalised key for deciding whether two preset names are "the same"
    for the overwrite check (#59).

    Strips invisible characters and folds case, but keeps dots, hyphens, spaces
    and underscores *distinct* — they're legitimate, meaning-bearing parts of a
    name (e.g. ``w11.5mm`` ≠ ``w11_5mm``), so they must not be collapsed. The
    dot-vs-underscore duplicate is prevented at the source instead: the layout
    editor's Save & apply now keeps dots rather than forcing them to underscores.
    """
    return _clean_preset_name(name).casefold()


def _layout_options_from_params(params):
    """Build an editor ``LayoutOptions`` (Set A) from Create Chart ``ChartParams``.

    The one place the manual panel's effective layout knobs are mapped to the
    editor's ``LayoutOptions`` — shared by the chart's meta stamp and the
    Save-Preset layout sync so both describe the layout identically (#92)."""
    from workflow.ti2_relayout import LayoutOptions
    return LayoutOptions(
        spacer_mode=("none" if params.no_spacers
                     else "bw" if params.bw_spacers else "colored"),
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
# Extended 1944-patch RGB target (shuffled patch set), in A4 and US-Letter
# layouts. Same patch set, two page sizes — paper carried in the label so the
# pair is distinguishable in the dropdown and the overlay.
EXT1944_A4_PRESET_KEY = "__chromiq_ext1944_a4_builtin__"
EXT1944_A4_PRESET_LABEL = "★  i1Pro · A4-1944p-3pages extended target by Pharmacist  ·  built-in"
EXT1944_LETTER_PRESET_KEY = "__chromiq_ext1944_letter_builtin__"
EXT1944_LETTER_PRESET_LABEL = "★  i1Pro · Letter-1944p-3pages extended target by Pharmacist  ·  built-in"

# key -> (asset stem under assets/charts, default target name). Charts are filed
# by creator/colorspace/instrument/paper/target; the stem locates <stem>.ti1,
# <stem>.ti2 and the <stem>_NN.tif page TIFFs inside that leaf folder.
# The default target name follows the sortable convention (#68):
# <instrument>-<paper>-<patches>p-<pages>pages-<set name>. Orientation isn't
# stored for these pre-rendered charts, so it's omitted (the colour-set name is
# the "additional text" tail). It's only the prompt's suggested default — the
# user can edit it freely.
PREBUILT_PRESETS = {
    TC924_PRESET_KEY:          ("assets/charts/pharmacist/rgb/i1pro/a4/tc924/tc924",            "i1Pro-A4-924p-2pages-TC9.24 by Pharmacist"),
    ABW1110_PRESET_KEY:        ("assets/charts/pharmacist/rgb/i1pro/a4/abw1110/abw1110",        "i1Pro-A4-1110p-2pages-ABW-optimized by Pharmacist"),
    TC918EG_A4_PRESET_KEY:     ("assets/charts/pharmacist/rgb/i1pro/a4/tc918eg/tc918eg",        "i1Pro-A4-1160p-2pages-TC9.18 extended greys by Pharmacist"),
    TC918EG_LETTER_PRESET_KEY: ("assets/charts/pharmacist/rgb/i1pro/letter/tc918eg/tc918eg",    "i1Pro-Letter-1160p-2pages-TC9.18 extended greys by Pharmacist"),
    TC300_PRESET_KEY:          ("assets/charts/pharmacist/rgb/colormunki/a4/tc300/tc300",       "ColorMunki-A4-300p-1page-TC3.00 by Pharmacist"),
    ABW702_PRESET_KEY:         ("assets/charts/pharmacist/rgb/colormunki/a4/abw702/abw702",     "ColorMunki-A4-702p-2pages-ABW-optimized by Pharmacist"),
    TC924_CM_A3_PRESET_KEY:    ("assets/charts/pharmacist/rgb/colormunki/a3/tc924/tc924",       "ColorMunki-A3-924p-1page-TC9.24 by Pharmacist"),
    TC918EG_CM_A3_PRESET_KEY:  ("assets/charts/pharmacist/rgb/colormunki/a3plus/tc918eg/tc918eg", "ColorMunki-A3+-1160p-1page-TC9.18 extended greys by Pharmacist"),
    EXT1944_A4_PRESET_KEY:     ("assets/charts/pharmacist/rgb/i1pro/a4/extended1944/extended1944",     "i1Pro-A4-1944p-3pages-extended target by Pharmacist"),
    EXT1944_LETTER_PRESET_KEY: ("assets/charts/pharmacist/rgb/i1pro/letter/extended1944/extended1944", "i1Pro-Letter-1944p-3pages-extended target by Pharmacist"),
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

# Knut's "Full layout setup" family (#63): multi-colour-set charts, each with
# its OWN bundled .ti1 (unlike the shared-.ti1 TC9.18 presets) AND a complete
# Create-Chart recipe (the colour-set generators + layout), so loading one
# repopulates the whole Create Chart tab — they're meant as a basis for new
# charts. Driven by his exported Create Chart presets; 8-bit, default randomise
# (printtarg -r off, no fixed -R seed).
KNUT_FLS_SUFFIX = " · Full layout setup"
_KNUT_FLS_DIR = "assets/charts/knut/rgb/fulllayout"

# Knut's Scanner family (#100): engine-built charts for flatbed-scanner printer
# profiling. One shared LayoutRecipe (his exported preset, verbatim) — only the
# paper differs between the A4 and Letter rows. randomize=False + seed=None keeps
# the printed layout identical to Knut's originals; patch order doesn't matter
# for scanin (the .cht fiducials locate every patch).
KNUT_SCANNER_SUFFIX = " · Profile printer with scanner"
_KNUT_SCANNER_DIR = "assets/charts/knut/rgb/scanner"
_KNUT_SCANNER_RECIPE: dict = {
    "instrument": "SS", "paper": "A4R", "dpi": 300,
    "randomize": False, "seed": None, "hflag": False,
    "cm_density": 1, "cm_stagger": False,
    "spacer_on": True, "spacer_mode": "colored", "spacer_palette": [],
    "spacer_overrides": {}, "edge_spacers": False,
    "patch_area_align": "top-left", "pscale": 1.0, "sscale": 1.0,
    "border": 6.0, "margin_top": 8.0, "margin_right": 4.0,
    "margin_bottom": 4.0, "margin_left": 4.0,
    "use_instrument_margins": False,
    "patch_w_mm": 0.0, "patch_h_mm": 0.0,
    "layout_mode": "area_first", "area_method": "by_width",
    "area_cols": 0, "area_rows": 0, "area_ratio": 1.0,
    "area_min_patch_mm": 4.0,
    "spacer_width_mm": 0.0, "inter_patch_mm": 0.0, "strip_gap_mm": 0.0,
    "max_strip_mm": 0.0, "strip_indicator_gap_mm": 0.0,
    "offset_x_mm": 0.0, "offset_y_mm": 0.0,
    "compression": "lzw", "show_strip_indicators": True,
    "indicator_font": "JetBrains Mono", "indicator_align": "left",
    "underline_mode": "off", "underline_thickness_mm": 0.5,
    "underline_gap_mm": 0.5,
    "chart_text_font": "Inter", "text_edge_mm": 4.0,
    "text_edge_top_mm": 4.0, "text_edge_clip_mm": 4.0,
    "clip_border": True, "clip_border_width_mm": 26.0, "clip_side": "left",
    "clip_content_mode": "off", "clip_text_font": "Inter",
    "clip_image_scale": 100.0,
    "strip_pattern": "A-Z, A-Z", "patch_pattern": "0-9,@-9,@-9;1-999",
}


# Red River Paper vendor family: one fixed 2052-patch verification set (their
# .ti1, byte-identical), offered as four ready starting points in the dropdown /
# overlay. Engine-built (layout_recipe drives the ChromIQ layout engine); the
# patch set is locked (targen greyed) but every layout control stays editable, so
# a user can re-flow paper / margins / branding freely. Each row differs only in
# instrument + paper; the recipes below carry the worked-out, verified layout
# (i1Pro: instrument margins + clip-border record; ColorMunki: Guided high-
# density with edge spacers). ColorMunki triple density is intentionally NOT
# offered — it is hardware-unverified.
_REDRIVER_SUFFIX = " · Standard Patch Set v25"
_REDRIVER_DIR = "assets/charts/redriver/rgb/standard_patch_set_v25"

# Common engine settings shared by every Red River variant.
# Layout: "area first" (Prioritise chart area, then fit patches) so the page
# margins are LAW and the patches fill the margin box — Knut's preference, for
# margin control. by_width sizes the patches from a per-instrument minimum width
# and grows them to fill; the minimum lives on each instrument recipe below.
_REDRIVER_BASE: dict = {
    "dpi": 300, "randomize": True, "seed": None,
    "spacer_on": True, "spacer_mode": "colored",
    "edge_spacers": True,               # each strip starts + ends on a spacer
    "layout_mode": "area_first",
    "area_method": "by_width",
    "area_ratio": 1.0,                  # patch height ≈ width (square-ish)
    "border": 6.0,
}
# i1Pro: area-first BY GRID (columns × rows). i1Pro strips must stay under the
# 240 mm jig ruler, and area-first "by width" fills the whole page height (~280 mm
# strips, over the ruler). A fixed grid + a paper-tuned bottom margin keeps the
# strip length just under 240 mm (Knut). The clip band (≈ left margin) carries the
# Red River / ChromIQ logo. area_cols / area_rows / margin_bottom are set per paper
# on each preset row. Path resolves in dev + frozen via resource_path.
_REDRIVER_RECIPE_I1: dict = {
    **_REDRIVER_BASE,
    "instrument": "i1", "cm_density": 1,
    "area_method": "by_grid",
    "use_instrument_margins": False,
    "margin_top": 38.0, "margin_right": 9.0, "margin_left": 26.0,
    "clip_border": True, "clip_border_width_mm": 26.0, "clip_side": "left",
    "clip_content_mode": "image",
    "clip_image_path": str(resource_path(f"{_REDRIVER_DIR}/clip_logo.png")),
    "clip_image_rotation": 90, "clip_image_scale": 100.0,
}
# ColorMunki: area-first BY GRID (columns × rows), Knut's tuned 13 × 20. The
# ColorMunki is hand-guided (no jig ruler), so a full-page strip is fine; a fixed
# grid + these margins give a comfortable 13.5 mm patch and pack the set into 8
# pages. The 26 mm clip band (= left margin, so no clip-vs-margin flag) carries the
# same Red River / ChromIQ logo band as the i1Pro clip. No strip stagger (Knut).
_REDRIVER_RECIPE_CM: dict = {
    **_REDRIVER_BASE,
    "instrument": "CM", "cm_stagger": False,
    "area_method": "by_grid", "area_cols": 13, "area_rows": 20,
    "use_instrument_margins": False,
    "margin_top": 28.0, "margin_right": 9.0, "margin_bottom": 10.0, "margin_left": 26.0,
    "clip_border": False, "clip_side": "left", "clip_border_width_mm": 26.0,
    "clip_content_mode": "image",
    "clip_image_path": str(resource_path(f"{_REDRIVER_DIR}/clip_logo.png")),
    "clip_image_rotation": 90, "clip_image_scale": 100.0,
}


# Pulls a "-w<number>mm" patch-width token (e.g. "-w11.5mm") out of a name.
_WIDTH_TOKEN_RE = re.compile(r"-w\d+(?:\.\d+)?mm")


def _sortable_builtin_name(instr_label: str, full_name: str, suffix: str) -> str:
    """Normalise a built-in preset's name to the sortable convention (#68):

        <instrument>-<paper>-<patches>p-<pages>pages-<orientation>-<extras>

    The instrument leads (so sorting groups by device), and the two non-sorting
    bits — the layout's ``-w<number>mm`` patch width and the colour-set name
    (e.g. "TC9.18+Spyderprint Grays") — move to the tail as "additional text",
    exactly where the user's own free text would sit. Earlier the width sat in
    the middle and the instrument was missing, which broke folder sorting and
    re-ordered inconsistently.
    """
    base = full_name
    set_name = ""
    if suffix and base.endswith(suffix):
        base = base[: -len(suffix)]
        set_name = suffix.strip(" ·")          # " · Full layout setup" → "Full layout setup"
    width = ""
    m = _WIDTH_TOKEN_RE.search(base)
    if m:
        width = m.group(0)[1:]                  # "-w11.5mm" → "w11.5mm"
        base = base[: m.start()] + base[m.end():]   # leaves "…-<orientation>"
    name = f"{instr_label}-{base}"
    tail = "-".join(t for t in (width, set_name) if t)
    return f"{name}-{tail}" if tail else name


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
    triple_density: bool = False        # ChromIQ triple density (i1Pro layout + CM tag)
    spacer_scale: float | None = None   # printtarg -A (None → leave at default)
    seed: int | None = None             # printtarg -R (None → default randomise)
    # Full-layout-setup family (#63) extensions. The defaults reproduce the shared-.ti1
    # TC9.18+Spyderprint presets byte-for-byte, so only the new family sets them:
    ti1_asset: str = KNUT_TI1_ASSET     # bundled .ti1 (shared one by default)
    patches: int = KNUT_PATCHES         # descriptive targen -f (panel display only)
    white: int = KNUT_WHITE             # descriptive targen -e
    black: int = KNUT_BLACK             # descriptive targen -B
    no_strip_limit: bool = True         # printtarg -P
    suppress_left_clip: bool = False    # printtarg -L
    no_randomise: bool = False          # printtarg -r (False = randomise, the default)
    tiff_16bit: bool = True             # 16-bit TIFF (→ -T)
    suffix: str = KNUT_SUFFIX           # family name tail (stripped for target name)
    # Scanner family (#100) extensions: an engine-built preset carries the full
    # ChromIQ layout-engine recipe (LayoutRecipe.to_dict()); selecting it turns
    # the engine on and seeds the layout panel instead of the printtarg widgets.
    layout_recipe: dict | None = None   # engine recipe → engine-built preset
    # Full-layout-setup presets that reproduce printtarg EXACTLY through the
    # ChromIQ engine (verified byte-for-byte) build on the engine path instead
    # of printtarg — so they carry native engine geometry (scanner-ready) with
    # no printtarg -s capture. The recipe is derived from the preset's own
    # printtarg fields at selection (_fls_engine_recipe), so nothing is
    # hand-authored. Unlike `layout_recipe`, the printtarg fields stay the
    # source of truth. (#63; Basti — the 4 double-density "near" presets that
    # only match in size keep the printtarg path.)
    engine: bool = False
    group: str = ""                     # dropdown/overlay group ("" → by instrument)

    @property
    def key(self) -> str:
        return f"__chromiq_knut_{self.slug}__"

    @property
    def display_group(self) -> str:
        """Group header in the dropdown + overlay — an explicit family group
        ("Scanner") or, classically, the instrument the chart targets."""
        return self.group or ("i1Pro" if self.instrument == _KNUT_I1
                              else "ColorMunki")

    @property
    def combo_label(self) -> str:
        return f"★  {self.display_group} · {self.name}  ·  built-in"

    @property
    def overlay_label(self) -> str:
        return self.name  # the overlay already groups by instrument / family

    @property
    def default_target_name(self) -> str:
        return _sortable_builtin_name(self.display_group, self.name, self.suffix)


# Named printtarg page sizes in mm (only those the presets use); custom sizes are
# given as "WxH" and parsed directly. Used to order the presets by paper size.
_PAPER_MM = {
    "A4": (210.0, 297.0), "A4R": (297.0, 210.0),
    "Letter": (215.9, 279.4), "LetterR": (279.4, 215.9),
    "A3": (297.0, 420.0), "A2": (420.0, 594.0),
    # "11x17" is an inch designation (Tabloid), not millimetres — its real size
    # is 279.4 × 431.8 mm. Listed here so _paper_area_mm2 resolves it by name
    # before the "WxH" fallback would misread "11x17" as 187 mm².
    "11x17": (279.4, 431.8),
}


def _paper_area_mm2(paper: str) -> float:
    """Sheet area in mm² for a printtarg -p value (named size or 'WxH')."""
    # Named sizes win over the "WxH" split so inch-designated codes like
    # "11x17" (which contain an 'x' but are not millimetres) resolve correctly.
    dims = _PAPER_MM.get(paper)
    if dims:
        return dims[0] * dims[1]
    if "x" in paper:
        try:
            w, h = paper.split("x", 1)
            return float(w) * float(h)
        except ValueError:
            return 0.0
    return 0.0


# Instrument flag → margin-threshold label (must match settings_dialog
# _MARGIN_INSTRUMENTS and core.settings seed keys).
_MARGIN_INSTR_LABEL = {
    "i1": "i1Pro", "p3": "i1Pro 3+", "CM": "ColorMunki",
    "SS": "SpectroScan", "isis": "i1iSis",
}

# Canonical sheet name keyed by sorted (short, long) mm, rounded — so any paper
# code (named, "WxH", or rotated) resolves to one threshold-combo paper name.
# Orientation is carried separately, so Tabloid/Ledger (same sheet) share "Tabloid".
_CANON_PAPER_BY_DIMS = {
    (210.0, 297.0): "A4",
    (215.9, 279.4): "Letter",
    (215.9, 355.6): "Legal",
    (297.0, 420.0): "A3",
    (329.0, 483.0): "A3+",
    (420.0, 594.0): "A2",
    (279.4, 431.8): "Tabloid",
}


def _canonical_paper_name(w_mm: float, h_mm: float) -> str | None:
    """Best-effort canonical sheet name from page dimensions (mm), or None.

    Tolerant to ~2 mm so a measured TIFF page (px → mm) still matches the named
    size. Returns None for unknown sizes (→ no thresholds for that combo)."""
    lo, hi = sorted((w_mm, h_mm))
    for (clo, chi), name in _CANON_PAPER_BY_DIMS.items():
        if abs(lo - clo) <= 2.5 and abs(hi - chi) <= 2.5:
            return name
    return None


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
    # (The 17 "TC9.18+Spyderprint Grays" shared-.ti1 presets were removed in #89 —
    # only the Full layout setup and "by Pharmacist" built-ins remain.)

    # Full-layout-setup family (#63) — Knut's exported Create Chart charts, each
    # with its own bundled .ti1 (per-preset patch set + layout) AND a sidecar
    # recipe.json (the colour-set + layout recipe) so the preset can seed a New
    # chart. Several ColorMunki ones are triple density (i1Pro layout + ColorMunki
    # tag); the i1Pro ones keep the left clip + strip limit (-L/-P). All 8-bit.
    # Rows + assets generated from his JSON exports (see scripts).
    # ColorMunki Full-layout-setup family — reworked by Knut (#89). The multi-
    # page charts are double density; the dense single-page charts stay triple
    # density (the export's printtarg block diverges from its editor_recipe for
    # those — the recipe's td/scale is authoritative). Patch width is in each name.
    _Ti1Preset("fls_colormunki_a3_1196p_2pages_portrait", "A3-1196p-2pages-Portrait-w12.0mm" + KNUT_FLS_SUFFIX,
               _KNUT_CM, "A3", 0.88, 6, 2,
               double_density=True, ti1_asset=f"{_KNUT_FLS_DIR}/fls_colormunki_a3_1196p_2pages_portrait/chart.ti1", patches=1196, white=9, black=8, no_strip_limit=True, tiff_16bit=False, suffix=KNUT_FLS_SUFFIX, engine=True),
    _Ti1Preset("fls_colormunki_a3_1224p_2pages_landscape", "A3-1224p-2pages-Landscape-w12.0mm" + KNUT_FLS_SUFFIX,
               _KNUT_CM, "420x297", 0.85, 6, 2,
               double_density=True, ti1_asset=f"{_KNUT_FLS_DIR}/fls_colormunki_a3_1224p_2pages_landscape/chart.ti1", patches=1224, white=9, black=8, no_strip_limit=True, tiff_16bit=False, suffix=KNUT_FLS_SUFFIX),
    _Ti1Preset("fls_colormunki_a3_1575p_3pages_portrait", "A3-1575p-3pages-Portrait-w13.0mm" + KNUT_FLS_SUFFIX,
               _KNUT_CM, "A3", 0.94, 6, 3,
               double_density=True, ti1_asset=f"{_KNUT_FLS_DIR}/fls_colormunki_a3_1575p_3pages_portrait/chart.ti1", patches=1575, white=9, black=8, no_strip_limit=True, tiff_16bit=False, suffix=KNUT_FLS_SUFFIX),
    _Ti1Preset("fls_colormunki_a3_2016p_4pages_portrait", "A3-2016p-4pages-Portrait-w13.0mm" + KNUT_FLS_SUFFIX,
               _KNUT_CM, "A3", 0.96, 6, 4,
               double_density=True, ti1_asset=f"{_KNUT_FLS_DIR}/fls_colormunki_a3_2016p_4pages_portrait/chart.ti1", patches=2016, white=9, black=8, no_strip_limit=True, tiff_16bit=False, suffix=KNUT_FLS_SUFFIX, engine=True),
    _Ti1Preset("fls_colormunki_a3_2016p_4pages_portrait_nature_focus", "A3-2016p-4pages-Portrait-w13.0mm-Nature Focus" + KNUT_FLS_SUFFIX,
               _KNUT_CM, "A3", 0.96, 6, 4,
               double_density=True, ti1_asset=f"{_KNUT_FLS_DIR}/fls_colormunki_a3_2016p_4pages_portrait_nature_focus/chart.ti1", patches=2016, white=9, black=8, no_strip_limit=True, tiff_16bit=False, suffix=KNUT_FLS_SUFFIX, engine=True),
    _Ti1Preset("fls_colormunki_a3plus_1190p_1page_portrait", "A3Plus-1190p-1page-Portrait-w9.0mm" + KNUT_FLS_SUFFIX,
               _KNUT_CM, "329x483", 1.14, 6, 1,
               triple_density=True, ti1_asset=f"{_KNUT_FLS_DIR}/fls_colormunki_a3plus_1190p_1page_portrait/chart.ti1", patches=1190, white=9, black=8, no_strip_limit=True, suppress_left_clip=True, tiff_16bit=False, suffix=KNUT_FLS_SUFFIX, engine=True),
    _Ti1Preset("fls_colormunki_a3plus_1196p_1page_landscape", "A3Plus-1196p-1page-Landscape-w9.0mm" + KNUT_FLS_SUFFIX,
               _KNUT_CM, "483x329", 1.12, 6, 1,
               triple_density=True, ti1_asset=f"{_KNUT_FLS_DIR}/fls_colormunki_a3plus_1196p_1page_landscape/chart.ti1", patches=1196, white=9, black=8, no_strip_limit=True, suppress_left_clip=True, tiff_16bit=False, suffix=KNUT_FLS_SUFFIX, engine=True),
    _Ti1Preset("fls_colormunki_a4_480p_2pages_portrait", "A4-480p-2pages-Portrait-w13.0mm" + KNUT_FLS_SUFFIX,
               _KNUT_CM, "A4", 0.93, 6, 2,
               double_density=True, ti1_asset=f"{_KNUT_FLS_DIR}/fls_colormunki_a4_480p_2pages_portrait/chart.ti1", patches=480, white=9, black=8, no_strip_limit=True, tiff_16bit=False, suffix=KNUT_FLS_SUFFIX, engine=True),
    _Ti1Preset("fls_colormunki_a4_484p_1page_portrait", "A4-484p-1page-Portrait-w8.5mm" + KNUT_FLS_SUFFIX,
               _KNUT_CM, "A4", 1.08, 6, 1,
               triple_density=True, ti1_asset=f"{_KNUT_FLS_DIR}/fls_colormunki_a4_484p_1page_portrait/chart.ti1", patches=484, white=9, black=8, no_strip_limit=True, suppress_left_clip=True, tiff_16bit=False, suffix=KNUT_FLS_SUFFIX, engine=True),
    _Ti1Preset("fls_colormunki_a4_495p_1page_landscape", "A4-495p-1page-Landscape-w8.0mm" + KNUT_FLS_SUFFIX,
               _KNUT_CM, "A4R", 1.06, 6, 1,
               triple_density=True, ti1_asset=f"{_KNUT_FLS_DIR}/fls_colormunki_a4_495p_1page_landscape/chart.ti1", patches=495, white=9, black=8, no_strip_limit=True, suppress_left_clip=True, tiff_16bit=False, suffix=KNUT_FLS_SUFFIX, engine=True),
    # i1Pro A4 portrait family — reworked by Knut (#88) to keep the i1Pro clip
    # border (no -L) and honour the strip-length limit (no -P), with patch
    # widths baked into the names. The 960p landscape preset was retired.
    _Ti1Preset("fls_i1pro_a4_1200p_3pages_portrait", "A4-1200p-3pages-Portrait-w8.5mm" + KNUT_FLS_SUFFIX,
               _KNUT_I1, "A4", 1.05, 10, 3,
               ti1_asset=f"{_KNUT_FLS_DIR}/fls_i1pro_a4_1200p_3pages_portrait/chart.ti1", patches=1200, white=9, black=8, no_strip_limit=False, suppress_left_clip=False, tiff_16bit=False, suffix=KNUT_FLS_SUFFIX, engine=True),
    _Ti1Preset("fls_i1pro_a4_484p_1page_portrait", "A4-484p-1page-Portrait-w7.5mm" + KNUT_FLS_SUFFIX,
               _KNUT_I1, "A4", 0.96, 10, 1,
               ti1_asset=f"{_KNUT_FLS_DIR}/fls_i1pro_a4_484p_1page_portrait/chart.ti1", patches=484, white=9, black=8, no_strip_limit=False, suppress_left_clip=False, tiff_16bit=False, suffix=KNUT_FLS_SUFFIX, engine=True),
    _Ti1Preset("fls_i1pro_a4_495p_1page_landscape", "A4-495p-1page-Landscape" + KNUT_FLS_SUFFIX,
               _KNUT_I1, "A4R", 1.03, 10, 1,
               ti1_asset=f"{_KNUT_FLS_DIR}/fls_i1pro_a4_495p_1page_landscape/chart.ti1", patches=495, no_strip_limit=True, suppress_left_clip=True, tiff_16bit=False, suffix=KNUT_FLS_SUFFIX, engine=True),
    _Ti1Preset("fls_i1pro_a4_924p_2pages_portrait", "A4-924p-2pages-Portrait-w7.5mm" + KNUT_FLS_SUFFIX,
               _KNUT_I1, "A4", 0.98, 10, 2,
               ti1_asset=f"{_KNUT_FLS_DIR}/fls_i1pro_a4_924p_2pages_portrait/chart.ti1", patches=924, white=9, black=8, no_strip_limit=False, suppress_left_clip=False, tiff_16bit=False, suffix=KNUT_FLS_SUFFIX),
    _Ti1Preset("fls_i1pro_a4_924p_2pages_portrait_nature_focus", "A4-924p-2pages-Portrait-w7.5mm-Nature Focus" + KNUT_FLS_SUFFIX,
               _KNUT_I1, "A4", 0.98, 10, 2,
               ti1_asset=f"{_KNUT_FLS_DIR}/fls_i1pro_a4_924p_2pages_portrait_nature_focus/chart.ti1", patches=924, white=9, black=8, no_strip_limit=False, suppress_left_clip=False, tiff_16bit=False, suffix=KNUT_FLS_SUFFIX),

    # Scanner family (#100) — Knut's flatbed-scanner printer-profiling charts.
    # Engine-built (the layout_recipe drives the ChromIQ layout engine, not
    # printtarg): a dense 4 mm SpectroScan-style grid, printed without colour
    # management, scanned on a flatbed, then read via Tools → "Build scanner or
    # camera profile" with "Profile my printer from this scan". The recipes are
    # Knut's exported presets verbatim (only the paper differs between the two).
    # Knut's #107 refresh FILE said "Portrait", but both charts are laid out
    # on rotated (landscape) sheets — the name stays truthful (Basti).
    _Ti1Preset("scanner_a4_3430p_1page_landscape",
               "A4-3430p-1page-Landscape-w4.0mm" + KNUT_SCANNER_SUFFIX,
               "SS", "A4R", 1.0, 4, 1,
               ti1_asset=f"{_KNUT_SCANNER_DIR}/a4/chart.ti1", patches=3430,
               white=2, black=2, tiff_16bit=False, suffix=KNUT_SCANNER_SUFFIX,
               group="Scanner",
               layout_recipe=dict(_KNUT_SCANNER_RECIPE, paper="A4R")),
    _Ti1Preset("scanner_letter_3250p_1page_landscape",
               "Letter-3250p-1page-Landscape-w4.0mm" + KNUT_SCANNER_SUFFIX,
               "SS", "LetterR", 1.0, 4, 1,
               ti1_asset=f"{_KNUT_SCANNER_DIR}/letter/chart.ti1", patches=3250,
               white=2, black=2, tiff_16bit=False, suffix=KNUT_SCANNER_SUFFIX,
               group="Scanner",
               layout_recipe=dict(_KNUT_SCANNER_RECIPE, paper="LetterR")),
    # Two-page variants (Knut, #108): the same 4 mm scanner layout with a
    # denser patch set spread over two sheets.
    _Ti1Preset("scanner_a4_6860p_2pages_landscape",
               "A4-6860p-2pages-Landscape-w4.0mm" + KNUT_SCANNER_SUFFIX,
               "SS", "A4R", 1.0, 4, 2,
               ti1_asset=f"{_KNUT_SCANNER_DIR}/a4_2page/chart.ti1", patches=6860,
               white=3, black=3, tiff_16bit=False, suffix=KNUT_SCANNER_SUFFIX,
               group="Scanner",
               layout_recipe=dict(_KNUT_SCANNER_RECIPE, paper="A4R")),
    _Ti1Preset("scanner_letter_6500p_2pages_landscape",
               "Letter-6500p-2pages-Landscape-w4.0mm" + KNUT_SCANNER_SUFFIX,
               "SS", "LetterR", 1.0, 4, 2,
               ti1_asset=f"{_KNUT_SCANNER_DIR}/letter_2page/chart.ti1", patches=6500,
               white=3, black=3, tiff_16bit=False, suffix=KNUT_SCANNER_SUFFIX,
               group="Scanner",
               layout_recipe=dict(_KNUT_SCANNER_RECIPE, paper="LetterR")),
    # Three-page variants (Knut, #118), completing the 1/2/3-page set per paper.
    _Ti1Preset("scanner_a4_10290p_3pages_landscape",
               "A4-10290p-3pages-Landscape-w4.0mm" + KNUT_SCANNER_SUFFIX,
               "SS", "A4R", 1.0, 4, 3,
               ti1_asset=f"{_KNUT_SCANNER_DIR}/a4_3page/chart.ti1", patches=10290,
               white=3, black=3, tiff_16bit=False, suffix=KNUT_SCANNER_SUFFIX,
               group="Scanner",
               layout_recipe=dict(_KNUT_SCANNER_RECIPE, paper="A4R")),
    _Ti1Preset("scanner_letter_9750p_3pages_landscape",
               "Letter-9750p-3pages-Landscape-w4.0mm" + KNUT_SCANNER_SUFFIX,
               "SS", "LetterR", 1.0, 4, 3,
               ti1_asset=f"{_KNUT_SCANNER_DIR}/letter_3page/chart.ti1", patches=9750,
               white=3, black=3, tiff_16bit=False, suffix=KNUT_SCANNER_SUFFIX,
               group="Scanner",
               layout_recipe=dict(_KNUT_SCANNER_RECIPE, paper="LetterR")),

    # --- Red River Paper vendor family (one shared, locked 2052-patch .ti1) ---
    _Ti1Preset("redriver_i1pro_a4_2052p_4pages",
               "i1Pro · A4-2052p-4pages" + _REDRIVER_SUFFIX,
               "i1", "A4", 1.0, 6, 4,
               ti1_asset=f"{_REDRIVER_DIR}/chart.ti1", patches=2052,
               white=6, black=6, tiff_16bit=False, suffix=_REDRIVER_SUFFIX,
               group="Red River Paper",
               layout_recipe=dict(_REDRIVER_RECIPE_I1, paper="A4",
                                  area_cols=21, area_rows=25, margin_bottom=19.0)),
    _Ti1Preset("redriver_i1pro_letter_2052p_4pages",
               "i1Pro · Letter-2052p-4pages" + _REDRIVER_SUFFIX,
               "i1", "Letter", 1.0, 6, 4,
               ti1_asset=f"{_REDRIVER_DIR}/chart.ti1", patches=2052,
               white=6, black=6, tiff_16bit=False, suffix=_REDRIVER_SUFFIX,
               group="Red River Paper",
               layout_recipe=dict(_REDRIVER_RECIPE_I1, paper="Letter",
                                  area_cols=22, area_rows=24, margin_bottom=13.0)),
    _Ti1Preset("redriver_colormunki_a4_2052p_8pages",
               "ColorMunki · A4-2052p-8pages" + _REDRIVER_SUFFIX,
               "CM", "A4", 1.0, 6, 8,
               ti1_asset=f"{_REDRIVER_DIR}/chart.ti1", patches=2052,
               white=6, black=6, tiff_16bit=False, suffix=_REDRIVER_SUFFIX,
               group="Red River Paper",
               layout_recipe=dict(_REDRIVER_RECIPE_CM, paper="A4")),
    _Ti1Preset("redriver_colormunki_letter_2052p_8pages",
               "ColorMunki · Letter-2052p-8pages" + _REDRIVER_SUFFIX,
               "CM", "Letter", 1.0, 6, 8,
               ti1_asset=f"{_REDRIVER_DIR}/chart.ti1", patches=2052,
               white=6, black=6, tiff_16bit=False, suffix=_REDRIVER_SUFFIX,
               group="Red River Paper",
               layout_recipe=dict(_REDRIVER_RECIPE_CM, paper="Letter")),
    # A larger-patch ColorMunki option (13 × 16): fewer rows → ~14 mm patches,
    # the sweet spot for a ruler (Knut), at the cost of two more pages. Knut's
    # margins for this one (top 26, left 20, so a 20 mm clip band).
    _Ti1Preset("redriver_colormunki_a4_2052p_10pages",
               "ColorMunki · A4-2052p-10pages" + _REDRIVER_SUFFIX,
               "CM", "A4", 1.0, 6, 10,
               ti1_asset=f"{_REDRIVER_DIR}/chart.ti1", patches=2052,
               white=6, black=6, tiff_16bit=False, suffix=_REDRIVER_SUFFIX,
               group="Red River Paper",
               layout_recipe=dict(_REDRIVER_RECIPE_CM, paper="A4", area_rows=16,
                                  margin_top=26.0, margin_left=20.0,
                                  clip_border_width_mm=20.0)),
    _Ti1Preset("redriver_colormunki_letter_2052p_10pages",
               "ColorMunki · Letter-2052p-10pages" + _REDRIVER_SUFFIX,
               "CM", "Letter", 1.0, 6, 10,
               ti1_asset=f"{_REDRIVER_DIR}/chart.ti1", patches=2052,
               white=6, black=6, tiff_16bit=False, suffix=_REDRIVER_SUFFIX,
               group="Red River Paper",
               layout_recipe=dict(_REDRIVER_RECIPE_CM, paper="Letter", area_rows=16,
                                  margin_top=26.0, margin_left=20.0,
                                  clip_border_width_mm=20.0)),
]
KNUT_PRESETS_BY_KEY: dict[str, _Ti1Preset] = {p.key: p for p in KNUT_PRESETS}
KNUT_PRESET_KEYS = frozenset(KNUT_PRESETS_BY_KEY)


# --- built-in preset recipes (Set B: a preset's New-chart / Add design) -------
# Built-in presets can carry a creation recipe — the same colour-set + layout
# settings a user preset stores in its own .json — so loading the preset seeds
# the New-chart window, exactly like a locally-saved preset (Knut). A preset's
# recipe is looked up two ways, in order: a per-preset ``recipe.json`` sitting
# beside its bundled ``chart.ti1`` (the general convention — any built-in, any
# folder, can carry one; the Full-layout-setup family uses these), then an
# optional shared ``recipes.json`` keyed by the preset's display name (a legacy
# fallback; no shipped family relies on it any more).
def _recipe_display_key(p: "_Ti1Preset") -> str:
    """The name a preset's recipe is filed under in a shared recipes.json —
    group label (instrument, or "Scanner" for that family, #107) + the
    preset's name without its family suffix."""
    return f"{p.display_group} {p.name.replace(p.suffix, '').strip()}"


def _load_shared_wg_recipes() -> dict:
    try:
        path = resource_path(f"{_KNUT_FLS_DIR}/recipes.json")
        if path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
    except Exception:  # noqa: BLE001 — never block preset loading
        pass
    return {}


def builtin_preset_recipe(preset_key: str) -> dict | None:
    """The creation recipe a built-in preset carries, or None. Tries a
    per-preset ``recipe.json`` next to its ``chart.ti1`` first, then the shared
    wide-gamut store keyed by display name."""
    p = KNUT_PRESETS_BY_KEY.get(preset_key)
    if p is None:
        return None
    if p.ti1_asset:
        try:
            side = resource_path(p.ti1_asset).parent / "recipe.json"
            if side.is_file():
                rec = json.loads(side.read_text(encoding="utf-8"))
                if isinstance(rec, dict) and rec:
                    return rec
        except Exception:  # noqa: BLE001
            pass
    rec = _load_shared_wg_recipes().get(_recipe_display_key(p))
    return rec if isinstance(rec, dict) and rec else None


def builtin_recipe_choices() -> dict[str, dict]:
    """``{display_name: recipe}`` for every built-in preset that carries a
    recipe — registry-driven, so it's not tied to one hardcoded file and any
    future built-in with a recipe shows up automatically (Knut)."""
    out: dict[str, dict] = {}
    for p in KNUT_PRESETS:
        rec = builtin_preset_recipe(p.key)
        if rec:
            out[_recipe_display_key(p)] = rec
    return out


# Built-in presets can be parked here (shown greyed-out, non-selectable) pending
# a fix from their author. The i1Pro/A4 TC9.24 chart is parked: its bundled page
# image disagrees with its own .ti2 reference (one patch renders white where the
# reference says grey), so both printing it and deriving scanner geometry from it
# are unsafe — it returns once the bundle is regenerated. Its sibling ColorMunki
# A3 TC9.24 (TC924_CM_A3_PRESET_KEY) is fine and stays available.
DISABLED_BUILTIN_PRESET_KEYS = frozenset({TC924_PRESET_KEY})

# Every built-in (non-deletable) preset key — all four are prebuilt-files. Used
# to protect them from the delete button and to keep disk presets from shadowing
# them.
BUILTIN_PRESET_KEYS = frozenset(PREBUILT_PRESETS) | KNUT_PRESET_KEYS
BUILTIN_PRESET_LABELS = frozenset({
    TC924_PRESET_LABEL, ABW1110_PRESET_LABEL,
    TC918EG_A4_PRESET_LABEL, TC918EG_LETTER_PRESET_LABEL,
    TC300_PRESET_LABEL, ABW702_PRESET_LABEL,
    TC924_CM_A3_PRESET_LABEL, TC918EG_CM_A3_PRESET_LABEL,
    EXT1944_A4_PRESET_LABEL, EXT1944_LETTER_PRESET_LABEL,
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
          for p in sorted((q for q in KNUT_PRESETS if q.display_group == grp),
                          key=lambda q: _paper_sort_key(q.paper))]
    for grp in ("ColorMunki", "i1Pro", "Scanner", "Red River Paper")
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
        # A4 first (ascending patch count), then US-Letter — keep paper grouped.
        (TC924_PRESET_LABEL,   "A4-924p-2pages TC9.24 by Pharmacist",          TC924_PRESET_KEY),
        (ABW1110_PRESET_LABEL, "A4-1110p-2pages ABW-optimized by Pharmacist",  ABW1110_PRESET_KEY),
        (TC918EG_A4_PRESET_LABEL,     "A4-1160p-2pages TC9.18 extended greys by Pharmacist",     TC918EG_A4_PRESET_KEY),
        (EXT1944_A4_PRESET_LABEL,     "A4-1944p-3pages extended target by Pharmacist",     EXT1944_A4_PRESET_KEY),
        (TC918EG_LETTER_PRESET_LABEL, "Letter-1160p-2pages TC9.18 extended greys by Pharmacist", TC918EG_LETTER_PRESET_KEY),
        (EXT1944_LETTER_PRESET_LABEL, "Letter-1944p-3pages extended target by Pharmacist", EXT1944_LETTER_PRESET_KEY),
        *_KNUT_GROUP_ENTRIES["i1Pro"],
    ]),
    # Scanner family (#100): engine-built charts for flatbed-scanner printer
    # profiling — its own group, since no spectrophotometer is involved.
    ("Scanner", [
        *_KNUT_GROUP_ENTRIES["Scanner"],
    ]),
    # Vendor family: Red River Paper's shared verification patch set, four ready
    # starting points (its own group so it reads as a partner section).
    ("Red River Paper", [
        *_KNUT_GROUP_ENTRIES["Red River Paper"],
    ]),
]


def comparable_presets(settings) -> list[tuple[str, list[tuple[str, "Path"]]]]:
    """Presets whose patch set exists on disk, grouped for the #66 "Compare with
    profile" dropdown: ``[(group, [(label, .ti1 path), …]), …]`` — built-in
    presets by instrument plus a "Custom presets" group for user presets that
    bundled a .ti1. Re-read on each call (newly saved / deleted presets appear or
    disappear by themselves). Shared by the Tools 3D viewer and the TI2 editor."""
    groups: list[tuple[str, list[tuple[str, Path]]]] = []
    for instr, entries in BUILTIN_PRESET_GROUPS:
        items: list[tuple[str, Path]] = []
        for _combo, overlay_label, key in entries:
            asset = TabChart._builtin_ti1_asset(key)
            if asset:
                p = resource_path(asset)
                if p.is_file():
                    items.append((overlay_label, p))
        if items:
            groups.append((instr, items))
    custom: list[tuple[str, Path]] = []
    for name, data in _load_tab_presets("create_chart", settings).items():
        if isinstance(data, dict) and data.get("attached_ti1"):
            sc = _preset_sidecar_path("create_chart", str(name), ".ti1")
            if sc.is_file():
                custom.append((str(name), sc))
    if custom:
        groups.append((tr("Custom presets"), custom))
    return groups


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


class _CappedComboBox(NoScrollComboBox):
    """A combo whose popup is capped at ~15 rows and scrolls.

    On macOS, ``maxVisibleItems`` / the ``combobox-popup`` QSS hint don't
    reliably cap a styled compound combo's popup (it shows every row), so cap the
    popup container's height directly once it's shown — robust on every platform.
    """

    _MAX_ROWS = 20

    def showPopup(self) -> None:  # noqa: N802
        super().showPopup()
        view = self.view()
        if view is None:
            return
        row_h = view.sizeHintForRow(0) if self.count() else 0
        if row_h <= 0:
            row_h = 22
        max_h = row_h * self._MAX_ROWS + 4
        container = view.window()            # the popup frame
        if container is None:
            return
        if container.height() > max_h:
            view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            container.setMaximumHeight(max_h)
            container.resize(container.width(), max_h)
        # Re-anchor under the combo. macOS positions the menu-style popup so
        # the SELECTED item overlaps the combo — with a long list and a
        # selection near its end, the frame starts far above the widget (top
        # of the screen), and the height cap above shrinks it in place
        # without moving it back (Basti: popup stranded at the window top
        # after picking a Scanner preset). Anchoring below (or above when
        # there's no room) makes it behave like a plain dropdown.
        below = self.mapToGlobal(self.rect().bottomLeft())
        scr = (self.screen() or container.screen()).availableGeometry()
        y = below.y()
        if y + container.height() > scr.bottom():
            y = max(scr.top(),
                    self.mapToGlobal(self.rect().topLeft()).y()
                    - container.height())
        x = min(max(below.x(), scr.left()),
                max(scr.left(), scr.right() - container.width()))
        container.move(x, y)


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


def ti1_sidecar(src: Path) -> "Path | None":
    """The chart-settings file that belongs to a patch set, or None.

    A chart ChromIQ wrote keeps its layout recipe — patch size, margins,
    spacers, and the seed the patches were shuffled with — in a
    ``<stem>.channels.json`` beside the chart itself. When a user loads such a
    ``.ti1`` back in, that file is what lets the sheet come out exactly as it
    was rather than merely holding the same colours (Knut, #130 2026-07-27).
    """
    if src is None:
        return None
    cand = Path(src).with_suffix(".channels.json")
    return cand if cand.is_file() else None


def _chart_date_from_ti2(ti2: Path) -> str:
    """The day a chart was made, as ``YYYY-MM-DD``, read from its ``.ti2``.

    Charts written from now on save the record strip's date in their sidecar,
    so a rebuild can redraw it. Charts made before that — every project already
    on disk, including Knut's — have no such key, and their ``.ti2`` header is
    the only record of when the chart was created:

        CREATED "Thu Jul 30 17:45:54 2026"

    Returns "" when there is no usable date, which leaves the caller to stamp
    today: a guess would be worse than the honest current date.
    """
    import re as _re
    from datetime import datetime
    try:
        head = Path(ti2).read_text(errors="replace")[:4000]
    except OSError:
        return ""
    m = _re.search(r'CREATED\s+"([^"]+)"', head)
    if not m:
        return ""
    raw = m.group(1).strip()
    # ArgyllCMS and the engine both write C's asctime format. The weekday and
    # month names are locale-dependent when written (a German run produces
    # "Sa Aug 01 …"), so parse the numbers and ignore the words.
    m2 = _re.search(r"([A-Za-z]{3})\w*\s+(\d{1,2})\s+[\d:]+\s+(\d{4})", raw)
    if m2:
        months = {"jan": 1, "feb": 2, "mar": 3, "mär": 3, "apr": 4, "may": 5,
                  "mai": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10,
                  "okt": 10, "nov": 11, "dec": 12, "dez": 12}
        mon = months.get(m2.group(1).lower())
        if mon:
            try:
                return datetime(int(m2.group(3)), mon,
                                int(m2.group(2))).strftime("%Y-%m-%d")
            except ValueError:
                return ""
    # Some writers use an ISO date directly.
    m3 = _re.match(r"(\d{4}-\d{2}-\d{2})", raw)
    return m3.group(1) if m3 else ""


class _ChartRebuildGuard:
    """Keeps a chart's own files unchanged while its pages are redrawn.

    **Restore Used Chart redraws pages; it must never lay the chart out again.**
    Knut, #130 2026-07-29: he restored a verification's chart on
    Demo-Verify-History and the sheet that came back was a different sheet —
    shuffled where the original was in fixed order, a fresh seed, 15 patches per
    pass instead of 16, 60 sets instead of 64. The chart files in the dated
    ``chart/`` folder were fine; it was the redraw that replaced the live ones.

    The danger is quiet: a verification's ``.ti3`` describes the sheet that was
    measured, and if the ``.ti2`` beside it is silently swapped for another
    layout the two stop agreeing and nothing says so. So the bytes are held here
    and put back if the redraw changed them.

    The page images are deliberately NOT guarded — redrawing them is the whole
    point.
    """

    #: Everything that defines the chart, as opposed to how it looks on paper.
    SUFFIXES = (".ti1", ".ti2", ".channels.json")

    def __init__(self, ti2: Path) -> None:
        stem = Path(ti2).with_suffix("")
        self._held: dict[Path, bytes] = {}
        for suffix in self.SUFFIXES:
            path = Path(str(stem) + suffix)
            try:
                if path.is_file():
                    self._held[path] = path.read_bytes()
            except OSError:
                log.warning("could not hold %s for the rebuild", path)

    def put_back(self) -> list[str]:
        """Restore any held file the rebuild changed. Returns their names."""
        changed = []
        for path, data in self._held.items():
            try:
                if not path.is_file() or path.read_bytes() != data:
                    path.write_bytes(data)
                    changed.append(path.name)
            except OSError:
                log.warning("could not put %s back after the rebuild", path)
        if changed:
            log.warning("the page rebuild altered the chart itself (%s) — the "
                        "restored chart has been put back", ", ".join(changed))
        return changed


class TabChart(QWidget):
    """Step 1: create targen/printtarg test chart."""

    # (list[Path] tiffs, Path ti2, bool is_external_workflow)
    # is_external_workflow is True for i1iSis (i1Profiler hand-off); main_window
    # uses it to skip routing TIFFs/TI2 to the Print and Measure tabs.
    chart_finished  = pyqtSignal(object, object, bool)
    target_started  = pyqtSignal()
    # Asks the host to open the Edit / Create Chart Patch Set editor on the
    # current chart (from the "last page not full" hint, #93, Knut).
    edit_patch_set_requested = pyqtSignal()

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
        # Slow-chart watchdog: targen's default patch sampler (OFPS) can hang
        # for many minutes on certain pre-conditioning profiles at high patch
        # counts. If a generate runs longer than the threshold we offer the
        # user a way out (wait / rebuild faster / cancel). The trigger is
        # purely wall-clock — a healthy chart finishes in ~1-2 s regardless of
        # paper size or patch count, so elapsed time cleanly separates the
        # pathological case without us having to guess at patch totals.
        self._slow_watchdog = QTimer(self)
        self._slow_watchdog.setSingleShot(True)
        self._slow_watchdog.timeout.connect(self._on_slow_watchdog)
        self._slow_dialog = None        # the live SlowChartDialog, if any
        self._cancelled_by_user = False  # set when a slow-chart cancel is in flight
        self._progress_line_active = False  # last log line is a % progress line
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
        # Which Knut preset is active — each Full-layout-setup one has its OWN .ti1, so a
        # regenerate must reuse that preset's .ti1, not the shared TC9.18 one (#58).
        self._knut_active_key: str | None = None
        # Set once the user unlocks a vendor preset's patch recipe: from then on
        # the chart is no longer that vendor's certified set, so neither its clip
        # logo nor its layout-name stamp may keep naming the vendor. Reset on
        # every fresh preset selection.
        self._vendor_debranded = False
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
        # A chart handed over from the TI2 layout editor ("Save & apply"): its
        # files live in a staging folder we copy into a fresh run. Behaves like a
        # prebuilt-files preset — both panels start greyed, "Generate Chart"
        # re-imports the files verbatim (or re-lays the staged .ti1 if the user
        # unlocks printtarg, or runs a fresh targen if they unlock the recipe).
        self._applied_active = False
        self._applied_src_dir: Path | None = None
        self._applied_stem: str | None = None
        self._applied_targen_sig: list | None = None
        self._applied_printtarg_sig: list | None = None
        # A chart loaded in the Print/Measure tab is *reflected* here (read-only):
        # both panels grey, the pages show in the preview, but NOTHING is copied
        # and no project is created. Generating does nothing until the user
        # unlocks a panel (which drops the reflection and starts a fresh chart).
        self._reflected_active = False
        self._reflected_ti2: Path | None = None
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
        # The active chart-defining preset's New-chart/Add recipe (Set B), if it
        # carries one. Written into the generated run's meta.json so reopening
        # the chart in the layout editor seeds New chart / Add from this design
        # rather than the app-wide last-used state — restoring the rule "show
        # last-used only when the loaded layout has no saved settings" (#70, Knut
        # follow-up). None for Default / built-ins / plain targen charts.
        self._pending_editor_recipe: dict | None = None
        # Bundled .ti1 of the currently-selected built-in preset (TC9.18 /
        # Knut / prebuilt). Built-ins don't use _preset_ti1_path (that's for
        # user presets), but their patch count still feeds the Suggest-name
        # button (#62) — read from this. None for targen-based built-ins.
        self._builtin_ti1_path: Path | None = None
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

        # Load-profile / load-layout / built-in-presets / reveal-folder icons in
        # the header's upper-right (title height), matching the Measure, Build
        # Profile and Print tabs (Basti). They used to sit next to the
        # Guided / Manual switch.
        from ui.widgets import RevealFolderButton
        _hdr_trailing = QWidget(left)
        _ht = QHBoxLayout(_hdr_trailing)
        _ht.setContentsMargins(0, 0, 0, 0)
        _ht.setSpacing(6)
        # MOVED TO THE MASTHEAD (#130, spec agreed 2026-07-31). These acted on
        # the whole app rather than on one tab, and Load .ti2 existed twice —
        # once here and once on the other tab. Both now live top-left in the
        # masthead; see MastheadHeader.load_project_clicked / load_ti2_clicked.
        self._load_ti1_btn = PatchGridButton(SPEC_MAGENTA, _hdr_trailing)
        self._load_ti1_btn.setToolTip(
            tr("Load patch set.\n"
               "Open an existing chart layout (its patch set) and lay it\n"
               "out — targen is skipped. Accepts an Argyll .ti1, or an\n"
               "i1Profiler RGB set (.pxf or CGATS .txt), which are\n"
               "converted to .ti1 automatically."))
        self._load_ti1_btn.clicked.connect(self._on_load_ti1)
        _ht.addWidget(self._load_ti1_btn)
        self._builtin_preset_btn = BuiltinPresetButton(_hdr_trailing)
        self._builtin_preset_btn.clicked.connect(self._open_builtin_preset_overlay)
        _ht.addWidget(self._builtin_preset_btn)
        self._reveal_folder_btn = RevealFolderButton(SPEC_MAGENTA, _hdr_trailing)
        self._reveal_folder_btn.setToolTip(tr(
            "Open the folder holding the generated chart's files (the TIFF "
            "pages, .ti1/.ti2 and sidecars) in {manager}.").format(
                manager=file_manager_name()))
        self._reveal_folder_btn.clicked.connect(self._reveal_chart_folder)
        _ht.addWidget(self._reveal_folder_btn)
        left_layout.addWidget(TabHeader(
            tr("STEP 01 · GENERATE CHART"), tr("Create test chart"), "#ff4573", left,
            tooltip_title=tr("Step 1 — Make a test chart"),
            tooltip_body=tr(
                "This is where you design the sheet of colour patches your printer "
                "will print. The patches are how ChromIQ later \"learns\" how your "
                "printer reproduces colour.\n\n"
                "Before you start:\n"
                "• Pick the printer and paper you actually want to profile — the "
                "profile will only be accurate for that exact combination.\n"
                "• Have a rough idea of how careful you want to be. More patches = "
                "more accuracy, but also more ink and paper.\n\n"
                "First, name your profiling project.\n"
                "The \"Printer profile project name\" field at the top is the name of this "
                "whole job. It becomes the project folder, every file ChromIQ makes "
                "along the way (chart, measurements, ICC profile) and the name "
                "written inside the profile itself — so what you see later in, say, "
                "macOS ColorSync Utility matches the folder exactly. A good name "
                "describes the printer, the paper and the quality, e.g. "
                "Canon_Pro1000_PhotoRagBaryta_i1Pro3_High. Change your mind? Just "
                "edit the name — ChromIQ offers to rename the folder and files to "
                "match (until the profile has been built, after which you copy it to "
                "a new name instead). Your work is saved automatically; there's no "
                "Save button to remember.\n\n"
                "Coming back to a profile later?\n"
                "Click the magenta folder button in the header (top right) "
                "to reopen a profile you started before — its chart, measurements "
                "and any finished profile are all exactly where you left them. It "
                "asks for the profile's \"project.json\" file inside your ChromIQ "
                "folder.\n\n"
                "You have three ways to make a chart — from quickest to most "
                "hands-on:\n\n"
                "☰  Built-in presets — the presets button in the header, top right "
                "(its icon looks like a small list).\n"
                "Click it to open a little menu of ready-made, professionally tuned "
                "charts, grouped by the measuring instrument they're made for "
                "(i1Pro or ColorMunki). Pick one and ChromIQ drops the finished "
                "chart straight into your profile — under the name you chose above, "
                "without changing it — so there are no settings to understand and "
                "nothing to get wrong. This is the fastest way to a known-good "
                "target, and a great choice if you just want a reliable chart "
                "without thinking about the details. (The very same presets also "
                "live at the bottom of Manual mode's \"Presets\" dropdown, in case "
                "you'd rather find them there.)\n\n"
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
            trailing_widget=_hdr_trailing,
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
        self._guided_btn = QPushButton(tr("GUIDED"), self)
        self._guided_btn.setCheckable(True)
        self._guided_btn.setChecked(True)
        self._guided_btn.setObjectName("mode_btn")
        self._guided_btn.setFont(_mode_font)
        self._manual_btn = QPushButton(tr("MANUAL"), self)
        self._manual_btn.setCheckable(True)
        self._manual_btn.setObjectName("mode_btn")
        self._manual_btn.setFont(_mode_font)
        self._guided_btn.clicked.connect(lambda: self._switch_mode("guided"))
        self._manual_btn.clicked.connect(lambda: self._switch_mode("manual"))
        mode_row.addWidget(self._guided_btn)
        mode_row.addWidget(self._manual_btn)
        mode_row.addStretch()
        # (The load / preset / reveal icons moved to the header's upper-right.)
        left_layout.addWidget(self._mode_row_widget)

        # Stacked panel
        self._stack = QStackedWidget(self)
        self._guided_panel = self._make_guided_panel()
        self._manual_panel = self._make_manual_panel()
        self._link_instrument_controls()
        self._stack.addWidget(self._guided_panel)
        self._stack.addWidget(self._manual_panel)
        left_layout.addWidget(self._stack, stretch=1)

        # Auto-update-preview toggle, just above Generate (it governs what happens
        # after you've generated once). Manual mode only (Knut) — shown/hidden in
        # _switch_mode; Guided has no layout panel to tune live.
        self._auto_preview_row_w = QWidget(self)
        auto_row = QHBoxLayout(self._auto_preview_row_w)
        auto_row.setContentsMargins(0, 0, 0, 0)
        self._auto_preview_check = QCheckBox(
            tr("Auto-update preview when a layout setting changes"), self)
        self._auto_preview_check.setChecked(
            bool(self._settings.get("auto_update_preview", False)))
        self._auto_preview_check.toggled.connect(self._on_auto_preview_toggled)
        # Debounce: coalesce a burst of changes into one re-render.
        self._auto_preview_timer = QTimer(self)
        self._auto_preview_timer.setSingleShot(True)
        self._auto_preview_timer.timeout.connect(self._auto_regenerate_preview)
        self._last_auto_sig: str | None = None
        auto_row.addWidget(self._auto_preview_check)
        auto_row.addStretch()
        auto_row.addWidget(TooltipButton(
            tr("Auto-update preview"),
            tr("When this is on, the chart preview refreshes by itself every time "
               "you change a layout setting — margins, patch size, columns, "
               "spacers, the clip border, and so on — so you can see the effect "
               "immediately without clicking Generate Chart each time.\n\n"
               "How it works:\n"
               "• It only starts once you've generated (or loaded) a chart, so "
               "there's always something to update.\n"
               "• It re-uses the patches already in your chart and just re-lays "
               "them out, so the refresh is quick — it does NOT pick new colours "
               "or re-run the patch generator.\n"
               "• While it's on, ChromIQ won't pop up the “there's a little room "
               "left on the last page” reminder after each change — that would be "
               "in the way when you're tuning the layout live. You can still open "
               "the patch-set editor any time to add or remove patches.\n\n"
               "Turn it off to go back to updating the preview only when you click "
               "Generate Chart."), self))
        left_layout.addWidget(self._auto_preview_row_w)
        self._auto_preview_row_w.setVisible(False)   # Manual only (set in _switch_mode)

        # Bottom buttons
        btn_row = QHBoxLayout()
        self._generate_btn = QPushButton(tr("Generate Chart"), self)
        self._generate_btn.setObjectName("primary")
        self._generate_btn.setFixedHeight(36)
        self._generate_btn.clicked.connect(self._on_generate)

        self._save_defaults_btn = QPushButton(tr("Save as Defaults"), self)
        self._save_defaults_btn.setFixedHeight(36)
        self._save_defaults_btn.clicked.connect(self._on_save_defaults)

        btn_row.addWidget(self._generate_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._save_defaults_btn)
        left_layout.addLayout(btn_row)

        # Log output
        from PyQt6.QtWidgets import QPlainTextEdit
        self._log = QPlainTextEdit(self)
        self._log.setObjectName("log")
        self._log.setReadOnly(True)
        # Nine lines of the font this really gets, measured after polish
        # — not 67 pixels, which was six (Knut, beta.125).
        fit_log_height(self._log)
        self._log.setPlaceholderText(tr("Output will appear here…"))
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
        self._preview.set_caption(tr("CHART PREVIEW"))
        right_layout.addWidget(self._preview, stretch=1)

        # Margin inspector — measures the realised page margins of the generated
        # preview and flags ruler/jig threshold violations (Knut). Hidden when
        # the user disables it in Preferences → Margin Thresholds.
        # Page TIFFs + ti2 of the chart currently in the preview (for measuring).
        # Set BEFORE the panel is wired so restoring the saved guide-checkbox
        # state (which can emit guides_toggled) never finds these unset.
        self._margin_tiffs: list[Path] = []
        self._margin_ti2: Path | None = None
        from ui.margin_inspector_panel import MarginInspectorPanel
        from ui.chart_layout_info_panel import ChartLayoutInfoPanel
        self._margin_panel = MarginInspectorPanel(right)
        # Chart layout info (patch count, grid, pages) beside the margin readout
        # so it's no longer buried in the log (Knut, #93).
        self._layout_info_panel = ChartLayoutInfoPanel(right)
        _info_row = QHBoxLayout()
        _info_row.setContentsMargins(0, 0, 0, 0)
        _info_row.setSpacing(8)
        _info_row.addWidget(self._margin_panel, stretch=3)
        _info_row.addWidget(self._layout_info_panel, stretch=2)
        right_layout.addLayout(_info_row)
        self._margin_panel.set_guides_checked(
            bool(self._settings.get("margin_guides_show", False)))
        self._margin_panel.set_measured_guides_checked(
            bool(self._settings.get("margin_measured_guides_show", False)))
        self._margin_panel.set_coords_checked(
            bool(self._settings.get("margin_coords_show", False)))
        self._margin_panel.setVisible(
            bool(self._settings.get("margin_inspector_show", True)))
        self._layout_info_panel.setVisible(
            bool(self._settings.get("layout_info_show", True)))
        # Connect only after the initial state is restored, so building the UI
        # can't trigger a measure pass.
        self._margin_panel.guides_toggled.connect(self._on_margin_guides_toggled)
        self._margin_panel.measured_guides_toggled.connect(
            self._on_margin_measured_guides_toggled)
        self._margin_panel.coords_toggled.connect(self._on_margin_coords_toggled)
        # Restore the coordinate readout state on the preview (dpi = render res).
        if self._margin_panel.coords_enabled():
            self._preview.set_coord_readout(
                True, float(self._settings.get("printtarg_dpi", 300) or 300))
        # Re-measure when the user pages through a multi-page chart so the
        # inspector + guides always describe the page on screen (#83).
        self._preview.page_changed.connect(lambda _i: self._update_margin_inspector())
        self._preview.page_changed.connect(lambda _i: self._update_layout_info())

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        # The preset combo IGNORES its width (long built-in names must not
        # stretch the row), which also removes it from the pane's minimum-size
        # calculation — so a narrow window let the divider slide OVER the
        # left pane's fields (Knut, beta.124). Give the pane a hard floor.
        left.setMinimumWidth(400)
        splitter.setCollapsible(0, False)

        root.addWidget(splitter)

    def _reveal_chart_folder(self) -> None:
        """Open the current chart's run folder (or the working folder before
        any chart exists) in the file manager (Knut)."""
        from core.preset_store import reveal_in_file_manager
        target: Path | None = None
        if self._margin_tiffs:
            target = self._margin_tiffs[0].parent
        elif self._margin_ti2 is not None:
            target = self._margin_ti2.parent
        else:
            custom = str(self._settings.get("custom_output_path", "")).strip()
            target = Path(custom).expanduser() if custom else Path.home() / "ChromIQ"
        reveal_in_file_manager(target)

    def _warn_if_hexagonal_selected(self, *_a) -> None:
        """Heads-up when the user switches the SpectroScan patch shape to
        Hexagonal: the scanner / camera (CHT) features can't use such a chart
        (Knut). Fires only on a real hex selection (not while a preset loads),
        and re-arms once the shape leaves hex so each new pick is flagged."""
        pnl = self._manual_layout_panel
        if pnl is None or pnl.instr is None or pnl.mode is None:
            return
        is_hex = (pnl.instr.currentData() == "SS"
                  and pnl.mode.currentData() == "hex")
        if not is_hex:
            self._hex_warned = False
            return
        if getattr(pnl, "_loading", False) or getattr(self, "_hex_warned", False):
            return
        self._hex_warned = True
        from workflow.hex_support import hex_unsupported_message
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            self, tr("Hexagonal patches — a heads-up"),
            hex_unsupported_message())

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
        folder_grp = QGroupBox(tr("Output"), inner)
        folder_layout = QVBoxLayout(folder_grp)

        name_row = QHBoxLayout()
        _guided_name_lbl = QLabel(tr("Printer profile project name:"), inner)
        name_row.addWidget(_guided_name_lbl)
        self._target_name_edit = self._make_lineedit("", inner)
        # Live-update the guided command preview as the user types.
        self._target_name_edit.textChanged.connect(self._update_patch_count)
        name_row.addWidget(self._target_name_edit, stretch=1)
        name_row.addWidget(TooltipButton(
            tr("Printer profile project name"),
            self._profile_name_tooltip(),
            inner,
            min_width=540,
        ))
        folder_layout.addLayout(name_row)
        # Pin the label to its natural width (matches the manual fixed-width
        # label trick, keeping the two modes' fields aligned).
        _guided_lbl_w = _guided_name_lbl.sizeHint().width()
        _guided_name_lbl.setFixedWidth(_guided_lbl_w)
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
        instr_grp = QGroupBox(tr("Measurement Instrument"), inner)
        instr_layout = QVBoxLayout(instr_grp)
        instr_layout.setSpacing(6)
        row = QHBoxLayout()
        instr_label = QLabel(tr("Instrument:"), inner)
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
            tr("Measurement Instrument"),
            tr("Tells the chart generator which spectrophotometer you will use to read "
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
            "In Guided mode the layout adapts to this choice automatically."),
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
        self._for_rig_label = QLabel(tr("For rig:"), inner)
        self._for_rig_label.setMinimumWidth(instr_label.sizeHint().width())
        dd_row.addWidget(self._for_rig_label)
        self._dd_check = QCheckBox(tr("Double density"), inner)
        self._dd_check.toggled.connect(self._update_patch_count)
        self._dd_check.toggled.connect(self._on_guided_dd_toggled)
        self._dd_tooltip = TooltipButton(
            tr("Double Density (-h)"),
            tr("Doubles the number of patches that fit in each measurement strip when "
            "using a ColorMunki / i1Studio / ColorChecker Studio.\n\n"
            "REQUIRES the physical measuring rig accessory — a clear plastic guide "
            "that mounts the instrument over the chart. Without the rig the device "
            "cannot align to the tighter patch spacing and will misread.\n\n"
            "With the rig you get roughly twice as many patches per page, which "
            "means either a more detailed profile from the same number of sheets, "
            "or the same profile quality on fewer sheets. Recommended for anyone "
            "with the rig — it's a strict upgrade on patch density.\n\n"
            "Has no effect on i1Pro, i1Pro 3 Plus or SpectroScan — the option is "
            "hidden when those are selected."),
            inner,
            min_width=600,
        )
        self._td_check = QCheckBox(tr("Triple density"), inner)
        self._td_check.toggled.connect(self._update_patch_count)
        self._td_check.toggled.connect(self._on_guided_td_toggled)
        self._td_tooltip = TooltipButton(
            tr("Triple Density (i1Pro layout emulation)"),
            tr("ColorMunki + rig only. The chart is generated with the i1Pro strip "
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
            "hidden when those are selected."),
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
        paper_grp = QGroupBox(tr("Paper"), inner)
        paper_layout = QVBoxLayout(paper_grp)
        paper_row = QHBoxLayout()
        paper_row.addWidget(QLabel(tr("Paper size:"), inner))
        self._paper_combo = NoScrollComboBox(inner)
        self._paper_combo.currentIndexChanged.connect(self._update_patch_count)
        # Paper changes also affect ChromIQ-style gating, which decides whether
        # the guided -L checkbox is visible.
        self._paper_combo.currentIndexChanged.connect(self._update_dd_visibility)
        paper_row.addWidget(self._paper_combo, stretch=1)
        paper_row.addWidget(TooltipButton(
            tr("Paper Size"),
            tr("Sets the dimensions of each sheet in the printed chart. The chart "
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
            "and page count update automatically."),
            inner,
            min_width=600,
        ))
        paper_layout.addLayout(paper_row)
        layout.addWidget(paper_grp)

        # Pages + left border
        pages_grp = QGroupBox(tr("Chart Size"), inner)
        pages_layout = QVBoxLayout(pages_grp)
        pages_layout.setSpacing(6)

        pages_row = QHBoxLayout()
        pages_row.addWidget(QLabel(tr("Number of pages:"), inner))
        self._pages_spin = NoScrollSpinBox(inner)
        self._pages_spin.setRange(1, 20)
        self._pages_spin.setValue(1)
        self._pages_spin.valueChanged.connect(self._update_patch_count)
        pages_row.addWidget(self._pages_spin)
        pages_row.addStretch()
        pages_row.addWidget(TooltipButton(
            tr("Number of Pages"),
            tr("How many physical sheets the chart spans. Each sheet is filled with "
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
            "better."),
            inner,
            min_width=600,
        ))
        pages_layout.addLayout(pages_row)

        lb_row = QHBoxLayout()
        self._lb_check = QCheckBox(tr("Suppress left clip border (-L)"), inner)
        self._lb_check.setChecked(True)
        self._lb_check.toggled.connect(self._update_patch_count)
        self._lb_tooltip = TooltipButton(
            tr("Suppress Left Clip Border (-L)"),
            tr("Removes the left-edge paper-clip border, gaining ~15 mm for extra patches.\n"
            "Enable unless you use a physical page-clamp jig.  Recommended: ON."),
            inner,
        )
        self._nsl_check = QCheckBox(tr("Don't limit strip length (-P)"), inner)
        self._nsl_check.toggled.connect(self._update_patch_count)
        self._nsl_tooltip = TooltipButton(
            tr("Don't Limit Strip Length (-P)"),
            tr("Removes printtarg's built-in strip-length cap (~250 mm) so each "
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
            "effect on either layout."),
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
        precond_grp = QGroupBox(tr("Refinement (Optional)"), inner)
        precond_row = QHBoxLayout(precond_grp)
        precond_row.setSpacing(6)

        self._guided_precond_check = QCheckBox(tr("Refinement profile"), inner)
        self._guided_precond_check.toggled.connect(self._on_guided_precond_toggled)
        precond_row.addWidget(self._guided_precond_check)

        self._guided_precond_path = QLineEdit(inner)
        self._guided_precond_path.setReadOnly(True)
        self._guided_precond_path.setPlaceholderText(tr("No profile selected"))
        self._guided_precond_path.setEnabled(False)
        precond_row.addWidget(self._guided_precond_path, stretch=1)

        self._guided_precond_browse = make_browse_button(
            inner, tr("Select pre-conditioning profile"), icon="folder_create",
        )
        self._guided_precond_browse.setEnabled(False)
        self._guided_precond_browse.clicked.connect(self._on_guided_precond_browse)
        precond_row.addWidget(self._guided_precond_browse)

        precond_row.addWidget(TooltipButton(
            tr("Refinement Profile (Pre-conditioning)"),
            tr("Use this to make a second, noticeably better profile after you have "
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
            "the cleverer patch placement gives you."),
            inner,
            min_width=580,
        ))

        layout.addWidget(precond_grp)

        # Patch count display
        count_grp = QGroupBox(tr("Calculated Patches"), inner)
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
        self._cal_target_grp = QGroupBox(tr("Calibration Chart"), w)
        cal_tgt_layout = QVBoxLayout(self._cal_target_grp)
        cal_tgt_row = QHBoxLayout()
        self._cal_target_check = QCheckBox(tr("Create chart for calibration"), w)
        cal_tgt_row.addWidget(self._cal_target_check)
        cal_tgt_row.addStretch()
        cal_tgt_row.addWidget(TooltipButton(
            tr("Create Chart for Calibration"),
            tr("Use this before running printcal to create a printer linearisation curve.\n\n"
            "When enabled:\n"
            "  • Output files are prefixed with 'cal_' (e.g. cal_MyChart.ti1)\n"
            "  • Patch count is set to 0 (auto), white and black patches set to 0\n"
            "  • Single channel steps set to 20, randomisation disabled\n"
            "  • Good distribution (-G) is disabled\n\n"
            "Generate the chart, print it, and measure it. The resulting cal_*.ti3\n"
            "file is automatically routed to the Create Calibration File module\n"
            "in the Calibration & Profiling tab.\n\n"
            "Existing cal_* files in your working folder are preserved when this\n"
            "option is OFF, so your .cal file survives the next chart generation."),
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
        output_grp = QGroupBox(tr("Output"), w)
        output_layout = QVBoxLayout(output_grp)
        # Shared label width keeps the "Target name:" and "Chart notes:"
        # input fields aligned vertically. Sized to the translated labels so
        # longer locales widen the column (the stretchy edits absorb it).
        name_row = QHBoxLayout()
        _name_lbl = QLabel(tr("Printer profile project name:"), w)
        # Label column = the wider label's full sizeHint (the same measure guided
        # uses) — its natural width incl. margins, so the column matches guided's
        # left edge without clipping the label's trailing ":".
        _notes_probe = QLabel(tr("Chart notes:"))   # no parent → measure only
        _OUTPUT_LBL_W = max(_name_lbl.sizeHint().width(),
                            _notes_probe.sizeHint().width())
        _name_lbl.setFixedWidth(_OUTPUT_LBL_W)
        name_row.addWidget(_name_lbl)
        self._manual_target_name_edit = self._make_lineedit("", w)
        # Live-update the manual command preview as the user types.
        self._manual_target_name_edit.textChanged.connect(
            self._refresh_manual_command_preview
        )
        name_row.addWidget(self._manual_target_name_edit, stretch=1)
        name_row.addWidget(TooltipButton(
            tr("Printer profile project name"),
            self._profile_name_tooltip(),
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
        _notes_lbl = QLabel(tr("Chart notes:"), self._manual_chart_notes_row)
        _notes_lbl.setFixedWidth(_OUTPUT_LBL_W)
        m_notes_row.addWidget(_notes_lbl)
        self._manual_chart_notes_edit = self._make_lineedit("", self._manual_chart_notes_row)
        self._manual_chart_notes_edit.setPlaceholderText(tr("e.g. Canon Pro-1000 / Hahnemühle Photo Rag 308"))
        m_notes_row.addWidget(self._manual_chart_notes_edit, stretch=1)
        m_notes_row.addWidget(TooltipButton(
            tr("Chart Notes"),
            tr("Optional free-text label stamped onto the right edge of the chart "
            "TIFFs alongside the targen and printtarg commands that produced them. "
            "Useful for recording the exact printer/paper combination this chart "
            "was made for, so you can match it to the right ICC profile months "
            "later. Patch pixels are not modified — only the white margin to the "
            "right of the patches is stamped."),
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
            tr("Stamp targen and printtarg commands on the chart"), self._manual_stamp_cmd_row
        )
        self._manual_stamp_cmd_check.setChecked(True)
        stamp_row.addWidget(self._manual_stamp_cmd_check)
        stamp_row.addStretch()
        stamp_row.addWidget(TooltipButton(
            tr("Stamp Commands"),
            tr("When enabled, the exact targen and printtarg commands used to "
            "produce the chart — plus the ChromIQ version — are stamped onto "
            "the right edge of the generated TIFF (alongside Argyll's own "
            "vertical ID line). This makes the chart self-documenting: months "
            "later you can read the printed sheet and recreate the same chart "
            "exactly. Disable if you'd rather keep the right margin clean and "
            "only stamp your own notes (or leave the chart fully unstamped if "
            "you also clear the notes field)."),
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
            tr("Print info in left clip area"), self._manual_left_clip_row
        )
        left_clip_row.addWidget(self._manual_left_clip_check)
        left_clip_row.addStretch()
        left_clip_row.addWidget(TooltipButton(
            tr("Left Clip Info"),
            tr("Fills the wide blank strip on the LEFT side of the chart — the "
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
            "clip strip is stamped."),
            self._manual_left_clip_row,
            min_width=560,
        ))
        output_layout.addWidget(self._manual_left_clip_row)
        self._manual_left_clip_row.setVisible(False)

        layout.addWidget(output_grp)

        # Presets
        presets_grp = QGroupBox(tr("Presets"), w)
        presets_row = QHBoxLayout(presets_grp)
        presets_row.setContentsMargins(8, 4, 8, 8)
        presets_row.addWidget(QLabel(tr("Select preset:"), w))
        self._preset_combo = _CappedComboBox(w)
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
        # The popup is capped + scrolled by _CappedComboBox.showPopup (macOS
        # ignores maxVisibleItems for this styled compound combo); keep
        # maxVisibleItems too for platforms that do honour it.
        self._preset_combo.setMaxVisibleItems(20)
        self._preset_combo.addItem(tr("none"), userData=None)
        presets_row.addWidget(self._preset_combo, stretch=1)
        self._preset_add_btn = QPushButton(w)
        self._preset_add_btn.setObjectName("icon_btn")
        self._preset_add_btn.setFixedSize(28, 28)
        set_preset_icon(self._preset_add_btn, "plus")
        self._preset_add_btn.setIconSize(QSize(14, 14))
        self._preset_add_btn.setToolTip(tr("Save current settings as a new preset"))
        self._preset_del_btn = QPushButton(w)
        self._preset_del_btn.setObjectName("icon_btn")
        self._preset_del_btn.setFixedSize(28, 28)
        set_preset_icon(self._preset_del_btn, "minus")
        self._preset_del_btn.setIconSize(QSize(14, 14))
        self._preset_del_btn.setToolTip(tr("Delete selected preset"))
        self._preset_del_btn.setEnabled(False)
        self._preset_reveal_btn = QPushButton(w)
        self._preset_reveal_btn.setObjectName("icon_btn")
        self._preset_reveal_btn.setFixedSize(28, 28)
        set_folder_icon(self._preset_reveal_btn, "folder_create")
        self._preset_reveal_btn.setIconSize(QSize(14, 14))
        self._preset_reveal_btn.setToolTip(
            tr("Open this tab's presets folder in {manager}.\n"
            "Each preset is a plain .json file — copy one to a colleague\n"
            "and they can drop it into their own folder to share.").format(manager=file_manager_name())
        )
        self._preset_reveal_btn.clicked.connect(
            lambda: reveal_in_file_manager(tab_dir("create_chart"))
        )
        presets_row.addWidget(self._preset_add_btn)
        presets_row.addWidget(self._preset_del_btn)
        presets_row.addWidget(self._preset_reveal_btn)
        presets_row.addWidget(TooltipButton(
            tr("Manual Presets"),
            tr("Save and recall named snapshots of all Manual mode settings.\n\n"
            "  +  Save current parameter values as a new named preset.\n"
            "  −  Delete the currently selected preset.\n"
            "  ▢  Open this tab's presets folder in {manager}.\n\n"
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
            "Presets persist between sessions.").format(manager=file_manager_name()),
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

        # Engine toggle lives HERE now (moved out of Settings, Knut #93): above the
        # targen/printtarg groups so switching engines per chart/preset is easy. It
        # decides whether the layout below is the printtarg controls or the ChromIQ
        # layout panel. Created ONCE, before the per-tool loop — building it inside
        # the loop added it twice (once per tool), so the toggle appeared above both
        # targen and printtarg.
        _eng_row = QHBoxLayout()
        self._manual_engine_check = QCheckBox(
            tr("Use the ChromIQ layout engine instead of printtarg"), inner)
        self._manual_engine_check.setChecked(
            bool(self._settings.get("use_chromiq_layout_engine", False)))
        self._manual_engine_check.toggled.connect(self._on_manual_engine_toggled)
        _eng_row.addWidget(self._manual_engine_check)
        _eng_row.addStretch()
        _eng_row.addWidget(TooltipButton(
            tr("ChromIQ layout engine"),
            tr("When ON, ChromIQ builds your test charts itself instead of "
               "calling ArgyllCMS printtarg. The engine packs the colour "
               "patches more efficiently, can put useful information where "
               "printtarg leaves blank space, and lets you fully customise the "
               "layout below per instrument and paper.\n\n"
               "When OFF the chart is made by printtarg exactly as before. This "
               "switch only affects how charts are CREATED; printing and "
               "measuring existing charts always work the same way, so it is "
               "safe to switch back at any time.\n\n"
               "─────────────────────────────────\n"
               "What each one gives you\n"
               "─────────────────────────────────\n\n"
               "Only with the ChromIQ engine:\n"
               "  • more patches on every sheet\n"
               "  • you choose the patch size\n"
               "  • you choose each margin separately\n"
               "  • the instrument's own margins are enforced\n"
               "  • spacer size and colour are yours to set\n"
               "  • notes and a record area printed on the sheet\n"
               "  • a clip border to cut along\n"
               "  • multi-ink (CMY+N) charts\n"
               "  • the layout is saved with the chart and can be reopened\n"
               "  • the live patch preview while measuring\n"
               "  • scanner-target geometry\n"
               "  • reading-pace guidance (with the reading engine too)\n\n"
               "The same either way:\n"
               "  • the chart is read and profiled identically\n"
               "  • every ArgyllCMS tool accepts it unchanged\n\n"
               "Both produce a chart ArgyllCMS reads and profiles in exactly "
               "the same way — the difference is what the sheet looks like and "
               "how much you can decide about it."), inner))
        _eng_w = QWidget(inner)
        _eng_w.setLayout(_eng_row)
        # Added to the layout inside the loop, just above the printtarg group (the
        # engine REPLACES printtarg, so the toggle reads right there) (Knut).

        for tool, params in [
            ("targen",    self._params.get("targen", [])),
            ("printtarg", self._params.get("printtarg", [])),
        ]:
            # Outer section frame is collapsible (Knut). targen starts collapsed
            # (most charts don't touch the patch recipe); printtarg starts open.
            grp = CollapsibleGroupBox(
                tr("{tool} parameters").format(tool=tool), inner,
                collapsed=(tool == "targen"))
            # Keep a handle to the outer group (its inner content is greyed via
            # _manual_*_content while a preset locks the panel).
            if tool == "targen":
                self._manual_targen_grp = grp
            else:
                self._manual_printtarg_grp = grp
            grp_layout = QVBoxLayout(grp.body)

            # Override row — pinned ABOVE the (collapsible) section frame so it
            # stays visible even when the frame is collapsed (Knut). Hidden until a
            # preset that supplies a fixed patch set (ti1) or a fixed layout
            # (prebuilt) is active. Ticking it re-enables the greyed controls and
            # expands the targen frame.
            override_row = QWidget(inner)
            override_l = QHBoxLayout(override_row)
            override_l.setContentsMargins(0, 0, 0, 2)
            if tool == "targen":
                ov_check = QCheckBox(tr("Edit patch recipe (override preset)"), override_row)
                ov_tip = TooltipButton(tr("Edit patch recipe"), tr(_OVERRIDE_TARGEN_TIP),
                                       override_row, min_width=600)
                self._override_targen_check = ov_check
                self._override_targen_row = override_row
            else:
                ov_check = QCheckBox(tr("Edit page layout (override preset)"), override_row)
                ov_tip = TooltipButton(tr("Edit page layout"), tr(_OVERRIDE_PRINTTARG_TIP),
                                       override_row, min_width=600)
                self._override_printtarg_check = ov_check
                self._override_printtarg_row = override_row
            override_l.addWidget(ov_check)
            override_l.addStretch()
            override_l.addWidget(ov_tip)
            override_row.setVisible(False)   # added to inner_layout below the loop
            ov_check.toggled.connect(self._update_preset_locks)
            ov_check.toggled.connect(self._refresh_manual_command_preview)
            ov_check.clicked.connect(
                lambda checked, t=tool: self._on_override_clicked(t, checked)
            )

            # Collapsible sections (Knut): click the title to fold a frame away.
            # Expert is collapsed by default; the targen Basic frame starts
            # collapsed and auto-expands when "Edit patch recipe" is ticked
            # (wired in _update_preset_locks), so a locked recipe stays tidy.
            basic_grp = CollapsibleGroupBox(tr("Basic"), grp)
            basic_layout = QVBoxLayout(basic_grp.body)
            expert_grp = CollapsibleGroupBox(tr("Expert Options"), grp,
                                             collapsed=True)
            expert_layout = QVBoxLayout(expert_grp.body)
            # Content widgets greyed out (not the override row) while locked.
            if tool == "targen":
                self._manual_targen_content = [basic_grp, expert_grp]
                self._manual_targen_basic_grp = basic_grp
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
                    self._bit8_radio = QRadioButton(tr("8-bit"), pw)
                    self._bit16_radio = QRadioButton(tr("16-bit"), pw)
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
                    self._manual_auto_patches_check = QCheckBox(tr("Auto"), pw)
                    self._manual_auto_patches_check.setToolTip(
                        tr("Auto-compute the patch count to fill exactly the number of\n"
                        "pages set under printtarg → Pages, using the current paper,\n"
                        "instrument, double-density, left-border, patch scale and margin.")
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
                    self._manual_auto_white_check = QCheckBox(tr("Auto"), pw)
                    self._manual_auto_white_check.setToolTip(
                        tr("Auto-compute white patches (-e) from the chart's total\n"
                        "patch count. Anchor: 560 patches → 4 whites. Doubling the\n"
                        "total adds 50 % to the count, capped at 8 (min 2).")
                    )
                    insert_at = pw.layout().count() - 1
                    pw.layout().insertWidget(insert_at, self._manual_auto_white_check)
                    self._manual_auto_white_check.toggled.connect(
                        lambda v: self._on_auto_neutral_toggled("white", v)
                    )

                if tool == "targen" and flag == "-B":
                    self._manual_B_pw = pw
                    pw._control.setMaximumWidth(90)
                    self._manual_auto_black_check = QCheckBox(tr("Auto"), pw)
                    self._manual_auto_black_check.setToolTip(
                        tr("Auto-compute black patches (-B) from the chart's total\n"
                        "patch count. Anchor: 560 patches → 4 blacks. Doubling the\n"
                        "total adds 50 % to the count, capped at 8 (min 2).")
                    )
                    insert_at = pw.layout().count() - 1
                    pw.layout().insertWidget(insert_at, self._manual_auto_black_check)
                    self._manual_auto_black_check.toggled.connect(
                        lambda v: self._on_auto_neutral_toggled("black", v)
                    )

                if tool == "targen" and flag == "-g":
                    self._manual_g_pw = pw
                    pw._control.setMaximumWidth(90)
                    self._manual_auto_grey_check = QCheckBox(tr("Auto"), pw)
                    self._manual_auto_grey_check.setToolTip(
                        tr("Auto-compute grey-axis steps (-g) from the chart's total\n"
                        "patch count. Anchor: 560 patches → 32 steps. Doubling the\n"
                        "total doubles the steps, capped at 128 (min 8).")
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
                pages_lbl = QLabel(tr("Pages:"), pages_row_w)
                pages_lbl.setFixedWidth(190)
                # param_label carries the right per-theme colour AND a :disabled
                # rule, so it greys when a preset locks the printtarg panel.
                pages_lbl.setObjectName("param_label")
                self._manual_pages_lbl = pages_lbl
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
                    tr("Pages (Auto patch count)"),
                    tr("How many physical sheets the chart should span. This control "
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
                    "Patch Count requires."),
                    pages_row_w,
                    min_width=600,
                ))
                idx = basic_layout.indexOf(self._manual_paper_pw)
                basic_layout.insertWidget(idx + 1 if idx >= 0 else basic_layout.count(),
                                          pages_row_w)
                self._manual_pages_row = pages_row_w

            grp_layout.addWidget(basic_grp)
            grp_layout.addWidget(expert_grp)
            if tool == "printtarg":
                inner_layout.addWidget(_eng_w)   # engine toggle above printtarg
            inner_layout.addWidget(override_row)  # override box above its frame
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

        # ChromIQ layout panel (engine on): the full per-chart layout mirror,
        # replacing the printtarg controls. Hidden when the engine is off.
        from ui.dialogs.layout_options_panel import LayoutOptionsPanel
        self._manual_layout_grp = CollapsibleGroupBox(tr("ChromIQ layout"), inner)
        _llg = QVBoxLayout(self._manual_layout_grp.body)
        _llg.setContentsMargins(8, 8, 8, 8)
        self._manual_layout_panel = LayoutOptionsPanel(
            self._manual_layout_grp, with_selectors=True, with_calibration=True)
        # Let the panel's "Use instrument margins" checkbox read the user's
        # Instrument-Margins thresholds for the current combo (#93, Knut).
        self._manual_layout_panel.set_threshold_lookup(self._combo_thresholds)
        # Warn once when the user picks SpectroScan hexagonal patches — the CHT
        # scanner/camera features can't handle that chart (Knut).
        if self._manual_layout_panel.mode is not None:
            self._manual_layout_panel.mode.currentIndexChanged.connect(
                self._warn_if_hexagonal_selected)
        # Keep the engine panel's instrument/paper and the canonical Manual
        # selection (printtarg -i/-p) in step, so loading a preset then enabling
        # the engine carries Instrument/Paper across and the threshold lookup +
        # Preferences preselect use the right combo (#93, Knut beta-13).
        if self._manual_layout_panel.instr is not None:
            self._manual_layout_panel.instr.currentIndexChanged.connect(
                self._sync_manual_selection_from_panel)
        if self._manual_layout_panel.paper is not None:
            self._manual_layout_panel.paper.currentIndexChanged.connect(
                self._sync_manual_selection_from_panel)
        self._manual_layout_panel.changed.connect(self._refresh_manual_command_preview)
        _llg.addWidget(self._manual_layout_panel)
        inner_layout.addWidget(self._manual_layout_grp)
        self._manual_layout_grp.setVisible(False)
        self._manual_panel_inited = False
        self._syncing_manual_sel = False
        # Treat the engine's start-of-session state as "already settled" so the
        # first preview render isn't seen as an off→on toggle (which would pull
        # the printtarg default over a restored saved recipe at startup) (#93).
        self._engine_was_active = bool(
            self._settings.get("use_chromiq_layout_engine", False))

        # Layout-engine preset bar (issue #93): shown only when the ChromIQ
        # layout engine is active. Summarises the active preset (instrument ×
        # paper × mode), flags when the current settings differ from it, and
        # lets the user reset to / update that preset, or edit the defaults.
        self._manual_preset_bar = QWidget(inner)
        _pbar = QHBoxLayout(self._manual_preset_bar)
        _pbar.setContentsMargins(0, 0, 0, 0)
        _pbar.setSpacing(6)
        self._manual_preset_reset_btn = QPushButton(
            tr("Reset to preset"), self._manual_preset_bar)
        self._manual_preset_reset_btn.clicked.connect(self._reset_manual_to_preset)
        self._manual_preset_update_btn = QPushButton(
            tr("Update preset"), self._manual_preset_bar)
        self._manual_preset_update_btn.clicked.connect(self._update_manual_preset)
        self._manual_preset_edit_btn = QPushButton(
            tr("Edit defaults…"), self._manual_preset_bar)
        self._manual_preset_edit_btn.clicked.connect(self._edit_layout_defaults)
        # Buttons fill the panel width equally (full labels fit) with reduced
        # height. A stylesheet sets the height because a global QSS min-height
        # overrides setFixedHeight/setMinimumHeight (see Qt-button-sizing note).
        for _b in (self._manual_preset_reset_btn, self._manual_preset_update_btn,
                   self._manual_preset_edit_btn):
            _b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            _b.setStyleSheet("QPushButton { min-height: 16px; padding: 3px 10px; }")
            _pbar.addWidget(_b, 1)
        inner_layout.addWidget(self._manual_preset_bar)
        self._manual_preset_bar.setVisible(False)

        # Live command preview — mirrors the guided info box but reflects the
        # actual targen / printtarg args the workflow will build from the
        # current ParameterWidget state.  Sits at the bottom of the scrollable
        # area so it follows the last parameter group.
        self._manual_info_lbl = QLabel("", inner)
        self._manual_info_lbl.setObjectName("info")
        self._manual_info_lbl.setWordWrap(True)
        # The command preview is meant to be copied (e.g. into a bug report), so
        # make it text-selectable (#58).
        self._manual_info_lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
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

    def _on_manual_engine_toggled(self, on: bool) -> None:
        """The engine toggle moved from Settings to Create Chart (Knut #93).
        Persist the choice, keep the engine and the old printtarg ChromIQ
        clip-border mutually exclusive (the engine replaces the printtarg path),
        and refresh the manual UI so the right frame shows."""
        was_on = bool(self._settings.get("use_chromiq_layout_engine", False))
        self._settings.set("use_chromiq_layout_engine", bool(on))
        if on:
            # Remember + clear the old ChromIQ clip-border so use_engine doesn't
            # silently collapse back to the printtarg path (chart_creator).
            if self._settings.get("i1pro_chromiq_clip_style", False):
                self._engine_clip_saved = True
                self._settings.set("i1pro_chromiq_clip_style", False)
            # Same for the legacy printtarg-only "Print info in left clip area":
            # left over checked, it forces use_engine False and silently flips the
            # frame back to printtarg while the engine toggle still reads ON (Knut).
            chk = getattr(self, "_manual_left_clip_check", None)
            if chk is not None and chk.isChecked():
                self._engine_leftclip_saved = True
                chk.setChecked(False)
        else:
            if getattr(self, "_engine_clip_saved", False):
                self._settings.set("i1pro_chromiq_clip_style", True)
                self._engine_clip_saved = False
            if getattr(self, "_engine_leftclip_saved", False):
                chk = getattr(self, "_manual_left_clip_check", None)
                if chk is not None:
                    chk.setChecked(True)
                self._engine_leftclip_saved = False
        # Convert the shared layout settings across the toggle so the layout you
        # dialled in on one side isn't lost on the other (Knut #3). Only the
        # convertible fields move (instrument, paper, margins, patch scale, clip
        # border, density, strip-limit); engine-only / printtarg-only options stay
        # on their own side.
        if on and not was_on:
            self._convert_printtarg_to_engine()
        elif was_on and not on:
            self._convert_engine_to_printtarg()
        # Re-evaluate the left-clip row: it must hide while the engine is on and
        # reappear (with the user's restored choice) when it goes off.
        self._update_manual_lb_visibility()
        self._refresh_manual_command_preview()

    def _convert_printtarg_to_engine(self) -> None:
        """Engine OFF→ON: seed the engine layout panel from the printtarg widgets
        the user had set, overriding the convertible fields and keeping the
        panel's engine-only options (layout mode, columns, clip content…) (Knut
        #3). The full field map is documented in _convert_engine_to_printtarg."""
        panel = getattr(self, "_manual_layout_panel", None)
        if panel is None:
            return
        if not self._manual_panel_inited:
            self._init_manual_layout_panel()
        try:
            from dataclasses import replace
            g = lambda f, d: self._manual_get("printtarg", f, d)
            cur = panel.get_recipe()
            instr = str(g("-i", "i1"))
            suppress = bool(g("-L", True))           # -L = no left/clip border
            dd = bool(g("-h", False))
            td = (self._manual_td_check is not None
                  and self._manual_td_check.isChecked() and instr == "CM")
            # Spacers: -n (none) wins, then -b (B&W), then -c / default (coloured).
            spacer_mode = ("none" if bool(g("-n", False))
                           else "bw" if bool(g("-b", False))
                           else "colored")
            preserve = bool(g("-r", False))          # -r = preserve order
            # Only carry the seed as a FIXED seed when the user actually enabled
            # the -R row (printtarg always has an internal default, but the engine
            # "no fixed seed" state must survive a round-trip).
            has_seed = self._manual_enabled("printtarg", "-R")
            seed_val = int(g("-R", 1) or 1)
            bit16 = bool(self._bit16_radio is not None
                         and self._bit16_radio.isChecked())
            disable_comp = bool(g("-C", False))      # -C = no TIFF compression

            # Margins: printtarg carries ONE value, the engine has four. Only
            # collapse to all-four when the user actually changed printtarg's
            # margin since the last switch — otherwise keep the engine's own
            # (possibly distinct) four so toggling back and forth never loses them
            # (Knut: don't transfer the non-1:1 field when it would clobber).
            cur_m = float(g("-m", 6) or 6)
            snap_m = getattr(self, "_pt_margin_at_switch", None)
            if snap_m is not None and int(round(cur_m)) == int(snap_m):
                margins = dict(
                    margin_top=cur.margin_top, margin_right=cur.margin_right,
                    margin_bottom=cur.margin_bottom, margin_left=cur.margin_left,
                    border=cur.border,
                    use_instrument_margins=cur.use_instrument_margins)
            else:
                margins = dict(
                    margin_top=cur_m, margin_right=cur_m, margin_bottom=cur_m,
                    margin_left=cur_m, border=cur_m, use_instrument_margins=False)

            recipe = replace(
                cur,
                instrument=instr, paper=str(g("-p", "A4")),
                dpi=int(g("-t", 300) or 300),
                pscale=float(g("-a", 1.0) or 1.0),
                nolimit=bool(g("-P", False)),
                cm_density=(3 if td else 2 if dd else 1),
                spacer_mode=spacer_mode, spacer_on=(spacer_mode != "none"),
                randomize=(not preserve),
                seed=(seed_val if (has_seed and not preserve) else None),
                bit16=bit16,
                compression=("none" if disable_comp else "lzw"),
                clip_border=((not suppress) if instr in ("i1", "p3")
                             else cur.clip_border),
                clip_content_mode=(("off" if suppress else "notes")
                                   if instr in ("i1", "p3")
                                   else cur.clip_content_mode),
                **margins,
            )
            panel.set_recipe(recipe)
            if (getattr(panel, "pages", None) is not None
                    and self._manual_pages_spin is not None):
                panel.pages.setValue(int(self._manual_pages_spin.value()))
        except Exception:  # noqa: BLE001 — never block the toggle
            log.warning("printtarg→engine conversion failed", exc_info=True)

    def _convert_engine_to_printtarg(self) -> None:
        """Engine ON→OFF: write the engine panel's settings back onto the
        printtarg widgets so the layout survives the toggle (Knut #3). Field map
        (both directions, inverse where noted):
          -i ↔ Instrument        -p ↔ Paper            pages ↔ Pages
          -t ↔ Resolution        -a ↔ Patch scale      -P ↔ Don't-limit-strip
          -L ↔ Clip border (inv, i1/p3)   -r ↔ Randomise (inv)
          -R ↔ fixed Seed        -C ↔ Compression (-C on ⇔ "none")
          -n/-b/-c ↔ Spacers (none/bw/coloured)        bit radios ↔ Bit depth
          -h + triple-density ↔ Density (1/2/3)
          -m ↔ Margins (only when all four are equal — see below)."""
        panel = getattr(self, "_manual_layout_panel", None)
        if panel is None:
            return
        try:
            r = panel.get_recipe()
            # Instrument + paper first (changing -i cascades the instrument
            # defaults for -a/-m, so set those afterwards).
            self._set_manual_value("printtarg", "-i", r.instrument)
            self._set_manual_value("printtarg", "-p", r.paper)
            self._set_manual_value("printtarg", "-t", int(r.dpi))
            self._set_manual_value("printtarg", "-a", round(float(r.pscale), 3))
            self._set_manual_value("printtarg", "-P", bool(r.nolimit))
            self._set_manual_value("printtarg", "-h", bool(r.cm_density == 2))
            # Spacers (mutually exclusive flags).
            self._set_manual_value("printtarg", "-n", r.spacer_mode == "none")
            self._set_manual_value("printtarg", "-b", r.spacer_mode == "bw")
            self._set_manual_value("printtarg", "-c", r.spacer_mode == "colored")
            # Randomise / fixed seed.
            self._set_manual_value("printtarg", "-r", not r.randomize)
            if r.seed is not None:
                self._set_manual_value("printtarg", "-R", int(r.seed))
            # TIFF compression (-C disables it → engine "none").
            self._set_manual_value("printtarg", "-C", r.compression == "none")
            # Bit depth (the 8/16-bit radios live on the printtarg row).
            if self._bit16_radio is not None and self._bit8_radio is not None:
                (self._bit16_radio if r.bit16
                 else self._bit8_radio).setChecked(True)
            self._set_manual_value(
                "printtarg", "-L",
                bool(r.instrument in ("i1", "p3") and not r.clip_border))
            if self._manual_td_check is not None:
                self._manual_td_check.setChecked(
                    r.instrument == "CM" and r.cm_density == 3)
            # Margins: only collapse the four engine margins onto printtarg's
            # single -m when they're all equal (lossless). When they differ,
            # leave printtarg's margin untouched so the distinct values survive a
            # round-trip (restored on the way back). Record what we left -m at so
            # the reverse conversion can tell whether the user changed it.
            ms = (r.margin_top, r.margin_right, r.margin_bottom, r.margin_left)
            if max(ms) - min(ms) < 0.5:
                self._set_manual_value("printtarg", "-m", int(round(r.margin_top)))
            self._pt_margin_at_switch = int(self._manual_get("printtarg", "-m", 6) or 6)
            if (self._manual_pages_spin is not None
                    and getattr(panel, "pages", None) is not None):
                self._manual_pages_spin.setValue(int(panel.pages.value()))
        except Exception:  # noqa: BLE001 — never block the toggle
            log.warning("engine→printtarg conversion failed", exc_info=True)

    def _refresh_manual_command_preview(self) -> None:
        """Rebuild the manual info label from the current ParameterWidget state.

        Mirrors workflow/chart_creator.py:_build_targen_args /
        _build_printtarg_args so the preview matches exactly what runs."""
        # Keep the Create-Chart engine checkbox in step with the setting (a preset
        # load or engine switch can change it elsewhere) without re-firing toggled.
        chk = getattr(self, "_manual_engine_check", None)
        if chk is not None:
            want = bool(self._settings.get("use_chromiq_layout_engine", False))
            if chk.isChecked() != want:
                chk.blockSignals(True)
                chk.setChecked(want)
                chk.blockSignals(False)
        # Any manual layout/recipe change routes through here, so this is the
        # single hook for the live preview refresh (Knut, opt-in; guarded by a
        # layout-signature check so it only fires on a real change).
        self._maybe_schedule_auto_preview()
        if getattr(self, "_manual_info_lbl", None) is None:
            return
        try:
            p = self._collect_manual()
        except Exception:
            self._manual_info_lbl.setText(tr("Manual mode — preview unavailable."))
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

        # When the ChromIQ layout engine is active it replaces printtarg for the
        # generate path, so the preview shows what the engine will build.
        from workflow.chart_creator import ENGINE_INSTRUMENTS
        use_engine = (
            bool(self._settings.get("use_chromiq_layout_engine", False))
            and p.instrument in ENGINE_INSTRUMENTS
            and not (p.chromiq_clip_style or p.left_clip_info))

        def _layout_cmd() -> str:
            if use_engine:
                # The engine recipe panel — not the printtarg widgets — is the
                # source of truth in Manual mode, so summarise the recipe (#93).
                if getattr(self, "_manual_layout_panel", None) is not None:
                    try:
                        return self._engine_info_line_from_recipe(
                            self._current_layout_recipe())
                    except Exception:
                        pass
                return self._engine_info_line(
                    p.instrument, p.paper, p.tiff_dpi, dd=p.double_density,
                    td=triple, eff_lb=(p.disable_left_border or force_l),
                    nsl=p.no_strip_limit, pscale=p.patch_scale, margin=p.margin_mm)
            return f"printtarg {' '.join(pt_args)}"

        pages = (
            self._manual_pages_spin.value()
            if self._manual_pages_spin is not None else 1
        )
        notes = [tr("1 page") if pages == 1 else tr("{pages} pages").format(pages=pages)]
        if self._manual_auto_patches_check is not None \
                and self._manual_auto_patches_check.isChecked():
            notes.append(tr("Auto patch count"))
        auto_neutrals = [
            lbl for lbl, chk in (
                (tr("grey"),  self._manual_auto_grey_check),
                (tr("white"), self._manual_auto_white_check),
                (tr("black"), self._manual_auto_black_check),
            ) if chk is not None and chk.isChecked()
        ]
        if auto_neutrals:
            notes.append(tr("Auto") + " " + "/".join(auto_neutrals))
        if p.tiff_16bit:
            notes.append(tr("16-bit TIFF"))

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
                    tr("Built-in preset — patch recipe changed ({notes}):\n"
                       "Builds a fresh chart from your settings — the patches "
                       "will NOT match the preset.").format(notes=" · ".join(notes))
                    + f"\ntargen {' '.join(targen_args)}"
                    + f"\n{_layout_cmd()}"
                )
            elif printtarg_changed:
                info = (
                    tr("Built-in preset — re-laid out ({notes}):\n"
                       "Re-arranges the preset's exact patches on the page "
                       "(targen skipped).").format(notes=" · ".join(notes))
                    + f"\nprinttarg {' '.join(pt_args)}"
                )
            else:
                info = tr(
                    "Built-in preset — ready-made chart:\n"
                    "Copies the bundled patch set as-is (targen and printtarg "
                    "skipped).\n"
                    "Unlock \"Edit page layout\" to re-arrange the same patches, "
                    "or \"Edit patch recipe\" to build a different chart."
                )
            # Fall through to the shared visibility/label tail below — an early
            # return here (the old behaviour) skipped the engine↔printtarg panel
            # swap, so enabling the ChromIQ layout engine on a prebuilt preset
            # (e.g. TC9.18 by Pharmacist) left only the printtarg layout showing
            # and the engine panel hidden (Knut). The tail sets the info label.
        elif tc918_repro:
            info = (
                tr("i1Pro TC9.18 by Pharmacist — fixed patch set ({notes}):\n"
                   "Uses the bundled tc918.ti1 (targen skipped).").format(
                    notes=" · ".join(notes))
                + f"\nprinttarg {' '.join(pt_args)}\n"
                + tr("Change a targen setting above to build a fresh chart instead.")
            )
        elif knut_repro:
            kp = KNUT_PRESETS_BY_KEY.get(self._knut_active_key or "")
            npatch = kp.patches if kp is not None else KNUT_PATCHES
            info = (
                tr("Built-in preset — fixed patch set ({notes}):\n"
                   "Uses the bundled {n}-patch .ti1 (targen skipped).").format(
                    notes=" · ".join(notes), n=npatch)
                + f"\nprinttarg {' '.join(pt_args)}\n"
                + tr("Change a targen setting above to build a fresh chart instead.")
            )
        else:
            layout = self._targen_skipped_layout_name()
            if layout is not None:
                # Built from an existing patch set (user preset .ti1, applied or
                # reflected chart) — targen is skipped, so name the layout (#70).
                info = (
                    tr("Manual mode — chart layout “{layout}” ({notes}):\n"
                       "Lays out the existing patch set (targen skipped).").format(
                        layout=layout, notes=" · ".join(notes))
                    + f"\nprinttarg {' '.join(pt_args)}"
                )
            else:
                info = (
                    tr("Manual mode — your current configuration ({notes}):").format(
                        notes=" · ".join(notes))
                    + f"\ntargen {' '.join(targen_args)}"
                    + f"\n{_layout_cmd()}"
                )
        # Engine on: the printtarg layout group is replaced by the layout panel.
        if getattr(self, "_manual_layout_grp", None) is not None:
            if use_engine and not self._manual_panel_inited:
                self._init_manual_layout_panel()
            # On the off→on transition, carry the current Manual instrument/paper
            # (e.g. from a just-loaded preset) into the engine panel (#93, Knut).
            if use_engine and not getattr(self, "_engine_was_active", False):
                self._sync_engine_panel_selection()
            self._engine_was_active = use_engine
            self._manual_layout_grp.setVisible(use_engine)
        if getattr(self, "_manual_printtarg_grp", None) is not None:
            self._manual_printtarg_grp.setVisible(not use_engine)
        # The command stamp covers targen + the layout engine when it's active
        # (no printtarg). Relabel it, and default it off the first time the
        # engine becomes active — the stamp is most useful for the printtarg
        # command line, less so for the engine.
        if getattr(self, "_manual_stamp_cmd_check", None) is not None:
            self._manual_stamp_cmd_check.setText(
                tr("Stamp targen and layout-engine info on the chart") if use_engine
                else tr("Stamp targen and printtarg commands on the chart"))
            if getattr(self, "_stamp_engine_state", None) != use_engine:
                self._stamp_engine_state = use_engine
                self._manual_stamp_cmd_check.setChecked(not use_engine)
        status = self._layout_preset_status() if use_engine else None
        if status is not None:
            summary, modified = status
            info += "\n" + summary + ("   " + tr("● modified") if modified else "")
        self._manual_info_lbl.setText(info)
        self._refresh_manual_preset_bar(use_engine, status)
        self._refresh_name_prefix()     # keep the name field plain (no prefix)

        # Live layout-info estimate (Manual + engine). Runs even with a chart on
        # screen so the "estimate" column tracks the current settings (#93).
        manual_active = (self._manual_btn is not None
                         and self._manual_btn.isChecked())
        if manual_active and getattr(self, "_layout_info_panel", None) is not None:
            if use_engine and getattr(self, "_manual_layout_panel", None) is not None:
                try:
                    from workflow.layout_engine import instruments
                    r = self._current_layout_recipe()
                    # Margin boxes are ALWAYS the law now (Knut, new model): the
                    # render never clamps to instrument minimums, so the estimate
                    # mustn't either, or the two would disagree. Below-minimum is
                    # only flagged as a violation in the inspector.
                    geom = instruments.geom_from_build_kwargs(r.build_kwargs())
                    pages_req = (self._manual_pages_spin.value()
                                 if self._manual_pages_spin is not None else 1)
                    # Use the on-screen chart's fixed patch count ONLY when the
                    # count is fixed (Auto patch count OFF). With Auto ON the count
                    # is a capacity-fill that changes with the patch size, so let
                    # the estimate recompute it (npat=None) — otherwise the estimate
                    # sticks on the stale generated count when you change e.g. the
                    # minimum patch width (#93, Knut beta-14 regression).
                    _auto = (self._manual_auto_patches_check is not None
                             and self._manual_auto_patches_check.isChecked())
                    self._predict_layout_info(
                        geom, r.paper, pages_req,
                        npat=None if _auto else self._onscreen_patch_total())
                except Exception:
                    self._layout_info_panel.clear_estimate()
            else:
                self._layout_info_panel.clear_estimate()

    # ------------------------------------------------------------------
    # Layout-engine per-chart preset bar (issue #93)
    # ------------------------------------------------------------------
    def _layout_store(self):
        from core.preset_store import load_presets
        from workflow.layout_engine.presets import PresetStore
        return PresetStore.from_named_dict(load_presets("chart_layout", self._settings))

    def _init_manual_layout_panel(self) -> None:
        """Seed the layout panel (first time the engine is shown in Manual).

        Prefer the recipe saved by "Save as Defaults" (every engine option,
        incl. paper, restored verbatim); otherwise fall back to the active
        per-(instrument/paper/mode) preset for the current selection (#93)."""
        self._manual_panel_inited = True
        saved = self._settings.get("manual_engine_recipe", None)
        if isinstance(saved, dict):
            from workflow.layout_engine.presets import LayoutRecipe
            try:
                self._manual_layout_panel.set_recipe(LayoutRecipe.from_dict(saved))
                return
            except Exception as exc:  # noqa: BLE001 — fall back to the preset
                log.warning("restore engine layout defaults failed: %s", exc)
        inst, paper, mode = self._manual_layout_panel.selection()
        store = self._layout_store()
        # No styling overlay here: _current_layout_recipe applies the Settings
        # strip-indicator styling at read time, so seeding stays verbatim.
        self._manual_layout_panel.set_recipe(store.get(inst, paper, mode))

    def _sync_engine_panel_selection(self) -> None:
        """Seed the engine layout panel's instrument/paper from the canonical
        Manual selection (printtarg -i/-p) — so enabling the engine after loading
        a preset carries Instrument and Paper into the ChromIQ frame, and the
        threshold lookup / Preferences preselect use the right combo (#93, Knut
        beta-13). Run only on the off→on transition; after that the panel is the
        source and the reverse mirror keeps printtarg in step."""
        p = getattr(self, "_manual_layout_panel", None)
        if p is None or p.instr is None or p.paper is None:
            return
        if getattr(self, "_syncing_manual_sel", False):
            return
        eng = {"3p": "p3"}.get(self._active_instrument_flag(),
                               self._active_instrument_flag())
        if eng not in ("i1", "p3", "CM", "SS"):
            eng = "i1"
        paper = self._active_paper_code() or "A4"
        self._syncing_manual_sel = True
        try:
            ii = p.instr.findData(eng)
            if ii >= 0 and p.instr.currentIndex() != ii:
                p.instr.setCurrentIndex(ii)          # rebuilds the paper list
            pi = p.paper.findData(paper)
            if pi >= 0:
                p.paper.setCurrentIndex(pi)
        finally:
            self._syncing_manual_sel = False

    def _sync_manual_selection_from_panel(self, *_a) -> None:
        """Reverse of :meth:`_sync_engine_panel_selection`: mirror the engine
        panel's instrument/paper back onto the printtarg -i/-p widgets, so the
        margin/layout Preferences preselect and naming follow what the engine
        panel shows (#93, Knut beta-13)."""
        p = getattr(self, "_manual_layout_panel", None)
        if (p is None or p.instr is None
                or getattr(self, "_syncing_manual_sel", False)
                or getattr(p, "_loading", False)):
            return
        eng = p.instr.currentData() or "i1"
        paper = p.paper.currentData() or "A4"
        flag = {"p3": "3p"}.get(eng, eng)
        self._syncing_manual_sel = True
        try:
            for pw in self._manual_widgets.get("printtarg", []):
                if pw.flag == "-i":
                    pw.set_value(flag)
                elif pw.flag == "-p":
                    pw.set_value(paper)
        finally:
            self._syncing_manual_sel = False

    def _current_layout_recipe(self):
        """The LayoutRecipe from the engine layout panel, with the strip-
        indicator styling overlaid from Preferences → Chart Layout. That styling
        is global — the single source of truth for every engine chart; loaded
        presets / saved defaults carry the styling fields only as inert
        history. Overlaying at read time means a style change in Preferences
        reaches the next build/preview immediately, on any recipe (#93)."""
        return self._settings.apply_indicator_style(
            self._manual_layout_panel.get_recipe())

    def _pin_restored_recipe(self, params) -> bool:
        """Rebuild a restored chart from the recipe it was BUILT with.

        Knut, #130 (2026-07-28, and again 2026-08-01: *"every time I clicked
        restore a new random sequence was shown in the preview"*): the sheet
        that comes back from Restore Used Chart is not the sheet that was
        measured. Driving the real app over his four-run project showed every
        page image changing — while the ``.ti2`` beside it stayed byte-identical
        apart from its ``CREATED`` line. So the patch order was never the
        problem; the *drawing* of it was.

        The cause is :meth:`_current_layout_recipe`, which deliberately overlays
        the ten strip-indicator styling fields from Preferences → Chart Layout
        on top of whatever the panel holds. That is right for a chart being
        made: the styling is app-wide and a change there should reach the next
        build. It is wrong for a chart being *reproduced*. His run had been
        drawn with a 4.23 mm indicator; Preferences said "auto", so the rebuild
        drew it at auto, the label band grew from 64 to 86 px, and every page
        came out different.

        A second, quieter source of drift: the size spinbox is whole points, so
        a recipe that went through the panel comes back rounded (4.23 mm →
        12 pt → 4.233 mm). Small, but a rebuild that must match cannot afford
        even that. Both are avoided the same way — by using the recipe read
        straight from the chart's own sidecar rather than anything the widgets
        have touched.

        Returns True when a stored recipe was pinned, so callers can tell the
        exact case from the best-effort one.
        """
        recipe = getattr(self, "_restored_exact_recipe", None)
        # Only meaningful for an engine chart: a printtarg chart has no recipe,
        # and `layout_recipe` is None unless the engine path is the active one.
        if recipe is None or getattr(params, "layout_recipe", None) is None:
            return False
        params.layout_recipe = recipe
        params.instrument = recipe.instrument
        params.paper = recipe.paper
        params.tiff_dpi = recipe.dpi
        # The record strip prints the date the chart was made. Rebuilt without
        # it, a restored sheet claims to have been made on the day it was
        # restored — so the paper in the user's hand and the paper on screen
        # disagree about their own history.
        params.chart_date = getattr(self, "_restored_chart_date", "") or ""
        return True

    @staticmethod
    def _layout_recipe_values(r) -> dict:
        """The comparable value fields of a recipe (ignores seed / chart text /
        strip-indicator styling — the styling is app-global, so it never counts
        as a preset modification)."""
        from core.settings import INDICATOR_STYLE_KEYS
        d = r.to_dict()
        for k in INDICATOR_STYLE_KEYS:
            d.pop(k, None)
        d.pop("seed", None)
        d.pop("chart_text", None)
        return d

    def _layout_preset_status(self):
        """``(summary, modified)`` for the active layout preset, or None."""
        try:
            cur = self._current_layout_recipe()
            preset = self._layout_store().get(cur.instrument, cur.paper, cur.mode())
        except Exception:
            return None
        modified = (self._layout_recipe_values(cur)
                    != self._layout_recipe_values(preset))
        from workflow.layout_engine import papers
        summary = tr("Layout preset: {i} · {p} · {m}").format(
            i=cur.instrument, p=papers.friendly_label(cur.paper), m=cur.mode())
        return summary, modified

    def _refresh_manual_preset_bar(self, use_engine: bool, status=None) -> None:
        bar = getattr(self, "_manual_preset_bar", None)
        if bar is None:
            return
        bar.setVisible(use_engine)
        if not use_engine:
            return
        modified = bool(status[1]) if status else False
        self._manual_preset_reset_btn.setEnabled(modified)
        self._manual_preset_update_btn.setEnabled(modified)

    def _reset_manual_to_preset(self) -> None:
        try:
            cur = self._current_layout_recipe()
            preset = self._layout_store().get(cur.instrument, cur.paper, cur.mode())
        except Exception as exc:
            log.warning("reset-to-preset failed: %s", exc)
            return
        self._manual_layout_panel.set_recipe(preset)
        self._refresh_manual_command_preview()

    def _update_manual_preset(self) -> None:
        from core.preset_store import save_presets
        try:
            store = self._layout_store()
            store.set(self._current_layout_recipe())
            save_presets("chart_layout", store.as_named_dict())
        except Exception as exc:
            log.warning("update-preset failed: %s", exc)
            return
        self._refresh_manual_command_preview()

    def _edit_layout_defaults(self) -> None:
        """Open Settings on the Chart Layout tab, preselected to the layout the
        user is editing here (#93)."""
        from ui.dialogs.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self._settings, self,
                             margin_combo=self.current_margin_combo(),
                             layout_combo=self.current_layout_combo())
        tabs = getattr(dlg, "_tabs", None)
        if tabs is not None:
            for i in range(tabs.count()):
                if tabs.tabText(i) == tr("Chart Layout"):
                    tabs.setCurrentIndex(i)
                    break
        dlg.exec()
        self._refresh_manual_command_preview()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:      # noqa: N802 (Qt override)
        super().showEvent(event)
        self._refit_logs()

    def _refit_logs(self) -> None:
        """Re-measure every log panel here in the font it actually has.

        Sizing in ``__init__`` happens before polish, so the stylesheet font is
        not yet applied and the measurement is against the wrong metrics. This
        runs once the widget is shown and again on any style or font change,
        which is also what makes the panels follow a theme switch.
        """
        for attr in ("_log", "_pc_log", "_ac_log"):
            panel = getattr(self, attr, None)
            if panel is not None:
                fit_log_height(panel)

    def changeEvent(self, event) -> None:      # noqa: N802 (Qt override)
        super().changeEvent(event)
        from PyQt6.QtCore import QEvent as _QEvent
        if event.type() in (_QEvent.Type.StyleChange, _QEvent.Type.FontChange):
            self._refit_logs()

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
                tr("Calibration file found: {name} — auto-filled into -I and -K "
                   "fields below.").format(name=cal_file.name)
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
        # Target-name fields support a locked, auto-updated descriptive prefix
        # (the "Add a descriptive prefix" option); an empty prefix = plain field.
        le = PrefixLockedLineEdit(parent)
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
        if cleaned != raw:
            removed = raw[len(cleaned):]
            edit.setText(cleaned)
            hint.setText(
                tr("Removed “{removed}” — the printer profile project name is used for the project folder and every generated file, so it shouldn't include a file extension.").format(removed=removed)
            )
            hint.setVisible(True)
        else:
            hint.setVisible(False)
        # A name change after a project already exists is reconciled here, the
        # moment the field loses focus (#70) — rename the folder/files, keep both,
        # or (once a profile is built) refuse and offer copy-to-new instead.
        self._maybe_rename_on_edit(edit, hint)

    def _maybe_rename_on_edit(self, edit: Any, hint: QLabel) -> None:
        """Reconcile a profile-name change as soon as the field loses focus.

        When a project already exists under the previous name and the user types
        a different (free) name, offer the rename/keep/delete chooser straight
        away (#70, itsab1989). Once the profile has been *built*, renaming is
        refused — the ICC's embedded description is baked in — and the user is
        told to copy it to a new name instead (Knut). Reverts the field on a
        cancelled rename so the displayed name always matches what's on disk.
        """
        new_name = self._file_mgr.strip_workfile_ext(edit.text().strip())
        old_name = getattr(self, "_last_target_name", "") or ""
        if not old_name or not new_name:
            return
        old_root = self._file_mgr.root_dir() / old_name
        if not (old_root / "project.json").exists():
            return                                   # nothing created under the old name
        new_root = self._file_mgr.preview_project_root(new_name)
        if new_root is None or new_root == old_root:
            return                                   # unchanged / equivalent name
        # A finished profile can't be renamed — the embedded ICC description was
        # baked at build time. Refuse, explain, and restore the built name.
        if self._file_mgr.project_has_built_profile(old_name):
            self._warn_rename_after_profile(old_name)
            edit.setText(old_name)
            hint.setVisible(False)
            return
        if new_root.exists():
            return                                   # a different project owns the new name
        if not self._handle_target_rename(new_name):
            edit.setText(old_name)                   # cancelled → keep the old name shown
            return
        # Rename / keep / delete all "move on" to the new name; point the
        # FileManager at it so a later Generate lands in the right place and
        # doesn't prompt a second time.
        self._file_mgr.set_target_name(new_name)
        self._last_target_name = new_name

    def _warn_rename_after_profile(self, name: str) -> None:
        """Tell the user a built profile can't be renamed (#70, Knut)."""
        InfoDialog(
            tr("This profile has already been built"),
            tr("“{name}” already has a finished ICC profile, so its name is now "
               "fixed — the name is written inside the profile itself (what you "
               "see in, for example, ColorSync Utility), and renaming the folder "
               "wouldn't change that.\n\n"
               "To continue under a different name, copy this project to a new "
               "name and build a fresh profile there.").format(name=name),
            self, min_width=540,
        ).exec()

    # ------------------------------------------------------------------
    # Load an existing printer profile to continue it later (#70, Knut)
    # ------------------------------------------------------------------
    def _make_load_profile_button(self, parent: QWidget) -> QToolButton:
        """The magenta stacked-pages button (left of the built-in-presets star)
        that reopens an existing profiling project, so a profile started earlier
        can be picked up another day (#70, Knut). Two stacked pages = "a project
        (its files) you started earlier" (Sebastian). Styled to match the star
        and the other load glyphs — same 40×40 hit target, the ``#tooltip_btn``
        hover background, and the spectrum magenta."""
        from ui.widgets import StackedPagesButton
        btn = StackedPagesButton(SPEC_MAGENTA, parent)
        btn.setToolTip(
            tr("Load profile.\n"
               "Reopen a printer profile you started earlier to carry on\n"
               "with it — its chart, measurements and any profile are\n"
               "all where you left them. Pick the project's “project.json”\n"
               "file under your ChromIQ folder."))
        btn.clicked.connect(self._load_existing_profile)
        return btn

    def _maybe_announce_project_port(self, manifest: Path) -> None:
        """If *manifest* is from an older ChromIQ, show a one-time, friendly
        explanation that opening it will bring the folder up to the current
        layout (#130 Model C). Reads the raw schema_version BEFORE Project.load
        migrates it. Never blocks — porting is safe and non-destructive."""
        import json as _json
        from core.file_manager import SCHEMA_VERSION
        try:
            data = _json.loads(manifest.read_text(encoding="utf-8"))
            ver = int(data.get("schema_version", 1))
        except Exception:      # noqa: BLE001 — a load problem surfaces later
            return
        if ver >= SCHEMA_VERSION:
            return
        InfoDialog(
            tr("Bringing this profile up to date"),
            tr("“{name}” was made by an older version of ChromIQ.\n\n"
               "Opening it now updates the folder to the current layout — the "
               "chart, measurement and profile files are tidied into per-run "
               "folders, with reports, exports and verifications kept in their "
               "own sub-folders.\n\n"
               "This happens in place and is completely safe: nothing is "
               "deleted, and a short “How this folder is organised” guide is "
               "written alongside your files. You only see this message once "
               "per profile.").format(name=manifest.parent.name),
            self, min_width=560,
        ).exec()

    def _update_name_fields(self) -> None:
        """Reflect the current target name in both the guided and manual
        “Printer profile project name” fields, so opening/creating a project is
        visibly loaded in the Create Chart tab (#130, Knut)."""
        # Read WITHOUT get_target_name(): it invents and stores a
        # "Printer_Paper_Type_Instr_<timestamp>" name when none is set, which
        # would then be written into the field over whatever the user had typed.
        # There is nothing to reflect until a project actually carries a name.
        name = getattr(self._file_mgr, "_target_name", "")
        if not name:
            return
        self._last_target_name = name
        for f in (getattr(self, "_target_name_edit", None),
                  getattr(self, "_manual_target_name_edit", None)):
            if f is not None:
                if isinstance(f, PrefixLockedLineEdit):
                    f.set_prefix("")
                f.setText(self._last_target_name)

    def _load_existing_profile(self) -> None:
        """Reopen an existing project: make it the active profile, fill the name
        field, and show its current chart (#70, Knut)."""
        root = self._file_mgr.root_dir()
        start = str(root) if root.exists() else str(Path.home())
        picked = open_file_dialog(
            self,
            tr("Open a printer profile"),
            name_filter=tr("ChromIQ profile (project.json)") + " (project.json)",
            start_dir=start,
        )
        if not picked:
            return
        manifest = Path(picked)
        # Accept either the project.json itself or its folder.
        if manifest.is_dir():
            manifest = manifest / "project.json"
        if manifest.name != "project.json" or not manifest.is_file():
            InfoDialog(
                tr("Not a ChromIQ profile"),
                tr("That isn't a ChromIQ project. Choose the “project.json” file "
                   "inside a profile folder under your ChromIQ folder."),
                self, min_width=520,
            ).exec()
            return
        # #130 (Knut bug): a project OUTSIDE the working folder must not open
        # silently — the model keeps every project in the working folder so it
        # can find them again. Offer to copy it in (per the unified load
        # strategy); a project already in the working folder opens directly.
        proj_root = manifest.parent
        working = Path(self._file_mgr.root_dir())     # the base ~/ChromIQ folder
        # #130 (Knut): a project may be organised in a SUB-folder of the ChromIQ
        # folder — treat any project UNDER the ChromIQ folder (at any depth) as
        # internal and open it in place. Only a project truly outside the ChromIQ
        # folder offers the copy-in pop-up.
        try:
            rp = proj_root.resolve(); rootp = working.resolve()
            is_external = rootp != rp.parent and rootp not in rp.parents
        except OSError:
            is_external = False
        if is_external:
            from ui.ti2_loader import _ask_project_name, _choice_dialog
            import workflow.chart_import as _chart_import
            intro = tr(
                "<b>{name}</b> is a complete ChromIQ project, but it is outside "
                "your ChromIQ working folder.<br><br>ChromIQ keeps every project "
                "in your working folder so it can always find it again. Copy "
                "this project in to open it?"
            ).format(name=proj_root.name)
            choice = _choice_dialog(
                self, tr("Open a printer profile project"), intro,
                [(tr("Copy it into my working folder"),
                  tr("Recommended. Copies the whole project — every run, chart, "
                     "measurement, profile and verification — into your working "
                     "folder, then opens the copy. The original is left "
                     "untouched."), "copy")])
            if choice != "copy":
                return
            picked_name, replace = _ask_project_name(self, proj_root.name, working)
            if picked_name is None:
                return
            try:
                new_root = _chart_import.copy_whole_project(
                    proj_root, working, picked_name, replace=replace)
            except Exception as exc:      # noqa: BLE001
                InfoDialog(tr("Couldn't copy the project"),
                           tr("The project could not be copied into your "
                              "working folder.\n\nWhat went wrong: {error}"
                              "\n\nYour original project has not been "
                              "touched, so nothing is lost. The usual causes "
                              "are a full disk, a folder ChromIQ is not "
                              "allowed to write to, or a drive that is no "
                              "longer connected. Check the working folder in "
                              "Preferences → Paths, then try again."
                              ).format(error=str(exc)),
                           self, min_width=500).exec()
                return
            manifest = new_root / "project.json"
        # #130 (Model C): a project written by an older ChromIQ (pre-#127 flat
        # layout, or a pre-verifications manifest) is brought up to the current
        # folder layout the moment it's opened. The migration is in-place and
        # never deletes anything, but the folder visibly reorganises — so tell
        # the user first, in plain language, before it happens.
        self._maybe_announce_project_port(manifest)
        # Open at the project's ACTUAL folder (handles a nested sub-folder
        # location as well as a direct child of the ChromIQ folder).
        self._file_mgr.open_project_at(manifest.parent)
        self._last_target_name = self._file_mgr.get_target_name()
        self._update_name_fields()
        # Loading a saved project is a clean slate for the preset/applied bindings.
        self._tc918_active = False
        self._tc918_targen_sig = None
        self._knut_active = False
        self._knut_targen_sig = None
        self._knut_active_key = None
        self._preset_ti1_path = None
        self._preset_ti1_targen_sig = None
        # The reopened run's meta.json already carries its own recipe (if any);
        # don't let a previously-selected preset's recipe override it on a later
        # regenerate (#70).
        self._pending_editor_recipe = None
        if self._prebuilt_active:
            self._leave_prebuilt()
        if self._applied_active:
            self._leave_applied()
        if self._reflected_active:
            self._leave_reflected()
        # Show the project's current chart, if it has one already.
        try:
            run = self._file_mgr.project().current_run()
            ti2 = run.chart_ti2
            tiffs = sorted(run.dir.glob(f"{run.stem}_*.tif"))
            if not tiffs and (run.dir / f"{run.stem}.tif").is_file():
                tiffs = [run.dir / f"{run.stem}.tif"]
        except Exception as exc:  # noqa: BLE001 — never block on a malformed run
            log.warning("Could not read loaded project's current run: %s", exc)
            ti2, tiffs = None, []
        self._log.clear()
        self._log.appendPlainText(
            tr("Loaded profile “{name}”.").format(name=self._last_target_name))
        if tiffs:
            ti1 = run.dir / f"{run.stem}.ti1"
            self._display_run_chart(ti2, tiffs, ti1)
        else:
            self._preview.clear()
            self._current_ti1_path = None
        # #130: default the shared bar to this project's current run.
        self._default_bar_to_current_run()
        self._reset_run_type_for_loaded_project()

    def _display_run_chart(self, ti2: Path, tiffs: list[Path], ti1: Path) -> None:
        """Show an existing chart (its pages, margins and own creation settings)
        in the Create-Chart tab and hand it to Print / Measure. Shared by
        project-load (:meth:`_load_existing_profile`) and the Run-type switch
        (:meth:`_on_target_changed`), so both paths tell one story."""
        self._preview.set_notice(None)     # a real chart is showing — drop guidance
        self._preview.load_tiff(list(tiffs))
        # Feed the Chart-layout-information panel and the margin inspector, so
        # the "on screen" column shows the LOADED chart's real numbers (mavtop:
        # it sat empty after reloading a project).
        self._set_margin_chart(list(tiffs), ti2)
        # And bring the option panels back to the settings this chart was
        # actually made with, so screen and chart tell one story.
        restored_full = self._restore_chart_settings(ti2)
        # …and the page count comes from the chart in front of you, always.
        #
        # Knut, #130 2026-07-28: every run showed "pages = 20", including one
        # with two pages, and changing any parameter made it correct again. 20
        # was his saved default: the chart's own count is only restored inside
        # the full-recipe branch, and a saved default could be applied over it
        # afterwards. The pages are countable from the chart itself, so there is
        # no reason to leave the field reading anything else.
        self._show_loaded_page_count(list(tiffs), ti2)
        notes_too = getattr(self, "_restored_notes_stamp", False)
        if restored_full and notes_too:
            self._log.appendPlainText(tr(
                "Restored the chart's own layout settings — patch size, "
                "spacers, margins, seed, notes and patch count now show "
                "the values this chart was made with."))
        elif restored_full:
            # Chart saved before notes/stamp were recorded per chart.
            self._log.appendPlainText(tr(
                "Restored the chart's own layout settings — patch size, "
                "spacers, margins, seed and patch count now show the "
                "values this chart was made with."))
        elif notes_too:
            self._log.appendPlainText(tr(
                "This chart carries no saved layout recipe (made with "
                "printtarg), so its instrument, paper, patch count, "
                "chart notes and stamp choice were restored — the "
                "preview still shows the chart exactly as it is."))
        else:
            self._log.appendPlainText(tr(
                "This chart carries no saved layout recipe (made with "
                "printtarg or an older ChromIQ), so only its instrument, "
                "paper and patch count could be restored — the preview "
                "still shows the chart exactly as it is."))
        # Recompute the layout-info ESTIMATE column from the restored settings —
        # set_recipe applies silently (no changed signal), so without this the
        # estimate kept showing the pre-load values while the options already
        # showed the chart's own (Basti).
        self._refresh_manual_command_preview()
        self._current_ti1_path = ti1 if ti1.is_file() else None
        self._shown_chart_ti2 = ti2      # track the artefact now on screen (#130)
        self._shown_chart_stamp = self._chart_stamp(ti2)
        # Let Print / Measure pick the chart up, as if it had just been built.
        self.chart_finished.emit(list(tiffs), ti2, False)

    def _load_yaml_params(self) -> dict:
        path = resource_path("data/parameters.yaml")
        # Use libyaml's C loader when available — it parses parameters.yaml
        # several times faster than the pure-Python SafeLoader (~70 ms off app
        # start) and produces byte-for-byte the same data. Falls back to the
        # pure-Python loader on the rare build without the C extension.
        try:
            from yaml import CSafeLoader as _Loader
        except ImportError:
            from yaml import SafeLoader as _Loader
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.load(f, Loader=_Loader)
            from core.i18n import translate_parameters
            return translate_parameters(data.get("parameters", {}))
        except Exception as exc:
            log.error("Cannot load parameters.yaml: %s", exc)
            return {}

    def _switch_mode(self, mode: str) -> None:
        prev = self._current_mode()     # capture BEFORE the stack changes
        if mode == "guided":
            self._stack.setCurrentIndex(0)
            self._guided_btn.setChecked(True)
            self._manual_btn.setChecked(False)
        else:
            self._stack.setCurrentIndex(1)
            self._guided_btn.setChecked(False)
            self._manual_btn.setChecked(True)
        self._update_isis_preview_banner()
        self._refresh_name_prefix()     # apply the prefix to the now-active field
        # Auto-update-preview is a Manual-only control (Knut).
        if getattr(self, "_auto_preview_row_w", None) is not None:
            self._auto_preview_row_w.setVisible(mode == "manual")
        # Keep the two tabs in step (Knut #9): carry the shared chart-defining
        # settings the user CHANGED in the tab they're leaving into the one they're
        # opening. Only changed fields move (snapshot-on-arrival / diff-on-leave),
        # so a setting the destination can't represent — e.g. an A3 paper Guided
        # doesn't offer — is never "changed" there and so can never clobber the
        # other tab on the way back. The post-generate #79 path still does the full
        # exact-recipe seed.
        if prev != mode and not getattr(self, "_mode_transfer_active", False):
            self._mode_transfer_active = True
            try:
                if mode == "manual" and getattr(self, "_guided_transfer_pending", False):
                    # #79: a chart was just generated in Guided — seed Manual with
                    # the EXACT recipe that produced it (incl. scale/margin), once.
                    self._guided_transfer_pending = False
                    self._transfer_guided_to_manual()
                else:
                    self._carry_shared_settings(prev, mode)
            finally:
                self._mode_transfer_active = False
        # Snapshot the now-active tab's shared settings so the next switch can tell
        # what the user changed while it was open.
        self._snapshot_shared_settings(mode)
        # Refresh the now-active mode's predictors so the patch count and the
        # Chart-layout-information estimate describe the mode on screen (#93) —
        # each predictor is guarded by active mode, so the just-hidden one stops
        # updating and the newly-shown one takes over.
        if mode == "guided":
            self._update_patch_count()
        else:
            self._refresh_manual_command_preview()

    def _transfer_guided_to_manual(self, quiet: bool = False) -> None:
        """Seed the Manual panel from the Guided settings.

        *quiet* = the plain tab-switch sync (Knut #9): carry only the shared
        chart-defining fields and leave Manual's patch count and custom
        scale/margin alone (changing -i below still cascades the instrument
        defaults). Without *quiet* it's the post-generation #79 transfer, which
        reproduces the EXACT generated chart (scale, margin, Auto count) and logs.
        Best-effort: never blocks a mode switch."""
        try:
            p = self._collect_guided()
        except Exception:
            log.warning("Guided→Manual transfer skipped (could not read guided "
                        "settings)", exc_info=True)
            return
        # Instrument + paper first: changing the instrument can cascade (reset
        # -a/-m to the instrument default), so scale/margin are set afterwards.
        self._set_manual_value("printtarg", "-i", p.instrument)
        self._set_manual_value("printtarg", "-p", p.paper)
        if self._manual_pages_spin is not None:
            self._manual_pages_spin.setValue(int(p.pages))
        self._set_manual_value("targen", "-d", str(p.device_type))
        self._set_manual_value("targen", "-G", bool(p.good_mode))
        if not quiet:
            # Reproduce the exact generated chart: mirror Guided's Auto count
            # (which drives the neutral counts) and its derived scale/margin.
            if self._manual_auto_patches_check is not None:
                self._manual_auto_patches_check.setChecked(True)
            self._set_manual_value("printtarg", "-a", round(float(p.patch_scale), 3))
            self._set_manual_value("printtarg", "-m", int(p.margin_mm))
        self._set_manual_value("printtarg", "-h", bool(p.double_density))
        self._set_manual_value("printtarg", "-P", bool(p.no_strip_limit))
        self._set_manual_value("printtarg", "-L", bool(p.disable_left_border))
        if self._manual_td_check is not None:
            self._manual_td_check.setChecked(bool(p.triple_density))
        # Pre-conditioning profile (-c), if the guided chart used one.
        try:
            toks = shlex.split(p.extra_targen_args or "")
            if "-c" in toks:
                i = toks.index("-c")
                if i + 1 < len(toks) and toks[i + 1]:
                    self._set_manual_value("targen", "-c", toks[i + 1])
        except ValueError:
            pass
        if not quiet:
            # Printer profile project name + a one-time confirmation.
            name_edit = getattr(self, "_target_name_edit", None)
            name = name_edit.text().strip() if name_edit is not None else ""
            if name:
                self._set_manual_name_plain(name)
        # With the engine on, the layout panel (not the printtarg widgets) builds
        # the Manual chart, so load the FULL engine recipe Guided used into the
        # panel — instrument, paper, pages AND clip-border suppression, margins,
        # patch scale, density, edge spacers — or Manual silently rebuilds a
        # different chart (Knut: clip border reappeared, patches too near the
        # labels). Otherwise (engine off) just sync the canonical selection.
        self._apply_guided_engine_recipe(p)
        self._refresh_manual_command_preview()
        if not quiet:
            self._log.appendPlainText(tr(
                "Guided settings copied to Manual mode — edit and regenerate as "
                "needed."))

    # Shared chart-defining settings both tabs express (Knut #9). Each is read /
    # written per tab below; only the ones the user CHANGED in the tab being left
    # are carried, so a value the other tab can't represent never clobbers it.
    _SHARED_SETTINGS = ("instrument", "paper", "pages", "double_density",
                        "triple_density", "left_border", "no_strip_limit",
                        "precond")
    # On a plain tab switch (no Generate) only these carry — the rest waits for
    # the post-Generate transfer (Knut #2).
    _SWITCH_CARRY_FIELDS = ("instrument", "paper")

    def _manual_get(self, tool: str, flag: str, default: Any) -> Any:
        for pw in self._manual_widgets.get(tool, []):
            if pw.flag == flag:
                v = pw.get_raw_value()
                return v if v is not None else default
        return default

    def _manual_enabled(self, tool: str, flag: str) -> bool:
        """True when an expert flag's enable-checkbox is ticked (so it reaches the
        command). Used to transfer a value only when the user actually set it."""
        for pw in self._manual_widgets.get(tool, []):
            if pw.flag == flag:
                return bool(pw.is_enabled_by_user)
        return False

    def _shared_get(self, tab: str) -> "dict[str, Any]":
        """Current value of every shared setting for *tab* ('guided'|'manual')."""
        if tab == "guided":
            precond = (self._guided_precond_path.text().strip()
                       if self._guided_precond_check.isChecked() else "")
            return {
                "instrument": self._instr_combo.currentData(),
                "paper": self._paper_combo.currentData(),
                "pages": int(self._pages_spin.value()),
                "double_density": self._dd_check.isChecked(),
                "triple_density": self._td_check.isChecked(),
                "left_border": self._lb_check.isChecked(),
                "no_strip_limit": self._nsl_check.isChecked(),
                "precond": precond,
            }
        # manual
        toks = []
        try:
            toks = shlex.split(str(self._manual_get("targen", "-c", "") or ""))
        except ValueError:
            toks = []
        precond = toks[0] if toks else str(self._manual_get("targen", "-c", "") or "")
        td = (self._manual_td_check is not None
              and self._manual_td_check.isChecked())
        return {
            "instrument": str(self._manual_get("printtarg", "-i", "i1")),
            "paper": str(self._manual_get("printtarg", "-p", "A4")),
            "pages": (int(self._manual_pages_spin.value())
                      if self._manual_pages_spin is not None else 1),
            "double_density": bool(self._manual_get("printtarg", "-h", False)),
            "triple_density": bool(td),
            "left_border": bool(self._manual_get("printtarg", "-L", True)),
            "no_strip_limit": bool(self._manual_get("printtarg", "-P", False)),
            "precond": precond,
        }

    def _shared_set(self, tab: str, field: str, value: Any) -> None:
        """Apply one shared setting to *tab*. Skips quietly when the tab can't
        represent the value (e.g. a paper Guided doesn't offer) so it never gets
        clobbered to a wrong value."""
        if tab == "guided":
            if field == "instrument":
                i = self._instr_combo.findData(value)
                if i >= 0:
                    self._instr_combo.setCurrentIndex(i)
            elif field == "paper":
                i = self._paper_combo.findData(value)
                if i < 0:                       # try a same-dimensions guided code
                    dims = _PAPER_MM.get(value)
                    if dims:
                        for k in range(self._paper_combo.count()):
                            if _PAPER_MM.get(self._paper_combo.itemData(k)) == dims:
                                i = k
                                break
                if i >= 0:
                    self._paper_combo.setCurrentIndex(i)
            elif field == "pages":
                self._pages_spin.setValue(int(value))
            elif field == "double_density":
                self._dd_check.setChecked(bool(value))
            elif field == "triple_density":
                self._td_check.setChecked(bool(value))
            elif field == "left_border":
                self._lb_check.setChecked(bool(value))
            elif field == "no_strip_limit":
                self._nsl_check.setChecked(bool(value))
            elif field == "precond":
                self._guided_precond_path.setText(str(value or ""))
                self._guided_precond_check.setChecked(bool(value))
        else:  # manual (a superset of guided's options)
            if field == "instrument":
                self._set_manual_value("printtarg", "-i", value)
            elif field == "paper":
                self._set_manual_value("printtarg", "-p", value)
            elif field == "pages":
                if self._manual_pages_spin is not None:
                    self._manual_pages_spin.setValue(int(value))
            elif field == "double_density":
                self._set_manual_value("printtarg", "-h", bool(value))
            elif field == "triple_density":
                if self._manual_td_check is not None:
                    self._manual_td_check.setChecked(bool(value))
            elif field == "left_border":
                self._set_manual_value("printtarg", "-L", bool(value))
            elif field == "no_strip_limit":
                self._set_manual_value("printtarg", "-P", bool(value))
            elif field == "precond":
                self._set_manual_value("targen", "-c", str(value or ""))

    def _link_instrument_controls(self) -> None:
        """Keep Guided's and Manual's instrument the same, in both directions.

        Knut, #130 2026-07-28: he opened a project whose instrument was a
        ColorMunki, saw it correctly in Manual, and found Guided still showing
        the default i1Pro. His rule: *"When loading project, or changing
        instrument, the instrument selection shall always be the same for
        guided and for manual mode (linked both ways)."*

        **Why a link and not another call site.** The instrument is written by a
        dozen different paths — opening a project, a preset, a prebuilt chart, a
        loaded patch set, the layout editor, the Guided→Manual transfer. Adding
        the mirror to each one would have fixed today's report and left the next
        path to be found by Knut. Linking the two controls makes every path
        right, including ones written later.

        A tab switch still carries the other shared settings (paper, pages…) as
        before; only the instrument is continuous.
        """
        self._syncing_instrument = False

        def _mirror(src: str) -> None:
            if self._syncing_instrument:
                return                      # the echo of our own write
            self._syncing_instrument = True
            try:
                value = self._shared_get(src).get("instrument")
                if value:
                    # _shared_set skips quietly when the other side cannot show
                    # this instrument — Guided deliberately omits the external
                    # ones (i1iSis), and must not be forced to a wrong value.
                    self._shared_set("manual" if src == "guided" else "guided",
                                     field="instrument", value=value)
            except Exception:      # noqa: BLE001 — a mirror must never block a load
                log.warning("Could not mirror the instrument between modes",
                            exc_info=True)
            finally:
                self._syncing_instrument = False

        if getattr(self, "_instr_combo", None) is not None:
            self._instr_combo.currentIndexChanged.connect(
                lambda *_: _mirror("guided"))
        for pw in self._manual_widgets.get("printtarg", []):
            if pw.flag == "-i":
                pw.value_changed.connect(lambda *_: _mirror("manual"))
                break

    def _snapshot_shared_settings(self, tab: str) -> None:
        """Remember *tab*'s shared settings as they are now, so the next switch
        can tell which ones the user changed while it was open."""
        try:
            snaps = self.__dict__.setdefault("_shared_snapshots", {})
            snaps[tab] = self._shared_get(tab)
        except Exception:  # noqa: BLE001 — never block a mode switch
            log.debug("shared-settings snapshot skipped", exc_info=True)

    def _carry_shared_settings(self, src: str, dst: str) -> None:
        """Carry the shared settings the user CHANGED in *src* into *dst* (#9)."""
        try:
            snaps = getattr(self, "_shared_snapshots", {})
            before = snaps.get(src)
            now = self._shared_get(src)
        except Exception:  # noqa: BLE001
            log.debug("Guided↔Manual transfer skipped", exc_info=True)
            return
        if not now:
            return
        # A plain tab switch carries ONLY instrument + paper, so the two tabs
        # agree on the device without the surprise of margins/density/etc. jumping
        # across un-generated (Knut: full transfer happens on Generate). Snapshot/
        # diff still guards against an unrepresentable paper clobbering the source.
        for field in self._SWITCH_CARRY_FIELDS:
            new = now.get(field)
            if before is None or before.get(field) != new:
                self._shared_set(dst, field, new)
        if dst == "guided":
            self._update_patch_count()
        else:
            self._sync_engine_panel_after_transfer()
            self._refresh_manual_command_preview()

    def _sync_engine_panel_after_transfer(self) -> None:
        """When the ChromIQ engine is on, a Manual chart is built from the engine
        LAYOUT PANEL, not the printtarg -i/-p/-a/-m widgets. So after carrying
        settings into Manual, push the canonical instrument / paper / pages into
        the panel too — otherwise the panel keeps its old instrument and the
        generated chart ignores what was transferred (Knut #9)."""
        if not bool(self._settings.get("use_chromiq_layout_engine", False)):
            return
        p = getattr(self, "_manual_layout_panel", None)
        if p is None:
            return
        self._sync_engine_panel_selection()      # instrument + paper → panel
        if (getattr(p, "pages", None) is not None
                and self._manual_pages_spin is not None):
            p.pages.setValue(int(self._manual_pages_spin.value()))

    def _apply_guided_engine_recipe(self, guided_params) -> None:
        """Load the FULL engine recipe a Guided chart used into the Manual layout
        panel, so Manual reproduces it exactly (Knut bugfix B).

        Guided builds engine charts from ``ChartCreator._engine_build_kwargs`` —
        the same kwargs converted to a :class:`LayoutRecipe` here — so clip-border
        suppression, margins, patch scale, density and edge spacers all carry, not
        just instrument/paper. No-op when the engine is off (then the printtarg
        widgets the transfer already set are what build the chart)."""
        if not bool(self._settings.get("use_chromiq_layout_engine", False)):
            return
        panel = getattr(self, "_manual_layout_panel", None)
        if panel is None:
            return
        try:
            from workflow.layout_engine.presets import LayoutRecipe
            kw = self._creator._engine_build_kwargs(guided_params)
            recipe = LayoutRecipe.from_build_kwargs(kw)
            panel.set_recipe(recipe)
            if (getattr(panel, "pages", None) is not None
                    and self._manual_pages_spin is not None):
                panel.pages.setValue(int(self._manual_pages_spin.value()))
        except Exception:  # noqa: BLE001 — never block the mode switch
            log.warning("Guided→Manual engine-recipe transfer failed",
                        exc_info=True)
            self._sync_engine_panel_after_transfer()   # fall back to light sync

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
            declutter_settings=self._settings,
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
        # mirror into the Manual module's targen expert option (-c) so the
        # profile is pre-filled there too if the user flips to Manual
        if self._manual_targen_c_pw is not None:
            self._manual_targen_c_pw.set_value(str(profile_path))
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
            from workflow.chart_creator import ENGINE_INSTRUMENTS
            paper = (self._manual_paper_pw.get_raw_value()
                     if self._manual_paper_pw is not None else "A4") or "A4"
            lb_on = (bool(self._manual_lb_pw.get_raw_value())
                     if self._manual_lb_pw is not None else False)
            # Hidden while the ChromIQ layout engine is on: the engine has its own
            # Clip-border content, and this legacy printtarg-only option would
            # otherwise silently force the printtarg path and flip the frame (Knut).
            engine_on = (bool(self._settings.get("use_chromiq_layout_engine", False))
                         and instr in ENGINE_INSTRUMENTS)
            show_left_clip = (
                not chromiq_clip
                and not engine_on
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
        lbl = QLabel(tr("Triple density"), row_w)
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
            tr("Triple Density (i1Pro layout emulation)"),
            tr("ColorMunki + rig only. Generates the chart with the i1Pro strip "
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
            "is hidden when those are selected."),
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
            if getattr(self, "_suppress_td_override", False):
                # Restoring a saved triple-density chart: the -a / -m / -P / -L
                # widgets already hold the *effective* TD layout (the values that
                # were saved), so DON'T overwrite them with the TD defaults — that
                # was the round-trip bug (#89) where a custom TD scale snapped back
                # to 1.3. Stash clean non-TD defaults so unticking later reverts
                # sensibly.
                self._td_saved_layout = {"-a": 1.0, "-m": 6, "-P": False, "-L": False}
            else:
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
        # Grey the "Pages:" label too (not just the spin) — with Auto off the
        # user has set an exact patch count, so the page count is fixed (#93).
        if getattr(self, "_manual_pages_lbl", None) is not None:
            self._manual_pages_lbl.setEnabled(checked)
        # Same for the engine layout panel's own Pages control (shown when the
        # ChromIQ engine is on), which is a separate widget.
        if getattr(self, "_manual_layout_panel", None) is not None:
            self._manual_layout_panel.set_pages_enabled(checked)
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
        self._preset_combo.addItem(tr("none"), userData=None)
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
        """Tooltip for a ti1 → printtarg built-in preset (TC9.18 or Full layout setup)."""
        p = KNUT_PRESETS_BY_KEY[key]
        if p.layout_recipe is not None:
            # Engine preset (Scanner family, #100).
            rec = p.layout_recipe
            return (
                "Built-in chart — cannot be deleted.\n"
                f"Loads the bundled {p.patches}-patch set and lays it out with "
                f"the ChromIQ layout engine\n"
                f"({rec.get('paper', p.paper)}, {p.pages}-page, "
                f"{rec.get('area_min_patch_mm', 4):g} mm patches).\n"
                "Print it WITHOUT colour management, scan it on a flatbed "
                "scanner, then use\n"
                "Tools → “Build profile with scanner or camera” with “Profile my "
                "printer from this scan”.\n"
                "Creates the target right away; the patch set stays fixed but "
                "you can adjust\nany layout setting and regenerate."
            )
        instr = "i1Pro" if p.instrument == _KNUT_I1 else "ColorMunki (double density)"
        family = ("TC9.18 + Spyderprint-greys" if p.suffix == KNUT_SUFFIX
                  else "Full layout setup")
        bits = [f"-p{p.paper}", f"-a{p.patch_scale:g}", f"-M{p.margin}"]
        if p.spacer_scale is not None:
            bits.append(f"-A{p.spacer_scale:g}")
        if p.seed is not None:
            bits.append(f"-R{p.seed}")
        return (
            "Built-in chart — cannot be deleted.\n"
            f"Loads the bundled {p.patches}-patch {family} set and\n"
            f"lays it out for the {instr} ({p.pages}-page):\n"
            f"printtarg -i{p.instrument} -T200 {' '.join(bits)}\n"
            "Creates the target right away; the patch set stays fixed but you\n"
            "can adjust any printtarg setting and regenerate."
        )

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

        # Built-in presets generate immediately under the current Printer-profile
        # name — selecting a preset is a *chart-layout* choice and never changes
        # the profile name the user typed (#70, Knut's model). The preset's own
        # default name is only a fallback used when the name field is still empty.
        if data in BUILTIN_PRESET_KEYS:
            if self._runner.is_running:
                log.warning("Built-in preset: a process is already running")
                self._revert_preset_combo()
                return
            name = None
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
            # Picking any preset drops an applied editor chart's binding.
            if self._applied_active:
                self._leave_applied()
            if self._reflected_active:
                self._leave_reflected()
            self._preset_ti1_path = None  # built-ins are not ti1-user-presets
            self._preset_ti1_targen_sig = None
            # A built-in that ships a creation recipe (Set B) seeds the New-chart
            # window just like a user preset — so loading it carries its colour
            # sets / layout into New chart, not the app-wide last-used state
            # (Knut). None for built-ins that are fixed .ti1 charts with no recipe.
            self._pending_editor_recipe = builtin_preset_recipe(data)
            # …but a built-in's own bundled .ti1 still feeds Suggest-name (#62).
            asset = self._builtin_ti1_asset(data)
            self._builtin_ti1_path = resource_path(asset) if asset else None
            # Start the freshly-picked built-in with its panels locked again.
            self._reset_override_checks()
            self._preset_del_btn.setEnabled(False)
            self._last_preset_index = index
            # Load each built-in with the engine it was made with: most are
            # printtarg-based (they predate the engine), but the Scanner family
            # carries a layout_recipe and needs the ChromIQ engine ON so the
            # recipe drives the layout (#100). Set BEFORE the dispatch so the
            # engine↔printtarg conversion runs first and the preset's values
            # then win — otherwise the layout panel would show leftovers
            # instead of the preset's real instrument/paper (Knut).
            _kp = KNUT_PRESETS_BY_KEY.get(data)
            engine_builtin = _kp is not None and (
                _kp.layout_recipe is not None or _kp.engine)
            if getattr(self, "_manual_engine_check", None) is not None \
                    and self._manual_engine_check.isChecked() != engine_builtin:
                self._manual_engine_check.setChecked(engine_builtin)
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
        # Likewise an applied editor chart is dropped for Default / a user preset.
        if self._applied_active:
            self._leave_applied()
        if self._reflected_active:
            self._leave_reflected()

        self._last_preset_index = index
        self._preset_del_btn.setEnabled(self._is_deletable_preset(index))
        s = self._settings
        if index == 0:
            # Returning to Default builds a fresh chart via targen. The
            # Printer-profile name is the user's own and is left untouched (#70).
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
            self._builtin_ti1_path = None     # Default builds via targen
            self._pending_editor_recipe = None  # Default builds via targen, no recipe
            if self._bit8_radio is not None and self._bit16_radio is not None:
                is_16bit = bool(s.get("manual_printtarg_tiff_16bit", False))
                self._bit16_radio.setChecked(is_16bit)
                self._bit8_radio.setChecked(not is_16bit)
            if self._manual_pages_spin is not None:
                self._manual_pages_spin.setValue(int(s.get("manual_pages", 1)))
            if self._manual_auto_patches_check is not None:
                auto_on = bool(s.get("manual_auto_patches", True))
                self._manual_auto_patches_check.setChecked(auto_on)
                self._on_auto_patches_toggled(auto_on)
            self._load_auto_neutral_states(
                grey  = bool(s.get("manual_auto_grey",  True)),
                white = bool(s.get("manual_auto_white", True)),
                black = bool(s.get("manual_auto_black", True)),
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
            # Load the preset with the engine it was made with (Knut #93): a
            # Manual preset stores printtarg widget values (no layout_recipe), so
            # select the printtarg engine — otherwise the ChromIQ engine would try
            # to render it and the preview is wrong. The restored -i/-p widgets
            # then drive the (correct) instrument & paper. An engine preset (future
            # layout_recipe) would instead switch the engine on.
            if getattr(self, "_manual_engine_check", None) is not None:
                has_recipe = isinstance(pdata, dict) and bool(pdata.get("layout_recipe"))
                self._manual_engine_check.setChecked(has_recipe)
            # Carry the preset's stored New-chart recipe (Set B), if any, so a
            # chart generated from it reopens in the editor with this design
            # pre-loaded into New chart / Add (#70, Knut follow-up).
            rec = pdata.get("editor_recipe") if isinstance(pdata, dict) else None
            self._pending_editor_recipe = rec if isinstance(rec, dict) and rec else None
            self._builtin_ti1_path = None     # a user preset, not a built-in
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
        # Re-establish the descriptive prefix: cleared while a preset name is
        # loaded, re-applied to the editable tail back on Default (#68).
        self._refresh_name_prefix()

        # A user preset flagged "generate on select" (▶) generates straight away
        # under the current Printer-profile name (#70) — the values are already
        # loaded above. The preset name is never written into the profile field.
        if data is not None and data not in BUILTIN_PRESET_KEYS:
            presets = self._load_presets_from_settings()
            pdata = presets.get(data, {})
            if isinstance(pdata, dict) and pdata.get("auto_run"):
                if self._runner.is_running:
                    return
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
        # Apply triple-density last. The saved values already ARE the effective
        # TD layout, so suppress the override so re-enabling the checkbox keeps
        # the restored -a / -m / -P / -L instead of snapping them to 1.3 / 5 (#89).
        if self._manual_td_check is not None:
            td_on = bool(data.get("triple_density", False))
            self._suppress_td_override = td_on
            try:
                self._manual_td_check.setChecked(td_on)
            finally:
                self._suppress_td_override = False
        # Auto-match the engine toggle to what the preset actually contains, so
        # the shown controls reflect the preset (engine panel vs printtarg). A
        # preset carries "layout_recipe" iff it was saved with the engine on;
        # old/printtarg presets lack it → engine off. Shareable + back-compat
        # (the flag lives in the preset file, not local state) (#93). Toggle and
        # refresh FIRST so the engine panel is built before we seed it (the
        # build reseeds from the store, which would clobber the preset recipe).
        lr = data.get("layout_recipe")
        engine_on = isinstance(lr, dict) and bool(lr)
        if bool(self._settings.get("use_chromiq_layout_engine", False)) != engine_on:
            self._settings.set("use_chromiq_layout_engine", engine_on)
        if engine_on:
            self._refresh_manual_command_preview()   # swap groups + init panel
            if getattr(self, "_manual_layout_panel", None) is not None:
                from workflow.layout_engine.presets import LayoutRecipe
                self._manual_layout_panel.set_recipe(LayoutRecipe.from_dict(lr))
                # The recipe carries its own instrument/paper — mirror them onto
                # the printtarg -i/-p so Preferences preselect + naming follow the
                # loaded engine preset (set_recipe suppresses the live mirror) (#93).
                self._sync_manual_selection_from_panel()
        else:
            self._refresh_manual_command_preview()   # show printtarg controls
        # Chart notes + stamp choice, gated on key presence so presets saved
        # without them keep the fields untouched. AFTER the engine block: an
        # engine flip resets the stamp checkbox to its mode default via
        # _refresh_manual_command_preview, which would overwrite these.
        if "chart_notes" in data and self._manual_chart_notes_edit is not None:
            self._manual_chart_notes_edit.setText(
                str(data.get("chart_notes") or ""))
        if ("stamp_commands" in data
                and self._manual_stamp_cmd_check is not None):
            self._manual_stamp_cmd_check.setChecked(
                bool(data.get("stamp_commands")))

    def _preset_save_prefill(self) -> tuple[str, bool, bool, bool]:
        """Initial (name, auto_run, attach, from_generator) for the Save Preset
        dialog.

        A preset names a **chart layout**, so the default is the descriptive
        generator name (instrument-paper-patches-pages-orientation) — *not* the
        printer-profile name in the Output frame, which describes the job, not
        the layout (#70, Knut). A non-built-in preset selected in the combo is
        the fallback when there's no generator name yet.

        Options follow the *name*: if it matches an existing user preset (i.e.
        you're about to overwrite it) its stored auto_run / attach are reused;
        otherwise it's a new preset and both default on — the common case."""
        generated = self._suggest_target_name().strip()
        cur_key = self._preset_combo.currentData()
        selected_preset = (str(cur_key)
                           if cur_key is not None and cur_key not in BUILTIN_PRESET_KEYS
                           else "")
        name = generated or selected_preset
        existing = self._load_presets_from_settings().get(name)
        if isinstance(existing, dict):
            return (name, bool(existing.get("auto_run")),
                    bool(existing.get("attached_ti1")), bool(generated))
        return (name, True, True, bool(generated))

    @staticmethod
    def _paper_name_and_orientation(paper: str) -> tuple[str, str]:
        """(base paper name, orientation) for a printtarg -p value, read from the
        paper labels (which carry "… Portrait" / "… Landscape"), e.g.
        ``"A4R"`` → ``("A4", "Landscape")``. Custom ``WxH`` sizes derive the
        orientation from their dimensions."""
        label = PAPER_LABELS.get(paper, "")
        if label:
            # Filesystem-safe readable token (A3+ → A3Plus, 8×10" → 8x10in) (#68).
            base = paper_name_token(paper)
            orient = ("Landscape" if "Landscape" in label
                      else "Portrait" if "Portrait" in label else "")
            return base, orient
        if "x" in str(paper):
            try:
                w, h = (float(v) for v in str(paper).split("x", 1))
                return str(paper), ("Landscape" if w > h else "Portrait")
            except ValueError:
                pass
        return str(paper), ""

    def comparable_presets(self) -> list[tuple[str, list[tuple[str, "Path"]]]]:
        """See the module-level :func:`comparable_presets` (#66)."""
        return comparable_presets(self._settings)

    @staticmethod
    def _builtin_ti1_asset(data: str) -> str | None:
        """Asset path of a built-in preset's bundled .ti1, or None for the
        targen-based built-ins (ColorMunki Triple-density) that have no .ti1."""
        if data == TC918_PRESET_KEY:
            return TC918_TI1_ASSET
        if data in KNUT_PRESETS_BY_KEY:
            return KNUT_PRESETS_BY_KEY[data].ti1_asset
        if data in PREBUILT_PRESETS:
            return PREBUILT_PRESETS[data][0] + ".ti1"
        return None

    def _loaded_ti1_patch_count(self) -> int | None:
        """Patch count of the .ti1 backing the current selection, if any —
        a user preset's sidecar (_preset_ti1_path), a built-in's bundled .ti1
        (_builtin_ti1_path, #62), or the chart just generated (_current_ti1_path)."""
        for p in (getattr(self, "_preset_ti1_path", None),
                  getattr(self, "_builtin_ti1_path", None),
                  getattr(self, "_current_ti1_path", None)):
            if p and Path(p).is_file():
                try:
                    txt = Path(p).read_text(encoding="latin-1", errors="ignore")
                    m = re.search(r"NUMBER_OF_SETS\s+(\d+)", txt)
                    if m:
                        return int(m.group(1))
                except OSError:
                    pass
        return None

    def _generated_page_count(self) -> int:
        """Actual number of pages the currently-previewed chart spans, or 0 when
        nothing is loaded. Mirrors what the user sees in the preview, so a fixed
        layout that printtarg split across extra sheets is counted correctly
        (#73)."""
        try:
            return self._preview.page_count()
        except Exception:  # noqa: BLE001 — name suggestion must never crash
            return 0

    def _suggest_target_name(self) -> str:
        """A descriptive default name from the current settings (#62):
        ``<instrument>-<paper>[-<N>p]-<pages>pages-<orientation>``. The patch
        count comes from the predicted count (guided) or the loaded preset's
        .ti1 (manual); the orientation comes from the paper selection."""
        instr_lbl = {"i1": "i1Pro", "CM": "ColorMunki", "3p": "i1Pro3Plus",
                     "p3": "i1Pro3", "SS": "SpectroScan"}
        manual = self._manual_btn is not None and self._manual_btn.isChecked()
        if manual:
            engine_on = (self._manual_engine_check is not None
                         and self._manual_engine_check.isChecked())
            panel = self._manual_layout_panel
            if engine_on and panel is not None and panel.paper is not None:
                # The layout ENGINE replaces printtarg — instrument and paper
                # live in its own panel; the printtarg widgets can hold stale
                # values (Knut: A4 Landscape suggested "A4…Portrait", Letter
                # Landscape even suggested "A4…Portrait", #108).
                instr = (panel.instr.currentData()
                         if panel.instr is not None else "") or "i1"
                paper = panel.paper.currentData() or "A4"
            else:
                instr = (self._manual_instr_pw.get_raw_value()
                         if self._manual_instr_pw is not None else "") or "i1"
                paper = (self._manual_paper_pw.get_raw_value()
                         if self._manual_paper_pw is not None else "") or "A4"
            spin = self._manual_pages_spin
            patches = self._loaded_ti1_patch_count()
        else:
            instr = (self._instr_combo.currentData()
                     if self._instr_combo is not None else "") or "i1"
            paper = (self._paper_combo.currentData()
                     if self._paper_combo is not None else "") or "A4"
            spin = self._pages_spin
            patches = getattr(self, "_predicted_patch_count", None)
        pages = int(spin.value()) if spin is not None else 1
        # When the Pages control is locked (a preset / .ti1 drives the layout),
        # its value can't be trusted — printtarg may split the fixed chart across
        # more sheets than it shows (e.g. a "1page" preset that lays out on 2).
        # Use the real page count of the generated chart instead (#73, Knut).
        if spin is not None and not spin.isEnabled():
            actual = self._generated_page_count()
            if actual:
                pages = actual
        base_paper, orient = self._paper_name_and_orientation(str(paper))
        parts = [instr_lbl.get(str(instr), str(instr)), base_paper]
        if patches:
            parts.append(f"{patches}p")
        parts.append("1page" if pages == 1 else f"{pages}pages")
        if orient:
            parts.append(orient)
        return "-".join(parts)

    # ------------------------------------------------------------------
    # Auto descriptive prefix (#68): keep a live, locked
    # "<instrument>-<paper>-<patches>p-<pages>-<orientation>-" head on the
    # target-name field, toggled by the "Add a descriptive prefix" option.
    # ------------------------------------------------------------------
    @staticmethod
    def _auto_suffix_tooltip() -> str:
        return tr(
            "Names this preset after its chart layout, so layout presets sort and read "
            "clearly together. With this on, ChromIQ leads the name with the layout's "
            "key details — instrument, paper size, patch count, pages and orientation — "
            "as a locked prefix, then you add your own detail after. So the name begins "
            "“i1Pro-A4-484p-1page-Portrait-” and you just add what tells this layout "
            "apart from your others.\n\n"
            "Add a detail about the layout itself — for example a variant or revision "
            "(“v2”), how it was built (“denser”, “no-greys”), or a date. There's no need "
            "to repeat printer or paper here: those name the finished profile, not the "
            "chart layout.\n\n"
            "The prefix updates on its own as you change the settings and can't be "
            "edited directly — click the field and your cursor lands right after it, "
            "ready to type. Turn the option off to name the preset entirely yourself.")

    @staticmethod
    def _profile_name_tooltip() -> str:
        """Guidance for the Printer-profile name field (#70, Knut's model).

        Speaks only to the *profile's* identity — the working folder, the files
        and the embedded ICC description (colprof -D) all share this name, so it
        deliberately says nothing about chart-layout naming (that lives in Save
        Preset and the editor's Save As)."""
        return tr(
            "The name of this whole profiling project — think of it as the job's "
            "title. It becomes the project folder on disk, the base name of every "
            "file ChromIQ makes along the way (chart, measurements, the finished "
            "ICC profile) and the profile's own embedded description — so what "
            "you see later in, for example, macOS ColorSync Utility matches the "
            "folder and files exactly.\n\n"
            "(The “printer profile” itself is the .icc / .icm file this project "
            "produces at the end. Naming the project after the printer and paper "
            "keeps that file easy to recognise.)\n\n"
            "Choose a name that identifies this printer and paper at a glance. "
            "A good name describes the printer (name or abbreviation), the paper "
            "(type/id and substrate such as glossy or matte), the colour space, "
            "the measurement instrument and the profile quality — e.g. "
            "Canon_Pro1000_PhotoRagBaryta_RGB_i1Pro3_High. Use underscores or "
            "dashes instead of spaces.\n\n"
            "You can rename it later: change the name here and ChromIQ offers to "
            "rename the folder and files to match — until the profile has been "
            "built, after which you copy it to a new name instead.")

    def _active_name_field(self):
        manual = self._manual_btn is not None and self._manual_btn.isChecked()
        return (self._manual_target_name_edit if manual
                else getattr(self, "_target_name_edit", None))

    def _name_prefix(self) -> str:
        """The locked descriptive head, e.g. ``i1Pro-A4-484p-1page-Portrait``;
        the user's free text follows it. The separator is supplied by
        PrefixLockedLineEdit and only appears once a tail is typed (#68)."""
        return self._suggest_target_name() or ""

    def _refresh_name_prefix(self) -> None:
        """Keep the Create Chart name fields plain (#70, Knut's model).

        The descriptive prefix now lives only in Save Preset and the editor's
        Save As; the Create Chart name is a plain, manual *printer-profile* name.
        This just clears any stale locked prefix left on the active field."""
        field = self._active_name_field()
        if isinstance(field, PrefixLockedLineEdit):
            field.set_prefix("")

    def _set_manual_name_plain(self, name: str) -> None:
        """Set the manual profile-name field verbatim (no locked prefix)."""
        f = self._manual_target_name_edit
        if f is None:
            return
        if isinstance(f, PrefixLockedLineEdit):
            f.set_prefix("")
        f.setText(name)

    def _ensure_profile_name(self, default: str) -> str:
        """Return the current Printer-profile name, seeding the field with
        ``default`` only when the user hasn't typed one (#70, Knut's model:
        presets / loaded charts never overwrite a name the user already chose).
        """
        f = self._manual_target_name_edit
        cur = (f.text().strip() if f is not None else "")
        if cur:
            return cur
        self._set_manual_name_plain(default)
        return default

    @staticmethod
    def _toggle_name_prefix(edit: "PrefixLockedLineEdit", on: bool, prefix: str) -> None:
        """Flip a name field between the locked-prefix and free modes (#68,
        Knut's model). ON: the descriptive head is locked + greyed with a
        trailing '-' and an empty editable tail (ready to type). OFF: the
        descriptive name is shown as a plain, fully editable field (no dash, no
        lock) — keep it, edit it, or replace it."""
        if on:
            edit.set_prefix("")        # drop any prior lock
            edit.setText("")
            edit.set_prefix(prefix)    # → "prefix-" with an empty tail
        else:
            edit.set_prefix("")        # remove the lock
            edit.setText(prefix)       # the generated name, fully editable

    def _on_preset_save(self) -> None:
        capture: dict = {}
        # Store the EFFECTIVE widget values, including the triple-density layout
        # (-a / -m / -P / -L) when TD is on — so the preset round-trips with the
        # right scale/margin (#89). On restore the TD checkbox is re-enabled in
        # suppressed mode so it won't clobber these back to the TD defaults.
        for tool, widgets in self._manual_widgets.items():
            for pw in widgets:
                if pw in self._d_cascade_widgets:
                    continue
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
        # ChromIQ layout engine: store the full layout recipe (minus the per-chart
        # seed) so a named preset carries the engine options too, exactly like it
        # carries the printtarg ones (#93). Only when the engine is active.
        if (getattr(self, "_manual_layout_panel", None) is not None
                and bool(self._settings.get("use_chromiq_layout_engine", False))):
            from dataclasses import replace
            capture["layout_recipe"] = replace(
                self._manual_layout_panel.get_recipe(), seed=None).to_dict()
        # Chart notes + stamp choice round-trip with the preset (mavtop,
        # forum). Presets saved before these keys existed simply lack them,
        # and loading such a preset leaves both fields untouched.
        capture["chart_notes"] = (
            self._manual_chart_notes_edit.text().strip()
            if self._manual_chart_notes_edit is not None else "")
        capture["stamp_commands"] = bool(
            self._manual_stamp_cmd_check is not None
            and self._manual_stamp_cmd_check.isChecked())
        (_prefill_name, prefill_run, prefill_attach,
         prefilled_from_target) = self._preset_save_prefill()
        # A patch set can only be attached if one is currently loaded.
        have_ti1 = (self._current_ti1_path is not None
                    and self._current_ti1_path.is_file())

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Save Preset"))
        dlg.setMinimumWidth(500)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(22, 20, 22, 16)
        lay.setSpacing(10)

        heading = QLabel(tr("Save preset"), dlg)
        heading.setStyleSheet("font-weight: bold;")
        lay.addWidget(heading)
        info = QLabel(
            tr("Give this preset a name. All current Manual-mode parameter values are "
            "saved under it and can be recalled any time from the preset list. "
            "Re-saving with an existing name overwrites it."),
            dlg,
        )
        info.setWordWrap(True)
        lay.addWidget(info)

        lay.addSpacing(6)
        # An explicit label above the field — the placeholder is hidden once the
        # field is pre-filled, so a visible "Preset name:" keeps it clear (#50).
        name_lbl = QLabel(tr("Preset name:"), dlg)
        lay.addWidget(name_lbl)
        edit = PrefixLockedLineEdit(dlg)
        edit.setMinimumHeight(28)
        edit.setPlaceholderText(tr("Preset name"))
        lay.addWidget(edit)
        # "Add a descriptive prefix": a preset names a CHART LAYOUT, so the
        # default comes from the layout generator (instrument · paper · patch ·
        # pages · orientation), never the printer-profile name. ON locks that as
        # a greyed prefix with a trailing '-' for a distinguishing detail; OFF
        # shows it as a plain editable name. (#70, Knut)
        preset_suffix_cb = QCheckBox(tr("Add a descriptive prefix"), dlg)
        preset_suffix_cb.setChecked(bool(self._settings.get("create_chart_auto_suffix", True)))
        preset_suffix_cb.toggled.connect(
            lambda on: self._toggle_name_prefix(edit, on, self._name_prefix()))
        suffix_row = QHBoxLayout()
        suffix_row.setContentsMargins(0, 0, 0, 0)
        suffix_row.addWidget(preset_suffix_cb)
        suffix_row.addStretch()
        suffix_row.addWidget(TooltipButton(tr("Add a descriptive prefix"),
                                           self._auto_suffix_tooltip(), dlg, min_width=520))
        lay.addLayout(suffix_row)
        # Seed the field from the chart-layout generator (not the profile name):
        # ON → "<generated>-", OFF → "<generated>" editable.
        self._toggle_name_prefix(edit, preset_suffix_cb.isChecked(), self._name_prefix())
        if prefilled_from_target:
            name_hint = QLabel(
                tr("Suggested from this chart's layout — add a detail to tell it "
                "apart from your other layout presets."),
                dlg)
            name_hint.setWordWrap(True)
            name_hint.setObjectName("info")
            lay.addWidget(name_hint)

        run_chk = QCheckBox(
            tr("Generate the chart immediately when this preset is selected"), dlg)
        run_chk.setChecked(prefill_run)
        lay.addWidget(run_chk)
        run_note = QLabel(
            tr("When on, picking this preset asks for a printer profile project name and then creates "
            "the chart straight away (it's shown with a ▶ in the list), instead of "
            "only loading the values. This is saved inside the preset file, so it "
            "travels with a shared preset."),
            dlg,
        )
        run_note.setWordWrap(True)
        run_note.setObjectName("info")
        lay.addWidget(run_note)

        lay.addSpacing(6)
        attach_chk = QCheckBox(
            tr("Build from the currently loaded patch set (attach its .ti1)"), dlg)
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
        bb.addButton(tr("Cancel"), QDialogButtonBox.ButtonRole.RejectRole)
        bb.addButton(tr("Save"), QDialogButtonBox.ButtonRole.AcceptRole)
        bb.rejected.connect(dlg.reject)
        bb.accepted.connect(dlg.accept)
        lay.addWidget(bb)
        edit.returnPressed.connect(dlg.accept)
        edit.setFocus()
        dlg.adjustSize()

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        # Normalise away invisible characters before saving / comparing: a name
        # pasted from elsewhere can carry a zero-width space (U+200B), a
        # non-breaking space, or other format/control characters that .strip()
        # leaves in place — so "MyChart" and "MyChart​" looked identical but
        # didn't match, the overwrite prompt never fired, and a duplicate was
        # created (#59). NFC-normalise and drop control/format chars on both
        # the typed name and the stored keys before comparing.
        name = _clean_preset_name(edit.text())
        if not name:
            return
        # Don't silently overwrite (or duplicate) an existing preset — ask first
        # (#59). Match on a separator-insensitive, case-insensitive key so
        # case-variants AND punctuation-variants (e.g. a dot vs the underscore
        # the name cleaning produces, "w11.5mm" vs "w11_5mm") are caught; reuse
        # the existing key so the match replaces it cleanly.
        existing = self._load_presets_from_settings()
        nkey = _preset_match_key(name)
        match = next((k for k in existing if _preset_match_key(k) == nkey), None)
        if match is not None:
            if not self._confirm_overwrite_preset(match):
                return
            name = match
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
        # Carry the chart's creation recipe (Set B) into the preset when the
        # current chart has one (e.g. applied from the editor), so it can later
        # be reloaded into the New chart window via "Load setup from preset"
        # (#55). Presets without it simply won't appear in that dropdown.
        recipe = self._current_chart_recipe()
        if recipe:
            capture["editor_recipe"] = self._recipe_synced_to_manual(recipe)
        presets = self._load_presets_from_settings()
        presets[name] = capture
        self._save_presets_to_settings(presets)
        self._populate_preset_combo(presets, select_name=name)

    def _recipe_synced_to_manual(self, recipe: dict) -> dict:
        """A copy of the chart's creation recipe (Set B) with its ``layout``
        block refreshed from the current Manual-tab printtarg settings (Set A),
        so a saved preset's two records can never disagree on scale / margin /
        density / etc. (#92).

        Only the layout (and the instrument / paper identity) sync — the
        generators, colour-set params, source mode and patch count stay frozen as
        "what was used at creation". Falls back to the recipe unchanged if the
        manual params can't be read."""
        # Engine charts: the printtarg widgets didn't produce the chart (the
        # engine recipe did, and the preset carries it as layout_recipe), so
        # syncing from them would stamp unrelated instrument/paper/layout values
        # into the recipe (#100). Keep it exactly as created.
        if bool(self._settings.get("use_chromiq_layout_engine", False)):
            return recipe
        try:
            from workflow.ti2_relayout import recipe_layout_from_options
            opts = _layout_options_from_params(self._collect_params())
        except Exception:  # noqa: BLE001 — sync is best-effort, never block save
            return recipe
        synced = dict(recipe)
        synced["layout"] = recipe_layout_from_options(opts)
        return synced

    def _current_chart_recipe(self) -> dict | None:
        """The current run's stored New-chart creation recipe (Set B), or None.

        Read from the run's ``meta.json`` (``editor_recipe``) — present for charts
        applied from the layout editor; absent for plain targen charts."""
        try:
            if not (self._file_mgr.working_dir() / "project.json").exists():
                return None
            meta = self._file_mgr.project().current_run().load_meta()
        except Exception:  # noqa: BLE001 — recipe capture is best-effort
            return None
        return meta.editor_recipe if isinstance(meta.editor_recipe, dict) else None

    def _confirm_overwrite_preset(self, name: str) -> bool:
        """Ask whether to overwrite an existing same-named preset (#59).

        Returns True to overwrite, False to cancel (the user can retry with a
        different name)."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(tr("Preset already exists"))
        box.setText(tr("A preset named “{name}” already exists. Overwrite it, "
                       "or cancel and choose a different name.").format(name=name))
        overwrite = box.addButton(tr("Overwrite"),
                                  QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        return box.clickedButton() is overwrite

    def _on_preset_delete(self) -> None:
        if not self._is_deletable_preset(self._preset_combo.currentIndex()):
            return  # Default and the built-in presets are protected
        # Use userData (bare name), not the shown text which may carry a ▶ prefix.
        name = self._preset_combo.currentData()
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Delete Preset"))
        dlg.setMinimumWidth(460)
        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setSpacing(10)
        dlg_layout.setContentsMargins(20, 20, 20, 16)
        heading = QLabel(tr("Delete the preset \"{name}\"?").format(name=name), dlg)
        heading.setStyleSheet("font-weight: bold;")
        heading.setWordWrap(True)
        dlg_layout.addWidget(heading)
        info = QLabel(
            tr("All parameter values saved in this preset will be permanently removed. "
            "This cannot be undone."),
            dlg,
        )
        info.setWordWrap(True)
        dlg_layout.addWidget(info)
        bb = QDialogButtonBox(dlg)
        bb.addButton(tr("Cancel"), QDialogButtonBox.ButtonRole.RejectRole)
        bb.addButton(tr("Delete"), QDialogButtonBox.ButtonRole.AcceptRole)
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

    def _seed_manual_printtarg_from_layout(self, opts) -> None:
        """Reflect an editor ``LayoutOptions`` bundle onto the manual printtarg
        panel so a chart handed over from the layout editor shows the exact
        knobs it was laid out with — patch scale (-a), spacer scale (-A),
        margin (-m), spacers (-b/-n), double/triple density, DPI and bit depth,
        -L/-P — not just instrument + paper.

        The panel is locked right after this, so the seeding is display-faithful
        (the override boxes let the user unlock and edit). Scalar expert rows
        mirror :meth:`LayoutOptions.to_printtarg_args`' default-suppression: a
        row at its default value is reset (disabled) rather than spuriously
        enabled, so the panel reads exactly like the flags printtarg received.
        """
        # Spacers: at most one of -b / -n; "colored" leaves both off.
        self._set_manual_value("printtarg", "-b", opts.spacer_mode == "bw")
        self._set_manual_value("printtarg", "-n", opts.spacer_mode == "none")
        # DPI + bit depth.
        self._set_manual_value("printtarg", "-t", opts.dpi)
        if self._bit16_radio is not None and self._bit8_radio is not None:
            (self._bit16_radio if opts.tiff_16bit
             else self._bit8_radio).setChecked(True)
        # Triple density FIRST: its toggle handler re-applies the canonical
        # i1Pro-layout preset (-a1.3 / -m5 / -P / -L), so it must run *before* the
        # margin / patch-scale / spacer / -L / -P rows below — otherwise it would
        # clobber the editor's real values with the TD defaults. Knut's #45: a
        # triple-density chart laid out at margin 6 / patch-scale 1.06 came back
        # as margin 5 / 1.30 because TD ran last and overwrote them.
        if self._manual_td_check is not None:
            self._manual_td_check.setChecked(bool(opts.triple_density))
        # Strip-reader / density booleans (override any TD preset above).
        self._set_manual_value("printtarg", "-L", opts.suppress_left_clip)
        self._set_manual_value("printtarg", "-P", opts.no_strip_limit)
        self._set_manual_value("printtarg", "-h", opts.double_density)
        # The layout editor always lays its charts out in fixed order
        # (printtarg -r — see workflow/ti2_relayout.py), so the applied chart is
        # "preserve patch order". Reflect that on the panel and in the baseline:
        # otherwise -r sits at its factory default and unchecking Preserve Patch
        # Order to get randomisation reads as "no change", so Generate copies the
        # fixed-order files verbatim and the chart is never randomised (the
        # randomisation only appeared as a side effect of toggling another knob).
        self._set_manual_value("printtarg", "-r", True)
        # Scalar expert rows: set+enable only when non-default, else reset. These
        # run last so the chart's actual patch/spacer scale and margin win over
        # the triple-density preset applied above.
        if abs(opts.patch_scale - 1.0) > 0.01:
            self._set_manual_value("printtarg", "-a", opts.patch_scale)
        else:
            self._reset_manual_value("printtarg", "-a")
        if abs(opts.spacer_scale - 1.0) > 0.01:
            self._set_manual_value("printtarg", "-A", opts.spacer_scale)
        else:
            self._reset_manual_value("printtarg", "-A")
        # Margin is always a deliberate layout choice in the editor, so show it
        # enabled even at the default 6 mm. Suppressing it left the Create Chart
        # margin row unticked after Save & apply, reading as "no margin set" (#61).
        self._set_manual_value("printtarg", "-m", opts.margin_mm)

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
        # An applied editor chart — or a chart reflected from the Print/Measure
        # tab — locks both panels exactly like a prebuilt-files preset (the
        # patches AND the layout are fixed until the user opts in).
        prebuilt = self._prebuilt_active or self._applied_active or self._reflected_active
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
        # When a preset locks the recipe, collapse the targen frame while it's
        # locked and expand it the moment the user ticks "Edit patch recipe", so
        # the now-editable controls come into view (Knut). Outside a lock the
        # frame keeps its own collapsed-by-default / user-clicked state.
        tgrp = getattr(self, "_manual_targen_grp", None)
        if tgrp is not None and show_targen_cb:
            tgrp.set_collapsed(not targen_unlocked)

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
        # A newly selected preset starts fully branded again.
        self._vendor_debranded = False

    def _on_override_clicked(self, tool: str, checked: bool) -> None:
        """User ticked/unticked an override box — warn (once) when unlocking.

        Fires only on real clicks (not programmatic setChecked), so the warning
        pop-up appears exactly when the user themselves unlocks a panel."""
        if not checked:
            return
        if tool == "targen":
            InfoDialog(tr(_OVERRIDE_TARGEN_POPUP_TITLE), tr(_OVERRIDE_TARGEN_POPUP_BODY),
                       self, min_width=560).exec()
            # Editing the patch recipe drops the vendor identity: once the locked
            # patch set can be changed, the chart is no longer that vendor's
            # certified set, so its branding must not stay on it. Revert a
            # branded clip band (a bundled vendor logo) to ChromIQ's own notes
            # record — no vendor logo / text remains on the chart.
            self._debrand_on_override()
        else:
            InfoDialog(tr(_OVERRIDE_PRINTTARG_POPUP_TITLE), tr(_OVERRIDE_PRINTTARG_POPUP_BODY),
                       self, min_width=560).exec()

    def _debrand_on_override(self) -> None:
        """Strip a vendor preset's branding from the layout when the user unlocks
        the patch recipe: a bundled-logo clip band (clip_content_mode "image")
        reverts to ChromIQ's regular chart-notes clip border, so nothing on the
        chart still names the vendor."""
        key = getattr(self, "_knut_active_key", None)
        p = KNUT_PRESETS_BY_KEY.get(key or "")
        branded = bool(
            p is not None and p.layout_recipe
            and p.layout_recipe.get("clip_content_mode") == "image")
        if not branded:
            return
        # Drop the vendor identity from the layout-name stamp too (the "Chart
        # layout <name>" text on the sheet edge), not just the clip logo.
        self._vendor_debranded = True
        panel = getattr(self, "_manual_layout_panel", None)
        if panel is None:
            return
        rec = self._current_layout_recipe()
        if rec is None:
            return
        from dataclasses import replace
        panel.set_recipe(replace(
            rec,
            clip_content_mode="notes",   # ChromIQ's own record, not a vendor logo
            clip_image_path="",
            clip_image_rotation=0,
            clip_border_width_mm=26.0,    # the regular clip-border width
        ))

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

        # The chart is built under the current Printer-profile name; the preset
        # never overwrites it (#70). Only seed a name if the field is still empty.
        self._ensure_profile_name(target_name or TC918_TARGET_NAME)

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

        # Built under the current Printer-profile name; the preset never
        # overwrites it (#70). Seed a name only when the field is still empty.
        self._ensure_profile_name(target_name or f"ColorMunki-{patches}")

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

    def _fls_engine_recipe(self, p: "_Ti1Preset"):
        """The layout-engine recipe for a Full-layout-setup ENGINE preset,
        derived from the preset's own printtarg fields.

        Built from the exact same mapping the engine build uses
        (`ChartCreator._engine_build_kwargs`), so the engine reproduces
        printtarg byte-for-byte (verified for all 11 engine presets). We add the
        explicit per-edge ``margins`` (the mapping only emits ``border``) so the
        recipe round-trip keeps the preset's margin instead of defaulting to
        6 mm."""
        from workflow.chart_creator import ChartParams
        from workflow.layout_engine.presets import LayoutRecipe
        params = ChartParams(
            instrument=p.instrument, paper=p.paper, is_manual=True,
            tiff_dpi=KNUT_DPI, tiff_16bit=p.tiff_16bit,
            patch_scale=p.patch_scale, margin_mm=p.margin,
            triple_density=p.triple_density, double_density=p.double_density,
            disable_left_border=p.suppress_left_clip,
            no_strip_limit=p.no_strip_limit)
        kw = self._creator._engine_build_kwargs(params)
        kw["margins"] = (float(p.margin),) * 4
        kw["dpi"] = KNUT_DPI
        r = LayoutRecipe.from_build_kwargs(kw)
        r.instrument, r.paper = p.instrument, p.paper
        return r

    def _seed_knut_preset(self, key: str, target_name: str | None = None) -> None:
        """Load a TC9.18+Spyderprint preset's fixed printtarg layout into the panel.

        Sets every printtarg control the recipe touches (and resets the optional
        -A / -R rows when it doesn't), so the layout is fully determined no matter
        which preset was selected before. Split from _apply_knut_preset so it can
        be unit-tested without running printtarg."""
        p = KNUT_PRESETS_BY_KEY[key]
        triple = p.triple_density and p.instrument == "CM"

        # Clear modes that would otherwise hijack the seeded printtarg values.
        if self._manual_td_check is not None:
            self._manual_td_check.setChecked(False)
        if self._manual_auto_patches_check is not None:
            self._manual_auto_patches_check.setChecked(False)
            self._on_auto_patches_toggled(False)
        self._load_auto_neutral_states(grey=False, white=False, black=False)

        if p.layout_recipe is not None or p.engine:
            # Engine preset — the ChromIQ layout engine lays the bundled patch
            # set out, so seed the layout panel with the recipe instead of the
            # (hidden) printtarg widgets. The engine toggle is already on
            # (_on_preset_selected sets it before dispatching here). Scanner
            # presets carry an explicit recipe; the Full-layout-setup engine
            # presets derive theirs from their printtarg fields, reproducing
            # printtarg exactly (verified) but on the native engine path (#63).
            if getattr(self, "_manual_layout_panel", None) is not None:
                from workflow.layout_engine.presets import LayoutRecipe
                recipe = (LayoutRecipe.from_dict(p.layout_recipe)
                          if p.layout_recipe is not None
                          else self._fls_engine_recipe(p))
                self._manual_layout_panel.set_recipe(recipe)
                self._manual_layout_panel.set_pages(p.pages)
            if self._bit16_radio is not None and self._bit8_radio is not None:
                (self._bit16_radio if p.tiff_16bit
                 else self._bit8_radio).setChecked(True)
            # Descriptive targen values (the bundled .ti1 is the real source).
            self._set_manual_value("targen", "-f", p.patches)
            self._set_manual_value("targen", "-e", p.white)
            self._set_manual_value("targen", "-B", p.black)
            if self._manual_pages_spin is not None:
                self._manual_pages_spin.setValue(p.pages)
            self._ensure_profile_name(target_name or p.default_target_name)
            return

        # Instrument first — it drives -h visibility and the per-instrument
        # default margin; we set the margin explicitly afterwards so ours wins.
        self._set_manual_value("printtarg", "-i", p.instrument)
        self._set_manual_value("printtarg", "-p", p.paper)
        self._set_manual_value("printtarg", "-t", KNUT_DPI)        # dpi (with -T)
        if self._bit16_radio is not None and self._bit8_radio is not None:
            (self._bit16_radio if p.tiff_16bit
             else self._bit8_radio).setChecked(True)               # -T (16-bit) / 8-bit
        # Triple density BEFORE the scalar rows: its toggle handler seeds
        # -a1.3/-m5/-P/-L, so it must run first or it would clobber the recipe's
        # own -a/-m below (the #45 ordering). Instrument is already CM, so the
        # TD row is visible/settable here.
        if triple and self._manual_td_check is not None:
            self._manual_td_check.setChecked(True)
        self._set_manual_value("printtarg", "-a", p.patch_scale)
        self._set_manual_value("printtarg", "-P", p.no_strip_limit)  # don't limit strips
        self._set_manual_value("printtarg", "-m", p.margin)        # → -m/-M
        self._set_manual_value("printtarg", "-L", p.suppress_left_clip)  # left clip border
        self._set_manual_value("printtarg", "-r", p.no_randomise)  # preserve order? (default: randomise)
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
        self._set_manual_value("targen", "-f", p.patches)
        self._set_manual_value("targen", "-e", p.white)
        self._set_manual_value("targen", "-B", p.black)

        if self._manual_pages_spin is not None:
            self._manual_pages_spin.setValue(p.pages)
        self._ensure_profile_name(target_name or p.default_target_name)

    def _apply_knut_preset(self, key: str, target_name: str | None = None) -> None:
        """Seed a TC9.18+Spyderprint preset and build it from the bundled .ti1."""
        if self._runner.is_running:
            log.warning("Knut preset: a process is already running")
            return
        ti1 = resource_path(KNUT_PRESETS_BY_KEY[key].ti1_asset)
        if not ti1.is_file():
            InfoDialog(
                "Patch set not found",
                "The bundled patch set for this preset could not be "
                f"located:\n\n{ti1}\n\nThe app bundle may be incomplete.",
                self, min_width=520,
            ).exec()
            return
        self._seed_knut_preset(key, target_name)
        self._knut_active = True
        self._knut_active_key = key
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

    def _leave_applied(self) -> None:
        """Clear applied-editor-chart state and re-enable the param panels."""
        self._applied_active = False
        self._applied_src_dir = None
        self._applied_stem = None
        self._applied_targen_sig = None
        self._applied_printtarg_sig = None
        self._reset_override_checks()
        self._update_preset_locks()

    def _leave_reflected(self) -> None:
        """Clear the reflected-chart state and re-enable the param panels."""
        self._reflected_active = False
        self._reflected_ti2 = None
        self._reset_override_checks()
        self._update_preset_locks()

    def _apply_loaded_chart_settings(self, sidecar: Path) -> bool:
        """Take a loaded patch set's chart-settings file and put those settings
        on screen, so the sheet is rebuilt as it was laid out (#130, Knut).

        :meth:`_restore_chart_settings` is written around a chart's ``.ti2``
        because that is where a patch count can also be read; here only the
        sidecar exists, so it is addressed by the stem the two share.
        """
        try:
            return self._restore_chart_settings(
                Path(sidecar).with_suffix("").with_suffix(".ti2"))
        except Exception:      # noqa: BLE001 — a bad sidecar must not block a load
            log.warning("Could not apply the loaded chart's settings from %s",
                        sidecar, exc_info=True)
            return False

    def _show_loaded_page_count(self, tiffs: "list[Path]",
                                ti2_path: Path) -> None:
        """Put the loaded chart's real number of pages in the pages field.

        Counted from what is actually there — the page images first, and the
        chart's own patch geometry as a fallback when a chart is shown before
        its pages have been rendered. Best-effort: a field that cannot be set
        is never worth failing a chart load over.
        """
        try:
            pages = len([t for t in tiffs if t.exists()])
            if not pages:
                import json as _json
                sidecar = ti2_path.with_suffix("").with_suffix(".channels.json")
                if not sidecar.exists():
                    sidecar = ti2_path.parent / f"{ti2_path.stem}.channels.json"
                if sidecar.exists():
                    layout = _json.loads(sidecar.read_text()).get("layout", {})
                    pages = 1 + max((int(p.get("page", 0))
                                     for p in layout.get("patches") or []),
                                    default=-1)
            # Read for the log only — and defensively, because a diagnostic
            # must never be able to stop the thing it is describing.
            try:
                before = self._manual_pages_spin.value()
            except Exception:      # noqa: BLE001
                before = None
            if pages > 0 and self._manual_pages_spin is not None:
                self._manual_pages_spin.setValue(int(pages))
            if pages > 0 and getattr(self, "_pages_spin", None) is not None:
                self._pages_spin.setValue(int(pages))
            # Knut asked me to find the stuck "pages = 20" in his log and it was
            # not there to find: ChromIQ never recorded the page count, so no
            # log could show what it held or who set it (#130, 2026-07-29).
            # It does now.
            log.info("chart loaded: %s page(s) counted from %s "
                     "(field was %s, now %s)", pages,
                     "the page images" if tiffs else "the patch geometry",
                     before, pages if pages > 0 else before)
        except Exception:      # noqa: BLE001 — never block a chart load
            log.warning("could not show the loaded chart's page count",
                        exc_info=True)

    def _restore_chart_settings(self, ti2_path: Path) -> bool:
        """Fill the Create-Chart options with the settings the loaded chart
        was actually made with, so what's on screen matches the chart —
        instead of whatever the panels happened to hold (mavtop, forum: a
        reloaded chart showed default patch counts, empty notes, seed 0…).

        Engine charts carry their complete layout recipe in the chart's own
        ``channels.json`` (patch size, spacers, margins, seed, notes,
        alignment — everything), so those restore fully: the engine toggle
        comes on, the layout panel takes the recipe, the pages/notes fields
        follow, and the patch count is pinned to the chart's real total.
        printtarg charts store no recipe — only instrument/paper (seeded by
        the callers) and the patch count can be recovered. Returns True when
        a full recipe was restored.

        Newer sidecars additionally carry ``chart_notes`` and
        ``stamp_commands`` (both chart kinds — the TIFF stamp itself can't be
        read back), restored gated on key presence so older charts keep the
        fields untouched; ``self._restored_notes_stamp`` tells the caller
        whether they were, for an accurate log line (mavtop, forum)."""
        import json as _json
        import re as _re
        # Forget the previous chart's recipe first: a chart that carries none
        # must not inherit the last one's layout (it would be rebuilt as some
        # other sheet entirely).
        self._restored_exact_recipe = None
        self._restored_chart_date = ""
        # Patch count from the .ti2 itself — works for every chart kind.
        try:
            txt = Path(ti2_path).read_text(errors="replace")
            m = _re.search(r"NUMBER_OF_SETS\s+(\d+)", txt)
            if m:
                self._set_manual_value("targen", "-f", int(m.group(1)))
                if self._manual_auto_patches_check is not None:
                    # Pin the count: with Auto on it would be recomputed from
                    # the layout and drift away from the loaded chart's total.
                    self._manual_auto_patches_check.setChecked(False)
        except Exception:  # noqa: BLE001 — count seeding is best-effort
            log.warning("could not seed patch count from %s", ti2_path,
                        exc_info=True)
        sidecar = Path(ti2_path).with_suffix(".channels.json")
        self._restored_notes_stamp = False
        if not sidecar.is_file():
            return False
        try:
            doc = _json.loads(sidecar.read_text())
        except Exception:  # noqa: BLE001 — never block a load on a bad sidecar
            log.warning("could not restore chart settings from %s", sidecar,
                        exc_info=True)
            return False
        restored_full = False
        try:
            layout = doc.get("layout") or {}
            rec_dict = layout.get("recipe") or {}
            if rec_dict:
                from workflow.layout_engine.presets import LayoutRecipe
                recipe = LayoutRecipe.from_dict(rec_dict)
                # The seed the chart was ACTUALLY built with (Knut, #130
                # 2026-07-27: "the random seed must survive the restore and
                # regeneration of the chart image"). The recipe records what
                # the user asked for — and "draw a fresh one each time" is
                # written there as no seed at all, so rebuilding from the
                # recipe alone shuffles the patches differently and the sheet
                # that comes back is not the sheet that was measured. The
                # build writes the drawn number one level up, and that is the
                # one that reproduces this chart.
                if isinstance(layout.get("seed"), int):
                    recipe.seed = int(layout["seed"])
                # Keep the recipe EXACTLY as the chart recorded it, before any
                # widget has rounded it and before Preferences has had its say.
                # A rebuild that must reproduce this chart reads this, not the
                # panel — see _restored_exact_recipe's use in the Restore path.
                self._restored_exact_recipe = recipe
                self._restored_chart_date = (
                    str(layout.get("date") or "")
                    or _chart_date_from_ti2(Path(ti2_path)))
                # Engine on first (builds/updates the panel), then the recipe.
                if (self._manual_engine_check is not None
                        and not self._manual_engine_check.isChecked()):
                    self._manual_engine_check.setChecked(True)
                if self._manual_layout_panel is not None:
                    self._manual_layout_panel.set_recipe(recipe)
                n_pages = 1 + max((int(p.get("page", 0))
                                   for p in layout.get("patches") or []),
                                  default=0)
                if self._manual_pages_spin is not None:
                    self._manual_pages_spin.setValue(n_pages)
                if (self._manual_chart_notes_edit is not None
                        and "chart_notes" not in doc
                        and getattr(recipe, "chart_text", "")):
                    # Sidecar predates the chart_notes key: the recipe's
                    # on-sheet text is the only note-like value left to show.
                    self._manual_chart_notes_edit.setText(recipe.chart_text)
                restored_full = True
        except Exception:  # noqa: BLE001 — never block a load on a bad sidecar
            log.warning("could not restore chart settings from %s", sidecar,
                        exc_info=True)
        # Chart notes + stamp choice — recorded for BOTH chart kinds. A
        # missing key means an older chart: leave the fields untouched.
        # Applied AFTER the engine toggle above, which resets the stamp
        # checkbox to its mode default (_refresh_manual_command_preview)
        # and would overwrite anything set earlier.
        try:
            if ("chart_notes" in doc
                    and self._manual_chart_notes_edit is not None):
                self._manual_chart_notes_edit.setText(
                    str(doc.get("chart_notes") or ""))
                self._restored_notes_stamp = True
            if ("stamp_commands" in doc
                    and self._manual_stamp_cmd_check is not None):
                self._manual_stamp_cmd_check.setChecked(
                    bool(doc.get("stamp_commands")))
                self._restored_notes_stamp = True
        except Exception:  # noqa: BLE001
            log.warning("could not restore notes/stamp from %s", sidecar,
                        exc_info=True)
        # printtarg charts carry no layout recipe, but they DO save their
        # printtarg parameter fields (margins, patch scale, spacers, …). Restore
        # them so toggling between two charts shows EACH chart's own printtarg
        # settings, not whichever preset was loaded last (#130 Bug 1, Knut).
        if not restored_full:
            # This chart was drawn by printtarg: an engine chart always embeds
            # its recipe, and a sidecar with no recipe therefore describes a
            # printtarg layout. So the engine toggle has to come OFF, exactly as
            # it comes ON for an engine chart a few lines above.
            #
            # Knut, #130 2026-07-29, naming the case he had suspected all along:
            # *"if the stored chart in chart/ folder was made with printtarg
            # layout engine, and I change the Create Chart manual mode parameters
            # for ChromIQ layout engine, then settings from both layout engines
            # should be restored when clicking Restore Used Chart."* With the
            # engine left on, the printtarg fields restored on the next line were
            # simply ignored — `_collect_params` reads whichever engine is
            # selected — so the options on screen did not describe the stored
            # chart at all. That is the asymmetry: restoring an engine chart
            # switched the engine on, restoring a printtarg chart left it on too.
            if (self._manual_engine_check is not None
                    and self._manual_engine_check.isChecked()):
                self._manual_engine_check.setChecked(False)
        # BOTH chart kinds get their printtarg fields back, not just printtarg
        # charts. On an engine chart these values are inert — the engine lays
        # the sheet out and the printtarg panel is hidden — but they are still
        # *recorded* in the sidecar, and leaving them alone meant a rebuild
        # wrote whatever the panel happened to hold. The sidecar then differed
        # from the stored one, the rebuild guard reported that the chart had
        # been altered, and the warning was about nothing: the layout was
        # identical and only this dormant history had moved (#130, seen while
        # reproducing Knut's Second-Project-R restore).
        self._restore_printtarg_fields(doc.get("printtarg_fields"))
        return restored_full

    def _snapshot_printtarg_fields(self) -> list:
        """The current manual printtarg fields as ``[{flag, value, enabled}]`` —
        saved with each chart so it can be shown exactly when reloaded (#130)."""
        out = []
        for pw in self._manual_widgets.get("printtarg", []):
            try:
                out.append({"flag": pw.flag, "value": pw.get_raw_value(),
                            "enabled": bool(pw.is_enabled_by_user)})
            except Exception:  # noqa: BLE001
                pass
        return out

    def _restore_printtarg_fields(self, fields) -> None:
        """Apply saved printtarg field values (from :meth:`_snapshot_printtarg_
        fields`) to the manual printtarg panel (#130 Bug 1)."""
        if not fields:
            return
        by_flag = {pw.flag: pw for pw in self._manual_widgets.get("printtarg", [])}
        for f in fields:
            pw = by_flag.get(f.get("flag"))
            if pw is None:
                continue
            try:
                pw.set_value(f.get("value"))
                pw.set_user_enabled(bool(f.get("enabled")))
            except Exception:  # noqa: BLE001 — one bad field must not abort
                pass

    def _store_printtarg_fields_in_sidecar(self, ti2: "Path | None") -> None:
        """Merge the current printtarg fields into a chart's channels.json so a
        later load restores them (#130 Bug 1). Best-effort; never raises."""
        if not ti2:
            return
        sidecar = Path(ti2).with_suffix(".channels.json")
        try:
            doc = json.loads(sidecar.read_text()) if sidecar.is_file() else {}
        except Exception:  # noqa: BLE001
            doc = {}
        doc["printtarg_fields"] = self._snapshot_printtarg_fields()
        try:
            sidecar.write_text(json.dumps(doc))
        except Exception:  # noqa: BLE001
            log.warning("could not store printtarg fields in %s", sidecar)

    def reflect_loaded_chart(self, ti2_path: Path, tiffs: list[Path]) -> None:
        """Mirror a chart loaded in the Print/Measure tab, read-only.

        Called by the main window when the user clicks "Load .ti2" in Print or
        Measure. Shows the chart's pages here with both panels greyed (so it's
        clear the loaded layout is what's active), WITHOUT copying anything or
        creating a project — the chart already lives in its own folder. A
        one-time note explains that the previously-shown layout is preserved.
        """
        ti2_path = Path(ti2_path)
        self._switch_mode("manual")
        # Drop any other fixed-layout binding for a consistent lock state.
        self._tc918_active = False
        self._tc918_targen_sig = None
        self._knut_active = False
        self._knut_targen_sig = None
        self._preset_ti1_path = None
        self._preset_ti1_targen_sig = None
        # A reflected chart replaces whatever was loaded; drop the built-in's
        # bundled .ti1 too, or its patch count would shadow the live chart in
        # the Save-Preset name suggestion (_loaded_ti1_patch_count, Knut).
        self._builtin_ti1_path = None
        self._pending_editor_recipe = None   # reflected chart carries its own meta
        if self._prebuilt_active:
            self._leave_prebuilt()
        if self._applied_active:
            self._leave_applied()
        self._reflected_active = True
        self._reflected_ti2 = ti2_path
        self._reset_override_checks()
        # Seed the instrument + page the chart was laid out for, so an
        # unlock-and-edit starts from the right device/paper.
        try:
            from workflow.ti2_relayout import ChartSpec
            spec = ChartSpec.from_ti2(ti2_path)
            self._set_manual_value("printtarg", "-i", spec.instrument_flag)
            self._set_manual_value("printtarg", "-p", spec.paper_flag)
        except Exception as exc:  # noqa: BLE001 — seeding is best-effort
            log.warning("Could not seed instrument/paper from reflected chart: %s", exc)
        # Bring the option panels to the chart's own creation settings BEFORE
        # locking, so the greyed panels show the truth about this chart —
        # and an unlock-and-edit really does start "from these settings", as
        # the loaded-chart dialog promises (mavtop, forum).
        self._restore_chart_settings(ti2_path)
        # A reflected chart is shown for reference only and never overwrites the
        # user's Printer-profile name (#70); seed it only if the field is empty.
        self._ensure_profile_name(ti2_path.stem)
        self._update_preset_locks()      # grey both panels
        self._log.clear()
        self._log.appendPlainText(
            f"Reflecting loaded chart “{ti2_path.name}” "
            f"({count_phrase(len(tiffs), tr('1 page'), tr('{n} pages'))}). "
            + tr("Loaded for reference only — not generated.")
        )
        if Path(ti2_path).with_suffix(".channels.json").is_file():
            self._log.appendPlainText(tr(
                "The locked panels show the settings this chart was made "
                "with — tick “Edit patch recipe (override preset)” or “Edit "
                "page layout (override preset)” to build a new chart starting "
                "from them."))
        if tiffs:
            self._preview.load_tiff(list(tiffs))
            self._set_margin_chart(list(tiffs), ti2_path)
        else:
            self._preview.clear()
            self._set_margin_chart([], None)
        # Estimate column follows the restored settings (set_recipe applies
        # silently, and the margin chart — the estimate's patch-count anchor
        # — only landed just above).
        self._refresh_manual_command_preview()
        self._maybe_warn_reflected_backfill(ti2_path)

    def announce_duplicated_run(self, ti2_path: Path, run_label: str,
                                source_label: str) -> None:
        """Say what a Duplicate just did — in the words of a duplicate.

        Knut, #130 2026-08-01, on the window that used to appear here: *"Why
        mention safe in its own project folder, or that ti2 file can be opened
        again from Print or Measure?? First, Duplicate action was performed, so
        we are still inside the same open project. No need to say it is safe."*
        He is right; that text is written for a chart loaded from elsewhere, and
        every reassurance in it answers a worry a duplicate does not raise.

        He also caught the last paragraph describing how to build a new chart
        from these settings — *"This sounds like creating a verification run
        chart, without mentioning that it is, and that run type must be set
        correctly to do so."* So the verification route is named explicitly,
        with the step that actually matters.
        """
        if bool(self._settings.get("duplicate_notice_hide", False)):
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Your duplicated run is ready"))
        dlg.setMinimumWidth(560)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 20, 24, 16)
        lay.setSpacing(12)
        heading = QLabel(
            tr("{run} is a copy of {source}, and it is now the run you are "
               "working in").format(run=run_label, source=source_label), dlg)
        heading.setWordWrap(True)
        heading.setStyleSheet("font-weight: 600; font-size: 14px;")
        lay.addWidget(heading)
        body = QLabel(
            tr("Create Chart is showing the copied chart — “{name}” — and the "
               "Print and Measure tabs are on it too, so every tab is working "
               "on the new run.\n\n"
               "{source} has not changed. Its chart, its measurement and its "
               "profile are exactly as they were, and you can go back to it at "
               "any time from the “Profile run” box.\n\n"
               "WHAT YOU CAN DO NOW\n"
               "•  Measure this chart again — the copied measurement is here, "
               "so tick “Refine / resume existing measurement” to add to it, or "
               "leave it unticked to start fresh.\n"
               "•  Build a different profile from the copied measurement, on "
               "the Build Profile tab.\n"
               "•  Give this run a different verification chart: set “Run "
               "type” to “Verification” first, then create the chart — the "
               "copy deliberately starts with none, which is why duplicating "
               "is the way to change one.").format(name=ti2_path.name), dlg)
        body.setWordWrap(True)
        lay.addWidget(body)
        hide_cb = QCheckBox(tr("Don't show this again"), dlg)
        lay.addWidget(hide_cb)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, dlg)
        bb.accepted.connect(dlg.accept)
        lay.addWidget(bb)
        dlg.exec()
        if hide_cb.isChecked():
            self._settings.set("duplicate_notice_hide", True)

    def _ti2_is_inside_current_project(self, ti2_path: Path) -> bool:
        """Whether *ti2_path* already lives under the project that is open.

        Used to keep the "loaded chart is now shown here" window for the case
        it was written for — a chart brought in from somewhere else — and out
        of the case where the user simply picked a file the project already
        owned.
        """
        try:
            project = self._file_mgr.project()
            root = getattr(project, "root", None) or getattr(project, "dir", None)
            if root is None:
                return False
            return Path(root).resolve() in Path(ti2_path).resolve().parents
        except Exception:      # noqa: BLE001 — a missing project is not "inside"
            return False

    def _maybe_warn_reflected_backfill(self, ti2_path: Path) -> None:
        """One-time, friendly heads-up that a loaded chart now shows here.

        Skipped after a Duplicate: that path shows its own window, because this
        one is written for a chart loaded from somewhere else and every
        reassurance in it is wrong for a copy made inside the open project
        (Knut, #130 2026-08-01 — see :meth:`announce_duplicated_run`).
        """
        if getattr(self, "_suppress_reflect_notice", False):
            return
        if bool(self._settings.get("reflect_backfill_hide_warning", False)):
            return
        # Nothing was imported, so there is nothing to announce. Knut, #130
        # beta.120: choosing a .ti2 that already lives in the open project and
        # picking "Continue" copies no files and moves nothing — *"This is
        # strange, as no import action was performed in this case, so this
        # window could be removed"*. Same reasoning as the Duplicate skip above.
        if self._ti2_is_inside_current_project(ti2_path):
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Loaded chart is now shown in Create Chart"))
        dlg.setMinimumWidth(560)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 20, 24, 16)
        lay.setSpacing(12)
        heading = QLabel(
            tr("The chart you just loaded is now also shown in “Create Chart”"),
            dlg)
        heading.setWordWrap(True)
        heading.setStyleSheet("font-weight: 600; font-size: 14px;")
        lay.addWidget(heading)
        body = QLabel(
            tr("So every tab agrees on what you're working with, the Create "
               "Chart tab now mirrors this loaded chart — “{name}”. Its patch "
               "recipe and page layout are shown locked, because the chart "
               "already exists; ChromIQ won't change it.\n\n"
               "Nothing you built before is lost: any chart you'd generated "
               "earlier is still safe in its own project folder under "
               "~/ChromIQ, and you can open it again at any time with “Open "
               "Chart File (.ti2)” at the top left of the window.\n\n"
               "If you'd like to build a NEW chart starting from these "
               "settings, tick the “Edit patch recipe (override preset)” or "
               "“Edit page layout (override preset)” checkbox in the Create "
               "Chart tab, make your changes, and click “Generate Chart” — the "
               "loaded chart stays untouched. For charts made with the ChromIQ "
               "layout engine, "
               "the panels really do show the chart's own creation settings "
               "— patch size, spacers, margins, seed, notes and patch count "
               "are all restored from the chart itself.").format(name=ti2_path.name),
            dlg)
        body.setWordWrap(True)
        lay.addWidget(body)
        hide_cb = QCheckBox(tr("Don't show this again"), dlg)
        lay.addWidget(hide_cb)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, dlg)
        bb.accepted.connect(dlg.accept)
        lay.addWidget(bb)
        dlg.exec()
        if hide_cb.isChecked():
            self._settings.set("reflect_backfill_hide_warning", True)

    def apply_external_chart(self, src_dir: Path, name: str) -> bool:
        """Adopt a chart the TI2 layout editor just wrote into ``src_dir``.

        Called by the main window when the user clicks **Overwrite** in the
        editor's "Apply / Save" window (#70, Knut's model). ``src_dir`` is a
        staging folder holding ``<name>.ti1`` / ``.ti2`` / ``<name>_NN.tif`` /
        ``meta.json`` — ``name`` is only the chart-*layout* file stem, NOT the
        profile name. The chart is imported into the **current** Create Chart
        profile (replacing the chart loaded there); the profile name is never
        changed. Both param panels are greyed so the applied patches and layout
        can't be overwritten by accident — the override boxes let the user opt
        back in, exactly like a prebuilt preset.

        Returns True (applied).
        """
        src_dir = Path(src_dir)
        # Applied charts always land in the manual module (the override boxes and
        # locked panels only exist there).
        self._switch_mode("manual")
        # Drop any other fixed-layout binding so the locks stay consistent.
        self._tc918_active = False
        self._tc918_targen_sig = None
        self._knut_active = False
        self._knut_targen_sig = None
        self._preset_ti1_path = None
        self._preset_ti1_targen_sig = None
        # The applied editor chart becomes the live chart; clear the built-in's
        # bundled .ti1 too. Otherwise its patch count shadows the applied chart
        # in the Save-Preset name suggestion (_loaded_ti1_patch_count checks
        # _builtin_ti1_path before _current_ti1_path) — Knut's 1168-vs-1575 bug.
        self._builtin_ti1_path = None
        # Carry the applied chart's creation recipe (Set B) along: the editor
        # writes it into the staging folder's meta.json, and only this pending
        # slot gets it into the regenerated run's meta.json (_stamp_chart_meta).
        # Without it the New-patch-set design is lost on apply, so presets saved
        # from the run can't reload it into the editor (#100).
        from workflow.ti2_relayout import load_editor_recipe
        rec = load_editor_recipe(src_dir / f"{name}.ti2")
        self._pending_editor_recipe = rec if isinstance(rec, dict) and rec else None
        if self._prebuilt_active:
            self._leave_prebuilt()
        if self._reflected_active:
            self._leave_reflected()
        # Create Chart OWNS the layout (Knut #93): applying takes only the editor's
        # PATCH SET (the .ti1) and lays it out with the layout currently set here —
        # it never changes your instrument / paper / margins / patch size. So we
        # adopt the .ti1 as the patch source (the same mechanism a bundled-.ti1
        # preset uses: patch set fixed, layout fully editable) and regenerate. We
        # do NOT seed or lock the editor's layout, and the layout panels stay live.
        self._applied_active = False
        ti1 = src_dir / f"{name}.ti1"
        if not ti1.is_file():
            log.warning("Applied patch set has no .ti1: %s", ti1)
            return False
        import shutil
        try:
            dest = self._file_mgr.working_dir() / "edited_patch_set.ti1"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ti1, dest)
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not stage the edited patch set: %s", exc)
            return False
        self._preset_ti1_path = dest
        self._preset_ti1_targen_sig = self._targen_signature()
        # Never overwrite the user's profile name — only seed it when empty.
        self._ensure_profile_name(name)
        self._reset_override_checks()
        self._update_preset_locks()
        # Lay the patch set out NOW with the current Create Chart layout.
        self._generate_from_ti1(dest)
        return True

    def _carry_engine_recipe_from(self, channels_json) -> None:
        """Carry an adopted chart's engine recipe back into Create Chart (#93).

        If *channels_json* holds a ChromIQ-engine recipe, turn the engine on and
        seed the Manual engine panel so the options chosen in the editor come
        back here; otherwise make sure the engine is off so the printtarg seeding
        shows. Best-effort — never blocks adopting the chart.
        """
        try:
            from workflow.layout_engine.presets import LayoutRecipe
            eng = LayoutRecipe.from_channels_json(channels_json)
            self._settings.set("use_chromiq_layout_engine", eng is not None)
            self._refresh_manual_command_preview()
            if eng is not None and getattr(self, "_manual_layout_panel", None) is not None:
                self._manual_layout_panel.set_recipe(eng)
        except Exception as exc:  # noqa: BLE001 — carry-back is best-effort
            log.warning("Could not carry engine recipe back from editor: %s", exc)

    def _import_applied_chart(self, add_new_run: bool = False) -> None:
        """Copy the applied editor chart's files into the current run and load it.

        No targen/printtarg is run: the staged ``.ti1`` / ``.ti2`` / TIFF pages
        are copied into runs/<current>/ under the fixed ``chart`` stem and the
        TIFFs are shown in the preview, then routed downstream like any chart.
        The editor's richer ``meta.json`` (full layout) is copied in afterwards
        so reopening the run restores it exactly as the editor saved it.
        """
        import shutil
        if self._runner.is_running:
            log.warning("Applied chart: a process is already running")
            return
        if self._applied_src_dir is None or self._applied_stem is None:
            return
        src_dir = self._applied_src_dir
        stem = self._applied_stem
        src_ti1 = src_dir / f"{stem}.ti1"
        src_ti2 = src_dir / f"{stem}.ti2"
        # Multi-page charts are "<stem>_01.tif…"; a single page is just
        # "<stem>.tif". Accept both so a one-page applied chart still imports.
        src_tiffs = sorted(src_dir.glob(f"{stem}_*.tif"))
        if not src_tiffs and (src_dir / f"{stem}.tif").is_file():
            src_tiffs = [src_dir / f"{stem}.tif"]
        if not src_ti1.is_file() or not src_tiffs:
            InfoDialog(
                "Applied chart not found",
                "The chart handed over from the layout editor could not be "
                f"located:\n\n{src_dir}",
                self, min_width=520,
            ).exec()
            return

        self.target_started.emit()
        name = (self._manual_target_name_edit.text().strip()
                if self._manual_target_name_edit is not None else "") or stem
        self._file_mgr.set_target_name(name)
        project = self._file_mgr.project()
        # "Add as a new run" preserves the existing project's runs (and their
        # measurements) by filing this chart in a fresh runN; otherwise it goes
        # into — and resets — the project's current run.
        run = project.new_run() if add_new_run else project.current_run()
        run.reset_chart_artefacts()
        work_dir = run.ensure_dir()

        self._log.clear()
        self._preview.clear()
        try:
            shutil.copy(src_ti1, run.chart_ti1)
            if src_ti2.is_file():
                shutil.copy(src_ti2, run.chart_ti2)
            # Engine charts carry a channels.json (engine marker + recipe + strip
            # geometry); copy it so the run reads as an engine chart (#93).
            _src_ch = src_ti1.with_suffix(".channels.json")
            if _src_ch.is_file():
                shutil.copy(_src_ch, run.chart_channels_json)
            tiffs: list[Path] = []
            for i, src_tif in enumerate(src_tiffs, start=1):
                dest = work_dir / f"{run.stem}_{i:02d}.tif"
                shutil.copy(src_tif, dest)
                tiffs.append(dest)
        except OSError as exc:
            log.error("Applied-chart copy failed: %s", exc)
            InfoDialog(
                "Could not create target",
                f"Copying the chart into\n\n{work_dir}\n\nfailed:\n{exc}",
                self, min_width=520,
            ).exec()
            return

        self._last_target_name = name
        self._log.appendPlainText(
            f"Applied chart from the layout editor into {work_dir} "
            f"({count_phrase(len(tiffs), tr('1 page'), tr('{n} pages'))}). "
            + tr("targen and printtarg skipped.")
        )
        # The laid-out .ti2 may hold more patches than the designed .ti1: a
        # partial last strip is topped up with paper-white patches (printtarg
        # behaviour, mirrored by the engine). Say so, or the total silently
        # grows from the designed count (#124 report 6: 896 → 910).
        designed = _number_of_sets(run.chart_ti1)
        total = _number_of_sets(run.chart_ti2)
        if designed and total and total > designed:
            self._log.appendPlainText(
                f"Patch count: {designed} designed + {total - designed} "
                f"paper-white fill-up patch(es) completing the last strip "
                f"= {total} total. Instruments read whole strips; the "
                f"fill-up patches are measured like any others."
            )
        # The chart wasn't built from ChartParams; clear them so the meta stamp
        # falls back to instrument/paper only and preserves the editor layout we
        # copy in next.
        self._last_params = None
        self._on_generate_finished(tiffs)
        # Overlay the editor's full meta.json (richer editor_layout) so reopening
        # this run in the editor restores every knob, not just instrument/paper.
        src_meta = src_dir / "meta.json"
        if src_meta.is_file():
            try:
                shutil.copy(src_meta, run.meta_path)
            except OSError as exc:
                log.warning("Could not copy applied-chart meta.json: %s", exc)
        # Carry the i1Profiler hand-off pair (and the colour list) the editor
        # wrote into the run folder too, so the working folder is self-contained
        # for users who profile in i1Profiler instead of measuring here. The
        # staged files carry the editor's layout name; rename them to the run
        # stem (the profile name) so the whole run folder is self-consistent —
        # the profile name and the chart layout name now differ (#70).
        for extra in sorted(src_dir.glob(f"{stem}-i1profiler.*")) + \
                sorted(src_dir.glob(f"{stem}-colours.txt")):
            dest_name = run.stem + extra.name[len(stem):]
            try:
                shutil.copy(extra, run.dir / dest_name)
            except OSError as exc:
                log.warning("Could not copy applied-chart extra %s: %s",
                            extra.name, exc)

    def _apply_prebuilt_preset(self, key: str, target_name: str | None = None) -> None:
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
        # Built under the current Printer-profile name; never overwritten (#70).
        self._ensure_profile_name(target_name or PREBUILT_PRESETS[key][1])
        # Baselines for the Generate-time change detection, taken after seeding.
        self._prebuilt_targen_sig = self._targen_signature()
        self._prebuilt_printtarg_sig = self._printtarg_signature()
        self._update_preset_locks()      # grey both panels
        self._create_prebuilt_target(key, target_name)

    def _create_prebuilt_target(self, key: str, target_name: str | None = None) -> None:
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
        # Remember the loaded project BEFORE the name is applied, so a build into
        # the SAME project can honour the Profile-run bar (Overwrite run N / New
        # run); a build under a NEW name is its own project (#130).
        _ctl = getattr(self, "_target_ctl", None)
        _proj_before = _ctl.project_or_none() if _ctl is not None else None
        name = (self._manual_target_name_edit.text().strip()
                if self._manual_target_name_edit is not None else "") \
            or target_name or default_name
        self._file_mgr.set_target_name(name)
        # #130 CRITICAL (Knut): a prebuilt preset must build into the run the bar
        # shows — "Overwrite run N" → run N, "New run" → a fresh run — NOT always
        # the project's current run (which jumped the chart to the last run and
        # overwrote it). The params-based presets already do this via _on_generate;
        # the prebuilt-copy path bypassed it. Skipped for a build under a new name.
        _same_project = self._builds_into_project(_proj_before)
        if _same_project:
            self._align_current_run_to_target()
        # Run type = Verification copies through the run root too — keep the
        # run's profiling chart (#130, Knut K3).
        self._arm_verification_snapshot()
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
            # Engine charts carry a channels.json (engine marker + recipe + strip
            # geometry); copy it so the run reads as an engine chart (#93).
            _src_ch = src_ti1.with_suffix(".channels.json")
            if _src_ch.is_file():
                shutil.copy(_src_ch, run.chart_channels_json)
            tiffs: list[Path] = []
            for i, src_tif in enumerate(src_tiffs, start=1):
                dest = work_dir / f"{run.stem}_{i:02d}.tif"
                shutil.copy(src_tif, dest)
                tiffs.append(dest)
        except OSError as exc:
            log.error("Prebuilt copy failed: %s", exc)
            # The run root was already cleared for the copy — give the run its
            # profiling chart back before bailing out (#130, Knut K3).
            self._restore_profiling_chart()
            InfoDialog(
                "Could not create target",
                f"Copying the bundled chart into\n\n{work_dir}\n\nfailed:\n{exc}",
                self, min_width=520,
            ).exec()
            return

        self._last_target_name = name
        self._log.appendPlainText(
            f"Copied prebuilt patch set into {work_dir} "
            f"({count_phrase(len(tiffs), tr('1 page'), tr('{n} pages'))}). "
            "targen and printtarg skipped."
        )
        # Prebuilt sets aren't generated from ChartParams — clear any stale
        # params so _stamp_chart_meta falls back to instrument/paper only
        # (read from the bundled .ti2) rather than a previous chart's knobs.
        self._last_params = None
        self._on_generate_finished(tiffs)

    def _targen_skipped_layout_name(self) -> str | None:
        """Layout name when Generate will skip targen for a *non-built-in* ti1
        source (a user preset's .ti1, an applied editor chart, or a reflected
        chart). Built-in presets have their own preview text above; returns None
        when a fresh targen will run (#70)."""
        if getattr(self, "_reflected_active", False) and self._reflected_ti2 is not None:
            return self._reflected_ti2.stem
        if getattr(self, "_applied_active", False) and self._applied_stem:
            if (self._applied_targen_sig is None
                    or self._targen_signature() == self._applied_targen_sig):
                return self._applied_stem
        if getattr(self, "_preset_ti1_path", None) is not None:
            if (self._preset_ti1_targen_sig is None
                    or self._targen_signature() == self._preset_ti1_targen_sig):
                cur = self._preset_combo.currentData()
                if cur is not None and cur not in BUILTIN_PRESET_KEYS:
                    return str(cur)
        return None

    def _active_layout_name(self) -> str | None:
        """A human label for the chart *layout* currently driving generation —
        a built-in/user preset, a prebuilt chart, an editor-applied layout, or a
        loaded .ti1. Stamped onto the TIFF as "Chart layout <name>" in place of
        the targen command when no targen was run (#70, Knut's model)."""
        if getattr(self, "_tc918_active", False):
            return "TC9.18"
        # A de-branded vendor preset (patch recipe unlocked) must NOT stamp the
        # vendor's name onto the sheet — fall through to a neutral label.
        if getattr(self, "_knut_active", False) and not self._vendor_debranded:
            p = KNUT_PRESETS_BY_KEY.get(self._knut_active_key or "")
            return p.default_target_name if p is not None else "TC9.18+Spyderprint"
        if getattr(self, "_prebuilt_active", False) and self._prebuilt_key:
            return PREBUILT_PRESETS[self._prebuilt_key][1]
        if getattr(self, "_applied_active", False) and self._applied_stem:
            return self._applied_stem
        if getattr(self, "_reflected_active", False) and self._reflected_ti2 is not None:
            return self._reflected_ti2.stem
        if getattr(self, "_preset_ti1_path", None) is not None:
            cur = self._preset_combo.currentData()
            if cur is not None and cur not in BUILTIN_PRESET_KEYS:
                return str(cur)
        ti1 = getattr(self, "_current_ti1_path", None)
        if ti1 is not None:
            return Path(ti1).stem
        return None

    def _generate_from_ti1(self, ti1_path: Path, *, ask: bool = True) -> None:
        """Create the target by running printtarg only on an existing .ti1.

        Used by the TC9.18 preset both for its initial creation and for every
        later "Generate Chart" click while the bundled patch set is still the
        active source. Shares _on_generate_finished with the normal path.

        *ask* is False only for the live auto-update preview, which cannot open
        a window on every turn of a knob — see :meth:`_auto_regenerate_preview`,
        which does its own §4 check and simply does not re-lay-out a run that
        holds work.
        """
        if self._runner.is_running:
            log.warning("A process is already running")
            return
        # §4: every path that lays out a new chart asks first, not just the
        # Generate Chart button — a preset, an imported chart and a bundled
        # patch set all replace the chart a measurement describes.
        if ask and not self._confirm_displacing_results():
            return
        if not ti1_path.is_file():
            InfoDialog(
                "Patch set not found",
                f"The .ti1 patch set could not be located:\n\n{ti1_path}",
                self, min_width=520,
            ).exec()
            return
        self.target_started.emit()
        # Remember the loaded project before the name is applied (#130).
        _ctl = getattr(self, "_target_ctl", None)
        _proj_before = _ctl.project_or_none() if _ctl is not None else None
        name = (self._manual_target_name_edit.text().strip()
                if self._manual_target_name_edit is not None else "")
        if name:
            self._file_mgr.set_target_name(name)
        # #130 CRITICAL (Knut): a .ti1-based preset (TC9.18, Spyderprint) must
        # build into the run the Profile-run bar shows — Overwrite run N / New
        # run — not always the project's current run. Skipped for a build under a
        # new name (that's a different project).
        _same_project = self._builds_into_project(_proj_before)
        if _same_project:
            self._align_current_run_to_target()
        # Run type = Verification builds through the run root too — keep the
        # run's profiling chart (#130, Knut K3).
        self._arm_verification_snapshot()
        base_name = self._file_mgr.get_target_name() or TC918_TARGET_NAME
        params = self._collect_params()
        self._last_params = params  # for _stamp_chart_meta (see _on_generate)
        params.target_name = base_name
        # Built from an existing patch set (targen not run) → the stamp names the
        # chart layout instead of a misleading targen command (#70).
        params.chart_layout_name = self._active_layout_name()
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

    def _combo_thresholds(self, instr: str, paper: str):
        """The user's margin-threshold minimums for an engine instrument + paper,
        or None — so the live patch count honours the same minimums the engine
        enforces at generation (#93)."""
        try:
            from core.settings import thresholds_for_combo
            from workflow.layout_engine import papers
            w_mm, h_mm = papers.dimensions_mm(paper)
            return thresholds_for_combo(
                self._settings.get_margin_thresholds(), instr, w_mm, h_mm)
        except Exception:
            return None

    def _engine_geom(self, instr: str, paper: str, *, dd: bool, td: bool,
                     eff_lb: bool, nsl: bool, pscale: float, margin: float):
        """Build a layout-engine Geom from the guided/manual effective values,
        with the user's margin thresholds enforced (so the count matches what
        the engine will actually build, #93)."""
        from workflow.layout_engine import instruments
        kw: dict = dict(instrument=instr, paper=paper, spacer_on=True,
                        pscale=float(pscale),
                        margins=(float(margin),) * 4, border=float(margin),
                        nolimit=bool(nsl))
        # The strip-reading instruments bracket each strip with a leading +
        # trailing spacer (chart_creator._engine_build_kwargs does the same for
        # the real build); those two reserved gaps must be counted here too, or
        # the estimate over-counts what the engine actually fits (i1 A4 read 575
        # vs the real 550).
        if instr in ("i1", "p3", "CM"):
            kw["edge_spacers"] = True
        if instr in ("i1", "p3"):
            kw["nolpcbord"] = bool(eff_lb)
        elif instr == "CM":
            kw["density"] = 3 if td else (2 if dd else 1)
            if dd and not td:
                # Double density couples the tighter rows with a half-patch row
                # stagger, whose overhang reserves ¼-patch and reduces capacity;
                # the build sets it, so the count must too (else it over-counts
                # — CM double A3 read 480 vs the real 460).
                kw["cm_stagger"] = True
            if td:
                # Same printtarg-> engine scale conversion the build applies
                # (chart_creator._engine_build_kwargs): the guided pscale is the
                # printtarg -ii1 -a value (1.3 default), and the engine's native
                # extra-high size reproduces -a1.3 at pscale 1.0. Without this
                # the count used the raw 1.3 → oversized patches → undercount.
                from workflow.chart_creator import CM_TRIPLE_PRINTTARG_SCALE
                kw["pscale"] = float(pscale) / CM_TRIPLE_PRINTTARG_SCALE
        elif instr == "SS":
            kw["hflag"] = bool(dd)
        # Guided mode has no margin boxes and no "Use instrument margins"
        # recipe toggle, so the jig-safety threshold clamp is NOT applied here.
        # It would pin the patch count regardless of the clip-border / strip-cap
        # toggles (the thresholds dominate). Mirrors chart_creator's Guided
        # generation path so the estimate matches the real render.
        return instruments.geom_from_build_kwargs(kw, thresholds=None)

    def _engine_capacity(self, instr: str, paper: str, *, dd: bool, td: bool,
                         eff_lb: bool, nsl: bool, pscale: float, margin: float):
        """Patches per sheet from the ChromIQ engine (None if it can't lay out)."""
        try:
            from workflow.layout_engine import geometry, papers
            geom = self._engine_geom(instr, paper, dd=dd, td=td, eff_lb=eff_lb,
                                     nsl=nsl, pscale=pscale, margin=margin)
            w_mm, h_mm = papers.dimensions_mm(paper)
            return geometry.patches_per_sheet(geom, w_mm, h_mm)
        except Exception:
            return None

    def _engine_info_line(self, instr: str, paper: str, dpi: int, *, dd: bool,
                          td: bool, eff_lb: bool, nsl: bool, pscale: float,
                          margin: float) -> str:
        """One-line description of what the ChromIQ engine will build.

        Used by Guided mode, where the engine runs on fixed settings derived
        from the instrument/paper (not from an editable recipe). Manual mode
        has a live recipe panel — see :meth:`_engine_info_line_from_recipe`."""
        bits = [tr("ChromIQ layout engine"), instr, paper, f"{dpi} dpi",
                tr("margin {mm:g} mm").format(mm=margin)]
        if abs(pscale - 1.0) > 0.01:
            bits.append(tr("patch ×{s:.2f}").format(s=pscale))
        if instr in ("i1", "p3"):
            bits.append(tr("clip border off") if eff_lb else tr("clip border on"))
        if instr == "CM":
            bits.append({3: tr("extra-high density"), 2: tr("high density")}.get(
                3 if td else (2 if dd else 1), tr("hand-held")))
        if instr == "SS" and dd:
            bits.append(tr("hexagonal"))
        if nsl:
            bits.append(tr("no strip-length cap"))
        return " · ".join(bits)

    @staticmethod
    def _engine_info_line_from_recipe(r) -> str:
        """One-line summary of what the engine will build, read straight from
        the live layout recipe (Manual mode's source of truth).

        The printtarg widgets do NOT drive the engine here, so the info box has
        to reflect the recipe's own margins / patch size / clip border / etc.,
        otherwise it shows stale printtarg values (#93)."""
        from workflow.layout_engine import papers
        bits = [tr("ChromIQ layout engine"), r.instrument,
                papers.friendly_label(r.paper), f"{r.dpi} dpi"]
        # Margins — collapse to one value when all four agree, else show them.
        m = (r.margin_top, r.margin_right, r.margin_bottom, r.margin_left)
        if len(set(m)) == 1:
            bits.append(tr("margin {mm:g} mm").format(mm=m[0]))
        else:
            bits.append(tr("margins {t:g}/{r:g}/{b:g}/{l:g} mm").format(
                t=m[0], r=m[1], b=m[2], l=m[3]))
        # Layout strategy: area-first shows the target grid (patches are derived);
        # patch-first shows the explicit size or scale.
        if getattr(r, "layout_mode", "patch_first") == "area_first":
            if getattr(r, "area_method", "by_width") == "by_grid":
                _c = r.area_cols or tr("auto")
                _rr = r.area_rows or tr("auto")
                bits.append(tr("area-fit {c}×{r}").format(c=_c, r=_rr))
            elif r.area_min_patch_mm > 0:
                bits.append(tr("area-fit ≥{mm:g} mm").format(
                    mm=r.area_min_patch_mm))
            else:
                bits.append(tr("area-fit"))
        elif r.patch_w_mm > 0 and r.patch_h_mm > 0:
            bits.append(tr("patch {w:g}×{h:g} mm").format(
                w=r.patch_w_mm, h=r.patch_h_mm))
        elif abs(r.pscale - 1.0) > 0.01:
            bits.append(tr("patch ×{s:.2f}").format(s=r.pscale))
        if r.instrument in ("i1", "p3"):
            bits.append(tr("clip border on") if r.clip_border
                        else tr("clip border off"))
        if r.instrument == "CM":
            bits.append({3: tr("extra-high density"), 2: tr("high density")}.get(
                r.cm_density, tr("hand-held")))
        if r.instrument == "SS" and r.hflag:
            bits.append(tr("hexagonal"))
        if r.nolimit:
            bits.append(tr("no strip-length cap"))
        # Patch-area alignment, only when it differs from the default.
        if (r.patch_area_align or "top-left") != "top-left":
            bits.append(tr("align {a}").format(a=r.patch_area_align))
        return " · ".join(bits)

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

        # Which engine the COUNT must model has to match what will actually
        # build: Guided always lays out engine instruments with the ChromIQ
        # engine (regardless of the Manual "use engine" toggle — that governs
        # Manual only); Manual honours the toggle. Mirroring _should_use_engine
        # here fixes the Guided count/estimate reading the printtarg DB (or
        # showing nothing) when the Manual toggle happened to be off (Basti).
        from workflow.chart_creator import ENGINE_INSTRUMENTS
        guided_active = not (self._manual_btn is not None
                             and self._manual_btn.isChecked())
        engine_on = (instr in ENGINE_INSTRUMENTS) and (
            guided_active or bool(self._settings.get("use_chromiq_layout_engine", False)))
        if engine_on:
            per_sheet = self._engine_capacity(
                instr, paper, dd=dd, td=td, eff_lb=eff_lb, nsl=nsl_eff,
                pscale=eff_scale, margin=eff_margin)
        else:
            per_sheet = query_patches(instr, paper, dd, suppress_lb=eff_lb,
                                      margin_mm=eff_margin, patch_scale=eff_scale,
                                      triple_density=td, no_strip_limit=nsl_eff)
        if per_sheet is not None:
            total = per_sheet * pages
            self._predicted_patch_count = total   # for the Suggest-name button (#62)
            self._patch_count_lbl.setText(str(total))
            self._patch_detail_lbl.setText(
                tr("PATCHES · {pages} PAGES · {paper}").format(
                    pages=pages, paper=paper.upper())
            )
        else:
            self._predicted_patch_count = None
            self._patch_count_lbl.setText("?")
            self._patch_detail_lbl.setText(tr("CUSTOM LAYOUT"))

        # Live layout-info estimate (Guided + engine). Runs even with a chart on
        # screen, so its "estimate" column tracks the current settings while the
        # "on screen" column keeps the generated chart's real numbers (#93).
        if guided_active and getattr(self, "_layout_info_panel", None) is not None:
            if engine_on:
                geom = self._engine_geom(instr, paper, dd=dd, td=td, eff_lb=eff_lb,
                                         nsl=nsl_eff, pscale=eff_scale,
                                         margin=eff_margin)
                self._predict_layout_info(geom, paper, pages)
            else:
                self._layout_info_panel.clear_estimate()

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
                recommendation = "\n" + tr(
                    "Tip: use at least as many pages as the original profile.")
            else:
                recommendation = "\n" + tr(
                    "Pick a profile to refine from (Browse… above).")

        # With a refinement profile (-c) the neutral ramp samples the profile-
        # defined neutral axis (-n) rather than naïve device grey (-g).
        grey_flag = "-n" if (precond_active and precond_path) else "-g"

        target_name = self._preview_target_name("guided")
        targen_line = (f"targen -d2 -G -e{wp} -B{bp} "
                       f"{grey_flag}{grey_steps}{precond_line} {target_name}")
        if engine_on:
            layout_line = self._engine_info_line(
                instr, paper, dpi, dd=dd, td=td, eff_lb=eff_lb, nsl=nsl_eff,
                pscale=eff_scale, margin=eff_margin)
            info = (tr("Guided mode applies these fixed settings:")
                    + f"\n{targen_line}\n{layout_line}{recommendation}")
        else:
            info = (
                tr("Guided mode applies these fixed settings:")
                + f"\n{targen_line}\n"
                f"printtarg -i{preview_instr} -p{paper} -t{dpi} {scale_flag}{lb_flag}{dd_flag}{margin_flag}{strip_flag}{target_name}"
                f"{recommendation}"
            )
        if hasattr(self, "_guided_info_lbl"):
            self._guided_info_lbl.setText(info)

        # Patch count / options just changed → refresh the live name prefix
        # (no-op when it's unchanged, so this can't loop with the field's own
        # textChanged → _update_patch_count).
        self._refresh_name_prefix()

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
            self._dd_check.setText(tr("Double density"))
            self._dd_tooltip._title = tr("Double Density (-h)")
            self._dd_tooltip._body = tr(
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
            self._dd_tooltip.setToolTip(tr("Double Density (-h)\n\nClick for details"))
        elif instr == "SS":
            self._dd_check.setVisible(True)
            self._dd_tooltip.setVisible(True)
            self._dd_check.setText(tr("Hexagon patches (packs ~15% more per sheet)"))
            self._dd_tooltip._title = tr("Hexagon Patches (-h)")
            self._dd_tooltip._body = tr(
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
            self._dd_tooltip.setToolTip(tr("Hexagon Patches (-h)\n\nClick for details"))
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
            else:
                self._refresh_after_rename(new_name)
        elif action == TargetChangeAction.DELETE:
            self._file_mgr.delete_project_folder(old_name)
        # KEEP: leave the old folder; set_target_name creates the fresh one.
        return True

    def _refresh_after_rename(self, new_name: str) -> None:
        """Re-push the renamed run's files to every tab holding absolute paths.

        The rename moves the whole project folder and fixes the file stems, but
        the chart preview here and the Print tab still hold the OLD paths in
        memory — printing right after a rename failed with "no such file"
        (Basti, #108 batch). Best-effort: never blocks the rename itself."""
        try:
            self._file_mgr.set_target_name(new_name)
            run = self._file_mgr.project().current_run()
            tiffs = run.chart_tiffs()
            if tiffs:
                self._preview.load_tiff(tiffs)
                self.chart_finished.emit(tiffs, run.chart_ti2, False)
            self._last_target_name = new_name
        except Exception:  # noqa: BLE001 — refresh must never block the rename
            log.warning("post-rename path refresh failed", exc_info=True)

    def _on_generate(self) -> None:
        if self._runner.is_running:
            log.warning("A process is already running")
            return
        if not self._confirm_displacing_results():
            return
        # The per-ink inspector describes the PREVIOUS chart — drop it the
        # moment a new build starts; load_tiff rebuilds it for the new chart's
        # ink set when the build lands (#72, Basti).
        self._preview.reset_ink_inspector()
        # Chart reflected from the Print/Measure tab — read-only. While nothing
        # is unlocked there is nothing to generate (the chart lives in its own
        # folder already); say so and stop. Unlocking a panel means the user
        # wants to build their own, so drop the reflection and fall through to
        # the normal fresh-chart path.
        if self._reflected_active and self._current_mode() == "manual":
            unlocked = (
                (self._override_targen_check is not None
                 and self._override_targen_check.isChecked())
                or (self._override_printtarg_check is not None
                    and self._override_printtarg_check.isChecked()))
            if not unlocked:
                InfoDialog(
                    "This chart is loaded from elsewhere",
                    "This chart was opened with “Open Chart File (.ti2)” at the "
                    "top left of the window, so it's shown here just for "
                    "reference — it already lives in its own folder and there's "
                    "nothing to generate.\n\n"
                    "If you want to build your own chart from these settings, "
                    "tick “Edit patch recipe (override preset)” or “Edit page "
                    "layout (override preset)” above, make your changes, then "
                    "click “Generate Chart” — that creates a brand-new chart and "
                    "leaves the loaded one untouched.",
                    self, min_width=540,
                ).exec()
                return
            self._leave_reflected()
        # Chart applied from the TI2 layout editor. Mirrors the prebuilt-files
        # logic, but the source is the editor's staging folder rather than a
        # bundled asset:
        #   • targen changed   → fresh targen run (different patches): fall through
        #   • else printtarg changed → re-lay-out the staged .ti1 (same patches)
        #   • else                   → re-import the staged files verbatim
        if self._applied_active and self._applied_src_dir is not None \
                and self._current_mode() == "manual":
            targen_changed = (self._applied_targen_sig is not None
                              and self._targen_signature() != self._applied_targen_sig)
            printtarg_changed = (self._applied_printtarg_sig is not None
                                 and self._printtarg_signature() != self._applied_printtarg_sig)
            if targen_changed:
                # User unlocked the recipe — drop the applied binding and build a
                # fresh chart from the current settings (fall through below).
                self._leave_applied()
            elif printtarg_changed:
                self._generate_from_ti1(
                    self._applied_src_dir / f"{self._applied_stem}.ti1",
                    ask=False)
                return
            else:
                self._import_applied_chart()
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
                self._generate_from_ti1(bundled_ti1, ask=False)
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
                    self._generate_from_ti1(self._preset_ti1_path, ask=False)
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
                self._generate_from_ti1(self._tc918_ti1_path(), ask=False)
                return
            self._tc918_active = False
            self._tc918_targen_sig = None
        # Same for Knut's TC9.18+Spyderprint presets: while active and the targen
        # settings are untouched, re-lay-out the bundled 1168-patch .ti1 (printtarg
        # only). Changing a targen setting opts into a fresh targen chart.
        if self._knut_active and self._current_mode() == "manual":
            if self._targen_signature() == self._knut_targen_sig:
                # Reuse THIS preset's own .ti1 (Full-layout-setup presets each bundle a
                # different one); never the shared TC9.18 set (#58).
                p = KNUT_PRESETS_BY_KEY.get(self._knut_active_key or "")
                ti1 = (resource_path(p.ti1_asset) if p is not None
                       else self._knut_ti1_path())
                self._generate_from_ti1(ti1, ask=False)
                return
            self._knut_active = False
            self._knut_targen_sig = None
            self._knut_active_key = None
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

        # #130: remember which project we're in BEFORE the profile name is
        # applied. A build under the SAME profile name can honour the shared
        # bar's Profile-run selection (Overwrite runN / New run); a build under a
        # NEW name is its own new project (with its own run1), so the bar's
        # run selection — which refers to the previously loaded project — must
        # NOT drive it.
        _ctl = getattr(self, "_target_ctl", None)
        _proj_before = _ctl.project_or_none() if _ctl is not None else None

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

        # #130 (Knut): for a normal build INTO the loaded project, point the
        # current run at the shared bar's Profile-run selection so the chart
        # lands where the bar shows — Overwrite runN → runs/runN/, New run → a
        # fresh runs/runN+1/ (Run type = Verification then files it under that
        # run's verifications/ in _on_generate_finished). Skipped for
        # calibration and refinement (they chose their run above) and for a
        # build under a new name (that's a different project with its own run1).
        _same_project = self._builds_into_project(_proj_before)
        if not cal_target_active and not self._preconditioning_from_dialog \
                and _same_project:
            self._align_current_run_to_target()

        # #130 (Knut bug): a verification chart must live ONLY in the run's
        # verifications/ folder — the profiling chart at the run root must
        # survive. Generating the verify chart writes <stem>.ti1/.ti2/.tif into
        # the run root (overwriting the profiling chart) before it's moved into
        # verifications/, so snapshot the profiling chart now and restore it in
        # _on_generate_finished after the move.
        self._verify_profiling_backup = None
        if not cal_target_active:
            self._arm_verification_snapshot()

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

        # Arm the slow-chart watchdog: only this path runs targen (the tool
        # that can hit the OFPS hang). printtarg-only paths (load .ti1,
        # re-layout, prebuilt copy) are always fast and don't arm it.
        self._cancelled_by_user = False
        self._progress_line_active = False
        self._slow_watchdog.start(_SLOW_CHART_WATCHDOG_MS)
        self._creator.generate(
            params,
            on_line=self._on_log_line,
            on_finish=self._on_generate_finished,
        )

    # ------------------------------------------------------------------
    # Slow-chart watchdog (targen OFPS-cliff escape hatch)
    # ------------------------------------------------------------------

    def _on_slow_watchdog(self) -> None:
        """Fired when a chart generate has run past the watchdog threshold.

        Offers the user wait / rebuild-faster / cancel. The user must decide
        again on every slow generate — the choice is never remembered."""
        if not self._runner.is_running:
            return  # finished in the gap before the timer fired
        from ui.dialogs.slow_chart_dialog import SlowChartDialog

        dlg = SlowChartDialog(self.window())
        self._slow_dialog = dlg
        choice = dlg.exec()       # nested loop; targen keeps running behind it
        self._slow_dialog = None

        # targen may have finished (or been swapped out) while the dialog was
        # open — _on_generate_finished closes the dialog in that case, so bail.
        if not self._runner.is_running:
            return

        if choice == SlowChartDialog.FAST:
            self._log.appendPlainText(
                tr("Switching to the faster patch layout and rebuilding the chart…")
            )
            self._log.ensureCursorVisible()
            if not self._creator.restart_with_fast_sampler():
                self._cancel_generation()
        elif choice == SlowChartDialog.CANCEL:
            self._cancel_generation()
        else:
            # Keep waiting: re-arm so the user can change their mind later.
            self._slow_watchdog.start(_SLOW_CHART_WATCHDOG_MS)

    def _cancel_generation(self) -> None:
        self._cancelled_by_user = True
        self._creator.cancel()

    def _ti1_load_destination(self, src: Path) -> "str | None":
        """Ask where a loaded patch set's chart should be built (#130).

        Returns ``"into"`` (lay it into the currently loaded profile project, so
        Create Chart writes it per the Profile-run bar), ``"into_replace"``,
        ``"into_new"``, ``"into_chart"`` (swap the chart only, #130), ``"new"``
        (start a new project named after the file), or ``None`` (Cancel). With no
        project loaded there is nothing to choose → ``"new"`` without a dialog."""
        from core.measurement_target import (RUN_TYPE_VERIFICATION)
        from ui.ti2_loader import _choice_dialog
        # Whether the patch set brought its layout settings along decides what
        # "replace only the chart" can promise, so the answer is worked out once
        # and stated in the option's own text.
        _has_sidecar = ti1_sidecar(src) is not None
        ctl = getattr(self, "_target_ctl", None)
        proj = ctl.project_or_none() if ctl is not None else None
        if proj is None:
            return "new"
        # Describe the bar so the user knows exactly where "into this project"
        # would put the chart.
        t = ctl.target
        run_id = t.profile_run
        if run_id and proj.has_run(run_id):
            where = tr("overwrite <b>{run}</b>").format(run=run_id)
        else:
            where = tr("a new run")
        rtype = (tr("Verification") if t.run_type == RUN_TYPE_VERIFICATION
                 else tr("Profiling"))
        pname = proj.root.name
        intro = tr(
            "You loaded the patch set <b>{file}</b>.<br><br>"
            "A profile project is open: <b>{project}</b>. Where should the chart "
            "these patches make be built?"
        ).format(file=src.name, project=pname)
        into_desc = tr(
            "Keep working in <b>{project}</b>. When you click <b>Create Chart</b>, "
            "the patches are laid out and saved into this project — following the "
            "Profile-run bar (Run type = <b>{rtype}</b>, {where}). Nothing is "
            "overwritten until you actually create the chart."
        ).format(project=pname, rtype=rtype, where=where)
        new_desc = tr(
            "Start a fresh profile project from these patches. You'll be asked "
            "for the project name (pre-filled as <b>{name}</b> — change it or "
            "keep it). The current project <b>{project}</b> is left untouched; "
            "the new project gets its own folder and its own run 1."
        ).format(name=self._file_mgr.strip_workfile_ext(src.stem), project=pname)
        # #130 §3 (Model B): building into a run that already holds work is a
        # Replace — say so, and offer a new run instead, before anything moves.
        if self._run_has_work_to_displace(proj, run_id):
            from ui.ti2_loader import _run_label
            # Friendly label ("run 1") in prose and on the button; the raw folder
            # id only inside the <code> paths, so both read naturally.
            label = _run_label(t)
            if t.run_type == RUN_TYPE_VERIFICATION:
                replace_desc = tr(
                    "Build the chart as <b>{label}</b>'s verification chart. The "
                    "verification chart that is there now moves to "
                    "<code>runs/{run}/verifications/old/</code> first — nothing "
                    "is deleted — and the new chart is saved in "
                    "<code>runs/{run}/verifications/</code>. Your dated "
                    "verification results are kept, and so are this run's own "
                    "chart, measurement and printer profile."
                ).format(label=label, run=run_id)
            else:
                replace_desc = tr(
                    "Build the chart into <b>{label}</b>. That run's current "
                    "chart, measurement and printer profile — together with "
                    "every folder inside it, including its reports and "
                    "verifications — move to <code>runs/{run}/old/</code> first, "
                    "and the new chart is saved in <code>runs/{run}/</code>. "
                    "Nothing is deleted. Everything moves because a new chart no "
                    "longer matches the measurement, profile or checks made from "
                    "the old one."
                ).format(label=label, run=run_id)
            new_run_desc = tr(
                "Build the chart in a brand-new run of <b>{project}</b> instead, "
                "so everything in <b>{run}</b> stays exactly as it is. The "
                "Profile-run bar moves to the new run."
            ).format(project=pname, run=label)
            # #130 (Knut, 2026-07-27): a fourth way — swap ONLY the chart and
            # leave everything else in the run standing. His reading (b): it is
            # a convenience that can also serve as a repair tool, and the user
            # must be warned about the consequence, because whether the incoming
            # patch set matches the measurement already in the run is a judgement
            # only a person can make.
            chart_only_desc = tr(
                "Swap the chart in <b>{label}</b> and leave everything else "
                "standing: the measurement, the profile, the reports and the "
                "verifications stay put, and nothing moves to <code>old/</code>. "
                "<b>ChromIQ cannot check that these patches are the ones your "
                "measurement was taken with</b> — only you can, and if they are "
                "not, the run keeps a measurement that no longer matches its "
                "chart. {sidecar}"
            ).format(label=label, sidecar=(
                tr("The chart's settings file was found beside it, so the sheet "
                   "is laid out exactly as it was.")
                if _has_sidecar else
                tr("No chart settings file was found beside it, so only the "
                   "patches are replaced and the settings now on screen decide "
                   "the layout.")))
            return _choice_dialog(
                self, tr("Where should this patch set's chart go?"), intro,
                [(tr("Replace {run}").format(run=label), replace_desc,
                  "into_replace"),
                 (tr("Build it as a new run instead"), new_run_desc, "into_new"),
                 (tr("Replace only the chart"), chart_only_desc, "into_chart"),
                 (tr("Start a new project"), new_desc, "new")],
            )
        return _choice_dialog(
            self, tr("Where should this patch set's chart go?"), intro,
            [(tr("Add to this project"), into_desc, "into"),
             (tr("Start a new project"), new_desc, "new")],
        )

    def _run_has_work_to_displace(self, proj, run_id: str) -> bool:
        """Whether building into *run_id* is an **Overwrite** of an existing run,
        and must therefore offer New-vs-Replace first (#130 §3).

        Knut's ruling of 2026-07-25 — "Always ask on an Overwrite run" — makes
        this a question about the run's existence, not its contents: any build
        into a run the user already has asks first, even when that run holds
        only a chart. Only "New run" proceeds without the question, because
        there is nothing there to displace.
        """
        return bool(run_id) and proj is not None and proj.has_run(run_id)

    def _on_load_ti1(self) -> None:
        path = open_file_dialog(
            self, "Load patch set",
            "Patch sets (*.ti1 *.pxf *.cgats *.txt)",
            extra_path=self._settings.get("custom_output_path", ""),
            declutter_settings=self._settings,
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

        # A loaded patch set supplies its own fixed colorimetry, so it's built by
        # printtarg only — targen is skipped, exactly like a user preset that
        # bundled a .ti1. Point Generate at the loaded file and snapshot the
        # targen controls so the override box can still opt into a fresh targen
        # run; clear any other preset binding that was active.
        self._tc918_active = False
        self._tc918_targen_sig = None
        self._knut_active = False
        self._knut_targen_sig = None
        if self._prebuilt_active:
            self._leave_prebuilt()
        if self._applied_active:
            self._leave_applied()
        if self._reflected_active:
            self._leave_reflected()
        self._preset_ti1_path = ti1
        self._preset_ti1_targen_sig = self._targen_signature()
        # Grey the targen panel (printtarg stays editable) so the loaded patch
        # set can't be silently overwritten by a stray targen run, and so
        # "Generate Chart" re-lays the same patches with the new printtarg knobs.
        self._reset_override_checks()
        self._update_preset_locks()
        # #130: where should the laid-out chart go? If a profile project is loaded,
        # ask — the patches can go INTO that project (Create Chart then writes them
        # per the Profile-run bar: Overwrite run N, or a new run), or start their
        # own new project named after the file. With no project loaded there's
        # nothing to disambiguate, so the file's own name seeds a new project.
        dest = self._ti1_load_destination(src)
        if dest is None:                       # Cancel — load nothing
            self._preset_ti1_path = None
            self._preview.clear()
            self._generate_btn.setEnabled(True)
            return
        if dest == "new":
            # Bug 4 (Knut): starting a new project from a patch set must let the
            # user confirm or change the name (pre-filled from the file, like
            # creating any new profile project), then actually LOAD it — show the
            # new name in the "Printer profile project name" field.
            from ui.ti2_loader import _ask_project_name
            name, _replace = _ask_project_name(
                self, self._file_mgr.strip_workfile_ext(src.stem),
                self._file_mgr.root_dir())
            if name is None:                      # cancelled the name prompt
                self._preset_ti1_path = None
                self._preview.clear()
                self._generate_btn.setEnabled(True)
                return
            self._file_mgr.start_new_project(name)
            self._update_name_fields()
        else:
            # #130 (Knut K3): building INTO the open project must follow the
            # Profile-run bar — Overwrite run N → that run, New run → a fresh one
            # — instead of always using the project's current run, which quietly
            # built the chart into a different run than the bar showed.
            if dest == "into_new":
                # The user chose a fresh run over replacing the selected one.
                ctl = getattr(self, "_target_ctl", None)
                if ctl is not None:
                    ctl.set_profile_run("")            # "New run"
            self._align_current_run_to_target()
            # §4: loading a patch set into a run that already holds work is the
            # same replacement the Generate Chart button makes, so it asks the
            # same question. Knut, beta.125: *"Step 3 in test, but now loading a
            # ti1 file from button in Create Chart. Preview updates, but no
            # message comes. Bug again."* Both destinations that land on an
            # existing run are covered — "replace the run" and "replace only the
            # chart" — because either one leaves the measurement describing
            # patches that are no longer on the sheet.
            if dest in ("into_replace", "into_chart") \
                    and not self._confirm_displacing_results():
                self._preset_ti1_path = None
                self._preview.clear()
                self._generate_btn.setEnabled(True)
                return
            if dest == "into_replace":
                # #130 §5a/§5b: a Replace archives what it displaces — the same
                # rule, and the same helper, as a Print/Measure chart import.
                self._archive_run_for_replace()
        # "Replace only the chart" (#130, Knut 2026-07-27): the run keeps its
        # measurement and profile, and — when the patch set brought its settings
        # file along — the sheet is laid out exactly as that file describes,
        # seed included, so a chart put back this way is the chart it was.
        chart_only = dest == "into_chart"
        if chart_only:
            sidecar = ti1_sidecar(ti1) or ti1_sidecar(src)
            if sidecar is not None:
                self._apply_loaded_chart_settings(sidecar)
        # Run type = Verification lays the chart down at the run root before it
        # is filed under verifications/ — keep the run's profiling chart.
        self._arm_verification_snapshot()
        params = self._collect_params()
        self._preview.clear()
        self._generate_btn.setEnabled(False)
        self._creator.load_ti1_and_generate_preview(
            ti1, params,
            on_line=self._on_log_line,
            on_finish=self._on_generate_finished,
            keep_results=chart_only,
        )

    def _on_log_line(self, line: str) -> None:
        # Collapse targen's "Added N/M" seeding spam into one live percentage.
        matches = _TARGEN_ADDED_RE.findall(line)
        if matches:
            done, total = int(matches[-1][0]), int(matches[-1][1])
            pct = int(done * 100 / total) if total else 0
            self._set_progress_line(
                tr("Arranging colour patches: {pct}%").format(pct=pct)
            )
            return
        self._progress_line_active = False
        self._log.appendPlainText(line)
        self._log.ensureCursorVisible()

    def _set_progress_line(self, text: str) -> None:
        """Show ``text`` as the log's last line, replacing it in place if the
        previous line was already a progress line (so the percentage ticks up
        without scrolling hundreds of lines past)."""
        from PyQt6.QtGui import QTextCursor

        if self._progress_line_active:
            cur = self._log.textCursor()
            cur.movePosition(QTextCursor.MoveOperation.End)
            cur.select(QTextCursor.SelectionType.LineUnderCursor)
            cur.removeSelectedText()
            cur.insertText(text)
            self._log.setTextCursor(cur)
        else:
            self._log.appendPlainText(text)
            self._progress_line_active = True
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
            txt_path, pxf_path = export_from_ti1(
                ti1, exports_dir, base_name=base_name,
                also_shuffled=self._settings.get("export_shuffled_pxf", False))
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
        if self._settings.get("export_shuffled_pxf", False):
            shuf = pxf_path.with_name(f"{pxf_path.stem}-shuffled.pxf")
            if shuf.is_file():
                self._log.appendPlainText(f"[i1iSis] wrote {shuf.name} (shuffled)")

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

    def set_target_controller(self, controller) -> None:
        """Receive the shared Profile-run / Run-type controller (#130) so a
        Verification generation is filed as the run's verify chart, and so
        switching Run type / Profile run swaps the Create-Chart tab to that
        target's own chart (settings + preview)."""
        self._target_ctl = controller
        # Let the bar's "Location being edited" line follow the name as it is
        # typed, so it is answerable before the first chart exists (#130).
        for _f in (getattr(self, "_target_name_edit", None),
                   getattr(self, "_manual_target_name_edit", None)):
            if _f is not None:
                _f.textChanged.connect(controller.set_pending_project_name)
                controller.set_pending_project_name(_f.text())
        # The actual chart (.ti2 path) the tab currently displays. Tracking the
        # real artefact — not a (run, type) key — keeps the swap correct even
        # after a generation or reload changed the chart out from under us
        # (Knut #130 beta-2 test: switching Run type showed the wrong chart).
        self._shown_chart_ti2: "Path | None" = None
        #: (path, .ti2 mtime) of the chart on screen — see _chart_stamp.
        self._shown_chart_stamp: "tuple | None" = None
        controller.changed.connect(self._on_target_changed)

    def clear_loaded_project(self) -> None:
        """Forget the project this tab is showing, leaving it as at launch.

        #130 (Knut, 2026-07-29): after "Delete the whole project" the name field
        still held the deleted project's name, so the next thing that touched it
        made the folder all over again — *"After deletion of the whole project I
        was working in, the user interface must return to the starting state of
        the app, empty and no loaded project. It must not create another project
        that I did not ask for."*

        Only the identity of the project is dropped. Every chart OPTION the user
        has set — instrument, paper, patch count, layout — is deliberately left
        alone, because those are their working preferences and re-typing them
        after a delete would be its own annoyance.
        """
        self._last_target_name = ""
        self._last_shown_project_name = None
        for f in (getattr(self, "_target_name_edit", None),
                  getattr(self, "_manual_target_name_edit", None)):
            if f is None:
                continue
            if isinstance(f, PrefixLockedLineEdit):
                f.set_prefix("")
            f.clear()
        # Nothing is on screen any more: no chart, no patch list, no preview.
        self._shown_chart_ti2 = None
        self._shown_chart_stamp = None
        self._current_ti1_path = None
        self._preview.clear()
        self._log.appendPlainText(tr(
            "The project was deleted, so ChromIQ is back where it starts: no "
            "project is open. Type a name into “Printer profile project name” "
            "and create a chart to begin a new one, or use the folder icon to "
            "open a project you already have."))
        # Tell Print and Measure to let go of the chart as well.
        self.chart_finished.emit([], None, False)

    def _confirm_displacing_results(self) -> bool:
        """Ask before a new chart displaces work made with the one it replaces.

        §4 of ``docs/design/unified_measurement_management.md``. A `.ti3`
        describes one chart and a profile describes one `.ti3`, so replacing a
        chart can break a chain three links deep — measurement, profile, and the
        dated verification measurements printed *through* that profile.

        Knut, #131 2026-07-28: he read one strip of a chart, went to Create
        Chart, changed the column count and re-generated. The measurement was
        archived to ``old/`` — correctly, and without a word — so back on the
        Measure tab the run simply had no measurement any more, and he spent a
        long time thinking the checkboxes were broken.

        Nothing is ever deleted; this only makes the move visible, and only when
        there is something to move. A run with no results yet — the ordinary case
        while you are still settling on chart options — never sees it.
        """
        ctl = getattr(self, "_target_ctl", None)
        if ctl is not None and not ctl.target.profile_run:
            # "New run" — the build makes a fresh, empty run, so nothing at all
            # is displaced. The results belong to whichever run happened to be
            # selected before, which is not the one being built (Knut, #130
            # 2026-07-28: "this is not at all relevant for a new run that is
            # being created, so this message should not happen").
            return True
        try:
            run = self._file_mgr.project().current_run()
        except Exception:      # noqa: BLE001 — no project yet: nothing at risk
            return True

        from workflow.chart_integrity import (assess_profiling_chart,
                                              assess_verification_chart)
        if self._is_verification_target():
            cost = assess_verification_chart(run)
            if not cost.warn:
                return True
            return self._ask_chart_question(*self._verify_chart_message(cost),
                                            tr("Generate the new chart"))

        cost = assess_profiling_chart(run)
        if not cost.warn:
            return True
        return self._ask_chart_question(*self._profiling_chart_message(run, cost),
                                        tr("Generate the new chart"))

    def _ask_chart_question(self, title: str, body: str, go_label: str) -> bool:
        """One window for both §4 messages: headline, explanation, two buttons."""
        from PyQt6.QtWidgets import QMessageBox
        from ui.widgets import fit_message_box_buttons

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        # macOS paints no title on a message box, so a window the user can name
        # is one whose title is IN it (Knut, #131 2026-07-27). The headline goes
        # in setText, which is bold, and the explanation in setInformativeText
        # at normal weight — a whole screen of bold is a wall nobody reads.
        box.setWindowTitle(title)
        box.setText(title)
        box.setInformativeText(body)
        go = box.addButton(go_label, QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(go)
        # Long labels clip once the font swap widens them, and polish does not
        # happen offscreen — so fit them here (Knut, #130).
        fit_message_box_buttons(box)
        box.exec()
        return box.clickedButton() is go

    def _pages_paragraph(self, cost) -> str:
        """M-CHART-NOPAGES — §4a rows 3 and 5, appended when it applies."""
        from workflow import measurement_messages as M

        if cost.can_redraw_pages:
            return ""
        if not cost.pages:
            pages = tr(M.M_CHART_NOPAGES_NONE)
        elif cost.pages == 1:
            pages = tr(M.M_CHART_NOPAGES_ONE)
        else:
            pages = tr(M.M_CHART_NOPAGES_SOME).format(n=cost.pages)
        _title, body = M.M_CHART_NOPAGES.render(pages=pages)
        return "\n\n" + tr(M.M_CHART_NOPAGES.title) + "\n" + body

    def _corrupt_measurement_note(self, cost) -> str:
        """M-CHART-CORRUPT — §4, when the run's measurement cannot be read.

        Knut, 2026-08-04: a corrupt or empty `.ti3` is not "a measurement of 0
        patches"; it is a file the user should look at before it is archived,
        and — when a profile is there too — the moment the chain from chart to
        profile stops being describable on disk.
        """
        from workflow import measurement_messages as M

        if not (cost.has_measurement and cost.readings == 0):
            return ""
        _title, body = M.M_CHART_CORRUPT.render()
        note = "\n\n" + tr(M.M_CHART_CORRUPT.title) + "\n" + body
        if cost.has_profile:
            note += tr(M.M_CHART_CORRUPT_WITH_PROFILE)
        return note

    def _duplicate_blocked_note(self, cost) -> str:
        """M-DUPLICATE-BLOCKED — appended to any message recommending Duplicate
        when this run cannot be duplicated (§4a, §6)."""
        from workflow import measurement_messages as M

        if cost.can_duplicate:
            return ""
        return tr(M.M_DUPLICATE_BLOCKED).format(
            missing=", ".join(cost.duplicate_blocked_by))

    def _profiling_chart_message(self, run, cost) -> "tuple[str, str]":
        """M-CHART-PROFILING, or M-CHART-W4 when the run has a history.

        The text is the reviewed catalogue's (§M); this only chooses the ID and
        fills the numbers.
        """
        from workflow import measurement_messages as M
        from workflow.chart_integrity import Blast

        if cost.blast is Blast.RUN_AND_HISTORY:
            title, body = M.M_CHART_W4.render(
                c=cost.readings, v=cost.verifications, folder=str(run.old_dir))
        else:
            items = []
            if cost.readings == 1:
                items.append(tr(M.M_CHART_ITEM_MEASUREMENT_ONE))
            elif cost.readings:
                items.append(tr(M.M_CHART_ITEM_MEASUREMENT).format(
                    c=cost.readings))
            elif cost.has_measurement:
                # §M's {items} list has no entry for a measurement whose
                # readings cannot be counted, and "a measurement of 0 patches"
                # would be false. PROPOSED — on the issue for approval.
                items.append(tr(M.M_CHART_ITEM_MEASUREMENT_UNCOUNTABLE))
            if cost.has_profile:
                items.append(tr(M.M_CHART_ITEM_PROFILE))
            title, body = M.M_CHART_PROFILING.render(
                items="\n".join(items), folder=str(run.old_dir))
        return title, body + self._corrupt_measurement_note(cost) \
            + self._pages_paragraph(cost) + self._duplicate_blocked_note(cost)

    def _verify_chart_message(self, cost) -> "tuple[str, str]":
        """M-CHART-VERIFY — §4's W5."""
        from workflow import measurement_messages as M

        title, body = M.M_CHART_VERIFY.render(v=cost.verifications)
        return title, body + self._pages_paragraph(cost) \
            + self._duplicate_blocked_note(cost)

    def _is_verification_target(self) -> bool:
        ctl = getattr(self, "_target_ctl", None)
        return ctl is not None and ctl.target.is_verification()

    def _snapshot_profiling_chart(self) -> "Path | None":
        """Copy the current run's PROFILING work aside before a verification
        chart is built into the same run root, so building the verify chart
        (which overwrites the run root before the files are moved into
        verifications/) never disturbs it (#130, Knut). Returns the temp folder,
        or None when the run has nothing to protect.

        Covers the chart files **and the run's measurement (.ti3) and printer
        profile (.icc/.icm)**: the build starts with ``reset_chart_artefacts()``,
        which archives those to ``old/`` — so without this the run appeared to
        have lost its finished profile the moment a verification chart was made.
        """
        try:
            run = self._file_mgr.project().current_run()
        except Exception:      # noqa: BLE001
            return None
        stem = run.stem
        srcs = [run.dir / f"{stem}{ext}" for ext in
                (".ti1", ".ti2", ".cht", ".channels.json", ".strips.json",
                 ".tif", ".ti3", ".icc", ".icm")]
        srcs += list(run.dir.glob(f"{stem}_*.tif"))
        present = [p for p in srcs if p.is_file()]
        if not present:
            return None
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="chromiq_prof_chart_"))
        for p in present:
            try:
                shutil.copy2(p, tmp / p.name)
            except OSError:
                pass
        return tmp

    def _restore_profiling_chart(self) -> None:
        """Move the snapshotted profiling chart back to the run root after a
        verification chart was generated + filed into verifications/ (#130)."""
        bak = getattr(self, "_verify_profiling_backup", None)
        self._verify_profiling_backup = None
        if not bak:
            return
        try:
            run = self._file_mgr.project().current_run()
            for p in Path(bak).iterdir():
                shutil.move(str(p), str(run.dir / p.name))
        except Exception:      # noqa: BLE001 — never break a finished generation
            log.warning("Could not restore the profiling chart after verify "
                        "generation", exc_info=True)
        finally:
            shutil.rmtree(bak, ignore_errors=True)

    def _resolve_target_chart(self) -> "tuple[Path, list[Path], Path] | None":
        """``(ti2, tiffs, ti1)`` for the current Profile-run / Run-type target's
        EXISTING chart — the verification chart for Run type = Verification, the
        run's profiling chart for Profiling — or ``None`` when that chart hasn't
        been generated yet. Never creates anything (#130)."""
        ctl = getattr(self, "_target_ctl", None)
        if ctl is None:
            return None
        try:
            proj = ctl.project_or_none()
            if proj is None:
                return None
            t = ctl.target
            run_id = t.profile_run
            if not run_id or not proj.has_run(run_id):
                return None                      # "New run" / no such run yet
            run = proj.run(run_id)
            if t.is_verification():
                ti2, ti1 = run.verify_chart_ti2, run.verify_chart_ti1
                tiffs = run.verify_chart_tiffs()
            else:
                ti2, ti1 = run.chart_ti2, run.chart_ti1
                tiffs = sorted(run.dir.glob(f"{run.stem}_*.tif"))
                if not tiffs and (run.dir / f"{run.stem}.tif").is_file():
                    tiffs = [run.dir / f"{run.stem}.tif"]
            if ti2.is_file() and tiffs:
                return ti2, list(tiffs), ti1
        except Exception as exc:  # noqa: BLE001 — never break the tab on this
            log.warning("Run-type switch: could not resolve target chart: %s", exc)
        return None

    def _default_bar_to_current_run(self) -> None:
        """Point the shared bar at the loaded project's current run (#130), so the
        bar reads "Overwrite run N" rather than its empty "New run" default — and
        a plain Generate overwrites that run instead of creating a spurious new
        one. A no-op without a project or controller; the user can still pick
        "New run" explicitly afterwards."""
        ctl = getattr(self, "_target_ctl", None)
        if ctl is None:
            return
        try:
            proj = ctl.project_or_none()
            if proj is None:
                return
            rid = proj.current_run().id
            if ctl.target.profile_run != rid:
                ctl.set_profile_run(rid)
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not default the target bar to the current run: %s", exc)

    def _reset_run_type_for_loaded_project(self) -> None:
        """Put Run type back to Profiling when a project is OPENED.

        Knut asked for this (#130, 2026-07-29): *"When using the load profile
        button in create chart, and then loading a stored project.json file:
        Reset Run type to Profiling, so that all newly loaded charts start at
        its profiling data."* Run type is working state rather than a property
        of the project, and it was simply whatever the previous project had been
        left on.

        **Only on a project load.** It lived in _default_bar_to_current_run at
        first, which every successful generation also calls — including the
        redraw that follows Restore Used Chart. So restoring a verification's
        chart threw the user back to Profiling mid-task, and he could no longer
        tell whether the chart had been replaced at all: *"This should NOT
        happen. Going back to run type profiling automatically shall only happen
        when loading a profile.json file from the load ti1 button in create
        chart tab."*
        """
        ctl = getattr(self, "_target_ctl", None)
        if ctl is None:
            return
        try:
            if ctl.target.is_verification():
                ctl.set_run_type("profiling")
                ctl.set_verification_id("")
        except Exception as exc:      # noqa: BLE001 — never block a load
            log.warning("Could not reset the run type on project load: %s", exc)

    def _builds_into_project(self, proj_before) -> bool:
        """Whether the build about to run targets the project that was loaded
        *before* the name was applied — i.e. an in-project build that must honour
        the Profile-run bar, rather than a build under a new name (its own,
        brand-new project).

        Compares the actual folders, not just their names (#130, Knut): a project
        opened from a SUB-folder of the ChromIQ folder has the same name as the
        ``<ChromIQ>/<name>`` path a fresh project would use, so a name-only check
        called a different folder "the same project".
        """
        if proj_before is None:
            return False
        try:
            return (Path(proj_before.root).resolve()
                    == Path(self._file_mgr.working_dir()).resolve())
        except OSError:                     # unreadable path — assume different
            return False

    def _archive_run_for_replace(self) -> None:
        """Move everything a Replace displaces in the current run to
        ``runs/runN/old/<timestamp>/`` (#130 §5a/§5b) — the run's chart,
        measurement, printer profile, reports and verifications for a Profiling
        build; the verification chart and all dated verifications for a
        Verification build. Never deletes; shares the helper the Print/Measure
        chart import uses, so both Replace paths behave identically."""
        from workflow.chart_import import archive_run_for_replace
        try:
            run = self._file_mgr.project().current_run()
            archive_run_for_replace(
                run, verification=self._is_verification_target())
        except Exception:      # noqa: BLE001 — never block a build on this
            log.warning("Could not archive the run before a Replace build",
                        exc_info=True)

    def rebuild_verification_pages(self) -> bool:
        """Redraw the printable pages of the chart that was just restored, for
        **either** run type (#130, Knut).

        Called after **Restore Used Chart** has put an older chart back: the
        snapshot deliberately holds no page images when the chart carries a
        layout recipe, so the pages are rebuilt here rather than copied. The
        chart's own saved settings are applied first — including the seed it was
        actually shuffled with — so the rebuilt sheet is the sheet that was
        measured: same patch order, patch size, margins and spacers, not
        whatever the panels happen to show.

        Profiling runs kept their own copy only from beta.42 on, and until now
        nothing redrew their pages afterwards: the restore left the chart files
        right but the Create Chart preview empty, which is what Knut saw
        (2026-07-27). Both run types now take the same route; only *which* chart
        files are read differs.

        Returns True when a rebuild was started. Best-effort: a chart that can't
        be rebuilt leaves the restored files in place and says so via the caller.
        """
        ctl = getattr(self, "_target_ctl", None)
        if ctl is None:
            return False
        verification = ctl.target.is_verification()
        try:
            proj = ctl.project_or_none()
            run_id = ctl.target.profile_run
            if proj is None or not run_id or not proj.has_run(run_id):
                return False
            run = proj.run(run_id)
            ti1, ti2 = ((run.verify_chart_ti1, run.verify_chart_ti2)
                        if verification else (run.chart_ti1, run.chart_ti2))
            if not ti1.is_file():
                return False
            # Build the restored chart exactly as it was made: its own recipe
            # first, then the normal build, which lays the pages at the run root
            # — and, for a verification, files them back under verifications/.
            restored_recipe = False
            if ti2.is_file():
                restored_recipe = self._restore_chart_settings(ti2)
            # …and BUILD IN THE MODE THAT RECIPE LANDED IN.
            #
            # Knut, #130 2026-07-29, on Demo-Verify-History: he restored a
            # verification's chart and *"it was clear that the restored chart
            # was very different from the one that was in the verifications
            # folder"*. He was right, and it was not the demo data.
            # _restore_chart_settings fills the MANUAL panels — the engine
            # toggle, the layout recipe, the pinned patch count — but
            # _collect_params() reads whichever mode is on screen, and the app
            # opens in Guided. So every one of those restored settings was
            # discarded and the rebuild laid out a brand-new chart: shuffled
            # where the original was in fixed order, with a fresh seed, 15
            # patches per pass instead of 16 and 60 sets instead of 64.
            if restored_recipe and self._current_mode() != "manual":
                self._switch_mode("manual")
            # SAY SO WHEN THE OPTIONS COULD NOT COME BACK.
            #
            # Knut, #130 2026-07-29: *"after restore of the chart the options in
            # the Create Chart is not changed back to what they were before."*
            # A chart whose stored copy carries its settings sidecar restores
            # them completely — that is checked by test. But a copy taken before
            # the sidecar was included, or a chart made without one, has nothing
            # recording those settings, so the options on screen are simply left
            # alone. That was happening in silence, which is indistinguishable
            # from the restore having failed. Now it is said plainly, together
            # with what IS guaranteed: the chart files themselves are the ones
            # that were measured.
            if not restored_recipe:
                self._log.appendPlainText(tr(
                    "The chart files have been put back exactly as they were "
                    "measured, but this stored chart carries no record of the "
                    "Create Chart options it was made with — so the options on "
                    "screen have been left as they are. Only its patch count "
                    "could be recovered. Charts created from now on always save "
                    "their settings with them, so a later restore will bring "
                    "those back too."))
            if proj.current_run().id != run_id:
                proj.set_current_run(run_id)
            self._arm_verification_snapshot()
            params = self._collect_params()
            params.target_name = self._file_mgr.get_target_name()
            self._pin_restored_recipe(params)
            # THE CHART ITSELF MUST SURVIVE THE REDRAW.
            #
            # Redrawing pages is a rendering job; it is not licence to lay the
            # chart out again. If the rebuild writes a different .ti2 the run's
            # measurement no longer describes the sheet beside it, and nothing
            # warns anybody — the files simply stop agreeing. So the chart is
            # kept and put back if the redraw changes it (Knut, #130
            # 2026-07-29).
            self._rebuild_guard = _ChartRebuildGuard(ti2)
            self._preview.clear()
            self._generate_btn.setEnabled(False)
            self._creator.load_ti1_and_generate_preview(
                ti1, params,
                on_line=self._on_log_line,
                on_finish=self._on_generate_finished,
                # This IS the chart the run's measurement was taken with, so
                # redrawing its pages must not move that measurement aside
                # (Knut, #130 2026-07-27).
                keep_results=True,
            )
            return True
        except Exception:      # noqa: BLE001 — never break a restore
            log.warning("Could not rebuild the restored chart pages",
                        exc_info=True)
            return False

    def _arm_verification_snapshot(self) -> None:
        """Protect the run's PROFILING chart before a verification chart is built
        into the same run root (#130, Knut K3).

        Every build — Generate, a prebuilt preset, a .ti1 preset, a loaded patch
        set — lays its chart down at the run root first; for Run type =
        Verification, ``_on_generate_finished`` then moves it into
        ``verifications/``. Without a snapshot the run's own profiling chart is
        overwritten (and ``reset_chart_artefacts`` clears what's left), so it was
        simply gone once the user switched Run type back to Profiling. Taking the
        snapshot here — the one place every build path passes through before
        starting — is what ``_restore_profiling_chart`` puts back afterwards.
        """
        self._verify_profiling_backup = None
        if self._is_verification_target():
            self._verify_profiling_backup = self._snapshot_profiling_chart()

    def _align_current_run_to_target(self) -> None:
        """Point the loaded project's current run at the shared bar's Profile-run
        selection before a normal build, so the chart is written where the bar
        shows (#130, Knut): **Overwrite run N** → that run's folder; **New run**
        → a fresh ``runs/runN+1/``. Only called for an in-project build (same
        profile name); never for calibration, refinement or a new-name project.

        For "New run" the bar is advanced to the freshly created run so the next
        action targets it too (and so the run stops reading as "New run")."""
        ctl = getattr(self, "_target_ctl", None)
        if ctl is None:
            return
        proj = ctl.project_or_none()
        if proj is None:
            return
        run_id = ctl.target.profile_run
        if run_id and proj.has_run(run_id):
            if proj.current_run().id != run_id:
                proj.set_current_run(run_id)
                log.info("Create Chart: build target run → %s (overwrite)", run_id)
        elif not run_id:                     # "New run"
            new_run = proj.new_run()
            log.info("Create Chart: build target run → %s (new run)", new_run.id)
            ctl.set_profile_run(new_run.id)

    def _no_chart_guidance(self) -> str:
        """Friendly text for the empty preview when the selected Profile-run /
        Run-type has no chart yet (#130, Knut beta-6): explain that nothing is
        wrong and how to make the chart, tailored to Profiling vs Verification."""
        ctl = getattr(self, "_target_ctl", None)
        if ctl is not None and ctl.target.is_verification():
            return tr(
                "No verification chart for this run yet.\n\n"
                "To make one, keep “Run type” set to “Verification”, choose your "
                "chart options above and click “Generate Chart”. Then print that "
                "chart through your finished profile (with colour management on) "
                "and measure it on the Measure tab.")
        return tr(
            "No chart for this profile run yet.\n\n"
            "Choose your chart options above and click “Generate Chart” to make "
            "it. (If you had a chart here before, its files may have been moved "
            "or deleted — just create it again.)")

    def _on_target_changed(self) -> None:
        """React to a Profile-run / Run-type change: show THAT target's chart —
        its own Create-Chart settings + preview — and hand it to Print / Measure,
        so the chart that prints and is measured always matches the selected
        Profile run and Run type (#130, Knut beta-2 tests).

        When the selected target has no chart yet (a fresh run, or a verification
        chart not made yet), the previous chart is CLEARED from the preview and
        from Print / Measure so a stale chart can never linger there; the
        Create-Chart editing settings are left as-is so the new chart can be made."""
        ctl = getattr(self, "_target_ctl", None)
        if ctl is None:
            return
        # #130 Bug C (Knut): if the loaded PROJECT changed (e.g. a Print/Measure
        # load copied a new project into the working folder), reflect its name in
        # the "Printer profile project name" field so it's visibly loaded. Gated
        # on the name actually changing, so run/type toggles within one project
        # never overwrite a name the user is typing.
        # Read the name WITHOUT get_target_name(): that invents and stores a
        # "Printer_Paper_Type_Instr_<timestamp>" name whenever none is set, and
        # the line below would then stamp that invented name straight over what
        # the user had typed — on nothing more than a Run-type toggle. Only a
        # name that genuinely belongs to a loaded project should be reflected.
        cur_name = getattr(self._file_mgr, "_target_name", "")
        if cur_name and cur_name != getattr(self, "_last_shown_project_name", None):
            self._last_shown_project_name = cur_name
            self._update_name_fields()
        resolved = self._resolve_target_chart()
        if resolved is None:
            if self._shown_chart_ti2 is not None:
                self._shown_chart_ti2 = None
                self._shown_chart_stamp = None
                self._preview.clear()
                self._current_ti1_path = None
                # Empty payload → main window drops the chart from Print / Measure.
                self.chart_finished.emit([], None, False)
            # #130 (Knut beta-6): the empty preview must tell the user WHY it's
            # empty and how to fill it — this run/type simply has no chart yet.
            self._preview.set_notice(self._no_chart_guidance())
            return
        ti2, tiffs, ti1 = resolved
        stamp = self._chart_stamp(ti2)
        if stamp is not None and stamp == self._shown_chart_stamp:
            return                               # already showing this exact chart
        self._shown_chart_ti2 = ti2              # set first so the dedup is robust
        self._shown_chart_stamp = stamp
        kind = (tr("verification chart") if ctl.target.is_verification()
                else tr("profiling chart"))
        self._log.appendPlainText(
            tr("Switched to this run's {kind}.").format(kind=kind))
        self._display_run_chart(ti2, tiffs, ti1)

    @staticmethod
    def _chart_stamp(ti2) -> "tuple | None":
        """What makes a chart *this* chart on screen: its path AND when its
        ``.ti2`` was last written.

        The path alone is not enough. Restore Used Chart puts different bytes at
        the SAME path — same run, same stem — so a dedup that compares paths
        decides the chart is already showing and skips the reload. Knut, #130
        2026-07-29: *"pressing Restore Used Chart, I get a warning message
        (good), but the preview is not updated. I have to click NEXT and PREV
        buttons to get the screen to redraw preview."* Regenerating a chart into
        the same run has the same shape, and the overlay had exactly this bug in
        beta.75.
        """
        if ti2 is None:
            return None
        try:
            return (str(ti2), Path(ti2).stat().st_mtime_ns)
        except OSError:
            return (str(ti2), None)

    def _release_rebuild_guard(self) -> None:
        """Put the chart back if redrawing its pages changed it, and say so.

        Called AFTER the verification chart has been filed into
        ``verifications/`` — the build lays its files at the run root and
        ``adopt_run_chart_as_verify`` moves them across, so releasing the guard
        any earlier restores the bytes and then watches the move overwrite them
        again. That is exactly what happened on the first attempt at this fix.
        """
        guard, self._rebuild_guard = getattr(self, "_rebuild_guard", None), None
        if guard is None:
            return
        changed = guard.put_back()
        if not changed:
            return
        try:
            self._log.appendPlainText(tr(
                "Redrawing the pages would have changed the chart itself, so "
                "the restored chart has been put back exactly as it was. Your "
                "measurement still matches the chart file beside it. The pages "
                "shown here were drawn from a different layout — create the "
                "chart again in this tab if you need printable pages."))
        except Exception:      # noqa: BLE001 — never break a finished build
            log.warning("could not report the rebuild guard", exc_info=True)

    def _on_generate_finished(self, tiffs: list[Path]) -> None:
        # Disarm the slow-chart watchdog and dismiss its dialog if it's still
        # open (targen finished/was swapped while the user was deciding).
        self._slow_watchdog.stop()
        if self._slow_dialog is not None:
            from ui.dialogs.slow_chart_dialog import SlowChartDialog
            self._slow_dialog.done(SlowChartDialog.WAIT)
        self._generate_btn.setEnabled(True)
        # One-shot flag: consumed by this run, don't carry over to the next.
        self._preconditioning_from_dialog = False
        self._precond_parent_run_id = None

        # Deliberate user cancel via the watchdog: report it plainly and skip
        # the generic "generation failed" error path below.
        if not tiffs and self._cancelled_by_user:
            self._cancelled_by_user = False
            self._log.appendPlainText(tr("Chart generation cancelled."))
            self._log.ensureCursorVisible()
            return
        is_isis = self._is_isis_selected()
        # File stem is fixed by the folder layout ("chart" / "calibration").
        # Derive it from the actual page bitmaps so it's correct regardless of
        # which flow produced them; fall back to "chart" when none exist.
        if tiffs:
            m = re.match(r"(.+?)_\d+$", tiffs[0].stem)
            stem = m.group(1) if m else tiffs[0].stem
        else:
            stem = "chart"

        # #130: when the user chose Run type = Verification, move the just-
        # generated chart into the run's verifications/ folder as its shared
        # verify chart, then continue with the moved files (preview, meta,
        # sidecars and the chart_finished signal all use the verify paths).
        # Guarded — profiling generation is completely untouched.
        if tiffs and self._is_verification_target():
            try:
                run = self._file_mgr.project().current_run()
                new_ti2 = run.adopt_run_chart_as_verify()
                if new_ti2 is not None:
                    tiffs = run.verify_chart_tiffs()
                    stem = run.verify_stem
                    self._log.appendPlainText(tr(
                        "This chart was saved as the run's verification chart "
                        "(in the “verifications” folder). Print it through your "
                        "finished profile, then measure it with the run type set "
                        "to Verification."))
            except Exception:  # noqa: BLE001 — never break a finished generation
                log.warning("verify-chart adopt failed", exc_info=True)
            # Put the profiling chart back at the run root — the verify chart now
            # lives only in verifications/, and the two must coexist (#130, Knut).
            self._restore_profiling_chart()
        else:
            # ONLY when the build produced no chart: it failed or was cancelled,
            # so the release further down (after the auto-tag) is never reached
            # and nothing else would free the guard.
            #
            # A SUCCESSFUL profiling build must not release it here. This branch
            # was written when a profiling build could never arm the guard, but
            # since beta.42 a profiling run keeps its own chart copy and the
            # redraw that follows Restore Used Chart arms the guard for it. This
            # point is BEFORE `_maybe_autotag_randomised`, which upgrades a
            # well-mixed fixed-order chart from CHART_ID to RANDOM_START — so
            # releasing here put the restored bytes back and then re-tagged them
            # a line later, and the restored chart came out marked as shuffled
            # when it had been laid out in fixed order. chartread reads those two
            # differently, so the run's measurement described a sheet that no
            # longer existed, silently. Exactly the beta.97 fault, on the
            # profiling path (#130, found while reproducing Knut's beta.98
            # report).
            if not tiffs:
                self._release_rebuild_guard()
            # The run root has already been cleared when a verification build
            # failed, so put the snapshot back rather than dropping it — a failed
            # verification chart must not cost the run its profiling work.
            self._restore_profiling_chart()

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
            self._preview.set_notice(None)   # chart just made — drop any guidance
            self._preview.load_tiff(tiffs)
            log.info("Preview loaded: %d TIFF(s)", len(tiffs))
            ti2 = tiffs[0].parent / f"{stem}.ti2"
            # #130 Bug 1 (Knut): save this chart's printtarg fields with it, so
            # switching Run type later shows THIS chart's printtarg settings
            # (not the last preset's). Engine charts restore from their recipe
            # instead; this is the printtarg-chart counterpart.
            self._store_printtarg_fields_in_sidecar(ti2)
            # Record the chart's instrument + paper in the run's meta.json,
            # mirroring what the TI2 layout editor writes (see
            # workflow.ti2_relayout.save_editor_meta). The .ti2 carries these
            # too, but stamping them in meta.json keeps the run folder
            # self-describing. Read straight from the just-written .ti2 so it's
            # correct for every creation path (normal / prebuilt / from-.ti1).
            self._stamp_chart_meta(ti2)
            # Always leave the hand-off sidecars with the chart — the colour
            # list and the i1Profiler pair — so every generated chart is
            # self-contained for users who profile elsewhere, not only the i1iSis
            # flow (Knut). They go into the exports/ sub-folder (#127); works
            # for run folders and cal/ alike since the folder is derived from
            # wherever the chart was generated. The .cht comes from the build
            # itself (engine emit_cht / printtarg). Best-effort; the colour
            # list skips CMYK charts.
            try:
                from core.file_manager import exports_subdir
                from workflow.chart_exports import write_sidecars
                extras = write_sidecars(
                    ti2.with_suffix(".ti1"), exports_subdir(ti2.parent), stem,
                    also_shuffled=self._settings.get("export_shuffled_pxf", False))
                for e in extras:
                    self._log.appendPlainText(f"wrote {e.name}")
            except Exception:  # noqa: BLE001 — never block on the sidecars
                log.warning("chart sidecar export failed", exc_info=True)
            # If this chart was laid out in fixed order (-r "Preserve Patch
            # Order", e.g. a pre-shuffled generate-colour-sets / editor-recipe
            # layout) but its colours are actually well mixed, upgrade the tag so
            # chartread can read it bidirectionally — the same auto-tag the TI2
            # layout editor does on save. No-op for the common case (printtarg
            # randomises by default → already RANDOM_START).
            self._maybe_autotag_randomised(ti2)
            # AFTER the auto-tag, which is the last thing that writes to the
            # chart. Releasing the guard before it meant the bytes were put back
            # and then re-tagged a line later — the restored chart came out
            # marked RANDOM_START when it had been laid out in fixed order, and
            # chartread reads those two differently.
            self._release_rebuild_guard()
            # If the patch set leaves a notably under-filled last page (or spilled
            # onto a near-empty extra page), offer to edit the patch set (#93, Knut).
            self._maybe_warn_partial_last_page(ti2)
            # Remember the .ti1 backing this chart so the Save Preset dialog can
            # offer to attach it.
            ti1 = tiffs[0].parent / f"{stem}.ti1"
            self._current_ti1_path = ti1 if ti1.is_file() else None
            # Baseline the auto-preview signature to what we just rendered, so the
            # refresh this generation triggers doesn't immediately re-render.
            self._last_auto_sig = self._layout_signature()
            self._set_margin_chart(tiffs, ti2)
            # #79: arm the one-shot Guided→Manual transfer when this chart was
            # built in Guided mode, so opening Manual seeds the recipe used.
            self._guided_transfer_pending = (self._current_mode() == "guided")
            # Track the just-built chart so a later Run-type switch back to it
            # doesn't needlessly reload (#130).
            self._shown_chart_ti2 = ti2
            self._shown_chart_stamp = self._chart_stamp(ti2)
            # #130: default the shared bar to the run we just built into, so a
            # plain re-Generate OVERWRITES it instead of spuriously creating a new
            # run (the bar's empty default reads as "New run").
            self._default_bar_to_current_run()
            self.chart_finished.emit(tiffs, ti2, is_isis)
        else:
            self._set_margin_chart([], None)
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
                elif self._creator.unmatched_failure() is not None:
                    # No pattern recognised the message — but the tool DID report
                    # one, and the user is still owed a word rather than an empty
                    # preview (Knut, #130 2026-07-30: printtarg refused his chart
                    # with "Input file doesn't contain two or three tables", which
                    # nothing here knew, so no window ever appeared).
                    #
                    # Gated on the tool having said something: a build that ends
                    # with no output at all — a cancel, or a caller driving this
                    # handler directly — has nothing to report, and a window
                    # saying "no further detail" would be noise. It also kept a
                    # test waiting forever on a modal nobody could dismiss.
                    raw = self._creator.unmatched_failure()
                    said = raw[1]
                    InfoDialog(
                        tr("The chart could not be built"),
                        tr("ChromIQ could not build this chart, so the preview "
                           "is empty. Your chart files and any measurement in "
                           "this run are untouched.\n\n"
                           "This is what the tool reported:\n\n{said}\n\n"
                           "If this happened just after “Restore Used Chart”, the "
                           "chart itself is safely back — only its printable "
                           "pages could not be redrawn, and you can create the "
                           "chart again in this tab when you need to print it."
                           ).format(said=said),
                        self, min_width=560).exec()

    # ------------------------------------------------------------------
    # Margin inspector
    # ------------------------------------------------------------------
    def _set_margin_chart(self, tiffs: "list[Path]", ti2: "Path | None") -> None:
        """Record the chart now in the preview and refresh the margin inspector."""
        self._margin_tiffs = list(tiffs or [])
        self._margin_ti2 = ti2 if (ti2 and Path(ti2).is_file()) else None
        self._update_margin_inspector()
        self._update_layout_info()

    def _onscreen_patch_total(self) -> "int | None":
        """Patch count of the chart currently in the preview (its .ti2
        NUMBER_OF_SETS), or None when nothing is generated. Lets the estimate lay
        out the SAME patches the on-screen chart has under the current settings,
        instead of a capacity-fill (#93, Knut beta-13: estimate pages were wrong
        for a loaded chart)."""
        ti2 = getattr(self, "_margin_ti2", None)
        if not ti2 or not getattr(self, "_margin_tiffs", None):
            return None
        try:
            import re
            m = re.search(r"NUMBER_OF_SETS\s+(\d+)",
                          Path(ti2).read_text(errors="replace"))
            return int(m.group(1)) if m else None
        except Exception:
            return None

    def _predict_layout_info(self, geom, paper: str, pages_req: int,
                             npat: "int | None" = None) -> None:
        """Fill the Chart-layout-information panel with the engine's predicted
        grid (#93). With *npat* (the on-screen chart's patch count) the SAME
        patches are laid out under the current settings; otherwise a capacity-
        filled layout of *pages_req* pages is shown (the auto-count prediction)."""
        panel = getattr(self, "_layout_info_panel", None)
        if panel is None:
            return
        try:
            from workflow.layout_engine import geometry, papers
            w_mm, h_mm = papers.dimensions_mm(paper)
            per_sheet = geometry.patches_per_sheet(geom, w_mm, h_mm)
            if not per_sheet:
                panel.show_placeholder()
                return
            total = npat if npat else per_sheet * max(1, pages_req)
            lay = geometry.compute(geom, w_mm, h_mm, total)
            rows = lay.steps_in_pass
            n0 = min(lay.total_patches, lay.patches_per_page)
            cols = (n0 + rows - 1) // rows if rows else 0
            panel.set_estimate(total=lay.total_patches, rows=rows, cols=cols,
                               pages=lay.pages, patch_w=geom.pwid, patch_h=geom.plen,
                               page_patches=n0,
                               fillup=getattr(lay, "padding", None))
        except Exception:
            panel.clear_estimate()

    def _update_layout_info(self) -> None:
        """Fill the on-screen column of the Chart-layout-information panel from
        the previewed chart's .ti2 (patch count, strip grid) + page TIFFs (#93).
        The estimate column is driven separately by the live predictors."""
        panel = getattr(self, "_layout_info_panel", None)
        if panel is None:
            return
        show = bool(self._settings.get("layout_info_show", True))
        panel.setVisible(show)
        if not show:
            return
        tiffs = getattr(self, "_margin_tiffs", None)
        ti2 = getattr(self, "_margin_ti2", None)
        if not tiffs or not ti2:
            panel.clear_actual()
            return
        try:
            import re
            from core.strip_utils import parse_passes_per_page
            txt = Path(ti2).read_text(errors="replace")
            total = int(re.search(r"NUMBER_OF_SETS\s+(\d+)", txt).group(1))
            _m = re.search(r'STEPS_IN_PASS\s+"?(\d+)"?', txt)
            rows = int(_m.group(1)) if _m else 0
            passes = parse_passes_per_page(ti2) or []
            idx = self._preview.current_page()
            if not (0 <= idx < len(passes)):
                idx = 0
            cols = passes[idx] if passes else 0
            pw, ph = self._chart_patch_size_mm(ti2)
            # Patches on the SHOWN page: full passes are `rows` tall; the chart's
            # last pass may be partial, so cap by the remaining count (#93, Knut).
            before = rows * sum(passes[:idx]) if passes else 0
            page_patches = (min(rows * cols, total - before)
                            if rows and cols else None)
            # Fill-up count = laid-out total minus the designed patch count (the
            # .ti1 next to the .ti2): a partial last strip is topped up with
            # paper-white patches, and this row is where Knut read the grown
            # total without an explanation (#124 follow-up).
            designed = _number_of_sets(Path(ti2).with_suffix(".ti1"))
            fillup = (total - designed
                      if designed is not None and 0 <= total - designed else None)
            panel.set_actual(total=total, rows=rows, cols=cols, pages=len(tiffs),
                             patch_w=pw, patch_h=ph, page_patches=page_patches,
                             fillup=fillup)
        except Exception:
            panel.clear_actual()

    @staticmethod
    def _chart_patch_size_mm(ti2: "Path") -> "tuple[float, float]":
        """Patch (width, height) in mm of the previewed chart, from its engine
        ``channels.json`` patch rects (px → mm). (0, 0) for printtarg charts /
        when unavailable (#93)."""
        try:
            import json
            sidecar = Path(ti2).with_suffix(".channels.json")
            if not sidecar.is_file():
                return (0.0, 0.0)
            doc = json.loads(sidecar.read_text())
            layout = doc.get("layout") or {}
            rects = layout.get("patches") or []
            recipe = layout.get("recipe") or {}
            dpi = float(recipe.get("dpi") or 300)
            if not rects or dpi <= 0:
                return (0.0, 0.0)
            r0 = rects[0]
            return (r0["w"] * 25.4 / dpi, r0["h"] * 25.4 / dpi)
        except Exception:
            return (0.0, 0.0)

    def _update_margin_inspector(self) -> None:
        panel = getattr(self, "_margin_panel", None)
        if panel is None:
            return
        tiffs = getattr(self, "_margin_tiffs", None)
        show = bool(self._settings.get("margin_inspector_show", True))
        panel.setVisible(show)
        if not show or not tiffs:
            panel.show_placeholder()
            self._preview.set_margin_guides(None)
            self._preview.set_measured_guides(None)
            return

        from workflow.margin_inspector import measure_margins, check_violations
        from core.settings import margin_combo_key

        # ChromIQ always renders with printtarg -M (the margin is kept inside the
        # TIFF), so the page TIFF already spans the full sheet — the TIFF's own
        # size is the page. Do NOT pass a paper size here: the Create Chart paper
        # combo can be stale relative to the chart actually in the preview (e.g.
        # after loading a preset), and a wrong paper size would inflate every
        # measured margin by the bogus (paper − tiff)/2 offset (#83).
        dpi = float(self._settings.get("printtarg_dpi", 300) or 300)
        # Measure the page CURRENTLY SHOWN in the preview, so the numbers, the
        # threshold guides and the visible patches all describe the same page.
        # Multi-page charts have different per-page margins, so measuring a
        # different page than the one on screen made the guides land away from
        # the patches (#83). Re-runs when the user pages through (page_changed).
        idx = self._preview.current_page()
        if not (0 <= idx < len(self._margin_tiffs)):
            idx = 0
        # Engine charts: report EXACT margins/patch size from the recorded
        # geometry (channels.json) instead of detecting them from the image —
        # the image detector mis-reads the patch width as the strip pitch and a
        # large Strip gap corrupts the detected margins (#93, Knut). Falls back to
        # image measurement for printtarg charts.
        self._ruler_over_mm = None
        _geom_ruler = None
        report = None
        if self._margin_ti2 is not None:
            from workflow.margin_inspector import measure_from_engine
            ch = Path(self._margin_ti2).with_suffix(".channels.json")
            eng = measure_from_engine(ch, idx) if ch.is_file() else None
            if eng is not None:
                report, _geom_ruler = eng
        if report is None:
            report = measure_margins(self._margin_tiffs[idx], dpi=dpi,
                                     ti2_path=self._margin_ti2)
        if report is None:
            panel.show_placeholder()
            self._preview.set_margin_guides(None)
            self._preview.set_measured_guides(None)
            return

        # An engine chart records the instrument it was actually laid out for.
        # Trust that over the printtarg -i widget, which is hidden and stale
        # while the layout engine is on — reading it there fell back to "i1" and
        # judged a ColorMunki chart against i1Pro's margins (Knut, #130
        # 2026-07-27).
        instr_flag = self._chart_instrument_flag() or self._active_instrument_flag()
        instr_label = _MARGIN_INSTR_LABEL.get(instr_flag, "i1Pro")
        paper_name = _canonical_paper_name(report.page_w_mm, report.page_h_mm)
        orient = "Landscape" if report.page_w_mm > report.page_h_mm else "Portrait"
        # Which minimums this chart is judged against (Knut, #130 2026-07-27).
        # With "Use instrument margins" ON: the per-instrument minimums from
        # Preferences. With it OFF: the margins the chart was actually laid out
        # to — the user still wants to know when a printed margin came out
        # under what they asked for; they only declined the instrument's
        # guideline, not the check itself.
        thresholds = self._chart_own_margins()
        if thresholds is None and paper_name:
            key = margin_combo_key(instr_label, paper_name, orient)
            thresholds = self._settings.get_margin_thresholds().get(key)

        # Strip-length (ruler) limit: the per-combo value configured in
        # Preferences → Instrument Limits wins; else the instrument's built-in ruler
        # reported by the engine geometry (#93, Knut). Warn when the strip is over.
        _eff_ruler = _geom_ruler
        try:
            _cfg = float((thresholds or {}).get("ruler") or 0.0)
            if _cfg > 0:
                _eff_ruler = _cfg
        except (TypeError, ValueError):
            pass
        if (_eff_ruler and report.strip_length_mm is not None
                and report.strip_length_mm > _eff_ruler + 0.5):
            self._ruler_over_mm = _eff_ruler

        violations = check_violations(report, thresholds)
        warns = self._engine_text_overflow_warnings()
        if getattr(self, "_ruler_over_mm", None):
            warns = list(warns) + [tr(
                "⚠ Strip length {len:.0f} mm exceeds the {ruler:.0f} mm "
                "instrument ruler — the strip may not fit your jig").format(
                    len=report.strip_length_mm or 0.0, ruler=self._ruler_over_mm)]
        panel.update_report(
            report, violations,
            thresholds_defined=bool(thresholds),
            notify=bool(self._settings.get("margin_violation_notify", True)),
            thresholds=thresholds,
            text_warnings=warns,
        )
        self._refresh_margin_guides(report, thresholds, violations)
        self._refresh_measured_guides(report)

    def _refresh_measured_guides(self, report) -> None:
        """Push long purple/blue lines at the measured margins (patch-area edges)
        to the preview, when the second checkbox is on (#89)."""
        panel = getattr(self, "_margin_panel", None)
        if panel is None or not panel.measured_guides_enabled() or report is None:
            self._preview.set_measured_guides(None)
            return
        pw, ph = report.page_w_mm, report.page_h_mm
        guides: list[tuple[str, float]] = []
        if pw > 0:
            guides.append(("v", report.left_mm / pw))
            guides.append(("v", 1.0 - report.right_mm / pw))
        if ph > 0:
            guides.append(("h", report.top_mm / ph))
            guides.append(("h", 1.0 - report.bottom_mm / ph))
        self._preview.set_measured_guides(guides or None)

    def _engine_text_overflow_warnings(self) -> "list[str]":
        """Warnings for when a page margin is too small to hold the text band that
        side carries (margins are the law, so the text overflows toward the page
        edge — flag it below the preview, by the margin violations) (#93, Knut).
        Engine-Manual only; empty otherwise."""
        warns: list[str] = []
        try:
            manual = (self._manual_btn is not None and self._manual_btn.isChecked())
            if not (manual and getattr(self, "_manual_layout_panel", None) is not None
                    and bool(self._settings.get("use_chromiq_layout_engine", False))):
                return warns
            r = self._current_layout_recipe()
            # The text-overflow warning only applies in "margins are law" mode,
            # which is now AREA-FIRST (Knut #93): there the label/text lives inside
            # the margin, so a too-small margin overflows toward the page edge. In
            # patch-first the band is reserved above/below the patches — no overflow.
            if r.layout_mode != "area_first":
                return warns
            from workflow.layout_engine import instruments
            geom = instruments.geom_from_build_kwargs(r.build_kwargs())
            lab = geom.label_band_mm if geom.label_band_mm >= 0 else geom.txhisl
            if r.show_strip_indicators and lab > 0 and \
                    r.margin_top + 0.05 < r.text_edge_top_mm + lab:
                warns.append(tr("⚠ Top margin is too small for the strip labels — "
                                "they overflow toward the page edge."))
            nlines = (1 if r.chart_text else 0) + (1 if r.stamp_command else 0)
            if nlines and r.margin_bottom + 0.05 < r.text_edge_mm + 4.2 * nlines:
                warns.append(tr("⚠ Bottom margin is too small for the sheet text — "
                                "it overflows toward the page edge."))
        except Exception:  # noqa: BLE001 — never block the inspector on this
            pass
        return warns

    def _refresh_margin_guides(self, report, thresholds, violations) -> None:
        """Push dotted threshold guide lines to the preview (or clear them)."""
        panel = getattr(self, "_margin_panel", None)
        if panel is None or not panel.guides_enabled() or not thresholds:
            self._preview.set_margin_guides(None)
            return
        violated = {v.edge for v in violations}
        guides: list[tuple[str, float, bool]] = []
        # (key, edge, axis, page-extent, measured-from-start)
        specs = (
            ("L", "Left", "v", report.page_w_mm, True),
            ("R", "Right", "v", report.page_w_mm, False),
            ("T", "Top", "h", report.page_h_mm, True),
            ("B", "Bottom", "h", report.page_h_mm, False),
        )
        for key, edge, axis, extent, from_start in specs:
            raw = thresholds.get(key)
            if raw in (None, "") or not extent:
                continue
            try:
                thr = float(raw)
            except (TypeError, ValueError):
                continue
            frac = (thr / extent) if from_start else (1.0 - thr / extent)
            guides.append((axis, frac, edge in violated))
        self._preview.set_margin_guides(guides or None)

    def _on_margin_guides_toggled(self, on: bool) -> None:
        self._settings.set("margin_guides_show", bool(on))
        self._update_margin_inspector()

    def _on_margin_measured_guides_toggled(self, on: bool) -> None:
        self._settings.set("margin_measured_guides_show", bool(on))
        self._update_margin_inspector()

    def _on_margin_coords_toggled(self, on: bool) -> None:
        self._settings.set("margin_coords_show", bool(on))
        self._preview.set_coord_readout(
            bool(on), float(self._settings.get("printtarg_dpi", 300) or 300))

    def _chart_own_margins(self) -> "dict | None":
        """The margins this chart was laid out to, when it declined the
        instrument's minimums — otherwise None, so the caller falls back to
        Preferences (Knut, #130 2026-07-27).

        Returned in the same shape as a Preferences threshold row, so the panel
        compares and reports it identically.
        """
        try:
            import json
            if self._margin_ti2 is None:
                return None
            ch = Path(self._margin_ti2).with_suffix(".channels.json")
            if not ch.is_file():
                return None
            recipe = (json.loads(ch.read_text()).get("layout") or {}).get("recipe")
            if not isinstance(recipe, dict):
                return None
            if recipe.get("use_instrument_margins", True):
                return None            # judged against the instrument instead
            return {
                "L": float(recipe.get("margin_left", 0.0)),
                "R": float(recipe.get("margin_right", 0.0)),
                "T": float(recipe.get("margin_top", 0.0)),
                "B": float(recipe.get("margin_bottom", 0.0)),
                "desc": tr("the margins this chart was laid out to"),
            }
        except Exception:      # noqa: BLE001 — the inspector must never crash
            return None

    def _chart_uses_instrument_margins(self) -> bool:
        """Whether the chart in the preview was built with the instrument's
        margin minimums enforced.

        Only an engine chart records the choice; anything else (a printtarg
        chart, or no chart at all) is judged as before.
        """
        try:
            import json
            if self._margin_ti2 is None:
                return True
            ch = Path(self._margin_ti2).with_suffix(".channels.json")
            if not ch.is_file():
                return True
            doc = json.loads(ch.read_text())
            layout = doc.get("layout") or {}
            recipe = layout.get("recipe")
            if not isinstance(recipe, dict) or "use_instrument_margins" not in recipe:
                return True
            return bool(recipe["use_instrument_margins"])
        except Exception:      # noqa: BLE001 — the inspector must never crash
            return True

    def _chart_instrument_flag(self) -> str:
        """The instrument recorded in the chart's own layout recipe, or "".

        Only a ChromIQ-engine chart has one. It is the truth about the chart in
        the preview, whereas the printtarg widget describes what the panel would
        build next — and with the engine on, that widget is not even shown.
        """
        try:
            import json
            if self._margin_ti2 is None:
                return ""
            ch = Path(self._margin_ti2).with_suffix(".channels.json")
            if not ch.is_file():
                return ""
            doc = json.loads(ch.read_text())
            recipe = (doc.get("layout") or {}).get("recipe") or {}
            return str(recipe.get("instrument") or "")
        except Exception:      # noqa: BLE001 — the inspector must never crash
            return ""

    def _active_instrument_flag(self) -> str:
        """The instrument the chart in the preview was built with. In Manual mode
        that is the manual -i widget; otherwise the Guided instrument combo. Used
        so the margin combo follows the chart, not a stale mode's control (#81)."""
        if self._manual_btn is not None and self._manual_btn.isChecked():
            for pw in self._manual_widgets.get("printtarg", []):
                if pw.flag == "-i":
                    return str(pw.get_raw_value() or "i1")
        combo = getattr(self, "_instr_combo", None)
        return (combo.currentData() if combo is not None else "i1") or "i1"

    def _active_paper_code(self) -> str:
        """The paper code currently selected (manual -p in Manual mode, else the
        Guided paper combo)."""
        if self._manual_btn is not None and self._manual_btn.isChecked():
            for pw in self._manual_widgets.get("printtarg", []):
                if pw.flag == "-p":
                    return str(pw.get_raw_value() or "A4")
        combo = getattr(self, "_paper_combo", None)
        return (combo.currentData() if combo is not None else "A4") or "A4"

    def current_margin_combo(self) -> "tuple[str, str, str] | None":
        """The (instrument label, paper name, orientation) the Margin Thresholds
        tab should preselect (#80/#81). Always follows the active mode's current
        instrument + paper *selection* — what the user is looking at in the
        dropdowns — so Preferences opens on it immediately, even before a chart
        is generated and regardless of any chart still in the preview."""
        instr_label = _MARGIN_INSTR_LABEL.get(self._active_instrument_flag())
        code = self._active_paper_code()
        if not instr_label or not code:
            return None
        dims = _PAPER_MM.get(code)
        if dims is None and "x" in str(code):
            try:
                w, h = str(code).split("x", 1)
                dims = (float(w), float(h))
            except ValueError:
                dims = None
        if dims is None:
            return None
        paper_name = _canonical_paper_name(dims[0], dims[1])
        if not paper_name:
            return None
        orient = "Landscape" if dims[0] > dims[1] else "Portrait"
        return (instr_label, paper_name, orient)

    def current_layout_combo(self) -> "tuple[str, str, str] | None":
        """The (engine instrument, paper code, layout mode) the Chart Layout tab
        should preselect (#93), mirroring :meth:`current_margin_combo`. Follows
        the live engine recipe in Manual when present, else the active
        instrument + paper selection — so Preferences opens on what the user is
        editing, instead of always resetting to i1/A4 (which made a preset saved
        under any other combination look lost)."""
        try:
            if (self._manual_btn is not None and self._manual_btn.isChecked()
                    and getattr(self, "_manual_layout_panel", None) is not None):
                r = self._current_layout_recipe()
                return (r.instrument, r.paper, r.mode())
        except Exception:
            pass
        instr = {"3p": "p3"}.get(self._active_instrument_flag(),
                                 self._active_instrument_flag())
        if instr not in ("i1", "p3", "CM", "SS"):
            instr = "i1"
        paper = self._active_paper_code() or "A4"
        try:
            from workflow.layout_engine.presets import default_recipe
            mode = default_recipe(instr, paper).mode()
        except Exception:
            mode = "clip" if instr in ("i1", "p3") else (
                "freehand" if instr == "CM" else "flat")
        return (instr, paper, mode)

    def refresh_margin_inspector_settings(self) -> None:
        """Re-read the Create-Chart preview-panel settings after the Preferences
        dialog closes (margin-inspector visibility, notify, thresholds, and the
        Chart-layout-information panel's visibility may have changed)."""
        panel = getattr(self, "_margin_panel", None)
        if panel is not None:
            panel.set_guides_checked(
                bool(self._settings.get("margin_guides_show", False)))
            panel.set_measured_guides_checked(
                bool(self._settings.get("margin_measured_guides_show", False)))
        self._update_margin_inspector()
        self._update_layout_info()

    def _last_page_capacity(self, ti2: Path) -> int:
        """How many patches a sheet of this chart's layout holds, or 0.

        Reported beside the free-slot count so the number in the window can be
        checked against the patch count already on screen.
        """
        try:
            from workflow.layout_engine.presets import LayoutRecipe
            from workflow.layout_engine import instruments, geometry, papers
            rec = LayoutRecipe.from_channels_json(
                Path(ti2).with_suffix(".channels.json"))
            if rec is None:
                return 0
            geom = instruments.geom_from_build_kwargs(rec.build_kwargs())
            w_mm, h_mm = papers.dimensions_mm(rec.paper)
            return max(0, int(geometry.patches_per_sheet(geom, w_mm, h_mm)))
        except Exception as exc:  # noqa: BLE001 — never block a hint
            log.debug("last-page capacity unavailable: %s", exc)
            return 0

    #: How full the last page must be before "it doesn't quite fill" is a fair
    #: description of it. Below this the chart is not *almost* full, it is
    #: mostly empty, and the hint is noise (see _partial_last_page_blank).
    _PARTIAL_PAGE_MIN_FILL = 0.5

    def _partial_last_page_blank(self, ti2: Path) -> "int | None":
        """Engine charts only: the number of unused patch slots on the last page
        when that page is nearly — but not quite — full, else None. Pure so it's
        unit-testable (#93).

        The gap used to be "at least one empty strip", which is true of an
        almost-full page and equally true of an almost-empty one. Knut, #130
        2026-08-01, on a 12-patch chart:

            *"I get message 'Your patch set doesn't quite fill the last page -
            there's space for about 670 more patches'. Simultaneously the total
            patches count below the preview says 12 patches … The number in the
            message is wrong."*

        The arithmetic was right — the sheet really did have room for 670 more —
        but nothing else about it was. A 12-patch chart has not *almost* filled
        its page, and "add a few more patches to fill the gap" is not advice
        anybody can act on when the gap is fifty times the chart. So the hint
        now only appears once the page is at least half full, which is what
        "doesn't quite fill" means to a reader.
        """
        try:
            from workflow.layout_engine.presets import LayoutRecipe
            from workflow.layout_engine import instruments, geometry, papers
            ch = Path(ti2).with_suffix(".channels.json")
            rec = LayoutRecipe.from_channels_json(ch)
            if rec is None:
                return None                  # printtarg chart — no engine layout
            m = re.search(r"NUMBER_OF_SETS\s+(\d+)",
                          Path(ti2).read_text(errors="replace"))
            if not m:
                return None
            total = int(m.group(1))
            geom = instruments.geom_from_build_kwargs(rec.build_kwargs())
            w_mm, h_mm = papers.dimensions_mm(rec.paper)
            per = geometry.patches_per_sheet(geom, w_mm, h_mm)
            if per <= 0 or total <= 0:
                return None
            lay = geometry.compute(geom, w_mm, h_mm, total)
            steps = lay.steps_in_pass or 1
            on_last = total - (lay.pages - 1) * per
            blank = per - on_last
            if blank < steps:
                return None            # full enough; nothing worth saying
            if on_last < per * self._PARTIAL_PAGE_MIN_FILL:
                return None            # mostly empty — not an almost-full page
            return blank
        except Exception as exc:  # noqa: BLE001
            log.debug("partial-last-page check skipped: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Auto-update preview (Knut): live-refresh on layout changes
    # ------------------------------------------------------------------
    def _on_auto_preview_toggled(self, on: bool) -> None:
        """Persist the auto-update-preview choice; confirm with the user the first
        time they turn it on so they know what it does (Knut)."""
        self._settings.set("auto_update_preview", bool(on))
        # Knut's rule: the "preview is not being re-drawn" window comes once per
        # switch-on, so switching on re-arms it (see _say_preview_is_paused).
        self._said_auto_update_paused = False
        if on:
            InfoDialog(
                tr("Auto-update preview is on"),
                tr("From now on, the chart preview will refresh automatically "
                   "whenever you change a layout setting — margins, patch size, "
                   "columns, spacers, the clip border, and so on — once you've "
                   "generated or loaded a chart.\n\n"
                   "To keep it quick, ChromIQ re-lays-out the patches already in "
                   "your chart; it does not pick new colours or re-run the patch "
                   "generator. While this is on, the “there's a little room left "
                   "on the last page” reminder is hidden so it doesn't interrupt "
                   "you — you can still open the patch-set editor whenever you "
                   "like to add or remove patches.\n\n"
                   "Turn the option off any time to go back to refreshing the "
                   "preview only when you click Generate Chart."),
                self, min_width=560,
            ).exec()
        else:
            self._auto_preview_timer.stop()

    def _layout_signature(self) -> "str | None":
        """A cheap fingerprint of the current layout settings, so the auto-preview
        only re-renders when something actually changed (and the post-render
        refresh doesn't loop)."""
        try:
            if (bool(self._settings.get("use_chromiq_layout_engine", False))
                    and getattr(self, "_manual_layout_panel", None) is not None):
                # Via _current_layout_recipe so a Settings styling change also
                # counts as a layout change and re-triggers the auto-preview.
                return repr(self._current_layout_recipe().to_dict())
            return repr(self._printtarg_signature())
        except Exception:  # noqa: BLE001
            return None

    def _maybe_schedule_auto_preview(self) -> None:
        """Start the debounce timer to re-render the preview, if auto-update is on,
        a chart already exists, nothing is running, and the layout actually
        changed since the last render."""
        if not bool(self._settings.get("auto_update_preview", False)):
            return
        # Manual mode only — ignored in Guided even if the option is on (Knut).
        if self._current_mode() != "manual":
            return
        if self._runner.is_running:
            return
        ti1 = getattr(self, "_current_ti1_path", None)
        if not (ti1 is not None and ti1.is_file()):
            return
        if self._layout_signature() == self._last_auto_sig:
            return
        self._auto_preview_timer.start(450)

    def _auto_regenerate_preview(self) -> None:
        """Re-lay-out the current chart's patch set with the current layout, to
        refresh the preview live (Knut). Fast: no targen, same patches."""
        if (self._runner.is_running
                or self._current_mode() != "manual"
                or not bool(self._settings.get("auto_update_preview", False))):
            return
        ti1 = getattr(self, "_current_ti1_path", None)
        if not (ti1 is not None and ti1.is_file()):
            return
        # Record the signature we're about to render so the post-render refresh
        # (same layout) doesn't immediately re-schedule another render.
        # §4: the auto-update preview re-lays out the chart in the run, which
        # would leave the measurement describing patch positions that are no
        # longer on the sheet. A window here would open on every turn of a
        # layout knob, so this path declines instead and says so once — the
        # Generate Chart button still offers the full choice.
        from workflow.chart_integrity import assess_profiling_chart
        try:
            _run = self._file_mgr.project().current_run()
        except Exception:      # noqa: BLE001
            _run = None
        if assess_profiling_chart(_run).warn:
            self._say_preview_is_paused()
            return
        self._last_auto_sig = self._layout_signature()
        self._generate_from_ti1(ti1, ask=False)

    #: Message text — the same sentences on screen and in the log, so a user
    #: comparing the two never wonders whether they mean different things.
    PREVIEW_PAUSED_TITLE = "The live preview is not being re-drawn"

    def _preview_paused_body(self) -> str:
        return tr(
            "This run already holds work made with the chart the preview would "
            "replace, so the preview is left as it is rather than re-drawn "
            "over it.\n\n"
            "Press “Generate Chart” when you want the new layout. You will be "
            "told exactly what moves to the run's “old” folder first, and "
            "nothing is deleted.\n\n"
            "This window appears once each time you switch “Auto-update "
            "preview” on. While it stays on, the same note goes to the log "
            "instead, so your layout work is not interrupted.")

    def _say_preview_is_paused(self) -> None:
        """§4, auto-update — Knut's ruling in beta.125.

        He accepted that a window on every turn of a knob would be unusable,
        and set the rule: *"the popup window saying 'The live preview is not
        being re-drawn...' should come once only, then again the next time
        'auto-update preview ...' is enabled. At the same time it can come in
        the log window until 'auto-update preview ...' is disabled."*

        So: the log line every time, the window only on the first refusal after
        the option was switched on. :meth:`_on_auto_preview_toggled` re-arms it.
        """
        self._log.appendPlainText(
            tr(self.PREVIEW_PAUSED_TITLE) + " — " + self._preview_paused_body()
            .replace("\n\n", " "))
        if getattr(self, "_said_auto_update_paused", False):
            return
        self._said_auto_update_paused = True
        from PyQt6.QtWidgets import QMessageBox

        from ui.widgets import fit_message_box_buttons
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        title = tr(self.PREVIEW_PAUSED_TITLE)
        box.setWindowTitle(title)
        box.setText(title)
        box.setInformativeText(self._preview_paused_body())
        box.addButton(tr("OK"), QMessageBox.ButtonRole.AcceptRole)
        fit_message_box_buttons(box)
        box.exec()

    def _maybe_warn_partial_last_page(self, ti2: Path) -> None:
        """If the patch set leaves a notably under-filled last page (or spilled
        onto a near-empty extra page), show a friendly heads-up with a button to
        open the patch-set editor so the user can fill or trim the set (Knut #93).
        We don't auto-fill or guess — over/under-fill can equally mean patches
        should be removed.

        Only in Manual mode with a FIXED patch count: in Guided (and Manual with
        "Auto patch count" on) the count is auto-filled to the page, so any small
        gap is just estimate rounding, not the user's choice — and Guided has no
        patch-set editor to point them at (Knut)."""
        # While auto-update-preview is on, this reminder would interrupt every
        # live layout tweak — suppress it (the user can still open the editor).
        if bool(self._settings.get("auto_update_preview", False)):
            return
        manual = (getattr(self, "_manual_btn", None) is not None
                  and self._manual_btn.isChecked())
        auto_count = (getattr(self, "_manual_auto_patches_check", None) is not None
                      and self._manual_auto_patches_check.isChecked())
        if not manual or auto_count:
            return
        # A fixed-patch-set preset (a bundled .ti1: TC9.18, Knut, a vendor family
        # like Red River, or a user preset with an attached .ti1) owns its patch
        # count — the set is locked and targen is greyed, so "add/remove a few
        # patches" is exactly the wrong advice. Suppress the heads-up for those.
        if self._ti1_preset_active():
            return
        blank = self._partial_last_page_blank(ti2)
        if not blank:
            return
        # A bare "space for about N more" is unverifiable from the screen, and
        # an N that looks wrong is indistinguishable from one that is wrong
        # (Knut, #130 2026-08-01). Saying how many the page holds lets anyone
        # check the arithmetic against the patch count already on display.
        capacity = self._last_page_capacity(ti2)
        try:
            from PyQt6.QtWidgets import QMessageBox
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Information)
            box.setWindowTitle(tr("There's a little room left on the last page"))
            box.setText(tr(
                "Your patch set doesn't quite fill the last page — there's space "
                "for about {n} more patches on it (the page holds about {cap} "
                "in total).\n\n"
                "That's perfectly fine to print as it is; the empty area is just "
                "blank paper. If you'd rather have a tidy, completely full page, "
                "you have two easy options in the patch-set editor:\n\n"
                "• Add a few more patches to fill the gap, or\n"
                "• Remove a few so the set ends neatly on the previous page.\n\n"
                "The page layout itself — instrument, paper, margins and patch "
                "size — stays exactly as you've set it here in Create Chart; only "
                "the colours in the set change. Click “Edit patch set…” to open "
                "the editor now, or “OK” to keep the chart as it is."
            ).format(n=blank, cap=capacity))
            edit_btn = box.addButton(tr("Edit patch set…"),
                                     QMessageBox.ButtonRole.ActionRole)
            box.addButton(QMessageBox.StandardButton.Ok)
            box.exec()
            if box.clickedButton() is edit_btn:
                self.edit_patch_set_requested.emit()
        except Exception as exc:  # noqa: BLE001 — never block on this hint
            log.debug("partial-last-page check skipped: %s", exc)

    def _maybe_autotag_randomised(self, ti2: Path) -> None:
        """Upgrade a fixed-order (CHART_ID) chart to RANDOM_START when its layout
        is well mixed, so chartread gets auto strip-ID + bidirectional reading.

        Mirrors the TI2 layout editor's auto-tag-on-save
        (:meth:`TI2RelayoutDialog._maybe_tag_randomised`): a one-directional,
        gate-checked upgrade that can only ever help. printtarg randomises by
        default (already RANDOM_START → skipped here); a chart carries CHART_ID
        only when "Preserve Patch Order" (-r) is in effect — e.g. when a
        pre-shuffled generate-colour-sets / editor-recipe layout is generated.
        A structured chart (a deliberate ramp, a calibration ramp) fails the
        gate and is left untouched. Best-effort: never blocks chart creation.
        """
        try:
            if not ti2.is_file():
                return
            # Cheap guard: only fixed-order charts need upgrading. The default
            # printtarg output is already RANDOM_START, so skip the heavier
            # analysis for it.
            text = ti2.read_text(encoding="utf-8", errors="ignore")
            if "CHART_ID" not in text or "RANDOM_START" in text:
                return
            from workflow.ti2_relayout import (
                analyze_randomisation, tag_ti2_randomised,
            )
            if analyze_randomisation(ti2).safe and tag_ti2_randomised(ti2):
                log.info("Auto-tagged %s as randomised (layout is well mixed).",
                         ti2.name)
        except Exception as exc:  # noqa: BLE001
            log.warning("auto-tag randomised check failed for %s: %s",
                        ti2.name, exc)

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
            from workflow.ti2_relayout import ChartSpec, save_editor_meta
            spec = ChartSpec.from_ti2(ti2)
            run = Run.for_dir(run_dir)
            # Build the editor's LayoutOptions from the params this chart was
            # generated with (stored at generate time). Without params we can
            # still stamp instrument/paper but not the layout knobs.
            params = getattr(self, "_last_params", None)
            if params is not None:
                opts = _layout_options_from_params(params)
                # Pass the active preset's recipe (Set B) so a preset-generated
                # chart carries it into meta.json; None preserves any existing
                # recipe and never invents one for plain targen charts (#70).
                # save_editor_meta reconciles the recipe's layout to these opts,
                # so Set A and Set B never disagree on what was built (#92) —
                # except for engine-built charts, whose real layout is the
                # engine recipe in channels.json, not these printtarg-derived
                # opts: their creation recipe stays as created (#100).
                from workflow.layout_engine.presets import LayoutRecipe
                is_engine = LayoutRecipe.from_channels_json(
                    ti2.with_suffix(".channels.json")) is not None
                save_editor_meta(ti2, spec, opts, run.stem,
                                 recipe=self._pending_editor_recipe,
                                 sync_layout=not is_engine)
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
        # Persist the full ChromIQ layout-engine recipe so every engine option
        # (paper, margins, indicators, strip gap, label offset, …) survives a
        # restart — _init_manual_layout_panel restores it. Without this, only the
        # printtarg widgets above were saved and the engine panel reset (#93).
        if getattr(self, "_manual_layout_panel", None) is not None:
            try:
                s.set("manual_engine_recipe",
                      self._current_layout_recipe().to_dict())
            except Exception as exc:  # noqa: BLE001 — don't fail the whole save
                log.warning("save engine layout defaults failed: %s", exc)
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

        # ChromIQ layout engine on: the layout panel is the source of truth for
        # the chart layout. Take instrument/paper + the full recipe + calibration
        # from it (the printtarg layout widgets are hidden), so every panel option
        # takes effect.
        if (getattr(self, "_manual_layout_panel", None) is not None
                and bool(self._settings.get("use_chromiq_layout_engine", False))):
            recipe = self._current_layout_recipe()
            p.instrument = recipe.instrument
            p.paper = recipe.paper
            p.tiff_dpi = recipe.dpi
            p.pages = self._manual_layout_panel.get_pages()
            p.layout_recipe = recipe
            cal_path, apply_cal = self._manual_layout_panel.cal_settings()
            p.engine_cal_path = cal_path
            p.engine_apply_cal = apply_cal

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
            # All four targen-basic Auto options default ON (Knut): the patch
            # count and neutral counts auto-fill unless the user opts out.
            auto_on = bool(s.get("manual_auto_patches", True))
            self._manual_auto_patches_check.setChecked(auto_on)
            self._on_auto_patches_toggled(auto_on)
        self._load_auto_neutral_states(
            grey  = bool(s.get("manual_auto_grey",  True)),
            white = bool(s.get("manual_auto_white", True)),
            black = bool(s.get("manual_auto_black", True)),
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
