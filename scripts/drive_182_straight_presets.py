#!/usr/bin/env python3
"""Knut's six straight-strip CR30 presets, loaded one by one in a REAL window.

Knut, #182, 2026-09-13, after testing them as user presets on beta 7: *"all 6
profiles give no warnings at all. The A4 chart presets look good and work
exactly as desinged. No overlap warnings... show top=12.3mm and bottom = 6.9mm
in Measured from Preview. All ok. Ship the presets."*

This drives the SHIPPED built-ins, which is a different path from his user
presets, and photographs the panel for each one so the numbers can be read off
the screen rather than off a log. It records, per preset:

    the four measured margins, as the tab hands them to the panel
    the violations, text notices and overlap notices, likewise
    the "Patch width" the panel prints (this is the readout that was showing a
        turned honeycomb's COLUMN PITCH instead of the patch)
    the status line the user sees

Everything is read off `MarginInspectorPanel.update_report`'s own arguments,
where the tab makes the call, so nothing here re-derives what it is checking.

Basti's preferences are copied to a throwaway .ini and his ChromIQ root is
replaced by a sandbox. Nothing of his is touched. Check afterwards with

    defaults read com.chromiq.ChromIQ custom_output_path

Usage::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-straight.ini \
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-straight-presets \
        python scripts/drive_182_straight_presets.py [--out DIR]
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


def pump(app, ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def run(app, out: Path) -> int:
    from core.settings import AppSettings

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq-straight-"))
    src = QSettings(str(REAL_PLIST), QSettings.Format.NativeFormat)
    dst = QSettings(str(sandbox / "settings.ini"), QSettings.Format.IniFormat)
    for k in src.allKeys():
        dst.setValue(k, src.value(k))
    dst.sync()
    settings = AppSettings()
    settings._qs = dst
    work = sandbox / "ChromIQ"
    work.mkdir()
    # PINNED, not merely sandboxed: an unset custom_output_path in a fresh
    # store still points the app at the user's real ~/ChromIQ.
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
    from ui.margin_inspector_panel import MarginInspectorPanel
    from ui.theme import apply_appearance
    from ui.tabs.tab_chart import BUILTIN_PRESET_GROUPS, TabChart
    TabChart._confirm_displacing_results = lambda self, *a, **k: True

    seen: dict = {}
    _orig = MarginInspectorPanel.update_report

    def _spy(self, report, violations, **kw):
        seen.clear()
        seen.update({
            "report": None if report is None else {
                "L": round(report.left_mm, 3), "R": round(report.right_mm, 3),
                "T": round(report.top_mm, 3), "B": round(report.bottom_mm, 3),
                "patch_width_mm": (None if report.strip_width_mm is None
                                   else round(report.strip_width_mm, 3)),
                "page": [round(report.page_w_mm, 1), round(report.page_h_mm, 1)],
            },
            "violations": [f"{v.edge} {v.measured_mm:.3f} < {v.threshold_mm:.1f}"
                           for v in violations],
            "thresholds": kw.get("thresholds"),
            "thresholds_defined": bool(kw.get("thresholds_defined")),
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
    on_screen = win.isVisible()
    print(f"    window is on screen: {on_screen} "
          f"{win.frameGeometry().width()}x{win.frameGeometry().height()}",
          flush=True)
    if not on_screen:
        print("    !! NO WINDOW. This run proves nothing about what is drawn.",
              flush=True)

    from scripts.onscreen_capture import capture_window, session_is_locked
    out.mkdir(parents=True, exist_ok=True)

    combo = tab._preset_combo
    panel = tab._margin_panel
    todo = [(label, key)
            for _instr, entries in BUILTIN_PRESET_GROUPS
            for (label, _o, key) in entries
            if "Straight" in label]
    print(f"    {len(todo)} straight-strip presets in the dropdown\n", flush=True)

    rows = []
    for n, (label, key) in enumerate(todo, 1):
        idx = combo.findData(key)
        assert idx >= 0, f"{label} is not in the real dropdown"
        if tab._manual_target_name_edit is not None:
            tab._manual_target_name_edit.setText(f"ST-{n:02d}")
        pump(app, 150)
        seen.clear()
        tab._margin_ti2 = None
        # The tab listens on `activated`, so setCurrentIndex alone applies
        # nothing. This is the click.
        combo.setCurrentIndex(idx)
        combo.activated.emit(idx)
        pump(app, 250)
        built = False
        for _ in range(480):
            pump(app, 250)
            if getattr(tab, "_margin_ti2", None) and seen:
                built = True
                break
        pump(app, 900)
        shot = out / f"straight-{n:02d}-{key.strip('_').replace('__', '')}.png"
        ok, why = capture_window(win, shot)
        row = {
            "n": n, "label": label, "key": key, "built": built,
            "status_message": panel.status_message(),
            "panel_patch_width_text": panel._strip_mm.text(),
            "panel_top_text": panel._value_labels["T"][0].text(),
            "panel_bottom_text": panel._value_labels["B"][0].text(),
            "photograph": shot.name if ok else f"REFUSED: {why}",
            **{k: v for k, v in seen.items()},
        }
        rows.append(row)
        r = row.get("report") or {}
        print(f"    [{n}/{len(todo)}] {label[:52]:<52} "
              f"T={r.get('T')} B={r.get('B')} patch={r.get('patch_width_mm')} "
              f"viol={len(row['violations'])} text={len(row['text_warnings'])} "
              f"overlap={len(row['overlap_warnings'])} "
              f"photo={'ok' if ok else 'REFUSED'}", flush=True)
        (out / "straight-presets.json").write_text(
            json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"\n    screen locked: {session_is_locked()}", flush=True)
    print(f"    proof in {out}", flush=True)
    win.close()
    pump(app, 500)
    bad = [r for r in rows
           if not r["built"] or r["violations"] or r["overlap_warnings"]]
    if bad:
        print(f"\n    !! {len(bad)} preset(s) did not come up clean")
        return 1
    print("\n    all clean: built, no violations, no overlap notices")
    return 0


def main() -> int:
    out = Path("/tmp/chromiq-straight-proof")
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--out":
            out = Path(args[i + 1])
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    return run(app, out)


if __name__ == "__main__":
    raise SystemExit(main())
