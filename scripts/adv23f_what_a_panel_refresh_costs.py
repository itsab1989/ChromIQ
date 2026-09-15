#!/usr/bin/env python3
"""Adversary 23f — what one "Measured from Preview" refresh costs.

The stale-panel fault is fixed by refreshing the panel from the same hook every
layout change already routes through. That hook fires on EVERY keystroke of
every Manual row, so the cost has to be measured before it is added, not after.

Times `_update_margin_inspector()` in the built state, in both layout modes,
with the warning up and with it down, and times a run of real keystrokes in the
Patches box with the refresh wired in.
"""
from __future__ import annotations

import json
import os
import statistics
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
from PyQt6.QtCore import Qt                                   # noqa: E402
from PyQt6.QtTest import QTest                                # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.005)


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert os.environ.get("QT_QPA_PLATFORM") != "offscreen", "ON SCREEN ONLY"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv23f-"))
    settings = AppSettings()
    for k, v in (("custom_output_path", str(work)), ("language", "en"),
                 ("use_chromiq_layout_engine", True),
                 ("restore_last_session", False), ("appearance", "dark"),
                 ("margin_inspector_show", True),
                 ("auto_update_preview", False)):
        settings.set(k, v)
    QDialog.exec = lambda self: 1                    # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore
    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    from ui.theme import apply_appearance
    TabChart._confirm_displacing_results = lambda self, *a, **k: True
    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.resize(1680, 1100)
    win.show()
    win.raise_()
    pump(app, 2400)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 700)
    tab._user_switch_mode("manual")
    pump(app, 1400)
    tab._manual_target_name_edit.setText("adv23f")
    pump(app, 400)
    p = tab._manual_layout_panel
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    pump(app, 900)
    if p.use_instr_margins.isChecked():
        p.use_instr_margins.setChecked(False)
        pump(app, 400)
    p.paper.setCurrentIndex(p.paper.findData("A4"))
    for k, v in (("t", 12.0), ("l", 10.0), ("r", 10.0), ("b", 8.0)):
        p.margins[k].setValue(v)
    p.helper_markers_cb.setChecked(False)
    p.text_edge.setValue(4.0)
    p.chart_text.setText("ChromIQ demo sheet")
    p.chart_text_size.setValue(24.0)
    p.stamp_command.setChecked(False)
    pump(app, 1200)
    tab._generate_btn.click()
    for _ in range(900):
        pump(app, 200)
        if tab._generate_btn.isEnabled() and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 2600)
    print("    built:", bool(getattr(tab, "_margin_tiffs", None)), flush=True)

    rec = {}

    def time_it(tag, n=15):
        ts = []
        for i in range(n):
            # a different margin each turn so nothing is cached
            p.margins["b"].setValue(6.0 + 0.5 * (i % 12))
            app.processEvents()
            t0 = time.perf_counter()
            tab._update_margin_inspector()
            ts.append((time.perf_counter() - t0) * 1000.0)
        rec[tag] = {"median_ms": round(statistics.median(ts), 1),
                    "max_ms": round(max(ts), 1),
                    "min_ms": round(min(ts), 1)}
        print(f"  {tag:44} median {rec[tag]['median_ms']:6.1f} ms  "
              f"max {rec[tag]['max_ms']:6.1f} ms", flush=True)

    for mode, idx in (("patch size first", 0), ("chart area first", 1)):
        p.layout_mode.setCurrentIndex(idx)
        pump(app, 600)
        p.chart_text_size.setValue(24.0)
        pump(app, 400)
        time_it(f"{mode}, 24 pt (the warning is up in area-first)")
        p.chart_text.setText("")
        pump(app, 400)
        time_it(f"{mode}, no sheet text")
        p.chart_text.setText("ChromIQ demo sheet")
        p.chart_text_size.setValue(72.0)
        pump(app, 400)
        time_it(f"{mode}, 72 pt (the worst wording)")
        p.chart_text_size.setValue(24.0)

    # and the "no margin clears it" branch, which walks every larger paper
    p.layout_mode.setCurrentIndex(1)
    p.chart_text_size.setValue(72.0)
    p.margins["b"].setValue(59.5)
    pump(app, 900)
    a, over = TabChart._engine_text_notes(tab)
    rec["ceiling_notice"] = [s for s in over if "No bottom margin" in s]
    t0 = time.perf_counter()
    TabChart._engine_text_notes(tab)
    rec["ceiling_branch_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
    print(f"  the 'no margin clears it' branch: "
          f"{rec['ceiling_branch_ms']} ms, notice "
          f"{'yes' if rec['ceiling_notice'] else 'no'}", flush=True)

    (out / "adv23f.json").write_text(json.dumps(rec, indent=2,
                                                ensure_ascii=False),
                                     encoding="utf-8")
    win.close()
    pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
