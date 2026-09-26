#!/usr/bin/env python3
"""K51-E (Knut, #182 5846297769, K50-5; B8-1336): Preferences > Chart Layout,
the i1Pro group, ON SCREEN, with the ChromIQ layout engine ON.

    CHROMIQ_TREE=<tree> python drive_k51_i1pro_group.py <out> <en|de>

The sandboxed settings are seeded with the layout engine on, the i1Pro, A4
and Guided mode, and the factory i1Pro preset ("-m 10 -a 0.95"). Then, as a
person does:

1. Create Chart, Guided: "Calculated patches" read and photographed;
2. Preferences opened from the app's own action, the Chart Layout tab
   brought to the front and scrolled to the i1Pro group: photographed, and
   whether the group is enabled recorded; its help button's text recorded;
3. "Default layout" set to "-m 6 -a 1.0" and OK pressed;
4. Guided's "Calculated patches" read and photographed again.

Everything is recorded in ``<lang>-i1pro.json``. A watchdog answers any
window the drive did not open itself; a deadline ends the run. Settings,
presets and the output folder are sandboxed by `userdrive.Drive`.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

TREE = os.environ.get("CHROMIQ_TREE") or str(Path(__file__).resolve().parents[1])
sys.path.insert(0, TREE + "/scripts")
sys.path.insert(0, TREE)
HERE = str(Path(__file__).resolve().parent)
if HERE not in sys.path:
    sys.path.append(HERE)
from userdrive import Drive                                    # noqa: E402
import drive_b42_k36 as K36                                    # noqa: E402

K36.DEADLINE_S = 300


def _count(tab) -> str:
    return re.sub(r"<[^>]+>", "", tab._patch_count_lbl.text()).strip()


def script(lang):
    def s(d):
        rec = d.record
        rec.update({"language": lang, "tree": TREE, "mode": "ON SCREEN"})
        K36._install_watchdog(d, rec)
        K36.EXPECTED.add("SettingsDialog")
        for k, v in {"use_chromiq_layout_engine": True,
                     "i1pro_default_preset": "m10_a0.95",
                     "chart_instrument": "i1", "chart_paper": "A4",
                     "chart_mode": "guided"}.items():
            d.settings.set(k, v)
        d.settings.sync()
        yield 500
        d.goto_tab("chart")
        yield 1500
        tab = d.win._tab_chart
        tab._guided_btn.click()
        yield 800
        for combo, data in ((tab._instr_combo, "i1"), (tab._paper_combo, "A4")):
            i = combo.findData(data)
            combo.setCurrentIndex(i)
            combo.activated.emit(i)
            yield 600
        tab._update_patch_count()
        yield 800
        rec["guided_before"] = {"count": _count(tab),
                                "detail": tab._patch_detail_lbl.text(),
                                "suppress_left_clip_border":
                                    tab._lb_check.isChecked(),
                                "engine": d.settings.get(
                                    "use_chromiq_layout_engine")}
        d.shot(d.win, f"{lang}-00-guided-before-clip-default")
        # K50-5's table is for the clip border OFF: "-L" ticked, as a
        # person does
        if not tab._lb_check.isChecked():
            tab._lb_check.click()
            yield 900
        tab._update_patch_count()
        yield 800
        rec["guided_before_no_clip"] = {
            "count": _count(tab), "detail": tab._patch_detail_lbl.text(),
            "suppress_left_clip_border": tab._lb_check.isChecked()}
        d.note(f"Guided A4 i1Pro, -m 10 -a 0.95: {rec['guided_before']}")
        d.shot(d.win, f"{lang}-01-guided-before")
        # -- Preferences, from the app's own action
        d.later(d.win._open_settings)
        yield 3000
        dlg = d.top_dialog("SettingsDialog")
        if dlg is None:
            rec["error"] = "no Preferences window"
            d.note("NO PREFERENCES WINDOW")
            return
        dlg.resize(1100, 900)
        from PyQt6.QtWidgets import QScrollArea, QTabWidget
        grp = dlg._i1pro_grp
        for tw in dlg.findChildren(QTabWidget):
            for i in range(tw.count()):
                if tw.widget(i).isAncestorOf(grp):
                    tw.setCurrentIndex(i)
        yield 2500
        sc = grp.parentWidget()
        while sc is not None and not isinstance(sc, QScrollArea):
            sc = sc.parentWidget()
        if sc is not None:
            sc.ensureWidgetVisible(grp, 20, 20)
            sc.verticalScrollBar().setValue(sc.verticalScrollBar().maximum())
        yield 1200
        from ui.tooltip_button import TooltipButton
        helps = [b for b in grp.findChildren(TooltipButton)]
        rec["prefs"] = {
            "group_title": grp.title(),
            "group_enabled": grp.isEnabled(),
            "combo_enabled": dlg._i1pro_preset_combo.isEnabled(),
            "engine_on": d.settings.get("use_chromiq_layout_engine"),
            "help": [getattr(b, "_body", None) or b.toolTip() for b in helps],
        }
        d.note(f"Preferences: {rec['prefs']['group_title']!r} enabled "
               f"{rec['prefs']['group_enabled']}")
        d.shot(dlg, f"{lang}-02-prefs-i1pro-group")
        combo = dlg._i1pro_preset_combo
        i = combo.findData("m6_a1.0")
        combo.setCurrentIndex(i)
        combo.activated.emit(i)
        yield 900
        d.shot(dlg, f"{lang}-03-prefs-m6-a1.0-chosen")
        from PyQt6.QtWidgets import QDialogButtonBox
        for box in dlg.findChildren(QDialogButtonBox):
            if box.isVisible():
                btn = box.button(QDialogButtonBox.StandardButton.Ok)
                if btn is not None:
                    btn.click()
                    break
        yield 3000
        tab._update_patch_count()
        yield 800
        rec["guided_after"] = {"count": _count(tab),
                               "detail": tab._patch_detail_lbl.text(),
                               "preset": d.settings.get("i1pro_default_preset")}
        d.note(f"Guided A4 i1Pro, -m 6 -a 1.0: {rec['guided_after']}")
        d.shot(d.win, f"{lang}-04-guided-after")
        (d.out / f"{lang}-i1pro.json").write_text(
            json.dumps({k: rec.get(k) for k in
                        ("guided_before", "guided_before_no_clip", "prefs",
                         "guided_after")},
                       indent=2, ensure_ascii=False), encoding="utf-8")
    return s


def main() -> int:
    out = Path(sys.argv[1])
    lang = sys.argv[2]
    d = Drive(out, projects=[], language=lang)
    rc = d.run(script(lang))
    print(f"rc={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
