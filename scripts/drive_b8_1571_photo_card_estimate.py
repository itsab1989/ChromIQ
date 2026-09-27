#!/usr/bin/env python3
"""B8-1571 on screen: Knut's 10 x 15 cm photo card, selected in Create Chart,
Manual (it generates on selection). After Generate, Chart layout information's
"on screen" and "estimate" patch sizes must read the same. Records the panel's
text and photographs the window. Adapted from challenge 4b's driver.

    CHROMIQ_LOG_DIR=<sandbox> python scripts/drive_b8_1571_photo_card_estimate.py <out>
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
K36.OURS = set(K36.OURS) - {"_InfoDialog"}

KEY = "__chromiq_knut_i1_photo_100x150mm_150p_1page_portrait_w7_5mm__"


def _info(tab) -> str:
    from PyQt6.QtWidgets import QLabel
    pnl = getattr(tab, "_layout_info_panel", None)
    if pnl is None:
        return ""
    return " | ".join(w.text() for w in pnl.findChildren(QLabel)
                      if w.isVisible() and w.text().strip())


def script(d):
    rec = d.record
    assert os.environ.get("CHROMIQ_LOG_DIR"), "SANDBOX THE LOG FIRST"
    K36._install_watchdog(d, rec)
    yield 600
    d.goto_tab("chart")
    tab = d.win._tab_chart
    yield 800
    tab._user_switch_mode("manual")
    yield 1500
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("PhotoCardB81571")
    yield 300
    combo = tab._preset_combo
    idx = combo.findData(KEY)
    rec["preset_found"] = idx >= 0
    if idx < 0:
        return
    combo.setCurrentIndex(idx)
    combo.activated.emit(idx)
    yield 25000
    pnl = tab._manual_layout_panel
    r = pnl.get_recipe()
    from workflow.layout_engine import geometry, instruments, papers
    g = instruments.geom_from_build_kwargs(r.build_kwargs())
    w, h = papers.dimensions_mm(r.paper)
    lay = geometry.compute(g, w, h, 150)
    rec["panel"] = {
        "layout_mode": r.layout_mode, "area_method": r.area_method,
        "pscale_stored": r.pscale, "sscale": r.sscale,
        "pscale_widget_visible": pnl.pscale.isVisible(),
        "engine_plen": round(g.plen, 3), "engine_pwid": round(g.pwid, 3),
        "engine_pspa": round(g.pspa, 3),
        "steps_in_pass": lay.steps_in_pass, "pages": lay.pages,
    }
    rec["info"] = _info(tab)
    pp = tab._layout_info_panel
    rec["patch_on_screen"] = pp._actual_labels["patch"].text()
    rec["patch_estimate"] = pp._estimate_labels["patch"].text()
    d.shot(d.win, "01-photo-card-150p-generated")
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
