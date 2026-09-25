#!/usr/bin/env python3
"""B8-1228: "Save as Defaults" on a paper, then a NEW SESSION, on screen.

    python scripts/drive_b8_1228_custom_defaults_restart.py OUT PHASE ENGINE PAPER START SANDBOX

PHASE ``save`` seeds a new sandbox (ColorMunki, the layout engine ``on`` or
``off``, the Create Chart module stored as START, ``guided`` or ``manual``),
opens Manual, chooses PAPER in the Paper field ON SCREEN (the layout panel's
with the engine on, printtarg's with it off; ``custom:130x180`` goes through
Custom and its W x H boxes), photographs it, presses "Save as Defaults" and
photographs that. PHASE ``restart`` is a second process on the same SANDBOX:
it photographs the Create Chart tab as it opens, then Manual and Guided as a
person clicks them, and records the Paper field of each and the paper the
preset lists are filtered to (B8-1221: the paper on screen).

Everything is sandboxed: settings, presets, the output folder (userdrive), and
the ISO file forced to the repo's copy. A watchdog answers every modal the
drive did not open itself (No / Cancel, a name question accepted), and a
deadline ends the run, so nobody has to click.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

_TREE = Path(os.environ.get("CHROMIQ_TREE")
             or Path(__file__).resolve().parents[1]).resolve()
sys.path.insert(0, str(_TREE / "scripts"))
sys.path.insert(0, str(_TREE))

OUT = Path(sys.argv[1]).resolve()
PHASE = sys.argv[2]
ENGINE = sys.argv[3] == "on"
PAPER = sys.argv[4]
START = sys.argv[5]
SB = Path(sys.argv[6]).resolve()
DEADLINE_MS = 240_000
os.environ["CHROMIQ_SETTINGS_FILE"] = str(SB / "settings.ini")
os.environ["CHROMIQ_PRESETS_DIR"] = str(SB / "presets")
os.environ["CHROMIQ_COMPLIANCE_ISO_FILE"] = str(
    _TREE / "data" / "compliance_sets" / "iso12647.json")

if PAPER.startswith("custom:"):
    CODE, DIMS = "custom", tuple(int(v) for v in PAPER[7:].split("x"))
    WANT = PAPER[7:]
else:
    CODE, DIMS, WANT = PAPER, None, PAPER

if PHASE == "save":
    if SB.exists():
        shutil.rmtree(SB)
    (SB / "presets").mkdir(parents=True)
    from core.settings import AppSettings
    _s = AppSettings()
    for k, v in {"chart_instrument": "CM", "chart_paper": "A4",
                 "chart_mode": START, "manual_printtarg_-i_l": "CM",
                 "use_chromiq_layout_engine": ENGINE,
                 "restore_last_session": False, "restore_last_tab": False,
                 "update_notify": False, "show_splash": False}.items():
        _s.set(k, v)
    _s.sync()
elif PHASE == "restart":
    # The module the next session opens on. Nothing in the app writes
    # `chart_mode` (Save as Defaults does not), so it is the seeded value.
    from core.settings import AppSettings
    _s = AppSettings()
    _s.set("chart_mode", START)
    _s.sync()

from userdrive import Drive                                   # noqa: E402


def _install_watchdog(d) -> None:
    from PyQt6.QtCore import QObject, QTimer
    from PyQt6.QtWidgets import (QApplication, QDialog, QInputDialog,
                                 QMessageBox)

    class Watchdog(QObject):
        def __init__(self):
            super().__init__(QApplication.instance())
            self.seen: dict[int, float] = {}
            self._t = QTimer(self)
            self._t.setInterval(300)
            self._t.timeout.connect(self.tick)
            self._t.start()
            self._end = QTimer(self)
            self._end.setSingleShot(True)
            self._end.timeout.connect(self.deadline)
            self._end.start(DEADLINE_MS)

        def tick(self):
            w = QApplication.activeModalWidget()
            if w is None or not w.isVisible():
                self.seen.clear()
                return
            first = self.seen.setdefault(id(w), time.monotonic())
            if time.monotonic() - first < 0.8:
                return
            text = d.modal_text(w)
            clicked = "(reject)"
            if isinstance(w, QInputDialog):
                clicked = "(accept)"
                w.accept()
            elif isinstance(w, QMessageBox):
                pick = next((b for b in w.buttons() if w.buttonRole(b) in (
                    QMessageBox.ButtonRole.RejectRole,
                    QMessageBox.ButtonRole.NoRole)), None)
                pick = pick or w.escapeButton() or w.defaultButton()
                if pick is not None:
                    clicked = pick.text()
                    pick.click()
                else:
                    w.reject()
            elif isinstance(w, QDialog):
                w.reject()
            else:
                w.close()
            d.record.setdefault("watchdog", []).append(
                {"class": type(w).__name__, "title": w.windowTitle(),
                 "text": text, "clicked": clicked})
            d.note(f"   [watchdog] {type(w).__name__} {w.windowTitle()!r}: "
                   f"{text[:140].replace(chr(10), ' / ')!r} -> {clicked}")

        def deadline(self):
            d.note("DEADLINE: the drive ran too long and was ended")
            d.record["deadline_hit"] = True
            d._flush()
            for _ in range(4):
                w = QApplication.activeModalWidget()
                if w is not None:
                    w.done(99)
            QApplication.instance().quit()

    d._watchdog = Watchdog()


def script(d):
    _install_watchdog(d)
    d.goto_tab("chart")
    yield 1500
    tab = d.win._tab_chart
    tag = f"{'engine' if ENGINE else 'printtarg'}-{WANT}-start-{START}"
    rec = d.record
    rec.update({"phase": PHASE, "engine": ENGINE, "paper": WANT,
                "start": START, "cells": []})

    def field() -> tuple[str, str, str]:
        """(mode, code, text) of the Paper field the person SEES."""
        mode = tab._mode_name()
        if mode == "guided":
            c = tab._paper_combo
            return mode, str(c.currentData() or ""), c.currentText()
        panel = tab._manual_layout_panel
        if panel is not None and panel.paper is not None \
                and panel.paper.isVisible():
            txt = panel.paper.currentText()
            if panel.paper.currentData() == "__custom__":
                txt += (f" {int(panel.custom_w.value())} x "
                        f"{int(panel.custom_h.value())}")
            return mode, panel.selection()[1], txt
        pw = tab._manual_paper_pw
        txt = pw._custom_combo.currentText()
        if pw._custom_combo.currentData() == "custom":
            txt += (f" {int(pw._custom_w_spin.value())} x "
                    f"{int(pw._custom_h_spin.value())}")
        return mode, str(pw.get_raw_value() or ""), txt

    def field_widget():
        if tab._mode_name() == "guided":
            return tab._paper_combo
        panel = tab._manual_layout_panel
        if panel is not None and panel.paper is not None \
                and panel.paper.isVisible():
            return panel.custom_h if panel.paper.currentData() == "__custom__" \
                else panel.paper
        return tab._manual_paper_pw

    def show_field():
        """Scroll the Paper field into view, as a person scrolls to it."""
        from PyQt6.QtWidgets import QScrollArea
        w = field_widget()
        p = w.parentWidget()
        while p is not None and not isinstance(p, QScrollArea):
            p = p.parentWidget()
        if p is not None:
            p.ensureWidgetVisible(w, 50, 120)

    def cell(step: str, photo: str):
        show_field()
        d.pump(400)
        mode, code, text = field()
        panel = tab._manual_layout_panel
        instr = (tab._instr_combo.currentData() if mode == "guided"
                 else panel.selection()[0] if ENGINE and panel is not None
                 else tab._shared_get("manual")["instrument"])
        c = {"step": step, "mode": mode, "paper_field": code,
             "paper_text": text, "filter_paper": tab._preset_paper_selected(),
             "instrument": instr}
        rec["cells"].append(c)
        d.note(f"{step}: {mode} Paper = {code!r} ({text!r}), "
               f"lists filtered to {c['filter_paper']!r}, instrument {instr!r}")
        d.shot(tab, f"{tag}-{photo}")

    def user_mode(mode):
        (tab._guided_btn if mode == "guided" else tab._manual_btn).click()

    def user_paper():
        panel = tab._manual_layout_panel
        if panel is not None and panel.paper is not None \
                and panel.paper.isVisible():
            c = panel.paper
            i = c.findData("__custom__" if CODE == "custom" else CODE)
            if DIMS:
                panel.custom_w.setValue(DIMS[0])
                panel.custom_h.setValue(DIMS[1])
        else:
            pw = tab._manual_paper_pw
            c = pw._custom_combo
            i = c.findData(CODE)
            if DIMS:
                pw._custom_w_spin.setValue(DIMS[0])
                pw._custom_h_spin.setValue(DIMS[1])
        assert i >= 0, f"{CODE} is not in the Paper field on screen"
        c.setCurrentIndex(i)
        c.activated.emit(i)

    if PHASE == "save":
        user_mode("manual")
        yield 1500
        user_paper()
        yield 1500
        cell("save: Manual, paper chosen", "1-save-manual-chosen")
        tab._save_defaults_btn.click()
        yield 2000
        cell("save: after Save as Defaults", "2-save-after-save-as-defaults")
        d.settings.sync()
        rec["store"] = {k: d.settings.get(k) for k in (
            "chart_paper", "manual_printtarg_-p_l", "chart_mode")}
        r = d.settings.get("manual_engine_recipe")
        rec["store"]["manual_engine_recipe.paper"] = (
            r.get("paper") if isinstance(r, dict) else None)
        d.note(f"store: {rec['store']}")
        return

    cell("restart: as opened", "3-restart-as-opened")
    other = "guided" if tab._mode_name() == "manual" else "manual"
    user_mode(other)
    yield 1500
    cell(f"restart: {other} clicked", f"4-restart-{other}")
    user_mode("guided" if other == "manual" else "manual")
    yield 1500
    back = tab._mode_name()
    cell(f"restart: back to {back}", f"5-restart-back-{back}")
    if back != "manual":
        user_mode("manual")
        yield 1500
    # The "Select preset" pulldown as a person opens it in Manual.
    cb = tab._preset_combo
    cb.showPopup()
    yield 1200
    d.shot(cb.view(), f"{tag}-6-restart-manual-select-preset-open")
    cb.hidePopup()
    yield 500


if __name__ == "__main__":
    drive = Drive(OUT, language="en", size=(1500, 1000))
    rc = drive.run(script)
    (OUT / "cells.json").write_text(json.dumps(
        {"store": drive.record.get("store"),
         "cells": drive.record.get("cells", []),
         "watchdog": drive.record.get("watchdog", [])}, indent=2),
        encoding="utf-8")
    sys.exit(rc or 0)
