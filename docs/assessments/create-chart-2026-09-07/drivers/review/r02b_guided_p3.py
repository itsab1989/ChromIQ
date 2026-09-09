#!/usr/bin/env python3
"""R02b: the two p3 Guided builds of R02 again, selecting the instrument by
its data key ("p3") instead of by text (R02's text match hit the i1 row).
Also i1 Letter landscape and CM A4 landscape for the same question: which
Guided defaults are red under the shipped seeds without any clamp."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import r_lib as L  # noqa: E402

OUT = L.SHOTS / "R02-f007-f018"
PROJECT = "R2-Guided"
R: dict = {}


def guided(tab, win, watcher, instr_key, paper_key, pages, label):
    L.click(tab._guided_btn); L.pump(400)
    ok_i = L.set_combo_data(tab._instr_combo, instr_key); L.pump(400)
    ok_p = L.set_combo_data(tab._paper_combo, paper_key)
    L.set_spin(tab._pages_spin, pages); L.pump(600)
    head = tab._patch_count_lbl.text()
    n0 = len(L.APP_LINES)
    s = L.gen(tab, watcher, label, extra_expect=[("already", "Continue")])
    run_dir = L.current_run_dir(win)
    ch = L.read_json(next(run_dir.glob("*.channels.json"), Path("/nonexistent")))
    rec = ((ch or {}).get("layout") or {}).get("recipe") or {}
    out = {"instr_text": tab._instr_combo.currentText(), "paper_text": tab._paper_combo.currentText(),
           "ok": (ok_i, ok_p), "headline": head, "snap": s,
           "recipe_margins": [rec.get(k) for k in ("margin_top", "margin_right", "margin_bottom", "margin_left")],
           "recipe_instr": rec.get("instrument"), "clamp_lines": L.app_lines_since(n0, r"raised|threshold|clamp"),
           "guided_info": tab._guided_info_lbl.text() if hasattr(tab, "_guided_info_lbl") else None}
    L.log(f"  GUIDED {label}: {out['instr_text']!r} {out['paper_text']!r} head={head[:4]!r} built={s['layout_info_actual']} status={s['margin_status']!r} recipe={out['recipe_instr']} {out['recipe_margins']} clamp={out['clamp_lines']}")
    return out


def main() -> int:
    app, settings = L.build_app()
    watcher = L.ModalWatcher(app)
    win = L.build_window(app, settings)
    L.open_project(win, settings, PROJECT)
    tab = L.goto_chart_tab(win)
    L.click(tab._guided_btn); L.pump(300)
    L.log(f"paper keys={L.combo_items(tab._paper_combo)}")
    R["p3_A4R"] = guided(tab, win, watcher, "p3", "A4R", 1, "p3 A4 landscape")
    L.grab(win, OUT / "06-guided-p3-A4R-real.png")
    R["p3_A4"] = guided(tab, win, watcher, "p3", "A4", 1, "p3 A4 portrait")
    L.grab(win, OUT / "07-guided-p3-A4-real.png")
    R["i1_LetterR"] = guided(tab, win, watcher, "i1", "LetterR", 1, "i1 Letter landscape")
    R["CM_A4R"] = guided(tab, win, watcher, "CM", "A4R", 1, "CM A4 landscape")
    L.grab(win, OUT / "08-guided-CM-A4R.png")
    R["i1_A4_2p"] = guided(tab, win, watcher, "i1", "A4", 2, "i1 A4 portrait 2 pages")
    R["unexpected"] = watcher.unexpected; R["serious"] = L.serious_since(0)
    L.save_json(R, L.LOGS / "r02b_results.json")
    L.log(f"unexpected={watcher.unexpected} serious={L.serious_since(0)}")
    win.close(); L.pump(300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
