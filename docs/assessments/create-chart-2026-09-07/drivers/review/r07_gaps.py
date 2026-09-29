#!/usr/bin/env python3
"""R07: gaps Agent 1 listed as not reached. Keyboard focus order (window
activated, read through win.focusWidget()), Delete run from the bar
(cancelled), expert targen/printtarg rows (preview line vs executed command),
the Guided Refinement profile row (empty path, then a real .icc), a run
folder with files removed by hand (.tif, .ti2, channels.json), each restored
before the next. Project R2-Guided. Unattended."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import r_lib as L  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

OUT = L.SHOTS / "R07-gaps"
R: dict = {}
PROJ = Path("/Users/Basti/ChromIQ-assessment")
RUN1 = PROJ / "R2-Guided" / "runs" / "run1"
BACKUP = Path("/private/tmp/claude-502/-Users-Basti-develop-ChromIQ/43fe026d-47c0-4e05-aad3-52c64d8d9eca/scratchpad/r2guided_run1_backup")


def desc(w) -> str:
    if w is None:
        return "None"
    t = type(w).__name__
    txt = ""
    for attr in ("text", "currentText", "placeholderText"):
        f = getattr(w, attr, None)
        if callable(f):
            try:
                v = f()
                if v:
                    txt = v.replace("\n", " ")[:36]
                    break
            except Exception:  # noqa: BLE001
                pass
    return f"{t}({w.objectName() or ''}|{txt})"


def main() -> int:
    app, settings = L.build_app()
    watcher = L.ModalWatcher(app)
    win = L.build_window(app, settings)
    tab = L.goto_chart_tab(win)
    bar = win._target_bar
    tab.open_project_manifest(PROJ / "R2-Guided" / "project.json"); L.pump(1500)

    # ---------- keyboard focus order ----------
    win.activateWindow(); win.raise_(); L.pump(500)
    def tab_order(start, n):
        start.setFocus(); L.pump(150)
        seq = [desc(win.focusWidget())]
        for _ in range(n):
            win.focusNextChild(); L.pump(40)
            seq.append(desc(win.focusWidget()))
        return seq
    L.click(tab._manual_btn); L.pump(300)
    R["focus_manual"] = tab_order(tab._manual_target_name_edit, 50)
    L.click(tab._guided_btn); L.pump(300)
    R["focus_guided"] = tab_order(tab._target_name_edit, 30)
    L.log("  FOCUS manual: " + " > ".join(R["focus_manual"]))
    L.log("  FOCUS guided: " + " > ".join(R["focus_guided"]))

    # ---------- Delete run via the bar (cancel) ----------
    ns = len(watcher.seen)
    watcher.expect("Delete", "Cancel")
    L.click(bar._delete_btn); L.pump(1500); watcher.clear()
    R["delete_run"] = {"dialogs": [((d.get("title") or ""), (d.get("text") or "")[:500], d.get("buttons"), d.get("answer")) for d in watcher.seen[ns:]],
                       "runs_after": sorted(p.name for p in (PROJ / "R2-Guided" / "runs").glob("run*"))}
    L.log(f"  DELETE run (cancelled): {R['delete_run']}")

    # ---------- expert rows (engine off) ----------
    L.click(tab._manual_btn); L.pump(300)
    L.set_check(tab._manual_engine_check, False); L.pump(500)
    auto = tab._manual_auto_patches_check
    if not auto.isChecked():
        auto.click(); L.pump(200)
    exp = {}
    for tool, flag, val in (("printtarg", "-A", 1.5), ("printtarg", "-R", 4242), ("targen", "-N", 0.9), ("printtarg", "-n", True)):
        w = L.pw(tab, tool, flag)
        if w is None:
            exp[f"{tool} {flag}"] = "no widget"; continue
        try:
            if w.has_separate_enable:
                w.set_user_enabled(True)
            w.set_value(val)
            exp[f"{tool} {flag}"] = {"raw": w.get_raw_value(), "enabled": w.is_enabled_by_user, "args": w.build_args(), "visible": w.isVisible(), "expert": w.expert_only}
        except Exception as e:  # noqa: BLE001
            exp[f"{tool} {flag}"] = f"error {e!r}"
    L.pump(500)
    R["expert"] = {"set": exp, "preview": tab._manual_info_lbl.text()}
    n0 = len(L.APP_LINES)
    s = L.gen(tab, watcher, "expert rows printtarg build", extra_expect=[("already", "Continue")])
    R["expert"].update({"executed": L.app_lines_since(n0, r"Run: .*(targen|printtarg)"), "actual": s["layout_info_actual"], "errors": s["errors"]})
    L.log(f"  EXPERT: preview={R['expert']['preview']!r}\n     executed={R['expert']['executed']}")
    L.grab(win, OUT / "e01-expert-rows.png")
    # reset the expert rows
    for tool, flag in (("printtarg", "-A"), ("printtarg", "-R"), ("targen", "-N"), ("printtarg", "-n")):
        w = L.pw(tab, tool, flag)
        if w is not None:
            w.reset_to_default()
    # does a printtarg expert row leak into an engine build?
    L.set_check(tab._manual_engine_check, True); L.pump(500)
    w = L.pw(tab, "printtarg", "-A")
    if w is not None:
        w.set_user_enabled(True) if w.has_separate_enable else None
        w.set_value(1.5)
    L.pump(300)
    R["expert_engine"] = {"preview": tab._manual_info_lbl.text(), "A_visible": w.isVisible() if w else None}
    L.log(f"  EXPERT under engine: {R['expert_engine']}")
    if w is not None:
        w.reset_to_default()

    # ---------- Guided refinement profile row ----------
    L.click(tab._guided_btn); L.pump(300)
    L.set_combo_data(tab._instr_combo, "i1"); L.set_combo_data(tab._paper_combo, "A4"); L.set_spin(tab._pages_spin, 1)
    L.set_check(tab._guided_precond_check, True); tab._guided_precond_path.setText(""); L.pump(300)
    R["refine_empty"] = {"checked": tab._guided_precond_check.isChecked(), "path_enabled": tab._guided_precond_path.isEnabled(),
                         "info": tab._guided_info_lbl.text()[:200] if hasattr(tab, "_guided_info_lbl") else None, "gen_enabled": tab._generate_btn.isEnabled()}
    ns = len(watcher.seen); n0 = len(L.APP_LINES)
    watcher.expect("quite fill", "OK"); watcher.expect("already", "Continue"); watcher.expect("profile", "<reject>")
    L.click(tab._generate_btn); L.wait_build(tab, 180_000); L.pump(1200); watcher.clear()
    R["refine_empty"].update({"dialogs": [(d.get("class"), d.get("title"), (d.get("text") or "")[:300], d.get("buttons"), d.get("answer")) for d in watcher.seen[ns:]],
                              "targen": L.app_lines_since(n0, r"Run: .*targen"), "errors": L.app_lines_since(n0, r"ERROR|WARNING"), "loc": bar._location.text()})
    L.log(f"  REFINE empty path: {R['refine_empty']}")
    L.grab(win, OUT / "r01-refine-empty.png")
    icc = PROJ / "Demo-Full-RGB" / "runs" / "run1" / "Demo-Full-RGB.icc"
    tab._guided_precond_path.setText(str(icc)); L.pump(400)
    R["refine_icc"] = {"icc_exists": icc.exists(), "info": tab._guided_info_lbl.text()[:240] if hasattr(tab, "_guided_info_lbl") else None,
                       "runs_before": sorted(p.name for p in (PROJ / "R2-Guided" / "runs").glob("run*"))}
    ns = len(watcher.seen); n0 = len(L.APP_LINES)
    watcher.expect("quite fill", "OK"); watcher.expect("already", "Continue"); watcher.expect("pre-conditioning", "<accept>"); watcher.expect("refine", "<accept>")
    L.click(tab._generate_btn); L.wait_build(tab, 180_000); L.pump(1500); watcher.clear()
    run_dir = L.current_run_dir(win)
    R["refine_icc"].update({"dialogs": [(d.get("class"), d.get("title"), (d.get("text") or "")[:300], d.get("buttons"), d.get("answer")) for d in watcher.seen[ns:]],
                            "targen": L.app_lines_since(n0, r"Run: .*targen"), "errors": L.app_lines_since(n0, r"ERROR|WARNING"),
                            "loc": bar._location.text(), "runs_after": sorted(p.name for p in (PROJ / "R2-Guided" / "runs").glob("run*")),
                            "run_files": sorted(p.name for p in run_dir.glob("*")) if run_dir else None,
                            "actual": L.panel_snapshot(tab)["layout_info_actual"]})
    L.log(f"  REFINE with icc: {R['refine_icc']}")
    L.grab(win, OUT / "r02-refine-icc.png")
    L.set_check(tab._guided_precond_check, False); tab._guided_precond_path.setText(""); L.pump(200)

    # ---------- run folder with files removed by hand ----------
    tab.open_project_manifest(PROJ / "R2-Guided" / "project.json"); L.pump(1200)
    L.set_combo_data(bar._run_combo, "run1"); L.pump(1200)
    if BACKUP.exists():
        shutil.rmtree(BACKUP)
    shutil.copytree(RUN1, BACKUP)
    stem = "R2-Guided"
    R["removed"] = {}
    other = [p.name for p in (PROJ / "R2-Guided" / "runs").glob("run*") if p.name != "run1"]
    for victim in (f"{stem}.tif", f"{stem}.ti2", f"{stem}.channels.json", f"{stem}.ti1"):
        # restore a pristine run1 first
        for p in RUN1.glob("*"):
            if p.is_file():
                p.unlink()
        for p in BACKUP.glob("*"):
            if p.is_file():
                shutil.copy2(p, RUN1 / p.name)
        (RUN1 / victim).unlink()
        n0 = len(L.APP_LINES); ns = len(watcher.seen)
        # switch away and back so the run is re-read
        if other:
            L.set_combo_data(bar._run_combo, other[0]); L.pump(1000)
        else:
            L.set_combo_data(bar._run_combo, "\x00new"); L.pump(1000)
        L.set_combo_data(bar._run_combo, "run1"); L.pump(1500)
        snap = L.panel_snapshot(tab)
        R["removed"][victim] = {"preview_pages": snap["preview_pages"], "status": snap["margin_status"], "status_visible": snap["margin_status_visible"],
                                "actual": snap["layout_info_actual"], "notice": getattr(tab._preview, "_notice_text", None),
                                "dialogs": [((d.get("title") or ""), (d.get("text") or "")[:160], d.get("answer")) for d in watcher.seen[ns:]],
                                "errors": L.app_lines_since(n0, r"ERROR|WARNING|Traceback")[:4], "gen_enabled": tab._generate_btn.isEnabled(),
                                "run_files_now": sorted(p.name for p in RUN1.glob("*")), "info_line": tab._manual_info_lbl.text()[:120] if tab._manual_btn.isChecked() else None}
        L.log(f"  REMOVED {victim}: pages={snap['preview_pages']} status={snap['margin_status']!r} actual={snap['layout_info_actual'] and snap['layout_info_actual'].get('total')} errors={R['removed'][victim]['errors'][:2]} dialogs={R['removed'][victim]['dialogs']}")
        L.grab(win, OUT / f"x-removed-{victim.split('.', 1)[1].replace('.', '-')}.png")
    # restore pristine
    for p in RUN1.glob("*"):
        if p.is_file():
            p.unlink()
    for p in BACKUP.glob("*"):
        if p.is_file():
            shutil.copy2(p, RUN1 / p.name)

    R["unexpected"] = watcher.unexpected; R["serious"] = L.serious_since(0)
    L.save_json(R, L.LOGS / "r07_results.json")
    L.log(f"unexpected={[(u.get('title'), (u.get('text') or '')[:120]) for u in watcher.unexpected]} serious={L.serious_since(0)}")
    win.close(); L.pump(300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
