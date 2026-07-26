"""Snapshot and restore the chart a verification run was measured against
(#130, Knut's specification of 2026-07-25).

A run's verification chart lives once, at the root of ``runs/runN/verifications/``,
and is shared by every dated verification underneath it. Replace that chart and
the older dated results silently stop describing anything you still have — you
can no longer tell what was on the sheet you measured last month.

So each verification measurement takes a **copy of the chart it is about to
measure** into its own dated folder::

    runs/runN/verifications/
        <name>-verify.ti2          ← the live chart
        <name>-verify.ti1
        <name>-verify.channels.json
        <name>-verify_01.tif
        2026-07-25_143000/
            chart/                 ← the snapshot: what THIS run measured
                <name>-verify.ti2
                <name>-verify.ti1
                <name>-verify.channels.json
            <name>-verify.ti3      ← the measurement itself

and **Restore Used Chart** puts a snapshot back when you need the old chart
again.

Two rules from the specification shape what is copied:

* Page images (``.tif``/``.tiff``) are **not** snapshotted — they are rebuilt
  from the chart files, which keeps a snapshot small.
* **Unless they cannot be rebuilt.** Rebuilding needs the layout recipe in
  ``.channels.json``; a chart laid out by ``printtarg`` has no such file. When
  the recipe is missing the images are snapshotted too, so a restore always ends
  with printable pages (Knut, 2026-07-25).

Pure file logic — no Qt — so every branch is unit-testable.
"""
from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from core.file_manager import Run, Verification
from core.logger import get_logger

log = get_logger(__name__)

CHART_SUBDIR = "chart"
_IMAGE_SUFFIXES = (".tif", ".tiff")
_RECIPE_SUFFIX = ".channels.json"


# ---------------------------------------------------------------------------
# what counts as a chart file
# ---------------------------------------------------------------------------
def _is_image(p: Path) -> bool:
    return p.suffix.lower() in _IMAGE_SUFFIXES


def live_chart_files(run: Run) -> list[Path]:
    """Every file at the root of ``verifications/`` — the live verification
    chart. Folders (the dated runs, ``old/``, ``reports/``) are never included."""
    vdir = run.verifications_dir
    if not vdir.exists():
        return []
    return sorted(p for p in vdir.iterdir() if p.is_file())


def has_layout_recipe(files: "list[Path]") -> bool:
    """Whether *files* carry the recipe the page images can be rebuilt from."""
    return any(p.name.endswith(_RECIPE_SUFFIX) for p in files)


def files_to_snapshot(run: Run) -> list[Path]:
    """The chart files a snapshot copies: everything at the root of
    ``verifications/`` except the page images — plus the page images when there
    is no ``.channels.json`` to rebuild them from."""
    files = live_chart_files(run)
    if not files:
        return []
    if has_layout_recipe(files):
        return [p for p in files if not _is_image(p)]
    return files                      # no recipe → the images must travel too


# ---------------------------------------------------------------------------
# snapshot
# ---------------------------------------------------------------------------
def snapshot_dir(verification: Verification) -> Path:
    return verification.dir / CHART_SUBDIR


def snapshot_chart(verification: Verification) -> "Path | None":
    """Copy the live verification chart into ``<date_time>/chart/`` before the
    measurement starts. Returns the snapshot folder, or None when the run has no
    verification chart to copy. Never moves or deletes anything."""
    run = verification.run
    sources = files_to_snapshot(run)
    if not sources:
        return None
    dest = snapshot_dir(verification)
    dest.mkdir(parents=True, exist_ok=True)
    for src in sources:
        shutil.copy2(src, dest / src.name)
    log.info("verification %s: snapshotted %d chart file(s)",
             verification.id, len(sources))
    return dest


def snapshot_files(verification: Verification) -> list[Path]:
    """The files held in a verification's chart snapshot (empty when none)."""
    d = snapshot_dir(verification)
    if not d.exists():
        return []
    return sorted(p for p in d.iterdir() if p.is_file())


def has_snapshot(verification: Verification) -> bool:
    """Whether this verification has a restorable chart."""
    return bool(snapshot_files(verification))


# ---------------------------------------------------------------------------
# restore
# ---------------------------------------------------------------------------
def _digest(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _restored_name(src_name: str, snap_stem: str, live_stem: str) -> str:
    """A snapshot file's name under the run's CURRENT verify stem, so a project
    renamed since the snapshot restores as ``<new-name>-verify.ti2`` rather than
    reintroducing the old name (#130)."""
    if snap_stem and snap_stem != live_stem and src_name.startswith(snap_stem):
        return live_stem + src_name[len(snap_stem):]
    return src_name


def _snapshot_stem(files: "list[Path]") -> str:
    """The verify stem the snapshot was taken under, read from its .ti2."""
    for p in files:
        if p.suffix.lower() == ".ti2":
            return p.stem
    return ""


def live_differs_from_snapshot(verification: Verification) -> bool:
    """Whether the live chart differs from this verification's snapshot.

    Compared by **content**, not timestamps: ``copy2`` preserves mtimes, so a
    restored chart carries the snapshot's old date and a "newer than" test would
    wrongly call them unchanged (#130, Knut). A missing counterpart on either
    side counts as a difference.
    """
    snap = snapshot_files(verification)
    if not snap:
        return False
    run = verification.run
    live = {p.name: p for p in live_chart_files(run)}
    snap_stem = _snapshot_stem(snap)
    for s in snap:
        want = _restored_name(s.name, snap_stem, run.verify_stem)
        counterpart = live.get(want)
        if counterpart is None or _digest(counterpart) != _digest(s):
            return True
    return False


@dataclass
class RestoreResult:
    """What a restore did, so the UI can report it in plain language."""
    restored: list[Path] = field(default_factory=list)
    images_restored: bool = False      # page images came from the snapshot
    needs_regeneration: bool = False   # no images and no recipe to rebuild them
    rolled_back: bool = False
    error: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.restored) and not self.rolled_back

    @property
    def should_rebuild(self) -> bool:
        """The pages were not in the snapshot, but the recipe to redraw them
        was — so the caller can rebuild them and the user need do nothing.

        The three outcomes are exclusive: the images came back
        (:attr:`images_restored`), they can be redrawn (this), or they can
        neither be restored nor redrawn (:attr:`needs_regeneration`, which is the
        only case the user is asked to act on).
        """
        return self.ok and not self.images_restored and not self.needs_regeneration


def restore_chart(verification: Verification) -> RestoreResult:
    """Put a verification's snapshotted chart back as the run's live chart.

    **Transactional** (#130, Knut): the live chart files are moved aside first,
    the snapshot is copied in, and only then is the set-aside copy discarded. Any
    failure puts the original files back exactly as they were, so a restore can
    never leave the run with a half-replaced chart.

    Folders inside ``verifications/`` — the dated results, ``old/``, ``reports/``
    — are never touched. Page images are restored when the snapshot carries them;
    otherwise ``needs_regeneration`` tells the caller to rebuild them from the
    recipe.
    """
    result = RestoreResult()
    snap = snapshot_files(verification)
    if not snap:
        result.error = "no snapshot"
        return result

    run = verification.run
    vdir = run.verifications_dir
    vdir.mkdir(parents=True, exist_ok=True)
    displaced = live_chart_files(run)
    stash = verification.dir / f".restore-stash-{verification.id}"
    snap_stem = _snapshot_stem(snap)

    try:
        # 1. move the live chart aside (not delete — this is the rollback copy)
        if displaced:
            stash.mkdir(parents=True, exist_ok=True)
            for p in displaced:
                shutil.move(str(p), str(stash / p.name))
        # 2. copy the snapshot in, under the run's current verify stem
        for s in snap:
            target = vdir / _restored_name(s.name, snap_stem, run.verify_stem)
            shutil.copy2(s, target)
            result.restored.append(target)
        result.images_restored = any(_is_image(p) for p in result.restored)
        result.needs_regeneration = not result.images_restored and \
            not has_layout_recipe(result.restored)
    except OSError as exc:
        # 3. rollback — put every displaced file back, drop anything written
        log.warning("restore failed, rolling back: %s", exc)
        for p in result.restored:
            p.unlink(missing_ok=True)
        if stash.exists():
            for p in stash.iterdir():
                shutil.move(str(p), str(vdir / p.name))
        result.restored = []
        result.rolled_back = True
        result.error = str(exc)
    finally:
        shutil.rmtree(stash, ignore_errors=True)

    if result.ok:
        log.info("verification %s: restored %d chart file(s)%s",
                 verification.id, len(result.restored),
                 " (pages need rebuilding)" if result.needs_regeneration else "")
    return result
