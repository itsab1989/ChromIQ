#!/usr/bin/env python3
"""Does a project's stored Guided instrument survive opening another project?

The report (Basti, 2026-09-08): a chart built for the CR30 comes back with
Guided showing **ColorMunki, double density**. Reproduced from his own project
by `drive_youtube_cr30_shows_colormunki.py`; his `meta.json` says
``guided.instrument = "CM"`` while the ``.ti2`` and the ``channels.json`` beside
it both say ``CR30``.

His log shows the shape of it, and it is not the build:

    11:04:56  chart build (Generate Chart) in guided: engine kwargs
              {'instrument': 'CR30', ...}          <- the build used CR30
    11:04:57  create-chart settings written for run1 (40 parameters + ui state)
    11:05:08  Opened nested project at: .../CR30-Test
    11:05:08  create-chart settings written for run1  <- 0.1 s after an OPEN
    ...
    13:55:37  Opened nested project at: .../Youtube
    13:55:38  create-chart settings written for run1  <- again, 0.14 s

So OPENING a project writes to it. This script asks the only question that
matters about that: after building for one instrument in project A, does
visiting project B and coming back leave A still saying A's instrument?

It builds real charts through the real widgets, so it needs the layout engine
and a few seconds per build. Everything happens in a sandbox: a throwaway
settings `.ini` and a throwaway ChromIQ root. Nothing of the user's is touched.

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-leak.ini \
        python scripts/drive_guided_instrument_leaks_between_projects.py
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
from PyQt6.QtGui import QFontDatabase                           # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from core.resource_path import resource_path                    # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"
SHOTS = Path.home() / "Desktop" / "guided-instrument-leak"


def pump(app, ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def shot(w, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    w.grab().save(str(SHOTS / f"{name}.png"))
    print(f"        saved {name}.png")


def _stored(work: Path, name: str) -> dict:
    """The Guided row a project has on disk, plus what its chart really is."""
    proj = work / name
    run = next((proj / "runs").iterdir())
    meta = json.loads((run / "meta.json").read_text(encoding="utf-8"))
    ui = meta.get("create_chart_ui", {})
    ti2 = next(run.glob("*.ti2"), None)
    real = None
    if ti2 is not None:
        import re
        m = re.search(r'^TARGET_INSTRUMENT\s+"([^"]*)"', ti2.read_text(
            "latin-1", errors="ignore"), re.M)
        real = m.group(1) if m else None
    return {
        "guided_instrument": ui.get("guided", {}).get("instrument"),
        "guided_dd": ui.get("guided", {}).get("double_density"),
        "engine_recipe_instrument": (ui.get("engine_recipe") or {}).get("instrument"),
        "meta_instrument": meta.get("instrument"),
        "chart_TARGET_INSTRUMENT": real,
        "mode": ui.get("mode"),
    }


def _report(tag: str, st: dict) -> None:
    print(f"        {tag:<28} guided={st['guided_instrument']!r:<7} "
          f"dd={str(st['guided_dd']):<5} "
          f"engine_recipe={st['engine_recipe_instrument']!r:<7} "
          f"chart={st['chart_TARGET_INSTRUMENT']!r}")


def run(app) -> int:
    from core.settings import AppSettings

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq-leak-"))
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
    settings.set("use_chromiq_layout_engine", True)
    print(f"    sandbox: {sandbox}")

    QDialog.exec = lambda self: 1                      # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    TabChart._confirm_displacing_results = lambda self, *a, **k: True

    win = MainWindow(settings)
    win.show()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 600)
    tab._user_switch_mode("guided")
    pump(app, 1200)

    def build(name: str, instr: str, pages: int = 1) -> None:
        """Type a name, pick an instrument in GUIDED, press Generate."""
        # A NEW project, so start the tab from nothing: with a project open the
        # name box is the open project's identity and typing over it renames
        # rather than creating (the guard `_name_needs_asking` relies on).
        tab._file_mgr.start_new_project(name)
        for edit in (getattr(tab, "_manual_target_name_edit", None),
                     getattr(tab, "_target_name_edit", None)):
            if edit is not None:
                edit.setText(name)
        pump(app, 400)
        idx = tab._instr_combo.findData(instr)
        assert idx >= 0, f"{instr} is not offered in Guided"
        tab._instr_combo.setCurrentIndex(idx)
        tab._instr_combo.currentIndexChanged.emit(idx)
        pump(app, 500)
        # Guided decides the patch count itself; `pages` is the only knob.
        tab._pages_spin.setValue(pages)
        pump(app, 300)
        print(f"        Guided instrument combo now "
              f"{tab._instr_combo.currentData()!r}, pressing Generate")
        tab._margin_ti2 = None
        tab._on_generate()
        for _ in range(240):
            pump(app, 250)
            if getattr(tab, "_margin_ti2", None):
                break
        pump(app, 1500)
        built = getattr(tab, "_margin_ti2", None)
        print(f"        built -> {built}")
        assert built, f"{name}: nothing was built"
        assert Path(built).parents[2].name == name, (
            f"{name}: the chart landed in {Path(built).parents[2].name!r} "
            "instead — the typed name was not adopted")

    print("\n    STEP 1 — build a CR30 chart in Guided, project 'A-CR30'")
    build("A-CR30", "CR30")
    a_after_build = _stored(work, "A-CR30")
    _report("A right after its build", a_after_build)
    shot(win, "01-A-just-built-for-CR30")

    print("\n    STEP 2 — a second project, so the tab has somewhere else to be")
    b_after_build = {"guided_instrument": None, "engine_recipe_instrument": None,
                     "chart_TARGET_INSTRUMENT": None, "guided_dd": None}
    try:
        build("B-CM", "CM")
        b_after_build = _stored(work, "B-CM")
        _report("B right after its build", b_after_build)
    except AssertionError as exc:
        print(f"        (skipped: {exc})")
    a_after_b = _stored(work, "A-CR30")
    _report("A, meanwhile", a_after_b)

    print("\n    STEP 3 — open A again, the way the Open button opens it")
    tab.open_project_manifest(work / "A-CR30" / "project.json")
    pump(app, 3000)
    a_after_reopen = _stored(work, "A-CR30")
    _report("A after reopening it", a_after_reopen)
    print(f"        Guided combo on screen now: "
          f"{tab._instr_combo.currentData()!r}  "
          f"(double density ticked: {tab._dd_check.isChecked()})")
    shot(win, "02-A-after-reopening")

    print("\n    VERDICT")
    bad = 0
    for tag, st in (("after its own build", a_after_build),
                    ("while B was built", a_after_b),
                    ("after reopening", a_after_reopen)):
        ok = st["guided_instrument"] == "CR30"
        print(f"        A's stored Guided instrument {tag:<22} "
              f"{st['guided_instrument']!r:<7} {'OK' if ok else '<<< WRONG'}")
        bad += 0 if ok else 1
    on_screen = tab._instr_combo.currentData()
    if on_screen != "CR30":
        print(f"        and the panel shows {on_screen!r} for a CR30 chart"
              "   <<< the reported symptom")
        bad += 1

    (SHOTS if SHOTS.exists() else Path(tempfile.mkdtemp())).mkdir(
        parents=True, exist_ok=True)
    (SHOTS / "leak-report.json").write_text(json.dumps({
        "A_after_build": a_after_build, "B_after_build": b_after_build,
        "A_while_B_built": a_after_b, "A_after_reopen": a_after_reopen,
        "panel_after_reopen": on_screen,
    }, indent=1), encoding="utf-8")
    win.close()
    pump(app, 400)
    print(f"\n    report: {SHOTS / 'leak-report.json'}")
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
