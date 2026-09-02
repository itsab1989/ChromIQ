"""Editor's live "Pages" spin fills patches up to that many full pages (#93).

When a chart is loaded in the layout editor and the engine is on, bumping the
Pages value asks the patch generator to top the chart up so the new page is
filled, then re-renders. Lowering Pages never deletes patches.
"""
import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

import ui.dialogs.ti2_relayout_dialog as M  # noqa: E402
from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.settings import AppSettings  # noqa: E402
from workflow import ti2_relayout as R  # noqa: E402

_TI2 = """CTI2

ORIGINATOR "test"
TARGET_INSTRUMENT "GretagMacbeth i1 Pro"
COLOR_REP "iRGB"
PAPER_SIZE "210.0x297.0"
APPROX_WHITE_POINT "95.1 100.0 108.8"

NUMBER_OF_FIELDS 8
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT

NUMBER_OF_SETS 3
BEGIN_DATA
1 "A1" 100.0 100.0 100.0 95.1 100.0 108.8
2 "A2" 0.0 0.0 0.0 0.0 0.0 0.0
3 "A3" 100.0 0.0 0.0 41.2 21.3 1.9
END_DATA
"""


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _settings():
    s = AppSettings()
    s._qs = QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      "chromiq-test", "editor-pages-fill")
    s._qs.clear()
    s.set("use_chromiq_layout_engine", True)
    return s


def _engine_editor(qapp, tmp_path, monkeypatch, cap=5):
    ed = M.Ti2RelayoutDialog(ArgyllRunner(_settings()), _settings())
    # Make the engine path active without a full chart load: a spec + a visible
    # engine panel is all _engine_active() needs.
    ti2 = tmp_path / "chart.ti2"
    ti2.write_text(_TI2, encoding="utf-8")
    ed._spec = R.ChartSpec.from_ti2(ti2)
    ed._engine_panel_grp.setVisible(True)
    # Seed the grid with a few patches.
    for rgb in ((100.0, 100.0, 100.0), (0.0, 0.0, 0.0), (50.0, 50.0, 50.0)):
        ed._grid.addItem(ed._grid_item(rgb))
    # Pin a small, deterministic per-page capacity so the fill is fast.
    monkeypatch.setattr(ed, "_engine_cap_per_page", lambda: cap)
    assert ed._engine_active()
    return ed


def test_increasing_pages_fills_to_full_pages(qapp, tmp_path, monkeypatch):
    ed = _engine_editor(qapp, tmp_path, monkeypatch, cap=5)
    ed._on_engine_pages_changed(2)
    assert ed._grid.count() == 10            # 2 pages × 5/page


def test_lowering_pages_keeps_patches(qapp, tmp_path, monkeypatch):
    ed = _engine_editor(qapp, tmp_path, monkeypatch, cap=5)
    ed._on_engine_pages_changed(3)
    assert ed._grid.count() == 15
    ed._on_engine_pages_changed(1)           # never deletes
    assert ed._grid.count() == 15


def test_pages_fill_is_wired_to_the_spin(qapp, tmp_path, monkeypatch):
    ed = _engine_editor(qapp, tmp_path, monkeypatch, cap=4)
    ed._engine_panel.pages.setValue(2)       # user edit fires the handler
    assert ed._grid.count() == 8


def test_fill_enforces_minimum_distance(qapp, tmp_path, monkeypatch):
    """Patches added by the page-fill honour the same hard minimum-distance rule
    as the generator (no two patches closer than _GEN_MIN_DIST in 0..100 RGB)."""
    import math
    import ui.dialogs.ti2_relayout_dialog as M
    ed = _engine_editor(qapp, tmp_path, monkeypatch, cap=40)
    ed._on_engine_pages_changed(3)             # add ~117 patches
    prog = ed._program_from_grid()
    md = M._GEN_MIN_DIST
    # brute-force nearest-neighbour check (small enough program)
    closest = min(
        math.dist(prog[i], prog[j])
        for i in range(len(prog)) for j in range(i + 1, len(prog)))
    assert closest >= md - 1e-6


def test_sync_does_not_refill(qapp, tmp_path, monkeypatch):
    ed = _engine_editor(qapp, tmp_path, monkeypatch, cap=5)
    ed._syncing_pages = True
    ed._on_engine_pages_changed(4)           # guarded → no change
    assert ed._grid.count() == 3
