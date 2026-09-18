"""B8-384 — changing "Judged against" may not touch one saved report.

Knut, 2026-09-18, testing beta 21::

    When I change Judged Against to another setting, all listed reports in the
    Saved reports pulldown change to the new judged against setting, AND
    created a new (third) report. This is not the behaviour I specified.

and, asked directly whether that supersedes **D23**, the archive-then-
recalculate rule stated twice in his own name in §5 of
`docs/design/measurement_report_limits.md`::

    Agreed. D23 stands.

**WHICH READING OF D23 THIS IS.** §5 states D23 as *"Every recalculation … first
copies each dated report whose content has no copy yet into
`reports/old/<timestamp>/`, then rewrites the file in place (Knut D23; nothing
is deleted)"*. That is a rule about HOW a recalculation is done, not about
whether one happens; the other half of §5, his beta-20 ruling and N.2 of the
same section, decide that: *"If a report has been generated, those reports
shall not be recalculated if I want to create a new report with a different
Judged Against threshold set."* So the file is left alone, which keeps D23's
promise — nothing of a saved verdict is lost — more completely than archiving
it would.

**AND FOR A REPORT THAT RECORDS NO LIMIT SET OF ITS OWN, LEAVING IT ALONE IS
THE ONLY READING THAT WORKS.** A rewrite is the one thing that can stamp a set
onto such a file, and stamping it is what relabelled the entries Knut
photographed: `_saved_report_label` reads the set off the FILE, so two reports
that had recorded none came back named "ChromIQ tight", claiming a press nobody
made. Archiving a copy first would have kept the old bytes and still left the
live file lying about itself.

THE FIXTURE HOLDS FOUR SHAPES, because one too tidy to contain the fault agrees
with the code: a report from an older schema with no limit set and no verdict;
a 4.2.x-shaped report carrying a set of its own; a document written by the
window's own Generate report button; and a second run whose folder name
extends the first's (`run1` / `run10`), which is the prefix trap this window
has been bitten by before.

Measured on screen before and after, in a real window
(`scripts/drive_b384_the_older_reports.py`,
`~/Desktop/ChromIQ-beta22-proof/b384-and-b385/`): changing "Judged against"
rewrote **3 of 8** report files, moved 3 mtimes, relabelled 3 entries in the
pulldown, showed one confirmation and left 4 copies in `reports/old`; after the
fix, **0 of 8**, no mtime moved, no entry renamed, no question and no copy, and
every entry still opens.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.file_manager import Project                     # noqa: E402
from core.settings import AppSettings                     # noqa: E402
from workflow import measurement_report as mr             # noqa: E402
from workflow import run_compliance as rc                 # noqa: E402
from workflow.ti3_analysis import mark_verification_ti3   # noqa: E402

from tests.test_report_judging import _colours, _ramp, _write_ti3  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _settings(tmp_path) -> AppSettings:
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    return s


def _measure(run, when: datetime):
    v = run.new_verification(when)
    v.ensure_dir()
    raw = v.dir / "P.ti3"
    _write_ti3(raw, _ramp(16) + _colours(), verification=False)
    mark_verification_ti3(raw).rename(v.dir / f"{run.verify_stem}.ti3")
    return v, v.dir / f"{run.verify_stem}.ti3"


def _messy_project(tmp_path):
    """A project holding reports of every shape a user's disk can hold.

    Returns ``(project, run, the run that must not be touched, a .ti3)``.
    """
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    first = None
    for i in range(2):
        v, ti3 = _measure(run, datetime(2026, 1, 1 + i, 10, 0, 0))
        first = first or ti3
        # 1. AN OLDER SCHEMA: no limit set, no verdict, nothing to restore
        old = mr.build_report(ti3)
        old["schema"] = 5
        old.pop("compliance", None)
        old.pop("verdict", None)
        old.pop("report_type", None)
        mr.save_report(old, v.dir)
        # 2. THE 4.2.x SHAPE: schema 7, its own set and verdict, no document
        recent = mr.build_report(ti3)
        mr.set_report_type(recent, "t2_full_colour_check")
        mr.stamp_verdict(recent, rc.run_limits(run, {}).limits,
                         set_id="chromiq_quick", set_label="Quick check")
        mr.save_report(recent, v.dir)
    # 4. THE RUN THAT MUST NOT BE TOUCHED, and its name extends this one's:
    #    "…/runs/run10" starts with "…/runs/run1", which this window has
    #    already been bitten by once.
    other = proj.new_run()
    while other.dir.name != "run10":
        other = proj.new_run()
    other.ensure_dir()
    ov, oti3 = _measure(other, datetime(2026, 4, 4, 10, 0, 0))
    orep = mr.build_report(oti3)
    mr.stamp_verdict(orep, rc.run_limits(other, {}).limits,
                     set_id="chromiq_quick", set_label="Quick check")
    mr.save_report(orep, ov.dir)
    # a project made before #182: the run carries no set at all
    meta = run.load_meta()
    meta.compliance_set_id = ""
    meta.compliance_thresholds = None
    run.save_meta(meta)
    assert not rc.is_bound(run), "the fixture is bound, so it proves nothing"
    return proj, run, other, first


def _inventory(*runs) -> dict:
    """Every live report file: its bytes, its hash and its mtime."""
    out = {}
    for run in runs:
        for v in list(run.verifications()) + [run]:
            d = getattr(v, "reports_dir", None)
            if d is None or not d.is_dir():
                continue
            for f in sorted(d.glob("report_*.json")):
                b = f.read_bytes()
                out[str(f)] = (len(b), hashlib.sha256(b).hexdigest(),
                               f.stat().st_mtime_ns)
    return out


def _dialog(s, ti3):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    return MeasurementReportDialog(s, None, initial_ti3=ti3)


def _entries(dlg) -> list:
    return [dlg._saved_combo.itemText(i)
            for i in range(dlg._saved_combo.count())]


def _choose_another_set(dlg, qapp) -> str:
    """The app's own door: pick a different set in the "Judged against"
    pulldown, exactly as a user does."""
    now = dlg._set_combo.currentData()
    other = next(dlg._set_combo.itemData(i)
                 for i in range(dlg._set_combo.count())
                 if dlg._set_combo.itemData(i)
                 and dlg._set_combo.itemData(i) != now)
    dlg._set_combo.setCurrentIndex(dlg._set_combo.findData(other))
    qapp.processEvents()
    return other


# ---------------------------------------------------------------------------
def test_changing_the_set_rewrites_not_one_report_file(qapp, tmp_path,
                                                       monkeypatch):
    """Every shape, every byte, every modification time.

    MUTATION: put `self._recalculate_run()` back at the end of
    `_on_set_chosen` and this goes red.
    """
    proj, run, other, ti3 = _messy_project(tmp_path)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)
        # a DOCUMENT, written by the window's own button, so all four shapes
        # are on disk when the set changes
        dlg._on_generate_report()
        qapp.processEvents()
        before = _inventory(run, other)
        assert len(before) >= 5, before

        _choose_another_set(dlg, qapp)

        after = _inventory(run, other)
        assert set(after) == set(before), (
            "a file was added or removed by a change of limit set: "
            f"{sorted(set(after) ^ set(before))}")
        moved = [p for p in before if after[p][1] != before[p][1]]
        assert not moved, f"these saved reports were rewritten: {moved}"
        touched = [p for p in before if after[p][2] != before[p][2]]
        assert not touched, f"these mtimes moved: {touched}"
    finally:
        dlg.close()


def test_a_report_that_records_no_set_still_records_none(qapp, tmp_path,
                                                         monkeypatch):
    """The exact thing Knut watched: a report that had no limit set of its own
    came back claiming one, and the pulldown entry was named after it.

    MUTATION: put `self._recalculate_run()` back and this goes red.
    """
    proj, run, other, ti3 = _messy_project(tmp_path)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)
        legacy = [f for v in run.verifications()
                  for f in sorted(v.reports_dir.glob("report_*.json"))
                  if json.loads(f.read_text(encoding="utf-8")).get(
                      "schema") == 5]
        assert legacy, "the fixture holds no report from an older schema"
        quick = [f for v in run.verifications()
                 for f in sorted(v.reports_dir.glob("report_*.json"))
                 if (json.loads(f.read_text(encoding="utf-8")).get(
                     "compliance") or {}).get("set_id") == "chromiq_quick"]
        assert quick, "the fixture holds no report of the 4.2.x shape"

        chosen = _choose_another_set(dlg, qapp)

        for f in legacy:
            d = json.loads(f.read_text(encoding="utf-8"))
            assert d.get("compliance") is None, (
                f"a report that recorded no limit set now claims {d['compliance']}")
            assert d.get("schema") == 5, "the older report was re-stamped"
        for f in quick:
            d = json.loads(f.read_text(encoding="utf-8"))
            assert d["compliance"]["set_id"] == "chromiq_quick", (
                "a report's own recorded set was replaced by the one chosen "
                f"in the pulldown ({chosen})")
    finally:
        dlg.close()


def test_the_entries_in_the_list_keep_their_names(qapp, tmp_path, monkeypatch):
    """*"all listed reports in the Saved reports pulldown change to the new
    judged against setting"* — his own sentence, as an assertion.

    MUTATION: put `self._recalculate_run()` back and this goes red.
    """
    proj, run, other, ti3 = _messy_project(tmp_path)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)
        before = sorted(_entries(dlg))
        assert before, "the list is empty, so this proves nothing"
        _choose_another_set(dlg, qapp)
        assert sorted(_entries(dlg)) == before, (
            "entries were renamed by a change of limit set:\n"
            f"  before {before}\n  after  {sorted(_entries(dlg))}")
    finally:
        dlg.close()


def test_nothing_is_archived_because_nothing_is_rewritten(qapp, tmp_path,
                                                          monkeypatch):
    """`Verification.archive_reports` copied every live report of a date into
    `reports/old/<stamp>/` before the rewrite, generated documents included,
    even though they were then skipped. Nothing is rewritten now, so nothing is
    copied: D23's "kept first" has nothing to keep.

    MUTATION: put `self._recalculate_run()` back and this goes red.
    """
    proj, run, other, ti3 = _messy_project(tmp_path)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)
        _choose_another_set(dlg, qapp)
        copies = sorted(str(p) for p in run.dir.glob("**/old/**/report_*.json"))
        assert not copies, f"a set change archived these: {copies}"
    finally:
        dlg.close()


def test_no_question_is_asked_about_a_rewrite_that_cannot_happen(
        qapp, tmp_path, monkeypatch):
    """Knut called the box *"wrong functionality"*. It promised a
    recalculation, and there is none to promise.

    MUTATION: put the `_recalculating_would_rewrite_history` branch back in
    `_on_set_chosen` and this goes red.
    """
    proj, run, other, ti3 = _messy_project(tmp_path)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        asked: list = []
        monkeypatch.setattr(type(dlg), "_confirm",
                            lambda self, t, x: asked.append((t, x)) or True)
        _choose_another_set(dlg, qapp)
        assert not asked, f"the pulldown asked: {asked}"
    finally:
        dlg.close()


def test_another_runs_reports_are_not_touched_either(qapp, tmp_path,
                                                     monkeypatch):
    """`…/runs/run10` starts with `…/runs/run1`. The folders are asked of the
    run rather than matched out of a string, and this keeps it that way whether
    or not anything is rewritten.

    MUTATION: put `self._recalculate_run()` back AND make it match run folders
    by prefix again, and this goes red.
    """
    proj, run, other, ti3 = _messy_project(tmp_path)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)
        before = _inventory(other)
        assert before, "the other run holds no report"
        _choose_another_set(dlg, qapp)
        assert _inventory(other) == before, (
            "the run next door was rewritten by a set change made on this one")
    finally:
        dlg.close()


def test_every_saved_report_still_opens_afterwards(qapp, tmp_path, monkeypatch):
    """The absolute constraint: nothing on a user's disk may be destroyed, and
    every report that exists must still open."""
    proj, run, other, ti3 = _messy_project(tmp_path)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)
        _choose_another_set(dlg, qapp)
        assert dlg._saved_combo.count() >= 4, dlg._saved_combo.count()
        for i in range(dlg._saved_combo.count()):
            dlg._saved_combo.setCurrentIndex(i)
            qapp.processEvents()
            assert dlg._saved_combo.currentIndex() == i
            assert len(dlg._view.toHtml()) > 500, (
                f"entry {i} ({dlg._saved_combo.itemText(i)!r}) draws nothing")
    finally:
        dlg.close()


def test_the_run_is_still_bound_to_the_set_that_was_chosen(qapp, tmp_path,
                                                           monkeypatch):
    """What the pulldown still does, and must: the set is the run's yardstick
    for the dated verifications still to come, and for anything with no verdict
    of its own. Only the saved reports are out of its reach.

    MUTATION: drop the `bind_run` call from `_on_set_chosen` and this goes red.
    """
    proj, run, other, ti3 = _messy_project(tmp_path)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)
        chosen = _choose_another_set(dlg, qapp)
        assert rc.is_bound(run)
        assert rc.run_limits(run, {}).set_id == chosen
    finally:
        dlg.close()


def test_the_unlock_door_still_recalculates(qapp, tmp_path, monkeypatch):
    """**THE TWO OTHER DOORS ARE UNCHANGED**, and this is the one that proves
    the change was aimed at the pulldown and nowhere else.

    §5 and D23 still govern them, and whether Knut's N.3 (*"Unlocking a run's
    limits and saving a change in the Edit limits window must result in the
    same behaviour"*) reaches them is an open question for him, registered as
    B8-310. Nothing here assumes an answer.

    MUTATION: remove `self._recalculate_run()` from `_on_unlock_toggled` too
    and this goes red.
    """
    proj, run, other, ti3 = _messy_project(tmp_path)
    s = _settings(tmp_path)
    s.set("compliance_allow_edit_after_measurement", True)
    rc.bind_run(run, "chromiq_default", {})
    dlg = _dialog(s, ti3)
    try:
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)
        before = _inventory(run)
        dlg._unlock_check.setChecked(True)
        qapp.processEvents()
        after = _inventory(run)
        assert any(after[p][1] != before[p][1] for p in before), (
            "the unlock door stopped recalculating the run's saved reports")
        copies = sorted(str(p) for p in run.dir.glob("**/old/**/report_*.json"))
        assert copies, "it recalculated without keeping the previous reports"
    finally:
        dlg.close()
