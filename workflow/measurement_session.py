"""Protecting the measurement a session starts from, and judging what it left.

The behaviour half of *Unified Measurement Management* §2a and §3b — see
``docs/design/unified_measurement_management.md``. Still free of Qt: it copies
files and returns findings, so the UI's only job is to show the message this
names.

**Why a copy at the start rather than a rescue at the end.** ArgyllCMS
``chartread`` writes its ``.ti3`` only on a clean exit (§0), and a resume writes
over the file it is resuming from. So by the time anything has gone wrong the
evidence is already gone: there is nothing on disk to compare against and
nothing to put back. Knut settled the policy (#130, 2026-08-03) — *"archiving
the ti3 at every session start is the safest option, yes"* — and it is what
makes §3b's C₀ → C comparison possible at all.

The copy costs a few kilobytes and is never deleted.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.logger import get_logger
from workflow.measurement_state import (SessionVerdict, Ti3State,
                                        added_by_session, classify,
                                        judge_session)

log = get_logger(__name__)


@dataclass
class SessionOutcome:
    """What a session did, and what to tell the user — §3b, §S3."""

    verdict: SessionVerdict
    before: int
    after: int
    restored: bool = False
    removed: bool = False
    archive: "Path | None" = None
    kept_beside: "Path | None" = None

    @property
    def added(self) -> int:
        return added_by_session(self.before, self.after)

    @property
    def message_id(self) -> "str | None":
        """Which message of the §M catalogue this outcome calls for."""
        return {
            SessionVerdict.DELETE_AND_RESTORE: "M-TI3-EMPTY",
            SessionVerdict.RESTORE_AND_KEEP_BOTH: "M-TI3-SHRANK",
        }.get(self.verdict)


class MeasurementSession:
    """One measuring session, from the copy taken before it to the verdict after.

    Deliberately not a context manager: a measurement ends in a dozen different
    ways (§1), several of them not on the code path that started it, so
    :meth:`finish` is called from wherever the end actually happens.
    """

    def __init__(self, ti3_path: Path, ti2_path: "Path | None" = None,
                 old_dir: "Path | None" = None) -> None:
        self.ti3_path = Path(ti3_path)
        self.ti2_path = Path(ti2_path) if ti2_path else None
        #: Where the pre-session copy goes. Defaults beside the measurement so
        #: this works for a plain folder as well as a project run.
        self.old_dir = Path(old_dir) if old_dir else self.ti3_path.parent / "old"
        self.before: int = 0
        self.archive: "Path | None" = None

    # ---- before ------------------------------------------------------
    def begin(self, when: "datetime | None" = None) -> "Path | None":
        """Record C₀ and copy the existing measurement aside. Returns the copy.

        Copied, not moved: the session may be a resume, which reads the live
        file. Missing or unreadable files are simply nothing to protect.
        """
        facts = classify(self.ti3_path, self.ti2_path)
        self.before = facts.held or 0
        if not self.ti3_path.is_file():
            return None
        when = when or datetime.now()
        dest = self.old_dir / when.strftime("%Y-%m-%d_%H%M%S")
        try:
            dest.mkdir(parents=True, exist_ok=True)
            target = dest / self.ti3_path.name
            n = 1
            while target.exists():
                target = dest / f"{self.ti3_path.stem}_{n}{self.ti3_path.suffix}"
                n += 1
            shutil.copy2(self.ti3_path, target)
        except OSError:
            # A measurement must never be blocked by a failure to protect it —
            # but say so, because the safety net is then not there.
            log.warning("could not archive %s before measuring",
                        self.ti3_path.name, exc_info=True)
            return None
        self.archive = target
        log.info("archived %s (%d readings) to %s before measuring",
                 self.ti3_path.name, self.before, dest.name)
        return target

    # ---- after -------------------------------------------------------
    def finish(self, *, resumed: bool) -> SessionOutcome:
        """Judge what the session left behind and act on it — §3b, §S3.

        At most one of the outcomes applies, which is what keeps §S3 to a single
        window after a measurement.
        """
        facts = classify(self.ti3_path, self.ti2_path)
        after = facts.held or 0
        verdict = judge_session(self.before, after, resumed=resumed)
        out = SessionOutcome(verdict=verdict, before=self.before, after=after,
                             archive=self.archive)

        if verdict is SessionVerdict.DELETE_AND_RESTORE:
            out.removed = self._set_aside_empty()
            out.restored = self._restore()
        elif verdict is SessionVerdict.RESTORE_AND_KEEP_BOTH:
            out.kept_beside = self._keep_beside()
            out.restored = self._restore()
        return out

    # ---- the file moves themselves -----------------------------------
    def _set_aside_empty(self) -> bool:
        """Move a measurement that holds nothing out of the way.

        Not deleted even though it is empty: it is still evidence of what
        happened, and the rule is that ChromIQ never deletes a file it did not
        create in that same breath.
        """
        if not self.ti3_path.is_file():
            return False
        try:
            dest = (self.archive.parent if self.archive
                    else self.old_dir / datetime.now().strftime("%Y-%m-%d_%H%M%S"))
            dest.mkdir(parents=True, exist_ok=True)
            shutil.move(str(self.ti3_path), str(dest / f"empty-{self.ti3_path.name}"))
            return True
        except OSError:
            log.warning("could not set aside the empty measurement",
                        exc_info=True)
            return False

    def _keep_beside(self) -> "Path | None":
        """Keep a session's own file when its readings went backwards.

        Both files are kept because we do not know which is the good one — the
        specification is explicit that ChromIQ can see the numbers disagree and
        cannot see why.
        """
        if not self.ti3_path.is_file():
            return None
        try:
            dest = (self.archive.parent if self.archive
                    else self.old_dir / datetime.now().strftime("%Y-%m-%d_%H%M%S"))
            dest.mkdir(parents=True, exist_ok=True)
            target = dest / f"shorter-{self.ti3_path.name}"
            shutil.move(str(self.ti3_path), str(target))
            return target
        except OSError:
            log.warning("could not keep the shorter measurement", exc_info=True)
            return None

    def _restore(self) -> bool:
        if self.archive is None or not Path(self.archive).is_file():
            return False
        try:
            shutil.copy2(self.archive, self.ti3_path)
            log.info("restored %s from %s", self.ti3_path.name,
                     Path(self.archive).parent.name)
            return True
        except OSError:
            log.warning("could not restore the archived measurement",
                        exc_info=True)
            return False
