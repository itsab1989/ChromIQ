"""The shared "Profile run" + "Run type" selector, used across the Create Chart,
Print Chart and Measure tabs (#130).

A single :class:`MeasurementTargetController` owns the app-wide selection and a
``changed`` signal; each tab embeds a :class:`MeasurementTargetBar` bound to that
controller, so changing the selection on any tab updates all of them. No tab
holds the state itself — the controller is the single source of truth.
"""
from __future__ import annotations

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from core.i18n import tr
from core.logger import get_logger
from core.measurement_target import (
    RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION, MeasurementTarget)
from ui.tooltip_button import TooltipButton
from ui.widgets import NoScrollComboBox

log = get_logger(__name__)

_NEW = "\x00new"          # sentinel userData for the "New …" combo entries


class MeasurementTargetController(QObject):
    """Holds the shared :class:`MeasurementTarget` and answers the questions the
    bar needs about the loaded project (its runs and each run's verification
    dates). ``changed`` fires whenever the selection changes."""

    changed = pyqtSignal()
    #: emitted after a verification's used chart has been restored, so the tabs
    #: can rebuild the pages and refresh what they show (#130).
    chart_restored = pyqtSignal()

    def __init__(self, file_mgr, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._fm = file_mgr
        self._target = MeasurementTarget()
        # Chart-changing controls are unavailable while a measurement runs.
        self._measuring = False
        #: the outcome of the most recent Restore Used Chart, so the listener of
        #: ``chart_restored`` knows whether the pages still need redrawing.
        self._last_restore = None
        # The name typed into "Printer profile project name" before any project
        # exists on disk, so the location line can answer "where will this go?"
        # while the user is still setting up (#130, Knut).
        self._pending_name = ""

    def set_pending_project_name(self, raw: str) -> None:
        """Track the profile-project name being typed, so the bar's location
        line follows it before the project folder exists."""
        raw = (raw or "").strip()
        if raw != self._pending_name:
            self._pending_name = raw
            self.changed.emit()

    @property
    def target(self) -> MeasurementTarget:
        return self._target

    def project_or_none(self):
        try:
            # Don't go through working_dir() before a name exists: it calls
            # get_target_name(), which INVENTS and stores a
            # "Printer_Paper_Type_Instr_<timestamp>" name. The bar asks this
            # question constantly, so that invented name would then be written
            # into the user's "Printer profile project name" field on the next
            # refresh. With no name and no opened project there is nothing to
            # find anyway.
            # Only skip when we POSITIVELY know there is no name: a file
            # manager that doesn't expose these (a test double, or any other
            # duck-typed one) falls through to the normal lookup below.
            name = getattr(self._fm, "_target_name", None)
            if name == "":
                override = getattr(self._fm, "project_root_override", None)
                if override is None or override() is None:
                    return None
            if (self._fm.working_dir() / "project.json").exists():
                return self._fm.project()
        except Exception:      # noqa: BLE001 — the bar must never crash a tab
            pass
        return None

    def run_ids(self) -> list[str]:
        p = self.project_or_none()
        return [r.id for r in p.all_runs()] if p is not None else []

    def verification_ids(self, run_id: str) -> list[str]:
        p = self.project_or_none()
        if p is None or not run_id or not p.has_run(run_id):
            return []
        return [v.id for v in p.run(run_id).verifications()]

    def verification_has_measurement(self, run_id: str, vid: str) -> bool:
        """Whether a dated verification actually holds a measurement.

        A folder is created the moment a verification measurement starts, so one
        that was cancelled or failed leaves a dated entry with a stored chart but
        no result (#130, Knut's decision 1: keep it, and mark it). The chart is
        still restorable from it, which is why the entry stays selectable."""
        p = self.project_or_none()
        if p is None or not run_id or not vid or not p.has_run(run_id):
            return False
        try:
            return p.run(run_id).verification(vid).exists()
        except Exception:      # noqa: BLE001
            return False

    # ---- mutators (each emits changed only on a real change) --------------
    def set_run_type(self, value: str) -> None:
        if value != self._target.run_type:
            self._target.run_type = value
            self.changed.emit()

    def set_profile_run(self, run_id: str) -> None:
        if run_id != self._target.profile_run:
            self._target.profile_run = run_id
            # A different run has its own verification dates — drop a stale pick.
            self._target.verification_id = ""
            self.changed.emit()

    def set_verification_id(self, vid: str) -> None:
        if vid != self._target.verification_id:
            self._target.verification_id = vid
            self.changed.emit()

    def location_being_edited(self) -> str:
        """The folder the current Profile-run / Run-type selection writes into,
        written from the ChromIQ folder down (#130, Knut 2026-07-25) — e.g.
        ``ChromIQ/My-Printer/runs/run1/`` for Profiling, or
        ``ChromIQ/My-Printer/runs/run1/verifications/`` for Verification.

        A project kept in a sub-folder shows its real place
        (``ChromIQ/customers/2026/My-Printer/runs/run1/``), because that is where
        the files actually are.

        **It does not wait for the project to exist.** As soon as a profile
        project name is known — typed into "Printer profile project name", or
        carried by an opened project — the destination is answerable, and that is
        precisely when the answer is most useful: before the first chart is
        generated. Returns an empty string only when nothing is named at all, so
        a freshly-started app shows no half-formed path.
        """
        from pathlib import Path
        try:
            proj = self.project_or_none()
            if proj is None:
                # No project folder yet. Use the name shown in "Printer profile
                # project name" — deliberately NOT the FileManager's target name,
                # which get_target_name() invents as
                # Printer_Paper_Type_Instr_<timestamp> the first time anything
                # asks for it. Showing that invented name as a location would be
                # worse than showing nothing: it names a folder the user never
                # chose and that may never exist.
                if not self._pending_name:
                    return ""
                from core.file_manager import FileManager
                clean = FileManager._sanitise(
                    FileManager.strip_workfile_ext(self._pending_name))
                if not clean:
                    return ""
                proj_root = Path(self._fm.root_dir()) / clean
            else:
                proj_root = Path(proj.root)
            root = Path(self._fm.root_dir())
            try:
                rel = proj_root.resolve().relative_to(root.resolve())
            except (ValueError, OSError):
                rel = Path(proj_root.name)          # project outside the folder
            run_id = self._target.profile_run
            if not run_id:
                # "New run" — name the folder that would be created, so the user
                # can see where a Generate is about to put things.
                try:
                    run_id = f"run{proj._next_run_index()}" if proj is not None \
                        else "run1"
                except Exception:      # noqa: BLE001
                    run_id = "run…"
            parts = [root.name, *rel.parts, "runs", run_id]
            if self._target.is_verification():
                parts.append("verifications")
            return "/".join(parts) + "/"
        except Exception:      # noqa: BLE001 — a label must never break the bar
            return ""

    # ---- Restore Used Chart (#130, Knut 2026-07-25) -----------------------
    def selected_verification(self):
        """The :class:`Verification` the bar points at, or None when the type is
        not Verification, no run is selected, or the dropdown says "New"."""
        try:
            if not self._target.is_verification():
                return None
            proj = self.project_or_none()
            run_id = self._target.profile_run
            vid = self._target.verification_id
            if proj is None or not run_id or not vid or not proj.has_run(run_id):
                return None
            return proj.run(run_id).verification(vid)
        except Exception:      # noqa: BLE001
            return None

    def restore_state(self) -> "tuple[bool, str]":
        """``(enabled, tooltip)`` for the Restore Used Chart button, with the
        exact wording from the specification for each reason it is unavailable."""
        from workflow.verify_chart_snapshot import has_snapshot
        if self._measuring:
            return False, tr("Not while a measurement is running")
        verification = self.selected_verification()
        if verification is None:
            return False, tr("Select an existing Verification run date to "
                             "restore its used chart")
        if not has_snapshot(verification):
            return False, tr("Selected Verification run date has no available "
                             "chart to restore")
        return True, tr("Restore chart used for selected verification run date")

    def restore_needs_confirmation(self) -> bool:
        """Whether the live chart differs from the snapshot, so the user should
        be warned before it is replaced."""
        from workflow.verify_chart_snapshot import live_differs_from_snapshot
        verification = self.selected_verification()
        return (verification is not None
                and live_differs_from_snapshot(verification))

    def restore_used_chart(self):
        """Put the selected verification's snapshotted chart back. Returns the
        :class:`RestoreResult`, or None when there is nothing to restore."""
        from workflow.verify_chart_snapshot import restore_chart
        verification = self.selected_verification()
        if verification is None:
            return None
        result = restore_chart(verification)
        if result.ok:
            # The listener rebuilds the pages when the snapshot held none but
            # the recipe to redraw them is there (result.should_rebuild).
            self._last_restore = result
            self.chart_restored.emit()
        return result

    def set_measuring(self, running: bool) -> None:
        """Chart-changing controls are unavailable while a measurement runs."""
        if running != self._measuring:
            self._measuring = running
            self.changed.emit()

    def notify_changed(self) -> None:
        """Force a ``changed`` emission even when no field value differs — used
        after the working PROJECT is switched out from under the bar (e.g. a
        Print/Measure load copied a new project in), so listeners refresh even
        if the new project's run id happens to match the old one (#130, Knut)."""
        self.changed.emit()


class MeasurementTargetBar(QWidget):
    """A compact row: **Profile run** (a friendly single dropdown), **Run type**
    (Profiling / Verification), and — when ``show_verification`` and the type is
    Verification — a **Verification** date dropdown. Reflects and drives the
    shared controller."""

    def __init__(self, controller: MeasurementTargetController,
                 *, show_verification: bool = True,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctl = controller
        self._show_verification = show_verification
        self._syncing = False

        self._accent = TooltipButton.ACCENT

        # A column: the selection row, then the "Location being edited" line
        # underneath it (#130, Knut 2026-07-25).
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(2)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        column.addLayout(row)

        self._run_label = self._mk_label(tr("Profile run:"))
        row.addWidget(self._run_label)
        self._run_combo = NoScrollComboBox(self)
        self._run_combo.setToolTip(tr(
            "Which profile build this applies to. Every profile you make is a "
            "“run”, kept in its own folder. Pick an existing run to work on it "
            "again — that overwrites that run's files — or choose “New run” to "
            "start a fresh profile alongside the ones you already have. Your "
            "older runs are never touched unless you select them here."))
        self._run_combo.currentIndexChanged.connect(self._on_run_changed)
        # Wide enough that its content ("Run N (overwrite)", "New run") stays
        # fully readable instead of being truncated (Basti); grows to fit longer
        # labels (e.g. two-digit run numbers) but never shrinks below this floor.
        from PyQt6.QtWidgets import QComboBox
        self._run_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)
        # A representative widest label for the floor; AdjustToContents grows it
        # if a translation runs longer, so this need not be translated itself.
        self._run_combo.setMinimumWidth(
            self._run_combo.fontMetrics().horizontalAdvance(
                "Run 8 (overwrite)") + 44)
        row.addWidget(self._run_combo)

        row.addSpacing(4)
        self._type_label = self._mk_label(tr("Run type:"))
        row.addWidget(self._type_label)
        self._type_combo = NoScrollComboBox(self)
        self._type_combo.addItem(tr("Profiling"), RUN_TYPE_PROFILING)
        self._type_combo.addItem(tr("Verification"), RUN_TYPE_VERIFICATION)
        self._type_combo.setToolTip(tr(
            "Are you building the printer profile itself, or checking a "
            "finished one?\n\n"
            "• Profiling — measure a chart printed with colour management OFF, "
            "so ChromIQ can learn your printer and build a profile from it. "
            "This is the normal choice.\n\n"
            "• Verification — measure a (usually smaller) chart printed THROUGH "
            "a finished profile, with colour management ON, to check how "
            "accurate that profile still is. A verification never builds a "
            "profile; it is kept as a dated record so you can watch a profile "
            "hold up — or drift — over time."))
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        row.addWidget(self._type_combo)

        self._verify_label = self._mk_label(tr("Verification:"))
        row.addWidget(self._verify_label)
        self._verify_combo = NoScrollComboBox(self)
        self._verify_combo.setToolTip(tr(
            "Which verification to work on. “New verification” starts a fresh, "
            "dated check that is kept next to your earlier ones — so you build "
            "up a history of how this profile performs month after month. Pick "
            "an existing date instead to re-measure that particular check."))
        self._verify_combo.currentIndexChanged.connect(self._on_verify_changed)
        row.addWidget(self._verify_combo)

        # Restore Used Chart — puts back the chart a past verification was
        # measured against (#130, Knut 2026-07-25). Sits directly right of the
        # Verification dropdown, with its own ⓘ.
        from PyQt6.QtWidgets import QPushButton
        self._restore_btn = QPushButton(tr("Restore Used Chart"), self)
        self._restore_btn.setObjectName("compact_input")
        self._restore_btn.setAutoDefault(False)
        self._restore_btn.clicked.connect(self._on_restore_clicked)
        row.addWidget(self._restore_btn)
        self._restore_tip = TooltipButton(
            tr("Restore Used Chart"),
            tr("Puts back the verification chart that the selected verification "
               "date was actually measured with.\n\n"
               "Every time you measure a verification, ChromIQ keeps a copy of "
               "the chart it measured inside that verification's own folder. If "
               "you later change or re-create the verification chart, the older "
               "results no longer describe a chart you still have — this button "
               "brings the original one back so those results make sense again, "
               "and so you can reprint exactly the same sheet.\n\n"
               "It becomes available once you pick an existing verification date "
               "that has a stored chart. Your measurements are never touched: "
               "only the chart files at the top of the verifications folder are "
               "replaced, and you are asked first whenever the chart currently "
               "there is different."),
            self)
        row.addWidget(self._restore_tip)

        self._tip_btn = TooltipButton(
            tr("Profile run and Run type"),
            tr("These two choices decide what your next action works on, and "
            "they stay in step across the Create Chart, Print Chart and Measure "
            "tabs, so the right chart is always the one shown, printed and "
            "measured.\n\n"
            "“Profile run” picks which profile build you're working on (or a "
            "new one). “Run type” switches between building the profile "
            "(Profiling) and checking a finished profile (Verification). When "
            "you choose Verification, an extra box lets you start a new dated "
            "check or re-measure an existing one.\n\n"
            "A verification always belongs to a finished profile, so if the "
            "selected run has no profile yet, ChromIQ will ask you to build one "
            "first."),
            self)
        row.addWidget(self._tip_btn)

        # Hole 7 (State B): shown next to the greyed selectors when no profile
        # project is loaded — a first chart is made from Create Chart's name
        # field, not from here, so there's nothing to select yet.
        self._hint = self._mk_label(tr(
            "Load a profile project, or specify a profile project name and "
            "create your first chart, then you may choose a profile run."))
        self._hint.setObjectName("target_bar_hint")
        self._hint.setVisible(False)
        row.addWidget(self._hint)

        # Compact the three dropdowns to exactly the Manual-module look
        # (#compact_input → max-height 22 px) so the bar seats on the version rail.
        for c in (self._run_combo, self._type_combo, self._verify_combo):
            c.setObjectName("compact_input")
        self.set_accent(self._accent)

        # The folder this selection writes into, spelled out from the ChromIQ
        # folder down so "where are my files?" is answered on the spot.
        self._location = QLabel("", self)
        self._location.setObjectName("target_bar_location")
        self._location.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self._location.setToolTip(tr(
            "The folder your current Profile run and Run type selection works "
            "in. Charts you create, print or measure for this selection are "
            "read from and written to this folder, inside your ChromIQ folder. "
            "It follows the two dropdowns above, so you can always see where "
            "your files are going before you do anything."))
        column.addWidget(self._location)

        self._ctl.changed.connect(self._sync_from_controller)
        self.refresh()

    # ---- compact helpers --------------------------------------------------
    def _mk_label(self, text: str) -> QLabel:
        lbl = QLabel(text, self)
        lbl.setObjectName("target_bar_label")
        return lbl

    def set_accent(self, color: str) -> None:
        """Tint the combobox highlight and the ⓘ icon to follow the active
        tab's accent colour (called by the main window on tab change). Only the
        accent bits are set here so the #compact_input height/padding still win."""
        self._accent = color
        qss = (
            f"QComboBox#compact_input:hover, QComboBox#compact_input:focus "
            f"{{ border: 1px solid {color}; }}"
            f"QComboBox#compact_input QAbstractItemView "
            f"{{ selection-background-color: {color}; }}"
        )
        for c in (self._run_combo, self._type_combo, self._verify_combo):
            c.setStyleSheet(qss)
        self._tip_btn.set_color(color)

    def _on_restore_clicked(self) -> None:
        """Restore the selected verification's used chart, warning first when
        the chart currently in place is a different one (#130)."""
        from PyQt6.QtWidgets import QMessageBox
        if self._ctl.restore_needs_confirmation():
            box = QMessageBox(self)
            box.setWindowTitle(tr("Restore the chart this verification used?"))
            box.setText(tr(
                "The verification chart currently in this run will be replaced "
                "by the one this verification date was measured with.\n\n"
                "Your measurements are not affected — only the chart files are "
                "replaced. The chart that is there now is not kept, so if you "
                "still need it, cancel and save a copy first."))
            restore = box.addButton(tr("Restore Chart"),
                                    QMessageBox.ButtonRole.AcceptRole)
            box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
            box.exec()
            if box.clickedButton() is not restore:
                return
        result = self._ctl.restore_used_chart()
        if result is None:
            return
        if not result.ok:
            QMessageBox.warning(
                self, tr("The chart could not be restored"),
                tr("Nothing was changed — the verification chart is exactly as "
                   "it was.\n\nReason: {reason}").format(
                       reason=result.error or tr("unknown")))
            return
        if result.needs_regeneration:
            QMessageBox.information(
                self, tr("Chart restored — the pages need rebuilding"),
                tr("The chart files are back in place, but this chart was made "
                   "without the layout information ChromIQ needs to redraw its "
                   "printable pages, and no page images were stored with it.\n\n"
                   "Open the Create Chart tab and create the chart again to "
                   "produce the pages, then print as usual."))
        elif result.should_rebuild:
            # The pages are being redrawn from the chart's own recipe; the
            # finished build shows itself in the preview.
            log.info("restored chart: rebuilding its pages")

    def _update_location(self) -> None:
        """Refresh the "Location being edited" line for the current selection
        (#130, Knut). Hidden entirely until a profile project is open, so an
        empty app never shows a half-formed path."""
        where = self._ctl.location_being_edited()
        self._location.setVisible(bool(where))
        # Clear the text too, so a hidden label can never surface a stale path
        # if something shows it again later.
        self._location.setText(
            tr("Location being edited: {path}").format(path=where) if where else "")

    # ---- rebuild the run + verification lists from the project -----------
    def refresh(self) -> None:
        """Repopulate from the loaded project — call when the project or its
        runs change (e.g. a new run was created)."""
        self._sync_from_controller()

    def _sync_from_controller(self) -> None:
        self._update_location()
        self._syncing = True
        try:
            t = self._ctl.target
            # Hole 7 (State B): with no profile project loaded, grey the
            # selectors and show the hint; enable + hide it once a project exists.
            has_project = self._ctl.project_or_none() is not None
            for w in (self._run_label, self._run_combo, self._type_label,
                      self._type_combo, self._verify_label, self._verify_combo):
                w.setEnabled(has_project)
            self._hint.setVisible(not has_project)
            # Run dropdown: "Run N (overwrite)" per existing run + "New run".
            self._run_combo.clear()
            for rid in self._ctl.run_ids():
                self._run_combo.addItem(
                    tr("{run} (overwrite)").format(run=self._pretty_run(rid)), rid)
            self._run_combo.addItem(tr("New run"), _NEW)
            self._select_data(self._run_combo, t.profile_run or _NEW)

            # Run type.
            self._select_data(self._type_combo, t.run_type)

            # Verification dropdown (only for verification + when allowed here).
            is_verif = t.is_verification()
            show = self._show_verification and is_verif
            self._verify_label.setVisible(show)
            self._verify_combo.setVisible(show)
            self._restore_btn.setVisible(show)
            self._restore_tip.setVisible(show)
            if show:
                enabled, tip = self._ctl.restore_state()
                self._restore_btn.setEnabled(enabled)
                self._restore_btn.setToolTip(tip)
            if show:
                self._verify_combo.clear()
                run_id = t.profile_run
                for vid in self._ctl.verification_ids(run_id):
                    label = tr("Overwrite {when}").format(
                        when=self._pretty_date(vid))
                    if not self._ctl.verification_has_measurement(run_id, vid):
                        # Created when a measurement started, but never finished
                        # — say so, so an empty date is not mistaken for a result
                        # (#130, Knut). Its chart can still be restored.
                        label = tr("{when} — no measurement yet").format(
                            when=self._pretty_date(vid))
                    self._verify_combo.addItem(label, vid)
                self._verify_combo.addItem(tr("New verification"), _NEW)
                self._select_data(self._verify_combo, t.verification_id or _NEW)
        finally:
            self._syncing = False

    # ---- user edits → controller -----------------------------------------
    def _on_run_changed(self, _i: int) -> None:
        if self._syncing:
            return
        data = self._run_combo.currentData()
        self._ctl.set_profile_run("" if data == _NEW else str(data))

    def _on_type_changed(self, _i: int) -> None:
        if self._syncing:
            return
        self._ctl.set_run_type(str(self._type_combo.currentData()))

    def _on_verify_changed(self, _i: int) -> None:
        if self._syncing:
            return
        data = self._verify_combo.currentData()
        self._ctl.set_verification_id("" if data == _NEW else str(data))

    # ---- helpers ----------------------------------------------------------
    @staticmethod
    def _select_data(combo: NoScrollComboBox, data) -> None:
        idx = combo.findData(data)
        combo.setCurrentIndex(idx if idx >= 0 else max(0, combo.count() - 1))

    @staticmethod
    def _pretty_run(run_id: str) -> str:
        # "run1" → "Run 1"
        n = run_id[3:] if run_id.startswith("run") else run_id
        return tr("Run {n}").format(n=n)

    @staticmethod
    def _pretty_date(vid: str) -> str:
        # "2026-07-15_103000" → "2026-07-15 10:30"
        try:
            date, time = vid.split("_", 1)
            return f"{date} {time[:2]}:{time[2:4]}"
        except Exception:      # noqa: BLE001
            return vid
