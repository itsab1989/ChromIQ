"""K60: Knut's answers D1 to D3 in #182 5850164956 (beta 44), on a sheet
printed raw.

* **D1 (B8-1395)**: *"Whatever the text, it must be true, so you dont need to
  ask if I want to keep something that is false. Use the new sentence."* A
  single-run raw report whose limited paper or solid row read N-A opens "...;
  the paper and the solid colours are judged against the profile where the
  limit set has a limit for them and the measurement can answer them. ...".
  His "I dont know what you mean" about the plural (A4) is settled under the
  same rule: where a paper or solid row was judged, the plural opening carries
  the same clause, "against the profiles", in the form that is true (ours,
  awaiting his confirmation, B8-1403).
* **D2 (B8-1397)**: *"Accepted."* A report ACROSS RUNS with sheets printed
  both ways opens with M-REPORT-MIXED-OPENING-RUNS, verbatim.
* **D3 (B8-1398)**: *"Yes, judge them, since printing raw does not affect this
  metric."* A raw sheet's two repeatability rows are judged where the set
  limits them; the Overall word, the counts and "Judged against" follow, and
  no opening claims the paper or the solids were judged when only the
  repeatability rows were.

Every test names the mutation that turns it red; each was run red
(~/Desktop/ChromIQ-beta44-proof/k60/mutations.txt).
"""
from __future__ import annotations

import html as _html
import json
import re
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402

from workflow import compliance_sets as CS                     # noqa: E402
from workflow import measurement_messages as M                 # noqa: E402
from workflow import measurement_report as MR                  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REPEAT = ("repeat_patches_de00_max", "repeat_measurement_de00_max")

SCOPE = " The measurements it covers are listed under Report Scope."
S_RAW = ("This report follows the printer behind the profile built in "
         "{where}. Its sheets were printed without the profile, measured, and "
         "compared with the chart's own aim values")
P_RAW = ("This report follows the printers behind the profiles built in "
         "{where}. Their sheets were printed without the profiles, measured, "
         "and compared with the charts' own aim values")
#: D1, Knut's words verbatim.
S_ANSWERABLE = (S_RAW + "; the paper and the solid colours are judged "
                "against the profile where the limit set has a limit for them "
                "and the measurement can answer them." + SCOPE)
S_WHERE = (S_RAW + "; the paper and the solid colours are judged against the "
           "profile where the limit set has a limit for them." + SCOPE)
P_ALL = (P_RAW + "; the paper and the solid colours are judged against the "
         "profiles." + SCOPE)
P_WHERE = (P_RAW + "; the paper and the solid colours are judged against the "
           "profiles where the limit set has a limit for them." + SCOPE)
P_ANSWERABLE = (P_RAW + "; the paper and the solid colours are judged against "
                "the profiles where the limit set has a limit for them and the "
                "measurements can answer them." + SCOPE)
#: A4, as Knut accepted it (B8-1383).
P_PLAIN = P_RAW + "." + SCOPE


def _de() -> dict:
    return json.loads((ROOT / "data/i18n/de.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _dialog(qapp):
    from tests.test_calibration_reports import _settings
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    return MeasurementReportDialog(_settings())


def _sheet(colour="raw", run="run3", when="2026-11-16_100000", *,
           profile=True, paper=0.4, k_solid=0.5, repeat=None) -> dict:
    """A verification sheet of Demo, printed *colour*, against the design;
    its paper and solids compared with the profile when *profile*; its
    within-sheet repeatability row *repeat* (None: the chart repeats
    nothing)."""
    rep = {"is_verification": True, "sheet_kind": "verification",
           "reference_source": "design", "printing": {"colour": colour},
           "chart": "Demo-verify", "ti3": "Demo-verify.ti3",
           "created": "2026-11-16T10:00:00",
           "_origin_dir": f"/nowhere/Demo/runs/{run}/verifications/{when}",
           "de00": MR._stats([12.0 + 0.1 * i for i in range(60)])}
    if profile:
        rep["condition_reference"] = {
            "paper": {"from": MR.CONDITION_FROM_PROFILE, "de": paper},
            "solids": {"from": MR.CONDITION_FROM_PROFILE,
                       "de": {"C": 0.3, "M": 0.2, "Y": 0.1, "K": k_solid},
                       "dhab": {"C": 0.1, "M": 0.2, "Y": 0.1}}}
    if repeat is not None:
        rep["repeat_within_sheet"] = {"eligible": True, "max": repeat,
                                      "groups": 12, "pairs": 12}
    return rep


def _live(dlg, monkeypatch, set_id: str):
    """The dialog judges every column against *set_id*, live."""
    from types import SimpleNamespace
    name = CS.set_label(set_id)
    got = SimpleNamespace(limits=CS.effective_limits(set_id, {}),
                          set_id=set_id, set_label=name, label_en=name,
                          edited=False)
    monkeypatch.setattr(type(dlg), "_limits_for", lambda self, r: got)


def _opening(dlg, monkeypatch, set_id, runs):
    _live(dlg, monkeypatch, set_id)
    monkeypatch.setattr(type(dlg), "_report_kind",
                        lambda self, runs: "verification")
    return dlg._what_this_report_judges(runs)


# --------------------------------------------------------------------------
# D3: the repeatability rows of a raw sheet are judged
# --------------------------------------------------------------------------
@pytest.mark.parametrize("value,word", [(0.4, CS.PASS), (2.6, CS.FAIL)])
def test_a_raw_sheet_judges_its_repeatability_rows(value, word):
    """ChromIQ default limits the within-sheet repeatability row at 2.0 and
    puts "–" on the paper and solids: a raw sheet's repeatability row reads
    PASS or FAIL like on any other sheet, and the stored verdict is graded,
    its Overall word and counts about that row. Where the set does not limit
    it, the row stays out of the verdict (a "–" row is not in the report).

    MUTATION, proven red: drop ``graded=_repeat_graded`` from the
    within-sheet row in `row_values` (the row reads INFO, Overall INFO)."""
    rep = _sheet(repeat=value)
    lim = CS.effective_limits("chromiq_default", {})
    MR.stamp_verdict(rep, lim, set_id="chromiq_default", set_label="d")
    rows = {r["row_id"]: r for r in rep["verdict"]["rows"]}
    assert rows["repeat_patches_de00_max"]["word"] == word
    assert rows["all_de00_avg"]["word"] == CS.INFO
    v = rep["verdict"]
    assert v["graded"] is True and v["overall"] == word, v
    assert v["summary"]["checked"] == 1, v["summary"]
    assert v["summary"]["failed"] == (1 if word == CS.FAIL else 0)
    assert v["summary"]["reason"] != M.M_REPORT_RAW_OVERALL.body


def test_the_same_sheet_printed_through_the_profile_is_unchanged():
    """D3 changes a raw sheet only: a sheet printed through its profile was
    judged on every row already, and a profiling sheet is never judged.

    MUTATION, proven red: set ``graded=True`` on the repeatability rows
    whatever the sheet (the profiling sheet's row reads PASS)."""
    lim = CS.effective_limits("chromiq_default", {})
    through = _sheet("through-profile", repeat=0.4)
    MR.stamp_verdict(through, lim, set_id="chromiq_default", set_label="d")
    words = {r["row_id"]: r["word"] for r in through["verdict"]["rows"]}
    assert words["repeat_patches_de00_max"] == CS.PASS
    prof = dict(_sheet(repeat=0.4), is_verification=False,
                sheet_kind="profiling")
    MR.stamp_verdict(prof, lim, set_id="chromiq_default", set_label="d")
    words = {r["row_id"]: r["word"] for r in prof["verdict"]["rows"]}
    assert words["repeat_patches_de00_max"] == CS.INFO


def test_the_window_follows_overall_counts_and_judged_against(qapp,
                                                              monkeypatch):
    """In the window: the repeatability cell reads FAIL, the Overall word
    FAIL, "Judged against" names the set "(printed raw)" rather than "not
    judged", no raw print note on the repeatability row, and the sentence
    under the results is not the one that says the values are all shown for
    information (M-REPORT-RAW-RESULTS).

    MUTATION, proven red: count only `ROWS_JUDGED_ON_A_RAW_PRINT` in
    `drift_check_judges` (the column reads "not judged (printed raw)" and
    Overall INFO beside a FAIL)."""
    dlg = _dialog(qapp)
    try:
        _live(dlg, monkeypatch, "chromiq_default")
        rep = dict(_sheet(repeat=2.6), _fresh=True)
        rows, _rec = dlg._verdict_rows(rep)
        rp = [x for x in rows if x["row_id"] == "repeat_patches_de00_max"]
        assert rp and rp[0]["word"] == CS.FAIL
        assert MR.NOTE_RAW_PRINT_INFO not in (rp[0].get("notes") or ())
        assert dlg._column_summary(rep).word == CS.FAIL
        cell = _html.unescape(dlg._thresholds_cell(rep))
        assert "(printed raw)" in cell
        assert M.M_REPORT_RAW_NOT_JUDGED.body not in cell
        html = dlg._report_results_html([rep])
        assert _html.escape(M.M_REPORT_RAW_RESULTS.body) not in html
        assert _html.escape(M.M_REPORT_RAW_RESULTS_JUDGED.body) not in html
        assert _html.escape(M.M_REPORT_RAW_RESULTS_SOME.body) in html
    finally:
        dlg.deleteLater()


def test_openings_do_not_claim_the_paper_or_solids_for_repeatability_alone(
        qapp, monkeypatch):
    """A raw column that judged only its repeatability rows: the plural
    opening stays as Knut accepted it (no judged clause); the singular one
    is his conditional form, which ChromIQ's own sets were given in K59
    (every limited paper and solid row judged; none is limited). Neither is
    the plain clause, and none says "the measurements can answer them".

    MUTATION, proven red: decide the plural clause with `_drift_judges`
    (any judged row) instead of `_raw_paper_or_solids_judged` (the plural
    opening claims the paper and solids)."""
    dlg = _dialog(qapp)
    try:
        runs = [_sheet(run="run1", repeat=0.4), _sheet(run="run3", repeat=0.4)]
        said = _opening(dlg, monkeypatch, "chromiq_default", runs)
        assert said == P_PLAIN.format(where="Demo, run 1; Demo, run 3"), said
        runs = [_sheet(repeat=0.4),
                _sheet(when="2026-11-23_100000", repeat=0.4)]
        said = _opening(dlg, monkeypatch, "chromiq_default", runs)
        assert said == S_WHERE.format(where="Demo, run 3"), said
    finally:
        dlg.deleteLater()


def test_a_saved_raw_sheet_with_an_ungraded_repeat_row_is_worked_out_again():
    """A raw sheet saved before D3 kept a limited repeatability row as INFO;
    this version judges it, so Report Scope says an earlier version worked
    it out (M-REPORT-WORKED-OUT-EARLIER), as K51 did for the paper row.

    MUTATION, proven red: drop the D3 block of `_worked_out_differently`."""
    from ui.dialogs.measurement_report_dialog import _worked_out_differently
    lim = CS.effective_limits("chromiq_default", {})
    now = _sheet(repeat=0.4)
    MR.stamp_verdict(now, lim, set_id="chromiq_default", set_label="d")
    saved = json.loads(json.dumps(now))
    for r in saved["verdict"]["rows"]:
        if r["row_id"] in REPEAT:
            r["word"] = CS.INFO
    saved["verdict"]["graded"] = False
    assert _worked_out_differently(saved, now)
    assert not _worked_out_differently(json.loads(json.dumps(now)), now)


# --------------------------------------------------------------------------
# D1: the singular opening where a limited row read N-A, and the plural
# --------------------------------------------------------------------------
def test_d1_the_singular_opening_is_knuts_new_sentence(qapp, monkeypatch):
    """ISO 12647-7 limits the paper and both solid rows; with no readable
    profile all three read N-A: the opening is Knut's D1 sentence, verbatim.
    One column that judged beside one that could not answer gets it too.

    MUTATION, proven red: map "answerable" back to the opening that stops
    before the clause (A3)."""
    dlg = _dialog(qapp)
    try:
        said = _opening(dlg, monkeypatch, "iso_12647_7",
                        [_sheet(profile=False)])
        assert said == S_ANSWERABLE.format(where="Demo, run 3"), said
        said = _opening(dlg, monkeypatch, "iso_12647_7",
                        [_sheet(), _sheet(when="2026-11-23_100000",
                                          profile=False)])
        assert said == S_ANSWERABLE.format(where="Demo, run 3"), said
    finally:
        dlg.deleteLater()


@pytest.mark.parametrize("set_id,profiles,want", [
    ("iso_12647_7", (True, True), P_ALL),           # all three judged
    ("iso_12647_8", (True, True), P_WHERE),         # the paper only limited
    ("iso_12647_7", (True, False), P_ANSWERABLE),   # one run's rows N-A
    ("iso_12647_7", (False, False), P_PLAIN),       # nothing judged
    ("chromiq_default", (True, True), P_PLAIN),     # nothing limited
])
def test_d1_the_plural_opening_carries_the_true_clause(qapp, monkeypatch,
                                                      set_id, profiles, want):
    """Across runs, every sheet raw: the judged clause, "against the
    profiles", only where a paper or solid row was judged, in the form true
    of exactly the rows judged; otherwise Knut's A4 as he accepted it.

    MUTATION, proven red: give the plural its clause wherever
    `_raw_clause` names one (ChromIQ default is told its paper and solids
    are judged)."""
    dlg = _dialog(qapp)
    try:
        runs = [_sheet(run="run1", profile=profiles[0]),
                _sheet(run="run3", profile=profiles[1])]
        said = _opening(dlg, monkeypatch, set_id, runs)
        assert said == want.format(where="Demo, run 1; Demo, run 3"), said
    finally:
        dlg.deleteLater()


# --------------------------------------------------------------------------
# D2: across runs, sheets printed both ways
# --------------------------------------------------------------------------
def test_d2_across_runs_both_ways_is_knuts_sentence_verbatim(qapp,
                                                            monkeypatch):
    """Knut, D2: "Accepted." The words are his, the message approved; a
    report across runs of sheets printed through their profiles only keeps
    the approved plural sentence.

    MUTATION, proven red: drop the ``if _any_raw`` branch of the plural case
    (the approved "Each was verified by printing a chart through its
    profile" over raw sheets)."""
    assert M.M_REPORT_MIXED_OPENING_RUNS.approved
    assert M.M_REPORT_MIXED_OPENING_RUNS.body == (
        "This report judges the profiles built in {where}. Some of their "
        "sheets were printed through their profiles and compared with the "
        "charts' own aim values; the others, marked “printed raw”, were "
        "printed without them. The measurements it covers, and the profile "
        "run each comes from, are listed under Report Scope.")
    dlg = _dialog(qapp)
    try:
        said = _opening(dlg, monkeypatch, "iso_12647_7",
                        [_sheet("through-profile", run="run1"),
                         _sheet("raw", run="run3")])
        assert said == M.M_REPORT_MIXED_OPENING_RUNS.body.format(
            where="Demo, run 1; Demo, run 3"), said
        said = _opening(dlg, monkeypatch, "iso_12647_7",
                        [_sheet("through-profile", run="run1"),
                         _sheet("through-profile", run="run3")])
        assert said.startswith("This report judges the profiles built in "
                               "Demo, run 1; Demo, run 3. Each was verified")
    finally:
        dlg.deleteLater()


# --------------------------------------------------------------------------
# German, by hand
# --------------------------------------------------------------------------
def test_every_new_opening_has_german_by_hand():
    """The four new openings and D2's message: German written by hand, no
    em dash, no "du" in report text, and the singular D1 sentence uses the
    words of M-REPORT-RAW-RESULTS-SOME's German clause.

    MUTATION, proven red: set any German value back to its English key, or
    its last sentence (the Report Scope sentence) back to English."""
    import re
    de = _de()
    keys = [S_ANSWERABLE, P_ALL, P_WHERE, P_ANSWERABLE,
            M.M_REPORT_MIXED_OPENING_RUNS.body,
            M.M_REPORT_MIXED_OPENING_RUNS.title]
    for k in keys:
        t = de[k]
        assert t != k, k[:60]
        assert "—" not in k and "—" not in t
        assert not re.search(r"\b(du|dein\w*|dich|dir)\b", t), t
        assert ("{where}" in k) == ("{where}" in t)
        if k.startswith("This report"):
            # every opening ends in the approved German Report Scope sentence
            assert "unter „Berichtsumfang“" in t and "Report Scope" not in t, t
    assert ("wo der Grenzwertsatz einen Grenzwert für sie hat und die Messung "
            "sie beantworten kann") in de[S_ANSWERABLE]
    assert "gegen die Profile" in de[P_ALL]


# --------------------------------------------------------------------------
# Knut, #182 5850330710: the texts explain only the report generated today
# --------------------------------------------------------------------------
_SETS = (r"ChromIQ default|ChromIQ tight|Quick check|ChromIQ-Standard|"
         r"ChromIQ eng|Schnellprüfung")
_RELATION = re.compile(
    rf"({_SETS})[^.;]{{0,80}}\b(half|halves|halved|halving|double|doubles|"
    rf"doubled|twice|Hälfte|halb\w*|doppelt\w*|verdoppel\w*)\b"
    rf"|\b(half|halves|double|doubles|twice|Hälfte|Doppelte)\b[^.;]{{0,40}}"
    rf"({_SETS})", re.I)
_NUMBER = re.compile(rf"({_SETS})[^.;]{{0,80}}\b\d+[.,]\d\b")


def _current_texts() -> "list[str]":
    """Every English text of the report, its guide and its help (the scan of
    `test_k59_no_drift_in_the_report`), with the German each is shown as."""
    from tests.test_k59_no_drift_in_the_report import _report_texts
    texts = _report_texts()
    de = _de()
    return texts + [de[t] for t in texts if t in de]


def test_no_text_explains_cond():
    """COND is not a word any report generated today can show: no row
    reads it (retired 2026-09-21) and no column's Overall can (the ISO cap
    went 2026-09-22; `set_summary` returns it only for a row that already
    reads COND, which only a report saved before 4.3.0 holds). So no guide,
    help or report text mentions it. What is left is the word itself, the
    label a saved older report's cell is drawn with.

    MUTATION, proven red: put "which may also read COND" back into "What this
    tool does"."""
    import re as _re
    bad = [t[:90] for t in _current_texts()
           if _re.search(r"\bCOND\b", t) and t != "COND"]
    assert not bad, bad


def test_no_text_relates_one_limit_set_to_another_or_repeats_its_numbers():
    """"ChromIQ tight halves those two" described a relation that is only
    today's values of two separate sets; and the texts may not repeat the
    numbers the Report limits window holds.

    MUTATION, proven red: restore the blurb "Twice ChromIQ default: a quick
    health check ..." (or "ChromIQ default (2.0 on the averages, ...")."""
    texts = _current_texts()
    rel = [t[:90] for t in texts if _RELATION.search(t)]
    assert not rel, rel
    num = [t[:90] for t in texts if _NUMBER.search(t)]
    assert not num, num
    # the guard reaches the texts it is about
    assert any("ChromIQ tight has stricter limits" in t for t in texts)
    assert any("strengere Grenzwerte" in t for t in texts)
