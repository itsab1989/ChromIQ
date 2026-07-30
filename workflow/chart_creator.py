"""Orchestrates targen + printtarg to create a test chart."""
from __future__ import annotations

import math
import re
import shlex
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from core.logger import get_logger
from data.patch_db import EXTERNAL_INSTRUMENTS, SUPPORTED_PATCH_SCALES, query_patches

if TYPE_CHECKING:
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager, Run
    from core.settings import AppSettings


log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Structured error / warning patterns for targen and printtarg.
# Line refs target Argyll 3.5.0 target/targen.c and target/printtarg.c.
# Most error()s in these files are internal asserts (malloc / RSPL / sobol
# failures) — we surface only the ones with a user-actionable fix.
# ---------------------------------------------------------------------------

_TARGEN_ERROR_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # L824 / L863 — preconditioning profile mismatched
    (re.compile(r"ICC profile doesn't match device!"),
     "icc_profile_mismatch",
     "The preconditioning ICC profile doesn't match the chart's colour space. "
     "Pick a profile that was built for the same printer / colour space (RGB vs "
     "CMYK), or clear the preconditioning profile setting."),
    (re.compile(r"MPP profile doesn't match device!"),
     "mpp_profile_mismatch",
     "The MPP profile doesn't match the chart's colour space. Choose an MPP "
     "file generated for the same device."),
    # L659 — cal curve broken
    (re.compile(r"calibration curve is non-invertable"),
     "cal_noninvertable",
     "The calibration file's transfer curve isn't invertible. The .cal file "
     "may be corrupt — regenerate it with printcal."),
    # L1985 — wrong -p flag for the colour space
    (re.compile(r"Composite grey wedges aren't appropriate for (\S+) device"),
     "grey_wedges_wrong_device",
     "Composite grey wedges aren't appropriate for a '{0}' device. Disable "
     "the composite-grey-wedge option for this colour space."),
    # L1497 — Argyll doesn't know the colorant set
    (re.compile(r"Don't know how to deal with inverted colorant combination 0x([0-9a-fA-F]+)"),
     "unknown_inverted_colorants",
     "Argyll doesn't recognise the inverted colorant combination 0x{0}. "
     "Check the printer / colour-space combo in the Chart tab."),
    # L2454
    (re.compile(r"N-channel must be 16 or less than channels"),
     "too_many_channels",
     "Multi-channel charts can request at most 16 channels and must be less "
     "than the device's channel count. Reduce the N-channel setting."),
    # L3209
    (re.compile(r"Write error\s*:\s*(.+)$"),
     "write_error",
     "Could not write the chart file.\n\nArgyll reported: {0}\n\nCheck that the "
     "output folder is writable and has enough free space."),
]

_TARGEN_WARNING_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # L826
    (re.compile(r"Profile '([^']+)' no\. channels match, but colorant types have not been checked"),
     "profile_unchecked_colorants",
     "Profile '{0}' has the right number of channels for this chart, but its "
     "colorant types weren't verified — make sure it really targets this printer."),
]

_PRINTTARG_ERROR_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # L2287 — paper too short for the TID strip
    (re.compile(r"Paper size not long enough for target identification row \(need ([\d.]+) mm, got ([\d.]+) mm\)"),
     "paper_too_short_tid",
     "The paper isn't long enough for the chart's identification row "
     "(need {0} mm, paper is only {1} mm). Use larger paper, or pick a chart "
     "instrument that doesn't require a TID strip."),
    # L2293
    (re.compile(r"Paper size not long enough for a single patch per row"),
     "paper_too_short_row",
     "The paper isn't long enough for even one patch row. Reduce the patch "
     "scale, switch to a smaller instrument, or use larger paper."),
    # L2331
    (re.compile(r"Not enough width for even one row"),
     "paper_too_narrow",
     "The paper isn't wide enough for even one patch row. Rotate to landscape "
     "or use wider paper."),
    # L2247
    (re.compile(r"Unsupported instrument type"),
     "unsupported_instrument",
     "printtarg doesn't support the selected instrument for chart layout. "
     "Pick a different chart instrument in the Chart tab."),
    # L347 / L364 / L379 (PostScript path) and L752/L768/L786 (TIFF path) and
    # L971/L987/L1005 (Render2D path)
    (re.compile(r"Device (white|black|CMY) encoding not appropriate"),
     "device_encoding",
     "The selected instrument's '{0}' colour encoding isn't appropriate for "
     "the chart's colour space — change the instrument or colour space."),
]


# Instruments the ChromIQ layout engine can lay out itself (issue #93).
ENGINE_INSTRUMENTS = {"i1", "p3", "CM", "SS"}

# printtarg's ColorMunki triple-density trick (-ii1) uses -a1.3 by default; the
# engine's native extra-high-density (pscale 1.0) reproduces exactly that size,
# so a printtarg -a maps to engine pscale = -a / this. (Converted in
# _engine_build_kwargs; the engine geometry is in instruments.py density>=3.)
CM_TRIPLE_PRINTTARG_SCALE = 1.3


def _engine_padding_log_line(total: int, padding: int) -> str:
    """The log line explaining strip fill-up padding, or "" when there is none.

    Shown right after the engine's "<total> patches" line so a total that grew
    past the designed count (e.g. 896 designed → 910 printed) is explained at
    the same place the number appears (#124 follow-up, Knut)."""
    if not padding or padding <= 0:
        return ""
    designed = total - padding
    return (f"[ChromIQ layout engine] patch count: {designed} designed "
            f"+ {padding} paper-white fill-up patch(es) completing the last "
            f"strip = {total} total. Instruments read whole strips; the "
            f"fill-up patches are measured like any others.")


def _chromiq_clip_active(p: "ChartParams") -> bool:
    """True when ChromIQ-style clipping border applies to this chart.

    Gating: setting enabled AND the user did NOT suppress the left clip border
    AND instrument is i1Pro family AND paper is large enough for the rotated
    text to be legible.

    The suppress toggle stays meaningful even with the setting on: leaving it
    unchecked yields the ChromIQ branded strip (we force -L internally and
    shift the patches to make room); checking it suppresses the border
    entirely (-L, no shift, no strip) and routes commands/notes to the right
    margin as usual.
    """
    from workflow.tiff_metadata import ALLOWED_LEFT_CLIP_PAPERS
    return (
        p.chromiq_clip_style
        and not p.disable_left_border
        and p.instrument in {"i1", "p3"}
        and p.paper in ALLOWED_LEFT_CLIP_PAPERS
    )


def _effective_suppress_lb(p: "ChartParams") -> bool:
    """The -L state used for patch-capacity lookups.

    ChromIQ-style forces -L, so the page is laid out at full (-L-enabled)
    capacity even when the user left "Suppress left clip border" unchecked.
    Triple-density also forces -L: the i1Pro layout has no useful clip border
    on a ColorMunki workflow, and the patch tables for that mode assume -L.
    """
    triple = p.triple_density and p.instrument == "CM"
    return p.disable_left_border or _chromiq_clip_active(p) or triple


def _extra_printtarg_affects_layout(extra: str) -> bool:
    """True when extra_printtarg_args contains a flag that changes capacity.

    -A <scale != 1.0>  → spacer-bar width changes, capacity shifts.
    -n                 → no spacers at all, more room per patch.
    Other printtarg extras the manual mode collects (-Q, -N, -K, -I, -R, -D,
    -U, -C, -c) leave the layout untouched and are safe for the fast
    patch_db lookup. When this returns True the caller routes to the binary
    search so the override actually participates in the patch count.
    """
    if not extra:
        return False
    try:
        toks = shlex.split(extra)
    except ValueError:
        return False
    i = 0
    while i < len(toks):
        tok = toks[i]
        if tok == "-n":
            return True
        scale_val: str | None = None
        consumed = 1
        if tok == "-A" and i + 1 < len(toks):
            scale_val = toks[i + 1]
            consumed = 2
        elif tok.startswith("-A") and len(tok) > 2:
            scale_val = tok[2:]
        if scale_val is not None:
            try:
                if abs(float(scale_val) - 1.0) > 0.01:
                    return True
            except ValueError:
                pass
        i += consumed
    return False


# Stamped-text shortening: long target names and -c/-K filenames blow out the
# right-margin command lines on the TIFF, so we truncate them for display only.
# The argv handed to ArgyllRunner is unchanged — only the strings rendered by
# the stamper see the shortened form.
_STAMP_NAME_CAP = 16
_STAMP_ELLIPSIS = "(…)"
_STAMP_PATH_FLAGS = frozenset({"-c", "-K", "-k"})


def _shorten_for_stamp(token: str) -> str:
    """Path → basename → truncate at _STAMP_NAME_CAP, append `(…)` if cut."""
    base = Path(token).name if ("/" in token or "\\" in token) else token
    if len(base) <= _STAMP_NAME_CAP:
        return base
    return base[:_STAMP_NAME_CAP] + _STAMP_ELLIPSIS


def _shorten_argv_for_stamp(args: list[str]) -> list[str]:
    """Return a copy of argv with long names shortened for the printed stamp.

    Affects the trailing positional (target name) and the value following any
    path-bearing short flag (-c preconditioning profile, -K/-k calibration).
    """
    out = list(args)
    i = 0
    while i < len(out) - 1:
        if out[i] in _STAMP_PATH_FLAGS:
            out[i + 1] = _shorten_for_stamp(out[i + 1])
            i += 2
            continue
        i += 1
    if out and not out[-1].startswith("-"):
        out[-1] = _shorten_for_stamp(out[-1])
    return out


# Auto neutrals: -g, -e, -B targets. Shared between Guided Mode (always
# auto-computed from instrument+paper+pages) and Manual Mode (opt-in per
# row via Auto checkboxes).
#
# Anchor: 560 total patches → -g32 -e4 -B4. 560 matches i1Pro+A4 landscape
# at the m10_a0.95 -L reference layout and gives a clean "A3 landscape =
# 2× A4 landscape" ratio in Guided Mode. This is the *default* anchor; the
# user can override it via the "Grey ramp reference" setting, which is passed
# in as ref_budget to manual_neutrals() / guided_neutrals() (lower = denser
# neutrals, higher = sparser). The floors/caps below are unaffected.
#
# Scaling: "effective sheets" = total_patches / ref_budget (default 560).
#   -g  scales linearly: 32 × eff_sheets, capped at 128.
#   -e/-B compound ×1.5 per doubling of eff_sheets, capped at 8.
#   floors: -g ≥ 8, -e/-B ≥ 2.
#
# For Guided Mode the total_patches is the patch_db nominal × pages, with
# layout knobs (margin, patch_scale) pinned to reference values and
# suppress_lb / density flags following the chart's actual state. For
# Manual Mode the user supplies total_patches directly (or it's the auto-
# estimated patch count from -f Auto).
REF_BUDGET                = 560   # query_patches("i1","A4R", suppress_lb=True,
                                  #                margin_mm=10, patch_scale=0.95)
GUIDED_REF_MARGIN_MM      = 10
GUIDED_REF_PATCH_SCALE    = 0.95
GUIDED_GREY_REF_STEPS     = 32    # "1 effective sheet → 32 grey steps"
GUIDED_GREY_MAX           = 128
GUIDED_GREY_MIN           = 8
GUIDED_NEUTRAL_BASE       = 4     # -e/-B reference at eff_sheets = 1
GUIDED_NEUTRAL_DOUBLE_X   = 1.5   # multiplier per doubling of eff_sheets
GUIDED_NEUTRAL_MAX        = 8
GUIDED_NEUTRAL_MIN        = 2
GUIDED_NEUTRAL_BUDGET_FRC = 0.50  # Guided-only: neutrals ≤ 50 % of nominal
GUIDED_LOW_CAPACITY_PS    = 200   # Guided-only: drop -e/-B base by 1 here

# Back-compat alias (older import sites).
GUIDED_REF_BUDGET         = REF_BUDGET

# Sanity check: keep REF_BUDGET in sync with patch_db.
assert query_patches("i1", "A4R", suppress_lb=True,
                     margin_mm=GUIDED_REF_MARGIN_MM,
                     patch_scale=GUIDED_REF_PATCH_SCALE) == REF_BUDGET, (
    "REF_BUDGET out of sync with patch_db — update the constant or the "
    "patch_db entry."
)


def _neutrals_from_eff_sheets(eff_sheets: float,
                              base_white: int,
                              base_black: int) -> tuple[int, int, int]:
    """Core math shared by Guided and Manual neutrals.

    grey scales linearly (32 × eff_sheets); -e/-B compound by ×1.5 per
    doubling. Floors and caps applied at the boundaries.
    """
    grey  = max(GUIDED_GREY_MIN,
                min(GUIDED_GREY_MAX,
                    round(GUIDED_GREY_REF_STEPS * eff_sheets)))
    if eff_sheets > 0:
        # 1.5^log2(eff) — equivalent to eff^log2(1.5). At eff=1 → 1×,
        # at eff=2 → 1.5×, at eff=0.5 → 1/1.5×.
        factor = GUIDED_NEUTRAL_DOUBLE_X ** math.log2(eff_sheets)
    else:
        factor = 0.0
    white = max(GUIDED_NEUTRAL_MIN,
                min(GUIDED_NEUTRAL_MAX, round(base_white * factor)))
    black = max(GUIDED_NEUTRAL_MIN,
                min(GUIDED_NEUTRAL_MAX, round(base_black * factor)))
    return grey, white, black


def manual_neutrals(total_patches: int,
                    base_white: int = GUIDED_NEUTRAL_BASE,
                    base_black: int = GUIDED_NEUTRAL_BASE,
                    ref_budget: int = REF_BUDGET) -> tuple[int, int, int]:
    """Return (grey_steps, white_patches, black_patches) for Manual Mode.

    Drives the per-row Auto checkboxes on -g / -e / -B. Total patches is
    whatever the user (or the -f Auto estimator) currently has set. At the
    anchor (ref_budget, default 560) the result is the original suggester's
    -g32 -e4 -B4. ref_budget is the user-configurable "Grey ramp reference".
    """
    if total_patches <= 0:
        # Sentinel for the live preview when -f itself is still being
        # auto-estimated and we don't have a real total to work from.
        return GUIDED_GREY_MIN, base_white, base_black
    eff = total_patches / max(1, ref_budget)
    return _neutrals_from_eff_sheets(eff, base_white, base_black)


def guided_neutrals(instrument: str,
                    paper: str,
                    pages: int,
                    base_white: int,
                    base_black: int,
                    suppress_lb: bool,
                    double_density: bool = False,
                    triple_density: bool = False,
                    no_strip_limit: bool = False,
                    ref_budget: int = REF_BUDGET) -> tuple[int, int, int]:
    """Return (grey_steps, white_patches, black_patches) for Guided Mode.

    All three values are driven by a single number — "effective sheets" —
    so they scale together with the instrument+paper+pages combo. The
    nominal lookup uses the chart's actual suppress_lb (clip strip eats
    real space on i1Pro/p3) plus density flags (ColorMunki rig modes
    multiply the budget significantly), but otherwise pins margin and
    patch_scale to the reference values so layout knobs don't perturb
    neutrals.

    A final proportional-scale guardrail kicks in only for degenerate
    tiny-budget combos where the trio would still crowd out colour patches.
    """
    nominal = query_patches(instrument, paper,
                            double_density=double_density,
                            suppress_lb=suppress_lb,
                            margin_mm=GUIDED_REF_MARGIN_MM,
                            patch_scale=GUIDED_REF_PATCH_SCALE,
                            triple_density=triple_density,
                            no_strip_limit=no_strip_limit)
    if nominal is None:
        # ColorMunki and SpectroScan have fixed layouts in patch_db —
        # margin/patch_scale aren't honored, so the reference kwargs miss.
        # Retry with patch_db's default layout (those instruments ignore
        # the layout knobs internally anyway).
        nominal = query_patches(instrument, paper,
                                double_density=double_density,
                                suppress_lb=suppress_lb,
                                triple_density=triple_density,
                                no_strip_limit=no_strip_limit)
    if nominal is None and triple_density and instrument == "CM":
        # Triple table was measured at -a 1.3 -m 5 -P; the reference and
        # default kwargs above don't match those values, so query_patches
        # now returns None on a non-preset call. Guided mode always uses
        # the preset, so retry with it explicitly.
        nominal = query_patches(instrument, paper,
                                double_density=False,
                                suppress_lb=suppress_lb,
                                margin_mm=5, patch_scale=1.3,
                                triple_density=True, no_strip_limit=True)
    if nominal is None:
        # Genuinely unknown combo — fall back to a page-based ladder so
        # the chart still gets sensible neutrals.
        eff_sheets = float(pages)
    else:
        eff_sheets = (nominal * pages) / max(1, ref_budget)

    if nominal is not None and nominal < GUIDED_LOW_CAPACITY_PS:
        eff_white = max(base_white - 1, GUIDED_NEUTRAL_MIN)
        eff_black = max(base_black - 1, GUIDED_NEUTRAL_MIN)
    else:
        eff_white = base_white
        eff_black = base_black

    grey_ideal, white_ideal, black_ideal = _neutrals_from_eff_sheets(
        eff_sheets, eff_white, eff_black
    )

    if nominal is None:
        return grey_ideal, white_ideal, black_ideal

    total_budget = nominal * pages
    neutrals     = grey_ideal + white_ideal + black_ideal
    cap          = int(total_budget * GUIDED_NEUTRAL_BUDGET_FRC)
    if neutrals <= cap or neutrals == 0:
        return grey_ideal, white_ideal, black_ideal

    scale = cap / neutrals
    return (max(GUIDED_GREY_MIN,    int(grey_ideal  * scale)),
            max(GUIDED_NEUTRAL_MIN, int(white_ideal * scale)),
            max(GUIDED_NEUTRAL_MIN, int(black_ideal * scale)))


@dataclass
class ChartParams:
    # Guided-mode selections
    instrument: str = "i1"
    paper: str = "A4"
    pages: int = 1
    double_density: bool = False
    disable_left_border: bool = True

    # targen params
    device_type: str = "2"
    patches: int = 0            # 0 = auto-compute from DB / binary search (guided); pass -f0 to targen (manual)
    is_manual: bool = False     # True = manual mode; skip patch DB lookup, pass patches directly to targen
    white_patches: int = 4
    black_patches: int = 4
    good_mode: bool = True
    grey_steps: int = 0
    single_channel_steps: int = 0
    # When True, emit the neutral ramp as targen -n (profile-derived neutral
    # axis) instead of -g (device-space grey). Set by Guided Mode when a
    # refinement / pre-conditioning profile (-c) is supplied; -n requires it.
    neutral_axis_from_profile: bool = False
    extra_targen_args: str = ""
    # When True, build the full-spread patches with targen's perceptual
    # quasi-random sampler (-Q) instead of the default Optimised Farthest
    # Point Sampling (OFPS). OFPS gives the best spread but degenerates into
    # an effective hang for certain preconditioning profiles at high patch
    # counts; -Q keeps the perceptual distribution but is always fast. Set by
    # the "rebuild faster" escape hatch when the slow-chart watchdog fires.
    # See docs / the targen OFPS-cliff investigation.
    fast_sampler: bool = False

    # printtarg params
    tiff_dpi: int = 300
    tiff_16bit: bool = False
    patch_scale: float = 1.0
    # printtarg -A (spacer-only scale). Carried for metadata (the editor's
    # LayoutOptions) only — the printtarg command itself still gets -A via the
    # manual ParameterWidget build_args path, so this field must NOT be re-emitted
    # there or -A would appear twice.
    spacer_scale: float = 1.0
    margin_mm: int = 6
    no_randomise: bool = False
    bw_spacers: bool = False
    # printtarg -n (no spacers at all). Like spacer_scale, carried for metadata
    # (the editor's LayoutOptions spacer_mode="none") only — manual mode emits
    # -n via the widget build_args path, so this field must NOT be re-emitted.
    no_spacers: bool = False
    no_strip_limit: bool = False
    extra_printtarg_args: str = ""

    # ChromIQ-only synthetic option (ColorMunki + rig only). When True we
    # generate the chart with -ii1 (i1Pro strip geometry) plus -a 1.3 / -m 5 /
    # -P so a ColorMunki + rig can read the tighter layout, then rewrite the
    # produced .ti2 so TARGET_INSTRUMENT references the ColorMunki again.
    triple_density: bool = False

    target_name: str = "chart"
    chart_notes: str = ""             # free-text user notes stamped onto the TIFF
    stamp_commands: bool = True       # also stamp the targen + printtarg commands used
    # When the chart was laid out from an existing patch set (a preset, a loaded
    # .ti1, a prebuilt chart, or one applied from the editor), targen was NOT run
    # — so the command stamp shows the chart-LAYOUT name instead of a misleading
    # targen line, keeping only the printtarg command (#70, Knut's model).
    chart_layout_name: str | None = None
    # When True (and gating holds: instrument in {i1, p3}, -L off, paper in
    # ALLOWED_LEFT_CLIP_PAPERS), fill the left clip strip with two rotated
    # info columns: chart context + archival form fields + jig-orientation note.
    left_clip_info: bool = False
    # ChromIQ-style clipping border (Preferences → i1Pro). When True and gating
    # holds (instrument in {i1, p3} + paper in ALLOWED_LEFT_CLIP_PAPERS), the
    # workflow forces -L, shifts patches right by ~28 mm to create a fresh
    # left strip, and always stamps the ChromIQ left-clip content there. The
    # right-margin command/notes stamp is skipped because its target area
    # gets pushed off the page by the shift.
    chromiq_clip_style: bool = False
    # When True, this run targets the calibration chart (writes to ``cal/``
    # with stem ``calibration``). When False, writes to the project's current
    # run folder with stem ``chart``. See ``FileManager.cwd_for_chart``.
    cal_target: bool = False

    # ChromIQ layout engine (issue #93): the full per-chart layout recipe from
    # the Manual/editor LayoutOptionsPanel. When set (engine on), the engine
    # builds from this (instrument/paper taken from the fields above) instead of
    # the ChartParams-derived basics. engine_cal_* attach a printer .cal (-K/-I).
    layout_recipe: "object | None" = None
    engine_cal_path: str | None = None
    engine_apply_cal: bool = False
    # When True, the .icc/.ti3 from a prior session in the same working folder
    # are renamed to pre_*.icc/pre_*.ti3 instead of being overwritten on the
    # following measure / colprof runs. Set by the guided tab when the user
    # arrived via "Use as pre-conditioning profile" in a result dialog.


class ChartCreator:
    def __init__(
        self,
        runner: "ArgyllRunner",
        file_mgr: "FileManager",
        settings: "AppSettings",
    ) -> None:
        self._runner = runner
        self._file_mgr = file_mgr
        self._settings = settings

        self._pending_on_finish: Callable[[list[Path]], None] | None = None
        self._pending_params: ChartParams | None = None
        # State for the slow-chart watchdog escape hatch (see generate /
        # restart_with_fast_sampler / cancel). The on_line callback, work dir
        # and patch count are stashed so a running targen can be killed and
        # re-launched with the fast sampler without re-deriving anything.
        self._pending_on_line: Callable[[str], None] | None = None
        self._pending_work_dir: Path | None = None
        self._pending_patch_count: int = 0
        self._restart_fast = False   # next targen-finish should relaunch with -Q
        self._cancelling = False     # next targen-finish is a deliberate cancel
        # Captured structured errors/warnings from the most-recent run.
        # Tagged with the tool name so the dispatcher knows which dialog to show.
        self._matched_errors: list[tuple[str, str, str]] = []   # (tool, key, friendly)
        #: Every line a tool called an error, in order, whether or not a friendly
        #: pattern matched it — so a build can never fail without a word.
        self._raw_errors: list[tuple[str, str]] = []
        self._matched_warnings: list[tuple[str, str, str]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        params: ChartParams,
        on_line: Callable[[str], None],
        on_finish: Callable[[list[Path]], None],
    ) -> None:
        """Run targen then printtarg; call on_finish(tiff_paths) on completion.

        Folder routing:
          * ``cal_target=True``  → writes to ``project.calibration.dir/`` with
            stem ``calibration``.
          * ``cal_target=False`` → writes to ``project.current_run().dir/`` with
            stem ``chart``.

        Cleanup is folder-scoped: a calibration regen resets ``cal/``; a normal
        chart regen resets only the current run's chart artefacts (preserving
        any ``preconditioning.*`` already seeded). Other runs and the cal
        folder are untouched by definition — they live in different folders.
        """
        self._pending_on_finish = on_finish
        self._pending_params = params
        self._pending_on_line = on_line
        self._restart_fast = False
        self._cancelling = False

        proj = self._file_mgr.project()
        if params.cal_target:
            proj.calibration.reset()
            work_dir = proj.calibration.ensure_dir()
        else:
            run = proj.current_run()
            self._announce_result_archive(run, on_line, False)
            run.reset_chart_artefacts()
            work_dir = run.ensure_dir()
            # External -c preconditioning: copy ICC (and sibling .ti3 if
            # refinement is on) into the current run so the chart and the
            # snapshot live together.
            params.extra_targen_args = self._import_external_preconditioning(
                params.extra_targen_args, run,
            )

        if params.is_manual:
            patch_count = params.patches  # pass value as-is; 0 lets targen decide
        else:
            patch_count = params.patches if params.patches > 0 else self._lookup_patches(params)
        log.info("Chart generation: %d patches, instrument=%s paper=%s disable_lb=%s",
                 patch_count, params.instrument, params.paper, params.disable_left_border)

        self._pending_work_dir = work_dir
        self._pending_patch_count = patch_count
        self._matched_errors = []
        self._raw_errors = []
        self._matched_warnings = []
        self._start_targen(params, patch_count, on_line, work_dir)

    def _start_targen(
        self,
        params: ChartParams,
        patch_count: int,
        on_line: Callable[[str], None],
        work_dir: Path,
    ) -> None:
        """Launch targen for the given params. Shared by the first run and the
        fast-sampler relaunch so both stream progress and share the finish
        handler."""
        # -v makes targen stream its "Added N/M" progress so the UI can show
        # it's working (and the slow-chart watchdog has something to watch).
        # It's prepended only to the live argv; the stamped command rebuilt in
        # _stamp_tiff_metadata uses _build_targen_args directly, so the TIFF
        # metadata stays clean.
        targen_args = ["-v"] + self._build_targen_args(params, patch_count)
        log.info("targen args: %s", targen_args)

        def _targen_scan(line: str) -> None:
            self._scan_line("targen", line)
            on_line(line)

        self._runner.run(
            "targen",
            targen_args,
            work_dir,
            on_line=_targen_scan,
            on_finish=lambda code: self._targen_done(code, params, on_line, work_dir),
        )

    def restart_with_fast_sampler(self) -> bool:
        """Kill the running targen and relaunch the same chart with the fast
        (-Q) sampler. Returns False if there's nothing to restart.

        The kill triggers the normal targen-finished path; ``_restart_fast``
        diverts it into the relaunch instead of reporting failure."""
        if (self._pending_params is None or self._pending_work_dir is None
                or not self._runner.is_running):
            return False
        log.info("Slow-chart: restarting targen with fast sampler (-Q)")
        self._restart_fast = True
        self._runner.abort()
        return True

    def cancel(self) -> None:
        """Kill a running targen/printtarg as a deliberate user cancel.

        Sets ``_cancelling`` so the finish handler reports an empty result
        (re-enabling the UI) without logging a scary targen error line."""
        if not self._runner.is_running:
            return
        log.info("Slow-chart: user cancelled chart generation")
        self._cancelling = True
        self._runner.abort()

    def estimate_patches(
        self,
        params: ChartParams,
        progress_cb: Callable[[str], None] | None = None,
    ) -> int:
        """Return max patches for the given params (fast lookup or binary search)."""
        # ChromIQ layout engine: when active it owns the packing, so the auto
        # count is its own capacity × pages (not the printtarg DB / binary search).
        eng = self._engine_total_patches(params)
        if eng is not None:
            if progress_cb:
                progress_cb(f"ChromIQ layout engine: {eng} patches "
                            f"({params.pages} page(s))")
            return eng

        triple = params.triple_density and params.instrument == "CM"
        # The patch_db only covers the headline layout knobs (-a, -m, -L, -P,
        # -h). Anything else that influences capacity (-A spacer scale, -n
        # no-spacers, custom paper dimensions) lives in extra_printtarg_args
        # and would be silently ignored by the fast lookup, so detect it
        # here and route to the binary search instead.
        layout_extras = _extra_printtarg_affects_layout(params.extra_printtarg_args)
        if (not layout_extras
                and (triple or any(abs(params.patch_scale - s) <= 0.01
                                   for s in SUPPORTED_PATCH_SCALES))):
            per_sheet = query_patches(params.instrument, params.paper, params.double_density,
                                      suppress_lb=_effective_suppress_lb(params),
                                      margin_mm=params.margin_mm,
                                      patch_scale=params.patch_scale,
                                      triple_density=triple,
                                      no_strip_limit=params.no_strip_limit)
            if per_sheet is not None:
                n = per_sheet * params.pages
                if progress_cb:
                    progress_cb(
                        f"Lookup: {per_sheet} patches/sheet × {params.pages} = {n}"
                    )
                return n

        # Binary search for unsupported patch_scale / margin_mm, or whenever
        # extra_printtarg_args contains a layout-affecting flag.
        if progress_cb:
            progress_cb("Custom layout detected — running binary search…")
        per_sheet = self._binary_search(params, progress_cb)
        return per_sheet * params.pages

    def _announce_result_archive(self, run, on_line, keep_results: bool) -> None:
        """Say — in the log the user is watching — that a run's finished work is
        being set aside before a new chart replaces it (Knut, #130 2026-07-27:
        "Generate Chart silently moved the .ti3 to old/").

        The move itself is deliberate and long-standing: a new chart no longer
        matches the measurement or the profile made from the old one, so they are
        archived rather than deleted. What was missing is that nobody said so.
        """
        if keep_results or on_line is None:
            return
        from core.i18n import tr
        s = run.stem
        results = [run.dir / f"{s}.ti3", run.dir / f"{s}.icc",
                   run.dir / f"{s}.icm", run.dir / "merged.ti3",
                   run.dir / "merged.icc", run.dir / "calibrated.icc"]
        if not any(p.exists() for p in results):
            return
        on_line(tr(
            "This run already holds a measurement or a printer profile. A new "
            "chart no longer matches them, so they are moved into the run's "
            "“old” folder before the new chart is written. Nothing is deleted — "
            "you can open that folder and take them back at any time."))

    def load_ti1_and_generate_preview(
        self,
        ti1_path: Path,
        params: ChartParams,
        on_line: Callable[[str], None],
        on_finish: Callable[[list[Path]], None],
        *,
        keep_results: bool = False,
    ) -> None:
        """Run printtarg only on an existing .ti1 file.

        Always targets the current run's chart slot (preview is never a
        calibration target). Copies the input .ti1 into ``chart.ti1``, wipes
        prior chart artefacts in that run, then runs printtarg.

        ``keep_results`` is for redrawing the pages of the chart that is already
        in the run — **Restore Used Chart** — where the measurement and profile
        belong to exactly this chart and must be left alone (Knut, #130).
        """
        # _printtarg_done writes the <stem>.channels.json sidecar only when
        # _pending_params is set; otherwise the preview can't identify inks
        # in a future session. Mirror the generate() path so this entry point
        # produces the same artifacts.
        self._pending_params = params
        # Capture the input patch set BEFORE wiping the run: when ti1_path lives
        # inside this very run folder (e.g. a re-layout of the run's own chart),
        # reset_chart_artefacts() would delete it and the copy below would have
        # nothing to read — printtarg then exits 0 having written no TIFFs
        # (the "0 TIFFs" generation failure, #68). Reading the bytes first makes
        # the input survive the reset no matter where it lives.
        ti1_bytes = Path(ti1_path).read_bytes()
        run = self._file_mgr.project().current_run()
        self._announce_result_archive(run, on_line, keep_results)
        run.reset_chart_artefacts(keep_results=keep_results)
        work_dir = run.ensure_dir()
        stem = run.stem
        dest = run.chart_ti1
        dest.write_bytes(ti1_bytes)

        # ChromIQ layout engine: when enabled, lay the loaded patches out with the
        # engine instead of printtarg — otherwise a loaded preset / built-in chart
        # silently ignored the engine (columns / patch width / notes box did
        # nothing) because this path always ran printtarg (#93). The .ti1 is
        # already in place, so the engine builds from it just like the targen path.
        if self._should_use_engine(params):
            self._pending_on_finish = on_finish
            self._pending_on_line = on_line
            self._matched_errors = []
            self._raw_errors = []
            self._matched_warnings = []
            self._run_engine(params, work_dir, on_line)
            return

        pt_args = self._build_printtarg_args(params)
        log.debug("printtarg args (from ti1): %s", pt_args)
        self._matched_errors = []
        self._raw_errors = []
        self._matched_warnings = []

        def _printtarg_scan(line: str) -> None:
            self._scan_line("printtarg", line)
            on_line(line)

        self._runner.run(
            "printtarg",
            pt_args,
            work_dir,
            on_line=_printtarg_scan,
            on_finish=lambda code: self._printtarg_done(code, work_dir, on_finish, stem),
        )

    def _import_external_preconditioning(self, extra_args: str, run: "Run") -> str:
        """Copy an external ``-c <icc>`` into the run as ``preconditioning.icc``.

        Triggered when the user picks a profile from outside the project (e.g.
        a profile shipped with a colour-managed printer) as the targen
        ``-c`` argument. Local picks (e.g. ``runs/runN-1/profile.icc``) are
        handled upstream by ``Project.new_run(preconditioning_from=...)``
        and won't reach this code.

        When ``chromiq_refinement`` is enabled and the source profile has a
        sibling ``.ti3``, that measurement file is copied alongside as
        ``preconditioning.ti3`` so ``workflow/ti3_merge.py`` can fold its
        patches in at colprof time.

        Rewrites the ``-c`` arg to point at the local copy so the targen
        command line is self-contained within the run folder.
        """
        if not extra_args:
            return extra_args
        parts = shlex.split(extra_args)
        try:
            idx = parts.index("-c")
        except ValueError:
            return extra_args
        if idx + 1 >= len(parts):
            return extra_args

        src = Path(parts[idx + 1])
        if not src.is_file():
            return extra_args

        # If the picked profile is ALREADY the current run's preconditioning
        # ICC (e.g. seeded by Project.new_run), there's nothing to do.
        try:
            if src.resolve() == run.preconditioning_icc.resolve():
                return extra_args
        except OSError:
            pass

        import shutil
        try:
            shutil.copy2(src, run.preconditioning_icc)
            log.info(
                "Imported external preconditioning profile to %s",
                run.preconditioning_icc.name,
            )
        except OSError as exc:
            log.warning(
                "Could not import preconditioning %s -> %s: %s",
                src, run.preconditioning_icc, exc,
            )
            return extra_args

        # Sibling .ti3 → preconditioning.ti3 (only when refinement is on,
        # otherwise the merge step won't run anyway).
        if bool(self._settings.get("chromiq_refinement", False)):
            ti3_src = src.with_suffix(".ti3")
            if ti3_src.is_file():
                try:
                    shutil.copy2(ti3_src, run.preconditioning_ti3)
                    log.info(
                        "Imported external preconditioning measurements to %s",
                        run.preconditioning_ti3.name,
                    )
                except OSError as exc:
                    log.warning(
                        "Could not import preconditioning ti3 %s -> %s: %s",
                        ti3_src, run.preconditioning_ti3, exc,
                    )

        parts[idx + 1] = str(run.preconditioning_icc)
        return shlex.join(parts)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _scan_line(self, tool: str, line: str) -> None:
        # Remember ANY line the tool itself calls an error, matched or not.
        # Knut, #130 2026-07-30: printtarg refused his chart with "Input file
        # doesn't contain two or three tables" — a message no pattern here knows,
        # so `primary_failure()` returned None and the window that reports a
        # failed build never appeared. He was left with an empty preview and two
        # lines in the log. An unrecognised error is still an error, and the user
        # is still owed the tool's own words.
        low = line.lower()
        if ("error" in low or "failed" in low) and line.strip():
            self._raw_errors.append((tool, line.strip()))
        if tool == "targen":
            for pattern, key, fmt in _TARGEN_ERROR_PATTERNS:
                m = pattern.search(line)
                if m:
                    self._matched_errors.append((tool, key, fmt.format(*m.groups())))
            for pattern, key, fmt in _TARGEN_WARNING_PATTERNS:
                m = pattern.search(line)
                if m:
                    self._matched_warnings.append((tool, key, fmt.format(*m.groups())))
        elif tool == "printtarg":
            for pattern, key, fmt in _PRINTTARG_ERROR_PATTERNS:
                m = pattern.search(line)
                if m:
                    self._matched_errors.append((tool, key, fmt.format(*m.groups())))

    def primary_failure(self) -> tuple[str, str, str] | None:
        """Return (tool, key, friendly_message) of the first structured error,
        or None if no known pattern matched."""
        return self._matched_errors[0] if self._matched_errors else None

    def unmatched_failure(self) -> tuple[str, str] | None:
        """``(tool, the tool's own line)`` for a failure no pattern recognised.

        The fallback that makes a silent failure impossible: when nothing here
        knows the message, the user still gets the tool's own words rather than
        an empty preview and a log entry (#130, Knut 2026-07-30)."""
        if self._matched_errors or not self._raw_errors:
            return None
        return self._raw_errors[0]

    def captured_warnings(self) -> list[tuple[str, str, str]]:
        return list(self._matched_warnings)

    def _targen_done(
        self,
        exit_code: int,
        params: ChartParams,
        on_line: Callable[[str], None],
        work_dir: Path,
    ) -> None:
        # Watchdog escape hatch: the previous targen was killed so we could
        # relaunch the identical chart with the fast (-Q) sampler.
        if self._restart_fast:
            self._restart_fast = False
            params.fast_sampler = True
            self._start_targen(params, self._pending_patch_count, on_line, work_dir)
            return
        # Deliberate user cancel: report an empty result without the error line.
        if self._cancelling:
            self._cancelling = False
            log.info("targen cancelled by user (exit code %d)", exit_code)
            if self._pending_on_finish:
                self._pending_on_finish([])
            return
        if exit_code != 0:
            log.error("targen failed with code %d", exit_code)
            on_line(f"[ERROR] targen exited with code {exit_code}")
            if self._pending_on_finish:
                self._pending_on_finish([])
            return

        # ChromIQ layout engine (issue #93): when enabled (and the chart isn't
        # using a printtarg-only clip-content feature), build the chart in-process
        # instead of running printtarg. targen has already produced the .ti1.
        if self._should_use_engine(params):
            self._run_engine(params, work_dir, on_line)
            return

        pt_args = self._build_printtarg_args(params)
        log.info("printtarg args: %s", pt_args)

        def _printtarg_scan(line: str) -> None:
            self._scan_line("printtarg", line)
            on_line(line)

        self._runner.run(
            "printtarg",
            pt_args,
            work_dir,
            on_line=_printtarg_scan,
            on_finish=lambda code: self._printtarg_done(
                code, work_dir, self._pending_on_finish,
                self._file_mgr.chart_stem(cal_target=params.cal_target),
            ),
        )

    # ------------------------------------------------------------------
    # ChromIQ layout engine path (issue #93)
    # ------------------------------------------------------------------
    def _should_use_engine(self, params: "ChartParams") -> bool:
        if params.instrument not in ENGINE_INSTRUMENTS:
            return False
        # Clip-border *content* (ChromIQ clip style / left-clip info) is a later
        # engine phase — fall back to the printtarg path for those charts.
        if params.chromiq_clip_style or params.left_clip_info:
            return False
        # Guided mode always uses the engine: it reproduces printtarg's Guided
        # geometry for every instrument/paper/option (verified 161/161, #93). The
        # `use_chromiq_layout_engine` toggle now governs the MANUAL tab only, so
        # the printtarg-based built-in presets keep their exact printtarg layout.
        if not params.is_manual:
            return True
        return bool(self._settings.get("use_chromiq_layout_engine", False))

    def _engine_build_kwargs(self, params: "ChartParams") -> dict:
        spacer_mode = ("none" if params.no_spacers
                       else "bw" if params.bw_spacers else "colored")
        kw: dict = dict(
            instrument=params.instrument,
            paper=params.paper,
            dpi=int(params.tiff_dpi or 300),
            randomize=not params.no_randomise,
            spacer_on=not params.no_spacers,
            spacer_mode=spacer_mode,
            bit16=bool(params.tiff_16bit),
            pscale=float(params.patch_scale or 1.0),
            sscale=float(params.spacer_scale or 1.0),
            border=float(params.margin_mm),
            nolimit=bool(params.no_strip_limit),
        )
        # Guided/basic path: bracket each strip with a leading + trailing spacer
        # for the strip-reader instruments (i1Pro / i1Pro 3+ / ColorMunki), so the
        # instrument always starts and ends a strip on a spacer (#93).
        if params.instrument in ("i1", "p3", "CM"):
            kw["edge_spacers"] = True
        if params.instrument in ("i1", "p3"):
            suppress = _effective_suppress_lb(params)
            kw["nolpcbord"] = suppress
            # Guided/basic path (no layout recipe): when the i1/p3 clip border is
            # kept, fill it with the ChromIQ notes record instead of leaving it
            # blank (Manual already defaults to this via the recipe) (#93).
            kw["clip_content_mode"] = "off" if suppress else "notes"
        elif params.instrument == "CM":
            density = 3 if params.triple_density else (
                2 if params.double_density else 1)
            kw["density"] = density
            if density == 3:
                # patch_scale carries printtarg's -ii1 triple-density -a value
                # (1.3 = the default). The engine's extra-high-density native
                # size (pscale 1.0) reproduces printtarg's -a1.3, so a -a maps to
                # engine scale = -a / 1.3. Guided's 1.3 → 1.0 (unchanged 10.4 mm);
                # a preset's -a1.08 → 0.83 (8.6 mm, matching printtarg exactly).
                kw["pscale"] = float(params.patch_scale or CM_TRIPLE_PRINTTARG_SCALE) \
                    / CM_TRIPLE_PRINTTARG_SCALE
            elif density == 2:
                # printtarg's ColorMunki double density (-h) inseparably couples
                # the 13.7 mm rows with a half-patch row stagger; reproduce it so
                # Guided matches printtarg. (The decoupled cm_stagger toggle stays
                # a Manual-only extra.) (#93)
                kw["cm_stagger"] = True
        elif params.instrument == "SS":
            kw["hflag"] = bool(params.double_density)   # hexagon patches
        return kw

    def _engine_total_patches(self, params: "ChartParams") -> int | None:
        """Patches the engine fits across all pages (capacity × pages), or None.

        Used to drive the targen ``-f`` count in Guided and Manual-auto so the
        chart fills the page(s) under the engine's own packing.
        """
        if not self._should_use_engine(params):
            return None
        try:
            from workflow.layout_engine import geometry, instruments, papers
            kw = self._engine_kwargs(params)
            geom = instruments.geom_from_build_kwargs(kw)
            w_mm, h_mm = papers.dimensions_mm(kw["paper"])
            per_sheet = geometry.patches_per_sheet(geom, w_mm, h_mm)
            return per_sheet * max(1, int(params.pages))
        except Exception as exc:  # noqa: BLE001
            log.warning("engine patch estimate failed: %s", exc)
            return None

    def _engine_kwargs(self, params: "ChartParams") -> dict:
        """build_chart kwargs: the full layout recipe when set, else the basics.

        With a recipe (Manual/editor LayoutOptionsPanel) every layout option
        takes effect; instrument/paper come from the ChartParams, and a printer
        calibration (-K/-I) is attached when chosen.
        """
        if params.layout_recipe is not None and hasattr(params.layout_recipe, "build_kwargs"):
            kw = params.layout_recipe.build_kwargs()
            kw["instrument"] = params.instrument
            kw["paper"] = params.paper
            kw["project"] = params.target_name   # {project} → profile name
            if params.engine_cal_path:
                kw["cal_path"] = params.engine_cal_path
                kw["apply_cal"] = bool(params.engine_apply_cal)
            # The per-edge margin boxes are ALWAYS the law (Knut, new model): the
            # engine never silently raises them to meet instrument-margin minimums.
            # "Use instrument margins" only pre-fills the boxes once in the UI;
            # going below an instrument minimum is allowed and merely flagged as a
            # violation in the Measured-from-Preview panel. So no build-time clamp.
            self._threshold_notes = []
            return kw
        # Guided mode has no editable margin boxes and no "Use instrument
        # margins" toggle, so the jig-safety threshold clamp is intentionally
        # NOT applied here. Clamping pinned the patch count regardless of the
        # clip-border / strip-cap toggles (the thresholds dominated), which the
        # user asked to revert: Guided behaves like before the #93 threshold
        # feature. Mirrors the Guided capacity estimate in
        # tab_chart._engine_geom (thresholds=None) so count and chart agree.
        self._threshold_notes = []
        return self._engine_build_kwargs(params)

    def _apply_margin_thresholds(self, kw: dict) -> dict:
        """Raise the layout's margins so the patch area meets the user's margin
        thresholds for this instrument/paper combo (#93). No-op when the combo
        has no thresholds. Records any adjustments in ``_threshold_notes`` for
        the build log. Applied at this one point so the capacity estimate
        (_engine_total_patches) and the real render agree."""
        self._threshold_notes: list[str] = []
        try:
            from core.settings import thresholds_for_combo
            from workflow.layout_engine import margins_fit, papers
            w_mm, h_mm = papers.dimensions_mm(kw.get("paper", "A4"))
            thr = thresholds_for_combo(
                self._settings.get_margin_thresholds(), kw.get("instrument", "i1"),
                w_mm, h_mm)
            kw, notes = margins_fit.clamp_margins_to_thresholds(kw, thr)
            self._threshold_notes = notes
        except Exception as exc:  # noqa: BLE001 — never block generation on this
            log.warning("margin-threshold clamp skipped: %s", exc)
        return kw

    def _run_engine(
        self,
        params: "ChartParams",
        work_dir: Path,
        on_line: Callable[[str], None],
    ) -> None:
        from workflow.layout_engine import chart as le_chart

        stem = self._file_mgr.chart_stem(cal_target=params.cal_target)
        ti1 = work_dir / f"{stem}.ti1"
        on_line("[ChromIQ layout engine] building chart from the targen .ti1…")
        engine_kwargs = self._engine_kwargs(params)
        for _note in getattr(self, "_threshold_notes", []):
            on_line(f"[ChromIQ layout engine] {_note}")
        try:
            # No .cht at build time: a scan-recognition template is only useful
            # paired with a *measured* .cie, so both are produced together after
            # measurement (workflow.scanin_target, #97) — an aim-value .cht here
            # would just be an orphaned half-target (its aim .cie was dropped in
            # beta.59). The engine keeps the capability (emit_cht) for that flow.
            result = le_chart.build_chart(
                ti1, work_dir / stem, **engine_kwargs)
        except Exception as exc:  # noqa: BLE001 — surface any engine failure
            log.exception("ChromIQ layout engine failed")
            on_line(f"[ERROR] ChromIQ layout engine: {exc}")
            if self._pending_on_finish:
                self._pending_on_finish([])
            return

        on_line(
            f"[ChromIQ layout engine] {result.layout.total_patches} patches "
            f"({result.layout.steps_in_pass}×{result.layout.passes}), "
            f"{result.layout.pages} page(s), random start {result.seed}")
        # Explain a total that grew past the designed count: a partial last
        # strip is topped up with paper-white patches so the instrument reads
        # whole strips (printtarg behaviour, mirrored by the engine). Knut
        # missed this on the ENGINE build path (#124 follow-up) — the note was
        # only on the editor-save and applied-chart copy paths before.
        pad_line = _engine_padding_log_line(result.layout.total_patches,
                                            getattr(result.layout, "padding", 0))
        if pad_line:
            on_line(pad_line)
        if result.low_contrast_passes:
            on_line(f"[ChromIQ layout engine] note: low patch/spacer contrast in "
                    f"{len(result.low_contrast_passes)} strip(s)")

        tiffs = sorted(result.tiff_paths or [])
        if tiffs and self._pending_params is not None:
            self._write_channel_sidecar(work_dir, stem, self._pending_params)
            self._embed_layout_geometry(work_dir, stem, result, params)
            self._stamp_tiff_metadata(tiffs, self._pending_params)

        if self._pending_on_finish:
            self._pending_on_finish(tiffs)

    def _embed_layout_geometry(self, work_dir: Path, stem: str, result,
                               params: "ChartParams") -> None:
        """Fold the engine's strip/patch geometry + recipe into channels.json.

        The Measure-tab highlighter reads this for exact, guess-free strip
        recognition; the recipe enables the Create Chart ⇄ editor round-trip.
        """
        import json
        sidecar = work_dir / f"{stem}.channels.json"
        strips = work_dir / f"{stem}.strips.json"
        try:
            doc = json.loads(sidecar.read_text()) if sidecar.exists() else {}
            layout = json.loads(strips.read_text()) if strips.exists() else {}
            layout["engine"] = "chromiq"      # explicit marker: a ChromIQ-engine chart
            layout["engine_version"] = 1
            layout["seed"] = result.seed
            layout["color_rep"] = result.color_rep
            # Persist the FULL recipe so loading / preset-creation / built-in
            # presets can reconstruct the exact engine layout (round-trip).
            if params.layout_recipe is not None and hasattr(params.layout_recipe, "to_dict"):
                layout["recipe"] = params.layout_recipe.to_dict()
            else:
                # Store a real recipe (not raw build kwargs) so reloading doesn't
                # lose fields like clip_border (which kwargs spell as nolpcbord)
                # and the editor reproduces the exact layout (#93).
                from workflow.layout_engine.presets import LayoutRecipe
                layout["recipe"] = LayoutRecipe.from_build_kwargs(
                    self._engine_build_kwargs(params)).to_dict()
            doc["layout"] = layout
            sidecar.write_text(json.dumps(doc))
            if strips.exists():
                strips.unlink()   # geometry now lives in channels.json
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not embed layout geometry: %s", exc)

    def _printtarg_done(
        self,
        exit_code: int,
        work_dir: Path,
        on_finish: Callable[[list[Path]], None] | None,
        stem: str = "chart",
    ) -> None:
        if exit_code != 0:
            log.error("printtarg failed with code %d", exit_code)
            if on_finish:
                on_finish([])
            return

        # Set-comprehension dedupes Windows' case-insensitive glob matches
        # (chart.tif matches both *.tif and *.TIF), which otherwise made the
        # preview display "Page 1/2" for a single-file chart (forum #148124).
        tiffs = sorted({
            *work_dir.glob(f"{stem}*.tif"),
            *work_dir.glob(f"{stem}*.TIF"),
            *work_dir.glob(f"{stem}*.tiff"),
        })
        log.info("printtarg produced %d TIFF(s) in %s", len(tiffs), work_dir)
        if not tiffs:
            log.warning("No TIFFs found; searched %s for %s*.tif "
                        "(printtarg exited 0 but wrote nothing — usually a "
                        "missing/empty input %s.ti1)", work_dir, stem, stem)

        if tiffs and self._pending_params is not None:
            # Triple-density: printtarg saw -ii1 so it wrote TARGET_INSTRUMENT
            # "GretagMacbeth i1 Pro" into the .ti2 — rewrite it so chartread
            # opens the ColorMunki the user actually owns.
            if self._pending_params.triple_density:
                self._patch_ti2_instrument(work_dir, stem)
            self._write_channel_sidecar(work_dir, stem, self._pending_params)
            self._capture_scanner_cht(work_dir, stem, self._pending_params)
            self._stamp_tiff_metadata(tiffs, self._pending_params)

        if on_finish:
            on_finish(tiffs)

    def _patch_ti2_instrument(self, work_dir: Path, stem: str) -> None:
        """Rewrite TARGET_INSTRUMENT from i1 Pro to ColorMunki for triple density."""
        ti2 = work_dir / f"{stem}.ti2"
        if not ti2.is_file():
            log.warning("ti2 not found for triple-density patch: %s", ti2)
            return
        try:
            text = ti2.read_text(encoding="utf-8", errors="ignore")
            new = text.replace(
                'TARGET_INSTRUMENT "GretagMacbeth i1 Pro"',
                'TARGET_INSTRUMENT "X-Rite ColorMunki"',
            )
            if new != text:
                ti2.write_text(new, encoding="utf-8")
                log.info("Patched %s: i1 Pro → ColorMunki (triple density)", ti2.name)
            else:
                log.warning("ti2 had no i1 Pro line to patch: %s", ti2)
        except OSError as exc:
            log.error("Could not patch ti2 %s: %s", ti2, exc)

    def _stamp_tiff_metadata(self, tiffs: list[Path], params: "ChartParams") -> None:
        """Stamp the actual targen/printtarg commands (and optional notes) into each TIFF."""
        try:
            from core.version import APP_VERSION
            from workflow.tiff_metadata import (
                ALLOWED_LEFT_CLIP_PAPERS,
                shift_patches_for_chromiq_clip,
                stamp_chart_metadata,
                stamp_left_clip_info,
            )
        except Exception as exc:
            log.warning("Could not import metadata stamper: %s", exc)
            return

        patch_count = self._count_patches_in_ti1(
            tiffs[0].parent / f"{self._file_mgr.chart_stem(cal_target=params.cal_target)}.ti1"
        ) or params.patches or 0

        chromiq_clip = _chromiq_clip_active(params)

        # Build the command/notes lines once. They go to the right margin in
        # normal mode, or into a clip-border column under ChromIQ-style.
        cmd_lines: list[str] = []
        if params.chart_notes:
            cmd_lines.append(params.chart_notes)
        if params.stamp_commands:
            # Display-only shortening of long target names / -c profile paths /
            # -K calibration paths. The argv actually handed to ArgyllRunner
            # stays full-length; this only rewrites the string that gets
            # rendered onto the TIFF. " ".join (not shlex.join) so the "(…)"
            # marker doesn't trigger shell quoting in the rendered line.
            if params.chart_layout_name:
                # Built from an existing patch set — targen wasn't run, so name
                # the chart layout instead of stamping a misleading targen line.
                cmd_lines.append(f"Chart layout {params.chart_layout_name} |")
            else:
                cmd_lines.append("targen " + " ".join(
                    _shorten_argv_for_stamp(self._build_targen_args(params, patch_count))
                ))
            if self._should_use_engine(params):
                # The ChromIQ layout engine replaces printtarg, so stamping a
                # printtarg command would be a lie — name the engine instead.
                cmd_lines.append("ChromIQ layout engine")
            else:
                cmd_lines.append("printtarg " + " ".join(
                    _shorten_argv_for_stamp(self._build_printtarg_args(params))
                ))
            cmd_lines.append(f"ChromIQ {APP_VERSION}")

        if not chromiq_clip:
            # Normal mode: commands/notes go to the right margin.
            if cmd_lines:
                stamp_chart_metadata(tiffs, cmd_lines)
        else:
            # ChromIQ-style: shift the patch block right by ~28 mm so the left
            # side becomes a fresh white strip ready for the left-clip stamp.
            shift_patches_for_chromiq_clip(tiffs)

        # Left clip info stamp. Active when:
        #   • ChromIQ-style clipping border is on (always stamp the branded
        #     content into the freshly-shifted white strip), OR
        #   • the user opted in via the per-chart "Print info in left clip
        #     area" toggle AND -L is off (the native i1Pro clip strip exists).
        instrument_ok = params.instrument in {"i1", "p3"}
        paper_ok = params.paper in ALLOWED_LEFT_CLIP_PAPERS
        plain_left_clip = (
            params.left_clip_info
            and instrument_ok
            and not params.disable_left_border
            and paper_ok
        )
        if chromiq_clip or plain_left_clip:
            from data.patch_db import PAPER_LABELS
            paper_label = PAPER_LABELS.get(params.paper, params.paper)
            patches_label = f"{patch_count}-patch" if patch_count else "RGB"
            header_lines = [
                f"ArgyllCMS {patches_label} RGB target on {paper_label}",
                "PRINT: borderless, 100% size (no scaling), color management OFF",
            ]
            # Each field gets its own ": ___" with the underscore length
            # sized to the paper inside stamp_left_clip_info().
            form_fields = [
                "date",
                "printer",
                "ink set",
                "profile name",
                "paper type",
                "driver/resolution",
            ]
            # Under ChromIQ-style the commands/notes become a clip-border
            # column instead of the (now off-page) right margin.
            command_lines = cmd_lines if chromiq_clip else None
            stamp_left_clip_info(
                tiffs, header_lines, form_fields, inner_lines=[],
                command_lines=command_lines,
            )

    @staticmethod
    def _count_patches_in_ti1(ti1_path: Path) -> int | None:
        """Best-effort patch-count parse from a targen .ti1 file (NUMBER_OF_SETS)."""
        if not ti1_path.is_file():
            return None
        try:
            for line in ti1_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.strip().startswith("NUMBER_OF_SETS"):
                    return int(line.split()[-1])
        except Exception as exc:
            log.debug("Could not parse patch count from %s: %s", ti1_path, exc)
        return None

    def _write_channel_sidecar(
        self, work_dir: Path, stem: str, params: "ChartParams"
    ) -> None:
        """Write <stem>.channels.json so the preview can identify inks in future sessions."""
        import json
        from ui.tiff_preview import resolve_ink_channels
        channels = resolve_ink_channels(params.device_type, params.extra_targen_args)
        sidecar = work_dir / f"{stem}.channels.json"
        try:
            sidecar.write_text(json.dumps({
                "ink_channels": channels,
                # Create Chart restores these two when the chart is loaded
                # again — the TIFF stamp itself can't be read back (mavtop,
                # forum). Recorded for engine and printtarg charts alike.
                "chart_notes": params.chart_notes,
                "stamp_commands": bool(params.stamp_commands),
            }))
            log.debug("Wrote channel sidecar %s: %s", sidecar.name, channels)
        except Exception as exc:
            log.warning("Could not write channel sidecar: %s", exc)

    def _capture_scanner_cht(self, work_dir: Path, stem: str,
                             params: "ChartParams") -> None:
        """Best-effort: store this chart's exact scan-recognition geometry in
        ``channels.json`` so a scanner target can be built later (#8).

        First choice is printtarg's own ``.cht`` (:meth:`_capture_printtarg_cht`
        re-runs it with ``-s``); when that capture is impossible — scan mode
        paginates a few tightly-packed layouts differently (e.g. ColorMunki
        double density at -a0.91–0.93, #108) — fall back to deriving the
        geometry from the rendered TIFF itself, colour-verified patch by patch
        against the ``.ti2`` (:mod:`workflow.layout_from_render`). Both paths
        are correct-or-absent; never raises into the caller.

        Skipped for non-RGB charts: scan geometry is colour-matched in RGB and a
        CMYK / CMYK+N printer target is measured with a spectro, never scanned —
        so there is nothing to capture (and the RGB matchers would only warn)."""
        if params.device_type not in ("2", "3"):     # 2=Print RGB, 3=Video RGB
            log.debug("Scanner .cht capture skipped for %s (device -d%s is not RGB)",
                      stem, params.device_type)
            return
        if not self._capture_printtarg_cht(work_dir, stem, params):
            self._derive_geometry_from_render(work_dir, stem)

    def _capture_printtarg_cht(self, work_dir: Path, stem: str,
                               params: "ChartParams") -> bool:
        """Capture printtarg's exact ``.cht`` geometry into ``channels.json``,
        returning True when stored.

        Re-runs printtarg with ``-s`` on the chart's own ``.ti1`` in a temp dir.
        printtarg's ``.cht`` is **seed-independent** (it encodes loc→position,
        which the random patch assignment doesn't touch — verified), so it matches
        the printed sheet regardless of randomisation; a low render DPI keeps it
        fast. We only persist it after checking its patch locs against the chart's
        own ``.ti2`` — correct-or-absent, never silently wrong."""
        import json
        import shutil
        import subprocess
        import tempfile

        try:
            ti1 = work_dir / f"{stem}.ti1"
            if not ti1.is_file():
                return False
            from core.resource_path import argyll_binary
            bin_dir = Path(self._settings.get("argyll_bin_path",
                                              "/Applications/Argyll/bin"))
            pt = bin_dir / argyll_binary("printtarg")
            if not pt.exists():
                return False
            # Same layout args, but a temp basename, a fast low render DPI (the
            # .cht is in device-independent points), and -s to emit the .cht.
            args = [a for a in self._build_printtarg_args(params)
                    if not (a.startswith("-t") or a.startswith("-T"))]
            args[-1] = "cap"                       # swap the chart stem
            cmd = [str(pt), "-s", "-t72", *args]
            with tempfile.TemporaryDirectory(prefix="chromiq_cht_") as td:
                tdp = Path(td)
                shutil.copy(ti1, tdp / "cap.ti1")
                subprocess.run(cmd, cwd=td, capture_output=True, text=True,
                               timeout=120)
                pages = [c.read_text(encoding="utf-8")
                         for c in sorted(tdp.glob("cap*.cht"))]
            if not pages:
                log.warning("Scanner .cht capture produced no file for %s", stem)
                return False
            # printtarg's scan mode (-s) needs slightly more room per page,
            # so a chart packed to the last few percent of capacity paginates
            # differently with -s (verified: CM double density at -a0.91–0.93
            # spills 2→3 pages; ≤0.90 matches again; i1/CM-plain never diverge
            # — #108, Knut). A capture whose page count differs from the
            # printed chart is wrong by construction: discard it
            # (correct-or-absent, never silently off).
            printed = len(sorted(work_dir.glob(f"{stem}_*.tif")))
            if printed == 0 and (work_dir / f"{stem}.tif").is_file():
                printed = 1
            if printed and len(pages) != printed:
                log.warning(
                    "Scanner .cht capture discarded for %s: printtarg -s laid "
                    "out %d page(s) but the printed chart has %d — this chart "
                    "type can't carry scan-recognition geometry.",
                    stem, len(pages), printed)
                return False
            # Verify the captured geometry against the chart's own .ti2.
            from workflow.scanin_target import _cht_x_box_locs
            from workflow.ti3_analysis import parse_ti3
            ti2 = work_dir / f"{stem}.ti2"
            ti2_locs = set(parse_ti3(ti2).sample_locs) if ti2.is_file() else set()
            cht_locs: set[str] = set()
            for text in pages:
                cht_locs |= set(_cht_x_box_locs(text))
            if ti2_locs and cht_locs != ti2_locs:
                log.warning("Scanner .cht capture loc mismatch for %s (%d vs %d) "
                            "— not stored", stem, len(cht_locs), len(ti2_locs))
                return False
            sidecar = work_dir / f"{stem}.channels.json"
            doc = json.loads(sidecar.read_text()) if sidecar.exists() else {}
            doc["layout"] = {"engine": "printtarg", "cht_pages": pages,
                             "locs": sorted(cht_locs)}
            sidecar.write_text(json.dumps(doc))
            log.info("Captured scanner .cht geometry for %s: %d page(s), %d patches",
                     stem, len(pages), len(cht_locs))
            return True
        except Exception as exc:  # noqa: BLE001 — best-effort, never break creation
            log.warning("Scanner .cht capture failed for %s (non-fatal): %s",
                        stem, exc)
        return False

    def _derive_geometry_from_render(self, work_dir: Path, stem: str) -> None:
        """Fallback scan geometry: derive the exact patch grid from the chart's
        own rendered TIFF(s), colour-verified against the .ti2 patch by patch
        (workflow.layout_from_render). Correct-or-absent; never raises."""
        import json
        try:
            ti2 = work_dir / f"{stem}.ti2"
            tiffs = sorted(work_dir.glob(f"{stem}_*.tif"))
            if not tiffs and (work_dir / f"{stem}.tif").is_file():
                tiffs = [work_dir / f"{stem}.tif"]
            if not ti2.is_file() or not tiffs:
                return
            from workflow.layout_from_render import derive_layout_from_render
            layout = derive_layout_from_render(tiffs, ti2)
            sidecar = work_dir / f"{stem}.channels.json"
            doc = json.loads(sidecar.read_text()) if sidecar.exists() else {}
            doc["layout"] = layout
            sidecar.write_text(json.dumps(doc))
            log.info("Derived scanner geometry from the render for %s: "
                     "%d patches, %d page(s)", stem,
                     len(layout["patches"]), len(tiffs))
        except Exception as exc:  # noqa: BLE001 — best-effort, never break creation
            log.warning("Render-derived geometry failed for %s (non-fatal): %s",
                        stem, exc)

    # ------------------------------------------------------------------
    # Arg builders
    # ------------------------------------------------------------------

    def _build_targen_args(self, p: ChartParams, patches: int) -> list[str]:
        args: list[str] = [f"-d{p.device_type}"]
        args += [f"-f{patches}"]
        args += [f"-e{p.white_patches}"]
        args += [f"-B{p.black_patches}"]
        if p.fast_sampler:
            # Perceptual quasi-random full-spread: keeps the preconditioning
            # distribution but skips OFPS (which can hang on some profiles).
            # -G only tunes OFPS, so it's mutually exclusive with -Q here.
            args.append("-Q")
        elif p.good_mode:
            args.append("-G")
        if p.grey_steps > 0:
            # -n samples the profile-defined neutral axis; only valid with -c,
            # which Guided Mode pairs it with. Otherwise the naïve device grey -g.
            flag = "-n" if p.neutral_axis_from_profile else "-g"
            args += [f"{flag}{p.grey_steps}"]
        if p.single_channel_steps > 0:
            args += [f"-s{p.single_channel_steps}"]
        if p.extra_targen_args:
            args += shlex.split(p.extra_targen_args)
        args.append(self._file_mgr.chart_stem(cal_target=p.cal_target))
        return args

    def _build_printtarg_args(self, p: ChartParams) -> list[str]:
        args: list[str] = []
        # Triple-density (CM + rig) emulates the i1Pro layout by swapping the
        # instrument to -ii1 and forcing -L; the matching -a / -m / -P preset
        # (1.3 / 5 / on) is seeded into the manual widgets when the user
        # toggles Triple density on but the user can override those values
        # afterwards, so we pass p.patch_scale / p.margin_mm / p.no_strip_limit
        # through verbatim. Guided mode sets the same preset values directly
        # on ChartParams.
        triple = p.triple_density and p.instrument == "CM"
        if triple:
            pt_instr = "i1"
        elif p.instrument in EXTERNAL_INSTRUMENTS:
            # i1iSis is driven by i1Profiler, not Argyll. We still run printtarg
            # to give the user a layout preview, but i1Profiler re-lays-out the
            # actual chart from the patch list, so a generic strip layout (i1)
            # is fine here.
            pt_instr = "i1"
        else:
            # printtarg uses "3p" for i1Pro 3 Plus; help text lists "p3" but that's a typo
            pt_instr = "3p" if p.instrument == "p3" else p.instrument
        args.append(f"-i{pt_instr}")
        args.append(f"-p{p.paper}")
        dpi_flag = "-T" if p.tiff_16bit else "-t"
        args.append(f"{dpi_flag}{p.tiff_dpi}")
        # -h is only meaningful for CM (double density) and SS (hexagon
        # patches). -L only affects strip instruments (i1, p3). Filter
        # so leftover UI state can't append no-op flags to the recorded
        # command in stamped TIFF metadata.
        if not triple and p.double_density and p.instrument in {"CM", "SS"}:
            args.append("-h")
        # ChromIQ-style clipping border forces -L regardless of the per-chart
        # toggle so printtarg fills the page with patches; we manufacture the
        # clip strip post-process in _stamp_tiff_metadata. Triple density
        # uses the i1 strip layout and the suppress-LB widget is hidden in
        # that mode, so -L is forced unconditionally too.
        force_l = _chromiq_clip_active(p) or triple
        l_applies = p.instrument in {"i1", "p3"} or triple
        if (p.disable_left_border or force_l) and l_applies:
            args.append("-L")
        if abs(p.patch_scale - 1.0) > 0.01:
            # 2 decimals normally (so -a1.30 / -a0.95 read as before), but keep a
            # 3rd place when the value actually needs it — the TC9.18+Spyderprint
            # presets are tuned to 3 decimals (0.929, 1.125, 1.013, …) to land on
            # an exact page count.
            scale = (f"{p.patch_scale:.2f}"
                     if round(p.patch_scale, 2) == round(p.patch_scale, 3)
                     else f"{p.patch_scale:.3f}")
            args += [f"-a{scale}"]
        if p.margin_mm != 6:
            args += [f"-m{p.margin_mm}"]
        args.append(f"-M{p.margin_mm}")
        if p.no_randomise:
            args.append("-r")
        if p.bw_spacers:
            args.append("-b")
        if p.no_strip_limit:
            args.append("-P")
        if p.extra_printtarg_args:
            args += shlex.split(p.extra_printtarg_args)
        args.append(self._file_mgr.chart_stem(cal_target=p.cal_target))
        return args

    # ------------------------------------------------------------------
    # Patch count helpers
    # ------------------------------------------------------------------

    def _lookup_patches(self, p: ChartParams) -> int:
        eng = self._engine_total_patches(p)
        if eng is not None:
            return eng
        eff_lb = _effective_suppress_lb(p)
        triple = p.triple_density and p.instrument == "CM"
        layout_extras = _extra_printtarg_affects_layout(p.extra_printtarg_args)
        if (not layout_extras
                and (triple or any(abs(p.patch_scale - s) <= 0.01
                                   for s in SUPPORTED_PATCH_SCALES))):
            per_sheet = query_patches(p.instrument, p.paper, p.double_density,
                                      suppress_lb=eff_lb,
                                      margin_mm=p.margin_mm,
                                      patch_scale=p.patch_scale,
                                      triple_density=triple,
                                      no_strip_limit=p.no_strip_limit)
            if per_sheet is not None:
                return per_sheet * p.pages
        return self._binary_search(p) * p.pages

    def _binary_search(
        self,
        p: ChartParams,
        progress_cb: Callable[[str], None] | None = None,
    ) -> int:
        bin_dir = Path(self._settings.get("argyll_bin_path", "/Applications/Argyll/bin"))
        targen_bin    = bin_dir / "targen"
        printtarg_bin = bin_dir / "printtarg"

        eff_lb = _effective_suppress_lb(p)
        triple = p.triple_density and p.instrument == "CM"
        if not targen_bin.exists():
            log.warning("targen not found for binary search, returning estimate")
            return (query_patches(p.instrument, p.paper, p.double_density,
                                  suppress_lb=eff_lb,
                                  margin_mm=p.margin_mm,
                                  patch_scale=p.patch_scale,
                                  triple_density=triple,
                                  no_strip_limit=p.no_strip_limit)
                    or query_patches(p.instrument, p.paper, p.double_density,
                                     suppress_lb=eff_lb,
                                     triple_density=triple,
                                     no_strip_limit=p.no_strip_limit)
                    or 500)

        pt_args_base = self._build_printtarg_args(p)[:-1]  # strip trailing target name

        est_raw = (query_patches(p.instrument, p.paper, p.double_density,
                                 suppress_lb=eff_lb,
                                 margin_mm=p.margin_mm,
                                 patch_scale=p.patch_scale,
                                 triple_density=triple,
                                 no_strip_limit=p.no_strip_limit)
                   or query_patches(p.instrument, p.paper, p.double_density,
                                    suppress_lb=eff_lb,
                                    triple_density=triple,
                                    no_strip_limit=p.no_strip_limit)
                   or 400)
        # Per-sheet capacity scales roughly as 1/patch_scale² — each patch
        # occupies patch_scale² of the standard cell area. Without this
        # adjustment the [0.5×, 2.5×] window misses the real value for
        # patch_scale > ~1.4, the loop never sees pages==1, and `best`
        # stays at its initial sentinel.
        scale_sq = max(p.patch_scale ** 2, 0.01)
        est = max(20, int(est_raw / scale_sq))

        lo = max(20, int(est * 0.5))
        hi = max(lo + 50, int(est * 2.5))
        lo_init, hi_init = lo, hi
        best = 0

        with tempfile.TemporaryDirectory() as tmp_str:
            tmpdir = Path(tmp_str)
            total_steps = max(1, (hi - lo).bit_length())
            step = 0

            while lo <= hi:
                mid = (lo + hi) // 2
                step += 1
                if progress_cb:
                    progress_cb(f"Step {step}/{total_steps} — probing {mid} patches…")

                pages = self._probe(targen_bin, printtarg_bin, mid, p.device_type,
                                    pt_args_base + ["calc"], tmpdir)
                self._cleanup_probe(tmpdir)

                if pages == 0:
                    hi = mid - 1
                elif pages == 1:
                    best = mid
                    lo = mid + 1
                else:
                    hi = mid - 1

        if best == 0:
            log.warning("_binary_search found no valid capacity in [%d, %d]; "
                        "falling back to scaled estimate %d", lo_init, hi_init, est)
            return est
        return best

    @staticmethod
    def _probe(
        targen_bin: Path,
        printtarg_bin: Path,
        patches: int,
        device_type: str,
        pt_args: list[str],
        tmpdir: Path,
    ) -> int:
        tg_args = [f"-d{device_type}", f"-f{patches}", "calc"]
        r = subprocess.run(
            [str(targen_bin)] + tg_args,
            capture_output=True, timeout=60, cwd=str(tmpdir),
            stdin=subprocess.DEVNULL,
        )
        if r.returncode != 0 or not (tmpdir / "calc.ti1").exists():
            return 0
        pt = subprocess.run(
            [str(printtarg_bin)] + pt_args,
            capture_output=True, timeout=60, cwd=str(tmpdir),
            stdin=subprocess.DEVNULL,
        )
        if pt.returncode != 0:
            return 0
        return len(list(tmpdir.glob("calc*.tif")))

    @staticmethod
    def _cleanup_probe(tmpdir: Path) -> None:
        for f in tmpdir.glob("calc*"):
            try:
                f.unlink()
            except OSError:
                pass
