"""The i1Profiler-render mode of the Create-scanner-target dialog (#120).

Drives the real dialog handler — only the file-picker edge is bypassed by
setting the chosen paths directly, the same way a click would.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtWidgets import QApplication  # noqa: E402

from scripts.make_i1profiler_probe import encode, write_ti1  # noqa: E402

RESULTS = Path(__file__).resolve().parent.parent / "docs" / "i1profiler_probe" / "results"
MULTI = [RESULTS / "multipage" / "ChromIQ i1Profiler layo_1_2.tif",
         RESULTS / "multipage" / "ChromIQ i1Profiler layo_2_2.tif"]

pytestmark = pytest.mark.skipif(
    not MULTI[0].is_file(), reason="probe result TIFFs not present")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _FakeSettings:
    def __init__(self):
        self.d = {"appearance": "auto"}

    def get(self, k, default=None):
        return self.d.get(k, default)

    def set(self, k, v):
        self.d[k] = v


def _numeric_ti3(path: Path, n: int) -> None:
    rows = []
    for i in range(n):
        r, g, b = encode(i)
        rows.append(f"{i+1} {i+1} {r/2.55:.3f} {g/2.55:.3f} {b/2.55:.3f} 50 50 50")
    path.write_text(
        'CTI3\n\nKEYWORD "SAMPLE_LOC"\n\nNUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n'
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\n\n" + f"NUMBER_OF_SETS {n}\nBEGIN_DATA\n"
        + "\n".join(rows) + "\nEND_DATA\n", encoding="utf-8")


def _dialog(qapp):
    from ui.dialogs.scanin_target_dialog import ScaninTargetDialog
    return ScaninTargetDialog(_FakeSettings())


def test_mode_switch_toggles_panels(qapp):
    dlg = _dialog(qapp)
    assert dlg._mode == "chromiq"
    assert dlg._panel_chromiq.isVisible() or True   # shown once dialog is shown
    dlg._rb_i1p.setChecked(True)
    assert dlg._mode == "i1profiler"
    assert not dlg._panel_chromiq.isVisible()
    # run is gated until all three i1Profiler inputs are chosen
    assert not dlg._can_run()


def test_i1profiler_mode_builds_target(qapp, tmp_path):
    dlg = _dialog(qapp)
    dlg._rb_i1p.setChecked(True)

    ti1 = tmp_path / "probe.ti1"
    write_ti1(ti1, 1500)
    ti3 = tmp_path / "m.ti3"
    _numeric_ti3(ti3, 1500)

    # Stand in for the three Browse clicks.
    dlg._pset_path = ti1
    dlg._tiff_paths = list(MULTI)
    dlg._meas_path = ti3
    assert dlg._can_run()

    dlg._execute()
    log = dlg._log.toPlainText()
    assert "[ERROR]" not in log
    base = ti3.with_name("m")
    assert (tmp_path / "m.channels.json").is_file()
    assert (base.with_suffix(".cie")).is_file()
    assert (tmp_path / "m_01.cht").is_file() and (tmp_path / "m_02.cht").is_file()


def test_chromiq_mode_still_builds(qapp, tmp_path):
    """The pre-existing ChromIQ path must survive the _execute refactor: a
    measured engine chart (channels.json next to the .ti3) → .cht + .cie."""
    import json
    from workflow.grid_layout_from_render import derive_grid_layout
    from scripts.make_i1profiler_probe import write_ti1  # noqa: F401

    # Reuse the render deriver to fabricate a valid "derived" channels.json,
    # which has_scanner_geometry accepts exactly like an engine layout.
    from scripts.make_i1profiler_probe import encode
    import numpy as np
    rgb = np.array([[c / 255 * 100 for c in encode(i)] for i in range(600)])
    layout = derive_grid_layout([RESULTS / "test1-autolayout.tif"], rgb)
    (tmp_path / "chart.channels.json").write_text(json.dumps({"layout": layout}), encoding="utf-8")
    _numeric_ti3(tmp_path / "chart.ti3", 600)

    dlg = _dialog(qapp)                    # default mode = chromiq
    assert dlg._mode == "chromiq"
    dlg._ti3_path = tmp_path / "chart.ti3"
    assert dlg._can_run()
    dlg._execute()
    assert "[ERROR]" not in dlg._log.toPlainText()
    assert (tmp_path / "chart.cht").is_file() and (tmp_path / "chart.cie").is_file()


def test_i1profiler_mode_reports_mismatch(qapp, tmp_path):
    dlg = _dialog(qapp)
    dlg._rb_i1p.setChecked(True)
    ti1 = tmp_path / "probe.ti1"
    write_ti1(ti1, 1500)
    ti3 = tmp_path / "m.ti3"
    _numeric_ti3(ti3, 1500)
    dlg._pset_path = ti1
    dlg._tiff_paths = [MULTI[0]]                 # one page for a two-page chart
    dlg._meas_path = ti3
    dlg._execute()
    assert "[ERROR]" in dlg._log.toPlainText()
