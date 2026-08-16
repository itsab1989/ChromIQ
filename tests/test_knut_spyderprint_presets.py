"""Knut's TC9.18 + Spyderprint-greys built-in presets.

Each of the 17 presets shares ONE bundled 1168-patch .ti1 and differs only in
its printtarg layout. Selecting one seeds the Manual printtarg panel and builds
the chart from the .ti1 (via _preset_ti1_path). These tests pin that the seeded
panel reproduces Knut's commands:

  i1Pro:      printtarg -P -ii1  -T200 -p<paper> -M8 -R<seed> -a<scale> -A0.6  (no -L)
  ColorMunki: printtarg -P -iCM -h -T200 -p<paper> -a<scale> -M6

ChromIQ emits -m<m> -M<m> together (functionally == Knut's lone -M) and keeps
the left clip border (no -L) on the i1 charts.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.file_manager import FileManager  # noqa: E402
from core.resource_path import resource_path  # noqa: E402
from core.settings import AppSettings  # noqa: E402
from ui.tabs.tab_chart import (  # noqa: E402
    KNUT_PRESETS,
    KNUT_PRESETS_BY_KEY,
    KNUT_PRESET_KEYS,
    KNUT_TI1_ASSET,
    BUILTIN_PRESET_GROUPS,
    BUILTIN_PRESET_KEYS,
    BUILTIN_PRESET_LABELS,
    TabChart,
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def settings(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "chromiq_test.ini"), QSettings.Format.IniFormat)
    # These tests exercise the printtarg path explicitly — since 4.0.0
    # the ChromIQ layout engine is the Manual default (schema 18), so
    # the mode under test is pinned rather than inherited.
    s.set("use_chromiq_layout_engine", False)
    # Overriding QSettings alone is not enough: `custom_output_path` then falls
    # back to its default of "", which means the REAL ~/ChromIQ. Seeding a
    # preset asks the FileManager where it is working, that invents a
    # "Printer_Paper_Type_Instr_<timestamp>" name and creates the folder — so
    # every gate run left a project behind on the developer's machine
    # (Basti, 2026-08-01, after deleting 77 of them by hand).
    s.set("custom_output_path", str(tmp_path / "out"))
    return s


def _make_tab(qapp, settings) -> TabChart:
    t = TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    t._switch_mode("manual")
    return t


def _printtarg_args(tab) -> list[str]:
    """printtarg argv the current panel would run, minus the trailing stem."""
    params = tab._collect_manual()
    return tab._creator._build_printtarg_args(params)[:-1]


def _fmt_scale(v: float) -> str:
    return f"{v:.2f}" if round(v, 2) == round(v, 3) else f"{v:.3f}"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def test_registry_shape():
    # The five i1Pro "Full layout setup" presets (#63; the 17 shared-.ti1
    # "TC9.18+Spyderprint Grays" ones went in #89, and the ten ColorMunki ones
    # were replaced by Knut's 2026-08-16 ColorMunki family — see
    # test_colormunki_builtin_presets.py), his 45 ColorMunki charts, the six
    # engine-built Scanner charts (#100, #108, #118), and the six Red River
    # Paper vendor variants (one shared 2052-patch .ti1: i1Pro A4/Letter, and
    # ColorMunki A4/Letter in both a compact 8-page and a ruler-size 10-page cut).
    assert len(KNUT_PRESETS) == 62
    assert len(KNUT_PRESET_KEYS) == 62  # all keys unique
    assert sum(1 for p in KNUT_PRESETS if p.slug.startswith("fls_")) == 5
    assert sum(1 for p in KNUT_PRESETS if p.slug.startswith("cm_")) == 45
    assert sum(1 for p in KNUT_PRESETS if p.slug.startswith("scanner_")) == 6
    assert sum(1 for p in KNUT_PRESETS if p.slug.startswith("redriver_")) == 6
    assert KNUT_PRESET_KEYS <= BUILTIN_PRESET_KEYS
    assert all(p.combo_label in BUILTIN_PRESET_LABELS for p in KNUT_PRESETS)
    # every preset is reachable from a dropdown/overlay group
    grouped = {k for _i, entries in BUILTIN_PRESET_GROUPS for (_c, _o, k) in entries}
    assert KNUT_PRESET_KEYS <= grouped


def test_fulllayout_ti1_assets_present():
    # Every Full-layout-setup chart (#63) ships its own .ti1 + recipe.json —
    # guard the bundled files.
    fls = [p for p in KNUT_PRESETS if p.slug.startswith("fls_")]
    assert len(fls) == 5
    for p in fls:
        assert resource_path(p.ti1_asset).is_file(), f"missing {p.ti1_asset}"
        recipe = resource_path(p.ti1_asset).parent / "recipe.json"
        assert recipe.is_file(), f"missing {recipe}"


def test_keys_are_stable_sentinels():
    # The slug, not the display name, is the identity — guard the format so a
    # rename can't silently change a key and orphan saved selections.
    for p in KNUT_PRESETS:
        assert p.key == f"__chromiq_knut_{p.slug}__"


# ---------------------------------------------------------------------------
# Seeded printtarg command per preset
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", sorted(KNUT_PRESET_KEYS))
def test_seeded_command_matches_recipe(qapp, settings, key):
    p = KNUT_PRESETS_BY_KEY[key]
    if p.layout_recipe is not None or p.engine:
        pytest.skip("engine-built preset — printtarg not used")
    tab = _make_tab(qapp, settings)
    tab._seed_knut_preset(key)
    args = _printtarg_args(tab)

    # Field-driven so it covers both the TC9.18 family and the Full-layout-setup one.
    triple = p.triple_density and p.instrument == "CM"
    if triple:
        # Triple density lays out with the i1Pro geometry and forces -L; it's
        # mutually exclusive with double density (-h).
        assert "-ii1" in args
        assert "-L" in args
        assert "-h" not in args
    else:
        assert f"-i{p.instrument}" in args
        assert ("-L" in args) == p.suppress_left_clip     # left clip border
        assert ("-h" in args) == p.double_density         # double density
    assert f"-p{p.paper}" in args
    if p.tiff_16bit:
        assert "-T200" in args and "-t200" not in args   # 16-bit raster at 200 dpi
    else:
        assert "-t200" in args and "-T200" not in args    # 8-bit raster at 200 dpi
    assert ("-P" in args) == p.no_strip_limit             # don't limit strip length
    assert f"-M{p.margin}" in args
    if abs(p.patch_scale - 1.0) > 0.01:                   # -a only when non-default
        assert f"-a{_fmt_scale(p.patch_scale)}" in args
    assert ("-r" in args) == p.no_randomise   # preserve order honours the preset
    # -m is emitted alongside -M only when the margin differs from the default 6.
    if p.margin != 6:
        assert f"-m{p.margin}" in args
    else:
        assert f"-m{p.margin}" not in args
    joined = " ".join(args)
    if p.spacer_scale is not None:
        assert f"-A {p.spacer_scale:.2f}" in joined
    else:
        assert not any(a.startswith("-A") for a in args)
    if p.seed is not None:
        assert f"-R {p.seed}" in joined
    else:
        assert not any(a.startswith("-R") for a in args)


def test_fulllayout_preset_uses_its_own_ti1_and_count(qapp, settings):
    # #58: a Full-layout-setup preset bundles its OWN .ti1 (not the shared TC9.18
    # set), and its reuse info box reports that preset's patch count, not 1168.
    key = "__chromiq_knut_fls_i1pro_a4_1200p_3pages_portrait__"
    p = KNUT_PRESETS_BY_KEY[key]
    assert p.ti1_asset != KNUT_TI1_ASSET
    assert p.patches == 1200
    tab = _make_tab(qapp, settings)
    tab._seed_knut_preset(key)
    tab._knut_active = True
    tab._knut_active_key = key
    tab._knut_targen_sig = tab._targen_signature()
    tab._refresh_manual_command_preview()
    info = tab._manual_info_lbl.text()
    assert "1200" in info and "1168" not in info
    assert "Full layout setup" in tab._knut_tooltip(key)


# A surviving Full-layout-setup preset used across the generic tests below.
_FLS_KEY = "__chromiq_knut_fls_i1pro_a4_924p_2pages_portrait__"


def test_targen_signature_ignores_printtarg_changes(qapp, settings):
    # While a preset is active, changing only printtarg settings must keep the
    # bundled .ti1 as the source (signature unchanged); a targen change opts into
    # a fresh targen chart (signature differs).
    tab = _make_tab(qapp, settings)
    tab._seed_knut_preset(_FLS_KEY)
    sig0 = tab._targen_signature()
    tab._set_manual_value("printtarg", "-a", 1.05)      # printtarg-only edit
    assert tab._targen_signature() == sig0
    tab._set_manual_value("targen", "-f", 500)          # targen edit
    assert tab._targen_signature() != sig0


def test_info_box_announces_ti1_reuse(qapp, settings):
    tab = _make_tab(qapp, settings)
    tab._seed_knut_preset(_FLS_KEY)
    tab._knut_active = True
    tab._knut_active_key = _FLS_KEY
    tab._knut_targen_sig = tab._targen_signature()
    tab._refresh_manual_command_preview()
    txt = tab._manual_info_lbl.text()
    assert "targen skipped" in txt and "924" in txt   # this preset's own count
    # A targen change flips the note back to the normal targen+printtarg view.
    tab._set_manual_value("targen", "-f", 500)
    tab._refresh_manual_command_preview()
    assert "targen skipped" not in tab._manual_info_lbl.text()


def test_leaving_preset_reverts_overrides(qapp, settings):
    # Leaving a preset (for Default / a user preset) must not leak its forced
    # printtarg flags into the next chart — _reset_knut_overrides handles it.
    tab = _make_tab(qapp, settings)
    tab._seed_knut_preset(_FLS_KEY)            # forces -P -h -a0.93
    tab._knut_active = True
    tab._reset_knut_overrides()
    args = _printtarg_args(tab)
    assert "-P" not in args
    assert "-a0.93" not in args        # back to the default scale (1.0 → no -a)
