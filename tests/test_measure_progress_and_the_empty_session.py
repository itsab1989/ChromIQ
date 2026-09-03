"""One screen, one answer: the Measure tab's progress bar and its patch marks
must describe the same measurement.

The owner, 2026-09-03, on his CR30-Test project (390 patches, a previous
measurement of 18):

    *"i opened the cr30 test chart and started measurement while not proceeding
    with the already available one but starting fresh. progress bar still showed
    4,6% when measurement was running and no patch was displayed as already
    measured"*

    *"after i stopped the measurement without having measured a single patch it
    showed the measured vs expected patches from before but the progress bar was
    then at 0%"*

18 / 390 = 4.6154 %. The bar was reading the count seeded from the previous
`.ti3` at chart load, which nothing put back to zero when the fresh read moved
that `.ti3` into `old/`; the marks beside it were reading the (empty) live
session. After the stop the two swapped places: the bar was settled from the
file at the top of `_on_measure_done`, before §S3 had judged the session and
restored the previous measurement, so it read a file that was not there — while
everything else in the app went back to 18 of 390.

And a third fault fell out of the same session: `_ti3_mtime_before` was captured
*after* the fresh read archived the old `.ti3`, so it was `None`, so the restored
previous measurement was read as this session's own output. The app then claimed
"partial readings saved", ticked Refine/resume, emitted `measure_finished`, and
saved a dated measurement report that was a byte-for-byte copy of the previous
session's.

`docs/design/unified_measurement_management.md` §S3 already sets the order these
tests pin: S3.1 read the file, S3.2 an empty one goes aside and the archived copy
comes back, and only then does anything else look.
"""
from __future__ import annotations

import inspect
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication, QDialog  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


class _Settings:
    def __init__(self, **over):
        self._d = {"appearance": "dark", "measure_progress_bar": True}
        self._d.update(over)

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value):
        self._d[key] = value


_TI2 = """CTI2

DESCRIPTOR "Argyll Calibration Target chart information 2"
COLOR_REP "iRGB"

NUMBER_OF_FIELDS 5
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B
END_DATA_FORMAT

NUMBER_OF_SETS {n}
BEGIN_DATA
{rows}END_DATA
"""

_TI3 = """CTI3

DESCRIPTOR "Argyll Calibration Target chart information 3"
DEVICE_CLASS "OUTPUT"
COLOR_REP "iRGB_XYZ"

NUMBER_OF_FIELDS 8
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT

NUMBER_OF_SETS {n}
BEGIN_DATA
{rows}END_DATA
"""


def _loc(i: int) -> str:
    return f"{chr(ord('A') + (i - 1) // 26)}{(i - 1) % 26 + 1}"


def _write_ti2(p: Path, n: int) -> Path:
    rows = "".join(f'{i} "{_loc(i)}" 0 0 0\n' for i in range(1, n + 1))
    p.write_text(_TI2.format(n=n, rows=rows), encoding="utf-8")
    return p


def _write_ti3(p: Path, n: int) -> Path:
    rows = "".join(f'{i} "{_loc(i)}" 0 0 0 1 1 1\n' for i in range(1, n + 1))
    p.write_text(_TI3.format(n=n, rows=rows), encoding="utf-8")
    return p


def _make_tab(settings=None):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    s = settings or _Settings()
    return TabMeasure(ArgyllRunner(s), s)


def _his_chart(tmp_path: Path):
    """His chart, to the patch: 390 laid out, 18 already measured."""
    run = tmp_path / "runs" / "run1"
    run.mkdir(parents=True)
    ti1 = run / "CR30-Test.ti1"
    ti1.touch()
    _write_ti2(run / "CR30-Test.ti2", 390)
    _write_ti3(run / "CR30-Test.ti3", 18)
    return ti1


# --------------------------------------------------------------------------
# 4.6 % — the figure he saw, and where it came from
# --------------------------------------------------------------------------

def test_his_chart_really_does_read_four_point_six(tmp_path):
    """Solve for the fraction before believing any explanation of it."""
    from workflow.measurement_state import expected_patches, progress_percent
    ti1 = _his_chart(tmp_path)
    total = expected_patches(ti1.with_suffix(".ti2"))
    assert total == 390
    assert round(progress_percent(18, total), 1) == 4.6


def test_the_bar_starts_at_the_previous_measurements_count(tmp_path):
    """Loading a part-measured chart SHOULD pick it up where it was left."""
    tab = _make_tab()
    tab.set_ti1_path(_his_chart(tmp_path))
    assert tab._progress_base == 18
    assert round(tab._preview.measurement_progress(), 1) == 4.6


# --------------------------------------------------------------------------
# Fault 1 — a fresh read must not carry that count into the new session
# --------------------------------------------------------------------------

def _start_a_read(tab, monkeypatch, *, resume: bool):
    """Run the real `_on_start` with only the questions and the reader stubbed.

    Everything the fault lives in — the archive, the fresh/resume fork, the
    snapshot of the file's age — is the shipped code.
    """
    from ui.tabs.tab_measure import TabMeasure
    started: list = []
    monkeypatch.setattr(TabMeasure, "_confirm_replacing_measurement",
                        lambda self: True)
    monkeypatch.setattr(TabMeasure, "_confirm_nonrandom_bidir",
                        lambda self, p: True)
    monkeypatch.setattr(TabMeasure, "_snapshot_verification_chart",
                        lambda self: True)
    monkeypatch.setattr(TabMeasure, "_read_builds_on_existing",
                        lambda self: resume)
    monkeypatch.setattr(tab._manager, "start",
                        lambda *a, **k: started.append(True))
    tab._on_start()
    assert started, "the reader was never started — the journey stopped early"


def test_a_fresh_read_does_not_carry_the_previous_count(tmp_path, monkeypatch):
    """His symptom, exactly: the bar frozen at 4.6 % with nothing read.

    A read that REPLACES starts from nothing — the file that fed the 18 has
    just been moved into old/, and there is no measurement left to be part of.
    """
    tab = _make_tab()
    ti1 = _his_chart(tmp_path)
    tab.set_ti1_path(ti1)
    assert tab._progress_base == 18                      # seeded at load

    _start_a_read(tab, monkeypatch, resume=False)

    assert not ti1.with_suffix(".ti3").exists()          # archived, as designed
    assert tab._progress_base == 0
    assert tab._progress_locs == set()
    assert tab._preview.measurement_progress() == 0.0


def test_a_resuming_read_keeps_the_count_it_is_adding_to(tmp_path, monkeypatch):
    """The other half of the same fork must not be broken by fixing the first.

    A refine/resume builds on the existing measurement — the overlay is seeded
    from it and the bar counts the same readings, so 18 of 390 is right there.
    """
    tab = _make_tab()
    ti1 = _his_chart(tmp_path)
    tab.set_ti1_path(ti1)

    _start_a_read(tab, monkeypatch, resume=True)

    assert ti1.with_suffix(".ti3").exists()              # never archived
    assert tab._progress_base == 18
    assert round(tab._preview.measurement_progress(), 1) == 4.6


# --------------------------------------------------------------------------
# Fault 2 — the file may only settle the count once §S3 has judged it
# --------------------------------------------------------------------------

def test_the_bar_is_settled_only_after_the_session_has_been_judged():
    """§S3: the verdict acts on the file BEFORE anything else reads it.

    `_finish_session_guard` and `_archive_empty_measurement` are what put an
    empty file aside and bring the previous measurement back. A progress refresh
    in front of them reads the one state that is never the run's answer.
    """
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._on_measure_done)
    settle = src.index("_refresh_progress_from_files()")
    for verdict in ("_finish_session_guard()", "_archive_empty_measurement()"):
        assert src.index(verdict) < settle, (
            f"{verdict} must act on the .ti3 before the progress bar reads it")


def test_after_a_session_that_read_nothing_the_bar_matches_the_file(
        tmp_path, monkeypatch):
    """His second symptom: 0 % beside a run that holds 18 of 390.

    Stop with nothing read, the previous measurement comes back — and the bar
    has to come back with it, because it is describing the same file.
    """
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)

    tab = _make_tab()
    ti1 = _his_chart(tmp_path)
    tab.set_ti1_path(ti1)
    ti3 = ti1.with_suffix(".ti3")
    mtime = ti3.stat().st_mtime

    _start_a_read(tab, monkeypatch, resume=False)
    assert tab._preview.measurement_progress() == 0.0    # the fresh session
    assert not ti3.exists()

    # chartread was killed before the first patch, so it wrote nothing at all.
    tab._all_done_shown = False
    tab._measure_failed = False
    tab._on_measure_done(9)

    assert ti3.exists(), "the previous measurement must be put back"
    assert ti3.stat().st_mtime == pytest.approx(mtime, abs=1e-6)
    assert tab._progress_base == 18
    assert round(tab._preview.measurement_progress(), 1) == 4.6


def test_the_file_settle_is_not_gated_on_the_progress_preference():
    """#156 needs the record of WHICH patches have a reading whether or not the
    bar is on — `_count_strip_progress` says so in as many words. An early
    return here froze that record for anyone who had switched the bar off."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._refresh_progress_from_files)
    assert "_progress_enabled" not in src


def test_the_settle_still_repaints_nothing_when_the_bar_is_off(tmp_path):
    """…and the preference is still honoured, one level down."""
    tab = _make_tab(_Settings(measure_progress_bar=False))
    tab.set_ti1_path(_his_chart(tmp_path))
    tab._refresh_progress_from_files()
    assert tab._progress_base == 18                       # the record is kept
    assert tab._preview.measurement_progress() is None    # the bar is not drawn


# --------------------------------------------------------------------------
# Fault 3 — a session that wrote nothing must not adopt the restored file
# --------------------------------------------------------------------------

def test_the_files_age_is_noted_before_it_is_archived():
    """`_on_measure_done` reads "no file beforehand" as "anything here now is
    this session's". Taken after the archive, that snapshot was always None on
    a fresh read, and the restored measurement walked straight into it."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._on_start)
    assert (src.index("_ti3_mtime_before")
            < src.index("_archive_measurement_before_replacing()")), (
        "the .ti3's mtime must be noted before the file is moved out of the way")


def test_a_session_that_read_nothing_claims_nothing(tmp_path, monkeypatch):
    """No measure_finished, so no report, no completion sound, no resume tick.

    A dated measurement report describing readings that were never taken is a
    false record — and the one his session saved was byte-identical to the
    previous session's.
    """
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)

    tab = _make_tab()
    ti1 = _his_chart(tmp_path)
    tab.set_ti1_path(ti1)

    finished: list = []
    tab.measure_finished.connect(finished.append)

    _start_a_read(tab, monkeypatch, resume=False)
    tab._all_done_shown = False
    tab._measure_failed = False
    tab._on_measure_done(9)

    assert finished == [], (
        "the restored previous measurement was adopted as this session's work")
    assert "partial readings saved" not in tab._log.toPlainText()


def test_a_stop_the_user_chose_is_not_called_a_failure(tmp_path, monkeypatch):
    """The fault the fix above uncovered, and had to fix with it.

    Stop kills the reader, so the exit code is always non-zero; the only thing
    keeping "[ERROR] Measurement failed" off the screen was a .ti3 being there
    afterwards — and the restored previous measurement was standing in for one.
    `MeasureManager.abort` has recorded the deliberate ending all along:
    *"the non-zero exit that follows must not be described as one"*.
    """
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)

    tab = _make_tab()
    tab.set_ti1_path(_his_chart(tmp_path))
    _start_a_read(tab, monkeypatch, resume=False)

    tab._manager.abort()                     # "Discard and stop"
    assert tab._manager.ended_by_the_user
    tab._all_done_shown = False
    tab._measure_failed = False
    tab._on_measure_done(9)                  # the kill's exit code

    log = tab._log.toPlainText()
    assert "Measurement failed" not in log
    assert "no measurement (.ti3) file was created" in log


def test_a_real_failure_is_still_called_one(tmp_path, monkeypatch):
    """…and the mutation that would make that pass by never saying anything."""
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)

    tab = _make_tab()
    tab.set_ti1_path(_his_chart(tmp_path))
    _start_a_read(tab, monkeypatch, resume=False)

    assert not tab._manager.ended_by_the_user   # nobody stopped anything
    tab._all_done_shown = False
    tab._measure_failed = False
    tab._on_measure_done(1)                     # the reader died on its own

    assert "Measurement failed" in tab._log.toPlainText()


def test_a_session_that_really_measured_still_reports(tmp_path, monkeypatch):
    """The mutation that would make the test above pass for the wrong reason:
    never emitting at all. A read that DOES write a fresh .ti3 must still be
    announced."""
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)

    tab = _make_tab()
    ti1 = _his_chart(tmp_path)
    tab.set_ti1_path(ti1)
    ti3 = ti1.with_suffix(".ti3")

    _start_a_read(tab, monkeypatch, resume=False)
    assert not ti3.exists()
    _write_ti3(ti3, 200)                     # chartread's own output
    tab._displaced_measurement = None        # it was replaced, fair and square

    finished: list = []
    tab.measure_finished.connect(finished.append)
    tab._all_done_shown = True
    tab._measure_failed = False
    tab._on_measure_done(0)

    assert [p.name for p in finished] == ["CR30-Test.ti3"]
    assert tab._progress_base == 200
