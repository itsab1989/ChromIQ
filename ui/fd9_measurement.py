"""Normal Measure-tab FD9 routing. Device work stays off the GUI thread."""

from pathlib import Path
import threading
from dataclasses import replace
from PyQt6.QtCore import QThread, pyqtSignal, QSettings
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QCheckBox,
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QDialogButtonBox,
)
from core.i18n import tr
from core.thread_stack import roomy
from core import instrument_lease
from core.keep_awake import keep_awake
from workflow.fd9.measurement import (
    FD9Settings,
    is_fd9_chart,
    checked_chart,
    measure_chart,
    publish_measurement,
    resume_plan,
    sha,
)


class FD9Job(QThread):
    progress = pyqtSignal(str)
    readings = pyqtSignal(int)
    scan_ready = pyqtSignal(object)
    patch_ready = pyqtSignal(object)
    result = pyqtSignal(object)
    failed = pyqtSignal(str, bool)

    def __init__(self, chart, settings, session, parent=None, action=measure_chart):
        super().__init__(parent)
        roomy(self)
        self.chart = chart
        self.settings = settings
        self.session = session
        self.action = action
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
                )
            )
        except Exception as e:
            self.failed.emit(str(e), self.stop_event.is_set())

    def note_readings(self, count):
        self.new_readings = count
        self.readings.emit(count)

    def request_stop(self):
        self.stop_event.set()


class FD9Setup(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("FD-9 setup"))
        self.resize(650, 420)
        self.store = settings
        self.inputs = {}
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)
        edit = QLineEdit(str(settings.value("host", "")))
        self.inputs["host"] = edit
        form.addRow(tr("Ethernet address"), edit)
        note = QLabel(
            tr(
                "The independent driver uses the FD-9’s own factory characterization. No conversion profile, reference measurement or manufacturer host software is required. Disconnect other FD-9 clients before measuring. This driver is experimental and has been tested on one FD-9."
            )
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save(self):
        for key, edit in self.inputs.items():
            self.store.setValue(key, edit.text().strip())
        self.accept()


class FD9MeasureMixin:
    def _init_fd9_panel(self, layout):
        self._fd9_store = QSettings("ChromIQ", "IndependentFD9")
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
        self._fd9_scan_chart = None
        self._fd9_ordered_locations = []
        self._fd9_prior_count = 0
        self._fd9_prior_measurement = None
        self._fd9_panel = QWidget(self)
        row = QHBoxLayout(self._fd9_panel)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel(tr("FD-9 condition:")))
        self._fd9_condition = QComboBox()
        # ISO condition identifiers are language-independent profile values.
        for condition in ("M0", "M1", "M2"):
            self._fd9_condition.addItem(condition, condition)
        self._fd9_condition.setCurrentText("M1")
        row.addWidget(self._fd9_condition)
        self._fd9_resume = QCheckBox(tr("Resume"))
        self._fd9_resume.toggled.connect(self._fd9_resume_changed)
        row.addWidget(self._fd9_resume)
        self._fd9_setup_btn = QPushButton(tr("FD-9 setup…"))
        self._fd9_setup_btn.clicked.connect(self._configure_fd9)
        row.addWidget(self._fd9_setup_btn)
        layout.addWidget(self._fd9_panel)
        self._fd9_panel.hide()

    def _fd9_resume_changed(self, checked):
        self._refresh_start_button_label()

    def _configure_fd9(self):
        FD9Setup(self._fd9_store, self).exec()

    def _is_fd9_target(self):
        path = getattr(self, "_ti1_path", None)
        return bool(path and is_fd9_chart(self._chart_file_for(path)))

    def _refresh_fd9_panel(self):
        active = self._is_fd9_target()
        if hasattr(self, "_fd9_panel"):
            self._fd9_panel.setVisible(active)
        for name in ("_g_options", "_m_options", "_m_presets_grp"):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.setEnabled(not active and not self._fd9_live)
        if active:
            from workflow.measurement_state import classify, Ti3State

            chart = self._chart_file_for(self._ti1_path)
            available = (
                self._fd9_pending is not None
                or classify(chart.with_suffix(".ti3"), chart).state is Ti3State.PARTIAL
            )
            self._fd9_resume.setVisible(available)
            if not available:
                self._fd9_resume.setChecked(False)
            self._refresh_start_button_label()
            self._preview.set_no_swipe(True)
            self._calm_outer.hide()
            self._save_defaults_btn.setEnabled(False)
        elif hasattr(self, "_calm_outer"):
            self._calm_outer.setVisible(self._current_mode() == "guided")

    def _fd9_load_preview(self, base_path):
        """Display-only geometry diagram, never a printable chart TIFF."""
        from PIL import Image, ImageDraw
        from PyQt6.QtCore import QRect

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
            if event and event["layout_sha256"] == sha(layout_path):
                self._fd9_show_scan(event, chart)
                return True
            self._fd9_scan_preview = None
            self._fd9_scan_chart = None
            scale = 4
            paper = layout.get("paper_mm", [137, 300])
            patch = layout.get("patch_mm", [8, 8])
            image = Image.new(
                "RGB", (round(paper[0] * scale), round(paper[1] * scale)), "white"
            )
            draw = ImageDraw.Draw(image)
            boxes = {}
            columns = [[] for _ in layout["rows"][0]]
            for row in layout["rows"]:
                for c, p in enumerate(row):
                    values = dict(zip(layout["channel_tokens"], p["device_values"]))
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
                    rep = layout.get("color_rep")
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
                    columns[c].append(rect)
            for x, y in layout["fiducials_mm"]:
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
            cache = chart.parent / "cache"
            cache.mkdir(exist_ok=True)
            path = cache / ("fd9-preview-" + sha(layout_path)[:12] + ".png")
            image.save(path)
            self._tiff_pages = [path]
            self._preview.load_tiff([path])
            self._patch_boxes = [boxes]
            rects = []
            for column in columns:
                rect = QRect(column[0])
                for r in column[1:]:
                    rect = rect.united(r)
                rects.append(rect)
            self._page_stripe_rects = [rects]
            self._strips_per_page = [len(columns)]
            self._preview.set_page_patch_boxes({0: list(boxes.values())})
            self._preview.set_stripe_rects(rects, "base")
            self._preview.set_no_swipe(True)
            self._preview.set_notice(
                tr("FD-9 layout preview: approximate colours, not a print file.")
            )
            return True
        except Exception as e:
            self._fd9_log("[FD9 preview] " + str(e))
            return False

    def _fd9_settings(self):
        s = self._fd9_store
        source = str(s.value("driver_source", "")).strip()
        return FD9Settings(
            Path(source) if source else None,
            None,
            None,
            None,
            str(s.value("host", "")),
            self._fd9_condition.currentText(),
            True,  # Selecting an FD-9 chart selects its independent driver.
            conversion_source="instrument_firmware",
        )

    def _start_fd9_measurement(self):
        if self._fd9_live or self._runner.is_running:
            return
        if self._blocked_by_new_run() or self._blocked_by_missing_chart_file():
            return
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
            settings = replace(
                settings,
                resume=self._fd9_resume.isChecked() or self._fd9_pending is not None,
                resume_source=(
                    Path(self._fd9_pending["staged"]) if self._fd9_pending else None
                ),
            )
            settings.validate()
            prior_path, prior_rows, _ = resume_plan(chart, settings)
            block = self._verification_guard()
            if block:
                title, body = block.render()
                raise ValueError(title + "\n" + body)
            if not instrument_lease.acquire(self, instrument_lease.MEASURE_TAB):
                raise ValueError(tr("Another window holds the instrument."))
            if not self._snapshot_verification_chart():
                instrument_lease.release(self)
                return
            chart = self._chart_file_for(self._ti1_path)
            checked_chart(chart)
            from uuid import uuid4

            session = chart.parent / "fd9-sessions" / uuid4().hex[:12]
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
            self._fd9_active_settings = settings
            self._fd9_condition.setCurrentText(settings.condition)
            self.save_target_settings()
            self._fd9_live = True
            self._fd9_prior_count = len(prior_rows)
            self._fd9_prior_measurement = prior_path
            self._live_expected = self._expected_source_for(chart.with_suffix(".ti3"))
            self._reset_flag_judge()
            self._fd9_scan_preview = None
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
            self._fd9_previous_job = (
                self._fd9_job
            )  # retain completed thread until its queued signals have drained
            self._fd9_job = FD9Job(chart, settings, session, self)
            self._fd9_job.progress.connect(self._fd9_log)
            self._fd9_job.readings.connect(self._fd9_count_changed)
            self._fd9_job.scan_ready.connect(self._fd9_scan_ready)
            self._fd9_job.patch_ready.connect(self._fd9_patch_ready)
            self._fd9_job.result.connect(self._fd9_result)
            self._fd9_job.failed.connect(self._fd9_failed)
            keep_awake.hold()
            self._fd9_awake = True
            self.measurement_active.emit(True)
            self._fd9_job.start()
        except Exception as e:
            instrument_lease.release(self)
            self._fd9_failed(str(e), False)

    def _fd9_log(self, text):
        self._log.appendPlainText(text)

    def _fd9_restore_controls(self):
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

    def _fd9_scan_ready(self, event):
        try:
            chart = self._chart_file_for(self._ti1_path)
            if event["session"] != str(self._fd9_job.session.resolve()) or event[
                "layout_sha256"
            ] != sha(chart.with_suffix(".fd9.json")):
                return
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
            self._on_chart_measured(event)
        except Exception as error:
            self._fd9_log("[FD9 preview] " + str(error))

    def _fd9_show_scan(self, event, chart):
        from PyQt6.QtCore import QPointF
        from PyQt6.QtGui import QPolygonF

        self._fd9_scan_preview = event
        self._fd9_scan_chart = str(chart.resolve())
        image = Path(event["image"])
        self._tiff_pages = [image]
        self._preview.load_tiff([image])
        # Remap a resumed prefix to the new scan rather than retaining boxes
        # from the nominal TIFF or a previous insertion.
        self._preview.clear_patch_overlay()
        boxes = [
            QPolygonF([QPointF(x, y) for x, y in cell]).boundingRect().toAlignedRect()
            for row in event["rows"]
            for cell in row
        ]
        if len(boxes) != len(self._fd9_ordered_locations):
            raise ValueError("Scan grid does not match the selected chart")
        self._patch_boxes = [dict(zip(self._fd9_ordered_locations, boxes))]
        columns = []
        ncols = len(event["rows"][0])
        for c in range(ncols):
            rect = boxes[c]
            for i in range(c + ncols, len(boxes), ncols):
                rect = rect.united(boxes[i])
            columns.append(rect)
        self._page_stripe_rects = [columns]
        self._strips_per_page = [len(columns)]
        self._preview.set_stripe_rects(columns, "base")
        self._preview.set_page_patch_boxes({0: boxes})
        self._preview.set_patch_click_enabled(False)
        self._preview.set_stripe_click_enabled(False)
        self._preview.set_no_swipe(True)
        self._preview.set_notice(tr("FD-9 scan: green rows are complete."))
        self._refresh_progress()
        self._fd9_restore_scan_colours(chart)

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
        event = self._fd9_scan_preview
        if not event or not self._ti1_path:
            return
        if self._fd9_scan_chart != str(self._chart_file_for(self._ti1_path).resolve()):
            return
        measured = self._progress_file_locs | self._progress_locs
        locations = self._fd9_ordered_locations
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
        self._progress_locs = set(self._fd9_ordered_locations[start : start + count])
        self._refresh_progress()

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
                    "The previous measurement is unchanged. Raw session evidence is preserved. If the sheet remains in the FD-9, use its controls to recover it."
                )
            )
        if prompt:
            self._fd9_end_prompt(self.END_FAILURE_WINDOW)

    def _fd9_publish(self, result):
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
            self._fd9_failed(str(error), False)
            return
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
                tr("If the sheet remains in the FD-9, use its controls to recover it.")
            )

    def _fd9_failed(self, message, cancelled):
        if self._fd9_ending:
            self._fd9_deferred = ("failed", (message, cancelled))
            return
        if not self._fd9_pending:
            self._reset_progress()
        self._fd9_restore_controls()
        self._drop_unused_verification_stage()
        self._fd9_log(("[STOPPED] " if cancelled else "[ERROR] ") + message)
        self._fd9_log(
            tr(
                "The previous measurement is unchanged. Raw session evidence is preserved. If the sheet remains in the FD-9, use its controls to recover it."
            )
        )
        if self._fd9_choice == "discard":
            self._fd9_pending = None
        if self._fd9_pending:
            self._fd9_panel.setEnabled(False)
            self._stop_btn.setEnabled(True)
            self.measurement_active.emit(True)

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
                        "Stopping FD-9 communication. Keep this window open until the operation ends."
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
        if self._fd9_deferred is not None:
            kind, value = self._fd9_deferred
            self._fd9_deferred = None
            if kind == "result":
                self._fd9_result(value, prompt=False)
            else:
                self._fd9_failed(*value)

    def _fd9_worker_running(self):
        job = getattr(self, "_fd9_job", None)
        running = getattr(job, "isRunning", None)
        return bool(callable(running) and running())

    def _stop_fd9_measurement(self):
        self._fd9_end_prompt(self.END_STOP)
