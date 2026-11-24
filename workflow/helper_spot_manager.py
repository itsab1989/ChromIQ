"""Read single patches through ChromIQ's own helper (item 43 steps 2-3).

``SpotReadManager`` drives stock ArgyllCMS ``spotread``, which hands back ONE
measurement condition per reading. This manager drives the chart-reading
helper in its spot session (``chromiq-chartread --json --spot-session``,
``native/chartread_helper/chromiq_spotsession.c``), which reads exactly as the
helper reads a chart patch by patch, with no chart and no file, and keeps
M0, M1 and M2 of every press where the instrument gives them:

* an X-Rite i1Pro 3, whose driver works out all three from the one reading it
  always makes (with the Beta "X-Rite i1Pro 3 and i1Pro 2: keep M0, M1 and M2
  from every scan");
* an X-Rite i1Pro 2 with the dual scan Beta: the dual spot (the lamp reading,
  then the same spot with the UV light, one press).

It has the same signals and methods as ``SpotReadManager``, so the window
does not care which one runs, plus :attr:`reading_conditions` (every
condition of the reading that follows) and a few notes of the dual scan's own.

Before anything is read, an instrument that cannot give the other conditions
(the guess before Start was wrong) ends this session and the window starts
stock spotread instead (:attr:`fallback_requested`), the way step 1 started
spotread again without ``-F``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from core.logger import get_logger

if TYPE_CHECKING:
    from core.argyll_runner import ArgyllRunner

log = get_logger(__name__)

#: the helper's capability word for this mode (``--caps``)
CAPABILITY = "spot_session"

#: conditions-event reasons, before any reading, that mean "this instrument
#: gives no other condition here": the session is handed to stock spotread
FALLBACK_REASONS = ("instrument", "dual_not_available", "dual_no_uv_tables",
                    "dual_high_resolution", "dual_nocal", "mode", "filter")


@dataclass
class HelperSpotParams:
    instrument: str = "1"
    disable_initial_cal: bool = False
    #: the dual scan's own arguments (``workflow.dual_scan.storage.helper_args``)
    #: for an i1Pro 2; empty for an i1Pro 3
    dual_args: "list[str]" = field(default_factory=list)
    #: the condition the person chose (the list shows it first)
    chosen: str = "M0"
    #: tests and the on-screen driver only: the helper's replay instrument
    replay: "Path | None" = None
    helper: "Path | None" = None

    @property
    def dual(self) -> bool:
        return bool(self.dual_args)


def helper_can_spot(helper: "Path | None" = None) -> bool:
    """The bundled helper knows ``--spot-session``. Never raises."""
    try:
        from workflow.chartread_engine import helper_caps, helper_path
        return CAPABILITY in helper_caps(helper or helper_path())
    except Exception:          # noqa: BLE001 - no helper: spotread, as before
        return False


def _triple(v) -> "tuple[float, float, float] | None":
    try:
        t = tuple(float(x) for x in v)
    except (TypeError, ValueError):
        return None
    return t if len(t) == 3 else None    # type: ignore[return-value]


def _spectrum(d) -> "tuple[float, float, list[float]] | None":
    if not isinstance(d, dict):
        return None
    try:
        vals = [float(x) for x in d.get("v", ())]
        return (float(d["short"]), float(d["long"]), vals) if vals else None
    except (KeyError, TypeError, ValueError):
        return None


class HelperSpotManager(QObject):
    reading_ready           = pyqtSignal(tuple, tuple)
    ready_to_read           = pyqtSignal()
    instrument_detected     = pyqtSignal(str)
    calibration_prompt      = pyqtSignal()
    calibration_finished    = pyqtSignal()
    calibration_position_wrong = pyqtSignal()
    misread                 = pyqtSignal()
    sensor_wrong_position   = pyqtSignal()
    no_instrument           = pyqtSignal()
    device_busy             = pyqtSignal()
    instrument_disconnected = pyqtSignal()
    coms_init_failed        = pyqtSignal(str)
    inst_init_failed        = pyqtSignal(str)
    session_ended           = pyqtSignal(int)
    calibration_suspect     = pyqtSignal(object)
    condition_dropped       = pyqtSignal(str)
    #: item 43 steps 2-3: {"M0": (xyz, lab), "M1": ..., "M2": ...} of the
    #: reading whose ``reading_ready`` follows (only the conditions it has)
    reading_conditions      = pyqtSignal(object)
    #: M1 and M2 ended for the rest of this session (a translated sentence);
    #: the readings go on in M0
    conditions_ended        = pyqtSignal(str)
    #: an i1Pro 2 dual spot was refused: the reason id ("uv_spot_failed",
    #: "no_dual_calibration", ...) and whether a new calibration mends it
    dual_spot_refused       = pyqtSignal(str, bool)
    #: a calibration asked for in the session failed (the helper's detail);
    #: nothing is read until a calibration succeeds
    calibration_failed      = pyqtSignal(str)
    #: before anything was read, the instrument gave no other condition:
    #: the window starts stock spotread instead (after session_ended is NOT
    #: emitted for this session)
    fallback_requested      = pyqtSignal()

    def __init__(self, runner: "ArgyllRunner", parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._runner = runner
        from workflow.spot_calibration_check import SpotCalibrationCheck
        self._cal_check = SpotCalibrationCheck()
        self._params: "HelperSpotParams | None" = None
        self._calib_announced = False
        self._prompt_open = False          # a cal_required waits for "ok"
        self._prompt_requested = False     # ... of a calibration asked for
        self._pending_refusal: "tuple[str, bool] | None" = None
        self._filter = ""                  # the filter the driver reads through
        self._after_misread = False
        self._readings = 0
        self._model = ""
        self._conditions_live = False
        self._fallback = False
        self._detached = False
        self._buf = ""

    # ------------------------------------------------------------------
    @property
    def dual(self) -> bool:
        return bool(self._params is not None and self._params.dual)

    @property
    def conditions_live(self) -> bool:
        """The session keeps M0, M1 and M2 of every reading (so far)."""
        return self._conditions_live

    def build_args(self, p: HelperSpotParams) -> "list[str]":
        args = ["--json", "--spot-session", "--spot-conditions"]
        args += list(p.dual_args)
        if p.replay is not None:
            args += ["--replay", str(p.replay)]
        args += ["-c", str(p.instrument)]
        # -N is never passed with the dual scan: a dual spot needs the dual
        # calibration (the window says so); the helper would refuse it too
        if p.disable_initial_cal and not p.dual:
            args.append("-N")
        return args

    def start(self, params: HelperSpotParams,
              on_line: "Callable[[str], None]") -> None:
        from workflow.chartread_engine import helper_path
        helper = params.helper or helper_path()
        args = self.build_args(params)
        self._params = params
        self._calib_announced = False
        self._prompt_open = False
        self._prompt_requested = False
        self._pending_refusal = None
        self._filter = ""
        self._after_misread = False
        self._readings = 0
        self._model = ""
        self._conditions_live = False
        self._fallback = False
        self._cal_check.reset()
        cwd = Path(helper).parent
        log.info("spot read (helper): %s %s", helper, " ".join(args))
        from core.instrument_port import refused_port
        if refused_port(str(helper), args) is not None:
            QTimer.singleShot(0, self._finish_refused_start)
            return
        self._runner.run(
            str(helper), args, cwd,
            on_line=lambda line: self._handle_line(line, on_line),
            on_finish=self._on_finish,
            use_pty=False,              # JSON over plain pipes, as the Measure tab
        )

    def _finish_refused_start(self) -> None:
        self.no_instrument.emit()
        self.session_ended.emit(1)

    def _on_finish(self, code: int) -> None:
        if self._detached:
            return
        if self._fallback:
            self._fallback = False
            log.info("spot read (helper): handing the session to spotread")
            self.fallback_requested.emit()
            return
        self.session_ended.emit(code)

    # --- the window's controls ----------------------------------------
    def _send(self, **cmd) -> None:
        self._runner.write_stdin(json.dumps(cmd) + "\n")

    def take_reading(self) -> None:
        self._after_misread = False
        self._send(cmd="read")

    def request_calibration(self) -> None:
        self._send(cmd="calibrate")

    def send_key(self, key: str = "\r") -> None:
        """spotread's keys, as the window sends them: Return confirms a
        calibration placement (or leaves a misread), Esc ends the session."""
        if key == "\x1b":
            if self._prompt_open and self._prompt_requested:
                # Esc at a calibration asked for cancels only that calibration
                # in the helper; the window means the whole session
                self._send(cmd="cal_cancel")
            self._prompt_open = False
            self._send(cmd="quit")
            return
        if self._prompt_open:
            self._prompt_open = False
            self._send(cmd="ok")
            return
        if self._after_misread:
            # the helper is already waiting for the next press: leaving the
            # misread is the window's own state, and Ready says so
            self._after_misread = False
            self.ready_to_read.emit()

    def quit(self) -> None:
        self._send(cmd="quit")

    def abort(self) -> None:
        self._runner.abort()

    def restart_pending(self) -> bool:
        return False

    def cancel_restart(self) -> None:
        self.session_ended.emit(0)

    def detach(self) -> None:
        self._detached = True
        try:
            self._runner.forget_run_callbacks()
        except Exception:      # noqa: BLE001 - closing must never raise
            log.warning("Could not detach the spot-read session", exc_info=True)

    @property
    def is_running(self) -> bool:
        return self._runner.is_running

    # --- the helper's events ------------------------------------------
    def _handle_line(self, line: str, on_line: "Callable[[str], None]") -> None:
        on_line(line)
        s = line.strip()
        if not s.startswith("{"):
            return
        try:
            ev = json.loads(s)
        except ValueError:
            return
        if isinstance(ev, dict) and "event" in ev:
            self.handle_event(ev)

    def handle_event(self, ev: dict) -> None:
        k = ev.get("event")
        if self._fallback:
            # this session is ending for spotread: nothing it still says is
            # for the window (a calibration window opened now would send its
            # key to the spotread that follows; seen on screen)
            return
        if k == "instrument":
            self._model = str(ev.get("model") or "")
            self.instrument_detected.emit(self._model)
        elif k == "conditions":
            self._on_conditions(ev)
        elif k == "filter":
            self._filter = str(ev.get("filter") or "")
        elif k == "cal_required":
            self._prompt_open = True
            self._prompt_requested = bool(ev.get("requested"))
            if self._calib_announced:
                self.calibration_position_wrong.emit()
            else:
                self._calib_announced = True
                self.calibration_prompt.emit()
        elif k == "cal_result":
            res = ev.get("result")
            self._prompt_open = False
            if res == "done":
                self._cal_check.reset()
            elif res in ("cancelled", "unavailable") and not ev.get("damaged"):
                self._calib_announced = False
            elif res in ("failed",) or ev.get("damaged"):
                self._calib_announced = False
                self.calibration_failed.emit(str(ev.get("detail") or ""))
        elif k == "cal_done":
            self._cal_check.reset()
        elif k == "spot_ready":
            if self._after_misread:
                return                    # the misread stays on screen
            if self._calib_announced:
                self._calib_announced = False
                self.calibration_finished.emit()
            self.ready_to_read.emit()
        elif k == "spot_reading":
            self._on_reading(ev)
        elif k == "dual_pass_result":
            if not ev.get("ok"):
                why = str(ev.get("why") or "")
                log.info("spot read (helper): dual spot refused: %s%s", why,
                         " (calibrate again)" if ev.get("calibrate") else "")
                self._pending_refusal = (why, bool(ev.get("calibrate")))
        elif k == "error":
            self._on_error(ev)

    def _on_conditions(self, ev: dict) -> None:
        if ev.get("active"):
            self._conditions_live = True
            log.info("spot read (helper): every reading keeps M0, M1 and M2%s",
                     " (i1Pro 2 dual spot)" if ev.get("dual") else "")
            return
        why = str(ev.get("why") or "")
        was = self._conditions_live
        self._conditions_live = False
        if not was and self._readings == 0 and why in FALLBACK_REASONS:
            # the instrument gives no other condition here: spotread, as
            # before (nothing has been read)
            log.info("spot read (helper): %s gives no other condition (%s); "
                     "ending this session for spotread", self._model or
                     "the instrument", why)
            self._fallback = True
            self.condition_dropped.emit(self._model)
            self._send(cmd="quit")
            return
        from workflow.dual_scan.session import reason_sentence
        log.info("spot read (helper): M1 and M2 ended for this session (%s); "
                 "M0 goes on", why)
        self.conditions_ended.emit(reason_sentence(why))

    def _on_reading(self, ev: dict) -> None:
        xyz = _triple(ev.get("XYZ"))
        lab = _triple(ev.get("Lab"))
        if xyz is None or lab is None:
            return
        self._readings += 1
        self._after_misread = False
        self._pending_refusal = None
        # M0 is the reading itself, the instrument's own lamp, unless the
        # instrument reads through a filter (a fitted UV-cut filter): then
        # the reading's condition is not known and none is recorded
        plain = self._filter in ("", "none")
        conds = {"M0": (xyz, lab)} if plain else {}
        for c, v in ((ev.get("conditions") or {}) if plain else {}).items():
            cx, cl = _triple((v or {}).get("XYZ")), _triple((v or {}).get("Lab"))
            if c in ("M1", "M2") and cx is not None and cl is not None:
                conds[c] = (cx, cl)
        self.reading_conditions.emit(conds)
        self.reading_ready.emit(xyz, lab)
        # item 41: the calibration is judged on the M0 reading, the lamp's
        verdict = self._cal_check.on_reading(xyz, _spectrum(ev.get("spec")))
        if verdict is not None:
            log.warning("spot read (helper): reading lighter than a print can be "
                        "after this calibration (%s); asking about the calibration",
                        verdict.reason)
            self.calibration_suspect.emit(verdict)

    def _on_error(self, ev: dict) -> None:
        kind = str(ev.get("kind") or "")
        detail = str(ev.get("detail") or "")
        if kind == "misread":
            refusal = self.__dict__.get("_pending_refusal")
            self._pending_refusal = None
            self._after_misread = True
            if refusal:
                self.dual_spot_refused.emit(*refusal)
                return
            self.misread.emit()
            from workflow import spot_calibration_check as SCC
            if SCC.SATURATED_RE.search(detail):
                verdict = self._cal_check.on_saturated()
                if verdict is not None:
                    self.calibration_suspect.emit(verdict)
        elif kind == "coms":
            self.instrument_disconnected.emit()
        elif kind == "no_instrument":
            if detail:
                self.inst_init_failed.emit(detail)
            else:
                self.no_instrument.emit()
        elif kind == "cal_failed":
            self.calibration_failed.emit(detail)
        else:
            log.info("spot read (helper): %s %s", kind, detail)
