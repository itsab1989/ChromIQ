"""B4 — per-target switching of the four engine rows (S16).

Manual + accurate on run1: set all four rows. Duplicate the run through the
bar's own button (a second run made in the app, its modal answered and
recorded). Switch run2 → run1 → run2 with the bar's run dropdown and read
the rows each time; read runs/run*/meta.json afterwards.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.engine_challenge.harness import Harness            # noqa: E402
from scripts.engine_challenge.drive_B_common import (            # noqa: E402
    CHART_924, WORK_B, active_modal, button_named, buttons_of, click, grab,
    pick, run_journey, sandbox, say)

OUT = WORK_B / "B4"
OUT.mkdir(parents=True, exist_ok=True)
SEEN: list[tuple[str, str]] = []


def state(prof) -> dict:
    return {"spectral": prof._m_spectral_cb.isChecked(),
            "iccver": prof._m_iccver_combo.currentData(),
            "noise": prof._m_noise_cb.isChecked(),
            "render": prof._m_render_combo.currentData(),
            "quality": prof._m_qual_combo.currentData()}


def metas(h) -> dict:
    out = {}
    for m in sorted((h.work / "Real-924/runs").glob("run*/meta.json")):
        ps = (json.loads(m.read_text(encoding="utf-8")).get("profile_settings") or {})
        out[m.parent.name] = {k: ps.get(k) for k in ("spectral_physics", "icc_version", "noise_model", "render_style", "quality")}
    return out


def journey(h):
    win, prof, bar = h.win, h.win._tab_profile, h.win._target_bar
    h.go_profile_tab("manual")
    yield 400
    say(f"run combo items: {[bar._run_combo.itemText(i) for i in range(bar._run_combo.count())]} current={bar._run_combo.currentText()!r}")
    say(f"start state on run1: {state(prof)}")

    say("set all four rows on run1 (+ quality High as a control that is known to be per-target)")
    click(prof._m_spectral_cb); yield 150
    click(prof._m_noise_cb); yield 150
    ok1 = pick(prof._m_render_combo, "ChromIQ bijective (experimental)"); yield 150
    ok2 = pick(prof._m_iccver_combo, "Both (v2 + v4)"); yield 150
    qi = [i for i in range(prof._m_qual_combo.count()) if prof._m_qual_combo.itemData(i) == "h"][0]
    ok3 = pick(prof._m_qual_combo, prof._m_qual_combo.itemText(qi)); yield 150
    say(f"  popup picks worked: render={ok1} iccver={ok2} quality={ok3}; state={state(prof)}")
    grab(win, OUT / "01-run1-set.png")

    say("second run: the bar's Duplicate is greyed ('This run does not have a complete chart yet') and 'New run'"
        " creates nothing until a chart is generated — so run2 is made with the same call the app uses,"
        " Project.new_run(), and the measurement copied in (ASSISTED step), then selected on the bar")
    import shutil
    proj = win._file_mgr.project()
    r2 = proj.new_run()
    shutil.copyfile(h.work / "Real-924/runs/run1/Real-924.ti3", r2.measurement_ti3)
    yield 200
    h.open_project("Real-924", "run2")
    yield 800
    say(f"  run combo now={bar._run_combo.currentText()!r} items={[bar._run_combo.itemText(i) for i in range(bar._run_combo.count())]}")
    say(f"  runs on disk: {sorted(p.name for p in (h.work / 'Real-924/runs').iterdir())}")
    say(f"  run2 files: {sorted(p.name for p in (h.work / 'Real-924/runs/run2').iterdir())}")
    say(f"  state after the switch to run2 (bar on {bar._run_combo.currentText()!r}): {state(prof)}")
    say(f"  ti3 label={prof._file_lbl.text()!r} build enabled={prof._build_btn.isEnabled()}")
    say(f"  metas: {json.dumps(metas(h))}")
    grab(win, OUT / "03-on-run2-first.png")

    say("bar: pick 'Run 1 (overwrite)'")
    ok = pick(bar._run_combo, "Run 1 (overwrite)")
    yield 700
    say(f"  picked via popup={ok}; combo={bar._run_combo.currentText()!r}; state={state(prof)}")
    grab(win, OUT / "04-back-on-run1.png")

    say("bar: pick 'Run 2 (overwrite)'")
    ok = pick(bar._run_combo, "Run 2 (overwrite)")
    yield 700
    say(f"  picked via popup={ok}; combo={bar._run_combo.currentText()!r}; state={state(prof)}")
    grab(win, OUT / "05-on-run2.png")

    say("change ONE row on run2 (noise on), go to run1 and back")
    click(prof._m_noise_cb); yield 200
    say(f"  run2 state={state(prof)}")
    pick(bar._run_combo, "Run 1 (overwrite)"); yield 700
    say(f"  run1 state={state(prof)}")
    pick(bar._run_combo, "Run 2 (overwrite)"); yield 700
    say(f"  run2 state={state(prof)}")
    say(f"  metas: {json.dumps(metas(h))}")

    say("leave the tab (Measure) and come back — the tab-left write")
    win._tabs.setCurrentWidget(win._tab_measure); yield 500
    win._tabs.setCurrentWidget(prof); yield 500
    say(f"  run2 state after tab round-trip={state(prof)}")
    say(f"  metas: {json.dumps(metas(h))}")


def main() -> int:
    h = Harness(sandbox("B4"))
    h.boot()
    h.make_project("Real-924", CHART_924)
    h.enable_engine("accurate")
    h.open_project("Real-924")
    run_journey(h, journey(h), timeout=600)
    say(f"dialogs I clicked: {SEEN}; watchdog: {h.modals_answered}")
    say(f"sandbox: {h.sandbox}  out: {OUT}")
    h.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
