"""A SAVED verdict may keep its word and may not keep it alone.

Round three of the challenge drove the real report window and found what the
tests written the same morning could not see: `_column_summary` returns the word
a report was SAVED with, from an early return twenty lines above the caveat
rule, so a report saved by an earlier build printed

    Overall  PASS   (green, bold)
    Judged against: Custom ISO 12647-7 (historical)
    "Every value this limit set requires was checked and is within its limit."

in the window and in the PDF, while the same report's own text two paragraphs
above says it never says anything conforms to a standard.

The earlier tests were green because every one of them called `set_summary` and
`applies_a_standard` directly. Nothing went near the window. So this one goes
through `_column_summary`, which is the thing that was wrong.

**The word is kept on purpose.** `docs/design/measurement_report_limits.md` has
Knut ruling that a run keeps its values and its verdicts, so recomputing PASS
into COND would contradict a binding record. What the promise to a rights holder
forbids is the word standing ALONE under a standard's name, so the sentence
gains the caveat and the word does not move.
"""
from __future__ import annotations

import html as _html
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.file_manager import Project                     # noqa: E402
from core.settings import AppSettings                     # noqa: E402
from workflow import measurement_report as mr             # noqa: E402
from workflow import run_compliance as rc                 # noqa: E402
from workflow.compliance_sets import PASS, STANDARD_CAVEAT  # noqa: E402
from workflow.ti3_analysis import mark_verification_ti3   # noqa: E402

from tests.test_report_judging import _colours, _ramp, _write_ti3   # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _settings(tmp_path) -> AppSettings:
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    return s


def _saved_run(tmp_path, set_id: str, set_label: str):
    """A run with one dated verification whose report was SAVED with a verdict."""
    from datetime import datetime
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run(); run.ensure_dir()
    v = run.new_verification(datetime(2026, 1, 1, 10, 0, 0))
    v.ensure_dir()
    raw = v.dir / "P.ti3"
    _write_ti3(raw, _ramp(16) + _colours(), verification=False)
    mark_verification_ti3(raw).rename(v.dir / f"{run.verify_stem}.ti3")
    target = v.dir / f"{run.verify_stem}.ti3"
    rep = mr.build_report(target)
    # PERMISSIVE ON PURPOSE, so the fixture really saves a PASS. With the
    # factory limits this synthetic sheet saves COND and every case below would
    # SKIP, which is a test that proves nothing and is exactly the trap this
    # project keeps a note about.
    mr.stamp_verdict(rep, rc.run_limits(run, {}).limits,
                     set_id=set_id, set_label=set_label)
    # THE RECORD AN EARLIER BUILD WOULD HAVE WRITTEN. This test is about how the
    # window RENDERS a saved verdict, not about how one comes to be, and a
    # synthetic sheet cannot honestly reach PASS because several rows need a
    # reference file. Forcing the fixture's own limits instead only produced
    # COND again and every case SKIPPED, which is a test that proves nothing.
    rep.setdefault("verdict", {})["overall"] = "PASS"
    rep["verdict"].setdefault("rows", [])
    rep["verdict"]["summary"] = {
        "checked": 5, "total": 5, "failed": 0, "cond": 0, "not_computed": 0,
        "reason": "Every value this limit set requires was checked and is "
                  "within its limit.",
    }
    mr.save_report(rep, v.dir)
    return proj, run, target


def _dialog(s, ti3):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    return MeasurementReportDialog(s, None, initial_ti3=ti3)


#: The three shapes round three drove, all of which printed a bare PASS.
_STANDARD_SETS = [
    ("custom_iso_12647_7_v1", "Custom ISO 12647-7"),    # an id this build forgot
    ("custom_iso_12647_7", "Custom ISO 12647-7"),       # a live custom column
    ("iso_12647_7", "ISO 12647-7:2016 values"),         # the read-only column
    # …AND THE OTHER STANDARD. Round 40c pointed out that all three shapes
    # above are 12647-7, so a change that recognised one standard's name and
    # not the other's would have passed the whole file.
    ("custom_iso_12647_8", "Custom ISO 12647-8"),
    ("iso_12647_8", "ISO 12647-8:2021 values"),
]


@pytest.mark.parametrize("set_id, label", _STANDARD_SETS)
def test_the_saved_word_is_kept(qapp, tmp_path, set_id, label):
    proj, run, ti3 = _saved_run(tmp_path, set_id, label)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        runs = dlg._runs_for_report()
        assert runs, "the saved verification produced no column"
        sm = dlg._column_summary(runs[0])
        assert sm.word == PASS, (
            f"the fixture no longer saves a PASS ({sm.word}), so this test "
            "would prove nothing about the case it exists for")
        # The WORD is what this checks. The caveat is not in the reason and
        # must not be: it travels through one render, the Overall cell's
        # `title=`, so a caveat put here reaches a tooltip and no PDF, and it
        # also broke the exact-equality that selects the ungraded footnote and
        # the tr() lookup for every language but English. It is a footnote now,
        # checked by test_the_caveat_is_in_the_report_body_and_the_pdf below.
        assert STANDARD_CAVEAT not in sm.reason, (
            "the caveat is back in the reason, where it reaches a tooltip and "
            "breaks two other things")
    finally:
        dlg.deleteLater()


def test_a_saved_verdict_under_chromiqs_own_set_is_left_alone(qapp, tmp_path):
    """The other half. ChromIQ's own limits are nobody's published figures, so
    a PASS there is a plain PASS and must not gain a sentence about standards."""
    proj, run, ti3 = _saved_run(tmp_path, "chromiq_default",
                                "ChromIQ default (recommended)")
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        sm = dlg._column_summary(dlg._runs_for_report()[0])
        assert "not a test against that standard" not in sm.reason, sm.reason
    finally:
        dlg.deleteLater()


# ---- and it must be in the OUTPUT, which is where this went wrong twice ----
def _visible(body: str) -> str:
    """The report with every tag stripped, which is what removes a `title=`."""
    import re
    return _html.unescape(re.sub(r"<[^>]+>", " ", body))


@pytest.mark.parametrize("set_id, label", _STANDARD_SETS)
def test_the_caveat_is_in_the_report_body_and_the_pdf(qapp, tmp_path,
                                                      set_id, label):
    """SECOND TIME IN ONE DAY. The ungraded explanation reached only a `title=`
    attribute, was fixed, and then the caveat for a saved PASS under a
    standard's name went into the very same attribute on the graded path, which
    `_summary_cell` renders and no PDF carries. A beta-4 planning agent measured
    it after the fix: caveat in the window false, caveat in the PDF false, the
    word PASS visible true.
    """
    proj, run, ti3 = _saved_run(tmp_path, set_id, label)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        runs = dlg._runs_for_report()
        body = dlg._report_body_html(runs, for_pdf=True)
        seen = _visible(body)
        assert "not a test against that standard" in seen, (
            f"the caveat for {label!r} is not in the rendered report. If it is "
            "only in a tooltip it is not in the PDF and a reader never sees it.")
        # …AND THE CLAUSE KNUT ASKED FOR WHEN HE RETIRED THE CAP, 2026-09-22:
        # *"ChromIQ's results are only indications that results that PASS
        # likely fulfil the standard ... It is not proof that results fulfil
        # the standard. The report text notes should explain this detail."*
        #
        # **CHECKED AS THE WHOLE CAVEAT, AND WRITTEN OUT HERE** (adversary
        # round 40c, finding 5, and then again on the first attempt at fixing
        # it). Two things were wrong. Looking for "not proof that it does"
        # alone was satisfied by a paragraph of `_how_to_read_html`, which
        # every multi-section report prints whatever it is judged against. And
        # the first correction built the expected string out of
        # `STANDARD_CAVEAT_APPLIED + STANDARD_CAVEAT_PROOF`, which is a test
        # reading the constant it checks: gutting the second sentence changed
        # both sides of the comparison and it stayed green.
        #
        # So the sentence is TYPED HERE. That is the cost of guarding a
        # promise made to a rights holder: a change to the wording has to be
        # made in two places, and the second place is a test that says why.
        _CAVEAT = (
            "This limit set holds a standard's published values applied to "
            "your chart. It is not a test against that standard: the chart is "
            "not the standard's chart, and the metrics are ChromIQ's own "
            "rather than the standard's methods. A result inside these limits "
            "is an indication that the print would likely meet the standard, "
            "not proof that it does.")
        assert _CAVEAT in " ".join(seen.split()), (
            f"the report for {label!r} does not carry the caveat whole. The "
            "clause saying a pass is an indication and not proof is the half "
            "Knut asked for when he retired the cap, and the rest is the "
            "promise this file exists for.")
    finally:
        dlg.deleteLater()


def test_chromiqs_own_set_gets_no_such_sentence(qapp, tmp_path):
    """A caveat printed on every report would teach the reader to skip it."""
    proj, run, ti3 = _saved_run(tmp_path, "chromiq_default",
                                "ChromIQ default (recommended)")
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        body = dlg._report_body_html(dlg._runs_for_report(), for_pdf=True)
        assert "not a test against that standard" not in _visible(body)
    finally:
        dlg.deleteLater()


# ===========================================================================
# …AND A LIVE COLUMN IS ASKED THE SAME QUESTION AS A SAVED ONE
# ===========================================================================
# **FOUND BY ADVERSARY ROUND 40a (F6), DRIVEN ON SCREEN.** Every test above
# goes through `_saved_run`, so every one of them hands the dialog a column
# whose compliance block holds both the set id and the label. The notes block
# read the stored label from that block and passed "" for a column that has no
# saved report, asking `applies_a_standard` about the id alone. A run bound to
# a set id this build no longer knows, with a standard's name stored beside it
# (which is what today's files look like to a future ChromIQ), then printed a
# green PASS under "ISO 12647-7:2028 (historical)" with no caveat anywhere.
# Pressing Generate closed it, because saving writes the label into the block:
# the hole was open exactly while the column was live.
def _live_run(tmp_path, set_id: str, set_label: str):
    """A run BOUND to a set and never reported on: no compliance block, so the
    only record of what it is judged against is the run's own meta.json."""
    from datetime import datetime
    proj = Project.create(tmp_path / "L", "L")
    run = proj.current_run(); run.ensure_dir()
    v = run.new_verification(datetime(2026, 1, 1, 10, 0, 0))
    v.ensure_dir()
    raw = v.dir / "L.ti3"
    _write_ti3(raw, _ramp(16) + _colours(), verification=False)
    mark_verification_ti3(raw).rename(v.dir / f"{run.verify_stem}.ti3")
    target = v.dir / f"{run.verify_stem}.ti3"
    meta = run.load_meta()
    # Written the way `bind_run` writes it, then the id is replaced by one this
    # build does not define, which is what a future ChromIQ reads here.
    rc.bind_run(run, "custom_iso_12647_7", {})
    meta = run.load_meta()
    meta.compliance_set_id = set_id
    meta.compliance_set_label = set_label
    run.save_meta(meta)
    return proj, run, target


#: An id with no standard's name in it, beside a stored label that has one.
#: The two halves of `applies_a_standard`'s question, pulled apart.
_FORGOTTEN = ("contract_proof_2028", "ISO 12647-7:2028")


def test_a_live_column_under_a_forgotten_standard_still_gets_the_caveat(
        qapp, tmp_path):
    """MUTATION: drop the stored-label fallback from
    `MeasurementReportDialog._names_a_standard` and this goes red, in the
    window and in the PDF."""
    proj, run, ti3 = _live_run(tmp_path, *_FORGOTTEN)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        runs = dlg._runs_for_report()
        assert runs, "the bound run produced no column"
        assert dlg._names_a_standard(runs[0]), (
            "a column headed with a standard's name is not recognised as one, "
            "so nothing will make it carry the caveat")
        label = dlg._judged_label_for(runs[0])
        assert "ISO 12647-7:2028" in label, label
        body = dlg._report_body_html(runs, for_pdf=True)
        assert "not a test against that standard" in _visible(body), (
            "a live column named after a standard prints its verdict with no "
            "caveat. This is the claim-by-juxtaposition the caveat exists to "
            "prevent, on the one path where the label is all there is.")
    finally:
        dlg.deleteLater()


def test_and_a_live_column_under_chromiqs_own_set_still_gets_none(qapp,
                                                                  tmp_path):
    """The other half, or the guard above would pass on a caveat printed on
    every live column whatever it is judged against."""
    proj, run, ti3 = _live_run(tmp_path, "house_rules_2028", "House rules")
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        runs = dlg._runs_for_report()
        assert not dlg._names_a_standard(runs[0])
        body = dlg._report_body_html(runs, for_pdf=True)
        assert "not a test against that standard" not in _visible(body)
    finally:
        dlg.deleteLater()
