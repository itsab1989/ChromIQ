#!/usr/bin/env python3
"""ADVERSARY 14 — Knut's doors for the new Alignment parameter, on screen.

    The new alignment parameter must be added in the list of parameters so that
    it is saved/remembered or loaded in all cases for a profile run or run
    type, when changing profile run or run type, or when loading a preset,
    generating chart and all the other events that will load, save or generate.

So: set a non-default alignment, then walk every one of those doors and read
the pulldown back out of the REAL panel each time.

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-adv14d.ini \
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-adv14d-presets \
        python scripts/adv14_alignment_doors.py <out-dir>
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402

from onscreen_capture import capture_window                      # noqa: E402

WANT = "between_margins"


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv14d-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("use_chromiq_layout_engine", True)
    settings.set("restore_last_session", False)
    settings.set("appearance", "dark")
    settings.set("margin_inspector_show", True)
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import BUILTIN_PRESET_GROUPS, TabChart
    from ui.theme import apply_appearance
    TabChart._confirm_displacing_results = lambda self, *a, **k: True

    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.resize(1620, 1040)
    win.show(); win.raise_(); win.activateWindow()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 800)
    tab._user_switch_mode("manual")
    pump(app, 1500)
    print(f"    ON SCREEN: visible={win.isVisible()} "
          f"{win.frameGeometry().width()}x{win.frameGeometry().height()}", flush=True)

    combo, panel = tab._preset_combo, tab._manual_layout_panel
    for instr, entries in BUILTIN_PRESET_GROUPS:
        if "i1Pro /" not in instr:
            continue
        for n, (label, _o, key) in enumerate(entries, 1):
            if combo.findData(key) < 0:
                continue
            if tab._manual_target_name_edit is not None:
                tab._manual_target_name_edit.setText("AdvDoors")
            pump(app, 200)
            combo.setCurrentIndex(combo.findData(key))
            combo.activated.emit(combo.findData(key))
            pump(app, 1200)
            break
        break
    for _ in range(200):
        pump(app, 120)
        if getattr(tab, "_margin_ti2", None):
            break

    doors = []

    def read(where, extra=None):
        r = panel.get_recipe()
        row = {"door": where,
               "pulldown": str(panel.chart_text_align.currentData() or ""),
               "recipe": str(getattr(r, "chart_text_align", "")),
               "ok": str(getattr(r, "chart_text_align", "")) == WANT}
        row.update(extra or {})
        doors.append(row)
        print("   ", json.dumps(row), flush=True)
        return row

    i = panel.chart_text_align.findData(WANT)
    assert i >= 0
    panel.chart_text_align.setCurrentIndex(i)
    panel.chart_text.setText("ADVERSARY 14 alignment door test")
    pump(app, 800)
    read("after setting it in the pulldown")

    # ---- Generate Chart ----------------------------------------------------
    # THE REAL HANDLER. The first version of this called
    # `_on_generate_clicked`, which does not exist, behind a `hasattr` guard,
    # so the door reported "ok" without generating anything.
    assert hasattr(tab, "_on_generate"), "the Generate handler moved"
    tab._on_generate()
    built = None
    for _ in range(900):
        pump(app, 200)
        cand = sorted(Path(work).rglob("*.tif"))
        if cand:
            built = cand[0]
            break
    pump(app, 2500)
    read("after Generate Chart", {"a_tiff_was_written": bool(built),
                                  "tiff": str(built or "")})

    # ---- switch the profile run and come back ------------------------------
    bar = getattr(win, "_target_bar", None) or getattr(win, "_measurement_bar", None)
    if bar is None:
        for name in dir(win):
            w = getattr(win, name, None)
            if hasattr(w, "_run_combo") and hasattr(w, "_type_combo"):
                bar = w
                break
    if bar is None:
        doors.append({"door": "profile-run combo", "error": "bar not found"})
    else:
        rc = bar._run_combo
        before_idx = rc.currentIndex()
        print("    run combo entries:",
              [rc.itemText(k) for k in range(rc.count())], flush=True)
        if rc.count() > 1:
            rc.setCurrentIndex((before_idx + 1) % rc.count())
            pump(app, 2500)
            read("after switching the PROFILE RUN away")
            rc.setCurrentIndex(before_idx)
            pump(app, 2500)
            read("after switching the PROFILE RUN back")
        else:
            # make a second run through the combo's own "new run" entry
            for k in range(rc.count()):
                if "new" in rc.itemText(k).lower():
                    rc.setCurrentIndex(k)
                    pump(app, 2500)
                    read("after 'New run' in the profile-run pulldown")
                    break
            else:
                doors.append({"door": "profile run",
                              "error": f"only one entry: {rc.itemText(0)!r}"})
        tc = bar._type_combo
        print("    run type entries:",
              [tc.itemText(k) for k in range(tc.count())], flush=True)
        if tc.count() > 1:
            t0 = tc.currentIndex()
            tc.setCurrentIndex((t0 + 1) % tc.count())
            pump(app, 2500)
            read("after switching the RUN TYPE away")
            tc.setCurrentIndex(t0)
            pump(app, 2500)
            read("after switching the RUN TYPE back")

    # ---- close the project and open it again -------------------------------
    try:
        names = [tab._target_combo.itemText(k)
                 for k in range(tab._target_combo.count())] \
            if hasattr(tab, "_target_combo") else []
        print("    target combo:", names, flush=True)
    except Exception as exc:                                   # noqa: BLE001
        print("    no target combo:", exc, flush=True)
    # reopen via the controller: re-select the same target, which reloads the
    # run's stored Create Chart state from disk
    try:
        ctl = win._ctl if hasattr(win, "_ctl") else None
        if ctl is not None:
            cur = ctl.target_name() if hasattr(ctl, "target_name") else None
            print("    controller target:", cur, flush=True)
            if cur:
                ctl.set_target(cur)
                pump(app, 2500)
                read("after re-selecting the same target (reload from disk)")
    except Exception as exc:                                   # noqa: BLE001
        doors.append({"door": "reopen", "error": repr(exc)})
        print("    reopen door error:", exc, flush=True)

    capture_window(win, out / "doors-final.png")
    (out / "doors.json").write_text(json.dumps(doors, indent=2), encoding="utf-8")
    print("WROTE", out / "doors.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
