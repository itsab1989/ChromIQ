# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""The Measure tab's window that drives the X-Rite i1iO 2 table (build step 9, 2026-11-17).

Inside the EXISTING Beta "X-Rite i1iO support" (``workflow.i1io.support``): START MEASUREMENT on
a chart made for an i1iO 2 with an i1Pro 2 opens this window, in Manual and in Guided alike. The
IMPORT module stays the place for measurements made in i1Profiler. With the Beta off nothing here
is imported (the Measure tab asks ``workflow.i1io.support.i1io_enabled()`` first).

What the window does, and what it never does:

* It drives the table only through the job (``workflow.i1io.table.job.TableJob``), which owns
  every safety rule: the allow-list, the caps, the hands-off GO, the stops, the true state. The
  window shows the job's questions, passes the person's answers, and shows the job's true state
  after every step. It never talks to the table itself.
* The job's steps run in a worker thread (``_JobWorker``), so the GUI thread is never blocked:
  Stop and Report a problem stay pressable while a line is on its way (the job is built for
  ``stop_at_next_pause()`` and ``report_problem()`` from another thread).
* No button is a default, so Enter never answers a question (STEP8_NOTES: no confirmation has a
  default). No native QMessageBox: the questions are pages of this one window. No slot is a
  lambda that captures ``self`` on a child's signal (CLAUDE.md): each connection is a bound
  method.
* Every text is the §M catalogue's (``workflow.measurement_messages``, M-I1IO-DRIVE-*, proposed
  texts shown as Knut ruled on 2026-10-14); button labels and short state lines go through
  ``tr()``.

The job is imported lazily (``default_job_factory``), only after START on such a chart; the
on-screen driver of this step replaces ``JOB_FACTORY`` with the simulated table the tests use, so
no USB device is ever opened by a driver.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from PyQt6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit,
                             QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from core.i18n import tr

log = logging.getLogger(__name__)

#: the version of M-I1IO-DRIVE-CONSENT's text; a changed text raises it and asks again
CONSENT_VERSION = 1
CONSENT_KEY = "i1io_table_consent_given"
ASK_KEY = "i1io_table_ask_after_each_step"
#: the only chart the window drives (STEP4_PROPOSAL section 2): an i1iO 2 with an i1Pro 2
CHART_TABLE, CHART_HEAD = "i1iO 2", "i1Pro 2"

# the job's result kinds (``workflow.i1io.table.job.Kind``), by value: the job is not imported here
OK, REFUSED, STOPPED, NEEDS = "ok", "refused", "stopped", "needs_confirmation"
REPORT = "report_after_step"


# ---- which charts the window drives ----------------------------------------------------------

def drivable_sheet(chart_ti2) -> "dict | None":
    """The side file of a chart this window drives, or None (then START keeps today's window).

    Only a PROFILING run's chart (``<project>/runs/<run>/``; calibration and verification charts
    keep their windows until the job has a twin for them), and only when the chart's own side file
    names an i1iO 2 with an i1Pro 2. Reads the side file only; never raises."""
    try:
        chart = Path(chart_ti2)
        if chart.parent.parent.name != "runs":
            return None
        name = chart.name[:-4] if chart.name.lower().endswith(".ti2") else chart.stem
        side = chart.with_name(name + ".i1io.json")
        if not side.is_file():
            return None
        sheet = json.loads(side.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(sheet, dict):
        return None
    if sheet.get("table_model") != CHART_TABLE or sheet.get("head_model") != CHART_HEAD:
        return None
    if not sheet.get("pages"):
        return None
    return sheet


def consent_given(settings) -> bool:
    try:
        return int(settings.get(CONSENT_KEY, 0) or 0) >= CONSENT_VERSION
    except (TypeError, ValueError):
        return False


def ask_after_each_step(settings) -> bool:
    try:
        return bool(settings.get(ASK_KEY, True))
    except Exception:      # noqa: BLE001 - the safe answer
        return True


def default_job_factory(sheet: dict, page: int, run, stamp: str, ask: bool):
    """The real job: ChromIQ's own USB route, the real helper, the app-level marker place."""
    from workflow.i1io.table import job as J
    from workflow.i1io.table_settle import app_marker_place
    return J.TableJob(sheet, page, run=run, stamp=stamp, ask_after_each_step=ask,
                      app_marker_place=app_marker_place())


#: replaced by the on-screen driver (and the tests) with the simulated table
JOB_FACTORY = default_job_factory


def usb_status():
    """(ok, message id) of the USB library, read only (no device is touched)."""
    try:
        import core.usb_library as usb_library
        st = usb_library.status()
    except Exception:      # noqa: BLE001 - said, never a crash
        return False, "M-I1IO-DRIVE-USB-MISSING"
    if st.ok:
        return True, ""
    return False, usb_library.MESSAGE_FOR_PROBLEM.get(st.problem, "M-I1IO-DRIVE-USB-MISSING")


#: replaced by the tests; the driver keeps the real (read-only) check
USB_STATUS = usb_status


def new_stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def unique_stamp(run, now: "str | None" = None) -> str:
    """A session stamp no session of *run* has yet: two STARTs in the same second get
    ``_2``, ``_3`` (the form ``Run.i1io_table_session_dir`` accepts), never one folder."""
    base = now or new_stamp()
    stamp, n = base, 1
    try:
        while run is not None and run.i1io_table_session_dir(stamp).exists():
            n += 1
            stamp = f"{base}_{n}"
    except (ValueError, OSError, AttributeError):
        return base
    return stamp


def stamp_text(stamp: str) -> str:
    """"2026-11-17 14:00" from a session stamp (numbers only: the same in every language)."""
    try:
        return f"{stamp[0:4]}-{stamp[4:6]}-{stamp[6:8]} {stamp[9:11]}:{stamp[11:13]}"
    except (TypeError, IndexError):
        return str(stamp)


# ---- words for the job's ids --------------------------------------------------------------------

def choice_label(kind: str, value: str) -> str:
    """The button for one choice of one confirmation."""
    labels = {
        ("start_up", "yes"): tr("Start the table"),
        ("start_up", "i1profiler"): tr("Leave it to i1Profiler"),
        ("go", "yes"): tr("Go"),
        ("go", "back"): tr("Back"),
        ("sheet_laid", "yes"): tr("Yes, it is on the table"),
        # review 10, M-3: the panel has ONE Stop (the footer's); an answer that only ends
        # the step on screen says so
        ("sheet_laid", "stop"): tr("End this step"),
        ("arm_felt", "free"): tr("It moves freely"),
        ("arm_felt", "holds"): tr("It holds"),
        ("arm_felt", "not sure"): tr("Not sure"),
        ("aimed", "aimed"): tr("Aimed"),
        ("aimed", "stop"): tr("End this step"),
        ("front_choice", "back"): tr("Lay it further back"),
        ("front_choice", "go on"): tr("Feel the way forward"),
        ("front_yes", "yes"): tr("Yes, feel forward"),
        ("front_yes", "no"): tr("No"),
        ("first_visit", "yes"): tr("Make this move"),
        ("first_visit", "no"): tr("No"),
        ("pending_marker", "switched off and on"): tr("I switched it off and on"),
        ("pending_marker", "stop"): tr("Not now"),
        ("ready_to_open", "yes"): tr("Start"),
        ("ready_to_open", "stop"): tr("Not now"),
        ("report_after_step", "as described"): tr("As described"),
        ("report_after_step", "something wrong"): tr("Something was wrong"),
        ("report_after_step", "not sure"): tr("Not sure"),
        ("reader_consent", "yes"): tr("Open the instrument"),
        ("reader_consent", "no"): tr("No"),
        ("calibration_place", "own tile"): tr("Own tile (recommended)"),
        ("calibration_place", "table tile"): tr("Table's tile"),
        ("calibration_place", "stop"): tr("End this step"),
        ("calibration_own_tile", "ready"): tr("Ready"),
        ("calibration_own_tile", "stop"): tr("End this step"),
        ("calibration_reseated", "seated"): tr("Seated"),
        ("calibration_reseated", "stop"): tr("End this step"),
        ("row_failed", "again"): tr("Read it again"),
        ("row_failed", "skip"): tr("Skip it"),
        ("row_failed", "stop"): tr("End this step"),
        ("end_of_session", "save"): tr("Save and stop"),
        ("end_of_session", "discard"): tr("Discard and stop"),
        ("end_of_session", "keep measuring"): tr("Keep measuring"),
    }
    return labels.get((kind, value), value)


#: the answer that withdraws a question (End measurement pressed while it is open): the choice
#: that moves nothing
WITHDRAW = {"go": "back", "sheet_laid": "stop", "aimed": "stop", "front_choice": "back",
            "front_yes": "no", "first_visit": "no", "pending_marker": "stop",
            "ready_to_open": "stop", "reader_consent": "no", "calibration_place": "stop",
            "calibration_own_tile": "stop", "calibration_reseated": "stop",
            "row_failed": "stop", "start_up": "i1profiler", "arm_felt": "not sure"}

#: the job's refusals that are the person's own Stop taking effect
STOP_REASONS = ("stopped_before_the_next_move", "stopped_between_patches",
                "stopped_at_a_creep_pause")

#: the choices the window offers (the job's ``CHOICES``, in the order shown; "skip" at the free
#: arm is not offered: every answer but "free" ends the alignment the same way)
SHOWN_CHOICES = {"arm_felt": ("free", "holds", "not sure")}


def step_done_text(step: str, detail: dict) -> str:
    """What the step that just ran did, for M-I1IO-DRIVE-REPORT's first paragraph."""
    if step == "read_row":
        return tr("The arm moved along row {row} of page {page} and read its "
                  "patches.").format(row=detail.get("row", "?"), page=detail.get("page", "?"))
    return {
        "start_up": tr("The table started, the way i1Profiler starts a table that was just "
                       "switched on."),
        "park": tr("The arm made its recorded homing at its resting place."),
        "align": tr("The arm moved to the place where you aim it, the table let go of it, and "
                    "you aimed it at the three marks."),
        "creep": tr("The arm felt its way towards the front of the table in steps of 5 mm."),
        "check_move": tr("The arm moved by itself to mark 3."),
    }.get(step, tr("The table did the step that was described."))


def corner_text(corner: str) -> str:
    return {"top-left": tr("the one at the top left"),
            "bottom-left": tr("the one at the bottom left"),
            "bottom-right": tr("the one at the bottom right"),
            "top-right": tr("the one at the top right")}.get(corner, tr("as printed"))


def option_text(flag: str, why: str) -> str:
    """One line of M-I1IO-DRIVE-OPTIONS / -OPTION-REFUSED: the option and why."""
    names = {
        "-T": tr("Patch consistency tolerance (-T)"),
        "-B": tr("Bidirectional strip reading"),
        "-b": tr("Bidirectional strip reading"),
        "strip": tr("Patch-by-patch mode (-p) is off"),
        "-F": tr("Spectral filter (-F)"),
        "-x": tr("External values (-x)"),
        "-l": tr("Save Lab (-l)"),
        "-L": tr("Save Lab and XYZ (-L)"),
        "-n": tr("No spectral values (-n)"),
        "-H": tr("High resolution spectral mode (-H)"),
    }
    whys = {
        "the_table_knows_where_each_patch_is": tr(
            "the table knows where each patch is, so no strip is recognised"),
        "no_meaning_for_spot_readings": tr("the table reads one patch at a time"),
        "strip_rows_not_built_spot_is_used": tr(
            "reading whole strips with the table is not built yet, so ChromIQ reads patch by "
            "patch"),
        "i1pro2_refuses_every_filter": tr("the i1Pro 2 cannot measure with a filter"),
        "external_values_not_with_the_table": tr(
            "values from another program cannot be combined with the table"),
        "fields": tr("the earlier readings were measured with another setting"),
    }
    name = names.get(flag, flag)
    return f"•  {name}: {whys.get(why, why)}"


def reason_text(rid: str, detail: "dict | None" = None) -> str:
    """Why a step was refused or stopped, in a sentence (M-I1IO-DRIVE-REFUSED's {why})."""
    d = detail or {}
    texts = {
        "chart_not_for_i1io2_with_i1pro2": tr(
            "This chart was not made for an i1iO 2 with an i1Pro 2."),
        "not_ready_to_open": tr("You chose Not now, so ChromIQ did not connect to the table."),
        "pending_marker_not_cleared": tr(
            "You chose Stop at the question about switching the table off, so ChromIQ did not "
            "connect to the table."),
        "start_up_left_to_i1profiler": tr(
            "You chose to leave the start-up to i1Profiler. ChromIQ has let go of the table."),
        "person_chose_back": tr("You chose Back, so the arm did not move."),
        "sheet_not_laid": tr("You chose Stop before the arm moved to the aiming place."),
        "arm_did_not_give_way_at_the_alignment_start": tr(
            "The arm did not move freely when you pushed it, so ChromIQ does not aim with it."),
        "stopped_during_the_aims": tr("You chose Stop while aiming."),
        "sheet_to_be_laid_further_back": tr(
            "You chose to lay the sheet further back. Please lay it again and aim at its marks "
            "again."),
        "first_visit_declined": tr("You chose not to make that move, so the arm did not move."),
        "stopped_before_the_next_move": tr("You pressed Stop, so ChromIQ stopped before the "
                                           "next move."),
        "stopped_by_person": tr("You chose Send nothing more, so ChromIQ sends nothing more "
                                "to the table in this measurement."),
        "only_the_homing_now": tr(
            "After a problem was reported, only bringing the arm home is possible."),
        "report_due": tr("Please first answer the question about the last step."),
        "option_refused": tr("An option on the Measure tab cannot be used with the table."),
        "options_change_the_fields": tr(
            "These options would not match the readings this measurement completes."),
        "needs_calibration": tr("The instrument has to be calibrated first."),
        "calibration_due": tr("The instrument's calibration is about to run out, so it is "
                              "calibrated again first, with the arm at home."),
        "instrument_not_in_the_arm": tr("The i1Pro 2 is not back in the arm yet."),
        "helper_missing": tr("ChromIQ's reading program for the i1Pro 2 is missing from this "
                             "installation."),
        "helper_not_runnable": tr("ChromIQ's reading program for the i1Pro 2 cannot be "
                                  "started on this computer."),
        "wrong_instrument": tr("The instrument in the arm is not an i1Pro 2."),
        "instrument_not_reported": tr("The instrument did not say which model it is."),
        "reader_died": tr("ChromIQ's reading program for the i1Pro 2 stopped unexpectedly."),
        "reading_timed_out": tr("The instrument did not answer in time."),
        "instrument_asks_for_calibration": tr("The instrument asks for a new calibration."),
        "rows_read_again_limit": tr("Two rows of this page have been read again already, "
                                    "which is the most a page allows."),
        "row_not_in_chart": tr("That row is not on this page."),
        "page_read": tr("Every row of this page has been read."),
        "no_more_pages": tr("There is no further page to read."),
        "nothing_missing_on_this_page": tr("Nothing is missing on this page."),
        "an_earlier_page_is_to_be_read_first": tr("An earlier page has to be read first."),
        "session_ended": tr("This measurement has ended. Only bringing the arm home is "
                            "possible now."),
        "measurement_not_written": tr(
            "The measurement could not be written into the run (the disk did not take it). "
            "Nothing reached the run; your readings stay in this measurement's folder."),
        "run_has_a_measurement_already": tr("This run holds another measurement already."),
        "run_has_a_complete_measurement": tr(
            "This run holds a complete measurement, so the interrupted readings cannot be "
            "completed into it."),
        "not_an_interrupted_session": tr("That earlier session is not an interrupted one."),
        "adopted_already": tr("That earlier session is being completed already."),
        "readings_with_different_fields": tr(
            "The readings were measured with different settings and cannot go into one file."),
        "nothing_to_resume": tr("There is nothing to resume: the run has no partial "
                                "measurement of this chart."),
        "i1profiler_running": tr("i1Profiler is open on this computer."),
        "table_not_open": tr("ChromIQ is not connected to the table."),
        "sending_closed": tr("ChromIQ sends nothing more to the table in this measurement."),
        "movement_may_be_unfinished": tr("The last movement was not reported as finished."),
        "table_not_started": tr("The table has not been started."),
        "arm_not_at_rest": tr("The arm is not at its resting place."),
        "arm_not_out_on_the_table": tr("The arm is not out on the table."),
        "arm_not_out_on_the_sheet": tr("The arm is not out over the sheet."),
        "needs_alignment": tr("The sheet has to be aimed at first."),
        "ran_as_often_as_allowed": tr("This step has run as often as a page allows."),
        "cancelled_by_person": tr("You stopped it."),
        "link_lost": tr("The table's USB connection was lost."),
        "table_did_not_answer": tr("The table did not answer."),
        "table_refused_a_line": tr("The table refused a command."),
        "movement_outside_time_window": tr("A movement took longer or shorter than recorded."),
        "arm_not_where_expected": tr("The arm did not report the place it was sent to."),
        "target_outside_area": tr("The place lies outside the area ChromIQ sends the arm to."),
        "target_off_sheet": tr("The place lies outside the aimed marks of the sheet."),
        "path_leaves_area": tr("The way there would leave the area ChromIQ allows."),
        "target_beyond_confirmed_front": tr(
            "The place lies further forward than the arm has felt its way in this sitting."),
        "unexpected_error": tr("Something unexpected happened inside ChromIQ."),
        "no_run": tr("No profile run is selected."),
        "nothing_waits_for_a_confirmation": tr("No question is open."),
        "another_step_waits_for_a_confirmation": tr("Another question is still open."),
    }
    if rid.startswith("aims_") or rid in ("sheet_marks_on_one_line", "sheet_turned",
                                          "alignment_refused"):
        return tr("The three marks you aimed at do not fit this sheet. Nothing has moved over "
                  "your sheet; please aim again, in the order shown.")
    if rid.startswith("creep_"):
        return tr("Feeling the way forward stopped at a step that did not arrive exactly.")
    if rid.startswith("instrument_"):
        return tr("ChromIQ needs exactly one i1Pro 2 in the table's arm and no other measuring "
                  "instrument connected.")
    if rid.startswith("session_") or rid == "step_cap":
        return tr("The measurement reached the number of commands ChromIQ allows for it.")
    if rid in texts:
        return texts[rid]
    return tr("ChromIQ could not do this step ({reason}). The diagnostics file of this "
              "measurement has the details.").format(reason=rid)


# ---- the worker -------------------------------------------------------------------------------

class _Signals(QObject):
    """Lives in the GUI thread; a job call's result reaches the window through it (queued)."""

    done = pyqtSignal(int, object)
    #: the job's display-only progress, emitted from the job's thread
    progress = pyqtSignal(dict)


class _JobCall(QRunnable):
    """One job call, run in the window's own one-thread pool (so calls never overlap and the
    GUI thread is never blocked). The result, or the exception it raised, goes back through
    *signals*; a window closed meanwhile gets nothing."""

    def __init__(self, token: int, fn, signals: _Signals) -> None:
        super().__init__()
        self.token, self.fn, self.signals = token, fn, signals
        self.setAutoDelete(True)

    def run(self) -> None:
        try:
            res = self.fn()
        except BaseException as exc:      # noqa: BLE001 - every way a call can end is shown
            log.exception("i1iO table job call failed")
            res = exc
        try:
            self.signals.done.emit(self.token, res)
        except RuntimeError:              # the window is gone
            pass


_POOL: "QThreadPool | None" = None


def _pool() -> QThreadPool:
    global _POOL
    if _POOL is None:
        _POOL = QThreadPool()
        _POOL.setMaxThreadCount(1)
    return _POOL


# ---- the window -------------------------------------------------------------------------------

class TableMeasureWindow(QFrame):
    """One START on the i1iO table: a PANEL in the Measure tab's own measurement area (Basti,
    2026-11-17, after watching the first version: no window over the chart preview). The
    tab puts it where its options stand while a hand measurement runs, locks the rest of the
    app as a hand measurement does, and lets the preview follow the job (:attr:`progress`).
    Nothing of it is modal and nothing covers the preview; the GUI thread keeps running."""

    #: display only, for the tab's preview: the job's row / patch progress, and where the arm
    #: should point while the person aims (a dict, see TableJob.on_progress and _aim_event)
    progress = pyqtSignal(dict)

    #: the run's measurement file was written: (path, the job's Save detail)
    saved = pyqtSignal(object, dict)
    #: the window is done: "consent_declined", "not_started", "ended", "usb_missing", ...
    finished_with = pyqtSignal(str)

    def __init__(self, parent, settings, sheet: dict, run, chart_args, *, only_locs=None,
                 mode: str = "manual", replace_agreed: bool = False, archive=None,
                 stamp: "str | None" = None) -> None:
        super().__init__(parent)
        self.setObjectName("i1io_table_window")
        self._settings = settings
        self._sheet = sheet
        self._run = run
        self._chart_args = list(chart_args or [])
        self._only_locs = only_locs
        self._mode = mode
        self._replace_agreed = bool(replace_agreed)
        self._archive = archive
        self._stamp = stamp or unique_stamp(run)
        self.job = None
        self._token = 0
        self._busy = False
        self._then = None
        self._last = None
        self._checked_page: "int | None" = None
        self._again_rows: "list[int]" = []
        self._finished = False
        self._closed_job = False
        self._ending_open = False
        self._report_step: "str | None" = None
        self._pending_save_retry = False
        self._log_name = ""
        self.pages_shown: "list[str]" = []      # what the window showed, in order (tests)
        #: a Stop, a failed row or a problem in this window: the "don't ask again" offer is
        #: not made (NEXT_STEPS 4d), whatever the job's close() says
        self._troubled = False
        #: review 10, B-1: the person quit ChromIQ during this session
        self._quit_wanted = False
        self._archived = False
        self._build()
        self._signals = _Signals(self)
        self._signals.done.connect(self._on_done, Qt.ConnectionType.QueuedConnection)
        self._signals.progress.connect(self._relay_progress, Qt.ConnectionType.QueuedConnection)

    # ---- layout --------------------------------------------------------------------------
    #: the Stop button's own look (review 10, M-3): the one Stop, the strongest control of the
    #: panel while anything can move, in the same place on every page
    STOP_QSS = ("QPushButton#i1io_table_stop { background: #c62828; color: #ffffff;"
                " border: 1px solid #8e1b1b; border-radius: 6px; font-weight: 700;"
                " font-size: 15px; letter-spacing: 1px; padding: 6px 18px; }"
                "QPushButton#i1io_table_stop:hover { background: #b71c1c; }"
                "QPushButton#i1io_table_stop:pressed { background: #8e1b1b; }")
    #: an answer button is never squeezed below its own height (review 10, M-2)
    ANSWER_MIN_H = 34

    def _build(self) -> None:
        """Review 10, M-2: the question's text, its ticks and the note stand in ONE scroll
        area that takes all the free height (it scrolls only when the page is longer than the
        tab), the answers stand under it in rows that never overlap (two to a row only when
        both labels fit), then the true state, and the footer is pinned at the bottom: the
        switch-off line, Report a problem and End measurement, and the one Stop."""
        body = QVBoxLayout(self)
        body.setContentsMargins(16, 8, 16, 8)
        body.setSpacing(8)
        self._header = QLabel(tr("MEASURE · X-RITE i1iO TABLE (BETA)"), self)
        self._header.setObjectName("i1io_table_header")
        self._header.setStyleSheet("letter-spacing: 1px; font-size: 11px;")
        body.addWidget(self._header)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        page = QWidget(self._scroll)
        self._page = QVBoxLayout(page)
        self._page.setContentsMargins(0, 0, 6, 0)
        self._page.setSpacing(10)
        self._title = QLabel("", page)
        self._title.setObjectName("i1io_table_title")
        self._title.setWordWrap(True)
        f = self._title.font()
        f.setBold(True)
        f.setPointSizeF(f.pointSizeF() * 1.15)
        self._title.setFont(f)
        self._text = QLabel("", page)
        self._text.setObjectName("i1io_table_text")
        self._text.setWordWrap(True)
        self._text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._text.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._page.addWidget(self._title)
        self._page.addWidget(self._text)
        # the ticks right under the text they confirm
        self._ticks = QVBoxLayout()
        self._ticks.setSpacing(4)
        self._page.addLayout(self._ticks)

        # the person's own words (M-I1IO-DRIVE-NOTE), under the question it is about
        self._note_box = QWidget(page)
        nb = QVBoxLayout(self._note_box)
        nb.setContentsMargins(0, 4, 0, 0)
        nb.setSpacing(4)
        from workflow import measurement_messages as M
        n_title, n_body = M.M_I1IO_DRIVE_NOTE.render()
        self._note_title = QLabel(n_title, self._note_box)
        self._note_title.setWordWrap(True)
        self._note_edit = QPlainTextEdit(self._note_box)
        self._note_edit.setObjectName("i1io_table_note")
        self._note_edit.setFixedHeight(64)
        self._note_hint = QLabel(n_body, self._note_box)
        self._note_hint.setWordWrap(True)
        self._note_save = QPushButton(tr("Save note"), self._note_box)
        self._note_save.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._note_save.clicked.connect(self._on_save_note)
        nb.addWidget(self._note_title)
        nb.addWidget(self._note_edit)
        nb.addWidget(self._note_hint)
        nb.addWidget(self._note_save, 0, Qt.AlignmentFlag.AlignRight)
        self._note_box.setVisible(False)
        self._page.addWidget(self._note_box)
        self._page.addStretch(1)
        self._scroll.setWidget(page)
        # the text's height follows the width the viewport really has (it is known only once
        # the panel is laid out, and changes when the scroll bar comes or goes)
        self._scroll.viewport().installEventFilter(self)
        body.addWidget(self._scroll, 1)

        # the answers: two to a row when both labels fit the column, else one
        self._choices = QGridLayout()
        self._choices.setHorizontalSpacing(8)
        self._choices.setVerticalSpacing(6)
        body.addLayout(self._choices)

        # one line for what the panel is waiting for or what was just done
        self._status = QLabel("", self)
        self._status.setObjectName("i1io_table_status")
        self._status.setWordWrap(True)
        body.addWidget(self._status)

        # the true state, after every step, and live while a step runs
        self._state = QLabel("", self)
        self._state.setObjectName("i1io_table_state")
        self._state.setWordWrap(True)
        self._state.setFrameShape(QFrame.Shape.StyledPanel)
        self._state.setContentsMargins(8, 6, 8, 6)
        self._state.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self._state.setVisible(False)
        body.addWidget(self._state)

        # the footer: pinned, the same place on every page
        line = QFrame(self)
        line.setFrameShape(QFrame.Shape.HLine)
        body.addWidget(line)
        self._switch_off = QLabel(tr("To stop the arm at once, switch the table off at its "
                                     "power switch. Stop below lets the move that has "
                                     "started finish, then nothing more moves."), self)
        self._switch_off.setWordWrap(True)
        f2 = self._switch_off.font()
        f2.setBold(True)
        self._switch_off.setFont(f2)
        body.addWidget(self._switch_off)
        foot = QHBoxLayout()
        foot.setSpacing(8)
        self._problem_btn = QPushButton(tr("Report a problem"), self)
        self._problem_btn.setObjectName("i1io_table_problem")
        self._problem_btn.clicked.connect(self._on_problem)
        self._end_btn = QPushButton(tr("End measurement"), self)
        self._end_btn.setObjectName("i1io_table_end")
        self._end_btn.clicked.connect(self._on_end_pressed)
        self._close_btn = QPushButton(tr("Close"), self)
        self._close_btn.clicked.connect(self._on_close_pressed)
        for b in (self._problem_btn, self._end_btn, self._close_btn):
            b.setMinimumHeight(self.ANSWER_MIN_H)
        foot.addWidget(self._problem_btn)
        foot.addStretch(1)
        foot.addWidget(self._end_btn)
        foot.addWidget(self._close_btn)
        body.addLayout(foot)
        self._stop_btn = QPushButton(tr("Stop"), self)
        self._stop_btn.setObjectName("i1io_table_stop")
        self._stop_btn.setToolTip(tr("ChromIQ stops before the next move. A move that has "
                                     "started finishes first."))
        self._stop_btn.setStyleSheet(self.STOP_QSS)
        self._stop_btn.setMinimumHeight(46)
        self._stop_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._stop_btn.clicked.connect(self._on_stop)
        body.addWidget(self._stop_btn)
        self._moving_controls(False)
        self._end_btn.setVisible(False)
        # Esc as on the hand path's ending (review 10, S-1): the Close button's way out, never
        # an answer that moves (a question open is withdrawn with its own "no")
        from PyQt6.QtGui import QKeySequence, QShortcut
        # (the whole main window, as the hand path's key filter takes Esc anywhere in it; a
        # hidden panel's shortcut is never live)
        self._esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._esc.setContext(Qt.ShortcutContext.WindowShortcut)
        self._esc.activated.connect(self.reject)

    def _text_min_height(self) -> int:
        """The question's area never shrinks below about eight lines of its text."""
        return self._text.fontMetrics().lineSpacing() * 8 + 12

    def _sync_footer(self) -> None:
        """End measurement while the table is open and the session not over; Close only when
        the window may close (nothing opened, or the job has let go of the table)."""
        j = self.job
        open_ = j is not None and j.phase == "open" and not self._closed_job
        self._end_btn.setVisible(open_)
        own = {tr("Close"), tr("Cancel"), tr("Not now")}
        page_close = any(b.text() in own for b in getattr(self, "_buttons", []))
        self._close_btn.setVisible(not open_ and not page_close)

    def _moving_controls(self, on: bool) -> None:
        """Stop and Report a problem, and the switch-off line: visible while anything can move."""
        for w in (self._stop_btn, self._problem_btn, self._switch_off):
            w.setVisible(on)

    def _clear_page(self) -> None:
        for lay in (self._choices, self._ticks):
            while lay.count():
                it = lay.takeAt(0)
                w = it.widget()
                if w is not None:
                    w.setParent(None)
                    w.deleteLater()

    def _flow_choices(self) -> None:
        """Lay the answer buttons out: two to a row when the two widest labels fit side by
        side in the panel's width, else one to a row (review 10, M-2: never on top of each
        other, at any width the main window allows and in every language)."""
        made = list(getattr(self, "_buttons", []))
        while self._choices.count():
            self._choices.takeAt(0)
        if not made:
            return
        room = max(0, self.width() - 32 - self._choices.horizontalSpacing())
        widest = max(b.sizeHint().width() for b in made)
        cols = 2 if widest * 2 <= room and len(made) > 1 else 1
        for n, b in enumerate(made):
            self._choices.addWidget(b, n // cols, n % cols)
        self._choice_cols = cols

    def resizeEvent(self, event) -> None:      # noqa: N802
        super().resizeEvent(event)
        self._scroll.setMinimumHeight(min(self._text_min_height(),
                                          max(80, self.height() // 3)))
        self._flow_choices()
        self._fit_text()

    def eventFilter(self, obj, event) -> bool:      # noqa: N802
        from PyQt6.QtCore import QEvent
        if obj is self._scroll.viewport() and event.type() == QEvent.Type.Resize:
            self._fit_text()
        return False

    def _fit_text(self) -> None:
        """A word-wrapped label in a scroll area is laid out at its one-line minimum, so its
        last lines were cut off (review 10, M-2): the title and the text get the height their
        words need at the width they really have, and the scroll area scrolls the rest."""
        vw = self._scroll.viewport().width() - 6
        if vw <= 0:
            return
        for lab in (self._title, self._text):
            # QLabel's heightForWidth never answers less than the label's own minimum, so
            # the minimum is taken off first (measured on screen: a two-line text kept the
            # 736 px of a long page before it, and the page scrolled over empty space)
            old = lab.minimumHeight()
            lab.setMinimumHeight(0)
            need = lab.heightForWidth(vw) if lab.text() else 0
            lab.setMinimumHeight(max(0, need))
            if old != need:
                lab.updateGeometry()

    def _show(self, page_id: str, title: str, text: str, buttons=(), ticks=()) -> "list":
        """One page: a title, its text, optional ticks and the answer buttons (none default).
        Returns the buttons in order."""
        from ui.widgets import WrappingCheckBox
        self._clear_page()
        self.pages_shown.append(page_id)
        self._page_id = page_id
        self._status.setText(self._quit_hint())
        # the note field stays while what it is about is on screen (a problem, a stop, a
        # failure); the next job call clears that
        self._note_box.setVisible(bool(getattr(self, "_note_sticky", False)))
        self._title.setText(title)
        self._text.setText(text)
        self._scroll.verticalScrollBar().setValue(0)
        made_ticks = []
        for label in ticks:
            cb = WrappingCheckBox(label, self)
            cb.setObjectName(f"i1io_tick_{len(made_ticks)}")
            self._ticks.addWidget(cb)
            made_ticks.append(cb)
        made = []
        # the answer helpers live as long as their page (a connection to a bound method of a
        # plain object does not keep that object alive)
        self._slot_owners = [getattr(slot, "__self__", None) for _l, slot in buttons]
        for label, slot in buttons:
            b = QPushButton(label, self)
            b.setAutoDefault(False)
            b.setDefault(False)
            b.setMinimumHeight(self.ANSWER_MIN_H)
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            b.clicked.connect(slot)
            made.append(b)
        from ui.dialogs.no_default_button import no_default_button
        no_default_button(self)
        self._tick_widgets = made_ticks
        self._buttons = made
        self._flow_choices()
        self._fit_text()
        QTimer.singleShot(0, self._fit_text)
        self._sync_footer()
        return made

    # ---- the true state --------------------------------------------------------------------
    def state_text(self) -> str:
        j = self.job
        if j is None:
            return ""
        st = j.state()
        lines = []
        if st.table is None:
            lines.append(tr("Table: not connected."))
        elif st.link_lost:
            lines.append(tr("Table: the USB connection was lost."))
        elif st.sending_closed:
            lines.append(tr("Table: ChromIQ sends nothing more to it in this measurement."))
        else:
            lines.append(tr("Table: connected."))
        p = st.position_now or st.last_read
        if st.table is None:
            pass
        elif st.movement_may_be_unfinished:
            lines.append(tr("Arm: a movement was not reported as finished."))
        elif st.at_rest or j.parked():
            lines.append(tr("Arm: at its resting place."))
        elif st.arm_free:
            lines.append(tr("Arm: free (the table has let go of it)."))
        elif p is not None:
            lines.append(tr("Arm: out over the table; the table reports X {x}, Y {y} (in "
                            "tenths of a millimetre).").format(x=int(p[0]), y=int(p[1])))
        else:
            lines.append(tr("Arm: where it is is not known."))
        pages = j.pages_in_chart()
        rows = self._rows_on_page()
        status = j.row_status.get(j.page, {})
        read = sum(1 for v in status.values() if v == "read")
        lines.append(tr("Page {page} of {pages}: {read} of {rows} rows read.").format(
            page=j.page + 1, pages=pages, read=read, rows=rows))
        missing = sorted(k + 1 for k, v in status.items() if v in ("failed", "skipped"))
        if len(missing) == 1:
            lines.append(tr("Missing on this page: row {row}.").format(row=missing[0]))
        elif missing:
            lines.append(tr("Missing on this page: rows {rows}.").format(
                rows=", ".join(str(m) for m in missing)))
        n = j.accepted_in_this_session()
        lines.append(tr("Readings taken in this measurement: 1.") if n == 1 else
                     tr("Readings taken in this measurement: {n} (a patch read again counts "
                        "again).").format(n=n))
        return "\n".join(lines)

    @staticmethod
    def _mm(units) -> str:
        from core.i18n import decimal_text
        try:
            return decimal_text(float(units) / 10.0, 1)
        except (TypeError, ValueError):
            return "?"

    def _rows_on_page(self) -> int:
        try:
            return len(self._sheet["pages"][self.job.page]["strips"])
        except (KeyError, IndexError, TypeError):
            return 0

    def _refresh_state(self) -> None:
        if self.job is not None and self.job.phase not in ("new", "closed"):
            self._state.setText(self.live_state_text() if self._busy else self.state_text())
            self._state.setVisible(True)

    # ---- the state while a step runs (review 10, M-3: counts as they are read) -----------
    def _live_begin(self) -> None:
        """Before a job call starts (GUI thread, the job idle): the counts the live state line
        starts from."""
        j = self.job
        if j is None:
            return
        try:
            status = j.row_status.get(j.page, {})
            self._live = {"page": j.page + 1, "rows": self._rows_on_page(),
                          "rows_read": {k + 1 for k, v in status.items() if v == "read"},
                          "readings": j.accepted_in_this_session(), "now": "",
                          "table": self.state_text().split("\n", 1)[0]}
        except Exception:      # noqa: BLE001 - display only
            self._live = {}

    def _live_event(self, ev: dict) -> None:
        live = getattr(self, "_live", None)
        if not live:
            return
        kind = ev.get("event")
        if kind == "row_start":
            live["now"] = tr("Now: moving to row {row} of page {page}.").format(
                row=ev.get("row", "?"), page=ev.get("page", "?"))
        elif kind == "patch_next":
            live["now"] = tr("Now: reading row {row} of page {page}, patch {loc}.").format(
                row=ev.get("row", "?"), page=ev.get("page", "?"), loc=ev.get("loc", "?"))
        elif kind == "patch_read":
            live["readings"] = int(live.get("readings", 0)) + 1
        elif kind == "row_end":
            if ev.get("status") == "read":
                live["rows_read"].add(int(ev.get("row") or 0))
                live["now"] = tr("Now: row {row} is read.").format(row=ev.get("row", "?"))
            else:
                live["now"] = tr("Now: row {row} could not be read.").format(
                    row=ev.get("row", "?"))
        elif kind == "aim":
            live["now"] = tr("Now: aiming at mark {mark}.").format(mark=ev.get("mark", "?"))
        if self._busy and self._state.isVisible():
            self._state.setText(self.live_state_text())

    def live_state_text(self) -> str:
        """While a step runs: what the job reported last, without asking the job (it works
        in its own thread): the table, the arm moving, the rows and readings so far."""
        live = getattr(self, "_live", None) or {}
        if not live:
            return self._state.text()
        lines = [live.get("table") or tr("Table: connected."),
                 tr("Arm: moved by the table now.")]
        if live.get("now"):
            lines.append(live["now"])
        lines.append(tr("Page {page} of {pages}: {read} of {rows} rows read.").format(
            page=live.get("page", 1), pages=self.job.pages_in_chart() if self.job else 1,
            read=len(live.get("rows_read", ())), rows=live.get("rows", 0)))
        n = int(live.get("readings", 0))
        lines.append(tr("Readings taken in this measurement: 1.") if n == 1 else
                     tr("Readings taken in this measurement: {n} (a patch read again counts "
                        "again).").format(n=n))
        return "\n".join(lines)

    # ---- calling the job -------------------------------------------------------------------
    def _call(self, fn, then=None, status: str = "") -> None:
        """Run one job call in the worker; *then* (a bound method) gets its result."""
        self._token += 1
        self._live_begin()
        self._busy = True
        self._note_sticky = False
        self._then = then or self._on_result
        self._end_btn.setEnabled(False)
        self._close_btn.setEnabled(False)
        self._show_working(status)
        _pool().start(_JobCall(self._token, fn, self._signals))

    def _show_working(self, status: str = "") -> None:
        """While a job call runs: no answer buttons (an answer given is not shown as open),
        what is happening, and the hands-off reminder; Stop and Report a problem stay."""
        if getattr(self, "_page_id", "") == "problem":
            return
        self._clear_page()
        self._buttons = []
        self._tick_widgets = []
        self._page_id = "working"
        self._title.setText(status or tr("The table is working"))
        QTimer.singleShot(0, self._fit_text)
        self._text.setText(tr("Please keep your hands away from the table and the arm while it "
                              "works. Stop and Report a problem stay available below."))
        self._status.setText("")
        self._refresh_state()

    @pyqtSlot(int, object)
    def _on_done(self, token: int, res) -> None:
        if token != self._token:
            return
        self._busy = False
        self._end_btn.setEnabled(True)
        self._close_btn.setEnabled(True)
        self._status.setText("")
        then, self._then = self._then, None
        if getattr(self, "_page_id", "") == "problem" and not isinstance(res, BaseException):
            # the person is choosing what to report: the step's result waits behind it
            self._last = res
            self._deferred = (then, res)
            self._refresh_state()
            return
        if isinstance(res, BaseException):
            self._show_error(res)
            return
        self._last = res
        self._refresh_state()
        then(res)

    def _show_error(self, exc: BaseException) -> None:
        from workflow import measurement_messages as M
        title, body = _refused(M, reason_text("unexpected_error"))
        self._show("error", title, body, [(tr("End measurement"), self._on_end_pressed)])
        self._after_stop_controls()

    # ---- start ------------------------------------------------------------------------------
    def start(self) -> None:
        """The first page: the USB library, the explanation once, earlier sessions, options."""
        ok, mid = USB_STATUS()
        if not ok:
            from workflow import measurement_messages as M
            msg = M.I1IO_DRIVE_USB_MESSAGE.get(mid, M.M_I1IO_DRIVE_USB_MISSING)
            title, body = msg.render(log=tr("not written: nothing was started"))
            self._show("usb_missing", title, body, [(tr("Close"), self._finish_not_started)])
            self._why_not = "usb_missing"
            return
        if not consent_given(self._settings):
            self._show_consent()
            return
        self._build_job()

    def _show_consent(self) -> None:
        from workflow import measurement_messages as M
        title, body = M.M_I1IO_DRIVE_CONSENT.render()
        btns = self._show("consent", title, body,
                          [(tr("Not now"), self._on_consent_declined),
                           (tr("I understand, drive my table"), self._on_consent_given)],
                          ticks=[tr("I have read this.")])
        self._consent_go = btns[1]
        self._consent_go.setEnabled(False)
        self._tick_widgets[0].toggled.connect(self._on_consent_tick)

    def _on_consent_tick(self, on: bool) -> None:
        self._consent_go.setEnabled(bool(on))

    def _on_consent_declined(self) -> None:
        self._why_not = "consent_declined"
        self._finish_not_started()

    def _on_consent_given(self) -> None:
        if not self._tick_widgets or not self._tick_widgets[0].isChecked():
            return
        self._settings.set(CONSENT_KEY, CONSENT_VERSION)
        self._build_job()

    def _build_job(self) -> None:
        page = 0
        self.job = JOB_FACTORY(self._sheet, page, self._run, self._stamp,
                               ask_after_each_step(self._settings))
        # the preview follows the job (display only; emitted from the job's thread)
        self.job.on_progress = self._signals.progress.emit
        try:
            log_path = self._run.i1io_table_log(self._stamp)
            self._log_name = tr("{path}, in this run's folder").format(
                path=Path(log_path).relative_to(self._run.dir).as_posix())
        except Exception:      # noqa: BLE001
            self._log_name = ""
        self._earlier = [e for e in self.job.earlier_sessions() if e.get("state") ==
                         "interrupted"]
        self._next_earlier()

    def _next_earlier(self) -> None:
        if not self._earlier:
            self._set_options()
            return
        e = self._earlier[0]
        from workflow import measurement_messages as M
        read = int(e.get("accepted") or e.get("read") or 0)
        title, body = M.M_I1IO_DRIVE_EARLIER.render(when=stamp_text(e.get("stamp", "")),
                                                    read=read)
        self._show("earlier", title, body,
                   [(tr("Complete it"), self._on_adopt), (tr("Discard it"), self._on_discard_e),
                    (tr("Cancel"), self._finish_not_started)])

    def _on_adopt(self) -> None:
        e = self._earlier.pop(0)
        # review 10, S-2: with the replace agreed at START (M-REPLACE-*) the run's measurement
        # stays where it is until the Save writes the new one (the Save path archives it then,
        # through the tab's own archive); a Discard, an ending before any reading, a crash or a
        # quit leave the run exactly as it was
        replacing = bool(self._replace_agreed and self._run is not None
                         and Path(self._run.measurement_ti3).exists())
        res = self.job.adopt_earlier(e["stamp"], replacing=replacing)
        self._adopted_any = self._adopted_any or res.ok if hasattr(self, "_adopted_any") \
            else res.ok
        if not res.ok:
            self._show_refusal(res, after=self._next_earlier)
            return
        self._next_earlier()

    def _on_discard_e(self) -> None:
        e = self._earlier.pop(0)
        self.job.discard_earlier(e["stamp"])
        self._next_earlier()

    def _reads_note_from(self, res) -> None:
        """Open point a: what this session reads, said on the first page (a refinement's
        patches, or the patches a resume completes)."""
        from workflow import measurement_messages as M
        self._reads_note = ""
        d = res.detail or {}
        if d.get("refine"):
            self._reads_note = M.M_I1IO_DRIVE_REFINE.render(n=int(d["refine"]))[1]
        elif d.get("resume_unread"):
            self._reads_note = M.M_I1IO_DRIVE_RESUME.render(n=int(d["resume_unread"]))[1]

    def _set_options(self) -> None:
        res = self.job.set_options(self._chart_args, only_locs=self._only_locs)
        self._options_note = ""
        self._reads_note_from(res)
        if res.reason == "option_refused":
            from workflow import measurement_messages as M
            lines = "\n".join(option_text(k, v) for k, v in res.detail.get("refused", {}).items())
            title, body = M.M_I1IO_DRIVE_OPTION_REFUSED.render(options=lines)
            self._show("option_refused", title, body,
                       [(tr("Close"), self._finish_not_started)])
            return
        if res.reason == "options_change_the_fields":
            from workflow import measurement_messages as M
            used = [t for t in self._chart_args if t in res.detail.get("field_options", [])]
            lines = "\n".join(option_text(t, "fields") for t in used) or "•  -"
            title, body = M.M_I1IO_DRIVE_OPTIONS_FIELDS.render(options=lines)
            self._show("options_fields", title, body,
                       [(tr("Measure the rest that way"), self._measure_the_rest_that_way),
                        (tr("Cancel"), self._finish_not_started)])
            return
        if not res.ok:
            self._show_refusal(res, after=self._finish_not_started)
            return
        shown = {k: v for k, v in res.detail.get("no_meaning", {}).items()
                 if k in ("-T", "-B", "-b", "strip")}
        if shown:
            from workflow import measurement_messages as M
            _t, body = M.M_I1IO_DRIVE_OPTIONS.render(
                options="\n".join(option_text(k, v) for k, v in shown.items()))
            self._options_note = body
        self._show_prepare()

    def _measure_the_rest_that_way(self) -> None:
        """Review 10, M-4: the field options are taken from the readings being completed; the
        resume, its base, the patches to read and every other option stay as asked, so only
        the rest is measured, as M-I1IO-DRIVE-OPTIONS-FIELDS says."""
        res = self.job.set_options(self._chart_args, only_locs=self._only_locs,
                                   fields_as_built_on=True)
        if not res.ok:
            self._show_refusal(res, after=self._finish_not_started)
            return
        self._reads_note_from(res)
        self._show_prepare()

    def _first_page(self) -> int:
        pages = self.job.pages_to_read()
        return (pages[0] - 1) if pages else 0

    def _show_prepare(self) -> None:
        # the job is built on the first page with something to read (review 9, NOTE)
        first = self._first_page()
        if first != self.job.page and self.job.phase == "new":
            self.job.page = first
        from workflow import measurement_messages as M
        pages = self.job.pages_in_chart()
        title, body = M.M_I1IO_DRIVE_PREPARE.render(page=self.job.page + 1, pages=pages)
        if getattr(self, "_reads_note", ""):
            body = self._reads_note + "\n\n" + body
        if self._options_note:
            body += "\n\n" + self._options_note
        self._show("prepare", title, body,
                   [(tr("Not now"), self._finish_not_started),
                    (tr("Start"), self._on_start_pressed)],
                   ticks=[tr("Ask after each step of this measurement whether the table did "
                             "what was described")])
        self._tick_widgets[0].setChecked(ask_after_each_step(self._settings))
        self._tick_widgets[0].toggled.connect(self._on_ask_toggled)

    def _on_ask_toggled(self, on: bool) -> None:
        self._settings.set(ASK_KEY, bool(on))
        if self.job is not None and self.job.phase == "new":
            self.job.ask_after_each_step = bool(on)

    def _on_start_pressed(self) -> None:
        self._end_btn.setVisible(True)
        self._moving_controls(True)
        self._call(self.job.open, status=tr("Connecting to the table..."))

    # ---- one result --------------------------------------------------------------------------
    def _on_result(self, res) -> None:
        if res.kind == NEEDS:
            if getattr(self, "_end_after", False) and res.confirm != "end_of_session":
                # End measurement was pressed while a question was open: it is withdrawn with
                # its own "no" (nothing moves), then the ending is asked
                self._pending_kind = res.confirm
                self.answer(WITHDRAW.get(res.confirm, "stop"))
                return
            self._ask(res)
            return
        if res.confirm == REPORT and self.job.report_due is not None:
            self._ask_report(res)
            return
        if getattr(self, "_end_after", False):
            self._end_after = False
            self._call(self.job.end)
            return
        self._dispatch(res)

    def _dispatch(self, res) -> None:
        if res.kind == OK:
            self._after_ok(res)
            return
        if res.kind == REFUSED:
            self._on_refused(res)
            return
        self._on_stopped(res)

    def _after_ok(self, res) -> None:
        step = res.step
        if step == "open" and res.detail.get("table") == "cold":
            self._call(self.job.start_up)
            return
        if step == "align":
            self._checked_page = None        # a new alignment is checked at mark 3 again
        if step == "check_move":
            self._ask_check_mark()
            return
        if step == "next_page":
            self._show_next_page(res)
            return
        if step == "end":
            self._after_end(res)
            return
        if step == "save":
            self._after_saved(res)
            return
        if step == "home" and self.job.ended is not None:
            self._close_job()
            return
        if step == "home" and self.job.only_home:
            self._show_after_problem()
            return
        if step == "home" and getattr(self, "_home_then_stop", False):
            self._home_then_stop = False
            self._show_stopped_by_you(None)
            return
        self._next()

    def _next(self) -> None:
        """The next step of the measurement, from the job's true state."""
        j = self.job
        if j.ended is not None:
            return
        out = j.out_known() or bool(j.state().arm_free)
        if j.calibration_due:
            if out:
                self._call(j.home, status=tr("Bringing the arm home before the new "
                                             "calibration..."))
            else:
                self._call(j.calibrate, status=tr("Calibrating the instrument..."))
            return
        if j.calibration is None and not j.options_report.options.skip_initial_calibration:
            if out:
                self._call(j.home, status=tr("Bringing the arm home first."))
            else:
                self._call(j.calibrate, status=tr("Calibrating the instrument..."))
            return
        # a page with nothing missing (a resume, an adopted session) is never aligned or read
        left = j.rows_left() if j.page_has_something_to_read() else []
        want = bool(left or self._again_rows)
        if want and j.alignment is None:
            self._call(j.align, status=tr("Aiming at the sheet..."))
            return
        if want and j.front_need is not None and j.front_reached() < j.front_need:
            self._call(j.creep, status=tr("Feeling the way forward..."))
            return
        if want and self._checked_page != j.page:
            self._call(j.check_move, status=tr("Moving the arm to mark 3..."))
            return
        if self._again_rows:
            row = self._again_rows.pop(0)
            self._call(lambda: j.read_row(row), status=self._row_status(row))
            return
        if left:
            self._call(j.read_row, status=self._row_status(left[0]))
            return
        later = [p for p in j.pages_to_read() if p > j.page + 1]
        if later:
            self._page_done = j.page + 1
            if out:
                self._call(j.home, status=tr("Bringing the arm home first."))
            else:
                self._call(j.next_page)
            return
        self._on_end_pressed()

    def _row_status(self, row: int) -> str:
        return tr("Reading row {row} of {rows} on page {page} of {pages}...").format(
            row=row, rows=self._rows_on_page(), page=self.job.page + 1,
            pages=self.job.pages_in_chart())

    # ---- questions --------------------------------------------------------------------------
    def _ask(self, res) -> None:
        from workflow import measurement_messages as M
        kind, d = res.confirm, res.detail
        page = (d.get("page") or self.job.page + 1)
        if kind == "ready_to_open":
            title, body = M.M_I1IO_DRIVE_READY.render()
            btns = self._show("ready_to_open", title, body,
                              [(choice_label(kind, "stop"), self._answer_stop),
                               (choice_label(kind, "yes"), self._answer_yes)],
                              ticks=[tr("The arm is at its resting place, over the small white "
                                        "tile."),
                                     tr("Nothing lies on the table's bed except your sheet.")])
            self._ready_go = btns[1]
            self._ready_go.setEnabled(False)
            for cb in self._tick_widgets:
                cb.toggled.connect(self._on_ready_tick)
            self._pending_kind = kind
            return
        texts = {
            "pending_marker": (M.M_I1IO_DRIVE_MARKER_APP_ENDED.render
                               if d.get("app_ended") and d.get("app_ended") == d.get("markers")
                               else M.M_I1IO_DRIVE_MARKER.render),
            "start_up": M.M_I1IO_DRIVE_START_UP.render,
            "go": M.M_I1IO_DRIVE_GO.render,
            "arm_felt": M.M_I1IO_DRIVE_ARM_FELT.render,
            "front_yes": M.M_I1IO_DRIVE_FRONT_YES.render,
            "first_visit": M.M_I1IO_DRIVE_FIRST_VISIT.render,
            "calibration_place": M.M_I1IO_DRIVE_CAL_PLACE.render,
            "calibration_own_tile": M.M_I1IO_DRIVE_CAL_OWN_TILE.render,
            "calibration_reseated": M.M_I1IO_DRIVE_CAL_RESEAT.render,
        }
        if kind in texts:
            title, body = texts[kind]()
        elif kind == "sheet_laid":
            title, body = M.M_I1IO_DRIVE_SHEET_LAID.render(page=page)
        elif kind == "aimed":
            title, body = M.M_I1IO_DRIVE_AIM.render(mark=d.get("mark", "?"),
                                                    corner=corner_text(d.get("corner", "")))
            self._aim_event(d.get("mark"), d.get("patch") if d.get("target") == "patch"
                            else None)
        elif kind == "front_choice":
            title, body = M.M_I1IO_DRIVE_FRONT.render(back_mm=d.get("back_mm", "?"))
        elif kind == "reader_consent":
            mac = ""
            if "macos_normally_starts_that_service_again_by_itself" in d.get("facts", []):
                mac = M.M_I1IO_DRIVE_READER_CONSENT_MAC.render()[1]
            title, body = M.M_I1IO_DRIVE_READER_CONSENT.render(mac=mac)
        elif kind == "row_failed":
            title, body = M.M_I1IO_DRIVE_ROW_FAILED.render(
                row=d.get("row", "?"), page=d.get("page", page),
                why=reason_text(d.get("why", "")).rstrip("."))
            if not d.get("again_allowed", True):
                why = (reason_text("calibration_due") if d.get("calibration_due")
                       else reason_text("rows_read_again_limit"))
                body += "\n\n" + M.M_I1IO_DRIVE_ROW_NOT_AGAIN.render(why=why)[1]
        elif kind == "end_of_session":
            self._ask_end(res)
            return
        else:
            title, body = kind, ""
        if kind == "go" and d.get("again"):
            body = M.M_I1IO_DRIVE_GO.render()[1]
        self._pending_kind = kind
        values = SHOWN_CHOICES.get(kind, res.choices)
        buttons = [(choice_label(kind, v), self._answer_slot(v)) for v in values]
        made = self._show(kind, title, body, buttons)
        if kind == "row_failed" and not d.get("again_allowed", True):
            made[0].setEnabled(False)
        self._status.setText(tr("ChromIQ waits for your answer. Nothing moves until you "
                                "answer."))
        if kind == "row_failed":
            self._troubled = True
            self._show_note()

    def _answer_slot(self, value: str):
        """A bound answer for one button (no lambda capturing self on a child's signal)."""
        return _Answer(self, value).fire

    def answer(self, value: str) -> None:
        kind = self._pending_kind
        job = self.job
        self._call(lambda: job.answer(kind, value))

    def _answer_yes(self) -> None:
        if self._pending_kind == "ready_to_open" and not all(
                cb.isChecked() for cb in self._tick_widgets):
            return
        self.answer("yes")

    def _answer_stop(self) -> None:
        self.answer("stop")

    def _on_ready_tick(self, _on: bool) -> None:
        self._ready_go.setEnabled(all(cb.isChecked() for cb in self._tick_widgets))

    def _ask_report(self, res) -> None:
        from workflow import measurement_messages as M
        step = self.job.report_due
        title, body = M.M_I1IO_DRIVE_REPORT.render(step=step_done_text(step, res.detail))
        self._report_res = res
        buttons = [(choice_label(REPORT, v), _Report(self, v).fire)
                   for v in ("as described", "something wrong", "not sure")]
        self._show("report_after_step", title, body, buttons)
        self._status.setText(tr("ChromIQ waits for your answer. Nothing moves until you "
                                "answer."))

    def report(self, value: str) -> None:
        res = self.job.report_after_step(value)
        self._refresh_state()
        if not res.ok:
            self._show_refusal(res)
            return
        if value != "as described":
            self._troubled = True
            self._show_note()
            self._show_after_problem()
            return
        if getattr(self, "_end_after", False):
            # End measurement (or a quit) was asked while the step ran: the ending now, after
            # the report it was waiting for (fix round 10)
            self._end_after = False
            self._call(self.job.end)
            return
        self._dispatch(self._report_res)

    def _ask_check_mark(self) -> None:
        self._aim_event(3, self._aim_patch(3))
        from workflow import measurement_messages as M
        title, body = M.M_I1IO_DRIVE_CHECK_MARK.render()
        self._show("check_mark", title, body,
                   [(tr("Yes, it is centred"), self._on_mark_ok),
                    (tr("No"), self._on_mark_wrong)])

    def _aim_patch(self, mark) -> "str | None":
        try:
            for a in self._sheet["pages"][self.job.page]["aim_points"]:
                if a.get("number") == mark and a.get("target") == "patch":
                    return a.get("patch")
        except (KeyError, IndexError, TypeError):
            pass
        return None

    def _on_mark_ok(self) -> None:
        self.job.note("check_mark", "centred")
        self._checked_page = self.job.page
        self._next()

    def _on_mark_wrong(self) -> None:
        self.job.note("check_mark", "not centred")
        self.job.restrict_to_homing("the person said the opening is not on mark 3")
        self._show_note()
        self._show_after_problem()

    def _show_next_page(self, res) -> None:
        from workflow import measurement_messages as M
        nxt = res.detail.get("page", self.job.page + 1)
        title, body = M.M_I1IO_DRIVE_NEXT_PAGE.render(page=getattr(self, "_page_done", nxt - 1),
                                                      next=nxt)
        self._checked_page = None
        self._show("next_page", title, body,
                   [(tr("End measurement"), self._on_end_pressed),
                    (tr("Go on"), self._next)])

    # ---- refusals, stops, problems ------------------------------------------------------
    def _on_refused(self, res) -> None:
        reason = res.reason
        if reason in STOP_REASONS:
            self._show_stopped_by_you(res)
            return
        if reason in ("problem_reported", "only_the_homing_now") and res.kind == REFUSED:
            self._show_after_problem()
            self._show_note()
            return
        if reason == "calibration_due":
            self._next()
            return
        if reason == "report_due" and self.job.report_due is not None:
            self._ask_report(getattr(self, "_report_res", res))
            return
        if reason == "run_has_a_measurement_already" and res.step in ("save", "end") \
                and self._replace_agreed and self._archive is not None:
            # the person agreed at START to replace the run's measurement (the hand path's
            # M-REPLACE window): it is moved to old/ now, at the moment the new one is
            # written, through the tab's own archive (review 10, S-2)
            self._archive()
            self._archived = True
            self._call(self.job.save)
            return
        if res.step == "open" and reason in ("usb_open_refused", "driver_not_installed_for_table",
                                             "i1profiler_running",
                                             "table_held_by_another_program",
                                             "table_held_by_a_kernel_driver") \
                or res.step == "open" and reason.startswith("instrument_"):
            self._show_open_refused(res)
            return
        if res.step == "open":
            self._show_refusal(res, after=self._finish_not_started)
            return
        self._show_refusal(res)

    def _show_open_refused(self, res) -> None:
        from workflow import measurement_messages as M
        d, reason = res.detail, res.reason
        logname = self._log_name
        if reason == "usb_open_refused":
            mid = d.get("message_id", "")
            msg = (M.I1IO_DRIVE_USB_MESSAGE.get(mid)
                   or M.CATALOGUE.get(mid) or M.M_I1IO_DRIVE_USB_UNEXPECTED)
            title, body = msg.render(**_fill(msg, log=logname))
        elif reason == "driver_not_installed_for_table":
            title, body = M.M_I1IO_DRIVE_TABLE_DRIVER.render()
        elif reason == "i1profiler_running":
            title, body = M.M_I1IO_DRIVE_I1PROFILER_OPEN.render()
        elif reason == "table_held_by_another_program":
            holder = ", ".join(str(x) for x in d.get("holders", d.get("names", [])) or []) or "?"
            title, body = M.M_I1IO_DRIVE_BUSY.render(holder=holder)
        elif reason == "table_held_by_a_kernel_driver":
            title, body = M.M_I1IO_DRIVE_USB_LINUX_KERNEL_DRIVER.render(log=logname)
        else:
            seen = ", ".join(f"{k} {v}" for k, v in d.items() if isinstance(v, (int, str)))
            title, body = M.M_I1IO_DRIVE_NOT_I1PRO2.render(seen=seen or "?")
        self._moving_controls(False)
        self._end_btn.setVisible(False)
        self._show("open_refused", title, body, [(tr("Close"), self._close_job_then_finish)])

    def _show_refusal(self, res, after=None) -> None:
        from workflow import measurement_messages as M
        why = reason_text(res.reason, res.detail)
        if res.reason == "measurement_not_written" and getattr(self, "_archived", False):
            why += " " + tr("Your previous measurement was moved to the run's old folder for "
                            "this Save. If this measurement ends without a Save, ChromIQ puts "
                            "it back where it was.")
        title, body = _refused(M, why)
        if after is not None:
            self._show("refused", title, body, [(tr("Close"), after)])
            return
        self._show("refused", title, body, self._way_on_buttons())
        if (res.detail.get("by_person") and res.reason != "person_chose_back") \
                or res.kind == STOPPED:
            self._show_note()

    def _way_on_buttons(self) -> list:
        """What may follow a refusal: carry on, the homing, the ending."""
        j = self.job
        out = []
        if j is not None and j.phase == "open" and j.ended is None and not j.only_home \
                and not j.stopped_by_person and j.state().table is not None \
                and not j.state().sending_closed:
            out.append((tr("Carry on"), self._next))
        if j is not None and j.way_back() == "home_offered":
            out.append((tr("Bring the arm home"), self._on_home))
        if j is None or j.ended is not None or j.phase != "open":
            out.append((tr("Close"), self._close_job))
        # End measurement is the footer's button (always there while the table is open)
        return out

    def _show_stopped_by_you(self, res) -> None:
        from workflow import measurement_messages as M
        title, body = M.M_I1IO_DRIVE_STOPPED_BY_YOU.render()
        self._show("stopped_by_you", title, body, self._way_on_buttons())
        self._show_note()

    def _on_stopped(self, res) -> None:
        """The table part has ended (nothing more is sent): the way back, then the ending."""
        from workflow import measurement_messages as M
        wb = res.way_back
        where = self._where()
        msgs = {"switch_off_pending": M.M_I1IO_DRIVE_SWITCH_OFF,
                "switch_off_unfinished": M.M_I1IO_DRIVE_SWITCH_OFF,
                "link_lost_replug": M.M_I1IO_DRIVE_LINK_LOST,
                "link_lost_switch_off_first": M.M_I1IO_DRIVE_LINK_LOST_SWITCH_OFF,
                "cold_not_started": M.M_I1IO_DRIVE_COLD,
                "cold_way_out": M.M_I1IO_DRIVE_COLD_WAY_OUT,
                "home_offered": M.M_I1IO_DRIVE_HOME_OFFERED}
        msg = msgs.get(wb)
        if msg is None and wb == "none" and res.reason in ("stopped_by_person",
                                                           "cancelled_by_person"):
            title, body = _refused(M, reason_text(res.reason))
        else:
            msg = msg or M.M_I1IO_DRIVE_STOPPED
            title, body = msg.render(**_fill(msg, where=where, log=self._log_name))
            body = reason_text(res.reason, res.detail) + "\n\n" + body
        self._show("stopped", title, body, self._way_on_buttons())
        self._after_stop_controls()
        self._show_note()

    def _after_stop_controls(self) -> None:
        j = self.job
        can_move = (j is not None and j.state().table is not None
                    and not j.state().sending_closed)
        self._moving_controls(can_move)

    def _where(self) -> str:
        j = self.job
        st = j.state() if j is not None else None
        p = (st.position_now or st.last_read) if st is not None else None
        if p is None:
            return tr("no position")
        return tr("X {x}, Y {y} (in tenths of a millimetre)").format(x=int(p[0]), y=int(p[1]))

    def _on_stop(self) -> None:
        if self.job is None:
            return
        self.job.stop_at_next_pause()
        self._troubled = True
        self._status.setText(tr("Stop pressed: ChromIQ stops before the next move. A move that "
                                "has started finishes first."))
        # the report question (asking mode) stays: the stop acts at the next move, after it
        if not self._busy and getattr(self, "_page_id", "") in ("check_mark", "next_page"):
            self._show_stopped_by_you(None)

    def _on_problem(self) -> None:
        from workflow import measurement_messages as M
        title, body = M.M_I1IO_DRIVE_PROBLEM.render()
        self._problem_back = getattr(self, "_page_id", "")
        self._troubled = True
        self._show("problem", title, body,
                   [(tr("Cancel"), self._problem_cancel),
                    (tr("Send nothing more"), self._problem_stop_now),
                    (tr("Something looks or sounds wrong"), self._problem_wrong)])

    def _problem_cancel(self) -> None:
        # nothing reported: the page that was shown comes back with the job's last result
        deferred, self._deferred = getattr(self, "_deferred", None), None
        if deferred is not None:
            then, res = deferred
            then(res)
            return
        if self._busy:
            self._page_id = "working"
            self._show_working(tr("The step goes on"))
            return
        if self._last is not None:
            self._on_result(self._last)

    def _problem_stop_now(self) -> None:
        self._deferred = None                 # a question it held is closed by the report
        res = self.job.report_problem("stop now")
        self._refresh_state()
        self._reported_while_busy()
        self._show_note()
        if not self._busy:
            self._on_stopped(res)

    def _problem_wrong(self) -> None:
        self._deferred = None                 # a question it held is closed by the report
        self.job.report_problem("something looked or sounded wrong")
        self._refresh_state()
        self._reported_while_busy()
        self._show_note()
        if not self._busy:
            self._show_after_problem()

    def _reported_while_busy(self) -> None:
        """The report is in while a step runs: the problem page gives way, and the step's
        result is shown when it comes (the step finishes its move first)."""
        if self._busy:
            self._page_id = "problem_reported"
            self._show_working(tr("Your report is in. The move that has started finishes "
                                  "first; then nothing more moves except bringing the arm "
                                  "home."))

    def _show_after_problem(self) -> None:
        from workflow import measurement_messages as M
        j = self.job
        if j.way_back() == "home_offered" and j.ended is None:
            title, body = M.M_I1IO_DRIVE_HOME_OFFERED.render(where=self._where())
        else:
            title, body = M.M_I1IO_DRIVE_AFTER_PROBLEM.render()
        self._show("after_problem", title, body, self._way_on_buttons())
        if j.way_back() != "home_offered":
            self._moving_controls(False)       # nothing can move any more

    def _show_note(self) -> None:
        self._note_sticky = True
        self._note_box.setVisible(True)

    def _on_save_note(self) -> None:
        text = self._note_edit.toPlainText()
        if self.job is not None and text.strip():
            self.job.add_note(text)
            self._note_edit.setPlainText("")
            self._status.setText(tr("Your note was saved in the diagnostics file of this "
                                    "measurement."))

    def _on_home(self) -> None:
        self._call(self.job.home, status=tr("Bringing the arm home..."))

    # ---- endings --------------------------------------------------------------------------
    def _on_end_pressed(self) -> None:
        if self.job is None or self._busy:
            return
        if self.job.ended is not None:
            self._close_job()
            return
        if self.job.phase == "new":
            self._finish_not_started()
            return
        if isinstance(self._last, object) and getattr(self._last, "kind", "") == NEEDS \
                and self._pending_kind != "end_of_session":
            self._end_after = True
            self.answer(WITHDRAW.get(self._pending_kind, "stop"))
            return
        self._call(self.job.end)

    def _ask_end(self, res) -> None:
        from workflow import measurement_messages as M
        st = res.detail.get("end_state", {})
        n = int(st.get("read_in_this_session") or 0)
        if getattr(self, "_adopted_any", False) and "read" in st:
            total = int(st["read"])
            read_line = (tr("This measurement holds 1 patch, together with the readings of "
                            "the earlier session you chose to complete.") if total == 1 else
                         tr("This measurement holds {n} patches, together with the readings "
                            "of the earlier session you chose to complete.").format(n=total))
        else:
            if "read" in st:
                # distinct patches (a row read again is counted once), as the file will hold
                n = min(n, int(st["read"])) if n else int(st["read"])
            read_line = (tr("You have read 1 patch in this session.") if n == 1
                         else tr("You have read {n} patches in this session.").format(n=n))
        # review 10, S-6: the table's own variant of M-END's choices (§M-PROPOSED): no
        # "window" to close, and no em dash
        body = read_line + " " + M.M_I1IO_DRIVE_END_CHOICES.render()[1]
        body += "\n\n" + M.M_I1IO_DRIVE_END.render()[1]
        self._ending_open = True
        self._pending_kind = "end_of_session"
        self._show("end_of_session", tr("Keep what you have measured so far?"), body,
                   [(choice_label("end_of_session", "save"), self._answer_slot("save")),
                    (choice_label("end_of_session", "discard"), self._answer_slot("discard")),
                    (choice_label("end_of_session", "keep measuring"),
                     self._answer_slot("keep measuring"))])

    def _after_end(self, res) -> None:
        self._ending_open = False
        ending = res.detail.get("ending")
        if ending in ("keep_measuring", "dismissed") and self._quit_wanted:
            # the hand path's rule: Keep measuring cancels the quit
            self._quit_wanted = False
        if ending == "keep_measuring":
            page = res.detail.get("current_page", self.job.page + 1)
            self._again_rows = [r["row"] for r in res.detail.get("missing_rows", [])
                                if r.get("page") == page]
            self._next()
            return
        if ending == "dismissed":
            from workflow import measurement_messages as M
            title, body = M.M_I1IO_DRIVE_ENDING_CLOSED.render()
            self._show("ending_closed", title, body, self._way_on_buttons())
            self._status.setText(tr("ChromIQ stays open."))
            return
        if ending == "saved":
            self._after_saved(res)
            return
        # discarded, or nothing read
        self._offer_home_or_close(res, nothing_read=(ending == "nothing_read"))

    def _after_saved(self, res) -> None:
        if self._run is not None:
            self.saved.emit(Path(self._run.measurement_ti3), dict(res.detail))
        self._offer_home_or_close(res)

    def _offer_home_or_close(self, res, nothing_read: bool = False) -> None:
        if "home" in (res.detail.get("next") or []):
            from workflow import measurement_messages as M
            title, body = M.M_I1IO_DRIVE_HOME_OFFERED.render(where=self._where())
            if nothing_read:
                body = tr("Nothing was measured, so nothing was saved.") + "\n\n" + body
            self._show("home_offered", title, body,
                       [(tr("Leave it there"), self._close_job),
                        (tr("Bring the arm home"), self._on_home)])
            return
        self._close_job()

    def _close_job(self) -> None:
        if self.job is None or self._closed_job:
            self._finish("ended")
            return
        self._call(self.job.close, then=self._after_close)

    def _close_job_then_finish(self) -> None:
        self._close_job()

    def _after_close(self, res) -> None:
        self._closed_job = True
        self._moving_controls(False)
        self._end_btn.setVisible(False)
        from workflow import measurement_messages as M
        j = self.job
        what = {"saved": tr("The measurement was saved into the run."),
                "discarded": tr("The readings of this measurement were discarded; nothing was "
                                "written into the run's measurement."),
                "nothing_read": tr("Nothing was measured, so nothing was saved.")}.get(
            j.ended or "", tr("The measurement was not saved."))
        title, body = M.M_I1IO_DRIVE_DONE.render(what=what, log=self._log_name)
        wb = res.way_back
        if wb not in ("none", "home_offered"):
            msgs = {"switch_off_pending": M.M_I1IO_DRIVE_SWITCH_OFF,
                    "switch_off_unfinished": M.M_I1IO_DRIVE_SWITCH_OFF,
                    "link_lost_replug": M.M_I1IO_DRIVE_LINK_LOST,
                    "link_lost_switch_off_first": M.M_I1IO_DRIVE_LINK_LOST_SWITCH_OFF,
                    "cold_not_started": M.M_I1IO_DRIVE_COLD,
                    "cold_way_out": M.M_I1IO_DRIVE_COLD_WAY_OUT}
            msg = msgs.get(wb, M.M_I1IO_DRIVE_STOPPED)
            body = msg.render(**_fill(msg, where=self._where(), log=self._log_name))[1] + \
                "\n\n" + body
        if self._quit_wanted and wb in ("none", "home_offered"):
            # review 10, B-1: the person quit ChromIQ; the job has let go of the table and
            # nothing waits to be said: ChromIQ closes now
            self._finish("quit")
            return
        ticks = []
        self._offer_dont_ask = (res.detail.get("offer") == "may_offer_do_not_ask_again"
                                and not self._troubled and not self._quit_wanted)
        if self._offer_dont_ask:
            ticks = [tr("Don't ask after each step from now on. (You can switch the question "
                        "back on in Preferences.)")]
        self._show("done", title, body, [(tr("Close"), self._on_done_close)], ticks=ticks)
        if self._quit_wanted:
            self._status.setText(tr("ChromIQ closes when you press Close."))
        self._close_btn.setVisible(False)
        self._state.setVisible(False)          # the session is over; the text says how

    def _on_done_close(self) -> None:
        if getattr(self, "_offer_dont_ask", False) and self._tick_widgets \
                and self._tick_widgets[0].isChecked():
            self._settings.set(ASK_KEY, False)
        self._finish("ended")

    # ---- closing the window ----------------------------------------------------------------
    def _table_can_be_left(self) -> bool:
        """The window may close: nothing opened yet, or the job closed (let go of the USB)."""
        return self.job is None or self.job.phase in ("new", "closed")

    def _on_close_pressed(self) -> None:
        if self._busy:
            return
        if self._table_can_be_left():
            self._finish(getattr(self, "_why_not", "not_started"))
            return
        if self._ending_open:
            self._dismiss_end()
            return
        self._on_end_pressed()

    def _dismiss_end(self) -> None:
        self._ending_open = False
        self._call(self.job.dismiss_end)

    def _finish_not_started(self) -> None:
        if self.job is not None and self.job.phase == "open":
            self._close_job()
            return
        self._finish(getattr(self, "_why_not", "not_started"))

    def _finish(self, why: str) -> None:
        if self._finished:
            return
        self._finished = True
        self.progress.emit({"event": "end"})
        self.setVisible(False)
        self.finished_with.emit("quit" if self._quit_wanted else why)

    # ---- quitting ChromIQ during a session (review 10, B-1) ---------------------------------
    def _quit_hint(self) -> str:
        if not getattr(self, "_quit_wanted", False):
            return ""
        return tr("You asked ChromIQ to quit. It closes once this table measurement has "
                  "ended here.")

    def request_quit(self) -> bool:
        """The main window's close (Cmd-Q, the close box, a logout) during this session. True:
        nothing is open, the panel has finished and ChromIQ may close now. False: the table's
        own ending is asked here first (the same questions as End measurement; nothing moves
        without the hands-off GO), and when it has run and the job has let go of the table
        (``close()``: the USB released, the session's markers written), the panel finishes
        with "quit" and the tab closes ChromIQ. A step that is running ends at its next pause
        (Stop: the move that has started finishes) before the ending is asked."""
        if self._finished:
            return True
        j = self.job
        if j is None or j.phase == "new" or self._closed_job or j.phase == "closed":
            self._finish(getattr(self, "_why_not", "not_started") if self._closed_job is False
                         else "ended")
            return True
        self._quit_wanted = True
        if self._busy:
            j.stop_at_next_pause()
            self._troubled = True
            self._end_after = True
            self._status.setText(tr("You asked ChromIQ to quit. The table stops before its next "
                                    "move; then ChromIQ asks what to do with your readings, "
                                    "and closes after that."))
            return False
        if self._ending_open or j.ended is not None:
            # the ending is on screen, or saved / discarded already and the homing offer (or
            # Close) on screen decides: the person's answer there ends it
            self._status.setText(self._quit_hint())
            return False
        self._on_end_pressed()
        return False

    def _relay_progress(self, ev: dict) -> None:
        self._live_event(ev)
        self.progress.emit(dict(ev))

    def _aim_event(self, mark, patch=None) -> None:
        """Where the arm should point now (display only): mark *mark* of the job's page, or
        the corner patch the chart names for it."""
        page = (self.job.page + 1) if self.job is not None else 1
        self.progress.emit({"event": "aim", "mark": mark, "patch": patch, "page": page})

    def reject(self) -> None:          # Esc
        self._on_close_pressed()

    def closeEvent(self, event) -> None:   # the window's X
        if self._finished:
            event.accept()
            return
        event.ignore()
        self._on_close_pressed()


class _Answer:
    """A bound method for one answer button."""

    def __init__(self, win: TableMeasureWindow, value: str) -> None:
        self.win, self.value = win, value

    def fire(self) -> None:
        self.win.answer(self.value)


class _Report:
    def __init__(self, win: TableMeasureWindow, value: str) -> None:
        self.win, self.value = win, value

    def fire(self) -> None:
        self.win.report(self.value)


def _refused(M, why: str) -> "tuple[str, str]":
    """M-I1IO-DRIVE-REFUSED with the reason; the true state is the panel under it."""
    return M.M_I1IO_DRIVE_REFUSED.render(why=why)


def _fill(msg, **kw) -> dict:
    """Only the placeholders *msg* has (a message never gets a key it does not name)."""
    import re
    names = set(re.findall(r"\{(\w+)\}", msg.body + msg.title + (msg.body_one or "")))
    return {k: v for k, v in kw.items() if k in names}
