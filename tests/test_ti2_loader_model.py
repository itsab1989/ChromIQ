"""#130 unified load model — the bar-aware `.ti2` load dialogs route an external
chart into the right place per Profile-run / Run-type. The pop-ups are stubbed
(offscreen widget-drive of the modal choice isn't practical); the file outcomes
and bar side-effects are asserted."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication                       # noqa: E402

import ui.ti2_loader as L                                      # noqa: E402
from core.file_manager import Project                          # noqa: E402
from core.measurement_target import (RUN_TYPE_PROFILING,       # noqa: E402
                                     RUN_TYPE_VERIFICATION, MeasurementTarget)
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _FM:
    def __init__(self, root: Path):
        self._root = root
        self._target_name = root.name

    def working_dir(self) -> Path:
        return self._root

    def project(self) -> Project:
        return Project.load(self._root)

    def set_target_name(self, name):        # used by A2b "open" / whole-copy
        self._target_name = name

    def open_project_at(self, root):        # used by A2b "open"
        self._root = Path(root)
        self._target_name = Path(root).name


def _settings(tmp_path):
    class _S:
        def get(self, k, d=None):
            return str(tmp_path / "work") if k == "custom_output_path" else d
    return _S()


def _loose(folder: Path, stem="ext", ti3=False, icc=False):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{stem}.ti1").write_text("ti1")
    ti2 = folder / f"{stem}.ti2"; ti2.write_text("ti2")
    (folder / f"{stem}_01.tif").write_text("t")
    if ti3:
        (folder / f"{stem}.ti3").write_text("m")
    if icc:
        (folder / f"{stem}.icc").write_text("i")
    return ti2


def _ctl_for(project_root):
    return MeasurementTargetController(_FM(project_root))


def test_loose_new_run_profiling(qapp, tmp_path, monkeypatch):
    work = tmp_path / "work"; work.mkdir(parents=True)
    proj = Project.create(work / "P", "P"); proj.current_run().ensure_dir()
    ctl = _ctl_for(proj.root)
    ctl.set_run_type(RUN_TYPE_PROFILING); ctl.set_profile_run("")     # New run
    ti2 = _loose(tmp_path / "ext", ti3=True, icc=True)
    monkeypatch.setattr(L, "_choice_dialog", lambda *a, **k: "import")
    out, tiffs = L.resolve_ti2(None, ti2, _settings(tmp_path), ctl)
    r = Project.load(proj.root).run("run2")
    assert out == r.chart_ti2 and r.measurement_ti3.exists() and r.profile_icc.exists()
    assert ctl.target.profile_run == "run2"          # bar points at the new run


def test_loose_new_run_verification_chart_only(qapp, tmp_path, monkeypatch):
    work = tmp_path / "work"; work.mkdir(parents=True)
    proj = Project.create(work / "P", "P"); proj.current_run().ensure_dir()
    ctl = _ctl_for(proj.root)
    ctl.set_run_type(RUN_TYPE_VERIFICATION); ctl.set_profile_run("")
    ti2 = _loose(tmp_path / "ext", ti3=True, icc=True)
    monkeypatch.setattr(L, "_choice_dialog", lambda *a, **k: "import")
    out, _ = L.resolve_ti2(None, ti2, _settings(tmp_path), ctl)
    r = Project.load(proj.root).run("run2")
    assert out == r.verify_chart_ti2 and r.verify_chart_ti2.exists()
    assert not r.profile_icc.exists()                # icc/ti3 ignored


def test_loose_overwrite_replace_archives(qapp, tmp_path, monkeypatch):
    work = tmp_path / "work"; work.mkdir(parents=True)
    proj = Project.create(work / "P", "P"); run = proj.current_run(); run.ensure_dir()
    run.chart_ti2.write_text("old"); run.measurement_ti3.write_text("m")
    run.profile_icc.write_text("icc")
    ctl = _ctl_for(proj.root)
    ctl.set_run_type(RUN_TYPE_PROFILING); ctl.set_profile_run("run1")
    ti2 = _loose(tmp_path / "ext", ti3=True, icc=True)
    monkeypatch.setattr(L, "_choice_dialog", lambda *a, **k: "replace")
    out, _ = L.resolve_ti2(None, ti2, _settings(tmp_path), ctl)
    r = Project.load(proj.root).run("run1")
    assert r.old_dir.exists() and out == r.chart_ti2 and r.chart_ti2.read_text() == "ti2"


def test_loose_overwrite_new_run_instead(qapp, tmp_path, monkeypatch):
    work = tmp_path / "work"; work.mkdir(parents=True)
    proj = Project.create(work / "P", "P"); run = proj.current_run(); run.ensure_dir()
    run.chart_ti2.write_text("old")
    ctl = _ctl_for(proj.root)
    ctl.set_run_type(RUN_TYPE_PROFILING); ctl.set_profile_run("run1")
    ti2 = _loose(tmp_path / "ext")
    monkeypatch.setattr(L, "_choice_dialog", lambda *a, **k: "new")
    out, _ = L.resolve_ti2(None, ti2, _settings(tmp_path), ctl)
    assert out == Project.load(proj.root).run("run2").chart_ti2   # new run, run1 untouched
    assert (work / "P" / "runs" / "run1" / "P.ti2").read_text() == "old"


def test_inside_current_continue_sets_bar(qapp, tmp_path, monkeypatch):
    work = tmp_path / "work"; work.mkdir(parents=True)
    proj = Project.create(work / "P", "P"); run = proj.current_run(); run.ensure_dir()
    run.chart_ti2.write_text("c"); (run.dir / "P_01.tif").write_text("t")
    ctl = _ctl_for(proj.root)
    monkeypatch.setattr(L, "_choice_dialog", lambda *a, **k: "continue")
    out, _ = L.resolve_ti2(None, run.chart_ti2, _settings(tmp_path), ctl)
    assert out == run.chart_ti2                       # used in place, no copy
    assert ctl.target.profile_run == "run1" and not ctl.target.is_verification()


def test_cancel_returns_none(qapp, tmp_path, monkeypatch):
    work = tmp_path / "work"; work.mkdir(parents=True)
    proj = Project.create(work / "P", "P"); proj.current_run().ensure_dir()
    ctl = _ctl_for(proj.root); ctl.set_profile_run("")
    ti2 = _loose(tmp_path / "ext")
    monkeypatch.setattr(L, "_choice_dialog", lambda *a, **k: None)    # Cancel
    assert L.resolve_ti2(None, ti2, _settings(tmp_path), ctl) is None


def test_full_project_copy_whole(qapp, tmp_path, monkeypatch):
    work = tmp_path / "work"; work.mkdir(parents=True)
    proj = Project.create(work / "P", "P"); proj.current_run().ensure_dir()
    ctl = _ctl_for(proj.root)
    # an external complete project Q
    q = Project.create(tmp_path / "ext" / "Q", "Q"); qr = q.current_run(); qr.ensure_dir()
    qr.chart_ti2.write_text("qc"); (qr.dir / "Q_01.tif").write_text("t")
    monkeypatch.setattr(L, "_choice_dialog", lambda *a, **k: "whole")
    monkeypatch.setattr(L, "_ask_project_name", lambda *a, **k: ("Q", False))
    out, _ = L.resolve_ti2(None, qr.chart_ti2, _settings(tmp_path), ctl)
    assert (work / "Q" / "project.json").is_file()
    assert out == Project.load(work / "Q").current_run().chart_ti2


# ---------------------------------------------------------------------------
# Gap rows added for the exhaustive #130 conformance run (Knut, 2026-07-24).
# Each encodes a model-v3 expectation; a failure here is a conformance finding.
# ---------------------------------------------------------------------------

def _seed_verify(run, *, date="2026-01-01_120000"):
    """Give a run a shared verify chart + one dated verification folder. The id
    MUST match _VERIFY_ID_RE (yyyy-mm-dd_HHMMSS) or Run.verifications() ignores
    it — which is what real dated folders look like."""
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    run.verify_chart_ti1.write_text("v1")
    run.verify_chart_ti2.write_text("vc")
    (run.verifications_dir / f"{run.verify_stem}_01.tif").write_text("t")
    vdated = run.verifications_dir / date
    vdated.mkdir(parents=True, exist_ok=True)
    (vdated / "measured.ti3").write_text("meas")
    return vdated


def test_A03plus_profiling_replace_also_archives_verifications(qapp, tmp_path, monkeypatch):
    """Model v3 §5a: a Profiling Replace moves the run's verifications/ tree to
    old/ too — not just the run-root chart/ti3/icc."""
    work = tmp_path / "work"; work.mkdir(parents=True)
    proj = Project.create(work / "P", "P"); run = proj.current_run(); run.ensure_dir()
    run.chart_ti2.write_text("old"); run.profile_icc.write_text("icc")
    vdated = _seed_verify(run)
    ctl = _ctl_for(proj.root)
    ctl.set_run_type(RUN_TYPE_PROFILING); ctl.set_profile_run("run1")
    ti2 = _loose(tmp_path / "ext", ti3=True, icc=True)
    monkeypatch.setattr(L, "_choice_dialog", lambda *a, **k: "replace")
    L.resolve_ti2(None, ti2, _settings(tmp_path), ctl)
    r = Project.load(proj.root).run("run1")
    assert r.old_dir.exists()
    assert not vdated.exists(), "the dated verification should have moved to old/"
    assert not r.verifications_dir.exists() or not list(r.verifications_dir.glob("*")), \
        "verifications/ tree should be archived on a Profiling Replace (§5a)"


def test_A04_verification_replace_archives_and_keeps_profile(qapp, tmp_path, monkeypatch):
    """Model v3 §5b / A-04, as ruled 2026-07-25: a Verification Replace acts
    ONLY on the files at the root of verifications/, archives them into
    verifications/old/ (not the run's own old/), installs the loaded chart, and
    leaves both the profile and the dated verification folders alone."""
    work = tmp_path / "work"; work.mkdir(parents=True)
    proj = Project.create(work / "P", "P"); run = proj.current_run(); run.ensure_dir()
    run.profile_icc.write_text("keepme")
    vdated = _seed_verify(run)
    ctl = _ctl_for(proj.root)
    ctl.set_run_type(RUN_TYPE_VERIFICATION); ctl.set_profile_run("run1")
    ti2 = _loose(tmp_path / "ext", ti3=True, icc=True)
    monkeypatch.setattr(L, "_choice_dialog", lambda *a, **k: "replace")
    out, _ = L.resolve_ti2(None, ti2, _settings(tmp_path), ctl)
    r = Project.load(proj.root).run("run1")
    assert r.verifications_old_dir.exists(), "archive belongs in verifications/old/"
    assert not r.old_dir.exists(), "a verification Replace must not touch the run root"
    assert vdated.exists(), "dated verification results are kept, not archived"
    assert out == r.verify_chart_ti2 and r.verify_chart_ti2.read_text() == "ti2"
    assert r.profile_icc.read_text() == "keepme", "profile must be untouched"


def test_A07_full_project_import_just_this_chart(qapp, tmp_path, monkeypatch):
    """A-07: from a full external project, 'Import just this chart' copies only
    the chart per the bar (New run · Profiling), not the whole project."""
    work = tmp_path / "work"; work.mkdir(parents=True)
    proj = Project.create(work / "P", "P"); proj.current_run().ensure_dir()
    ctl = _ctl_for(proj.root)
    ctl.set_run_type(RUN_TYPE_PROFILING); ctl.set_profile_run("")
    q = Project.create(tmp_path / "ext" / "Q", "Q"); qr = q.current_run(); qr.ensure_dir()
    qr.chart_ti2.write_text("qc"); (qr.dir / "Q.ti1").write_text("q1")
    (qr.dir / "Q_01.tif").write_text("t")
    # first dialog → "chart"; the inner loose dialog → "import"
    keys = iter(["chart", "import"])
    monkeypatch.setattr(L, "_choice_dialog", lambda *a, **k: next(keys))
    out, _ = L.resolve_ti2(None, qr.chart_ti2, _settings(tmp_path), ctl)
    assert not (work / "Q").exists(), "must NOT copy the whole project"
    assert out == Project.load(proj.root).run("run2").chart_ti2


def test_A09_verify_chart_continue_sets_bar(qapp, tmp_path, monkeypatch):
    """A-09: loading the run's own verify chart → Continue → no copy; bar set to
    Overwrite run1 · Verification."""
    work = tmp_path / "work"; work.mkdir(parents=True)
    proj = Project.create(work / "P", "P"); run = proj.current_run(); run.ensure_dir()
    _seed_verify(run)
    ctl = _ctl_for(proj.root)
    monkeypatch.setattr(L, "_choice_dialog", lambda *a, **k: "continue")
    out, _ = L.resolve_ti2(None, run.verify_chart_ti2, _settings(tmp_path), ctl)
    assert out == run.verify_chart_ti2                      # used in place
    assert ctl.target.profile_run == "run1" and ctl.target.is_verification()


def test_A10_use_as_base_for_new_profile(qapp, tmp_path, monkeypatch):
    """A-10: the loaded project's own chart → Use as base → copied to a new named
    project; the original P is untouched."""
    work = tmp_path / "work"; work.mkdir(parents=True)
    proj = Project.create(work / "P", "P"); run = proj.current_run(); run.ensure_dir()
    run.chart_ti1.write_text("c1"); run.chart_ti2.write_text("c2")
    (run.dir / "P_01.tif").write_text("t")
    ctl = _ctl_for(proj.root)
    monkeypatch.setattr(L, "_choice_dialog", lambda *a, **k: "new")
    monkeypatch.setattr(L, "_ask_profile_name", lambda *a, **k: ("Fresh", False))
    out, _ = L.resolve_ti2(None, run.chart_ti2, _settings(tmp_path), ctl)
    assert (work / "Fresh").exists() and out is not None
    assert (work / "P" / "runs" / "run1" / "P.ti2").read_text() == "c2"  # P untouched


def test_A11_open_other_project(qapp, tmp_path, monkeypatch):
    """A-11: loading a chart that lives in a DIFFERENT project → Open switches the
    working project to it; nothing copied."""
    work = tmp_path / "work"; work.mkdir(parents=True)
    proj = Project.create(work / "P", "P"); proj.current_run().ensure_dir()
    other = Project.create(work / "R", "R"); orun = other.current_run(); orun.ensure_dir()
    orun.chart_ti2.write_text("rc"); (orun.dir / "R_01.tif").write_text("t")
    ctl = _ctl_for(proj.root)
    monkeypatch.setattr(L, "_choice_dialog", lambda *a, **k: "open")
    out, _ = L.resolve_ti2(None, orun.chart_ti2, _settings(tmp_path), ctl)
    assert out == orun.chart_ti2                            # used in place
    assert ctl.project_or_none().root == other.root         # switched to R
    assert ctl.target.profile_run == "run1" and not ctl.target.is_verification()


def test_A12_flat_chart_offers_no_continue(qapp, tmp_path, monkeypatch):
    """A-12: an old/flat chart (no project.json) offers NO 'Continue' — it is
    copied per the bar like a loose external chart."""
    work = tmp_path / "work"; work.mkdir(parents=True)
    proj = Project.create(work / "P", "P"); proj.current_run().ensure_dir()
    ctl = _ctl_for(proj.root)
    ctl.set_run_type(RUN_TYPE_PROFILING); ctl.set_profile_run("")
    # a flat chart folder INSIDE the working folder, but not a project
    ti2 = _loose(work / "flatchart")
    seen_keys = []
    def _rec(parent, title, intro, choices):
        seen_keys.extend(k for _l, _d, k in choices)
        return "import"
    monkeypatch.setattr(L, "_choice_dialog", _rec)
    out, _ = L.resolve_ti2(None, ti2, _settings(tmp_path), ctl)
    assert "continue" not in seen_keys, "flat/loose chart must not offer Continue"
    assert out == Project.load(proj.root).run("run2").chart_ti2
