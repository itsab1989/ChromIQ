#!/usr/bin/env python3
"""B8-1280: the i1iSis and "Save as Defaults", ON SCREEN.

    python scripts/drive_b8_1280_isis_defaults.py OUT save    ENGINE PAPER N P START SANDBOX
    python scripts/drive_b8_1280_isis_defaults.py OUT restart ENGINE PAPER N P START SANDBOX
    python scripts/drive_b8_1280_isis_defaults.py OUT live    ENGINE -     - - manual SANDBOX
    python scripts/drive_b8_1280_isis_defaults.py OUT seeded  ENGINE PAPER N P START SANDBOX

``save`` seeds a new sandbox (the instrument ``B8_INSTR``, default the i1iSis;
the layout engine ``on``/``off``; the Create Chart module stored as START),
opens Manual, chooses PAPER in the Paper field on screen, ticks or unticks
printtarg's "no spacers" (-n) and "unlimited strip length" (-P) to N / P
(``1``/``0``) by clicking them, photographs, presses "Save as Defaults" and
records what the store holds. ``restart`` is a second process on the same
SANDBOX: it photographs the tab as it opens, then Manual, and judges -i, -p,
-n, -P, -m and -a against what the SAVE PHASE had on screen (read from its
cells.json, never from anything the app computes now).

``seeded`` is the challenge round's own case (beta 44 round 2, finding 10):
the store is written by hand, as that round did, and opened.

``B8_M`` / ``B8_A`` (save phase, engine off) also set printtarg's margin and
patch scale, as a person types them (B8-1281).

``live`` switches the instrument in one session, as a person does: ColorMunki
on A4 to the i1iSis (A3+ Portrait, -n, -P on), the person's own change while
on the i1iSis (A4, -n off), away to the ColorMunki and back.

Sandboxed: settings, presets, output folder (userdrive), ISO file forced to the
repo's copy. A watchdog answers every modal the drive did not open, and a
deadline ends the run.
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
WANT_N = sys.argv[5] == "1"
WANT_P = sys.argv[6] == "1"
START = sys.argv[7]
SB = Path(sys.argv[8]).resolve()
DEADLINE_MS = 240_000
INSTR = os.environ.get("B8_INSTR", "isis")
PHOTOS = os.environ.get("B8_PHOTOS", "1") != "0"
SAVE_OUT = os.environ.get("B8_SAVE_OUT")      # the save phase's OUT, for restart
os.environ["CHROMIQ_SETTINGS_FILE"] = str(SB / "settings.ini")
os.environ["CHROMIQ_PRESETS_DIR"] = str(SB / "presets")
os.environ["CHROMIQ_COMPLIANCE_ISO_FILE"] = str(
    _TREE / "data" / "compliance_sets" / "iso12647.json")

_BASE = {"restore_last_session": False, "restore_last_tab": False,
         "update_notify": False, "show_splash": False}

if PHASE in ("save", "live", "seeded"):
    if SB.exists():
        shutil.rmtree(SB)
    (SB / "presets").mkdir(parents=True)
    from core.settings import AppSettings
    _s = AppSettings()
    seed = dict(_BASE)
    if PHASE == "seeded":
        # EXACTLY the challenge round's hand-written store (its r6-isis-a4-*
        # sandbox), including its key for -P: "manual_printtarg_-P_l", which is
        # not the key the app writes (-P is upper case, "_u").
        seed.update({"chart_instrument": "isis", "chart_mode": START,
                     "manual_printtarg_-i_l": "isis",
                     "manual_printtarg_-p_l": PAPER,
                     "manual_printtarg_-n_l": WANT_N,
                     "manual_printtarg_-P_l": WANT_P,
                     "use_chromiq_layout_engine": ENGINE})
    else:
        first = INSTR if PHASE == "save" else "CM"
        seed.update({"chart_instrument": first, "chart_paper": "A4",
                     "chart_mode": START, "manual_printtarg_-i_l": first,
                     "use_chromiq_layout_engine": ENGINE})
    for k, v in seed.items():
        _s.set(k, v)
    _s.sync()
elif PHASE == "restart":
    from core.settings import AppSettings
    _s = AppSettings()
    _s.set("chart_mode", START)      # the module the next session opens on
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
    tag = (f"{PHASE}-{'engine' if ENGINE else 'printtarg'}-{PAPER}"
           f"-n{int(WANT_N)}-P{int(WANT_P)}-start-{START}")
    rec = d.record
    rec.update({"phase": PHASE, "engine": ENGINE, "paper": PAPER,
                "n": WANT_N, "P": WANT_P, "start": START, "instr": INSTR,
                "cells": []})

    def panel_shown() -> bool:
        grp = tab._manual_layout_grp
        return grp is not None and grp.isVisible()

    def paper_field() -> tuple[str, str]:
        """(code, text) of Manual's Paper field the person SEES."""
        panel = tab._manual_layout_panel
        if panel_shown():
            return panel.selection()[1], panel.paper.currentText()
        pw = tab._manual_paper_pw
        return str(pw.get_raw_value() or ""), pw._custom_combo.currentText()

    def instr_field() -> tuple[str, str]:
        panel = tab._manual_layout_panel
        if panel_shown() and panel.instr is not None:
            return str(panel.instr.currentData() or ""), panel.instr.currentText()
        pw = tab._manual_instr_pw
        return str(pw.get_raw_value() or ""), pw._control.currentText()

    def expand_expert():
        """Open "Expert Options" of printtarg, where -n and -P live, as a
        person clicks its title, and scroll the two rows into view."""
        from PyQt6.QtWidgets import QScrollArea
        from ui.widgets import CollapsibleGroupBox
        w = tab._manual_n_pw
        p = w.parentWidget()
        while p is not None and not isinstance(p, CollapsibleGroupBox):
            p = p.parentWidget()
        if p is not None and p.is_collapsed():
            p.toggle()
        d.pump(300)
        s = w.parentWidget()
        while s is not None and not isinstance(s, QScrollArea):
            s = s.parentWidget()
        if s is not None:
            s.ensureWidgetVisible(tab._manual_P_pw, 50, 50)
            s.ensureWidgetVisible(tab._manual_n_pw, 50, 50)

    def show_paper():
        from PyQt6.QtWidgets import QScrollArea
        w = (tab._manual_layout_panel.paper if panel_shown()
             else tab._manual_paper_pw)
        s = w.parentWidget()
        while s is not None and not isinstance(s, QScrollArea):
            s = s.parentWidget()
        if s is not None:
            s.ensureWidgetVisible(w, 50, 120)

    def state(step: str) -> dict:
        code, text = paper_field()
        icode, itext = instr_field()
        c = {"step": step, "mode": tab._mode_name(),
             "panel_shown": panel_shown(),
             "instrument_field": icode, "instrument_text": itext,
             "paper_field": code, "paper_text": text,
             "-i": tab._manual_instr_pw.get_raw_value(),
             "-p": tab._manual_paper_pw.get_raw_value(),
             "-n": bool(tab._manual_n_pw.get_raw_value()),
             "-P": bool(tab._manual_P_pw.get_raw_value()),
             "-m": tab._manual_m_pw.get_raw_value(),
             "-a": tab._manual_a_pw.get_raw_value()}
        return c

    def cell(step: str, photo: str, judge=None) -> dict:
        c = state(step)
        if judge is not None:
            bad = {k: (c.get(k), v) for k, v in judge.items() if c.get(k) != v}
            c["ok"] = not bad
            c["wrong"] = {k: f"shows {a!r}, wanted {b!r}"
                          for k, (a, b) in bad.items()}
        rec["cells"].append(c)
        d.note(f"{step}: {c['mode']} instrument {c['instrument_field']!r}, "
               f"Paper {c['paper_field']!r} ({c['paper_text']!r}), "
               f"-n {c['-n']} -P {c['-P']} -m {c['-m']} -a {c['-a']}"
               f"{'' if c.get('ok', True) else '   <-- WRONG ' + str(c['wrong'])}")
        if PHOTOS:
            if c["mode"] == "manual" and not c["panel_shown"]:
                expand_expert()
                d.pump(300)
                d.shot(tab, f"{tag}-{photo}-expert")
            show_paper()
            d.shot(tab, f"{tag}-{photo}")
        return c

    def user_mode(mode):
        (tab._guided_btn if mode == "guided" else tab._manual_btn).click()

    def user_paper(code: str):
        if panel_shown():
            c = tab._manual_layout_panel.paper
        else:
            c = tab._manual_paper_pw._custom_combo
        i = c.findData(code)
        assert i >= 0, f"{code} is not in the Paper field on screen"
        c.setCurrentIndex(i)
        c.activated.emit(i)

    def user_tick(pw, on: bool):
        box = pw._control if pw._control is not None else pw._enable_check
        if bool(pw.get_raw_value()) != on:
            box.click()

    def user_instr(code: str):
        c = tab._manual_instr_pw._control
        i = c.findData(code)
        assert i >= 0, f"{code} is not in the instrument field"
        c.setCurrentIndex(i)
        c.activated.emit(i)

    if PHASE == "save":
        user_mode("manual")
        yield 1500
        cell("save: Manual as opened", "0-save-manual-opened")
        user_paper(PAPER)
        yield 1200
        if not panel_shown():
            user_tick(tab._manual_n_pw, WANT_N)
            user_tick(tab._manual_P_pw, WANT_P)
            # B8-1281: a margin / patch scale of the person's own
            for flag_pw, env in ((tab._manual_m_pw, "B8_M"),
                                 (tab._manual_a_pw, "B8_A")):
                if os.environ.get(env):
                    flag_pw.set_user_enabled(True)
                    flag_pw.set_value(float(os.environ[env]) if env == "B8_A"
                                      else int(os.environ[env]))
            yield 800
        c = cell("save: Manual, chosen", "1-save-chosen")
        tab._save_defaults_btn.click()
        yield 2000
        cell("save: after Save as Defaults", "2-save-after")
        d.settings.sync()
        rec["store"] = {k: d.settings.get(k) for k in (
            "chart_instrument", "chart_paper", "manual_printtarg_-i_l",
            "manual_printtarg_-p_l", "manual_printtarg_-n_l",
            "manual_printtarg_-P_u", "manual_printtarg_-m_l",
            "manual_printtarg_-a_l", "chart_no_strip_limit")}
        r = d.settings.get("manual_engine_recipe")
        if isinstance(r, dict):
            rec["store"].update({f"recipe.{k}": r.get(k) for k in (
                "instrument", "paper", "spacer_on", "nolimit", "border",
                "pscale")})
        rec["saved"] = {k: c[k] for k in ("-i", "-p", "-n", "-P", "-m", "-a",
                                           "paper_field", "instrument_field")}
        d.note(f"store: {rec['store']}")
        return

    if PHASE == "seeded":
        cell("seeded: as opened", "1-seeded-as-opened")
        if tab._mode_name() != "manual":
            user_mode("manual")
            yield 1500
            cell("seeded: Manual clicked", "2-seeded-manual")
        return

    if PHASE == "restart":
        saved = json.loads((Path(SAVE_OUT) / "cells.json").read_text(encoding="utf-8"))["saved"]
        judge = {k: saved[k] for k in ("-i", "-p", "-n", "-P", "-m", "-a")}
        judge["paper_field"] = saved["paper_field"]
        judge["instrument_field"] = saved["instrument_field"]
        first = cell("restart: as opened", "3-restart-as-opened",
                     judge if tab._mode_name() == "manual" else None)
        if first["mode"] != "manual":
            user_mode("manual")
            yield 1500
            cell("restart: Manual clicked", "4-restart-manual", judge)
            user_mode("guided")
            yield 1500
            user_mode("manual")
            yield 1500
            cell("restart: Guided and back to Manual", "5-restart-back", judge)
        else:
            user_mode("guided")
            yield 1500
            cell("restart: Guided clicked", "4-restart-guided")
            user_mode("manual")
            yield 1500
            cell("restart: back to Manual", "5-restart-back", judge)
        return

    # PHASE == "live": one session, the instrument switched by a person.
    user_mode("manual")
    yield 1500
    base = {"paper_field": "A4", "-n": False, "-P": False}
    cell("live: ColorMunki, as opened", "1-live-cm", {"-i": "CM", **base})
    user_instr("isis")
    yield 1500
    cell("live: i1iSis chosen", "2-live-isis",
         {"-i": "isis", "paper_field": "329x483", "-n": True, "-P": True})
    # the person's own choices on the i1iSis
    user_paper("A4")
    yield 800
    user_tick(tab._manual_n_pw, False)
    yield 800
    cell("live: on the i1iSis, A4 and -n off by hand", "3-live-isis-own",
         {"-i": "isis", "paper_field": "A4", "-n": False, "-P": True})
    tab._apply_instrument_default_margin()     # any later call, same instrument
    yield 500
    cell("live: a later refresh on the i1iSis", "4-live-isis-refresh",
         {"-i": "isis", "paper_field": "A4", "-n": False, "-P": True})
    user_instr("CM")
    yield 1500
    cell("live: back to the ColorMunki", "5-live-cm-again",
         {"-i": "CM", "paper_field": "A4", "-n": False, "-P": False})
    user_instr("isis")
    yield 1500
    cell("live: the i1iSis again", "6-live-isis-again",
         {"-i": "isis", "paper_field": "329x483", "-n": True, "-P": True})
    user_instr("i1")
    yield 1500
    cell("live: to the i1Pro", "7-live-i1",
         {"-i": "i1", "paper_field": "A4", "-n": False, "-P": False})


if __name__ == "__main__":
    drive = Drive(OUT, language="en", size=(1500, 1000))
    rc = drive.run(script)
    (OUT / "cells.json").write_text(json.dumps(
        {"store": drive.record.get("store"),
         "saved": drive.record.get("saved"),
         "cells": drive.record.get("cells", []),
         "watchdog": drive.record.get("watchdog", [])}, indent=2),
        encoding="utf-8")
    sys.exit(rc or 0)
