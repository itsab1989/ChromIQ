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


def _cht_without_expected(data: bytes) -> bytes:
    """A ``.cht`` with its ``EXPECTED`` block taken out.

    A ``.cht`` holds two things: WHERE every patch sits on the page (``BOXES``,
    ``XLIST``/``YLIST``, the fiducials) and an ``EXPECTED XYZ`` value per patch.
    Only the first describes the chart. The second, in a run's folder, is
    written from the run's MEASUREMENT: the scanner-recognition target
    (``workflow/scanin_target.py``, "Save scanner files" in the Quality Check
    window, ``scanner_target_enabled``) rewrites ``<stem>.cht`` from the
    ``.ti3`` every time the run is checked, "so it always reflects the latest
    measurement". A chart built by the layout engine writes EXPECTED values
    that come from the patch set, and the ``.ti1``/``.ti2`` already decide
    those.

    Knut, #182 5956210745 (beta 3): re-measuring run1 said "Stored chart
    differs", Restore Used Chart then changed nothing he could see, and the
    question came back after every re-measurement. His run1's chart files
    were identical to its stored copy byte for byte except ``test.cht``, and
    that differed in five EXPECTED rows only (E23, F1, F3, H9, N1: the patches
    he had re-read before the Quality Check rebuilt the file).
    """
    out: list[bytes] = []
    in_expected = False
    for line in data.splitlines(keepends=True):
        stripped = line.strip()
        if in_expected:
            # the block is its header and the indented rows after it
            if stripped and line[:1] in (b" ", b"\t"):
                continue
            in_expected = False
        if stripped.startswith(b"EXPECTED"):
            in_expected = True
            continue
        out.append(line)
    return b"".join(out)


def chart_content(path: Path) -> bytes:
    """The bytes of *path* that define the chart.

    Every chart file counts in full, except a ``.cht``'s ``EXPECTED`` block:
    see :func:`_cht_without_expected`. This is what every "is it the same
    chart?" question compares (``snapshot_matches_live``,
    ``slot_live_differs``, ``live_differs_from_snapshot``), so the warning
    before a measurement and the Restore Used Chart button can never disagree.
    """
    data = path.read_bytes()
    if path.suffix.lower() == ".cht":
        return _cht_without_expected(data)
    return data


def _cht_geometry(data: bytes) -> bytes:
    """What of a ``.cht`` says where the patches are, with the incidental
    layout of the text taken out: the ``EXPECTED`` block
    (:func:`_cht_without_expected`), line endings, trailing blanks and empty
    lines. Two ``.cht`` files with equal geometry describe the same sheet."""
    kept = _cht_without_expected(data)
    return b"\n".join(ln.rstrip() for ln in kept.split(b"\n") if ln.strip())


def _not_kept_in_a_snapshot(slot, path: Path) -> bool:
    """A ``.cht`` in a run's or the calibration's ``chart/`` folder.

    Knut, #182 5958921500: the run's ``.cht`` is made from a completed
    measurement and is never backed up to ``chart/``. Snapshots taken before
    that ruling can still hold one; the file is left on disk (it is the
    user's), but it is no longer part of the stored chart, so it neither makes
    the stored chart "differ" nor comes back with a restore. A verification
    slot is unchanged: every file at its root is chart.
    """
    return bool(getattr(slot, "holds_measurement_cht", False)) and \
        path.suffix.lower() == ".cht"


def live_chart_files(run: Run) -> list[Path]:
    """Every file at the root of ``verifications/`` — the live verification
    chart. Folders (the dated runs, ``old/``, ``reports/``) are never included."""
    vdir = run.verifications_dir
    if not vdir.exists():
        return []
    # …EXCEPT A MEASUREMENT. ``<verify stem>.ti3`` beside the chart is the
    # reader's working file (chartread's output, or a dated verification staged
    # there for Refine / resume), never part of the chart. A session that died
    # leaves it behind, and counting it as chart copied one date's readings
    # into the NEXT date's ``chart/`` snapshot, made every stored chart "differ"
    # from the live one, and let Restore Used Chart stash and then discard it
    # (review of f53874ca). ``<stem>-reference.ti3`` IS chart, and stays.
    # …AND ITS YELLOW MEMORY (#182 K4, review AN). ``<verify stem>.confirmed.json``
    # is written beside that working file while a verification is read, and a
    # session ended with "Discard and stop" (or a crash) leaves it there; it
    # describes readings, so it is never chart either.
    from workflow.confirmed_patches import SUFFIX as _MEMORY
    measurement = {f"{run.verify_stem}.ti3".lower(),
                   f"{run.verify_stem}{_MEMORY}".lower()}
    return sorted(p for p in vdir.iterdir()
                  if p.is_file() and p.name.lower() not in measurement)


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
    stored = [f for f in slot_snapshot_files(slot)
              if not _not_kept_in_a_snapshot(slot, f)]
    # meta.json and its kind travel WITH the chart but do not define it —
    # `slot_live_differs` has always skipped them for exactly that reason, and
    # this check must agree or the two disagree about whether a restore would
    # change anything. Knut's run4 differed from its stored copy by two bytes of
    # meta.json, which kept "Restore Used Chart" enabled for ever while runs 1-3
    # behaved (#130, 2026-08-01).
    # …and so does the print record: printing the same chart again rewrites
    # its `printed_at` and changes nothing about the chart (Knut, 4.3.3 run5).
    from workflow.chart_slot import _is_image, defines_the_chart
    stored = [f for f in stored if defines_the_chart(f)]
    live = [f for f in live if defines_the_chart(f)]
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
            if chart_content(f) != chart_content(d / f.name):
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
    return any(not _not_kept_in_a_snapshot(slot, p)
               for p in slot_snapshot_files(slot))


def slot_live_differs(slot) -> bool:
    """Whether the live chart differs from the copy, by CONTENT — ``copy2``
    keeps mtimes, so a "newer than" test would call a restored chart
    unchanged. A missing counterpart on either side counts as a difference."""
    snap = slot_snapshot_files(slot)
    if not snap:
        return False
    live = {p.name: p for p in slot.live_files()}
    from workflow.chart_slot import defines_the_chart
    for s in snap:
        # Files that merely travel WITH the chart — meta.json and the print
        # record — are restored but do not decide whether the chart itself
        # changed. Otherwise editing the printtarg knobs would raise "this is a
        # different chart" (Knut, #130 2026-07-27), and so would printing the
        # same chart again (Knut, 4.3.3 run5).
        if not defines_the_chart(s) or _not_kept_in_a_snapshot(slot, s):
            continue
        counterpart = live.get(s.name)
        if counterpart is None or _digest(counterpart) != _digest(s):
            return True
    return False


@dataclass
class ChtPlan:
    """What Restore Used Chart will do with the run's ``.cht`` page(s)."""
    keep: "list[Path]" = field(default_factory=list)
    remove: "list[Path]" = field(default_factory=list)


def restore_cht_plan(slot) -> ChtPlan:
    """Which of the run's scanner ``.cht`` files a restore keeps, and which it
    archives into ``old/<date>/`` and removes (Knut, #182 5958921500).

    *"if the cht file exists in the run's folder (not applicable for a
    verification run), and the content of the cht file is in agreement with
    the chart in the chart/ folder, then the cht file should be kept in the
    run's folder. If the cht file differs from the chart that is being
    restored … then the cht file should be backed up to the old/ folder … and
    removed from the run."*

    AGREEMENT, precisely: a ``.cht`` is kept when it is, line for line, a
    page the scanner target would write for the RESTORED chart, everything
    but its ``EXPECTED`` rows compared. The page is rebuilt from the stored
    copy's ``.channels.json`` by the code that writes the file
    (:func:`workflow.scanin_target.scanner_cht_pages`), under the name it
    would get (``<stem>.cht``, or ``<stem>_NN.cht`` for page NN). The
    ``EXPECTED`` rows are left out because they are the measurement's XYZ, not
    the chart's, and they change with every re-read (#182 5956210745). So:

    * same patch boxes, fiducials, edge lists, page count and page → kept;
    * any of those different, a page the restored chart does not have, or a
      stored chart with no scanner geometry (no ``.channels.json`` or no
      layout in it, so it could never have produced this file) → removed.

    Empty for a verification slot, and when the run has no such file.
    """
    plan = ChtPlan()
    try:
        files = slot.scanner_cht_files()
    except (AttributeError, OSError):
        return plan
    if not files:
        return plan
    recipe = [s for s in slot_snapshot_files(slot)
              if s.name.endswith(".channels.json")]
    pages = None
    if recipe:
        from workflow.scanin_target import scanner_cht_pages
        pages = scanner_cht_pages(recipe[0], slot.stem)
    for f in files:
        want = (pages or {}).get(f.name)
        try:
            same = want is not None and _cht_geometry(f.read_bytes()) == \
                _cht_geometry(want.encode("utf-8"))
        except OSError:
            same = False
        (plan.keep if same else plan.remove).append(f)
    # A .cht and its .cie are a pair (Knut, #182 5959825756: "the cht and cie
    # file are always a pair that belongs together and must always match for
    # the chart used"): a removed .cht takes its .cie with it.
    for f in list(plan.remove):
        cie = f.with_suffix(".cie")
        if cie.is_file() and cie not in plan.remove:
            plan.remove.append(cie)
    return plan


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


#: THE FIELDS OF A RUN'S `meta.json` THAT BELONG TO THE CHART (B8-740, Knut
#: 2026-09-22, #182 comment 5775260868: *"Agreed. The Description and the
#: seven compliance fields are the run's and stay"*, and of everything else that
#: is neither the chart's nor the run's Description: *"It sounds like they
#: should survive too."*). So Restore Used Chart takes ONLY these from the
#: snapshot, and every other field (the Description, the limit binding and
#: report type, and the run's own record: status, what its profile was built
#: from, its measure and profile settings, averaging, lineage) stays as it is
#: live. Named once, here: a field added later is the run's until it is listed.
CHART_META_KEYS: "tuple[str, ...]" = (
    "instrument", "paper", "scanner_target_enabled",
    "chart_notes", "verify_chart_notes",
    "create_chart_settings", "create_chart_ui", "print_settings",
    "editor_layout", "editor_basename", "editor_recipe",
)


def merge_restored_meta(live: dict, snapshot: dict) -> dict:
    """The live `meta.json` with the CHART's fields taken from the snapshot."""
    out = dict(live)
    for key in CHART_META_KEYS:
        if key in snapshot:
            out[key] = snapshot[key]
        else:
            out.pop(key, None)
    return out


def _archive_replaced_chart(stash: Path, archive_with, existing: "Path | None",
                            sub: "str | None" = None) -> "Path | None":
    """Keep the chart a restore replaced (Knut, #182 5959825756: *"archive
    olde chart files to old, except the tif files, they are deleted and can
    be regenerated if the other files are restored"*). Everything set aside in
    *stash* except page images goes into *existing* (the archive this restore
    already made for its side files) or a new ``old/<date>/`` made by
    *archive_with(paths)*; page images stay in the stash, which the caller
    then removes. Returns the archive folder, or None when nothing was kept.

    *sub* puts the chart one level down, in ``<archive>/<sub>/``: a
    calibration's chart goes into ``cal/old/<date>/chart/``, because Knut ruled
    at beta.148 that a bare chart must not sit at the top of a calibration's
    dated folder, where it reads like a kept calibration
    (``Calibration.archive_to_old``, core/file_manager.py)."""
    if not stash.is_dir():
        return existing
    keep = [p for p in stash.iterdir() if p.is_file() and not _is_image(p)]
    if not keep:
        return existing
    def _place(folder: Path, files) -> None:
        if sub:
            folder = folder / sub
            folder.mkdir(parents=True, exist_ok=True)
        for p in files:
            dest = folder / p.name
            n = 2
            while dest.exists():
                dest = folder / f"{p.stem}_{n}{p.suffix}"
                n += 1
            shutil.move(str(p), str(dest))

    if existing is not None:
        _place(existing, keep)
        return existing
    arch = archive_with(keep)
    if arch is not None and sub:
        _place(arch, [arch / p.name for p in keep if (arch / p.name).is_file()])
    return arch


def _is_calibration_slot(slot) -> bool:
    """Whether *slot* is a project's calibration chart (``<project>/cal``)."""
    try:
        from core.file_manager import is_a_project
        return slot.live_dir.name == "cal" and is_a_project(slot.live_dir.parent)
    except Exception:          # noqa: BLE001 — a guess never blocks a restore
        return False


def _fresh_stash(base: Path) -> Path:
    """A stash folder no earlier restore is still using.

    A stash survives a restore only when something could not be put where it
    belongs (an archive or a rollback that failed), and then it holds the ONLY
    copy of a chart. Reusing it would move the next chart's files over those
    of the same name (``shutil.move`` replaces a file) and the success path
    would then archive only the newer one: measured, review AM, the chart of
    the first restore was gone."""
    if not base.exists():
        return base
    n = 2
    while (cand := base.with_name(f"{base.name}-{n}")).exists():
        n += 1
    return cand


def _undo_side_archive(moved: "dict[Path, Path]", live_dir: Path) -> None:
    """Put every file a restore archived back where it came from, by the
    name it really got in ``old/`` (a clash renames it, and an archive that
    raised part way has no folder to return). Raises OSError like any move."""
    for src, dst in moved.items():
        if dst.exists() and not src.exists():
            shutil.move(str(dst), str(src))


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
    # THE RUN'S `.cht` IS NOT PART OF THE STORED CHART (Knut, #182
    # 5958921500). A `.cht` an older snapshot still holds is not put back, and
    # the run's own `.cht` is kept when it agrees with the chart being
    # restored, otherwise archived into old/ with the side files and removed:
    # see `restore_cht_plan`, which the confirmation window reads too.
    snap = [s for s in snap if not _not_kept_in_a_snapshot(slot, s)]
    if not snap:
        result.error = "no snapshot"
        return result
    cht_plan = restore_cht_plan(slot)
    result.cht_kept = [p.name for p in cht_plan.keep]
    result.cht_removed = [p.name for p in cht_plan.remove]
    displaced = [p for p in all_live if p.name not in CHART_SIDE_FILES]
    # ARCHIVE A SIDE FILE THE SNAPSHOT WILL OVERWRITE, WHATEVER THE SLOT.
    #
    # `live_files()` is suffix-filtered on a profiling run's slot and on a
    # calibration's (`PROFILING_CHART_SUFFIXES`, which holds no `meta.json`),
    # so this list was ALWAYS EMPTY on those two: nothing was archived, and
    # the copy loop below still wrote the snapshot's `meta.json` over the live
    # one. Measured, challenge round 36: a profiling run lost all 34 fields on
    # the file and a calibration all 7, with no archive and no undo, from one
    # press of "Restore Used Chart" (B8-740).
    #
    # This does NOT decide which of those fields belong to the chart. That is
    # a ruling and it is Knut's, because #182 added seven compliance fields to
    # a file whose snapshot rule was written for `editor_recipe` and the
    # printtarg knobs. What it restores is the guarantee this function's own
    # docstring already makes: a replaced side file is archived into `old/`
    # first, so the loss is recoverable instead of silent and final.
    side_replaced = [slot.live_dir / name for name in CHART_SIDE_FILES
                     if name in snap_names
                     and (slot.live_dir / name).is_file()]
    # …and the `.cht` that does not belong to the restored chart, into the
    # same dated folder, so one restore leaves one archive.
    side_replaced += list(cht_plan.remove)
    side_archive = None
    side_moved: "dict[Path, Path]" = {}
    stash = _fresh_stash(
        slot.snapshot_dir.parent / f".restore-stash-{slot.snapshot_dir.name}")
    # THE LIVE meta.json, READ BEFORE ANYTHING MOVES (B8-740): only the chart's
    # fields are restored from the snapshot, so the rest must come from here.
    import json as _json
    live_meta: "dict | None" = None
    _live_meta_path = slot.live_dir / "meta.json"
    if _live_meta_path.is_file():
        try:
            live_meta = _json.loads(_live_meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("could not read the live meta.json before restoring: "
                        "%s", exc)
            live_meta = None
    # Set before the try: the `finally` reads it on EVERY path.
    _rollback_ok = True
    try:
        if side_replaced:
            from core.file_manager import Run as _Run
            side_archive = _Run.for_dir(slot.live_dir).archive_to_old(
                side_replaced, into=slot.live_dir / "old", moved=side_moved)
        if displaced:
            stash.mkdir(parents=True, exist_ok=True)
            for p in displaced:
                shutil.move(str(p), str(stash / p.name))
        for s in snap:
            target = slot.live_dir / s.name
            if s.name == "meta.json" and isinstance(live_meta, dict):
                # THE CHART'S FIELDS FROM THE SNAPSHOT, EVERYTHING ELSE LIVE.
                try:
                    snap_meta = _json.loads(s.read_text(encoding="utf-8"))
                except ValueError as exc:
                    # a snapshot we cannot read restores NO field: the live
                    # settings stay exactly as they were (the rollback below
                    # only handles OSError, so this must not escape)
                    log.warning("snapshot meta.json unreadable, live settings "
                                "kept: %s", exc)
                    snap_meta = {k: live_meta[k] for k in CHART_META_KEYS
                                 if k in live_meta}
                target.write_text(_json.dumps(
                    merge_restored_meta(live_meta, snap_meta), indent=2),
                    encoding="utf-8")
            else:
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
        # A ROLLBACK THAT FAILS MUST NOT ALSO DESTROY THE ONLY COPY.
        # These moves were outside any `try`, while the `finally` below deletes
        # the stash unconditionally — so a rollback that raised part way
        # through left the live chart half-restored AND took the stash holding
        # the originals with it. Fault-injected: 2 of 3 live chart files gone,
        # nothing anywhere, and the exception escaping on top. The stash is the
        # last copy while a rollback is in flight, so it is kept whenever the
        # rollback did not fully succeed, and its location is logged loudly for
        # the person who now has to put it right by hand.
        _rollback_ok = True
        try:
            for p in result.restored:
                p.unlink(missing_ok=True)
            if stash.exists():
                for p in stash.iterdir():
                    shutil.move(str(p), str(slot.live_dir / p.name))
            # By the name each file REALLY got (review AM): an archive that
            # raised part way returned no folder, and one sharing its dated
            # folder with an earlier restore renamed a clash, so `old/<date>/
            # meta.json` could be the EARLIER restore's file.
            _undo_side_archive(side_moved, slot.live_dir)
        except OSError as roll_exc:      # noqa: BLE001 — report, never destroy
            _rollback_ok = False
            log.error("THE ROLLBACK ITSELF FAILED (%s). The chart files are "
                      "kept at %s — nothing there has been deleted, and only a "
                      "person can put this right.", roll_exc, stash)
        result.restored = []
        result.rolled_back = True
        result.error = str(exc)
        result.cht_removed = []
    finally:
        # The replaced chart is KEPT in old/, page images apart, and only
        # after the restore worked; a rolled-back restore has already put it
        # back in the run.
        if _rollback_ok and not result.rolled_back:
            try:
                from core.file_manager import Run as _Run2
                result.archive = _archive_replaced_chart(
                    stash,
                    lambda ps: _Run2.for_dir(slot.live_dir).archive_to_old(
                        ps, into=slot.live_dir / "old"),
                    side_archive,
                    sub="chart" if _is_calibration_slot(slot) else None)
            except OSError as exc:     # noqa: BLE001 — never lose the stash
                log.error("could not archive the replaced chart; it is kept "
                          "at %s: %s", stash, exc)
                _rollback_ok = False
        # Only when nothing depends on it any more.
        if _rollback_ok:
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


def set_aside_stored_chart(verification: Verification,
                           when: str) -> "Path | None":
    """Move a dated verification's stored chart to ``<date>/old/<when>/chart/``
    before a DIFFERENT chart is snapshotted in its place ("Replace the stored
    chart"). Returns where it went, or None when there was nothing to keep.

    :func:`snapshot_chart` copies over the top, so a replace used to lose the
    chart the date's measurement was made with, and left that chart's files
    mixed into the new one: a gamut chart's ``-verify-reference.ti3`` stayed
    behind a regular chart, and Restore Used Chart then put a colorimetric
    reference back beside it. Moving the folder away first keeps the old chart
    (nothing is deleted) and lets the snapshot start from an empty folder.

    *when* is the same ``%Y-%m-%d_%H%M%S`` stamp the date's previous
    measurement is kept under when the new one is filed, so the old chart and
    the old measurement it belongs to end up side by side. Raises OSError when
    the move fails; nothing has moved then.
    """
    src = snapshot_dir(verification)
    if not src.is_dir() or not any(src.iterdir()):
        return None
    keep = verification.dir / "old" / when
    keep.mkdir(parents=True, exist_ok=True)
    dest = keep / CHART_SUBDIR
    n = 2
    while dest.exists():
        dest = keep / f"{CHART_SUBDIR}_{n}"
        n += 1
    shutil.move(str(src), str(dest))
    log.info("verification %s: the stored chart it replaces is kept in %s",
             verification.id, dest)
    return dest


def put_back_stored_chart(verification: Verification,
                          set_aside: Path) -> bool:
    """Undo :func:`set_aside_stored_chart` for a session that filed nothing:
    the chart copied in for it goes, and the chart the date's measurement was
    made with is its stored chart again. Returns True when that is so.

    The copy that goes is a copy of the live verification chart, which is
    still there; the chart that comes back is the only copy of itself, so it
    is moved back before anything is removed, and a failure leaves it in
    ``old/`` (where it is safe) rather than nowhere.
    """
    if set_aside is None or not set_aside.is_dir():
        return False
    live = snapshot_dir(verification)
    stash = None
    try:
        if live.exists():
            stash = _fresh_stash(verification.dir / f".unused-{CHART_SUBDIR}")
            shutil.move(str(live), str(stash))
        try:
            shutil.move(str(set_aside), str(live))
        except OSError:
            if stash is not None and not live.exists():
                shutil.move(str(stash), str(live))
            raise
    except OSError as exc:
        log.warning("verification %s: could not put the stored chart back; "
                    "it is kept in %s: %s", verification.id, set_aside, exc)
        return False
    if stash is not None:
        shutil.rmtree(stash, ignore_errors=True)
    # The dated folder the set-aside made, and old/ itself, when nothing else
    # has been kept there since.
    for d in (set_aside.parent, set_aside.parent.parent):
        try:
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
        except OSError:
            pass
    log.info("verification %s: nothing was filed, so the stored chart it "
             "was measured with is back in %s", verification.id, live)
    return True


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
    """The digest of what defines the chart in *path* (:func:`chart_content`),
    so a measurement-derived ``.cht`` EXPECTED block is never "a different
    chart"."""
    h = hashlib.sha256()
    h.update(chart_content(path))
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
    from workflow.chart_slot import defines_the_chart
    for s in snap:
        # Side files (the settings meta.json) travel with the chart but do
        # not decide whether the chart changed — otherwise every settings
        # edit would make every dated check look like "a different chart"
        # (the same rule slot_live_differs already follows). Nor does the
        # print record: Knut printed run5's verification chart again, started
        # a fresh measurement and was told "Stored chart differs" because the
        # record's `printed_at` had moved (4.3.3). See `print_record_differs`
        # for what Start does with a record that has changed.
        if not defines_the_chart(s):
            continue
        want = _restored_name(s.name, snap_stem, run.verify_stem)
        counterpart = live.get(want)
        if counterpart is None or _digest(counterpart) != _digest(s):
            return True
    return False


def print_record_differs(verification: Verification) -> bool:
    """Whether the date's stored print record is not the live one.

    Not a different chart (:func:`workflow.chart_slot.defines_the_chart`):
    the same chart printed again. Start uses it to keep the record of the
    sheet the date's earlier measurement was made from beside that
    measurement in ``old/<stamp>/``, without asking anything, because the
    snapshot about to be taken carries the new record. False when the date has
    no stored chart, or neither side has a record.
    """
    from workflow.chart_slot import PRINT_RECORD_SUFFIX
    snap = snapshot_files(verification)
    if not snap:
        return False
    run = verification.run
    snap_stem = _snapshot_stem(snap)
    stored = {_restored_name(p.name, snap_stem, run.verify_stem): p
              for p in snap if p.name.lower().endswith(PRINT_RECORD_SUFFIX)}
    live = {p.name: p for p in live_chart_files(run)
            if p.name.lower().endswith(PRINT_RECORD_SUFFIX)}
    if set(stored) != set(live):
        return True
    try:
        return any(stored[n].read_bytes() != live[n].read_bytes()
                   for n in stored)
    except OSError:
        return True


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
    # The run's scanner `.cht` page(s), by name: kept because they agree with
    # the restored chart, or archived into old/ and removed because they do
    # not (Knut, #182 5958921500; see `restore_cht_plan`).
    cht_kept: "list[str]" = field(default_factory=list)
    cht_removed: "list[str]" = field(default_factory=list)
    # Where the replaced chart was archived (page images apart), Knut #182
    # 5959825756; None when nothing was replaced.
    archive: "Path | None" = None

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
    side_moved: "dict[Path, Path]" = {}
    stash = _fresh_stash(verification.dir / f".restore-stash-{verification.id}")
    snap_stem = _snapshot_stem(snap)

    try:
        if side_replaced:
            side_archive = run.archive_to_old(
                side_replaced, into=run.verifications_old_dir,
                moved=side_moved)
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
        _undo_side_archive(side_moved, vdir)
        result.restored = []
        result.rolled_back = True
        result.error = str(exc)
    finally:
        _keep_stash = False
        if not result.rolled_back:
            try:
                result.archive = _archive_replaced_chart(
                    stash,
                    lambda ps: run.archive_to_old(
                        ps, into=run.verifications_old_dir),
                    side_archive)
            except OSError as exc:     # noqa: BLE001 — never lose the stash
                log.error("could not archive the replaced chart; it is kept "
                          "at %s: %s", stash, exc)
                _keep_stash = True
        if not _keep_stash:
            shutil.rmtree(stash, ignore_errors=True)

    if result.ok:
        log.info("verification %s: restored %d chart file(s)%s",
                 verification.id, len(result.restored),
                 " (pages need rebuilding)" if result.needs_regeneration else "")
    return result
