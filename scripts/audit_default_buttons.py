#!/usr/bin/env python3
"""K44 audit: in every window, which button is FILLED and which one Return
presses (Knut, #182 5833983335: one standard for every window and pop-up).

    CHROMIQ_SETTINGS_FILE=... CHROMIQ_PRESETS_DIR=... \\
        python scripts/audit_default_buttons.py <output-root> [light,dark,neutral]

Builds each window the way the app does (Preferences, every Tools window,
the gear window, Patch distribution, a report question), shows it with the
app's own event filters installed (so the default is settled and frozen as in
the app), and prints one JSON line: per appearance, per window, every visible
push button with its text, isDefault, autoDefault, objectName, the painted
fill and whether that fill is the ACCENT (a filled button).

A button is "filled" when its fill is far from the ordinary button fill and
from the window ground, and is an accent: saturated in Light and Dark, the
near-black ACTION in Neutral.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CHROMIQ_TREE") or Path(__file__).resolve().parents[1])
sys.path.insert(0, str(ROOT))


def main() -> int:
    out_root = sys.argv[1]
    modes = (sys.argv[2].split(",") if len(sys.argv) > 2
             else ["light", "dark", "neutral"])
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QColor
    try:
        from ui.default_button import is_destructive as _is_destructive
    except ImportError:                 # a tree before B8-1181
        def _is_destructive(_b):
            return False
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication, QMessageBox, QPushButton
    app = QApplication.instance() or QApplication([])
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from ui.widgets import CompositeAppFilter
    filt = CompositeAppFilter(app)
    app.installEventFilter(filt)
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui import light_styles, neutral_styles, styles
    from ui.dialogs.settings_dialog import SettingsDialog
    from ui.dialogs.tools_dialogs import TOOL_DIALOG_KEYS, build_tool_dialog
    from ui.main_window import MainWindow
    from ui.theme import apply_appearance

    settings = AppSettings()
    settings.set("custom_output_path", out_root)
    plain = {"light": light_styles.LM_BG_WIDGET, "dark": styles.NEUTRAL_BTN,
             "neutral": neutral_styles.NM_BG_WIDGET}

    def dist(a: QColor, b: QColor) -> int:
        return max(abs(a.red() - b.red()), abs(a.green() - b.green()),
                   abs(a.blue() - b.blue()))

    def filled(b, ground, mode) -> "tuple[bool, str]":
        img = b.grab().toImage()
        fill = QColor(img.pixel(min(6, img.width() - 1), img.height() // 2))
        _h, s, v, _a = fill.getHsv()
        far = (dist(fill, QColor(plain[mode])) > 24
               and dist(fill, ground) > 24)
        # Neutral fills in near-black ACTION; Light's fallback, since
        # 2026-09-26, is near-black too (Restore Factory Defaults' look).
        accent = ((v < 40) if mode == "neutral"
                  else (s > 90 and v > 90) or (mode == "light" and v < 40)
                  or (mode == "dark" and v > 225 and s < 25))
        if not b.isEnabled() or b.isCheckable():
            # A greyed button is no action, and a checked toggle's fill says
            # "on", not "Return": neither can be a filled action.
            far = False
        return bool(far and accent), fill.name()

    def survey(win, mode):
        ground = win.palette().window().color()
        rows = []
        for b in win.findChildren(QPushButton):
            if not b.isVisibleTo(win) or b.window() is not win:
                continue
            if b.width() < 12 or b.height() < 8:
                continue
            is_filled, fill = filled(b, ground, mode)
            row = {"text": b.text().replace("&", ""),
                   "name": b.objectName(), "default": b.isDefault(),
                   "auto": b.autoDefault(), "enabled": b.isEnabled(),
                   "fill": fill, "filled": is_filled,
                   "safe": bool(b.property("chromiq_safe_default")),
                   # B8-1181: the button the keyboard focus is on, as the
                   # window holds it (active or not): Space presses it.
                   "focus": win.focusWidget() is b}
            if _is_destructive(b):
                # On screen macOS activates a window AFTER B8-1042's pass
                # and hands the focus to the first button in the chain;
                # offscreen never does. So do what activation does, and see
                # whether a destructive button keeps that focus (Space
                # would press it).
                row["destructive"] = True
                win.activateWindow()
                b.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
                QTest.qWait(80)
                row["keeps_activation_focus"] = win.focusWidget() is b
                b.clearFocus()
            if not b.isEnabled():
                # Most tools grey their main action until the inputs are
                # chosen: enable it, as choosing them would, and look again
                # (every greyed button, so a coloured one that is not the
                # default, like the patch set editor's Apply / Save, is seen).
                b.setEnabled(True)
                QTest.qWait(30)
                row["filled_when_enabled"], row["fill_when_enabled"] = \
                    filled(b, ground, mode)
                row["default_when_enabled"] = b.isDefault()
                b.setEnabled(False)
            rows.append(row)
        return rows

    result = {}
    for mode in modes:
        apply_appearance(app, None, mode)
        settings.set("appearance", mode)
        win = MainWindow(settings)
        apply_appearance(app, win, mode)
        win.resize(1500, 1000)
        win.show()
        QTest.qWait(300)
        windows = {}

        def take(name, dlg, size=None):
            if size:
                dlg.resize(*size)
            dlg.show()
            QTest.qWait(260)            # the focus clears and the freeze
            windows[name] = survey(dlg, mode)
            dlg.close()
            dlg.deleteLater()
            QTest.qWait(20)

        take("Preferences", SettingsDialog(settings, win))
        runner = ArgyllRunner(settings)
        for key in TOOL_DIALOG_KEYS:
            dlg = build_tool_dialog(key, runner, settings, win)
            if dlg is not None:
                take("tool/" + key, dlg)
        tab = win._tab_chart
        from core.curated_presets import paper_filter_on, shown_keys
        from ui.dialogs.builtin_presets_shown_dialog import (
            BuiltinPresetsShownDialog)
        from ui.tabs.tab_chart import BUILTIN_PRESET_KEYS, builtin_preset_facts
        take("gear window", BuiltinPresetsShownDialog(
            tab._curated_dialog_groups(),
            shown_keys(settings, BUILTIN_PRESET_KEYS), tab,
            facts=builtin_preset_facts(), folder=Path(out_root),
            paper_filter=paper_filter_on(settings)))
        # The report question, built as the report window builds it.
        from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
        rep = MeasurementReportDialog(settings, win)
        rep.show()
        QTest.qWait(200)
        box = QMessageBox(rep)
        new = box.addButton("Create New", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Update", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(new)
        take("report question (as built)", box)
        # A destructive question keeps Cancel as its default (M-REPORT-DELETE
        # is built this way): Return presses Cancel, and Cancel is not drawn
        # as the main action.
        dele = QMessageBox(rep)
        dele.setStandardButtons(QMessageBox.StandardButton.Ok
                                | QMessageBox.StandardButton.Cancel)
        dele.button(QMessageBox.StandardButton.Ok).setText("Delete")
        dele.setDefaultButton(QMessageBox.StandardButton.Cancel)
        take("destructive question (Cancel default)", dele)
        # A window that already fills its main action (#primary) and keeps a
        # different default (Profile Built: Install… filled, Done default).
        from PyQt6.QtWidgets import QDialog, QHBoxLayout
        mixed = QDialog(win)
        lay = QHBoxLayout(mixed)
        inst = QPushButton("Install", mixed)
        inst.setObjectName("primary")
        done = QPushButton("Done", mixed)
        done.setDefault(True)
        lay.addWidget(inst)
        lay.addWidget(done)
        take("#primary beside another default", mixed)

        # Basti, 2026-09-25: the Build Profile and Check & Refine result
        # windows that colour two (or more) buttons STAY as they are. Built by
        # the tabs' own methods (each exec()s), surveyed while open, closed.
        from PyQt6.QtCore import QTimer

        def take_modal(name, call):
            def grab():
                m = QApplication.activeModalWidget()
                if m is None:
                    windows[name] = [{"error": "no window"}]
                    return
                QTest.qWait(260)
                windows[name] = survey(m, mode)
                m.reject()
            QTimer.singleShot(300, grab)
            try:
                call()
            except Exception as exc:            # noqa: BLE001
                windows[name] = [{"error": repr(exc)}]
            QTest.qWait(30)

        prof = win._tab_profile
        icc = Path(out_root) / "demo.icc"
        take_modal("Profile Built", lambda: prof._show_build_result_dialog(icc, []))
        take_modal("Calibration Applied",
                   lambda: prof._show_applycal_result_dialog(icc))
        take_modal("Calibration File Created",
                   lambda: prof._show_printcal_result_dialog(
                       Path(out_root) / "demo.cal"))
        chk = win._tab_check
        chk._icc_path = icc
        chk._ti3_path = Path(out_root) / "demo.ti3"
        from types import SimpleNamespace
        res = SimpleNamespace(avg_de=1.2, peak_de=4.0, patch_errors=[])
        # A DESTRUCTIVE action is never drawn filled, even as the default
        # (beta 43, 2026-09-25). The real windows, rejected unanswered.
        chart = win._tab_chart
        chart._is_deletable_preset = lambda _i: True     # this instance only
        take_modal("Delete Preset (Create Chart)", chart._on_preset_delete)
        take_modal("Delete Preset (Measure)",
                   win._tab_measure._on_m_preset_delete)
        take_modal("Preset already exists",
                   lambda: chart._confirm_overwrite_preset("Mine"))
        take_modal("New chart over a run's work",
                   lambda: chart._ask_chart_question(
                       "Replace?", "Body", "Generate the new chart"))
        take_modal("Delete Preset (Build Profile)",
                   win._tab_profile._on_m_preset_delete)
        take_modal("Delete Preset (Check & Refine)",
                   win._tab_check._on_m_preset_delete)
        # Knut, #182 5835722977 (beta 43): "I think Cancel as the default is
        # the safest." Every destructive question on B8-1155's list, built by
        # its own method; only what the method reads first is stood in for,
        # on this instance, and put back.
        bar = win._target_bar
        real_ctl = bar._ctl
        bar._ctl = SimpleNamespace(
            restore_needs_confirmation=lambda: True,
            target=SimpleNamespace(is_verification=lambda: False),
            selection_has_measurement=lambda: True)
        try:
            take_modal("Restore Chart", bar._on_restore_clicked)
        finally:
            bar._ctl = real_ctl
        ti2 = build_tool_dialog("ti2_relayout", runner, settings, win)
        take_modal("Overwrite patch set", ti2._prompt_apply_action)
        ti2.close()
        ti2.deleteLater()
        meas = win._tab_measure
        meas._measurement_at_risk = lambda: Path(out_root) / "held.ti3"
        meas._read_builds_on_existing = lambda: False
        meas._replace_warning_scope = lambda: None
        take_modal("Measure anyway", meas._confirm_replacing_measurement)
        import workflow.profile_rebuild_guard as guard
        real_assess = guard.assess
        guard.assess = lambda run, silenced=False: SimpleNamespace(
            needed=True, can_duplicate=False, duplicate_blocked_by=["a chart"],
            dated=2, oldest="2026-09-01")
        prof._run_being_built_into = lambda: None
        try:
            take_modal("Build here anyway",
                       prof._confirm_rebuild_over_verifications)
        finally:
            guard.assess = real_assess
        pr = win._tab_print
        real_module = pr._module
        pr._module = SimpleNamespace(get_stuck_jobs=lambda _p: ["job-1"],
                                     cancel_all_jobs=lambda _p: 0)
        try:
            take_modal("Clear & Print", lambda: pr._handle_stuck_jobs("Printer"))
        finally:
            pr._module = real_module
        prefs = SettingsDialog(settings, win)
        take_modal("Profile engine opt-in",
                   lambda: prefs._on_profile_engine_clicked(True))
        prefs.deleteLater()
        import ui.dialogs.translation_dialog as tdmod
        from ui.dialogs.translation_dialog import TranslationDialog
        tdlg = TranslationDialog(settings, win)
        tdlg._resolve_target = lambda: ("fr", "French")
        real = (tdmod.open_file_dialog, tdmod.rt.read_rows, tdmod.rt.apply_rows)
        tdmod.open_file_dialog = lambda *a, **k: str(Path(out_root) / "de.csv")
        tdmod.rt.read_rows = lambda _p: []
        tdmod.rt.apply_rows = lambda _c, _r: (
            {}, {}, SimpleNamespace(code_mismatch="de"))
        try:
            take_modal("Different language", tdlg._on_import)
        finally:
            (tdmod.open_file_dialog, tdmod.rt.read_rows,
             tdmod.rt.apply_rows) = real
        tdlg.deleteLater()
        take_modal("Profile Quality Assessment (Good, refine offered)",
                   lambda: chk._show_result_dialog(
                       res, [("A", 1.0)], [("A", 3.0)],
                       Path(out_root) / "strips.txt", False))
        from ui.dialogs.thresholds_dialog import ThresholdsDialog
        try:
            take("Report limits", ThresholdsDialog(settings, rep))
        except TypeError as exc:
            windows["Report limits"] = [{"error": str(exc)}]
        rep.close()
        rep.deleteLater()
        win.close()
        win.deleteLater()
        QTest.qWait(50)
        result[mode] = windows
    print("RESULT " + json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
