#!/usr/bin/env python3
"""Knut's beta-21 report, driven: his chart warns on CR30 and says nothing on
SpectroScan.

> *"Using this chart, there is a warning message for overlapping strip labels
> for the CR30, but if you change instrument to SpectroScan, there is no
> warning. All the warnings for the label overlapping, row indicator
> overlapping, or clip-border text overlapping, or bottom text overlapping,
> they should all also happen for the SpectroScan instrument."*

His `meta.json` carries the whole `create_chart_ui.engine_recipe`, and his
`test.ti1` carries the 648 patches, so this is HIS chart rather than one shaped
like it: the recipe goes into the real Manual panel through `set_recipe` and is
READ BACK field by field before anything is judged, and the .ti1 is armed as a
fixed patch set so Generate lays out his patches instead of making new ones.

Run it twice over: once as he saved it (CR30) and once with the instrument
pulldown moved to SpectroScan, with a Generate Chart in between so that the
"Measured from Preview" numbers every notice now reads describe the sheet on
screen.
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
from PyQt6.QtWidgets import (QApplication, QDialog,       # noqa: E402
                             QMessageBox, QAbstractScrollArea)
from onscreen_capture import capture_window                # noqa: E402

CHART = Path.home() / "Desktop/ChromIQ-beta22-proof/knut-chart-warnings/chart"


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.005)


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert os.environ.get("QT_QPA_PLATFORM") != "offscreen", "ON SCREEN"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    rec_d = json.loads((CHART / "meta.json").read_text(encoding="utf-8"))["create_chart_ui"]["engine_recipe"]

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-b22-knut-"))
    settings = AppSettings()
    for k, v in (("custom_output_path", str(work)), ("language", "en"),
                 ("use_chromiq_layout_engine", True),
                 ("restore_last_session", False), ("appearance", "dark"),
                 ("margin_inspector_show", True),
                 ("auto_update_preview",
                  os.environ.get("B22_AUTO_PREVIEW") == "1")):
        settings.set(k, v)
    QDialog.exec = lambda self: 1                    # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore
    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    from ui.theme import apply_appearance
    from workflow.layout_engine.presets import LayoutRecipe
    TabChart._confirm_displacing_results = lambda self, *a, **k: True
    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.resize(1680, 1100)
    win.show()
    win.raise_()
    pump(app, 2400)
    print("    window on screen:", win.isVisible(), flush=True)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 800)
    tab._user_switch_mode("manual")
    pump(app, 1500)
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("knut-b22")
    pump(app, 400)
    p = tab._manual_layout_panel

    # ---- HIS RECIPE, LOADED AND THEN READ BACK -----------------------------
    p.set_recipe(LayoutRecipe.from_dict(rec_d))
    pump(app, 2000)
    back = tab._current_layout_recipe()
    drift = {}
    for k, v in sorted(rec_d.items()):
        got = getattr(back, k, "<no such field>")
        same = (got == v) or (isinstance(v, float) and isinstance(got, (int, float))
                              and abs(float(got) - v) < 1e-6)
        print(f"      {k:28s} asked={v!r:28.28} panel={got!r:28.28} {'ok' if same else 'DRIFT'}",
              flush=True)
        if not same:
            drift[k] = {"asked": v, "panel": got}
    print("    fields that did not come back:", len(drift), flush=True)

    # HIS 648 PATCHES, not a fresh targen set.
    tab._preset_ti1_path = CHART / "test.ti1"
    tab._preset_ti1_targen_sig = None
    pump(app, 500)
    print("    armed patch set:", tab._pending_patch_set_total(), flush=True)

    def build_and_read(tag: str) -> dict:
        tab._generate_btn.click()
        for _ in range(1200):
            pump(app, 200)
            if tab._generate_btn.isEnabled() and getattr(tab, "_margin_tiffs", None):
                break
        pump(app, 3000)
        warns, over = TabChart._engine_text_notes(
            tab, getattr(tab, "_margin_report", None))
        mp = getattr(tab, "_margin_panel", None)
        panel_text = mp._status.text() if mp is not None else ""
        rep = getattr(tab, "_margin_report", None)
        meas = ({"left": rep.left_mm, "right": rep.right_mm, "top": rep.top_mm,
                 "bottom": rep.bottom_mm, "page": (rep.page_w_mm, rep.page_h_mm)}
                if rep is not None else None)
        r_used = TabChart._notice_layout_recipe(tab)
        print(f"    [{tag}] built:", bool(getattr(tab, "_margin_tiffs", None)),
              " instrument in the panel:", p.instr.currentData(),
              " recipe the notices judge:", getattr(r_used, "instrument", None),
              flush=True)
        print(f"    [{tag}] measured from preview:", meas, flush=True)
        print(f"    [{tag}] notices: {len(warns)} in the ⓘ, {len(over)} in red",
              flush=True)
        for i, s in enumerate(over):
            print(f"        red {i+1}: {s[:200]}", flush=True)
        for i, s in enumerate(warns):
            print(f"        info {i+1}: {s[:160]}", flush=True)
        return {"instrument": p.instr.currentData(),
                "judged_recipe_instrument": getattr(r_used, "instrument", None),
                "measured": meas, "warns": warns, "over": over,
                "panel_text": panel_text}

    a = build_and_read("CR30")
    ok1, why1 = capture_window(win, out / "W1-CR30-the-warning-is-there.png")

    # ---- THE ONE CHANGE HE MAKES: the instrument pulldown ------------------
    p.instr.setCurrentIndex(p.instr.findData("SS"))
    pump(app, 2500)
    print("    instrument now:", p.instr.currentData(), flush=True)
    # …AND READ THE PANEL BEFORE ANY GENERATE, which is what he sees: he moved
    # one pulldown, he did not rebuild the sheet.
    _live = tab._current_layout_recipe()
    print("    [SS, NO Generate] LIVE recipe:",
          {k: getattr(_live, k, None) for k in (
              "instrument", "layout_mode", "use_instrument_margins",
              "margin_top", "text_edge_top_mm", "helper_markers",
              "helper_markers_top_bottom", "helper_marker_edge_mm",
              "helper_marker_len_mm", "show_strip_indicators",
              "indicator_size_mm", "hflag", "clip_border",
              "clip_border_width_mm", "clip_content_mode", "dpi")},
          flush=True)
    print("    [SS, NO Generate] tiffs:", bool(getattr(tab, "_margin_tiffs", None)),
          " ti2:", getattr(tab, "_margin_ti2", None), flush=True)
    _w0, _o0 = TabChart._engine_text_notes(
        tab, getattr(tab, "_margin_report", None))
    _r0 = TabChart._notice_layout_recipe(tab)
    _rep0 = getattr(tab, "_margin_report", None)
    print("    [SS, NO Generate] report present:", _rep0 is not None,
          " recipe judged:", getattr(_r0, "instrument", None),
          " notices:", len(_w0), "/", len(_o0), flush=True)
    for i, s_ in enumerate(_o0):
        print(f"        red {i+1}: {s_[:200]}", flush=True)
    okA, whyA = capture_window(win, out / "W1b-SS-before-any-Generate.png")
    a_nogen = {"report_present": _rep0 is not None,
               "judged_recipe_instrument": getattr(_r0, "instrument", None),
               "warns": _w0, "over": _o0, "captured": okA, "why": whyA}
    b = build_and_read("SS")
    ok2, why2 = capture_window(win, out / "W2-SpectroScan-no-warning.png")
    print("    photographs:", ok1, ok2, why1, why2, flush=True)

    (out / "knut-two-instruments.json").write_text(json.dumps(
        {"recipe_drift": drift, "CR30": a, "SS_before_generate": a_nogen, "SS": b}, indent=2,
        ensure_ascii=False), encoding="utf-8")
    win.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
