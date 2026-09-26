#!/usr/bin/env python3
"""K50 (Knut, #182 5845519118 and 5845588201): Create Chart, ON SCREEN.

    python scripts/drive_k50_create_chart.py OUT_DIR [lists] [frames]

lists   B8-1310: Manual, Paper "Custom…" at 420 x 297, 210 x 297 and
        250 x 300 (engine on), and 210 x 297 with the engine off (printtarg's
        own Custom), each after A4 Landscape so a stale list would show. For
        each: the class the filter reads, both lists' groups, and a
        photograph of each list open over the window.
frames  B8-1311: a 1512 x 982 window (a MacBook Pro 14"'s screen in points),
        Manual, the Output and Presets frames open (the default), then both
        folded: the height the parameters' scroll area gets, how far it
        scrolls, and photographs, the parameters scrolled to the bottom too.

Nothing is patched out of the app; a watchdog is not needed because nothing
here opens a modal (a preset is never chosen). Sandbox: userdrive's (settings,
presets, the ISO file forced to the repo's). Run with CHROMIQ_TREE pointing at
another tree for the "before" pictures.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_TREE = Path(os.environ.get("CHROMIQ_TREE")
             or Path(__file__).resolve().parents[1]).resolve()
sys.path.insert(0, str(_TREE / "scripts"))
sys.path.insert(0, str(_TREE))
sys.path.insert(0, str(Path(__file__).resolve().parent))

OUT = Path(sys.argv[1]).resolve()
WHAT = set(sys.argv[2:]) or {"lists", "frames"}
OUT.mkdir(parents=True, exist_ok=True)
os.environ["CHROMIQ_SETTINGS_FILE"] = str(OUT / "sandbox" / "settings.ini")
os.environ["CHROMIQ_PRESETS_DIR"] = str(OUT / "sandbox" / "presets")
(OUT / "sandbox" / "presets").mkdir(parents=True, exist_ok=True)

from userdrive import Drive                                   # noqa: E402
from drive_b8_1319_preset_list_scroll_bar import (            # noqa: E402
    shoot_popup_over_window)

FRAME_W, FRAME_H = 1512, 982


def script(d):
    from PyQt6.QtWidgets import QApplication, QScrollArea
    d.goto_tab("chart")
    yield 2000
    tab = d.win._tab_chart
    rec = d.record
    tab._manual_btn.click()
    yield 1500

    def lists_now():
        cb = tab._preset_combo
        tab._reveal_current_preset_group()
        view = cb.view()
        heads = {h for h, _e in __import__("ui.tabs.tab_chart", fromlist=["x"])
                 .BUILTIN_PRESET_GROUPS}
        pull = []
        for r in range(cb.count()):
            if view.isRowHidden(r):
                continue
            t, k = cb.itemText(r), cb.itemData(r)
            if k is None and t in heads:
                pull.append([t, 0])
            elif pull and isinstance(k, str) and not cb.itemData(r, cb.MORE_ROLE):
                pull[-1][1] += 1
        return pull

    if "lists" in WHAT:
        rec["lists"] = []
        cells = [("engine-on", True, (420, 297)), ("engine-on", True, (210, 297)),
                 ("engine-on", True, (250, 300)), ("engine-off", False, (210, 297))]
        only = os.environ.get("K50_SIZES")        # e.g. "250x300"
        if only:
            cells = [c for c in cells if f"{c[2][0]}x{c[2][1]}" in only.split(",")]
        for tag, engine, (w, h) in cells:
            if bool(tab._manual_engine_check.isChecked()) != engine:
                tab._manual_engine_check.click()
                yield 2000
            if engine:
                p = tab._manual_layout_panel
                i = p.paper.findData("A4R")
                p.paper.setCurrentIndex(i); p.paper.activated.emit(i)
                yield 1200
                p.custom_w.setValue(w); p.custom_h.setValue(h)
                i = p.paper.findData("__custom__")
                p.paper.setCurrentIndex(i); p.paper.activated.emit(i)
                yield 1500
            else:
                pw = tab._manual_paper_pw
                c = pw._custom_combo
                i = c.findData("A4R")
                c.setCurrentIndex(i); c.activated.emit(i)
                yield 1200
                pw._custom_w_spin.setValue(w); pw._custom_h_spin.setValue(h)
                i = c.findData("custom")
                c.setCurrentIndex(i); c.activated.emit(i)
                yield 1500
            name = f"{tag}-custom-{w}x{h}"
            cell = {"cell": name, "paper_on_screen": tab._manual_paper_on_screen(),
                    "filter_class": tab._preset_paper_selected(),
                    "select_preset_groups": lists_now()}
            d.shot(tab, f"{name}-00-panel")
            tab._preset_combo.showPopup()
            yield 1500
            ok = shoot_popup_over_window(tab._preset_combo.view().window(), d.win,
                                         d.shots / f"{name}-01-select-preset.png",
                                         d.pump)
            tab._preset_combo.hidePopup()
            yield 800
            tab._builtin_preset_btn.click()
            yield 1500
            pop = tab._builtin_preset_popup
            cell["builtin_groups"] = [[h, len(e), len(pop._more.get(h, []))]
                                      for h, e in pop._groups]
            ok2 = shoot_popup_over_window(pop, d.win,
                                          d.shots / f"{name}-02-built-in-list.png",
                                          d.pump)
            pop.close()
            yield 800
            cell["photos"] = [ok, ok2]
            rec["lists"].append(cell)
            d.note("LISTS " + json.dumps(cell))

    if "frames" in WHAT:
        if not tab._manual_engine_check.isChecked():
            tab._manual_engine_check.click()
            yield 1500
        fg = d.win.frameGeometry()
        g = d.win.geometry()
        d.win.resize(FRAME_W - (fg.width() - g.width()),
                     FRAME_H - (fg.height() - g.height()))
        yield 2000
        w = tab._manual_targen_grp
        while w is not None and not isinstance(w, QScrollArea):
            w = w.parentWidget()
        sa = w
        rec["frames"] = []

        def frame_state(label):
            fg = d.win.frameGeometry()
            og = getattr(tab, "_manual_output_grp", None)
            pg = getattr(tab, "_manual_presets_grp", None)
            c = {"step": label, "window_frame": [fg.width(), fg.height()],
                 "params_viewport_h": sa.viewport().height(),
                 "params_scroll_max": sa.verticalScrollBar().maximum(),
                 "output_foldable": hasattr(og, "is_collapsed"),
                 "presets_foldable": hasattr(pg, "is_collapsed"),
                 "output_folded": bool(getattr(og, "is_collapsed", lambda: False)()),
                 "presets_folded": bool(getattr(pg, "is_collapsed", lambda: False)())}
            rec["frames"].append(c)
            d.note("FRAMES " + json.dumps(c))
            return c

        frame_state("open (as started)")
        d.shot(tab, "frames-01-open-as-started")
        sa.verticalScrollBar().setValue(sa.verticalScrollBar().maximum())
        yield 800
        d.shot(tab, "frames-02-open-scrolled-to-the-bottom")
        sa.verticalScrollBar().setValue(0)
        for grp in (getattr(tab, "_manual_output_grp", None),
                    getattr(tab, "_manual_presets_grp", None)):
            if hasattr(grp, "toggle"):
                grp.toggle()          # what a click on its title does
        yield 1500
        frame_state("both folded")
        d.shot(tab, "frames-03-both-folded")
        sa.verticalScrollBar().setValue(sa.verticalScrollBar().maximum())
        yield 800
        d.shot(tab, "frames-04-folded-scrolled-to-the-bottom")
        sa.verticalScrollBar().setValue(0)
        for grp in (getattr(tab, "_manual_output_grp", None),
                    getattr(tab, "_manual_presets_grp", None)):
            if hasattr(grp, "toggle"):
                grp.toggle()
        yield 1500
        frame_state("both open again")
        d.shot(tab, "frames-05-open-again")


if __name__ == "__main__":
    drive = Drive(OUT, language="en", size=(1500, 1000))
    rc = drive.run(script)
    (OUT / "cells.json").write_text(json.dumps(
        {k: drive.record.get(k) for k in ("lists", "frames",
                                          "log_warnings_and_errors",
                                          "window_on_screen", "photos")},
        indent=2, default=str), encoding="utf-8")
    sys.exit(rc or 0)
