#!/usr/bin/env python3
"""Drive the REAL window: when does the "you have not built this yet" line show?

`docs/design/per_target_settings.md` §2.2, confirmed by Knut Larsson and
Sebastian on 2026-09-10. Selecting a run paints that run's chart over the Create
Chart panel, so a setting changed and not built survives only until the run is
left. Knut asked for *"a red warning text to notify user to click Generate Chart
to apply the change, and changes not applied will be lost when closing project
or changing between runs"*.

The hard part is WHEN it appears, so this walks the eight situations that decide
it and photographs each one:

  1 a freshly opened run with a built chart      2 the user moving one control
  3 pressing Generate Chart                      4 another run, and back
  5 loading a preset                             6 opening a .ti2
  7 a brand new run with nothing built           8 restoring a used chart

Settings, presets and the ChromIQ root are all sandboxed; nothing of the user's
is touched. Check afterwards with

    defaults read com.chromiq.ChromIQ custom_output_path

Usage::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-warn.ini \
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-warn-presets \
        python scripts/drive_the_unapplied_change_warning.py
"""
from __future__ import annotations

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

from PyQt6.QtGui import QFontDatabase                            # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog,               # noqa: E402
                             QMessageBox)

from core.resource_path import resource_path                     # noqa: E402

SHOTS = Path.home() / "Desktop" / "ChromIQ-beta3-proof" / "unapplied-warning"
PATCHES = 40           # small enough that targen is a few seconds
rows: list[tuple] = []
bad = 0
shot_n = 0


def pump(app, ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def build(app, tab, timeout_s=180):
    """Press Generate Chart and wait for it to come back."""
    tab._on_generate()
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.02)
        if tab._generate_btn.isEnabled() and not tab._runner.is_running:
            pump(app, 900)
            if tab._generate_btn.isEnabled() and not tab._runner.is_running:
                return True
    return False


def showing(tab) -> bool:
    # isHidden, not isVisible: the answer must be "was it set visible", and on
    # a window that is up they agree.
    return not tab._unapplied_lbl.isHidden()


def note(app, win, tab, name, expected, why):
    """Photograph the situation and record expected vs. actual."""
    global bad, shot_n
    shot_n += 1
    got = showing(tab)
    SHOTS.mkdir(parents=True, exist_ok=True)
    slug = name.lower().replace(" ", "-").replace(",", "").replace("'", "")
    win.grab().save(str(SHOTS / f"{shot_n:02d}-{slug}.png"))
    ok = got == expected
    if not ok:
        bad += 1
    rows.append((shot_n, name, expected, got, ok, why))
    print(f"  {shot_n:02d} {name:<44} expected {'SHOWS' if expected else 'quiet':<5} "
          f"got {'SHOWS' if got else 'quiet':<5} {'ok' if ok else '<<< DIFFERS'}")


def run(app) -> int:
    from core.settings import AppSettings

    sb = Path(tempfile.mkdtemp(prefix="chromiq-warn-"))
    s = AppSettings()
    work = sb / "ChromIQ"
    work.mkdir()
    s.set("custom_output_path", str(work))
    s.set("restore_last_session", False)
    s.set("use_chromiq_layout_engine", True)
    s.set("auto_update_preview", False)   # one variable at a time

    QDialog.exec = lambda self: 1                  # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    TabChart._confirm_displacing_results = lambda self, *a, **k: True
    TabChart._prompt_target_name = lambda self, *a, **k: "Warn-Demo"
    TabChart._maybe_warn_partial_last_page = lambda self, *a, **k: None

    win = MainWindow(s)
    win.show()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 800)
    tab._user_switch_mode("manual")
    pump(app, 800)
    tab._target_name_edit.setText("Warn-Demo")
    tab._set_manual_value("targen", "-f", PATCHES)
    pump(app, 600)

    print("\n  building run 1's chart (targen + the ChromIQ engine)")
    if not build(app, tab):
        print("  >>> the first build never came back; nothing else can be judged")
        return 2
    pump(app, 1200)
    ctl = tab._target_ctl

    # 1 ------------------------------------------------------------------
    note(app, win, tab, "a freshly opened run with a built chart", False,
         "the panel is what just built the chart, so nothing pends")

    # 2 ------------------------------------------------------------------
    tab._set_manual_value("targen", "-f", PATCHES + 20)
    pump(app, 900)
    note(app, win, tab, "the user moves one control", True,
         "the patch count on screen is not in the chart")

    # 2b -----------------------------------------------------------------
    tab._set_manual_value("targen", "-f", PATCHES)
    pump(app, 900)
    note(app, win, tab, "…and moves it back", False,
         "it compares, so undoing the change takes the line away")

    # 3 ------------------------------------------------------------------
    tab._set_manual_value("targen", "-f", PATCHES + 20)
    pump(app, 900)
    print("\n  building again, with the changed patch count")
    build(app, tab)
    pump(app, 1200)
    note(app, win, tab, "pressing Generate Chart", False,
         "the build wrote the panel into the chart")

    # 4 ------------------------------------------------------------------
    print("\n  a second run, so there is somewhere to go and come back from")
    ctl.set_profile_run("")            # New run
    pump(app, 1200)
    note(app, win, tab, "a brand new run with nothing built", False,
         "nothing overwrites the panel, so nothing is at risk")

    tab._set_manual_value("targen", "-f", PATCHES + 40)
    pump(app, 900)
    note(app, win, tab, "…moving a control on that new run", False,
         "still nothing built, so still nothing to lose")

    if not build(app, tab):
        print("  >>> the second build never came back")
    pump(app, 1500)
    runs = [r.id for r in ctl.project_or_none().all_runs()] \
        if ctl.project_or_none() else []
    print(f"     runs now: {runs}")

    ctl.set_profile_run("run1")
    pump(app, 1800)
    note(app, win, tab, "selecting another run", False,
         "the run's own chart has just been painted over the panel")

    tab._set_manual_value("targen", "-f", 777)
    pump(app, 900)
    note(app, win, tab, "a change made and NOT built", True,
         "this is the change Knut asked to be warned about")

    ctl.set_profile_run("run2")
    pump(app, 1800)
    ctl.set_profile_run("run1")
    pump(app, 1800)
    back = tab._manual_get("targen", "-f", 0)
    note(app, win, tab, "coming back to the run", False,
         f"the chart won, as §2.2 says: the box reads {back}")

    # 5 ------------------------------------------------------------------
    print("\n  loading a built-in preset over a run that holds a chart")
    try:
        from ui.tabs.tab_chart import KNUT_PRESETS_BY_KEY
        key = sorted(KNUT_PRESETS_BY_KEY)[0]
        tab._seed_knut_preset(key, "Warn-Demo")
        pump(app, 2000)
        note(app, win, tab, "loading a preset", True,
             "the preset's values are not in the run's chart yet")
    except Exception as exc:                       # noqa: BLE001
        print(f"     (preset step skipped: {exc})")

    # 6 ------------------------------------------------------------------
    ctl.set_profile_run("run1")
    pump(app, 1800)
    proj = ctl.project_or_none()
    other = proj.run("run2").chart_ti2 if proj and proj.has_run("run2") else None
    if other is not None and Path(other).is_file():
        print("\n  opening a .ti2 that belongs to this project (run 2's)")
        pages = sorted(Path(other).parent.glob(f"{Path(other).stem}*.tif"))
        tab.reflect_loaded_chart(Path(other), pages)
        pump(app, 2000)
        note(app, win, tab, "opening a .ti2 the project owns", False,
             "the tab shows it AS this tab's own chart (_chart_is_in_this_"
             "project), so the panel and the chart on screen agree")

        print("\n  opening a .ti2 that lives outside any project")
        import shutil
        away = sb / "elsewhere"
        away.mkdir(exist_ok=True)
        for f in sorted(Path(other).parent.glob(f"{Path(other).stem}*")):
            if f.is_file():
                shutil.copy(f, away / f.name)
        foreign = away / Path(other).name
        # Back to run 1 PROPERLY. The step above left run 2's chart painted on
        # the panel while the bar still said run 1, and `set_profile_run` is a
        # no-op when the value has not changed -- so without this round trip
        # the foreign copy of run 2's chart is compared against run 2's own
        # settings and honestly finds no difference.
        ctl.set_profile_run("run2")
        pump(app, 1800)
        ctl.set_profile_run("run1")
        pump(app, 1800)
        print(f"     run 1 patch count before the foreign chart: "
              f"{tab._manual_get('targen', '-f', 0)}")
        tab.reflect_loaded_chart(foreign,
                                 sorted(away.glob(f"{foreign.stem}*.tif")))
        pump(app, 2000)
        note(app, win, tab, "opening a .ti2 from elsewhere", True,
             "the panel now describes a chart this run does not hold, and "
             "Generate Chart is what would put it there")
    else:
        print("     (.ti2 step skipped: no second chart on disk)")

    # 8 ------------------------------------------------------------------
    ctl.set_profile_run("run1")
    pump(app, 2000)
    print("\n  restoring the used chart")
    try:
        tab._set_manual_value("targen", "-f", 555)
        pump(app, 800)
        note(app, win, tab, "before the restore", True,
             "a pending change is standing")
        ok = tab.rebuild_verification_pages()
        end = time.monotonic() + 180
        while time.monotonic() < end and not tab._generate_btn.isEnabled():
            app.processEvents()
            time.sleep(0.02)
        pump(app, 2000)
        note(app, win, tab, "restoring a used chart", False,
             f"the chart's own settings are back on the panel (rebuilt={ok})")
    except Exception as exc:                       # noqa: BLE001
        print(f"     (restore step skipped: {exc})")

    win.close()
    pump(app, 500)

    print("\n  ---- the table ----")
    for n, name, exp, got, ok, why in rows:
        print(f"  {n:02d} | {name:<44} | expected "
              f"{'SHOWS' if exp else 'quiet':<5} | got "
              f"{'SHOWS' if got else 'quiet':<5} | {'ok' if ok else 'DIFFERS'}"
              f" | {why}")
    print(f"\n  rows that differ: {bad}")
    print(f"  pictures in {SHOTS}")
    print(f"  sandbox was {sb}")
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
