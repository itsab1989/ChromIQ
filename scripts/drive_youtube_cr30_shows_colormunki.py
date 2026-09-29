#!/usr/bin/env python3
"""Reproduce, on screen: a CR30 chart whose Guided panel says ColorMunki.

Basti, 2026-09-08: *"i have loaded the youtube project and the chart was made
for the cr30. but in guided mode it shows colormunki with double density
selected. i did not check manual module."*

The project is COPIED into a sandbox ChromIQ root first, and the settings are
redirected, so his own project and his own preferences are never touched. Check
afterwards with

    defaults read com.chromiq.ChromIQ custom_output_path

What this prints, in the order a person would meet it:

1. what the run's files say the chart really is (the .ti2 the engine wrote and
   the channels.json beside it);
2. what the run's meta.json remembers about the Create Chart panel;
3. what the GUIDED panel actually shows once the project is opened the way the
   Open button opens it, read off the live widgets;
4. whether the double-density checkbox is even visible while it is ticked.

Usage::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-yt.ini \
        python scripts/drive_youtube_cr30_shows_colormunki.py [<project dir>]
"""
from __future__ import annotations

import json
import shutil
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
from PyQt6.QtGui import QFontDatabase                           # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from core.resource_path import resource_path                    # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"
SRC_PROJECT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "ChromIQ/youtube"
SHOTS = Path.home() / "Desktop" / "youtube-cr30-repro"


def pump(app, ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def shot(w, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    p = SHOTS / f"{name}.png"
    w.grab().save(str(p))
    print(f"    saved {p.name}")


def _cgats_keywords(path: Path) -> dict:
    import re
    txt = path.read_text("latin-1", errors="ignore")
    return dict(re.findall(r'^([A-Z_0-9]+)\s+"([^"]*)"\s*$', txt, re.M))


def run(app) -> int:
    from core.settings import AppSettings

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq-yt-"))
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

    proj = work / SRC_PROJECT.name
    shutil.copytree(SRC_PROJECT, proj)
    print(f"    sandbox : {sandbox}")
    print(f"    project : copied {SRC_PROJECT} -> {proj}")

    QDialog.exec = lambda self: 1                      # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    # ---- 1. what the chart really is ------------------------------------
    run_dir = next((proj / "runs").iterdir())
    ti2 = next(run_dir.glob("*.ti2"))
    kw = _cgats_keywords(ti2)
    ch = ti2.with_suffix(".channels.json")
    rec = {}
    if ch.is_file():
        rec = (json.loads(ch.read_text(encoding="utf-8"))
               .get("layout", {}).get("recipe") or {})
    print("\n    THE CHART ITSELF (written by whatever built it)")
    print(f"        {ti2.name}  ORIGINATOR        {kw.get('ORIGINATOR')!r}")
    print(f"        {ti2.name}  TARGET_INSTRUMENT {kw.get('TARGET_INSTRUMENT')!r}")
    print(f"        {ti2.name}  HEXAGON_PATCHES   {kw.get('HEXAGON_PATCHES')!r}")
    print(f"        channels.json recipe.instrument {rec.get('instrument')!r}"
          f"   hflag {rec.get('hflag')!r}   cm_density {rec.get('cm_density')!r}")

    # ---- 2. what meta.json remembers about the panel ---------------------
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    ui_state = meta.get("create_chart_ui", {})
    g = ui_state.get("guided", {})
    er = ui_state.get("engine_recipe", {})
    print("\n    WHAT meta.json REMEMBERS ABOUT THE PANEL")
    print(f"        meta.instrument            {meta.get('instrument')!r}"
          "   <- stamped from the .ti2, correct")
    print(f"        create_chart_ui.mode       {ui_state.get('mode')!r}")
    print(f"        guided.instrument          {g.get('instrument')!r}")
    print(f"        guided.double_density      {g.get('double_density')!r}")
    print(f"        engine_on                  {ui_state.get('engine_on')!r}")
    print(f"        engine_recipe.instrument   {er.get('instrument')!r}")
    print(f"        engine_recipe.hflag        {er.get('hflag')!r}")
    print(f"        editor_layout.double_density "
          f"{meta.get('editor_layout', {}).get('double_density')!r}")

    # ---- 3. open it the way the Open button opens it ---------------------
    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.show()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 800)

    tab.open_project_manifest(proj / "project.json")
    pump(app, 2500)

    tab._user_switch_mode("guided")
    pump(app, 1500)

    from data.patch_db import INSTRUMENT_LABELS
    shown_code = tab._instr_combo.currentData()
    shown_text = tab._instr_combo.currentText()
    dd_checked = tab._dd_check.isChecked()
    dd_visible = tab._dd_check.isVisible()
    print("\n    WHAT THE GUIDED PANEL SHOWS, read off the live widgets")
    print(f"        project opened             {tab._file_mgr.get_target_name()!r}")
    print(f"        Instrument combo           {shown_text!r}  (code {shown_code!r})")
    print(f"        Double density ticked      {dd_checked}")
    print(f"        Double density visible     {dd_visible}")
    print(f"        Paper combo                {tab._paper_combo.currentData()!r}")
    print(f"        engine checkbox            "
          f"{bool(settings.get('use_chromiq_layout_engine', False))}")
    shot(win, "01-guided-after-opening-the-project")

    truth = rec.get("instrument") or kw.get("TARGET_INSTRUMENT")
    bad = 0
    if shown_code != "CR30":
        print(f"\n    >>> REPRODUCED: the chart is {truth!r} and Guided shows "
              f"{INSTRUMENT_LABELS.get(shown_code, shown_code)!r}")
        bad += 1
    if dd_checked and shown_code == "CM":
        print("    >>> and double density is ticked, which only a ColorMunki has")
        bad += 1
    if dd_checked and not dd_visible:
        print("    >>> the double-density box is TICKED WHILE HIDDEN")
        bad += 1
    if not bad:
        print("\n    not reproduced: Guided shows the chart's own instrument")

    win.close()
    pump(app, 400)
    print(f"\n    screenshots in {SHOTS}")
    return 1 if bad else 0


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)
    return run(app)


if __name__ == "__main__":
    raise SystemExit(main())
