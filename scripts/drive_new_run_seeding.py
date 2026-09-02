"""Does "New run" really start from the last selected run's chart settings?

Knut, relayed 2026-08-08: *"Did you notice that 'new run' uses last selected
runs chart settings as staring point, then user can change settings before
Generate Chart clicked? This is what you mentioned at one time and is a kind of
copy chart without going through a preset save. Don't know if it works at
intended. Should only work for profiling and verification runs."*

Four questions, driven through the REAL app on screen:

  K1a  Selecting a run and then "New run" — does the New run show that run's
       settings?
  K1b  Does it follow the LAST selected run? Pick run A, then run B, then
       "New run": B's settings must win, not A's.
  K1c  Is Calibration excluded as a SOURCE, as Knut says it should be? A
       calibration sheet's settings must not become a profiling run's
       starting point.
  K2   Is "Save as Defaults" reachable at all once every target carries its
       own stored settings?

    python -u scripts/drive_new_run_seeding.py
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

HARD_STOP_S = 180


def _arm_hard_stop() -> None:
    def _die() -> None:
        print(f"\n!! hard stop after {HARD_STOP_S}s — the app blocked", flush=True)
        os.kill(os.getpid(), signal.SIGKILL)
    t = threading.Timer(HARD_STOP_S, _die)
    t.daemon = True
    t.start()


_arm_hard_stop()

FINDINGS: list[tuple[str, bool, str]] = []


def check(step: str, got, want) -> bool:
    ok = got == want
    FINDINGS.append((step, ok, f"got {got!r}, want {want!r}"))
    print(f"  {'OK  ' if ok else 'FAIL'} {step}")
    print(f"         got  {got!r}")
    if not ok:
        print(f"         want {want!r}")
    return ok


def note(step: str, detail: str) -> None:
    FINDINGS.append((step, True, detail))
    print(f"  ..   {step}\n         {detail}")


def _find_subject() -> "Path | None":
    cache = Path(os.environ.get("TMPDIR", "/tmp")) / "chromiq-demo-projects-cache"
    for cand in sorted(cache.glob("*/Demo-Full-RGB")):
        if (cand / "cal").is_dir() and (cand / "project.json").is_file():
            return cand
    return None


def main() -> int:
    src = _find_subject()
    if src is None:
        print("No cached Demo-Full-RGB. Run the test suite once to build it.")
        return 2
    work = Path(tempfile.mkdtemp(prefix="new-run-seed-"))
    shutil.copytree(src, work / src.name)
    print(f"subject: {work / src.name}")

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

    import core.settings as cs
    ini = Path(tempfile.mkdtemp()) / "drive.ini"
    cs.QSettings = lambda *a, **k: _QS(str(ini), _QS.Format.IniFormat)
    s = cs.AppSettings()
    s.set("custom_output_path", str(work))
    s.set("calibration_mode", True)
    apply_appearance(app, None, "light")

    from core.measurement_target import (RUN_TYPE_CALIBRATION,
                                         RUN_TYPE_PROFILING)
    from ui.main_window import MainWindow
    w = MainWindow(s)
    apply_appearance(app, w, "light")
    w.resize(1600, 1000)
    w.show()

    def settle(n=30):
        for _ in range(n):
            app.processEvents()

    settle(60)
    tab, ctl = w._tab_chart, w._target_bar._ctl
    w._file_mgr.set_target_name("Demo-Full-RGB")
    w._target_bar.refresh()
    settle()

    proj = w._file_mgr.project()
    runs = [r.id for r in proj.all_runs()]
    print(f"runs in the project: {runs}")
    if len(runs) < 2:
        print("need at least two runs to test 'last selected'")
        return 2
    run_a, run_b = runs[0], runs[1]

    # The row we watch: targen's patch count. It is per-target, visible, and
    # not one of the six rows Run type = Calibration owns.
    def patch_row():
        for pw in tab._manual_widgets.get("targen", []):
            if pw.flag == "-f":
                return pw
        raise AssertionError("no targen -f row")

    def select(run_id, run_type=RUN_TYPE_PROFILING):
        ctl.set_run_type(run_type)
        if run_type != RUN_TYPE_CALIBRATION:
            ctl.set_profile_run(run_id)
        tab._on_target_changed()
        settle()

    def select_new_run():
        ctl.set_run_type(RUN_TYPE_PROFILING)
        ctl.set_profile_run("")          # "" is the bar's "New run"
        tab._on_target_changed()
        settle()

    # ---------------------------------------------------------------- K1a
    print("\n--- K1a: does 'New run' start from the selected run's settings? ---")
    select(run_a)
    patch_row().set_value(137)
    tab.save_target_settings()
    settle()
    note(f"{run_a} patch count set", "137")
    select_new_run()
    check("New run starts from the run just left", patch_row().get_raw_value(), 137)

    # ---------------------------------------------------------------- K1b
    print("\n--- K1b: does it follow the LAST selected run, not the first? ---")
    select(run_a)
    patch_row().set_value(111)
    tab.save_target_settings()
    settle()
    select(run_b)
    patch_row().set_value(222)
    tab.save_target_settings()
    settle()
    note(f"{run_a} = 111, {run_b} = 222", "now ask for a New run")
    select_new_run()
    got = patch_row().get_raw_value()
    if got == 222:
        check(f"New run followed the last selected run ({run_b})", got, 222)
    else:
        check(f"New run followed the last selected run ({run_b}) — it did not",
              got, 222)

    # ---------------------------------------------------------------- K1c
    print("\n--- K1c: is Calibration excluded as a SOURCE? ---")
    # The patch count is one of the six rows _CALIBRATION_OWNED strips from the
    # seed, so watching it would show a pass whatever happens. Watch a row that
    # is NOT stripped instead — the paper size, which no calibration sheet
    # should be able to impose on a profiling run.
    def paper_row():
        for pw in tab._manual_widgets.get("printtarg", []):
            if pw.flag == "-p":
                return pw
        raise AssertionError("no printtarg -p row")

    # Start from a clean slate: an existing block is the user's and is kept
    # (N-1), which would mask the question entirely.
    for stale in Path(work / src.name).rglob("cache/new_run.json"):
        stale.unlink()
    tab.clear_new_run_block()

    select(run_b)
    paper_row().set_value("A4")
    tab.save_target_settings()
    settle()
    note(f"{run_b} paper", paper_row().get_raw_value())

    select("", RUN_TYPE_CALIBRATION)
    paper_row().set_value("A3")
    tab.save_target_settings()
    settle()
    cal_paper = paper_row().get_raw_value()
    seeded = list(Path(work / src.name).rglob("cache/new_run.json"))
    note("the calibration sheet's paper", cal_paper)
    note("New-run blocks on disk after visiting Calibration",
         ", ".join(str(x.relative_to(work / src.name)) for x in seeded) or "none")

    select_new_run()
    after_cal = paper_row().get_raw_value()
    print(f"  after Calibration → New run, the paper is {after_cal!r}")

    # COMPARING A VALUE HERE PROVES NOTHING, and nearly reported a false pass.
    # The block is written once and then left alone (N-1), so whether a given
    # value leaks depends on whether the block already existed when the row was
    # edited — not on whether calibration is excluded. The structural question
    # is the real one: is a New-run block written into cal/ at all?
    cal_block = Path(work / src.name) / "cal" / "cache" / "new_run.json"
    if cal_block.is_file():
        import json as _json
        keys = len(_json.loads(cal_block.read_text(encoding="utf-8")))
        note("cal/cache/new_run.json contents", f"{keys} rows carried")
    check("no New-run block is written into cal/ — Knut: seeding should only "
          "work for profiling and verification runs", cal_block.is_file(), False)

    # ----------------------------------------------------------------- K2
    print("\n--- K2: can 'Save as Defaults' still reach anything? ---")
    select(run_a)
    patch_row().set_value(999)
    tab._on_save_defaults()
    settle()
    note("saved 999 as the app-wide default",
         f"manual_targen_-f = {s.get('manual_targen_-f')!r}")
    select(run_b)
    on_b = patch_row().get_raw_value()
    note(f"selecting {run_b} after saving defaults", f"shows {on_b!r}")
    select_new_run()
    on_new = patch_row().get_raw_value()
    note("selecting New run after saving defaults", f"shows {on_new!r}")
    print("  → the default is reached only when a target has nothing stored "
          "AND there is no New-run seed.")

    print("\n--- summary ---")
    fails = [f for f, ok, _ in FINDINGS if not ok]
    for step, ok, detail in FINDINGS:
        print(f"  {'OK  ' if ok else 'FAIL'} {step}")
    print(f"\n{len(FINDINGS) - len(fails)} OK/noted, {len(fails)} FAIL")
    w.close()
    settle()
    sys.stdout.flush()
    os._exit(1 if fails else 0)


if __name__ == "__main__":
    raise SystemExit(main())
