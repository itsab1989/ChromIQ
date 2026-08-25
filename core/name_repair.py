"""Repair of file stems truncated by the pre-4.1.3-beta.16 layout-engine bug.

WHAT WENT WRONG
    `workflow/layout_engine/chart.py` derived every artefact name with
    ``Path(out_base).with_suffix("")`` on a value that is a *stem*, not a
    filename. A project called ``X-A4-484p-w10.0mm`` has no extension, but
    pathlib reads ``.0mm`` as one, so the ``.ti2``, the page TIFFs and
    ``.strips.json`` were written as ``X-A4-484p-w10.*`` while the ``.ti1`` —
    written by ``core.file_manager.Run``, which concatenates — kept the whole
    name. The run could then not be measured at all.

WHAT THIS DOES
    Renames those files back to the name the rest of ChromIQ looks for. Nothing
    is copied, nothing is deleted, nothing is rewritten, and no file is ever
    touched unless its name is on a whitelist built from the project's own name.

WHY IT CANNOT TOUCH THE WRONG FILE — the three gates, in order

    1. ``<full>.ti1`` must exist.  ``Run.chart_ti1`` is the one artefact the
       buggy code never produced, because ``Run`` builds it by concatenation.
       Its presence proves this folder belongs to a full-named project chart.
       It is also what makes a hand-renamed project safe: rename the folder and
       ``<full>.ti1`` stops existing, so nothing is repaired.
    2. ``<full>.ti2`` must NOT exist.  If it does, the chart is fine and there
       is nothing to repair — whatever else is in the folder is somebody's.
    3. ``<trunc>.strips.json`` must exist.  **This is the bug's fingerprint.**
       ``.strips.json`` is written by exactly one function in ChromIQ
       (``layout_engine.chart.build_chart``) and by no version of ArgyllCMS or
       any other tool; the FIXED build writes it under the FULL name. A
       truncated one can therefore only have been produced by the broken build.

    Gates 1-3 are evaluated ONCE per folder, on the whole folder. An interrupted
    repair is finished from the journal (below), not by re-running detection with
    a weaker gate — which is how a per-file gate would have to work, and a
    per-file gate is a per-file chance to be wrong.

THE WHITELIST IS EXACT NAMES, NEVER A GLOB
    ``<trunc>`` is a *prefix* of ``<full>``, so a glob of ``<trunc>*`` matches
    the correctly-named files as well — ``X-w10*`` matches ``X-w10.0mm.ti1``.
    Any prefix-glob implementation of this repair renames the good files into
    garbage. The whitelist below is a closed set of literal names plus one
    anchored page-number pattern, and a file whose name starts with ``<full>``
    is refused outright as a second line of defence.

THE JOURNAL
    Every planned move is written to ``<project>/name-repair.json`` BEFORE the
    first rename. If the journal cannot be written, nothing is renamed — a move
    ChromIQ cannot record is a move it does not make. The journal carries the
    ChromIQ version, the timestamp, every ``from``/``to`` pair, each entry's
    outcome, and a plain-sentence note saying how to undo it by hand.

MODES  (``CHROMIQ_NAME_REPAIR``)
    ``on``   — default; repair and journal.
    ``dry``  — log exactly what would be renamed and change nothing on disk.
    ``off``  — do nothing at all. The kill switch, so a fault in the field can
               be stopped without shipping a build.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

from core.logger import get_logger

log = get_logger(__name__)

__all__ = ["plan_for_folder", "repair_project", "JOURNAL_NAME", "mode"]

JOURNAL_NAME = "name-repair.json"
_ENV = "CHROMIQ_NAME_REPAIR"

#: The complete set of extensions the broken engine ever wrote under a
#: truncated stem. `.cht` is deliberately ABSENT: the engine writes no .cht at
#: build time (workflow/chart_creator.py:1167 — "No .cht at build time"), and
#: the .cht/.cie pair that workflow/scanin_target.py writes is a SEPARATE,
#: still-open bug whose damage costs one button press to redo, not a reprint.
#: Adding an extension here widens what may be renamed; do not do it without
#: a fingerprint as strong as `.strips.json`.
_EXACT_EXTS = (".ti2", ".strips.json", ".pdf", ".tif", ".tiff")
#: `<trunc>_01.tif` … the page images of a multi-page chart.
_PAGE_EXTS = ("tif", "tiff")


def mode() -> str:
    """``"on"`` (default), ``"dry"`` or ``"off"`` — from ``CHROMIQ_NAME_REPAIR``."""
    v = (os.environ.get(_ENV) or "on").strip().lower()
    return v if v in ("on", "dry", "off") else "on"


def _truncation_of(full: str) -> str | None:
    """Exactly what the old code would have produced for this stem, or None.

    Uses ``Path(full).stem`` because that is literally the operation the bug
    performed (``with_suffix("")``). It is not a general "strip the extension"
    helper and must never become one.
    """
    if not full or full.startswith("."):
        return None                      # a dotfile-looking name has no suffix
    trunc = Path(full).stem
    if not trunc or trunc == full:
        return None                      # no dot in the name → bug impossible
    # The bug can only split `full` at a dot. Anything else means our idea of
    # the name is wrong, and we stop rather than guess.
    if not (full.startswith(trunc) and full[len(trunc):].startswith(".")):
        return None
    return trunc


def plan_for_folder(folder: Path, full: str) -> list[tuple[Path, Path]]:
    """The exact renames for one folder, or ``[]``. Reads only; never writes."""
    trunc = _truncation_of(full)
    if trunc is None or not folder.is_dir():
        return []
    # --- the three gates, on the folder as a whole -------------------------
    if not (folder / f"{full}.ti1").is_file():
        return []
    if (folder / f"{full}.ti2").exists():
        return []
    if not (folder / f"{trunc}.strips.json").is_file():
        return []
    # --- the hard whitelist ------------------------------------------------
    exact = {f"{trunc}{e}" for e in _EXACT_EXTS}
    page = re.compile(rf"^{re.escape(trunc)}_\d{{2,4}}\.(?:{'|'.join(_PAGE_EXTS)})$",
                      re.IGNORECASE)
    moves: list[tuple[Path, Path]] = []
    for src in sorted(folder.iterdir()):
        if not src.is_file() or src.is_symlink():
            continue
        n = src.name
        if n.startswith(full):
            continue        # a correctly-named file. Belt and braces: the
                            # whitelist cannot contain one, and this makes it
                            # impossible for a future edit to make it contain one.
        if n not in exact and not page.fullmatch(n):
            continue
        dst = folder / (full + n[len(trunc):])
        if dst.name == n or len(dst.name) <= len(n):
            log.warning("name repair: refusing a non-lengthening rename %s", src)
            continue        # unreachable by construction; a tripwire, not logic
        if dst.exists():
            # Something is already called what this file would be called. The
            # run is therefore not broken in the way this repair fixes, and the
            # user put one of the two files there. Never overwrite, never move
            # anything aside — say so and leave both alone.
            log.warning("name repair: %s already exists — leaving %s alone",
                        dst.name, src.name)
            continue
        moves.append((src, dst))
    return moves


def _folders(project) -> list[tuple[Path, str]]:
    """``(folder, full_stem)`` for every place the engine ever wrote a chart.

    Only ``runs/run*/`` and ``cal/``, only their DIRECT children — never a
    recursive walk, so a project nested inside another cannot be entered.
    The calibration stem is ``<name>-cal``, whose truncation is NOT the same
    as the project's (``Path("X-w10.0mm-cal").stem == "X-w10"``), which is why
    each folder carries its own stem rather than sharing the project's.
    """
    out: list[tuple[Path, str]] = []
    runs_root = project.runs_root
    if runs_root.is_dir():
        for d in sorted(runs_root.glob("run*")):
            if d.is_dir() and not (d / "project.json").exists():
                out.append((d, d.parents[1].name))
    cal = project.calibration
    if cal.dir.is_dir():
        out.append((cal.dir, cal.stem))
    return out


def _journal_path(root: Path) -> Path:
    return Path(root) / JOURNAL_NAME


def _load_journal(path: Path) -> dict | None:
    try:
        if path.is_file():
            d = json.loads(path.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else None
    except Exception as exc:            # noqa: BLE001 — never block a load
        log.warning("name repair: unreadable journal %s: %s", path, exc)
    return None


def _write_journal(path: Path, data: dict) -> bool:
    """True if written. A move ChromIQ cannot record is a move it does not make."""
    try:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        return True
    except OSError as exc:
        log.warning("name repair: cannot write %s (%s) — nothing will be "
                    "renamed in this project", path, exc)
        return False


def _apply(entries: list[dict], root: Path) -> tuple[int, int]:
    """Perform the moves an entry list still marks ``planned``. Returns
    (done, failed). One failure never stops the others — the journal records
    each outcome, so a run interrupted anywhere is finished on the next open."""
    done = failed = 0
    for e in entries:
        if e.get("state") == "done":
            continue
        src, dst = root / e["from"], root / e["to"]
        if dst.exists():
            e["state"] = "skipped-destination-exists"
            log.warning("name repair: %s already exists, skipping", dst)
            continue
        if not src.is_file():
            e["state"] = "skipped-source-gone"
            continue
        try:
            src.rename(dst)
            e["state"] = "done"
            done += 1
            log.info("name repair: %s -> %s", e["from"], e["to"])
        except OSError as exc:
            e["state"] = f"failed: {exc.__class__.__name__}"
            failed += 1
            log.warning("name repair: could not rename %s: %s", src, exc)
    return done, failed


def repair_project(project, *, app_version: str = "") -> int:
    """Repair one project. Returns the number of files renamed (0 in dry mode).

    Never raises: a project must open whatever the filesystem says.
    """
    try:
        return _repair_project(project, app_version)
    except Exception as exc:            # noqa: BLE001 — opening must not fail
        log.warning("name repair: aborted on %s: %s", project.root, exc,
                    exc_info=True)
        return 0


def _plan(project) -> list[dict]:
    """Every whitelisted rename this project needs right now, as journal rows."""
    root = Path(project.root)
    out: list[dict] = []
    for folder, full in _folders(project):
        for src, dst in plan_for_folder(folder, full):
            out.append({"from": str(src.relative_to(root)),
                        "to": str(dst.relative_to(root)),
                        "state": "planned"})
    return out


def _repair_project(project, app_version: str) -> int:
    m = mode()
    if m == "off":
        return 0
    root = Path(project.root)
    # THE COMMON CASE COSTS TWO STRING OPERATIONS AND NO SYSCALL.
    # `Project.load` runs on every target switch (FileManager.project() caches,
    # but `set_target_name` invalidates the cache — measured: 3 loads for 4
    # switches), so this must not stat anything for a project that cannot be
    # affected. A name with no dot cannot produce a truncation, and neither can
    # `<name>-cal` derived from it; both are checked because the calibration
    # stem is not the project name.
    if (_truncation_of(root.name) is None
            and _truncation_of(f"{root.name}-cal") is None):
        return 0
    jp = _journal_path(root)
    doc = _load_journal(jp) or {}
    # The journal is a LIST of repair sessions, never one session overwritten.
    # An undo record that a later repair can erase is not an undo record.
    sessions = doc.get("repairs")
    if not isinstance(sessions, list):
        sessions = []

    # --- 1. finish anything an earlier session left unfinished --------------
    pending = [s for s in sessions
               if isinstance(s, dict) and s.get("state") != "complete"]
    # --- 2. and look for work nobody has planned yet ------------------------
    #     Three stat() calls per folder decide this; `iterdir` only runs when
    #     all three gates pass. Deliberately NOT short-circuited on
    #     "the journal says complete": a user who restores an old backup into a
    #     repaired project gets repaired again, and gets a second record.
    already = {e["from"] for s in sessions for e in s.get("moves", [])
               if isinstance(e, dict) and e.get("state") == "planned"}
    fresh = [e for e in _plan(project) if e["from"] not in already]

    if not pending and not fresh:
        return 0

    if m == "dry":
        for s in pending:
            for e in s.get("moves", []):
                if e.get("state") != "done":
                    log.info("name repair [DRY]: would resume %s -> %s",
                             e.get("from"), e.get("to"))
        for e in fresh:
            log.info("name repair [DRY]: would rename %s -> %s",
                     e["from"], e["to"])
        log.info("name repair [DRY]: %d file(s) in %s — nothing changed",
                 sum(1 for s in pending
                     for e in s.get("moves", []) if e.get("state") != "done")
                 + len(fresh), root)
        return 0

    if fresh:
        sessions.append({
            "what": "ChromIQ renamed these files back to the project's full "
                    "name. A version before 4.1.3 wrote them under a shortened "
                    "name, so the app could not find the chart. Nothing was "
                    "deleted and no file content was changed — only renamed.",
            "how_to_undo": "Rename each file below from its 'to' name back to "
                           "its 'from' name. Paths are relative to this folder.",
            "chromiq_version": app_version,
            "started": datetime.now().isoformat(timespec="seconds"),
            "state": "planned",
            "moves": fresh,
        })
    doc = {"repairs": sessions}
    # A move ChromIQ cannot record is a move it does not make.
    if not _write_journal(jp, doc):
        return 0

    done = failed = 0
    for s in sessions:
        if s.get("state") == "complete":
            continue
        d, f = _apply(s.get("moves", []), root)
        done += d
        failed += f
        s["state"] = "complete" if all(
            e.get("state") in ("done", "skipped-source-gone",
                               "skipped-destination-exists")
            for e in s.get("moves", [])) else "partial"
        s["finished"] = datetime.now().isoformat(timespec="seconds")
    _write_journal(jp, doc)
    log.info("name repair: renamed %d file(s) in %s (%d could not be renamed); "
             "record in %s", done, root, failed, jp.name)
    return done
