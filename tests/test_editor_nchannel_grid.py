"""Editor grid + TI1 routing on a multi-ink chart (#72 Tier A).

Loads a CMYK .ti2 into the layout editor and checks the N-tuple plumbing that
Tier A wired up: grid swatches via the engine's display approximation, per-ink
tooltips, device tuples preserved through the grid, `_engine_grid_ti1` writing
the engine-format .ti1, and the RGB-only colour edits gated off. (The full
"non-RGB forces the engine panel" UX lands in Tier B.)
"""
import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings, Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

import ui.dialogs.ti2_relayout_dialog as M  # noqa: E402
from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.settings import AppSettings  # noqa: E402
from workflow.layout_engine import ti1_reader  # noqa: E402

_TI2_CMYK = """CTI2

ORIGINATOR "test"
TARGET_INSTRUMENT "GretagMacbeth i1 Pro"
COLOR_REP "CMYK"
PAPER_SIZE "210.0x297.0"
APPROX_WHITE_POINT "96.42 100.0 82.49"

NUMBER_OF_FIELDS 9
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC CMYK_C CMYK_M CMYK_Y CMYK_K XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT

NUMBER_OF_SETS 3
BEGIN_DATA
1 "A1" 0.0 0.0 0.0 0.0 96.4 100.0 82.5
2 "A2" 40.0 10.0 0.0 5.0 40.0 45.0 60.0
3 "A3" 0.0 0.0 0.0 100.0 1.0 1.0 1.0
END_DATA
"""


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _settings():
    s = AppSettings()
    s._qs = QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      "chromiq-test", "editor-nchannel")
    s._qs.clear()
    return s


@pytest.fixture
def editor_cmyk(qapp, monkeypatch, tmp_path):
    ed = M.Ti2RelayoutDialog(ArgyllRunner(_settings()), _settings())
    monkeypatch.setattr(ed, "_regenerate", lambda **k: None)
    ti2 = tmp_path / "chart.ti2"
    ti2.write_text(_TI2_CMYK, encoding="utf-8")
    assert ed._load_chart_from(ti2) is not False
    yield ed
    ed.deleteLater()


def test_grid_holds_device_tuples_and_ink_tooltips(editor_cmyk):
    ed = editor_cmyk
    assert ed._grid.count() == 3
    prog = ed._program_from_grid()
    assert prog[1] == (40.0, 10.0, 0.0, 5.0)          # 4-tuples, not RGB
    tip = ed._grid.item(1).toolTip()
    assert "C 40" in tip and "M 10" in tip and "K 5" in tip
    # Paper-white swatch displays as white, K-only as black (display approx).
    assert ed._display_rgb((0.0, 0.0, 0.0, 0.0)) == pytest.approx((100, 100, 100))
    assert ed._display_rgb((0.0, 0.0, 0.0, 100.0)) == pytest.approx((0, 0, 0))


def test_engine_grid_ti1_writes_engine_format(editor_cmyk, tmp_path):
    out = editor_cmyk._engine_grid_ti1(tmp_path / "grid.ti1")
    tgt = ti1_reader.read_ti1(out)
    assert tgt.color_rep == "CMYK"
    assert tgt.n_channels == 4
    assert [dev for dev, _ in tgt.patches] == [
        (0.0, 0.0, 0.0, 0.0), (40.0, 10.0, 0.0, 5.0), (0.0, 0.0, 0.0, 100.0)]
    # XYZ preserved from the .ti2, not re-estimated.
    assert tgt.patches[1][1] == pytest.approx((40.0, 45.0, 60.0), abs=1e-3)


def test_rgb_colour_edits_are_gated(editor_cmyk):
    ed = editor_cmyk
    ed._grid.item(0).setSelected(True)
    before = ed._program_from_grid()
    ed._set_patch_colour()                             # must refuse, not corrupt
    ed._transform_selection(1.1)
    assert ed._program_from_grid() == before
    assert "RGB charts" in ed._status.text()


def test_write_colour_values_file_skips_non_rgb(editor_cmyk, tmp_path):
    p = tmp_path / "c-colours.txt"
    editor_cmyk._write_colour_values_file(p)           # no crash, no file
    assert not p.exists()


# --- decision 0: non-RGB charts are engine-only in the editor (#72 Tier B) ----


def test_cmyk_chart_forces_engine_path(editor_cmyk):
    ed = editor_cmyk
    assert ed._engine_active() is True                 # regardless of toggles
    assert ed._loaded_printtarg_chart is False
    assert ed._engine_recipe is not None               # seeded from the spec
    assert ed._engine_recipe.instrument == "i1"
    assert ed._engine_recipe.paper == "A4"


# Captured at import time — conftest's autouse fixture stubs the class-level
# _regenerate to a no-op for the suite; this test exercises the REAL one
# (safe here: the CMYK branch never builds the printtarg worker).
_REAL_REGENERATE = M.Ti2RelayoutDialog._regenerate


def test_regenerate_routes_cmyk_to_engine_preview(qapp, monkeypatch, tmp_path):
    ed = M.Ti2RelayoutDialog(ArgyllRunner(_settings()), _settings())
    calls = []
    monkeypatch.setattr(ed, "_do_engine_preview", lambda: calls.append(1))
    ti2 = tmp_path / "chart.ti2"
    ti2.write_text(_TI2_CMYK, encoding="utf-8")
    assert ed._load_chart_from(ti2)
    assert ed._spec is not None and ed._spec.color_rep == "CMYK"
    assert ed._grid.count() == 3
    calls.clear()
    _REAL_REGENERATE(ed, save_to=None)                 # real method, no worker
    assert calls == [1]
    assert ed._worker is None or not ed._worker.isRunning()
    ed.deleteLater()


def test_add_patches_gated_on_cmyk(editor_cmyk, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("Add dialog must not open for a multi-ink chart")
    monkeypatch.setattr(M, "_AddPatchesDialog", boom)
    editor_cmyk._add_patch()
    assert "RGB-only" in editor_cmyk._status.text()


def test_save_as_writes_engine_cmyk_deliverable(editor_cmyk, tmp_path):
    # Full integration: Save As on a CMYK chart renders through the engine —
    # engine .ti2 (COLOR_REP CMYK), channels.json with the recipe, and the
    # device-native separated TIFF from Tier D.
    target = tmp_path / "cmyk-save"
    msg = editor_cmyk._write_chart_into(target, "cmyktest")
    assert "engine chart" in msg
    ti2 = target / "cmyktest.ti2"
    assert 'COLOR_REP "CMYK"' in ti2.read_text(encoding="utf-8")
    import json
    sidecar = json.loads((target / "cmyktest.channels.json").read_text(encoding="utf-8"))
    assert sidecar["layout"]["engine"] == "chromiq"
    assert sidecar["layout"]["color_rep"] == "CMYK"
    tiffs = sorted(target.glob("cmyktest*.tif"))
    assert tiffs, "engine wrote no pages"
    import tifffile
    with tifffile.TiffFile(tiffs[0]) as tf:
        page = tf.pages[0]
        assert page.samplesperpixel == 4               # separated CMYK raster
    # i1Profiler pair rides along; the RGB-only colour list is skipped.
    assert (target / "cmyktest-i1profiler.pxf").exists()
    assert not (target / "cmyktest-colours.txt").exists()
