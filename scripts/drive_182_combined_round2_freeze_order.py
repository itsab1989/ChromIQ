#!/usr/bin/env python3
"""Combined round 2: the 5.9-second repaint, and whether it is memory.

Round 1 walked 200 -> 300 -> 600 -> 1200 dpi and, at 1200, one of five frame
repaints took 5862.4 ms where the other four ran 194 to 206. A re-run at 1200
ALONE produced twelve repaints between 166.6 and 182.6 ms and the outlier did
not come back, so it was recorded as not reproduced. It also recorded it as
"an early repaint", which the data cannot say: the driver sorts `times` before
writing them, so the ORDER was thrown away.

This keeps the order, walks the same four resolutions in the same process three
times over, and records what the process is carrying at each sample: resident
memory, the Python heap's generation counts, and whether a collection ran. If a
reader can meet a six-second freeze in this panel, the walk is where it lives.
"""
from __future__ import annotations

import gc
import json
import os
import resource
import subprocess
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

    def rss_mb() -> float:
        """PEAK resident memory. `ru_maxrss` is a high-water mark and never
        falls, so it says what the process has HAD, not what it holds."""
        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                     / (1024.0 * 1024.0), 1)

    def live_mb() -> float:
        """What the process holds RIGHT NOW, which is what `ru_maxrss` cannot
        say. `ps` is asked because it is the same number Activity Monitor
        shows the owner."""
        try:
            o = subprocess.run(["ps", "-o", "rss=", "-p", str(os.getpid())],
                               capture_output=True, text=True,
                               encoding="utf-8", timeout=10)
            return round(int(o.stdout.strip()) / 1024.0, 1)
        except Exception:                            # noqa: BLE001
            return -1.0

    def faults() -> tuple:
        """(major, minor) page faults so far. A repaint that stalls on memory
        the system has reclaimed shows up HERE and nowhere else."""
        r = resource.getrusage(resource.RUSAGE_SELF)
        return (r.ru_majflt, r.ru_minflt)

    rows = []
    for sweep in range(1, 4):
     for dpi in (200, 300, 600, 1200):
        panel.dpi.setValue(dpi)
        pump(app, 500)
        assert panel.dpi.value() == dpi
        tab._margin_report = None
        rss_before = rss_mb()
        live_before = live_mb()
        gc_before = gc.get_count()
        gc_stats_before = [d["collections"] for d in gc.get_stats()]
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
        samples = []
        try:
            for i in range(12):
                n["c"] = 0
                c0 = [d["collections"] for d in gc.get_stats()]
                r0 = live_mb()
                f0 = faults()
                t1 = time.monotonic()
                tab._update_margin_inspector()
                ms = round((time.monotonic() - t1) * 1000.0, 1)
                times.append(ms)
                c1 = [d["collections"] for d in gc.get_stats()]
                f1 = faults()
                samples.append({"i": i, "ms": ms,
                                "gc_runs": [b - a for a, b in zip(c0, c1)],
                                "live_mb_before": r0, "live_mb_after": live_mb(),
                                "major_faults": f1[0] - f0[0],
                                "minor_faults": f1[1] - f0[1],
                                "probes": n["c"]})
                probes = n["c"]
                pump(app, 150)
        finally:
            mi.engine_patch_bottom_mm = real
        warns, over = TabChart._engine_text_notes(
            tab, getattr(tab, "_margin_report", None))
        rise = [m for m in over if "by about" in m and "Bottom" in m]
        # NOT SORTED. The order is the whole question.
        srt = sorted(times)
        row = {"sweep": sweep, "dpi": dpi, "generate_s": round(gen, 1),
               "frame_repaint_ms_in_order": times,
               "samples": samples,
               "peak_rss_mb_before_generate": rss_before,
               "live_mb_before_generate": live_before,
               "gc_count_before_generate": list(gc_before),
               "gc_collections_before_generate": gc_stats_before,
               "max_ms": max(times), "min_ms": min(times),
               "median_ms": srt[len(srt) // 2],
               "geometry_rebuilds_per_repaint": probes,
               "names_a_rise": bool(rise),
               "rise_sentence": rise[0][:300] if rise else ""}
        rows.append(row)
        print(f"    sweep {sweep} {dpi:5} dpi: generate {gen:5.1f}s | "
              f"median {row['median_ms']:7.1f} ms  max {row['max_ms']:8.1f} ms "
              f"| live {live_before} -> {live_mb()} MB (peak {rss_mb()}) "
              f"| {probes} rebuilds",
              flush=True)
        if sweep == 1:
            ok, why = capture_window(win, out / f"FR2-{dpi}dpi.png")
            row["photograph"] = "OK" if ok else f"REFUSED: {why}"

    (out / "freeze-faults.json").write_text(json.dumps(rows, indent=2,
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
