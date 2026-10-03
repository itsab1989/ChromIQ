"""Measure: a chart whose locations its patterns cannot read never reaches
stock chartread, and a helper that never started still does.

Forum report, 2026-10-03: a chart made with strip pattern "0-9" and 14 strips.
The engine stopped with "Bad location field value '(null)' on patch 266", the
log said "(unknown error)", ChromIQ restarted on stock chartread, which reads
the chart with the same ArgyllCMS code and failed identically. Knut, #182
5965589190 Q2: such a sheet, printed with ChromIQ's labels from before
4.3.3-beta.7, is read by ChromIQ's engine as printed; a stock chartread user
is told plainly.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from PyQt6.QtCore import QCoreApplication

from workflow.measure_manager import MeasureManager, MeasureParams


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QCoreApplication.instance() or QCoreApplication(sys.argv)


class _RecordingRunner:
    def __init__(self) -> None:
        self.runs: list[dict] = []

    def run(self, tool, args, cwd, on_line=None, on_finish=None,
            use_pty=False) -> None:
        self.runs.append({"tool": str(tool), "args": list(args),
                          "on_finish": on_finish})

    def write_stdin(self, text: str) -> None:
        pass

    def abort(self) -> None:
        pass


def _start(tmp_path: Path, **kw):
    runner = _RecordingRunner()
    mgr = MeasureManager(runner)
    mgr._guided_state = "disabled"
    ti1 = tmp_path / "chart.ti1"
    ti1.write_text("", encoding="utf-8")
    params = MeasureParams(ti1_path=ti1,
                           engine_helper=Path("/fake/chromiq-chartread"), **kw)
    lines: list[str] = []
    finished: list[int] = []
    got = {"unreadable": [], "legacy": [], "fell": [], "resumed": []}
    mgr.chart_unreadable.connect(got["unreadable"].append)
    mgr.legacy_chart_read_ended.connect(got["legacy"].append)
    mgr.engine_fell_back.connect(got["fell"].append)
    mgr.engine_fell_back_resumed.connect(got["resumed"].append)
    mgr.start(params, lines.append, finished.append)
    assert len(runner.runs) == 1
    return mgr, runner, lines, finished, got


def _feed(mgr, event, lines):
    mgr._handle_engine_line(json.dumps(event), lines.append)


def _partial_ti3(tmp_path: Path) -> None:
    (tmp_path / "chart.ti3").write_text(
        "CTI3\n\nNUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n\n"
        "NUMBER_OF_SETS 1\nBEGIN_DATA\n1 10 10 10\nEND_DATA\n",
        encoding="utf-8")


# ---- the typed event: no reader can read the chart -------------------------
def test_the_unreadable_chart_event_never_reaches_stock_chartread(tmp_path):
    mgr, runner, lines, finished, got = _start(tmp_path)
    _feed(mgr, {"event": "error", "kind": "chart_unreadable",
                "detail": "patch 266 location '14M'"}, lines)
    runner.runs[-1]["on_finish"](1)
    assert len(runner.runs) == 1, "stock chartread must not be launched"
    assert finished == [1]
    assert got["unreadable"] == ["patch 266 location '14M'"]
    assert got["fell"] == []


def test_nor_the_resume_after_some_strips_were_read(tmp_path):
    mgr, runner, lines, finished, got = _start(tmp_path)
    _partial_ti3(tmp_path)
    _feed(mgr, {"event": "strip_read", "strip": "A", "worst_de": 0.4}, lines)
    _feed(mgr, {"event": "error", "kind": "chart_unreadable"}, lines)
    runner.runs[-1]["on_finish"](1)
    assert len(runner.runs) == 1
    assert got["resumed"] == [] and len(got["unreadable"]) == 1


def test_nor_the_whole_sheet_mode_fallback(tmp_path):
    mgr, runner, lines, finished, got = _start(tmp_path)
    _feed(mgr, {"event": "error", "kind": "chart_unreadable"}, lines)
    mgr._engine_mode_fallback = True
    runner.runs[-1]["on_finish"](1)
    assert len(runner.runs) == 1


# ---- a sheet only the engine can read (stock_cannot_read_chart) ------------
def test_an_engine_only_sheet_never_falls_back_immediately(tmp_path):
    mgr, runner, lines, finished, got = _start(
        tmp_path, stock_cannot_read_chart="the location “14M” does not fit")
    _feed(mgr, {"event": "error", "kind": "coms"}, lines)
    runner.runs[-1]["on_finish"](1)
    assert len(runner.runs) == 1
    assert finished == [1]
    assert got["legacy"] == ["communication problem"]
    assert got["fell"] == []


def test_an_engine_only_sheet_never_resumes_on_stock(tmp_path):
    mgr, runner, lines, finished, got = _start(
        tmp_path, stock_cannot_read_chart="x")
    _partial_ti3(tmp_path)
    _feed(mgr, {"event": "strip_read", "strip": "1", "worst_de": 0.4}, lines)
    _feed(mgr, {"event": "error", "kind": "coms"}, lines)
    runner.runs[-1]["on_finish"](1)
    assert len(runner.runs) == 1
    assert got["resumed"] == []
    assert not any("carry on measuring" in ln for ln in lines)


def test_an_engine_only_sheet_never_takes_the_whole_sheet_fallback(tmp_path):
    mgr, runner, lines, finished, got = _start(
        tmp_path, stock_cannot_read_chart="x")
    mgr._engine_mode_fallback = True
    runner.runs[-1]["on_finish"](0)
    assert len(runner.runs) == 1


# ---- what must still fall back --------------------------------------------
def test_a_helper_that_never_started_still_falls_back(tmp_path):
    """No exec bit, quarantine: no event at all, so nothing identified the
    chart. Stock chartread is the rescue, as before."""
    mgr, runner, lines, finished, got = _start(tmp_path)
    runner.runs[-1]["on_finish"](126)
    assert len(runner.runs) == 2 and runner.runs[1]["tool"] == "chartread"


def test_the_reason_is_the_helpers_own_sentence_not_unknown_error(tmp_path):
    """The engine died before any event; the log used to say "(unknown error)"
    while the helper had printed exactly what was wrong."""
    mgr, runner, lines, finished, got = _start(tmp_path)
    mgr._handle_engine_line(
        "chromiq-chartread: Error - Bad location field value '14M' on patch 1",
        lines.append)
    runner.runs[-1]["on_finish"](1)
    assert got["fell"] and "unknown error" not in got["fell"][0]
    assert "14M" in got["fell"][0]


# ---- the Measure tab's pre-check -------------------------------------------
def _ti1(d: Path, n: int) -> Path:
    lines = ["CTI1", "", 'DESCRIPTOR "p"', 'ORIGINATOR "ChromIQ"',
             "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
             f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    for i in range(n):
        lines.append(f"{i+1} {(i*7)%100}.0 {(i*13)%100}.0 {(i*29)%100}.0 40 45 50")
    lines += ["END_DATA", ""]
    p = d / "p.ti1"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def _chart(d: Path, strip, patch, rule) -> Path:
    from workflow.layout_engine import chart as le_chart
    d.mkdir(parents=True, exist_ok=True)
    le_chart.build_chart(_ti1(d, 400), d / "c", instrument="i1", paper="A4",
                         dpi=72, seed=5, strip_pattern=strip,
                         patch_pattern=patch, label_rule=rule)
    return d / "c.ti2"


class _Log:
    def __init__(self):
        self.lines = []

    def appendPlainText(self, t):          # noqa: N802
        self.lines.append(t)

    def ensureCursorVisible(self):         # noqa: N802
        pass


def _tab(ti2: Path, *, engine: bool):
    from ui.tabs.tab_measure import TabMeasure

    class _T:
        _chart_file_for = staticmethod(TabMeasure._chart_file_for)
        _blocked_by_unreadable_locations = \
            TabMeasure._blocked_by_unreadable_locations

        def __init__(self):
            self._ti1_path = ti2
            self._log = _Log()
            self.windows = []

        def _engine_selected(self):
            return engine

        def _chart_unreadable_window(self, detail):
            self.windows.append(("unreadable", detail))

        def _chart_legacy_stock_window(self, detail):
            self.windows.append(("legacy-stock", detail))
    return _T()


@pytest.fixture
def engine_reads_legacy(monkeypatch):
    from workflow import chartread_engine
    monkeypatch.setattr(chartread_engine, "is_available", lambda: True)
    monkeypatch.setattr(chartread_engine, "reads_legacy_labels",
                        lambda helper=None: True)


def test_a_legacy_sheet_goes_to_the_engine_and_never_to_stock(
        tmp_path, engine_reads_legacy):
    t = _tab(_chart(tmp_path / "l", "0-9", "A-Z", "legacy"), engine=True)
    assert t._blocked_by_unreadable_locations() is False
    assert t._engine_only_chart, "the manager must be told: no stock fallback"
    assert t.windows == []


def test_a_legacy_sheet_on_stock_chartread_is_refused_plainly(
        tmp_path, engine_reads_legacy):
    t = _tab(_chart(tmp_path / "l", "0-9", "A-Z", "legacy"), engine=False)
    assert t._blocked_by_unreadable_locations() is True
    assert [w[0] for w in t.windows] == ["legacy-stock"]


def test_a_legacy_sheet_with_an_engine_that_cannot_read_it_is_refused(
        tmp_path, monkeypatch):
    from workflow import chartread_engine
    monkeypatch.setattr(chartread_engine, "reads_legacy_labels",
                        lambda helper=None: False)
    t = _tab(_chart(tmp_path / "l", "0-9", "A-Z", "legacy"), engine=True)
    assert t._blocked_by_unreadable_locations() is True
    assert [w[0] for w in t.windows] == ["unreadable"]


def test_a_sheet_no_reader_can_read_is_refused(tmp_path, engine_reads_legacy):
    """Numbers on both sides, printed with the old rule: "111" is strip 1
    patch 11 and strip 11 patch 1 at once, for every reader."""
    t = _tab(_chart(tmp_path / "n", "0-9", "1-999", "legacy"), engine=True)
    assert t._blocked_by_unreadable_locations() is True
    assert [w[0] for w in t.windows] == ["unreadable"]


@pytest.mark.parametrize("strip,patch", [("A-Z, A-Z", "0-9,@-9,@-9;1-999"),
                                         ("0-9,@-9;1-99", "A-Z")])
def test_a_chart_argyll_reads_is_not_held_up(tmp_path, strip, patch,
                                              engine_reads_legacy):
    t = _tab(_chart(tmp_path / "ok", strip, patch, "argyll"), engine=False)
    assert t._blocked_by_unreadable_locations() is False
    assert t.windows == [] and not t._engine_only_chart
