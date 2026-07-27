"""#130 CRITICAL (Knut): a preset must build the chart into the run the
Profile-run bar shows ("Overwrite run N"), not the project's current (last) run.
The prebuilt "by Pharmacist" presets and the .ti1-based presets (TC9.18,
Spyderprint) bypassed the bar alignment and jumped the chart to the last run."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog               # noqa: E402

from core.argyll_runner import ArgyllRunner                     # noqa: E402
from core.file_manager import FileManager, Project              # noqa: E402
from core.measurement_target import RUN_TYPE_PROFILING          # noqa: E402
from core.settings import AppSettings                           # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402
from ui.tabs.tab_chart import TabChart                          # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _no_dialogs(monkeypatch):
    monkeypatch.setattr(QDialog, "exec", lambda self: 0, raising=False)


def _tab_with_three_runs(tmp_path):
    s = AppSettings(); s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path)); s.set("use_chromiq_layout_engine", False)
    fm = FileManager(s)
    tab = TabChart(ArgyllRunner(s), fm, s)
    tab._switch_mode("manual")
    if not tab._manual_panel_inited:
        tab._init_manual_layout_panel()
    ctl = MeasurementTargetController(fm); tab.set_target_controller(ctl)
    proj = Project.create(tmp_path / "P", "P"); proj.current_run().ensure_dir()
    proj.new_run().ensure_dir(); proj.new_run().ensure_dir()   # run1, run2, run3
    fm.set_target_name("P"); tab._update_name_fields()
    return tab, fm, ctl


def test_prebuilt_preset_builds_into_bar_run_not_last(qapp, tmp_path):
    tab, fm, ctl = _tab_with_three_runs(tmp_path)
    assert Project.load(tmp_path / "P").current_run().id == "run3"   # last is current
    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_PROFILING)

    tab._apply_prebuilt_preset("__chromiq_tc300_builtin__", "P")

    # The chart landed in run1 (the bar's selection), not run3.
    p = Project.load(tmp_path / "P")
    assert p.current_run().id == "run1"
    assert ctl.target.profile_run == "run1"
    assert p.run("run1").chart_ti2.exists()
    assert not p.run("run2").chart_ti2.exists()
    assert not p.run("run3").chart_ti2.exists()


def test_loaded_patch_set_aligns_to_bar_run(qapp, tmp_path, monkeypatch):
    """#130 (Knut K3): "Load .ti1" → "build it into this project" must follow the
    Profile-run bar too. It used the project's CURRENT run instead, so the chart
    quietly appeared in a different run than the bar showed."""
    import ui.tabs.tab_chart as tc
    tab, fm, ctl = _tab_with_three_runs(tmp_path)
    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_PROFILING)
    assert Project.load(tmp_path / "P").current_run().id == "run3"
    src = tmp_path / "patchset.ti1"; src.write_text("CTI1\n")
    monkeypatch.setattr(tc, "open_file_dialog", lambda *a, **k: str(src))
    monkeypatch.setattr(tab, "_ti1_load_destination", lambda _src: "into")
    captured = {}
    monkeypatch.setattr(
        tab._creator, "load_ti1_and_generate_preview",
        lambda *a, **k: captured.__setitem__(
            "run", Project.load(tmp_path / "P").current_run().id))

    tab._on_load_ti1()

    assert captured.get("run") == "run1"      # the bar's run, not the last one


def test_verification_build_protects_the_runs_profiling_work(qapp, tmp_path, monkeypatch):
    """#130 (Knut K3): building a VERIFICATION chart lays it down at the run root
    first, so the run's profiling chart, measurement and printer profile must be
    snapshotted — otherwise they were gone the moment the user switched Run type
    back to Profiling."""
    import ui.tabs.tab_chart as tc
    from core.measurement_target import RUN_TYPE_VERIFICATION
    tab, fm, ctl = _tab_with_three_runs(tmp_path)
    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_VERIFICATION)
    run = Project.load(tmp_path / "P").run("run1")
    Project.load(tmp_path / "P").set_current_run("run1")
    run.chart_ti2.write_text("PROFILING-CHART")
    run.chart_ti1.write_text("PROFILING-TI1")
    run.measurement_ti3.write_text("MEASUREMENT")
    run.profile_icc.write_bytes(b"ICC-PROFILE")
    src = tmp_path / "patchset.ti1"; src.write_text("CTI1\n")
    monkeypatch.setattr(tc, "open_file_dialog", lambda *a, **k: str(src))
    monkeypatch.setattr(tab, "_ti1_load_destination", lambda _src: "into")
    # Stand in for the real build: it wipes the run root exactly like
    # load_ti1_and_generate_preview does before printtarg runs.
    monkeypatch.setattr(
        tab._creator, "load_ti1_and_generate_preview",
        lambda *a, **k: Project.load(tmp_path / "P").run("run1").reset_chart_artefacts())

    tab._on_load_ti1()
    tab._restore_profiling_chart()            # what _on_generate_finished calls

    r = Project.load(tmp_path / "P").run("run1")
    assert r.chart_ti2.read_text() == "PROFILING-CHART"
    assert r.chart_ti1.read_text() == "PROFILING-TI1"
    assert r.measurement_ti3.read_text() == "MEASUREMENT"
    assert r.profile_icc.read_bytes() == b"ICC-PROFILE"


def test_patch_set_into_used_run_offers_new_vs_replace(qapp, tmp_path, monkeypatch):
    """#130 §3 (F4): building a patch set into a run that already holds work is a
    Replace — it must be offered as such, not done silently."""
    import ui.ti2_loader as L
    tab, fm, ctl = _tab_with_three_runs(tmp_path)
    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_PROFILING)
    run = Project.load(tmp_path / "P").run("run1")
    run.chart_ti2.write_text("EXISTING")
    offered: list[list[str]] = []
    monkeypatch.setattr(L, "_choice_dialog",
                        lambda p, t, i, choices: (offered.append(
                            [k for _l, _d, k in choices]), None)[1])

    assert tab._ti1_load_destination(tmp_path / "x.ti1") is None      # Cancel
    # "into_chart" joined the list with Knut's ruling of 2026-07-27 — swap the
    # chart, leave the run's measurement and profile standing.
    assert offered == [["into_replace", "into_new", "into_chart", "new"]]


def test_patch_set_into_any_existing_run_offers_new_vs_replace(qapp, tmp_path, monkeypatch):
    """#130, Knut's ruling of 2026-07-25 — "always ask on an Overwrite run": even
    an EMPTY existing run gets the New-vs-Replace question, because the user
    chose that run deliberately and a build changes what is in it."""
    import ui.ti2_loader as L
    tab, fm, ctl = _tab_with_three_runs(tmp_path)
    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_PROFILING)
    offered: list[list[str]] = []
    monkeypatch.setattr(L, "_choice_dialog",
                        lambda p, t, i, choices: (offered.append(
                            [k for _l, _d, k in choices]), "into_replace")[1])

    assert tab._ti1_load_destination(tmp_path / "x.ti1") == "into_replace"
    # "into_chart" joined the list with Knut's ruling of 2026-07-27 — swap the
    # chart, leave the run's measurement and profile standing.
    assert offered == [["into_replace", "into_new", "into_chart", "new"]]


def test_patch_set_into_new_run_asks_nothing_extra(qapp, tmp_path, monkeypatch):
    """"New run" has nothing to displace, so it keeps the plain two-way choice."""
    import ui.ti2_loader as L
    tab, fm, ctl = _tab_with_three_runs(tmp_path)
    ctl.set_profile_run(""); ctl.set_run_type(RUN_TYPE_PROFILING)   # New run
    offered: list[list[str]] = []
    monkeypatch.setattr(L, "_choice_dialog",
                        lambda p, t, i, choices: (offered.append(
                            [k for _l, _d, k in choices]), "into")[1])

    assert tab._ti1_load_destination(tmp_path / "x.ti1") == "into"
    assert offered == [["into", "new"]]


def test_patch_set_replace_archives_what_it_displaces(qapp, tmp_path, monkeypatch):
    """#130 §5a: the Replace archives the run's chart, measurement, profile,
    reports AND verifications to old/ — never deletes them."""
    import ui.tabs.tab_chart as tc
    tab, fm, ctl = _tab_with_three_runs(tmp_path)
    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_PROFILING)
    proj = Project.load(tmp_path / "P"); proj.set_current_run("run1")
    run = proj.run("run1")
    run.chart_ti2.write_text("OLD-CHART")
    run.measurement_ti3.write_text("OLD-MEASUREMENT")
    run.profile_icc.write_bytes(b"OLD-ICC")
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    run.verify_chart_ti2.write_text("OLD-VERIFY")
    src = tmp_path / "patchset.ti1"; src.write_text("CTI1\n")
    monkeypatch.setattr(tc, "open_file_dialog", lambda *a, **k: str(src))
    monkeypatch.setattr(tab, "_ti1_load_destination", lambda _s: "into_replace")
    monkeypatch.setattr(tab._creator, "load_ti1_and_generate_preview",
                        lambda *a, **k: None)

    tab._on_load_ti1()

    r = Project.load(tmp_path / "P").run("run1")
    archived = sorted(p.name for p in r.old_dir.rglob("*") if p.is_file())
    assert "P.ti3" in archived and "P.icc" in archived and "P.ti2" in archived
    assert not r.measurement_ti3.exists()      # moved, not left behind
    assert not r.profile_icc.exists()


def test_patch_set_new_run_leaves_the_selected_run_alone(qapp, tmp_path, monkeypatch):
    """"Build it as a new run instead" must not touch the run the bar showed."""
    import ui.tabs.tab_chart as tc
    tab, fm, ctl = _tab_with_three_runs(tmp_path)
    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_PROFILING)
    proj = Project.load(tmp_path / "P"); proj.set_current_run("run1")
    proj.run("run1").chart_ti2.write_text("KEEP-ME")
    src = tmp_path / "patchset.ti1"; src.write_text("CTI1\n")
    monkeypatch.setattr(tc, "open_file_dialog", lambda *a, **k: str(src))
    monkeypatch.setattr(tab, "_ti1_load_destination", lambda _s: "into_new")
    captured = {}
    monkeypatch.setattr(tab._creator, "load_ti1_and_generate_preview",
                        lambda *a, **k: captured.__setitem__(
                            "run", Project.load(tmp_path / "P").current_run().id))

    tab._on_load_ti1()

    assert captured.get("run") == "run4"       # a fresh run, not run1
    assert ctl.target.profile_run == "run4"    # the bar followed along
    assert Project.load(tmp_path / "P").run("run1").chart_ti2.read_text() == "KEEP-ME"


def test_failed_verification_build_gives_the_profiling_chart_back(qapp, tmp_path):
    """A verification build that produces nothing (cancelled or failed) must not
    cost the run its profiling chart — the run root was already cleared."""
    from core.measurement_target import RUN_TYPE_VERIFICATION
    tab, fm, ctl = _tab_with_three_runs(tmp_path)
    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_VERIFICATION)
    proj = fm.project(); proj.set_current_run("run1")   # the tab's own instance
    run = proj.run("run1")
    run.chart_ti2.write_text("PROFILING-CHART")
    run.profile_icc.write_bytes(b"ICC")

    tab._arm_verification_snapshot()
    run.reset_chart_artefacts()               # what the build does first
    assert not run.chart_ti2.exists()
    tab._on_generate_finished([])              # generation produced nothing

    r = Project.load(tmp_path / "P").run("run1")
    assert r.chart_ti2.read_text() == "PROFILING-CHART"
    assert r.profile_icc.read_bytes() == b"ICC"


def test_profiling_build_takes_no_snapshot(qapp, tmp_path):
    """The guard is verification-only — a normal profiling build must not arm it."""
    tab, fm, ctl = _tab_with_three_runs(tmp_path)
    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_PROFILING)

    tab._arm_verification_snapshot()

    assert tab._verify_profiling_backup is None


def test_ti1_preset_aligns_to_bar_run(qapp, tmp_path, monkeypatch):
    """_generate_from_ti1 (TC9.18 / Spyderprint) must align the current run to the
    bar before generating — checked by capturing the run at generation time."""
    tab, fm, ctl = _tab_with_three_runs(tmp_path)
    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_PROFILING)
    captured = {}
    monkeypatch.setattr(
        tab._creator, "load_ti1_and_generate_preview",
        lambda *a, **k: captured.__setitem__(
            "run", Project.load(tmp_path / "P").current_run().id))
    ti1 = tmp_path / "P" / "runs" / "run1" / "seed.ti1"; ti1.write_text("CTI1\n")

    tab._generate_from_ti1(ti1)

    assert captured.get("run") == "run1"     # aligned to the bar, not run3
