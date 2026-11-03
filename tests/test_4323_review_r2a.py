"""4.3.23 review round 2, part A: the findings, each pinned (Basti's
rulings of 2026-11-03).

S-A1  Refine / resume onto a measurement that records a condition, with -F
      giving another one (or none), is refused before anything happens
      (M-RESUME-CONDITION); onto one that records none it goes ahead, records
      nothing at the end and says why in the log. Imports alike.
S-A3  "not recorded" against M1/M2/M3 is ASKED about, for the
      pre-conditioning merge and Tools > Merge (M-MERGE-CONDITION-ASK); two
      different recorded conditions stay refused, and the refusal never asks
      the person to match "not recorded". A caller that cannot ask does not
      merge, and logs it.
S-A2  averaging (the Measure tab's and Tools > Average) follows the same
      rule; the averaged result keeps the common condition, or none.
M-A1  the report folds only ArgyllCMS's generic "GretagMacbeth i1 Pro" into
      the i1Pro the other runs name; i1 Pro 2 against i1 Pro 3 is flagged.
M-A2  the FWA tooltip of a chartread M1/M2/M3 says to set -F to None (M0)
      or switch it off; M3 has its own sentence.
"""
from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.test_4323_review_r1 import _ti3

ROOT = Path(__file__).resolve().parents[1]
EM_DASH = "—"


def _cond(path, condition):
    from workflow.measurement_condition import record_condition
    if condition:
        record_condition(path, condition)
    return path


# ---------------------------------------------------------------------------
# S-A1: resume with a different condition
# ---------------------------------------------------------------------------

class _Log:
    def __init__(self):
        self.lines = []

    def appendPlainText(self, s):
        self.lines.append(s)

    def ensureCursorVisible(self):
        pass


class _Box:
    def __init__(self, text):
        self._text = text

    def text(self):
        return self._text


def _resume_tab(ti3, code):
    """A stand-in carrying exactly what the check asks."""
    from ui.tabs.tab_measure import TabMeasure
    t = SimpleNamespace()
    t._measurement_to_continue = lambda: ti3
    t._measure_filter_code = lambda: code
    t._filter_label = lambda c: TabMeasure._filter_label(t, c)
    t._FILTER_LABELS = TabMeasure._FILTER_LABELS
    t._current_mode = lambda: "manual"
    t._m_resume_cb = _Box("Refine / resume existing measurement (-r)")
    t._resume_cb = t._m_resume_cb
    t._log = _Log()
    t._sound = None
    t.shown = []
    t._say_on_screen = lambda title, body: t.shown.append((title, body))
    return t


def _blocked(tmp_path, recorded, code, name="chart.ti3", **kw):
    from ui.tabs.tab_measure import TabMeasure
    ti3 = _cond(_ti3(tmp_path / name, **kw), recorded)
    t = _resume_tab(ti3, code)
    return TabMeasure._blocked_by_a_differing_condition(t), t


@pytest.mark.parametrize("recorded,code", [
    ("M1", None), ("M1", "u"), ("M1", "n"), ("M2", "5"), ("M0", None),
    ("M1", "6"), ("M3", "5")])
def test_s_a1_a_resume_under_another_condition_is_refused(tmp_path, recorded,
                                                          code):
    blocked, t = _blocked(tmp_path, recorded, code)
    assert blocked
    (title, body), = t.shown
    from workflow.measurement_condition import (FILTER_CONDITIONS,
                                                condition_name)
    assert condition_name(recorded) in body
    setting = {"M0": "None (M0)", "M1": "D50 (M1)", "M2": "UV Cut (M2)",
               "M3": "Polarizing (M3)"}[recorded]
    assert f"“{setting}”" in body
    if code is None:
        assert "switched off" in body
    elif FILTER_CONDITIONS.get(code):
        assert condition_name(FILTER_CONDITIONS[code]) in body
    else:
        assert "D65" in body and "no measurement condition" in body
    assert "Refine / resume existing measurement (-r)" in body
    assert "{" not in body and EM_DASH not in body and EM_DASH not in title
    assert t._log.lines and title in t._log.lines[0]


@pytest.mark.parametrize("recorded,code", [
    ("M1", "5"), ("M2", "u"), ("M0", "n"), ("M3", "p"),
    (None, "5"), (None, None), (None, "u")])
def test_s_a1_the_same_condition_or_none_recorded_is_not_refused(
        tmp_path, recorded, code):
    blocked, t = _blocked(tmp_path, recorded, code)
    assert not blocked and not t.shown


def test_s_a1_an_imported_m1_measurement_is_refused_alike(tmp_path):
    """An i1Profiler import records its condition the same way."""
    p = _ti3(tmp_path / "chart.ti3", condition="M1")
    text = p.read_text(encoding="utf-8").replace(
        'TARGET_INSTRUMENT', 'CHROMIQ_I1P_INSTRUMENT "i1Pro 3"\n'
        'TARGET_INSTRUMENT', 1)
    p.write_text(text, encoding="utf-8")
    from ui.tabs.tab_measure import TabMeasure
    t = _resume_tab(p, None)
    assert TabMeasure._blocked_by_a_differing_condition(t)
    t = _resume_tab(p, "5")
    assert not TabMeasure._blocked_by_a_differing_condition(t)


def test_s_a1_nothing_to_continue_is_never_refused(tmp_path):
    from ui.tabs.tab_measure import TabMeasure
    t = _resume_tab(None, None)
    assert not TabMeasure._blocked_by_a_differing_condition(t)


def test_s_a1_the_check_runs_before_anything_is_touched():
    """Beside the layout check: before the calibration, the archive, the
    staging and the replace question."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._on_start)
    i = src.index("self._blocked_by_a_differing_condition()")
    assert src.index("self._blocked_by_a_misfitting_measurement()") < i
    for later in ("self._confirm_replacing_measurement()",
                  "self._log.clear()", "self._run_cr30_calibration()",
                  "self._stage_verification_for_resume()",
                  "self._archive_measurement_before_replacing()"):
        assert i < src.index(later), later


def test_s_a1_a_resume_onto_an_unrecorded_file_records_nothing():
    """Allowed; the filter is dropped before the session ends, so the stamp
    at the end writes nothing, and the log says why."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._on_start)
    i = src.index("self._resumes_unrecorded_condition(")
    assert src.index("self._session_filter = filter_code_from_args(") < i
    assert i < src.index("self._ti3_mtime_before = (")
    block = src[i:src.index("self._ti3_mtime_before = (")]
    assert "resume_condition_unrecorded_line" in block
    assert "self._session_filter = None" in block
    assert 'getattr(params, "resume", False)' in src[i - 200:i]


def test_s_a1_unrecorded_is_told_apart(tmp_path):
    from ui.tabs.tab_measure import TabMeasure
    t = SimpleNamespace()
    none = _ti3(tmp_path / "none.ti3")
    m1 = _cond(_ti3(tmp_path / "m1.ti3"), "M1")
    assert TabMeasure._resumes_unrecorded_condition(t, none)
    assert not TabMeasure._resumes_unrecorded_condition(t, m1)
    assert not TabMeasure._resumes_unrecorded_condition(t, tmp_path / "x.ti3")
    assert not TabMeasure._resumes_unrecorded_condition(t, None)


def test_s_a1_the_log_line_says_why():
    from workflow.measurement_messages import \
        resume_condition_unrecorded_line
    line = resume_condition_unrecorded_line("D50 (M1)")
    assert line.startswith("[NOTE]")
    assert "does not record" in line and "D50 (M1)" in line
    assert EM_DASH not in line


# ---------------------------------------------------------------------------
# S-A3: "not recorded" against M1/M2/M3 is a question
# ---------------------------------------------------------------------------

def test_s_a3_the_rule():
    from workflow.ti3_merge import condition_unrecorded, conditions_clash
    assert conditions_clash("M1", "M2") and conditions_clash("M0", "M1")
    for a, b in (("M1", ""), ("", "M2"), ("", "M3"), ("", ""), ("M0", ""),
                 ("M1", "M1")):
        assert not conditions_clash(a, b), (a, b)
    for a, b in (("M1", ""), ("", "M2"), ("M3", "")):
        assert condition_unrecorded(a, b), (a, b)
    for a, b in (("M0", ""), ("", ""), ("M1", "M2"), ("M1", "M1")):
        assert not condition_unrecorded(a, b), (a, b)


def test_s_a3_the_check_over_several_files(tmp_path):
    from workflow.ti3_merge import condition_check
    a = _cond(_ti3(tmp_path / "a.ti3"), "M1")
    b = _ti3(tmp_path / "b.ti3")
    c = _cond(_ti3(tmp_path / "c.ti3"), "M2")
    d = _cond(_ti3(tmp_path / "d.ti3"), "M1")
    chk = condition_check([b, a, c])
    assert chk.clash is not None and not chk.asks
    assert [p.name for p, _ in chk.clash] == ["a.ti3", "c.ti3"]
    chk = condition_check([b, a, d])
    assert chk.clash is None and chk.asks and chk.recorded == "M1"
    assert chk.common == "" and [p.name for p in chk.unrecorded] == ["b.ti3"]
    assert ("b.ti3", "not recorded") in chk.lines()
    chk = condition_check([a, d])
    assert not chk.asks and chk.common == "M1"
    chk = condition_check([b, _cond(_ti3(tmp_path / "e.ti3"), "M0")])
    assert not chk.asks and chk.clash is None


def test_s_a3_the_refusal_never_asks_to_match_not_recorded():
    from workflow import measurement_messages as M
    for msg in (M.M_MERGE_CONDITION, M.M_MERGE_CONDITION_TOOLS,
                M.M_AVERAGE_CONDITION):
        assert "Not recorded" not in msg.body
        assert "not recorded" not in msg.body
        assert EM_DASH not in msg.body + msg.title
        assert not msg.approved


def test_s_a3_the_question_explains_and_offers_both_answers():
    from workflow import measurement_messages as M
    for kind, yes, no in (("build", "Merge them", "Don't merge"),
                          ("merge", "Merge them", "Don't merge"),
                          ("average", "Average them", "Don't average"),
                          ("average_tool", "Average them", "Don't average")):
        title, body, y, n = M.condition_ask(
            kind, [("pre.ti3", "not recorded"),
                   ("chart.ti3", "M1 (daylight with UV, D50)")],
            "M1 (daylight with UV, D50)", read="read2.ti3")
        assert (y, n) == (yes, no)
        assert "'pre.ti3': not recorded" in body
        assert "ChromIQ 4.3.22 or older" in body
        assert "same setting" in body
        assert "{" not in body and EM_DASH not in body + title
    _t, body, _y, _n = M.condition_ask("build", [], "M1")
    assert "built from the new measurement only" in body
    _t, body, _y, _n = M.condition_ask("average", [], "M1", read="read2.ti3")
    assert "read2.ti3" in body
    for mid in ("M-MERGE-CONDITION-ASK", "M-AVERAGE-CONDITION-ASK",
                "M-CONDITION-ASK-PARTS", "M-CONDITION-NOT-ASKED",
                "M-AVERAGE-CONDITION", "M-RESUME-CONDITION",
                "M-RESUME-CONDITION-PARTS"):
        assert mid in M.CATALOGUE and mid in M.PROPOSED, mid


def test_s_a3_the_question_defaults_to_dont(qapp, monkeypatch):
    """A window closed without an answer merges nothing."""
    from PyQt6.QtWidgets import QMessageBox
    from ui.widgets import ask_condition_question
    seen = {}

    def _exec(box):
        seen["default"] = box.defaultButton().text()
        seen["escape"] = box.escapeButton().text()
        return 0
    monkeypatch.setattr(QMessageBox, "exec", _exec)
    assert ask_condition_question(None, "T", "B", "Merge them",
                                  "Don't merge") is False
    assert seen == {"default": "Don't merge", "escape": "Don't merge"}


def test_s_a3_without_a_yes_nothing_is_merged(tmp_path):
    """The default of both merges is "Don't merge", so a caller that cannot
    ask (none exists today) gets that, with a [NOTE] line as the message."""
    from workflow.ti3_merge import (Ti3MergeConditionUnrecorded,
                                    merge_measurements, merge_preconditioning)
    fresh = _cond(_ti3(tmp_path / "chart.ti3"), "M1")
    pre = _ti3(tmp_path / "preconditioning.ti3")
    out = tmp_path / "merged.ti3"
    with pytest.raises(Ti3MergeConditionUnrecorded) as exc:
        merge_preconditioning(fresh, pre, out)
    assert exc.value.message.startswith("[NOTE]")
    assert "preconditioning.ti3" in exc.value.message
    with pytest.raises(Ti3MergeConditionUnrecorded):
        merge_measurements([pre, fresh], out)
    assert not out.exists()


ARGYLL = Path("/Applications/Argyll/bin")
needs_argyll = pytest.mark.skipif(not (ARGYLL / "average").exists(),
                                  reason="ArgyllCMS average not installed")


@needs_argyll
def test_s_a3_with_a_yes_they_are_merged(tmp_path):
    from workflow.ti3_merge import merge_measurements, merge_preconditioning
    fresh = _cond(_ti3(tmp_path / "chart.ti3"), "M1")
    pre = _ti3(tmp_path / "preconditioning.ti3")
    out = tmp_path / "merged.ti3"
    assert merge_preconditioning(fresh, pre, out, bin_dir=ARGYLL,
                                 merge_unrecorded=True) == 4
    assert out.is_file()
    out2 = tmp_path / "tools.ti3"
    assert merge_measurements([pre, fresh], out2, bin_dir=ARGYLL,
                              merge_unrecorded=True) == 4


class _ProfileStandIn:
    def __init__(self, fresh, pre, answer):
        self._settings = {"argyll_bin_path": str(ARGYLL)}
        self._log = _Log()
        self.asked = []
        self.failures = []
        self._plan = (fresh, pre, fresh.parent / "merged.ti3")
        self._answer = answer

    def _preconditioning_merge_plan(self, params):
        return self._plan

    def _ask_merge_unrecorded_condition(self, check):
        self.asked.append(check)
        return self._answer

    def _show_tool_failure_dialog(self, title, body):
        self.failures.append((title, body))


def _apply(tmp_path, fresh_cond, pre_cond, answer, monkeypatch):
    import ui.tabs.tab_profile as TP
    calls = []

    def _merge(fresh, src, merged, bin_dir=None, *, merge_unrecorded=False):
        # The real checks, without running ArgyllCMS.
        from workflow.ti3_merge import Ti3MergeError, merge_refusal
        calls.append(merge_unrecorded)
        refusal = merge_refusal(fresh, src)
        if refusal:
            raise Ti3MergeError(refusal)
        return 4
    monkeypatch.setattr(TP, "merge_preconditioning", _merge)
    fresh = _cond(_ti3(tmp_path / "chart.ti3"), fresh_cond)
    pre = _cond(_ti3(tmp_path / "preconditioning.ti3"), pre_cond)
    t = _ProfileStandIn(fresh, pre, answer)
    params = SimpleNamespace(ti3_path=fresh)
    monkeypatch.setattr(TP, "replace", lambda p, **kw: ("merged", kw))
    result = TP.TabProfile._apply_preconditioning_merge(t, params)
    return t, calls, result, params


def test_s_a3_build_merge_them(tmp_path, monkeypatch):
    t, calls, result, params = _apply(tmp_path, "M1", None, True, monkeypatch)
    assert len(t.asked) == 1 and calls == [True]
    assert result[0] == "merged" and not t.failures


def test_s_a3_build_dont_merge_builds_from_the_new_one(tmp_path, monkeypatch):
    t, calls, result, params = _apply(tmp_path, None, "M2", False, monkeypatch)
    assert len(t.asked) == 1 and calls == [] and result is params
    assert any("not merged" in s for s in t._log.lines)
    assert not t.failures


def test_s_a3_build_two_recorded_conditions_are_refused_unasked(
        tmp_path, monkeypatch):
    t, calls, result, params = _apply(tmp_path, "M1", "M2", True, monkeypatch)
    assert t.asked == [] and calls == [False] and result is params
    (title, body), = t.failures
    assert "M1" in body and "M2" in body and "not recorded" not in body


def test_s_a3_build_m0_and_unrecorded_merges_unasked(tmp_path, monkeypatch):
    t, calls, result, params = _apply(tmp_path, "M0", None, False, monkeypatch)
    assert t.asked == [] and calls == [False] and result[0] == "merged"


def test_s_a3_the_command_box_says_the_build_asks():
    from ui.tabs.tab_profile import TabProfile
    src = inspect.getsource(TabProfile._colprof_commands_text)
    assert "merge_asks(" in src and "asks before it" in src


def _tools_dialog(qapp, cls, *args):
    from core.settings import AppSettings
    return cls(*args, AppSettings())


def _set_output(dlg, folder, name):
    dlg._output._name_edit.setText(name)
    out = dlg._output
    for attr in ("_dir_edit", "_folder_edit", "_path_edit"):
        w = getattr(out, attr, None)
        if w is not None:
            w.setText(str(folder))
            break
    else:
        pytest.skip("output row has no folder field")


def test_s_a3_tools_merge_asks_and_dont_writes_nothing(qapp, tmp_path,
                                                       monkeypatch):
    import ui.dialogs.tools_dialogs as TD
    a = _cond(_ti3(tmp_path / "a.ti3"), "M1")
    b = _ti3(tmp_path / "b.ti3")
    dlg = _tools_dialog(qapp, TD.MergeMeasurementsDialog)
    _set_output(dlg, tmp_path, "out")
    if dlg._output.directory is None:
        pytest.skip("output folder not settable here")
    dlg._primary, dlg._additional = a, [b]
    asked = []
    monkeypatch.setattr(TD, "_ask_unrecorded_condition",
                        lambda parent, kind, chk: asked.append(kind) or False)
    dlg._execute()
    assert asked == ["merge"]
    assert not (Path(dlg._output.directory) / "out.ti3").exists()
    assert "Nothing was merged" in dlg._log.toPlainText()


def test_s_a2_tools_average_refuses_and_asks(qapp, tmp_path, monkeypatch):
    import ui.dialogs.tools_dialogs as TD
    from core.argyll_runner import ArgyllRunner
    a = _cond(_ti3(tmp_path / "a.ti3"), "M1")
    b = _cond(_ti3(tmp_path / "b.ti3"), "M2")
    c = _ti3(tmp_path / "c.ti3")
    from core.settings import AppSettings
    dlg = TD.AverageMeasurementsDialog(ArgyllRunner(AppSettings()),
                                       AppSettings())
    _set_output(dlg, tmp_path, "avg")
    if dlg._output.directory is None:
        pytest.skip("output folder not settable here")
    ran = []
    monkeypatch.setattr(dlg._avg_runner, "run",
                        lambda *a, **k: ran.append(a))
    asked = []
    monkeypatch.setattr(TD, "_ask_unrecorded_condition",
                        lambda parent, kind, chk: asked.append(kind) or False)
    dlg._inputs = [a, b]
    dlg._execute()
    assert ran == [] and asked == []
    log = dlg._log.toPlainText()
    assert "[ERROR]" in log and "not averaged" in log and "M2" in log
    dlg._inputs = [c, a]
    dlg._execute()
    assert ran == [] and asked == ["average_tool"]
    assert "Nothing was averaged" in dlg._log.toPlainText()


# ---------------------------------------------------------------------------
# S-A2: the Measure tab's averaging
# ---------------------------------------------------------------------------

class _Runner:
    def __init__(self):
        self.ran = []

    def run(self, params, on_line=None, on_finish=None):
        self.ran.append(params)


class _Sig:
    def __init__(self):
        self.sent = []

    def emit(self, *a):
        self.sent.append(a)


def _measure_stand_in(run_dir, answer):
    from ui.tabs.tab_measure import TabMeasure
    t = SimpleNamespace()
    t._log = _Log()
    t._on_log_line = lambda line: None
    t._avg_runner = _Runner()
    t.asked = []
    t._ask_average_unrecorded = lambda chk, reads: t.asked.append(chk) or answer
    t.failed = []
    t._show_average_failed_dialog = lambda d: t.failed.append(d)
    t._save_confirmed_memory = lambda p: None
    t.measure_finished = _Sig()
    t._put_the_last_read_back = \
        lambda out: TabMeasure._put_the_last_read_back(t, out)
    t._average_not_made = \
        lambda out, chk: TabMeasure._average_not_made(t, out, chk)
    return t


def _reads(tmp_path, *conds):
    from core.file_manager import Run
    run = tmp_path / "runs" / "run1"
    (run / "reads").mkdir(parents=True)
    reads = []
    for i, c in enumerate(conds, 1):
        reads.append(_cond(_ti3(run / "reads" / f"read{i}.ti3"), c))
    return Run.for_dir(run), reads


def test_s_a2_two_recorded_conditions_are_not_averaged(tmp_path):
    from ui.tabs.tab_measure import TabMeasure
    run, reads = _reads(tmp_path, "M1", "M2")
    t = _measure_stand_in(run, True)
    TabMeasure._run_average_and_proceed(t, run.measurement_ti3, reads, "mean")
    assert t._avg_runner.ran == [] and t.asked == []
    assert t.failed and "M2" in t.failed[0] and "not averaged" in t.failed[0]
    # The last read is the run's measurement, as when `average` refuses.
    assert run.measurement_ti3.read_bytes() == reads[-1].read_bytes()
    assert t.measure_finished.sent == [(run.measurement_ti3,)]


def test_s_a2_unrecorded_beside_m1_is_asked(tmp_path):
    from ui.tabs.tab_measure import TabMeasure
    run, reads = _reads(tmp_path, None, "M1")
    t = _measure_stand_in(run, False)
    TabMeasure._run_average_and_proceed(t, run.measurement_ti3, reads, "mean")
    assert len(t.asked) == 1 and t._avg_runner.ran == [] and not t.failed
    assert any("not averaged, as chosen" in s for s in t._log.lines)
    assert run.measurement_ti3.is_file()
    run2, reads2 = _reads(tmp_path / "b", None, "M1")
    t = _measure_stand_in(run2, True)
    TabMeasure._run_average_and_proceed(t, run2.measurement_ti3, reads2,
                                        "mean")
    assert len(t.asked) == 1 and len(t._avg_runner.ran) == 1


def test_s_a2_the_same_or_m0_beside_none_is_averaged_unasked(tmp_path):
    from ui.tabs.tab_measure import TabMeasure
    for i, conds in enumerate((("M1", "M1"), (None, "M0"), (None, None))):
        run, reads = _reads(tmp_path / str(i), *conds)
        t = _measure_stand_in(run, False)
        TabMeasure._run_average_and_proceed(t, run.measurement_ti3, reads,
                                            "mean")
        assert t.asked == [] and len(t._avg_runner.ran) == 1, conds


def test_s_a2_the_result_keeps_the_common_condition_or_none(tmp_path):
    from workflow.measurement_condition import read_condition
    from workflow.ti3_merge import condition_check, settle_combined_condition
    a = _cond(_ti3(tmp_path / "a.ti3"), "M1")
    b = _cond(_ti3(tmp_path / "b.ti3"), "M1")
    n = _ti3(tmp_path / "n.ti3")
    out = _cond(_ti3(tmp_path / "out.ti3"), "M1")
    settle_combined_condition(out, condition_check([a, b]))
    assert read_condition(out) == "M1"
    # "Average them" on a not-recorded pair: `average` copied the first
    # file's M1, and the result records nothing.
    before = out.read_bytes().split(b"BEGIN_DATA_FORMAT", 1)[1]
    settle_combined_condition(out, condition_check([a, n]))
    assert read_condition(out) is None
    assert b"MEASUREMENT_CONDITION" not in out.read_bytes()
    assert out.read_bytes().split(b"BEGIN_DATA_FORMAT", 1)[1] == before


def test_s_a2_the_result_is_settled_before_the_yellow_memory():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._run_average_and_proceed)
    assert src.index("settle_combined_condition(result, check)") < \
        src.index("self._save_confirmed_memory(result)")
    assert src.index("condition_check(reads)") < \
        src.index("self._avg_runner.run(")


@needs_argyll
def test_s_a2_argyll_average_keeps_the_first_files_condition(tmp_path):
    """Why the result is settled: `average` copies the first file's
    header (measured on ArgyllCMS 3.5.0)."""
    import subprocess
    from workflow.measurement_condition import read_condition
    a = _cond(_ti3(tmp_path / "a.ti3"), "M1")
    b = _ti3(tmp_path / "b.ti3")
    out = tmp_path / "o.ti3"
    subprocess.run([str(ARGYLL / "average"), str(a), str(b), str(out)],
                   capture_output=True, timeout=120, check=True)
    assert read_condition(out) == "M1"


def test_s_a2_clear_condition_crlf(tmp_path):
    from workflow.measurement_condition import clear_condition, read_condition
    p = _cond(_ti3(tmp_path / "c.ti3", crlf=True), "M2")
    assert read_condition(p) == "M2"
    assert clear_condition(p)
    assert read_condition(p) is None
    assert b"\r\n" in p.read_bytes() and b"\n\n" not in p.read_bytes()
    assert not clear_condition(p)


# ---------------------------------------------------------------------------
# M-A1: two specific i1Pro names are two instruments
# ---------------------------------------------------------------------------

def _scope(*instruments):
    from tests.test_4323_review_r1 import _scope_warnings
    return _scope_warnings(*instruments)


def test_m_a1_i1pro2_against_i1pro3_is_flagged():
    w = _scope("X-Rite i1 Pro 3", "X-Rite i1 Pro 3", "i1Pro 2")
    assert len(w) == 1 and [r["instrument"] for r in w[0]["runs"]] == \
        ["i1Pro 2"]


def test_m_a1_the_generic_name_goes_with_the_specific_one():
    assert _scope("GretagMacbeth i1 Pro", "X-Rite i1 Pro 3") == []
    assert _scope("GretagMacbeth i1 Pro", "GretagMacbeth i1 Pro",
                  "i1Pro 2") == []
    w = _scope("GretagMacbeth i1 Pro", "X-Rite i1 Pro 3", "X-Rite i1 Pro 3",
               "X-Rite i1 Pro 2")
    assert len(w) == 1 and [r["instrument"] for r in w[0]["runs"]] == \
        ["X-Rite i1 Pro 2"]


# ---------------------------------------------------------------------------
# M-A2: the FWA tooltip of a chartread M1/M2/M3
# ---------------------------------------------------------------------------

def test_m_a2_a_chartread_m1_is_told_to_set_minus_f_to_none(tmp_path):
    from workflow.fwa_gate import fwa_refusal_for_file
    for cond in ("M1", "M2", "M3"):
        p = _cond(_ti3(tmp_path / f"{cond}.ti3"), cond)
        reason = fwa_refusal_for_file(p).reason
        assert "“Spectral filter type (-F)”" in reason
        assert "“None (M0)”" in reason and "switched off" in reason
        assert ".mxf" not in reason and EM_DASH not in reason


def test_m_a2_an_import_is_still_told_to_import_m0(tmp_path):
    from workflow.fwa_gate import fwa_refusal
    r = fwa_refusal("X-Rite i1 Pro 3", condition="M1", i1p_import=True)
    assert ".mxf" in r.reason and "Spectral filter type" not in r.reason


def test_m_a2_m3_has_its_own_sentence():
    from workflow.fwa_gate import fwa_refusal
    m3 = fwa_refusal("X-Rite i1 Pro 3", condition="M3").reason
    assert "polarising filter" in m3 and "M1 readings" not in m3
    m1 = fwa_refusal("X-Rite i1 Pro 3", condition="M1").reason
    assert "polarising" not in m1 and "M1 readings" in m1
