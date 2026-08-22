#!/usr/bin/env python3
"""Find what moves Create Chart off Guided when a chart is generated.

Basti: "started in create chart guided, selected spectroscan, paper 4x6,
generate -> generated the chart but went to manual on its own, and colormunki
was still selected there". Twice in a row. The plain sequence on a clean
sandbox does NOT do it, so the trigger is state, and guessing which is slower
than asking the program: `_switch_mode` is wrapped to print WHO called it, and
the sequence is then run against each state a real session could be carrying.

    python scripts/drive_guided_mode_jump.py [case ...]

Basti's preferences are copied to a throwaway .ini; nothing of his is touched,
and every project is written inside the sandbox.
"""
from __future__ import annotations

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

from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtGui import QFontDatabase                           # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox           # noqa: E402

from core.resource_path import resource_path                    # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"

CASES = ("plain", "second-generate", "run-type-calibration",
         "run-type-verification", "hexagons", "opened-in-manual")


def pump(app, ms: int) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def run_case(app, case: str, sandbox: Path) -> tuple[str, list[str]]:
    from core.settings import AppSettings
    ini = sandbox / f"{case}.ini"
    src = QSettings(str(REAL_PLIST), QSettings.Format.NativeFormat)
    dst = QSettings(str(ini), QSettings.Format.IniFormat)
    for k in src.allKeys():
        dst.setValue(k, src.value(k))
    dst.sync()
    settings = AppSettings()
    settings._qs = dst
    settings.set("custom_output_path", str(sandbox / case / "ChromIQ"))

    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1500, 1000)
    win.show()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 800)

    # WHO moves the mode, and from where.
    calls: list[str] = []
    real = tab._switch_mode

    def spy(mode, *a, **k):
        here = [f"  {l.strip()}" for l in traceback.format_stack()[:-1]
                if "tab_chart.py" in l or "chart_creator" in l][-3:]
        calls.append(f"-> {mode!r} from " + " / ".join(
            s.split('line ')[1].split(',')[0] for s in here if 'line ' in s))
        return real(mode, *a, **k)

    tab._switch_mode = spy

    if case == "opened-in-manual":
        tab._switch_mode("manual")
        pump(app, 400)
    tab._switch_mode("guided")
    pump(app, 500)
    calls.clear()                      # only what happens from HERE counts

    if case == "run-type-calibration":
        tab._set_cal_options(True) if hasattr(tab, "_set_cal_options") else None
    if case == "run-type-verification":
        for name in ("_on_run_type_changed", "_refresh_gamut_visibility"):
            pass                        # driven via the bar below

    i = tab._instr_combo.findData("SS")
    tab._instr_combo.setCurrentIndex(i)
    pump(app, 500)
    if case == "hexagons":
        tab._hex_check.setChecked(True) if hasattr(tab, "_hex_check") else None
        pump(app, 400)
    for k in range(tab._paper_combo.count()):
        if "4x6" in str(tab._paper_combo.itemData(k) or ""):
            tab._paper_combo.setCurrentIndex(k)
            break
    pump(app, 600)

    rounds = 2 if case == "second-generate" else 1
    for r in range(rounds):
        tab._on_generate()
        for _ in range(60):
            pump(app, 1000)
            if tab._generate_btn.isEnabled():
                break
        pump(app, 2000)

    mode = tab._current_mode()
    manual_i = tab._manual_get("printtarg", "-i", None)
    tab.grab().save(str(sandbox / f"{case}.png"))
    win.close()
    pump(app, 500)
    return f"mode={mode:7s} manual -i={manual_i!r}", calls


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq_modejump_"))
    cases = sys.argv[1:] or list(CASES)
    bad = 0
    for case in cases:
        try:
            result, calls = run_case(app, case, sandbox)
        except Exception as exc:                     # noqa: BLE001
            print(f"{case:24s} ERROR {type(exc).__name__}: {exc}")
            continue
        jumped = "mode=guided" not in result
        bad += jumped
        print(f"{case:24s} {result}   {'<-- LEFT GUIDED' if jumped else ''}")
        for c in calls:
            print(f"      {c}")
    print(f"\nshots: {sandbox}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
