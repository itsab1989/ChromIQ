#!/usr/bin/env python3
"""B8-1541: in "Prioritise chart area" the Chart layout information's estimate
column disagreed with the chart on screen. Driven ON SCREEN.

    CHROMIQ_LOG_DIR=<sandbox> python scripts/drive_b8_1541_layout_estimate.py <out>

The estimate is defined in the panel's own help as "what the settings you have
right now would produce if you generate". So the question is not whether the
two columns differ while the preview shows an older chart re-laid out, but
whether pressing Generate then builds what the estimate promised. Knut's steps
(#182 5857405680), then Generate, in each layout mode and chart-area method:

1. patch-first with a typed size, Generate;
2. area-first, By columns / rows, 8 x 12: estimate recorded, Generate, the
   chart built recorded;
3. area-first, By patch width: the same;
4. the same on 2 and 3 pages;
5. the clip border off, to show what the 26 mm left edge is.

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

K36.DEADLINE_S = 900
# No help window is ours: every info window the drive does not answer itself
# is photographed and closed (the "Auto-update preview is on" window once sat
# unanswered because the shared watchdog exempts this class).
K36.OURS = set(K36.OURS) - {"_InfoDialog"}

_KEYS = ("total", "fillup", "page_patches", "rows", "cols", "pages", "patch")


def _cols(tab) -> dict:
    pnl = tab._layout_info_panel
    est = pnl.predicted() or {}
    act = dict(getattr(pnl, "_actual", None) or {})
    return {"estimate": {k: est.get(k) for k in _KEYS},
            "on_screen": {k: act.get(k) for k in _KEYS}}


def _left_mm(tab) -> str:
    from PyQt6.QtWidgets import QLabel
    box = getattr(tab, "_margin_panel", None) or tab
    texts = [w.text() for w in box.findChildren(QLabel)
             if w.isVisible() and w.text().strip()]
    for i, t in enumerate(texts):
        if t.startswith("Left (to first patch)") and i + 1 < len(texts):
            return texts[i + 1]
    return ""


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
        tab._manual_target_name_edit.setText("LayoutEstimate")
    if not tab._manual_engine_check.isChecked():
        tab._manual_engine_check.setChecked(True)
        yield 1500
    pnl = tab._manual_layout_panel
    if pnl.use_instr_margins.isChecked():
        pnl.use_instr_margins.setChecked(False)
        yield 500
    rec["auto_patch_count"] = bool(tab._manual_auto_patches_check.isChecked())

    def pick(combo, data):
        i = combo.findData(data)
        combo.setCurrentIndex(i)
        return i >= 0

    def generate(name, wait=20000):
        d.later(tab._generate_btn.click)
        yield wait
        rec[name] = _cols(tab)
        d.shot(d.win, name)

    # Knut's step 1: patch size first, with a typed size, a scale, an offset.
    pick(pnl.layout_mode, "patch_first")
    yield 800
    pnl.patch_x.setValue(14.0)
    pnl.patch_y.setValue(10.0)
    pnl.pscale.setValue(1.3)
    pnl.offx.setValue(6.0)
    pnl.offy.setValue(6.0)
    for k in ("t", "r", "b", "l"):
        pnl.margins[k].setValue(20.0)
    yield 800
    # Auto-update preview, as in B8-1540's drive: ticking it opens ChromIQ's
    # "Auto-update preview is on" window, answered with its only button.
    K36.EXPECTED.add("_InfoDialog")
    d.later(lambda: tab._auto_preview_check.setChecked(True))
    yield 300
    rec["auto_update_popup"] = d.answer("close", "00-auto-update-popup",
                                        within_ms=6000)
    K36.EXPECTED.discard("_InfoDialog")
    yield 400
    yield from generate("01-patch-first-generated")

    # Knut's step 2: chart area first, by columns / rows, then Generate.
    pick(pnl.layout_mode, "area_first")
    yield 800
    pick(pnl.area_method, "by_grid")
    yield 600
    pnl.area_cols.setValue(8)
    pnl.area_rows.setValue(12)
    yield 12000
    rec["02-by-grid-before-generate"] = _cols(tab)
    d.shot(d.win, "02-by-grid-before-generate")
    yield from generate("03-by-grid-generated")

    # Knut's step 3: by patch width, then Generate.
    pick(pnl.area_method, "by_width")
    yield 12000
    rec["04-by-width-before-generate"] = _cols(tab)
    d.shot(d.win, "04-by-width-before-generate")
    yield from generate("05-by-width-generated")

    # 2 and 3 pages, both methods.
    for pages in (2, 3):
        tab._manual_pages_spin.setValue(pages)
        yield 1500
        for method in ("by_grid", "by_width"):
            pick(pnl.area_method, method)
            yield 8000
            name = f"06-{method}-{pages}p"
            rec[name + "-before"] = _cols(tab)
            yield from generate(name + "-generated")

    # Patch size first on 2 pages, the third mode.
    pick(pnl.layout_mode, "patch_first")
    yield 8000
    rec["07-patch-first-2p-before"] = _cols(tab)
    yield from generate("07-patch-first-2p-generated")

    # The 26 mm left edge: the i1Pro clip border, on then off.
    tab._manual_pages_spin.setValue(1)
    pick(pnl.layout_mode, "area_first")
    pick(pnl.area_method, "by_grid")
    yield 8000
    yield from generate("08-clip-border-on")
    rec["08-left-with-clip"] = _left_mm(tab)
    rec["08-clip-width-mm"] = pnl.clip_width.value()
    # THE i1Pro's CLIP BORDER IS ITS Mode COMBO ("clip" / "noclip"). The
    # "Clip border" combo is the CM / SS / CR30 switch; on an i1Pro it is
    # hidden and clears only the band's content, so the 26 mm stays reserved.
    # Using it here measured a border this drive had not switched off.
    rec["09-mode-noclip-found"] = pick(pnl.mode, "noclip")
    yield 8000
    yield from generate("09-clip-border-off")
    rec["09-left-without-clip"] = _left_mm(tab)
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
