#!/usr/bin/env python3
"""Adversary round 27b: the "Which presets can be verified?" button, ON SCREEN.

Basti, on the shipped beta 22:

    *"the which presets can be verified button in create chart tab under the
    presets combobox is very big. at least the hight could be reduced. maybe
    you can find an even better solution / placement so it takes up less
    space"*

    *"clicking the button takes quite long until the window opens."*

and Knut, the same day, that the button belongs to a **verification run only**.

Three commits answer those. This driver does not take their word for any of it.
It builds the REAL `MainWindow` the way `main.py` does — Fusion through
`WinButtonLayoutStyle`, the composite application filter that gives every
button its Menlo/uppercase font — opens a real project, and then:

1. photographs the presets group with Run type = **Profiling** and again with
   Run type = **Verification**, and records what is visible in each;
2. measures the button's HEIGHT against beta 22's, by putting beta 22's button
   (the same label, no stylesheet) into the same row and letting the same
   layout and the same font filter size it;
3. puts a CLOCK around the button press — cold cache and warm cache — instead
   of an impression, and around the idle warming itself;
4. STRESSES the warming, because it is a timer on a widget and CLAUDE.md
   records what a badly-held slot does to PyQt6: opens the window while the
   warming is half done, opens it twice in a row, changes run type and target
   mid-warm, and closes the tab mid-warm. Every step is flushed to
   `progress.log` before it runs, so a SIGSEGV names the step that caused it.

TWO PIXEL-IDENTICAL FRAMES of every photograph. Never
``QT_QPA_PLATFORM=offscreen``: this is a driver, not a test.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-r27b/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-r27b/presets
    python scripts/adv27b_the_preset_button.py <out-dir>
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtWidgets import QApplication, QPushButton        # noqa: E402

from drive_182_preset_verification_window import pump, twice  # noqa: E402

WORK = Path("/tmp/chromiq-r27b/work")
PROJECT = "R27b-Button"

LOG: "list[str]" = []
PROGRESS: Path


def say(line: str = "") -> None:
    print(line, flush=True)
    LOG.append(line)


def step(tag: str) -> None:
    """Name the step BEFORE it runs, on disk. A crash then has a name."""
    with PROGRESS.open("a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%H:%M:%S')}  {tag}\n")
        fh.flush()
        os.fsync(fh.fileno())


def app_like_main() -> QApplication:
    """The QApplication `main.py` builds, not a bare one: the style and the
    application event filter both change what a button measures."""
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    app.setOrganizationName("ChromIQ")
    from core.resource_path import resource_path
    from PyQt6.QtGui import QFontDatabase
    try:
        for f in resource_path("assets/fonts").glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(f))
    except Exception:                                        # noqa: BLE001
        pass
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from ui.widgets import CompositeAppFilter
    app._r27b_filter = CompositeAppFilter(app)               # keep it alive
    app.installEventFilter(app._r27b_filter)
    return app


def geom(w) -> dict:
    if w is None:
        return {"exists": False}
    return {"exists": True, "visible": bool(w.isVisible()),
            "height": int(w.height()), "width": int(w.width()),
            "hint_h": int(w.sizeHint().height()),
            "x": int(w.mapTo(w.window(), w.rect().topLeft()).x()),
            "y": int(w.mapTo(w.window(), w.rect().topLeft()).y())}


def main() -> int:
    global PROGRESS
    out = Path(sys.argv[1] if len(sys.argv) > 1 else
               Path.home() / "Desktop/ChromIQ-beta23-proof/round-27b-chart")
    shots = out / "shots"
    shots.mkdir(parents=True, exist_ok=True)
    PROGRESS = out / "progress.log"
    PROGRESS.write_text("", encoding="utf-8")

    sfile = os.environ.get("CHROMIQ_SETTINGS_FILE", "")
    if "/tmp/" not in sfile:
        print("REFUSING: CHROMIQ_SETTINGS_FILE is not sandboxed", file=sys.stderr)
        return 2
    if "/tmp/" not in os.environ.get("CHROMIQ_PRESETS_DIR", ""):
        print("REFUSING: CHROMIQ_PRESETS_DIR is not sandboxed", file=sys.stderr)
        return 2

    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)

    measured: dict = {}
    step("app")
    app = app_like_main()

    from core.settings import AppSettings
    s = AppSettings()
    s.set("custom_output_path", str(WORK))
    s.set("argyll_bin_path", "/Applications/Argyll/bin")

    from core.file_manager import Project
    from core.measurement_target import (RUN_TYPE_PROFILING,
                                         RUN_TYPE_VERIFICATION)
    from ui.main_window import MainWindow
    from workflow import preset_eligibility as PE

    proj_dir = WORK / PROJECT
    Project.create(proj_dir, PROJECT).current_run().ensure_dir()

    say("# round 27b — the preset-verification button, on screen")
    say("")
    say(f"driven {time.strftime('%Y-%m-%d %H:%M:%S')}")
    say(f"settings sandbox : {sfile}")
    say(f"presets sandbox  : {os.environ['CHROMIQ_PRESETS_DIR']}")
    say("mode             : ON SCREEN, a real window, capture_window by id")
    say("")

    # ---- what the app start costs, before anything is clicked -------------
    step("MainWindow")
    t0 = time.perf_counter()
    win = MainWindow(s)
    win.resize(1500, 1020)
    win.show()
    t_show = time.perf_counter() - t0
    pump(app, 1500)
    tab = win._tab_chart
    ctl = win._target_ctl

    step("open project")
    win._file_mgr.open_project_at(proj_dir)
    ctl.changed.emit()
    pump(app, 800)

    say("## 0. what showing the tab costs before anything is clicked")
    say("")
    say(f"    MainWindow(...) + show() returned in {t_show*1000:.0f} ms")
    warm_started = getattr(tab, "_preset_warm_timer", None) is not None
    n_warm = len(getattr(tab, "_preset_warm_charts", []) or [])
    say(f"    the idle warming started on show : {warm_started}")
    say(f"    charts it queued                 : {n_warm}")
    say(f"    run type at this point           : {ctl.target.run_type}")
    say(f"    …and the button is visible       : "
        f"{tab._preset_verify_btn.isVisible()}")
    measured["startup"] = {"show_ms": round(t_show * 1000),
                           "warm_started": warm_started,
                           "warm_charts": n_warm,
                           "run_type": str(ctl.target.run_type),
                           "button_visible": tab._preset_verify_btn.isVisible()}

    # how long the warming takes to drain, in wall clock, on the event loop
    step("drain the warm")
    t0 = time.perf_counter()
    deadline = t0 + 60
    while (getattr(tab, "_preset_warm_timer", None) is not None
           and getattr(tab, "_preset_warm_at", 0) < n_warm
           and time.perf_counter() < deadline):
        app.processEvents()
    t_warm = time.perf_counter() - t0
    say(f"    the warming drained {getattr(tab, '_preset_warm_at', 0)} charts "
        f"in {t_warm:.2f} s of event loop")
    measured["startup"]["warm_drain_s"] = round(t_warm, 2)
    say("")

    # ---- 1. the run-type rule --------------------------------------------
    step("profiling frame")
    ctl.set_run_type(RUN_TYPE_PROFILING)
    pump(app, 700)
    win._tabs.setCurrentIndex(win._tabs.indexOf(tab))
    pump(app, 700)
    tab._manual_btn.click()
    pump(app, 900)
    from ui.fade_scroll import FadeScrollArea
    host = tab._preset_verify_btn.parent()
    while host is not None and not isinstance(host, FadeScrollArea):
        host = host.parent()

    def bring_into_view():
        if host is not None:
            host.ensureWidgetVisible(tab._preset_combo, 0, 120)
            pump(app, 600)

    bring_into_view()
    say("## 1. Knut's rule: the pair belongs to a verification run only")
    say("")
    prof = {"button": geom(tab._preset_verify_btn),
            "help": geom(getattr(tab, "_preset_verify_help", None))}
    say(f"    Run type = Profiling   -> button visible "
        f"{prof['button']['visible']}, help visible {prof['help']['visible']}")
    ok, why, d = twice(app, win, shots / "01-profiling-run.png")
    say(f"    photograph 01-profiling-run.png: "
        f"{'kept' if ok else 'REFUSED: ' + why} (frames differ by {d} %)")

    step("verification frame")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    pump(app, 900)
    bring_into_view()
    verif = {"button": geom(tab._preset_verify_btn),
             "help": geom(getattr(tab, "_preset_verify_help", None))}
    say(f"    Run type = Verification-> button visible "
        f"{verif['button']['visible']}, help visible {verif['help']['visible']}")
    ok2, why2, d2 = twice(app, win, shots / "02-verification-run.png")
    say(f"    photograph 02-verification-run.png: "
        f"{'kept' if ok2 else 'REFUSED: ' + why2} (frames differ by {d2} %)")
    # …and NOW the warming may have started, because the button is there.
    started_here = getattr(tab, "_preset_warm_timer", None) is not None
    n2 = len(getattr(tab, "_preset_warm_charts", []) or [])
    t0 = time.perf_counter()
    while (getattr(tab, "_preset_warm_at", 0) < n2
           and time.perf_counter() - t0 < 60):
        app.processEvents()
    say(f"    the warming started when the button appeared: {started_here} "
        f"({getattr(tab, '_preset_warm_at', 0)} of {n2} charts, "
        f"{time.perf_counter() - t0:.2f} s)")
    measured.setdefault("startup", {})["warm_started_on_verification"] = \
        started_here
    measured["startup"]["warm_charts_on_verification"] = n2
    measured["run_type_rule"] = {"profiling": prof, "verification": verif,
                                 "frames": {"01": [ok, why, d],
                                            "02": [ok2, why2, d2]}}
    say("")

    # ---- 2. the height, against beta 22's -------------------------------
    step("height")
    say("## 2. the height, measured against beta 22's own button")
    say("")
    row = tab._preset_verify_btn.parentWidget().layout()
    # beta 22's button: the same label, the same parent, NO stylesheet. Put it
    # in the same row so the same layout and the same font filter size it.
    import core.i18n as I18N
    old = QPushButton(I18N.tr("Which presets can be verified?"),
                      tab._preset_verify_btn.parentWidget())
    vr = None
    for i in range(row.count()):
        it = row.itemAt(i)
        if it.layout() is not None and it.layout().indexOf(
                tab._preset_verify_btn) >= 0:
            vr = it.layout()
    if vr is None:                      # the row IS the layout holding it
        for i in range(row.count()):
            it = row.itemAt(i)
            if it.widget() is tab._preset_verify_btn:
                vr = row
    if vr is None:
        vr = tab._preset_verify_btn.parentWidget().layout()
    vr.insertWidget(1, old)
    old.show()
    pump(app, 800)
    now_h = tab._preset_verify_btn.height()
    old_h = old.height()
    say(f"    beta 22's button (no stylesheet) : {old_h} px tall, "
        f"hint {old.sizeHint().height()} px")
    say(f"    the shipped button               : {now_h} px tall, "
        f"hint {tab._preset_verify_btn.sizeHint().height()} px")
    say(f"    the preset pulldown beside it    : "
        f"{tab._preset_combo.height()} px")
    say(f"    the +/- icon buttons             : "
        f"{tab._preset_add_btn.height()} px")
    # is the LABEL still whole at that height? Menlo, uppercase, the app's font.
    from PyQt6.QtGui import QFontMetrics
    fm = QFontMetrics(tab._preset_verify_btn.font())
    txt = tab._preset_verify_btn.text().upper()
    say(f"    the label needs {fm.height()} px of line height and "
        f"{fm.horizontalAdvance(txt)} px of width")
    say(f"    the button gives it {now_h} px x {tab._preset_verify_btn.width()} px")
    ok3, why3, d3 = twice(app, win, shots / "03-old-and-new-height.png")
    say(f"    photograph 03-old-and-new-height.png (beta 22's button "
        f"inserted beside the shipped one): "
        f"{'kept' if ok3 else 'REFUSED: ' + why3} (differ by {d3} %)")
    measured["height"] = {
        "beta22_px": old_h, "beta22_hint": old.sizeHint().height(),
        "shipped_px": now_h,
        "shipped_hint": tab._preset_verify_btn.sizeHint().height(),
        "combo_px": tab._preset_combo.height(),
        "icon_btn_px": tab._preset_add_btn.height(),
        "font_line_px": fm.height(),
        "label_width_px": fm.horizontalAdvance(txt),
        "button_width_px": tab._preset_verify_btn.width(),
        "frame": [ok3, why3, d3]}
    vr.removeWidget(old)
    old.setParent(None)
    old.deleteLater()
    pump(app, 500)
    say("")

    # ---- 3. the clock around the press -----------------------------------
    step("clock")
    say("## 3. a clock around the press, not an impression")
    say("")
    from ui.dialogs import preset_verification_dialog as PVD
    opened: list = []
    orig_exec = PVD.PresetVerificationDialog.exec

    def _no_block(self):
        opened.append((self, time.perf_counter()))
        self.show()
        return 0
    PVD.PresetVerificationDialog.exec = _no_block

    def press_and_time(label: str) -> float:
        opened.clear()
        t = time.perf_counter()
        tab._preset_verify_btn.click()
        el = (opened[0][1] - t) if opened else -1.0
        pump(app, 400)
        say(f"    {label:<46} {el*1000:7.0f} ms")
        return el

    try:
        # WARM: the cache the idle warming filled is still there.
        warm_ms = press_and_time("warm (the idle warming has run)")
        dlg = opened[0][0]
        dlg.close()
        pump(app, 400)
        # COLD: exactly what a user gets if they click before the warming has
        # drained, or on the first show of a session that never idled.
        PE.clear_cache()
        cold_ms = press_and_time("cold (the cache emptied first)")
        dlg = opened[0][0]
        ok4, why4, d4 = twice(app, dlg, shots / "04-the-window.png")
        say(f"    photograph 04-the-window.png: "
            f"{'kept' if ok4 else 'REFUSED: ' + why4} (differ by {d4} %)")
        # what does the window pre-select? The user chose a preset; does the
        # window open on it?
        cur = dlg._tree.currentItem()
        say(f"    the window opens with this preset selected: "
            f"{cur.text(0) if cur is not None else 'NOTHING'}")
        say(f"    the Create Chart pulldown had: "
            f"{tab._preset_combo.currentText()!r}")
        say(f"    presets listed in the window: "
            f"{sum(dlg._tree.topLevelItem(i).childCount() for i in range(dlg._tree.topLevelItemCount()))}")
        say(f"    is there any way to search/filter by name? "
            f"{'yes' if [c for c in dlg.findChildren(object) if type(c).__name__ == 'QLineEdit'] else 'NO — no text field in the window'}")
        measured["timing"] = {"warm_ms": round(warm_ms * 1000),
                              "cold_ms": round(cold_ms * 1000),
                              "frame": [ok4, why4, d4],
                              "preselected": (cur.text(0) if cur is not None
                                              else None),
                              "combo_text": tab._preset_combo.currentText()}
        dlg.close()
        pump(app, 500)

        # ---- 4. the warming, stressed ------------------------------------
        say("")
        say("## 4. the idle warming, stressed (a crash here is a blocker)")
        say("")
        stress: dict = {}

        def restart_warm():
            """Put the tab back in the state a fresh show leaves it in."""
            t = getattr(tab, "_preset_warm_timer", None)
            if t is not None:
                t.stop()
                t.deleteLater()
            tab._preset_warm_timer = None
            tab._preset_warm_at = 0
            PE.clear_cache()
            tab._warm_preset_eligibility()
            # let it get HALF WAY, no further
            n = len(getattr(tab, "_preset_warm_charts", []) or [])
            while getattr(tab, "_preset_warm_at", 0) < n // 2:
                app.processEvents()

        for tag, act in (
            ("open the window while the warming is half done",
             lambda: tab._preset_verify_btn.click()),
            ("open it twice in a row, mid-warm",
             lambda: (tab._preset_verify_btn.click(),
                      opened and opened[-1][0].close(),
                      tab._preset_verify_btn.click())),
            ("change run type mid-warm",
             lambda: (ctl.set_run_type(RUN_TYPE_PROFILING),
                      ctl.set_run_type(RUN_TYPE_VERIFICATION))),
            ("switch tab away and back mid-warm",
             lambda: (win._tabs.setCurrentIndex(0),
                      win._tabs.setCurrentIndex(win._tabs.indexOf(tab)))),
            ("hide the tab mid-warm and drain the loop",
             lambda: (tab.hide(), pump(app, 1200), tab.show())),
        ):
            step("stress: " + tag)
            restart_warm()
            before = getattr(tab, "_preset_warm_at", 0)
            act()
            pump(app, 1500)
            for w, _t in list(opened):
                try:
                    w.close()
                except Exception:                            # noqa: BLE001
                    pass
            opened.clear()
            pump(app, 600)
            after = getattr(tab, "_preset_warm_at", 0)
            alive = getattr(tab, "_preset_warm_timer", None) is not None
            stress[tag] = {"warmed_before": before, "warmed_after": after,
                           "timer_alive": alive, "survived": True}
            say(f"    survived: {tag}")
            say(f"        warmed {before} -> {after}, timer still held: {alive}")
        measured["stress"] = stress

        # the last one on its own: the tab DESTROYED mid-warm.
        step("stress: destroy the tab mid-warm")
        restart_warm()
        n = len(getattr(tab, "_preset_warm_charts", []) or [])
        at = getattr(tab, "_preset_warm_at", 0)
        say(f"    destroying the tab with {n - at} charts still queued")
        win.close()
        pump(app, 400)
        win.deleteLater()
        pump(app, 2500)
        say("    survived: the tab destroyed mid-warm")
        measured["stress"]["destroy the tab mid-warm"] = {"survived": True}
    finally:
        PVD.PresetVerificationDialog.exec = orig_exec

    step("done")
    (out / "measured.json").write_text(json.dumps(measured, indent=2),
                                       encoding="utf-8")
    (out / "on-screen-button.md").write_text("\n".join(LOG) + "\n",
                                             encoding="utf-8")
    say("")
    say(f"written: {out / 'on-screen-button.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
