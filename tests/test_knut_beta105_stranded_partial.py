"""#130 (Knut, 2026-07-30, testing beta.104): readings saved when a measurement
stopped early must not become unreachable.

*"I loaded a project that had a run with a file 'Test-Profiling-P.ti3.engine-
partial'. But the measure tab did not register that it had a partial measurement.
No popup 'This chart already has a measurement' warning message happened when
opening the measure tab, or moving from another run to the run that has this file.
The checkbox for 'Refine...' and 'Show overlay...' was not visible. A partial
stored measurement should be allowed to be continued on, and show overlay, and get
warned."*

Two faults sat behind that, and the first explains how he got into the state at
all:

1. The backup was ORPHANED. ``reset_chart_artefacts`` archives ``<stem>.ti3``
   when a re-generation would displace it, but it named only that file — so the
   ``.engine-partial`` beside it stayed in the run folder while the measurement it
   belonged to moved into ``old/``. That is a run holding nothing but a backup.

2. Nothing ever read a backup BACK. Every feature keys on ``<stem>.ti3``, so the
   readings were on disk and unreachable — the exact opposite of why the copy is
   taken ("the user's measurements must never be lost").

The fix recovers the partial as the run's ordinary measurement, which is
deliberately the whole of it: the resume tick, the overlay and the
already-measured window then work without knowing the file was ever special.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.file_manager import FileManager, Project, Run   # noqa: E402
from core.settings import AppSettings                     # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _partial_with_readings(n: int = 3) -> str:
    """A partial measurement that actually holds readings.

    Since beta.107 the recovery refuses a backup with no data rows — an empty
    backup is not readings to carry on from (Knut, #130 2026-07-30). These
    fixtures used a one-line stand-in, which the guard now correctly rejects, so
    they carry real rows.
    """
    rows = "\n".join(f"{i} A{i} 50 50 50 20 20 20" for i in range(1, n + 1))
    return (
        "CTI3\n\n"
        'DESCRIPTOR "partial measurement"\n'
        'TARGET_INSTRUMENT "X-Rite ColorMunki"\n\n'
        "NUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {n}\nBEGIN_DATA\n{rows}\nEND_DATA\n")


def _run(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    root = tmp_path / "ChromIQ"
    root.mkdir(exist_ok=True)
    s.set("custom_output_path", str(root))
    fm = FileManager(s)
    proj = Project.create(root / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    fm.set_target_name("P")
    return s, fm, run


# ---- 1. the backup travels with the measurement it belongs to -------------
def test_the_partial_is_named_by_the_run_itself():
    """A string built at each call site is a string one site can forget — which
    is how it came to be left behind."""
    assert Run.partial_ti3.__doc__
    src = inspect.getsource(Run.partial_ti3.fget)
    assert '.ti3.engine-partial' in src


def test_the_backup_matches_the_name_the_engine_writes():
    """Two places name this file; they must agree, or recovery silently finds
    nothing."""
    from workflow.measure_manager import MeasureManager
    src = inspect.getsource(MeasureManager._backup_partial_ti3)
    assert 'ti3.name + ".engine-partial"' in src


def test_a_regeneration_archives_the_partial_with_the_measurement(tmp_path):
    """This is what stranded it: the .ti3 went to old/ and the backup stayed."""
    _s, _fm, run = _run(tmp_path)
    run.chart_ti1.write_text("CTI1", encoding="utf-8")
    run.chart_ti2.write_text("CTI2", encoding="utf-8")
    run.measurement_ti3.write_text("CTI3 measured", encoding="utf-8")
    run.partial_ti3.write_text(_partial_with_readings(), encoding="utf-8")

    run.reset_chart_artefacts()

    assert not run.measurement_ti3.exists()
    assert not run.partial_ti3.exists(), \
        "the partial was left behind in the run folder again"
    archived = sorted(p.name for p in run.old_dir.rglob("*") if p.is_file())
    assert f"{run.stem}.ti3" in archived
    assert f"{run.stem}.ti3.engine-partial" in archived, \
        "the readings' backup did not travel with the measurement"


def test_keeping_results_keeps_the_partial_too(tmp_path):
    """Restore Used Chart redraws the pages and must not touch the measurement —
    nor the backup of it."""
    _s, _fm, run = _run(tmp_path)
    run.chart_ti2.write_text("CTI2", encoding="utf-8")
    run.measurement_ti3.write_text("CTI3", encoding="utf-8")
    run.partial_ti3.write_text(_partial_with_readings(), encoding="utf-8")

    run.reset_chart_artefacts(keep_results=True)

    assert run.measurement_ti3.exists()
    assert run.partial_ti3.exists()


# ---- 2. a stranded backup is offered back --------------------------------
def test_a_backup_beside_its_measurement_is_not_stranded(tmp_path):
    """The ordinary case after a successful resume: both files exist, the
    measurement is the real one, and nothing needs recovering."""
    _s, _fm, run = _run(tmp_path)
    run.measurement_ti3.write_text("CTI3", encoding="utf-8")
    run.partial_ti3.write_text(_partial_with_readings(), encoding="utf-8")
    assert run.recoverable_partial_ti3() is None


def test_a_backup_without_its_measurement_is_recoverable(tmp_path):
    """Knut's run."""
    _s, _fm, run = _run(tmp_path)
    run.partial_ti3.write_text(_partial_with_readings(), encoding="utf-8")
    assert run.recoverable_partial_ti3() == run.partial_ti3


def test_no_backup_means_nothing_to_recover(tmp_path):
    _s, _fm, run = _run(tmp_path)
    assert run.recoverable_partial_ti3() is None
    run.measurement_ti3.write_text("CTI3", encoding="utf-8")
    assert run.recoverable_partial_ti3() is None


# ---- the Measure tab acts on it ------------------------------------------
def _tab(tmp_path, qapp):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    s, fm, run = _run(tmp_path)
    tab = TabMeasure(ArgyllRunner(s), s)
    return tab, run


def test_recovering_makes_it_the_runs_measurement(qapp, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    tab, run = _tab(tmp_path, qapp)
    run.chart_ti2.write_text("CTI2", encoding="utf-8")
    run.partial_ti3.write_text(_partial_with_readings(), encoding="utf-8")
    tab._ti1_path = run.chart_ti2

    chosen = {}

    def _exec(self):
        # Answer with the accepting button, as a user pressing "Recover" does.
        for b in self.buttons():
            if "Recover" in b.text():
                chosen["btn"] = b
        return 0

    monkeypatch.setattr(QMessageBox, "exec", _exec)
    monkeypatch.setattr(QMessageBox, "clickedButton",
                        lambda self: chosen.get("btn"))

    assert tab._recover_stranded_partial() is True
    assert run.measurement_ti3.read_text(encoding="utf-8") == _partial_with_readings()
    assert run.partial_ti3.exists(), "the backup must be kept either way"


def test_declining_leaves_everything_and_stops_asking(qapp, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    tab, run = _tab(tmp_path, qapp)
    run.chart_ti2.write_text("CTI2", encoding="utf-8")
    run.partial_ti3.write_text(_partial_with_readings(), encoding="utf-8")
    tab._ti1_path = run.chart_ti2

    seen = []
    chosen = {}

    def _exec(self):
        seen.append(1)
        for b in self.buttons():
            if "Leave" in b.text():
                chosen["btn"] = b
        return 0

    monkeypatch.setattr(QMessageBox, "exec", _exec)
    monkeypatch.setattr(QMessageBox, "clickedButton",
                        lambda self: chosen.get("btn"))

    assert tab._recover_stranded_partial() is False
    assert not run.measurement_ti3.exists()
    assert len(seen) == 1
    # Asked once and declined: not asked again while the app runs.
    assert tab._recover_stranded_partial() is False
    assert len(seen) == 1, "it asked again after being told to leave it alone"


def test_it_is_offered_before_the_already_measured_window(qapp):
    """Order matters: recovering is what gives the already-measured offer
    something to offer, so it has to run first."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._offer_existing_overlay_now)
    assert src.index("_recover_stranded_partial") < \
        src.index("_maybe_offer_existing_overlay")


def test_nothing_is_recovered_over_a_running_measurement(qapp, tmp_path):
    tab, run = _tab(tmp_path, qapp)
    run.chart_ti2.write_text("CTI2", encoding="utf-8")
    run.partial_ti3.write_text(_partial_with_readings(), encoding="utf-8")
    tab._ti1_path = run.chart_ti2

    class _Busy:
        is_running = True
    tab._runner = _Busy()                     # type: ignore[assignment]
    assert tab._recover_stranded_partial() is False
    assert not run.measurement_ti3.exists()


def test_the_window_says_nothing_is_overwritten(qapp):
    """It only ever runs when the run has no measurement, and saying so is what
    stops the offer reading like a risk."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._recover_stranded_partial)
    assert "Nothing is overwritten" in src
    assert "backup file is kept" in src
    assert "(s)" not in src
