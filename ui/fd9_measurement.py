"""Measure-tab routing for the Konica Minolta FD-9. Device work stays off the
GUI thread.

FD-9 support was written and contributed by lessbones (PR #213). It is a Beta
(Preferences > Beta, restart to apply, `workflow.fd9.support`): with it off,
`TabMeasure` never builds the FD-9 panel (`_init_fd9_panel` is not called), so
`_fd9_on()` is False, every hook in the tab answers "not an FD-9 chart" without
reading a file, and nothing here runs. `workflow.fd9.measurement` and the
vendored driver are imported only from inside the methods, so with the option
off they are not even loaded (`tests/test_fd9_off_changes_nothing.py`).

Every window here takes its text from the §M catalogue
(`workflow.measurement_messages`, M-FD9-*), through `_fd9_window`.
"""

import re
import threading
from dataclasses import replace
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core import instrument_lease
from core.i18n import tr
from core.keep_awake import keep_awake
from core.logger import get_logger
from core.thread_stack import roomy

log = get_logger(__name__)

#: FD-9 jobs that have been started and may not have finished yet.
#:
#: NOT PARENTED TO THE TAB, for the reason `workflow/cr30/measure_bridge.py`
#: records for its `_LIVE`: a QThread destroyed while it still runs calls
#: qFatal(), and a parent and its thread in a reference cycle are freed by the
#: cyclic collector at an arbitrary moment. Holding the job here keeps it
#: reachable until it has said it is finished (review M11).
_LIVE_JOBS: "list[QThread]" = []


def _measure_chart(*args, **kwargs):
    from workflow.fd9.measurement import measure_chart
    return measure_chart(*args, **kwargs)


class FD9Job(QThread):
    progress = pyqtSignal(str)
    readings = pyqtSignal(int)
    scan_ready = pyqtSignal(object)
    patch_ready = pyqtSignal(object)
    page_requested = pyqtSignal(int, int)
    result = pyqtSignal(object)
    #: (message, stopped by the user, which M-FD9-* window: `fd9_exception_kind`)
    failed = pyqtSignal(str, bool, str)

    def __init__(self, chart, settings, session, parent=None, action=None):
        super().__init__(parent)
        roomy(self)
        self.chart = chart
        self.settings = settings
        self.session = session
        self.action = action or _measure_chart
        self.stop_event = threading.Event()
        self.new_readings = 0

    def run(self):
        try:
            self.result.emit(
                self.action(
                    self.chart,
                    self.settings,
                    self.session,
                    progress=self.progress.emit,
                    cancelled=self.stop_event.is_set,
                    on_readings=self.note_readings,
                    on_scan=self.scan_ready.emit,
                    on_patch=self.patch_ready.emit,
                    on_page=self.queue_page,
                )
            )
        except Exception as e:
            self.failed.emit(str(e), self.stop_event.is_set(),
                             fd9_exception_kind(e))

    def note_readings(self, count):
        self.new_readings = count
        self.readings.emit(count)

    def queue_page(self, page, pages):
        if self.stop_event.is_set():
            raise InterruptedError("Operator stopped between FD-9 pages")
        if page > 1:
            self.page_requested.emit(page, pages)

    def request_stop(self):
        self.stop_event.set()


def condition_help() -> "tuple[str, str]":
    """The (i) beside the M0 / M1 / M2 choice: title and text."""
    return tr("Measurement condition (M0, M1, M2)"), "\n\n".join((
        tr("M0, M1 and M2 are the measurement conditions of the ISO 13655 "
           "standard. They differ in how much ultraviolet light is in the light "
           "the FD-9 measures with, and that matters for papers with optical "
           "brighteners (OBAs). Brighteners are added to many papers to make "
           "them look whiter: they turn invisible ultraviolet light into "
           "visible blue light, so the paper looks bluer and brighter the more "
           "ultraviolet there is."),
        tr("  •  M1 is like daylight (D50), with its ultraviolet, so the "
           "brighteners glow as they do in daylight. It is the usual choice "
           "for printing today and the default here. If you are not sure, "
           "choose M1.\n"
           "  •  M2 leaves the ultraviolet out (UV cut), so the brighteners do "
           "not glow. Choose it when your prints will be looked at under light "
           "with little or no ultraviolet, such as many indoor and LED lights, "
           "or when you want to compare with other M2 measurements.\n"
           "  •  M0 is how many older instruments measure, with a lamp whose "
           "ultraviolet is not defined. Choose it only to compare with older "
           "measurements made that way."),
        tr("On a paper without brighteners the three give almost the same "
           "colours. On a paper with them, M1 and M2 can differ clearly, "
           "mostly in the paper white and the light colours."),
        tr("The FD-9 measures all three at once, but ChromIQ saves the "
           "measurement only for the condition chosen here. Choose it before "
           "you press Start. Resume continues only with the same condition, so keep it "
           "the same until the chart is finished."),
        tr("**Default:** M1"),
    ))


def setup_note() -> str:
    """The explanation in the FD-9 setup window."""
    return tr(
        "ChromIQ measures with the FD-9 directly over your network, with its "
        "own driver. It reads the FD-9's own factory calibration from the "
        "instrument, so no Konica Minolta software, conversion profile or "
        "reference measurement is needed.\n\n"
        "Enter the address the FD-9 has on your network (an IP address such as "
        "192.168.1.50). The FD-9 and this computer must be on the same "
        "network, and no other program may be connected to the FD-9 while "
        "ChromIQ measures.\n\n"
        "FD-9 support is a beta and has been tested on one FD-9, on macOS. It "
        "works only with an FD-9 whose measuring sensor reports the version "
        "1.0.0.2, and ChromIQ checks that before the FD-9 moves anything.")


class FD9Setup(QDialog):
    """The FD-9's network address, kept in AppSettings ("fd9_host") so that
    CHROMIQ_SETTINGS_FILE sandboxes it like every other setting (review M3)."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setObjectName("fd9_setup")
        self.setWindowTitle(tr("FD-9 setup"))
        self.resize(560, 300)
        self.store = settings
        layout = QVBoxLayout(self)
        note = QLabel(setup_note())
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        layout.addLayout(form)
        self.host = QLineEdit(str(settings.get("fd9_host", "") or ""))
        self.host.setPlaceholderText("192.168.1.50")
        form.addRow(tr("Network address:"), self.host)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save(self):
        self.store.set("fd9_host", self.host.text().strip())
        self.accept()


#: The driver's English progress lines, and what the log says instead. The
#: driver is lessbones' package and stays as he wrote it; the user reads these.
def _progress_line(text: str) -> "tuple[str | None, str]":
    """(stage, line for the log) for one progress line of the driver."""
    if text.startswith("Remove any previously ejected sheet"):
        return "prepare", tr(
            "If a sheet from an earlier measurement is still in or at the "
            "FD-9, take it out completely. Keep this chart outside until the "
            "FD-9 is ready for it.")
    if text.startswith("FD9 insertion screen ready"):
        return "insert", tr(
            "The FD-9 is ready: insert the chart now, arrow first and printed "
            "side up.")
    if text.startswith("Sheet detected"):
        return "sheet_in", tr(
            "The FD-9 has the sheet and is looking for the chart on it.")
    m = re.match(r"Four marks verified\. Measuring (\d+) ", text)
    if m:
        return "measuring", tr(
            "The FD-9 found the chart. Measuring {n} patches.").format(
                n=int(m.group(1)))
    m = re.match(r"FD9 measurement: (\d+)/(\d+) patches", text)
    if m:
        return None, tr("FD-9: {count} of {total} patches measured.").format(
            count=int(m.group(1)), total=int(m.group(2)))
    if text.startswith("Measurement complete."):
        return "done", tr(
            "The FD-9 has finished measuring. Take the sheet completely out of "
            "the FD-9, past its paper sensor, before you start another "
            "measurement.")
    return None, text


def fd9_error_kind(message: str) -> str:
    """Which M-FD9-* window an error belongs to."""
    low = str(message or "").lower()
    # The vendored driver says "Sensor model version is not supported"
    # (instrument_model.py); the older wording is kept for saved sessions.
    if ("unsupported sensor model version" in low
            or "sensor model version is not supported" in low):
        return "firmware"
    if any(k in low for k in (
            "isolated square marks", "marks do not form", "chart skew",
            "grid must lie within the marks", "measurement cell lies outside")):
        return "marks"
    if low.startswith("resume") or any(k in low for k in (
            "only a consistent partial measurement can resume",
            "saved measurement printer calibration differs",
            "resume requires", "resume needs", "resume measurement",
            "resume factory", "resume spectral", "resume conversion",
            "pending measurement belongs to another chart")):
        return "resume"
    if "operator stopped" in low:
        return "stopped"
    if any(k in low for k in (
            "timed out", "connection refused", "no route to host",
            "network is unreachable", "host is down", "closed the connection",
            "deadline expired", "registration was declined",
            "nodename nor servname", "name or service not known",
            "connection reset", "connection abort", "broken pipe",
            "not connected",
            # Windows says it its own way (WinError 10061, 10060, 10065).
            "no connection could be made", "actively refused",
            "did not properly respond", "host has failed to respond",
            "unreachable host")):
        # Not "errno": every OSError says it, a missing layout file and an
        # unwritable session folder too, and neither is the network (review
        # r1 F4). The words a network fault puts after its [Errno N] are
        # listed above instead.
        return "connection"
    return "failed"


def _network_errnos() -> "set[int]":
    import errno
    return {getattr(errno, n) for n in (
        "ECONNREFUSED", "ECONNRESET", "ECONNABORTED", "EHOSTUNREACH",
        "EHOSTDOWN", "ENETUNREACH", "ENETDOWN", "ETIMEDOUT", "EPIPE",
        "ENOTCONN") if hasattr(errno, n)}


def fd9_exception_kind(error: BaseException) -> str:
    """Which M-FD9-* window an exception belongs to: by its TYPE first, so a
    network fault is a connection problem whatever it says, and any other
    OSError (a missing file, a folder that cannot be written) never is
    (review r1 F4). Then by its words, for the driver's own messages."""
    import socket
    # A capture that failed is wrapped ("Capture failed; evidence preserved:
    # ...") with the exception that ended it kept as its cause: that
    # exception's TYPE decides, not the wrapper's (review r2 M2).
    cause = getattr(error, "cause", None)
    if isinstance(cause, BaseException) and cause is not error:
        return fd9_exception_kind(cause)
    if isinstance(error, (ConnectionError, TimeoutError, socket.gaierror,
                          socket.herror)):
        return "connection"
    kind = fd9_error_kind(str(error))
    if (kind == "connection" and isinstance(error, OSError)
            and error.errno not in _network_errnos()):
        return "failed"
    return kind


def fd9_start_kind(error: BaseException) -> str:
    """The window for a fault BEFORE the worker started: nothing has been
    sent to the FD-9 yet, so it is never a connection problem. A refused
    resume keeps its own window; anything else is M-FD9-FAILED, which shows
    the reason (review r1 F4)."""
    kind = fd9_error_kind(str(error))
    return kind if kind == "resume" else "failed"


class FD9MeasureMixin:
    #: Class defaults, so every hook in TabMeasure can ask without getattr and
    #: with FD-9 support off the answers are the "nothing here" ones.
    _fd9_live = False
    _fd9_pending = None
    _fd9_job = None
    _fd9_shown = False
    _fd9_scan_preview = None
    _fd9_readings = 0
    _fd9_choice = None

    def _fd9_on(self) -> bool:
        """True when this tab has FD-9 support (the Beta was on at start-up)."""
        return "_fd9_panel" in self.__dict__

    def _init_fd9_panel(self, layout):
        """Build the FD-9 row. Called by TabMeasure only while FD-9 support is
        on (`workflow.fd9.support.fd9_enabled`)."""
        from ui.tooltip_button import TooltipButton

        self._fd9_live = False
        self._fd9_job = None
        self._fd9_awake = False
        self._fd9_pending = None
        self._fd9_choice = None
        self._fd9_ending = False
        self._fd9_deferred = None
        self._fd9_readings = 0
        self._fd9_seed_unsaved = 0
        self._fd9_scan_preview = None
        self._fd9_scan_previews = {}
        self._fd9_live_colours = {}
        self._fd9_scan_chart = None
        self._fd9_ordered_locations = []
        self._fd9_acquisition_locations = None
        self._fd9_prior_count = 0
        self._fd9_prior_measurement = None
        self._fd9_shown = False
        self._fd9_sheet_in = False
        self._fd9_insert_box = None
        self._fd9_session = None
        panel = QWidget(self)
        panel.setObjectName("fd9_panel")
        row = QHBoxLayout(panel)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel(tr("FD-9 condition:")))
        self._fd9_condition = QComboBox()
        self._fd9_condition.setObjectName("fd9_condition")
        # ISO condition identifiers are language-independent profile values.
        for condition in ("M0", "M1", "M2"):
            self._fd9_condition.addItem(condition, condition)
        self._fd9_condition.setCurrentText("M1")
        row.addWidget(self._fd9_condition)
        row.addWidget(TooltipButton(*condition_help(), self, min_width=620))
        self._fd9_resume = QCheckBox(tr("Resume"))
        self._fd9_resume.setObjectName("fd9_resume")
        self._fd9_resume.setToolTip(tr(
            "Continue this chart's measurement from the first row the FD-9 has "
            "not measured yet. Insert the same sheet again; the rows already "
            "measured are kept. Offered when the chart is partly measured."))
        self._fd9_resume.toggled.connect(self._fd9_resume_changed)
        row.addWidget(self._fd9_resume)
        self._fd9_setup_btn = QPushButton(tr("FD-9 setup…"))
        self._fd9_setup_btn.setObjectName("fd9_setup_button")
        self._fd9_setup_btn.setToolTip(tr(
            "Enter the FD-9's network address."))
        self._fd9_setup_btn.clicked.connect(self._configure_fd9)
        row.addWidget(self._fd9_setup_btn)
        row.addStretch()
        layout.addWidget(panel)
        panel.hide()
        self._fd9_panel = panel

    # ---- windows (text from the §M catalogue only) ------------------------
    def _fd9_window(self, message, **kw):
        """One M-FD9-* window: the catalogue's text, in the log and on screen.
        Returns the box after it closed (tests replace this method)."""
        from PyQt6.QtWidgets import QMessageBox
        from workflow import measurement_messages as M  # noqa: F401 (catalogue)
        title, body = message.render(**kw)
        self._log.appendPlainText(f"[{title}]\n{body}")
        self._log.ensureCursorVisible()
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle(title)
        box.setText(title)
        box.setInformativeText(body)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        from ui.widgets import (fit_message_box_buttons,
                                keep_message_box_inside_the_work_area)
        keep_message_box_inside_the_work_area(box, widen_when_it_fits=False)
        fit_message_box_buttons(box)
        box.exec()
        return box

    def _fd9_show_insert_window(self):
        """M-FD9-INSERT-SHEET, NOT modal: the worker is waiting for the sheet
        and the window closes by itself once the FD-9 has it."""
        from PyQt6.QtWidgets import QMessageBox
        from workflow import measurement_messages as M
        self._fd9_close_insert_window()
        title, body = M.M_FD9_INSERT_SHEET.render()
        box = QMessageBox(self)
        box.setObjectName("fd9_insert_sheet")
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle(title)
        box.setText(title)
        box.setInformativeText(body)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.setModal(False)
        from ui.widgets import keep_message_box_inside_the_work_area
        keep_message_box_inside_the_work_area(box, widen_when_it_fits=False)
        self._fd9_insert_box = box
        box.show()

    def _fd9_close_insert_window(self):
        box = self._fd9_insert_box
        self._fd9_insert_box = None
        if box is not None:
            try:
                box.close()
                box.deleteLater()
            except RuntimeError:
                pass

    def _fd9_explain_error(self, message, cancelled=False, kind=""):
        """Put an error into words, in the window that fits it. *kind* is the
        one `fd9_exception_kind` / `fd9_start_kind` found from the exception
        itself; without it the words decide (`fd9_error_kind`)."""
        from workflow import measurement_messages as M
        kind = "stopped" if cancelled else (kind or fd9_error_kind(message))
        sheet_in = bool(getattr(self, "_fd9_sheet_in", False))
        self._fd9_sheet_in = False
        if kind == "stopped":
            if sheet_in:
                self._fd9_window(M.M_FD9_SHEET_STILL_INSIDE)
            return
        reason = str(message or "").replace(
            "Capture failed; evidence preserved: ", "")
        if kind == "firmware":
            self._fd9_window(M.M_FD9_WRONG_FIRMWARE, reason=reason)
        elif kind == "marks":
            self._fd9_window(M.M_FD9_MARKS_NOT_FOUND, reason=reason)
        elif kind == "resume":
            self._fd9_window(M.M_FD9_RESUME_REFUSED, reason=reason)
        elif kind == "connection":
            self._fd9_window(M.M_FD9_NO_CONNECTION, reason=reason,
                             address=self._fd9_host() or "?")
        else:
            self._fd9_window(M.M_FD9_FAILED, reason=reason)

    # ---- state ------------------------------------------------------------
    def _fd9_resume_changed(self, checked):
        self._refresh_start_button_label()

    def _configure_fd9(self):
        FD9Setup(self._settings, self).exec()

    def _fd9_host(self) -> str:
        try:
            return str(self._settings.get("fd9_host", "") or "").strip()
        except Exception:  # noqa: BLE001
            return ""

    def _is_fd9_target(self):
        """True when FD-9 support is on and the loaded chart is an FD-9 chart.

        With FD-9 support off this is False without reading anything."""
        if not self._fd9_on():
            return False
        path = getattr(self, "_ti1_path", None)
        if not path:
            return False
        from workflow.fd9.measurement import is_fd9_chart
        return bool(is_fd9_chart(self._chart_file_for(path)))

    def _fd9_holds_a_result(self) -> bool:
        """True while an FD-9 read is live or its stopped result still waits
        for the end window ("Keep measuring" leaves it waiting). The chart file
        group stays greyed until then, so another chart cannot be loaded over a
        result that is not settled yet (review r1 F1)."""
        return bool(self._fd9_live or self._fd9_pending is not None)

    def _fd9_engaged(self) -> bool:
        """True when the FD-9 owns the tab's endings (Stop, quit, the end
        window): a read is live, or a waiting result belongs to the chart that
        is loaded NOW. A result left for another chart never takes over a
        normal chart's Stop or quit (review r1 F1)."""
        if self._fd9_live:
            return True
        pending = self._fd9_pending
        if pending is None:
            return False
        if not pending.get("chart"):
            return True           # no chart recorded: it may be this one
        try:
            loaded = self._chart_file_for(self._ti1_path).resolve()
            return Path(pending["chart"]).resolve() == loaded
        except Exception:  # noqa: BLE001 - no loaded chart, not this result
            return False

    def _fd9_settle(self):
        """An FD-9 ending: put a stored chart set aside at Start back, the way
        `_settles_the_replaced_chart` does after every chartread ending
        (review r1 F2). `_settle_the_replaced_chart` keeps it while the FD-9
        is still reading or a result still waits to be saved or resumed."""
        settle = getattr(self, "_settle_the_replaced_chart", None)
        if settle is not None:
            settle()

    def _fd9_options_locked(self) -> bool:
        """The chartread options are greyed while an FD-9 chart is loaded:
        none of them applies to the FD-9 (patch by patch included).
        `TabMeasure._set_settings_enabled` asks this, so a running read's own
        lock and this one never overwrite each other (review H3)."""
        return bool(self._fd9_shown)

    def _refresh_fd9_panel(self):
        """Follow the loaded chart. The option areas change ONLY when the tab
        enters or leaves an FD-9 chart, and then through the same rule
        `_set_settings_enabled` applies: never a blanket "enabled" over the
        lock of a running read (review H3)."""
        if not self._fd9_on():
            return
        active = self._is_fd9_target()
        self._fd9_panel.setVisible(active)
        if active != self._fd9_shown:
            self._fd9_shown = active
            unlocked = bool(getattr(self, "_settings_unlocked", True))
            for name in ("_g_options", "_m_options", "_m_presets_grp"):
                widget = getattr(self, name, None)
                if widget is not None:
                    widget.setEnabled(unlocked and not active)
            btn = getattr(self, "_save_defaults_btn", None)
            if btn is not None:
                btn.setEnabled(unlocked and not active)
            if not active:
                self._fd9_close_insert_window()
                # Give the preview back what the FD-9 changed on it: the
                # swipe arrow (the CR30 rule decides it again) and the FD-9's
                # own notice, if it is still the one showing. Found on screen:
                # a normal chart after an FD-9 chart kept "no swipe".
                self._preview.set_no_swipe(self._chart_is_cr30())
                self._preview.set_scan_grid(None)
                lbl = getattr(self._preview, "_notice_lbl", None)
                if lbl is not None and lbl.text() in self._fd9_notices():
                    self._preview.set_notice(None)
                if hasattr(self, "_calm_outer"):
                    self._calm_outer.setVisible(self._current_mode() == "guided")
        if not active:
            return
        from workflow.measurement_state import Ti3State, classify

        chart = self._chart_file_for(self._ti1_path)
        try:
            partial = classify(chart.with_suffix(".ti3"), chart).state is Ti3State.PARTIAL
        except Exception:  # noqa: BLE001
            partial = False
        available = self._fd9_pending is not None or partial
        self._fd9_resume.setVisible(available)
        if not available:
            self._fd9_resume.setChecked(False)
        self._refresh_start_button_label()
        self._preview.set_no_swipe(True)
        if hasattr(self, "_calm_outer"):
            self._calm_outer.hide()

    @staticmethod
    def _fd9_notices() -> "tuple[str, str]":
        """The two notices the FD-9 puts under the preview."""
        return (
            tr("FD-9 layout preview: the colours are approximate, and this is not the file that is printed."),
            tr("FD-9 scan of the sheet: rows outlined in green are measured, the amber row is next, and blue rows are still to come."),
        )

    def _fd9_resumes(self) -> bool:
        """The FD-9 twin of `_read_builds_on_existing`."""
        return bool(self._fd9_pending is not None or (
            not self._fd9_resume.isHidden() and self._fd9_resume.isChecked()))

    # ---- preview ----------------------------------------------------------
    def _fd9_load_preview(self, base_path):
        """Display-only geometry diagram, never a printable chart TIFF."""
        from PIL import Image, ImageDraw
        from PyQt6.QtCore import QRect

        from workflow.fd9.measurement import checked_chart, sha
        from workflow.fd9.sessions import preview_cache_dir

        try:
            chart = self._chart_file_for(base_path)
            layout_path, layout, locations = checked_chart(chart)
            self._fd9_ordered_locations = [
                locations[p["id"]] for row in layout["rows"] for p in row
            ]
            if self._fd9_scan_chart == str(chart.resolve()) and self._fd9_scan_preview:
                event = self._fd9_scan_preview
            else:
                from workflow.fd9.preview import saved_scan_preview

                event = None if self._fd9_live else saved_scan_preview(chart)
            if event and event["layout_sha256"] == sha(layout_path) and layout.get("schema") != 2:
                self._fd9_show_scan(event, chart)
                return True
            self._fd9_scan_preview = None
            self._fd9_scan_chart = None
            from workflow.fd9.chart import chart_pages
            pages = chart_pages(layout)
            cache = preview_cache_dir(chart)
            cache.mkdir(parents=True, exist_ok=True)
            paths, page_boxes, stripe_rects = [], [], []
            for page_index, page in enumerate(pages):
                scale = 4
                paper = page.get("paper_mm", [137, 300])
                patch = page.get("patch_mm", [8, 8])
                image = Image.new(
                    "RGB", (round(paper[0] * scale), round(paper[1] * scale)), "white"
                )
                draw = ImageDraw.Draw(image)
                boxes = {}
                for row in page["rows"]:
                    for c, p in enumerate(row):
                        values = dict(zip(page["channel_tokens"], p["device_values"]))
                        cyan = min(1, (values.get("C", 0) + values.get("c", 0)) / 100)
                        magenta = min(1, (values.get("M", 0) + values.get("m", 0)) / 100)
                        yellow = values.get("Y", 0) / 100
                        black = min(
                            1,
                            (values.get("K", 0) + values.get("k", 0) + values.get("1k", 0))
                            / 100,
                        )
                        red, green, blue = (values.get(k, 0) / 100 for k in ("R", "G", "B"))
                        rgb = tuple(
                            round(255 * max(0, 1 - a - b - c) * (1 - black))
                            for a, b, c in (
                                (cyan, green, blue),
                                (magenta, red, blue),
                                (yellow, red, green),
                            )
                        )
                        # RGB channels are additive device values, not the red,
                        # green and blue spot inks of a CMYK+N target.
                        rep = page.get("color_rep")
                        if rep in ("RGB", "iRGB") and set(values) == {"R", "G", "B"}:
                            rgb = tuple(
                                round(255 * values[k] / 100) for k in ("R", "G", "B")
                            )
                        elif rep in ("W", "K") and len(values) == 1:
                            gray = next(iter(values.values()))
                            if rep == "K":
                                gray = 100 - gray
                            rgb = (round(255 * gray / 100),) * 3
                        x, y = p["centre_mm"]
                        rect = QRect(
                            round((x - patch[0] / 2) * scale),
                            round((y - patch[1] / 2) * scale),
                            round(patch[0] * scale),
                            round(patch[1] * scale),
                        )
                        draw.rectangle(
                            [rect.x(), rect.y(), rect.right(), rect.bottom()], fill=rgb
                        )
                        boxes[locations[p["id"]]] = rect
                for x, y in page["fiducials_mm"]:
                    draw.rectangle(
                        [
                            round((x - 1.5) * scale),
                            round((y - 1.5) * scale),
                            round((x + 1.5) * scale),
                            round((y + 1.5) * scale),
                        ],
                        fill="black",
                    )
                middle = paper[0] * scale / 2
                draw.polygon(
                    [
                        (middle, 20),
                        (middle - 12, 40),
                        (middle - 4, 40),
                        (middle - 4, 65),
                        (middle + 4, 65),
                        (middle + 4, 40),
                        (middle + 12, 40),
                    ],
                    fill="black",
                )
                path = cache / ("fd9-preview-" + sha(layout_path)[:12] + f"-{page_index+1}.png")
                image.save(path)
                paths.append(path)
                page_boxes.append(boxes)
                self._fd9_use_rows_as_strips(page["rows"], list(boxes.values()))
                stripe_rects.append(self._page_stripe_rects[0])
            self._tiff_pages = paths
            self._preview.load_tiff(paths)
            self._patch_boxes = page_boxes
            self._page_stripe_rects = stripe_rects
            self._strips_per_page = [len(r) for r in stripe_rects]
            self._preview.set_page_patch_boxes({i: list(b.values()) for i,b in enumerate(page_boxes)})
            self._preview.set_stripe_rects(stripe_rects[0], "base")
            if event and event["layout_sha256"] == sha(layout_path):
                self._fd9_show_scan(event, chart)
            self._preview.set_no_swipe(True)
            self._preview.set_notice(
                tr("FD-9 layout preview: the colours are approximate, and this is not the file that is printed.")
            )
            return True
        except Exception as e:
            self._fd9_log("[FD9 preview] " + str(e))
            return False

    def _fd9_use_rows_as_strips(self, rows, boxes):
        """The FD-9 reads ROWS, so a row is what the preview may light up as
        "the strip", never a column (review M10). No swipe arrow: the FD-9
        moves the sheet itself."""
        ncols = len(rows[0]) if rows else 0
        strips = []
        for r in range(len(rows)):
            row_boxes = boxes[r * ncols:(r + 1) * ncols]
            if not row_boxes:
                continue
            rect = row_boxes[0]
            for b in row_boxes[1:]:
                rect = rect.united(b)
            strips.append(rect)
        self._page_stripe_rects = [strips]
        self._strips_per_page = [len(strips)]
        self._preview.set_stripe_rects(strips, "base")
        self._preview.set_stripe_click_enabled(False)
        self._preview.set_no_swipe(True)

    # ---- start ------------------------------------------------------------
    def _fd9_settings(self):
        from workflow.fd9.measurement import FD9Settings

        # Always the bundled driver: the hidden "driver_source" key that could
        # load Python from any folder is gone from the app (review M3).
        return FD9Settings(
            None,
            None,
            None,
            None,
            self._fd9_host(),
            self._fd9_condition.currentText(),
            True,  # Selecting an FD-9 chart selects its independent driver.
            conversion_source="instrument_firmware",
        )

    def _start_fd9_measurement(self):
        """Start on an FD-9 chart: THE SAME PREFLIGHT AS EVERY INSTRUMENT
        (review H4: §5's replace warnings, W6, the autosave recovery and the
        verification resume staging), then the FD-9 worker."""
        from workflow import measurement_messages as M
        from workflow.fd9.measurement import checked_chart, resume_plan, sha

        if self._fd9_live or self._runner.is_running:
            return
        if not self._ti1_path:
            return
        self._recover_engine_autosave()       # M3, before §3a looks at the .ti3
        if self._blocked_by_new_run() or self._blocked_by_missing_chart_file():
            return
        # Another window holding the instrument is asked FIRST, before any
        # question or snapshot, and in the window every instrument uses,
        # M-INSTRUMENT-BUSY (review r1 F7). The acquire below stays, for the
        # moment between this and the start.
        busy = instrument_lease.held_by_other(self)
        if busy is not None:
            self._instrument_busy_window(busy)
            return
        resumes = self._fd9_resumes()
        if self._blocked_by_a_misfitting_measurement(
                params=type("P", (), {"resume": resumes})()):
            return
        if not self._fd9_host():
            self._fd9_window(M.M_FD9_NO_ADDRESS)
            return
        block = self._verification_guard()
        if block:
            self._show_verification_guard(block)
            return
        # The verification chart's copy FIRST, then §5's replace question,
        # in the order every other instrument's Start asks them (review r2
        # M3, `TabMeasure._on_start`).
        if not self._snapshot_verification_chart():
            return
        if self._fd9_pending is None and not self._confirm_replacing_measurement():
            return
        staged = False
        try:
            chart = self._chart_file_for(self._ti1_path)
            checked_chart(chart)
            settings = self._fd9_settings()
            if self._fd9_pending:
                pending = self._fd9_pending
                existing = chart.with_suffix(".ti3")
                if str(chart) != pending["chart"] or (
                    sha(existing) if existing.exists() else None
                ) != pending.get("base_sha256"):
                    raise ValueError(
                        "Pending measurement belongs to another chart or changed measurement"
                    )
            elif self._stage_verification_for_resume() is not None:
                staged = True
            settings = replace(
                settings,
                resume=resumes or staged,
                resume_source=(
                    Path(self._fd9_pending["staged"]) if self._fd9_pending else None
                ),
            )
            settings.validate()
            prior_path, prior_rows, _ = resume_plan(chart, settings)
            if not instrument_lease.acquire(self, instrument_lease.MEASURE_TAB):
                raise ValueError(tr("Another window is using the instrument. Close it, then press Start again."))
            from workflow.fd9.sessions import new_session_dir

            session = new_session_dir(chart)
            from workflow.measurement_session import MeasurementSession

            self._fd9_guard = MeasurementSession(chart.with_suffix(".ti3"), chart)
            self._fd9_guard.begin()
            self._fd9_seed_unsaved = (
                self._fd9_pending.get(
                    "unsaved_readings", self._fd9_pending.get("new_readings", 0)
                )
                if self._fd9_pending
                else 0
            )
            self._fd9_readings = self._fd9_seed_unsaved
            self._fd9_choice = None
            self._fd9_sheet_in = False
            self._fd9_active_settings = settings
            self._fd9_session = session
            self._fd9_condition.setCurrentText(settings.condition)
            self.save_target_settings()
            self._fd9_live = True
            self._fd9_prior_count = len(prior_rows)
            self._fd9_prior_measurement = prior_path
            self._live_expected = self._expected_source_for(chart.with_suffix(".ti3"))
            self._reset_flag_judge()
            self._fd9_scan_preview = None
            self._fd9_scan_previews = {}
            self._fd9_live_colours = {}
            self._fd9_acquisition_locations = None
            self._fd9_scan_chart = None
            self._fd9_load_preview(chart)
            self._reset_progress(from_files=False)
            self._progress_file_locs = {row["SAMPLE_LOC"] for row in prior_rows}
            self._progress_base = len(prior_rows)
            if prior_rows:
                self._fd9_restore_scan_colours(chart)
            self._refresh_progress()
            self._set_settings_enabled(False)
            self._fd9_panel.setEnabled(False)
            self._start_btn.setEnabled(False)
            self._stop_btn.setEnabled(True)
            self._calibrate_btn.setEnabled(False)
            job = FD9Job(chart, settings, session, None)   # unparented: _LIVE_JOBS
            _LIVE_JOBS[:] = [j for j in _LIVE_JOBS if j.isRunning()]
            _LIVE_JOBS.append(job)
            self._fd9_job = job
            job.progress.connect(self._fd9_progress)
            job.readings.connect(self._fd9_count_changed)
            job.scan_ready.connect(self._fd9_scan_ready)
            job.patch_ready.connect(self._fd9_patch_ready)
            job.page_requested.connect(self._fd9_page_requested)
            job.result.connect(self._fd9_result)
            job.failed.connect(self._fd9_failed)
            keep_awake.hold()
            self._fd9_awake = True
            self.measurement_active.emit(True)
            job.start()
        except Exception as e:
            instrument_lease.release(self)
            if staged:
                self._drop_unused_verification_stage()
            self._fd9_failed(str(e), False, fd9_start_kind(e))

    def _fd9_log(self, text):
        self._log.appendPlainText(text)

    def _fd9_progress(self, text):
        """A progress line of the driver: in the user's words in the log, and
        the insertion window opened and closed at the right moments."""
        stage, line = _progress_line(str(text))
        if stage == "insert":
            self._fd9_close_page_notice()
            self._fd9_show_insert_window()
        elif stage in ("sheet_in", "measuring"):
            self._fd9_close_insert_window()
            self._fd9_sheet_in = True
        elif stage == "done":
            self._fd9_sheet_in = False
        self._fd9_log(line)

    def _fd9_page_requested(self, page, pages):
        from workflow import measurement_messages as M
        title, body = M.M_FD9_NEXT_PAGE.render(page=page, pages=pages)
        self._fd9_sheet_in = False
        self._fd9_close_insert_window()
        self._page_pause_box.set_content(title, body.split("\n\n"), "", [])
        self._page_pause_continue_btn.hide()
        self._page_pause_reread_btn.hide()
        self._page_pause_help_btn.hide()
        self._page_pause = {"plan": {"kind": "fd9", "page": page}, "button": False}
        self._page_pause_effect.setOpacity(1.0)
        self._place_page_pause_note()
        self._page_pause_panel.show()
        self._preview_legend_makes_way(True)
        self._fd9_log(f"[{title}]\n{body}")

    def _fd9_close_page_notice(self):
        if not getattr(self, "_page_pause", None) or self._page_pause["plan"].get("kind") != "fd9":
            return
        self._hide_page_pause()
        self._page_pause_panel.hide()
        self._preview_legend_makes_way(False)
        self._page_pause_continue_btn.show()
        self._page_pause_reread_btn.show()
        self._page_pause_help_btn.show()

    def _fd9_restore_controls(self):
        self._fd9_close_page_notice()
        self._fd9_close_insert_window()
        if self._fd9_awake:
            self._fd9_awake = False
            keep_awake.release()
        self._fd9_live = False
        instrument_lease.release(self)
        self._set_settings_enabled(True)
        self._fd9_panel.setEnabled(True)
        self._start_btn.setEnabled(
            bool(self._ti1_path and self._chart_file_for(self._ti1_path).exists())
        )
        self._stop_btn.setEnabled(False)
        self.measurement_active.emit(False)
        self._refresh_fd9_panel()
        self._refresh_progress()
        self._fd9_tidy_sessions()

    def _fd9_tidy_sessions(self):
        """Apply the session retention rule (`workflow.fd9.sessions`), keeping
        the session still running or still waiting to be saved or resumed."""
        try:
            if not self._ti1_path:
                return
            from workflow.fd9.sessions import prune_sessions

            keep = set()
            if self._fd9_live and self._fd9_session is not None:
                keep.add(Path(self._fd9_session).name)
            if self._fd9_pending:
                keep.add(Path(self._fd9_pending.get("session", "")).name)
            prune_sessions(self._chart_file_for(self._ti1_path), keep=keep)
        except Exception:  # noqa: BLE001 - housekeeping never fails a read
            log.warning("FD-9 session tidy-up failed", exc_info=True)

    def _fd9_scan_ready(self, event):
        from workflow.fd9.measurement import sha

        try:
            chart = self._chart_file_for(self._ti1_path)
            if event["session"] != str(self._fd9_job.session.resolve()) or event[
                "layout_sha256"
            ] != sha(chart.with_suffix(".fd9.json")):
                return
            if "measurement_locations" in event:
                planned = list(event["measurement_locations"])
                offset = int(event.get("reading_offset", 0))
                remaining = self._fd9_ordered_locations[self._fd9_prior_count:]
                if self._fd9_acquisition_locations is None:
                    self._fd9_acquisition_locations = list(remaining)
                expected = self._fd9_acquisition_locations[offset:offset+len(planned)]
                if offset < 0 or len(expected) != len(planned) or set(expected) != set(planned):
                    raise ValueError("Scan acquisition order does not match remaining patches")
                self._fd9_acquisition_locations[offset:offset+len(planned)] = planned
            self._fd9_show_scan(event, chart)
        except Exception as error:
            self._fd9_log("[FD9 preview] " + str(error))

    def _fd9_patch_ready(self, event):
        """Accept passive worker colour events only for the active session."""
        try:
            if not self._fd9_live or self._fd9_scan_preview is None:
                return
            chart = self._chart_file_for(self._ti1_path)
            if (
                event["session"] != str(self._fd9_job.session.resolve())
                or event["layout_sha256"] != self._fd9_scan_preview["layout_sha256"]
                or self._fd9_scan_chart != str(chart.resolve())
                or event["condition"] != self._fd9_active_settings.condition
            ):
                return
            self._fd9_live_colours.update({p["loc"]: p for p in event.get("patches", [])})
            self._on_chart_measured(event)
        except Exception as error:
            self._fd9_log("[FD9 preview] " + str(error))

    def _fd9_show_scan(self, event, chart):
        from PyQt6.QtCore import QPointF
        from PyQt6.QtGui import QPolygonF

        self._fd9_scan_preview = event
        self._fd9_scan_chart = str(chart.resolve())
        image = Path(event["image"])
        page = int(event.get("page", 0))
        count = int(event.get("pages", 1))
        paths = list(self._tiff_pages) if len(self._tiff_pages) == count else [image]*count
        paths[page] = image
        self._tiff_pages = paths
        self._preview.load_tiff(paths)
        # Remap a resumed prefix to the new scan rather than retaining boxes
        # from the nominal TIFF or a previous insertion.
        self._preview.clear_patch_overlay()
        boxes = [
            QPolygonF([QPointF(x, y) for x, y in cell]).boundingRect().toAlignedRect()
            for row in event["rows"]
            for cell in row
        ]
        page_locations = event.get("locations", self._fd9_ordered_locations)
        if len(boxes) != len(page_locations):
            raise ValueError("Scan grid does not match the selected chart")
        mapping = list(self._patch_boxes) if len(self._patch_boxes) == count else [{} for _ in range(count)]
        mapping[page] = dict(zip(page_locations, boxes))
        stripes = list(self._page_stripe_rects) if len(self._page_stripe_rects) == count else [[] for _ in range(count)]
        self._fd9_use_rows_as_strips(event["rows"], boxes)
        stripes[page] = self._page_stripe_rects[0]
        self._patch_boxes = mapping
        self._page_stripe_rects = stripes
        self._strips_per_page = [len(r) for r in stripes]
        self._preview.set_page_patch_boxes({i: list(b.values()) for i,b in enumerate(mapping)})
        self._fd9_scan_previews[page] = event
        self._preview.show_page(page)
        self._preview.set_patch_click_enabled(False)
        self._preview.set_notice(tr("FD-9 scan of the sheet: rows outlined in green are measured, the amber row is next, and blue rows are still to come."))
        self._refresh_progress()
        self._fd9_restore_scan_colours(chart)
        if self._fd9_live_colours:
            self._on_chart_measured({"patches": list(self._fd9_live_colours.values())}, live=False)

    def _fd9_restore_scan_colours(self, chart):
        try:
            from workflow.fd9.preview import saved_patch_colours

            measurement = (
                self._fd9_prior_measurement
                if self._fd9_live
                else chart.with_suffix(".ti3")
            )
            if measurement is None or not Path(measurement).is_file():
                return
            self._live_expected = self._expected_source_for(measurement)
            patches = saved_patch_colours(
                measurement, chart, expected=self._live_expected
            )
            self._on_chart_measured({"patches": patches}, live=False)
        except Exception as error:
            self._fd9_log("[FD9 preview] " + str(error))

    def _fd9_update_scan_grid(self):
        event = self._fd9_scan_previews.get(self._preview.current_page(), self._fd9_scan_preview)
        if event and event.get("page", 0) != self._preview.current_page():
            self._preview.set_scan_grid(None)
            return
        if not event or not self._ti1_path:
            return
        if self._fd9_scan_chart != str(self._chart_file_for(self._ti1_path).resolve()):
            return
        measured = self._progress_file_locs | self._progress_locs
        locations = event.get("locations", self._fd9_ordered_locations)
        ncols = len(event["rows"][0])
        completed = {
            i
            for i in range(len(event["rows"]))
            if set(locations[ncols * i : ncols * (i + 1)]).issubset(measured)
        }
        active = (
            next((i for i in range(len(event["rows"])) if i not in completed), None)
            if self._fd9_live
            else None
        )
        self._preview.set_scan_grid(event["rows"], completed, active)

    def _fd9_count_changed(self, count):
        self._fd9_readings = self._fd9_seed_unsaved + count
        start = self._fd9_prior_count
        planned = self._fd9_acquisition_locations
        if planned is None:
            planned = self._fd9_ordered_locations[start:]
        self._progress_locs = set(planned[:count])
        self._refresh_progress()

    # ---- the end ----------------------------------------------------------
    def _fd9_result(self, result, prompt=True):
        if self._fd9_ending:
            self._fd9_deferred = ("result", result)
            return
        self._fd9_readings = self._fd9_seed_unsaved + result.get(
            "new_readings", result.get("patches", 0)
        )
        if self._fd9_choice == "discard":
            self._fd9_pending = None
            self._reset_progress()
            self._fd9_restore_controls()
            self._fd9_settle()
            return
        stopped = self._fd9_job.stop_event.is_set()
        if self._fd9_choice == "save" or (
            not stopped and not result.get("acquisition_error")
        ):
            self._fd9_publish(result)
            return
        result["unsaved_readings"] = self._fd9_readings
        self._fd9_pending = result
        self._fd9_restore_controls()
        self._fd9_resume.setChecked(True)
        self._fd9_panel.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self.measurement_active.emit(True)
        if result.get("acquisition_error"):
            self._fd9_log("[ERROR] " + result["acquisition_error"])
            self._fd9_log(
                tr(
                    "Your previous measurement is unchanged, and everything the FD-9 sent is kept in the run's fd9-sessions folder. If the sheet is still in the FD-9, take it out with the FD-9's own controls."
                )
            )
            failure = result.get("acquisition_exception")
            self._fd9_explain_error(
                result["acquisition_error"], stopped,
                kind=(fd9_exception_kind(failure)
                      if isinstance(failure, BaseException) else ""))
        if prompt:
            self._fd9_end_prompt(self.END_FAILURE_WINDOW)

    def _fd9_publish(self, result):
        from workflow.fd9.measurement import publish_measurement, sha

        self._fd9_pending = result
        try:
            chart = self._chart_file_for(self._ti1_path)
            if (
                chart.resolve() != Path(result["chart"]).resolve()
                or sha(chart) != result["chart_sha256"]
            ):
                raise ValueError(
                    "Selected chart changed; result preserved in session only"
                )
            if (
                result.get("layout_sha256")
                and sha(chart.with_suffix(".fd9.json")) != result["layout_sha256"]
            ):
                raise ValueError(
                    "Selected layout changed; result preserved in session only"
                )
            if (
                result.get("staged_sha256")
                and sha(result["staged"]) != result["staged_sha256"]
            ):
                raise ValueError("Staged measurement changed; replacement refused")
            if (
                result.get("conversion_source")
                not in ("instrument_firmware", "instrument_model")
                and sha(self._fd9_active_settings.profile) != result["profile_sha256"]
            ):
                raise ValueError("Profile changed; result preserved in session only")
            options = {
                "allow_partial": True,
                "archive": getattr(getattr(self, "_fd9_guard", None), "archive", None),
            }
            if "base_sha256" in result:
                options["expected_base_sha256"] = result["base_sha256"]
            target = publish_measurement(
                result["staged"], result["destination"], chart, **options
            )
        except Exception as error:
            # Filing happens on this computer, after the FD-9 has finished.
            self._fd9_failed(str(error), False, "failed")
            return
        try:
            from workflow.fd9.sessions import mark_filed

            mark_filed(result.get("session"))
        except Exception:  # noqa: BLE001
            log.warning("could not mark the FD-9 session as filed", exc_info=True)
        self._fd9_pending = None
        self._fd9_choice = None
        self._fd9_restore_controls()
        self._fd9_log(tr("FD-9 measurement saved: {path}").format(path=target))
        self._adopt_imported_measurement(target)
        from workflow.measurement_state import classify, Ti3State

        complete = classify(target, chart).state is Ti3State.COMPLETE
        self._fd9_resume.setChecked(not complete)
        self._refresh_fd9_panel()
        self.save_target_settings()
        if complete:
            if self._is_verification_run():
                self._finalize_verification(target)
            else:
                self.measure_finished.emit(target)
        if result.get("acquisition_error"):
            self._fd9_log(
                tr("If the sheet is still in the FD-9, take it out with the FD-9's own controls.")
            )
        self._fd9_settle()

    def _fd9_failed(self, message, cancelled, kind=""):
        if self._fd9_ending:
            self._fd9_deferred = ("failed", (message, cancelled, kind))
            return
        # A discard is settled BEFORE the controls come back, so the chart
        # file group is not left greyed for a result nobody keeps (r1 F1).
        if self._fd9_choice == "discard":
            self._fd9_pending = None
        if not self._fd9_pending:
            self._reset_progress()
        self._fd9_restore_controls()
        self._drop_unused_verification_stage()
        self._fd9_log(("[STOPPED] " if cancelled else "[ERROR] ") + message)
        self._fd9_log(
            tr(
                "Your previous measurement is unchanged, and everything the FD-9 sent is kept in the run's fd9-sessions folder. If the sheet is still in the FD-9, take it out with the FD-9's own controls."
            )
        )
        if self._fd9_pending:
            self._fd9_panel.setEnabled(False)
            self._stop_btn.setEnabled(True)
            self.measurement_active.emit(True)
        self._fd9_settle()
        self._fd9_explain_error(message, cancelled, kind)

    def _fd9_end_prompt(self, how):
        if self._fd9_ending:
            return
        stopping = getattr(self._fd9_job, "stop_event", None)
        if self._fd9_live and stopping is not None and stopping.is_set():
            return
        if self._fd9_live and self._fd9_job is not None:
            self._fd9_count_changed(getattr(self._fd9_job, "new_readings", 0))
        self._fd9_ending = True
        try:
            choice = self._confirm_end_of_session(how)
        finally:
            self._fd9_ending = False
        self._fd9_choice = choice
        if choice is not None:
            if self._fd9_live:
                self._fd9_job.request_stop()
                self._stop_btn.setEnabled(False)
                self._fd9_log(
                    tr(
                        "Stopping the FD-9. Please keep ChromIQ open until this has finished."
                    )
                )
            elif self._fd9_pending:
                result = self._fd9_pending
                if choice == "save":
                    self._fd9_publish(result)
                else:
                    self._fd9_pending = None
                    self._reset_progress()
                    self._fd9_restore_controls()
                    self._refresh_fd9_panel()
                    self._fd9_settle()
        if self._fd9_deferred is not None:
            kind, value = self._fd9_deferred
            self._fd9_deferred = None
            if kind == "result":
                self._fd9_result(value, prompt=False)
            else:
                self._fd9_failed(*value)

    def _fd9_worker_running(self):
        job = self._fd9_job
        running = getattr(job, "isRunning", None)
        return bool(callable(running) and running())

    def _stop_fd9_measurement(self):
        self._fd9_end_prompt(self.END_STOP)
