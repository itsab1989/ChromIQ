"""4.3.53 (the tester Nelson, 20 Nov 2026): "with Auto checked the scan is unidirectional only".

Until 4.3.53 the Auto toggle of "Strip recognition" decided from the chart's TARGET_INSTRUMENT
only. A chart naming no instrument (or another one) read with an i1 Pro then got no -b, and on a
fixed-order chart ArgyllCMS accepted the strips in one direction only. Now Auto decides, for
such a chart, from the instrument THIS measurement is made with, exactly as for a chart naming
it; an explicit choice with Auto off is never changed. The whole table of what the helper is
told is pinned here: (chart names an i1 Pro / another instrument / none) x (Auto on / Auto off
with each choice) x (dual scan on / off), plus the measuring instrument known or not.
"""
from __future__ import annotations

import logging
import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.settings import DEFAULTS  # noqa: E402
from ui.tabs.tab_measure import TabMeasure  # noqa: E402
from workflow.measure_manager import MeasureManager  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


class _S:
    def __init__(self, **kw):
        self.d = dict(DEFAULTS)
        self.d.update(kw)

    def get(self, k, d=None):
        return self.d.get(k, d)

    def set(self, k, v):
        self.d[k] = v


CHARTS = {"i1pro": "GretagMacbeth i1 Pro", "other": "X-Rite ColorMunki", "none": None}


def _chart(tmp_path, name, instr):
    p = tmp_path / f"{name}.ti2"
    tgt = f'TARGET_INSTRUMENT "{instr}"\n' if instr else ""
    p.write_text(f'CTI2\nDESCRIPTOR "x"\n{tgt}CHART_ID "1"\nSTEPS_IN_PASS "24"\n'
                 'PASSES_IN_STRIPS2 "1"\nNUMBER_OF_FIELDS 2\nBEGIN_DATA_FORMAT\n'
                 'SAMPLE_ID SAMPLE_LOC\nEND_DATA_FORMAT\nNUMBER_OF_SETS 0\nBEGIN_DATA\n'
                 'END_DATA\n', encoding="ascii")
    (tmp_path / f"{name}.ti1").write_text("CTI1\n", encoding="ascii")
    return tmp_path / f"{name}.ti1"


def _flags(tab, mode):
    """The strip-recognition flag the helper's argument list gets (MeasureManager._build_args:
    -B if disable, else -b if force, else nothing)."""
    p = tab._collect_manual() if mode == "manual" else tab._collect_guided()
    args = MeasureManager._build_args(MeasureManager.__new__(MeasureManager), p)
    got = [a for a in args if a in ("-b", "-B")]
    assert len(got) <= 1
    return got[0] if got else ""


def _tab(monkeypatch, dual: bool, dual_name="X-Rite i1 Pro 2"):
    from workflow.dual_scan import session as D
    monkeypatch.setattr(D, "switched_on", lambda settings: dual)
    s = _S(dual_scan_instrument_name=dual_name if dual else "")
    return TabMeasure(ArgyllRunner(s), s)


@pytest.mark.parametrize("dual", [False, True], ids=["dual off", "dual on"])
@pytest.mark.parametrize("chart", sorted(CHARTS))
@pytest.mark.parametrize("mode", ["manual", "guided"])
def test_the_whole_table_of_what_the_helper_is_told(tmp_path, monkeypatch, dual, chart, mode):
    tab = _tab(monkeypatch, dual)
    tab.set_ti1_path(_chart(tmp_path, chart, CHARTS[chart]))
    auto, combo = tab._bidir_widgets(mode)
    # Auto off: exactly the person's choice, whatever the chart or the dual scan
    auto.setChecked(False)
    for choice, want in (("default", ""), ("disable", "-B"), ("force", "-b")):
        combo.setCurrentIndex(combo.findData(choice))
        assert _flags(tab, mode) == want, (choice, chart, dual)
    # Auto on: both directions for an i1 Pro chart; for any other chart as soon as the
    # instrument of this measurement is known to be an i1 Pro (here: the dual scan's own,
    # an i1Pro 2); Argyll's default only when nothing says an i1 Pro measures
    auto.setChecked(True)
    want = "-b" if (chart == "i1pro" or dual) else ""
    assert _flags(tab, mode) == want, (chart, dual)


@pytest.mark.parametrize("chart", ["other", "none"])
def test_the_instrument_this_measurement_is_made_with_decides_when_the_chart_does_not(
        tmp_path, monkeypatch, chart):
    """The tester's most likely case: a chart naming no i1 Pro, read with an i1Pro 2 that
    reported itself: Auto now gives -b (until 4.3.53: nothing, one direction on this
    fixed-order chart)."""
    tab = _tab(monkeypatch, False)
    tab.set_ti1_path(_chart(tmp_path, chart, CHARTS[chart]))
    auto, _c = tab._bidir_widgets("manual")
    auto.setChecked(True)
    assert _flags(tab, "manual") == ""
    tab._reported_instrument = "X-Rite i1 Pro 2"
    assert _flags(tab, "manual") == "-b"
    assert tab._bidir_auto_decision()[1:] == ("X-Rite i1 Pro 2", "reported_by_the_instrument")


def test_a_colormunki_measuring_keeps_argylls_default(tmp_path, monkeypatch):
    tab = _tab(monkeypatch, False)
    tab.set_ti1_path(_chart(tmp_path, "none", None))
    tab._bidir_widgets("manual")[0].setChecked(True)
    tab._reported_instrument = "X-Rite ColorMunki"
    assert _flags(tab, "manual") == ""


def test_the_app_log_says_what_auto_decided_from_at_every_start(tmp_path, monkeypatch, caplog):
    tab = _tab(monkeypatch, True)
    tab.set_ti1_path(_chart(tmp_path, "none", None))
    tab._bidir_widgets(tab._current_mode())[0].setChecked(True)
    with caplog.at_level(logging.INFO):
        tab._log_bidir_decision(tab._collect_manual() if tab._current_mode() == "manual"
                                else tab._collect_guided())
    msg = [r.getMessage() for r in caplog.records if "strip recognition:" in r.getMessage()]
    assert msg and "Auto -> force, decided from X-Rite i1 Pro 2 (the_dual_scan_setting)" \
        in msg[-1] and "the chart names no instrument" in msg[-1] \
        and "both directions accepted: yes" in msg[-1]
