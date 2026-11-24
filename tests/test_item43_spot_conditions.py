"""Item 43, step 1: M0 / M1 / M2 in Tools > Read single patches, for an i1Pro 3.

The i1Pro 3's ArgyllCMS driver computes M0, M1 and M2 from every reading and
returns the one spotread's -F asks for (-F 5 = M1, -F u = M2; no -F = M0). No
other instrument ArgyllCMS drives can do that, so:

* the "Measurement condition" row is shown only for an i1Pro 3 (USB id
  0765:6009, or spotread's own report when the USB list cannot tell), in
  Reflective mode, through ArgyllCMS (never for the CR30);
* hidden, the command line and the saved files are exactly today's;
* -F that reaches another instrument ends that start before anything is read,
  and the session starts again without it, once;
* every reading of an i1Pro 3 session records its condition; the CSV gets a
  condition column only for M1 / M2; the .ti3 names its condition, one
  condition per file, a mixed list split per condition;
* Average selected works only within one condition;
* the item-41 calibration check keeps working on the spectrum spotread prints
  (M1 with -F 5), and its window says the session is M1.

Stock spotread returns ONE condition per reading (the one -F chose), so a
reading carries one condition; keeping all three per reading needs ChromIQ's
own helper (item 43 steps 2-3).
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMessageBox          # noqa: E402

from workflow import spot_read_io as IO                          # noqa: E402
from workflow.spot_read_io import SpotReading                    # noqa: E402
from workflow.spot_read_manager import (SpotReadManager,         # noqa: E402
                                        SpotReadParams, is_i1pro3)

READY = ("Hit ESC or Q to exit, instrument switch or any other key to take "
         "a reading: ")
CAL_STEP = [" and then hit any key to continue,"]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _StubRunner:
    def __init__(self):
        self.writes: list[str] = []
        self.runs: list = []
        self.aborted = 0

    def write_stdin(self, text):
        self.writes.append(text)

    def run(self, tool, args, cwd, **kw):
        self.runs.append((tool, list(args)))

    def abort(self):
        self.aborted += 1

    def forget_run_callbacks(self):
        pass

    @property
    def is_running(self):
        return False


def _feed(mgr, lines):
    for ln in lines:
        mgr._handle_line(ln, lambda _l: None)


def _let_the_timer_fire(mgr):
    """The queued restart runs from the event loop, as in the app."""
    import time
    end = time.monotonic() + 2
    while mgr._restart_timer.isActive() and time.monotonic() < end:
        QApplication.processEvents()
    assert not mgr._restart_timer.isActive()


def _args(**kw):
    return SpotReadManager(_StubRunner())._build_args(SpotReadParams(**kw))


# ---- 1. the command line ---------------------------------------------------
def test_m1_and_m2_ask_spotread_for_the_filter(qapp):
    assert _args(condition="M1") == ["-v", "-c", "1", "-F", "5", "-s"]
    assert _args(condition="M2") == ["-v", "-c", "1", "-F", "u", "-s"]


@pytest.mark.parametrize("cond", [None, "M0", ""])
def test_m0_and_none_are_todays_command_line(qapp, cond):
    assert _args(condition=cond) == ["-v", "-c", "1", "-s"]
    assert _args(condition=cond, disable_initial_cal=True) == \
        ["-v", "-c", "1", "-N", "-s"]


@pytest.mark.parametrize("mode", ["emissive", "ambient"])
def test_no_filter_outside_reflective(qapp, mode):
    assert "-F" not in _args(condition="M1", mode=mode)


def test_the_i1pro3_is_recognised_by_its_report(qapp):
    assert is_i1pro3("i1Pro3")
    assert is_i1pro3("i1Pro3 Plus")
    assert is_i1pro3("X-Rite i1 Pro 3")
    for other in ("i1Pro 2", "i1Pro", "ColorMunki", "i1Studio", "", None):
        assert not is_i1pro3(other)


# ---- 2. -F that reached another instrument --------------------------------
def _started(monkeypatch, condition):
    monkeypatch.setattr("core.instrument_port.refused_port", lambda *a: None)
    runner = _StubRunner()
    mgr = SpotReadManager(runner)
    got = {"dropped": [], "cal": [], "ready": [], "ended": [], "detected": []}
    mgr.condition_dropped.connect(lambda m: got["dropped"].append(m))
    mgr.calibration_prompt.connect(lambda: got["cal"].append(1))
    mgr.ready_to_read.connect(lambda: got["ready"].append(1))
    mgr.session_ended.connect(lambda c: got["ended"].append(c))
    mgr.instrument_detected.connect(lambda m: got["detected"].append(m))
    mgr.start(SpotReadParams(condition=condition), lambda _l: None)
    return mgr, runner, got


def test_another_instrument_ends_the_start_and_starts_again_without_f(
        qapp, monkeypatch):
    mgr, runner, got = _started(monkeypatch, "M1")
    assert "-F" in runner.runs[0][1]
    _feed(mgr, ["Instrument Type:   i1Pro 2",
                "Setting requested filter not supported by instrument"])
    assert got["detected"] == ["i1Pro 2"]
    mgr._on_finish(255)
    assert got["dropped"] == ["i1Pro 2"]
    assert got["ended"] == []          # the window's session goes on
    assert mgr._restart_timer.isActive()      # the restart is really queued
    _let_the_timer_fire(mgr)
    assert len(runner.runs) == 2
    assert "-F" not in runner.runs[1][1]
    assert runner.runs[1][1] == ["-v", "-c", "1", "-s"]


def test_the_refusal_alone_is_enough(qapp, monkeypatch):
    mgr, runner, got = _started(monkeypatch, "M2")
    _feed(mgr, ["Setting requested filter not supported by instrument"])
    mgr._on_finish(255)
    assert got["dropped"] == [""]
    assert mgr._restart_timer.isActive()      # the restart is really queued
    _let_the_timer_fire(mgr)
    assert "-F" not in runner.runs[1][1]


def test_a_wrong_start_shows_no_calibration_window_and_quits_at_its_prompt(
        qapp, monkeypatch):
    mgr, runner, got = _started(monkeypatch, "M1")
    _feed(mgr, ["Instrument Type:   Spectrolino"] + CAL_STEP + [READY])
    assert got["cal"] == [] and got["ready"] == []
    assert runner.writes == ["q"]
    assert runner.aborted == 0          # left the way Stop leaves it


def test_the_restart_happens_once(qapp, monkeypatch):
    mgr, runner, got = _started(monkeypatch, "M1")
    _feed(mgr, ["Instrument Type:   ColorMunki"])
    mgr._on_finish(255)
    assert mgr._restart_timer.isActive()      # the restart is really queued
    _let_the_timer_fire(mgr)
    _feed(mgr, ["Instrument Type:   ColorMunki"])
    mgr._on_finish(0)
    assert got["dropped"] == ["ColorMunki"]
    assert got["ended"] == [0]
    assert len(runner.runs) == 2


def test_an_i1pro3_report_keeps_the_filter(qapp, monkeypatch):
    mgr, runner, got = _started(monkeypatch, "M1")
    _feed(mgr, ["Instrument Type:   i1Pro3"] + CAL_STEP + [READY])
    assert got["cal"] == [1] and got["ready"] == [1]
    mgr._on_finish(0)
    assert got["dropped"] == [] and got["ended"] == [0]


def test_without_f_nothing_restarts(qapp, monkeypatch):
    mgr, runner, got = _started(monkeypatch, None)
    _feed(mgr, ["Instrument Type:   i1Pro 2"] + CAL_STEP + [READY])
    mgr._on_finish(0)
    assert got["dropped"] == [] and got["ended"] == [0]
    assert got["cal"] == [1]


# ---- 3. the files ----------------------------------------------------------
def _readings(*conds):
    return [SpotReading(f"P{i}", (10.0 + i, 20.0, 30.0), (50.0, 1.0, -2.0), c)
            for i, c in enumerate(conds, start=1)]


@pytest.fixture
def frozen_stamp(monkeypatch):
    monkeypatch.setattr("workflow.colverify_runner.created_stamp",
                        lambda *a: "Tue Nov 24 12:00:00 2026")


def test_without_a_condition_the_csv_is_todays(tmp_path):
    p = IO.write_csv(tmp_path / "a.csv", _readings(None, None))
    lines = p.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "name,L,a,b,X,Y,Z,sRGB_hex"
    assert lines[1].count(",") == 7


def test_m0_alone_needs_no_csv_column(tmp_path):
    p = IO.write_csv(tmp_path / "a.csv", _readings("M0", "M0"))
    assert p.read_text(encoding="utf-8").splitlines()[0] == \
        "name,L,a,b,X,Y,Z,sRGB_hex"


def test_m1_gets_a_condition_column(tmp_path):
    p = IO.write_csv(tmp_path / "a.csv", _readings("M1", "M0", None))
    rows = p.read_text(encoding="utf-8").splitlines()
    assert rows[0] == "name,L,a,b,X,Y,Z,sRGB_hex,condition"
    assert [r.rsplit(",", 1)[1] for r in rows[1:]] == ["M1", "M0", ""]


def test_without_a_condition_the_ti3_is_byte_identical(tmp_path, frozen_stamp):
    from workflow.colverify_runner import write_reference_ti3
    rs = _readings(None, None, None)
    new = IO.write_ti3_files(tmp_path / "x", rs)
    assert [p.name for p in new] == ["x.ti3"]
    old = write_reference_ti3(tmp_path / "old.ti3", [r.xyz for r in rs],
                              space="XYZ")
    assert new[0].read_bytes() == old.read_bytes()


def test_one_condition_is_one_file_that_names_it(tmp_path, frozen_stamp):
    from workflow.measurement_condition import read_condition, read_header_keyword
    [p] = IO.write_ti3_files(tmp_path / "x", _readings("M1", "M1"))
    assert p.name == "x.ti3"
    assert read_condition(p) == "M1"
    assert read_header_keyword(p, "MEASUREMENT_CONDITION_SOURCE") is None
    [p0] = IO.write_ti3_files(tmp_path / "y", _readings("M0"))
    assert read_condition(p0) == "M0"
    # M0 is the i1Pro 3's normal mode (no -F), and says so
    assert read_header_keyword(p0, "MEASUREMENT_CONDITION_SOURCE") == \
        "INSTRUMENT_DEFAULT"


def test_a_mixed_list_is_split_per_condition(tmp_path, frozen_stamp):
    from workflow.measurement_condition import read_condition
    rs = _readings("M1", "M2", "M1", None)
    paths = IO.write_ti3_files(tmp_path / "x", rs)
    assert [p.name for p in paths] == ["x-M1.ti3", "x-M2.ti3", "x.ti3"]
    assert [read_condition(p) for p in paths] == ["M1", "M2", None]
    m1 = paths[0].read_text(encoding="utf-8")
    assert "NUMBER_OF_SETS 2" in m1
    assert "11" in m1 and "13" in m1 and "\n2 12" not in m1


def test_a_mixed_list_is_refused_by_the_single_writer(tmp_path):
    with pytest.raises(IO.MixedConditions):
        IO.write_ti3(tmp_path / "x.ti3", _readings("M1", "M2"))


def test_the_condition_lines_are_the_only_change(tmp_path, frozen_stamp):
    """An M2 file is today's file plus the two header lines that name M2."""
    rs = _readings("M2", "M2")
    [p] = IO.write_ti3_files(tmp_path / "x", rs)
    [old] = IO.write_ti3_files(tmp_path / "old", _readings(None, None))
    extra = [ln for ln in p.read_text(encoding="utf-8").splitlines()
             if ln not in old.read_text(encoding="utf-8").splitlines()]
    assert extra == ['KEYWORD "MEASUREMENT_CONDITION"',
                     'MEASUREMENT_CONDITION "M2"']


# ---- 4. averaging ----------------------------------------------------------
def test_averaging_keeps_the_condition():
    avg = IO.average_readings(_readings("M1", "M1"), "Average")
    assert avg.condition == "M1"
    assert IO.average_readings(_readings(None, None), "A").condition is None


@pytest.mark.parametrize("conds", [("M0", "M1"), ("M1", "M2"), (None, "M0")])
def test_averaging_across_conditions_is_refused(conds):
    with pytest.raises(IO.MixedConditions) as exc:
        IO.average_readings(_readings(*conds), "Average")
    assert exc.value.conditions == list(conds)


# ---- 5. the window ---------------------------------------------------------
def _dialog(monkeypatch, family, *, reader="argyll", stored=None):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    from workflow.dual_scan import instrument_model as IM

    class _D(SpotReadDialog):
        def _ask(self, box: QMessageBox):
            self.asked.append((box.text(), box.informativeText()))
            for b in box.buttons():
                if b.text().replace("&", "") == "Carry on measuring":
                    return b
            return None

    monkeypatch.setattr(IM, "attached_family", lambda: family)
    monkeypatch.setattr("core.instrument_port.refused_port", lambda *a: None)
    s = AppSettings()
    s.set("spot_read_instrument", reader)
    s.set("spot_read_condition", stored or "M0")
    runner = ArgyllRunner(s)
    runs: list = []
    monkeypatch.setattr(runner, "run",
                        lambda tool, args, cwd, **k: runs.append(list(args)))
    sent: list = []
    monkeypatch.setattr(runner, "write_stdin", sent.append)
    d = _D(runner, s)
    d.asked = []
    d.runs = runs
    d.sent = sent
    return d


def _start(d, model):
    d._on_start_stop()
    # (no calibration lines: their windows are the item-41 tests' business)
    _feed(d._manager, [f"Instrument Type:   {model}", READY])


def _visible(d):
    return not d._cond_row.isHidden()


def test_the_row_is_hidden_for_other_instruments(qapp, monkeypatch):
    from workflow.dual_scan import instrument_model as IM
    for fam in (IM.FAMILY_OTHER, IM.FAMILY_I1PRO, None):
        d = _dialog(monkeypatch, fam)
        assert not _visible(d), fam
        d.deleteLater()


def test_a_hidden_row_starts_todays_spotread(qapp, monkeypatch):
    from workflow.dual_scan import instrument_model as IM
    d = _dialog(monkeypatch, IM.FAMILY_OTHER, stored="M1")
    d._on_start_stop()
    assert d.runs == [["-v", "-c", "1", "-s"]]
    d.deleteLater()


def test_the_row_is_shown_for_an_i1pro3_on_usb(qapp, monkeypatch):
    from workflow.dual_scan import instrument_model as IM
    d = _dialog(monkeypatch, IM.FAMILY_I1PRO3)
    assert _visible(d)
    assert d._condition.currentData() == "M0"            # the safe default
    assert [d._condition.itemData(i) for i in range(d._condition.count())] \
        == ["M0", "M1", "M2"]
    d.deleteLater()


def test_the_row_follows_mode_and_reader(qapp, monkeypatch):
    from workflow.dual_scan import instrument_model as IM
    d = _dialog(monkeypatch, IM.FAMILY_I1PRO3)
    d._mode.setCurrentIndex(1)                          # emissive
    assert not _visible(d)
    d._mode.setCurrentIndex(0)
    assert _visible(d)
    d._instrument.setCurrentIndex(2)                    # CR30
    assert not _visible(d)
    d.deleteLater()


def test_an_m1_session_asks_for_m1_and_records_it(qapp, monkeypatch):
    from workflow.dual_scan import instrument_model as IM
    d = _dialog(monkeypatch, IM.FAMILY_I1PRO3)
    d._condition.setCurrentIndex(1)
    assert d._settings.get("spot_read_condition") == "M1"
    _start(d, "i1Pro3")
    assert d.runs == [["-v", "-c", "1", "-F", "5", "-s"]]
    assert not d._condition.isEnabled()          # one condition per session
    d._on_reading((40.0, 42.0, 35.0), (70.0, 1.0, 2.0))
    assert d._readings[0].condition == "M1"
    assert not d._table.isColumnHidden(8)
    assert d._table.item(0, 8).text() == "M1"
    d.deleteLater()


def test_an_i1pro3_in_m0_records_m0_without_f(qapp, monkeypatch):
    from workflow.dual_scan import instrument_model as IM
    d = _dialog(monkeypatch, IM.FAMILY_I1PRO3)
    _start(d, "i1Pro3")
    assert d.runs == [["-v", "-c", "1", "-s"]]
    d._on_reading((40.0, 42.0, 35.0), (70.0, 1.0, 2.0))
    assert d._readings[0].condition == "M0"
    d.deleteLater()


def test_another_instrument_records_nothing_and_shows_no_column(
        qapp, monkeypatch):
    from workflow.dual_scan import instrument_model as IM
    d = _dialog(monkeypatch, IM.FAMILY_OTHER)
    _start(d, "ColorMunki")
    d._on_reading((40.0, 42.0, 35.0), (70.0, 1.0, 2.0))
    assert d._readings[0].condition is None
    assert d._table.isColumnHidden(8)
    d.deleteLater()


def test_usb_cannot_tell_then_the_report_shows_the_row(qapp, monkeypatch):
    d = _dialog(monkeypatch, None, stored="M2")
    assert not _visible(d)
    _start(d, "i1Pro3 Plus")
    assert d.runs == [["-v", "-c", "1", "-s"]]          # no -F was sent
    assert _visible(d)
    # it shows what this session reads under, not the remembered M2
    assert d._condition.currentData() == "M0"
    d._on_reading((40.0, 42.0, 35.0), (70.0, 1.0, 2.0))
    assert d._readings[0].condition == "M0"
    assert d._settings.get("spot_read_condition") == "M2"
    d._on_session_ended(0)
    assert d._condition.currentData() == "M2"            # remembered again
    d.deleteLater()


def test_a_wrong_guess_starts_again_and_says_so(qapp, monkeypatch):
    from workflow import measurement_messages as M
    from workflow.dual_scan import instrument_model as IM
    d = _dialog(monkeypatch, IM.FAMILY_I1PRO3)
    d._condition.setCurrentIndex(2)                      # M2
    d._on_start_stop()
    assert "-F" in d.runs[0]
    _feed(d._manager, ["Instrument Type:   i1Pro 2",
                       "Setting requested filter not supported by instrument"])
    d._manager._on_finish(255)
    status = d._status.text()
    assert "i1Pro 2" in status
    assert status == M.M_SPOT_CONDITION_NOT_I1PRO3.render(model="i1Pro 2")[1]
    assert not _visible(d)
    assert d._manager._restart_timer.isActive()
    _let_the_timer_fire(d._manager)
    assert "-F" not in d.runs[1]
    _feed(d._manager, ["Instrument Type:   i1Pro 2", READY])
    # the restarted session's Ready line does not wipe it out (seen on screen)
    assert d._status.text().startswith(status)
    d._on_reading((40.0, 42.0, 35.0), (70.0, 1.0, 2.0))
    assert d._readings[0].condition is None
    d._on_ready()
    assert d._status.text().startswith(status)
    d._on_session_ended(0)
    # the instrument's report keeps winning over the USB guess (same cable):
    # no row, and the next start is today's command line, no second detour
    assert not _visible(d)
    d._on_start_stop()
    assert d.runs[-1] == ["-v", "-c", "1", "-s"]
    _feed(d._manager, ["Instrument Type:   i1Pro 2", READY])
    assert not d._status.text().startswith(status)   # a new session: gone
    d.deleteLater()


def test_average_selected_refuses_mixed_conditions(qapp, monkeypatch):
    from workflow import measurement_messages as M
    from workflow.dual_scan import instrument_model as IM
    d = _dialog(monkeypatch, IM.FAMILY_I1PRO3)
    for r in _readings("M1", "M0"):
        d._readings.append(r)
        d._append_row(r)
    d._table.selectAll()
    d._on_average_selected()
    assert len(d._readings) == 2
    assert d._status.text() == M.M_SPOT_AVERAGE_CONDITIONS.render(
        conditions="M1, M0")[1]
    d.deleteLater()


def test_average_selected_within_one_condition(qapp, monkeypatch):
    from workflow.dual_scan import instrument_model as IM
    d = _dialog(monkeypatch, IM.FAMILY_I1PRO3)
    for r in _readings("M2", "M2"):
        d._readings.append(r)
        d._append_row(r)
    d._table.selectAll()
    d._on_average_selected()
    assert len(d._readings) == 3 and d._readings[2].condition == "M2"
    d.deleteLater()


def test_save_writes_one_ti3_per_condition(qapp, monkeypatch, tmp_path):
    from workflow.dual_scan import instrument_model as IM
    import ui.widgets
    import ui.dialogs.spot_read_dialog as SRD
    d = _dialog(monkeypatch, IM.FAMILY_I1PRO3)
    for r in _readings("M1", "M2"):
        d._readings.append(r)
        d._append_row(r)
    monkeypatch.setattr(ui.widgets, "save_file_dialog",
                        lambda *a, **k: str(tmp_path / "spots.csv"))
    told: list = []
    monkeypatch.setattr(SRD, "inform", lambda _w, t, b: told.append(b))
    assert d._on_save()
    assert sorted(p.name for p in tmp_path.iterdir()) == \
        ["spots-M1.ti3", "spots-M2.ti3", "spots.csv"]
    assert "spots-M1.ti3" in told[0] and "spots-M2.ti3" in told[0]
    d.deleteLater()


# ---- 6. the item-41 calibration check, per condition ------------------------
def _too_light_lines():
    vals = ", ".join("120" for _ in range(36))
    return ["Spectrum from 380.000000 to 730.000000 nm in 36 steps", vals,
            " Result is XYZ: 115.0 120.0 99.0, D50 Lab: 107.0 0.5 0.5"]


@pytest.mark.parametrize("cond,family_model,note", [
    ("M1", "i1Pro3", True), (None, "i1Pro3", False), (None, "i1Pro 2", False)])
def test_the_check_still_works_and_names_m1(qapp, monkeypatch, cond,
                                            family_model, note):
    from workflow import measurement_messages as M
    from workflow.dual_scan import instrument_model as IM
    fam = IM.FAMILY_I1PRO3 if is_i1pro3(family_model) else IM.FAMILY_OTHER
    d = _dialog(monkeypatch, fam)
    if cond == "M1":
        d._condition.setCurrentIndex(1)
    _start(d, family_model)
    _feed(d._manager, _too_light_lines())
    assert len(d.asked) == 1, "the item-41 check must still speak"
    assert d.asked[0][0] == M.M_SPOT_CAL_TOO_LIGHT.render(percent="0")[0]
    m1_note = M.M_SPOT_CAL_CONDITION_M1.render()[1]
    assert (m1_note in d.asked[0][1]) is note
    d.deleteLater()


# ---- 7. the review's fix round ---------------------------------------------
def test_a_cr30_session_carries_no_restart_note(qapp, monkeypatch):
    """Review S1: the note and the condition of an earlier ArgyllCMS session
    are reset at EVERY start, the CR30's included."""
    from workflow.dual_scan import instrument_model as IM
    d = _dialog(monkeypatch, IM.FAMILY_I1PRO3)
    d._condition.setCurrentIndex(1)
    d._on_start_stop()
    _feed(d._manager, ["Instrument Type:   i1Pro 2",
                       "Setting requested filter not supported by instrument"])
    d._manager._on_finish(255)
    assert d._condition_note
    d._manager._restart_timer.stop()
    d._on_session_ended(0)
    started: list = []
    monkeypatch.setattr(d, "_chosen_reader", lambda: "cr30")
    monkeypatch.setattr(d, "_start_cr30_session", lambda: started.append(1))
    d._on_start_stop()
    assert started == [1]
    assert d._condition_note == "" and d._session_condition is None
    assert d._start_condition is None
    d._on_ready()
    assert d._status.text() == d._ready_text()
    d.deleteLater()


def test_the_m1_paragraph_is_only_on_the_too_light_warning(qapp, monkeypatch):
    """Review S2: never under the saturation warning, and it does not blame
    a paper brightener (its glow ends below 530 nm)."""
    from workflow import measurement_messages as M
    from workflow.dual_scan import instrument_model as IM
    note = M.M_SPOT_CAL_CONDITION_M1.render()[1]
    assert "paper" not in note
    d = _dialog(monkeypatch, IM.FAMILY_I1PRO3)
    d._condition.setCurrentIndex(1)
    _start(d, "i1Pro3")
    _feed(d._manager, ["", "Spot read failed due to misread (Sensor is saturated)"])
    assert len(d.asked) == 1
    assert d.asked[0][0] == M.M_SPOT_CAL_SATURATED.render()[0]
    assert note not in d.asked[0][1]
    d.deleteLater()


def test_a_reading_without_a_condition_is_named_in_words(qapp, monkeypatch):
    from workflow.dual_scan import instrument_model as IM
    d = _dialog(monkeypatch, IM.FAMILY_I1PRO3)
    for r in _readings(None, "M0"):
        d._readings.append(r)
        d._append_row(r)
    d._table.selectAll()
    d._on_average_selected()
    assert "(unknown, M0)" in d._status.text() and "?" not in d._status.text()
    d.deleteLater()


def _save_setup(d, monkeypatch, tmp_path):
    import ui.widgets
    import ui.dialogs.spot_read_dialog as SRD
    monkeypatch.setattr(ui.widgets, "save_file_dialog",
                        lambda *a, **k: str(tmp_path / "spots.csv"))
    monkeypatch.setattr(SRD, "inform", lambda *a, **k: None)
    for r in _readings("M1", "M2"):
        d._readings.append(r)
        d._append_row(r)


@pytest.mark.parametrize("answer,written", [("Cancel", False), ("Replace", True)])
def test_save_asks_before_replacing_earlier_condition_files(
        qapp, monkeypatch, tmp_path, answer, written):
    from workflow import measurement_messages as M
    from workflow.dual_scan import instrument_model as IM
    d = _dialog(monkeypatch, IM.FAMILY_I1PRO3)
    _save_setup(d, monkeypatch, tmp_path)
    (tmp_path / "spots-M1.ti3").write_text("old M1", encoding="utf-8")
    (tmp_path / "spots-M0.ti3").write_text("old M0", encoding="utf-8")

    def _ask(box):
        d.asked.append((box.text(), box.informativeText()))
        return next(b for b in box.buttons() if b.text() == answer)
    monkeypatch.setattr(d, "_ask", _ask)
    assert d._on_save() is written
    title, body = M.M_SPOT_SAVE_CONDITION_FILES.render(
        files="spots-M0.ti3, spots-M1.ti3")
    assert d.asked == [(title, body)]
    m1 = (tmp_path / "spots-M1.ti3").read_text(encoding="utf-8")
    assert (m1 != "old M1") is written
    # nothing is deleted: the earlier M0 file stays, and the text said so
    assert (tmp_path / "spots-M0.ti3").read_text(encoding="utf-8") == "old M0"
    d.deleteLater()


def test_save_without_earlier_condition_files_asks_nothing(
        qapp, monkeypatch, tmp_path):
    from workflow.dual_scan import instrument_model as IM
    d = _dialog(monkeypatch, IM.FAMILY_I1PRO3)
    _save_setup(d, monkeypatch, tmp_path)
    assert d._on_save()
    assert d.asked == []
    d.deleteLater()


def test_the_row_goes_when_the_i1pro3_is_unplugged(qapp, monkeypatch):
    import ui.dialogs.spot_read_dialog as SRD
    bus = {"fp": ((0x0765, 0x6009, 1),)}
    monkeypatch.setattr(SRD, "usb_fingerprint_now", lambda: bus["fp"])
    d = _dialog(monkeypatch, None)          # the list cannot name it
    _start(d, "i1Pro3")
    d._on_session_ended(0)
    assert _visible(d)                       # its own report, same cable
    bus["fp"] = ()                           # unplugged
    d._sync_condition_row()
    assert not _visible(d)
    d.deleteLater()


def test_stop_between_a_start_and_its_restart_starts_nothing(qapp, monkeypatch):
    from workflow.dual_scan import instrument_model as IM
    d = _dialog(monkeypatch, IM.FAMILY_I1PRO3)
    d._condition.setCurrentIndex(1)
    d._on_start_stop()
    _feed(d._manager, ["Setting requested filter not supported by instrument"])
    d._manager._on_finish(255)
    assert d._manager.restart_pending()
    d._on_start_stop()                       # Stop, in the gap
    assert not d._manager.restart_pending()
    assert d._start_btn.text() == "Start session"
    qapp.processEvents()
    assert len(d.runs) == 1
    d.deleteLater()


def test_a_filter_accepted_without_a_report_still_records_it(qapp, monkeypatch):
    """Review S3: -F accepted and no "Instrument Type:" line (spotread prints
    it only for some drivers): the reading was taken under the filter."""
    from workflow.dual_scan import instrument_model as IM
    d = _dialog(monkeypatch, IM.FAMILY_I1PRO3)
    d._condition.setCurrentIndex(2)
    d._on_start_stop()
    _feed(d._manager, [READY])
    d._on_reading((40.0, 42.0, 35.0), (70.0, 1.0, 2.0))
    assert d._readings[0].condition == "M2"
    d.deleteLater()
