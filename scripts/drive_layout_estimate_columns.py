#!/usr/bin/env python3
"""The Chart-layout-information panel's two columns, audited in the REAL window.

Basti, 4.1.5-beta.11: loading Knut's ``CR30-A4-360p-1page-Portrait-w11.0mm``
made the panel read *on screen 360, estimate 192*; loading the 192-patch preset
next made it read *on screen 192, estimate 360* — each column describing the
other preset's chart. The estimate also claimed **8** strips while the panel's
own "Strips (columns)" control said **15**.

This walks the journey he walked, in the real window, with his real presets
(copied into a sandbox — his folder is never written to), and prints the whole
two-column table at every step so both columns can be judged together:

  1  Manual, nothing generated
  2  select the 192-patch preset      (auto_run generates)
  3  select the 360-patch preset      → his first report
  4  select the 192-patch preset      → his second report (the "swap")
  5  press Generate again, nothing changed
  6  change a control by hand (strips 15 → 12)
  7  Auto patch count ON, then OFF
  8  switch to Guided, then back to Manual
  9  change the instrument, then the paper

Sandboxed by ``CHROMIQ_SETTINGS_FILE`` / ``CHROMIQ_PRESETS_DIR``, which must
already be exported, and the .ini must already name a ``custom_output_path``
under /tmp — otherwise the app writes into the owner's real ~/ChromIQ.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-cs.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-cs-presets
    python scripts/drive_layout_estimate_columns.py --out <dir>
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

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtGui import QFontDatabase                           # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from core.resource_path import resource_path                    # noqa: E402

PRESET_SRC = Path("/Users/Basti/Desktop/beta 9/knut-cr30-presets")
P360 = "CR30-A4-360p-1page-Portrait-w11.0mm"
P192 = "CR30-A4-192p-1page-Portrait-w11.0mm"

ROWS = ("total", "fillup", "page_patches", "rows", "cols", "pages",
        "patch", "pitch")
ROW_LABEL = {
    "total": "Total patches",
    "fillup": "… of those, fill-up",
    "page_patches": "Patches (this page)",
    "rows": "Patches per strip",
    "cols": "Strips (this page)",
    "pages": "Pages",
    "patch": "Patch size (mm)",
    "pitch": "Row pitch (mm)",
}

stages: list[tuple[str, dict]] = []


def pump(app, ms: int) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def wait_idle(app, tab, seconds: int = 90) -> None:
    for _ in range(seconds * 2):
        pump(app, 500)
        if not tab._runner.is_running:
            break
    pump(app, 1800)


def shot(widget, path: Path) -> None:
    ok = widget.grab().save(str(path))
    print(f"      {'saved ' if ok else 'FAILED'} {path.name}")


def controls(tab) -> dict:
    """What the panel's own controls say — the settings the estimate claims to
    describe."""
    try:
        r = tab._current_layout_recipe()
    except Exception as exc:                       # noqa: BLE001
        return {"error": repr(exc)}
    auto = getattr(tab, "_manual_auto_patches_check", None)
    return {
        "instrument": r.instrument,
        "paper": r.paper,
        "layout_mode": r.layout_mode,
        "area_method": r.area_method,
        "strips (columns)": r.area_cols,
        "patches per strip (rows)": r.area_rows,
        "auto patch count": bool(auto is not None and auto.isChecked()),
        "mode": tab._current_mode(),
    }


def read_panel(tab) -> dict:
    p = tab._layout_info_panel
    return {
        "on screen": {k: p._actual_labels[k].text() for k in ROWS},
        "estimate": {k: p._estimate_labels[k].text() for k in ROWS},
    }


def capture(app, tab, win, out: Path, key: str, title: str) -> None:
    pump(app, 400)
    data = read_panel(tab)
    ctl = controls(tab)
    ti2 = getattr(tab, "_margin_ti2", None)
    print(f"\n  {key}  {title}")
    for k, v in ctl.items():
        print(f"      {k:26} {v}")
    print(f"      {'chart on screen (.ti2)':26} {Path(ti2).name if ti2 else None}")
    print(f"      {'row':<22}{'on screen':>12}{'estimate':>12}")
    for r in ROWS:
        a, e = data["on screen"][r], data["estimate"][r]
        flag = "   <-- differ" if a != e and a != "—" and e != "—" else ""
        print(f"      {ROW_LABEL[r]:<22}{a:>12}{e:>12}{flag}")
    sys.stdout.flush()
    shot(win, out / f"{key}-window.png")
    shot(tab._layout_info_panel, out / f"{key}-info-panel.png")
    if getattr(tab, "_manual_layout_panel", None) is not None:
        shot(tab._manual_layout_panel, out / f"{key}-controls.png")
    stages.append((key, {"title": title, "controls": ctl,
                         "ti2": Path(ti2).name if ti2 else None, **data}))


def install_presets(dest_root: Path) -> None:
    """Copy Knut's presets into the sandbox. HIS FOLDER IS READ, NEVER WRITTEN."""
    d = dest_root / "Create Chart"
    d.mkdir(parents=True, exist_ok=True)
    for name in (P360, P192):
        for ext in (".json", ".ti1"):
            src = PRESET_SRC / f"{name}{ext}"
            if not src.is_file():
                raise SystemExit(f"missing preset file: {src}")
            shutil.copy2(src, d / f"{name}{ext}")
    print(f"presets copied into {d}")


def pick_preset(app, tab, name: str) -> None:
    idx = tab._preset_combo.findData(name)
    assert idx >= 0, f"{name} is not in the presets dropdown"
    tab._preset_combo.setCurrentIndex(idx)
    tab._on_preset_activated(idx)
    wait_idle(app, tab)


def main() -> int:
    out = (Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv
           else Path.home() / "Desktop" / "beta 9" / "layout-estimate-column")
    out.mkdir(parents=True, exist_ok=True)

    ini = os.environ.get("CHROMIQ_SETTINGS_FILE")
    if not ini:
        print("REFUSING TO RUN: CHROMIQ_SETTINGS_FILE is not set — this driver "
              "would write into the owner's real preferences.")
        return 2
    pdir = os.environ.get("CHROMIQ_PRESETS_DIR")
    if not pdir:
        print("REFUSING TO RUN: CHROMIQ_PRESETS_DIR is not set — this driver "
              "would write into the owner's real preset folder.")
        return 2
    print(f"settings sandbox : {ini}")
    print(f"presets sandbox  : {pdir}")
    install_presets(Path(pdir))

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
    settings.set("layout_info_show", True)

    # No modal may block a driver: a blocked driver gets clicked by a human and
    # everything after that point is human-assisted, not proof.
    QDialog.exec = lambda self: 1                      # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1750, 1080)
    win.show()
    pump(app, 2500)
    tab = win._tab_chart
    tab._switch_mode("manual")
    pump(app, 1200)
    tab._manual_target_name_edit.setText("CS-Estimate-Audit")
    tab._mark_name_typed_by_user()
    pump(app, 600)

    capture(app, tab, win, out, "S1", "Manual, nothing generated yet")

    print("\n=== 2  select the 192-patch preset (auto_run generates) ===")
    pick_preset(app, tab, P192)
    capture(app, tab, win, out, "S2", f"after selecting {P192}")

    print("\n=== 3  select the 360-patch preset — Basti's first report ===")
    pick_preset(app, tab, P360)
    capture(app, tab, win, out, "S3", f"after selecting {P360}")

    print("\n=== 4  select the 192-patch preset again — the 'swap' ===")
    pick_preset(app, tab, P192)
    capture(app, tab, win, out, "S4", f"after selecting {P192} again")

    print("\n=== 5  press Generate again, nothing changed ===")
    tab._on_generate()
    wait_idle(app, tab)
    capture(app, tab, win, out, "S5", "after pressing Generate with nothing changed")

    print("\n=== 6  change a control by hand: strips 15 -> 12 ===")
    panel = tab._manual_layout_panel
    if panel is not None and getattr(panel, "area_cols", None) is not None:
        panel.area_cols.setValue(12)
        pump(app, 1500)
    capture(app, tab, win, out, "S6", "strips (columns) changed by hand to 12")

    if panel is not None and getattr(panel, "area_cols", None) is not None:
        panel.area_cols.setValue(15)
        pump(app, 1200)

    print("\n=== 7  Auto patch count ON, then OFF ===")
    auto = getattr(tab, "_manual_auto_patches_check", None)
    if auto is not None:
        auto.setChecked(True)
        pump(app, 1500)
        capture(app, tab, win, out, "S7a", "Auto patch count ON")
        auto.setChecked(False)
        pump(app, 1500)
        capture(app, tab, win, out, "S7b", "Auto patch count back OFF")

    print("\n=== 8  Guided, then back to Manual ===")
    tab._switch_mode("guided")
    pump(app, 2000)
    capture(app, tab, win, out, "S8a", "switched to Guided")
    tab._switch_mode("manual")
    pump(app, 2000)
    capture(app, tab, win, out, "S8b", "switched back to Manual")

    print("\n=== 9  instrument, then paper ===")
    if panel is not None and panel.instr is not None:
        j = panel.instr.findData("i1")
        if j >= 0:
            panel.instr.setCurrentIndex(j)
            pump(app, 1800)
            capture(app, tab, win, out, "S9a", "instrument changed to i1")
        j = panel.instr.findData("CR30")
        if j >= 0:
            panel.instr.setCurrentIndex(j)
            pump(app, 1500)
    if panel is not None and panel.paper is not None:
        j = panel.paper.findData("Letter")
        if j >= 0:
            panel.paper.setCurrentIndex(j)
            pump(app, 1800)
            capture(app, tab, win, out, "S9b", "paper changed to Letter")

    (out / "stages.json").write_text(
        json.dumps([{"key": k, **v} for k, v in stages], indent=2),
        encoding="utf-8")
    print(f"\nwrote {out / 'stages.json'}")
    win.close()
    pump(app, 800)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
