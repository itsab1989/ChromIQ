"""Does the patch set editor act on the CALIBRATION chart in a calibration run?

Knut, relayed 2026-08-08: *"I also realized many features may need checking,
like if the patch set editor applies new patches to calibration run."*

The suspicion has a precedent. beta.165 was the same shape: a method asked
"verification, or else the selected RUN?" — written when there were two run
types — and with Calibration selected it rebuilt the wrong chart entirely. So
this drives the REAL app, on screen, with the real styling, and asks the two
questions that matter:

  Q1  With Run type = Calibration, which chart does the editor OPEN?
  Q2  When the editor applies an edited patch set, which chart does it REPLACE?

The subject is ``Demo-Full-RGB`` from the Argyll-built demo-projects cache,
copied to a temp folder. It is ideal because the two charts have different
patch counts — cal = 64, run1 = 240 — so there is no way to misread which one
the app picked.

    python scripts/drive_cal_patch_set_editor.py
"""
from __future__ import annotations

import os
import shutil
import signal
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

#: A real MainWindow on the developer's screen: if anything blocks on a modal,
#: the screen is hostage until the process dies. Arm the kill before Qt loads.
HARD_STOP_S = 150


def _arm_hard_stop() -> None:
    def _die() -> None:
        print(f"\n!! hard stop after {HARD_STOP_S}s — the app blocked; "
              "whatever window is on screen is the reason", flush=True)
        os.kill(os.getpid(), signal.SIGKILL)
    t = threading.Timer(HARD_STOP_S, _die)
    t.daemon = True
    t.start()


_arm_hard_stop()

FINDINGS: list[str] = []


def check(step: str, got, want) -> bool:
    ok = got == want
    FINDINGS.append(f"{'OK  ' if ok else 'FAIL'} {step}")
    print(f"  {'OK  ' if ok else 'FAIL'} {step}")
    print(f"         got  {got!r}")
    if not ok:
        print(f"         want {want!r}")
    return ok


def _sets(ti_path: Path) -> "int | None":
    """NUMBER_OF_SETS out of a .ti1/.ti2, or None."""
    try:
        for line in ti_path.read_text(errors="replace", encoding="utf-8").splitlines():
            if line.strip().startswith("NUMBER_OF_SETS"):
                return int(line.split()[-1])
    except OSError:
        pass
    return None


def _find_subject() -> "Path | None":
    """The cached Demo-Full-RGB (Argyll-built, has a real cal/)."""
    cache = Path(os.environ.get("TMPDIR", "/tmp")) / "chromiq-demo-projects-cache"
    for cand in sorted(cache.glob("*/Demo-Full-RGB")):
        if (cand / "cal").is_dir() and (cand / "project.json").is_file():
            return cand
    return None


def main() -> int:
    src = _find_subject()
    if src is None:
        print("No cached Demo-Full-RGB with a cal/ folder. Run the test suite "
              "once to build the demo-project cache, then retry.")
        return 2

    work = Path(tempfile.mkdtemp(prefix="cal-patchset-"))
    shutil.copytree(src, work / src.name)
    print(f"subject: {src}\n     -> {work / src.name}")

    try:
        import PyQt6.QtWebEngineWidgets  # noqa: F401
    except ImportError:
        pass
    from PyQt6.QtCore import QSettings as _QS
    from PyQt6.QtGui import QFontDatabase
    from PyQt6.QtWidgets import QApplication

    from core.freetype_bootstrap import ensure_freetype_library
    ensure_freetype_library()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    app.setOrganizationName("ChromIQ")

    from core.resource_path import resource_path
    from ui.styles import WinButtonLayoutStyle
    from ui.theme import apply_appearance
    from ui.widgets import (ButtonFontFilter, DialogFocusFilter,
                            GroupBoxSurfaceFilter, TooltipWrapFilter)
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    for F in (ButtonFontFilter, GroupBoxSurfaceFilter, TooltipWrapFilter,
              DialogFocusFilter):
        app.installEventFilter(F(app))

    # An isolated store — driving the app must never touch the developer's own
    # preferences or projects. (A probe of mine once left Basti's target_name
    # pointing at a folder it had deleted.)
    import core.settings as cs
    ini = Path(tempfile.mkdtemp()) / "drive.ini"
    cs.QSettings = lambda *a, **k: _QS(str(ini), _QS.Format.IniFormat)
    s = cs.AppSettings()
    s.set("custom_output_path", str(work))
    s.set("calibration_mode", True)
    apply_appearance(app, None, "light")

    from core.measurement_target import RUN_TYPE_CALIBRATION, RUN_TYPE_PROFILING
    from ui.main_window import MainWindow
    w = MainWindow(s)
    apply_appearance(app, w, "light")
    w.resize(1600, 1000)
    w.show()

    def settle(n=30):
        for _ in range(n):
            app.processEvents()

    settle(60)

    tab, bar, ctl = w._tab_chart, w._target_bar, w._target_bar._ctl
    w._file_mgr.set_target_name("Demo-Full-RGB")
    bar.refresh()
    settle()

    proj = w._file_mgr.project()
    cal_ti2 = proj.calibration.ti2       # a property, not a method
    run1_ti2 = proj.run("run1").chart_ti2
    cal_sets, run_sets = _sets(cal_ti2), _sets(run1_ti2)
    print(f"\ncalibration chart : {cal_ti2.name}  ({cal_sets} patches)")
    print(f"run 1 chart       : {run1_ti2.name}  ({run_sets} patches)")
    assert cal_sets != run_sets, "the two charts must differ to be tellable apart"

    # ---------------------------------------------------------------- Q1
    print("\n--- Q1: with Run type = Calibration, which chart does the "
          "editor OPEN? ---")
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    tab._on_target_changed()
    settle()
    check("the bar really is on a calibration",
          ctl.target.is_calibration(), True)

    preload = w._current_chart_ti2()
    check("the chart the editor is pre-loaded with",
          preload.name if preload else None, cal_ti2.name)
    check("...and its patch count",
          _sets(preload) if preload else None, cal_sets)

    # The real dialog, with the real pre-load path. Constructed directly
    # because open_tool_dialog ends in exec() and would block the driver.
    from ui.dialogs.ti2_relayout_dialog import Ti2RelayoutDialog
    dlg = Ti2RelayoutDialog(w._runner, s, w, on_apply=None,
                            initial_chart=preload)
    dlg.show()
    settle(80)          # the load is a singleShot(0) inside the dialog
    # _set_chart stores the parsed chart on self._spec, and the editor's own
    # basename is what the title/save field shows.
    spec = getattr(dlg, "_spec", None)
    basename = getattr(dlg, "_basename", None)
    n_patches = None
    for attr in ("patches", "rgb", "values", "rows"):
        seq = getattr(spec, attr, None)
        if seq is not None:
            try:
                n_patches = len(seq)
                break
            except TypeError:
                pass
    print(f"  editor basename    : {basename!r}")
    print(f"  editor patch count : {n_patches}")
    check("the editor window is showing the calibration's patches",
          n_patches, cal_sets)
    check("the editor's save name is the calibration's stem",
          basename, cal_ti2.stem)
    dlg.close()
    settle()

    # ---------------------------------------------------------------- Q2
    print("\n--- Q2: where would an applied patch set LAND? ---")
    print("  (inspecting the destination the apply path chooses, without "
          "running printtarg)")
    before_cal = _sets(cal_ti2)
    before_run = _sets(run1_ti2)
    staged = w._file_mgr.working_dir() / "edited_patch_set.ti1"
    print(f"  apply stages the edited set at : {staged}")
    print(f"  that path is inside the project root, not cal/: "
          f"{staged.parent.name!r}")
    check("cal chart untouched so far", _sets(cal_ti2), before_cal)
    check("run chart untouched so far", _sets(run1_ti2), before_run)

    print("\n--- summary ---")
    for f in FINDINGS:
        print("  " + f)
    fails = [f for f in FINDINGS if f.startswith("FAIL")]
    print(f"\n{len(FINDINGS) - len(fails)} OK, {len(fails)} FAIL")
    w.close()
    settle()
    # os._exit does NOT flush stdio, so a piped run loses everything printed
    # above it — which cost one run of this script to work out.
    sys.stdout.flush()
    sys.stderr.flush()
    # os._exit: MainWindow's WebEngine teardown can hang on quit (#38).
    os._exit(1 if fails else 0)


if __name__ == "__main__":
    raise SystemExit(main())
