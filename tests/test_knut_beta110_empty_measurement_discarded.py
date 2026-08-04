"""#130 (Knut, 2026-07-30): a session that measured nothing must not leave a
file behind that ChromIQ then treats as a measurement.

    *"is it possible to detect that a ti3 file is empty … and then move the
    empty ti3 files that do not have measurements to old/ folder right after
    measurement session was exited/stopped/completed (either it is using strip
    mode, patch-by-patch mode, resume or 'Read single patches') and then give
    user an information message window explaining that no measurements were
    performed or stored for that session, so file was moved to old/ folder?"*

He corrected an earlier draft of this ask that said "delete": the file is MOVED,
never destroyed. He also set the ordering — *"before determining if 'Refine /
resume' or 'Show overlay...' should be made visible after a measurement, and
should never be done during measurement, and only if the created file has no
measurements"*.

chartread creates its output file up front, so quitting before a single patch
was read leaves a ``.ti3`` holding a header and no data rows. Everything in
ChromIQ keys on "does the ``.ti3`` exist", so that empty file then claims the
run HAS a measurement: *"activating measure tab still detects a ti3 file so
reports a warning message, and changing a chart and clicking generate chart also
warns that a measurement exists"*.

Two halves, and both are needed. New sessions archive the empty file the moment
they end; and an empty file already on disk — from a session run before this
version — no longer counts as an existing measurement, so it stops warning
about something that was never taken.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                          # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox       # noqa: E402

from core.argyll_runner import ArgyllRunner                 # noqa: E402
from core.file_manager import Project                       # noqa: E402
from core.settings import AppSettings                       # noqa: E402
from ui.tabs.tab_measure import TabMeasure                  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


HEADER = (
    "CTI3\n\n"
    'DESCRIPTOR "Argyll Calibration Target chart information 3"\n'
    'TARGET_INSTRUMENT "X-Rite ColorMunki"\n\n'
    "NUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n"
    "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
    "END_DATA_FORMAT\n\n")


def empty_ti3() -> str:
    """What chartread leaves when the session ended before any patch was read."""
    return HEADER + "NUMBER_OF_SETS 0\nBEGIN_DATA\nEND_DATA\n"


def headerless_ti3() -> str:
    """Knut's other description of empty: *"No BEGIN_DATA and END_DATA tag
    existing"* — a file cut off before the data section was ever opened."""
    return HEADER + "NUMBER_OF_SETS 0\n"


def measured_ti3(n: int = 4) -> str:
    rows = "\n".join(f"{i} A{i} 50 50 50 20 20 20" for i in range(1, n + 1))
    return HEADER + f"NUMBER_OF_SETS {n}\nBEGIN_DATA\n{rows}\nEND_DATA\n"


def _run(tmp_path):
    """A real run folder, because ``old/`` is the run's own and the archive has
    to land inside it."""
    root = tmp_path / "ChromIQ"
    root.mkdir(exist_ok=True)
    proj = Project.create(root / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    return run


def _tab(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    return TabMeasure(ArgyllRunner(s), s)


def _silence(monkeypatch) -> list:
    """Answer the information window without opening it, and record that it
    would have opened."""
    seen: list = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self: seen.append(self.text()))
    return seen


def _archived(run) -> "list[str]":
    return [p.name for p in run.old_dir.rglob("*") if p.is_file()]


# ---- the file is MOVED, and only when it is genuinely empty ---------------
def test_an_empty_measurement_is_moved_into_old(qapp, tmp_path, monkeypatch):
    run = _run(tmp_path)
    run.chart_ti2.write_text("CTI2")
    run.measurement_ti3.write_text(empty_ti3())
    tab = _tab(tmp_path)
    tab._ti1_path = run.chart_ti2
    seen = _silence(monkeypatch)

    tab._archive_empty_measurement()

    assert not run.measurement_ti3.exists(), \
        "the empty file was left behind, still claiming to be a measurement"
    assert run.measurement_ti3.name in _archived(run), \
        "it was destroyed instead of moved — Knut asked for a move"
    assert seen, "nothing told the user where the file went"


def test_the_moved_file_keeps_its_contents(qapp, tmp_path, monkeypatch):
    """Moved, not emptied: whatever chartread wrote is still readable in old/."""
    run = _run(tmp_path)
    run.chart_ti2.write_text("CTI2")
    run.measurement_ti3.write_text(empty_ti3())
    tab = _tab(tmp_path)
    tab._ti1_path = run.chart_ti2
    _silence(monkeypatch)

    tab._archive_empty_measurement()

    moved = [p for p in run.old_dir.rglob("*") if p.is_file()]
    assert len(moved) == 1
    assert moved[0].read_text() == empty_ti3()


def test_a_file_with_no_data_section_at_all_counts_as_empty(qapp, tmp_path,
                                                            monkeypatch):
    run = _run(tmp_path)
    run.chart_ti2.write_text("CTI2")
    run.measurement_ti3.write_text(headerless_ti3())
    tab = _tab(tmp_path)
    tab._ti1_path = run.chart_ti2
    _silence(monkeypatch)

    tab._archive_empty_measurement()

    assert not run.measurement_ti3.exists()
    assert run.measurement_ti3.name in _archived(run)


def test_a_single_reading_is_a_measurement_and_stays(qapp, tmp_path, monkeypatch):
    """The line between 'nothing' and 'something' is one patch, and one patch
    already cost the user a print."""
    run = _run(tmp_path)
    run.chart_ti2.write_text("CTI2")
    run.measurement_ti3.write_text(measured_ti3(1))
    tab = _tab(tmp_path)
    tab._ti1_path = run.chart_ti2
    seen = _silence(monkeypatch)

    tab._archive_empty_measurement()

    assert run.measurement_ti3.read_text() == measured_ti3(1)
    assert not run.old_dir.exists() or not _archived(run)
    assert not seen, "it claimed nothing was measured after a patch was read"


def test_a_full_measurement_is_untouched_and_silent(qapp, tmp_path, monkeypatch):
    run = _run(tmp_path)
    run.chart_ti2.write_text("CTI2")
    run.measurement_ti3.write_text(measured_ti3())
    tab = _tab(tmp_path)
    tab._ti1_path = run.chart_ti2
    seen = _silence(monkeypatch)

    tab._archive_empty_measurement()

    assert run.measurement_ti3.exists()
    assert not seen


def test_no_file_at_all_says_nothing(qapp, tmp_path, monkeypatch):
    """A session that never created a file needs no explanation about one."""
    run = _run(tmp_path)
    run.chart_ti2.write_text("CTI2")
    tab = _tab(tmp_path)
    tab._ti1_path = run.chart_ti2
    seen = _silence(monkeypatch)

    tab._archive_empty_measurement()

    assert not seen


def test_no_chart_loaded_is_harmless(qapp, tmp_path, monkeypatch):
    tab = _tab(tmp_path)
    tab._ti1_path = None
    _silence(monkeypatch)
    tab._archive_empty_measurement()          # must not raise


def test_a_move_that_fails_does_not_crash_or_lie(qapp, tmp_path, monkeypatch):
    """A read-only folder is something to see in the log, not a traceback — and
    certainly not a window announcing a move that never happened."""
    import shutil
    run = _run(tmp_path)
    run.chart_ti2.write_text("CTI2")
    run.measurement_ti3.write_text(empty_ti3())
    tab = _tab(tmp_path)
    tab._ti1_path = run.chart_ti2
    seen = _silence(monkeypatch)

    monkeypatch.setattr(shutil, "move", lambda *a, **k: (_ for _ in ()).throw(
        OSError("read-only file system")))

    tab._archive_empty_measurement()          # must not raise
    assert not seen, "it announced a move that did not happen"
    assert run.measurement_ti3.exists(), "the file went missing after a failure"


# ---- a session that wrote nothing never replaced anything ----------------
# Knut, beta.128: *"If I then choose to cancel, the measurement exits, and the
# ti3 file is not returned to the run1 folder from old/ folder."* Archiving at
# Start is correct — chartread truncates its output the moment it opens it — but
# it is only a *replacement* once something takes the file's place. Cancelling
# the instrument-mismatch window, or an instrument that never opens, ends the
# session before chartread writes anything at all, so there is no empty file for
# the empty-file path to judge and the archive used to stay in old/ for ever.
def _replaced_then_cancelled(tmp_path, monkeypatch):
    """Set up exactly that: a real measurement, archived by the real Start-path
    method, and then a session that writes nothing."""
    run = _run(tmp_path)
    run.chart_ti2.write_text("CTI2")
    run.measurement_ti3.write_text(measured_ti3(12))
    tab = _tab(tmp_path)
    tab._ti1_path = run.chart_ti2
    tab._archive_measurement_before_replacing()          # the real Start step
    assert not run.measurement_ti3.exists(), "setup: it should have been moved"
    return run, tab


def test_a_cancelled_session_puts_the_measurement_back(qapp, tmp_path,
                                                       monkeypatch):
    run, tab = _replaced_then_cancelled(tmp_path, monkeypatch)
    seen = _silence(monkeypatch)

    tab._archive_empty_measurement()      # the session ended, having written nothing

    assert run.measurement_ti3.is_file(), "the measurement never came back"
    assert "NUMBER_OF_SETS 12" in run.measurement_ti3.read_text()
    assert seen, "the user was not told the read changed nothing"
    assert "put back exactly where it was" in seen[0]


def test_the_emptied_archive_folder_is_tidied_away(qapp, tmp_path, monkeypatch):
    """Nothing is left behind claiming to hold something."""
    run, tab = _replaced_then_cancelled(tmp_path, monkeypatch)
    _silence(monkeypatch)

    tab._archive_empty_measurement()

    assert not _archived(run), f"left in old/: {_archived(run)}"


def test_nothing_is_put_back_when_the_session_did_measure(qapp, tmp_path,
                                                          monkeypatch):
    """The guard is for sessions that wrote nothing. A real measurement stands,
    and the copy it displaced stays archived."""
    run, tab = _replaced_then_cancelled(tmp_path, monkeypatch)
    run.measurement_ti3.write_text(measured_ti3(5))       # this session's file
    _silence(monkeypatch)

    tab._archive_empty_measurement()

    assert "NUMBER_OF_SETS 5" in run.measurement_ti3.read_text()
    assert _archived(run), "the displaced measurement should still be in old/"


# ---- every ending is covered, which is why it sits in one place ----------
def test_it_runs_on_every_way_a_session_can_end(qapp):
    """Strip, patch-by-patch, resume and single patches all finish through the
    one handler; hanging this off any single mode would have missed the rest."""
    src = inspect.getsource(TabMeasure._on_measure_done)
    assert "_archive_empty_measurement()" in src


def test_it_runs_before_anything_reads_the_measurement(qapp):
    """Knut set this ordering himself: *"before determining if 'Refine / resume'
    or 'Show overlay...' should be made visible after a measurement"*."""
    src = inspect.getsource(TabMeasure._on_measure_done)
    assert src.index("_archive_empty_measurement") < \
        src.index("_restore_overlay_after_measurement")
    assert src.index("_archive_empty_measurement") < \
        src.index("_update_resume_availability")


def test_it_never_runs_during_a_measurement(qapp):
    """*"should never be done during measurement"*. It lives in the handler that
    runs when the process has already exited, which is what guarantees it."""
    src = inspect.getsource(TabMeasure._on_measure_done)
    assert src.index("_archive_empty_measurement") > src.index("measurement_active.emit(False)")


# ---- an empty file already on disk stops warning --------------------------
def test_an_empty_measurement_is_not_an_existing_measurement(qapp, tmp_path):
    """Knut's report: the Measure tab warned about a measurement, and Generate
    Chart warned one would be displaced, for a file holding no readings."""
    run = _run(tmp_path)
    run.chart_ti2.write_text("CTI2")
    run.measurement_ti3.write_text(empty_ti3())
    tab = _tab(tmp_path)
    tab._ti1_path = run.chart_ti2

    assert tab._existing_ti3_for_chart() is None


def test_a_real_measurement_still_is_one(qapp, tmp_path):
    run = _run(tmp_path)
    run.chart_ti2.write_text("CTI2")
    run.measurement_ti3.write_text(measured_ti3())
    tab = _tab(tmp_path)
    tab._ti1_path = run.chart_ti2

    assert tab._existing_ti3_for_chart() == run.measurement_ti3


def test_the_already_measured_window_asks_that_same_question(qapp):
    """One gate, so the window and the overlay can never disagree about whether
    a measurement exists."""
    src = inspect.getsource(TabMeasure._maybe_offer_existing_overlay)
    assert "_existing_ti3_for_chart() is None" in src


# ---- what the window says -------------------------------------------------
def test_the_window_says_where_the_file_went_and_what_is_safe(qapp, tmp_path,
                                                              monkeypatch):
    """Moving a file is alarming unless the message answers the fears it raises:
    where it went, that nothing was deleted, and that everything else stands."""
    run = _run(tmp_path)
    run.chart_ti2.write_text("CTI2")
    run.measurement_ti3.write_text(empty_ti3())
    tab = _tab(tmp_path)
    tab._ti1_path = run.chart_ti2
    seen = _silence(monkeypatch)

    tab._archive_empty_measurement()

    text = seen[0]
    assert "no readings to keep" in text
    assert "old" in text                       # names where it went
    assert "Nothing has been deleted and nothing else has changed" in text
    assert "start the measurement again" in text


def test_a_displaced_measurement_that_vanished_is_not_claimed_to_be_safe(
        qapp, tmp_path, monkeypatch):
    """Superseded requirement, kept as the defensive path.

    Knut first accepted the displaced measurement being left in ``old/``, then
    ruled (#130, 2026-07-31) that it must be put BACK — see the restore tests
    below. This covers what is left: the archive folder no longer holds the
    file, so there is nothing to restore, and the window must not pretend
    otherwise.
    """
    run = _run(tmp_path)
    run.chart_ti2.write_text("CTI2")
    run.measurement_ti3.write_text(empty_ti3())
    tab = _tab(tmp_path)
    tab._ti1_path = run.chart_ti2
    tab._displaced_measurement = run.old_dir / "gone"   # never created
    seen = _silence(monkeypatch)

    tab._archive_empty_measurement()

    assert seen, "the user was told nothing at all"
    assert "put back exactly where it was" not in seen[0], \
        "it claimed a restore that did not happen"


def test_the_claim_is_not_carried_into_the_next_session(qapp, tmp_path,
                                                        monkeypatch):
    """A stale flag would make every later window mention a displacement that
    did not happen."""
    run = _run(tmp_path)
    run.chart_ti2.write_text("CTI2")
    run.measurement_ti3.write_text(empty_ti3())
    tab = _tab(tmp_path)
    tab._ti1_path = run.chart_ti2
    tab._displaced_measurement = run.old_dir / "x"
    _silence(monkeypatch)

    tab._archive_empty_measurement()

    assert tab._displaced_measurement is None


def test_the_message_has_no_bracketed_plural(qapp):
    src = inspect.getsource(TabMeasure._archive_empty_measurement)
    assert "(s)" not in src


# ---- the sub-option does not outlive its parent ---------------------------
def _resume_widgets(tab):
    """(parent resume box, sub-option ROW) for each mode.

    The ROW, not the checkbox inside it. The sub-option is a checkbox plus its
    own help icon, and the icon is added straight to the row's layout — so
    hiding the checkbox alone left the icon behind in an empty space (Knut,
    #130 2026-08-01). The row is what goes, and taking it as the unit is also
    what these tests mean by "on screen".
    """
    return [(tab._resume_cb, tab._refine_row),
            (tab._m_resume_cb, tab._m_refine_row)]


def test_the_refinement_sub_option_hides_with_its_parent(qapp, tmp_path):
    """Knut, #130 2026-07-30: *"then 'Refine / resume..' and 'Show overlay...'
    are hidden, but the sub-level checkbox 'Use refinement strips file ....'
    still shows"*. It was only ever greyed, never hidden, so it stood alone
    under nothing — offering to refine a measurement that does not exist."""
    from core.file_manager import reports_subdir
    run = _run(tmp_path)
    run.chart_ti2.write_text("CTI2")
    run.measurement_ti3.write_text(empty_ti3())
    # A refinement-strips file IS present: that is what used to keep the
    # sub-option visible and ticked regardless of the measurement.
    reports = reports_subdir(run.dir)
    reports.mkdir(parents=True, exist_ok=True)
    (reports / f"Refine_Strips_{run.chart_ti2.stem}.txt").write_text("A\n")

    tab = _tab(tmp_path)
    tab._ti1_path = run.chart_ti2
    tab._update_resume_availability()

    # isVisible() is False for everything in a tab that was never shown, which
    # would make this pass without testing anything; isHidden() reflects the
    # explicit hide, which is what the fix sets.
    for parent, row in _resume_widgets(tab):
        assert parent.isHidden()
        assert row.isHidden(), \
            "the sub-option stayed on screen under a hidden parent"
    assert not tab._refine_cb.isChecked()
    assert not tab._m_refine_cb.isChecked()


def test_no_chart_hides_the_sub_option_too(qapp, tmp_path):
    tab = _tab(tmp_path)
    tab._ti1_path = None
    tab._update_resume_availability()
    for _parent, row in _resume_widgets(tab):
        assert row.isHidden()


def test_a_real_measurement_still_offers_the_sub_option(qapp, tmp_path):
    """The fix must not take the option away when it genuinely applies."""
    from core.file_manager import reports_subdir
    run = _run(tmp_path)
    run.chart_ti2.write_text("CTI2")
    run.measurement_ti3.write_text(measured_ti3())
    reports = reports_subdir(run.dir)
    reports.mkdir(parents=True, exist_ok=True)
    (reports / f"Refine_Strips_{run.chart_ti2.stem}.txt").write_text("A\n")

    tab = _tab(tmp_path)
    tab._ti1_path = run.chart_ti2
    tab._update_resume_availability()

    # The sub-option belongs to the resume tick, so it is on screen once that
    # is ticked — and available, which is the half this test guards.
    for parent, row in _resume_widgets(tab):
        assert not parent.isHidden()
        assert row.isHidden(), "not until the resume option it belongs to is on"
    for cb in (tab._resume_cb, tab._m_resume_cb):
        cb.setChecked(True)
    tab._sync_refine_rows()
    for _parent, row in _resume_widgets(tab):
        assert not row.isHidden()
    for cb in (tab._refine_cb, tab._m_refine_cb):
        assert cb.isEnabled()


# ---- the stored chart is REPLACED, not merged into -----------------------
def test_storing_a_chart_leaves_only_that_chart(tmp_path):
    """Knut, #130 2026-07-31: *"there is a cht file that does not disappear …
    None of the old files must survive."*

    He replaced the stored chart, measured a row, stopped — and "Stored chart
    differs" came back on the next start. It came back because the folder still
    held a file from the chart before, so the stored chart genuinely no longer
    matched the live one.
    """
    import types
    from workflow.verify_chart_snapshot import snapshot_slot

    live = tmp_path / "live"; live.mkdir()
    snap = tmp_path / "chart"; snap.mkdir()
    # What the previous chart left behind, including the .cht he named.
    (snap / "Old-Chart.cht").write_text("old")
    (snap / "Old-Chart.ti2").write_text("old")
    new_files = []
    for name in ("New-Chart.ti1", "New-Chart.ti2"):
        f = live / name
        f.write_text("new")
        new_files.append(f)

    slot = types.SimpleNamespace(snapshot_dir=snap,
                                 files_to_copy=lambda: new_files)
    snapshot_slot(slot)

    left = sorted(p.name for p in snap.iterdir())
    assert left == ["New-Chart.ti1", "New-Chart.ti2"], \
        f"files from the previous chart survived: {left}"


def test_an_empty_chart_list_leaves_the_stored_chart_alone(tmp_path):
    """Emptying only happens when there is a new chart to put in — otherwise a
    slot could be left holding neither."""
    import types
    from workflow.verify_chart_snapshot import snapshot_slot

    snap = tmp_path / "chart"; snap.mkdir()
    (snap / "Kept.ti2").write_text("keep me")
    slot = types.SimpleNamespace(snapshot_dir=snap, files_to_copy=lambda: [])

    assert snapshot_slot(slot) is None
    assert (snap / "Kept.ti2").exists()


# ---- a read that measured nothing is a true no-op ------------------------
def _displaced(tab, run, content):
    """Set up exactly what a replacing read leaves behind: the old measurement
    archived, and an empty file in its place."""
    dest = run.old_dir / "2026-07-31_120000"
    dest.mkdir(parents=True)
    (dest / run.measurement_ti3.name).write_text(content)
    run.measurement_ti3.write_text(empty_ti3())
    tab._displaced_measurement = dest
    return dest


def test_measuring_nothing_puts_the_old_measurement_back(qapp, tmp_path,
                                                         monkeypatch):
    """Knut, #130 2026-07-31: *"the empty ti3 should be removed and the ti3 that
    was temporarily stored in old should be returned to where it was placed."*"""
    run = _run(tmp_path)
    run.chart_ti2.write_text("CTI2")
    tab = _tab(tmp_path)
    tab._ti1_path = run.chart_ti2
    dest = _displaced(tab, run, measured_ti3())
    seen = _silence(monkeypatch)

    tab._archive_empty_measurement()

    assert run.measurement_ti3.read_text() == measured_ti3(), \
        "the previous measurement was not put back"
    assert not dest.exists(), "the old/<date_time> folder was left behind"
    assert seen and "put back exactly where it was" in seen[0]


def test_the_empty_file_is_not_left_anywhere(qapp, tmp_path, monkeypatch):
    """It must not survive in old/ either — it is not a measurement."""
    run = _run(tmp_path)
    run.chart_ti2.write_text("CTI2")
    tab = _tab(tmp_path)
    tab._ti1_path = run.chart_ti2
    _displaced(tab, run, measured_ti3())
    _silence(monkeypatch)

    tab._archive_empty_measurement()

    leftovers = [p for p in run.old_dir.rglob("*") if p.is_file()] \
        if run.old_dir.exists() else []
    assert leftovers == [], f"an empty file was left behind: {leftovers}"


def test_a_folder_holding_other_files_is_not_removed(qapp, tmp_path, monkeypatch):
    """Only the folder this read created gets cleaned up; anything else in it
    belongs to somebody."""
    run = _run(tmp_path)
    run.chart_ti2.write_text("CTI2")
    tab = _tab(tmp_path)
    tab._ti1_path = run.chart_ti2
    dest = _displaced(tab, run, measured_ti3())
    (dest / "someone-elses.icc").write_text("keep me")
    _silence(monkeypatch)

    tab._archive_empty_measurement()

    assert dest.exists()
    assert (dest / "someone-elses.icc").exists()


def test_with_nothing_displaced_it_still_archives_the_empty_file(qapp, tmp_path,
                                                                 monkeypatch):
    """The first-read case he described earlier must keep working."""
    run = _run(tmp_path)
    run.chart_ti2.write_text("CTI2")
    run.measurement_ti3.write_text(empty_ti3())
    tab = _tab(tmp_path)
    tab._ti1_path = run.chart_ti2
    tab._displaced_measurement = None
    seen = _silence(monkeypatch)

    tab._archive_empty_measurement()

    assert not run.measurement_ti3.exists()
    assert run.measurement_ti3.name in _archived(run)
    assert "put back exactly where it was" not in seen[0]
