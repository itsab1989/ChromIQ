#!/usr/bin/env python3
"""Adversary 17d, probe 4: what the two new gates cost per turn of the box.

`_bottom_lever_note(..., lowering_b_clears(r, …), typed_b, markers_off_clears(r, …))`
-- both gates are ARGUMENTS, so Python evaluates both on every refresh that
has an overlap, and `_bottom_lever_note` reads at most ONE of them: branch 1
uses `markers_route_clears`, branches 2 and 3 use `lever_clears`, and a "B"
typed as 0 returns before either is looked at. Each gate is a whole geometry
rebuild (`_bottom_clears_with` -> `geom_from_build_kwargs` +
`predicted_patch_bottom_mm`).

Round 2 measured 16 ms per COLD rebuild and 0.7 ms warm, and the number that
matters is the cold one because every candidate is new on every step. This
times the real panel, stepping the real spin box, against a build with the two
gates stubbed out, on two layouts.
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
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402

PRESET = ("__chromiq_knut_cr30_letter_792p_2pages_portrait"
          "_w11_0mm_hexagonal_straight__")


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents(); time.sleep(0.01)


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert os.environ.get("QT_QPA_PLATFORM") != "offscreen", "ON SCREEN"
    out = Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv17d4-"))
    settings = AppSettings()
    for k, v in (("custom_output_path", str(work)),
                 ("use_chromiq_layout_engine", True),
                 ("restore_last_session", False), ("appearance", "dark"),
                 ("margin_inspector_show", True),
                 ("margin_violation_notify", True)):
        settings.set(k, v)
    QDialog.exec = lambda self: 1                  # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore
    from ui.main_window import MainWindow
    from ui.tabs import tab_chart as tc
    from ui.theme import apply_appearance
    tc.TabChart._confirm_displacing_results = lambda self, *a, **k: True
    apply_appearance(app, None, "dark")
    win = MainWindow(settings); win.resize(1620, 1060)
    win.show(); win.raise_(); pump(app, 2500)
    print(f"    window on screen: {win.isVisible()}", flush=True)
    win._tabs.setCurrentWidget(win._tab_chart); tab = win._tab_chart
    pump(app, 800); tab._user_switch_mode("manual"); pump(app, 1500)
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("test")
    combo = tab._preset_combo
    i = combo.findData(PRESET); assert i >= 0
    combo.setCurrentIndex(i); combo.activated.emit(i); pump(app, 1500)
    for _ in range(400):
        pump(app, 120)
        if getattr(tab, "_margin_ti2", None) and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 800)
    panel = tab._manual_layout_panel
    if panel.use_instr_margins.isChecked():
        panel.use_instr_margins.setChecked(False); pump(app, 400)
    panel.chart_text.setText("test-{project}-page {page}-{paper}")
    j = panel.layout_mode.findData("area_first")
    panel.layout_mode.setCurrentIndex(j)
    panel.chart_text_size.setValue(28.0)
    panel.text_edge.setValue(0.0)          # a typed 0: NEITHER gate is read
    pump(app, 500)

    calls = {"lowering_b": 0, "markers_off": 0}
    real_low, real_mark = tc.lowering_b_clears, tc.markers_off_clears

    def counted_low(*a, **k):
        calls["lowering_b"] += 1; return real_low(*a, **k)

    def counted_mark(*a, **k):
        calls["markers_off"] += 1; return real_mark(*a, **k)

    def step(margins, note=""):
        """One timed pass over a run of DIFFERENT margins (every one cold)."""
        ts = []
        for mb in margins:
            panel.margins["b"].setValue(mb)
            pump(app, 120)
            t0 = time.perf_counter()
            tab._engine_text_notes()
            ts.append((time.perf_counter() - t0) * 1000.0)
        return {"note": note, "n": len(ts),
                "median_ms": round(statistics.median(ts), 1),
                "max_ms": round(max(ts), 1),
                "total_ms": round(sum(ts), 1)}

    margins = [6.0 + 0.5 * k for k in range(20)]
    tc.lowering_b_clears, tc.markers_off_clears = counted_low, counted_mark
    warm = step(margins, "warm-up")
    calls["lowering_b"] = calls["markers_off"] = 0
    with_gates = step([m + 0.1 for m in margins], "both gates live")
    counted = dict(calls)

    tc.lowering_b_clears = lambda *a, **k: True
    tc.markers_off_clears = lambda *a, **k: True
    without = step([m + 0.2 for m in margins], "both gates stubbed")
    tc.lowering_b_clears, tc.markers_off_clears = real_low, real_mark

    res = {"window_on_screen": bool(win.isVisible()),
           "B_typed": panel.text_edge.value(),
           "warm_up": warm,
           "with_the_two_gates": with_gates,
           "with_them_stubbed_out": without,
           "gate_calls_over_20_steps": counted,
           "note": ("B is typed as 0, so `_bottom_lever_note` returns at "
                    "branch 2 and reads NEITHER gate; both were evaluated "
                    "anyway because they are arguments.")}
    res["cost_of_the_two_gates_ms_per_step"] = round(
        with_gates["median_ms"] - without["median_ms"], 1)
    print(json.dumps(res, indent=2), flush=True)
    (out / "adv17d-what-the-two-gates-cost.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8")
    win.close(); pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
