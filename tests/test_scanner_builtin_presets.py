"""Scanner built-in presets (#100) — Knut's flatbed-scanner printer-profiling
charts as engine-built built-ins in their own "Scanner" preset group.

Each bundles a fixed .ti1 with a full ChromIQ layout-engine recipe; selecting
one turns the engine on, seeds the layout panel from the recipe, and builds
from the bundled patch set. Both papers carry a 1/2/3-page variant (#118):
3430p / 6860p / 10290p on A4 and 3250p / 6500p / 9750p on Letter.
"""
import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.resource_path import resource_path  # noqa: E402
from ui.tabs.tab_chart import (  # noqa: E402
    BUILTIN_PRESET_GROUPS, BUILTIN_PRESET_KEYS, BUILTIN_PRESET_LABELS,
    KNUT_PRESETS, KNUT_PRESETS_BY_KEY, TabChart,
)

_SCANNER = [p for p in KNUT_PRESETS if p.group == "Scanner"]
_A4_KEY = "__chromiq_knut_scanner_a4_3430p_1page_landscape__"
_LETTER_KEY = "__chromiq_knut_scanner_letter_3250p_1page_landscape__"
_A4_2P_KEY = "__chromiq_knut_scanner_a4_6860p_2pages_landscape__"
_LETTER_2P_KEY = "__chromiq_knut_scanner_letter_6500p_2pages_landscape__"
_A4_3P_KEY = "__chromiq_knut_scanner_a4_10290p_3pages_landscape__"
_LETTER_3P_KEY = "__chromiq_knut_scanner_letter_9750p_3pages_landscape__"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _make_tab(qapp, tmp_path):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    tab._switch_mode("manual")
    return tab, s


# ---------------------------------------------------------------------------
# Registry + assets
# ---------------------------------------------------------------------------

def test_scanner_family_registered():
    assert {p.key for p in _SCANNER} == {_A4_KEY, _A4_2P_KEY, _A4_3P_KEY,
                                          _LETTER_KEY, _LETTER_2P_KEY,
                                          _LETTER_3P_KEY}
    assert all(p.layout_recipe is not None for p in _SCANNER)
    assert all(p.key in BUILTIN_PRESET_KEYS for p in _SCANNER)
    assert all(p.combo_label in BUILTIN_PRESET_LABELS for p in _SCANNER)
    # Own "Scanner" group in the dropdown/overlay registry: both papers carry a
    # 1/2/3-page variant, A4 before Letter, page count ascending (#118).
    groups = dict(BUILTIN_PRESET_GROUPS)
    assert "Scanner" in groups
    assert [k for (_c, _o, k) in groups["Scanner"]] == [
        _A4_KEY, _A4_2P_KEY, _A4_3P_KEY,
        _LETTER_KEY, _LETTER_2P_KEY, _LETTER_3P_KEY]


def test_scanner_assets_match_declared_counts():
    for p in _SCANNER:
        ti1 = resource_path(p.ti1_asset)
        assert ti1.is_file(), f"missing {p.ti1_asset}"
        txt = ti1.read_text(encoding="latin-1", errors="ignore")
        m = re.search(r"NUMBER_OF_SETS\s+(\d+)", txt)
        assert m and int(m.group(1)) == p.patches
        # printtarg needs all three tables of a targen .ti1 (see the
        # i1Profiler-import lesson) — guard the bundled files' completeness.
        assert txt.count("NUMBER_OF_SETS") == 3


def test_scanner_sidecar_recipes_use_two_nearneutral_rings():
    """#118: the two 1-page charts shipped with a single near-neutral ring.
    Every scanner chart now carries two, so guard all six sidecars."""
    import json
    for p in _SCANNER:
        rec = json.loads((resource_path(p.ti1_asset).parent / "recipe.json")
                         .read_text(encoding="utf-8"))
        assert rec["sp"]["nearneutral_rings"] == 2, p.key
        assert rec["sp"]["fill_to"] == p.patches, p.key


@pytest.mark.slow
def test_scanner_recipes_reproduce_declared_page_count():
    """The bundled recipe + .ti1 must lay out to exactly the advertised page
    count — a threshold/margin regression in the engine would silently
    spill."""
    from workflow.layout_engine import chart as le_chart
    from workflow.layout_engine.presets import LayoutRecipe
    import tempfile
    from pathlib import Path
    for p in _SCANNER:
        rec = LayoutRecipe.from_dict(p.layout_recipe)
        assert rec.instrument == "SS"
        assert rec.randomize is False       # keep Knut's printed layout
        with tempfile.TemporaryDirectory() as tmp:
            res = le_chart.build_chart(str(resource_path(p.ti1_asset)),
                                       Path(tmp) / "chart", project="t",
                                       **rec.build_kwargs())
            assert len(res.tiff_paths) == p.pages


# ---------------------------------------------------------------------------
# Selection behaviour
# ---------------------------------------------------------------------------

def test_seed_scanner_preset_seeds_engine_panel(qapp, tmp_path):
    tab, s = _make_tab(qapp, tmp_path)
    s.set("use_chromiq_layout_engine", True)   # _on_preset_selected does this
    tab._seed_knut_preset(_A4_KEY)
    rec = tab._manual_layout_panel.get_recipe()
    assert rec.instrument == "SS"
    assert rec.paper == "A4R"
    assert rec.layout_mode == "area_first"
    assert rec.area_min_patch_mm == 4.0
    assert tab._manual_layout_panel.get_pages() == 1
    # Descriptive targen values reflect the bundled set.
    letter = KNUT_PRESETS_BY_KEY[_LETTER_KEY]
    tab._seed_knut_preset(_LETTER_KEY)
    assert tab._manual_layout_panel.get_recipe().paper == "LetterR"
    assert letter.patches == 3250


def test_selecting_scanner_preset_turns_engine_on(qapp, tmp_path, monkeypatch):
    """The real dropdown handler flips the engine to match the preset kind: ON
    for the Scanner family (and seeds the layout panel + builds from the
    bundled .ti1), OFF again for a printtarg-era built-in (#100)."""
    tab, s = _make_tab(qapp, tmp_path)
    built = []
    monkeypatch.setattr(tab, "_generate_from_ti1",
                        lambda p: built.append(p))     # stub the process edge
    idx = tab._preset_combo.findData(_A4_KEY)
    assert idx > 0
    tab._preset_combo.setCurrentIndex(idx)             # fires _on_preset_selected
    assert bool(s.get("use_chromiq_layout_engine", False)) is True
    assert tab._manual_layout_panel.get_recipe().instrument == "SS"
    assert built and built[-1].name == "chart.ti1"     # the bundled patch set


def test_selecting_a_printtarg_builtin_turns_the_engine_off(qapp, tmp_path,
                                                            monkeypatch):
    """The other half of the pair, SPLIT OUT so neither can hide the other.

    It used to live at the end of the "turns engine on" test, whose subject was
    a Full-layout-setup preset. Knut withdrew the two printtarg ones in
    4.1.3-beta.13, and asking `KNUT_PRESETS` for a replacement found none — so
    the test skipped, taking the engine-ON half's visible result with it.

    TC9.18 by Pharmacist is the real subject: it IS in the preset dropdown and
    is NOT in `KNUT_PRESETS_BY_KEY`, and that `None` lookup is precisely what
    switches the engine off.
    """
    tab, s = _make_tab(qapp, tmp_path)
    monkeypatch.setattr(tab, "_generate_from_ti1", lambda p: None)
    s.set("use_chromiq_layout_engine", True)

    idx = tab._preset_combo.findData("__chromiq_tc918eg_a4_builtin__")
    assert idx > 0, "the TC9.18 built-in is not in the dropdown"
    tab._preset_combo.setCurrentIndex(idx)

    assert bool(s.get("use_chromiq_layout_engine", False)) is False, (
        "a printtarg-path built-in left the ChromIQ layout engine switched on")


def test_scanner_tooltip_mentions_scan_workflow(qapp, tmp_path):
    tab, _s = _make_tab(qapp, tmp_path)
    tip = tab._knut_tooltip(_A4_KEY)
    assert "scan" in tip.lower()
    assert "3430" in tip
    assert "printtarg" not in tip            # engine preset, no printtarg line


def test_the_parking_mechanism_is_still_wired(qapp, tmp_path):
    """Nothing is parked today, and the machinery to park something must survive
    that.

    The i1Pro/A4 "TC9.24 by Pharmacist" chart was the one entry here — its
    bundled page image disagreed with its own .ti2 reference — and Knut asked
    for it to be removed outright rather than parked any longer (#164,
    2026-08-23). Deleting the LAST parked preset must not quietly take the
    parking rule with it: a built-in whose bundle turns out to be broken is a
    thing that happens, and the greying is how it is taken out of service
    without unpicking its wiring.
    """
    import inspect

    from ui.tabs.tab_chart import (DISABLED_BUILTIN_PRESET_KEYS, TabChart,
                                   TC924_CM_A3_PRESET_KEY)
    assert DISABLED_BUILTIN_PRESET_KEYS == frozenset()
    src = inspect.getsource(TabChart._add_builtin_preset_item)
    assert "temporarily unavailable" in src
    assert "disabled" in src
    assert "DISABLED_BUILTIN_PRESET_KEYS" in inspect.getsource(
        TabChart._populate_preset_combo)

    tab, _s = _make_tab(qapp, tmp_path)
    try:
        combo = tab._preset_combo
        # …and the ColorMunki A3 TC9.24, a different chart entirely, is
        # untouched by that removal.
        j = combo.findData(TC924_CM_A3_PRESET_KEY)
        assert j > 0 and combo.model().item(j).isEnabled()
        assert all("temporarily unavailable" not in combo.itemText(i).lower()
                   for i in range(combo.count()))
    finally:
        tab.deleteLater()


def test_suggested_name_reads_engine_paper(qapp, tmp_path):
    """#108 (Knut): with the layout engine ON, the suggested chart name must
    take instrument/paper/orientation from the ENGINE panel — the printtarg
    widgets can hold stale values (A4 Landscape suggested "A4…Portrait";
    Letter Landscape even suggested "A4…Portrait")."""
    tab, _s = _make_tab(qapp, tmp_path)
    try:
        tab._manual_engine_check.setChecked(True)
        panel = tab._manual_layout_panel
        panel.instr.setCurrentIndex(panel.instr.findData("SS"))
        panel.paper.setCurrentIndex(panel.paper.findData("LetterR"))
        name = tab._suggest_target_name()
        assert name.startswith("SpectroScan-Letter")
        assert "Landscape" in name
        assert "A4" not in name and "Portrait" not in name
    finally:
        tab.deleteLater()
