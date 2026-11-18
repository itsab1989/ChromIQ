"""X-Rite i1Pro 3 and i1Pro 2: keep M0, M1 and M2 from every scan (Preferences > Beta):
verifications (Basti, 2026-11-15, ruling 2).

* A verification keeps all three conditions too. Its pair lives in ONE
  folder for the whole run, ``verifications/conditions/``, named by the hash
  of the readings, so filing a read into its dated folder, a Replace or a
  restore needs no code of its own (`Run.condition_dir_of`).
* A verification of a run whose profile was built from another condition is
  judged in that condition, automatically, from the same readings kept in
  it, and the report says so (``report["measurement_condition"]``).
* Without readings in that condition, the rows that compare the sheet with
  the profile read N-A with the reason, and Row B is never computed across
  two conditions.
* With the Beta off nothing of this happens: the report is today's.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.file_manager import Run
from workflow import i1pro3_conditions as C
from workflow import measurement_report as MR

TI3 = """CTI3
DESCRIPTOR "x"
TARGET_INSTRUMENT "X-Rite i1 Pro 3"
{head}
NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT
NUMBER_OF_SETS 3
BEGIN_DATA
1 "A1" 100 100 100 {w} {w} {w}
2 "A2" 0 0 0 2 2 2
3 "A3" 100 0 0 40 20 5
END_DATA
"""


#: A main file records the condition it was measured in (the Measure tab
#: does so at the end of every session, R4); one that records none is the
#: case of review F1 (tests/test_i1pro3_conditions_review_fixes.py).
RECORDED_M0 = 'KEYWORD "MEASUREMENT_CONDITION"\nMEASUREMENT_CONDITION "M0"'


def _ti3(p: Path, w="85", head=RECORDED_M0) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(TI3.format(w=w, head=head), encoding="latin-1")
    return p


def _pair(main: Path, cond: str, w: str) -> Path:
    h = C.data_block_hash(main)
    dst = Run.for_dir(main.parent).condition_ti3(cond, measurement=main)
    return _ti3(dst, w=w, head=(
        f'KEYWORD "MEASUREMENT_CONDITION"\nMEASUREMENT_CONDITION "{cond}"\n'
        f'KEYWORD "CHROMIQ_CONDITION_OF"\nCHROMIQ_CONDITION_OF "{h}"'))


def _run(tmp_path, built_from="M1") -> Run:
    run = Run.for_dir(tmp_path / "Paper" / "runs" / "run1")
    run.dir.mkdir(parents=True)
    run.save_meta(run.load_meta())
    if built_from:
        run.record_profile_build({"builder": "colprof",
                                  C.BUILT_FROM_KEY: built_from})
    return run


def _verification(run: Run, vid="2026-11-15_120000", w="85") -> Path:
    return _ti3(run.verifications_dir / vid / "Paper-verify.ti3", w=w)


@pytest.fixture
def beta_on(monkeypatch):
    monkeypatch.setattr(C, "beta_on", lambda: True)


# ---------------------------------------------------------------------------
# where the pair lives
# ---------------------------------------------------------------------------

def test_every_copy_of_a_measurement_finds_its_pair_in_one_place(tmp_path):
    run = Run.for_dir(tmp_path / "P" / "runs" / "run1")
    d = run.dir
    v = run.verification_condition_dir
    assert v == d / "verifications" / "conditions"
    for f, want in (
            (d / "P.ti3", d / "conditions"),
            (d / "reads" / "read1.ti3", d / "conditions"),
            (d / "old" / "2026-11-15_101010" / "P.ti3", d / "conditions"),
            (d / "verifications" / "P-verify.ti3", v),
            (d / "verifications" / "2026-11-15_120000" / "P-verify.ti3", v),
            (d / "verifications" / "2026-11-15_120000" / "reads" / "r.ti3", v),
            (d / "verifications" / "2026-11-15_120000" / "old"
             / "2026-11-15_130000" / "P-verify.ti3", v),
            (tmp_path / "loose" / "x.ti3", tmp_path / "loose" / "conditions")):
        assert Run.condition_dir_of(f) == want, f


def test_marking_a_verification_keeps_its_pair(tmp_path):
    """`mark_verification_ti3` edits the header only, so the read filed into
    its dated folder still finds the pair the engine wrote beside the chart."""
    from workflow.ti3_analysis import mark_verification_ti3
    run = _run(tmp_path)
    read = _ti3(run.verifications_dir / "Paper.ti3")
    m1 = _pair(read, "M1", "88")
    marked = mark_verification_ti3(read)
    dst = run.verification(
        "2026-11-15_120000").ensure_dir() / "Paper-verify.ti3"
    marked.replace(dst)
    assert C.condition_file(dst, "M1") == m1


# ---------------------------------------------------------------------------
# the report
# ---------------------------------------------------------------------------

def test_a_verification_is_judged_in_the_profiles_condition(tmp_path, beta_on):
    run = _run(tmp_path, "M1")
    ver = _verification(run, w="85")
    _pair(ver, "M1", "90")
    got = C.profile_readings(ver)
    assert got is not None and got.verification and got.condition == "M1"
    rep = MR.build_report(ver)
    assert rep["measurement_condition"] == {
        "condition": "M1", "profile": "M1", "own": "M0", "from_profile": True}
    # the readings are the M1 ones: the paper is the M1 paper
    m1_white = MR.measurement_facts(C.condition_file(ver, "M1"))["paper_white"]
    assert rep["paper_white"] == m1_white
    assert not MR.other_condition(rep)
    # the saved report is still recognised as this measurement's
    assert not MR.facts_disagree(rep, ver)


def test_without_readings_in_that_condition_the_profile_rows_say_why(
        tmp_path, beta_on):
    run = _run(tmp_path, "M1")
    ver = _verification(run)
    rep = MR.build_report(ver)
    assert rep["measurement_condition"]["from_profile"] is False
    assert MR.other_condition(rep)
    cref = MR.condition_reference_block(rep, ti3_path=ver, argyll_bin=None)
    assert cref["paper"]["from"] == MR.CONDITION_OTHER_CONDITION
    assert cref["solids"]["from"] == MR.CONDITION_OTHER_CONDITION
    rep["condition_reference"] = cref
    vals = MR.row_values(rep)
    for rid in ("substrate_de00_max", "solids_de00_max",
                "cmy_solids_dhab_max"):
        assert vals[rid]["reason"] == MR.REASON_PROFILE_OTHER_CONDITION, rid


def test_row_b_is_never_computed_across_two_conditions(tmp_path, beta_on):
    run = _run(tmp_path, "M1")
    first = _verification(run, "2026-11-14_120000", w="84")
    ver = _verification(run, "2026-11-15_120000", w="85")
    _pair(ver, "M1", "90")
    rep = MR.build_report(ver)
    assert rep["repeat_across_sheets"]["reason"] == \
        MR.REASON_EARLIER_OTHER_CONDITION
    # ...and with the earlier one kept in M1 too, it is compared in M1
    _pair(first, "M1", "89")
    rep = MR.build_report(ver)
    assert rep["repeat_across_sheets"]["reason"] != \
        MR.REASON_EARLIER_OTHER_CONDITION
    assert rep["repeat_across_sheets"]["compared_with"] == "2026-11-14_120000"


def test_the_profiling_measurement_itself_is_reported_as_measured(
        tmp_path, beta_on):
    run = _run(tmp_path, "M1")
    main = _ti3(run.dir / "Paper.ti3", w="85")
    _pair(main, "M1", "90")
    rep = MR.build_report(main)
    assert rep["measurement_condition"]["condition"] == "M0"
    assert rep["paper_white"] == MR.measurement_facts(main)["paper_white"]


@pytest.mark.parametrize("built_from", ["", "M0"])
def test_a_profile_in_the_measurements_own_condition_changes_nothing(
        tmp_path, beta_on, built_from):
    run = _run(tmp_path, built_from)
    ver = _verification(run)
    _pair(ver, "M1", "90")
    assert C.profile_readings(ver) is None
    assert "measurement_condition" not in MR.build_report(ver)


def test_off_the_report_is_todays(tmp_path, monkeypatch):
    """Beta off and a profile that records no condition (built with the Beta
    off, or before it): exactly 4.3.40's report."""
    monkeypatch.setattr(C, "beta_on", lambda: False)
    run = _run(tmp_path, "")
    ver = _verification(run, w="85")
    _pair(ver, "M1", "90")
    assert C.profile_readings(ver) is None
    rep = MR.build_report(ver)
    assert "measurement_condition" not in rep
    assert rep["paper_white"] == MR.measurement_facts(ver)["paper_white"]


def test_off_afterwards_still_follows_the_profiles_recorded_condition(
        tmp_path, monkeypatch):
    """Review F2: a profile built from M1 stays an M1 profile when the Beta
    is switched off afterwards. Its verification is still judged in M1 (a
    read only), and without M1 readings the report says so instead of
    comparing across two conditions."""
    monkeypatch.setattr(C, "beta_on", lambda: False)
    run = _run(tmp_path, "M1")
    ver = _verification(run, w="85")
    got = C.profile_readings(ver)
    assert got is not None and got.condition == "M1" and got.path is None
    rep = MR.build_report(ver)
    assert rep["measurement_condition"]["from_profile"] is False
    m1 = _pair(ver, "M1", "90")
    got = C.profile_readings(ver)
    assert got is not None and got.path == m1
    rep = MR.build_report(ver)
    assert rep["measurement_condition"]["condition"] == "M1"
    assert rep["paper_white"] == MR.measurement_facts(m1)["paper_white"]


def test_the_report_window_says_which_condition(tmp_path, beta_on, qapp):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    rec = {"condition": "M1", "profile": "M1", "own": "M0",
           "from_profile": True}
    html = MeasurementReportDialog._measurement_condition_html(
        MeasurementReportDialog, {"measurement_condition": rec})
    assert "M1" in html and "judged in" in html
    rec = {"condition": "M0", "profile": "M1", "own": "M0",
           "from_profile": False}
    html = MeasurementReportDialog._measurement_condition_html(
        MeasurementReportDialog, {"measurement_condition": rec})
    assert "not shown" in html
    assert MeasurementReportDialog._measurement_condition_html(
        MeasurementReportDialog, {}) == ""


# ---------------------------------------------------------------------------
# Check & Refine
# ---------------------------------------------------------------------------

class _S(dict):
    def get(self, k, d=None):
        return super().get(k, d)


def test_check_and_refine_checks_a_verification_in_the_profiles_condition(
        tmp_path, qapp):
    from types import SimpleNamespace
    from ui.tabs.tab_check_refine import TabCheckRefine
    run = _run(tmp_path, "M1")
    ver = _verification(run)
    icc = run.dir / "Paper.icc"
    icc.write_bytes(b"x")
    fake = SimpleNamespace(_settings=_S({C.SETTING: True}), _ti3_path=ver,
                           _icc_path=icc)
    assert TabCheckRefine._readings_for_the_profile(fake) is None
    assert "only M0" in TabCheckRefine._other_condition_warning(fake) or \
        "has only" in TabCheckRefine._other_condition_warning(fake)
    m1 = _pair(ver, "M1", "90")
    assert TabCheckRefine._readings_for_the_profile(fake) == m1
    assert TabCheckRefine._other_condition_warning(fake) == ""
    # review F2: with the Beta switched off afterwards the check still
    # follows the condition the profile's build recorded (a read only)
    fake._settings = _S({C.SETTING: False})
    assert TabCheckRefine._readings_for_the_profile(fake) == m1
    m1.unlink()
    assert TabCheckRefine._readings_for_the_profile(fake) is None
    assert "has only" in TabCheckRefine._other_condition_warning(fake)
    # ... and a profile that records no condition: 4.3.40's check exactly
    run.record_profile_build({"builder": "colprof"})
    assert C.profile_condition(run) == ""
    assert TabCheckRefine._readings_for_the_profile(fake) is None
    assert TabCheckRefine._other_condition_warning(fake) == ""


# ---------------------------------------------------------------------------
# housekeeping at the end of a session
# ---------------------------------------------------------------------------

def _age(p: Path, seconds=3600):
    import os
    import time
    t = time.time() - seconds
    os.utime(p, (t, t))


def test_pairs_no_measurement_holds_are_pruned_and_nothing_else(tmp_path):
    run = _run(tmp_path)
    main = _ti3(run.dir / "Paper.ti3", w="85")
    keep_main = _pair(main, "M1", "90")
    old = _ti3(run.dir / "old" / "2026-11-14_101010" / "Paper.ti3", w="80")
    keep_old = _pair(old, "M1", "84")
    read = _ti3(run.reads_dir / "read1.ti3", w="83")
    keep_read = _pair(read, "M2", "79")
    gone_main = _ti3(tmp_path / "elsewhere.ti3", w="70")
    orphan = _pair(gone_main, "M1", "75")          # loose: elsewhere/conditions
    orphan = orphan.replace(run.condition_dir / orphan.name)
    fresh = run.condition_dir / "12-0000abcd-M2.ti3"
    fresh.write_text("x", encoding="utf-8")                          # a session still writing
    stranger = run.condition_dir / "notes.txt"
    stranger.write_text("Basti's", encoding="utf-8")
    ver = _verification(run)
    keep_ver = _pair(ver, "M1", "91")
    gone_ver = _ti3(tmp_path / "elsewhere2" / "v.ti3", w="71")
    v_orphan = _pair(gone_ver, "M1", "76")
    v_orphan = v_orphan.replace(run.verification_condition_dir / v_orphan.name)
    # named like ours, but its own header does not say ChromIQ wrote it so
    lookalike = run.condition_dir / "99-0badf00d-M1.ti3"
    lookalike.write_text("x", encoding="utf-8")
    wrong_cond = run.condition_dir / orphan.name.replace("-M1.", "-M2.")
    wrong_cond.write_bytes(orphan.read_bytes())    # header says M1, name M2
    for p in (keep_main, keep_old, keep_read, orphan, stranger, keep_ver,
              v_orphan, lookalike, wrong_cond):
        _age(p)
    gone = C.prune_run(run)
    assert sorted(gone) == sorted([orphan, v_orphan])
    for p in (keep_main, keep_old, keep_read, fresh, stranger, keep_ver,
              lookalike, wrong_cond):
        assert p.is_file(), p


def test_the_measure_tab_prunes_only_with_the_beta_on(tmp_path):
    from types import SimpleNamespace
    from ui.tabs.tab_measure import TabMeasure
    run = _run(tmp_path)
    orphan = _pair(_ti3(tmp_path / "elsewhere.ti3", w="70"), "M1", "75")
    run.condition_dir.mkdir(parents=True)
    orphan = orphan.replace(run.condition_dir / orphan.name)
    _age(orphan)
    fake = SimpleNamespace(_settings=_S({C.SETTING: False}),
                           _ti1_path=run.dir / "Paper.ti1")
    TabMeasure._prune_condition_pairs(fake)
    assert orphan.is_file()
    fake._settings = _S({C.SETTING: True})
    TabMeasure._prune_condition_pairs(fake)
    assert not orphan.exists()
