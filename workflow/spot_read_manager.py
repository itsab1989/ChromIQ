"""Drives ArgyllCMS ``spotread`` for interactive single-patch (spot) reading.

A thin sibling of ``MeasureManager`` (which drives chartread): it runs spotread
through the same PTY mechanism in ``ArgyllRunner``, feeds keystrokes back, and
parses spotread's line output into Qt signals the dialog reacts to.

spotread loops: it prints "… any other key to take a reading:" → the user takes
a reading → it prints "Result is XYZ: … Lab: …" → back to the prompt. Quitting
is a 'q' (or ESC) at that prompt. Calibration steps print an instruction line
followed by "… hit any key to continue,"; we surface those so the dialog can
show a Place-the-instrument pop-up and send the keypress on confirm.
"""
from __future__ import annotations

import re
import shlex
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from core.logger import get_logger

if TYPE_CHECKING:
    from core.argyll_runner import ArgyllRunner

log = get_logger(__name__)

# "Result is XYZ: 12.3 45.6 7.8, D50 Lab: 50.0 -1.2 3.4"  (mode/whitepoint vary,
# but every variant prints "XYZ: x y z" then "<space>Lab: l a b").
_RESULT_RE = re.compile(
    r"Result is XYZ:\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+).*?Lab:\s*"
    r"([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)",
    re.IGNORECASE,
)
# The per-reading menu prompt (no trailing newline; emitted by the PTY flush).
_READY_RE = re.compile(r"to take a reading", re.IGNORECASE)
# Manual calibration steps from spectro/instappsup.c always end with this line
# ("… and then hit any key to continue,"). It's specific to calibration prompts
# (the per-reading menu says "any other key to take a reading" instead), so it's
# a reliable trigger for the calibration pop-up.
_CALIB_CONTINUE_RE = re.compile(r"hit any key to continue", re.IGNORECASE)

_MISREAD_RE        = re.compile(r"Spot read failed due to misread",               re.IGNORECASE)
_COMS_FAIL_RE      = re.compile(r"Spot read failed due to communication problem", re.IGNORECASE)
_SENSOR_POS_RE     = re.compile(r"sensor being in the wrong position",            re.IGNORECASE)
_NO_INSTRUMENT_RE  = re.compile(r"no instrument detected|no suitable instruments|no instruments connected", re.IGNORECASE)
# spotread -v prints "Instrument Type:   ColorMunki" once it has opened the
# device. Knut ran it in a terminal and pasted the output (#130, 2026-07-31),
# which settled something I had got wrong: `-c 1` selects the COMMUNICATION
# PORT, not the instrument, so ChromIQ never actually knew which device was
# attached. This line is the only place spotread says.
_INST_TYPE_RE      = re.compile(r"Instrument Type:\s*(.+?)\s*$", re.IGNORECASE)
_DEVICE_BUSY_RE    = re.compile(r"Device being used",                             re.IGNORECASE)
_USB_ERROR_RE      = re.compile(r"ReadPipeAsync\s+failed",                        re.IGNORECASE)
_INIT_COMS_FAIL_RE = re.compile(r"Establishing communications with instrument failed with message\s+'([^']+)'", re.IGNORECASE)
_INIT_INST_FAIL_RE = re.compile(r"Initialising instrument failed with message\s+'([^']+)'", re.IGNORECASE)
# spotread refuses -s (print the spectrum) on an instrument without spectral
# data with exactly two lines, "Need spectral information for custom
# illuminant or observer" and then "and instrument doesn't support it", and
# exits (spotread.c, its only use of the first line). The second line alone
# ends EVERY capability refusal (a colorimeter in Reflective mode, Emissive on
# a reflective-only instrument, the "(ignored)" notes), so only the pair counts.
_NEED_SPECTRAL_RE  = re.compile(r"Need spectral information",                   re.IGNORECASE)
_NO_SPECTRAL_RE    = re.compile(r"instrument doesn't support it",               re.IGNORECASE)


@dataclass
class SpotReadParams:
    instrument: str = "1"
    mode: str = "reflective"        # "reflective" | "emissive" | "ambient"
    high_res: bool = False
    disable_initial_cal: bool = False
    extra_args: str = ""
    #: Ask spotread for each reflective reading's spectrum (-s), which is what
    #: the calibration check looks at (workflow/spot_calibration_check.py).
    spectrum: bool = True


class SpotReadManager(QObject):
    reading_ready           = pyqtSignal(tuple, tuple)  # (xyz, lab)
    ready_to_read           = pyqtSignal()              # menu prompt — Take reading enabled
    instrument_detected     = pyqtSignal(str)           # model name spotread reports
    calibration_prompt      = pyqtSignal()              # manual cal step needs a keypress
    # …and the other half of that: spotread going back to its ready prompt after
    # a calibration is the only signal that the calibration actually finished.
    # Without it the tool had nothing to tell the user with, which is what Knut
    # missed (#130, 2026-07-30): *"When I complete the calibration, there is no
    # infomation window that calibration is done and to turn the unit back to
    # measure mode."*
    calibration_finished    = pyqtSignal()
    # spotread re-prints its "set the sensor to calibration position" prompt when
    # the key was pressed but the instrument was not actually in position. Knut
    # pasted exactly that from a terminal (#130, 2026-07-31): the prompt simply
    # appears a second time. Without noticing it the tool sat on "Calibrating…"
    # for ever, and changing the dial afterwards did nothing.
    calibration_position_wrong = pyqtSignal()
    misread                 = pyqtSignal()
    sensor_wrong_position   = pyqtSignal()
    no_instrument           = pyqtSignal()
    device_busy             = pyqtSignal()
    instrument_disconnected = pyqtSignal()
    coms_init_failed        = pyqtSignal(str)
    inst_init_failed        = pyqtSignal(str)
    session_ended           = pyqtSignal(int)           # exit code
    # Item 41 (4.3.60): a reflective reading after a calibration is lighter
    # than any print can be, or the sensor saturated, so the calibration was
    # probably too weak. A spot_calibration_check.Verdict, at most once per
    # calibration. The reading itself has already gone out unchanged.
    calibration_suspect     = pyqtSignal(object)

    def __init__(self, runner: "ArgyllRunner", parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._runner = runner
        self._calib_announced: bool = False
        from workflow.spot_calibration_check import SpotCalibrationCheck
        self._cal_check = SpotCalibrationCheck()
        self._params: "SpotReadParams | None" = None
        self._on_line: "Callable[[str], None] | None" = None
        #: (wl_short, wl_long, steps) while the values line of a spectrum is due
        self._spectrum_head: "tuple[float, float, int] | None" = None
        #: the spectrum printed for the reading whose Result line comes next
        self._spectrum: "tuple[float, float, list[float]] | None" = None
        self._spectrum_refused = False
        #: True when this start passed -s, so a refusal of it can be one
        self._asked_spectrum = False
        #: True right after "Need spectral information" (the refusal's first line)
        self._need_spectral_seen = False
        #: True once the window let go of this manager (detach): a restart
        #: that was already queued must not start a spotread nobody owns.
        self._detached = False
        #: The one restart without -s, on a timer this manager owns, so it dies
        #: with the manager instead of firing into a closed window.
        self._restart_timer = QTimer(self)
        self._restart_timer.setSingleShot(True)
        self._restart_timer.setInterval(0)
        self._restart_timer.timeout.connect(self._restart_without_spectrum)
        self._restart_params: "SpotReadParams | None" = None

    # ------------------------------------------------------------------
    def start(self, params: SpotReadParams, on_line: Callable[[str], None]) -> None:
        args = self._build_args(params)
        cwd  = Path(tempfile.gettempdir())
        log.info("spotread: %s  [cwd=%s]", " ".join(args), cwd)
        self._calib_announced = False
        self._params = params
        self._on_line = on_line
        self._spectrum_head = None
        self._spectrum = None
        self._spectrum_refused = False
        self._asked_spectrum = "-s" in args
        self._need_spectral_seen = False
        # The session reads with a calibration in force from its first
        # reading on (the start-up one, or the stored one with -N).
        self._cal_check.reset()

        # A PORT THAT IS NOT AN INSTRUMENT IS NEVER OPENED (core/instrument_port):
        # with nothing plugged in, port 1 is macOS's Bluetooth incoming port,
        # whose open could block for ever. Reported as spotread reports "No
        # instrument detected", once this start has returned.
        from core.instrument_port import refused_port
        if refused_port("spotread", args) is not None:
            QTimer.singleShot(0, self._finish_refused_start)
            return

        self._runner.run(
            "spotread",
            args,
            cwd,
            on_line=lambda line: self._handle_line(line, on_line),
            on_finish=self._on_finish,
            use_pty=True,
        )

    def _on_finish(self, code: int) -> None:
        if (self._spectrum_refused and self._asked_spectrum
                and self._params is not None and not self._detached):
            # This instrument has no spectral data, so spotread refused -s and
            # ended before it calibrated anything. Start again without it,
            # once (the new start has spectrum=False, so it cannot refuse -s
            # again); the calibration check then judges by Y alone.
            log.info("spotread refused -s (no spectral data); starting again "
                     "without it")
            from dataclasses import replace
            self._restart_params = replace(self._params, spectrum=False)
            self._restart_timer.start()
            return
        self.session_ended.emit(code)

    def _restart_without_spectrum(self) -> None:
        params, self._restart_params = self._restart_params, None
        if params is None or self._detached:
            return
        self.start(params, self._on_line or (lambda _l: None))

    def request_calibration(self) -> None:
        """Ask spotread for a calibration from its ready prompt ('k')."""
        self._runner.write_stdin("k")

    def _finish_refused_start(self) -> None:
        """The ending of a start that would have opened a system port."""
        self.no_instrument.emit()
        self.session_ended.emit(1)

    def take_reading(self) -> None:
        """Take one reading — any key at the menu prompt does this."""
        self._runner.write_stdin(" ")

    def send_key(self, key: str = "\r") -> None:
        """Send a key (e.g. to confirm a calibration step)."""
        self._runner.write_stdin(key)

    def quit(self) -> None:
        """Ask spotread to exit cleanly from the menu prompt."""
        self._runner.write_stdin("q")

    def abort(self) -> None:
        self._runner.abort()

    def detach(self) -> None:
        """Let go of the shared runner, so nothing can call back into a window
        that is closing (#145).

        Killing the process is not enough on its own: the PTY reader thread
        can still deliver its completion afterwards, and this manager's
        callbacks would then emit signals on a C++ object Qt has already
        destroyed with the dialog. See ``ArgyllRunner.forget_run_callbacks``.
        """
        self._detached = True
        restart = self.__dict__.get("_restart_timer")
        if restart is not None:
            restart.stop()
        try:
            self._runner.forget_run_callbacks()
        except Exception:      # noqa: BLE001 — closing must never raise
            log.warning("Could not detach the spot-read session", exc_info=True)

    @property
    def is_running(self) -> bool:
        return self._runner.is_running

    # ------------------------------------------------------------------
    def _build_args(self, p: SpotReadParams) -> list[str]:
        # -v makes spotread announce the instrument it found; without it there is
        # no way to tell a ColorMunki from an i1Pro, and the calibration windows
        # fall back to generic wording (Knut, #130 2026-07-31).
        args: list[str] = ["-v", "-c", p.instrument]
        if p.mode == "emissive":
            args.append("-e")
        elif p.mode == "ambient":
            args.append("-a")
        # reflective is spotread's default — no flag.
        if p.high_res:
            args.append("-H")
        if p.disable_initial_cal:
            args.append("-N")
        extra = shlex.split(p.extra_args) if p.extra_args else []
        args += extra
        # The spectrum is what the calibration check reads (item 41). Only for
        # reflective readings: an emissive colorimeter has none, and spotread
        # would refuse to start.
        if (p.mode == "reflective" and p.spectrum
                and not any(a in ("-s", "-S") for a in extra)):
            args.append("-s")
        return args

    def _reflective(self) -> bool:
        return self._params is None or self._params.mode == "reflective"

    def _handle_line(self, line: str, on_line: Callable[[str], None]) -> None:
        on_line(line)

        from workflow import spot_calibration_check as SCC
        if self._spectrum_head is not None:
            lo, hi, n = self._spectrum_head
            self._spectrum_head = None
            values = SCC.parse_spectrum_values(line, n)
            if values is not None:
                self._spectrum = (lo, hi, values)
                return
        m = SCC.SPECTRUM_HEAD_RE.search(line)
        if m:
            self._spectrum_head = (float(m.group(1)), float(m.group(2)),
                                   int(m.group(3)))
            self._spectrum = None
            return

        m = _RESULT_RE.search(line)
        if m:
            xyz = (float(m.group(1)), float(m.group(2)), float(m.group(3)))
            lab = (float(m.group(4)), float(m.group(5)), float(m.group(6)))
            spectrum, self._spectrum = self._spectrum, None
            self.reading_ready.emit(xyz, lab)
            if self._reflective():
                verdict = self._cal_check.on_reading(xyz, spectrum)
                if verdict is not None:
                    log.warning(
                        "spot read: reading lighter than a print can be after "
                        "this calibration (%.1f %% between %g and %g nm, Y %.2f;"
                        " %s); asking about the calibration",
                        verdict.percent or 0.0, *SCC.BAND_NM, xyz[1],
                        "spectrum" if spectrum else "no spectrum, judged by Y")
                    self.calibration_suspect.emit(verdict)
            return

        m = _INST_TYPE_RE.search(line)
        if m:
            self.instrument_detected.emit(m.group(1).strip())
            return

        if _READY_RE.search(line):
            if self._calib_announced:
                # We are back at the ready prompt having been in a calibration,
                # so that calibration is done.
                self._cal_check.reset()
                self.calibration_finished.emit()
            self._calib_announced = False
            self.ready_to_read.emit()
            return

        # Calibration: fire the pop-up when spotread asks the user to position
        # the instrument and hit a key. (Reset on every ready prompt above so a
        # later calibration in the same session prompts again.)
        if _CALIB_CONTINUE_RE.search(line):
            if not self._calib_announced:
                self._calib_announced = True
                self.calibration_prompt.emit()
            else:
                # Asked again → the instrument was not where it needed to be.
                self.calibration_position_wrong.emit()

        if _MISREAD_RE.search(line):
            self.misread.emit()
            if SCC.SATURATED_RE.search(line) and self._reflective():
                verdict = self._cal_check.on_saturated()
                if verdict is not None:
                    log.warning("spot read: the sensor saturated on a "
                                "reflective patch after this calibration; "
                                "asking about the calibration")
                    self.calibration_suspect.emit(verdict)
        if _NEED_SPECTRAL_RE.search(line):
            self._need_spectral_seen = True
        elif _NO_SPECTRAL_RE.search(line):
            if self._need_spectral_seen and self._asked_spectrum:
                self._spectrum_refused = True
            self._need_spectral_seen = False
        elif line.strip():
            self._need_spectral_seen = False
        if _SENSOR_POS_RE.search(line):
            self.sensor_wrong_position.emit()
        if _COMS_FAIL_RE.search(line) or _USB_ERROR_RE.search(line):
            self.instrument_disconnected.emit()
        if _NO_INSTRUMENT_RE.search(line):
            self.no_instrument.emit()
        if _DEVICE_BUSY_RE.search(line):
            self.device_busy.emit()
        m = _INIT_COMS_FAIL_RE.search(line)
        if m:
            self.coms_init_failed.emit(m.group(1).strip())
        m = _INIT_INST_FAIL_RE.search(line)
        if m:
            self.inst_init_failed.emit(m.group(1).strip())
