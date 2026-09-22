#!/usr/bin/env python3
"""Basti, 2026-09-22 (German screenshot): "WELCHE PRESETS SIND FÜR DIE
VERIFIZIERUNG VERWENDBAR?" overlaps its own ⓘ in Create Chart.

Driven in German as a user: Report-Limits-Threshold-Series, Verification,
run1, Create Chart, MANUAL; the button's right edge and the ⓘ's left edge
are read in the tab's coordinates, and the row is photographed.

    python scripts/drive_preset_button_overlap.py <out-dir>
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import Drive                                   # noqa: E402

NAME = "Report-Limits-Threshold-Series"


def script(d):
    d.open_project(NAME)
    d.set_bar(run_type="Verification", run="run1")
    yield 800
    d.goto_tab("chart")
    tab = d.win._tab_chart
    tab._manual_btn.click()
    yield 1500
    btn, info = tab._preset_verify_btn, tab._preset_verify_help
    b = btn.mapTo(tab, btn.rect().topRight()).x()
    i = info.mapTo(tab, info.rect().topLeft()).x()
    grp = btn.parentWidget()
    d.note(f"label {btn.text()!r}")
    d.note(f"button right edge x={b}, info left edge x={i}: "
           f"{'OVERLAP' if i <= b else 'clear'} ({i - b} px)")
    d.note(f"left panel width {tab.width()}, group width {grp.width()}")
    d.record.update(button_right=b, info_left=i, gap=i - b,
                    tab_width=tab.width())
    # EVERY LANGUAGE'S LABEL against the room the row really has, measured
    # with the button's own font and the capitals the app draws it in.
    import json
    from PyQt6.QtGui import QFontMetrics
    fm = QFontMetrics(btn.font())
    room = grp.width() - info.width() - 6 - 2 * 10 - 8   # icon, gap, padding
    widths = {}
    for f in sorted((d.work.parent.parent.parent / "data" / "i18n").glob("*.json")) \
            if False else sorted(Path(__file__).resolve().parents[1].joinpath(
                "data", "i18n").glob("*.json")):
        cat = json.loads(f.read_text(encoding="utf-8"))
        t = cat.get("Which presets can be used for verification?")
        if isinstance(t, str):
            widths[f.stem] = fm.horizontalAdvance(t.upper())
    widths["en"] = fm.horizontalAdvance(
        "Which presets can be used for verification?".upper())
    d.note(f"room for the label: {room} px")
    for k, v in sorted(widths.items(), key=lambda kv: -kv[1]):
        d.note(f"   {k:6} {v:4d} px {'TOO WIDE' if v > room else 'fits'}")
    d.record.update(room=room, widths=widths)
    d.shot(tab, "create-chart-de")
    yield 300


if __name__ == "__main__":
    d = Drive(Path(sys.argv[1]), projects=[NAME], language="de")
    sys.exit(d.run(script))
