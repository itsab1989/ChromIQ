"""B5 — rebuild over an existing profile with "Both (v2 + v4)", the twin's
fate, the File guide, Install, Delete, and the failure case (observer 2015_2).

Install is NOT clicked: `ProfileBuilder.install_profile` copies into the
user's real ColorSync folder (`_profile_dir()`), which no sandbox covers.
What Install would copy is read from `_icc_path`.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.engine_challenge.harness import Harness            # noqa: E402
from scripts.engine_challenge.drive_B_common import (            # noqa: E402
    CHART_924, WORK_B, active_modal, build_and_answer, button_named,
    buttons_of, click, grab, pick, run_journey, sandbox, say)

OUT = WORK_B / "B5"
OUT.mkdir(parents=True, exist_ok=True)
SEEN: list[tuple[str, str]] = []


def listing(d: Path) -> dict:
    return {str(p.relative_to(d)): (p.stat().st_size, time.strftime("%H:%M:%S", time.localtime(p.stat().st_mtime)))
            for p in sorted(d.rglob("*")) if p.is_file() and "cache" not in p.parts}


def journey(h):
    win, prof, bar = h.win, h.win._tab_profile, h.win._target_bar
    run1 = h.work / "Real-924/runs/run1"
    icc, twin = run1 / "Real-924.icc", run1 / "Real-924-v4.icc"
    h.go_profile_tab("manual")
    yield 400
    ok = pick(prof._m_iccver_combo, "Both (v2 + v4)")
    say(f"ICC version → Both (popup={ok}); building #1")
    yield from build_and_answer(h, OUT, "build1", SEEN)
    l1 = listing(run1)
    say(f"  run1 after build #1: {json.dumps(l1)}")

    say("building #2 over the existing profile + twin")
    yield 1500
    yield from build_and_answer(h, OUT, "build2", SEEN)
    l2 = listing(run1)
    say(f"  run1 after build #2: {json.dumps(l2)}")
    say(f"  old/ exists={ (run1 / 'old').exists() }")
    say(f"  lines mentioning 'moved'/'previous': {[ln for ln in prof._log.toPlainText().splitlines() if 'moved' in ln.lower() or 'previous' in ln.lower()]}")

    say("File guide: does it know the twin?")
    from ui.file_guide import file_guide_body, file_guide_html
    body = file_guide_body()
    say(f"  file_guide_body mentions '-v4': {'-v4' in body}; 'v4': {'v4' in body}; '.icc' rows: {[ln.strip()[:90] for ln in body.splitlines() if '.icc' in ln][:6]}")
    wf = h.work / "Real-924/Where are my files.txt"
    say(f"  project 'Where are my files.txt' exists={wf.exists()} mentions v4={('v4' in wf.read_text(encoding="utf-8")) if wf.exists() else None}")
    say(f"Install would copy: _icc_path={prof._icc_path} install button enabled={prof._install_btn.isEnabled()} (NOT clicked — real ColorSync folder)")

    say("FAILURE CASE: observer → 2015 2° (Stockman), build")
    ok = pick(prof._m_obs_combo, "2015 2° (Stockman)")
    say(f"  observer picked (popup={ok}) data={prof._m_obs_combo.currentData()!r}")
    before = listing(run1)
    el, title = yield from build_and_answer(h, OUT, "fail-observer", SEEN, answer=("Close", "OK", "Done"))
    say(f"  failure modal title={title!r}")
    after = listing(run1)
    say(f"  run1 unchanged after failure: {before == after}; run1 now: {json.dumps(after)}")
    say(f"  log lines with ERROR/needs/colprof: {[ln for ln in prof._log.toPlainText().splitlines() if 'ERROR' in ln or 'needs' in ln or 'colprof' in ln][:6]}")
    pick(prof._m_obs_combo, "Default (1931 2° standard)"); yield 200

    say("DELETE: a second run is needed so run1 can be deleted as a run (not the project); Duplicate is greyed"
        " without a chart, so run2 is made with Project.new_run() (ASSISTED) and selected on the bar")
    import shutil
    proj = win._file_mgr.project()
    r2 = proj.new_run()
    shutil.copyfile(run1 / "Real-924.ti3", r2.measurement_ti3)
    h.open_project("Real-924", "run2"); yield 800
    say(f"  runs: {sorted(p.name for p in (h.work / 'Real-924/runs').iterdir())}; bar on {bar._run_combo.currentText()!r}")
    pick(bar._run_combo, "Run 1 (overwrite)"); yield 600
    say(f"  bar on {bar._run_combo.currentText()!r}; delete enabled={bar._delete_btn.isEnabled()} tip={bar._delete_btn.toolTip()[:100]!r}")
    trash_before = set(os.listdir(Path.home() / ".Trash"))
    click(bar._delete_btn)
    for _ in range(40):
        yield 100
        if active_modal(h) is not None:
            break
    m = active_modal(h)
    yield 300
    grab(m, OUT / "delete-modal.png")
    say(f"  delete modal {m.windowTitle()!r} buttons={[b.text() for b in buttons_of(m)]} text={m.text()[:400]!r}")
    go = [b for b in buttons_of(m) if b.text().lower().startswith("delete run")]
    go = go[0] if go else None
    SEEN.append((m.windowTitle(), go.text() if go else "?"))
    click(go); yield 1200
    say(f"  runs now: {sorted(p.name for p in (h.work / 'Real-924/runs').iterdir())}; bar on {bar._run_combo.currentText()!r}")
    new = sorted(set(os.listdir(Path.home() / ".Trash")) - trash_before)
    say(f"  new items in ~/.Trash: {new}")
    for n in new:
        p = Path.home() / ".Trash" / n
        if p.is_dir():
            say(f"    {n}: {sorted(str(q.relative_to(p)) for q in p.rglob('*.icc'))}")
    say(f"  log tail: {prof._log.toPlainText().splitlines()[-3:]}")
    grab(win, OUT / "after-delete.png")


def main() -> int:
    h = Harness(sandbox("B5"))
    h.boot()
    h.make_project("Real-924", CHART_924)
    h.enable_engine("accurate")
    h.open_project("Real-924")
    run_journey(h, journey(h), timeout=1200)
    say(f"dialogs I clicked: {SEEN}; watchdog: {h.modals_answered}")
    say(f"sandbox: {h.sandbox}  out: {OUT}")
    h.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
