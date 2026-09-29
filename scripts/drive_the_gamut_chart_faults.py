#!/usr/bin/env python3
"""Build a FROM PROFILE GAMUT chart with the app and read its report on screen.

Two faults were found on such a chart (B8-393, 2026-09-18): the selection kept
ink amounts no printer has got, and the measurement report read the cube
corners off whatever patch sat nearest instead of the ones the chart declares.
This driver is how they are shown, and how a fix is shown to hold, in a REAL
window on a REAL screen:

1. it builds a real profile with Argyll,
2. it drives the Create Chart tab's own FROM PROFILE GAMUT Generate,
3. it lays the sheet out with the ChromIQ layout engine and lets the app's own
   adopt hook write the colorimetric reference beside it,
4. it fake-reads that sheet through the same profile (a perfect printer, so
   every difference the report then shows is the report's own doing),
5. and it opens the Measurement Report window on the result, photographs it
   with ``capture_window`` (never ``widget.grab()``), and writes down what the
   RENDERED PAGE says about the corners and the three reference rows.

Run it once in a tree with the fix and once in a tree without, with the SAME
profile passed to both, and the two answers are the before and the after.

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-gamut/settings.ini \\
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-gamut/presets \\
        python scripts/drive_the_gamut_chart_faults.py <out> <label> \\
            [--tree <repo>] [--profile <chart.icc>] [--chart-from <dir>]

``--chart-from`` reports on a chart somebody else built (the folder holding
``<stem>.ti2``, ``<stem>.ti3`` and ``<stem>-reference.ti3``) instead of
building one, which is how the fixed app is shown reading a chart that was
written by the broken one.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(os.environ.get("CHROMIQ_TREE")
            or Path(__file__).resolve().parents[1]).resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

ARGYLL = Path("/Applications/Argyll/bin")
COUNT = 200


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def _frames_match(a: Path, b: Path, tol: int = 8) -> bool:
    try:
        import numpy as np
        from PIL import Image
        x = np.asarray(Image.open(a).convert("RGB")).astype(int)
        y = np.asarray(Image.open(b).convert("RGB")).astype(int)
        if x.shape != y.shape:
            return False
        return bool((np.abs(x - y).sum(axis=2) > tol).sum() == 0)
    except Exception:                                      # noqa: BLE001
        return False


def capture_settled(app, win, first: Path, second: Path, tries: int = 4):
    """Two consecutive photographs that agree pixel for pixel, or say so."""
    from onscreen_capture import capture_window
    ok = ok2 = False
    why = ""
    for n in range(1, tries + 1):
        pump(app, 900)
        ok, why = capture_window(win, first)
        pump(app, 900)
        ok2, why2 = capture_window(win, second)
        why = why or why2
        if ok and ok2 and _frames_match(first, second):
            return {"photographed": True, "settled": True, "attempts": n,
                    "file": first.name, "why": why}
    return {"photographed": bool(ok and ok2), "settled": False,
            "attempts": tries, "file": first.name, "why": why}


def _argyll(tool: str) -> str:
    p = shutil.which(tool) or str(ARGYLL / tool)
    if not Path(p).exists():
        raise SystemExit(f"Argyll {tool} not found")
    return p


def _run(cmd, cwd) -> None:
    subprocess.run([str(c) for c in cmd], cwd=str(cwd), check=True,
                   capture_output=True, timeout=900)


def build_profile(into: Path) -> Path:
    """A profile of the shape a user really builds: a few hundred patches,
    colprof's fast quality. The inverse of such a profile is what leaves the
    device cube."""
    into.mkdir(parents=True, exist_ok=True)
    icc = into / "chart.icc"
    if icc.is_file():
        return icc
    srgb = ARGYLL.parent / "ref" / "sRGB.icm"
    _run([_argyll("targen"), "-d2", "-e4", "-B4", "-g16", "-s12", "-f210",
          "chart"], into)
    _run([_argyll("fakeread"), str(srgb), "chart"], into)
    _run([_argyll("colprof"), "-v0", "-ql", "-aG", "chart"], into)
    return icc


def build_the_chart(app, settings, out_root: Path, profile: Path,
                    name: str) -> "tuple[Path, dict]":
    """The app's own Generate, the app's own adopt hook, and a fake read."""
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager, Project
    from core.measurement_target import RUN_TYPE_VERIFICATION
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_chart import TabChart
    from workflow import gamut_target as gt
    from workflow.layout_engine.chart import build_chart

    fm = FileManager(settings)
    pdir = out_root / name
    if pdir.exists():
        shutil.rmtree(pdir)
    Project.create(pdir, name).current_run().ensure_dir()
    fm.set_target_name(name)
    ctl = MeasurementTargetController(fm)
    tab = TabChart(ArgyllRunner(settings), fm, settings, None)
    tab.set_target_controller(ctl)
    run = fm.project().run("run1")
    shutil.copyfile(profile, run.profile_icc)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab._switch_mode("gamut")

    built: "list[Path]" = []
    tab._generate_from_ti1 = lambda ti1, **kw: (built.append(Path(ti1)) or True)
    tab._gamut_count_spin.setValue(COUNT)
    gt.clear_round_trip_cache()
    tab._on_generate()                              # THE APP'S OWN GENERATE
    if not built:
        raise SystemExit("Generate did not route through the gamut module")
    selection = tab._pending_gamut_selection

    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    ti2 = run.verify_chart_ti2
    shutil.copyfile(built[0], ti2.with_suffix(".ti1"))
    build_chart(ti2.with_suffix(".ti1"), ti2.with_suffix(""),
                instrument="i1", paper="A4", randomize=False)
    tab._write_gamut_reference_after_adopt(ti2)     # THE APP'S OWN ADOPT HOOK

    verification = run.new_verification()
    verification.ensure_dir()
    ti3 = verification.measurement_ti3
    read = pdir / "read"
    read.mkdir(exist_ok=True)
    shutil.copyfile(ti2.with_suffix(".ti1"), read / "sheet.ti1")
    _run([_argyll("fakeread"), str(profile), "sheet"], read)
    shutil.move(str(read / "sheet.ti3"), str(ti3))
    shutil.rmtree(read)
    tab.deleteLater()
    pump(app, 200)

    import numpy as np
    from workflow.ti3_analysis import parse_ti3
    rgb = np.asarray(parse_ti3(ti2).rgb, dtype=float)
    facts = {
        "project": name,
        "selected": len(selection.targets) if selection else None,
        "in_gamut_total": selection.in_gamut_total if selection else None,
        "chart_device_max": round(float(rgb.max()), 4),
        "chart_patches_over_100": int((rgb.max(axis=1) > 100.0).sum()),
        "chart_patches_over_101": int((rgb.max(axis=1) > 101.0).sum()),
    }
    return ti3, facts


def stage_a_chart(settings, out_root: Path, name: str, src: Path) -> Path:
    """Put a chart somebody else built into a project of our own."""
    from core.file_manager import FileManager, Project
    fm = FileManager(settings)
    pdir = out_root / name
    if pdir.exists():
        shutil.rmtree(pdir)
    Project.create(pdir, name).current_run().ensure_dir()
    fm.set_target_name(name)
    run = fm.project().run("run1")
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    stem = sorted(src.glob("*-reference.ti3"))[0].name[:-len("-reference.ti3")]
    for ext in (".ti1", ".ti2", ".channels.json", "-reference.ti3"):
        s = src / f"{stem}{ext}"
        if s.is_file():
            shutil.copyfile(s, run.verifications_dir /
                            f"{run.verify_stem}{ext}")
    verification = run.new_verification()
    verification.ensure_dir()
    shutil.copyfile(src / f"{stem}.ti3", verification.measurement_ti3)
    return verification.measurement_ti3


def read_the_page(dlg) -> dict:
    """What the RENDERED page says, not what the report file says."""
    text = dlg._view.toPlainText()
    lines = [ln.strip() for ln in text.splitlines()]
    corners: "list[str]" = []
    i = text.find("Cube corners (the eight ink extremes)")
    if i < 0:
        i = text.rfind("Cube corners")
    if i >= 0:
        corners = [ln.strip() for ln in text[i:i + 1400].splitlines()
                   if ln.strip()]
    wanted = ("Paper white", "Solid colours", "CMY solids")
    rows = [ln for ln in lines if any(ln.startswith(w) for w in wanted)]
    try:
        notice = dlg._mismatch_text()
    except Exception:                                      # noqa: BLE001
        notice = None
    return {"corner_section": corners, "reference_rows": rows,
            "page_characters": len(text), "mismatch_strip": notice}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("label")
    ap.add_argument("--tree", default=None)
    ap.add_argument("--profile", default=None)
    ap.add_argument("--chart-from", default=None)
    args = ap.parse_args()

    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert not os.environ.get("QT_QPA_PLATFORM"), "this DRIVER opens a window"

    out = Path(args.out).resolve()
    shots = out / "photographs"
    shots.mkdir(parents=True, exist_ok=True)

    from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox
    from onscreen_capture import session_is_locked
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    from core.settings import AppSettings
    settings = AppSettings()
    work = out / "projects"
    work.mkdir(parents=True, exist_ok=True)
    settings.set("custom_output_path", str(work))
    settings.set("argyll_bin_path", str(ARGYLL))
    settings.set("language", "en")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    record: dict = {
        "label": args.label,
        "tree": str(ROOT),
        "head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                               capture_output=True, text=True,
                               encoding="utf-8", errors="replace",
                               timeout=30).stdout.strip(),
        "screen_locked_at_start": session_is_locked(),
        "mode": "ON SCREEN",
    }

    name = f"Gamut-Chart-{args.label}"
    if args.chart_from:
        ti3 = stage_a_chart(settings, work, name, Path(args.chart_from))
        record["facts"] = {"project": name,
                           "chart_from": str(args.chart_from)}
    else:
        profile = (Path(args.profile) if args.profile
                   else build_profile(out.parent / "profile"))
        record["profile"] = str(profile)
        ti3, facts = build_the_chart(app, settings, work, profile, name)
        record["facts"] = facts

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    MeasurementReportDialog._confirm = (              # type: ignore[assignment]
        lambda self, title, body: True)
    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    dlg.setWindowTitle(f"Measurement Report - {args.label}")
    dlg.resize(1500, 1060)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    pump(app, 2600)
    record["window_visible"] = bool(dlg.isVisible())
    record["page"] = read_the_page(dlg)
    record["photograph"] = capture_settled(
        app, dlg, shots / f"{args.label}-report-1.png",
        shots / f"{args.label}-report-2.png")
    # And the section the faults are about, brought into view the way a
    # reader would bring it into view.
    from PyQt6.QtGui import QTextCursor
    dlg._view.moveCursor(QTextCursor.MoveOperation.Start)
    found = (dlg._view.find("Cube corners (the eight ink extremes)")
             or dlg._view.find("Cube corners"))
    dlg._view.ensureCursorVisible()
    # …and on past the heading, so the TABLE is what the photograph holds.
    sb = dlg._view.verticalScrollBar()
    sb.setValue(min(sb.maximum(), sb.value() + 170))
    pump(app, 600)
    record["scrolled_to_the_corner_table"] = bool(found)
    record["photograph_corners"] = capture_settled(
        app, dlg, shots / f"{args.label}-corners-1.png",
        shots / f"{args.label}-corners-2.png")

    from workflow.measurement_report import build_report, row_values
    rep = build_report(ti3, argyll_bin=ARGYLL)
    record["report"] = {
        "reference_source": rep.get("reference_source"),
        "corners": [{k: c.get(k) for k in
                     ("name", "sample", "loc", "rgb", "present", "declared", "de")}
                    for c in rep.get("corners") or []],
        "de00_n": (rep.get("de00") or {}).get("n"),
    }
    rows = row_values(rep)
    record["rows"] = {rid: {"value": rows[rid]["value"],
                            "reason": rows[rid]["reason"]}
                      for rid in ("substrate_de00_max", "solids_de00_max",
                                  "cmy_solids_dhab_max")
                      if rid in rows}
    dlg.close()
    pump(app, 200)
    (out / f"{args.label}.json").write_text(
        json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
