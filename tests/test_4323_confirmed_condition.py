"""4.3.23: after "Merge them" / "Average them" the result records the KNOWN
measurement condition (Basti's ruling, 2026-11-03).

M-MERGE-CONDITION-ASK and M-AVERAGE-CONDITION-ASK are asked when one
measurement records M1, M2 or M3 and another records nothing. Answering
"Merge them" / "Average them" is the person confirming that both were
measured the same way, so the merged or averaged file records the condition
the recorded file names, in the header only, in either order of the files.
Before, ArgyllCMS ``average`` copied the FIRST file's header, so the result
named whatever the first file had, or nothing, and FWA compensation could be
allowed on data that really is M1 or M2.

Every path that asks: the Build Profile pre-conditioning merge, Tools ▸
Merge measurements, the Measure tab's averaging of reads and Tools ▸ Average
measurements.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.test_4323_review_r1 import _ti3
from tests.test_4323_review_r2a import (ARGYLL, _cond, _Log,
                                        _measure_stand_in, _ProfileStandIn,
                                        _reads, _set_output, _Sig,
                                        needs_argyll)

#: (first file's condition, second file's condition): both orders.
ORDERS = [("M1", None), (None, "M1"), ("M2", None), (None, "M2")]


def _known(a, b):
    return a or b


def _fwa_refused_for(path, condition):
    """FWA is refused for *path* because of its condition (M1/M2)."""
    from workflow.fwa_gate import fwa_refusal_for_file
    refusal = fwa_refusal_for_file(path)
    assert refusal is not None and refusal.kind == "condition"
    assert refusal.condition == condition


def _data_of(path):
    return Path(path).read_bytes().split(b"BEGIN_DATA_FORMAT", 1)[1]


# ---------------------------------------------------------------------------
# The rule itself
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("first,second", ORDERS)
def test_a_confirmed_pair_records_the_known_condition(tmp_path, first,
                                                      second):
    from workflow.measurement_condition import read_condition
    from workflow.ti3_merge import condition_check, settle_combined_condition
    a = _cond(_ti3(tmp_path / "a.ti3"), first)
    b = _cond(_ti3(tmp_path / "b.ti3"), second)
    # What `average` leaves: the first file's header.
    out = tmp_path / "out.ti3"
    shutil.copyfile(a, out)
    before = _data_of(out)
    settle_combined_condition(out, condition_check([a, b]), confirmed=True)
    assert read_condition(out) == _known(first, second)
    assert _data_of(out) == before            # the header only
    _fwa_refused_for(out, _known(first, second))


def test_unconfirmed_or_m0_beside_none_records_nothing(tmp_path):
    """Nobody confirmed anything: a pair nobody was asked about (none beside
    M0) records nothing, as before; so does a call without the answer."""
    from workflow.measurement_condition import read_condition
    from workflow.ti3_merge import condition_check, settle_combined_condition
    m0 = _cond(_ti3(tmp_path / "m0.ti3"), "M0")
    m1 = _cond(_ti3(tmp_path / "m1.ti3"), "M1")
    n = _ti3(tmp_path / "n.ti3")
    out = _cond(_ti3(tmp_path / "out.ti3"), "M0")
    settle_combined_condition(out, condition_check([m0, n]), confirmed=True)
    assert read_condition(out) is None
    out = _cond(_ti3(tmp_path / "out2.ti3"), "M1")
    settle_combined_condition(out, condition_check([m1, n]))
    assert read_condition(out) is None


# ---------------------------------------------------------------------------
# Build Profile: the pre-conditioning merge
# ---------------------------------------------------------------------------

@needs_argyll
@pytest.mark.parametrize("fresh_cond,pre_cond", ORDERS)
def test_build_profile_merge_them_records_the_known_condition(
        tmp_path, monkeypatch, fresh_cond, pre_cond):
    import ui.tabs.tab_profile as TP
    from workflow.measurement_condition import read_condition
    fresh = _cond(_ti3(tmp_path / "chart.ti3"), fresh_cond)
    pre = _cond(_ti3(tmp_path / "preconditioning.ti3"), pre_cond)
    t = _ProfileStandIn(fresh, pre, True)
    monkeypatch.setattr(TP, "replace", lambda p, **kw: ("merged", kw))
    result = TP.TabProfile._apply_preconditioning_merge(
        t, SimpleNamespace(ti3_path=fresh))
    assert len(t.asked) == 1 and not t.failures
    merged = result[1]["ti3_path"]
    assert read_condition(merged) == _known(fresh_cond, pre_cond)
    _fwa_refused_for(merged, _known(fresh_cond, pre_cond))
    # The inputs are untouched.
    assert read_condition(fresh) == fresh_cond
    assert read_condition(pre) == pre_cond


# ---------------------------------------------------------------------------
# Tools ▸ Merge measurements
# ---------------------------------------------------------------------------

@needs_argyll
@pytest.mark.parametrize("primary_cond,other_cond", ORDERS)
def test_tools_merge_them_records_the_known_condition(
        qapp, tmp_path, monkeypatch, primary_cond, other_cond):
    import ui.dialogs.tools_dialogs as TD
    from core.settings import AppSettings
    from workflow.measurement_condition import read_condition
    a = _cond(_ti3(tmp_path / "a.ti3"), primary_cond)
    b = _cond(_ti3(tmp_path / "b.ti3"), other_cond)
    settings = AppSettings()
    settings.set("argyll_bin_path", str(ARGYLL))
    dlg = TD.MergeMeasurementsDialog(settings)
    _set_output(dlg, tmp_path, "out")
    if dlg._output.directory is None:
        pytest.skip("output folder not settable here")
    dlg._primary, dlg._additional = a, [b]
    asked = []
    monkeypatch.setattr(TD, "_ask_unrecorded_condition",
                        lambda parent, kind, chk: asked.append(kind) or True)
    dlg._execute()
    out = Path(dlg._output.directory) / "out.ti3"
    assert asked == ["merge"] and out.is_file(), dlg._log.toPlainText()
    assert read_condition(out) == _known(primary_cond, other_cond)
    _fwa_refused_for(out, _known(primary_cond, other_cond))


# ---------------------------------------------------------------------------
# The averages: `average` itself stood in for by a copy of the first input,
# which is what it does to the header (measured on ArgyllCMS 3.5.0,
# test_s_a2_argyll_average_keeps_the_first_files_condition).
# ---------------------------------------------------------------------------

class _CopyingRunner:
    """Runs "average" at once: the output is the first input's bytes."""

    def __init__(self):
        self.ran = []

    def run(self, params, on_line=None, on_finish=None):
        self.ran.append(params)
        shutil.copyfile(params.inputs[0], params.output)
        on_finish(Path(params.output))

    def primary_failure(self):
        return None


@pytest.mark.parametrize("first,second", ORDERS)
def test_measure_tab_average_them_records_the_known_condition(
        tmp_path, first, second):
    from ui.tabs.tab_measure import TabMeasure
    from workflow.measurement_condition import read_condition
    run, reads = _reads(tmp_path, first, second)
    t = _measure_stand_in(run, True)
    t._avg_runner = _CopyingRunner()
    t.proceed_to_profile = _Sig()
    TabMeasure._run_average_and_proceed(t, run.measurement_ti3, reads, "mean")
    assert len(t.asked) == 1 and len(t._avg_runner.ran) == 1
    assert t.measure_finished.sent == [(run.measurement_ti3,)]
    assert read_condition(run.measurement_ti3) == _known(first, second)
    _fwa_refused_for(run.measurement_ti3, _known(first, second))


@pytest.mark.parametrize("first,second", ORDERS)
def test_tools_average_them_records_the_known_condition(
        qapp, tmp_path, monkeypatch, first, second):
    import ui.dialogs.tools_dialogs as TD
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from workflow.measurement_condition import read_condition
    a = _cond(_ti3(tmp_path / "a.ti3"), first)
    b = _cond(_ti3(tmp_path / "b.ti3"), second)
    dlg = TD.AverageMeasurementsDialog(ArgyllRunner(AppSettings()),
                                       AppSettings())
    _set_output(dlg, tmp_path, "avg")
    if dlg._output.directory is None:
        pytest.skip("output folder not settable here")
    runner = _CopyingRunner()
    monkeypatch.setattr(dlg._avg_runner, "run",
                        lambda p, on_line, on_finish:
                        runner.run(p, on_line, on_finish))
    asked = []
    monkeypatch.setattr(TD, "_ask_unrecorded_condition",
                        lambda parent, kind, chk: asked.append(kind) or True)
    dlg._inputs = [a, b]
    dlg._execute()
    assert asked == ["average_tool"] and len(runner.ran) == 1
    out = Path(runner.ran[0].output)
    assert read_condition(out) == _known(first, second)
    _fwa_refused_for(out, _known(first, second))
