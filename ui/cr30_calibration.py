"""The CR30's calibration, dark-reference and tile-learning windows — once.

These windows were written inside ``ui/tabs/tab_measure.py`` because the Measure
tab was the only place that opened a CR30. Tools ▸ *Read single patches* is the
second, and two copies of a calibration window is how two windows come to
disagree: the wording, the button order, the escape-key rule, the "cap the right
way round" warning and the magnet-guard learning step all had to be argued for
once, several of them twice.

So they moved here **unchanged**, as a mixin. Nothing about them was rewritten
on the way: ``inspect.getsource(TabMeasure._calibrate_and_confirm)`` returns the
same text it did before, because an inherited method is the same function
object — which is also how the eight test files that read these methods' source
keep passing without being touched.

**What a host has to provide**, and every one of them already existed on the
Measure tab:

===========================  ====================================================
``_log``                     a ``QPlainTextEdit``-shaped sink: ``appendPlainText``
                             and ``ensureCursorVisible``
``_start_btn`` ``_stop_btn`` the two buttons held across the calibration, so a
                             nested event loop cannot re-enter the start
``_flash_status(text, …)``   a transient on-screen line
``_sound``                   ``core.sound``-shaped; ``play(PATCH_OK)``
``_start_button_name()``     what the start button is called, for the log notes
``_open_cr30_bridge()``      stand up this host's reader (and bridge, if it has
``_close_cr30_bridge()``     one) — ``_cr30_reader`` must be set by the first
``_cr30_reader``             the :class:`DeviceReader` those two manage
``_show_cr30_measuring_window()``  the "how to measure" window, which is the ONE
                             thing that legitimately differs: the Measure tab
                             describes a highlighted patch on a chart and the
                             spot window has no chart
===========================  ====================================================
"""
from __future__ import annotations

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication, QCheckBox

from core.i18n import tr
from core.logger import get_logger

log = get_logger(__name__)

#: The Measure tab's accent, which the tile-learning window's live line wears.
#: Kept as the same literal rather than imported from ``ui.tabs.tab_measure``:
#: this module must not import the tab, or the tab could not import it.
_TAB_COLOR = "#56d6a5"

#: Mean reflectance above which a dark reference is reported as suspect.
_CR30_ZERO_WARN = 0.05


class Cr30CalibrationMixin:
    """The CR30 calibration windows, for any host that satisfies the protocol
    in this module's docstring."""

    def _run_cr30_calibration(self, *, keep_bridge: bool = False) -> bool:
        """The calibration window. True to go on measuring, False to stop.

        `keep_bridge` is for the one caller that runs this DURING a session —
        the magnet remedy. See :meth:`_calibrate_and_confirm`.

        M-CR30-CALIBRATE (§M-PROPOSED). The instrument's owner ruled on
        2026-08-28 that ChromIQ triggers the calibration itself rather than
        asking the user to press the instrument's button, on BOTH transports —
        EXP-MEAS-004 proved the host trigger over USB and EXP-BLE-012 over
        Bluetooth, the second only after he pushed back on a "not known to be
        possible" that had never actually been tested.

        The reading it takes is NOT a measurement of anything: the helper has
        not started, so there is no prompt outstanding and nowhere for a value
        to go. That is what makes his ruling "the calibration reading must not
        be counted as a measurement" free rather than something to enforce.
        """
        from PyQt6.QtCore import QThread
        from PyQt6.QtWidgets import QMessageBox
        from workflow import measurement_messages as M
        from ui.widgets import (fit_message_box_buttons,
                                order_message_box_buttons)

        # The bridge FIRST, and calibrate through its reader. A second device
        # handle would mean opening the instrument twice — and over Bluetooth
        # that is a disconnect and reconnect of a peripheral that accepts one
        # connection at a time. Standing the bridge up arms nothing: it does
        # nothing until the helper's first spot prompt reaches on_patch_ready,
        # and the helper has not been started yet.
        # Waiting for the calibration below uses processEvents, which is a
        # NESTED event loop, and Start is not disabled until much later in
        # _on_start. Traced on screen: the calibration began at 0.72 s and
        # Start was still clickable at 1.21 s, re-entering _on_start and
        # raising a second modal over the first. So the controls that could
        # start or stop a run are held for the whole of this, and restored on
        # every path out of it — including the failures.
        self._start_btn.setEnabled(False)
        stop_was = self._stop_btn.isEnabled()
        self._stop_btn.setEnabled(False)
        try:
            return self._calibrate_and_confirm(keep_bridge=keep_bridge)
        finally:
            self._start_btn.setEnabled(True)
            self._stop_btn.setEnabled(stop_was)

    def _calibrate_and_confirm(self, *, keep_bridge: bool = False) -> bool:
        """The calibration proper. Split out so its caller can hold Start and
        Stop across every path out of it.

        `keep_bridge` distinguishes the two callers, and getting it wrong made
        the magnet remedy a dead end:

        * A **Start** calibrates before there is a session. It must not inherit
          a previous run's bridge, so it drops whatever is held and opens a
          fresh one.
        * The **magnet remedy** calibrates in the MIDDLE of a live session. The
          bridge is the session — it holds the outstanding patch, the retry
          counts and the stopped flag that `resume_after_magnet` exists to
          clear. Rebuilding it there threw all of that away and closed the
          instrument mid-recovery, and the resume then ran against a brand-new
          bridge that had never been stopped: it returned True without arming
          anything, under a log line promising the operator the session had
          carried on. Nothing was listening. The remedy for his own incident
          led straight into the fault it was written to remove.
        """
        from PyQt6.QtCore import QThread
        from PyQt6.QtWidgets import QMessageBox
        from workflow import measurement_messages as M
        from ui.widgets import (fit_message_box_buttons,
                                order_message_box_buttons)

        if not keep_bridge:
            # A previous session's bridge must not be inherited: this is the
            # first thing a Start does with the instrument, so let go of
            # anything still held before opening. _open_cr30_bridge's own guard
            # then keeps the later call from rebuilding what this one stands up.
            self._close_cr30_bridge()
        self._open_cr30_bridge()
        reader = getattr(self, "_cr30_reader", None)
        if reader is None:
            return True      # no reader to calibrate with; the run says why

        from ui.cr30_pictograms import BLACK_STEP, WHITE_STEP, steps_pair

        title, body = M.M_CR30_CALIBRATE.render()
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setIconPixmap(steps_pair(WHITE_STEP, self))
        box.setWindowTitle(tr("Calibrate the instrument"))
        box.setText(title)
        box.setInformativeText(body)
        # PER USE, AND DELIBERATELY NOT REMEMBERED.
        #
        # The black calibration is needed rarely and asks for the opposite of
        # what the window above asks for, so a remembered tick would turn
        # "occasionally, on purpose" into a second window and a device write on
        # every Start of this target for ever. Unticked each time means the
        # second window only appears for the user who just asked for it — which
        # is also the honest answer to "would this be two pop-ups every time".
        also_black = QCheckBox(tr("Also take the black calibration afterwards"))
        box.setCheckBox(also_black)
        go = box.addButton(tr("Calibrate now"), QMessageBox.ButtonRole.AcceptRole)
        cancel = box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(go)
        fit_message_box_buttons(box)
        # BASTI'S RULE, 2026-08-30: *"cancel should always be on the right
        # side"* — the action first, the way out last. It reverses the macOS
        # default (which puts the confirming button rightmost), so it is set
        # explicitly here and in every sibling window rather than left to the
        # platform. See ui/widgets.order_message_box_buttons.
        order_message_box_buttons(box, [go, cancel])
        box.exec()
        if box.clickedButton() is not go:
            # Cancel, the red traffic light, the Windows X and Esc all land
            # here — `clickedButton()` is None for every one of them, so
            # "anything but Calibrate now" is the right test HERE, where the
            # safe answer and the dismissing answer are the same thing. (Its
            # sibling below, the black window, has a third option where they
            # are NOT, and reading a dismissal as "skip" was a real fault.)
            #
            # Say so. Cancelling was silent, and a window that vanishes leaving
            # no trace is indistinguishable from one that failed.
            self._log.appendPlainText("\n" + tr(
                "[STOPPED] You cancelled the calibration, so this measurement "
                "did not start. Nothing has been changed and nothing has been "
                "measured — your instrument still has the calibration it had "
                "before. Press “{start}” whenever you are ready to begin."
                ).format(start=self._start_button_name()))
            self._log.ensureCursorVisible()
            return False
        want_black = also_black.isChecked()

        # Off the GUI thread: the reader holds its lock for the whole call, and
        # a slot that waited on it would freeze the window it was opened from —
        # the same primitive that froze the app for three minutes on Stop.
        #
        result: dict = {}

        class _Worker(QObject):
            done = pyqtSignal()

            def __init__(self, black=False):
                super().__init__()
                self._black = black

            def run(self) -> None:
                try:
                    reader.calibrate(black=self._black)
                except Exception as exc:      # noqa: BLE001 — reported below
                    result["error"] = str(exc) or type(exc).__name__
                self.done.emit()

        def _run_calibration(black: bool) -> None:
            thread, worker = QThread(self), _Worker(black)
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.done.connect(thread.quit)
            thread.start()
            # Both must stay referenced until the thread has finished, or Qt
            # collects a running QThread and takes the process with it.
            self._cal_thread, self._cal_worker = thread, worker
            while not thread.isFinished():
                QApplication.processEvents()
                thread.wait(20)
            self._cal_thread = self._cal_worker = None

        _run_calibration(black=False)

        if "error" in result:
            self._log.appendPlainText("\n" + tr(
                "The instrument could not be calibrated: {error}"
                ).format(error=self._plain_instrument_error(result["error"])))
            self._log.ensureCursorVisible()
            again = QMessageBox(self)
            again.setIcon(QMessageBox.Icon.NoIcon)
            again.setWindowTitle(tr("Calibrate the instrument"))
            again.setText(tr("The calibration did not go through."))
            # The same distinction the black step makes: bleak's own sentences
            # explain nothing to a user, and "switched on and still connected"
            # is the right advice for a lost link but not for a refusal.
            why = self._plain_instrument_error(result["error"])
            again.setInformativeText(tr(
                "ChromIQ asked your CR30 to calibrate and it did not answer.\n\n"
                "Check that the instrument is switched on and still connected "
                "— over Bluetooth, pressing its own button once wakes it — "
                "then start the measurement again.\n\n"
                "Nothing has been changed, and any measurement this run "
                "already had is untouched.\n\n"
                "What went wrong: {error}").format(error=why))
            again.setStandardButtons(QMessageBox.StandardButton.Ok)
            fit_message_box_buttons(again)
            again.exec()
            return False

        self._log.appendPlainText("\n" + tr(
            "[NOTE] ChromIQ asked the CR30 to take its white calibration. It "
            "cannot check the result — the instrument reports the same value "
            "whatever is under the cap."))
        # SAY WHICH WAY IT CONNECTED — AND SAY IT LAST.
        #
        # ChromIQ picks USB or Bluetooth by itself and has never said which it
        # chose, so a user who wants wireless cannot tell whether they got it,
        # and a user CERTAIN they unplugged the cable cannot show it afterwards.
        #
        # It is written after the calibration note, not before, because the log
        # pane can be as short as TWO lines and scrolls to the bottom: written
        # first, a longer note pushes it out of sight and nobody ever sees it.
        # The owner's own machine is set to two lines. Headless tests passed
        # either way; only looking at it on screen found this.
        try:
            kind = getattr(getattr(reader, "_dev", None), "kind", "")
            if kind:
                self._log.appendPlainText("\n" + (
                    tr("[NOTE] Connected to your CR30 over Bluetooth.")
                    if kind == "ble" else
                    tr("[NOTE] Connected to your CR30 over the USB cable.")))
        except Exception:              # noqa: BLE001 — a note, never fatal
            log.debug("could not name the CR30 transport", exc_info=True)
        self._log.ensureCursorVisible()

        # THE CAP IS STILL ON, WHICH IS THE ONLY MOMENT THIS CAN BE ASKED.
        # The black step is next and it asks for the cap OFF, so the learning
        # press has to happen here or not at all this session.
        self._offer_cr30_tile_learning(reader)

        if want_black and not self._run_cr30_black_calibration():
            return False

        # SAY IT HAPPENED, ON SCREEN, whatever the instrument does.
        #
        # The instrument DOES beep for a host-triggered calibration, on both
        # transports — the owner confirmed that on 2026-08-29 after running it
        # over USB and Bluetooth. An earlier comment here claimed the opposite
        # and cited EXP-BLE-015 as having measured it; that experiment recorded
        # no sound at all and the claim came from a first impression. What he
        # originally hit was LATENCY: over Bluetooth the cycle took ~1.85 s and
        # the button felt dead.
        #
        # The confirmation stays regardless, and stands on its own reasons: a
        # beep from a device on the far side of a desk is not an answer to
        # "did that work", and over Bluetooth it can arrive a second and a half
        # after the click. The sound is the one already used for "that worked",
        # rather than a new one nobody has chosen.
        from core import sound as _snd
        try:
            self._sound.play(_snd.PATCH_OK)
        except Exception:              # noqa: BLE001 — never block on audio
            log.debug("calibration sound failed", exc_info=True)
        self._flash_status(tr("Your CR30 has been calibrated."),
                           duration_ms=6000)
        # The instructions window is the confirmation window his ruling asks
        # for: it already says to take the magnetic cap off and how to
        # navigate. Shown here rather than after the helper starts, so the two
        # windows read as one sequence.
        self._show_cr30_measuring_window()
        return True

    #: Fragments of the underlying library's own error text that mean "the link
    #: to the instrument is gone", not "the instrument refused". Matched on the
    #: message because bleak raises one BleakError type for many causes.
    _LOST_LINK_SIGNS = ("service discovery has not been performed",
                        "not connected", "disconnected",
                        "no backend with an available connection")

    def _is_lost_link(self, message: str) -> bool:
        """Did this failure mean the instrument is unreachable?

        It matters because the two cases need OPPOSITE advice. A refused
        calibration is survivable — the white one still stands and the chart can
        still be measured. A LOST CONNECTION is not: nothing can be read at all,
        and telling the user "the measurement can go ahead" sends them to press
        a button nothing is listening to. The owner hit exactly that on
        2026-08-30: the Bluetooth link dropped between the white calibration and
        its read-back, and ChromIQ invited him to carry on.
        """
        return any(sign in str(message).lower() for sign in self._LOST_LINK_SIGNS)

    @staticmethod
    def _plain_instrument_error(message: str) -> str:
        """The instrument's own words, or plain English when they are a
        library's internals.

        "Service Discovery has not been performed yet" is bleak telling itself
        something true. Shown to a user it explains nothing, and it was shown to
        the owner in a window.
        """
        text = str(message)
        low = text.lower()
        if "service discovery has not been performed" in low or "not connected" in low:
            return tr("the Bluetooth connection to the instrument was lost")
        if "no backend with an available connection" in low:
            return tr("Bluetooth could not reach the instrument")
        return text

    def _do_black_calibration(self) -> bool:
        """Send the dark-reference command, then check what it produced.

        THE ZERO CHECK IS THE ONLY VERIFICATION THAT EXISTS. The instrument
        gives no success signal for either calibration — the reply's bytes fit
        a result code and fit equally well the high byte of a clock that was
        never set, and over Bluetooth that same field carried a real timestamp.
        So nothing here says "calibrated successfully".

        But a dark reference has one honest test the white one does not: after
        it, a reading of nothing should come back at nothing. That is checked
        by ASKING the instrument, not by trusting the command.
        """
        from PyQt6.QtCore import QThread
        from PyQt6.QtWidgets import QMessageBox
        from ui.widgets import (fit_message_box_buttons,
                                order_message_box_buttons)

        reader = getattr(self, "_cr30_reader", None)
        if reader is None:
            return True
        result: dict = {}

        class _BlackWorker(QObject):
            done = pyqtSignal()

            def run(self) -> None:
                try:
                    reader.calibrate(black=True)
                    result["zero"] = reader.read_zero()
                except Exception as exc:      # noqa: BLE001 — reported below
                    result["error"] = str(exc) or type(exc).__name__
                self.done.emit()

        thread, worker = QThread(self), _BlackWorker()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.done.connect(thread.quit)
        thread.start()
        self._cal_thread, self._cal_worker = thread, worker
        while not thread.isFinished():
            QApplication.processEvents()
            thread.wait(20)
        self._cal_thread = self._cal_worker = None

        if "error" in result:
            why = self._plain_instrument_error(result["error"])
            lost = self._is_lost_link(result["error"])
            self._log.appendPlainText("\n" + tr(
                "The black calibration could not be taken: {error}"
                ).format(error=why))
            self._log.ensureCursorVisible()
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.NoIcon)
            box.setWindowTitle(tr("Calibrate the instrument"))
            box.setText(tr("The black calibration did not go through."))
            if lost:
                # THE MEASUREMENT CANNOT GO AHEAD, so do not say it can.
                box.setInformativeText(tr(
                    "ChromIQ has lost contact with your CR30, so nothing can "
                    "be measured until it is back.\n\n"
                    "Nothing has been changed: your white calibration still "
                    "stands and the instrument keeps the dark reference it "
                    "already had.\n\n"
                    "Check that it is switched on and in range — over "
                    "Bluetooth, pressing its own button once wakes it — then "
                    "start the measurement again.\n\n"
                    "What went wrong: {error}").format(error=why))
            else:
                box.setInformativeText(tr(
                    "Your white calibration is unaffected and the measurement "
                    "can go ahead — the instrument keeps the dark reference it "
                    "already had.\n\n"
                    "What went wrong: {error}").format(error=why))
            box.setStandardButtons(QMessageBox.StandardButton.Ok)
            fit_message_box_buttons(box)
            box.exec()
            # A refused calibration is survivable; a lost instrument is not.
            return not lost

        # NO SECOND SOUND AND NO SECOND FLASH. The white step has already
        # played "that worked" and flashed "Your CR30 has been calibrated." a
        # moment earlier; repeating both here reads as two separate successes
        # for what the user experienced as one calibration.
        zero = result.get("zero")
        # ALSO TO THE FILE LOG. This number is the only honest check either
        # calibration has, and it was written to the on-screen panel alone —
        # so it never reached chromiq.log, and a report of a bad profile could
        # not be checked against it afterwards. Found while trying to read it
        # back during a live test, 2026-08-30.
        log.info("CR30 dark reference read back at %s %%R (warn above %s)",
                 "unreadable" if zero is None else f"{zero:.5f}",
                 _CR30_ZERO_WARN)
        if zero is None:
            self._log.appendPlainText("\n" + tr(
                "[NOTE] ChromIQ asked the CR30 to take its black calibration. "
                "It could not read back afterwards to see how it looks."))
        elif zero <= _CR30_ZERO_WARN:
            self._log.appendPlainText("\n" + tr(
                "[NOTE] ChromIQ asked the CR30 to take its black calibration, "
                "and a reading of nothing came back at {zero:.3f} %, which is "
                "what a healthy dark reference looks like. It does NOT say "
                "the reference "
                "was taken against the right thing: a dark calibration defines "
                "what zero means, so whatever the instrument was looking at "
                "reads as nothing straight afterwards."
                ).format(zero=zero))
        else:
            self._log.appendPlainText("\n" + tr(
                "[WARNING] After the black calibration, a reading of nothing "
                "came back at {zero:.3f} % instead of near zero. Something was "
                "probably in front of the opening. Take the black calibration "
                "again with the instrument pointing at nothing."
                ).format(zero=zero))
            self._log.ensureCursorVisible()
            return self._warn_dark_reference_looks_wrong(zero)
        self._log.ensureCursorVisible()
        return True

    def _warn_dark_reference_looks_wrong(self, zero: float) -> bool:
        """A dark reference that does not read as dark. Always a window.

        Basti's ruling, 2026-08-30: *"a failure message should be [a pop up] to
        warn the user and let him act accordingly because you can hide the log
        output as i do it and it is not that noticable there anyway"*. He does
        hide it, and this is the ONE honest check either calibration has — a
        finding nobody can see is not a finding.

        It offers the remedy rather than only naming it, because the remedy is
        four seconds of work and the alternative is a whole chart measured
        against a dark reference that is wrong by an unknown amount.
        """
        from PyQt6.QtWidgets import QMessageBox
        from ui.widgets import (fit_message_box_buttons,
                                order_message_box_buttons)

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle(tr("Check the dark calibration"))
        box.setText(tr("That dark reference does not look dark."))
        box.setInformativeText(tr(
            "Straight after the calibration, ChromIQ asked your CR30 to read "
            "nothing at all. It came back at {zero:.3f} % instead of near "
            "zero, which usually means something was in front of the opening "
            "— a hand, the cap, the paper it was resting on.\n\n"
            "It is worth putting right: every reading you take from now on is "
            "measured against this reference, and a wrong one shifts them all "
            "by an amount nothing afterwards can see.\n\n"
            "Hold the instrument with the opening pointing DOWNWARD into open "
            "space, with nothing in front of it, then press “Take it again”.\n\n"
            "If you would rather carry on, you can — your white calibration "
            "is unaffected either way."
            ).format(zero=zero))
        again = box.addButton(tr("Take it again"),
                              QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr("Carry on anyway"),
                      QMessageBox.ButtonRole.DestructiveRole)
        box.setDefaultButton(again)
        fit_message_box_buttons(box)
        order_message_box_buttons(box, box.buttons())
        box.exec()

        if box.clickedButton() is again:
            # ONE retry per press, never a loop of its own: if the second one
            # warns too, this window comes back and the user decides again.
            return self._do_black_calibration()
        self._log.appendPlainText("\n" + tr(
            "[NOTE] Carrying on with that dark reference, at your choice."))
        self._log.ensureCursorVisible()
        return True

    def _run_cr30_black_calibration(self) -> bool:
        """The second calibration: the dark reference, taken against air.

        M-CR30-CALIBRATE-BLACK (§M-PROPOSED). It asks for the OPPOSITE of the
        window before it — cap OFF, opening pointing at nothing — which is why
        both windows carry the same pair-of-steps picture with the current one
        marked. The owner's worry was that two similar windows would have
        someone do the same thing twice; showing the pair makes the difference
        visible rather than remembered.

        There is no black TILE on this instrument. The dark reference is open
        air, which is why the instruction says to point it at nothing rather
        than to put anything in front of it — and why the picture shows no
        black tile that somebody might go looking for.
        """
        from PyQt6.QtWidgets import QMessageBox
        from workflow import measurement_messages as M
        from ui.widgets import (fit_message_box_buttons,
                                order_message_box_buttons)
        from ui.cr30_pictograms import BLACK_STEP, steps_pair

        title, body = M.M_CR30_CALIBRATE_BLACK.render()
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setIconPixmap(steps_pair(BLACK_STEP, self))
        box.setWindowTitle(tr("Calibrate the instrument"))
        box.setText(title)
        box.setInformativeText(body)
        go = box.addButton(tr("Calibrate now"),
                           QMessageBox.ButtonRole.AcceptRole)
        skip = box.addButton(tr("Skip this step"),
                             QMessageBox.ButtonRole.RejectRole)
        cancel = box.addButton(tr("Cancel the measurement"),
                               QMessageBox.ButtonRole.DestructiveRole)
        box.setDefaultButton(go)
        # ESCAPE AND THE CLOSE BUTTON MUST MEAN CANCEL, AND SAYING SO IS NOT
        # ENOUGH — QT PICKS FOR YOU OTHERWISE.
        #
        # With no escape button set, QMessageBox detects one at exec() time and
        # chooses the RejectRole button — which here is "Skip this step". So
        # dismissing the window silently SKIPPED the dark reference and walked
        # into the measurement: precisely the fault the owner reported, still
        # present after the fix meant to remove it, because the branch that
        # handles a dismissal was unreachable.
        #
        # It was measured wrong twice before it was measured right. `box.close()`
        # on an unshown box returns None, and so does Escape on a box that was
        # only `show()`n — Qt does not detect the escape button until exec().
        # Only an exec'd box with a real key event tells the truth.
        box.setEscapeButton(cancel)
        fit_message_box_buttons(box)
        # "calibrate now, skip this step, cancel" — his order, verbatim.
        order_message_box_buttons(box, [go, skip, cancel])
        box.exec()
        clicked = box.clickedButton()

        if clicked is go:
            return self._do_black_calibration()

        if clicked is skip:
            # Skipping the dark reference is not cancelling the measurement —
            # the white calibration has already happened and the session is
            # perfectly usable without this.
            self._log.appendPlainText("\n" + tr(
                "[NOTE] The black calibration was skipped. Your measurement "
                "will go ahead using the dark reference the instrument "
                "already had."))
            self._log.ensureCursorVisible()
            return True

        # CLOSING A WINDOW IS A WITHDRAWAL, NEVER A CONSENT.
        #
        # `clickedButton()` is None for the red traffic light, the Windows X and
        # Esc alike — measured, not assumed. This branch used to be reached by
        # "anything that is not Calibrate now", so closing the window was read
        # as "skip" and the measurement went ahead: the owner found it,
        # 2026-08-30 — *"if i close them via the red traffic light button
        # chromiq gives me the next window anyway and allows me to go into the
        # measurement"*. Skipping a calibration step is a positive decision and
        # has its own button; dismissing the window is not that decision.
        #
        # Cancelling here costs nothing at all: the calibration runs BEFORE the
        # helper starts, so there is no session yet and nothing to lose.
        self._log.appendPlainText("\n" + tr(
            "[STOPPED] You cancelled at the dark-reference step, so this "
            "measurement did not start. Your white calibration was taken and "
            "is still in the instrument; nothing has been measured and nothing "
            "on disk has been changed. Press “{start}” when you want to begin, "
            "or press it and choose “Skip this step” if you would rather not "
            "take the dark reference at all."
            ).format(start=self._start_button_name()))
        self._log.ensureCursorVisible()
        return False

    def _offer_cr30_tile_learning(self, reader) -> None:
        """Capped presses teach this unit its own tile constant.

        M-CR30-LEARN-TILE (§M-PROPOSED). The magnet guard recognises the value
        the instrument returns when something magnetic is at the opening -- it
        stops measuring and hands back its stored white tile. That value was
        hard-coded from ONE unit, and the only other CR30 in evidence reads up
        to 4.69 %R away, 94x the tolerance: on anyone else's instrument the
        guard matched nothing and its owner had no protection at all.

        It cannot be read from the calibration -- afterwards the instrument's
        stored slot is zero-filled -- so it comes from a capped press. That is
        safe to ask for: a capped press does not damage the white reference,
        measured across EXP-TILE-002/003/004 on 2026-08-30.

        Never fatal, and always refusable. A declined or failed learn leaves
        the guard exactly as it is today.

        The window COLLECTS WHILE IT IS OPEN, and closes itself the moment the
        tile is proven. It must: over Bluetooth the learner needs two
        bit-identical readings, and the old shape asked for the presses, then
        waited to be dismissed, and only started listening afterwards -- so
        the presses a user made while reading it went nowhere.
        """
        from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal
        from PyQt6.QtWidgets import QApplication
        from workflow import measurement_messages as M
        from ui.widgets import fit_button_width
        try:
            if reader.guard_is_armed:
                return
        except Exception:              # noqa: BLE001 — never block a session
            log.debug("could not ask whether the guard is armed", exc_info=True)
            return

        # HOW MANY PRESSES — ASKED OF THE OPEN TRANSPORT, NOT ASSUMED.
        # The window said "One press teaches…" and buried the real rule four
        # paragraphs down: one press proves the tile over USB, where the header
        # carries the gate flag, but Bluetooth says nothing, so it takes TWO
        # bit-identical readings. Basti pressed once, confirmed, and the window
        # sat there until he killed the app; pressing twice worked at once.
        # Two is the safe default when the transport cannot be read — being
        # told to press twice and having it accept after one costs nothing;
        # being told once when two are needed is a dead end.
        _kind = ""
        try:
            _kind = (getattr(reader, "open_transport", "") or "").lower()
        except Exception:              # noqa: BLE001
            _kind = ""
        _times = 1 if _kind == "usb" else 2
        # THE WHOLE BODY COMES FROM THE CATALOGUE, not a sentence built here.
        # M-CR30-LEARN-TILE carries both bodies and `count_key="presses"`
        # picks between them, so each variant states its own rule FIRST and
        # then explains it. One shared body with a sentence injected into it
        # left both windows saying "Why the difference" about a difference
        # neither had mentioned, and the one-press window never said that
        # Bluetooth needs two (Basti, 2026-08-31).
        _title, _body = M.M_CR30_LEARN_TILE.render(presses=_times)

        # THE WINDOW LISTENS WHILE IT IS OPEN. It used to say "press the
        # button", wait for "I have pressed it", CLOSE, and only then start
        # collecting -- so every press made while reading the window was
        # thrown away, and the instruction was unfollowable. Basti pressed
        # once over Bluetooth on 2026-08-30, confirmed, and sat in front of a
        # closed window for 34 s before force-quitting the app. The learner
        # now runs behind the window, the window counts the presses as they
        # land, and it closes itself the moment the tile is proven.
        from PyQt6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout,
                                     QLabel, QScrollArea, QVBoxLayout, QWidget)
        from html import escape

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Teach ChromIQ your instrument"))
        dlg.setMinimumWidth(560)
        outer = QVBoxLayout(dlg)
        outer.setSpacing(16)
        outer.setContentsMargins(24, 20, 24, 20)

        row = QHBoxLayout()
        row.setSpacing(20)
        try:
            from ui.cr30_pictograms import press_button
            art = QLabel(dlg)
            art.setPixmap(press_button(_times, dlg))
            art.setAlignment(Qt.AlignmentFlag.AlignTop
                             | Qt.AlignmentFlag.AlignHCenter)
            row.addWidget(art, 0)
        except Exception:              # noqa: BLE001 — a picture is never
            log.debug("learn-tile pictogram unavailable", exc_info=True)

        words = QVBoxLayout()
        words.setSpacing(12)
        head = QLabel("<b>" + escape(_title) + "</b>", dlg)
        head.setTextFormat(Qt.TextFormat.RichText)
        head.setWordWrap(True)
        words.addWidget(head)
        body = QLabel(
            escape(_body).replace("\n\n", "<br><br>"), dlg)
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setWordWrap(True)
        words.addWidget(body)
        row.addLayout(words, 1)

        # IT MUST NEVER BE TALLER THAN THE SCREEN IT IS ON. This window is
        # eight paragraphs, and the instruction that matters -- how many
        # times to press -- sits in the middle of them. On a short display
        # the whole of the bottom half simply vanished, with nothing to say
        # anything was missing and no way to reach it.
        held = QWidget()
        held.setLayout(row)
        scroll = QScrollArea(dlg)
        scroll.setWidget(held)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)
        held.setAutoFillBackground(False)
        outer.addWidget(scroll, 1)

        # The live line: what ChromIQ has actually received so far, so nobody
        # has to guess whether a press was heard. OUTSIDE the scroll area --
        # it answers "did it hear me?", which is worthless if it can be
        # scrolled out of sight while somebody is looking at the instrument.
        heard = QLabel(tr("Waiting for the first press…"), dlg)
        heard.setWordWrap(True)
        heard.setStyleSheet(f"color: {_TAB_COLOR}; font-weight: 600;")
        outer.addWidget(heard, 0)

        buttons = QDialogButtonBox()
        later = buttons.addButton(tr("Not now"),
                                  QDialogButtonBox.ButtonRole.RejectRole)
        buttons.rejected.connect(dlg.reject)
        fit_button_width(later)
        outer.addWidget(buttons, 0)

        # Ask for the whole thing, then keep it inside the screen; the scroll
        # area takes up whatever is left over.
        #
        # A WORD-WRAPPED QLabel UNDER-REPORTS ITS HEIGHT. `sizeHint` on the
        # dialog cannot know how many lines the prose will take until it has a
        # width, so asking once opens the window a couple of hundred pixels
        # too short and puts a scrollbar on a message that would have fitted.
        # The real height is only knowable from `heightForWidth`, and only
        # after the layout has settled -- hence the second pass, once shown.
        screen = dlg.screen() or QApplication.primaryScreen()
        room = (screen.availableGeometry().height() - 80) if screen else 900
        dlg.resize(dlg.sizeHint().width(),
                   min(dlg.sizeHint().height(), max(320, room)))

        def _fit_to_its_own_words() -> None:
            from PyQt6 import sip
            if sip.isdeleted(dlg):
                return
            inner = scroll.viewport().width()
            need = held.heightForWidth(inner) if inner > 0 else -1
            if need <= 0:
                return
            grow = need - scroll.viewport().height()
            if grow > 0:
                dlg.resize(dlg.width(),
                           min(dlg.height() + grow, max(320, room)))

        QTimer.singleShot(0, _fit_to_its_own_words)

        result: dict = {}
        # TWO DIFFERENT QUESTIONS, AND THEY WERE ONE FLAG.
        #
        # `stop` tells the learner to give up, and it is set unconditionally
        # once the window has gone -- a learner still reading after its window
        # closed is exactly the hang this window was rebuilt to remove. But
        # the note afterwards asked the SAME flag whether the user had
        # declined, so a learn that failed for any other reason (the link went
        # away, the readings never agreed) reported "you can carry on, the
        # magnet check stays on the built-in value" and threw the instrument's
        # own error text away. Driven: a failure and a raised
        # "BLE link went away" both printed the declined note.
        stop = {"asked": False}
        declined = {"by_hand": False}
        dlg.rejected.connect(lambda: (stop.__setitem__("asked", True),
                                      declined.__setitem__("by_hand", True)))

        class _Learn(QObject):
            done = pyqtSignal()
            pressed = pyqtSignal(int)

            def run(self) -> None:
                try:
                    result.update(reader.learn_tile(
                        timeout=90.0,
                        cancelled=lambda: stop["asked"],
                        on_press=self.pressed.emit))
                except Exception as exc:   # noqa: BLE001 — reported below
                    result["error"] = str(exc) or type(exc).__name__
                self.done.emit()

        heard_count = {"n": 0}

        def _heard(n: int) -> None:
            # COUNTED HERE, NOT TAKEN FROM THE RESULT. When `learn_tile`
            # raises, the result carries only the error and no press count, so
            # a learn that took a reading and then lost the link reported
            # "Readings taken: 0" — which reads as "the instrument never
            # answered" when it had.
            heard_count["n"] = max(heard_count["n"], int(n))
            # A PRESS CAN ARRIVE AFTER THE WINDOW HAS GONE. "Not now" closes
            # it while the learner is still inside a read, and the next press
            # on the instrument delivers this signal to a label Qt has already
            # destroyed -- "wrapped C/C++ object of type QLabel has been
            # deleted", raised in a slot, which PyQt6 turns into an abort. It
            # is not a rare race: it is what happens whenever somebody
            # declines and then presses the button anyway.
            from PyQt6 import sip
            if sip.isdeleted(heard):
                return
            left = max(0, _times - n)
            heard.setText(
                tr("Reading {n} received. One more press to go.").format(n=n)
                if left == 1 else
                tr("Reading {n} received. Checking it…").format(n=n)
                if left == 0 else
                tr("Reading {n} received. {left} more presses to go.").format(
                    n=n, left=left))

        thread, worker = QThread(self), _Learn()
        worker.moveToThread(thread)
        worker.pressed.connect(_heard)          # queued onto the GUI thread
        thread.started.connect(worker.run)
        worker.done.connect(thread.quit)
        worker.done.connect(dlg.accept)         # it closes ITSELF when proven
        # …and nothing is delivered to the window's widgets once it is gone.
        #
        # `finished` FIRES TWICE ON THE DECLINE PATH, and the second one used to
        # end the process. Press "Not now": `reject()` fires it, the learner
        # thread then proves the tile and fires `dlg.accept()`, which fires it
        # again — and `disconnect` on an already-disconnected slot raises
        # `TypeError: 'function' object is not connected`. In a Qt slot that is
        # not a log line: PyQt6 hands an unhandled slot exception to
        # `sys.excepthook` and calls `qFatal()`, so ChromIQ aborted, mid
        # measurement, taking chartread's unwritten `.ti3` with it — six runs
        # of six. The window's own last line invites exactly this: *"You can
        # press 'Not now' and carry on measuring as usual."*
        #
        # Every other `disconnect` in this app is guarded; this was the only
        # one that was not (a whole-app sweep, challenge round 2026-09-01).
        def _stop_listening(_r) -> None:
            try:
                worker.pressed.disconnect(_heard)
            except (TypeError, RuntimeError):
                pass          # already disconnected, or the sender is gone

        dlg.finished.connect(_stop_listening)
        thread.start()
        # Both must stay referenced until the thread finishes, or Qt collects a
        # running QThread and takes the process with it.
        self._learn_thread, self._learn_worker = thread, worker
        dlg.exec()

        # The user pressed "Not now": the learner is told to stop, but it may
        # be inside a read with a timeout still to run, so it is never waited
        # for on the GUI thread -- that is what froze the app before.
        stop["asked"] = True
        if thread.isFinished():
            self._learn_thread = self._learn_worker = None
        else:
            # STILL REFERENCED UNTIL IT ACTUALLY ENDS. `cancelled` is polled
            # inside a read that may have most of its 90 s left, so the thread
            # routinely outlives the window -- and dropping the last reference
            # to a RUNNING QThread takes the process with it ("QThread:
            # Destroyed while thread is still running", seen on the very first
            # run of this window). Qt clears them when it has really stopped.
            thread.quit()

            def _forget(_t=thread):
                if self._learn_thread is _t:
                    self._learn_thread = self._learn_worker = None

            thread.finished.connect(_forget)

        # ONE NOTE, WHICHEVER WAY IT ENDED — and never two at once. Thirty-four
        # seconds of this feature failing left NO trace in the log at all,
        # which is why the first explanation of it was wrong.
        if result.get("learned"):
            self._log.appendPlainText("\n" + tr(
                "[NOTE] ChromIQ has learned this instrument's white-tile "
                "value, so it can now recognise a reading taken with "
                "something magnetic at the opening. Reason it was believed: "
                "{why}").format(why=result.get("provenance", "")))
            self._flash_status(
                tr("ChromIQ now knows your instrument's white tile."),
                duration_ms=6000)
        elif declined["by_hand"]:
            self._log.appendPlainText("\n" + tr(
                "[NOTE] The magnet check is running on ChromIQ's built-in "
                "value, which was measured on a different instrument. It may "
                "not recognise a covered opening on yours."))
        else:
            _why = str(result.get("error") or "").strip()
            _presses_seen = max(int(result.get("presses") or 0),
                                heard_count["n"])
            self._log.appendPlainText("\n" + tr(
                "[NOTE] ChromIQ could not learn this instrument's white-tile "
                "value this time, so the magnet check stays on its built-in "
                "one. Nothing else is affected, and it will offer again."))
            if _why or _presses_seen:
                self._log.appendPlainText(tr(
                    "        Readings taken: {n}. {why}").format(
                        n=_presses_seen,
                        why=_why or tr("They did not agree closely enough to "
                                       "be the tile.")))
        self._log.ensureCursorVisible()
