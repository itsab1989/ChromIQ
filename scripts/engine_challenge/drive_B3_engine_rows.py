"""B3 — the four engine-only rows, one at a time, on screen.

phase 1 (``build``): Manual, accurate. For each row: set it with a real
click, Build, read the log for the promised line, reset. Then all four set
→ Save as Defaults (settings.ini) → Save preset "engine-rows" → rows back to
defaults → pick the preset → do they come back?
phase 2 (``restart``): a NEW process on the same sandbox — do the saved
defaults bring the rows back?
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.engine_challenge.harness import Harness            # noqa: E402
from scripts.engine_challenge.drive_B_common import (            # noqa: E402
    CHART_924, WORK_B, active_modal, build_and_answer, button_named,
    buttons_of, click, grab, icc_version, pick, run_journey, sandbox, say)

OUT = WORK_B / "B3"
OUT.mkdir(parents=True, exist_ok=True)
SEEN: list[tuple[str, str]] = []
ROWS = ("_m_spectral_cb", "_m_iccver_combo", "_m_noise_cb", "_m_render_combo")


def state(prof) -> dict:
    return {"spectral": prof._m_spectral_cb.isChecked(),
            "iccver": prof._m_iccver_combo.currentData(),
            "noise": prof._m_noise_cb.isChecked(),
            "render": prof._m_render_combo.currentData()}


def grep(lines, *keys):
    return [ln for ln in lines if any(k.lower() in ln.lower() for k in keys)]


def journey_build(h):
    win, prof = h.win, h.win._tab_profile
    run_dir = h.work / "Real-924/runs/run1"
    icc = run_dir / "Real-924.icc"
    twin = run_dir / "Real-924-v4.icc"
    h.go_profile_tab("manual")
    yield 400
    say(f"rows visible={prof._m_engine_rows_widget.isVisible()} state={state(prof)}")

    # --- row 1: spectral physics on an RGB chart
    say("ROW 1: tick 'Spectral physics model'")
    click(prof._m_spectral_cb)
    yield 300
    say(f"  state={state(prof)}")
    yield from build_and_answer(h, OUT, "spectral", SEEN)
    lines = prof._log.toPlainText().splitlines()
    say("  lines about spectral/physics: " + json.dumps(grep(lines, "spectral", "physic")))
    click(prof._m_spectral_cb)
    yield 300

    # --- row 2: noise handling
    say("ROW 2: tick 'Measurement noise handling'")
    click(prof._m_noise_cb)
    yield 300
    say(f"  state={state(prof)}")
    yield from build_and_answer(h, OUT, "noise", SEEN)
    lines = prof._log.toPlainText().splitlines()
    say("  lines about noise/scatter/confidence: " + json.dumps(grep(lines, "noise", "scatter", "shadow", "highlight", "midtone", "saturated", "support")))
    click(prof._m_noise_cb)
    yield 300

    # --- row 3: bijective renderer
    say("ROW 3: Out-of-gamut rendering → ChromIQ bijective")
    ok = pick(prof._m_render_combo, "ChromIQ bijective (experimental)")
    say(f"  picked via popup={ok}; state={state(prof)}")
    yield 300
    yield from build_and_answer(h, OUT, "bijective", SEEN)
    lines = prof._log.toPlainText().splitlines()
    say("  lines about bijective/Argyll: " + json.dumps(grep(lines, "bijective", "matched to Argyll", "rendering")))
    ok = pick(prof._m_render_combo, "Argyll-matched (recommended)")
    yield 300

    # --- row 4: ICC version 4, then both
    say("ROW 4a: ICC profile version → Version 4")
    ok = pick(prof._m_iccver_combo, "Version 4")
    say(f"  picked via popup={ok}; state={state(prof)}")
    yield from build_and_answer(h, OUT, "v4", SEEN)
    say(f"  icc header version={icc_version(icc)} size={icc.stat().st_size}; run1={sorted(p.name for p in run_dir.iterdir())}")
    say("ROW 4b: ICC profile version → Both (v2 + v4)")
    ok = pick(prof._m_iccver_combo, "Both (v2 + v4)")
    say(f"  picked via popup={ok}; state={state(prof)}")
    yield from build_and_answer(h, OUT, "both", SEEN)
    lines = prof._log.toPlainText().splitlines()
    say(f"  icc version={icc_version(icc)}; twin exists={twin.exists()} version={icc_version(twin) if twin.exists() else None}")
    say(f"  run1={sorted(p.name for p in run_dir.iterdir())}")
    say("  lines about twin/v4: " + json.dumps(grep(lines, "twin", "v4", "version")))
    say(f"  Install button enabled={prof._install_btn.isEnabled()} _icc_path={prof._icc_path}")

    # --- all four set → Save as Defaults → preset
    say("ALL FOUR: spectral on, Both, noise on, bijective → Save as Defaults")
    click(prof._m_spectral_cb); yield 200
    click(prof._m_noise_cb); yield 200
    pick(prof._m_render_combo, "ChromIQ bijective (experimental)"); yield 200
    say(f"  state={state(prof)}")
    grab(win, OUT / "all-four-set.png")
    click(prof._save_defaults_btn)
    yield 600
    h.settings.sync()
    ini = h.ini.read_text(encoding="utf-8")
    keys = [ln for ln in ini.splitlines() if any(k in ln for k in ("spectral", "iccver", "noise", "render"))]
    say(f"  settings.ini rows: {keys}")
    say(f"  log tail: {prof._log.toPlainText().splitlines()[-1:]}")

    say("PRESET: click + (save preset) → name 'engine-rows'")
    click(prof._m_preset_add_btn)
    for _ in range(30):
        yield 100
        if active_modal(h) is not None:
            break
    dlg = active_modal(h)
    say(f"  modal {dlg.windowTitle() if dlg else None}")
    if dlg is not None:
        from PyQt6.QtWidgets import QLineEdit
        from PyQt6.QtTest import QTest
        edit = dlg.findChild(QLineEdit)
        QTest.keyClicks(edit, "engine-rows")
        yield 200
        grab(dlg, OUT / "preset-save-dialog.png")
        okb = button_named(dlg, "OK") or buttons_of(dlg)[-1]
        SEEN.append((dlg.windowTitle(), okb.text()))
        click(okb)
        yield 500
    say(f"  preset combo now={prof._m_preset_combo.currentText()!r}")
    pdir = Path(h.presets)
    files = sorted(str(p.relative_to(pdir)) for p in pdir.rglob("*") if p.is_file())
    say(f"  preset files: {files}")
    for f in pdir.rglob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            if "engine-rows" in d:
                e = d["engine-rows"]
                say(f"  preset 'engine-rows' keys of interest: " +
                    json.dumps({k: e.get(k) for k in ("spectral_physics", "icc_version", "noise_model", "render_style")}))
        except Exception as exc:      # noqa: BLE001
            say(f"  ({f.name}: {exc})")

    say("RESET rows to defaults by hand, then pick the preset")
    pick(prof._m_preset_combo, "none"); yield 300
    click(prof._m_spectral_cb); yield 150
    click(prof._m_noise_cb); yield 150
    pick(prof._m_render_combo, "Argyll-matched (recommended)"); yield 150
    pick(prof._m_iccver_combo, "Version 2 (most compatible)"); yield 150
    say(f"  state before preset={state(prof)}")
    pick(prof._m_preset_combo, "engine-rows")
    yield 500
    say(f"  state after preset={state(prof)}")
    grab(win, OUT / "after-preset.png")
    # leave the rows at defaults so phase 2 measures the SAVED DEFAULTS, not
    # a per-target write-back: switch back to 'none' and reset by hand.
    pick(prof._m_preset_combo, "none"); yield 200
    click(prof._m_spectral_cb); yield 150
    click(prof._m_noise_cb); yield 150
    pick(prof._m_render_combo, "Argyll-matched (recommended)"); yield 150
    pick(prof._m_iccver_combo, "Version 2 (most compatible)"); yield 150
    say(f"  state at exit={state(prof)}")


def journey_restart(h):
    prof = h.win._tab_profile
    h.go_profile_tab("manual")
    yield 500
    say(f"AFTER RESTART: rows visible={prof._m_engine_rows_widget.isVisible()} state={state(prof)}")
    say(f"  preset combo={prof._m_preset_combo.currentText()!r}")
    ini = h.ini.read_text(encoding="utf-8")
    say("  settings.ini rows: " + json.dumps([ln for ln in ini.splitlines() if any(k in ln for k in ("spectral", "iccver", "noise", "render"))]))
    meta = h.work / "Real-924/runs/run1/meta.json"
    if meta.exists():
        m = json.loads(meta.read_text(encoding="utf-8"))
        ps = m.get("profile_settings") or {}
        say("  run1/meta.json profile_settings engine keys: " + json.dumps({k: ps.get(k) for k in ("spectral_physics", "icc_version", "noise_model", "render_style")}))
    grab(h.win, OUT / "after-restart.png")


def main(phase: str) -> int:
    h = Harness(sandbox("B3"))
    h.boot()
    if phase == "build":
        h.make_project("Real-924", CHART_924)
        h.enable_engine("accurate")
    h.open_project("Real-924")
    run_journey(h, journey_build(h) if phase == "build" else journey_restart(h), timeout=1800)
    say(f"dialogs I clicked: {SEEN}; watchdog: {h.modals_answered}")
    say(f"sandbox: {h.sandbox}  out: {OUT}")
    h.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "build"))
