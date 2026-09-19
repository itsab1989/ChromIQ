#!/usr/bin/env python3
"""B8-409: the control-strip declaration's lifecycle, in the REAL app.

Knut, 2026-09-19::

    The control strip declaration is tied to the chart it is made for, not the
    run. If the declaration exists, and measurement is started, that file shall
    also be backed up to chart/ folder (like other chart files), and if the
    Restore Used Chart button is pressed, the controls strip declaration shall
    also be restored with the other chart files. The delete function, when run
    type is set to verification, or when the profile run is selected which the
    verification belongs to (profile run = run1 etc.), then the delete button
    function shall also delete the controls strip declaration file. Also, the
    backup function that copies to old/ folder shall copy the controls strip
    declaration file if it exists.

Four places, and this driver walks all four through a window the app opened,
listing the files on disk before and after each one:

1. a real chart is generated through **Create Chart**, with Run type =
   Verification, so the app files it into ``verifications/`` and declares its
   strip;
2. the chart is generated again, which ARCHIVES the first one — the ``old/``
   place;
3. a measurement start is asked for through the Measure tab's own
   ``_snapshot_verification_chart``, which is the call every Start makes — the
   ``chart/`` place;
4. the live declaration is replaced with a different one and the real **Restore
   Used Chart** button is pressed;
5. the real **Delete** button's plan is taken and run, twice: once with Run
   type = Verification and once with the profile run selected.

TWO PIXEL-IDENTICAL FRAMES are taken of every window; another agent is driving
this machine at the same time and a frame that differs from its own retake is
a frame something else walked through.

Run it::

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-lifecycle/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-lifecycle/presets
    python scripts/drive_182_declaration_lifecycle.py <out-dir>

Never set QT_QPA_PLATFORM=offscreen for this. It is a driver, not a test.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QTimer                                   # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog,               # noqa: E402
                             QMessageBox)

from drive_182_the_five_rows import pump, twice                   # noqa: E402

ARGYLL = Path("/Applications/Argyll/bin")
WORK = Path("/tmp/chromiq-lifecycle/work")
PROJECT = "Declaration-Lifecycle"
SIDECAR = ".control-strip.json"


def listing(d: Path) -> "list[str]":
    if not d.exists():
        return ["(no folder)"]
    out = []
    for p in sorted(d.rglob("*")):
        rel = p.relative_to(d)
        out.append(f"{'d ' if p.is_dir() else '- '}{rel}")
    return out or ["(empty)"]


def build_chart(dest: Path, patches: int = 100) -> Path:
    """A real chart, with ChartCreator's own manual-build flags."""
    dest.mkdir(parents=True, exist_ok=True)
    for cmd in ([ARGYLL / "targen", "-v", "-d2", f"-f{patches}", "-e4", "-B4",
                 "-G", "chart"],
                [ARGYLL / "printtarg", "-v", "-ii1", "-pA4", "-t300", "chart"]):
        subprocess.run([str(c) for c in cmd], cwd=str(dest), check=True,
                       capture_output=True, timeout=300)
    return dest / "chart.ti2"


def accept_modal(app, label_contains: str, tries: int = 40) -> str:
    """Click the button whose text contains *label_contains* in whatever modal
    is up. Returns what it clicked, or a note saying there was nothing.

    A driver that BLOCKS on a modal gets clicked by a human, and every result
    after that point measures the human.
    """
    for _ in range(tries):
        w = app.activeModalWidget()
        if isinstance(w, QMessageBox):
            for b in w.buttons():
                if label_contains.lower() in b.text().replace("&", "").lower():
                    b.click()
                    return f"clicked “{b.text()}”"
            w.reject()
            return "no such button; the box was rejected"
        if isinstance(w, QDialog):
            w.accept()
            return "a dialog was accepted"
        app.processEvents()
        time.sleep(0.05)
    return "no modal appeared"


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else
               Path.home() / "Desktop/ChromIQ-beta23-proof"
               / "the-declaration-lifecycle")
    shots = out / "shots"
    shots.mkdir(parents=True, exist_ok=True)

    sfile = os.environ.get("CHROMIQ_SETTINGS_FILE", "")
    if "/tmp/" not in sfile:
        print("REFUSING: CHROMIQ_SETTINGS_FILE is not sandboxed", file=sys.stderr)
        return 2

    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)

    app = QApplication.instance() or QApplication(sys.argv)
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))      # what main.py ships

    from core.settings import AppSettings
    s = AppSettings()
    s.set("custom_output_path", str(WORK))
    s.set("argyll_bin_path", str(ARGYLL))
    assert str(WORK) in str(s.get("custom_output_path", "")), "SANDBOX FAILED"

    from core.file_manager import Project
    from core.measurement_target import (RUN_TYPE_PROFILING,
                                         RUN_TYPE_VERIFICATION)
    from ui.main_window import MainWindow
    from workflow import control_strip as cs

    chart = build_chart(Path("/tmp/chromiq-lifecycle/chart"))

    proj_dir = WORK / PROJECT
    Project.create(proj_dir, PROJECT).current_run().ensure_dir()

    win = MainWindow(s)
    win.resize(1500, 1000)
    win.show()
    pump(app, 1200)

    fm = win._file_mgr
    fm.open_project_at(proj_dir)
    win._target_ctl.changed.emit()
    pump(app, 600)

    rep: "list[str]" = [
        "# B8-409 — the control-strip declaration's lifecycle, on screen", "",
        f"driven {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"settings sandbox : {sfile}",
        f"presets sandbox  : {os.environ.get('CHROMIQ_PRESETS_DIR', '(unset)')}",
        f"working folder   : {WORK}",
        "mode             : ON SCREEN, a real window, photographed with "
        "capture_window", ""]
    verdicts: "dict[str, bool]" = {}

    def shot(tag: str, title: str) -> None:
        p = shots / f"{tag}.png"
        ok, why, d = twice(app, win, p)
        verdicts[f"photograph {tag}"] = ok
        rep.extend(["", f"### photograph — {title}",
                    f"    {'kept' if ok else 'REFUSED: ' + why}: "
                    f"{p if ok else '(none kept)'}",
                    f"    the two frames differ by {d} %"])

    def generate(run_type: str) -> None:
        """Put the chart at the run root and let Create Chart finish."""
        run = fm.project().current_run()
        run.ensure_dir()
        for ext in (".ti1", ".ti2"):
            src = chart.with_suffix(ext)
            if src.is_file():
                shutil.copyfile(src, run.artefact(ext))
        tif = run.dir / f"{run.stem}_01.tif"
        shutil.copyfile(next(chart.parent.glob("*.tif")), tif)
        win._target_ctl.set_run_type(run_type)
        pump(app, 200)
        win._tab_chart._on_generate_finished([tif])
        pump(app, 600)

    # ---- 1. the app declares a strip for the chart it files ---------------
    rep += ["", "## 1. Create Chart, Run type = Verification"]
    rep += ["", "### disk before"] + ["    " + l for l in listing(proj_dir)]
    generate(RUN_TYPE_VERIFICATION)
    run = fm.project().current_run()
    decl = cs.declaration_path(run.verify_chart_ti2)
    rep += ["", "### disk after"] + ["    " + l for l in listing(proj_dir)]
    first_bytes = decl.read_bytes() if decl.is_file() else b""
    verdicts["the app declared a strip"] = decl.is_file()
    rep += ["", f"    declaration: {decl.name} — "
            f"{'WRITTEN' if decl.is_file() else 'MISSING'}"]
    if decl.is_file():
        doc = json.loads(decl.read_text(encoding="utf-8"))
        rep += [f"    it names {len(doc['sample_ids'])} patches, "
                f"generator {doc.get('generator')}"]
    win._tabs.setCurrentIndex(0)
    pump(app, 400)
    shot("01-chart-filed", "the chart filed as a verification chart")

    # ---- 2. the old/ archive ----------------------------------------------
    rep += ["", "## 2. Generate again — what the displaced chart takes with it"]
    generate(RUN_TYPE_VERIFICATION)
    old = run.verifications_old_dir
    archived = sorted(old.rglob("*" + SIDECAR))
    rep += ["", "### verifications/old/ after the regenerate"] + \
        ["    " + l for l in listing(old)]
    verdicts["the declaration was archived, not destroyed"] = bool(
        archived) and any(p.read_bytes() == first_bytes for p in archived)
    rep += ["", f"    archived declarations: "
            f"{[p.name for p in archived] or 'NONE'}",
            f"    one of them is byte-identical to the displaced original: "
            f"{any(p.read_bytes() == first_bytes for p in archived)}"]

    # ---- 3. the chart/ snapshot a measurement takes ------------------------
    rep += ["", "## 3. A measurement start — the chart/ snapshot"]
    decl = cs.declaration_path(run.verify_chart_ti2)
    live_bytes = decl.read_bytes()
    win._target_ctl.set_run_type(RUN_TYPE_VERIFICATION)
    pump(app, 200)
    went = win._tab_measure._snapshot_verification_chart()   # every Start's call
    pump(app, 400)
    vid = win._target_ctl.target.verification_id
    snap = run.verification(vid).dir / "chart"
    rep += ["", f"    _snapshot_verification_chart() -> {went}",
            f"    the dated folder: {vid}",
            "", "### the snapshot on disk"] + ["    " + l for l in listing(snap)]
    stored = snap / decl.name
    verdicts["the snapshot carries the declaration"] = (
        stored.is_file() and stored.read_bytes() == live_bytes)
    rep += ["", f"    {decl.name} in chart/: {stored.is_file()}"
            f"  identical: {stored.is_file() and stored.read_bytes() == live_bytes}"]
    win._target_ctl.changed.emit()
    pump(app, 400)
    shot("02-after-the-snapshot", "the bar on the dated verification")

    # ---- 4. Restore Used Chart --------------------------------------------
    rep += ["", "## 4. Restore Used Chart, pressed in the window"]
    decl.write_text(json.dumps({"name": "a later chart's strip",
                                "sample_ids": ["1"]}, indent=2) + "\n",
                    encoding="utf-8")
    run.verify_chart_ti2.write_text("A DIFFERENT CHART\n", encoding="utf-8")
    rep += ["", "### the live chart before the press"] + \
        ["    " + l for l in listing(run.verifications_dir)]
    rep += ["", f"    the live declaration now names: "
            f"{json.loads(decl.read_text(encoding='utf-8'))['sample_ids']}"]
    win._target_ctl.changed.emit()
    pump(app, 500)
    bar = win._target_bar
    btn = getattr(bar, "_restore_btn", None)
    enabled = bool(btn is not None and btn.isEnabled())
    rep += [f"    the Restore Used Chart button is enabled: {enabled}"]
    shot("03-restore-enabled", "Restore Used Chart, enabled")
    clicked = []
    QTimer.singleShot(400, lambda: clicked.append(
        accept_modal(app, "Restore Chart")))
    if btn is not None:
        btn.click()
    pump(app, 1500)
    for _ in range(3):                      # a second modal may follow
        if app.activeModalWidget() is not None:
            clicked.append(accept_modal(app, "OK"))
        pump(app, 400)
    back = json.loads(decl.read_text(encoding="utf-8"))
    stored_ids = json.loads(stored.read_text(encoding="utf-8"))["sample_ids"]
    rep += ["", "### after the press"] + \
        ["    " + l for l in listing(run.verifications_dir)]
    rep += ["", f"    modal(s): {clicked}",
            f"    the live declaration now names "
            f"{len(back['sample_ids'])} patches, name “{back['name']}”",
            f"    the stored copy names {len(stored_ids)} patches",
            f"    same patches as the stored copy: "
            f"{back['sample_ids'] == stored_ids}",
            f"    byte-identical to the declaration that stood here before "
            f"the press: {decl.read_bytes() == live_bytes}",
            "",
            "    NOTE. Restoring a chart makes the app REBUILD its page",
            "    images, and that rebuild runs back through Create Chart's own",
            "    finish (the log says so: “the page rebuild altered the chart",
            "    itself … the restored chart has been put back”), which",
            "    re-declares the strip for the chart now on disk. So the file",
            "    can be a fresh write of the same strip rather than the copied",
            "    bytes. What the rule asks is that the chart does not come back",
            "    under a LATER chart's declaration, and the patch list above is",
            "    what says whether it did."]
    verdicts["Restore Used Chart put the declaration back"] = (
        back["sample_ids"] == stored_ids)
    shot("04-after-restore", "after Restore Used Chart")

    # ---- 5. Delete ---------------------------------------------------------
    rep += ["", "## 5. Delete"]
    import core.run_delete as rd
    win._target_ctl.set_run_type(RUN_TYPE_VERIFICATION)
    pump(app, 300)
    plan = win._target_ctl.delete_plan()
    rep += ["", f"    Run type = Verification -> plan {getattr(plan, 'kind', plan)}"
            f" on {getattr(plan, 'path', '')}"]
    shot("05-delete-verification", "the bar with Run type = Verification")
    rd.delete_verification(plan)
    pump(app, 400)
    left = sorted(proj_dir.rglob("*" + SIDECAR))
    verdicts["Delete (verification) removed the declaration"] = not left
    rep += ["", "### the project after the verification delete"] + \
        ["    " + l for l in listing(proj_dir)]
    rep += [f"    declarations left anywhere in the project: "
            f"{[str(p.relative_to(proj_dir)) for p in left] or 'none'}"]

    # and again, this time deleting the profile run the verification belonged to
    generate(RUN_TYPE_VERIFICATION)
    win._target_ctl.set_run_type(RUN_TYPE_VERIFICATION)
    win._tab_measure._snapshot_verification_chart()
    proj = fm.project()
    proj.new_run()                       # a project always keeps one run
    win._target_ctl.set_profile_run("run1")
    win._target_ctl.set_run_type(RUN_TYPE_PROFILING)
    pump(app, 400)
    rep += ["", "### before the profile-run delete"] + \
        ["    " + l for l in listing(proj_dir)]
    plan2 = win._target_ctl.delete_plan()
    rep += ["", f"    profile run selected -> plan "
            f"{getattr(plan2, 'kind', plan2)} on {getattr(plan2, 'path', '')}"]
    rd.delete_run(proj, plan2)
    pump(app, 400)
    left2 = sorted(proj_dir.rglob("*" + SIDECAR))
    verdicts["Delete (profile run) removed the declaration"] = not left2
    rep += ["", "### the project after the profile-run delete"] + \
        ["    " + l for l in listing(proj_dir)]
    rep += [f"    declarations left anywhere in the project: "
            f"{[str(p.relative_to(proj_dir)) for p in left2] or 'none'}"]
    win._target_ctl.changed.emit()
    pump(app, 2500)          # the bar re-reads the project after a delete
    shot("06-after-delete", "the project after both deletes")

    rep += ["", "## verdicts", ""]
    for k, v in verdicts.items():
        rep.append(f"    {'PASS' if v else 'FAIL'}  {k}")
    (out / "on-screen-run.md").write_text("\n".join(rep) + "\n",
                                          encoding="utf-8")
    print("\n".join(rep[-(len(verdicts) + 3):]))
    print(f"\nwritten: {out / 'on-screen-run.md'}")
    win.close()
    pump(app, 300)
    return 0 if all(verdicts.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
