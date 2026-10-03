"""The one window about verifications from an earlier profile (#182, UMM §6f).

Knut's rulings, in order: 5964076758 (one window, no sound, the earlier
profile's reports go with it), 5964384250 Q1/Q2 (a rebuild archives the profile
only; "Make a new chart from current profile" also archives the old
verification runs; Cancel keeps them; an ordinary chart is kept), 5965626117
(an ordinary chart opens Create Chart too, so the user can confirm it and go
on to printing; "Keep" asks again after a restart).

**ONE TRIGGER.** The bar's ``(project, run type, profile run)`` choice changes
and the run type is Verification. The verification DATE is left out of the key
on purpose: Start Measurement sets it (``tab_measure`` before its bidir,
replace and CR30 questions), and a check keyed on it could open in the middle
of Start. A profile cannot change while Verification is selected (the Build
Profile tab is locked there, and the bar is locked during a build), so a
rebuild is always followed by this trigger.

**ONE CHECK AT A TIME.** Deferred to the next turn of the event loop and
coalesced: Load .ti2 changes the run type and the run in one go. While another
window is open it waits and asks when that window closes; while a measurement
or a build runs it is dropped until the next change of the key, which cannot
happen then because the bar is locked.

**WHAT IS REMEMBERED.** Only "Keep", per run, profile and profile time, for
this session. After "Archive" nothing needs remembering: the dates are gone,
and a stale FROM PROFILE GAMUT chart left behind (the user did not press
Generate Chart) is rightly asked about again.

The decision is ``workflow/verification_profile_match.py``; this file asks and
moves. Nothing is deleted: every move goes through ``Run.archive_to_old`` into
``verifications/old/<timestamp>/``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from PyQt6.QtCore import QObject, QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox, QWidget

from core.i18n import tr
from core.logger import get_logger

log = get_logger(__name__)

#: How often a check held back by an open window looks again, in ms.
WAIT_FOR_WINDOW_MS = 250

ARCHIVE = "archive"
KEEP = "keep"


class EarlierProfileOffer(QObject):
    """Asks, once per choice of Verification, about what an earlier profile
    left in the selected run, and does what the user picks."""

    def __init__(self, controller, parent: QWidget, *,
                 busy: "Callable[[], bool]",
                 open_create_chart: "Callable[[bool], None]",
                 log_line: "Callable[[str], None]",
                 refresh: "Callable[[], None] | None" = None) -> None:
        super().__init__(parent)
        self._ctl = controller
        self._parent = parent
        self._busy = busy
        self._open_create_chart = open_create_chart
        self._log_line = log_line
        self._refresh = refresh
        self._last_key: "tuple | None" = None
        self._queued = False
        #: (run dir, profile file name, profile time) answered "Keep".
        self._kept: "set[tuple]" = set()
        self._soon = QTimer(self)
        self._soon.setSingleShot(True)
        self._soon.setInterval(0)
        self._soon.timeout.connect(self._check)
        self._wait = QTimer(self)
        self._wait.setSingleShot(True)
        self._wait.setInterval(WAIT_FOR_WINDOW_MS)
        self._wait.timeout.connect(self._check)
        # A BOUND METHOD, never a self-capturing lambda (CLAUDE.md).
        controller.changed.connect(self._on_target_changed)

    # ---- the trigger ------------------------------------------------------
    def _key(self) -> tuple:
        t = self._ctl.target
        proj = None
        try:
            proj = self._ctl.project_or_none()
        except Exception:      # noqa: BLE001
            proj = None
        root = str(getattr(proj, "root", "") or "") if proj is not None else ""
        return (root, t.run_type, t.profile_run)

    def _on_target_changed(self) -> None:
        key = self._key()
        if key == self._last_key:
            return
        self._last_key = key
        try:
            if not self._ctl.target.is_verification():
                return
        except Exception:      # noqa: BLE001
            return
        self._queue()

    def _queue(self) -> None:
        if self._queued:
            return
        self._queued = True
        self._wait.stop()
        self._soon.start()

    # ---- the check --------------------------------------------------------
    def _check(self) -> None:
        self._queued = False
        try:
            if not self._ctl.target.is_verification():
                return
            if self._busy():
                # Dropped, not held: the bar is locked while measuring or
                # building, so the next change of the key is a new choice.
                return
            if QApplication.activeModalWidget() is not None:
                # ANOTHER WINDOW IS OPEN: ask when it closes, never on top.
                self._wait.start()
                return
            run = self._ctl.selected_run()
            if run is None:
                return
            from workflow.verification_profile_match import (
                earlier_profile_items)
            items = earlier_profile_items(run)
            if not items.variant:
                return
            key = (str(run.dir), run.built_profile_icc().name,
                   items.profile_when)
            if key in self._kept:
                return
        except Exception:      # noqa: BLE001 — a question is never worth a crash
            log.warning("could not check for verifications from an earlier "
                        "profile", exc_info=True)
            return
        answer = self._ask(items)
        if answer == KEEP:
            self._kept.add(key)
            log.info("Verifications from an earlier profile kept in %s "
                     "(asked again after a restart)", run.dir)
            return
        self._carry_out(run, items)

    # ---- the window -------------------------------------------------------
    def _message(self, items) -> "tuple[str, str, str, str]":
        """(title, body, main button, keep button) for *items*."""
        from workflow import measurement_messages as M
        from workflow.profile_rebuild_guard import readable_date

        when = items.profile_when.strftime("%Y-%m-%d %H:%M")
        n = len(items.dates)
        if items.variant == "C":
            title, body = M.M_VERIFY_CHART_EARLIER_PROFILE.render(
                profile_when=when)
            return title, body, tr(M.M_EARLIER_NEW_CHART), tr(M.M_EARLIER_KEEP_ONE)
        if items.variant == "A":
            msg = M.M_VERIFY_EARLIER_PROFILE
        elif items.has_chart:
            msg = M.M_VERIFY_EARLIER_PROFILE_KEEP_CHART
        else:
            # No chart at all: B's "the chart can still be used" is untrue.
            msg = M.M_VERIFY_EARLIER_PROFILE_NO_CHART
        title, body = msg.render(n=n, date=readable_date(items.dates[0]),
                                 profile_when=when)
        if items.variant == "A":
            main = (M.M_EARLIER_ARCHIVE_NEW_CHART_ONE if n == 1
                    else M.M_EARLIER_ARCHIVE_NEW_CHART)
        else:
            main = M.M_EARLIER_ARCHIVE_ONE if n == 1 else M.M_EARLIER_ARCHIVE
        keep = M.M_EARLIER_KEEP_ONE if n == 1 else M.M_EARLIER_KEEP
        return title, body, tr(main), tr(keep)

    def _ask(self, items) -> str:
        """ARCHIVE or KEEP. No sound (Knut, 5964076758 Q5). Escape and the
        close button mean Keep; the first button is the default."""
        from ui.widgets import fit_message_box_buttons

        title, body, main_label, keep_label = self._message(items)
        box = QMessageBox(self._parent)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle(title)
        box.setText(title)
        box.setInformativeText(body)
        main = box.addButton(main_label, QMessageBox.ButtonRole.AcceptRole)
        keep = box.addButton(keep_label, QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(main)
        box.setEscapeButton(keep)
        fit_message_box_buttons(box)
        self._exec(box)
        return ARCHIVE if box.clickedButton() is main else KEEP

    def _exec(self, box) -> None:
        """The one place the window blocks; a test answers it here."""
        box.exec()

    # ---- the answer -------------------------------------------------------
    def _carry_out(self, run, items) -> None:
        """Move what the window named, then open Create Chart (all three
        variants; on FROM PROFILE GAMUT for A and C)."""
        from workflow import measurement_messages as M

        line = ""
        if items.dates:
            when = datetime.now()
            paths = [run.verification(vid).dir for vid in items.dates]
            paths += list(items.documents)
            moved: dict = {}
            try:
                dest = run.archive_to_old(paths, when,
                                          into=run.verifications_old_dir,
                                          moved=moved)
                title, body = M.M_VERIFY_EARLIER_ARCHIVED_HERE.render(
                    n=len(items.dates), folder=dest)
                line = f"{title}\n{body}"
                log.info("Verifications from an earlier profile moved to %s",
                         dest)
            except Exception as exc:      # noqa: BLE001 — never undone
                folder = (next(iter(moved.values())).parent if moved
                          else run.verifications_old_dir)
                line = tr(M.M_EARLIER_NOT_ALL_MOVED).format(
                    error=exc, folder=folder)
                log.warning("Not everything from the earlier profile moved: "
                            "%s", exc)
        gamut = items.variant in ("A", "C")
        try:
            # The dated pick named a folder that may just have moved.
            self._ctl.set_verification_id("")
            self._open_create_chart(gamut)
            self._ctl.notify_changed()
            if self._refresh is not None:
                self._refresh()
        except Exception:      # noqa: BLE001
            log.warning("could not refresh after archiving", exc_info=True)
        if line:
            self._log_line(line)
