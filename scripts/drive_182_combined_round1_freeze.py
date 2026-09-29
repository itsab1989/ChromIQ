#!/usr/bin/env python3
"""Combined round 1: what the restored rise search costs the READER, in the
real panel, at the resolutions the Resolution box offers.

The suite's guard bounds the number of geometry rebuilds. A reader feels
seconds, and the cost of one rebuild is not a constant.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))
from onscreen_capture import capture_window, session_is_locked   # noqa: E402


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def check(app, box, want):
    if bool(box.isChecked()) != bool(want):
        box.click()
    pump(app, 200)


def main() -> int:                                   # noqa: C901
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    crashes: list = []
    prev = sys.excepthook
    sys.excepthook = lambda t, e, tb: (
        crashes.append("".join(traceback.format_exception(t, e, tb))),
        prev(t, e, tb))

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-b20r1f-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("use_chromiq_layout_engine", True)
    settings.set("restore_last_session", False)
    settings.set("appearance", "dark")
    settings.set("margin_inspector_show", True)
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    print(f"    screen locked at start: {session_is_locked()}", flush=True)

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    from ui.theme import apply_appearance
    from workflow import margin_inspector as mi
    TabChart._confirm_displacing_results = lambda self, *a, **k: True
    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.resize(1680, 1060)
    win.show()
    win.raise_()
    win.activateWindow()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 800)
    tab._user_switch_mode("manual")
    pump(app, 1500)
    panel = tab._manual_layout_panel
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("B20R1Freeze")
    pump(app, 400)
    check(app, panel.use_instr_margins, False)

    # THE STATE: chart-first, where a margin value is law and the search is
    # allowed to run, with a bottom line far too tall for the room.
    panel.layout_mode.setCurrentIndex(
        max(0, panel.layout_mode.findData("area_first")))
    pump(app, 400)
    for k, v in (("b", 4.0), ("t", 10.0), ("l", 10.0), ("r", 10.0)):
        panel.margins[k].setValue(v)
    panel.chart_text.setText("Combined round one")
    panel.chart_text_size.setValue(20.0)
    check(app, panel.stamp_command, True)
    panel.text_edge.setValue(4.0)
    pump(app, 500)

    rows = []
    for dpi in (200, 300, 600, 1200):
        panel.dpi.setValue(dpi)
        pump(app, 500)
        assert panel.dpi.value() == dpi
        tab._margin_report = None
        t0 = time.monotonic()
        tab._generate_btn.click()
        for _ in range(3000):
            pump(app, 150)
            if getattr(tab, "_margin_report", None) is not None:
                break
        gen = time.monotonic() - t0
        # Count the geometry rebuilds AND the wall clock of one frame repaint,
        # which is what a page turn and a Generate both pay.
        n = {"c": 0}
        real = mi.engine_patch_bottom_mm

        def counted(*a, **k):
            n["c"] += 1
            return real(*a, **k)

        mi.engine_patch_bottom_mm = counted
        times = []
        try:
            for _ in range(12):
                n["c"] = 0
                t1 = time.monotonic()
                tab._update_margin_inspector()
                times.append(round((time.monotonic() - t1) * 1000.0, 1))
                probes = n["c"]
                pump(app, 150)
        finally:
            mi.engine_patch_bottom_mm = real
        warns, over = TabChart._engine_text_notes(
            tab, getattr(tab, "_margin_report", None))
        rise = [m for m in over if "by about" in m and "Bottom" in m]
        times.sort()
        row = {"dpi": dpi, "generate_s": round(gen, 1),
               "frame_repaint_ms": times,
               "median_ms": times[len(times) // 2],
               "geometry_rebuilds_per_repaint": probes,
               "names_a_rise": bool(rise),
               "rise_sentence": rise[0][:300] if rise else ""}
        rows.append(row)
        print(f"    {dpi:5} dpi: generate {gen:5.1f}s | frame repaint "
              f"median {row['median_ms']:7.1f} ms {times} | "
              f"{probes} geometry rebuilds | names a rise: {row['names_a_rise']}",
              flush=True)
        ok, why = capture_window(win, out / f"F-{dpi}dpi.png")
        row["photograph"] = "OK" if ok else f"REFUSED: {why}"

    (out / "freeze.json").write_text(json.dumps(rows, indent=2,
                                                ensure_ascii=False),
                                     encoding="utf-8")
    (out / "crashes-freeze.txt").write_text("\n\n".join(crashes) or "none",
                                            encoding="utf-8")
    print(f"    crashes: {len(crashes)}", flush=True)
    win.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
