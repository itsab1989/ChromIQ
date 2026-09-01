#!/usr/bin/env python3
"""Knut's journey and the from-scratch journey, driven in the REAL window.

Knut, 4.1.5-beta.5: *"Loaded a colormunki preset, 84 patches. Then changed
instrument to CR30. The Create Layout parameter then changed from 'Prioritise
patch area…' to 'Prioritise patch size...'. Generate Chart then changed
appearance (much smaller patches)..."*

Basti's ruling, 2026-09-02: keep the instrument defaults, do not apply them to a
preset. This walks both halves of that on screen:

  A  a ColorMunki A4-84p built-in preset, then the instrument changed to CR30
  B  the same journey with the fix disabled — what Knut actually saw
  C  Create Chart opened from scratch, instrument changed to CR30
  D  from scratch: i1 → CR30 → i1, proving the spacer restore still fires

Sandboxed by ``CHROMIQ_SETTINGS_FILE`` / ``CHROMIQ_PRESETS_DIR``, which must
already be exported, and the .ini must already name a ``custom_output_path`` —
otherwise the app falls back to the owner's real ``~/ChromIQ``.

    export CHROMIQ_SETTINGS_FILE=/tmp/cr30.ini
    export CHROMIQ_PRESETS_DIR=/tmp/cr30-presets
    python scripts/drive_cr30_default_vs_preset.py --out <dir>
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtGui import QFontDatabase                           # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from core.resource_path import resource_path                    # noqa: E402

CM84 = ("__chromiq_knut_cm_a4_84p_1page_portrait_w26_0mm_fast_reading_"
        "speed_hand_held__")

facts: list = []


def pump(app, ms: int) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def shot(widget, path: Path) -> None:
    ok = widget.grab().save(str(path))
    print(f"    {'saved' if ok else 'FAILED'}  {path.name}")


def read(panel) -> dict:
    """What is on screen, in the words the panel shows and the recipe it hands
    the builder."""
    r = panel.get_recipe()
    return {
        "Create layout (shown)": panel.layout_mode.currentText(),
        "layout_mode": r.layout_mode,
        "area_method": r.area_method,
        "grid": f"{r.area_cols} x {r.area_rows}",
        "Spacers (shown)": panel.spacer_mode.currentText(),
        "spacer_mode": r.spacer_mode,
        "instrument": r.instrument,
        "paper": r.paper,
        "layout_explicit": r.layout_explicit,
    }


def patch_mm(panel, instrument: str) -> tuple:
    from workflow.layout_engine import instruments
    r = panel.get_recipe()
    g = instruments.geom_from_build_kwargs(
        {**r.build_kwargs(), "instrument": instrument, "paper": r.paper})
    return round(g.pwid, 2), round(g.plen, 2)


def built_charts(root) -> dict:
    """What is on the sheets, read from each chart's own recorded layout.

    Patch sizes are stored in PIXELS, so they are converted with the chart's own
    dpi — the numbers Knut's report is about are millimetres on paper.
    """
    out = {}
    for cj in sorted(Path(root).rglob("*.channels.json")):
        try:
            d = json.loads(cj.read_text())
        except Exception:      # noqa: BLE001 — a bad sidecar is not the subject
            continue
        lay = d.get("layout") or {}
        pats = lay.get("patches") or []
        rec = lay.get("recipe") or {}
        dpi = float(lay.get("dpi") or rec.get("dpi") or 200)
        mm = (lambda px: round(float(px) / dpi * 25.4, 2))
        out[str(Path(cj).relative_to(root))] = {
            "patches": len(pats),
            "grid": f"{rec.get('area_cols')} x {rec.get('area_rows')}",
            "layout_mode": rec.get("layout_mode"),
            "spacer_mode": rec.get("spacer_mode"),
            "instrument": rec.get("instrument"),
            "patch mm": (mm(pats[0]["w"]), mm(pats[0]["h"])) if pats else None,
        }
    return out


def note(title: str, data: dict) -> None:
    facts.append((title, data))
    print(f"  {title}")
    for k, v in data.items():
        print(f"      {k:24} {v}")


def open_chart_tab(app, settings, width=1700, height=1050):
    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(width, height)
    win.show()
    pump(app, 2500)
    tab = win._tab_chart
    tab._switch_mode("manual")
    pump(app, 1200)
    return win, tab


def main() -> int:
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else Path.home() / "Desktop" / "beta7" / "cr30-default-proof"
    out.mkdir(parents=True, exist_ok=True)

    ini = os.environ.get("CHROMIQ_SETTINGS_FILE")
    if not ini:
        print("REFUSING TO RUN: CHROMIQ_SETTINGS_FILE is not set — this driver "
              "would write into the owner's real preferences.")
        return 2
    print(f"settings sandbox : {ini}")
    print(f"presets sandbox  : {os.environ.get('CHROMIQ_PRESETS_DIR')}")

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)

    from core.settings import AppSettings
    settings = AppSettings()
    print(f"custom_output_path: {settings.get('custom_output_path', '')!r}")
    if not str(settings.get("custom_output_path", "")).startswith("/tmp/"):
        print("REFUSING TO RUN: the sandboxed .ini has no /tmp output path, so "
              "projects would land in the owner's real ~/ChromIQ.")
        return 2
    settings.set("use_chromiq_layout_engine", True)

    # No modal may block a driver: a blocked driver gets clicked by a human and
    # everything after that point is human-assisted, not proof.
    QDialog.exec = lambda self: 1                      # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    # ---------------------------------------------------------------- A
    print("\nA — Knut's journey, with the fix")
    win, tab = open_chart_tab(app, settings)
    tab._manual_target_name_edit.setText("CR30-Proof-Preset")
    tab._mark_name_typed_by_user()
    pump(app, 400)
    panel = tab._manual_layout_panel

    # Two clicks: open the presets dropdown and choose the ColorMunki 84p.
    idx = tab._preset_combo.findData(CM84)
    assert idx >= 0, "the ColorMunki A4-84p built-in is not in the dropdown"
    tab._preset_combo.setCurrentIndex(idx)
    tab._on_preset_activated(idx)
    for _ in range(60):                       # printtarg runs out of process
        pump(app, 500)
        if not tab._runner.is_running:
            break
    pump(app, 1500)
    note("A1  the preset, just loaded", read(panel))
    facts[-1][1]["patch size mm (CM)"] = patch_mm(panel, "CM")
    shot(panel, out / "A1-preset-loaded-panel.png")
    shot(win, out / "A1-preset-loaded-window.png")

    # The third click: the instrument.
    panel.instr.setCurrentIndex(panel.instr.findData("CR30"))
    pump(app, 1500)
    note("A2  after changing the instrument to CR30", read(panel))
    facts[-1][1]["patch size mm (CR30)"] = patch_mm(panel, "CR30")
    shot(panel, out / "A2-after-cr30-panel.png")
    shot(win, out / "A2-after-cr30-window.png")

    # …and Generate Chart, which is where Knut saw it.
    #
    # NO RENAME HERE. Typing a new project name is a TARGET CHANGE, and §2 of
    # `per_target_settings.md` says a target change loads that target's stored
    # settings — which put the ColorMunki straight back over the CR30 the panel
    # was showing. Measured: `load_target_settings ← _apply_ui_state` wrote the
    # panel twice between the instrument change and the build. Correct
    # behaviour, and not Knut's journey: he changed the instrument and pressed
    # Generate.
    tab._on_generate()
    for _ in range(80):
        pump(app, 500)
        if not tab._runner.is_running:
            break
    pump(app, 2500)
    shot(win, out / "A3-generated-window.png")
    shot(tab._preview, out / "A3-generated-preview.png")
    note("A3  the chart actually built",
         built_charts(settings.get("custom_output_path")))
    win.close()
    pump(app, 800)

    # ---------------------------------------------------------------- B
    print("\nB — the same journey with the fix disabled (what Knut saw)")
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    real_may_default = LayoutOptionsPanel._may_default
    LayoutOptionsPanel._may_default = lambda self, f: True   # the old code
    try:
        win2, tab2 = open_chart_tab(app, settings)
        tab2._manual_target_name_edit.setText("CR30-Proof-Old")
        tab2._mark_name_typed_by_user()
        p2 = tab2._manual_layout_panel
        i2 = tab2._preset_combo.findData(CM84)
        tab2._preset_combo.setCurrentIndex(i2)
        tab2._on_preset_activated(i2)
        for _ in range(60):
            pump(app, 500)
            if not tab2._runner.is_running:
                break
        pump(app, 1500)
        note("B1  the preset, just loaded (fix disabled)", read(p2))
        p2.instr.setCurrentIndex(p2.instr.findData("CR30"))
        pump(app, 1500)
        note("B2  after changing the instrument (fix disabled)", read(p2))
        facts[-1][1]["patch size mm (CR30)"] = patch_mm(p2, "CR30")
        shot(p2, out / "B2-old-behaviour-panel.png")
        shot(win2, out / "B2-old-behaviour-window.png")
        tab2._on_generate()
        for _ in range(80):
            pump(app, 500)
            if not tab2._runner.is_running:
                break
        pump(app, 2500)
        note("B3  the chart the old code built",
             built_charts(settings.get("custom_output_path")))
        shot(win2, out / "B3-old-behaviour-generated-window.png")
        shot(tab2._preview, out / "B3-old-behaviour-preview.png")
        win2.close()
        pump(app, 800)
    finally:
        LayoutOptionsPanel._may_default = real_may_default

    # ---------------------------------------------------------------- C
    print("\nC — from scratch, the CR30 default must survive")
    win3, tab3 = open_chart_tab(app, settings)
    p3 = tab3._manual_layout_panel
    note("C1  Create Chart, opened on nothing", read(p3))
    shot(p3, out / "C1-from-scratch-panel.png")
    p3.instr.setCurrentIndex(p3.instr.findData("CR30"))
    pump(app, 1500)
    note("C2  from scratch, instrument changed to CR30", read(p3))
    facts[-1][1]["patch size mm (CR30)"] = patch_mm(p3, "CR30")
    shot(p3, out / "C2-from-scratch-cr30-panel.png")
    shot(win3, out / "C2-from-scratch-cr30-window.png")

    # ---------------------------------------------------------------- D
    print("\nD — from scratch: the leftover spacers are still restored")
    p3.instr.setCurrentIndex(p3.instr.findData("i1"))
    pump(app, 1200)
    note("D1  back to an i1Pro after a CR30", read(p3))
    shot(p3, out / "D1-spacers-restored-panel.png")
    win3.close()
    pump(app, 800)

    (out / "facts.json").write_text(
        json.dumps([{"step": t, **d} for t, d in facts], indent=2, default=str),
        encoding="utf-8")
    print(f"\nShots and facts: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
