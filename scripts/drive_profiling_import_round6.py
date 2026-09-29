#!/usr/bin/env python3
"""Challenge round 6: the doors that REFUSE.

Rounds 3 to 5 came back clean on the journeys that succeed, so this one only
tries to break the ones that are supposed to fail, because a refusal that ends
in a traceback out of a Qt slot ends the process, and a refusal that ends in
silence reads as a broken app. Four files nobody should be able to import:

1. a file that is not a measurement at all (a text file);
2. the run's own **chart** picked as the measurement — an easy slip, since both
   sit in the run folder and both are CGATS;
3. an empty file;
4. a measurement of a chart with a different number of patches.

Every one of them must end in a sentence, write nothing, and leave the app
running.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

SANDBOX = Path(tempfile.mkdtemp(prefix="chromiq-profiling-import-r6-"))
os.environ["CHROMIQ_SETTINGS_FILE"] = str(SANDBOX / "settings.ini")
os.environ["CHROMIQ_PRESETS_DIR"] = str(SANDBOX / "presets")
os.environ.pop("QT_QPA_PLATFORM", None)

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
SHOTS = Path.home() / "Desktop" / "ChromIQ-beta18-proof" / "profiling-import"
SHOTS.mkdir(parents=True, exist_ok=True)

import scripts.onscreen_capture as onscreen_capture

RESULT: dict = {"sandbox": str(SANDBOX), "steps": [], "findings": [],
                "captures": []}
MODALS: list = []


def say(step, detail=None):
    print(f"[STEP] {step}" + (f"  {detail}" if detail is not None else ""),
          flush=True)
    RESULT["steps"].append({"step": step, "detail": detail})


def finding(text):
    print(f"[FINDING] {text}", flush=True)
    RESULT["findings"].append(text)


def shoot(win, name):
    path = SHOTS / f"{name}.png"
    ok, why = onscreen_capture.capture_window(win, path)
    RESULT["captures"].append({"name": name, "ok": ok, "why": why})
    print(f"[SHOT] {name}: {'OK' if ok else 'REFUSED — ' + why}", flush=True)


def arm(app):
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton

    def _look():
        w = QApplication.activeModalWidget()
        if w is None:
            return
        text = ((w.text() or "") + "\n" + (w.informativeText() or "")
                if isinstance(w, QMessageBox)
                else "\n".join(l.text() for l in w.findChildren(QLabel)
                               if l.text())[:800])
        MODALS.append({"title": w.windowTitle(), "text": text,
                       "buttons": [b.text() for b in w.findChildren(QPushButton)]})
        print(f"[MODAL] {w.windowTitle()!r}: {text[:200]}", flush=True)
        w.reject() if hasattr(w, "reject") else w.close()
        w.close()

    t = QTimer()
    t.timeout.connect(_look)
    t.start(400)
    return t


def main() -> int:
    from PyQt6.QtWidgets import QApplication

    root = SANDBOX / "projects"
    root.mkdir(parents=True)
    proj = root / "Import-Refusals"
    shutil.copytree(REPO / "demo-projects" / "Demo-Report-Matrix", proj)
    run1 = proj / "runs" / "run1"
    for f in list(run1.iterdir()):
        if f.is_file() and f.name.startswith("Demo-Report-Matrix"):
            f.rename(run1 / f.name.replace("Demo-Report-Matrix",
                                           "Import-Refusals"))
    m = proj / "project.json"
    m.write_text(m.read_text(encoding="utf-8")
                 .replace("Demo-Report-Matrix", "Import-Refusals"),
                 encoding="utf-8")
    good_ti3 = run1 / "Import-Refusals.ti3"
    chart = run1 / "Import-Refusals.ti2"
    bad = SANDBOX / "bad"
    bad.mkdir()
    not_a_measurement = bad / "my shopping list.txt"
    not_a_measurement.write_text("milk\nbread\ncoffee\n", encoding="utf-8")
    empty = bad / "nothing at all.ti3"
    empty.write_text("", encoding="utf-8")
    # A PARTIAL measurement of THIS chart: the first 40 rows of its own
    # readings. The first version of this case was labelled "a measurement of a
    # chart of a different size" and expected a refusal, which was the probe
    # being wrong rather than the app: truncating a measurement of this chart
    # is the definition of a partial one, and §I.10 says file it and state both
    # counts. It does, so the case now checks that instead.
    short = bad / "stopped after 40 patches.ti3"
    lines, out, state = good_ti3.read_text(encoding="utf-8").splitlines(), [], None
    kept = 0
    for ln in lines:
        t = ln.strip()
        if t.upper().startswith("NUMBER_OF_SETS"):
            out.append("NUMBER_OF_SETS 40")
            continue
        if t == "BEGIN_DATA":
            state = "d"
            out.append(ln)
            continue
        if t == "END_DATA":
            state = None
            out.append(ln)
            continue
        if state == "d" and t:
            if kept >= 40:
                continue
            kept += 1
        out.append(ln)
    short.write_text("\n".join(out) + "\n", encoding="utf-8")
    good_ti3.unlink()
    for icc in run1.glob("*.icc"):
        icc.unlink()

    from core.settings import AppSettings
    from core.measurement_target import RUN_TYPE_PROFILING
    from ui.main_window import MainWindow
    from ui.styles import WinButtonLayoutStyle

    s = AppSettings()
    s.set("custom_output_path", str(root))
    app = QApplication.instance() or QApplication(sys.argv)
    try:
        app.setStyle(WinButtonLayoutStyle("Fusion"))
    except Exception:                         # noqa: BLE001
        pass
    # KEPT IN A NAME. A QTimer nobody holds is collected the moment `arm`
    # returns, and the watchdog then silently does nothing — which is how
    # round 6 came to sit on a modal for four minutes while its own log said
    # the watchdog had met no windows at all.
    _watchdog = arm(app)
    win = MainWindow(s)
    win.resize(1500, 1000)
    win.show()
    win.raise_()
    for _ in range(60):
        app.processEvents()
    time.sleep(1.0)
    for _ in range(40):
        app.processEvents()

    tab = win._tab_measure
    ctl = win._target_ctl
    win._file_mgr.set_target_name("Import-Refusals")
    win._target_bar.refresh()
    ctl.set_run_type(RUN_TYPE_PROFILING)
    ctl.set_profile_run("run1")
    tab.set_ti1_path(chart)
    win._tabs.setCurrentWidget(tab)
    tab._switch_mode("import")
    for _ in range(40):
        app.processEvents()

    said: list = []
    tab._say_on_screen = lambda t, b: said.append((t, b))
    import ui.measurement_filing as mf
    mf.refuse_it_does_not_belong = lambda parent, reason: said.append(
        ("does not belong", reason))
    done: list = []
    tab._show_import_done_profiling = lambda r, d: done.append((r.id, d))

    for label, path in (("a text file that is not a measurement", not_a_measurement),
                        ("the run's own CHART picked as the measurement", chart),
                        ("an empty file", empty),
                        ("a partial measurement of this chart (§I.10)", short)):
        said.clear()
        modal_before = len(MODALS)
        before_done = len(done)
        tab._import_path = path
        try:
            tab._update_import_panel()
            for _ in range(20):
                app.processEvents()
            tab._on_import_measurement()
            for _ in range(40):
                app.processEvents()
            time.sleep(0.3)
            crashed = None
        except Exception as exc:              # noqa: BLE001
            crashed = f"{type(exc).__name__}: {exc}"
        spoke = said + [(m["title"], m["text"][:160]) for m in MODALS[modal_before:]]
        say(label, {
            "crashed": crashed,
            "said": spoke,
            "filed anything": len(done) > before_done
            or (run1 / "Import-Refusals.ti3").exists(),
        })
        if crashed:
            finding(f"{label}: the import raised out of a Qt slot — {crashed}")
        if not spoke:
            finding(f"{label}: refused in silence, which reads as a dead button")
        filed_it = (run1 / "Import-Refusals.ti3").exists()
        if filed_it and "\u00a7I.10" not in label:
            finding(f"{label}: was FILED")
        if not filed_it and "\u00a7I.10" in label:
            finding(f"{label}: was REFUSED, and \u00a7I.10 says a partial "
                    "measurement is filed with both counts stated")
        if filed_it:
            (run1 / "Import-Refusals.ti3").unlink()
        shoot(win, f"r6-{label.split()[0]}-{abs(hash(label)) % 1000}")

    say("the app is still running", {"window visible": win.isVisible()})
    RESULT["modals"] = MODALS
    (SHOTS / "drive-round6.json").write_text(
        json.dumps(RESULT, indent=2, default=str), encoding="utf-8")
    print("\n=== ROUND 6 FINDINGS ===", flush=True)
    for f in RESULT["findings"] or ["none"]:
        print(" -", f, flush=True)
    win.close()
    for _ in range(20):
        app.processEvents()
    return 1 if RESULT["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
