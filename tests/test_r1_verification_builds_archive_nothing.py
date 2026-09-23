"""Re-challenge R1 of beta 39, #3: a VERIFICATION build never archives the
run's profiling results.

Measured on screen (``~/Desktop/ChromIQ-beta39-proof/rechallenge-R1-
behaviour/fpg/preset-verif``): Run type Verification, Manual, the built-in
prebuilt preset "ColorMunki TC3.00". The run's profiling files came out
identical, but every build copied the run's ``.icc`` and ``.ti3`` into
``runs/run1/old/<stamp>/``: `TabChart._apply_prebuilt_preset` (and the
layout editor's applied chart, `_import_applied_chart`) called
`Run.reset_chart_artefacts()` without ``keep_results``, while every other
route passes ``keep_results=self._is_verification_target()``.

Every test names its mutation; each was run red (REPORT.md in
``~/Desktop/ChromIQ-beta39-proof/rechallenge-R1-fixes/``).
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.file_manager import Project                           # noqa: E402
from core.measurement_target import (RUN_TYPE_PROFILING,          # noqa: E402
                                     RUN_TYPE_VERIFICATION)
from tests.test_preset_honors_bar_run import (                   # noqa: E402
    _no_dialogs, _tab_with_three_runs, qapp)

assert _no_dialogs and qapp

_TREE = Path(__file__).resolve().parent.parent


def _with_results(tmp_path):
    p = Project.load(tmp_path / "P")
    p.set_current_run("run1")
    run = p.run("run1")
    run.chart_ti2.write_text("PROFILING-CHART", encoding="utf-8")
    run.measurement_ti3.write_text("MEASUREMENT", encoding="utf-8")
    run.profile_icc.write_bytes(b"ICC-PROFILE")
    return run


def _old_folders(tmp_path) -> "list[Path]":
    return sorted((tmp_path / "P" / "runs").glob("run*/old"))


def test_a_prebuilt_preset_under_verification_archives_nothing(
        qapp, tmp_path):
    """The tester's case: TC3.00 built under Verification into run 1, which
    has a measurement and a profile. No ``runs/run1/old/`` appears, and the
    measurement and profile keep their bytes.

    MUTATION, proven red: in `_apply_prebuilt_preset` call
    ``run.reset_chart_artefacts()`` again (``runs/run1/old/<stamp>/`` holds
    copies of the .ti3 and .icc)."""
    tab, fm, ctl = _tab_with_three_runs(tmp_path)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    run = _with_results(tmp_path)
    assert tab._apply_prebuilt_preset("__chromiq_tc300_builtin__", "P")
    assert _old_folders(tmp_path) == []
    assert run.measurement_ti3.read_text(encoding="utf-8") == "MEASUREMENT"
    assert run.profile_icc.read_bytes() == b"ICC-PROFILE"


def test_an_applied_editor_chart_under_verification_archives_nothing(
        qapp, tmp_path, monkeypatch):
    """The layout editor's hand-off (a .ti1 and its pages copied in) under
    Verification: no ``runs/run1/old/``.

    MUTATION, proven red: in `_import_applied_chart` call
    ``run.reset_chart_artefacts()`` without ``keep_results``."""
    from PIL import Image
    tab, fm, ctl = _tab_with_three_runs(tmp_path)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    run = _with_results(tmp_path)
    staged = tmp_path / "staged"
    staged.mkdir()
    (staged / "Layout.ti1").write_text("CTI1\n", encoding="utf-8")
    Image.new("RGB", (8, 8), "white").save(staged / "Layout_01.tif")
    tab._applied_src_dir, tab._applied_stem = staged, "Layout"
    monkeypatch.setattr(tab, "_gate_route_and_replace",
                        lambda *a, **k: (True, True))
    tab._import_applied_chart()
    assert (run.dir / f"{run.stem}.ti1").is_file() or any(
        run.verifications_dir.rglob("*.ti1")), "the chart was not built"
    assert _old_folders(tmp_path) == []
    assert run.measurement_ti3.read_text(encoding="utf-8") == "MEASUREMENT"
    assert run.profile_icc.read_bytes() == b"ICC-PROFILE"


def test_a_prebuilt_preset_under_profiling_still_archives(qapp, tmp_path,
                                                          monkeypatch):
    """The other side, so the fix cannot pass by never archiving: the same
    build under Profiling, agreed to, archives the measurement it displaces
    (Knut, #130: a chart re-generation never deletes a measurement).

    MUTATION, proven red: pass ``keep_results=True`` unconditionally in
    `_apply_prebuilt_preset`."""
    tab, fm, ctl = _tab_with_three_runs(tmp_path)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_PROFILING)
    _with_results(tmp_path)
    monkeypatch.setattr(tab, "_confirm_displacing_results", lambda: True)
    monkeypatch.setattr(tab, "_gate_route_and_replace",
                        lambda *a, **k: (True, True))
    assert tab._apply_prebuilt_preset("__chromiq_tc300_builtin__", "P")
    olds = _old_folders(tmp_path)
    assert olds, "a profiling rebuild left the measurement unarchived"
    assert any(p.suffix == ".ti3" for p in olds[0].rglob("*"))


def test_every_chart_reset_in_the_create_chart_tab_names_keep_results():
    """The audit, kept: every `reset_chart_artefacts` call and every build of
    `ChartCreator` in ``ui/tabs/tab_chart.py`` says what happens to the
    run's results, so a new route cannot fall back to the default (archive)
    under Verification unnoticed.

    MUTATION, proven red: drop the ``keep_results=`` argument from either
    call fixed here."""
    src = (_TREE / "ui" / "tabs" / "tab_chart.py").read_text(encoding="utf-8")
    missing = []
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
        if name not in ("reset_chart_artefacts",
                        "load_ti1_and_generate_preview"):
            continue
        if not any(k.arg == "keep_results" for k in node.keywords):
            missing.append((name, node.lineno))
    assert not missing, missing


# --------------------------------------------------------------------------
# #5: the profiling snapshot's temporary folder goes on every ending
# --------------------------------------------------------------------------
def _armed(tmp_path):
    tab, fm, ctl = _tab_with_three_runs(tmp_path)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    proj = fm.project()
    proj.set_current_run("run1")
    run = proj.run("run1")
    run.chart_ti2.write_text("PROFILING-CHART", encoding="utf-8")
    run.measurement_ti3.write_text("MEASUREMENT", encoding="utf-8")
    run.profile_icc.write_bytes(b"ICC-PROFILE")
    tab._arm_verification_snapshot()
    bak = tab._verify_profiling_backup
    assert bak and Path(bak).is_dir()
    return tab, run, Path(bak)


def test_a_stopped_verification_build_leaves_no_temporary_copy(qapp,
                                                               tmp_path):
    """Stop pressed (the tester: FROM PROFILE GAMUT, 1500 colours, Stop at
    2.5 s): the run keeps its files and ``chromiq_prof_chart_*`` is gone.

    MUTATION, proven red: drop the `_restore_profiling_chart` call in the
    cancel branch of `_on_generate_finished` (the folder is still there)."""
    tab, run, bak = _armed(tmp_path)
    tab._cancelled_by_user = True
    tab._on_generate_finished([])
    assert not bak.exists(), "the snapshot's copy was left in the temp folder"
    assert run.chart_ti2.read_text(encoding="utf-8") == "PROFILING-CHART"
    assert run.profile_icc.read_bytes() == b"ICC-PROFILE"


def test_a_failed_verification_build_leaves_no_temporary_copy(qapp, tmp_path):
    """A build that produced nothing without a Stop, and one that raised
    before it started: the copy goes in both.

    MUTATION, proven red: drop the `_restore_profiling_chart` call in
    `_the_chart_build_could_not_start_quietly` (the second copy stays)."""
    tab, run, bak = _armed(tmp_path)
    tab._on_generate_finished([])
    assert not bak.exists()
    tab._arm_verification_snapshot()
    bak2 = Path(tab._verify_profiling_backup)
    assert bak2.is_dir()
    tab._the_chart_build_could_not_start_quietly()
    assert not bak2.exists()
    assert run.measurement_ti3.read_text(encoding="utf-8") == "MEASUREMENT"


def test_arming_twice_for_one_build_keeps_one_copy(qapp, tmp_path):
    """A build through two doors arms twice: one snapshot, not two, and the
    one kept is the first (the state before the build). Switching to
    Profiling then drops it.

    MUTATION, proven red: put back the old first line of
    `_arm_verification_snapshot`, ``self._verify_profiling_backup = None``
    with no early return (the first copy is orphaned in the temp folder)."""
    tab, run, bak = _armed(tmp_path)
    tab._arm_verification_snapshot()
    assert Path(tab._verify_profiling_backup) == bak
    assert bak.is_dir()
    tab._target_ctl.set_run_type(RUN_TYPE_PROFILING)
    tab._arm_verification_snapshot()
    assert tab._verify_profiling_backup is None
    assert not bak.exists()
