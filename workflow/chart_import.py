"""Bar-aware import of an external chart into a project, per the shared
Profile-run / Run-type target (#130, unified file-handling model).

Pure file logic — **no Qt** — so the whole combination matrix is unit-tested
headless. The dialogs in ``ui/ti2_loader.py`` gather the user's choices (which
run, Replace vs new run, whole-project vs this-chart) and call these functions.

Destination rules (Model A of the design):
  • Run type = Profiling    → the run root ``runs/runN/`` gets the chart AND, if
    present beside the source, its measurement (``.ti3``) and profile
    (``.icc/.icm``).
  • Run type = Verification → only the chart files go to
    ``runs/runN/verifications/`` as the shared verify chart; any ``.icc/.icm``
    and ``.ti3`` beside the source are ignored.
  • Profile run = New run   → a fresh ``runs/runN+1/``.
  • Profile run = Overwrite → that run; a **Replace** first archives everything
    it displaces (including the verifications) to ``runs/runN/old/<timestamp>/``
    — never deletes (§5a/§5b).
"""
from __future__ import annotations

import shutil
from pathlib import Path

from core.file_manager import FileManager, Project, Run

# Chart-file extensions that travel WITH a chart (never the measurement/profile).
_CHART_EXTS = (".cht", ".channels.json", ".strips.json", ".cie", ".pdf")


def resolve_import_run(project: Project, target) -> Run:
    """The run an import writes into, per the bar's *target*: **New run** (empty
    ``profile_run``) → create ``runN+1`` and make it current; **Overwrite run N**
    → that run, made current. Never archives — that's the caller's Replace step."""
    rid = getattr(target, "profile_run", "") or ""
    if rid and project.has_run(rid):
        if project.current_run().id != rid:
            project.set_current_run(rid)
        return project.run(rid)
    return project.new_run()


def import_external_chart(ti2_path: Path, ti1: "Path | None", tiffs: "list[Path]",
                          project: Project, target, *, replace: bool = False) -> Path:
    """Copy an external chart into the target run per Run type. Returns the
    imported ``.ti2`` inside the project.

    *target* is a :class:`core.measurement_target.MeasurementTarget`; for the
    "Create a new run instead" choice the caller passes a target whose
    ``profile_run`` is empty. *replace* is only meaningful for an Overwrite target.
    """
    run = resolve_import_run(project, target)
    run.ensure_dir()
    verification = target.is_verification()
    if replace:
        archive_run_for_replace(run, verification=verification)
    if verification:
        run.verifications_dir.mkdir(parents=True, exist_ok=True)
        run._clear_verify_chart_files()          # drop any previous verify chart
        _copy_chart_set(ti2_path, ti1, tiffs, run.verifications_dir,
                        run.verify_stem, include_measurement=False)
        return run.verify_chart_ti2
    # Profiling → run root. Clear any stale page TIFFs first (a Replace already
    # archived the rest; a fresh New run is empty).
    for t in run.chart_tiffs():
        t.unlink(missing_ok=True)
    _copy_chart_set(ti2_path, ti1, tiffs, run.dir, run.stem, include_measurement=True)
    return run.chart_ti2


def archive_run_for_replace(run: Run, *, verification: bool) -> "Path | None":
    """Move what a Replace displaces into a timestamped ``old/`` folder (never
    delete). Returns the archive folder, or None when nothing existed.

    The two Run types archive to **different places**, because they act on
    different parts of the run (#130, Knut's ruling of 2026-07-25):

    • **Verification replace** → only the files at the root of
      ``verifications/`` (the shared verify chart), archived into
      ``runs/runN/verifications/old/<timestamp>/``. The dated verification
      folders and everything at the run root are left completely alone: a
      verification never touches the profiling side, and its dated results stay
      where the user expects to find them.
    • **Profiling replace** → the run-root chart, measurement and profile, plus
      **every folder inside the run** (reports, exports, cache, verifications,
      …), archived into ``runs/runN/old/<timestamp>/``. Once the chart is
      replaced, none of that material describes the run any more, so it travels
      with the chart it belonged to.
    """
    if verification:
        paths: list[Path] = [p for p in run.verifications_dir.glob("*")
                             if p.is_file()]
        return run.archive_to_old(paths, into=run.verifications_old_dir)
    s = run.stem
    paths = [run.dir / f"{s}.ti1", run.dir / f"{s}.ti2"]
    paths += [run.dir / f"{s}{ext}" for ext in _CHART_EXTS]
    paths += run.chart_tiffs()
    paths += [run.measurement_ti3, run.profile_icc, run.dir / f"{s}.icm"]
    # Every sub-folder except old/ itself — the chart they belonged to is going.
    paths += [d for d in run.dir.iterdir() if d.is_dir() and d.name != "old"] \
        if run.dir.exists() else []
    return run.archive_to_old([p for p in paths if p.exists()])


def _copy_chart_set(src_ti2: Path, src_ti1: "Path | None", tiffs: "list[Path]",
                    dst_dir: Path, dst_stem: str, *, include_measurement: bool) -> None:
    """Copy a chart's files from beside *src_ti2* into *dst_dir* under *dst_stem*.
    Page TIFFs are renumbered ``<stem>_01.tif``…; measurement/profile only when
    *include_measurement* (Profiling)."""
    old = src_ti2.stem
    dst_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_ti2, dst_dir / f"{dst_stem}.ti2")
    if src_ti1 and Path(src_ti1).exists():
        shutil.copy2(src_ti1, dst_dir / f"{dst_stem}.ti1")
    for ext in _CHART_EXTS:
        sib = src_ti2.with_name(f"{old}{ext}")
        if sib.exists():
            shutil.copy2(sib, dst_dir / f"{dst_stem}{ext}")
    for i, tif in enumerate(sorted(tiffs), start=1):
        shutil.copy2(tif, dst_dir / f"{dst_stem}_{i:02d}.tif")
    if include_measurement:
        ti3 = src_ti2.with_suffix(".ti3")
        if ti3.exists():
            shutil.copy2(ti3, dst_dir / f"{dst_stem}.ti3")
        for ext in (".icc", ".icm"):
            icc = src_ti2.with_suffix(ext)
            if icc.exists():
                shutil.copy2(icc, dst_dir / f"{dst_stem}.icc")
                break


def is_full_project(ti2_path: Path) -> "Path | None":
    """If *ti2_path* sits inside a complete ChromIQ project (an ancestor holds
    ``project.json``), return that project root; else None (A1a vs A1b)."""
    for anc in ti2_path.resolve().parents:
        if (anc / "project.json").is_file():
            return anc
    return None


def copy_whole_project(src_root: Path, working_dir: Path, new_name: str,
                       *, replace: bool = False) -> Path:
    """Copy an entire external ChromIQ project into *working_dir* as *new_name*
    (A1b option i). On a name collision: *replace* False raises
    :class:`FileExistsError`; *replace* True archives the existing project's
    contents to its own ``old/<timestamp>/`` first, then copies in. Returns the
    new project root."""
    name = FileManager._sanitise(FileManager.strip_workfile_ext(new_name))
    dest = Path(working_dir) / name
    if dest.exists():
        if not replace:
            raise FileExistsError(str(dest))
        _archive_project_contents(dest)
    else:
        shutil.copytree(src_root, dest)
        return dest
    # replace path: dest still exists but emptied into old/ — copy the source in
    for item in Path(src_root).iterdir():
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)
    return dest


def _archive_project_contents(project_root: Path) -> Path:
    """Move a project's current contents (except an existing ``old/``) into
    ``<project>/old/<timestamp>/`` before an overwrite."""
    from datetime import datetime
    dest = project_root / "old" / datetime.now().strftime("%Y-%m-%d_%H%M%S")
    dest.mkdir(parents=True, exist_ok=True)
    for item in list(project_root.iterdir()):
        if item.name == "old":
            continue
        shutil.move(str(item), str(dest / item.name))
    return dest
