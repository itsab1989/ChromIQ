"""The shared "Profile run" + "Run type" selector, used across the Create Chart,
Print Chart and Measure tabs (#130).

A single :class:`MeasurementTargetController` owns the app-wide selection and a
``changed`` signal; each tab embeds a :class:`MeasurementTargetBar` bound to that
controller, so changing the selection on any tab updates all of them. No tab
holds the state itself — the controller is the single source of truth.
"""
from __future__ import annotations

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from core.i18n import tr
from core.measurement_target import (
    RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION, MeasurementTarget)
from ui.tooltip_button import TooltipButton
from ui.widgets import NoScrollComboBox

_NEW = "\x00new"          # sentinel userData for the "New …" combo entries


class MeasurementTargetController(QObject):
    """Holds the shared :class:`MeasurementTarget` and answers the questions the
    bar needs about the loaded project (its runs and each run's verification
    dates). ``changed`` fires whenever the selection changes."""

    changed = pyqtSignal()

    def __init__(self, file_mgr, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._fm = file_mgr
        self._target = MeasurementTarget()

    @property
    def target(self) -> MeasurementTarget:
        return self._target

    def project_or_none(self):
        try:
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

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        row.addWidget(self._mk_label(tr("Profile run:")))
        self._run_combo = NoScrollComboBox(self)
        self._run_combo.setToolTip(tr(
            "Which profile build this applies to. Every profile you make is a "
            "“run”, kept in its own folder. Pick an existing run to work on it "
            "again — that overwrites that run's files — or choose “New run” to "
            "start a fresh profile alongside the ones you already have. Your "
            "older runs are never touched unless you select them here."))
        self._run_combo.currentIndexChanged.connect(self._on_run_changed)
        row.addWidget(self._run_combo)

        row.addSpacing(4)
        row.addWidget(self._mk_label(tr("Run type:")))
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

        # Compact the three dropdowns to exactly the Manual-module look
        # (#compact_input → max-height 22 px) so the bar seats on the version rail.
        for c in (self._run_combo, self._type_combo, self._verify_combo):
            c.setObjectName("compact_input")
        self.set_accent(self._accent)

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

    # ---- rebuild the run + verification lists from the project -----------
    def refresh(self) -> None:
        """Repopulate from the loaded project — call when the project or its
        runs change (e.g. a new run was created)."""
        self._sync_from_controller()

    def _sync_from_controller(self) -> None:
        self._syncing = True
        try:
            t = self._ctl.target
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
            if show:
                self._verify_combo.clear()
                run_id = t.profile_run
                for vid in self._ctl.verification_ids(run_id):
                    self._verify_combo.addItem(
                        tr("Overwrite {when}").format(when=self._pretty_date(vid)), vid)
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
