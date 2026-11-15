"""Review 2026-11-15, m6: an i1Profiler Measure Chart measurement through the
VERIFICATION door of the Measure tab, end to end (the real
`_on_import_measurement`, the real conversion of the picked ``.cmxf``, the
real filing into a dated verification), with the i1iO Beta on."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication  # noqa: E402

from tests import i1p_forward as F  # noqa: E402
from tests.test_import_measurement_module import (_capture_refusals,  # noqa: E402
                                                  _silence_done_dialog, _tab,
                                                  _verify_env)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def beta_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    yield
    support._latched = before


def _i1io_verification(tmp_path):
    """A verification-ready run whose verify chart is an i1iO chart with
    its side file, built by ChromIQ's own engine."""
    s, fm, ctl, run = _verify_env(tmp_path)
    rng = np.random.default_rng(6)
    rgbs = [tuple(rng.uniform(0, 100, 3)) for _ in range(96)]
    src = F.build_chart(tmp_path / "built", rgbs, seed=7)
    dst = run.verify_chart_ti2
    stem = dst.name[:-4]
    shutil.copy2(src, dst)
    shutil.copy2(Path(str(src)[:-4] + ".i1io.json"),
                 dst.parent / (stem + ".i1io.json"))
    return s, fm, ctl, run, F.load_sheet(dst)


def test_a_measure_chart_file_is_filed_into_a_dated_verification(
        tmp_path, qapp, beta_on, monkeypatch):
    from workflow.ti3_analysis import parse_ti3
    s, fm, ctl, run, sh = _i1io_verification(tmp_path)
    tab = _tab(s, fm, ctl)
    done = _silence_done_dialog(tab, monkeypatch)
    refused = _capture_refusals(tab, monkeypatch)
    try:
        tab._switch_mode("import")
        tab._import_path = F.measure(sh, tmp_path / "scan.cmxf")
        tab._on_import_measurement()
        log = tab._log.toPlainText()
    finally:
        tab.deleteLater()
    assert not refused, refused
    assert len(done) == 1, log[-800:]
    dst = done[0][1]
    assert dst.parent.parent == run.verifications_dir
    text = dst.read_text(encoding="utf-8")
    assert "CHROMIQ_PAIRED_BY_I1IO_GRID" in text
    assert "CHROMIQ_VERIFICATION" in text
    assert "i1Profiler \"Measure Chart\" measurement" in log
    # every row on its own patch: the chart's own device values by id
    filed = parse_ti3(dst)
    assert len(filed.sample_ids) == sh.rows * sh.cols
    for sid, rgb in zip(filed.sample_ids, filed.rgb):
        assert np.allclose(rgb, sh.rgb_of[int(str(sid).strip('"'))],
                           atol=1e-3)


def test_a_turned_sheet_is_refused_at_the_verification_door(
        tmp_path, qapp, beta_on, monkeypatch):
    s, fm, ctl, run, sh = _i1io_verification(tmp_path)
    tab = _tab(s, fm, ctl)
    done = _silence_done_dialog(tab, monkeypatch)
    refused = _capture_refusals(tab, monkeypatch)
    try:
        tab._switch_mode("import")
        tab._import_path = F.measure(sh, tmp_path / "turned.cmxf",
                                     F.mistakes(sh)["half-turn"])
        tab._on_import_measurement()
    finally:
        tab.deleteLater()
    assert not done
    assert len(refused) == 1 and "turned half round" in \
        refused[0][1]["reason"], refused
    # review m3: its own window, whose title does not say "another chart"
    assert refused[0][0] == "M-IMPORT-I1IO-REFUSED"
    assert not list(run.verifications_dir.rglob("*.ti3"))
