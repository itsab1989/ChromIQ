#!/usr/bin/env python3
"""D01 (A1): Manual, engine ON vs engine OFF (printtarg), same instrument,
paper and patch count, in a fresh project. Captures the info panels, the log,
the recipe, and the files written by each build; then runs printtarg by hand
on the engine build's .ti1 for the parity comparison."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cc_lib as L  # noqa: E402

OUT = L.SHOTS / "A1-engine-vs-printtarg"
PROJECT = "A1-EngineVsPrinttarg"
PATCHES = 400
SCRATCH = Path("/private/tmp/claude-502/-Users-Basti-develop-ChromIQ/43fe026d-47c0-4e05-aad3-52c64d8d9eca/scratchpad/a1_parity")


def pw(tab, tool, flag):
    for w in tab._manual_widgets.get(tool, []):
        if w.flag == flag:
            return w
    return None


def set_patch_count(tab, n):
    auto = tab._manual_auto_patches_check
    if auto is not None and auto.isChecked():
        auto.click()
        L.pump(200)
    w = pw(tab, "targen", "-f")
    w.set_value(n)
    L.pump(200)
    L.log(f"  -f set to {w.get_raw_value()} (auto={auto.isChecked() if auto else None})")


def capture(tag, win, tab):
    L.grab(win, OUT / f"{tag}-window.png")
    snap = L.panel_snapshot(tab)
    snap["recipe"] = L.recipe_of(tab)
    snap["manual_info_lbl"] = tab._manual_info_lbl.text()
    snap["log_tail"] = L.tab_log_text(tab)[-3000:]
    snap["run_bar"] = win._target_bar._run_combo.currentText()
    rd = L.current_run_dir(win)
    snap["run_dir"] = str(rd)
    snap["inventory"] = L.run_inventory(rd) if rd else None
    snap["pages_spin"] = (tab._manual_layout_panel.pages.value(),
                          tab._manual_layout_panel.pages.isEnabled())
    L.save_json(snap, L.LOGS / f"d01_{tag}.json")
    return snap


def main() -> int:
    app, settings = L.build_app()
    watcher = L.ModalWatcher(app)
    win = L.build_window(app, settings)
    tab = L.goto_chart_tab(win)
    L.click(tab._manual_btn)
    L.pump(500)

    # fresh project name
    tab._manual_target_name_edit.setText(PROJECT)
    tab._manual_target_name_edit.editingFinished.emit()
    L.pump(400)
    L.log(f"name hint: {tab._target_name_hint.text()!r}  project_exists_lbl={tab._project_exists_lbl.text()!r}")

    # ---------- engine ON ----------
    chk = tab._manual_engine_check
    if not chk.isChecked():
        L.set_check(chk, True)
    panel = tab._manual_layout_panel
    L.set_combo_data(panel.instr, "i1")
    L.set_combo_data(panel.paper, "A4")
    L.set_combo_data(panel.mode, "clip")
    L.pump(300)
    set_patch_count(tab, PATCHES)
    L.log(f"recipe before build: {json.dumps({k: v for k, v in L.recipe_of(tab).items() if k in ('instrument','paper','layout_mode','area_method','margin_top','margin_right','margin_bottom','margin_left','use_instrument_margins','clip_border','clip_content_mode','pscale','patch_area_align','randomize','dpi')})}")
    L.grab(win, OUT / "01-engine-on-before-generate.png")
    n0 = len(L.SERIOUS)
    watcher.expect("Give this project a name", "<reject>", note="should NOT appear")
    watcher.expect("already", "Continue this project", note="should NOT appear for a new name")
    L.click(tab._generate_btn)
    ok = L.wait_build(tab)
    watcher.clear()
    L.log(f"engine build finished ok={ok} serious={L.serious_since(n0)}")
    eng = capture("02-engine-built", win, tab)
    L.grab(tab._preview, OUT / "02-engine-preview.png")

    # ---------- printtarg (engine OFF) in a NEW run ----------
    L.set_combo_data(win._target_bar._run_combo, "\x00new")
    L.pump(1000)
    L.log(f"run bar now {win._target_bar._run_combo.currentText()!r}; location {win._target_bar._location.text()!r}")
    L.set_check(chk, False)
    L.pump(800)
    L.grab(win, OUT / "03-engine-off-before-generate.png")
    # confirm printtarg widgets
    for flag in ("-i", "-p", "-t", "-L", "-a", "-m", "-h", "-P", "-r", "-b"):
        w = pw(tab, "printtarg", flag)
        if w is not None:
            L.log(f"  printtarg {flag}: raw={w.get_raw_value()!r} visible={w.isVisible()} enabled={w.isEnabled()}")
    set_patch_count(tab, PATCHES)
    L.log(f"manual info lbl (printtarg): {tab._manual_info_lbl.text()[:400]!r}")
    n0 = len(L.SERIOUS)
    L.click(tab._generate_btn)
    ok = L.wait_build(tab)
    L.log(f"printtarg build finished ok={ok} serious={L.serious_since(n0)}")
    pt = capture("04-printtarg-built", win, tab)
    L.grab(tab._preview, OUT / "04-printtarg-preview.png")

    # ---------- engine back ON in a third run: same again for the toggle round trip ----------
    L.set_combo_data(win._target_bar._run_combo, "\x00new")
    L.pump(800)
    L.set_check(chk, True)
    L.pump(800)
    L.log(f"recipe after OFF->ON round trip: {json.dumps({k: v for k, v in L.recipe_of(tab).items() if k in ('instrument','paper','layout_mode','area_method','margin_top','margin_left','use_instrument_margins','clip_border','pscale','randomize')})}")
    L.grab(win, OUT / "05-engine-on-again.png")

    # ---------- parity: printtarg by hand on the engine's .ti1 ----------
    SCRATCH.mkdir(parents=True, exist_ok=True)
    eng_dir = Path(eng["run_dir"])
    ti1 = next(eng_dir.glob("*.ti1"), None)
    parity = {}
    if ti1:
        stem = SCRATCH / "parity"
        shutil.copy(ti1, stem.with_suffix(".ti1"))
        cmd = ["/Applications/Argyll/bin/printtarg", "-v", "-ii1", "-pA4", "-t300", "-M6", str(stem)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(SCRATCH))
            parity = {"cmd": " ".join(cmd), "rc": r.returncode,
                      "stdout": r.stdout[-2500:], "stderr": r.stderr[-1000:],
                      "inventory": L.run_inventory(SCRATCH)}
        except subprocess.TimeoutExpired:
            parity = {"cmd": " ".join(cmd), "error": "did not finish in 120 s"}
        # and once with -L (no clip border), which is the engine's noclip
        stem2 = SCRATCH / "parity_L"
        shutil.copy(ti1, stem2.with_suffix(".ti1"))
        cmd2 = ["/Applications/Argyll/bin/printtarg", "-v", "-ii1", "-pA4", "-t300", "-M6", "-L", str(stem2)]
        try:
            r = subprocess.run(cmd2, capture_output=True, text=True, timeout=120, cwd=str(SCRATCH))
            parity["L"] = {"cmd": " ".join(cmd2), "rc": r.returncode, "stdout": r.stdout[-1500:]}
        except subprocess.TimeoutExpired:
            parity["L"] = {"error": "timeout"}
    L.save_json(parity, L.LOGS / "d01_parity_printtarg_by_hand.json")

    L.log(f"dialogs seen: {watcher.seen}")
    L.log(f"unexpected: {watcher.unexpected}")
    L.log(f"all serious: {L.serious_since(0)}")
    win.close()
    L.pump(400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
