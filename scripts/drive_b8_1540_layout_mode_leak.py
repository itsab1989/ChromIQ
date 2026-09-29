#!/usr/bin/env python3
"""B8-1540 (Knut, #182 5857405680): a patch size typed in "Prioritise patch
size, then fit to page" still ruled the preview after switching to
"Prioritise chart area, then fit patches to it", driven ON SCREEN.

    CHROMIQ_LOG_DIR=<sandbox> python scripts/drive_b8_1540_layout_mode_leak.py <out>

Knut's steps, as a user takes them, in Create Chart, Manual, the ChromIQ
engine on:

1. "Prioritise patch size, then fit to page", a patch size typed in (not
   auto), a patch scale and a chart offset set too;
2. "Prioritise chart area, then fit patches to it", "By columns / rows",
   8 strips by 12 rows, margins 20 mm all round;
3. "By patch width", the other chart-area method;
4. back to "Prioritise patch size": the typed values must come back.

Each step photographs the whole window (the preview and the Chart layout
information beside it) and records what the layout information says.
Settings, presets and output are sandboxed by `userdrive`, the log by
CHROMIQ_LOG_DIR, the ISO file forced to the repository's own.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

TREE = os.environ.get("CHROMIQ_TREE") or str(Path(__file__).resolve().parents[1])
sys.path.insert(0, TREE + "/scripts")
sys.path.insert(0, TREE)
from userdrive import Drive                                    # noqa: E402
import drive_b42_k36 as K36                                    # noqa: E402

K36.DEADLINE_S = 600
# THIS DRIVE OPENS NO HELP WINDOW, so no `_InfoDialog` is ever ours. The shared
# watchdog exempts that class (the evenness drive opens help popups on
# purpose), and that exemption let ChromIQ's "Auto-update preview is on" window
# sit unanswered on screen until Basti saw it. Here every info window the drive
# does not answer itself is photographed and closed.
K36.OURS = set(K36.OURS) - {"_InfoDialog"}


def _info(tab) -> str:
    from PyQt6.QtWidgets import QLabel
    pnl = getattr(tab, "_layout_info_panel", None)
    if pnl is None:
        return ""
    return " | ".join(w.text() for w in pnl.findChildren(QLabel)
                      if w.isVisible() and w.text().strip())


def _engine_estimate(pnl) -> dict:
    """What the engine lays out for the panel's recipe, as the preview does."""
    from workflow.layout_engine import geometry, instruments, papers
    r = pnl.get_recipe()
    g = instruments.geom_from_build_kwargs(r.build_kwargs())
    w, h = papers.dimensions_mm(r.paper)
    lay = geometry.compute(g, w, h, 100_000)
    return {"patch_w": round(g.pwid, 2), "patch_h": round(g.plen, 2),
            "per_page": lay.patches_per_page,
            "stored_patch_w": r.patch_w_mm, "stored_patch_h": r.patch_h_mm,
            "stored_pscale": r.pscale, "stored_offset": (r.offset_x_mm,
                                                          r.offset_y_mm),
            "layout_mode": r.layout_mode, "area_method": r.area_method}


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
        tab._manual_target_name_edit.setText("LayoutModeLeak")
    if not tab._manual_engine_check.isChecked():
        tab._manual_engine_check.setChecked(True)
        yield 1500
    pnl = tab._manual_layout_panel
    if pnl.use_instr_margins.isChecked():
        pnl.use_instr_margins.setChecked(False)
        yield 500

    def pick(combo, data):
        i = combo.findData(data)
        combo.setCurrentIndex(i)
        return i >= 0

    # 1. patch size first, with a typed size, a scale and an offset
    rec["patch_first"] = pick(pnl.layout_mode, "patch_first")
    yield 800
    pnl.patch_x.setValue(14.0)
    pnl.patch_y.setValue(10.0)
    pnl.pscale.setValue(1.3)
    pnl.offx.setValue(6.0)
    pnl.offy.setValue(6.0)
    for k in ("t", "r", "b", "l"):
        pnl.margins[k].setValue(20.0)
    yield 800
    # A real chart first, so the preview has something to show; after that
    # "Auto-update preview" re-renders it on every change, as for a user.
    # Ticking the box opens ChromIQ's "Auto-update preview is on" window
    # (tab_chart._on_auto_preview_toggled, an InfoDialog with one OK). It
    # opens for anybody who ticks the box; it is not part of Knut's fault.
    # Ticked from `later` so its exec() cannot block this step, and answered
    # with its only button, "Close", as a user would.
    K36.EXPECTED.add("_InfoDialog")
    d.later(lambda: tab._auto_preview_check.setChecked(True))
    yield 300
    rec["auto_update_popup"] = d.answer("close", "00-auto-update-popup",
                                        within_ms=6000)
    K36.EXPECTED.discard("_InfoDialog")
    rec["auto_update_on"] = tab._auto_preview_check.isChecked()
    yield 400
    d.later(tab._generate_btn.click)
    yield 20000
    rec["1_patch_first"] = {"engine": _engine_estimate(pnl), "info": _info(tab)}
    d.shot(d.win, "01-patch-first-typed-size")

    # 2. chart area first, by columns / rows
    rec["area_first"] = pick(pnl.layout_mode, "area_first")
    yield 800
    rec["by_grid"] = pick(pnl.area_method, "by_grid")
    yield 600
    pnl.area_cols.setValue(8)
    pnl.area_rows.setValue(12)
    yield 12000
    rec["2_area_by_grid"] = {"engine": _engine_estimate(pnl), "info": _info(tab)}
    d.shot(d.win, "02-area-first-by-columns-rows")

    # 3. chart area first, by patch width
    rec["by_width"] = pick(pnl.area_method, "by_width")
    yield 12000
    rec["3_area_by_width"] = {"engine": _engine_estimate(pnl), "info": _info(tab)}
    d.shot(d.win, "03-area-first-by-patch-width")

    # 4. back to patch size first: the typed values come back
    pick(pnl.layout_mode, "patch_first")
    yield 12000
    rec["4_back_to_patch_first"] = {
        "engine": _engine_estimate(pnl), "info": _info(tab),
        "fields": (pnl.patch_x.value(), pnl.patch_y.value(),
                   pnl.pscale.value(), pnl.offx.value(), pnl.offy.value())}
    d.shot(d.win, "04-back-to-patch-first")
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
