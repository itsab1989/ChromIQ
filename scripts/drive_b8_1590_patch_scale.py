#!/usr/bin/env python3
"""B8-1590 on screen: the patch scale in "Prioritise chart area".

Picks, in Create Chart > Manual, one of Knut's i1Pro 7.5 mm presets (its 0.75
is the SPACER scale) and one of his photo cards (patch scale 0.95), each
generating on selection, and photographs the window with Chart layout
information in view. Then photographs the Layout panel's Basic section in
"Prioritise chart area", where, by Knut's ruling (#182 5859162180), the Patch
scale row is not shown and the patch scale has no effect: the photo card lays
out as beta 45 laid it out (plen 7.36, pspa 0.60).

Run from the tree whose behaviour you want (the fix, or an exported beta 45):

    CHROMIQ_LOG_DIR=<sandbox> python scripts/drive_b8_1590_patch_scale.py <out>
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

TREE = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, TREE + "/scripts")
sys.path.insert(0, TREE)
from userdrive import Drive                                    # noqa: E402
import drive_b42_k36 as K36                                    # noqa: E402

K36.DEADLINE_S = 600
# The "Auto-update preview is on" window is ChromIQ's own _InfoDialog, which
# the shared watchdog lets through; this driver never ticks that box, and if
# the window appears anyway the watchdog answers it (Close) and records it.
K36.OURS = set(K36.OURS) - {"_InfoDialog"}

PRESETS = (
    ("01-i1pro-a4-324p-spacer-scale-075",
     "__chromiq_knut_i1_w75_a4_324p_1page_portrait_w7_5mm__", 324),
    ("02-photo-card-150p-patch-scale-095",
     "__chromiq_knut_i1_photo_100x150mm_150p_1page_portrait_w7_5mm__", 150),
)


def _texts(pnl) -> dict:
    return {k: w.text() for k, w in pnl.items()}


def script(d):
    rec = d.record
    assert os.environ.get("CHROMIQ_LOG_DIR"), "SANDBOX THE LOG FIRST"
    K36._install_watchdog(d, rec)
    rec["tree"] = TREE
    yield 600
    d.goto_tab("chart")
    tab = d.win._tab_chart
    yield 800
    tab._user_switch_mode("manual")
    yield 1500
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("PatchScaleB81590")
    yield 300
    from workflow.layout_engine import geometry, instruments, papers
    for shot, key, n in PRESETS:
        combo = tab._preset_combo
        idx = combo.findData(key)
        entry = rec.setdefault("presets", {}).setdefault(shot, {})
        entry["found"] = idx >= 0
        if idx < 0:
            continue
        combo.setCurrentIndex(idx)
        combo.activated.emit(idx)
        yield 25000
        pnl = tab._manual_layout_panel
        r = pnl.get_recipe()
        g = instruments.geom_from_build_kwargs(r.build_kwargs())
        w, h = papers.dimensions_mm(r.paper)
        lay = geometry.compute(g, w, h, n)
        pp = tab._layout_info_panel
        entry.update({
            "layout_mode": r.layout_mode, "pscale": r.pscale, "sscale": r.sscale,
            "engine_pscale": r.build_kwargs()["pscale"],
            "engine_plen": round(g.plen, 3), "engine_pwid": round(g.pwid, 3),
            "engine_pspa": round(g.pspa, 3), "steps_in_pass": lay.steps_in_pass,
            "strips_per_page": lay.strips_per_page, "pages": lay.pages,
            "pscale_row_visible": all(w_.isVisible() for w_ in pnl._patch_scale_row),
            "on_screen": _texts(pp._actual_labels),
            "estimate": _texts(pp._estimate_labels),
        })
        d.shot(d.win, shot)
        yield 800
    # The Layout panel's Basic section, scrolled into view, in area-first.
    pnl = tab._manual_layout_panel
    try:
        from PyQt6.QtWidgets import QScrollArea
        w0 = pnl._patch_scale_row[1] if pnl._patch_scale_row[1].isVisible() \
            else pnl.layout_mode
        p = w0.parent()
        while p is not None and not isinstance(p, QScrollArea):
            p = p.parent()
        if p is not None:
            p.ensureWidgetVisible(pnl.layout_mode, 50, 200)
    except Exception as exc:  # noqa: BLE001
        rec["scroll_error"] = repr(exc)
    yield 800
    rec["panel_area_first"] = {
        "layout_mode": pnl.layout_mode.currentData(),
        "patch_scale_row_visible": all(w_.isVisible() for w_ in pnl._patch_scale_row),
        "patch_size_row_visible": any(w_.isVisible() for w_ in pnl._patch_size_row),
        "patch_scale_value": pnl.pscale.value(),
    }
    d.shot(d.win, "03-layout-panel-area-first")
    yield 800


def main() -> int:
    out = Path(sys.argv[1])
    d = Drive(out, projects=[], language="en", appearance="light")
    rc = d.run(script)
    (out / "record.json").write_text(
        json.dumps(d.record, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8")
    print(f"rc={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
