"""#182 beta 38: the fixes for the challenge round before the tag.

The findings are in ``~/Desktop/ChromIQ-beta38-proof/challenge/REPORT.md``:

* F1 (BLOCKER): a folder whose name differs from the project's only in CASE,
  then "Rename the project": `Project.rename` asked `dst.exists()`, which on a
  case-insensitive volume is the file itself, moved the built ICC aside as
  "…_conflicted_at_renaming_procedure.icc" and aborted with [Errno 2].
* F2 (HIGH): a renamed Finder duplicate's report window loaded its ORIGINAL's
  measurements and filed its own reports under "Reports including multiple
  projects".
* F3: every rename left ``*-verify.control-strip.json`` under the old name.
* F6: the rename failure message printed a bare path, and a case-only name
  twice.
* F7: "Where are my files" promised a recalculation on unlock, and a
  reports/old/ that is "copied, never moved".
* F8: two stacked red crosses drew the lower value above the higher.
* F9: the Colour accuracy legend said "ΔE" where every other graph says
  "(ΔE00)".

(F4, the PDF saved elsewhere, is in `test_k26_rulings.py`, beside the
cancelled save it extends.)

The rename tests run on the REAL file system under ``tmp_path``: macOS APFS
is case-insensitive by default, which is the volume the fault was found on.
A case-sensitive volume cannot show F1 at all, and those tests say so.

Every test names the mutation that turns it red; each was run.
"""
from __future__ import annotations

import errno
import json
import os
import shutil
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402


def _case_insensitive(where: Path) -> bool:
    probe = where / "CaseProbe"
    probe.write_text("x", encoding="utf-8")
    try:
        return (where / "caseprobe").exists()
    finally:
        probe.unlink()


def _needs_case_insensitive(tmp_path):
    if not _case_insensitive(tmp_path):
        pytest.skip("this volume is case-sensitive; F1 cannot happen on it")


def _listing(root: Path) -> list:
    """Every entry under *root*, spelled as the DISK spells it (os.listdir,
    not Path.exists, which answers True for any case on this volume)."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        for n in dirnames + filenames:
            out.append(os.path.normpath(os.path.join(rel, n)))
    return sorted(out)


def _project_with_a_built_profile(parent: Path, name: str):
    """A project with a chart, a measurement, a BUILT profile and a dated
    verification carrying a control-strip declaration."""
    from core.file_manager import Project
    proj = Project.create(parent / name, name)
    run = proj.current_run()
    run.ensure_dir()
    run.chart_ti2.write_text("CTI2", encoding="utf-8")
    run.measurement_ti3.write_text("CTI3", encoding="utf-8")
    run.profile_icc.write_bytes(b"THE-BUILT-PROFILE")
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    (run.verifications_dir / f"{name}-verify.ti2").write_text(
        "CTI2", encoding="utf-8")
    (run.verifications_dir / f"{name}-verify.control-strip.json").write_text(
        '{"name": "strip"}', encoding="utf-8")
    dated = run.verifications_dir / "2026-12-01_090000" / "chart"
    dated.mkdir(parents=True)
    (dated / f"{name}-verify.control-strip.json").write_text(
        '{"name": "strip"}', encoding="utf-8")
    return proj


class _Settings:
    def __init__(self, root: Path) -> None:
        self._root = root

    def get(self, key, default=None):
        return str(self._root) if key == "custom_output_path" else default


# ---------------------------------------------------------------------------
# F1: a case-only rename
# ---------------------------------------------------------------------------
def test_a_case_only_folder_keeps_its_built_profile(tmp_path):
    """The challenge round's R2, on disk: the folder renamed by hand to its
    project name in lower case, then "Rename the project". Every file is
    renamed to the new case, the built profile keeps its bytes, and nothing
    is moved aside.

    MUTATION, proven red: in `Project.rename` drop the `same_entry(f, dst)`
    branch (a case-only name then reads as a stranger): the profile becomes
    "demo-proj_conflicted_at_renaming_procedure.icc" and the rename raises
    [Errno 2], as on screen."""
    from core.file_manager import CONFLICT_MARKER, FileManager
    _needs_case_insensitive(tmp_path)
    _project_with_a_built_profile(tmp_path, "Demo-Proj")
    os.rename(tmp_path / "Demo-Proj", tmp_path / "demo-proj")   # Finder
    assert os.listdir(tmp_path) == ["demo-proj"]
    fm = FileManager(_Settings(tmp_path))
    fm.rename_existing_project(tmp_path / "demo-proj", "demo-proj")
    names = _listing(tmp_path / "demo-proj")
    assert not [n for n in names if CONFLICT_MARKER in n], names
    assert not [n for n in names if "Demo-Proj" in n], names
    icc = tmp_path / "demo-proj" / "runs" / "run1" / "demo-proj.icc"
    assert "runs/run1/demo-proj.icc" in names, names
    assert icc.read_bytes() == b"THE-BUILT-PROFILE"
    man = json.loads((tmp_path / "demo-proj" / "project.json").read_text(encoding="utf-8"))
    assert man["target_name"] == "demo-proj"
    assert man["former_names"] == ["Demo-Proj"]
    assert not [n for n in names if "chromiq-renaming" in n], names


def test_after_a_case_only_rename_no_date_is_listed_twice(tmp_path, qapp,
                                                          _quiet):
    """Found on screen after the F1 fix: the renamed project's report window
    listed the date it was opened on twice, because its saved report names
    "P-verify.ti3" and the file is now "p-verify.ti3", the same file on this
    volume but a different string.

    MUTATION, proven red: compare only the strings in
    `_is_this_measurement` (drop ``or same_entry(found, target)``): three
    rows for two dates."""
    from core.file_manager import FileManager
    from tests.test_report_shown_is_grouped_by_run_and_project import (
        _dated, _dialog)
    from tests.test_import_measurement_module import _verify_env
    _needs_case_insensitive(tmp_path)
    s, _fm, _ctl, run1 = _verify_env(tmp_path)
    v = [_dated(run1), _dated(run1)]
    os.rename(tmp_path / "P", tmp_path / "p")
    FileManager(_Settings(tmp_path)).rename_existing_project(tmp_path / "p",
                                                             "p")
    ti3 = (tmp_path / "p" / v[0].dir.relative_to(tmp_path / "P")
           / "p-verify.ti3")
    assert "p-verify.ti3" in os.listdir(ti3.parent)
    dlg = _dialog(s, ti3, qapp)
    try:
        dates = [str(r.get("_origin_dir")) for r in dlg._history]
        assert len(dates) == 2 and len(set(dates)) == 2, dates
    finally:
        dlg.close()


def test_the_ordinary_rename_changes_the_case_of_the_folder_too(tmp_path):
    """ChromIQ's own rename, "Demo-Proj" to "demo-proj": the folder and every
    file change case, in two steps, and nothing is moved aside. It raised
    FileExistsError, because the new name "exists" (it is the folder itself).

    MUTATION, proven red: drop ``and not case_only`` from the exists check in
    `FileManager.rename_existing_project` (FileExistsError, nothing renamed).
    """
    from core.file_manager import CONFLICT_MARKER, FileManager
    _needs_case_insensitive(tmp_path)
    _project_with_a_built_profile(tmp_path, "Demo-Proj")
    fm = FileManager(_Settings(tmp_path))
    new = fm.rename_existing_project(tmp_path / "Demo-Proj", "demo-proj")
    assert new == tmp_path / "demo-proj"
    assert os.listdir(tmp_path) == ["demo-proj"]
    names = _listing(tmp_path / "demo-proj")
    assert "runs/run1/demo-proj.icc" in names, names
    assert not [n for n in names if CONFLICT_MARKER in n or "Demo-Proj" in n]
    assert fm.get_target_name() == "demo-proj"


def test_a_rename_that_fails_part_way_is_undone(tmp_path, monkeypatch):
    """A stranger already holds the name the profile needs, so it is moved
    aside; then renaming the measurement fails. Everything goes back: the
    stranger to its own name, every file to the old name, the manifest
    untouched, so "Nothing was changed" is true.

    MUTATION, proven red: remove the undo loop (``for a, b in
    reversed(done)``) from `Project.rename`: the stranger is left as
    "…_conflicted_at_renaming_procedure.icc" and the profile as "Beta.icc"."""
    from core.file_manager import Project
    proj = _project_with_a_built_profile(tmp_path, "Alpha")
    run_dir = proj.current_run().dir
    (run_dir / "Beta.icc").write_bytes(b"A-STRANGER")
    before = _listing(tmp_path / "Alpha")
    manifest = (tmp_path / "Alpha" / "project.json").read_text(encoding="utf-8")
    real = Path.rename

    def _rename(self, target):
        if self.name == "Alpha.ti3":
            raise OSError(errno.EIO, "simulated failure")
        return real(self, target)
    monkeypatch.setattr(Path, "rename", _rename)
    with pytest.raises(OSError):
        Project.load(tmp_path / "Alpha").rename("Beta")
    monkeypatch.setattr(Path, "rename", real)
    assert _listing(tmp_path / "Alpha") == before
    assert (run_dir / "Beta.icc").read_bytes() == b"A-STRANGER"
    assert (run_dir / "Alpha.icc").read_bytes() == b"THE-BUILT-PROFILE"
    assert (tmp_path / "Alpha" / "project.json").read_text(encoding="utf-8") == manifest


def test_a_rename_that_cannot_finish_is_refused_before_anything_moves(
        tmp_path):
    """A folder of the project ChromIQ may not write in: refused with a
    sentence, before the first file (or a stranger) is touched.

    MUTATION, proven red: remove the ``os.access`` check from the plan pass
    of `Project.rename`: the rename starts, fails with a bare PermissionError
    (not `ProjectRenameRefused`), and the refusal names no folder."""
    from core.file_manager import Project, ProjectRenameRefused
    proj = _project_with_a_built_profile(tmp_path, "Alpha")
    locked = proj.current_run().verifications_dir
    before = _listing(tmp_path / "Alpha")
    os.chmod(locked, 0o555)
    try:
        with pytest.raises(ProjectRenameRefused) as exc:
            Project.load(tmp_path / "Alpha").rename("Beta")
    finally:
        os.chmod(locked, 0o755)
    assert "verifications" in str(exc.value)
    assert "/" not in str(exc.value)
    assert _listing(tmp_path / "Alpha") == before


def test_the_failure_message_says_what_went_wrong_in_words():
    """F6: "What went wrong" is a sentence, never a bare path, and a
    case-only rename does not print one name twice.

    MUTATION, proven red: make `rename_failure_reason` return ``str(exc)``
    (the path is back); or put ``“{folder}” to “{new}”`` back in the body
    (the case-only name twice)."""
    from workflow import measurement_messages as M
    taken = FileExistsError(errno.EEXIST, "already exists",
                            "/Users/x/ChromIQ/Report-Limits-copy")
    why = M.rename_failure_reason(taken)
    assert "Report-Limits-copy" in why and "/" not in why, why
    assert "/" not in M.rename_failure_reason(
        PermissionError(errno.EACCES, "denied", "/a/b"))
    assert "/" not in M.rename_failure_reason(
        FileNotFoundError(errno.ENOENT, "gone", "/a/b/c.icc"))
    _t, body = M.M_PROJECT_FOLDER_RENAME_FAILED.render(
        folder="report-limits", new="report-limits", error=why,
        name="Report-Limits")
    assert "“report-limits” to “report-limits”" not in body
    assert "“Report-Limits” to “report-limits”" in body
    assert "Nothing was changed" in body


# ---------------------------------------------------------------------------
# F3: the control-strip declarations travel with a rename
# ---------------------------------------------------------------------------
def test_a_rename_carries_the_control_strip_declarations(tmp_path):
    """Both declarations (the shared verification chart's and a dated
    chart's copy) carry the new name after an ordinary rename.

    MUTATION, proven red: put back ``\\.[\\w.]+$`` without the optional
    ``(\\.control-strip)?`` in `Project.rename`'s pattern: both keep "Alpha"."""
    from core.file_manager import FileManager
    _project_with_a_built_profile(tmp_path, "Alpha")
    FileManager(_Settings(tmp_path)).rename_existing_project(
        tmp_path / "Alpha", "Beta")
    names = _listing(tmp_path / "Beta")
    assert not [n for n in names if "Alpha" in n], names
    ver = "runs/run1/verifications"
    assert f"{ver}/Beta-verify.control-strip.json" in names, names
    assert (f"{ver}/2026-12-01_090000/chart/Beta-verify.control-strip.json"
            in names), names


# ---------------------------------------------------------------------------
# F2: a renamed Finder duplicate's report window stays in its own folder
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=False)
def _quiet(monkeypatch):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    monkeypatch.setattr(MeasurementReportDialog, "_ask_update_or_create_new",
                        lambda self: "new")


def test_a_renamed_duplicate_reads_only_its_own_measurements(
        tmp_path, qapp, _quiet):
    """The challenge round's R2-renamed-copy, on disk: project P with a
    report of two dates, duplicated beside itself as "P copy" and renamed
    (it becomes "P-copy"). Its window loads only P-copy's measurements, and
    every one of its reports is filed as P-copy's, not under "Reports
    including multiple projects".

    MUTATION, proven red: make `resolve_recorded_folder` return the recorded
    folder unchanged (``return d`` first): the report's second date is
    loaded from the ORIGINAL, and the reports go under "multiple projects".
    MUTATION, proven red: in `_entry_places` use the recorded folders as
    they are (``dirs = [d for d in recorded if d]``): the loader is right
    but every report is filed under "Reports including multiple projects".
    """
    from core.file_manager import FileManager
    from tests.test_report_shown_is_grouped_by_run_and_project import (
        _dated, _dialog, _headings, _save_doc)
    from tests.test_import_measurement_module import _verify_env
    s, fm, _ctl, run1 = _verify_env(tmp_path)
    v = [_dated(run1), _dated(run1)]
    _save_doc([v[0].dir, v[1].dir], [v[0].measurement_ti3,
                                     v[1].measurement_ti3])
    original = tmp_path / "P"
    shutil.copytree(original, tmp_path / "P copy")
    FileManager(_Settings(tmp_path)).rename_existing_project(
        tmp_path / "P copy", "P copy")
    copy = tmp_path / "P-copy"
    assert copy.is_dir() and original.is_dir()
    ti3 = (copy / v[0].dir.relative_to(original)
           / v[0].measurement_ti3.name.replace("P", "P-copy", 1))
    assert ti3.is_file()
    dlg = _dialog(s, ti3, qapp)
    try:
        origins = sorted({str(r.get("_origin_dir") or "")
                          for r in dlg._history})
        assert len(origins) == 2, origins
        for o in origins:
            assert Path(o).is_relative_to(copy), (
                f"the copy's window loaded {o} from another project")
        assert "Reports including multiple projects" not in _headings(dlg)
        from workflow.measurement_report import KIND_VERIFICATION
        docs = dlg._saved_documents(dlg._run_ctx.run)
        assert docs, "no report listed, so this proves nothing"
        for d in docs:
            places = dlg._entry_places(d)
            assert {p for p, _r in places} == {"P-copy"}, (d["label"], places)
        assert dlg._window_kind() == KIND_VERIFICATION
    finally:
        dlg.close()


def test_a_renamed_duplicate_loads_its_own_other_run(tmp_path, qapp, _quiet):
    """The drive's case, which the test above cannot show: the report covers
    a date of ANOTHER run (run 2), so opening on it has to LOAD that date,
    and the renamed copy's file is "P-copy-verify.ti3" while the report
    recorded "P-verify.ti3". It is loaded from the copy, and nothing from
    the original beside it.

    MUTATION, proven red: remove the `renamed_file_name` fallback from
    `_load_the_documents_other_measurements`: run 2's date "is not on disk"
    and the window holds run 1 alone (seen on screen before the fix was
    finished, fixes/F1-F2-F3-rename).
    MUTATION, proven red: `resolve_recorded_folder` returning the recorded
    folder (``return d`` first): run 2's date is loaded from the ORIGINAL."""
    from core.file_manager import FileManager
    from tests.test_report_shown_is_grouped_by_run_and_project import (
        _dialog, _headings, _save_doc, _two_runs)
    s, _fm, run1, run2, v1, v2 = _two_runs(tmp_path)
    _save_doc([v1[1].dir, v2[0].dir],
              [v1[1].measurement_ti3, v2[0].measurement_ti3])
    original = tmp_path / "P"
    shutil.copytree(original, tmp_path / "P copy")
    FileManager(_Settings(tmp_path)).rename_existing_project(
        tmp_path / "P copy", "P copy")
    copy = tmp_path / "P-copy"
    ti3 = (copy / v1[1].dir.relative_to(original)
           / v1[1].measurement_ti3.name.replace("P", "P-copy", 1))
    dlg = _dialog(s, ti3, qapp)
    try:
        origins = sorted({str(r.get("_origin_dir") or "")
                          for r in dlg._history})
        want = str(copy / v2[0].dir.relative_to(original))
        assert want in origins, origins
        for o in origins:
            assert Path(o).is_relative_to(copy), (
                f"the copy's window loaded {o} from another project")
        assert "Reports including multiple projects" not in _headings(dlg)
    finally:
        dlg.close()


def test_the_old_name_never_reaches_into_the_original(tmp_path):
    """A date the copy does not have is not taken from the original, however
    the original is named: `resolve_recorded_folder` answers None for a
    folder recorded under one of this project's own names.

    MUTATION, proven red: drop ``if ours: return None`` (the recorded path,
    which is the original's, comes back)."""
    from core.file_manager import Project
    from workflow.measurement_report import resolve_recorded_folder
    orig = Project.create(tmp_path / "P", "P")
    (tmp_path / "P" / "runs" / "run1" / "verifications" / "2026-01-01"
     ).mkdir(parents=True)
    shutil.copytree(tmp_path / "P", tmp_path / "P-copy")
    shutil.rmtree(tmp_path / "P-copy" / "runs" / "run1" / "verifications")
    man = json.loads((tmp_path / "P-copy" / "project.json").read_text(encoding="utf-8"))
    man["target_name"], man["former_names"] = "P-copy", ["P"]
    (tmp_path / "P-copy" / "project.json").write_text(json.dumps(man), encoding="utf-8")
    recorded = tmp_path / "P" / "runs" / "run1" / "verifications" / "2026-01-01"
    assert recorded.is_dir()
    assert resolve_recorded_folder(recorded, [tmp_path / "P-copy"]) is None
    # …while a genuinely other project, named by a report across projects,
    # is still found beside it
    q = Project.create(tmp_path / "Q", "Q")
    qd = tmp_path / "Q" / "runs" / "run1"
    assert resolve_recorded_folder(qd, [tmp_path / "P-copy"]) == qd
    assert orig and q


# ---------------------------------------------------------------------------
# F7: the folder guide says what Update, Delete and an unlock do now
# ---------------------------------------------------------------------------
def test_the_folder_guide_no_longer_promises_a_recalculation():
    """§18.2 and B8-391: an unlock recalculates nothing, and Update and
    Delete MOVE a report into reports/old/<stamp>/.

    MUTATION, proven red: put back either of the old sentences ("…and its
    reports recalculated. Copied, never moved…" or "…then recalculates
    them")."""
    from ui import file_guide as G
    texts = [G.file_guide_body(), G.file_guide_html()]
    for row in G._structure():
        texts.append(str(row[-1]))
    for row in G._folders():
        texts.append(str(row[-1]))
    for row in G._features():
        texts.extend(str(x) for x in row)
    blob = "\n".join(texts)
    assert "recalculat" not in blob.lower(), [
        t for t in texts if "recalculat" in t.lower()]
    assert "never moved, so the live report" not in blob
    assert "Delete Selected Report" in blob


# ---------------------------------------------------------------------------
# F8: the lower value's cross stays lower
# ---------------------------------------------------------------------------
def test_the_lower_value_s_cross_stays_lower():
    """Two crosses on one date, close enough to stack: the one drawn for the
    LOWER value (the larger y) stays below, whichever is listed first, and
    they sit one stacking step apart.

    MUTATION, proven red: put back the old rule (a later cross always moves
    up from the others): with the lower value listed second it lands on
    top."""
    from PyQt6.QtCore import QPointF as P
    import ui.dialogs.measurement_report_dialog as mrd
    top, bottom = 24.0, 300.0
    step = mrd._WITHHELD_STACK_PX
    # "nine locations" 0.203 at y 150, "difference from the mean" 0.114 at
    # y 156 (lower value, larger y), listed in that order
    hi, lo = mrd._stack_withheld_marks([(3, P(80, 150)), (3, P(80, 156))],
                                       top, bottom)
    assert lo.y() > hi.y(), (hi.y(), lo.y())
    assert lo.y() == pytest.approx(156)
    assert lo.y() - hi.y() == pytest.approx(step)
    # the same pair listed the other way round
    lo2, hi2 = mrd._stack_withheld_marks([(3, P(80, 156)), (3, P(80, 150))],
                                         top, bottom)
    assert lo2.y() > hi2.y()
    # near the top the higher one stays and the lower goes below it
    a, b = mrd._stack_withheld_marks([(0, P(10, 27)), (0, P(10, 30))],
                                     top, bottom)
    assert b.y() > a.y() and a.y() == pytest.approx(27)
    assert b.y() - a.y() == pytest.approx(step)


# ---------------------------------------------------------------------------
# F9: the Colour accuracy legend carries "(ΔE00)" like every other graph
# ---------------------------------------------------------------------------
def test_the_accuracy_legend_names_its_unit_as_the_others_do(tmp_path, qapp):
    """Every legend entry of every graph that measures a colour difference
    ends in "(ΔE00)"; none says a bare "ΔE".

    MUTATION, proven red: put `_METRIC_LABELS` back in `_trend_configs`
    ("Average ΔE, all patches", no "(ΔE00)")."""
    from workflow.compliance_sets import effective_limits
    from tests.test_trend_graphs_for_judged_metrics import _open
    dlg = _open(tmp_path, qapp, effective_limits("chromiq_default", {}))
    try:
        for series in ([{"created": "x", "avg_all": 1.0,
                         "de00_population": "all"}],
                       [{"created": "x", "avg_all": 1.0,
                         "de00_population": "in_gamut"}]):
            dlg._trend_series = series
            labels = [m[0] for m in dlg._trend_configs()[0][2]]
            assert len(labels) == 5
            for lbl in labels:
                assert lbl.endswith("(ΔE00)"), labels
                assert "ΔE," not in lbl, labels
    finally:
        dlg.deleteLater()
