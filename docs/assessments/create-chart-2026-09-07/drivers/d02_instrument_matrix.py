#!/usr/bin/env python3
"""D02 (A2 + A3 part): every engine instrument and mode on A4 portrait, A4
landscape, A3 portrait, A3 landscape and a custom 200x200 sheet. Manual, engine
ON, Auto patch count, 1 page, default layout. For each build: the estimate the
panel showed BEFORE Generate, the build's actual numbers, the margin panel, the
files, and a preview shot. One project, one run, overwriting (no measurement,
so no S4 window is expected)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cc_lib as L  # noqa: E402

OUT = L.SHOTS / "A2-instruments"
PROJECT = "A2-Instruments"
COMBOS = [("i1", "clip"), ("i1", "noclip"), ("p3", "clip"), ("p3", "noclip"),
          ("CM", "freehand"), ("CM", "high"), ("CM", "extrahigh"),
          ("SS", "flat"), ("SS", "hex"), ("CR30", "flat"), ("CR30", "hex")]
PAPERS = ["A4", "A4R", "A3", "420x297", "custom:200x200"]
FULL = "--full" in sys.argv          # otherwise A4 + A3-landscape + custom


def set_paper(panel, code):
    if code.startswith("custom:"):
        w, h = code.split(":")[1].split("x")
        L.set_combo_data(panel.paper, "__custom__")
        L.set_spin(panel.custom_w, float(w))
        L.set_spin(panel.custom_h, float(h))
        return True
    return L.set_combo_data(panel.paper, code)


def main() -> int:
    app, settings = L.build_app()
    watcher = L.ModalWatcher(app)
    win = L.build_window(app, settings)
    tab = L.goto_chart_tab(win)
    L.click(tab._manual_btn)
    L.pump(400)
    tab._manual_target_name_edit.setText(PROJECT)
    tab._manual_target_name_edit.editingFinished.emit()
    L.pump(300)
    chk = tab._manual_engine_check
    if not chk.isChecked():
        L.set_check(chk, True)
    panel = tab._manual_layout_panel
    auto = tab._manual_auto_patches_check
    if auto is not None and not auto.isChecked():
        auto.click()
        L.pump(200)
    L.set_spin(panel.pages, 1)
    papers = PAPERS if FULL else ["A4", "420x297", "custom:200x200"]
    results = []
    first = True
    for instr, mode in COMBOS:
        for paper in papers:
            tag = f"{instr}-{mode}-{paper.replace(':', '_')}"
            t0 = time.time()
            # arm the dialogs this step may raise
            watcher.expect("scanner", "OK", note="hex heads-up (hex modes only)")
            watcher.expect("quite fill", "OK", note="last page hint")
            watcher.expect("already", "Continue this project", note="S4.7 on 2nd+ build")
            L.set_combo_data(panel.instr, instr)
            L.pump(200)
            L.set_combo_data(panel.mode, mode)
            L.pump(200)
            ok_paper = set_paper(panel, paper)
            L.pump(500)
            if not ok_paper:
                results.append({"tag": tag, "skipped": "paper not offered",
                                "papers": [d for _, d in L.combo_items(panel.paper)]})
                L.log(f"[{tag}] paper not offered")
                watcher.clear()
                continue
            before = L.panel_snapshot(tab)
            rec = L.recipe_of(tab)
            hm = {"helper_markers_enabled": panel.helper_markers_cb.isEnabled(),
                  "helper_markers_tip": panel.helper_markers_cb.toolTip()[:200]}
            info_before = tab._manual_info_lbl.text()
            n0 = len(L.SERIOUS)
            if first:
                watcher.expect("Give this project a name", "<reject>", note="should not appear")
                first = False
            L.click(tab._generate_btn)
            ok = L.wait_build(tab, 300_000)
            dialogs = [d.get("answer") + ":" + (d.get("title") or d.get("text", "")[:60]) for d in watcher.seen[-3:]]
            watcher.clear()
            after = L.panel_snapshot(tab)
            rd = L.current_run_dir(win)
            inv = L.run_inventory(rd) if rd else None
            L.grab(tab._preview, OUT / f"{tag}-preview.png")
            logtxt = L.tab_log_text(tab)
            eng_lines = [l for l in logtxt.splitlines() if "layout engine]" in l][-6:]
            crit = [l for l in logtxt.splitlines() if "[ERROR]" in l or "CRITICAL" in l][-3:]
            r = {"tag": tag, "instrument": instr, "mode": mode, "paper": paper,
                 "ok": ok, "secs": round(time.time() - t0, 1),
                 "estimate_before": before["layout_info_estimate"],
                 "actual_after": after["layout_info_actual"],
                 "estimate_after": after["layout_info_estimate"],
                 "margin_text": after["margin_panel_text"][:500],
                 "margin_status": after["margin_status"],
                 "recipe_key": {k: rec.get(k) for k in ("instrument", "paper", "layout_mode", "area_method",
                                                        "margin_top", "margin_right", "margin_bottom", "margin_left",
                                                        "use_instrument_margins", "clip_border", "clip_content_mode",
                                                        "hflag", "cm_density", "cm_stagger", "spacer_mode", "pscale",
                                                        "patch_area_align", "edge_spacers")},
                 "info_before": info_before[-260:],
                 "engine_log": eng_lines, "errors": crit, "serious": L.serious_since(n0),
                 "dialogs": dialogs, "helper": hm,
                 "files": [f for f, _ in (inv or {}).get("files", [])],
                 "tiffs": (inv or {}).get("tiffs"),
                 "ti2": {k: v for k, v in (inv or {}).items() if k.startswith("ti2")},
                 "channels": (inv or {}).get("channels"),
                 "pages_shown": tab._preview.page_count() if hasattr(tab._preview, "page_count") else None,
                 "unexpected": list(watcher.unexpected)}
            watcher.unexpected.clear()
            results.append(r)
            L.log(f"[{tag}] ok={ok} {r['secs']}s est_before={r['estimate_before']} actual={r['actual_after']} status={r['margin_status']!r} eng={eng_lines[-3:-1] if len(eng_lines) > 2 else eng_lines}")
            L.save_json(results, L.LOGS / "d02_matrix.json")
    L.log(f"all serious: {L.serious_since(0)}")
    win.close()
    L.pump(300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
