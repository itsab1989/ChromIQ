"""An `average` that refuses must leave the run holding a measurement.

Found by the combined adversary round of 2026-09-15 (B8-215), pointed at round
5's own fix from the side it does not reach.

Round 5 (B8-213) gave two of the endings that can strand an averaging set a
file back: *Use last read only*, and a second read that produces nothing. There
is a THIRD, one branch further along the same door, and it is the one that only
ever appears when something has already gone wrong.

``Run.promote_measurement_to_read`` MOVES every read into ``reads/readN.ti3``,
and ``AverageRunner`` writes its output only on success. So when ``average``
refuses -- Argyll's own ``set_count_mismatch``, ``field_mismatch``,
``read_error``, or simply a non-zero exit because the output could not be
written -- ``_run_average_and_proceed``'s failure branch showed a window and
returned, leaving the run folder with no ``.ti3`` at all.

WHAT A USER SAW, driven on screen in a real window with a REAL Argyll refusal
(``~/Desktop/ChromIQ-beta18-proof/combined-round-6/``, ``A-result.json``,
``A1-the-averaging-failed-window.png``, ``A2-the-build-profile-tab-it-sends-
you-to.png``): two promoted reads, ``average: Error - File 'reads/read2.ti3'
has 15 sets, file 'reads/read1.ti3 has 90``, and afterwards

* the run folder held **no** ``.ti3``,
* the Measurement Report window opened on that run with **zero rows**,
* the Build Profile tab read **"No file selected"**,

all three under a window whose last sentence is *"Your individual reads are
still saved -- you can continue from the Build Profile tab using one of them."*

``D-result.json`` is the same drive afterwards: the run holds its own ``.ti3``
again, ``reads/`` still holds both reads, the report window shows its row, and
the Build Profile tab holds the run's measurement, which is what makes that
sentence true rather than merely hopeful.
"""
from __future__ import annotations

import inspect
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402
from PyQt6.QtCore import QSettings                         # noqa: E402
from PyQt6.QtWidgets import QApplication                   # noqa: E402

from core.argyll_runner import ArgyllRunner                # noqa: E402
from core.file_manager import FileManager, Project, Run    # noqa: E402
from core.settings import AppSettings                      # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _ti3(n_start: float) -> str:
    rows = "\n".join(
        f"{i + 1} A{i + 1} {i * 7 % 101} {i * 13 % 101} {i * 29 % 101} "
        f"{n_start + i:.4f} {n_start + i + 1:.4f} {n_start + i + 2:.4f}"
        for i in range(8))
    return ("CTI3\n\nDEVICE_CLASS \"OUTPUT\"\nCOLOR_REP \"RGB_XYZ\"\n"
            "NUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n"
            "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
            "END_DATA_FORMAT\nNUMBER_OF_SETS 8\nBEGIN_DATA\n"
            + rows + "\nEND_DATA\n")


def _ti2(stem: str) -> str:
    rows = "\n".join(
        f"{i + 1} A{i + 1} {i * 7 % 101} {i * 13 % 101} {i * 29 % 101} "
        f"{10.0 + i:.4f} {11.0 + i:.4f} {12.0 + i:.4f}" for i in range(8))
    return ("CTI2\n\nDEVICE_CLASS \"OUTPUT\"\nCOLOR_REP \"RGB_XYZ\"\n"
            "NUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n"
            "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
            "END_DATA_FORMAT\nNUMBER_OF_SETS 8\nBEGIN_DATA\n"
            + rows + "\nEND_DATA\n")


class _RefusingAverage:
    """What `AverageRunner` does when Argyll refuses: no output, on_finish(None).

    The real one is driven on screen in the proof folder; here the refusal is
    the fixture, so every ending below is measured without an Argyll install.
    """

    REASON = ("set_count_mismatch",
              "The reads contain different numbers of patches, so they can't "
              "be averaged. Re-read the same chart for every pass.")

    def __init__(self) -> None:
        self.calls = 0

    def run(self, params, on_line, on_finish) -> None:
        self.calls += 1
        on_line("average: Error - File 'reads/read2.ti3' has 15 sets, "
                "file 'reads/read1.ti3 has 90")
        on_finish(None)                      # …and the output is NOT written

    def primary_failure(self):
        return self.REASON


@pytest.fixture
def tab(qapp, tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path))
    s.set("averaging_enabled", True)
    fm = FileManager(s)
    proj = Project.create(tmp_path / "P", "P")
    proj.current_run().ensure_dir()
    fm.set_target_name("P")
    from ui.tabs.tab_measure import TabMeasure
    t = TabMeasure(ArgyllRunner(s), s)
    t.set_target_controller(MeasurementTargetController(fm))
    run = proj.current_run()
    run.chart_ti2.write_text(_ti2(run.stem), encoding="utf-8")
    run.chart_ti1.write_text("CTI1\n", encoding="utf-8")
    t._ti1_path = run.chart_ti1
    t._start_averaging_read = lambda: None
    t._avg_runner = _RefusingAverage()
    # The failure WINDOW is modal; its text is measured by its own suite. Here
    # it is recorded so no test can hang on `.exec()`.
    shown: list[str] = []
    t._show_average_failed_dialog = shown.append          # type: ignore[method-assign]
    t._windows_shown = shown
    yield t, run
    t.deleteLater()


def _a_set_of_two_then_average(tab):
    """Exactly the app's own moves: measure, "Measure again to average",
    measure again, "Average all reads & build" -- and the average refuses."""
    t, run = tab
    run.measurement_ti3.write_text(_ti3(20.0), encoding="utf-8")
    t._averaging_active = False
    cur, reads = t._promote_completed_read(run.measurement_ti3)
    t._apply_completion_action(run.measurement_ti3, cur, reads, "again", "mean")
    run.measurement_ti3.write_text(_ti3(31.0), encoding="utf-8")
    cur, reads = t._promote_completed_read(run.measurement_ti3)
    assert not run.measurement_ti3.exists(), "the app moved both reads away"
    t._apply_completion_action(run.measurement_ti3, cur, reads,
                               "average", "mean")
    return cur, reads


# ---------------------------------------------------------------------------
# the run is not left empty
# ---------------------------------------------------------------------------

def test_a_refused_average_leaves_the_run_holding_a_measurement(tab):
    t, run = tab
    _a_set_of_two_then_average(tab)
    assert t._avg_runner.calls == 1, "the average really was attempted"
    assert run.measurement_ti3.is_file(), (
        "the reads were moved into reads/ and the average wrote nothing, so "
        "this branch left the run with no measurement at all")


def test_the_measurement_it_keeps_is_the_read_taken_last(tab):
    t, run = tab
    _cur, reads = _a_set_of_two_then_average(tab)
    assert run.measurement_ti3.read_bytes() == reads[-1].read_bytes()


def test_every_read_is_still_in_the_reads_folder(tab):
    t, run = tab
    _a_set_of_two_then_average(tab)
    assert sorted(p.name for p in run.reads()) == ["read1.ti3", "read2.ti3"], (
        "a COPY, never a move: the set keeps every read it has")


def test_the_tab_the_window_names_is_armed_with_it(tab):
    """The window says to continue from the Build Profile tab; that tab is
    handed the run's measurement, exactly as every other ending hands it one."""
    t, run = tab
    got: list[Path] = []
    t.measure_finished.connect(got.append)
    _a_set_of_two_then_average(tab)
    assert got and got[-1] == run.measurement_ti3, (
        f"Build Profile was handed {got[-1] if got else None}")


def test_the_log_says_which_read_it_kept(tab):
    t, run = tab
    _a_set_of_two_then_average(tab)
    text = t._log.toPlainText()
    assert "read2.ti3" in text and "this run's measurement" in text, text[-400:]


def test_the_failure_window_is_still_shown(tab):
    """Keeping a read is not a reason to stop telling somebody it failed."""
    t, _run = tab
    _a_set_of_two_then_average(tab)
    assert t._windows_shown and "different numbers of patches" in \
        t._windows_shown[-1]


def test_a_run_that_still_holds_a_measurement_is_not_written_over(tab):
    """`_put_the_last_read_back` fills a gap; it never displaces a file."""
    t, run = tab
    run.measurement_ti3.write_text(_ti3(20.0), encoding="utf-8")
    t._averaging_active = False
    cur, reads = t._promote_completed_read(run.measurement_ti3)
    t._apply_completion_action(run.measurement_ti3, cur, reads, "again", "mean")
    run.measurement_ti3.write_text(_ti3(31.0), encoding="utf-8")
    cur, reads = t._promote_completed_read(run.measurement_ti3)
    keep = _ti3(99.0)
    run.measurement_ti3.write_text(keep, encoding="utf-8")   # an averaged result
    t._apply_completion_action(run.measurement_ti3, cur, reads,
                               "average", "mean")
    assert run.measurement_ti3.read_text(encoding="utf-8") == keep


def test_a_refusal_with_nothing_in_reads_says_nothing_and_does_nothing(tab):
    """No reads means nothing to put back, and no sentence claiming otherwise."""
    t, run = tab
    assert t._put_the_last_read_back(run.measurement_ti3) is None
    assert "this run's measurement" not in t._log.toPlainText()


# ---------------------------------------------------------------------------
# the mechanism is SHARED, so the two endings cannot drift apart again
# ---------------------------------------------------------------------------

def test_both_endings_put_a_read_back_through_the_same_helper():
    from ui.tabs.tab_measure import TabMeasure
    for meth in (TabMeasure._restore_a_read_when_the_set_lost_its_measurement,
                 TabMeasure._run_average_and_proceed):
        assert "_put_the_last_read_back" in inspect.getsource(meth), (
            f"{meth.__name__} has its own copy of the rule again")


def test_the_helper_copies_rather_than_moves():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._put_the_last_read_back)
    body = src.split('"""')[-1]              # the code, not the prose about it
    assert "shutil.copy2" in body
    assert "shutil.move" not in body and ".rename(" not in body, (
        "reads/ must keep every read it has")
