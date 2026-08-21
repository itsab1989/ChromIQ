#!/usr/bin/env python3
"""Drive the REAL ChromIQ window through #162 — the in-gamut colour count.

soul-traveller: *"the parameter that selects the number of in gamut patches is
not automatically defaulted to the number of patches that the settings in the
manual tab represents. Like, if I select a 484 patch preset, the default value
should be 484 patches (including the 8 color extremes)."*

His own preset is loaded in Manual, the module is opened, and the number on
screen is read back — together with the three things the default must not break:
a count the user typed, a count this target has recorded, and the existing
"Auto — fill the pages", which computes a different number on purpose.

    python scripts/drive_162_gamut_count_default.py

Basti's preferences are copied to a throwaway .ini; nothing of his is touched.
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

from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtGui import QFontDatabase                           # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from core.resource_path import resource_path                    # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"
PRESET_KEY = "__chromiq_knut_fls_i1pro_a4_484p_1page_portrait__"
#: A real project with a BUILT PROFILE — the module only exists for a
#: verification run that has one, and it opens itself when such a run is
#: selected. An earlier version of this script drove the module by calling
#: _switch_mode("gamut") on a project with no profile at all: a state the app
#: never reaches, where its own button is hidden and no per-target store exists.
PROJECT = "Pro300_EpsonPremSG_i1Studio_Jun26"
CORNERS = 8
RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((bool(ok), name, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


def pump(app, ms: int) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq_162_"))
    from core.settings import AppSettings
    src = QSettings(str(REAL_PLIST), QSettings.Format.NativeFormat)
    dst = QSettings(str(sandbox / "settings.ini"), QSettings.Format.IniFormat)
    for k in src.allKeys():
        dst.setValue(k, src.value(k))
    dst.sync()
    settings = AppSettings()
    settings._qs = dst
    configured = str(settings.get("custom_output_path") or "").strip()
    real_root = Path(configured) if configured else (Path.home() / "ChromIQ")
    if not real_root.is_dir():
        real_root = Path.home() / "ChromIQ"
    work = sandbox / "ChromIQ"
    work.mkdir()
    import shutil
    if (real_root / PROJECT).is_dir():
        shutil.copytree(real_root / PROJECT, work / PROJECT)
    settings.set("custom_output_path", str(work))
    # Open on that project, the way the app restores the last session.
    settings.set("restore_last_session", True)
    settings.set("session_target_name", PROJECT)
    settings.set("session_project_root", str(work))
    # The stored global he is complaining about: a count with nothing to do
    # with the chart in Manual.
    settings.set("gamut_target_count", 400)
    settings.set("gamut_target_auto", False)
    print(f"Sandbox: {sandbox}\n")

    QDialog.exec = lambda self: 1                      # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import KNUT_PRESETS_BY_KEY, TabChart
    TabChart._confirm_displacing_results = lambda self, *a, **k: True
    TabChart._prompt_target_name = lambda self, *a, **k: "gamut-162"

    win = MainWindow(settings)
    win.show()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart

    print("SCENARIO 1 — a verification run with a profile, and the module")
    from core.measurement_target import RUN_TYPE_VERIFICATION
    ctl = tab._target_ctl
    ctl.set_profile_run("run1")
    pump(app, 800)
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    pump(app, 1500)
    check(tab._gamut_profile() is not None,
          "the run has a built profile, so the module is available",
          "the module exists only for a verification run that has one")
    # This project has a RECORDED module ("manual"), and a recorded choice wins
    # over the automatic open by design — so the user clicks the button, which
    # is the path `_switch_mode` serves.
    tab._user_switch_mode("gamut")
    pump(app, 1200)
    check(tab._mode_name() == "gamut", "the module is open",
          f"mode={tab._mode_name()}")
    check(tab._gamut_count_spin.value() == 400,
          "…showing the stored global he complains about", "400")

    print("\nSCENARIO 2 — his 484-patch preset, chosen from inside the module")
    preset = KNUT_PRESETS_BY_KEY[PRESET_KEY]
    check(preset.patches == 484, "the preset holds 484 patches", preset.name)
    tab._seed_knut_preset(PRESET_KEY, "gamut-162")
    pump(app, 1500)
    manual_f = int(tab._manual_f_pw.get_raw_value() or 0)
    check(manual_f == 484, "Manual now represents 484 patches",
          f"targen -f {manual_f}")
    spin = tab._gamut_count_spin.value()
    check(spin == 484 - CORNERS,
          "the count defaulted to the chart Manual describes",
          f"the box reads {spin}, and the chart totals {spin + CORNERS}")
    check(spin + CORNERS == 484,
          "…which is the 484 he asked for, corners included")

    print("\nSCENARIO 3 — a number he types is his, and survives a save/load")
    tab._gamut_count_spin.setValue(300)
    pump(app, 400)
    stored = tab._collect_ui_state()
    check(stored["gamut"]["count"] == 300
          and stored["gamut"].get("count_chosen") is True,
          "the record says the count was CHOSEN, not merely what it was",
          "a record that only carries the number cannot be told from the global")
    tab._apply_ui_state(stored)
    tab._refresh_gamut_state()
    pump(app, 400)
    check(tab._gamut_count_spin.value() == 300,
          "…so loading it back does not re-default it")

    print("\nSCENARIO 4 — the count every existing target already carries")
    # _collect_ui_state files gamut.count for every target that is merely
    # visited, so every verification target that exists today holds the
    # untouched global. Reading that as a choice made the whole feature a no-op.
    tab._apply_ui_state({"gamut": {"count": 400}})
    tab._refresh_gamut_state()
    pump(app, 400)
    check(tab._gamut_count_spin.value() == 484 - CORNERS,
          "a count nobody chose does not disarm the default",
          "this is what the reporter's own projects look like")

    print("\nSCENARIO 5 — 'Auto — fill the pages' still means what it meant")
    for engine_on in (True, False):
        settings.set("use_chromiq_layout_engine", engine_on)
        tab._gamut_auto_check.setChecked(True)
        pump(app, 500)
        auto = tab._gamut_effective_count()
        tab._gamut_count_spin.setValue(123)
        pump(app, 300)
        check(tab._gamut_effective_count() == auto,
              f"[engine {'on' if engine_on else 'off'}] Auto ignores the box, "
              "as it always did",
              f"Auto computes {auto} + {CORNERS} = {auto + CORNERS}"
              + ("  (the same as the chart here — the preset pins the grid)"
                 if auto + CORNERS == 484 else
                 "  (the chart Manual describes is 484)"))
        tab._gamut_auto_check.setChecked(False)
        pump(app, 300)

    bad = [r for r in RESULTS if not r[0]]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} checks passed")
    win.close()
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
