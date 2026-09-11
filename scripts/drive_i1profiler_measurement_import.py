#!/usr/bin/env python3
"""On-screen reproduction and proof for the profile-build measurement import.

Drives the REAL ChromIQ window, on screen, against a sandboxed settings file, a
sandboxed presets folder and a sandboxed working folder, using a user's own
project and her own two i1Profiler exports.

It answers, with the app's own words on screen:

  R1  An i1Profiler CGATS export of RGB + spectral and NO XYZ. Does the Build
      Profile tab's import take it, or does it ask for an XYZ column?
  R2  Her chart: 4,000 designed patches, a 4,014-row `.ti2`. Her measurement
      holds 4,000. Does the app call that a partial measurement?
  R3  The same measurement into her existing run, and into a fresh project.
      Do the two doors agree?

Usage:

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-import2.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-import2-presets
    python scripts/drive_i1profiler_measurement_import.py --out DIR [--tag after]
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

from PyQt6.QtCore import QTimer                                   # noqa: E402
from PyQt6.QtGui import QFontDatabase                             # noqa: E402
from PyQt6.QtWidgets import QApplication                          # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window, session_is_locked     # noqa: E402

HER = Path("/Users/Basti/Desktop/Neuer Ordner")
SPECTRAL_ONLY = HER / "AuroraNatural_M1.txt"      # RGB + spectral, no XYZ
WITH_XYZ = HER / "ColorJetwxyz_M1.txt"            # RGB + XYZ(0..1) + spectral
PROJECT = "Pro1100-ColorJet97"
WORK = Path("/tmp/chromiq-import2-work")

modals: list = []
_timers: list = []


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def install_modal_watchdog(app, shots: Path, res: dict):
    """Photograph every modal that opens, record its words, then close it.

    A driver that blocks on a modal gets clicked by the owner, and every result
    after that point is his and not the run's.
    """
    seen = {"n": 0}

    def check():
        w = app.activeModalWidget()
        if w is None:
            return
        title = w.windowTitle()
        text = ""
        for attr in ("text", "toPlainText"):
            f = getattr(w, attr, None)
            if callable(f):
                try:
                    text = str(f())
                    break
                except Exception:
                    pass
        info = getattr(w, "informativeText", None)
        if callable(info):
            try:
                text += "\n" + str(info())
            except Exception:
                pass
        seen["n"] += 1
        p = shots / f"modal-{seen['n']:02d}.png"
        ok, why = capture_window(w, p)
        modals.append({"title": title, "text": text[:600],
                       "shot": p.name if ok else None, "capture": why or "ok"})
        print(f"    !! modal {seen['n']}: {title!r}")
        try:
            w.reject()
        except Exception:
            w.close()
    t = QTimer()
    t.setInterval(350)
    t.timeout.connect(check)
    t.start()
    _timers.append(t)


def shot(win, path: Path, res: dict, key: str) -> None:
    ok, why = capture_window(win, path)
    res.setdefault("shots", {})[key] = path.name if ok else f"REFUSED: {why}"
    print(f"    shot {key}: {'ok' if ok else 'REFUSED ' + why}")


def main() -> int:
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else Path("/tmp/chromiq-import2-proof")
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "run"
    shots = out / "shots"
    shots.mkdir(parents=True, exist_ok=True)

    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"

    res: dict = {"tag": tag, "modals": modals,
                 "screen_locked": session_is_locked()}
    print(f"00 screen locked: {res['screen_locked']}")

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from core.resource_path import resource_path
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))

    from core.settings import AppSettings
    settings = AppSettings()
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True, exist_ok=True)
    settings.set("custom_output_path", str(WORK))
    settings.set("appearance", "dark")
    from ui import theme as ui_theme
    ui_theme.apply_appearance(app, None, "dark")
    assert settings.get("custom_output_path", "") == str(WORK), "SANDBOX FAILED"
    print(f"00 sandbox: settings {os.environ['CHROMIQ_SETTINGS_FILE']}, "
          f"work {WORK}")

    shutil.copytree(HER / PROJECT, WORK / PROJECT)
    # Start from a run with no measurement filed, so the import is the act that
    # puts one there — that is the state she was in.
    (WORK / PROJECT / "runs/run1" / f"{PROJECT}.ti3").unlink(missing_ok=True)
    run_dir = WORK / PROJECT / "runs" / "run1"
    res["chart"] = {
        "ti1_sets": _sets(run_dir / f"{PROJECT}.ti1"),
        "ti2_sets": _sets(run_dir / f"{PROJECT}.ti2"),
        "i1profiler_txt_sets": _sets(
            run_dir / "exports" / f"{PROJECT}-i1profiler.txt"),
    }
    from workflow.measurement_state import expected_patches
    res["chart"]["expected_patches"] = expected_patches(run_dir / f"{PROJECT}.ti2")
    print(f"00 chart: {res['chart']}")

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1620, 1040)
    win.show()
    pump(app, 1500)
    install_modal_watchdog(app, shots, res)
    shot(win, shots / f"{tag}-00-opened.png", res, "00-opened")

    tab = win._tab_profile

    # ---------------------------------------------------------------- R1 ----
    print("R1 the spectral-only export, through the tab's own converter")
    conv = tab._convert_for_import(SPECTRAL_ONLY)
    pump(app, 700)
    res["R1"] = {"converted": str(conv) if conv else None}
    if conv:
        from workflow.measurement_import import assess
        # Judged against a chart of its OWN size, so the only thing that can
        # refuse it is the file itself.
        v = assess(Path(conv), None)
        res["R1"]["verdict"] = {"ok": v.ok, "reason": v.reason,
                                "n_measured": v.n_measured}
        from workflow.ti3_analysis import Ti3ParseError, parse_ti3
        try:
            d = parse_ti3(Path(conv))
            res["R1"]["patches"] = d.n_patches
            res["R1"]["has_xyz_column"] = "XYZ_X" in d.fields
            res["R1"]["white_xyz"] = [round(float(x), 3) for x in
                                      max(d.xyz, key=lambda r: r[1])]
        except Ti3ParseError as exc:
            res["R1"]["read_failed"] = str(exc)
    print(f"    {res['R1']}")

    # ---------------------------------------------------------------- R2 ----
    print("R2 her own measurement, into her own run")
    conv2 = tab._convert_for_import(WITH_XYZ)
    pump(app, 700)
    res["R2"] = {"converted": str(conv2) if conv2 else None}
    if conv2:
        from workflow.measurement_import import assess
        v = assess(Path(conv2), run_dir / f"{PROJECT}.ti2")
        res["R2"]["verdict"] = {"ok": v.ok, "partial": v.partial,
                                "reason": v.reason, "n_chart": v.n_chart,
                                "n_measured": v.n_measured}
        from workflow.ti3_analysis import parse_ti3
        d = parse_ti3(Path(conv2))
        res["R2"]["white_xyz"] = [round(x, 3) for x in
                                  max(d.xyz, key=lambda r: r[1])]
        # File it where the app files it, and load it the way the tab does.
        filed = run_dir / f"{PROJECT}.ti3"
        shutil.copy2(conv2, filed)
        # Open her project so the bar and the tab are really in it.
        ctl = getattr(tab, "_target_ctl", None)
        fm = getattr(ctl, "_fm", None)
        if fm is not None:
            from ui.measurement_filing import open_the_project
            open_the_project(tab, fm, PROJECT, WORK / PROJECT)
            pump(app, 900)
        tab.set_ti3_path(filed)
        pump(app, 900)
        res["R2"]["file_label"] = tab._file_lbl.text()
        res["R2"]["build_tooltip"] = tab._build_btn.toolTip()
        print(f"    label   : {res['R2']['file_label']}")
        print(f"    tooltip : {res['R2']['build_tooltip']!r}")
        shot(win, shots / f"{tag}-01-her-run.png", res, "01-her-run")

        # And the sentence the filing helper says about it.
        from ui.measurement_filing import say_what_was_filed
        before = len(modals)
        say_what_was_filed(win, filed)
        pump(app, 1200)
        res["R2"]["filing_windows"] = modals[before:]
        print(f"    filing windows: {len(modals) - before}")

    # ---------------------------------------------------------------- R3 ----
    print("R3 the same file as a brand-new project")
    if conv2:
        from workflow.measurement_import import assess
        v = assess(Path(conv2), None)
        res["R3"] = {"no_chart_to_judge_by": {"ok": v.ok, "partial": v.partial,
                                              "n_chart": v.n_chart,
                                              "n_measured": v.n_measured}}
        print(f"    {res['R3']}")

    shot(win, shots / f"{tag}-02-final.png", res, "02-final")
    (out / f"result-{tag}.json").write_text(json.dumps(res, indent=2),
                                            encoding="utf-8")
    print(f"\nwrote {out / f'result-{tag}.json'}")
    win.close()
    pump(app, 400)
    return 0


def _sets(p: Path) -> "int | None":
    import re
    try:
        m = re.search(r"NUMBER_OF_SETS\s+(\d+)",
                      p.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    return int(m.group(1)) if m else None


if __name__ == "__main__":
    raise SystemExit(main())
