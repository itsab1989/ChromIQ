""""Measure again to average" moves the measurement away BEFORE it knows the
next read can start, and every refusal in `_on_start` returned without it.

Found by the combined adversary round of 2026-09-16 (B8-218), pointed at the
averaging door's remaining branch: rounds 5 and 6 closed every ending that
happens AFTER chartread has run, and this is the one where chartread never runs.

`_apply_completion_action("again")` calls `Run.promote_measurement_to_read`,
which MOVES `<run>/<chart>.ti3` into `reads/read1.ti3`, and only then fires
`_start_averaging_read` through a zero-delay timer. `_on_start` then asks its
questions -- a dozen early returns, several of them windows with a Cancel
button -- and `_start_averaging_read` ended on a bare `self._on_start()`.

WHAT A PERSON SAW, driven on screen in a real window on a real 240-patch
measurement, with TWO DIFFERENT real refusals
(``~/Desktop/ChromIQ-beta18-proof/combined-round-7/``):

* ``A-result.json`` / ``A2-stored-chart-differs.png`` -- Cancel on "Stored
  chart differs", a window whose own words are *"Cancel - nothing is written
  and no measurement starts"* and whose last paragraph says *"You are averaging
  several readings of this run"*.
* ``B-result.json`` / ``B3-bidirectional-reading-on-a-fixed-order-chart.png``
  -- Cancel on the fixed-order bidirectional warning, where Cancel is the
  DEFAULT button.

Afterwards, in both, identically:

* the run folder held **no** ``.ti3`` at all; the reading was in ``reads/``,
* **nothing whatever was said** -- the log's last line was still
  "[INFO] First read saved as reads/read1.ti3",
* the Build Profile tab still NAMED ``runs/run1/<chart>.ti3``, a file that no
  longer existed (``B9-the-build-profile-tab.png``), and pressing **Build
  Profile** answered "[ERROR] No valid .ti3 file selected."

``C-result.json`` and ``D-result.json`` are the same two drives afterwards: the
run holds its own ``.ti3`` again, ``reads/read1.ti3`` is still there, the log
carries round 5's sentence, and Build Profile really runs colprof.

`_session_live` is the marker, because it is the one `_on_start` sets at its own
point of no return, one line before `self._manager.start(...)`.
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
from core.file_manager import FileManager, Project         # noqa: E402
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
    run.chart_ti2.write_text("CTI2\nNUMBER_OF_SETS 8\n", encoding="utf-8")
    run.chart_ti1.write_text("CTI1\n", encoding="utf-8")
    t._ti1_path = run.chart_ti1
    yield t, run
    t.deleteLater()


def _measure_then_measure_again(t, run, *, the_read_starts: bool):
    """Exactly the app's own moves: a finished read, then the person presses
    "Measure again to average" -- and `_on_start` either commits to the read or
    refuses, the way each of its dozen guards refuses: it returns."""
    run.measurement_ti3.write_text(_ti3(20.0), encoding="utf-8")
    t._averaging_active = False
    cur, reads = t._promote_completed_read(run.measurement_ti3)
    started: list[bool] = []

    def _on_start():
        started.append(True)
        if the_read_starts:
            t._session_live = True          # `_on_start`'s point of no return
    t._on_start = _on_start                 # type: ignore[method-assign]
    t._session_live = False
    # the button, and the zero-delay timer it fires, taken in one step
    t._apply_completion_action(run.measurement_ti3, cur, reads, "again", "mean")
    t._start_averaging_read()
    assert started, "the fixture never reached `_on_start` at all"
    # `_promote_completed_read` reports [] for the first read of a set (it
    # promotes inside `_apply_completion_action`), so the reads are asked for
    # after the fact rather than carried forward from a call that had none.
    return run.reads()


# ---------------------------------------------------------------------------
# the premise, measured rather than assumed
# ---------------------------------------------------------------------------

def test_measure_again_really_does_empty_the_run_first(tab):
    t, run = tab
    run.measurement_ti3.write_text(_ti3(20.0), encoding="utf-8")
    t._averaging_active = False
    cur, reads = t._promote_completed_read(run.measurement_ti3)
    t._start_averaging_read = lambda: None                # the timer, stubbed
    t._apply_completion_action(run.measurement_ti3, cur, reads, "again", "mean")
    assert not run.measurement_ti3.exists(), (
        "promote_measurement_to_read MOVES it; this is why a refusal one line "
        "later leaves the run with nothing")
    assert [p.name for p in run.reads()] == ["read1.ti3"]


# ---------------------------------------------------------------------------
# …and a read that never starts puts it back
# ---------------------------------------------------------------------------

def test_a_read_that_never_starts_leaves_the_run_holding_a_measurement(tab):
    t, run = tab
    _measure_then_measure_again(t, run, the_read_starts=False)
    assert run.measurement_ti3.is_file(), (
        "every guard in `_on_start` simply returns, and the reading the person "
        "took had already been moved into reads/")


def test_the_measurement_it_puts_back_is_the_reading_that_was_taken(tab):
    t, run = tab
    reads = _measure_then_measure_again(t, run, the_read_starts=False)
    assert run.measurement_ti3.read_bytes() == reads[-1].read_bytes()


def test_the_read_is_still_in_the_reads_folder(tab):
    """A COPY, never a move: the set is still live and `reads/` keeps it."""
    t, run = tab
    _measure_then_measure_again(t, run, the_read_starts=False)
    assert [p.name for p in run.reads()] == ["read1.ti3"]


def test_the_log_says_what_was_kept(tab):
    t, run = tab
    _measure_then_measure_again(t, run, the_read_starts=False)
    text = t._log.toPlainText()
    assert "read1.ti3" in text and "this run's measurement again" in text, \
        text[-400:]


def test_the_set_is_still_live_so_the_next_read_still_averages(tab):
    t, run = tab
    _measure_then_measure_again(t, run, the_read_starts=False)
    assert t._averaging_active is True


# ---------------------------------------------------------------------------
# …and a read that DOES start is left completely alone
# ---------------------------------------------------------------------------

def test_a_read_that_really_starts_is_not_interfered_with(tab):
    """chartread truncates its output file the moment it starts, so putting a
    read back over a live session would be the worse bug of the two."""
    t, run = tab
    _measure_then_measure_again(t, run, the_read_starts=True)
    assert not run.measurement_ti3.exists(), (
        "the read is running; the run's .ti3 is chartread's to write")
    assert "this run's measurement again" not in t._log.toPlainText()


def test_nothing_is_put_back_when_the_set_is_not_live(tab):
    """Outside an averaging set there is nothing in `reads/` that belongs to
    this run's measurement, and round 5's guard already says so."""
    t, run = tab
    run.reads_dir.mkdir(parents=True, exist_ok=True)
    (run.reads_dir / "read1.ti3").write_text(_ti3(5.0), encoding="utf-8")
    t._averaging_active = False
    t._restore_a_read_when_the_set_lost_its_measurement(run.measurement_ti3)
    assert not run.measurement_ti3.exists()


# ---------------------------------------------------------------------------
# the marker, and the mechanism, are the shared ones
# ---------------------------------------------------------------------------

def test_the_start_is_judged_by_the_marker_on_start_actually_sets():
    """`_session_live` and not, say, `_runner.is_running`: the engine and stock
    chartread start different things, and this is the one line both pass."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._start_averaging_read)
    body = src.split('"""')[-1]              # the code, not the prose about it
    assert "_session_live" in body, (
        "a read that never started must be noticed, not assumed away")
    assert "_restore_a_read_when_the_set_lost_its_measurement" in body, (
        "round 5's mechanism and round 5's sentence, not a second copy")
    assert body.index("self._on_start()") < body.index("_session_live"), (
        "the marker is read AFTER `_on_start` has had its chance to set it")


def test_start_averaging_read_never_assigns_the_marker():
    """Only `_on_start` and `_on_measure_done` own it; writing it here is the
    one way this guard could switch off a session that really is live."""
    from ui.tabs.tab_measure import TabMeasure
    body = inspect.getsource(
        TabMeasure._start_averaging_read).split('"""')[-1]
    assert "self._session_live =" not in body


def test_on_start_still_sets_the_marker_at_its_point_of_no_return():
    """The whole guard rests on this: if `_on_start` stops setting
    `_session_live`, a read that starts perfectly well gets a read copied over
    the file chartread is about to write."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._on_start)
    assert "self._session_live = True" in src
    assert src.index("self._session_live = True") < src.index(
        "self._manager.start("), (
        "it must be set BEFORE the reader is launched, or the window between "
        "the two is a hole")
