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
    assert "Nothing has been deleted" in text
    assert "Nothing has been deleted, and nothing else has changed" in text
    assert "start the measurement again" in text


def test_the_message_has_no_bracketed_plural(qapp):
    src = inspect.getsource(TabMeasure._archive_empty_measurement)
    assert "(s)" not in src


# ---- the sub-option does not outlive its parent ---------------------------
def _resume_widgets(tab):
    return [(tab._resume_cb, tab._refine_cb), (tab._m_resume_cb, tab._m_refine_cb)]


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
    for parent, sub in _resume_widgets(tab):
        assert parent.isHidden()
        assert sub.isHidden(), \
            "the sub-option stayed on screen under a hidden parent"
        assert not sub.isChecked()


def test_no_chart_hides_the_sub_option_too(qapp, tmp_path):
    tab = _tab(tmp_path)
    tab._ti1_path = None
    tab._update_resume_availability()
    for _parent, sub in _resume_widgets(tab):
        assert sub.isHidden()


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

    for parent, sub in _resume_widgets(tab):
        assert not parent.isHidden()
        assert not sub.isHidden()
        assert sub.isEnabled()
