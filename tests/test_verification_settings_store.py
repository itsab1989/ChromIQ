"""F1 (Knut's ruling, 2026-08-11): a verification has its OWN settings store.

    "I think the verification chart shall have its own settings, separate from
    the profile run's settings, and when a verification chart is stored in the
    verifications/<date_time>/chart/ folder when a measurement starts, the
    settings are also backed up with the chart, thus can be restored."

Found by the on-screen switching drive: Profiling and Verification on the same
run shared ``runs/runN/meta.json`` and overwrote each other's settings.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class _Target:
    def __init__(self, *, verification=False, calibration=False):
        self._v, self._c = verification, calibration

    def is_calibration(self):   return self._c
    def is_new_run(self):       return False
    def is_verification(self):  return self._v
    profile_run = "run1"


class _Ctl:
    def __init__(self, project, target):
        self._p, self.target = project, target

    def project_or_none(self):  return self._p


def _project(tmp_path: Path):
    from core.file_manager import Project
    return Project.create(tmp_path, "Proj")


def test_profiling_and_verification_resolve_to_different_stores(tmp_path):
    from workflow.per_target_settings import store_for_target
    proj = _project(tmp_path)
    prof = store_for_target(_Ctl(proj, _Target()))
    ver = store_for_target(_Ctl(proj, _Target(verification=True)))
    assert Path(prof.dir) == proj.run("run1").dir
    assert Path(ver.dir) == proj.run("run1").verifications_dir
    assert Path(prof.dir) != Path(ver.dir), \
        "one shared store is exactly the F1 fault"


def test_the_two_stores_hold_their_own_values(tmp_path):
    from workflow.per_target_settings import store_for_target
    proj = _project(tmp_path)
    prof = store_for_target(_Ctl(proj, _Target()))
    ver = store_for_target(_Ctl(proj, _Target(verification=True)))
    mp = prof.load_meta()
    mp.measure_settings = {"patch_by_patch": {"enabled": True, "value": True}}
    prof.save_meta(mp)
    mv = ver.load_meta()
    mv.measure_settings = {"patch_by_patch": {"enabled": True, "value": False}}
    ver.save_meta(mv)
    assert prof.load_meta().measure_settings["patch_by_patch"]["value"] is True
    assert ver.load_meta().measure_settings["patch_by_patch"]["value"] is False


def test_a_deleted_run_is_never_recreated_by_the_verification_store(tmp_path):
    """The one folder the resolver may create is verifications/ INSIDE a run
    that exists; a deleted run must stay deleted."""
    import shutil

    from workflow.per_target_settings import store_for_target
    proj = _project(tmp_path)
    run_dir = proj.run("run1").dir
    shutil.rmtree(run_dir)
    store = store_for_target(_Ctl(proj, _Target(verification=True)))
    assert not run_dir.exists(), "asking for the store recreated a deleted run"
    if store is not None:
        assert not Path(store.dir).exists()


def test_verification_replace_archives_the_chart_but_keeps_the_settings(tmp_path):
    """Regenerating the verification chart must not wipe the verification's
    settings — the same way a profiling replace leaves runs/runN/meta.json."""
    from workflow.chart_import import archive_run_for_replace
    proj = _project(tmp_path)
    run = proj.run("run1")
    vdir = run.verifications_dir
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / f"{run.verify_stem}.ti2").write_text("ti2")
    (vdir / "meta.json").write_text('{"measure_settings": {}}')
    arch = archive_run_for_replace(run, verification=True)
    assert arch is not None
    assert (arch / f"{run.verify_stem}.ti2").is_file()
    assert (vdir / "meta.json").is_file(), "the settings were archived away"
    assert not (arch / "meta.json").exists()


def test_snapshot_backs_the_settings_up_with_the_chart(tmp_path):
    """Knut: 'the settings are also backed up with the chart'."""
    from workflow.verify_chart_snapshot import snapshot_chart
    proj = _project(tmp_path)
    run = proj.run("run1")
    vdir = run.verifications_dir
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / f"{run.verify_stem}.ti2").write_text("ti2")
    (vdir / "meta.json").write_text('{"measure_settings": {}}')
    ver = run.new_verification()
    ver.ensure_dir()
    dest = snapshot_chart(ver)
    assert dest is not None
    assert (dest / "meta.json").is_file()
    assert (dest / f"{run.verify_stem}.ti2").is_file()


def test_restore_without_a_settings_backup_leaves_the_live_settings(tmp_path):
    """An OLD snapshot carries no meta.json. Restoring it must not delete the
    live settings file — the stash is discarded on success, and 'never
    destroy' outranks everything."""
    from workflow.verify_chart_snapshot import restore_chart, snapshot_chart
    proj = _project(tmp_path)
    run = proj.run("run1")
    vdir = run.verifications_dir
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / f"{run.verify_stem}.ti2").write_text("old-chart")
    ver = run.new_verification()
    ver.ensure_dir()
    snapshot_chart(ver)                       # snapshot WITHOUT settings
    (vdir / "meta.json").write_text('{"measure_settings": {"x": 1}}')
    (vdir / f"{run.verify_stem}.ti2").write_text("newer-chart")
    result = restore_chart(ver)
    assert result.ok, result.error
    assert (vdir / "meta.json").is_file(), \
        "the live settings were destroyed by a restore"
    assert json.loads((vdir / "meta.json").read_text()) == \
        {"measure_settings": {"x": 1}}


def test_restore_with_a_settings_backup_archives_then_replaces(tmp_path):
    """A snapshot WITH settings restores them — and the replaced live file is
    archived into old/, never deleted."""
    from workflow.verify_chart_snapshot import restore_chart, snapshot_chart
    proj = _project(tmp_path)
    run = proj.run("run1")
    vdir = run.verifications_dir
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / f"{run.verify_stem}.ti2").write_text("chart-a")
    (vdir / "meta.json").write_text('{"measure_settings": {"gen": 1}}')
    ver = run.new_verification()
    ver.ensure_dir()
    snapshot_chart(ver)                       # snapshot WITH settings
    (vdir / "meta.json").write_text('{"measure_settings": {"gen": 2}}')
    result = restore_chart(ver)
    assert result.ok, result.error
    assert json.loads((vdir / "meta.json").read_text()) == \
        {"measure_settings": {"gen": 1}}, "the backup was not restored"
    old = vdir / "old"
    archived = list(old.rglob("meta.json"))
    assert archived, "the replaced settings file was not archived"
    assert json.loads(archived[0].read_text()) == \
        {"measure_settings": {"gen": 2}}


def test_settings_edits_do_not_make_the_chart_look_different(tmp_path):
    """The change-detection that drives 'this is a different chart' must skip
    the settings file, or every settings edit would raise the warning."""
    from workflow.verify_chart_snapshot import (live_differs_from_snapshot,
                                                snapshot_chart)
    proj = _project(tmp_path)
    run = proj.run("run1")
    vdir = run.verifications_dir
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / f"{run.verify_stem}.ti2").write_text("chart")
    (vdir / "meta.json").write_text('{"measure_settings": {"gen": 1}}')
    ver = run.new_verification()
    ver.ensure_dir()
    snapshot_chart(ver)
    assert not live_differs_from_snapshot(ver)
    (vdir / "meta.json").write_text('{"measure_settings": {"gen": 2}}')
    assert not live_differs_from_snapshot(ver), \
        "a settings edit made the chart look different"


def test_every_guided_profile_field_exists_on_the_real_tab(qapp):
    """Knut's beta.3 bug-test: the Guided module's Manufacturer / Model /
    media-surface fields were outside the store because only Manual's
    widgets were mapped. A typo'd attribute in _GUIDED_PROFILE_FIELDS would
    silently re-open that hole — ask the real tab."""
    from core.argyll_runner import ArgyllRunner
    from core.settings import DEFAULTS
    from ui.tabs.tab_profile import TabProfile

    class _S:
        def __init__(self):
            self._d = dict(DEFAULTS)

        def get(self, k, d=None):   return self._d.get(k, d)
        def set(self, k, v):        self._d[k] = v

    s = _S()
    tab = TabProfile(ArgyllRunner(s), s)
    missing = [key for key, _kind, attr in tab._GUIDED_PROFILE_FIELDS
               if getattr(tab, attr, None) is None]
    assert not missing, (
        f"_GUIDED_PROFILE_FIELDS names widgets the tab does not have: "
        f"{missing}")
    collected = tab._collect_guided_profile_fields()
    absent = [key for key, _k, _a in tab._GUIDED_PROFILE_FIELDS
              if key not in collected]
    assert not absent, f"fields missing from the collect: {absent}"
