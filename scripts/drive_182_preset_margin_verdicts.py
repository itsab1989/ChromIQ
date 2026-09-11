#!/usr/bin/env python3
"""R5: load every built-in Create Chart preset in a REAL window and record
what the "Measured from Preview" panel says about its margins.

Knut, #182, 2026-09-11: *"if you load presets one-by-one, you will see that
some charts does not give any green 'Margins: OK' message at all. Why?"*

This driver answers that by measuring rather than reasoning. It picks each
built-in from the real Presets dropdown the way a person does (the tab listens
on ``activated``, so ``setCurrentIndex`` alone applies nothing), waits for the
chart to be built and the panel to be updated, and records BOTH what the panel
prints and the four inputs that decide it:

    thresholds_defined   -- are there instrument minimums for this
                            instrument x paper x orientation at all
    violations           -- margins under those minimums
    text_warnings        -- the row-indicator raise, the strip-length note
    overlap_warnings     -- text printed over the patches

Every one of those is read off the call the tab actually makes, by wrapping
``MarginInspectorPanel.update_report`` -- so the record is the app's own
arguments, not a re-derivation of them.

Basti's preferences are copied to a throwaway .ini and his ChromIQ root is
replaced by a sandbox. Nothing of his is touched. Check afterwards with

    defaults read com.chromiq.ChromIQ custom_output_path

Usage::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-margins.ini \
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-margins-presets \
        python scripts/drive_182_preset_margin_verdicts.py [--limit N] [--only SUBSTR]
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"
OUT = Path("/tmp/chromiq-margins-proof")


def pump(app, ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def run(app, limit: int, only: str) -> int:
    from core.settings import AppSettings

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq-margins-"))
    src = QSettings(str(REAL_PLIST), QSettings.Format.NativeFormat)
    dst = QSettings(str(sandbox / "settings.ini"), QSettings.Format.IniFormat)
    for k in src.allKeys():
        dst.setValue(k, src.value(k))
    dst.sync()
    settings = AppSettings()
    settings._qs = dst
    work = sandbox / "ChromIQ"
    work.mkdir()
    settings.set("custom_output_path", str(work))
    settings.set("restore_last_session", False)
    settings.set("appearance", "dark")
    settings.set("margin_inspector_show", True)
    settings.set("margin_violation_notify", True)
    print(f"    sandbox: {sandbox}", flush=True)

    QDialog.exec = lambda self: 1                      # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore

    from ui.main_window import MainWindow
    from ui.theme import apply_appearance
    from ui.tabs.tab_chart import BUILTIN_PRESET_GROUPS, TabChart
    from ui.margin_inspector_panel import MarginInspectorPanel
    TabChart._confirm_displacing_results = lambda self, *a, **k: True

    # The app's own arguments, captured where it makes the call.
    seen: dict = {}
    _orig = MarginInspectorPanel.update_report

    def _spy(self, report, violations, **kw):
        seen.clear()
        seen.update({
            "report": None if report is None else {
                "L": round(report.left_mm, 2), "R": round(report.right_mm, 2),
                "T": round(report.top_mm, 2), "B": round(report.bottom_mm, 2),
                "page_w": round(report.page_w_mm, 1),
                "page_h": round(report.page_h_mm, 1),
                "strip_len": (None if report.strip_length_mm is None
                              else round(report.strip_length_mm, 1)),
            },
            "violations": [f"{v.edge} {v.measured_mm:.1f}<{v.threshold_mm:.1f}"
                           for v in violations],
            "thresholds_defined": bool(kw.get("thresholds_defined")),
            "thresholds": kw.get("thresholds"),
            "notify": bool(kw.get("notify")),
            "text_warnings": list(kw.get("text_warnings") or []),
            "overlap_warnings": list(kw.get("overlap_warnings") or []),
        })
        return _orig(self, report, violations, **kw)

    MarginInspectorPanel.update_report = _spy          # type: ignore[assignment]

    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.show()
    win.raise_()
    win.activateWindow()
    pump(app, 3000)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 800)
    tab._user_switch_mode("manual")
    pump(app, 1500)
    print(f"    window is on screen: {win.isVisible()} "
          f"{win.frameGeometry().width()}x{win.frameGeometry().height()}",
          flush=True)

    combo = tab._preset_combo
    panel = tab._margin_panel
    todo = [(instr, label, key)
            for instr, entries in BUILTIN_PRESET_GROUPS
            for (label, _o, key) in entries]
    if only:
        todo = [t for t in todo if only.lower() in (t[1] + t[2]).lower()]
    if limit:
        todo = todo[:limit]
    print(f"    {len(todo)} built-in presets to load\n", flush=True)

    rows = []
    for n, (instr, label, key) in enumerate(todo, 1):
        idx = combo.findData(key)
        if idx < 0:
            print(f"    [{n:3d}] {label}: NOT IN THE DROPDOWN")
            continue
        target = f"MP-{n:03d}"
        if tab._manual_target_name_edit is not None:
            tab._manual_target_name_edit.setText(target)
        pump(app, 150)
        seen.clear()
        tab._margin_ti2 = None
        combo.setCurrentIndex(idx)
        combo.activated.emit(idx)
        pump(app, 250)
        built = False
        for _ in range(360):
            pump(app, 250)
            if getattr(tab, "_margin_ti2", None) and seen:
                built = True
                break
        pump(app, 700)
        status = panel.status_message()
        notes = panel.text_notes()
        row = {
            "n": n, "instrument": instr, "label": label, "key": key,
            "built": built,
            "status_message": status,
            "panel_visible": panel.isVisible(),
            "tooltip_notes": notes,
            **{k: v for k, v in seen.items()},
        }
        # The single reason the green line is not there.
        if not built:
            row["verdict"] = "DID-NOT-BUILD"
        elif not seen.get("notify", True):
            row["verdict"] = "notify-off"
        elif seen.get("report") is None:
            row["verdict"] = "no-report"
        elif seen.get("violations") or seen.get("overlap_warnings"):
            row["verdict"] = "RED"
        elif seen.get("text_warnings"):
            row["verdict"] = "BLANK (a text notice suppresses the line)"
        elif not seen.get("thresholds_defined"):
            row["verdict"] = "GREY (no instrument margins for this combo)"
        else:
            row["verdict"] = "GREEN"
        rows.append(row)
        print(f"    [{n:3d}/{len(todo)}] {label[:58]:<58} {row['verdict']}",
              flush=True)
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "r5-preset-margin-verdicts.json").write_text(
            json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")

    # One photograph of the real window at the end, if the screen allows it.
    from scripts.onscreen_capture import capture_window, session_is_locked
    OUT.mkdir(parents=True, exist_ok=True)
    ok, why = capture_window(win, OUT / "r5-create-chart-window.png")
    print(f"\n    capture: {'OK' if ok else 'REFUSED - ' + why} "
          f"(screen locked: {session_is_locked()})", flush=True)

    tally: dict[str, int] = {}
    for r in rows:
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1
    print("\n    ---- tally ----")
    for k, v in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"    {v:4d}  {k}")
    win.close()
    pump(app, 500)
    return 0


def main() -> int:
    limit = 0
    only = ""
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--limit":
            limit = int(args[i + 1])
        if a == "--only":
            only = args[i + 1]
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    return run(app, limit, only)


if __name__ == "__main__":
    raise SystemExit(main())
