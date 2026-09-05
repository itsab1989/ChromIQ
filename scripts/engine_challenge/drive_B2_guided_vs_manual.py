"""B2 — Guided + Maximum accuracy, then Manual with identical settings.

Engine on at settings level (B1 proved the Preferences path). Open the
924p project (the measurement follows the bar), press Build in GUIDED,
photograph the tab while it works (busy headline, progress-bar label), the
"Profile Built" window when it appears (then click Done, recorded), and
the finished state. Then MANUAL, same defaults, build again; compare the
two profiles tag by tag.
"""
from __future__ import annotations

import dataclasses
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.engine_challenge.harness import Harness            # noqa: E402
from scripts.engine_challenge.drive_B_common import (            # noqa: E402
    CHART_924, WORK_B, active_modal, button_named, buttons_of, click,
    grab, modal_title, run_journey, sandbox, say, screencapture)

OUT = WORK_B / "B2"
OUT.mkdir(parents=True, exist_ok=True)
SEEN: list[tuple[str, str]] = []


def build_and_watch(h, tag: str, shots=(3, 15, 40)):
    """Generator: press Build, photograph during, answer 'Profile Built'."""
    win, prof = h.win, h.win._tab_profile
    prof._log.clear()
    say(f"[{tag}] clicking Build Profile (mode={prof._current_mode()})")
    t0 = time.monotonic()
    click(prof._build_btn)
    yield 500
    taken = set()
    log_seen = 0
    while True:
        el = time.monotonic() - t0
        for s in shots:
            if el >= s and s not in taken:
                taken.add(s)
                grab(win, OUT / f"{tag}-building-{s:02d}s.png")
                pb = prof._progress_bar
                say(f"  [{tag} {el:4.0f}s] headline={prof._build_headline.text()!r} sub={prof._build_subtext.text()!r} "
                    f"bar label={getattr(pb, '_label', '?')!r}/{getattr(pb, '_sub', '?')!r} btn={prof._build_btn.text()!r}")
        lines = prof._log.toPlainText().splitlines()
        if len(lines) > log_seen:
            for ln in lines[log_seen:]:
                say(f"  [{tag} log +{el:4.0f}s] {ln}")
            log_seen = len(lines)
        m = active_modal(h)
        if m is not None:
            yield 400
            grab(m, OUT / f"{tag}-modal-{m.windowTitle().replace(' ', '_')}.png")
            screencapture(OUT / f"{tag}-modal-screen.png")
            btns = [b.text() for b in buttons_of(m)]
            say(f"  [{tag}] MODAL {m.windowTitle()!r} after {el:.0f}s; buttons={btns}")
            from PyQt6.QtWidgets import QLabel
            for lbl in m.findChildren(QLabel):
                if lbl.isVisible() and lbl.text().strip():
                    say(f"      label: {lbl.text()[:200]!r}")
            b = button_named(m, "Done") or button_named(m, "OK") or button_named(m, "Close")
            SEEN.append((m.windowTitle(), b.text() if b else "?"))
            if b is None:
                say("  !! no Done/OK/Close button; leaving it")
                return
            click(b)
            yield 500
            break
        if prof._build_btn.isEnabled() and not prof._engine_builder.is_running \
                and not prof._runner.is_running and el > 3:
            say(f"  [{tag}] build ended without a modal after {el:.0f}s")
            break
        if el > 900:
            say("  !! build timeout")
            break
        yield 200
    say(f"[{tag}] finished in {time.monotonic()-t0:.0f}s; modal now={modal_title(h)}")
    yield 300
    grab(win, OUT / f"{tag}-after.png")
    (OUT / f"{tag}-log.txt").write_text(prof._log.toPlainText(), encoding="utf-8")


def journey(h):
    win, prof = h.win, h.win._tab_profile
    run_dir = h.work / "Real-924/runs/run1"
    icc = run_dir / "Real-924.icc"

    say("GUIDED: the tab as the user finds it after opening the project")
    h.go_profile_tab("guided")
    yield 500
    say(f"  ti3 label={prof._file_lbl.text()!r} build enabled={prof._build_btn.isEnabled()}")
    grab(win, OUT / "guided-before.png")
    gp = prof._collect_params()
    (OUT / "guided-params.json").write_text(json.dumps(
        {k: str(v) for k, v in dataclasses.asdict(gp).items()}, indent=1), encoding="utf-8")
    yield from build_and_watch(h, "guided")
    say(f"  icc exists={icc.exists()} size={icc.stat().st_size if icc.exists() else 0}")
    say(f"  run1 contents: {sorted(p.name for p in run_dir.iterdir())}")
    shutil.copyfile(icc, OUT / "guided.icc")
    log = prof._log.toPlainText()
    hits = [ln for ln in log.splitlines() if any(k in ln.lower() for k in ("accura", "engine", "mode", "fast", "bit-exact"))]
    say("  log lines mentioning the engine/mode:")
    for ln in hits:
        say(f"    {ln}")

    say("MANUAL: click the MANUAL button, same defaults, build again")
    click(prof._manual_btn)
    yield 500
    say(f"  mode={prof._current_mode()} rows visible={prof._m_engine_rows_widget.isVisible()}")
    grab(win, OUT / "manual-before.png")
    mp = prof._collect_params()
    (OUT / "manual-params.json").write_text(json.dumps(
        {k: str(v) for k, v in dataclasses.asdict(mp).items()}, indent=1), encoding="utf-8")
    diffs = {f.name: (getattr(gp, f.name), getattr(mp, f.name))
             for f in dataclasses.fields(gp) if getattr(gp, f.name) != getattr(mp, f.name)}
    say(f"  ProfileParams differences Guided vs Manual: {diffs}")
    yield from build_and_watch(h, "manual")
    say(f"  run1 contents after 2nd build: {sorted(p.name for p in run_dir.iterdir())}")
    old = run_dir / "old"
    say(f"  old/ exists={old.exists()} contents={sorted(str(p.relative_to(run_dir)) for p in old.rglob('*')) if old.exists() else []}")
    shutil.copyfile(icc, OUT / "manual.icc")
    r = subprocess.run([sys.executable, str(WORK_B / "icc_tagdiff.py"),
                        str(OUT / "guided.icc"), str(OUT / "manual.icc")],
                       capture_output=True, text=True, timeout=60, encoding="utf-8")
    say("tag diff guided vs manual:\n" + r.stdout + r.stderr)


def main() -> int:
    h = Harness(sandbox("B2"))
    h.boot()
    h.make_project("Real-924", CHART_924)
    h.enable_engine("accurate")
    h.open_project("Real-924")
    run_journey(h, journey(h), timeout=1500)
    say(f"dialogs I clicked: {SEEN}")
    say(f"harness watchdog answered: {h.modals_answered}")
    say(f"sandbox: {h.sandbox}  out: {OUT}")
    h.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
