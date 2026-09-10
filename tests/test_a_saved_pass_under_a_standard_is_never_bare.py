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
]


@pytest.mark.parametrize("set_id, label", _STANDARD_SETS)
def test_a_saved_verdict_under_a_standard_carries_the_caveat(qapp, tmp_path,
                                                             set_id, label):
    proj, run, ti3 = _saved_run(tmp_path, set_id, label)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        runs = dlg._runs_for_report()
        assert runs, "the saved verification produced no column"
        sm = dlg._column_summary(runs[0])
        assert sm.word == PASS, (
            f"the fixture no longer saves a PASS ({sm.word}), so this test "
            "would prove nothing about the case it exists for")
        assert STANDARD_CAVEAT in sm.reason or "not a test against that standard" \
            in sm.reason, (
                f"a saved PASS under {label!r} prints with no caveat: {sm.reason!r}")
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
