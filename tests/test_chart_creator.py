"""Regression tests for the ChartCreator sidecar pipeline.

Issue #15 surfaced a gap: `_printtarg_done` writes the `<stem>.channels.json`
sidecar only when `self._pending_params` is non-None. The `generate()` entry
point sets it, but `load_ti1_and_generate_preview()` did not — so loading a
chart from an existing .ti1 produced no sidecar, leaving the preview unable
to identify inks in a future session.
"""
from __future__ import annotations

import json
import os
import shlex
from pathlib import Path

import numpy as np
import pytest
import tifffile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from data.patch_db import (
    I1PRO_DEFAULT_PRESET_KEY,
    I1PRO_DEFAULT_PRESETS,
    INSTRUMENT_DEFAULT_MARGIN,
    i1_defaults_from_preset,
    query_patches,
)
from tests.argyll_env import argyll_bin_dir, argyll_tool
from workflow.chart_creator import (
    ChartCreator,
    ChartParams,
    GUIDED_NEUTRAL_BASE,
    guided_neutrals,
    manual_neutrals,
)


class _MockRunner:
    """Synchronously fire on_finish(0) and stage the files printtarg would create."""

    def run(self, tool, args, cwd, on_line=None, on_finish=None):
        cwd = Path(cwd)
        stem = args[-1]
        if tool == "targen":
            (cwd / f"{stem}.ti1").write_text("FAKE TI1", encoding="utf-8")
        elif tool == "printtarg":
            (cwd / f"{stem}.ti2").write_text("FAKE TI2", encoding="utf-8")
            arr = np.zeros((100, 100, 3), dtype=np.uint8)
            tifffile.imwrite(
                str(cwd / f"{stem}_01.tif"),
                arr,
                resolution=(200, 200),
                resolutionunit="INCH",
            )
        if on_finish:
            on_finish(0)


class _MockFileManager:
    """Minimal FileManager stub for chart_creator tests.

    Backs ``project()`` with the real Project class so chart_creator's
    Project/Run-aware paths exercise the actual folder layout under tmp_path.
    """

    def __init__(self, root: Path) -> None:
        # ``root`` here is the *project* root (mirrors what working_dir()
        # would return in the real FileManager).
        self.root = root
        self._project = None

    def ensure_folder(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root

    def clean_folder(self, exts: list[str]) -> None:
        for f in self.root.iterdir():
            if f.is_file() and f.suffix.lstrip(".").lower() in exts:
                f.unlink()

    def project(self):
        from core.file_manager import Project
        if self._project is None:
            self._project = Project.create_or_load(self.root, self.root.name)
        return self._project

    def cwd_for_chart(self, *, cal_target: bool) -> Path:
        proj = self.project()
        return proj.calibration.ensure_dir() if cal_target else proj.current_run().ensure_dir()

    def chart_stem(self, *, cal_target: bool) -> str:
        proj = self.project()
        return proj.calibration.stem if cal_target else proj.current_run().stem


class _MockSettings:
    def get(self, key, default=None):
        # Mirror a configured app: the real Argyll wherever it lives on this
        # machine, not the product's macOS-shaped fallback default.
        if key == "argyll_bin_path":
            found = argyll_bin_dir()
            if found is not None:
                return str(found)
        return default


def _make_creator(tmp_path: Path) -> tuple[ChartCreator, Path]:
    work_dir = tmp_path / "chart_proj"
    return ChartCreator(_MockRunner(), _MockFileManager(work_dir), _MockSettings()), work_dir


def test_generate_writes_channels_sidecar(tmp_path: Path) -> None:
    creator, work_dir = _make_creator(tmp_path)
    finished: list[list[Path]] = []
    creator.generate(
        # Guided always uses the engine now (#93); exercise the printtarg
        # generation path (driven by the fake ArgyllRunner) via the Manual flow.
        ChartParams(target_name="mychart", device_type="2", is_manual=True),
        on_line=lambda _: None,
        on_finish=lambda tiffs: finished.append(tiffs),
    )
    # New layout: sidecar lives next to <stem>.ti1 inside runs/run1/, where
    # stem is the (sanitised) project folder name.
    sidecar = work_dir / "runs" / "run1" / "chart_proj.channels.json"
    assert sidecar.exists(), "generate() must write the channels sidecar"
    assert json.loads(sidecar.read_text(encoding="utf-8"))["ink_channels"] == ["r", "g", "b"]


def test_query_patches_margin10_i1_a4_with_left_border() -> None:
    """margin=10 i1/A4 must return the measured table value (not the m=6 baseline)."""
    n_m6 = query_patches("i1", "A4", suppress_lb=True, margin_mm=6)
    n_m10 = query_patches("i1", "A4", suppress_lb=True, margin_mm=10)
    assert n_m6 is not None and n_m10 is not None
    assert n_m10 < n_m6, "margin=10 must fit fewer patches than margin=6"
    assert n_m10 == 483, "regression guard against accidental table edits"


def test_query_patches_margin10_respects_left_border_flag() -> None:
    """The -L vs no-L distinction must propagate through margin=10 lookups."""
    with_l = query_patches("i1", "A4", suppress_lb=True, margin_mm=10)
    without_l = query_patches("i1", "A4", suppress_lb=False, margin_mm=10)
    assert with_l is not None and without_l is not None
    assert with_l > without_l, "-L must yield more patches than no-L"


def test_query_patches_unsupported_margin_returns_none() -> None:
    """Margin values outside {6, 10} must return None so callers fall back to binary search."""
    assert query_patches("i1", "A4", margin_mm=8) is None
    assert query_patches("i1", "A4", margin_mm=15) is None


def test_query_patches_margin10_only_for_i1_and_p3() -> None:
    """CM and SS don't change defaults, so their margin=10 lookups should be missing."""
    assert query_patches("CM", "A4", margin_mm=10) is None
    assert query_patches("SS", "A4", margin_mm=10) is None


def test_query_patches_scale095_i1_a4_with_left_border() -> None:
    """scale=0.95 must return a measured value bigger than the scale=1.0 baseline."""
    n_10 = query_patches("i1", "A4", suppress_lb=True, margin_mm=6, patch_scale=1.0)
    n_95 = query_patches("i1", "A4", suppress_lb=True, margin_mm=6, patch_scale=0.95)
    assert n_10 is not None and n_95 is not None
    assert n_95 > n_10, "smaller patches must fit more per sheet"
    assert n_95 == 550, "regression guard against accidental table edits"


def test_query_patches_scale095_respects_margin_and_lb() -> None:
    """scale=0.95 dispatch must propagate margin and -L flags."""
    m6_lb  = query_patches("i1", "A4", suppress_lb=True,  margin_mm=6,  patch_scale=0.95)
    m6_nolb = query_patches("i1", "A4", suppress_lb=False, margin_mm=6,  patch_scale=0.95)
    m10_lb = query_patches("i1", "A4", suppress_lb=True,  margin_mm=10, patch_scale=0.95)
    assert m6_lb is not None and m6_nolb is not None and m10_lb is not None
    assert m6_lb > m6_nolb, "-L must yield more patches than no-L"
    assert m6_lb > m10_lb,  "m=6 must yield more patches than m=10"


def test_query_patches_scale095_covers_cm_double_density() -> None:
    """CM at scale=0.95 must be covered for both -h states; -h gives ~2× capacity."""
    cm_std = query_patches("CM", "A4", double_density=False, margin_mm=6, patch_scale=0.95)
    cm_dd  = query_patches("CM", "A4", double_density=True,  margin_mm=6, patch_scale=0.95)
    assert cm_std is not None and cm_dd is not None
    assert cm_dd > cm_std, "-h must roughly double CM capacity"


def test_query_patches_scale095_no_cm_at_margin10() -> None:
    """CM doesn't have m=10 entries at any scale — must return None to trigger fallback."""
    assert query_patches("CM", "A4", margin_mm=10, patch_scale=0.95) is None


def test_query_patches_unsupported_scale_returns_none() -> None:
    """Scales outside SUPPORTED_PATCH_SCALES must return None so callers fall back."""
    assert query_patches("i1", "A4", margin_mm=6, patch_scale=0.85) is None
    assert query_patches("i1", "A4", margin_mm=6, patch_scale=1.10) is None


def test_query_patches_no_strip_limit_i1_big_paper() -> None:
    """-P removes the strip-length cap; big papers gain a lot of capacity."""
    base = query_patches("i1", "A2", suppress_lb=True, margin_mm=6, patch_scale=1.0)
    nsl  = query_patches("i1", "A2", suppress_lb=True, margin_mm=6, patch_scale=1.0,
                         no_strip_limit=True)
    assert base is not None and nsl is not None
    assert nsl > base, "-P must add patches when the cap previously bit"
    assert nsl == 2500, "regression guard against accidental table edits"


def test_query_patches_no_strip_limit_respects_margin_scale_lb() -> None:
    """-P dispatch must propagate margin, scale and -L through to the right table."""
    m6_lb   = query_patches("i1", "A2", suppress_lb=True,  margin_mm=6,  patch_scale=1.0,  no_strip_limit=True)
    m6_nolb = query_patches("i1", "A2", suppress_lb=False, margin_mm=6,  patch_scale=1.0,  no_strip_limit=True)
    m10_lb  = query_patches("i1", "A2", suppress_lb=True,  margin_mm=10, patch_scale=1.0,  no_strip_limit=True)
    a095_lb = query_patches("i1", "A2", suppress_lb=True,  margin_mm=6,  patch_scale=0.95, no_strip_limit=True)
    assert all(v is not None for v in (m6_lb, m6_nolb, m10_lb, a095_lb))
    assert m6_lb > m6_nolb, "-L must yield more patches than no-L under -P"
    assert m6_lb >= m10_lb, "m=6 must yield at least as many patches as m=10 under -P"
    assert a095_lb > m6_lb, "smaller patches (-a 0.95) must fit more per sheet under -P"


def test_query_patches_no_strip_limit_ignored_for_cm_and_ss() -> None:
    """-P only affects i1/p3 strip layouts; CM/SS must return their normal values."""
    assert (query_patches("CM", "A4", no_strip_limit=True)
            == query_patches("CM", "A4", no_strip_limit=False))
    assert (query_patches("SS", "A4", no_strip_limit=True)
            == query_patches("SS", "A4", no_strip_limit=False))


def test_query_patches_a2_landscape_all_instruments() -> None:
    """A2 landscape (594x420) is measured for every instrument + dd combo."""
    assert query_patches("i1", "594x420", suppress_lb=True, margin_mm=6) is not None
    assert query_patches("p3", "594x420", suppress_lb=True, margin_mm=6) is not None
    assert query_patches("CM", "594x420", double_density=False) is not None
    assert query_patches("CM", "594x420", double_density=True) is not None
    assert query_patches("SS", "594x420", double_density=False) is not None
    assert query_patches("SS", "594x420", double_density=True) is not None
    assert query_patches("CM", "594x420", triple_density=True,
                         margin_mm=5, patch_scale=1.3,
                         no_strip_limit=True) is not None


def test_query_patches_a2_landscape_beats_portrait_for_strip_readers() -> None:
    """Landscape A2 packs more strips than portrait A2 on i1/p3 (the whole point)."""
    for instr in ("i1", "p3"):
        port = query_patches(instr, "A2", suppress_lb=True, margin_mm=6)
        land = query_patches(instr, "594x420", suppress_lb=True, margin_mm=6)
        assert port is not None and land is not None
        assert land > port, f"{instr}: landscape A2 should beat portrait"


def test_query_patches_a2_landscape_regression_guard() -> None:
    """Exact-value guards against accidental table edits."""
    assert query_patches("i1", "594x420", suppress_lb=True, margin_mm=6) == 1512
    assert query_patches("p3", "594x420", suppress_lb=True, margin_mm=6) == 324
    assert query_patches("i1", "594x420", suppress_lb=True, margin_mm=6,
                         no_strip_limit=True) == 2520
    assert query_patches("CM", "594x420", triple_density=True,
                         margin_mm=5, patch_scale=1.3,
                         no_strip_limit=True) == 1485


def test_query_patches_triple_density_returns_none_on_override() -> None:
    """Triple table only applies at its measurement preset (-a1.3 -m5 -P).

    When the manual UI lets the user edit -a / -m / -P after toggling
    Triple density on, query_patches must return None so callers fall back
    to a live binary search via _build_printtarg_args.
    """
    base = query_patches("CM", "A4", triple_density=True,
                         margin_mm=5, patch_scale=1.3, no_strip_limit=True)
    assert base is not None, "preset lookup must succeed"
    assert query_patches("CM", "A4", triple_density=True,
                         margin_mm=6, patch_scale=1.3, no_strip_limit=True) is None
    assert query_patches("CM", "A4", triple_density=True,
                         margin_mm=5, patch_scale=1.0, no_strip_limit=True) is None
    assert query_patches("CM", "A4", triple_density=True,
                         margin_mm=5, patch_scale=1.3, no_strip_limit=False) is None


def test_build_printtarg_args_triple_honors_user_overrides(tmp_path: Path) -> None:
    """Triple density must pass user-edited -a / -m / -P through to printtarg.

    Bug fix: previously _build_printtarg_args hard-coded -a1.30 -m5 -M5 -P
    whenever triple_density was on, silently discarding manual-mode widget
    overrides of those flags.
    """
    creator, _ = _make_creator(tmp_path)
    p = ChartParams(
        instrument="CM",
        paper="A4",
        triple_density=True,
        patch_scale=1.5,        # user overrode 1.3 → 1.5
        margin_mm=8,            # user overrode 5 → 8
        no_strip_limit=False,   # user unticked -P
        disable_left_border=True,
        target_name="t",
    )
    args = creator._build_printtarg_args(p)
    assert "-ii1" in args, "triple still swaps instrument to -ii1"
    assert "-L" in args, "triple still forces -L"
    assert "-a1.50" in args, "user's -a override must flow through"
    assert "-m8" in args and "-M8" in args, "user's -m override must flow through"
    assert "-P" not in args, "user's unchecked -P must be respected"


def test_estimate_patches_routes_to_binary_search_on_spacer_extras(tmp_path: Path) -> None:
    """-A != 1.0 (spacer-only scale) and -n (no spacers) must trigger the
    binary search path so the override actually changes the patch count.

    Previously the fast patch_db lookup ran unconditionally on supported
    patch_scale values, ignoring extra_printtarg_args entirely.
    """
    from workflow import chart_creator as cc

    creator, _ = _make_creator(tmp_path)

    binary_called: list[bool] = []

    def fake_binary(p, progress_cb=None):
        binary_called.append(True)
        return 123

    # Override the binary search so we can observe whether it was invoked.
    creator._binary_search = fake_binary  # type: ignore[method-assign]

    # Baseline: no layout-affecting extras → fast lookup should still win.
    # Guided uses the engine's own capacity now (#93); the patch_db / binary-
    # search routing under test is the Manual path, so these are is_manual=True.
    p_default = ChartParams(instrument="i1", paper="A4", pages=1, is_manual=True,
                            patch_scale=1.0, margin_mm=6)
    n_default = creator.estimate_patches(p_default)
    assert not binary_called, "no extras → fast lookup expected"
    assert n_default == query_patches("i1", "A4", suppress_lb=True,
                                      margin_mm=6, patch_scale=1.0)

    # -A 0.5: layout-affecting extra → must route to binary search.
    binary_called.clear()
    p_spacer = ChartParams(instrument="i1", paper="A4", pages=1, is_manual=True,
                           patch_scale=1.0, margin_mm=6,
                           extra_printtarg_args="-A 0.5")
    assert creator.estimate_patches(p_spacer) == 123
    assert binary_called == [True], "-A 0.5 must trigger binary search"

    # -n (no spacers): also layout-affecting.
    binary_called.clear()
    p_nospacer = ChartParams(instrument="i1", paper="A4", pages=1, is_manual=True,
                             patch_scale=1.0, margin_mm=6,
                             extra_printtarg_args="-n")
    assert creator.estimate_patches(p_nospacer) == 123
    assert binary_called == [True], "-n must trigger binary search"

    # -A 1.0 (default value) and layout-neutral extras must NOT force binary.
    binary_called.clear()
    p_neutral = ChartParams(instrument="i1", paper="A4", pages=1, is_manual=True,
                            patch_scale=1.0, margin_mm=6,
                            extra_printtarg_args="-A 1.0 -Q 8")
    creator.estimate_patches(p_neutral)
    assert not binary_called, "layout-neutral extras must not force binary search"


def test_parameter_widget_float_get_value_avoids_ulp_noise() -> None:
    """Stepping a -A spinbox must produce "1.20", not "1.2000000000000002".

    QDoubleSpinBox tracks the value as a binary double, so stepping
    1.0 → 1.1 → 1.2 lands on 1.2000000000000002. setDecimals(2) hides this
    in the spinbox display, but str(c.value()) would otherwise leak the
    noise into extra_printtarg_args and from there into the live preview
    and the actual printtarg call.
    """
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])  # noqa: F841

    from ui.parameter_widget import ParameterWidget
    pw = ParameterWidget({
        "flag": "-A",
        "name": "Spacer-Only Scale",
        "type": "float",
        "min": 0.1,
        "max": 4.0,
        "default": 1.0,
        "step": 0.1,
    })
    spin = pw._control
    spin.setValue(1.0)
    spin.stepBy(1)  # 1.0 → 1.1
    spin.stepBy(1)  # 1.1 → 1.2 (raw double picks up ULP noise here)
    assert pw.get_value() == "1.20"
    assert pw.build_args() == ["-A", "1.20"]


def test_extra_printtarg_affects_layout_helper() -> None:
    """The detector accepts both -A 1.5 and -A1.5 spellings."""
    from workflow.chart_creator import _extra_printtarg_affects_layout
    assert _extra_printtarg_affects_layout("") is False
    assert _extra_printtarg_affects_layout("-Q 8") is False
    assert _extra_printtarg_affects_layout("-A 1.0") is False
    assert _extra_printtarg_affects_layout("-A 0.5") is True
    assert _extra_printtarg_affects_layout("-A0.5") is True
    assert _extra_printtarg_affects_layout("-A 2.0") is True
    assert _extra_printtarg_affects_layout("-n") is True
    assert _extra_printtarg_affects_layout("-K cal.cal") is False


def test_guided_neutrals_still_works_with_triple_density() -> None:
    """guided_neutrals must keep returning a patch_db lookup for triple density.

    Bug-fix follow-up: with query_patches now returning None on non-preset
    triple_density calls, guided_neutrals needs an explicit retry at the
    triple preset (-a1.3 -m5 -P). Without that retry the function would
    fall back to the page-count ladder and produce noticeably different
    neutrals for triple-density charts.
    """
    g_triple, w_triple, b_triple = guided_neutrals(
        "CM", "A4", pages=1,
        base_white=GUIDED_NEUTRAL_BASE, base_black=GUIDED_NEUTRAL_BASE,
        suppress_lb=True, triple_density=True,
    )
    g_page_ladder, _, _ = guided_neutrals(
        "??", "A4", pages=1,
        base_white=GUIDED_NEUTRAL_BASE, base_black=GUIDED_NEUTRAL_BASE,
        suppress_lb=True,
    )
    # If the triple retry is missing, g_triple collapses to the page ladder
    # (eff_sheets = 1 → grey = 32). The real triple anchor for CM/A4 is
    # ~324 patches → eff = 0.58 → grey ≈ 18, well below 32.
    assert g_triple < g_page_ladder, (
        "triple density must use its patch_db anchor, not the page ladder"
    )


def test_grey_ramp_reference_default_anchor() -> None:
    """At the default anchor (560 patches) the result is the classic -g32 -e4 -B4."""
    assert manual_neutrals(560) == (32, 4, 4)


def test_grey_ramp_reference_lower_anchor_is_denser() -> None:
    """Halving the anchor must roughly double neutral density (eff_sheets doubles)."""
    g0, w0, b0 = manual_neutrals(560)
    g1, w1, b1 = manual_neutrals(560, ref_budget=280)
    assert g1 > g0 and w1 >= w0 and b1 >= b0


def test_grey_ramp_reference_higher_anchor_is_sparser() -> None:
    """Doubling the anchor must reduce neutral density (eff_sheets halves)."""
    g0, _, _ = manual_neutrals(560)
    g1, _, _ = manual_neutrals(560, ref_budget=1120)
    assert g1 < g0


def test_grey_ramp_reference_floors_hold_for_tiny_targets() -> None:
    """A tiny target must keep the minimum neutral set regardless of the anchor."""
    # 50 patches with a low anchor must still floor at grey>=8, white/black>=2.
    g, w, b = manual_neutrals(50, ref_budget=280)
    assert g == 8 and w == 2 and b == 2


def test_grey_ramp_reference_applies_to_guided() -> None:
    """The anchor must propagate through guided_neutrals too."""
    g0, _, _ = guided_neutrals("i1", "A4", 1, 4, 4, True)
    g1, _, _ = guided_neutrals("i1", "A4", 1, 4, 4, True, ref_budget=280)
    assert g1 > g0


def test_guided_anchor_returns_full_base_at_reference_layout() -> None:
    """i1Pro + A4 landscape + 1 page must produce the classic -g32 -e4 -B4.

    Regression guard: the tab used to read the white/black base from a
    settings key that "Save as defaults" round-tripped from the auto-computed
    result, collapsing -e/-B toward 2 across save cycles. The base is now
    fixed at GUIDED_NEUTRAL_BASE; pin the anchor outcome here.
    """
    assert guided_neutrals(
        "i1", "A4R", 1, GUIDED_NEUTRAL_BASE, GUIDED_NEUTRAL_BASE, True
    ) == (32, 4, 4)


def test_i1_defaults_from_preset_known_keys() -> None:
    """All three documented preset keys must return the printtarg values they encode."""
    assert i1_defaults_from_preset("m6_a1.0")   == (6,  1.0)
    assert i1_defaults_from_preset("m10_a1.0")  == (10, 1.0)
    assert i1_defaults_from_preset("m10_a0.95") == (10, 0.95)


def test_i1_defaults_from_preset_app_default() -> None:
    """The app-wide default key must resolve to m=10, a=0.95."""
    assert I1PRO_DEFAULT_PRESET_KEY == "m10_a0.95"
    assert i1_defaults_from_preset(I1PRO_DEFAULT_PRESET_KEY) == (10, 0.95)


def test_i1_defaults_from_preset_unknown_falls_back() -> None:
    """An unknown / corrupted preset key falls back to the recommended default."""
    assert i1_defaults_from_preset("bogus")    == (10, 0.95)
    assert i1_defaults_from_preset("")         == (10, 0.95)


def test_i1_defaults_only_uses_supported_values() -> None:
    """All preset outputs must be in SUPPORTED_MARGINS × SUPPORTED_PATCH_SCALES."""
    from data.patch_db import SUPPORTED_MARGINS, SUPPORTED_PATCH_SCALES
    for margin, scale in I1PRO_DEFAULT_PRESETS.values():
        assert margin in SUPPORTED_MARGINS
        assert any(abs(scale - s) <= 0.01 for s in SUPPORTED_PATCH_SCALES)


def test_instrument_default_margin_keys() -> None:
    """i1 defaults to 10mm (edge-drift headroom); p3/CM/SS use printtarg's 6mm."""
    assert INSTRUMENT_DEFAULT_MARGIN["i1"] == 10
    assert INSTRUMENT_DEFAULT_MARGIN["p3"] == 6
    assert INSTRUMENT_DEFAULT_MARGIN["CM"] == 6
    assert INSTRUMENT_DEFAULT_MARGIN["SS"] == 6


def test_printtarg_done_dedupes_case_insensitive_glob(tmp_path: Path) -> None:
    """Single chart.tif must not appear twice in the preview list on Windows.

    Regression guard for forum bug #148124's "Page 1/2 from one file" symptom:
    pathlib.Path.glob is case-insensitive on Windows, so the prior code's
    sorted([*glob('*.tif'), *glob('*.TIF'), *glob('*.tiff')]) returned the
    same file two or three times.
    """
    creator, work_dir = _make_creator(tmp_path)
    work_dir.mkdir(parents=True, exist_ok=True)
    # Pretend printtarg produced a single TIFF for a one-page chart
    arr = np.zeros((100, 100, 3), dtype=np.uint8)
    tifffile.imwrite(
        str(work_dir / "single.tif"), arr,
        resolution=(200, 200), resolutionunit="INCH",
    )

    captured: list[list[Path]] = []
    creator._pending_params = ChartParams(target_name="single", device_type="2")
    creator._printtarg_done(0, work_dir, lambda t: captured.append(t), "single")

    assert captured, "on_finish was never called"
    assert len(captured[0]) == 1, f"expected 1 TIFF, got {len(captured[0])}: {captured[0]}"


def test_load_ti1_writes_channels_sidecar(tmp_path: Path) -> None:
    creator, work_dir = _make_creator(tmp_path)
    work_dir.mkdir(parents=True)
    src_ti1 = work_dir / "imported.ti1"
    src_ti1.write_text("FAKE TI1", encoding="utf-8")

    finished: list[list[Path]] = []
    creator.load_ti1_and_generate_preview(
        src_ti1,
        # Guided forces the engine (#93); the printtarg preview path is Manual.
        ChartParams(target_name="imported", device_type="2", is_manual=True),
        on_line=lambda _: None,
        on_finish=lambda tiffs: finished.append(tiffs),
    )
    # New layout: sidecar lives in the current run's chart slot, under the
    # project-name stem ("chart_proj" from the _make_creator fixture).
    sidecar = work_dir / "runs" / "run1" / "chart_proj.channels.json"
    assert sidecar.exists(), (
        "load_ti1_and_generate_preview() must set _pending_params so the "
        "sidecar is written — regression guard for the second half of #15"
    )
    assert json.loads(sidecar.read_text(encoding="utf-8"))["ink_channels"] == ["r", "g", "b"]


# ---------------------------------------------------------------------------
# External preconditioning import
# ---------------------------------------------------------------------------
# When the user picks an external .icc (e.g. shipped with their printer)
# as the targen -c argument, chart_creator must copy it into the current
# run's preconditioning.icc slot, and (when refinement is on) copy the
# sibling .ti3 alongside as preconditioning.ti3.


class _ToggleSettings:
    """Settings stub that honours a single chromiq_refinement boolean."""

    def __init__(self, chromiq_refinement: bool) -> None:
        self._on = chromiq_refinement

    def get(self, key, default=None):
        if key == "chromiq_refinement":
            return self._on
        return default


def test_import_external_preconditioning_copies_icc(tmp_path: Path) -> None:
    """External -c .icc must be copied into runs/run1/preconditioning.icc."""
    work_dir = tmp_path / "proj"
    # Create the external .icc somewhere outside the project.
    ext = tmp_path / "external" / "vendor.icc"
    ext.parent.mkdir()
    ext.write_text("EXT_ICC", encoding="utf-8")

    creator = ChartCreator(
        _MockRunner(), _MockFileManager(work_dir), _ToggleSettings(chromiq_refinement=False),
    )
    proj = creator._file_mgr.project()
    run = proj.current_run()
    # Mirror production: tab_chart builds extra_targen_args with shlex.join so
    # Windows backslashes survive the shlex.split inside _import_external_preconditioning.
    new_args = creator._import_external_preconditioning(shlex.join(["-c", str(ext)]), run)

    assert run.preconditioning_icc.read_text(encoding="utf-8") == "EXT_ICC"
    assert str(run.preconditioning_icc) in new_args, "-c arg must be rewritten"


def test_import_external_preconditioning_with_refinement_copies_ti3(tmp_path: Path) -> None:
    """When chromiq_refinement is on, sibling .ti3 is also copied as preconditioning.ti3."""
    work_dir = tmp_path / "proj"
    ext_dir = tmp_path / "external"
    ext_dir.mkdir()
    (ext_dir / "vendor.icc").write_text("EXT_ICC", encoding="utf-8")
    (ext_dir / "vendor.ti3").write_text("EXT_TI3", encoding="utf-8")

    creator = ChartCreator(
        _MockRunner(), _MockFileManager(work_dir), _ToggleSettings(chromiq_refinement=True),
    )
    run = creator._file_mgr.project().current_run()
    creator._import_external_preconditioning(
        shlex.join(["-c", str(ext_dir / "vendor.icc")]), run,
    )

    assert run.preconditioning_icc.read_text(encoding="utf-8") == "EXT_ICC"
    assert run.preconditioning_ti3.read_text(encoding="utf-8") == "EXT_TI3"


def test_import_external_preconditioning_noop_for_local_pick(tmp_path: Path) -> None:
    """If -c already points at run.preconditioning_icc, nothing changes."""
    work_dir = tmp_path / "proj"
    creator = ChartCreator(
        _MockRunner(), _MockFileManager(work_dir), _ToggleSettings(chromiq_refinement=True),
    )
    run = creator._file_mgr.project().current_run()
    run.preconditioning_icc.write_text("ALREADY_LOCAL", encoding="utf-8")
    in_args = shlex.join(["-c", str(run.preconditioning_icc)])
    new_args = creator._import_external_preconditioning(in_args, run)
    assert new_args == in_args
    assert run.preconditioning_icc.read_text(encoding="utf-8") == "ALREADY_LOCAL"


def test_stamp_uses_chart_layout_line_for_ti1_origin(tmp_path: Path, monkeypatch) -> None:
    """#70: a chart built from an existing patch set (chart_layout_name set) must
    stamp "Chart layout <name> |" in place of the (never-run) targen command,
    while still stamping the printtarg command."""
    import workflow.tiff_metadata as tm
    creator, work_dir = _make_creator(tmp_path)
    run = creator._file_mgr.project().current_run()
    run.ensure_dir()
    (run.dir / f"{run.stem}.ti1").write_text("NUMBER_OF_SETS 484\n", encoding="utf-8")
    tiff = run.dir / f"{run.stem}_01.tif"
    arr = np.zeros((100, 100, 3), dtype=np.uint8)
    tifffile.imwrite(str(tiff), arr, resolution=(200, 200), resolutionunit="INCH")

    captured: list[list[str]] = []
    monkeypatch.setattr(tm, "stamp_chart_metadata",
                        lambda tiffs, lines: captured.append(list(lines)))

    creator._stamp_tiff_metadata(
        [tiff],
        # Guided forces the engine (#93); the printtarg stamp branch is Manual.
        ChartParams(target_name=run.stem, device_type="2", is_manual=True,
                    chart_layout_name="TC9.18", stamp_commands=True),
    )
    assert captured, "stamp_chart_metadata should have been called"
    lines = captured[0]
    assert any(l == "Chart layout TC9.18 |" for l in lines)
    assert not any(l.startswith("targen ") for l in lines)
    assert any(l.startswith("printtarg ") for l in lines)


def test_stamp_uses_targen_line_for_fresh_chart(tmp_path: Path, monkeypatch) -> None:
    """#70: a normal targen-built chart (no chart_layout_name) still stamps the
    targen command as before."""
    import workflow.tiff_metadata as tm
    creator, work_dir = _make_creator(tmp_path)
    run = creator._file_mgr.project().current_run()
    run.ensure_dir()
    (run.dir / f"{run.stem}.ti1").write_text("NUMBER_OF_SETS 484\n", encoding="utf-8")
    tiff = run.dir / f"{run.stem}_01.tif"
    arr = np.zeros((100, 100, 3), dtype=np.uint8)
    tifffile.imwrite(str(tiff), arr, resolution=(200, 200), resolutionunit="INCH")

    captured: list[list[str]] = []
    monkeypatch.setattr(tm, "stamp_chart_metadata",
                        lambda tiffs, lines: captured.append(list(lines)))

    creator._stamp_tiff_metadata(
        [tiff],
        ChartParams(target_name=run.stem, device_type="2", stamp_commands=True),
    )
    lines = captured[0]
    assert any(l.startswith("targen ") for l in lines)
    assert not any(l.startswith("Chart layout ") for l in lines)


# --- scanner .cht geometry capture at creation (#8) ----------------------------
import subprocess as _subprocess

_PRINTTARG = argyll_tool("printtarg")
_TARGEN = argyll_tool("targen")


@pytest.mark.skipif(_PRINTTARG is None or _TARGEN is None,
                    reason="ArgyllCMS not installed")
def test_capture_scanner_cht_stores_verified_printtarg_geometry(tmp_path: Path) -> None:
    """_capture_scanner_cht re-runs printtarg -s and, after checking the captured
    patch locs against the chart's own .ti2, stores the .cht page(s) in
    channels.json under an engine="printtarg" layout (#8)."""
    creator, _ = _make_creator(tmp_path)
    stem = creator._file_mgr.chart_stem(cal_target=False)
    run_dir = creator._file_mgr.cwd_for_chart(cal_target=False)

    # Real targen + printtarg so a genuine <stem>.ti1 + .ti2 exist to capture from.
    _subprocess.run([str(_TARGEN), "-d3", "-f40", stem], cwd=run_dir,
                    check=True, capture_output=True)
    _subprocess.run([str(_PRINTTARG), "-ii1", "-pA4", stem], cwd=run_dir,
                    check=True, capture_output=True)
    (run_dir / f"{stem}.channels.json").write_text(
        json.dumps({"ink_channels": ["R", "G", "B"]}), encoding="utf-8")

    creator._capture_scanner_cht(
        run_dir, stem, ChartParams(instrument="i1", paper="A4", is_manual=True))

    doc = json.loads((run_dir / f"{stem}.channels.json").read_text(encoding="utf-8"))
    assert doc["ink_channels"] == ["R", "G", "B"]        # existing data preserved
    layout = doc["layout"]
    assert layout["engine"] == "printtarg" and layout["cht_pages"]
    assert all("BOXES" in t for t in layout["cht_pages"])

    from workflow.ti3_analysis import parse_ti3
    ti2_locs = set(parse_ti3(run_dir / f"{stem}.ti2").sample_locs)
    assert set(layout["locs"]) == ti2_locs               # verified against the .ti2

    # The stored geometry is directly consumable by the scanner-target builder.
    from workflow import scanin_target as ST
    assert ST.has_scanner_geometry(run_dir / f"{stem}.channels.json")
