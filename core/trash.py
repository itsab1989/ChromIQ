"""Move a file or folder to the system Trash, instead of destroying it.

WHY THIS EXISTS. `shutil.rmtree` is not atomic: it removes everything it can
reach and raises only at the end, so one unwritable sub-folder is enough to
leave a project half-destroyed. Measured on 2026-08-28 through the real Delete
button, on a project with a single read-only `reports/` folder:

    rmtree RAISED  -> the app said "Nothing was changed."
       files before 6, files now 1    project.json still there: False

`project.json` was among the casualties, so the survivors could no longer be
opened by ChromIQ at all — and the person had just been told nothing happened.

A Trash move is a rename, not a recursive unlink, so the unwritable child never
gets the chance to defeat it. The same tree, the same read-only folder:

    moveToTrash -> ok=True  dest='~/.Trash/chromiq-f2-trash-xk1_mxlr'
       files before 6, left at the source 0    source folder still there: False
       recovered from the Trash: 6 files, project.json present: True

Basti ruled on 2026-08-28 that deleting moves to the Trash.

WHAT IT DOES NOT PROMISE. Qt returns False without touching anything when there
is nowhere to put the files — a read-only volume, a share with no trash, a
platform that cannot. Callers must treat False as "nothing happened", say so,
and never fall back to destroying the files instead: that would put back exactly
the behaviour this module exists to remove.

Nor does it free disk space. The files are still on the volume until the person
empties the Trash, which matters when they pressed Delete precisely because a
disk was full — so a window that reports success should say where the files went.
"""
from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


class TrashResult:
    """What happened, in a form a window can read out.

    ``ok`` — the files are in the Trash and gone from their old place.
    ``destination`` — where they landed, when the platform says so. Worth
    showing: on macOS a volume has its own Trash, so "in the Trash" alone can
    send someone looking in the wrong place.
    ``reason`` — a short, plain explanation when ``ok`` is False. Never Qt's own
    string: it is unhelpful to the point of comedy ("Unknown error: 3328").
    """

    __slots__ = ("ok", "destination", "reason")

    def __init__(self, ok: bool, destination: "Path | None" = None,
                 reason: str = "") -> None:
        self.ok = ok
        self.destination = destination
        self.reason = reason

    def __repr__(self) -> str:      # pragma: no cover — debugging aid
        return (f"TrashResult(ok={self.ok!r}, destination={self.destination!r}, "
                f"reason={self.reason!r})")


def move_to_trash(path: "Path | str") -> TrashResult:
    """Move *path* to the system Trash. Never raises, never partly succeeds.

    A missing path counts as success — the caller wanted it gone and it is.
    """
    p = Path(path)
    if not p.exists():
        return TrashResult(True)
    try:
        from PyQt6.QtCore import QFile
    except Exception as exc:        # noqa: BLE001 — a headless caller, a script
        log.warning("No Qt available to reach the Trash: %s", exc)
        return TrashResult(False, reason=_no_trash_reason())
    try:
        ok, dest = QFile.moveToTrash(str(p))
    except Exception as exc:        # noqa: BLE001 — never let this raise
        log.warning("Could not move %s to the Trash: %s", p, exc)
        return TrashResult(False, reason=_no_trash_reason())
    if ok and not p.exists():
        where = Path(dest) if dest else None
        log.info("Moved %s to the Trash%s", p, f" ({where})" if where else "")
        return TrashResult(True, where)
    if ok:
        # Qt said yes and the folder is still there. Treat it as a failure:
        # reporting success for files that never moved is the fault this whole
        # module exists to prevent.
        log.warning("The Trash reported success but %s is still there", p)
    return TrashResult(False, reason=_no_trash_reason())


def _no_trash_reason() -> str:
    from core.i18n import tr
    return tr(
        "ChromIQ could not move these files to the Trash, so nothing has been "
        "deleted and everything is still exactly where it was.\n\n"
        "This usually happens for one of two reasons: the files are on a disk "
        "or a network share that has no Trash of its own, or the folder they "
        "are in is read-only. Moving the project to a folder on your own disk, "
        "or asking whoever looks after the share to give you permission to "
        "write there, will let you delete it."
    )
