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
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from core.file_manager import Run, Verification
from core.logger import get_logger

log = get_logger(__name__)

CHART_SUBDIR = "chart"
_IMAGE_SUFFIXES = (".tif", ".tiff")
_RECIPE_SUFFIX = ".channels.json"

# A chart file says which way its patches were ordered, and under which number.
# ChromIQ's layout engine writes RANDOM_START on a shuffled chart and CHART_ID
# on a fixed-order one (workflow/layout_engine/ti2_writer.py), following
# printtarg. Both carry a number, and the difference between them decides what
# can honestly be said about reproducing the chart — see :func:`chart_order_of`.
_ORDER_RE = re.compile(r'\b(RANDOM_START|CHART_ID)\s+"?(\d+)"?')

#: How a chart's patches were ordered, as reported by :func:`chart_order_of`.
ORDER_SHUFFLED = "shuffled"
ORDER_FIXED = "fixed"
ORDER_UNKNOWN = ""


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


def chart_order_of(files: "list[Path]") -> "tuple[str, str]":
    """``(order, number)`` for the ``.ti2`` among *files*.

    *order* is :data:`ORDER_SHUFFLED`, :data:`ORDER_FIXED` or
    :data:`ORDER_UNKNOWN`; *number* is the value beside the keyword, or "".

    Knut asked (#130, 2026-07-29) why the number in his chart —
    ``CHART_ID "1916078606"`` — did not reproduce the chart when he fed it to
    the layout engine as a seed. Two reasons, and this function is what lets the
    restore window say them:

    * ``CHART_ID`` means the chart was **not** shuffled. ChromIQ writes its
      layout seed under that keyword all the same, but with no shuffle to drive
      the seed changes nothing at all (``location_permutation`` is the identity
      when ``randomize`` is False).
    * Even on a shuffled chart the number is only half the story: the shuffle is
      applied to a patch set ArgyllCMS generated at the time, at the page and
      patch sizes then in force. Without the layout recipe none of that comes
      back, so the same number lands different colours in different places.
    """
    for p in files:
        if p.suffix.lower() != ".ti2":
            continue
        try:
            m = _ORDER_RE.search(p.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            return ORDER_UNKNOWN, ""
        if m is None:
            return ORDER_UNKNOWN, ""
        return (ORDER_SHUFFLED if m.group(1) == "RANDOM_START"
                else ORDER_FIXED), m.group(2)
    return ORDER_UNKNOWN, ""


def regeneration_message(order: str = ORDER_UNKNOWN, number: str = "") -> str:
    """What to tell the user when a restored chart cannot be redrawn.

    Knut, #130 2026-07-29: *"This information does not mention that, if
    randomisation was used on the original chart, it is likely not possible to
    reproduce the exact chart used for measurement unless user has the exact
    random seed number… This should be mentioned."*

    It is mentioned — and one correction is folded in, because it changes what
    the user should do. The number **is** stored: it sits in the restored
    ``.ti2`` itself. It is simply not sufficient, for the reasons in
    :func:`chart_order_of`. Telling someone to go and find a seed they already
    have would send them hunting for the wrong thing.
    """
    from core.i18n import tr
    parts = [tr(
        "The chart files are back in place, but this chart was made without the "
        "layout information ChromIQ needs to redraw its printable pages, and no "
        "page images were stored with it.\n\n"
        "Your measurements are safe, and they still belong to the chart file "
        "that has just been restored. Only the printed pages are missing."), ""]

    if order == ORDER_SHUFFLED:
        parts.append(tr(
            "One thing to know before you rebuild it: the patches on this chart "
            "were SHUFFLED. The number ChromIQ shuffled them with is recorded "
            "in the restored chart file as RANDOM_START “{number}”, so "
            "you have not lost it — but that number on its own is not enough to "
            "draw the same sheet again. The shuffle was applied to a patch set "
            "ArgyllCMS generated at the time, at the page size, patch size and "
            "margins then in force, and none of that was stored with the chart. "
            "A chart you create now will almost certainly put different colours "
            "in different places."
        ).format(number=number or tr("not recorded")))
    elif order == ORDER_FIXED:
        parts.append(tr(
            "One thing to know before you rebuild it: the patches on this chart "
            "were NOT shuffled — they sit in the order ArgyllCMS produced them. "
            "The number in the restored chart file, CHART_ID “{number}”, "
            "is ChromIQ's layout number, and on an unshuffled chart it changes "
            "nothing, so feeding it back as a seed will not reproduce anything. "
            "The patch colours themselves came from ArgyllCMS at the time and "
            "are not recreated from a number either, so a chart you create now "
            "will most likely not be the same chart."
        ).format(number=number or tr("not recorded")))
    else:
        parts.append(tr(
            "One thing to know before you rebuild it: if the patches on this "
            "chart were shuffled, the exact sheet cannot be reproduced. The "
            "shuffle was applied to a patch set ArgyllCMS generated at the time, "
            "at the page and patch sizes then in force, and none of that was "
            "stored with the chart. A chart you create now will most likely put "
            "different colours in different places."))

    parts.append("")
    parts.append(tr(
        "This matters only if you want to PRINT and MEASURE this chart again. "
        "It changes nothing about the measurement you already have, and nothing "
        "about the report or the profile built from it.\n\n"
        "To print a chart for this run again, open the Create Chart tab and "
        "create one, then print as usual — treating it as a new chart, which is "
        "what it will be."))
    return "\n".join(parts)


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


# ---------------------------------------------------------------------------
# The same three operations, for a profiling run or a dated verification
# (#130, Knut 2026-07-27). See workflow/chart_slot.py for what differs.
# ---------------------------------------------------------------------------
def snapshot_matches_live(slot) -> bool:
    """Whether the stored chart is already identical to the live one.

    Knut, #130 2026-07-30: *"when I press 'Restore Used Chart' seemingly nothing
    happens … then the 'Restore Used Chart' could be disabled / greyed with a
    tool-tip."* Restoring a copy of what is already there is a button press that
    produces no visible effect, which reads as a broken button.

    Compared by name and by bytes: same set of files, same contents. Anything
    unreadable counts as "not identical", so the button stays available — being
    offered a restore you did not need is a smaller fault than being denied one
    you did.
    """
    d = slot.snapshot_dir
    if not d.is_dir():
        return False
    # EVERYTHING THE RUN HOLDS, not just what a copy would take today.
    #
    # Knut, #130 2026-08-02, ruling on which files decide this: *"I prefer
    # images are always counted when both sides have them — even with a
    # recipe."* `files_to_copy()` answers a different question (what to put IN
    # the folder), and using it here meant a page image that had changed under
    # a recipe-carrying chart was never noticed.
    live = [p for p in slot.live_files()]
    if not live:
        return False
    # Through the same filter as everything else, so a stray .DS_Store cannot
    # make two identical charts look different and re-enable the button.
    stored = slot_snapshot_files(slot)
    # meta.json and its kind travel WITH the chart but do not define it —
    # `slot_live_differs` has always skipped them for exactly that reason, and
    # this check must agree or the two disagree about whether a restore would
    # change anything. Knut's run4 differed from its stored copy by two bytes of
    # meta.json, which kept "Restore Used Chart" enabled for ever while runs 1-3
    # behaved (#130, 2026-08-01).
    from workflow.chart_slot import CHART_SIDE_FILES, _is_image
    stored = [f for f in stored if f.name not in CHART_SIDE_FILES]
    live = [f for f in live if f.name not in CHART_SIDE_FILES]
    # A SNAPSHOT MAY HOLD MORE THAN A COPY WOULD TAKE TODAY.
    #
    # `files_to_copy` leaves the page images out when the chart carries a
    # layout recipe — they can be redrawn from it. But snapshots taken before
    # that rule, or from a chart that had no recipe, DO contain them, and
    # comparing "what a copy would take now" against "everything in the folder"
    # then finds extra files on the stored side and calls two identical charts
    # different. The button was enabled for ever, and pressing it did nothing
    # visible — the very fault greying it was meant to cure.
    #
    # Knut, #130 2026-08-01, on a duplicated run whose files are identical on
    # both sides: *"files in chart/ folder seem identical as the chart files in
    # run5/. The chart/ folder has tif files in this case. Why is still 'Restore
    # Used Chart' button enabled?"* Because of those .tif files.
    #
    # THE RULE, as Knut settled it (#130, 2026-08-02):
    #
    #   Both sides have page images  → the images are compared. A page that
    #                                  differs from its stored copy means
    #                                  something diverged, recipe or not.
    #   Only one side has them       → they are left out. The snapshot of a
    #                                  recipe-carrying chart deliberately omits
    #                                  them (they can be redrawn), so their
    #                                  absence is not a difference.
    stored_imgs = any(_is_image(f) for f in stored)
    live_imgs = any(_is_image(f) for f in live)
    if not (stored_imgs and live_imgs):
        stored = [f for f in stored if not _is_image(f)]
        live = [f for f in live if not _is_image(f)]
    if {f.name for f in stored} != {f.name for f in live}:
        return False
    try:
        for f in live:
            if f.read_bytes() != (d / f.name).read_bytes():
                return False
    except OSError:
        return False
    return True


def snapshot_slot(slot) -> "Path | None":
    """Replace *slot*'s snapshot folder with its live chart. Returns the folder,
    or None when there is no chart to copy.

    The folder is emptied first, so what it holds afterwards is exactly one
    chart. It used to copy over the top, which left files from the previous
    chart behind whenever the new one had fewer or differently-named ones —
    Knut, #130 2026-07-31: *"there is a cht file that does not disappear …
    All old files must be replaced with the new files. None of the old files
    must survive."* A stale file there is not merely untidy: the stored chart
    then no longer matches the live one, which is why "Stored chart differs"
    came back after he had already agreed to replace it.

    Nothing outside the snapshot folder is touched, and the folder is only
    emptied once there is a new chart to put in it — a failed copy can never
    leave the slot with neither.
    """
    sources = slot.files_to_copy()
    if not sources:
        return None
    d = slot.snapshot_dir
    d.mkdir(parents=True, exist_ok=True)
    for old_file in sorted(d.iterdir()):
        try:
            if old_file.is_dir():
                shutil.rmtree(old_file)
            else:
                old_file.unlink()
        except OSError as exc:
            log.warning("could not clear %s from the stored chart: %s",
                        old_file.name, exc)
    for src in sources:
        shutil.copy2(src, d / src.name)
    log.info("stored %s into %s",
             "1 chart file" if len(sources) == 1
             else f"{len(sources)} chart files", d)
    return d


def slot_snapshot_files(slot) -> "list[Path]":
    """The stored chart's files — never the operating system's own leftovers.

    macOS drops ``.DS_Store`` into any folder opened in Finder, and it was being
    snapshotted and restored as though it were part of the chart (found while
    reproducing Knut's `.cht` report, #130 2026-08-01). Harmless in effect, but
    it makes "the stored chart" contain something that is not the chart, and it
    skews the comparison that decides whether a restore would change anything.
    """
    d = slot.snapshot_dir
    if not d.exists():
        return []
    return sorted(p for p in d.iterdir()
                  if p.is_file() and not p.name.startswith("."))


def slot_has_snapshot(slot) -> bool:
    return bool(slot_snapshot_files(slot))


def slot_live_differs(slot) -> bool:
    """Whether the live chart differs from the copy, by CONTENT — ``copy2``
    keeps mtimes, so a "newer than" test would call a restored chart
    unchanged. A missing counterpart on either side counts as a difference."""
    snap = slot_snapshot_files(slot)
    if not snap:
        return False
    live = {p.name: p for p in slot.live_files()}
    from workflow.chart_slot import CHART_SIDE_FILES
    for s in snap:
        # Files that merely travel WITH the chart — meta.json and the like — are
        # restored but do not decide whether the chart itself changed. Otherwise
        # editing the printtarg knobs would raise "this is a different chart"
        # (Knut, #130 2026-07-27).
        if s.name in CHART_SIDE_FILES:
            continue
        counterpart = live.get(s.name)
        if counterpart is None or _digest(counterpart) != _digest(s):
            return True
    return False


def restore_would_lose_pages(slot) -> "list[Path]":
    """Page images a restore would remove and be unable to put back.

    A restore replaces the whole live chart with the stored one. If the run has
    page images, the snapshot has none, and there is no layout recipe to redraw
    them from, those pages are gone for good — the chart becomes unprintable,
    silently. Found by enumerating every recipe / images combination for Knut
    (#130, 2026-08-02); he asked for a warning that lets the user decide, so
    this is what the warning is built from.

    Returns the images at risk, newest first — an empty list when there is
    nothing to lose, which is the normal case.
    """
    from workflow.chart_slot import _is_image, has_layout_recipe
    snap = slot_snapshot_files(slot)
    if not snap:
        return []
    if any(_is_image(p) for p in snap):
        return []                      # the copy brings its own pages back
    live = slot.live_files()
    if has_layout_recipe(snap) or has_layout_recipe(live):
        return []                      # they can be redrawn
    return [p for p in live if _is_image(p)]


def restore_slot(slot) -> "RestoreResult":
    """Put *slot*'s copy back as the live chart.

    Transactional, exactly as the verification restore has always been: the
    live files are moved aside first, the copy is written, and the set-aside
    files are dropped only once that has worked. Any failure puts everything
    back as it was.

    The files keep the names they were copied under. Project renames already
    rewrite every stem everywhere, including inside these folders (Knut
    verified the reasoning, #130 2026-07-27), so nothing is renamed here.
    """
    result = RestoreResult()
    snap = slot_snapshot_files(slot)
    if not snap:
        result.error = "no snapshot"
        return result

    slot.live_dir.mkdir(parents=True, exist_ok=True)
    from workflow.chart_slot import CHART_SIDE_FILES
    all_live = slot.live_files()
    snap_names = {s.name for s in snap}
    # Side files (the settings meta.json — part of a verification slot's
    # live_files, whose suffix filter is None) never go into the stash: the
    # stash is discarded on success, and settings must never be destroyed.
    # One is replaced only when the snapshot carries a counterpart, and the
    # replaced file is archived into old/ first.
    displaced = [p for p in all_live if p.name not in CHART_SIDE_FILES]
    side_replaced = [p for p in all_live
                     if p.name in CHART_SIDE_FILES and p.name in snap_names]
    side_archive = None
    stash = slot.snapshot_dir.parent / f".restore-stash-{slot.snapshot_dir.name}"
    try:
        if side_replaced:
            from core.file_manager import Run as _Run
            side_archive = _Run.for_dir(slot.live_dir).archive_to_old(
                side_replaced, into=slot.live_dir / "old")
        if displaced:
            stash.mkdir(parents=True, exist_ok=True)
            for p in displaced:
                shutil.move(str(p), str(stash / p.name))
        for s in snap:
            target = slot.live_dir / s.name
            shutil.copy2(s, target)
            result.restored.append(target)
        result.images_restored = any(_is_image(p) for p in result.restored)
        result.needs_regeneration = not result.images_restored and \
            not has_layout_recipe(result.restored)
        if result.needs_regeneration:
            # Only then is it consulted, and only then does it cost a file read.
            result.chart_order, result.chart_number = \
                chart_order_of(result.restored)
    except OSError as exc:
        log.warning("restore failed, rolling back: %s", exc)
        for p in result.restored:
            p.unlink(missing_ok=True)
        if stash.exists():
            for p in stash.iterdir():
                shutil.move(str(p), str(slot.live_dir / p.name))
        if side_archive is not None:
            for name in {p.name for p in side_replaced}:
                src = side_archive / name
                if src.exists() and not (slot.live_dir / name).exists():
                    shutil.move(str(src), str(slot.live_dir / name))
        result.restored = []
        result.rolled_back = True
        result.error = str(exc)
    finally:
        shutil.rmtree(stash, ignore_errors=True)
    return result


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
    from workflow.chart_slot import CHART_SIDE_FILES
    for s in snap:
        # Side files (the settings meta.json) travel with the chart but do
        # not decide whether the chart changed — otherwise every settings
        # edit would make every dated check look like "a different chart"
        # (the same rule slot_live_differs already follows).
        if s.name in CHART_SIDE_FILES:
            continue
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
    # How the restored chart's patches were ordered, and under which number —
    # only meaningful when needs_regeneration is True, where it decides what can
    # honestly be said about reproducing the chart (Knut, #130 2026-07-29).
    chart_order: str = ORDER_UNKNOWN
    chart_number: str = ""

    @property
    def regeneration_message(self) -> str:
        """The window's words for :attr:`needs_regeneration`."""
        return regeneration_message(self.chart_order, self.chart_number)

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
    from workflow.chart_slot import CHART_SIDE_FILES
    all_live = live_chart_files(run)
    snap_names = {s.name for s in snap}
    # Side files (the settings meta.json) never go into the stash — the stash
    # is DISCARDED after a successful restore, and settings must never be
    # destroyed. A side file is replaced only when the snapshot carries one,
    # and the replaced file is archived into old/ first; a snapshot without
    # one leaves the live settings exactly as they are.
    displaced = [p for p in all_live if p.name not in CHART_SIDE_FILES]
    side_replaced = [p for p in all_live
                     if p.name in CHART_SIDE_FILES and p.name in snap_names]
    side_archive = None
    stash = verification.dir / f".restore-stash-{verification.id}"
    snap_stem = _snapshot_stem(snap)

    try:
        if side_replaced:
            side_archive = run.archive_to_old(
                side_replaced, into=run.verifications_old_dir)
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
        if result.needs_regeneration:
            # Only then is it consulted, and only then does it cost a file read.
            result.chart_order, result.chart_number = \
                chart_order_of(result.restored)
    except OSError as exc:
        # 3. rollback — put every displaced file back, drop anything written
        log.warning("restore failed, rolling back: %s", exc)
        for p in result.restored:
            p.unlink(missing_ok=True)
        if stash.exists():
            for p in stash.iterdir():
                shutil.move(str(p), str(vdir / p.name))
        if side_archive is not None:
            for name in {p.name for p in side_replaced}:
                src = side_archive / name
                if src.exists() and not (vdir / name).exists():
                    shutil.move(str(src), str(vdir / name))
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
