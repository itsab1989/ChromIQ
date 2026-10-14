#!/usr/bin/env python3
"""#209 on screen: the i1Profiler .txt import with ArgyllCMS's Windows names.

The bug is Windows-only: ArgyllCMS's programs are called ``txt2ti3.exe`` there,
and the Measure tab's import looked for ``txt2ti3``. macOS cannot show it as it
is, so this driver makes a Mac LOOK LIKE Windows in exactly that one respect
and nothing else:

* the real macOS ArgyllCMS programs are copied into ``<out>/argyll-win/bin``
  under their Windows names (``txt2ti3.exe``, ``spec2cie.exe``, ...); a Mach-O
  program runs the same under any name;
* ChromIQ's name helper ``core.resource_path.argyll_binary`` is patched IN THIS
  DRIVER ONLY to add ``.exe``, as it does on Windows. Nothing in the product is
  changed. Every module that asks for a tool's name gets the Windows one, the
  log's ``ArgyllRunner`` included.

Everything else is real: the real app window with the shipped styling, the
real Measure tab, the real Tools > Convert i1Profiler dialog, the real Argyll
conversions, on demo projects staged in ``<out>``.

Run it twice, once against the old code and once against the fix::

    git archive v4.3.5-beta.5 | tar -x -C <out>/before-tree
    python scripts/drive_209_txt_import_with_windows_tool_names.py \\
        --tree <out>/before-tree --out <out> --tag before
    python scripts/drive_209_txt_import_with_windows_tool_names.py \\
        --out <out> --tag after

What it does, each step photographed:

1. Tools > Convert i1Profiler -> TI3 converts the profiling export (the
   reporter's working route, through ``ArgyllRunner``).
2. A PROFILING run: Measure tab > Import of the ``.txt``. Before the fix this
   is the #209 window; after it, the measurement is filed.
   ``--tag before`` then imports the ``.ti3`` from step 1 instead (the
   workaround posted on #209).
3. A VERIFICATION: the same, with the verification chart's export.
4. A CALIBRATION run: the Measure tab offers no Import at all (§I.9 of
   unified_measurement_management.md: a calibration run cannot import). The
   calibration measurement is converted with Tools and loaded where a
   calibration's ``.ti3`` goes, Build Profile with Run type = Calibration, and
   printcal is run on it.
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

ap = argparse.ArgumentParser()
ap.add_argument("--tree", default=str(Path(__file__).resolve().parent.parent),
                help="the ChromIQ source tree to run (default: this one)")
ap.add_argument("--out", required=True, help="report folder")
ap.add_argument("--tag", required=True, choices=("before", "after"))
ARGS = ap.parse_args()

TREE = Path(ARGS.tree).resolve()
OUT = Path(ARGS.out).expanduser().resolve()
SHOTS = OUT / f"shots-{ARGS.tag}"
SANDBOX = OUT / f"sandbox-{ARGS.tag}"
REAL_ARGYLL = Path("/Applications/Argyll/bin")
WIN_ARGYLL = OUT / "argyll-win" / "bin"
TOOLS = ("txt2ti3", "spec2cie", "cxf2ti3", "colprof", "targen", "printtarg",
         "chartread", "printcal", "applycal", "profcheck", "iccgamut",
         "viewgam", "xicclu", "icclu", "cctiff", "fakeread", "average",
         "iccdump", "spotread")

if SANDBOX.exists():
    shutil.rmtree(SANDBOX)
SANDBOX.mkdir(parents=True)
SHOTS.mkdir(parents=True, exist_ok=True)
# Sandbox the settings and presets BEFORE anything of ChromIQ is imported.
os.environ["CHROMIQ_SETTINGS_FILE"] = str(SANDBOX / "settings.ini")
os.environ["CHROMIQ_PRESETS_DIR"] = str(SANDBOX / "presets")
os.environ.pop("QT_QPA_PLATFORM", None)
sys.path.insert(0, str(TREE / "scripts"))
sys.path.insert(0, str(TREE))

# ---- the ONE simulated thing: ArgyllCMS's Windows program names ------------
import core.resource_path as _rp                                  # noqa: E402

assert Path(_rp.__file__).resolve().is_relative_to(TREE), _rp.__file__
_rp.argyll_binary = lambda name: name + ".exe"

RESULT: dict = {"tag": ARGS.tag, "tree": str(TREE), "steps": [],
                "findings": []}


def say(step, detail=None):
    print(f"[STEP] {step}" + (f"  {detail}" if detail is not None else ""),
          flush=True)
    RESULT["steps"].append({"step": step, "detail": detail})


def windows_named_argyll() -> Path:
    WIN_ARGYLL.mkdir(parents=True, exist_ok=True)
    for t in TOOLS:
        src = REAL_ARGYLL / t
        dst = WIN_ARGYLL / f"{t}.exe"
        if src.exists() and not dst.exists():
            shutil.copy2(src.resolve(), dst)
    ref = WIN_ARGYLL.parent / "ref"
    if not ref.exists():
        ref.symlink_to((REAL_ARGYLL.parent / "ref").resolve())
    bare = [p.name for p in WIN_ARGYLL.iterdir() if p.suffix != ".exe"]
    assert not bare, bare
    return WIN_ARGYLL


def stage_project() -> Path:
    import make_demo_projects as mdp
    root = SANDBOX / "projects"
    root.mkdir()
    mdp.build_full(root)
    return root / "Demo-Full-RGB"


def fakeread(icc: Path, chart_ti1: Path, out_dir: Path, stem: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(chart_ti1, out_dir / f"{stem}.ti1")
    r = subprocess.run([str(REAL_ARGYLL / "fakeread"), str(icc), stem],
                       cwd=out_dir, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 0, r.stderr
    return out_dir / f"{stem}.ti3"


def as_i1profiler_txt(ti3: Path, out: Path) -> Path:
    """The readings written the way an i1Profiler CGATS export writes them
    (scripts/drive_profiling_import_round4.py)."""
    rows, fmt, mode = [], [], None
    for ln in ti3.read_text(encoding="utf-8").splitlines():
        t = ln.strip()
        if t in ("BEGIN_DATA_FORMAT", "BEGIN_DATA"):
            mode = t
            continue
        if t in ("END_DATA_FORMAT", "END_DATA"):
            mode = None
            continue
        if mode == "BEGIN_DATA_FORMAT":
            fmt = t.split()
        elif mode == "BEGIN_DATA" and t:
            rows.append(t.split())
    col = {n: i for i, n in enumerate(fmt)}
    dev = [c for c in ("RGB_R", "RGB_G", "RGB_B") if c in col]
    if not dev:
        dev = [c for c in ("CMY_C", "CMY_M", "CMY_Y") if c in col]
    lines = ['CGATS.17', 'ORIGINATOR "X-Rite i1Profiler"',
             'DESCRIPTOR "Measurement"', 'CREATED "October 14, 2026"',
             'INSTRUMENTATION "i1Pro 2"',
             'MEASUREMENT_SOURCE "Illumination=D50 ObserverAngle=2"', '',
             f'NUMBER_OF_FIELDS {1 + len(dev) + 3}', 'BEGIN_DATA_FORMAT',
             "SampleID " + " ".join(dev) + " XYZ_X XYZ_Y XYZ_Z",
             'END_DATA_FORMAT', '', f'NUMBER_OF_SETS {len(rows)}', 'BEGIN_DATA']
    for i, r in enumerate(rows, 1):
        d = [float(r[col[c]]) * 255.0 / 100.0 for c in dev]
        xyz = [float(r[col[c]]) for c in ("XYZ_X", "XYZ_Y", "XYZ_Z")]
        lines.append(f"{i} " + " ".join(f"{v:.4f}" for v in d + xyz))
    lines += ["END_DATA", ""]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def sets_in(path: Path) -> int:
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if ln.strip().upper().startswith("NUMBER_OF_SETS"):
            return int(ln.split()[1])
    return -1


def main() -> int:
    argyll = windows_named_argyll()
    proj = stage_project()
    stem = proj.name
    r1, r2, r3 = (proj / "runs" / f"run{n}" for n in (1, 2, 3))
    outside = SANDBOX / "from i1Profiler"
    work = SANDBOX / "fakeread"
    prof_txt = as_i1profiler_txt(
        fakeread(r1 / f"{stem}.icc", r3 / f"{stem}.ti1", work, "profiling"),
        outside / "profiling export.txt")
    verify_txt = as_i1profiler_txt(
        fakeread(r2 / f"{stem}.icc",
                 r2 / "verifications" / f"{stem}-verify.ti1", work, "verify"),
        outside / "verification export.txt")
    cal_txt = as_i1profiler_txt(
        fakeread(r1 / f"{stem}.icc", proj / "cal" / f"{stem}-cal.ti1", work,
                 "cal"),
        outside / "calibration export.txt")
    # run3 is the profiling run to import into: it has a chart and nothing else.
    say("staged", {"project": str(proj), "argyll (Windows names)": str(argyll),
                   "files in it": sorted(p.name for p in argyll.iterdir()),
                   "profiling export rows": sets_in(prof_txt),
                   "verification export rows": sets_in(verify_txt),
                   "calibration export rows": sets_in(cal_txt)})

    from PyQt6.QtWidgets import QApplication
    from capture_screens import build_app
    from onscreen_capture import PopupWatchdog, capture_window

    app = build_app()

    def pump(seconds: float = 0.5) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(0.02)

    def shoot(w, name: str) -> None:
        ok, why = capture_window(w, SHOTS / f"{name}.png")
        say(f"photograph {name}", "OK" if ok else f"REFUSED: {why}")
        if not ok:
            RESULT["findings"].append(f"{name}: no photograph ({why})")

    dog = PopupWatchdog(SHOTS, photograph=True, grace_s=2.5)
    dog.start()

    from core.settings import AppSettings
    from core.measurement_target import (RUN_TYPE_CALIBRATION,
                                         RUN_TYPE_PROFILING,
                                         RUN_TYPE_VERIFICATION)
    from ui.main_window import MainWindow

    s = AppSettings()
    s.set("custom_output_path", str(proj.parent))
    s.set("argyll_bin_path", str(argyll))
    s.set("calibration_mode", True)      # Preferences: offer the Calibration run type
    win = MainWindow(s)
    win.resize(1500, 1000)
    win.show()
    if hasattr(app, "_chromiq_focus_give_back"):
        app._chromiq_focus_give_back.give_back()
    pump(2.0)
    say("ArgyllCMS folder the app uses", s.get("argyll_bin_path"))
    say("the name the app asks for", __import__(
        "core.resource_path", fromlist=["x"]).argyll_binary("txt2ti3"))

    def convert_with_tools(txt: Path, name: str, shot: str) -> Path:
        from ui.dialogs.tools_dialogs import I1ProfilerToTi3Dialog
        dlg = I1ProfilerToTi3Dialog(win._runner, s, win)
        dlg.show()
        pump(0.5)
        dlg._txt = txt
        dlg._txt_field.setText(str(txt))
        dlg._output._dir_edit.setText(str(SANDBOX / "converted with Tools"))
        dlg._output._name_edit.setText(name)
        dlg._refresh()
        (SANDBOX / "converted with Tools").mkdir(exist_ok=True)
        dlg._run_btn.click()
        out = SANDBOX / "converted with Tools" / f"{name}.ti3"
        for _ in range(150):
            pump(0.1)
            if not win._runner.is_running and out.exists():
                break
        pump(1.0)
        say(f"Tools > Convert i1Profiler: {txt.name}",
            {"wrote": out.exists(), "patches": sets_in(out) if out.exists()
             else None, "log tail": dlg._log.toPlainText().splitlines()[-4:]})
        shoot(dlg, shot)
        dlg.close()
        pump(0.3)
        return out

    tab = win._tab_measure
    ctl = win._target_ctl
    win._file_mgr.set_target_name(stem)
    win._target_bar.refresh()
    pump(1.0)

    def import_on_the_measure_tab(path: Path, shot: str) -> list:
        win._tabs.setCurrentWidget(tab)
        pump(0.6)
        tab._switch_mode("import")
        pump(0.4)
        import ui.tabs.tab_measure as tm
        real = tm.open_file_dialog
        tm.open_file_dialog = lambda *a, **k: str(path)   # the green folder
        try:
            tab._on_import_browse()
        finally:
            tm.open_file_dialog = real
        pump(0.6)
        shoot(win, shot + "-chosen")
        before = len(dog.events)
        tab._import_go_btn.click()
        pump(1.5)
        shoot(win, shot + "-after")
        return [{"title": e.get("title"), "text": (e.get("text") or "")[:400]}
                for e in dog.events[before:]]

    # ---- 1 + 2: profiling ---------------------------------------------------
    prof_ti3 = convert_with_tools(prof_txt, "profiling export", "01-tools-convert")
    ctl.set_run_type(RUN_TYPE_PROFILING)
    ctl.set_profile_run("run3")
    pump(1.0)
    filed = r3 / f"{stem}.ti3"
    seen = import_on_the_measure_tab(prof_txt, "02-profiling-txt")
    say("PROFILING: Measure tab > Import of the .txt",
        {"windows": seen, "filed": filed.exists(),
         "patches": sets_in(filed) if filed.exists() else None})
    if ARGS.tag == "before":
        seen = import_on_the_measure_tab(prof_ti3, "03-profiling-ti3-workaround")
        say("PROFILING: the workaround, the .ti3 from Tools",
            {"windows": seen, "filed": filed.exists(),
             "patches": sets_in(filed) if filed.exists() else None})

    # ---- 3: verification ----------------------------------------------------
    verify_ti3 = convert_with_tools(verify_txt, "verification export",
                                    "04-tools-convert-verification")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    ctl.set_profile_run("run2")
    ctl.set_verification_id("")
    pump(1.0)
    vdir = r2 / "verifications"
    had = {p.name for p in vdir.iterdir() if p.is_dir()}
    seen = import_on_the_measure_tab(verify_txt, "05-verification-txt")
    new = sorted({p.name for p in vdir.iterdir() if p.is_dir()} - had)
    say("VERIFICATION: Measure tab > Import of the .txt",
        {"windows": seen, "new dated folders": new,
         "patches": [sets_in(t) for d in new for t in (vdir / d).glob("*.ti3")]})
    if ARGS.tag == "before":
        ctl.set_verification_id("")
        pump(0.6)
        had = {p.name for p in vdir.iterdir() if p.is_dir()}
        seen = import_on_the_measure_tab(verify_ti3,
                                         "06-verification-ti3-workaround")
        new = sorted({p.name for p in vdir.iterdir() if p.is_dir()} - had)
        say("VERIFICATION: the workaround, the .ti3 from Tools",
            {"windows": seen, "new dated folders": new,
             "patches": [sets_in(t) for d in new
                         for t in (vdir / d).glob("*.ti3")]})

    # ---- 4: calibration -----------------------------------------------------
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    pump(1.0)
    win._tabs.setCurrentWidget(tab)
    pump(0.8)
    say("CALIBRATION: is Import offered on the Measure tab?",
        {"run type": ctl.target.run_type,
         "IMPORT button visible": tab._import_btn.isVisible(),
         "import available": tab._import_available()})
    shoot(win, "07-calibration-measure-tab-no-import")
    cal_ti3 = convert_with_tools(cal_txt, "calibration export",
                                 "08-tools-convert-calibration")
    prof_tab = win._tab_profile
    win._tabs.setCurrentWidget(prof_tab)
    pump(0.8)
    import ui.tabs.tab_profile as tp
    real = tp.open_file_dialog
    tp.open_file_dialog = lambda *a, **k: str(cal_ti3)
    try:
        prof_tab._on_load_ti3()       # the header's load button, calibration
    finally:
        tp.open_file_dialog = real
    pump(0.6)
    shoot(win, "09-calibration-ti3-loaded-on-build-profile")
    prof_tab._pc_run_btn.click()
    for _ in range(300):
        pump(0.1)
        if not win._runner.is_running:
            break
    pump(1.0)
    cal_files = sorted(p.name for p in (proj / "cal").iterdir())
    say("CALIBRATION: printcal on the converted .ti3",
        {"loaded": str(prof_tab._cal_ti3_path),
         "log tail": prof_tab._pc_log.toPlainText().splitlines()[-5:],
         "cal folder": cal_files})
    shoot(win, "10-calibration-printcal-done")

    dog.stop()
    RESULT["popups"] = dog.events
    (SHOTS / "result.json").write_text(json.dumps(RESULT, indent=2,
                                                  default=str),
                                       encoding="utf-8")
    win.close()
    pump(0.5)
    return 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    os._exit(code)
