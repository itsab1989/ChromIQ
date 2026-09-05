"""B6 — locked controls during a build, then close the window while the
engine's colprof oracle is running (S15, N16, N20).

Manual, accurate, gamut source "Perceptual + Saturation (-S)" =
/Applications/Argyll/ref/ClayRGB1998.icm. Build; at ~4 s photograph the
locked state and list every control's enabled state; when the log shows
"Saturation table: matching colprof's rendering", `pgrep colprof`, then
`win.close()` (what the red button sends). Observe the window, the engine
thread, the child colprof, the .icc, the oracle temp dir; then exit the way
main.py does (os._exit) and let the shell check pgrep afterwards.
"""
from __future__ import annotations

import glob
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.engine_challenge.harness import Harness            # noqa: E402
from scripts.engine_challenge.drive_B_common import (            # noqa: E402
    CHART_924, WORK_B, active_modal, click, grab, modal_title, pick,
    run_journey, sandbox, say)

OUT = WORK_B / "B6"
OUT.mkdir(parents=True, exist_ok=True)
CLAY = "/Applications/Argyll/ref/ClayRGB1998.icm"


def pgrep(name: str) -> list[str]:
    r = subprocess.run(["pgrep", "-fl", name], capture_output=True, text=True, encoding="utf-8")
    return [ln[:140] for ln in r.stdout.splitlines() if "pgrep" not in ln and "zsh" not in ln]


def oracle_dirs() -> list[str]:
    td = tempfile.gettempdir()
    return sorted(glob.glob(os.path.join(td, "tmp*", "oracle.ti3")))


def lock_state(h) -> dict:
    win, prof, mh = h.win, h.win._tab_profile, h.win._masthead
    from PyQt6.QtWidgets import QAbstractButton
    tabs = {win._tabs.tabText(i): win._tabs.isTabEnabled(i) for i in range(win._tabs.count())}
    buttons = {b.toolTip() or b.text(): b.isEnabled() for b in mh.findChildren(QAbstractButton) if b.isVisible()}
    bar = h.win._target_bar
    return {"tabs": tabs, "masthead": buttons,
            "build": prof._build_btn.isEnabled(), "install": prof._install_btn.isEnabled(),
            "save_defaults": prof._save_defaults_btn.isEnabled(),
            "file_grp": prof._file_grp.isEnabled(), "stack": prof._stack.isEnabled(),
            "guided_btn": prof._guided_btn.isEnabled(), "manual_btn": prof._manual_btn.isEnabled(),
            "bar.run_combo": bar._run_combo.isEnabled(), "bar.delete": bar._delete_btn.isEnabled(),
            "bar.duplicate": bar._duplicate_btn.isEnabled()}


MODE = sys.argv[1] if len(sys.argv) > 1 else "wait"


def journey(h):
    win, prof = h.win, h.win._tab_profile
    run1 = h.work / "Real-924/runs/run1"
    icc = run1 / "Real-924.icc"
    h.go_profile_tab("manual")
    yield 400
    ok = pick(prof._m_gam_mode_combo, "Perceptual + Saturation (-S)  ← recommended")
    prof._m_gam_path_edit.setText(CLAY)
    yield 200
    say(f"gamut mode={prof._m_gam_mode_combo.currentData()!r} (popup={ok}) path={prof._m_gam_path_edit.text()}")
    say(f"before build: lock={lock_state(h)}")
    say(f"before build: colprof procs={pgrep('colprof')} oracle dirs={oracle_dirs()}")
    prof._log.clear()
    t0 = time.monotonic()
    click(prof._build_btn)
    yield 4000
    say(f"[{time.monotonic()-t0:.0f}s] LOCKED STATE: {lock_state(h)}")
    grab(win, OUT / "01-locked-during-build.png")
    # try the locked things for real: click a tab, the Tools button, Build
    win._tabs.tabBar().setCurrentIndex(2)      # what a click on '3. Measure' does
    yield 300
    say(f"  clicked tab index 2 → current tab={win._tabs.tabText(win._tabs.currentIndex())!r}")
    click(win._masthead.tools_button()); yield 500
    say(f"  clicked Tools → modal={modal_title(h)} popups={[w.__class__.__name__ for w in h.app.topLevelWidgets() if w.isVisible() and w is not win]}")
    click(prof._build_btn); yield 300
    say(f"  clicked Build → button text={prof._build_btn.text()!r} enabled={prof._build_btn.isEnabled()}")
    # wait for the oracle stage
    while time.monotonic() - t0 < 120:
        log = prof._log.toPlainText()
        if "Saturation table: matching colprof" in log:
            break
        yield 200
    yield 1500
    say(f"[{time.monotonic()-t0:.0f}s] oracle stage reached; colprof procs={pgrep('colprof')} oracle dirs={oracle_dirs()}")
    grab(win, OUT / "02-at-oracle-stage.png")
    say("CLOSING THE WINDOW (win.close())")
    tc = time.monotonic()
    click_ok = win.close()
    yield 300
    say(f"  close() returned {click_ok} after {time.monotonic()-tc:.2f}s; visible={win.isVisible()} modal={modal_title(h)}")
    if MODE == "exit":
        # What the shipped app does next: app.exec() returns on the last
        # window closing and main._hard_exit → os._exit. No pumping after.
        say(f"  engine thread running={prof._engine_builder.is_running} colprof={[p for p in pgrep('colprof') if 'oracle' in p]} "
            f"oracle dirs={oracle_dirs()} — now os._exit(0) like main._hard_exit")
        sys.stdout.flush()
        os._exit(0)
    for i in range(6):
        yield 1000
        say(f"  +{i+1}s: engine thread running={prof._engine_builder.is_running} colprof={pgrep('colprof')} "
            f"icc exists={icc.exists()} size={icc.stat().st_size if icc.exists() else 0} oracle dirs={oracle_dirs()}")
    # does the build finish anyway with the window gone?
    for _ in range(90):
        if not prof._engine_builder.is_running:
            break
        yield 1000
    say(f"  after wait: engine running={prof._engine_builder.is_running} colprof={pgrep('colprof')} "
        f"icc exists={icc.exists()} size={icc.stat().st_size if icc.exists() else 0} modal={modal_title(h)} oracle dirs={oracle_dirs()}")
    say(f"  log tail: {prof._log.toPlainText().splitlines()[-3:]}")
    (OUT / "log.txt").write_text(prof._log.toPlainText(), encoding="utf-8")


def main() -> int:
    h = Harness(sandbox("B6"))
    h.boot()
    h.make_project("Real-924", CHART_924)
    h.enable_engine("accurate")
    h.open_project("Real-924")
    run_journey(h, journey(h), timeout=400)
    say(f"watchdog: {h.modals_answered}; sandbox: {h.sandbox}")
    say("exiting like main.py: os._exit(0)")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
