"""Every averaging ending must leave the run holding the sheet it builds from.

Found by the combined adversary round of 2026-09-15 (B8-213), pointed at the
averaging path that round 4 had only reached at its very end.

``Run.promote_measurement_to_read`` MOVES ``<stem>.ti3`` into
``reads/readN.ti3``. Round 4 reached the ONE ending that writes a file back --
*Average all reads & build*, whose output is ``Run.measurement_ti3``. The other
endings of the same set did not:

* **Use last read only** handed ``reads/readN.ti3`` to Build Profile and left
  the run itself with no measurement at all;
* the same is what CLOSING the completion window does, because ``use_last`` is
  its default action whenever two or more reads exist;
* and *Measure again to average* followed by a second read that produces no
  file -- Stop before the first patch, or any failure -- left the run holding
  nothing while ChromIQ said *"no measurement (.ti3) file was created"* about a
  chart that had been measured perfectly well a minute earlier.

WHY IT MATTERS IS THE SPECIFICATION'S OWN SENTENCE. §I.7 of
``docs/design/unified_measurement_management.md`` requires a filed measurement
to take the run's canonical stem, *"because the report finds its chart by that
stem (``measurement_report._find_reference_ti2``) and a measurement filed under
any other name falls back to ``reference_source: device`` without saying so"*.

WHAT A USER SAW, driven on screen in a real window with the app's own
``_promote_completed_read`` / ``_apply_completion_action`` and the real
completion dialog clicked by its own button, on two real 90-patch reads of one
chart (``~/Desktop/ChromIQ-beta18-proof/combined-round-5/``,
``A2-A2-the-report-window.png``, ``A-result.json``): after *Use last read
only* the run folder held NO ``.ti3``; the Measurement Report window opened on
that run with **zero rows**; and the report the Preferences option saves
automatically went to ``runs/run1/reads/reports/`` -- a folder nothing in
ChromIQ ever lists -- carrying ``"chart": "read2"``,
``"sheet_kind": "standalone"`` and ΔE00 16.346 against a device reference,
while the log said *"Measurement report saved"*. ``B-result.json`` and
``B2-B2-the-report-window.png`` are the same drive afterwards: the run holds
its own ``.ti3``, the report is in ``runs/run1/reports/`` as
``"sheet_kind": "profiling"`` with ΔE00 16.379 against the chart, and the
window shows the row.
"""
from __future__ import annotations

import json
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


#: A tiny but REAL .ti3 -- `build_report` parses it, so a placeholder would make
#: every report assertion below pass for the wrong reason.
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


@pytest.fixture
def tab(qapp, tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path))
    s.set("averaging_enabled", True)
    s.set("save_measurement_report", True)
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
    yield t, run
    t.deleteLater()


def _measure(run: Run, seed: float) -> None:
    """What chartread leaves behind: the run's own .ti3."""
    run.measurement_ti3.write_text(_ti3(seed), encoding="utf-8")


def _a_set_of_two(tab, run: Run):
    """Drive the app's own moves: measure, "Measure again to average", measure
    again. Returns (current, reads) exactly as the tab computes them."""
    _measure(run, 20.0)
    tab._averaging_active = False
    cur, reads = tab._promote_completed_read(run.measurement_ti3)
    tab._apply_completion_action(run.measurement_ti3, cur, reads, "again", "mean")
    _measure(run, 31.0)
    return tab._promote_completed_read(run.measurement_ti3)


# ---------------------------------------------------------------------------
# "Use last read only"
# ---------------------------------------------------------------------------

def test_use_last_read_only_leaves_the_run_holding_that_read(tab):
    t, run = tab
    cur, reads = _a_set_of_two(t, run)
    assert not run.measurement_ti3.exists()      # the app moved it away
    t._apply_completion_action(run.measurement_ti3, cur, reads, "use_last", "mean")
    assert run.measurement_ti3.is_file(), (
        "the run builds from this read and must hold it")
    assert run.measurement_ti3.read_bytes() == cur.read_bytes()


def test_use_last_read_only_keeps_every_read_in_the_reads_folder(tab):
    t, run = tab
    cur, reads = _a_set_of_two(t, run)
    t._apply_completion_action(run.measurement_ti3, cur, reads, "use_last", "mean")
    assert sorted(p.name for p in run.reads()) == ["read1.ti3", "read2.ti3"]


def test_use_last_read_only_hands_build_profile_the_runs_own_file(tab):
    t, run = tab
    got: list[Path] = []
    t.measure_finished.connect(got.append)
    cur, reads = _a_set_of_two(t, run)
    t._apply_completion_action(run.measurement_ti3, cur, reads, "use_last", "mean")
    assert got and got[-1] == run.measurement_ti3, (
        f"Build Profile was handed {got[-1] if got else None}")


def test_use_last_read_only_files_its_report_where_the_run_can_see_it(tab):
    t, run = tab
    cur, reads = _a_set_of_two(t, run)
    t._apply_completion_action(run.measurement_ti3, cur, reads, "use_last", "mean")
    mine = sorted((run.dir / "reports").glob("report_*.json"))
    orphan = sorted((run.reads_dir / "reports").glob("report_*.json"))
    assert mine, "the run's own reports/ holds the report"
    assert not orphan, (
        "reads/reports/ is a folder nothing in ChromIQ ever lists")
    rep = json.loads(mine[-1].read_text(encoding="utf-8"))
    assert rep["ti3"] == run.measurement_ti3.name
    assert rep["chart"] == run.stem
    assert rep["sheet_kind"] == "profiling", (
        "a read filed under any other name is judged as a standalone sheet")


def test_the_report_is_judged_against_the_runs_own_chart(tab):
    """§I.7's stated reason: the wrong stem silently takes the chart away."""
    from workflow.measurement_report import _find_reference_ti2
    t, run = tab
    cur, reads = _a_set_of_two(t, run)
    assert not _find_reference_ti2(cur).is_file()        # inside reads/
    t._apply_completion_action(run.measurement_ti3, cur, reads, "use_last", "mean")
    live = [p for p in (run.measurement_ti3, cur) if p.is_file()][0]
    assert live == run.measurement_ti3
    assert _find_reference_ti2(live) == run.chart_ti2 and live.is_file()


def test_closing_the_completion_window_is_the_same_ending(tab):
    """The default action with two reads is ``use_last``, so the red button and
    Escape take the same route and must land in the same place."""
    import inspect
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._show_completion_dialog)
    assert '"use_last" if n_reads >= 2' in src


# ---------------------------------------------------------------------------
# the second read that never arrives
# ---------------------------------------------------------------------------

def test_a_stopped_second_read_keeps_the_reading_already_taken(tab):
    t, run = tab
    _measure(run, 20.0)
    t._averaging_active = False
    cur, reads = t._promote_completed_read(run.measurement_ti3)
    t._apply_completion_action(run.measurement_ti3, cur, reads, "again", "mean")
    assert not run.measurement_ti3.exists()
    t._restore_a_read_when_the_set_lost_its_measurement(run.measurement_ti3)
    assert run.measurement_ti3.is_file()
    assert run.measurement_ti3.read_bytes() == (run.reads_dir / "read1.ti3").read_bytes()


def test_the_restore_is_a_copy_so_the_set_keeps_every_read(tab):
    t, run = tab
    _measure(run, 20.0)
    t._averaging_active = False
    cur, reads = t._promote_completed_read(run.measurement_ti3)
    t._apply_completion_action(run.measurement_ti3, cur, reads, "again", "mean")
    t._restore_a_read_when_the_set_lost_its_measurement(run.measurement_ti3)
    assert [p.name for p in run.reads()] == ["read1.ti3"]


def test_the_restore_says_what_was_kept(tab):
    t, run = tab
    _measure(run, 20.0)
    t._averaging_active = False
    cur, reads = t._promote_completed_read(run.measurement_ti3)
    t._apply_completion_action(run.measurement_ti3, cur, reads, "again", "mean")
    before = t._log.toPlainText()
    t._restore_a_read_when_the_set_lost_its_measurement(run.measurement_ti3)
    said = t._log.toPlainText()[len(before):]
    assert "read1.ti3" in said and "measurement again" in said, said


def test_the_ending_that_produced_a_file_is_left_alone(tab):
    """No averaging set: the measurement is where chartread wrote it and
    nothing may be copied on top of it."""
    t, run = tab
    _measure(run, 20.0)
    t._averaging_active = False
    before = run.measurement_ti3.read_bytes()
    t._restore_a_read_when_the_set_lost_its_measurement(run.measurement_ti3)
    assert run.measurement_ti3.read_bytes() == before
    assert not run.reads_dir.exists() or not run.reads()


def test_a_standalone_read_is_never_copied_anywhere(tab):
    """Averaging off: `_promote_completed_read` moves nothing, so the ending
    must hand over exactly the file chartread wrote."""
    t, run = tab
    _measure(run, 20.0)
    t._averaging_active = False
    cur, reads = t._promote_completed_read(run.measurement_ti3)
    assert cur == run.measurement_ti3 and reads == []
    got = t._keep_the_read_as_the_runs_measurement(run.measurement_ti3, cur)
    assert got == run.measurement_ti3


def test_a_copy_that_fails_still_ends_the_measurement(tab, monkeypatch):
    """An ending must never be lost to a read-only folder."""
    import shutil as _sh
    t, run = tab
    cur, reads = _a_set_of_two(t, run)
    monkeypatch.setattr(
        _sh, "copy2",
        lambda *a, **k: (_ for _ in ()).throw(OSError("read-only")))
    got: list[Path] = []
    t.measure_finished.connect(got.append)
    t._apply_completion_action(run.measurement_ti3, cur, reads, "use_last", "mean")
    assert got and got[-1] == cur
