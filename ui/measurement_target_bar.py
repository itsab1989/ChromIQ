"""The shared "Profile run" + "Run type" selector, used across the Create Chart,
Print Chart and Measure tabs (#130).

A single :class:`MeasurementTargetController` owns the app-wide selection and a
``changed`` signal; each tab embeds a :class:`MeasurementTargetBar` bound to that
controller, so changing the selection on any tab updates all of them. No tab
holds the state itself — the controller is the single source of truth.
"""
from __future__ import annotations

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout,
                             QWidget)

from core.file_manager import CHART_SNAPSHOT_DIRNAME
from core.i18n import tr
from core.platform_paths import file_manager_name
from core.logger import get_logger
from core.measurement_target import (
    RUN_TYPE_CALIBRATION, RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION,
    MeasurementTarget, coerce_run_type)
from ui.tooltip_button import TooltipButton
from ui.widgets import NoScrollComboBox

log = get_logger(__name__)

_NEW = "\x00new"          # sentinel userData for the "New …" combo entries
#: "Profile run" while Run type = Calibration — a project has exactly one
#: calibration, so the box shows this single, unselectable entry (#137).
_CAL = "__calibration__"

#: The hint sentence against the row's trailing stretch. Ratios, not pixels: the
#: sentence gets the room, the stretch gets what is left of it.
_HINT_STRETCH = 1000


class MeasurementTargetController(QObject):
    """Holds the shared :class:`MeasurementTarget` and answers the questions the
    bar needs about the loaded project (its runs and each run's verification
    dates). ``changed`` fires whenever the selection changes."""

    changed = pyqtSignal()
    #: emitted after a verification's used chart has been restored, so the tabs
    #: can rebuild the pages and refresh what they show (#130).
    chart_restored = pyqtSignal()
    #: Raised the instant a target-changing pulldown opens, while the OUTGOING
    #: target is still selected — the write trigger in Knut's queue design
    #: (#130). Anything holding unsaved per-target state flushes it here.
    about_to_change_target = pyqtSignal()

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
        #: Preferences → Calibration options (#137). WITH THIS OFF THE APP MUST
        #: BEHAVE EXACTLY AS IT DID BEFORE: the third run type is not offered,
        #: cannot be reached, and a stored one is coerced away on the next
        #: read. Every calibration branch in this file is guarded by it.
        self._calibration_allowed = False

    def set_calibration_allowed(self, allowed: bool) -> None:
        """Follow Preferences → Calibration options.

        Switching it OFF while Calibration is selected drops back to Profiling —
        the selection would otherwise be unreachable but still active, which is
        the one way this feature could change behaviour for somebody who has it
        switched off.
        """
        allowed = bool(allowed)
        if allowed == self._calibration_allowed:
            return
        self._calibration_allowed = allowed
        if not allowed and self._target.is_calibration():
            self._target.run_type = RUN_TYPE_PROFILING
        self.changed.emit()

    @property
    def calibration_allowed(self) -> bool:
        return self._calibration_allowed

    def calibration_or_none(self):
        """The project's one calibration, or None when no project is open."""
        p = self.project_or_none()
        return None if p is None else p.calibration

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
            # Asked through getattr for the reason the comment above gives:
            # a duck-typed file manager may not have it, and four test doubles
            # do not. Calling it directly raised AttributeError, which this
            # `except` swallowed — and the bar then reported "no project" for a
            # project that was open, which sent the .ti2 loader down its
            # "outside any project" branch and into a modal dialog that never
            # closes without a user (#164).
            has_project = getattr(self._fm, "has_project", None)
            if has_project is None or has_project():
                return self._fm.project()
        except Exception as exc:   # noqa: BLE001 — the bar must never crash a tab
            # SAY SO ONCE, INSTEAD OF NOTHING AT ALL.
            #
            # Swallowing this is right — the bar asks constantly and must never
            # take a tab down with it — but swallowing it *silently* makes a
            # project that fails to load indistinguishable from no project at
            # all: every control on the bar goes inert, Restore Used Chart
            # reports "open a project first", and the log says nothing. A
            # malformed project.json cost real time to diagnose for exactly
            # that reason.
            #
            # Logged once per distinct failure, because this runs on every
            # refresh and an unconditional line would drown the log — which is
            # how the useful lines get missed in the first place.
            key = f"{type(exc).__name__}: {exc}"
            if key != getattr(self, "_last_project_error", None):
                self._last_project_error = key
                log.warning("the bar could not load the project — every "
                            "control on it will read as 'no project': %s", key)
            return None
        # A load that works clears the note, so a later failure is reported
        # again rather than being suppressed as a repeat.
        self._last_project_error = None
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
    # Each emits about_to_change_target FIRST: §2.1 makes every target change
    # one guarded write-then-load step. The pulldowns fire the write when they
    # OPEN (Q-1), but a change can also arrive programmatically — duplicate
    # run, a driver, a restore flow — and without the write here, the central
    # reload (§2 L3/L4) would discard the visible tab's unsaved edits instead
    # of filing them against the target they belong to. A second write after
    # Q-1 costs nothing: the last snapshot is remembered per target (Q-4).
    def set_run_type(self, value: str) -> None:
        # Coerced, never trusted: the value can arrive from a settings file
        # written while the preference was on, and Profiling is the only safe
        # landing place (#137 E21).
        value = coerce_run_type(value,
                                calibration_allowed=self._calibration_allowed)
        if value != self._target.run_type:
            self.about_to_change_target.emit()
            self._target.run_type = value
            self.changed.emit()

    def set_profile_run(self, run_id: str) -> None:
        if run_id != self._target.profile_run:
            self.about_to_change_target.emit()
            self._target.profile_run = run_id
            # A different run has its own verification dates — drop a stale pick.
            self._target.verification_id = ""
            self.changed.emit()

    def set_verification_id(self, vid: str) -> None:
        if vid != self._target.verification_id:
            self.about_to_change_target.emit()
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
            if self._target.is_calibration():
                # A CALIBRATION IS NOT IN A RUN. It is the project's one
                # calibration, in `cal/` — so naming a run folder here pointed
                # at a folder nothing was being written to. Knut, beta.147:
                # *"With Run type = Calibration, the 'Location being edited'
                # must show the path to the calibration folder
                # project_name/cal/ in relation to the ChromIQ default folder."*
                return "/".join([root.name, *rel.parts, "cal"]) + "/"
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

    def selected_run(self):
        """The :class:`Run` the bar points at, or None for "New run" / no
        project — the profiling counterpart of :meth:`selected_verification`."""
        try:
            proj = self.project_or_none()
            run_id = self._target.profile_run
            if proj is None or not run_id or not proj.has_run(run_id):
                return None
            return proj.run(run_id)
        except Exception:      # noqa: BLE001
            return None

    def restore_target(self):
        """Whichever of the THREE the button acts on, given the Run type.

        Calibration was missing here while `restore_state` already handled it,
        so the button could be offered for the calibration chart and then put
        the selected RUN's chart back instead — a restore that quietly replaces
        the wrong sheet (Knut, beta.150, asking why Restore did not work for a
        calibration).
        """
        if self._target.is_calibration():
            return self.calibration_or_none()
        if self._target.is_verification():
            return self.selected_verification()
        return self.selected_run()

    def restore_state(self) -> "tuple[bool, str]":
        """``(enabled, tooltip)`` for the Restore Used Chart button, with the
        exact wording from the specification for each reason it is unavailable."""
        from workflow.chart_slot import slot_for
        from workflow.verify_chart_snapshot import (slot_has_snapshot,
                                                    snapshot_matches_live)
        if self._measuring:
            return False, tr(
                "Not while a measurement is running. It will be available "
                "again as soon as the current measurement finishes or is "
                "stopped.")
        if self._target.is_calibration():
            cal = self.calibration_or_none()
            if cal is None:
                return False, tr(
                    "Open or create a printer profile project first — there is "
                    "no calibration chart to put back yet.")
            slot = slot_for(cal)
            if not slot_has_snapshot(slot):
                return False, tr(
                    "This project has no stored copy of a calibration chart "
                    "yet. A copy is kept as soon as you start measuring the "
                    "calibration chart, and this button can put it back "
                    "afterwards.")
            if snapshot_matches_live(slot):
                return False, tr(
                    "The calibration chart on disk is already identical to the "
                    "stored copy, so there is nothing to put back.")
            return True, tr(
                "Put back the calibration chart this project's calibration was "
                "measured with, exactly as it was printed — the pages, the "
                "patch layout and the .ti2 behind them. Use this when you want "
                "to reprint the sheet or read it again.")
        if self._target.is_verification():
            verification = self.selected_verification()
            if verification is None:
                return False, tr("Select an existing Verification run date to "
                                 "restore its used chart")
            if not slot_has_snapshot(slot_for(verification)):
                return False, tr("Selected Verification run date has no "
                                 "available chart to restore")
            if snapshot_matches_live(slot_for(verification)):
                return False, tr(
                    "Currently loaded chart files are already identical to "
                    "stored files in chart-folder. There is no need to restore "
                    "the chart files.")
            return True, tr("Restore chart used for selected verification "
                            "run date")
        # Profiling: the run itself holds one copy, so there is nothing to pick
        # — the button simply puts back the chart this run was measured with
        # (#130, Knut 2026-07-27).
        run = self.selected_run()
        if run is None:
            return False, tr("Create the chart for this run first — there is "
                             "nothing measured yet to restore a chart from")
        if not slot_has_snapshot(slot_for(run)):
            return False, tr("This profile run has no stored chart yet. A copy "
                             "is kept when you start a measurement, and this "
                             "button then brings that copy back")
        try:
            if run.load_meta().chart_snapshot_stale:
                # The user measured with "Measure without changing the stored
                # chart", so the copy describes an EARLIER measurement (#130).
                return True, tr(
                    "Restore the stored chart. Note: it is from an earlier "
                    "measurement — the measurement now in this run was taken "
                    "with a different chart")
        except Exception:      # noqa: BLE001
            pass
        if snapshot_matches_live(slot_for(run)):
            # Nothing to put back — pressing it would copy the chart over
            # itself, which is why it looked like nothing happened (Knut,
            # #130 2026-07-30).
            return False, tr(
                "Currently loaded chart files are already identical to stored "
                "files in chart-folder. There is no need to restore the chart "
                "files.")
        return True, tr("Restore the chart this profile run was measured with")

    def restore_needs_confirmation(self) -> bool:
        """Whether the live chart differs from the snapshot, so the user should
        be warned before it is replaced."""
        from workflow.chart_slot import slot_for
        from workflow.verify_chart_snapshot import slot_live_differs
        target = self.restore_target()
        return target is not None and slot_live_differs(slot_for(target))

    def restore_used_chart(self):
        """Put the selected verification's snapshotted chart back. Returns the
        :class:`RestoreResult`, or None when there is nothing to restore."""
        from workflow.chart_slot import slot_for
        from workflow.verify_chart_snapshot import restore_slot
        target = self.restore_target()
        if target is None:
            return None
        result = restore_slot(slot_for(target))
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

    def is_measuring(self) -> bool:
        """Whether a measurement is running right now.

        The bar asks, because everything on it changes which chart is being
        worked on — and doing that under a running measurement is what let
        Knut duplicate a run mid-read (#130, beta.120): the copy was made, the
        selection jumped to the new run, and the preview emptied while the
        instrument was still going.
        """
        return bool(self._measuring)

    def delete_plan(self):
        """What Delete would do for the current selection, or a ``BLOCK_*``
        code saying why the button is greyed (#130, Knut 2026-07-28)."""
        from core.run_delete import BLOCK_NO_PROJECT, plan_for
        try:
            return plan_for(self.project_or_none(), self._target,
                            measuring=self._measuring)
        except Exception:      # noqa: BLE001 — a greyed button, never a crash
            log.warning("Could not work out what Delete would do",
                        exc_info=True)
            return BLOCK_NO_PROJECT

    def delete_state(self) -> "tuple[bool, str]":
        """``(enabled, tooltip)`` for the Delete button — the same shape as
        :meth:`restore_state`, so the two buttons behave alike."""
        if self._target.is_calibration():
            return False, tr(
                "A project has exactly one calibration, and it is replaced "
                "rather than deleted: making a new calibration chart moves the "
                "one you have into the project's “cal/old” folder, named with "
                "the date, so you can always go back to it. Switch “Run type” "
                "to Profiling to delete a run.")
        from core.run_delete import block_tooltip, tooltip_for
        plan = self.delete_plan()
        if isinstance(plan, str):
            return False, block_tooltip(plan)
        return True, tooltip_for(plan)

    # ---- Duplicate run (#130, Knut + Sebastian, "course B" 2026-08-01) ----
    #: The chart files a run must have before it is worth duplicating. Knut's
    #: point 3: *"the basic chart files exist as minimum (ti1, ti2, .tif,
    #: .channels.json. All other specified files are copied only if they
    #: exist)"*.
    _DUPLICATE_REQUIRES = ("chart_ti1", "chart_ti2", "chart_channels_json")

    def selection_has_measurement(self) -> bool:
        """Whether the selected run (or dated verification) holds readings.

        A run can have a stored chart and no measurement — a Save Partial that
        read nothing removes the `.ti3` — and messages that speak about "your
        measurements" are then untrue (Knut, #130 2026-08-01).
        """
        try:
            proj = self.project_or_none()
            run_id = self._target.profile_run
            if proj is None or not run_id or not proj.has_run(run_id):
                return False
            run = proj.run(run_id)
            if self._target.is_verification():
                vid = self._target.verification_id
                if not vid:
                    return False
                return run.verification(vid).measurement_ti3.exists()
            return run.measurement_ti3.exists()
        except Exception:      # noqa: BLE001 — wording, never a crash
            return False

    def duplicate_source(self) -> "object | None":
        """The run Duplicate would copy, or None when it cannot run.

        Kept separate from :meth:`duplicate_state` so the button's reason and
        the button's action can never disagree about which run they mean.
        """
        try:
            proj = self.project_or_none()
            if proj is None:
                return None
            if self.target.is_verification():
                return None
            run_id = self.target.profile_run
            if not run_id or not proj.has_run(run_id):
                return None
            run = proj.run(run_id)
            if not all(getattr(run, name).exists()
                       for name in self._DUPLICATE_REQUIRES):
                return None
            if not run.chart_tiffs():
                return None
            return run
        except Exception:      # noqa: BLE001 — a greyed button, never a crash
            return None

    def _duplicate_missing_phrase(self) -> str:
        """"What is missing here" — named, so the rule is not a guessing game."""
        labels = {
            "chart_ti1":           tr("the patch list (.ti1)"),
            "chart_ti2":           tr("the laid-out chart (.ti2)"),
            "chart_channels_json": tr("the chart's layout recipe (.channels.json)"),
        }
        try:
            proj = self.project_or_none()
            run = proj.run(self.target.profile_run)
        except Exception:      # noqa: BLE001 — a tooltip, never a crash
            return tr("This run is missing some of them.")
        missing = [labels[n] for n in self._DUPLICATE_REQUIRES
                   if not getattr(run, n).exists()]
        try:
            if not run.chart_tiffs():
                missing.append(tr("at least one printed page (.tif)"))
        except Exception:      # noqa: BLE001
            pass
        if not missing:
            return tr("This run is missing some of them.")
        if len(missing) == 1:
            return tr("This run is missing {item}.").format(item=missing[0])
        return tr("This run is missing: {items}.").format(
            items=", ".join(missing))

    def duplicate_state(self) -> "tuple[bool, str]":
        """``(enabled, tooltip)`` for Duplicate — the same shape as
        :meth:`restore_state` and :meth:`delete_state`, so all three behave
        alike. Every disabled case names what to do about it, per Knut's
        point 5."""
        proj = self.project_or_none()
        if proj is None:
            return False, tr(
                "Open or create a printer profile first — there is no run yet "
                "to duplicate.")
        if self.target.is_calibration():
            return False, tr(
                "Duplicating works on a profiling run. A project has exactly "
                "one calibration, so there is nothing to duplicate here — "
                "switch “Run type” to Profiling to duplicate a run.")
        if self.target.is_verification():
            return False, tr(
                "Duplicating works on a profiling run. Switch “Run type” to "
                "Profiling to duplicate the run this verification belongs to.")
        run_id = self.target.profile_run
        if not run_id or not proj.has_run(run_id):
            return False, tr(
                "Select an existing profile run first — there is nothing yet "
                "to duplicate.")
        if self.duplicate_source() is None:
            # Knut, #130 beta.120: *"the tool-tip should also mention the
            # minimum requirement for a duplicate to be possible (Which chart
            # files must minimum be present for the button to activate)."* He
            # had worked out the rule himself from the greyed button; it should
            # not have taken working out.
            return False, tr(
                "This run does not have a complete chart yet, so there is "
                "nothing to copy.\n\n"
                "Duplicate needs all four of these in the run:\n"
                "  •  the patch list (.ti1)\n"
                "  •  the laid-out chart (.ti2)\n"
                "  •  the chart's layout recipe (.channels.json)\n"
                "  •  at least one printed page (.tif)\n\n"
                "{missing}\n\n"
                "The layout recipe is the one people are most often missing. "
                "It is what lets ChromIQ redraw the pages, so a run without it "
                "cannot be copied into a working chart — a .ti1 and .ti2 on "
                "their own would give you a run whose pages could never be "
                "printed. Charts made in older versions of ChromIQ, or brought "
                "in from elsewhere, may not have one.\n\n"
                "Create the chart in this run — or load it with “Open Chart "
                "File (.ti2)” at the top left — and Duplicate becomes "
                "available.").format(missing=self._duplicate_missing_phrase())
        return True, tr(
            "Duplicate this run. Makes a new run holding a copy of this run's "
            "chart, its measurement and the profile built from it, so you can "
            "carry on from here without changing anything you already have.\n\n"
            "Nothing is moved and nothing is overwritten — this run stays "
            "exactly as it is. Verification runs and their chart are not "
            "copied, so the new run is free to use a different one.")

    def duplicate_run(self) -> "str | None":
        """Duplicate the selected run and select the copy. Returns its id."""
        proj = self.project_or_none()
        source = self.duplicate_source()
        if proj is None or source is None:
            return None
        new_run = proj.duplicate_run(source)
        # Knut's point 6: "After duplicating the Profile run should switch to
        # the new run."
        self.set_run_type("Profiling")
        self.set_profile_run(new_run.id)
        self.notify_changed()
        return new_run.id

    def restore_slot_or_none(self):
        """The ChartSlot the Restore button would act on, or None.

        Same choice `restore_state` makes — the calibration, the dated
        verification, or the run itself — kept in one place so a warning about a
        restore can never describe a different slot from the one that gets
        restored.
        """
        try:
            from workflow.chart_slot import slot_for
            if self._target.is_calibration():
                cal = self.calibration_or_none()
                return slot_for(cal) if cal is not None else None
            if self._target.is_verification():
                verification = self.selected_verification()
                return slot_for(verification) if verification else None
            run = self.selected_run()
            return slot_for(run) if run else None
        except Exception:      # noqa: BLE001
            return None

    def reset_to_empty(self) -> None:
        """Forget which run and run type were selected, as at launch.

        Used after the whole project has been deleted (#130, Knut 2026-07-29):
        the selection named runs inside a folder that no longer exists, so
        keeping it would leave the bar describing a project the user just
        removed."""
        self._target = MeasurementTarget()
        self._pending_name = ""
        self._last_restore = None
        self.changed.emit()

    def notify_changed(self) -> None:
        """Force a ``changed`` emission even when no field value differs — used
        after the working PROJECT is switched out from under the bar (e.g. a
        Print/Measure load copied a new project in), so listeners refresh even
        if the new project's run id happens to match the old one (#130, Knut)."""
        self.changed.emit()


#: Qt's own "no maximum height" value. Setting a maximum and then clearing it
#: has to put back exactly this, or the widget keeps whatever ceiling it was
#: last given.
_QWIDGETSIZE_MAX = (1 << 24) - 1


class _AnnouncingComboBox(NoScrollComboBox):
    """A combo that says so *before* its list opens.

    Knut's trigger design for the settings queue (#130, 2026-08-06):

        "Writing queue request trigger could be when pulldown list of 'Profile
        run' or 'Run type' is clicked to see the pulldown menu, and reading
        queue request trigger could be when an option in the pulldown list is
        clicked/selected. Then there is some milliseconds between them too."

    That ordering is the point. When the list opens, the OUTGOING target is
    still the selected one, so a write triggered here lands on the target the
    values on screen actually belong to. By the time ``currentIndexChanged``
    fires the selection has already moved, and the same write would record the
    old target's values onto the new one.

    Nothing is connected to this yet — the tab-side half of the queue is still
    being built. It is here on its own because the mechanism is his and it is
    worth having in place, tested, before the behaviour that depends on it.
    """

    about_to_open = pyqtSignal()

    def showPopup(self) -> None:      # noqa: N802 — Qt's own name
        self.about_to_open.emit()
        super().showPopup()


class MeasurementTargetBar(QWidget):
    """A compact row: **Profile run** (a friendly single dropdown), **Run type**
    (Profiling / Verification), and — when ``show_verification`` and the type is
    Verification — a **Verification** date dropdown. Reflects and drives the
    shared controller."""

    #: The whole project folder was deleted (the second way out of the last-run
    #: case, #130 Knut D1) — the window closes the project and returns to the
    #: state a freshly started ChromIQ has.
    project_deleted = pyqtSignal()

    #: A run was duplicated (#130, "course B"): carries the NEW run's id. The
    #: host switches to Create Chart and refreshes the preview on all three
    #: tabs — Knut's point 6, "the Profile run should switch to the new run …
    #: Create Chart tab shows its chart".
    run_duplicated = pyqtSignal(str)

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
        self._run_combo = _AnnouncingComboBox(self)
        self._run_combo.setToolTip(tr(
            "Which profile build this applies to. Every profile you make is a "
            "“run”, kept in its own folder. Pick an existing run to work on it "
            "again — that overwrites that run's files — or choose “New run” to "
            "start a fresh profile alongside the ones you already have. Your "
            "older runs are never touched unless you select them here.\n\n"
            "While “Run type” is set to Calibration this shows “Project "
            "calibration” and cannot be changed: a calibration describes your "
            "printer, your paper and your inks — not one particular profile — "
            "so a project keeps exactly one, in its “cal” folder, and every "
            "profile run can use it. There is no run to pick."))
        #: The Calibration tooltip, swapped in while that run type is selected
        #: so the disabled box explains itself where the user tries to click.
        self._run_combo_cal_tip = tr(
            "A calibration describes your printer, your paper and your inks — "
            "not one particular profile — so a project keeps exactly one, in "
            "its “cal” folder, and every profile run can use it. There is no "
            "run to pick here.\n\n"
            "Switch “Run type” to Profiling or Verification to choose a run "
            "again.")
        self._run_combo.currentIndexChanged.connect(self._on_run_changed)
        # …and the WRITE trigger, before the list even appears.
        self._run_combo.about_to_open.connect(
            self._ctl.about_to_change_target)
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
        # Whether "Verification" may be picked from where the user is
        # standing; see set_verification_selectable.
        self._verification_selectable = True
        self._type_combo = _AnnouncingComboBox(self)
        self._type_combo.addItem(tr("Profiling"), RUN_TYPE_PROFILING)
        self._type_combo.addItem(tr("Verification"), RUN_TYPE_VERIFICATION)
        self._type_combo.setToolTip(tr(
"Are you preparing the printer first, building the profile "
            "itself, or checking a finished one?\n\n"
            "The list follows the order of the work: you calibrate, then "
            "you profile, then you verify. Most of the time you want "
            "Profiling, which is why it stays the one already selected.\n\n"
            "• Calibration — measure a special chart that brings the "
            "printer itself to a known, repeatable state before any profile "
            "is built. It produces a calibration file (.cal) which every "
            "profile run of this project can then use. One calibration is "
            "shared by the whole project, so there is nothing to choose "
            "under “Profile run” while this is selected. This step is "
            "optional; use it when you want your printer to behave the same "
            "way today and in six months. It is offered only while "
            "calibration options are switched on in Preferences.\n\n"
            "• Profiling — measure a chart printed with colour management "
            "OFF, so ChromIQ can learn your printer and build a profile "
            "from it. This is the normal choice.\n\n"
            "• Verification — measure a (usually smaller) chart printed "
            "THROUGH a finished profile, with colour management ON, to "
            "check how accurate that profile still is. A verification never "
            "builds a profile; it is kept as a dated record so you can "
            "watch a profile hold up — or drift — over time."))
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        # …and the WRITE trigger, before the list even appears.
        self._type_combo.about_to_open.connect(
            self._ctl.about_to_change_target)
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

        # The ⓘ for the three selectors belongs with the selectors, not at the
        # end of the row behind the buttons (Knut, #130 2026-07-28: "Move the
        # help info icon … to right after these, i.e. after the Verification
        # when that is visible, but then after Run type when Verification is
        # not visible"). One placement covers both: Verification is HIDDEN in
        # Profiling rather than removed, so a hidden box takes no width and the
        # icon closes up behind Run type by itself.
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
            "Choosing “New run” creates nothing yet — it copies the chart "
            "settings of the run you were just on as your starting point. "
            "Adjust whatever you like, and the moment you press “Generate "
            "Chart” a new run is made with exactly those settings. That makes "
            "“another run like this one, with one change” a ten-second job, "
            "and the run you came from is never touched.\n\n"
            "A verification always belongs to a finished profile, so if the "
            "selected run has no profile yet, ChromIQ will ask you to build one "
            "first."),
            self)
        row.addWidget(self._tip_btn)

        # Restore Used Chart — puts back the chart a past verification was
        # measured against (#130, Knut 2026-07-25). Sits directly right of the
        # Verification dropdown, with its own ⓘ.
        # The mark IS the button — no label beside it (#130, Knut 2026-07-29:
        # "The icons REPLACE the previous buttons totally… so that clicking the
        # icon functions as a button"), the same kind of widget as Create
        # Chart's "load profile" icon, at the height the text button had.
        # The three action pairs move right as a GROUP by this much (#130,
        # Basti 2026-08-03). Done as real spacing rather than another pixel of
        # glyph offset: the duplicate mark had reached the edge of its canvas,
        # so one more drawn pixel would have clipped it — and a whole-group
        # shift is a layout move by nature. Nothing before this point is
        # touched; only the cluster and the hint after it travel.
        row.addSpacing(self.CLUSTER_SHIFT)

        from ui.bar_icons import restore_chart_button
        self._restore_btn = restore_chart_button(
            self._accent, tr("Restore Used Chart"), self)
        self._restore_btn.clicked.connect(self._on_restore_clicked)
        row.addWidget(self._restore_btn)
        self._restore_tip = TooltipButton(
            tr("Restore Used Chart"),
            tr("Puts back the chart that was actually measured — which chart "
               "that is depends on “Run type”.\n\n"
               "RUN TYPE = PROFILING\n"
               "Every profile run keeps a copy of the chart it was measured "
               "with, saved the moment the measurement starts. If you later "
               "change or re-create that chart, the run's measurement no longer "
               "describes a chart you still have — this button brings the copy "
               "back, so the measurement makes sense again and you can reprint "
               "exactly the same sheet. It becomes available once that run has "
               "been measured at least once.\n\n"
               "RUN TYPE = VERIFICATION\n"
               "Each dated verification keeps its own copy in the same way, and "
               "the button puts back the one belonging to the date selected in "
               "the “Verification” box. Pick an existing date that has a stored "
               "chart and the button becomes available.\n\n"
               "RUN TYPE = CALIBRATION\n"
               "The project's calibration chart keeps a copy too, saved when "
               "its measurement starts. A calibration chart is the one chart "
               "that cannot simply be made again — the printed sheet you "
               "measured is the foundation of the calibration itself — so this "
               "copy is the way back to exactly that sheet. The button becomes "
               "available once the calibration has been measured.\n\n"
               "IN EVERY CASE\n"
               "Your measurements are never touched: only the chart files are "
               "replaced, and you are asked first whenever the chart currently "
               "in place is a different one. If a measurement was taken with "
               "the copy deliberately left alone, the button says so, because "
               "the copy then describes an earlier measurement."),
            self)
        row.addWidget(self._restore_tip)

        # Duplicate — a new run holding a copy of this one's work (#130, Knut
        # + Sebastian 2026-08-01, "course B"). His placement: "to the right of
        # 'Restore Used Chart' and its help icon, and to the left of 'delete'
        # icon", with its own ⓘ, taking the active tab's colour like the rest.
        from ui.bar_icons import duplicate_run_button
        self._duplicate_btn = duplicate_run_button(
            self._accent, tr("Duplicate"), self)
        self._duplicate_btn.clicked.connect(self._on_duplicate_clicked)
        row.addWidget(self._duplicate_btn)
        self._duplicate_tip = TooltipButton(
            tr("Duplicate"),
            tr("Makes a NEW profile run containing a copy of everything in the "
               "selected run that describes your work so far — the chart, the "
               "measurement, and the profile built from it.\n\n"
               "Nothing is moved and nothing is overwritten. The run you "
               "duplicate stays exactly as it is; the copy is somewhere fresh "
               "to carry on from.\n\n"
               "WHAT IT IS FOR\n"
               "•  Measuring the same chart again, without losing the "
               "measurement you already have.\n"
               "•  Building a different profile from a measurement you have "
               "already taken.\n"
               "•  Changing the chart your verification runs use — the copy "
               "starts with no verification chart, so you can give it a new "
               "one while the original run keeps its history.\n\n"
               "WHAT IS NOT COPIED\n"
               "Verification runs and their chart, and anything ChromIQ can "
               "rebuild by itself. You are shown exactly what will be copied, "
               "and asked, before anything happens.\n\n"
               "It becomes available once a profile run is selected — not "
               "“New run” — with “Run type” set to Profiling and a chart "
               "already in that run."),
            self)
        row.addWidget(self._duplicate_tip)

        # Delete — removes the selected profile run, or the selected run's
        # verification files (#130, Knut 2026-07-28). Sits right of Restore
        # Used Chart, with its own ⓘ; the hint text follows both.
        from ui.bar_icons import delete_button
        self._delete_btn = delete_button(self._accent, tr("Delete"), self)
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        row.addWidget(self._delete_btn)
        self._delete_tip = TooltipButton(
            tr("Delete"),
            tr("Removes work you no longer want, permanently. What it removes "
               "depends on “Run type”, and you are always shown exactly what "
               "will go — and asked — before anything is deleted.\n\n"
               "RUN TYPE = PROFILING\n"
               "Deletes the whole selected profile run: its chart, its "
               "measurement, its profile, its reports and its verifications. "
               "The remaining runs are then renumbered so the numbering stays "
               "unbroken — delete run 6 of 10 and run 7 becomes run 6, and so "
               "on — and ChromIQ moves to the last run in the project. The "
               "files inside the remaining runs are not renamed.\n\n"
               "If the run you pick is the only one in the project, it cannot "
               "be deleted on its own, because a project always has at least "
               "one run. You are offered two ways forward instead: empty that "
               "run, or delete the whole project.\n\n"
               "RUN TYPE = VERIFICATION\n"
               "With several verification dates and one of them selected, only "
               "that date is deleted. Otherwise the run's whole verification "
               "folder goes — the verification chart, any result in it, and the "
               "exports, archives and reports that belong to it — because with "
               "the last verification gone there is nothing left for those to "
               "belong to. The profiling side of the run is never touched.\n\n"
               "IN BOTH CASES\n"
               "Nothing is moved to the Trash and nothing is kept in an “old” "
               "folder: what you confirm is removed for good. The button is "
               "greyed whenever there is nothing specific to delete — during a "
               "measurement, or when the selection says “New run” or “New "
               "verification”, which name nothing on disk yet."),
            self)
        row.addWidget(self._delete_tip)

        # Hole 7 (State B): shown next to the greyed selectors when no profile
        # project is loaded — a first chart is made from Create Chart's name
        # field, not from here, so there's nothing to select yet.
        self._hint = self._mk_label(tr(
            "Load a profile project, or specify a profile project name and "
            "create your first chart, then you may choose a profile run."))
        self._hint.setObjectName("target_bar_hint")
        self._hint.setVisible(False)
        # It stays where it belongs — to the right of the ⓘ, beside the boxes it
        # is about — and WRAPS there rather than running past the version text
        # (Knut, #130 2026-07-27: my first fix moved it below the row, which is
        # the place reserved for "Location being edited:"). It takes the row's
        # leftover width and gives the rest back, so a long sentence turns into
        # a second line instead of a longer bar.
        self._hint.setWordWrap(True)
        # heightForWidth is what makes a wrapped label ask for the height its
        # GIVEN width needs. Without it the layout sizes it from a sizeHint that
        # assumes some other width, and the bar grows to a ridiculous height.
        _hp = QSizePolicy(QSizePolicy.Policy.Preferred,
                          QSizePolicy.Policy.Minimum)
        _hp.setHeightForWidth(True)
        self._hint.setSizePolicy(_hp)
        # No minimum of its own: a wrapped sentence can always take another
        # line, and a minimum here is added to the BAR's minimum — which at
        # narrow window widths pushed the whole bar out over the version text
        # instead of wrapping (measured at 1000 px).
        self._hint.setMinimumWidth(0)
        self._hint.setAlignment(Qt.AlignmentFlag.AlignLeft
                                | Qt.AlignmentFlag.AlignVCenter)
        # It takes essentially all the slack in the row, so its box runs from the
        # ⓘ to the version text rather than sharing the space with the trailing
        # stretch — which is what wrapped it into a narrow column of four lines
        # (Knut, #131 2026-07-27). The stretch still packs the boxes to the left
        # whenever the sentence is hidden, which is the usual case.
        self._hint_beside = True
        self._hint_wanted = False
        row.addWidget(self._hint, _HINT_STRETCH)
        # Everything in the row stays left-aligned and in sequence, so switching
        # Run type to Verification simply adds its boxes on the right (Knut,
        # #130 2026-07-26). Without this the row is as wide as the location line
        # below it, and the slack is shared out *between* the boxes — spreading
        # them across the screen and pulling every label away from its box.
        row.addStretch(1)

        # Compact the three dropdowns to exactly the Manual-module look
        # (#compact_input → max-height 22 px) so the bar seats on the version rail.
        for c in (self._run_combo, self._type_combo, self._verify_combo):
            c.setObjectName("compact_input")
            # A QComboBox expands by default; here it must keep its own width so
            # the trailing stretch is the only thing that grows.
            c.setSizePolicy(QSizePolicy.Policy.Preferred,
                            c.sizePolicy().verticalPolicy())
        # Know the calibration preference BEFORE the first widths are worked
        # out; MainWindow's fan-out arrives a paint too late. See
        # _settings_calibration_allowed.
        self._ctl.set_calibration_allowed(self._settings_calibration_allowed())
        self.set_accent(self._accent)

        # The bar sits ON the masthead's version rail, which the masthead paints
        # itself. Named so the dark stylesheet can keep the app-wide QWidget
        # background off it — see the rule in ui/styles.py (#130, Basti
        # 2026-08-03: the bar came out lighter than the rail in dark mode).
        self.setObjectName("target_bar")

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
            "your files are going before you do anything.\n\n"
            "If you would rather not see it, you can turn this line off in "
            "Preferences → General with “Show the location being edited”."))
        # The path can be long, and it must never be what decides how wide the
        # bar has to be: a label that refuses to shrink drags the bar out past
        # the version text, or — worse — forces a minimum the rail cannot give,
        # which is what makes the boxes above overlap. Its width is ignored and
        # the text is shortened in the middle when space is tight; the full path
        # stays in the tooltip.
        self._location.setSizePolicy(QSizePolicy.Policy.Ignored,
                                     QSizePolicy.Policy.Preferred)
        column.addWidget(self._location)

        # Each ⓘ travels with the mark it explains, so the gaps within each pair
        # stay as they are and the whole cluster shifts (#130, Basti 2026-08-03,
        # over several passes). The marks carry their own half in the NUDGE of
        # each button class in ui/bar_icons.py.
        self._restore_tip.set_nudge(1.0, 0.0)
        self._duplicate_tip.set_nudge(1.0, 0.0)
        self._delete_tip.set_nudge(-2.0, 0.0)

        self._ctl.changed.connect(self._sync_from_controller)
        self.refresh()

    # ---- locked on tabs that do not use the selection ---------------------
    def set_verification_selectable(self, selectable: bool) -> None:
        """Grey the "Verification" entry itself, rather than the whole box.

        Knut's answer to "what should happen if the user picks Verification
        while standing on tab 4", which is the tab a verification closes
        (beta.157): *"Can you grey out and disable the option 'Verification' in
        the dropdown list of Run type? and show a tool tip if hovering over
        that option … This method would tell user more than being thrown out of
        a tab."* He is right — being moved to another tab tells you nothing
        about why.
        """
        if selectable == getattr(self, "_verification_selectable", True):
            return
        self._verification_selectable = selectable
        self._apply_verification_item_state()

    def _apply_verification_item_state(self) -> None:
        """Enable or disable the one item, and give it its own tooltip.

        A QComboBox item is disabled through its model, not the widget: clearing
        the Enabled role greys it and makes it unselectable while the rest of
        the list stays live.
        """
        from PyQt6.QtCore import Qt as _Qt

        selectable = getattr(self, "_verification_selectable", True)
        model = self._type_combo.model()
        for i in range(self._type_combo.count()):
            if self._type_combo.itemData(i) != RUN_TYPE_VERIFICATION:
                continue
            item = model.item(i) if hasattr(model, "item") else None
            if item is None:
                return
            item.setEnabled(selectable)
            item.setToolTip("" if selectable else tr(
                "Not while standing on Build Profile / Calibration and "
                "Profiling tab. Change tab to select verification run."))

    def set_locked(self, locked: bool) -> None:
        """Grey the whole selection out, keeping it readable (Knut, #130
        2026-07-26).

        Build Profile and Check & Refine work on the measurement file you load
        into them, not on this selection — so leaving these boxes live there
        invites a change that appears to do nothing. Locked, they still say
        which run and run type you are on, and their tooltips say where to
        change it.
        """
        if locked == getattr(self, "_locked", False):
            return
        self._locked = locked
        self._sync_from_controller()

    def set_build_running(self, running: bool) -> None:
        """Grey the selection while a chart or a profile is being built.

        A THIRD REASON, not a rephrasing of the other two. The bar used to lock
        only for a measurement, so during a chart build Delete, Duplicate and
        the run picker all stayed live — on the very run targen was writing
        into. Driven to the end: Delete removed that run under the running
        subprocess, targen then failed with a message that gave no hint the
        person had caused it, and the survivors were renumbered while a
        subprocess still held a path inside the tree.

        NOT DRIVEN BY `ArgyllRunner.is_running`, which is the obvious answer and
        the wrong one: the runner is app-wide, so it is true for every Tools
        subprocess that touches nothing here, and it is FALSE exactly when this
        matters — between targen finishing and printtarg starting, and for the
        whole in-process layout-engine phase, which is when the .ti2 and every
        page image are written. `MainWindow` already keeps the three flags that
        do mean it and already funnels them through one method; this is fed from
        there, so the two cannot drift (#164's "from ONE place").
        """
        if running == getattr(self, "_build_running", False):
            return
        self._build_running = running
        self._sync_from_controller()

    def _building_note(self) -> str:
        return tr("Not while ChromIQ is building. The profile run you are "
                  "looking at is being written to at this very moment, and "
                  "changing it now could damage the chart being made. This "
                  "unlocks on its own as soon as the build finishes.")

    #: How far right the three action pairs sit as a group, in pixels. Grown a
    #: pixel at a time by eye (#130, Basti 2026-08-03). Kept apart from the
    #: per-mark NUDGE values in ui/bar_icons.py, which set the marks' positions
    #: RELATIVE to one another; this moves all of them together.
    CLUSTER_SHIFT = 1

    _LOCK_NOTE = None       # built lazily so tr() runs after the language loads

    _MEASURING_NOTE = None

    def _measuring_note(self) -> str:
        """Why everything on the bar is greyed while a measurement runs."""
        if self._MEASURING_NOTE is None:
            type(self)._MEASURING_NOTE = tr(
                "Not while a measurement is running. It will be available "
                "again as soon as the current measurement finishes or is "
                "stopped.\n\n"
                "Everything on this bar changes which chart is being worked "
                "on, and the instrument is reading one right now. Your place "
                "is kept: the same profile run and run type are still "
                "selected when it comes back.")
        return self._MEASURING_NOTE

    def _lock_note(self) -> str:
        if self._LOCK_NOTE is None:
            type(self)._LOCK_NOTE = tr(
                "This selection is not used on the Build Profile and Check & "
                "Refine tabs — both work on the measurement file you load into "
                "them. It is shown here so you can see where you are, and can "
                "be changed on the Create Chart, Print Chart and Measure tabs.")
        return self._LOCK_NOTE

    @staticmethod
    def _icon_tip(btn, body: str) -> str:
        """The tooltip for an icon-only button: its NAME, then the explanation.

        A button with a label carries its name on its face, so its tooltip could
        start straight into "why this is greyed". These two carry only a drawn
        mark (#130, Knut 2026-07-29), so the name has to come from the tooltip —
        otherwise the first thing a hover tells you about a greyed trash can is
        why you can't use something you were never told the name of.
        """
        name = btn.text()
        return f"{name}\n\n{body}" if name and body else (name or body)

    # ---- stable, readable widths (Knut, #130 2026-07-26) ------------------
    # What the compact_input stylesheet adds around a box's text: 6 px of left
    # padding, 28 px on the right for the arrow, plus the frame. Measured
    # rather than guessed from sizeHint(), because a widget's style-sheet
    # padding is not in its hint until Qt has polished it — which is why a box
    # could come up too narrow and then correct itself on a later visit.
    _COMBO_CHROME = 42
    _BUTTON_CHROME = 30

    @staticmethod
    def _combo_chrome(box) -> int:
        """How much of a combobox's width is NOT available to its text.

        Asked of the style rather than assumed: the arrow, the frame and the
        style sheet's padding differ between platforms and themes, and a guess
        that is a few pixels short shows up as an elided "Run 1 (overwr…".
        Returns 0 when the style cannot say, so the caller can fall back.
        """
        from PyQt6.QtWidgets import QStyle, QStyleOptionComboBox
        try:
            opt = QStyleOptionComboBox()
            opt.initFrom(box)
            opt.frame = True
            field = box.style().subControlRect(
                QStyle.ComplexControl.CC_ComboBox, opt,
                QStyle.SubControl.SC_ComboBoxEditField, box)
            return max(0, box.width() - field.width())
        except Exception:      # noqa: BLE001 — sizing must never raise
            return 0

    def _fit_box(self, box, texts) -> None:
        """Width *box* so every one of *texts* is fully readable, and never let
        it shrink again.

        Widths are computed from the widest text the box can **ever** show, not
        from what it happens to show now, so switching tabs, picking another run
        or a date gaining a measurement cannot change the layout under the
        user's hands.
        """
        # Measure against the font the box will actually be PAINTED with. A
        # stylesheet reaches a widget at polish, which without this happens
        # after the first fit — so the box was sized with the pre-stylesheet
        # font, then re-fitted when the real one arrived, and everything to its
        # right slid sideways as it grew. Measured: the Profile run box went
        # 147 -> 176 px on the first event pass, and the six controls after it
        # moved by exactly that 29 px (Basti, beta.142: *"directly after
        # loading it seems that the run type combobox is adjusting its width a
        # bit. looks like a jump"* — it was its neighbour pushing it).
        box.ensurePolished()
        fm = box.fontMetrics()
        widest = max((fm.horizontalAdvance(t) for t in texts if t), default=0)
        # +4 px of air so a text that measures exactly the field width is not
        # elided by a rounding difference between measuring and painting.
        want = widest + (self._combo_chrome(box) or self._COMBO_CHROME) + 4
        want = max(want, box.minimumWidth(), getattr(box, "_cq_floor", 0))
        box._cq_floor = want
        box.setFixedWidth(want)

    def changeEvent(self, event) -> None:      # noqa: N802
        """Re-fit when the style or the font changes.

        A widget's style-sheet padding is not in its metrics until Qt has
        polished it, so the fit done while the bar is being built is too tight.
        Re-fitting here means the correction lands before the first paint —
        this is what made a box "suddenly get wider" on the next tab switch
        (Knut, #130 2026-07-26).
        """
        from PyQt6.QtCore import QEvent
        super().changeEvent(event)
        if event.type() in (QEvent.Type.StyleChange, QEvent.Type.FontChange,
                            QEvent.Type.PaletteChange):
            self._fit_widths(getattr(self, "_last_labels", ()))

    def showEvent(self, event) -> None:         # noqa: N802
        super().showEvent(event)
        self._fit_widths(getattr(self, "_last_labels", ()))

    #: How narrow a box may be squeezed when the rail cannot hold the row at
    #: its comfortable width. Elided text is a poor second best — but it is far
    #: better than boxes climbing over each other, or over the version.
    _SQUEEZE_FLOOR = 150

    #: The absolute floor, used only when the comfortable one still leaves the
    #: row too wide for the rail. Below this a box shows almost nothing, so it
    #: is a last resort — but still better than a row that runs under the
    #: version text (the beta.29 overlap).
    _SQUEEZE_HARD_FLOOR = 96

    def wants_full_width(self) -> bool:
        """Whether the bar should be given the whole rail rather than just its
        own preferred width.

        True while the hint sentence is shown: its box has to reach the version
        text so the sentence wraps against that edge and follows the window as it
        is resized (Knut, #131 2026-07-27). At every other time the bar is
        exactly as wide as its boxes need, which is what keeps them packed left.
        """
        return bool(self._hint.isVisible())

    def set_available_width(self, px: int) -> None:
        """Tell the bar how much room it has, so it can give way gracefully.

        Called by the masthead before it places the bar. With plenty of room
        every box shows its longest entry in full; with too little, the widest
        box gives up width first, down to a floor — the bar never demands more
        than it has been given (Knut, #130 2026-07-26).
        """
        px = int(px)
        if px <= 0 or px == getattr(self, "_avail", 0):
            return
        self._avail = px
        # ORDER MATTERS. The boxes are sized for the layout they will be in,
        # not the one they were in: placing after fitting meant the squeeze was
        # computed against the PREVIOUS placement, which is half of the
        # beside/below flip-flop (a 6-rung oscillation, measured 1200-1140 px).
        self._place_labels()     # rung 1 — a label is the cheapest thing to lose
        self._place_hint()       # rung 2 — decide where the sentence lives …
        self._fit_widths(getattr(self, "_last_labels", ()))   # … then size the boxes
        self._place_hint()       # … and confirm, now the widths are known
        self.layout().activate()
        self._pin_row_when_alone()

    #: The narrowest the hint sentence may be beside the boxes. Below this it
    #: wraps into a column one or two words wide and the bar grows absurdly tall
    #: (measured: 47 px → 21 lines), so it moves under the row instead. Chosen so
    #: that Knut's rule still holds at 1200 px, a common window width.
    _HINT_FLOOR = 200

    #: The tallest the hint sentence may be while it sits BESIDE the marks —
    #: one row band, i.e. at most two lines. Beyond this it is a narrow column
    #: whose first and last lines are clipped (Basti: "a narrow column of 3
    #: lines with the top and bottom lines cut off"), so it takes a full-width
    #: line under the row instead, where it is read in one go.
    _HINT_BAND = 34

    #: Hysteresis on every ladder rung: a rung is given up at its own
    #: threshold and taken back only this much wider, so dragging the window
    #: edge across the boundary cannot make the bar chatter between layouts.
    _RUNG_HYSTERESIS = 24

    def _label_pairs(self):
        """Each label with the box it names.

        A label is WANTED only when its box is on screen. ``_verify_label`` is
        in the row at all times and merely hidden in Profiling, so counting it
        unconditionally overstated the row by ~90 px and dropped the other two
        a whole breakpoint early.
        """
        return ((self._run_label, self._run_combo),
                (self._type_label, self._type_combo),
                (self._verify_label, self._verify_combo))

    def _wanted_labels(self):
        return [lbl for lbl, box in self._label_pairs()
                if lbl is not None and box is not None and box.isVisibleTo(self)]

    def _fixed_row_width(self, with_labels: bool) -> int:
        """The width the row needs, WITHOUT the hint sentence.

        Summed from size hints rather than read off the live layout, because
        every caller uses it to decide something that would CHANGE the live
        layout. ``row.minimumSize().width()`` moves 141 px the moment the hint
        leaves the row, so a predicate reading it is bistable — which is what
        made the placement oscillate. A hidden widget's size hint does not
        move, so this number is stable whatever the decision turns out to be.
        """
        row = self.layout().itemAt(0).layout()
        wanted = self._wanted_labels()
        total = count = 0
        for i in range(row.count()):
            w = row.itemAt(i).widget()
            if w is None or w is self._hint:
                continue
            if w in wanted:
                if not with_labels:
                    continue
            elif not w.isVisibleTo(self):
                continue
            total += max(w.sizeHint().width(), w.minimumWidth())
            count += 1
        return total + row.spacing() * max(0, count - 1)

    def _free_for_hint(self) -> int:
        """The room the sentence would really be given beside the boxes."""
        avail = getattr(self, "_avail", 0)
        if not avail:
            return 0
        return (avail - self._fixed_row_width(getattr(self, "_labels_on", True))
                - self.layout().itemAt(0).layout().spacing())

    def _place_labels(self) -> None:
        """Drop "Profile run:" / "Run type:" / "Verification:" when the row
        cannot hold them, and bring them back when it can.

        The labels go before the boxes do, because a box's contents are the
        user's data and a label is a name the box's own tooltip already gives.
        In Verification at the minimum window width the three labels cost
        219 px in English and 331 px in Spanish — which is the whole of the
        overrun that put the Delete icon on top of the version number.

        Decided on ``_fixed_row_width``, which does not move when the decision
        fires, and with hysteresis so a drag cannot chatter.
        """
        avail = getattr(self, "_avail", 0)
        if not avail:
            return
        need = self._fixed_row_width(True)
        was = getattr(self, "_labels_on", True)
        on = (avail >= need - self._RUNG_HYSTERESIS) if was else (avail >= need)
        if on == was:
            return
        self._labels_on = on
        for lbl in self._wanted_labels():
            lbl.setVisible(on)

    def _place_hint(self) -> None:
        """Keep the hint sentence beside the boxes for as long as it fits there.

        Knut's rule (#131, 2026-07-27) is that the sentence lives to the right of
        the two ⓘ and wraps against the version text. That holds at every window
        width where it CAN hold. Below about 1100 px the row's own boxes already
        fill the rail, and honouring the rule there would give the sentence forty
        pixels — a column one word wide, twenty-one lines tall. At that point it
        moves to its own line under the row, where the whole window width is
        available, and returns the moment there is room again.
        """
        if self._hint is None:
            return
        avail = getattr(self, "_avail", 0)
        if not avail:
            return
        row = self.layout().itemAt(0).layout()
        # The honest criterion, replacing a flat 200 px: the sentence may stay
        # beside the marks only while it costs the row nothing — i.e. while it
        # still wraps within the row's own band. Measured against the room it
        # would REALLY get (`_free_for_hint`), not against a row minimum that
        # changes as soon as this decision moves the label. That self-reference
        # is what latched the old predicate into a flip-flop.
        free = self._free_for_hint()
        was = getattr(self, "_hint_beside", True)
        band = self._HINT_BAND
        beside = free > 0 and self._hint.heightForWidth(free) <= band
        # …plus hysteresis, so the boundary is not a chattering edge.
        if beside != was:
            probe = free + (self._RUNG_HYSTERESIS if was
                            else -self._RUNG_HYSTERESIS)
            beside = (probe > 0
                      and self._hint.heightForWidth(max(1, probe)) <= band)
        if beside == was:
            return
        self._hint_beside = beside
        col = self.layout()
        row.removeWidget(self._hint)
        col.removeWidget(self._hint)
        if beside:
            row.insertWidget(row.count() - 1, self._hint, _HINT_STRETCH)
        else:
            col.insertWidget(1, self._hint)      # under the row, above location
        self._hint.setParent(self)
        self._hint.setVisible(self._hint_wanted)
        col.activate()

    def _squeeze_to_fit(self) -> None:
        """Take width off the widest box until the row fits the space given."""
        avail = getattr(self, "_avail", 0)
        if not avail:
            return
        row = self.layout().itemAt(0).layout()
        natural = row.minimumSize().width()
        # The sentence is part of the row when it is shown, and it must keep a
        # readable width — so the boxes are squeezed for it, not the other way
        # round (Knut, #131 2026-07-27).
        # …but only while the sentence IS in the row. Charging the row 200 px
        # for a label that has moved below it crushed both boxes to their hard
        # floor at every narrow width — "New r" and "Profill" — while the row
        # itself had room to spare.
        if self._hint.isVisible() and getattr(self, "_hint_beside", True):
            natural += self._HINT_FLOOR
        excess = natural - avail
        if excess <= 0:
            return
        # The verification box is both the widest and the one whose entries
        # elide most gracefully — a shortened date still reads as a date.
        # Two passes with two floors. The comfortable floor is tried first, so
        # in the ordinary case nothing is squeezed harder than it has to be. If
        # the row STILL does not fit, the boxes give up more rather than let it
        # climb over the version text — that overrun is the beta.29 fault, and
        # a shortened date is a far smaller price than overlapping widgets.
        # The second floor became necessary when the Delete button joined the
        # row (#130, 2026-07-28): it and its ⓘ cost about 110 px, which is
        # exactly what a tight window did not have spare.
        # The comfortable floor is now PER BOX and is the box's own longest
        # entry: give up width, but never below what you must show. One number
        # for three boxes with three different contents in thirteen languages
        # could not do that job — at 150 px the Verification run box already
        # clipped, so the pass that is meant never to lose information lost it
        # on its first step.
        for readable in (True, False):
            for box in (self._verify_combo, self._run_combo, self._type_combo):
                if excess <= 0:
                    return
                if not box.isVisible():
                    continue
                floor = (self._readable_width(box) if readable
                         else self._SQUEEZE_HARD_FLOOR)
                # minimumWidth, not width(): setFixedWidth pins both bounds,
                # while the live geometry is whatever the last (too narrow)
                # layout left.
                have = box.minimumWidth()
                give = min(excess, max(0, have - floor))
                if give > 0:
                    box.setFixedWidth(have - give)
                    excess -= give

    def _readable_width(self, box) -> int:
        """The narrowest *box* may be while every entry it can show still fits."""
        fm = box.fontMetrics()
        widest = max((fm.horizontalAdvance(box.itemText(i))
                      for i in range(box.count())), default=0)
        return widest + (self._combo_chrome(box) or self._COMBO_CHROME) + 4

    def _fit_widths(self, verify_labels=()) -> None:
        """Give every box and the Restore button a width that stays put."""
        self._last_labels = tuple(verify_labels)
        self._fit_box(self._run_combo,
                      [self._run_combo.itemText(i)
                       for i in range(self._run_combo.count())]
                      # "Project calibration" is longer than "Run 8
                      # (overwrite)", which is what this box's floor was sized
                      # for. Included whatever is selected, so the box does not
                      # resize as the user moves between run types.
                      + ([tr("Project calibration")]
                         if self._ctl.calibration_allowed else []))
        self._fit_box(self._type_combo,
                      [self._type_combo.itemText(i)
                       for i in range(self._type_combo.count())])
        # The verification box is measured against BOTH labels every date can
        # carry — "Overwrite <date>" and "<date> — no measurement yet" — so a
        # date gaining a measurement never resizes it.
        self._fit_box(self._verify_combo, list(verify_labels) or
                      [self._verify_combo.itemText(i)
                       for i in range(self._verify_combo.count())])
        # Restore Used Chart and Delete need no width fitting any more: they
        # carry no text, so their size is the fixed square BarIconButton asks
        # for (#130, Knut 2026-07-29). Nothing here may widen them — a label
        # that isn't painted must not reserve room.

        # …and if that comfortable row does not fit the rail, give way.
        self.layout().activate()
        self._squeeze_to_fit()

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
        # EVERY ⓘ in the bar follows the active tab, not just the last one —
        # the Restore button's icon kept the Measure tab's green everywhere
        # else (Knut, #130 2026-07-27), and the Delete button's icon did the
        # same when it was added (Knut, #130 2026-07-28). Anything added to the
        # bar in future belongs in this tuple too.
        # Found by hand, twice by Knut and once by Sebastian, so it is now
        # found by looking rather than by remembering: every TooltipButton that
        # is a child of this bar, whoever added it.
        for tip in self.findChildren(TooltipButton):
            tip.set_color(color)
        # …and the two icon-only buttons, for the same reason: everything on
        # this bar follows the tab you are looking at. They ARE their marks now,
        # so this is the only place their colour comes from.
        self._restore_btn.set_accent(color)
        self._duplicate_btn.set_accent(color)
        self._delete_btn.set_accent(color)

    def _confirm_restore_losing_pages(self) -> bool:
        """Ask before a restore removes page images it cannot put back.

        Knut ruled on this (#130, 2026-08-02): *"I prefer option '1. Warn and
        let it proceed', but that the warning allow user to make the informed
        choice (The warning window must ask the user to investigate the
        specific files in question to make an informed decision)"* — so the
        files are named, the folders are named, and each button says what it
        does.

        Returns True to go ahead.
        """
        from PyQt6.QtWidgets import QMessageBox
        from workflow.verify_chart_snapshot import restore_would_lose_pages
        try:
            slot = self._ctl.restore_slot_or_none()
            at_risk = restore_would_lose_pages(slot) if slot else []
        except Exception:      # noqa: BLE001 — never block a restore on this
            return True
        if not at_risk:
            return True
        names = "\n".join(f"    •  {p.name}" for p in at_risk)
        run_folder = at_risk[0].parent
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        title = tr("The printable pages of this chart cannot be brought back")
        box.setWindowTitle(title)
        box.setText(title + "\n\n" + tr(
            "Restoring replaces everything in the run with the stored copy. "
            "The stored copy has no page images, and this chart carries no "
            "layout recipe for ChromIQ to redraw them from — so the "
            "following images would be removed and can not be recreated:\n\n"
            "{names}\n\n"
            "Please look at both folders before you decide:\n\n"
            "    the run:           {run}\n"
            "    the stored chart:  {stored}\n\n"
            "What each button does:\n\n"
            "•  Restore chart files anyway — the stored chart files are put "
            "back and the page images listed above are deleted. You would need "
            "to create the chart again to print it.\n\n"
            "•  Cancel and keep the current chart files — nothing is changed. "
            "The run keeps the chart and the pages it has now."
        ).format(
            names=names, run=run_folder,
            stored=run_folder / CHART_SNAPSHOT_DIRNAME))
        go = box.addButton(tr("Restore chart files anyway"),
                           QMessageBox.ButtonRole.DestructiveRole)
        keep = box.addButton(tr("Cancel and keep the current chart files"),
                             QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(keep)
        from ui.widgets import fit_message_box_buttons
        fit_message_box_buttons(box)
        box.exec()
        return box.clickedButton() is go

    def _on_restore_clicked(self) -> None:
        """Restore the selected verification's used chart, warning first when
        the chart currently in place is a different one (#130)."""
        from PyQt6.QtWidgets import QMessageBox
        if self._ctl.restore_needs_confirmation():
            box = QMessageBox(self)
            verif = self._ctl.target.is_verification()
            box.setWindowTitle(
                tr("Restore the chart this verification used?") if verif else
                tr("Restore the chart this profile run was measured with?"))
            # WHETHER THERE IS A MEASUREMENT AT ALL CHANGES WHAT IS TRUE HERE.
            #
            # Knut, #130 2026-08-01: he restored on a run whose `.ti3` had been
            # removed by a Save-Partial that read nothing, and was told "Your
            # measurements are not affected" about measurements that did not
            # exist — and "the one this run was measured with" about a run that
            # currently holds no measurement. *"the message is inaccurate …
            # the message above should ask if I want to restore the previously
            # used chart, although no measurement currently exist."*
            has_measurement = self._ctl.selection_has_measurement()
            if verif and has_measurement:
                body = tr(
                    "The verification chart currently in this run will be "
                    "replaced by the one this verification date was measured "
                    "with.\n\n"
                    "Your measurements are not affected — only the chart files "
                    "are replaced. The chart that is there now is not kept, so "
                    "if you still need it, cancel and save a copy first.")
            elif verif:
                body = tr(
                    "The verification chart currently in this run will be "
                    "replaced by the stored copy kept for this verification "
                    "date.\n\n"
                    "There is no measurement in this run at the moment, so "
                    "nothing is at risk — this simply puts the earlier chart "
                    "back. The chart that is there now is not kept, so if you "
                    "still need it, cancel and save a copy first.")
            elif has_measurement:
                body = tr(
                    "The chart currently in this profile run will be replaced "
                    "by the one this run was measured with.\n\n"
                    "Your measurements are not affected — only the chart files "
                    "are replaced. The chart that is there now is not kept, so "
                    "if you still need it, cancel and save a copy first.")
            else:
                body = tr(
                    "The chart currently in this profile run will be replaced "
                    "by the stored copy kept when a measurement was last "
                    "started here.\n\n"
                    "There is no measurement in this run at the moment, so "
                    "nothing is at risk — this simply puts that earlier chart "
                    "back. The chart that is there now is not kept, so if you "
                    "still need it, cancel and save a copy first.")
            box.setText(body)
            restore = box.addButton(tr("Restore Chart"),
                                    QMessageBox.ButtonRole.AcceptRole)
            box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
            box.exec()
            if box.clickedButton() is not restore:
                return
        if not self._confirm_restore_losing_pages():
            return
        result = self._ctl.restore_used_chart()
        if result is None:
            # Knut, #130: the button was enabled, he clicked it, and nothing
            # happened at all — no chart restored and no word about why. A
            # control that can silently do nothing is a fault whatever the
            # cause underneath, so it now says so instead of returning quietly.
            QMessageBox.information(
                self, tr("There is nothing to restore right now"),
                tr("ChromIQ could not work out which run's stored chart to put "
                   "back, so nothing has been changed.\n\n"
                   "This usually means the Profile run or Verification date "
                   "selection has moved on since the button was last enabled. "
                   "Pick the run you want in the bar and try again — your files "
                   "are exactly as they were."))
            return
        if not result.ok:
            QMessageBox.warning(
                self, tr("The chart could not be restored"),
                tr("Nothing was changed — the chart in this run is exactly as "
                   "it was.\n\nChromIQ could not read the stored copy: "
                   "{reason}\n\nThe stored chart is still in the run's "
                   "“chart” folder, so nothing is lost. If this keeps "
                   "happening, the folder may be read-only or on a drive that "
                   "is no longer connected — have a look at it in {manager}, "
                   "then try again.").format(
                       reason=result.error or tr("no reason given"),
                       manager=file_manager_name()))
            return
        if result.needs_regeneration:
            # The words live in workflow/verify_chart_snapshot so every branch
            # can be read back in a test, and so the sentence about reproducing
            # a shuffled chart (Knut, #130 2026-07-29) stays with the code that
            # knows whether this chart WAS shuffled.
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.NoIcon)
            box.setWindowTitle(tr("Chart restored — the pages need rebuilding"))
            box.setText(tr("Chart restored — the pages need rebuilding"))
            box.setInformativeText(result.regeneration_message)
            box.addButton(tr("OK"), QMessageBox.ButtonRole.AcceptRole)
            from ui.widgets import fit_message_box_buttons
            fit_message_box_buttons(box)
            box.exec()
        elif result.should_rebuild:
            # The pages are being redrawn from the chart's own recipe; the
            # finished build shows itself in the preview.
            log.info("restored chart: rebuilding its pages")

    @staticmethod
    def _duplicate_group_label(group: str) -> str:
        """How each copied group is named in the confirmation window.

        Written as a mapping of ``tr("…")`` calls rather than a dict of bare
        strings translated later: ``tr(some_variable)`` is invisible to
        ``scripts/i18n_extract.py``, so those six words would have sat in every
        catalogue's blind spot and shipped in English for ever.
        """
        return {
            "chart":       tr("Chart"),
            "measurement": tr("Measurement"),
            "profile":     tr("Profile"),
            "refinement":  tr("Refinement starting point"),
            "reports":     tr("Reports"),
            "exports":     tr("Export files"),
        }.get(group, group)

    @staticmethod
    def _pretty_size(n: int) -> str:
        """A size a person can judge at a glance. Knut asked to be shown what
        is being copied; bytes would not be showing him anything."""
        if n >= 1024 ** 3:
            return tr("{v:.1f} GB").format(v=n / 1024 ** 3)
        if n >= 1024 ** 2:
            return tr("{v:.1f} MB").format(v=n / 1024 ** 2)
        if n >= 1024:
            return tr("{v:.0f} KB").format(v=n / 1024)
        return tr("{v} bytes").format(v=n)

    def _duplicate_summary(self, plan) -> str:
        """The "what will be copied" list, built from what is really there."""
        from core.i18n import count_phrase
        lines = []
        for group, files, size in plan:
            label = self._duplicate_group_label(group)
            lines.append("    •  {name} — {count}, {size}".format(
                name=label,
                count=count_phrase(len(files), tr("1 file"), tr("{n} files")),
                size=self._pretty_size(size)))
        return "\n".join(lines)

    def request_duplicate(self) -> None:
        """Run the bar's Duplicate from somewhere else in the app (§6).

        The Build Profile warning offers "Duplicate the run and build there";
        it comes here rather than duplicating on its own, so there is one
        implementation, one confirmation window and one set of guards.
        """
        self._on_duplicate_clicked()

    def _on_duplicate_clicked(self) -> None:
        """Duplicate the selected run, after showing exactly what will be copied.

        Knut's point 7: *"Our principle throughout the app is that user shall be
        informed about what will happen and the consequences of an action, so a
        confirmation window is good. Must also allow Canceling."*
        """
        from PyQt6.QtWidgets import QMessageBox

        source = self._ctl.duplicate_source()
        proj = self._ctl.project_or_none()
        if source is None or proj is None:
            return                       # greyed; nothing to do
        plan = proj.duplicate_run_plan(source)
        total = sum(size for _g, _f, size in plan)

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        title = tr("Duplicate this run?")
        box.setWindowTitle(title)
        box.setText(title + "\n\n" + tr(
            "This makes a NEW run containing a copy of everything in {run} "
            "that describes your work so far — the chart, the measurement, and "
            "the profile built from it.\n\n"
            "The run you are duplicating is not changed in any way. Nothing is "
            "moved, and nothing is overwritten.\n\n"
            "What will be copied ({total} in total):\n\n{summary}\n\n"
            "Not copied: verification runs and their chart, so the new run is "
            "free to use a different one — and anything ChromIQ can rebuild by "
            "itself.\n\n"
            "Afterwards, ChromIQ switches to the new run and shows its chart "
            "in Create Chart.\n\n"
            "What each button does:\n\n"
            "•  Duplicate run — makes the copy now, and moves you to it.\n\n"
            "•  Cancel — nothing is copied and nothing is changed."
        ).format(run=self._run_phrase(source.id),
                 total=self._pretty_size(total),
                 summary=self._duplicate_summary(plan)))
        go = box.addButton(tr("Duplicate run"),
                           QMessageBox.ButtonRole.AcceptRole)
        cancel = box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(go)
        from ui.widgets import fit_message_box_buttons
        fit_message_box_buttons(box)
        box.exec()
        if box.clickedButton() is not go:
            return
        try:
            new_id = self._ctl.duplicate_run()
        except OSError as exc:
            QMessageBox.warning(
                self, tr("The run could not be duplicated"),
                tr("Nothing was copied and nothing was changed — the run you "
                   "selected is exactly as it was.\n\nReason: {reason}"
                   ).format(reason=str(exc)))
            return
        if new_id:
            self.run_duplicated.emit(new_id)

    def _run_phrase(self, run_id: str) -> str:
        """"run 3" for a run id, for use inside a sentence.

        NOT ``_run_label`` — that name is already the bar's own QLabel widget.
        """
        import re as _re
        m = _re.match(r"run(\d+)$", run_id or "")
        return tr("run {n}").format(n=m.group(1)) if m else str(run_id)

    def _on_delete_clicked(self) -> None:
        """Delete the selected run, or the selected run's verification files.

        Every branch asks first and names exactly what will go — see
        :mod:`core.run_delete`, which holds the rules and the words so both can
        be tested without a window.
        """
        from PyQt6.QtWidgets import QMessageBox

        import core.run_delete as rd
        plan = self._ctl.delete_plan()
        if isinstance(plan, str):
            return                       # greyed; nothing to do

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle(rd.title_for(plan))
        box.setText(rd.title_for(plan) + "\n\n" + rd.message_for(plan))
        if plan.kind == rd.KIND_LAST_RUN:
            empty_btn = box.addButton(
                tr("Empty run {n}").format(n=rd.run_number(plan.run_id)),
                QMessageBox.ButtonRole.DestructiveRole)
            project_btn = box.addButton(tr("Delete the whole project"),
                                        QMessageBox.ButtonRole.DestructiveRole)
            go_btn = None
        else:
            empty_btn = project_btn = None
            go_btn = box.addButton(rd.confirm_label(plan),
                                   QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel)     # never the destructive one
        # "Delete run 4 permanently" is a long label, and a button sizes itself
        # before the font swap widens it — fit every one of them (Knut, #130
        # 2026-07-28).
        from ui.widgets import fit_message_box_buttons
        fit_message_box_buttons(box)
        box.exec()
        clicked = box.clickedButton()
        if clicked is cancel or clicked is None:
            return

        try:
            if clicked is empty_btn:
                rd.empty_run(self._ctl.project_or_none(), plan.run_id)
            elif clicked is project_btn:
                self._delete_whole_project(plan)
                return
            elif plan.kind == rd.KIND_RUN:
                landed = rd.delete_run(self._ctl.project_or_none(), plan)
                # The manifest now says the last run is current, but the BAR
                # reads its selection from the target — which still named the
                # run that has just gone, so the dropdown kept showing a stale
                # choice and never jumped (Knut, #130 2026-07-28: "the Profile
                # run selection did not jump to last run in the list").
                self._ctl.set_profile_run(landed)
                self._ctl.set_verification_id("")
            else:
                rd.delete_verification(plan)
        except rd.DeleteFailed as exc:
            QMessageBox.warning(
                self, tr("Could not delete everything"),
                tr("ChromIQ deleted what it could, but some files could not be "
                   "removed:\n\n{paths}\n\nThis usually means a file is open in "
                   "another program, or the folder is on a disk that is "
                   "currently read-only. Close anything that might be using "
                   "these files and try again.\n\nNothing else was changed — "
                   "the run numbering has been left exactly as it was, so no "
                   "run has moved.").format(paths="\n".join(exc.paths)))
        self._after_delete()

    def _delete_whole_project(self, plan) -> None:
        """The second way out of the last-run case: remove the project folder
        and return to the state a freshly started ChromIQ has (Knut's D1)."""
        from PyQt6.QtWidgets import QMessageBox
        proj = self._ctl.project_or_none()
        root = getattr(proj, "root", None)
        if root is None:
            return
        # TO THE TRASH, NOT DESTROYED (Basti, 2026-08-28).
        #
        # `shutil.rmtree` removes everything it can reach and raises only at the
        # end, so ONE unwritable sub-folder was enough to leave the project half
        # gone behind a window saying nothing had happened. Measured on screen:
        # 10 of 29 files destroyed, `project.json` among them — so the 19
        # survivors could no longer be opened by ChromIQ at all — while the
        # person read "Nothing was changed." and reasonably concluded their
        # project was still there.
        #
        # A Trash move is a rename, so the unwritable child never gets the
        # chance to defeat it, and when there is nowhere to put the files Qt
        # changes nothing at all — which is what finally makes that sentence
        # true.
        from core.trash import move_to_trash
        res = move_to_trash(root)
        if not res.ok:
            QMessageBox.warning(
                self, tr("Could not delete the project"),
                res.reason or tr("Nothing was changed. Every file is still "
                                 "exactly where it was."))
            return
        log.info("Moved project folder %s to the Trash", root)
        self.project_deleted.emit()

    def _after_delete(self) -> None:
        """Rebuild the dropdowns from what is now on disk and tell the tabs."""
        try:
            self.refresh()
        except Exception:      # noqa: BLE001
            log.warning("Could not refresh the bar after a delete",
                        exc_info=True)
        self._ctl.notify_changed()

    #: Space above and below the tallest control in the selection row, on top
    #: of the control itself. **Zero**, and measured rather than chosen: with
    #: the location line shown — the state Basti judged as right — the row is
    #: exactly as tall as the tallest mark in it (34 px, the icon buttons), and
    #: the rail's own padding provides all the breathing room there is.
    #:
    #: Six was tried first, from a run of the app that had not been given
    #: main.py's fonts and Fusion style. Unstyled, the same row measures 40, and
    #: building the fix on that number reproduced the very gap it was meant to
    #: remove (Basti: *"with location being edited on the distance on top is
    #: still smaller than with it off"*). Measure the styled app.
    ROW_BREATHING = 0

    def _row_content_height(self) -> int:
        """How tall the selection row needs to be for the controls in it.

        With the location line shown, the column has two things to fit and the
        row ends up at exactly this height. With the line hidden the row is the
        only thing in the column, so it takes all of the bar and centres its
        controls in the slack — which pushes them 5 px further from the masthead
        than they sit with the line on. Basti, beta.142: *"when location being
        edited is on then the distance of the elements in the bar to the
        masthead above it is smaller than with location being edited is off. i
        want this smaller distance as well when location being edited is off and
        the same distance then at the bottom as well."*

        So the row is pinned to what it needs, and the two states differ only by
        the line itself.
        """
        # Only the controls that draw the row's visual band are asked. A label
        # in a QHBoxLayout is given the whole row height, so including labels
        # would measure the slack this method exists to remove — and the hint
        # sentence, which is a wrapped label, reports a height for a width it
        # has not got.
        band = (self._run_combo, self._type_combo, self._verify_combo,
                self._restore_btn, self._duplicate_btn, self._delete_btn)
        tallest = 0
        # The hint is a wrapped label in the same row, and its sizeHint is
        # computed for some other width — 48 px (three lines) where the text
        # actually needs 16 at the width it is given. Left to inflate the row,
        # it puts the controls back in the middle of slack, which is the
        # complaint this method exists to answer (Basti, beta.142, twice). So
        # the row is made as tall as the hint REALLY needs and no taller.
        hint_below = (getattr(self, "_hint_wanted", False)
                      and self._hint.isVisible()
                      and not getattr(self, "_hint_beside", True))
        if getattr(self, "_hint_wanted", False) and not hint_below:
            # Measured at the width the sentence is ABOUT to get, not at the
            # width the previous layout left on it — a stale narrow width
            # reports three lines where two are needed and inflates the row.
            free = self._free_for_hint()
            if free > 0:
                tallest = max(tallest, self._hint.heightForWidth(free))
        for control in band:
            if control is None or not control.isVisibleTo(self):
                continue
            # Its real height, not its hint: these controls are pinned — the
            # marks by setFixedSize, the boxes by #compact_input's max-height —
            # and a QToolButton's hint is ten pixels above what it is drawn at.
            tallest = max(tallest, control.height() or control.sizeHint().height())
        if not tallest:
            return 0
        if hint_below:
            # BELOW the row its height ADDS to the row's; it does not compete
            # with it. Taking the max instead left the row 16 px tall with
            # 34 px children, so the sentence was laid out INSIDE the band and
            # painted straight through the Restore, Duplicate and Delete
            # icons — at 30 of 53 window widths, measured.
            width = getattr(self, "_avail", 0) or self.width() or self._hint.width()
            return (tallest + self.ROW_BREATHING + self.layout().spacing()
                    + self._hint.heightForWidth(max(1, width)))
        return tallest + self.ROW_BREATHING

    def showEvent(self, event) -> None:        # noqa: N802
        """Re-measure the boxes the first time the bar is shown.

        The widths are first worked out in ``__init__``, where the widget has
        no stylesheet yet — one reaches a widget at polish, and the app's is
        applied after this window is built. The re-fit did happen, on the
        StyleChange that followed, but that lands during the first pass of the
        event loop, which is to say AFTER the first paint: the Profile run box
        went 147 -> 176 px on screen and the six controls to its right slid
        29 px sideways with it (Basti, beta.142: *"directly after loading it
        seems that the run type combobox is adjusting its width a bit. looks
        like a jump"* — it was its neighbour pushing it).

        ``showEvent`` runs after polish and before the first paint, so the
        numbers are right the first time they are drawn.
        """
        super().showEvent(event)
        if not getattr(self, "_fitted_on_show", False):
            self._fitted_on_show = True
            self.ensurePolished()
            self._fit_widths(getattr(self, "_last_labels", ()))
            self._pin_row_when_alone()

    def resizeEvent(self, event) -> None:      # noqa: N802
        """Re-pin when the width changes — the hint wraps differently, so the
        height it needs changes with it."""
        super().resizeEvent(event)
        if event.oldSize().width() != event.size().width():
            self._pin_row_when_alone()

    def _apply_hint_text(self) -> None:
        """Say what can be done from here, which depends on the preference.

        With calibration switched on, "Run type" is live even before a project
        exists (Knut's option 2), so the hint has to say so — a sentence that
        tells you to go and make a chart first, beside a dropdown you can use
        right now, is worse than no sentence at all.
        """
        if self._ctl.calibration_allowed:
            # Kept to the length of the sentence beside it, which has never
            # clipped: the hint wraps against the version text in a row whose
            # width it does not control, and a longer sentence is how you find
            # that out (Basti, beta.142).
            self._hint.setText(tr(
                "Load a project, or name one in Create Chart and generate a "
                "chart, then choose a run. Calibration needs no run."))
        else:
            self._hint.setText(tr(
                "Load a profile project, or specify a profile project name and "
                "create your first chart, then you may choose a profile run."))

    def _pin_row_when_alone(self) -> None:
        """Stop the selection row taking the whole bar when it is alone in it.

        With the location line shown, the column has two things to fit and the
        row settles at exactly the height its controls need. With the line
        hidden the row is the only item, takes the whole bar, and centres its
        controls in the slack — which is why the boxes sat further from the
        masthead with the line off than with it on, and why the space under
        them did not match the space over them.
        """
        # `_row_content_height` already accounts for the hint when it is shown,
        # so the pin no longer has to stand down for it — standing down was
        # what let the hint's inflated sizeHint push the controls apart again.
        needed = self._row_content_height()
        # The hint's width is only known once it has been laid out. Until then
        # there is nothing trustworthy to pin to, so this pass is skipped and
        # the next one — a resize, or the refresh that follows — does it.
        if getattr(self, "_hint_wanted", False) and self._hint.width() <= 0:
            return
        if self._location.isVisible() or needed <= 0:
            self.setMaximumHeight(_QWIDGETSIZE_MAX)
        else:
            self.setMaximumHeight(needed)
        self.updateGeometry()

    def _settings_calibration_allowed(self) -> bool:
        """Whether Preferences offers the Calibration run type.

        Read here as well as being fanned out by MainWindow, because the
        fan-out is deferred to the first pass of the event loop — which is
        after the first paint. The Profile run box is measured against
        "Project calibration" when this is on, so learning it late made the box
        grow from 147 to 176 px on screen and shoved the six controls to its
        right 29 px sideways (Basti, beta.142). Defaults to OFF, which is the
        preference's own default.
        """
        try:
            settings = getattr(self._ctl._fm, "_settings", None)
            if settings is None:
                return False
            return bool(settings.get("calibration_mode", False))
        except Exception:      # noqa: BLE001 — never break the bar over a setting
            return False

    def _settings_show_location(self) -> bool:
        """Whether Preferences says to show the "Location being edited" line.

        Reached through the controller's file manager: the bar has no settings
        of its own, and giving it one would mean changing every place that
        builds a bar. Defaults to showing it — the line is what answers "where
        are my files?", so a lookup that fails must not silently hide it.
        """
        try:
            settings = getattr(self._ctl._fm, "_settings", None)
            if settings is None:
                return True
            return bool(settings.get("show_location_being_edited", True))
        except Exception:      # noqa: BLE001 — never break the bar over a setting
            return True

    def _update_location(self) -> None:
        """Refresh the "Location being edited" line for the current selection
        (#130, Knut). Hidden entirely until a profile project is open, so an
        empty app never shows a half-formed path."""
        where = self._ctl.location_being_edited()
        # Turned off in Preferences → General, the line goes entirely — Knut
        # settled the polarity (#130, 2026-07-31): *"I prefer 'Show the location
        # being edited', enabled shows."* Read here rather than cached, so the
        # bar follows the preference the moment it is changed.
        show = bool(self._settings_show_location())
        self._location.setVisible(bool(where) and show)
        self._pin_row_when_alone()
        # Clear the text too, so a hidden label can never surface a stale path
        # if something shows it again later.
        self._location_full = (
            tr("Location being edited: {path}").format(path=where) if where else "")
        self._apply_location_text()

    def _apply_location_text(self) -> None:
        """Show the path, shortened in the middle if it does not fit."""
        full = getattr(self, "_location_full", "")
        if not full:
            self._location.setText("")
            return
        # Measured against the bar, which the label spans: the label's own
        # width is meaningless until the layout has run, and eliding against a
        # stale value shortens a path that would have fitted.
        room = self.width()
        fm = self._location.fontMetrics()
        if room > 40 and fm.horizontalAdvance(full) > room:
            from PyQt6.QtCore import Qt as _Qt
            self._location.setText(fm.elidedText(full, _Qt.TextElideMode.ElideMiddle,
                                                 room))
        else:
            self._location.setText(full)

    def resizeEvent(self, event) -> None:      # noqa: N802
        super().resizeEvent(event)
        self._apply_location_text()

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
            # Two different reasons to go quiet, and they read differently:
            # the tab-lock says "this selection isn't used here", measuring
            # says "not right now". Either disables; measuring explains.
            measuring = bool(self._ctl.is_measuring())
            building = bool(getattr(self, "_build_running", False))
            tab_locked = getattr(self, "_locked", False)
            locked = tab_locked or measuring or building
            # Restore and Delete already explain the measurement lock through
            # their own state(); the boxes and Duplicate had nothing, so they
            # get the same words rather than a second phrasing of them.
            # Three reasons, three sentences. "Not while a measurement is
            # running" is simply false during a chart build, and it is the
            # sentence the person would have read.
            if measuring:
                note = self._measuring_note()
            elif building:
                note = self._building_note()
            else:
                note = self._lock_note()
            for w in (self._run_label, self._run_combo,
                      self._verify_label, self._verify_combo):
                w.setEnabled(has_project and not locked)
            # …but "Run type" stays live with no project open, so a calibration
            # can be started from a clean app (Knut, #130 2026-08-05, ruling on
            # option 2). Calibration is the first step of the work and the one
            # run type that does not use the Profile run box — requiring a
            # profiling chart first in order to reach it had the order of the
            # job backwards. The project is created at Generate from the name
            # field, exactly as a first profiling chart creates it.
            type_live = ((has_project or self._ctl.calibration_allowed)
                         and not locked)
            self._type_label.setEnabled(type_live)
            self._type_combo.setEnabled(type_live)
            # A disabled widget still shows its tooltip, so the explanation is
            # reachable exactly where the user tries to click. The box's own
            # tooltip is put back the moment the bar is live again.
            for w in (self._run_combo, self._type_combo, self._verify_combo):
                if not hasattr(w, "_cq_tip"):
                    w._cq_tip = w.toolTip()
                w.setToolTip(note if locked else w._cq_tip)
            # …and the run box goes quiet while Calibration is selected: there
            # is exactly one calibration, so there is nothing to choose. AFTER
            # the loop above, which would otherwise put the general tooltip
            # straight back over this one.
            if self._ctl.target.is_calibration():
                self._run_combo.setEnabled(False)
                if not locked:
                    self._run_combo.setToolTip(self._run_combo_cal_tip)
            self._hint_wanted = not has_project
            self._apply_hint_text()
            self._hint.setVisible(self._hint_wanted)
            # Pin AGAIN, now that the hint's state is actually known. The first
            # attempt happens inside _update_location(), which runs at the TOP
            # of this method — 46 lines before `_hint_wanted` is worked out —
            # so it can only ever act on the previous refresh's answer. That
            # one-beat lag is visible: Basti, beta.142, *"when loading the app
            # now something in the bar changes its size. first it seems to look
            # good and then it gets bigger."* Idempotent, so running it twice
            # costs nothing and is far cheaper than reordering a method this
            # much of the bar depends on.
            self._pin_row_when_alone()
            self._place_hint()
            # Run dropdown: "Run N (overwrite)" per existing run + "New run".
            self._run_combo.clear()
            is_cal = t.is_calibration()
            if is_cal:
                # ONE CALIBRATION PER PROJECT, so there is no run to pick
                # (#137 A1). The box stays visible and shows what will be
                # worked on, rather than disappearing and moving everything
                # else along the bar.
                #
                # t.profile_run is deliberately NOT written back from here:
                # the user's run selection has to survive the round trip to
                # Calibration and back (#137 R3).
                self._run_combo.addItem(tr("Project calibration"), _CAL)
                self._run_combo.setCurrentIndex(0)
            else:
                for rid in self._ctl.run_ids():
                    self._run_combo.addItem(
                        tr("{run} (overwrite)").format(run=self._pretty_run(rid)), rid)
                self._run_combo.addItem(tr("New run"), _NEW)
                self._select_data(self._run_combo, t.profile_run or _NEW)

            # Run type. The third value is offered only while the preference is
            # on; with it off this loop rebuilds the two-value box the app has
            # always had, so nothing about that case changes (#137 E1).
            self._rebuild_type_combo()
            self._select_data(self._type_combo, t.run_type)

            # Verification dropdown (only for verification + when allowed here).
            is_verif = t.is_verification()
            show = self._show_verification and is_verif
            self._verify_label.setVisible(show)
            self._verify_combo.setVisible(show)
            # The date box belongs to Verification, but the chart a run was
            # measured with can be restored for EITHER run type (#130, Knut
            # 2026-07-27) — so the button follows the bar, not the date box.
            show_restore = self._show_verification
            self._restore_btn.setVisible(show_restore)
            self._restore_tip.setVisible(show_restore)
            if show_restore:
                enabled, tip = self._ctl.restore_state()
                self._restore_btn.setEnabled(enabled and not locked)
                self._restore_btn.setToolTip(self._icon_tip(
                    self._restore_btn,
                    self._lock_note() if tab_locked else tip))
            # Duplicate follows the same rule as Restore and Delete: shown
            # wherever the bar carries the Verification box, greyed with its
            # own reason. `locked` is a measurement in progress — Knut's point
            # 4: not while one is running.
            self._duplicate_btn.setVisible(show_restore)
            self._duplicate_tip.setVisible(show_restore)
            if show_restore:
                u_enabled, u_tip = self._ctl.duplicate_state()
                self._duplicate_btn.setEnabled(u_enabled and not locked)
                self._duplicate_btn.setToolTip(self._icon_tip(
                    self._duplicate_btn,
                    note if locked else u_tip))
            # Delete follows the same rule as Restore: shown wherever the bar
            # carries the Verification box, greyed with its own reason.
            self._delete_btn.setVisible(show_restore)
            self._delete_tip.setVisible(show_restore)
            if show_restore:
                d_enabled, d_tip = self._ctl.delete_state()
                self._delete_btn.setEnabled(d_enabled and not locked)
                self._delete_btn.setToolTip(self._icon_tip(
                    self._delete_btn,
                    self._lock_note() if tab_locked else d_tip))
            every_label: list[str] = []
            if show:
                self._verify_combo.clear()
                run_id = t.profile_run
                for vid in self._ctl.verification_ids(run_id):
                    label = tr("Overwrite {when}").format(
                        when=self._pretty_date(vid))
                    # Both forms this date could show, so the box is sized for
                    # the wider one whichever it currently is.
                    every_label += [label, tr("{when} — no measurement yet").format(
                        when=self._pretty_date(vid))]
                    if not self._ctl.verification_has_measurement(run_id, vid):
                        # Created when a measurement started, but never finished
                        # — say so, so an empty date is not mistaken for a result
                        # (#130, Knut). Its chart can still be restored.
                        label = tr("{when} — no measurement yet").format(
                            when=self._pretty_date(vid))
                    self._verify_combo.addItem(label, vid)
                self._verify_combo.addItem(tr("New verification"), _NEW)
                every_label.append(tr("New verification"))
                self._select_data(self._verify_combo, t.verification_id or _NEW)
            self._fit_widths(every_label)
        finally:
            self._syncing = False

    # ---- user edits → controller -----------------------------------------
    def _on_run_changed(self, _i: int) -> None:
        if self._syncing:
            return
        data = self._run_combo.currentData()
        if data == _CAL:
            # THE ONE THING THAT MUST NEVER HAPPEN (#137 R3): writing the
            # calibration sentinel into profile_run would destroy the run the
            # user had selected, and they would come back from Calibration to
            # the wrong one. The box is disabled while Calibration is selected,
            # so this is belt and braces — but it is the failure that would be
            # silent and would cost work, so it is guarded rather than assumed.
            return
        self._ctl.set_profile_run("" if data == _NEW else str(data))

    def _rebuild_type_combo(self) -> None:
        """Repopulate "Run type", with Calibration only while it is allowed.

        Rebuilt rather than shown/hidden because a QComboBox cannot hide one
        item; and rebuilt in place (signals blocked by the caller's _syncing
        guard) so no spurious selection change escapes to the tabs.
        """
        # Calibration first, because it comes first in the work: you calibrate
        # the printer, then you profile it, then you verify the profile. The
        # list reads as the order of the job rather than as the order the
        # features were built (Basti, beta.142). It is not the default — that
        # is still Profiling, set by the controller, because most sessions are
        # profiling sessions and a calibration is an occasional thing.
        want = []
        if self._ctl.calibration_allowed:
            want.append((tr("Calibration"), RUN_TYPE_CALIBRATION))
        want += [(tr("Profiling"), RUN_TYPE_PROFILING),
                 (tr("Verification"), RUN_TYPE_VERIFICATION)]
        have = [(self._type_combo.itemText(i), self._type_combo.itemData(i))
                for i in range(self._type_combo.count())]
        if have == want:
            return
        self._type_combo.clear()
        for label, data in want:
            self._type_combo.addItem(label, data)
        # The items are new objects, so the greyed state has to be put back.
        self._apply_verification_item_state()

    def set_calibration_allowed(self, allowed: bool) -> None:
        """Follow Preferences → Calibration options (#137).

        Called by MainWindow's existing fan-out, so the bar changes at exactly
        the same moment the tabs do.
        """
        self._ctl.set_calibration_allowed(allowed)
        self.refresh()

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
        # One formatter for the dropdown and for every message that names a
        # verification date, so they can never drift apart.
        from core.measurement_target import pretty_verification_date
        return pretty_verification_date(vid)
