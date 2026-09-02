"""Orchestrates chartread for interactive measurement."""
from __future__ import annotations

import re
import shlex
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from core.logger import get_logger
from core.strip_utils import letter_to_idx
from core.i18n import tr

if TYPE_CHECKING:
    from core.argyll_runner import ArgyllRunner

log = get_logger(__name__)

# Regex to detect which strip chartread is currently asking for.
# Handles formats:
#   "Ready to read strip pass A"   (Argyll 3.x default)
#   "Scanning strip 'A01'"
#   "Strip ID: B"
_STRIP_RE = re.compile(
    r"[Ss]trip\s+(?:pass\s+|ID:\s*'?|'?)([A-Za-z]{1,3}\d*)(?:')?(?![A-Za-z0-9])"
)

# The strip menu's own line — "Ready to read strip pass A". Distinct from
# _STRIP_RE, which also matches "Scanning strip" and other progress chatter:
# this one means chartread is sitting at the menu, waiting for a command.
_STRIP_MENU_RE         = re.compile(r"Ready\s+to\s+read\s+strip",                re.IGNORECASE)

_ALL_DONE_RE           = re.compile(r"ALL\s+ROWS\s+READ",                        re.IGNORECASE)
_CALIBRATION_RE        = re.compile(r"Calibration\s+complete",                   re.IGNORECASE)
_CALIBRATION_PROMPT_RE = re.compile(r"Set\s+instrument\s+sensor\s+to\s+calibration\s+position", re.IGNORECASE)
# chartread prints "Strip read failed …" from the shared path even patch by
# patch, but its own unexpected-error line says "Patch read failed due
# unexpected error :'…' (…)" (chartread.c:2278). Matching only "Strip" meant
# the wrong-sensor-position case raised no window at all reading patch by patch
# on stock chartread — Knut, beta.135.
_STRIP_ERROR_RE        = re.compile(r"(?:Strip|Patch)\s+read\s+failed[^(]*\(([^)]+)\)", re.IGNORECASE)
# chartread.c 3.5.0 L1671/L2238: a comms failure mid-strip. Unlike the misread
# and unexpected-error variants it prints no "(reason)" in parentheses, so
# _STRIP_ERROR_RE never matches it — hence this dedicated pattern. The prompt
# ("any other key to retry") returns to the strip menu just like a misread, so
# it routes through the same strip_error signal / dialog (Retry/Skip/Save).
_STRIP_COMS_FAIL_RE    = re.compile(r"Strip\s+read\s+failed\s+due\s+to\s+communication\s+problem", re.IGNORECASE)
_USB_ERROR_RE          = re.compile(r"ReadPipeAsync\s+failed",                   re.IGNORECASE)
_DEVICE_BUSY_RE        = re.compile(r"Device being used",                        re.IGNORECASE)
_NO_INSTRUMENT_RE      = re.compile(r"no instrument detected|no suitable instruments|no instruments connected", re.IGNORECASE)
_WRONG_STRIP_RE        = re.compile(r"Seem to have read strip pass (\w+) rather than (\w+)", re.IGNORECASE)
_UNEXPECTED_RESP_RE    = re.compile(r"unexpected response.*\(DeltaE\s*([\d.]+)\)",            re.IGNORECASE)
#: A successful read, in EITHER of stock chartread's two modes. It prints
#: " Strip read OK" per strip and " Patch read OK" per patch, and matching only
#: the first meant patch-by-patch never recorded that anything had been read
#: (Knut, #130 beta.120). The consequence was severe rather than cosmetic:
#: `has_unsaved_readings` stayed False, so Stop skipped the "keep what you have
#: measured?" window entirely and killed chartread — which holds its readings in
#: memory and writes the .ti3 only on a clean exit. The patches were simply
#: gone, with "[ERROR] Measurement failed" as the only clue.
_STRIP_OK_RE           = re.compile(r"(?:strip|patch)\s+read\s+ok",                          re.IGNORECASE)
#: chartread.c:1644, printed in STRIP mode: "Spot read failed due to the sensor
#: being in the wrong position\n(Sensor should be in surface position)". It says
#: "Spot" whatever the mode, and it carries no "(reason)" on the same line, so
#: neither _STRIP_ERROR_RE nor the ierror pattern sees it. Until beta.136 this
#: pattern was defined and never used, which is why the dial being in the wrong
#: position was silent in strip mode while patch-by-patch got a window
#: (Knut, beta.135).
_SENSOR_POSITION_RE    = re.compile(r"sensor.*wrong\s+position|sensor should be in surface", re.IGNORECASE)
_USB_VM_RE             = re.compile(r"Failed to get piif for USB device",                    re.IGNORECASE)
# chartread asks this when 'd' (done) is pressed with unread patches remaining;
# answering 'y' writes the partial .ti3, 'n' returns to the strip menu.
_ARE_YOU_SURE_RE       = re.compile(r"Are\s+you\s+sure\s+\[y/n\]",                          re.IGNORECASE)

# --- A. Mid-measurement recovery prompts ---------------------------------
# chartread.c 3.5.0 L1608: user hit the instrument switch / Ctrl-C mid-strip.
# The instrument line stock chartread prints under -v. Identical in
# wording to spotread's, verified from Knut's terminal on both tools.
_INST_TYPE_RE      = re.compile(r"Instrument Type:\s*(.+?)\s*$", re.IGNORECASE)
# …and "Spot read stopped at user request!" in patch-by-patch mode, which is
# the same prompt for the same reason. Matching only "Strip" meant the second
# 'q' of Save Partial & Quit was never sent there, so the session sat at
# "Hit Esc or 'q' to give up" until the user pressed q by hand (Knut,
# beta.133, engine + patch-by-patch).
_STRIP_INTERRUPTED_RE  = re.compile(r"(?:Strip|Spot) read stopped at user request", re.IGNORECASE)
# chartread.c 3.5.0 L1593: user pressed 'd' while patches are still unread.
# Captures the "id, loc" payload so we can show the user which patch is missing.
_UNREAD_CONFIRM_RE     = re.compile(r"Done\s*\?\s*-\s*At least one unread patch \(([^)]+)\)", re.IGNORECASE)
# chartread.c 3.5.0 L396: generic ierror() — transient instrument error outside the strip-read fast path.
_GENERIC_IERROR_RE     = re.compile(r"Got\s+'([^']+)'\s*\(([^)]+)\)\s+error\.", re.IGNORECASE)
#: Argyll's `numsup` fatal, as the helper prints it on stderr before exiting:
#: `chromiq-chartread: Error - <sentence>`. It is prose, not a JSON event, so
#: nothing had ever captured it and the reason rendered as "unknown error"
#: (#159). Captured for the reason string only — see `_engine_failure_reason`.
_HELPER_FATAL_RE       = re.compile(r"^\s*\S*chartread\S*\s*:\s*Error\s*[-–]\s*(.+)$",
                                    re.IGNORECASE)

# --- B. Startup / config failure messages --------------------------------
_INIT_COMS_FAIL_RE     = re.compile(r"Establishing communications with instrument failed with message\s+'([^']+)'", re.IGNORECASE)
_INIT_INST_FAIL_RE     = re.compile(r"Initialising instrument failed with message\s+'([^']+)'", re.IGNORECASE)
_CAPABILITY_FAIL_RE    = re.compile(r"Need (reflection|transmission|emissive)\s[^\n]*?reading capability", re.IGNORECASE)
_CCMX_FAIL_RE          = re.compile(
    r"Setting Colorimeter Correction Matrix failed"
    r"|Reading CCMX/CCSS File\s+'[^']+' failed"
    r"|Instrument doesn't have Colorimeter Correction Matrix capability"
    r"|Instrument doesn't have Colorimeter Calibration Spectral Sample capability",
    re.IGNORECASE,
)
_MODE_SET_FAIL_RE      = re.compile(r"Setting instrument mode failed with error\s*:?\s*'([^']+)'", re.IGNORECASE)

# --- B-status. Informational lines surfaced as status-bar messages -------
_INFO_CHART_INST_MISMATCH_RE = re.compile(r"Warning:\s*chart is for\s+(\S+),\s*using instrument\s+(\S+)", re.IGNORECASE)
# Battery level fires at the start of every chartread session on i1Pro and
# Spectro2 — surfacing it would be noisy. Logged via the normal log line, not
# flashed as a status message.
_INFO_BATTERY_RE             = re.compile(r"(?!x)x", re.IGNORECASE)   # disabled
_INFO_NO_SPECTRAL_RE         = re.compile(r"Instrument isn't capable of spectral measurement", re.IGNORECASE)
_INFO_HIGHRES_IGNORED_RE     = re.compile(r"high resolution ignored", re.IGNORECASE)
_INFO_UV_IGNORED_RE          = re.compile(r"UV measurement mode requested, but instrument doesn't support", re.IGNORECASE)
_INFO_SCAN_TOL_IGNORED_RE    = re.compile(r"Modified patch consistency tolerance ignored", re.IGNORECASE)

# --- D. Spot / XY mode defensive handlers --------------------------------
_XY_PLACE_SHEET_RE     = re.compile(r"Please place sheet\s+(\d+)\s+of\s+(\d+)\s+on table", re.IGNORECASE)
_XY_SHEET_OK_RE        = re.compile(r"Sheet\s+(\d+)\s+of\s+(\d+)\s+read OK", re.IGNORECASE)
_SPOT_READY_RE         = re.compile(r"Ready to read patch\s+'([^']+)'", re.IGNORECASE)
_ABORT_CONFIRM_RE      = re.compile(r"Abort\s*\?\s*-\s*Are you sure\s*\?\s*\[y/n\]", re.IGNORECASE)
_PATCH_NOT_FOUND_RE    = re.compile(r"Patch\s+'([^']+)'\s+not found", re.IGNORECASE)


def _instrument_text(raw: object) -> str:
    """An instrument-supplied instruction, or ``""`` when it isn't real text.

    chartread's calibration call fills a "condition identifier" buffer that is
    only meaningful for some conditions — stock Argyll prints it solely for
    ``inst_calc_message``. The engine helper serialises it either way, so for a
    condition that carries no identifier the buffer is whatever was on the stack:
    a real ColorMunki asking for its calibration position sends
    ``"4k2\\ufffd\\u0001"``. Showing that to someone is worse than showing
    nothing, so anything that doesn't look like a human sentence is dropped and
    the dialog falls back to its own wording.
    """
    text = str(raw or "").strip()
    if len(text) < 4:                       # too short to be an instruction
        return ""
    if "�" in text:                    # arrived as undecodable bytes
        return ""
    if any(ch != "\n" and ch != "\t" and not ch.isprintable() for ch in text):
        return ""
    if not any(ch.isalpha() for ch in text):
        return ""
    return text


# Automatic calibration retries (mavtop). An ageing bus-powered instrument can
# fail its calibration simply because the lamp strike browses out the USB rail,
# then succeed moments later — retrying costs seconds and often gets the user
# through. Also load-bearing: the engine BLOCKS waiting for an answer after a
# failed calibration, so something must always reply or the run deadlocks.
CAL_AUTO_RETRIES = 3            # attempts after the first = 4 tries in total
CAL_RETRY_PAUSE_MS = 2000       # let a sagging USB rail recover before retrying
CAL_AUTO_RETRIES_MAX = 20       # ceiling on the user-set count, so it can't loop


@dataclass
class MeasureParams:
    ti1_path: Path
    instrument: str = "1"
    disable_bidir: bool = False
    force_bidir: bool = False
    suppress_warnings: bool = True
    disable_initial_cal: bool = False
    patch_by_patch: bool = False
    high_res: bool = False
    resume: bool = False
    extra_args: str = ""
    # ChromIQ chart-reading engine (#126). When set, `engine_helper` is the
    # absolute path of the chromiq-chartread binary and chartread's console
    # is replaced by the JSON event/command protocol. Patch-by-patch mode
    # always uses stock chartread (the engine covers strip reading only).
    engine_helper: Path | None = None
    # Dev/testing: replay script path — no instrument needed.
    engine_replay: Path | None = None
    # Opt-in misalignment safety net (#50): pass --safenet to the helper so it
    # warns when a strip would fit dramatically better shifted by a patch.
    engine_safenet: bool = False
    # Opt-in (Settings → Beta): let the engine drive XY (SpectroScan) and chart
    # (i1iSis/DTP70) reading too. Off by default → those modes fall back to
    # stock chartread. Passed as --xychart.
    engine_xy_chart: bool = False
    # How many times to retry a failed calibration automatically before giving
    # up (mavtop's i1Pro1 lamp can need several strikes to burn in). Falls back
    # to CAL_AUTO_RETRIES when the caller doesn't set it.
    cal_auto_retries: int | None = None
    #: This chart names an instrument that stock ArgyllCMS chartread REFUSES
    #: outright (#159, the CR30: `inst_enum()` returns `instUnknown`, so it
    #: errors with "Unrecognised chart target instrument" before the first
    #: patch). Every engine→stock fallback below is therefore guaranteed to
    #: fail, and it fails with a more confusing message than the one the user
    #: already had. Set by the tab from the CHART, never from a preference or a
    #: connected device — see `TabMeasure._chart_is_cr30`.
    stock_reader_cannot_read: bool = False
    #: ChromIQ supplies the readings itself over its own transport, so the
    #: helper opens NO instrument and takes its values from the JSON command
    #: channel (#159, the CR30). Sent as `-xx` — XYZ, because `workflow/cr30`
    #: produces XYZ and `-xl` would make the helper run icmLab2XYZ over a
    #: conversion ChromIQ had already done.
    external_values: bool = False


class MeasureManager(QObject):
    stripe_changed         = pyqtSignal(str)  # emits strip ID string e.g. "A01"
    all_stripes_done       = pyqtSignal()    # emitted when chartread reports all rows read
    # Emitted when the instrument asks to be calibrated, carrying what it
    # actually asked for: (condition, the instrument's own instruction, optional).
    # The engine reports all three; stock chartread only has the bare prompt, so
    # it sends ("", "", False) and the dialog falls back to its own wording.
    calibration_prompt     = pyqtSignal(str, str, bool)
    # The engine could not use the instrument, so the run was restarted on stock
    # ArgyllCMS chartread. Carries the reason, for the log/status line.
    engine_fell_back       = pyqtSignal(str)
    # Like engine_fell_back, but the engine had ALREADY measured part of the
    # chart when it failed (#134): the run continues on stock chartread
    # RESUMING from the autosaved .ti3 (-r), so nothing measured is lost.
    # Carries the reason, for a reassuring status line.
    engine_fell_back_resumed = pyqtSignal(str)
    # #159: the engine run failed AND the chart names an instrument stock
    # ArgyllCMS chartread refuses outright, so there is no fallback to make.
    # The run ends here; this carries the reason so the tab can say the ONE
    # true thing instead of promising a rescue that cannot happen.
    engine_fallback_refused = pyqtSignal(str)
    # A failed calibration is being retried automatically: (attempt, of_total).
    calibration_retrying   = pyqtSignal(int, int)
    calibration_done       = pyqtSignal()    # emitted when instrument calibration completes
    strip_error            = pyqtSignal(str) # emitted on strip read failure; carries the reason string
    instrument_disconnected = pyqtSignal()   # emitted on USB communication failure
    device_busy             = pyqtSignal()   # emitted when instrument is held by another process
    no_instrument           = pyqtSignal()     # emitted when no instrument is detected at startup
    wrong_strip             = pyqtSignal(str, str)  # (read_strip, expected_strip)
    unexpected_response     = pyqtSignal(str)       # carries the DeltaE value string
    # #50 safety net: (strip, offset, base_de_str, best_de_str)
    strip_misaligned        = pyqtSignal(str, int, str, str)
    sensor_wrong_position   = pyqtSignal()          # emitted when instrument is in calibration position during scan
    usb_claimed_by_vm       = pyqtSignal()          # emitted when USB device is held exclusively by a VM

    # A. Mid-measurement recovery prompts
    strip_interrupted          = pyqtSignal()       # chartread reports the strip read was interrupted by user
    unread_confirm             = pyqtSignal(str)    # user pressed 'd' with unread patches; carries "id, loc"
    generic_instrument_error   = pyqtSignal(str, str)  # (friendly_msg, technical_detail) from ierror()

    # B. Startup / config failures (terminal — chartread exits)
    coms_init_failed           = pyqtSignal(str)    # serial/USB init failed
    inst_init_failed           = pyqtSignal(str)    # init_inst() failed
    instrument_wrong_type      = pyqtSignal(str)    # instrument can't do reflection/transmission/emissive as needed
    ccmx_load_failed           = pyqtSignal(str)    # CCMX/CCSS load failed
    mode_set_failed            = pyqtSignal(str)    # setting instrument mode failed

    # B-status. Non-blocking informational messages
    info_message               = pyqtSignal(str, str)  # (category, text)

    # D. Spot / XY mode (defensive coverage — won't fire in strip mode)
    xy_place_sheet             = pyqtSignal(int, int)  # (sheet_n, total_sheets)
    spot_ready                 = pyqtSignal(str)       # patch id
    abort_confirm              = pyqtSignal()

    # E. ChromIQ chart-reading engine (#126) — only fire when the engine is
    # active; the stock chartread path never emits them.
    session_map                = pyqtSignal(list)      # [{strip, sheet, read, verifiable}, …]
    strip_measured             = pyqtSignal(dict)      # full strip_read event payload
    #: the instrument fired — the swipe begins now (#131). In strip mode the
    #: instrument hands back the whole strip at once, so this and strip_measured
    #: are the only two moments from which reading pace can be judged at all.
    scan_started               = pyqtSignal()
    #: the model the instrument reported when it was opened, e.g.
    #: "X-Rite i1 Pro2" — Argyll distinguishes the i1Pro generations, which a
    #: chart's TARGET_INSTRUMENT does not (#131 Phase 2)
    instrument_detected        = pyqtSignal(str)
    readings_saved             = pyqtSignal(str, int)  # (.ti3 path, patches on disk)
    # Engine spot (patch-by-patch) mode: the patch to read next, and a patch's
    # measured result — the single-patch analogues of stripe_changed/strip_measured.
    patch_ready                = pyqtSignal(dict)      # {id, loc, read, all_done, exyz}
    patch_measured             = pyqtSignal(dict)      # {id, loc, xyz, exyz, de}
    # XY/chart modes read many patches at once: {patches:[…]} — whole chart or
    # one XY sheet. `chart_reading` announces an autonomous chart read is running.
    chart_measured             = pyqtSignal(dict)      # {patches:[…]}
    chart_reading              = pyqtSignal()          # autonomous whole-chart read started

    def __init__(self, runner: "ArgyllRunner", parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._runner         = runner
        self._is_resume:     bool = False
        #: whether a strip has been read in THIS session. On a resume the chart
        #: is already complete, so chartread reports "all done" the moment it
        #: offers the strip menu — and the completion window came up before the
        #: user had re-read anything (Knut, #131 2026-07-27).
        self._read_something: bool = False
        #: How many patches this session has read — see readings_this_session.
        self._readings_count: int = 0
        self._spot_mode: bool = False
        #: whether every strip already held a reading when the session opened.
        self._chart_was_complete: bool = False
        #: Strips read during THIS session, and the chart's full strip list, so
        #: a complete re-measurement can be told from a single-strip touch-up.
        #: Defaulted here as well as per run: the manager is driven directly by
        #: tests (and by the stock path) without going through `start`.
        self._strips_read_this_session: set = set()
        self._session_strips: list = []
        self._guided_strips: list[str] = []
        self._guided_menu_pending: bool = False
        self._guided_idx:    int  = 0
        # "disabled" until strips are actually given: everywhere else the rule
        # is "idle if there are strips, else disabled", and an "idle" default
        # with no strips would index an empty list on the first strip event.
        self._guided_state:  str  = "disabled"   # | "idle" | "navigating" | "waiting"
        self._guided_on_line: "Callable[[str], None] | None" = None
        # Queued key dispatched once chartread returns to the strip menu after
        # a misread retry — see send_post_retry_key().
        self._pending_post_retry_key: str | None = None
        #: True while the wrong-dial-position window is on screen, so the
        #: two lines chartread prints for it raise one window, not two.
        self._sensor_warning_open: bool = False
        #: Whether this session has seen its first spot_ready yet — the
        #: event that says whether the chart was already complete.
        self._saw_spot_ready: bool = False
        #: True once an ending has been answered, so the second form of the
        #: give-up prompt cannot re-ask about an ending already decided.
        self._ending_already_answered: bool = False
        #: The user chose to stop from a failure window and the key has
        #: gone out. Strip mode may need a second one — see
        #: `mark_stop_requested`.
        self._stop_requested: bool = False
        # True while the helper is blocked on a failure prompt ("Hit Esc or 'q'
        # to give up, any other key to retry"). Whatever we send there is spent
        # as that "any other key", so a navigation command sent while this is
        # True never navigates — it retries. skip_current_strip() branches on
        # it; see that docstring for Knut's log (#131, 2026-07-28).
        self._at_retry_prompt: bool = False
        # True while the reader is blocked on its OWN "Done ? - At least one
        # unread patch (…), Are you sure [y/n]" prompt, raised because the USER
        # pressed 'd'. It is not a retry prompt and it is not the menu: the only
        # key that saves from here is 'y', and every other key returns to the
        # read loop having saved nothing. `send_save_partial_and_quit` has to
        # know, because the sequence it would otherwise send waits for a prompt
        # that has already been printed and will never be printed again.
        self._at_unread_prompt: bool = False
        # Two-step state for "Save Partial & Quit" from the misread dialog:
        #   None             — idle
        self._save_partial_state: str | None = None
        # ChromIQ chart-reading engine (#126): True while a --json helper
        # session is running; send_key() then translates keys to commands.
        self._engine_active: bool = False
        # True while the run supplies its own values (chartread -x) rather than
        # opening an instrument. The two are independent: the CR30 is read by
        # ChromIQ and handed to the engine helper, so both are set at once.
        # It decides how a partial read is saved — see save_partial_and_quit().
        self._external_values: bool = False
        # Engine → stock-chartread safety net (#126, mavtop): the instrument
        # failure the engine reported, whether it ever read anything, whether
        # the user stopped it, and whether we already retried once.
        self._engine_fatal: str | None = None
        self._engine_error_prose: "str | None" = None
        self._stock_reader_cannot_read: bool = False
        self._engine_progress: bool = False
        self._engine_saw_event: bool = False
        self._engine_fallback_used: bool = False
        self._engine_mode_fallback: bool = False
        self._user_quit: bool = False
        self._cal_auto_retries: int = CAL_AUTO_RETRIES
        self._cal_retries_left: int = CAL_AUTO_RETRIES

    # ------------------------------------------------------------------

    def start(
        self,
        params: MeasureParams,
        on_line: Callable[[str], None],
        on_finish: Callable[[int], None],
    ) -> None:
        args = self._build_args(params)
        cwd  = params.ti1_path.parent
        self._is_resume      = params.resume
        self._read_something = False
        self._readings_count = 0
        #: patch-by-patch (spot) reading, which answers keys differently — see
        #: :meth:`skip_current_strip`.
        self._spot_mode      = bool(params.patch_by_patch)
        self._chart_was_complete = False
        #: Strips this session has actually read, and the chart's full
        #: strip list, so a re-measurement can be told from a touch-up.
        self._strips_read_this_session: set = set()
        self._session_strips: list = []
        self._guided_on_line = on_line
        # Reset guided state for this run
        self._guided_idx   = 0
        self._guided_state = "idle" if self._guided_strips else "disabled"
        #: chartread has re-announced the strip we are waiting on, so its
        #: menu is already up and no further event is coming.
        self._guided_menu_pending = False
        # The engine now covers patch-by-patch (spot) mode too — the spot loop
        # speaks the same JSON protocol as the strip loop (#126 follow-up).
        self._engine_active = params.engine_helper is not None
        #: External values (-x): ChromIQ reads the instrument itself and the
        #: helper opens none. Kept because the SAVE-AND-STOP path differs — see
        #: `save_partial_and_quit`.
        self._external_values = bool(getattr(params, "external_values", False))
        # Engine → stock-chartread safety net (#126, mavtop). Reset per run.
        self._engine_fatal = None
        self._engine_progress = False
        self._engine_saw_event = False
        self._engine_fallback_used = False
        self._engine_mode_fallback = False
        #: #159: stock chartread cannot read THIS chart, so no fallback to it
        #: may happen — see :attr:`MeasureParams.stock_reader_cannot_read`.
        self._stock_reader_cannot_read = bool(params.stock_reader_cannot_read)
        #: The helper's own last error sentence, printed as PROSE on stderr and
        #: outside the JSON channel. Nothing captured it, which is why the log
        #: said "(unknown error)" while the helper had said exactly what was
        #: wrong. Used ONLY for the reason string — never to decide a fallback,
        #: because `_engine_fatal is not None` is a fallback trigger and this
        #: must not change behaviour for any other instrument.
        self._engine_error_prose = None
        self._user_quit = False
        # The user can raise this for an ageing instrument (Settings → Beta);
        # clamp so a bad value can't disable retries or loop for ever.
        want = params.cal_auto_retries
        self._cal_auto_retries = (CAL_AUTO_RETRIES if want is None
                                  else max(0, min(int(want), CAL_AUTO_RETRIES_MAX)))
        self._cal_retries_left = self._cal_auto_retries

        def _on_finish(code: int) -> None:
            self._pending_post_retry_key = None
            self._at_retry_prompt = False
            self._at_unread_prompt = False
            self._save_partial_state = None
            was_engine = self._engine_active
            self._engine_active = False
            if (was_engine and self._engine_mode_fallback
                    and not self._stock_reader_cannot_read):
                # XY/chart mode with the engine opt-in off: silently re-run on
                # stock chartread (over a PTY, where those modes' console
                # prompts work). Not an error — no scary wording.
                self._engine_fallback_used = True
                on_line(tr("[Engine] This instrument reads whole sheets; "
                           "using ArgyllCMS chartread for it."))
                self._launch_stock(
                    self._without_resume_when_nothing_to_resume(
                        args, params.ti1_path), cwd, on_line, _on_finish)
                return
            if was_engine and not self._stock_reader_cannot_read:
                partial = self._resumable_partial_ti3(params.ti1_path)
                if partial is not None and self._engine_should_resume_fallback(code):
                    # The instrument failed PARTWAY through the chart, but the
                    # strips already read are saved on disk (#134). Continue on
                    # stock chartread resuming from that .ti3 (-r) instead of
                    # discarding the session — after backing the file up first,
                    # so the readings survive even if the resume misbehaves.
                    self._engine_fallback_used = True
                    reason = self._engine_fatal or "unknown error"
                    log.warning("engine failed mid-measurement (%s) — resuming "
                                "on stock chartread with -r", reason)
                    self._backup_partial_ti3(partial)
                    resume_args = args if "-r" in args else ["-r", *args]
                    on_line(tr(
                        "[Engine] ChromIQ's own measuring engine ran into a "
                        "problem with your instrument ({reason}) partway through "
                        "the chart. Don't worry — every strip you have already "
                        "measured has been saved and will be kept. ChromIQ is "
                        "now switching to ArgyllCMS's chartread and continuing "
                        "from exactly where you left off, so just carry on "
                        "measuring the remaining strips as usual. If this keeps "
                        "happening, you can turn the ChromIQ engine off for good "
                        "in Preferences."
                    ).format(reason=reason))
                    self.engine_fell_back_resumed.emit(reason)
                    self._launch_stock(resume_args, cwd, on_line, _on_finish)
                    return
            if (was_engine and self._stock_reader_cannot_read
                    and code != 0 and not self._user_quit):
                # #159. Stock chartread refuses this chart's TARGET_INSTRUMENT
                # before the first patch, so all three fallbacks below can only
                # replace one failure with a second, more confusing one — and
                # the resume path promises "every strip you have already
                # measured has been saved and will be kept" on its way there.
                # End on the helper's own exit and say the true thing once.
                reason = self._engine_failure_reason()
                log.warning("the chart's instrument is one stock chartread "
                            "cannot read (%s) — not falling back", reason)
                self.engine_fallback_refused.emit(reason)
                on_finish(code)
                return
            if was_engine and self._engine_should_fall_back(code):
                self._engine_fallback_used = True
                reason = self._engine_fatal or "unknown error"
                log.warning("engine could not use the instrument (%s) — "
                            "restarting on stock chartread", reason)
                on_line(tr(
                    "[Engine] ChromIQ's own measuring engine could not use your "
                    "instrument ({reason}). Starting again with ArgyllCMS's "
                    "chartread instead — just carry on measuring as usual."
                ).format(reason=reason))
                self.engine_fell_back.emit(reason)
                # This is the path Knut's log took at 19:09 (#148): the engine
                # refused the missing resume file, and the fallback re-launched
                # with the same -r and failed identically.
                self._launch_stock(
                    self._without_resume_when_nothing_to_resume(
                        args, params.ti1_path), cwd, on_line, _on_finish)
                return
            on_finish(code)

        if self._engine_active:
            eargs = ["--json"]
            if params.engine_safenet:
                eargs += ["--safenet"]
            if params.engine_xy_chart:
                eargs += ["--xychart"]
            if params.engine_replay is not None:
                eargs += ["--replay", str(params.engine_replay)]
            eargs += args
            log.info("chromiq-chartread: %s  [cwd=%s]", " ".join(eargs), cwd)
            self._runner.run(
                str(params.engine_helper),
                eargs,
                cwd,
                on_line=lambda line: self._handle_engine_line(line, on_line),
                on_finish=_on_finish,
                use_pty=False,          # JSON over plain pipes — no PTY
            )
            return

        self._launch_stock(args, cwd, on_line, _on_finish)

    def _launch_stock(self, args: list[str], cwd: Path,
                      on_line: Callable[[str], None],
                      on_finish: Callable[[int], None]) -> None:
        """Run stock ArgyllCMS chartread over a PTY (the classic console path).

        Chaining this from inside a finished-callback is safe: ArgyllRunner
        captures the per-run callbacks before invoking them, precisely so a
        follow-on run can register its own (same pattern as targen→printtarg)."""
        log.info("chartread: %s  [cwd=%s]", " ".join(args), cwd)
        self._runner.run(
            "chartread",
            args,
            cwd,
            on_line=lambda line: self._handle_line(line, on_line),
            on_finish=on_finish,
            use_pty=True,
        )

    def _handle_cal_failed(self, detail: str,
                           on_line: Callable[[str], None]) -> None:
        """Answer the engine after a failed calibration, retrying a few times.

        The engine blocks waiting for a reply here (``cq_wait_char``), so this
        must ALWAYS send something — otherwise the run deadlocks: the helper
        waits for a key that never comes, and the failure dialog never appears
        because it only runs once the process has exited.

        Why retry at all: an ageing bus-powered instrument can fail calibration
        because the lamp strike momentarily browns out the USB rail, and succeed
        seconds later (mavtop's i1Pro1 passes roughly one attempt in four). A few
        automatic attempts turn that from a dead end into a short pause. Once the
        attempts are used up the failure is reported as before, and quitting lets
        the run end so the stock-chartread fallback can still take over."""
        if not self._engine_active or self._user_quit:
            self.inst_init_failed.emit(detail)
            return

        if self._cal_retries_left <= 0:
            log.warning("calibration failed after %d attempts: %s",
                        self._cal_auto_retries + 1, detail or "unknown")
            on_line(tr(
                "[Engine] Calibration did not succeed after {total} attempts. "
                "Stopping here so you can check the instrument."
            ).format(total=self._cal_auto_retries + 1))
            self.inst_init_failed.emit(detail)
            # Sent as a COMMAND, not a key: this is our decision, not the user's,
            # so it must not mark the run as user-aborted — that flag would stop
            # the stock-chartread fallback from getting its turn.
            self.send_command({"cmd": "quit"})
            return

        self._cal_retries_left -= 1
        attempt = self._cal_auto_retries - self._cal_retries_left
        log.info("calibration failed (%s) — automatic retry %d/%d",
                 detail or "unknown", attempt, self._cal_auto_retries)
        on_line(tr(
            "[Engine] Calibration didn't succeed ({detail}). Trying again "
            "automatically — attempt {attempt} of {total}. Leave the instrument "
            "where it is."
        ).format(detail=detail or tr("no reason given"),
                 attempt=attempt, total=self._cal_auto_retries))
        self.calibration_retrying.emit(attempt, CAL_AUTO_RETRIES)
        # A pause gives a sagging USB rail time to recover; a single-shot timer
        # keeps the UI responsive instead of blocking on a sleep.
        QTimer.singleShot(CAL_RETRY_PAUSE_MS, self._send_cal_retry)

    def _send_cal_retry(self) -> None:
        """Tell the engine to try the calibration again, unless the run ended."""
        if not self._engine_active or self._user_quit:
            return
        self.send_command({"cmd": "retry"})

    def _engine_failure_reason(self) -> str:
        """The most informative reason available for a failed engine run.

        `_engine_fatal` is only ever set from a typed JSON event, so a helper
        that dies before it emits one leaves it `None` and the log said
        "(unknown error)" — which is what Basti saw on 2026-08-28 while the
        helper had printed a perfectly clear sentence on stderr one line above
        (`chromiq-chartread: Error - The chart was made for 'CR30' …`). That
        text does reach Python: `_handle_engine_line` reads it as prose. So
        capture it and fall back to it here.

        NOT folded into `_engine_fatal`: that attribute is a fallback TRIGGER
        (`_engine_should_fall_back`, `_engine_should_resume_fallback` both test
        `is not None`), and setting it from prose would change the fallback
        behaviour of every instrument. This is presentation only.

        A cleaner fix belongs on the C side — a typed
        `{"event":"error","kind":"chart_refused"}` before the `error()` call —
        and is requested in `docs/cr30_reports/09-impl-measure.md`.
        """
        return (self._engine_fatal
                or self._engine_error_prose
                or "unknown error")

    def _engine_should_fall_back(self, code: int) -> bool:
        """Whether a finished engine run should be retried on stock chartread.

        Only when the engine reported an instrument-level failure and never got
        as far as reading anything: restarting then costs the user nothing and
        rescues instruments the engine can't drive but Argyll can (mavtop's
        i1Pro1, which measures fine under stock chartread and spotread).

        A helper that never spoke at all counts too: if it exits non-zero
        without emitting a single event it never really ran (missing execute
        permission, macOS quarantine, an immediate crash), and stock chartread
        is exactly the right thing to try instead.

        Deliberately NOT retried when the user stopped the run themselves, when
        any reading was already taken (a restart would discard or duplicate it),
        or when a fallback has already been tried — a failing instrument must
        never put us in a restart loop."""
        if code == 0 or self._engine_progress or self._user_quit:
            return False
        if self._engine_fallback_used:
            return False
        return self._engine_fatal is not None or not self._engine_saw_event

    def _resumable_partial_ti3(self, ti1_path: Path) -> Path | None:
        """The engine's autosaved measurement for this chart, if there is one to
        resume from (#134).

        The engine saves readings to ``<stem>.ti3`` as it goes, so if the
        instrument fails partway through, that file holds the strips already
        measured — exactly what stock chartread ``-r`` reads to continue. Returns
        the path only when the file holds at least one readable reading;
        otherwise ``None`` (nothing safe to resume, so the run is handled the
        ordinary way).

        **"Non-empty" is not the same as "resumable".** This used to accept any
        file of non-zero size, and a `.ti3` that carries only a CGATS header is
        several hundred bytes of exactly that — no ``BEGIN_DATA``, no rows, and
        nothing for ``-r`` to continue from. Specification §3a puts that file in
        the *header only* row: *"no measurements — treat as empty"*, giving
        ``C₀ = 0``. The test is now
        :func:`workflow.measurement_state.has_any_readings`, so a fallback can no
        longer hand stock chartread a file it will refuse.

        **Not the stricter `can_resume`, on purpose.** That one implements §3a for
        the user's Refine / resume tick, where a corrupt file must never be
        resumed. Here a refusal throws away strips the user has already measured,
        which is the one thing this rescue exists to prevent — so a damaged
        autosave, exactly what a crash is most likely to leave behind, is still
        handed to chartread rather than abandoned.
        """
        from workflow.measurement_state import has_any_readings
        ti3 = ti1_path.with_suffix(".ti3")
        try:
            if has_any_readings(ti3):
                return ti3
        except OSError:
            pass
        return None

    def _without_resume_when_nothing_to_resume(
            self, args: list, ti1_path: Path) -> list:
        """*args* with ``-r`` removed when there is nothing to resume from.

        Belt and braces for the fallback paths. The flag is already withheld at
        source (the Measure tab asks §3a before setting it), but a fallback
        re-launches with whatever the engine was given — and Knut's log shows
        both readers failing on the same missing file, one after the other,
        because the second inherited the first's flag. Anything that re-launches
        should re-check rather than trust the arguments it was handed.
        """
        if "-r" not in args:
            return args
        try:
            if self._resumable_partial_ti3(ti1_path) is not None:
                return args
        except Exception:      # noqa: BLE001 — never block a fallback
            return args
        log.info("dropping -r for the fallback: nothing to resume from")
        return [a for a in args if a != "-r"]

    def _engine_should_resume_fallback(self, code: int) -> bool:
        """Whether a failed engine run that ALREADY read part of the chart should
        continue on stock chartread, resuming from the autosaved .ti3 (#134).

        The mirror of :meth:`_engine_should_fall_back` for the with-progress
        case: the instrument died mid-chart, but the strips already measured are
        on disk, so ArgyllCMS's chartread can pick up where the engine left off
        (``-r``) instead of throwing the whole session away. Caller also checks a
        resumable .ti3 actually exists.

        Never when the run exited cleanly, when the user stopped it themselves
        (a restart would fight a deliberate quit), or when a fallback has already
        happened (no restart loops). Requires a real instrument-level failure —
        an ordinary non-zero exit after normal reading is the run's own business,
        not something to silently retry."""
        if code == 0 or self._user_quit or self._engine_fallback_used:
            return False
        return self._engine_fatal is not None and self._engine_progress

    def _backup_partial_ti3(self, ti3: Path) -> None:
        """Copy the engine's partial measurement aside before handing it to stock
        chartread ``-r`` (#134), so the readings are recoverable even if the
        resume misbehaves — the user's measurements must never be lost.

        Best-effort: a failed copy is logged but must not stop the fallback, or a
        full/read-only disk would turn a recoverable hiccup into a dead end."""
        try:
            # The same name core.file_manager.Run.partial_ti3 answers with, so
            # the run knows about this file and can archive or offer it back.
            backup = ti3.parent / (ti3.name + ".engine-partial")
            shutil.copy2(ti3, backup)
            log.info("backed up engine partial measurement to %s", backup)
        except OSError as e:
            log.warning("could not back up engine partial %s: %s", ti3, e)

    def set_guided_strips(self, strips: list[str]) -> None:
        """Configure strips to auto-navigate during the next measurement run."""
        self._guided_strips = list(strips)
        self._guided_idx    = 0
        self._guided_state  = "idle" if strips else "disabled"

    def mark_stop_requested(self) -> None:
        """Record that the user has chosen to stop and the key has gone out.

        In strip mode one key is not always enough — see the ``strip_interrupted``
        branch, which is where this is spent. Cleared at every session start, so
        a stop chosen in one session can never leak into the next.
        """
        self._stop_requested = True

    def mark_ending_answered(self) -> None:
        """Record that the user has already answered how this session ends.

        The reader reports an interruption in its own words a moment after the
        key that caused it — as an event in strip mode and as a printed line in
        patch-by-patch. Without this, a Give Up answered in a failure window
        was followed by "Strip Read Interrupted" asking about the very same
        ending (Knut, beta.141).
        """
        self._ending_already_answered = True

    def send_key(self, key: str) -> None:
        """Send a keystroke to the running chartread process.

        With the engine active the key is translated to its JSON command —
        same semantics, so every existing call site works on both paths."""
        if key in ("q", "Q", "\x1b"):
            # A deliberate stop, so a non-zero exit must not look like an engine
            # failure worth retrying on stock chartread.
            self._user_quit = True
        if self._engine_active:
            from workflow.chartread_engine import (command_for_key,
                                                   repeated_command_for_key)
            cmd = command_for_key(key)
            if cmd is not None:
                self.send_command(cmd)
                return
            # 'F' / 'B' move ten at a time. The helper's vocabulary has only
            # single steps, so ten of those go out instead — the same movement.
            repeated = repeated_command_for_key(key)
            if repeated is not None:
                cmd, times = repeated
                for _ in range(times):
                    self.send_command(cmd)
                return
            log.warning("engine: no command mapping for key %r", key)
            return
        self._at_unread_prompt = False       # see send_command
        self._runner.write_stdin(key)

    def send_command(self, cmd: dict) -> None:
        """Send a raw JSON command to the engine (engine mode only)."""
        import json as _json
        # ONE CHARACTER ENDS THE UNREAD PROMPT, WHATEVER IT IS.
        #
        # The reader is blocked in a single `cq_wait_char` / `next_con_char`
        # there, so the first thing sent — a navigation key the user typed, a
        # goto, our own 'y' — is consumed by the prompt and the reader moves
        # on. Clearing here (and in send_key, which routes through this on the
        # engine) means the flag can never outlive the prompt it describes.
        self._at_unread_prompt = False
        self._runner.write_stdin(_json.dumps(cmd) + "\n")

    def goto_strip(self, strip: str) -> None:
        """Jump the engine directly to `strip` (engine mode only)."""
        if self._engine_active:
            self.send_command({"cmd": "goto", "strip": strip})

    def goto_patch(self, loc: str) -> None:
        """Jump the engine directly to patch `loc` in spot mode (engine only)."""
        if self._engine_active:
            self.send_command({"cmd": "goto", "patch": loc})

    @property
    def engine_active(self) -> bool:
        return self._engine_active

    def send_post_retry_key(self, key: str) -> None:
        """Acknowledge a misread and queue *key* for the strip menu that follows.

        **The two steps are both necessary, on the engine as much as on stock
        chartread**, and this was verified against the real helper binary rather
        than reasoned about (Knut, #131 2026-07-27, after two failed attempts):

        =========================  ==========================================
        sent at the retry prompt   what the strip menu does next
        =========================  ==========================================
        ``forward`` alone          nothing — the SAME strip is re-armed
        ``ok`` then ``forward``    moves on to the next strip
        =========================  ==========================================

        The reason is in the helper: after a failed strip it waits in
        ``cq_prompt_char()``, where **any key that is not Esc/q means "retry"**.
        A navigation command sent there is simply spent as that "any key" — so
        it reads as retry and the strip never changes. The acknowledgement has
        to be spent on the prompt first; only then is the menu listening.
        """
        self._pending_post_retry_key = key
        if self._engine_active:
            self.send_command({"cmd": "ok"})
            return
        self._runner.write_stdin("\r")

    def skip_current_strip(self) -> None:
        """Leave the strip that just failed and move on to the next one.

        **"Next unread" is the wrong instruction here**, which is why two
        earlier attempts at this failed: a strip that has just FAILED is itself
        still unread, so "go to the next unread strip" lands back on the strip
        you are trying to leave. On a chart that is already complete it has
        nowhere to go at all. "Forward" is what "skip this one" means, and it is
        right in both cases — confirmed against the real helper.

        **Patch by patch has both cases, and that is what beta.74 got wrong.**
        It is not "spot mode never sits at a retry prompt" — Knut's hardware log
        (#131, 2026-07-28) shows it doing exactly that, and shows why Skip then
        did nothing::

            Patch read failed … 'Wrong Sensor Position'
            Hit Esc or 'q' to give up, any other key to retry:
            send_key '{"cmd": "forward"}'
            {"event":"spot_ready","id":"25","loc":"A5"}     ← the SAME patch

        The ``forward`` was spent as the prompt's "any other key", i.e. as
        *retry*, and the helper looped straight back onto A5. So the real
        distinction is **not** strip vs patch, it is *"is a retry prompt open
        right now"* — and in patch mode both answers happen:

        =============================  =========================================
        where Skip is pressed          what has to be sent
        =============================  =========================================
        at the patch menu (no window)  ``forward`` — moves on, as Knut confirms
        at a failure window            ``retry`` first, then ``forward``
        =============================  =========================================

        The acknowledgement here is ``retry`` (the letter ``r``) and **not**
        ``ok``: ``ok`` is Return, and if it ever reached the patch menu instead
        of the prompt it would *read the patch* rather than acknowledge
        anything. ``r`` means "any other key" at the prompt and is inert at the
        menu, so it is safe whichever one is listening.
        """
        if self._engine_active and self._spot_mode:
            if self._at_retry_prompt:
                self._pending_post_retry_key = "f"
                self.send_command({"cmd": "retry"})
            else:
                self.send_command({"cmd": "forward"})
            return
        self.send_post_retry_key("f")

    def note_app_quitting(self) -> None:
        """The application is closing. Treat the ending as deliberate.

        `ArgyllRunner.cleanup()` kills the helper during shutdown, and
        `waitForFinished` then delivers `finished` synchronously — so this
        session's finish handler runs while the window is closing, with exit
        code 9 (SIGKILL) and no idea why.

        Without this the owner saw, on every quit:

            the chart's instrument is one stock chartread cannot read
            (unknown error) — not falling back

        a warning about a failure that never happened. Worse and latent: a
        non-CR30 engine session quit before its first event would RELAUNCH
        stock chartread during shutdown, leaving an orphan process behind the
        closing app.

        Quitting IS a deliberate ending, so saying so is both true and enough:
        `_user_quit` is exactly the flag those branches test. **The finish
        handler still runs**, which matters — it is what reconciles an empty
        `.ti3` (§3b / M-TI3-EMPTY), and an earlier version of this fix silenced
        that by dropping the callbacks outright.
        """
        self._user_quit = True

    def send_save_partial_and_quit(self) -> None:
        """Save what's been scanned so far and exit chartread cleanly.

        **Two 'q' commands, sent separately.** Knut established the protocol by
        hand (#130, 2026-07-30) after three wrong theories from me, and his log is
        unambiguous:

            Trigger instrument switch or any other key to start:
            q →  Strip read stopped at user request!
                 Hit Esc or 'q' to give up, any other key to retry:
            q →  [INFO] Measurement was interrupted — partial readings saved.

        The first 'q' stops the strip that is armed; the second answers the
        give-up prompt, and THAT is what makes chartread write the .ti3 and exit.
        Sending one and waiting for the other prompt is the whole of it.

        The previous chain (Return → strip menu → 'd' → "are you sure" → 'y')
        worked only when the reader happened to be sitting at the strip menu. From
        the misread prompt — the case this button exists for — the Return was
        spent as "retry", the menu never came, and the session hung with the
        instrument waiting. That is what he reported four times.

        **The two-'q' protocol is the ENGINE's, and only the engine's.** It
        works because ChromIQ's helper calls ``cq_write_ti3_atomic()`` before it
        gives up — a ChromIQ extension, marked *"never lose readings"* in
        ``chromiq_chartread.c``. Stock ArgyllCMS chartread has no such call:
        ``chartread.c:1654`` treats ``q`` at a misread prompt as "give up" and
        ``return -1``, and the file is never written.

        So on stock chartread the first 'q' ended the session and threw the
        readings away — Knut, #130 2026-08-01, having read a whole strip::

            [INFO] Measurement stopped — no measurement (.ti3) file was created.

        The path that *does* write on stock chartread is the strip menu's "done"
        question: retry back to the menu, 'd', then 'y' to the "Are you sure"
        prompt. That is what is sent there instead, one prompt at a time.
        """
        # ⚠ ANSWER THE PROMPT THAT IS OPEN, NOT THE ONE THIS CHAIN EXPECTS.
        #
        # Everything below assumes the reader is at a menu or a retry prompt,
        # and works by sending a key that MAKES it ask the saving question. But
        # one route arrives here with that question already on screen: the user
        # pressed 'd' themselves, chartread printed "Done ? - At least one
        # unread patch (…), Are you sure [y/n]" and is blocked on it, and the
        # window that offers "Save and stop" is the one raised BY that prompt
        # (`unread_confirm` → `TabMeasure._on_unread_confirm`). It exists only
        # because the prompt is already open.
        #
        # From there the chains below are not merely wrong, they are silent:
        # the reader takes one character, sees it is not 'y', and drops back
        # into the read loop having saved nothing — no second prompt is ever
        # printed, so the state waiting for one waits for ever. Measured on the
        # real manager, review2/R6-workflow F7: 'd' left it in
        # `wait_are_you_sure`, `{"cmd":"quit"}` in `wait_give_up_prompt`, and
        # the 'y' that writes the file was never sent on either reader. The
        # user met the same window twice and the first answer did nothing.
        #
        # 'y' is what writes the file here, on BOTH readers: stock chartread
        # breaks out of the loop and exits 0 (chartread.c), and the helper does
        # the same at chromiq_chartread.c:2153 (strip) and :3116 (patch), where
        # {"cmd":"yes"} is the mapped command. Nothing further is waited for,
        # because nothing further is printed.
        if self._at_unread_prompt:
            self._at_unread_prompt = False
            self._save_partial_state = None
            log.info("save-and-stop: the reader is at its own unread prompt; "
                     "sending 'y', which is what writes the .ti3 there")
            self.send_key("y")
            return
        # ⚠ THE TWO-'q' PROTOCOL DOES NOT WORK UNDER -x.
        #
        # It waits for the give-up prompt, and that prompt lives inside the
        # `read_sample` branch of the helper — the branch that drives a real
        # instrument. With external values the helper opens no instrument and
        # never enters it, so the prompt can never come: measured against the
        # real binary AND the real MeasureManager, one 'q' went out,
        # `abort_confirm` came back, and `_save_partial_state` sat in
        # `wait_give_up_prompt` for ever. The tab's Confirm-Abort ->
        # Keep-what-you-measured pair became a loop whose only exit was
        # "Discard and stop", and the helper was left running.
        #
        # The path that DOES write under -x is the one stock chartread uses:
        # 'd' (done) is answered by "at least one unread patch, are you sure",
        # and 'y' there saves and exits 0. Verified end to end: a partial .ti3
        # written this way is byte-identical in form to a completed one and
        # `-r` resumes from it.
        if self._engine_active and not self._external_values:
            self._save_partial_state = "wait_give_up_prompt"
            self.send_key("q")
            return
        if self._external_values:
            self._save_partial_state = "wait_are_you_sure"
            self.send_key("d")
            return
        if self._at_retry_prompt:
            # Any key that is not Esc/q means retry, which returns to the strip
            # menu — where 'd' is answered by a question that saves.
            self._save_partial_state = "wait_menu_then_done"
            self.send_key("r")
        else:
            self._save_partial_state = "wait_are_you_sure"
            self.send_key("d")

    @property
    def save_partial_in_progress(self) -> bool:
        """True while the Save-Partial-&-Quit prompt chain is still running."""
        return self._save_partial_state is not None

    @property
    def readings_this_session(self) -> int:
        """How many patches this session has read.

        Counted here rather than inferred from the file, because the file does
        not exist yet — chartread holds its readings until it exits (§0). The
        ending window needs the number to say what is at stake.
        """
        return int(getattr(self, "_readings_count", 0) or 0)

    @property
    def has_unsaved_readings(self) -> bool:
        """True when patches have been read that chartread has not written yet.

        chartread holds its readings in memory and writes the ``.ti3`` only on a
        clean exit, so killing the process throws them away. Knut, #130
        2026-08-01, on pressing Stop after reading a strip: *"the measurement
        session is ended without any measurement and the ti3 file is gone"* —
        and on patch-by-patch: *"no ti3 file is saved, even though I did read
        one patch"*. This is what lets Stop offer to keep them.
        """
        return bool(self._read_something)

    def abort(self) -> None:
        """End the run now. Always deliberate — never an engine failure.

        Every caller is a decision, not a malfunction: the user declined to
        measure, chose "Discard and stop", or the instrument was reported gone.
        None of them is a reason to retry the chart on stock chartread, and the
        non-zero exit that follows must not be described as one.

        Without this the user who closed the app mid-measurement was told
        "the chart's instrument is one stock chartread cannot read (unknown
        error)". Nothing had failed; they had quit.
        """
        self._user_quit = True
        self._runner.abort()

    # ------------------------------------------------------------------

    def _build_args(self, p: MeasureParams) -> list[str]:
        # -v makes stock chartread name the instrument it opened, exactly as
        # spotread does. Until now ChromIQ identified the device ONLY when the
        # ChromIQ engine was driving the read — on stock ArgyllCMS it knew
        # nothing, so anything keyed on the instrument fell back to generic
        # wording. Knut settled that -v changes nothing else by running both
        # forms side by side (#130, 2026-07-31): the only difference is a short
        # header, and "Instrument Type:" is the same line spotread prints.
        args: list[str] = ["-v", "-c", p.instrument]
        if p.external_values:
            # NEVER a bare `-x`: the letter IS the option's argument
            # (chromiq_chartread.c:3559-3569), and `na == NULL` calls usage().
            # `-xx` is XYZ; `-xl` would be L*a*b* and a double conversion.
            #
            # -c, -N, -B/-b and -T all become inert under it — new_icompaths is
            # skipped entirely and calibration lives inside `if (xtern == 0)` —
            # and they are left in place rather than stripped, because removing
            # a flag the helper ignores would only make this list disagree with
            # every other reader of MeasureParams.
            args.append("-xx")
        # -B (disable) and -b (force enable) are mutually exclusive; -B wins
        # if both are somehow set.
        if p.disable_bidir:
            args.append("-B")
        elif p.force_bidir:
            args.append("-b")
        if p.suppress_warnings:
            args.append("-S")
        if p.disable_initial_cal:
            args.append("-N")
        if p.patch_by_patch:
            args.append("-p")
        if p.high_res:
            args.append("-H")
        if p.resume:
            args.append("-r")
        if p.extra_args:
            args += shlex.split(p.extra_args)
        # Base name without extension
        args.append(str(p.ti1_path.with_suffix("")))
        return args

    @staticmethod
    def _measurement_was_complete(chart: "str | None", strips: list) -> bool:
        """Whether the chart's own .ti3 already held every reading.

        Falls back to the strip flags only when there is no chart path to
        resolve — they are coarse (per strip, not per patch) but they are
        better than assuming a fresh start.
        """
        if chart:
            try:
                from pathlib import Path as _P

                from workflow.measurement_state import Ti3State, classify

                ti2 = _P(chart)
                facts = classify(ti2.with_suffix(".ti3"), ti2)
                if facts.state is not Ti3State.UNREADABLE:
                    return facts.state is Ti3State.COMPLETE
            except Exception:      # noqa: BLE001 — never block a measurement
                log.warning("could not judge %s against its measurement",
                            chart, exc_info=True)
        return bool(strips) and all(s.get("read") for s in strips)

    def _all_done_is_news(self) -> bool:
        """Whether "all stripes read" is worth announcing.

        It is news only when the chart **became** complete in this session.

        Opening a chart that was already finished — a refine, or a re-read of a
        measurement you kept — and re-reading one strip does not complete
        anything: it was complete before you started. Announcing it there put
        the completion window in front of Knut every time he answered a strip
        window, as though he had just finished (#131, 2026-07-27/28). Reading the
        last outstanding strip of a partly-measured chart, on the other hand, IS
        a completion, and still says so.

        Verified against the real reading engine: on a complete chart the
        announcement is now silent both at the menu and after a re-read; on a
        chart with one strip left it still arrives when that strip is read.
        """
        if self._chart_was_complete:
            # …UNLESS THIS SESSION READ THE WHOLE CHART AGAIN.
            #
            # Basti, 2026-08-08: he re-measured printer-test end to end — every
            # strip A–F, from zero, with no `-r` — and no completion window
            # offered him Build Profile. His log shows the engine doing its part:
            # `{"strip":"F","read":true,"all_done":true}` and chartread's
            # "(!! ALL ROWS READ !!)".
            #
            # The suppression above is right for what it was written for and
            # says so: *"re-reading ONE strip does not complete anything"*. But
            # it was keyed only on the chart's state at the start, so any chart
            # that already had a finished .ti3 was silenced for ever after,
            # however much of it you read. A full re-measurement is a
            # completion by any reading of that sentence.
            #
            # Asking "did this session read every strip?" keeps Knut's case
            # silent (one strip re-read on a finished chart) and answers Basti's.
            # It does NOT weaken his beta.150 fix: `_chart_was_complete` still
            # comes from the .ti3, because the strip flags are per strip and the
            # gap can be per patch.
            return self._read_the_whole_chart_this_session()
        return bool(self._read_something or not self._is_resume)

    def _read_the_whole_chart_this_session(self) -> bool:
        """Whether every strip of the chart was read during this session."""
        wanted = {str(s.get("strip", "")).strip()
                  for s in (self._session_strips or [])
                  if str(s.get("strip", "")).strip()}
        if not wanted:
            return False
        return wanted <= self._strips_read_this_session

    def _handle_engine_line(self, line: str,
                            on_line: Callable[[str], None]) -> None:
        """Engine mode: typed events replace the regex forest. Prose lines
        (chartread's ordinary console output) still go to the log."""
        from workflow.chartread_engine import parse_engine_line

        ev = parse_engine_line(line)
        if ev is None:
            if line.strip():
                on_line(line)
                # Keep the helper's own fatal sentence, which arrives here as
                # prose. It is the only account of what went wrong when the
                # helper dies before emitting a single event (#159).
                m = _HELPER_FATAL_RE.match(line)
                if m:
                    self._engine_error_prose = m.group(1).strip()
                # The helper prints chartread's own startup failures as prose,
                # and they have to raise their window here too — this parser is
                # the only one that runs in engine mode (Knut, beta.141).
                self._check_startup_failures(line)
                # …and the notes it prints about settings the instrument
                # dropped, for the same reason: the user is told either way.
                self._check_informational(line)
                # The helper prints chartread's own prose alongside its events,
                # and one sentence in it needs more than the log: the dial being
                # in the wrong position (chartread.c:1644). There is no event for
                # it, so this is the only place it can be caught in engine mode.
                if _SENSOR_POSITION_RE.search(line) \
                        and not self._sensor_warning_open:
                    self._sensor_warning_open = True
                    self._at_retry_prompt = True
                    self.generic_instrument_error.emit(
                        tr("Wrong Sensor Position"),
                        tr("The instrument's dial is not in the reading "
                           "position. Turn it to the surface-reading position "
                           "and try again."))
                # --- c: the give-up prompt as PROSE, in engine mode ---------
                # The helper answers the first quit with an event in strip mode
                # and with this sentence in patch-by-patch. Only the event was
                # handled, so Save Partial & Quit reading patch by patch sent
                # one quit — which is Esc — and the session ended without
                # writing. Knut, beta.136: *"[INFO] Measurement stopped — no
                # measurement (.ti3) file was created"*, with readings on disk.
                if _STRIP_INTERRUPTED_RE.search(line):
                    # A PENDING SAVE IS ANSWERED FIRST — the same ordering the
                    # event path uses, and for the same reason: "Save and stop"
                    # marks the ending as answered, so the guard below used to
                    # eat the very prompt the save chain was waiting for and the
                    # second key never went out (Knut, beta.148).
                    #
                    # ONLY to finish a save-partial. The helper PRINTS this
                    # sentence and, in strip mode, also reports it as an event —
                    # so emitting the window from here as well raised "Strip
                    # Read Interrupted" straight after "Save and stop" had
                    # already been answered. Knut, beta.137: *"This is not the
                    # right window on exit of measurement … After clicking
                    # 'Save and Stop' I have already decided to save and
                    # stop."* The event is the authoritative one, the same rule
                    # the strip-error path already follows.
                    if self._save_partial_state == "wait_give_up_prompt":
                        self._save_partial_state = None
                        self._stop_requested = False
                        self._ending_already_answered = True
                        log.info("save partial: the printed give-up prompt "
                                 "arrived; sending the second key")
                        self.send_key("q")
                        return
                    if self._ending_already_answered:
                        return
            return

        self._engine_saw_event = True
        kind = ev["event"]

        if kind == "session_start":
            self._saw_spot_ready = False
            self._ending_already_answered = False
            self._stop_requested = False
            self._stop_requested = False
            strips = ev.get("strips", [])
            # Was there anything left to read when we opened it? That is what
            # decides whether "all strips read" can ever be news in this
            # session — see _all_done_is_news.
            #
            # ASK THE MEASUREMENT FILE, NOT THE STRIP FLAGS. A strip whose last
            # patch is unread still comes back `read: true` — the flags are per
            # strip and the gap is per patch. So a chart missing a few patches
            # looked complete, `_all_done_is_news` stayed False for the whole
            # session, and finishing every strip announced nothing at all: no
            # "All Strips Read" window and no completion sound. Knut, beta.150:
            # *"Started with a ti3 file that had one or a few patches missing in
            # last strip … Finishing all strips, but the concluding 'All Strips
            # Read' window with a Measurement Finished sound does NOT come."*
            #
            # Patch-by-patch had this fixed in beta.137 by asking the first
            # `spot_ready` instead; strip mode has no per-patch event to ask, so
            # it asks the .ti3 — which is the honest answer for both, and the
            # same one §3a uses everywhere else.
            self._chart_was_complete = self._measurement_was_complete(
                ev.get("chart"), strips)
            self._session_strips = list(strips or [])
            self.session_map.emit(strips)

        elif kind == "strip_ready":
            strip = ev.get("strip", "")
            self._at_retry_prompt = False        # back at the menu
            # …and the dial warning may be raised again next time. Its one-per-
            # prompt flag was cleared only on chartread's printed menu line,
            # which engine mode never produces — so after the first wrong-dial
            # window the flag stayed set and no further warning ever appeared.
            # Knut, beta.137, strip mode: *"Strip Read Failed window does NOT
            # come! Missing."* — with only the log line to show for it.
            self._sensor_warning_open = False
            self.stripe_changed.emit(strip)
            if ev.get("all_done") and self._all_done_is_news():
                self.all_stripes_done.emit()
            # Save-Partial no longer routes through the strip menu: it is two
            # 'q' commands (see send_save_partial_and_quit), which is the
            # sequence Knut verified by hand. Only the post-retry key is left.
            if self._pending_post_retry_key is not None:
                key = self._pending_post_retry_key
                self._pending_post_retry_key = None
                self.send_key(key)
            elif self._guided_state not in ("idle_done", "disabled"):
                self._guided_step(strip, on_line)

        elif kind == "scan_started":
            # The instrument has fired: the swipe starts NOW (#131). In strip
            # mode this is the only true start time — `strip_ready` arrives
            # while the user is still lining the head up.
            self.scan_started.emit()

        elif kind == "strip_read":
            self._engine_progress = True
            self._read_something = True
            _s = str(ev.get("strip", "")).strip()
            if _s:
                self._strips_read_this_session.add(_s)
            # "patches" IS THE LIST OF PATCHES, not a count.
            #
            # int(list) raises, and the raise happened one line before
            # strip_measured was emitted — so in engine strip mode every single
            # strip died here, silently as far as the screen was concerned:
            # no strip-completion sound, no pace figure under the preview, no
            # "read too fast" window, no split-patch overlay. Knut's beta.133
            # log, once per strip:
            #
            #   [CRITICAL] chromiq: Uncaught exception:
            #     File "workflow/measure_manager.py", line 863
            #   TypeError: int() argument must be … not 'list'
            #
            # He reported the four symptoms; they are one line.
            _patches = ev.get("patches")
            self._readings_count += (len(_patches) if isinstance(_patches, list)
                                     else int(_patches or 1))
            self.strip_measured.emit(ev)
            on_line(f" Strip read OK — {ev.get('strip', '?')} "
                    f"(worst patch ΔE {ev.get('worst_de', 0):.1f})")
            if self._guided_state == "waiting":
                self._advance_guided_strip(on_line)

        elif kind == "spot_ready":
            # Engine patch-by-patch mode: the read loop is now sitting on this
            # patch. Drives the current-patch highlight + page flip.
            # Reaching the patch menu also means any failure prompt is closed.
            self._at_retry_prompt = False
            self._sensor_warning_open = False
            # WAS THE CHART ALREADY COMPLETE? In patch-by-patch the strip flags
            # in `session_start` are too coarse to say: a strip whose last
            # patch is unread still comes back read=true, so a chart with ONE
            # patch left looked complete and the completion window was silenced
            # as "not news". Knut, beta.137, measured it exactly: with two
            # patches left the window came, with one it did not. The first
            # spot_ready of a session is the honest answer — it arrives before
            # anything has been read in this session.
            if not self._saw_spot_ready:
                self._saw_spot_ready = True
                # Only when nothing has been read yet in this session, and only
                # for a resume: that is the moment the answer describes what was
                # on disk beforehand rather than what this session has done. A
                # fresh measurement announces its completion either way.
                if self._is_resume and not self._read_something:
                    self._chart_was_complete = bool(ev.get("all_done"))
            self.patch_ready.emit(ev)
            # The second half of Skip Patch after a failed read: the retry
            # prompt has just been acknowledged, the menu is listening again,
            # and NOW the navigation key is the one that navigates (#131).
            if self._pending_post_retry_key is not None:
                key = self._pending_post_retry_key
                self._pending_post_retry_key = None
                self.send_key(key)
            # The same rule as strip mode, which this path was missing: a chart
            # that was ALREADY complete when the session opened has not been
            # completed by opening it, so re-reading a patch of a finished
            # measurement must not raise the completion window (Knut, #131
            # 2026-07-28 — the patch-mode half of the fault fixed in beta.69).
            if ev.get("all_done") and self._all_done_is_news():
                self.all_stripes_done.emit()

        elif kind == "instrument":
            # The engine opened the device and reports what it actually is.
            self.instrument_detected.emit(str(ev.get("model") or ""))

        elif kind == "patch_read":
            self._engine_progress = True
            self._read_something = True
            self._readings_count += 1
            self.patch_measured.emit(ev)

        elif kind == "mode_fallback":
            # Engine opt-in for XY/chart is off — the run will re-launch on
            # stock chartread when the helper exits (handled in _on_finish).
            self._engine_mode_fallback = True

        elif kind == "abort_confirm":
            # ESC HAD NO WINDOW ON THE ENGINE, AND THAT IS WHY IT LOOKED DEAD.
            #
            # Knut, #130: *"How can I reach the window during measurement
            # session that have an abort button?"* On the engine he could not.
            # Esc goes out as {"cmd":"quit"}, which the helper registers as an
            # abort (chromiq_chartread.c:2642); it then prints "Abort ? - Are
            # you sure ? [y/n]" and emits THIS event — and neither the event
            # nor the prose was handled here, because `_ABORT_CONFIRM_RE` is
            # matched only on the stock path in `_handle_line`. So the helper
            # sat at its own y/n prompt with nothing on screen to answer it:
            # the same "instrument stopped responding" shape as the unmapped
            # keys in KEY_TO_COMMAND.
            #
            # It also means the engine branch added to `_on_abort_confirm` in
            # beta.156 was never reachable. The window is what makes Abort go
            # through the model's single exit, so without this line the one
            # ending has a hole in it exactly where readings are at stake.
            self.abort_confirm.emit()

        elif kind == "chart_reading":
            self.chart_reading.emit()

        elif kind in ("chart_read", "xy_sheet_read"):
            self._engine_progress = True
            self.chart_measured.emit(ev)

        elif kind == "xy_place_sheet":
            self.xy_place_sheet.emit(int(ev.get("sheet", 1)),
                                     int(ev.get("total", 1)))

        elif kind == "xy_locate":
            on_line(tr("[Engine] Locate patch {p} with the table sight, then "
                       "continue.").format(p=ev.get("patch", "?")))

        elif kind == "saved":
            self._engine_progress = True
            self.readings_saved.emit(ev.get("path", ""),
                                     int(ev.get("read_patches", 0)))

        elif kind == "unread_confirm":
            # Normally the user's to answer: Save-Partial is two 'q' commands on
            # the engine path and never reaches here.
            #
            # Under -x it DOES reach here, because that path cannot use the two
            # 'q' protocol (see `save_partial_and_quit`) and asks 'd' instead.
            # The user has already said "keep what I measured", so answering
            # this prompt again would be asking the same question twice — and
            # leaving it unanswered is the wedge this replaced.
            if self._save_partial_state == "wait_are_you_sure":
                self._save_partial_state = None
                log.info("save-and-stop: confirming the unread patches (-x)")
                self.send_key("y")
                return
            info = f"{ev.get('id', '?')}, {ev.get('loc', '?')}"
            # The reader is now blocked on its own y/n and nothing else will be
            # printed until it is answered. Whatever ends this session has to
            # answer THIS prompt — see send_save_partial_and_quit.
            self._at_unread_prompt = True
            self.unread_confirm.emit(info)

        elif kind == "strip_warning":
            # The helper is blocked on "Hit Return to use it anyway, any other
            # key to retry, Esc or 'q' to give up". That is a retry prompt like
            # any other, and Skip has to acknowledge it before it can navigate
            # — without this the navigation key is spent as the prompt's "any
            # other key" and the reader never moves (Knut, #130 A2: Skip Patch
            # does nothing "when the reading is inconsistent").
            self._at_retry_prompt = True
            if ev.get("kind") == "wrong_strip":
                self.wrong_strip.emit(str(ev.get("read", "?")).upper(),
                                      str(ev.get("expected", "?")).upper())
            else:
                self.unexpected_response.emit(f"{ev.get('worst_de', 0):.2f}")

        elif kind == "strip_interrupted":
            # THE GIVE-UP PROMPT, ARRIVING AS AN EVENT — and three different
            # things can be waiting for it. They are answered in this order,
            # because each of the later guards would otherwise swallow it.
            #
            # In engine mode chartread's prose never reaches `_handle_line`, so
            # everything that used to key off the printed sentence has to be
            # driven from here.
            #
            # 1. A PENDING SAVE. `send_save_partial_and_quit` sends one 'q' and
            #    waits for this prompt to send the second — and the second is
            #    what makes chartread write the .ti3 and exit. "Save and stop"
            #    ALSO marks the ending as answered, so guard 3 below used to eat
            #    the prompt and the chain stalled. Knut, beta.148, from the
            #    Instrument Error window: *"the window closes, but the
            #    measurement session does NOT end, and the instrument is
            #    unresponsive."*
            #
            # 2. A STOP THE USER ALREADY CHOSE. In strip mode a wrong-dial
            #    failure is not a retry prompt: chartread prints it and goes
            #    back to the strip menu — *"Trigger instrument switch or any
            #    other key to start:"* — so the quit is read there as "interrupt
            #    this read", and the reader answers with this prompt. Knut,
            #    beta.147: *"since I did not make any measurements, the
            #    measurement session should have stopped. It did not."*
            #    Patch-by-patch ends on one key because there the same failure
            #    DOES leave a retry prompt; do not copy what that mode sends.
            #
            # 3. NOTHING. Then the ending has already been answered and this is
            #    the reader repeating itself — Knut, beta.138: *"Window 'Strip
            #    Read Interrupted' came again … You did not remove it."*
            #    Answering that window twice crashed the app.
            #
            # Otherwise it is a strip the user interrupted themselves, which has
            # a window of its own.
            if self._save_partial_state == "wait_give_up_prompt":
                self._save_partial_state = None
                self._stop_requested = False
                self._ending_already_answered = True
                log.info("save partial: the give-up prompt arrived; sending the "
                         "second key to write the .ti3 and exit")
                self.send_key("q")
                return
            if self._stop_requested:
                self._stop_requested = False
                self._ending_already_answered = True
                log.info("give up: the reader came back at the give-up prompt; "
                         "finishing the stop the user already chose")
                self.send_key("q")
                return
            if self._ending_already_answered:
                return
            # Nobody was waiting for this one, so it is the reader telling us
            # the user interrupted a strip themselves — that has its own window.
            self.strip_interrupted.emit()

        elif kind == "strip_misaligned":            # #50 safety net (opt-in)
            self.strip_misaligned.emit(
                str(ev.get("strip", "?")).upper(),
                int(ev.get("offset", 0)),
                f"{ev.get('base_de', 0):.1f}",
                f"{ev.get('best_de', 0):.1f}")

        elif kind == "error":
            ekind = ev.get("kind", "")
            if ekind == "misread":
                # The helper is now blocked on "…any other key to retry".
                self._at_retry_prompt = True
                detail = str(ev.get("detail") or "")
                # ONE WINDOW PER FAILURE — the printed line and this event are
                # the SAME physical failure, reported twice.
                #
                # The helper prints "Patch read failed … 'Wrong Sensor Position'
                # (Sensor should be in surface position)" and then, a moment
                # after the user answers that window, reports the same thing as
                # {"event":"error","kind":"misread"}. Raising a window for both
                # made an inescapable loop: Instrument Error → Retry → Patch
                # Read Failed → Retry → Instrument Error … Knut, beta.140:
                # *"An infinite loop. This was introduced in last betas."*
                #
                # _sensor_warning_open is still set at this point (spot_ready,
                # which clears it, arrives afterwards), so it is exactly the
                # "already told them" flag this needs.
                if self._sensor_warning_open and _SENSOR_POSITION_RE.search(detail):
                    log.debug("engine: misread event is the sensor-position "
                              "failure already reported — not raising a second "
                              "window")
                    return
                self.strip_error.emit(detail or "misread")
            elif ekind == "chart_refused":
                # #159. The helper refuses a chart whose TARGET_INSTRUMENT it
                # reads itself and stock chartread does not know at all. It
                # says so on stderr AND — since the C side gained this event —
                # in machine-readable form, so the reason no longer has to be
                # recovered from prose. Note this is a fatal, not a strip
                # error: nothing has been read and nothing can be.
                detail = str(ev.get("detail") or "")
                instr = str(ev.get("instrument") or "")
                self._engine_fatal = detail or (
                    f"the chart names {instr}, which this reader refuses"
                    if instr else "chart refused")
            elif ekind == "coms":
                self._at_retry_prompt = True
                self._engine_fatal = "communication problem"
                self.strip_error.emit("communication problem")
            elif ekind == "read_error":
                # The helper's generic ierror() path — where "Wrong Sensor
                # Position" lands. It prints the same "any other key to retry"
                # prompt as a misread and waits there, but nothing here said so,
                # so Skip Patch sent its navigation key straight into the prompt
                # and the reader stayed on the same patch (Knut, #130 A2, the
                # wrong-sensor-position half: "Skip Patch does not work after a
                # failed read").
                #
                # Stock chartread reaches this through the printed text instead
                # (_GENERIC_IERROR_RE in _handle_line); this is the engine's
                # equivalent, and both must set the flag.
                self._at_retry_prompt = True
                detail = str(ev.get("detail") or "")
                self.generic_instrument_error.emit(detail or "read error", detail)
            elif ekind == "needs_cal":
                on_line("[Engine] Instrument needs calibration…")
            elif ekind == "no_instrument":
                self._engine_fatal = "no instrument detected"
                self.no_instrument.emit()
            elif ekind == "cal_failed":
                detail = ev.get("detail", "")
                self._engine_fatal = detail or "calibration failed"
                self._handle_cal_failed(detail, on_line)

        elif kind == "cal_required":
            self.calibration_prompt.emit(str(ev.get("cond", "")),
                                         _instrument_text(ev.get("id")),
                                         bool(ev.get("optional", False)))

        elif kind == "aborted":
            # The user stopped the run themselves — never treat that as an
            # engine failure worth retrying on stock chartread.
            self._user_quit = True

        elif kind in ("cal_done", "cal_message"):
            if kind == "cal_done":
                self._cal_retries_left = self._cal_auto_retries
                self.calibration_done.emit()

        elif kind == "done":
            on_line("[Engine] Measurement session complete — file saved.")

        # "aborted" needs no handling: the process exit drives on_finish.

    def _check_startup_failures(self, line: str) -> None:
        """Raise the "Instrument Failed to Initialize" window from either reader.

        These failures happen BEFORE a measurement session exists — the
        instrument never came up — so there is nothing to send a key to and
        nothing to save. The window that explains them (unplug the cable, make
        sure it is switched on, try again) has existed since #130, but its
        trigger lived only in the stock-chartread parser. In engine mode the
        helper's prose goes straight to the log and never through that parser,
        so Knut saw the failure in the log window with no window at all
        (beta.141): *"Initialising instrument failed with message
        'Communications failure' … this message did not pop up with a window
        message, only in log window."*

        Called from both parsers now, so which reader is running cannot decide
        whether the user is told.
        """
        m = _INIT_COMS_FAIL_RE.search(line)
        if m:
            self.coms_init_failed.emit(m.group(1).strip())
        m = _INIT_INST_FAIL_RE.search(line)
        if m:
            self.inst_init_failed.emit(m.group(1).strip())
        # THE THREE NEIGHBOURS THE beta.141 FIX WALKED PAST.
        #
        # That fix moved exactly the two regexes above into this shared
        # checker and left these where they were — in the stock parser only —
        # so the same class of startup failure still went unheard on the
        # engine. They are printed by the helper as prose in every case
        # (chromiq_chartread.c:1004, :1063, :1085, :1409), so the condition is
        # fully reachable there; only the window was missing. Found by
        # auditing every signal after Knut's abort-window report (beta.160),
        # not by a second report.
        m = _CAPABILITY_FAIL_RE.search(line)
        if m:
            self.instrument_wrong_type.emit(m.group(1).lower())
        if _CCMX_FAIL_RE.search(line):
            self.ccmx_load_failed.emit(line.strip())
        m = _MODE_SET_FAIL_RE.search(line)
        if m:
            self.mode_set_failed.emit(m.group(1).strip())

    def _check_informational(self, line: str) -> None:
        """Surface the notes chartread prints, from either reader.

        Four of these say **a setting you chose was dropped by the instrument**
        — no spectral, high resolution ignored, UV not supported, patch
        consistency tolerance ignored. Not showing them means the user believes
        a setting is active when it is not, which is the same shape as the `-T`
        tolerance problem Knut already hit once.

        They lived in the stock parser only, so on the engine — the default
        reader — none of them appeared. Found by auditing every signal after
        the abort window (beta.160/161), not by a report. Same rule as
        `_check_startup_failures`: anything both readers can produce belongs
        where both parsers can reach it.
        """
        m = _INFO_CHART_INST_MISMATCH_RE.search(line)
        if m:
            self.info_message.emit(
                "chart_instrument_mismatch",
                f"Note: chart was generated for {m.group(1)}; reading with {m.group(2)} anyway.",
            )
        m = _INFO_BATTERY_RE.search(line)
        if m:
            try:
                pct = round(float(m.group(1)))
                self.info_message.emit("battery", tr("Instrument battery: {pct}%").format(pct=pct))
            except ValueError:
                pass
        if _INFO_NO_SPECTRAL_RE.search(line):
            self.info_message.emit(
                "no_spectral",
                "Spectral measurement not available on this instrument — colorimetric only.",
            )
        if _INFO_HIGHRES_IGNORED_RE.search(line):
            self.info_message.emit(
                "highres_ignored",
                "High-resolution mode requested but not supported — using normal resolution.",
            )
        if _INFO_UV_IGNORED_RE.search(line):
            self.info_message.emit(
                "uv_ignored",
                "UV mode requested but not supported on this instrument.",
            )
        if _INFO_SCAN_TOL_IGNORED_RE.search(line):
            self.info_message.emit(
                "scan_tol_ignored",
                "Patch consistency tolerance setting ignored — instrument doesn't support it.",
            )
        m = _PATCH_NOT_FOUND_RE.search(line)
        if m:
            self.info_message.emit("patch_not_found", tr("Patch '{name}' not found.").format(name=m.group(1)))

    def _handle_line(self, line: str, on_line: Callable[[str], None]) -> None:
        on_line(line)
        # Stock chartread announces the device in its -v header, before any
        # strip work begins. The engine reports the same thing as a JSON event
        # (see the "instrument" branch above), so both readers now identify the
        # instrument and the windows keyed on it stop falling back to generic
        # wording (#130, Knut 2026-07-31).
        m = _INST_TYPE_RE.search(line)
        if m:
            self.instrument_detected.emit(m.group(1).strip())
            return

        matches = _STRIP_RE.findall(line)
        if matches:
            current = matches[-1]
            self.stripe_changed.emit(current)
            # As above: the strip menu is no longer part of Save-Partial.
            if self._pending_post_retry_key is not None:
                key = self._pending_post_retry_key
                self._pending_post_retry_key = None
                self.send_key(key)
            elif self._guided_state not in ("idle_done", "disabled"):
                self._guided_step(current, on_line)
        # IMPORTANT: handle the user-initiated "unread patch" prompt BEFORE the
        # generic _ARE_YOU_SURE_RE auto-answer below, otherwise that branch
        # resets _save_partial_state to None and the gate here would let the
        # dialog fire even when our Save-Partial flow is in control.
        m = _UNREAD_CONFIRM_RE.search(line)
        if m:
            # On the ENGINE, Save-Partial is two 'q' commands and never reaches
            # this prompt, so it is the user's to answer. On STOCK chartread it
            # is exactly the prompt Save-Partial steers into — 'd' raises it and
            # 'y' is what writes the file — so there it is answered for them
            # rather than asking a question they have already answered by
            # pressing Save Partial (#130, 2026-08-01).
            if self._save_partial_state == "wait_are_you_sure":
                self._save_partial_state = None
                self.send_key("y")
            else:
                # Blocked on the user's own y/n — see the engine branch and
                # send_save_partial_and_quit.
                self._at_unread_prompt = True
                self.unread_confirm.emit(m.group(1).strip())
        elif (self._save_partial_state == "wait_are_you_sure"
                and _ARE_YOU_SURE_RE.search(line)):
            # The same question without the "(id, loc)" detail — chartread words
            # it either way depending on what is unread. Only answered while a
            # Save-Partial is steering; otherwise it is the user's.
            self._save_partial_state = None
            self.send_key("y")
        # The "Are you sure [y/n]" auto-answer belonged to the old strip-menu
        # chain and is unreachable now that Save-Partial is two 'q' commands. The
        # user-driven prompt above (_UNREAD_CONFIRM_RE) is untouched.
        if _STRIP_OK_RE.search(line):
            # Something was read in this session — which is what tells a resume
            # that a later "all stripes read" is real news.
            self._read_something = True
            self._readings_count += 1
            if self._guided_state == "waiting":
                self._advance_guided_strip(on_line)
        if (_ALL_DONE_RE.search(line)
                and not (self._is_resume and _STRIP_RE.search(line))
                and self._all_done_is_news()):
            self.all_stripes_done.emit()
        if _CALIBRATION_PROMPT_RE.search(line):
            self.calibration_prompt.emit("", "", False)
        if _CALIBRATION_RE.search(line):
            self.calibration_done.emit()
        # The engine PRINTS the same "Strip read failed …" line it also reports
        # as a JSON event, so parsing both raised the failure twice — two
        # windows, the second carrying its own default answer, which quietly
        # replaced whatever the user had chosen in the first (Knut, #130
        # 2026-07-27: his Save Partial & Quit ended up retrying instead). In
        # engine mode the JSON event is the authoritative one.
        # THE DIAL IS IN THE WRONG POSITION — in either engine, either mode.
        #
        # chartread.c:1644 prints this in strip mode and carries no "(reason)"
        # on the line, so no other pattern sees it. It is a retry prompt like
        # any other, and the user needs to be told to turn the dial rather than
        # left looking at a log line. Checked before the engine branch because
        # the helper prints the same sentence, and prose is all that reaches us
        # for it (Knut, beta.135: patch-by-patch got a window, strip mode did
        # not).
        if _SENSOR_POSITION_RE.search(line):
            # ONE WINDOW PER PROMPT. chartread prints the fault and its reason on
            # two lines — "Spot read failed due to the sensor being in the wrong
            # position" then "(Sensor should be in surface position)" — and the
            # pattern matches both, so beta.136 opened two identical windows.
            # Knut: *"TWO 'Instrument Error' windows comes simultaneously."*
            if not self._sensor_warning_open:
                self._sensor_warning_open = True
                self._at_retry_prompt = True
                self.generic_instrument_error.emit(
                    tr("Wrong Sensor Position"),
                    tr("The instrument's dial is not in the reading position. "
                       "Turn it to the surface-reading position and try "
                       "again."))

        if not self._engine_active:
            m = _STRIP_ERROR_RE.search(line)
            if m:
                # STOCK CHARTREAD IS NOW BLOCKED ON A RETRY PROMPT.
                #
                # chartread.c:1652-1654 prints "Strip read failed due to misread
                # (…)" and then "Hit Esc to give up, any other key to retry:",
                # where it waits. The engine's equivalent sets this flag; the
                # stock path never did, so Save Partial & Quit took the branch
                # that sends 'd' — which the prompt swallowed as "any other key
                # = retry". Knut, beta.128, with the engine switched off: *"Then
                # I pressed 'Save Partial and Quit' button, which then SHOULD
                # have exited measurement without any readings, but did not
                # exit. Had to press stop button."* With the flag set, the
                # retry-first chain runs and the strip menu's 'd' → 'y' is what
                # writes the file and ends the session.
                self._at_retry_prompt = True
                self.strip_error.emit(m.group(1).strip())
            elif _STRIP_COMS_FAIL_RE.search(line):
                self._at_retry_prompt = True      # chartread.c:1671-1673, same prompt
                self.strip_error.emit("communication problem")

        # A. Mid-measurement recovery prompts ------------------------------
        # (note: _UNREAD_CONFIRM_RE is handled above, before _ARE_YOU_SURE_RE,
        # so the Save-Partial state machine and the user-driven dialog don't
        # race each other when the prompt arrives.)
        if _STRIP_INTERRUPTED_RE.search(line):
            # The give-up prompt that follows the first 'q' of Save-Partial: the
            # second 'q' here is what writes the .ti3 and ends the session.
            if self._save_partial_state == "wait_give_up_prompt":
                self._save_partial_state = None
                self._ending_already_answered = True
                self.send_key("q")
            else:
                self.strip_interrupted.emit()
        # Save-Partial on STOCK chartread: retry took us back to the strip menu,
        # and 'd' there raises the question that actually writes the file
        # (#130, 2026-08-01 — 'q' on stock chartread exits without writing).
        if _SPOT_READY_RE.search(line):
            # Skip Patch, second half. The queued key is flushed on the STRIP
            # menu by the _STRIP_RE branch above, which never matches "Ready to
            # read patch '21' at 'A3'" — so on stock chartread, reading patch by
            # patch, Skip acknowledged the prompt and then never moved. Knut,
            # beta.136: every other combination jumped to the next unit; this
            # one *"does NOT jump to next patch ID"*.
            if self._pending_post_retry_key is not None:
                key = self._pending_post_retry_key
                self._pending_post_retry_key = None
                self.send_key(key)

        if _STRIP_MENU_RE.search(line) or _SPOT_READY_RE.search(line):
            self._sensor_warning_open = False      # the prompt is closed
            # Back at the menu — strip mode's "Ready to read strip pass A" or
            # patch-by-patch's "Ready to read patch '66' at 'A2'". Only the
            # first was recognised, so on stock chartread reading patch by
            # patch, Save Partial & Quit walked back to the menu and then
            # waited for a line that never came (Knut, beta.133). The
            # remaining prompt is closed either way.
            # engine clears this on its `strip_ready` event; the stock path had
            # no equivalent, so once a failure had been seen the flag stayed set
            # for the rest of the session and every later Save Partial spent a
            # retry key it did not need.
            self._at_retry_prompt = False
            if self._save_partial_state == "wait_menu_then_done":
                self._save_partial_state = "wait_are_you_sure"
                self.send_key("d")
        m = _GENERIC_IERROR_RE.search(line)
        if m:
            # ierror() waits on "any other key to retry" exactly like a misread,
            # so Skip must acknowledge the prompt before it navigates (#130 A2).
            self._at_retry_prompt = True
            self.generic_instrument_error.emit(m.group(1).strip(), m.group(2).strip())

        # B. Startup / config failures -------------------------------------
        # All of them live in the shared checker, so both readers raise the
        # same windows. Repeating them here would fire each one twice.
        self._check_startup_failures(line)

        # B-status. Informational ------------------------------------------
        self._check_informational(line)

        # D. Spot / XY mode ------------------------------------------------
        m = _XY_PLACE_SHEET_RE.search(line)
        if m:
            self.xy_place_sheet.emit(int(m.group(1)), int(m.group(2)))
        m = _XY_SHEET_OK_RE.search(line)
        if m:
            self.info_message.emit(
                "xy_sheet_ok",
                f"Sheet {m.group(1)} of {m.group(2)} read successfully.",
            )
        m = _SPOT_READY_RE.search(line)
        if m:
            self.spot_ready.emit(m.group(1))
        if _ABORT_CONFIRM_RE.search(line):
            self.abort_confirm.emit()

    # ------------------------------------------------------------------
    # Guided strip navigation
    # ------------------------------------------------------------------

    def _advance_guided_strip(self, on_line: Callable[[str], None]) -> None:
        """Called when 'Strip read OK' is detected while in guided-waiting state."""
        target = self._guided_strips[self._guided_idx]
        self._guided_idx += 1
        if self._guided_idx >= len(self._guided_strips):
            self._guided_state = "idle_done"
            on_line("[Guided Refinement] All target strips measured.")
            self.all_stripes_done.emit()
        else:
            next_target = self._guided_strips[self._guided_idx]
            self._guided_state = "navigating"
            on_line(
                f"[Guided Refinement] Strip {target} done. "
                f"Moving to strip {next_target}\u2026"
            )
            # Navigation is normally triggered by the next stripe_changed event —
            # chartread re-announces the current strip after Strip read OK in
            # resume mode, which fires stripe_changed and drives navigation.
            # If that announcement has ALREADY arrived (the pace prompt's modal
            # loop delivers it before this runs), there is no further event to
            # wait for, so make the move here instead.
            if getattr(self, "_guided_menu_pending", False):
                self._guided_menu_pending = False
                self._navigate_toward(target, next_target)

    def _guided_step(self, current: str, on_line: Callable[[str], None]) -> None:
        letter = "".join(c for c in current if c.isalpha()).upper()
        if not letter or not self._guided_strips:
            return

        if self._guided_state == "idle":
            target = self._guided_strips[0]
            self._guided_state = "navigating"
            strips_str = ", ".join(self._guided_strips)
            from core.i18n import count_phrase, tr
            _n = count_phrase(len(self._guided_strips),
                              tr("1 strip"), tr("{n} strips"))
            on_line(
                f"[Guided Refinement] Starting auto-navigation to "
                f"{_n}: {strips_str} — worst \u0394E first."
            )
            on_line("[Guided Refinement] The app will press 'f'/'b' for you. Do not touch the keyboard.")
            on_line(f"[Guided Refinement] Moving to strip {target}\u2026")
            self._navigate_toward(letter, target)
            return

        if self._guided_state == "navigating":
            target = self._guided_strips[self._guided_idx]
            if letter == target:
                self._guided_state = "waiting"
                on_line(f"[Guided Refinement] Arrived at strip {target} \u2014 please scan now.")
            else:
                self._navigate_toward(letter, target)

        elif self._guided_state == "waiting":
            target = self._guided_strips[self._guided_idx]
            if letter == target:
                # CHARTREAD IS BACK AT ITS MENU, STILL ON THIS STRIP.
                #
                # In resume mode it re-announces the same strip after a good
                # read, so this arrives for every refinement strip. Normally the
                # advance below has already run and moved the state on, so this
                # is harmless. But `strip_measured` is emitted BEFORE the advance
                # and the tab answers it with the modal "read a little fast"
                # prompt — whose nested event loop delivers this event first.
                # It was then consumed doing nothing, and the advance went on to
                # wait for a `stripe_changed` that had already been and gone, so
                # guided refinement stopped dead on strip A (Basti, 2026-08-08).
                #
                # Remember that the menu is already up; the advance then drives
                # the move itself instead of waiting for an event.
                self._guided_menu_pending = True
                return
            if letter != target:
                # chartread moved to a new strip — previous one was accepted
                self._guided_idx += 1
                if self._guided_idx >= len(self._guided_strips):
                    self._guided_state = "idle_done"
                    on_line(
                        "[Guided Refinement] All target strips measured. "
                        "You may press 'n' or 'd' to finish."
                    )
                else:
                    next_target = self._guided_strips[self._guided_idx]
                    self._guided_state = "navigating"
                    on_line(
                        f"[Guided Refinement] Strip {target} done. "
                        f"Moving to strip {next_target}\u2026"
                    )
                    self._navigate_toward(letter, next_target)

    def _navigate_toward(self, current: str, target: str) -> None:
        # Engine mode: one direct jump instead of a simulated keystream.
        if self._engine_active:
            self.goto_strip(target)
            return
        ci = letter_to_idx(current)
        ti = letter_to_idx(target)
        key = "f" if ti > ci else "b"
        self._runner.write_stdin(key)
