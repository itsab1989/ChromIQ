#!/usr/bin/env python3
"""B8-1284 to B8-1287: Preferences, the i1Pro Chart Defaults preset and the
saved engine recipe, ON SCREEN.

    python scripts/drive_b8_1285_preferences_and_restart.py OUT PHASE

PHASE:
  prefs           B8-1284, one session: a margin / scale set by hand, then
                  Preferences closed with nothing changed (Cancel or OK). The
                  challenge round's six cells (the last one, a custom pair, is
                  its control), then the preset CHANGED with OK: on the i1Pro
                  (house values move, a custom pair stays) and while Manual is
                  on another instrument (never touched).
  preset-save     i1Pro, Save as Defaults, then Preferences > i1Pro Chart
                  Defaults to "-m 6 -a 1.0" and OK; Guided read after.
  preset-restart  a second process on the same sandbox: Manual and Guided.
  recipe-save     B8_INSTR (p3 / CM / SS / i1), engine OFF, Manual, Save as
                  Defaults; the stored recipe recorded.
  recipe-restart  a second process: Manual as opened (engine off), then the
                  "ChromIQ layout engine" box ticked as a person does.
  recipe-restart2 a third process: the store now says engine ON (the tick
                  above is persisted at once), Manual as opened.
  fresh           no store at all: Manual, then every instrument in turn.

Sandboxed: CHROMIQ_SETTINGS_FILE / CHROMIQ_PRESETS_DIR under the sandbox
folder (B8_SB, default OUT/../sandbox-<OUT name>), the output folder by
userdrive, the ISO file forced to the repo's copy. A watchdog answers any
modal the drive did not open itself; a deadline ends the run.
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
os.environ["CHROMIQ_TREE"] = str(_TREE)
sys.path.insert(0, str(_TREE / "scripts"))
sys.path.insert(0, str(_TREE))

OUT = Path(sys.argv[1]).resolve()
PHASE = sys.argv[2]
SB = Path(os.environ.get("B8_SB")
          or (OUT.parent / f"sandbox-{OUT.name}")).resolve()
INSTR = os.environ.get("B8_INSTR", "i1")
PAPER = os.environ.get("B8_PAPER", "A4")      # recipe phases: Manual's paper
os.environ["CHROMIQ_SETTINGS_FILE"] = str(SB / "settings.ini")
os.environ["CHROMIQ_PRESETS_DIR"] = str(SB / "presets")
os.environ["CHROMIQ_COMPLIANCE_ISO_FILE"] = str(
    _TREE / "data" / "compliance_sets" / "iso12647.json")
DEADLINE_MS = 300_000

_BASE = {"restore_last_session": False, "restore_last_tab": False,
         "update_notify": False, "show_splash": False}

if PHASE in ("prefs", "preset-save", "recipe-save", "recipe-control",
             "recipe-control2", "fresh"):
    if SB.exists():
        shutil.rmtree(SB)
    (SB / "presets").mkdir(parents=True)
    if PHASE != "fresh":
        from core.settings import AppSettings
        _s = AppSettings()
        seed = dict(_BASE)
        first = INSTR if PHASE.startswith("recipe") else "i1"
        seed.update({"chart_instrument": first, "chart_mode": "manual",
                     "manual_printtarg_-i_l": first,
                     "use_chromiq_layout_engine": False})
        if PHASE in ("recipe-control", "recipe-control2"):
            # the same session, never saved: nothing in the store but this
            seed.update({"chart_paper": PAPER, "manual_printtarg_-p_l": PAPER})
        if PHASE == "recipe-control2":
            seed["use_chromiq_layout_engine"] = True
        for k, v in seed.items():
            _s.set(k, v)
        _s.sync()
        del _s

from userdrive import Drive                                   # noqa: E402


def _install_watchdog(d) -> None:
    from PyQt6.QtCore import QObject, QTimer
    from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

    class Watchdog(QObject):
        def __init__(self):
            super().__init__(QApplication.instance())
            self.seen: dict[int, float] = {}
            self.allowed: set[str] = set()
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
            if type(w).__name__ in self.allowed:
                return
            first = self.seen.setdefault(id(w), time.monotonic())
            if time.monotonic() - first < 2.5:
                return
            text = d.modal_text(w)
            if isinstance(w, QMessageBox):
                pick = w.escapeButton() or w.defaultButton()
                if pick is not None:
                    pick.click()
                else:
                    w.reject()
            elif isinstance(w, QDialog):
                w.reject()
            else:
                w.close()
            d.record.setdefault("watchdog", []).append(
                {"class": type(w).__name__, "title": w.windowTitle(),
                 "text": text})
            d.note(f"   [watchdog] {type(w).__name__} {w.windowTitle()!r}: "
                   f"{text[:160]!r}")

        def deadline(self):
            d.note("DEADLINE hit")
            d.record["deadline_hit"] = True
            for _ in range(4):
                w = QApplication.activeModalWidget()
                if w is not None:
                    w.done(99)
            QApplication.instance().quit()

    d._watchdog = Watchdog()


def _guided_margin(tab):
    """What Guided would build with: its ChartParams margin / scale."""
    try:
        p = tab._collect_guided()
        return {"margin": p.margin_mm, "patch_scale": p.patch_scale,
                "instrument": p.instrument}
    except Exception as exc:                               # noqa: BLE001
        return f"(could not read: {exc})"


def script(d):
    _install_watchdog(d)
    d._watchdog.allowed.add("SettingsDialog")
    d.goto_tab("chart")
    yield 1500
    tab = d.win._tab_chart
    rec = d.record
    rec["cells"] = []

    def panel_shown() -> bool:
        grp = tab._manual_layout_grp
        return grp is not None and grp.isVisible()

    def state(step):
        panel = tab._manual_layout_panel
        c = {"step": step, "mode": tab._mode_name(),
             "engine_box": bool(tab._manual_engine_check.isChecked()),
             "panel_shown": panel_shown(),
             "panel_instr": (str(panel.instr.currentData() or "")
                             if panel is not None and panel.instr is not None
                             else None),
             "panel_paper": (panel.selection()[1] if panel is not None
                             else None),
             "-i": tab._manual_instr_pw.get_raw_value(),
             "-p": tab._manual_paper_pw.get_raw_value(),
             "-m": tab._manual_m_pw.get_raw_value(),
             "-m_enabled": tab._manual_m_pw.is_enabled_by_user,
             "-a": round(float(tab._manual_a_pw.get_raw_value()), 3),
             "-n": bool(tab._manual_n_pw.get_raw_value()),
             "-P": bool(tab._manual_P_pw.get_raw_value())}
        if panel is not None and c["panel_shown"]:
            # what the layout panel would build with: a recipe nobody saw
            # (an uninitialised panel) reads 72 dpi and no page margins
            r = panel.get_recipe()
            c.update({"recipe_dpi": r.dpi,
                      "recipe_instrument_margins": bool(
                          r.use_instrument_margins),
                      "recipe_margin_top": r.margin_top,
                      "recipe_full": r.to_dict()})
        return c

    def show_margin_rows():
        from PyQt6.QtWidgets import QScrollArea
        from ui.widgets import CollapsibleGroupBox
        w = tab._manual_m_pw
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
            s.ensureWidgetVisible(tab._manual_a_pw, 50, 50)
            s.ensureWidgetVisible(tab._manual_m_pw, 50, 50)

    def show_panel_instr():
        from PyQt6.QtWidgets import QScrollArea
        w = tab._manual_layout_panel.instr
        s = w.parentWidget()
        while s is not None and not isinstance(s, QScrollArea):
            s = s.parentWidget()
        if s is not None:
            s.ensureWidgetVisible(w, 50, 120)

    def cell(step, photo, want=None):
        c = state(step)
        if want:
            bad = {k: f"shows {c.get(k)!r}, wanted {v!r}"
                   for k, v in want.items() if c.get(k) != v}
            c["ok"] = not bad
            c["wrong"] = bad
        rec["cells"].append(c)
        d.note(f"{step}: -i {c['-i']} -m {c['-m']} (on {c['-m_enabled']}) "
               f"-a {c['-a']} -p {c['-p']} -n {c['-n']} -P {c['-P']}"
               f" | engine box {c['engine_box']} panel {c['panel_instr']}"
               f"/{c['panel_paper']} shown {c['panel_shown']}"
               + (f" recipe dpi {c['recipe_dpi']} instrument margins "
                  f"{c['recipe_instrument_margins']} top "
                  f"{c['recipe_margin_top']}" if 'recipe_dpi' in c else "")
               +
               f"{'' if c.get('ok', True) else '   <-- WRONG ' + str(c['wrong'])}")
        if c["mode"] == "manual":
            if c["panel_shown"]:
                show_panel_instr()
            else:
                show_margin_rows()
        d.shot(tab, photo)
        return c

    def user_mode(mode):
        (tab._guided_btn if mode == "guided" else tab._manual_btn).click()

    def user_instr(code):
        c = tab._manual_instr_pw._control
        i = c.findData(code)
        assert i >= 0, code
        c.setCurrentIndex(i)
        c.activated.emit(i)

    def user_margin(m, a):
        """As a person: tick the -m row's box, type the value; type -a."""
        pw = tab._manual_m_pw
        if not pw.is_enabled_by_user:
            pw._enable_check.click()
        sp = pw._control
        sp.setFocus()
        sp.setValue(int(m))
        sp.editingFinished.emit()
        spa = tab._manual_a_pw._control
        spa.setFocus()
        spa.setValue(float(a))
        spa.editingFinished.emit()

    def open_prefs():
        d.later(d.win._open_settings)

    def prefs_dialog():
        return d.top_dialog("SettingsDialog")

    def close_prefs(button):          # "OK" or "Cancel"
        from PyQt6.QtWidgets import QDialogButtonBox
        dlg = prefs_dialog()
        std = (QDialogButtonBox.StandardButton.Ok if button == "OK"
               else QDialogButtonBox.StandardButton.Cancel)
        for box in dlg.findChildren(QDialogButtonBox):
            if not box.isVisible():
                continue
            btn = box.button(std)
            if btn is not None:
                btn.click()
                return True
        return False

    def pick_preset(dlg, key):
        """Bring Preferences > i1Pro Chart Defaults to the front and choose
        `key` in its "Default layout" field, as a person does."""
        from PyQt6.QtWidgets import QScrollArea, QStackedWidget, QTabWidget
        combo = dlg._i1pro_preset_combo
        p = combo.parentWidget()
        while p is not None:
            par = p.parentWidget()
            if isinstance(par, QStackedWidget):
                par.setCurrentWidget(p)
            p = par
        for tw in dlg.findChildren(QTabWidget):
            for i in range(tw.count()):
                if tw.widget(i).isAncestorOf(combo):
                    tw.setCurrentIndex(i)
        s = combo.parentWidget()
        while s is not None and not isinstance(s, QScrollArea):
            s = s.parentWidget()
        if s is not None:
            s.ensureWidgetVisible(combo, 50, 80)
        i = combo.findData(key)
        combo.setCurrentIndex(i)
        combo.activated.emit(i)

    def store_now(keys):
        d.settings.sync()
        return {k: d.settings.get(k) for k in keys}

    if PHASE == "fresh":
        cell("fresh: as opened (store empty)", "f0-as-opened")
        if tab._mode_name() != "manual":
            user_mode("manual")
            yield 1500
        # A fresh install has the layout engine ON: Manual shows the panel.
        cell("fresh: Manual", "f1-manual",
             {"-i": "i1", "-m": 10, "-a": 0.95, "-p": "A4",
              "engine_box": True, "panel_shown": True, "panel_instr": "i1",
              "recipe_dpi": 300, "recipe_instrument_margins": True})
        for code in ("p3", "CM", "SS", "CR30", "i1"):
            pc = tab._manual_layout_panel.instr
            i = pc.findData(code)
            assert i >= 0, code
            pc.setCurrentIndex(i)
            pc.activated.emit(i)
            yield 1500
            cell(f"fresh: engine on, panel switched to {code}",
                 f"f-panel-{code}",
                 {"-i": code, "panel_instr": code, "recipe_dpi": 300})
        tab._manual_engine_check.click()          # a person unticks it
        yield 1500
        cell("fresh: engine unticked", "f2-engine-off",
             {"-i": "i1", "engine_box": False, "panel_shown": False,
              "-m": 10, "-a": 0.95})
        for code, want in (("CM", {"-m": 6, "-a": 1.0}),
                           ("isis", {"-m": 6, "-a": 1.0, "-p": "329x483",
                                     "-n": True, "-P": True}),
                           ("SS", {"-m": 6, "-a": 1.0, "-p": "A4",
                                   "-n": False, "-P": False}),
                           ("p3", {"-m": 6, "-a": 1.0}),
                           ("i1", {"-m": 10, "-a": 0.95})):
            user_instr(code)
            yield 1500
            cell(f"fresh: switched to {code}", f"f-switch-{code}",
                 {"-i": code, **want})
        rec["guided"] = _guided_margin(tab)
        d.note(f"fresh: Guided would build with {rec['guided']}")
        return

    if PHASE == "prefs":
        user_mode("manual")
        yield 1500
        # (instrument, -m, -a, button, preset chosen in Preferences or None,
        #  what must show afterwards)
        cases = [("CM", 10, 1.0, "Cancel", None, (10, 1.0)),
                 ("CM", 6, 0.95, "OK", None, (6, 0.95)),
                 ("i1", 6, 1.0, "Cancel", None, (6, 1.0)),
                 ("isis", 10, 1.0, "Cancel", None, (10, 1.0)),
                 ("SS", 10, 0.95, "OK", None, (10, 0.95)),
                 ("i1", 12, 0.85, "Cancel", None, (12, 0.85)),  # the control
                 # the preset CHANGED and confirmed
                 ("i1", 10, 0.95, "OK", "m6_a1.0", (6, 1.0)),
                 ("i1", 12, 0.85, "OK", "m10_a0.95", (12, 0.85)),
                 ("CM", 10, 0.95, "OK", "m10_a1.0", (10, 0.95)),
                 ("i1", 10, 0.95, "Cancel", "m6_a1.0", (10, 0.95))]
        for n, (code, m, a, btn, preset, want) in enumerate(cases):
            if tab._manual_instr_pw.get_raw_value() != code:
                user_instr(code)
                yield 1500
            user_margin(m, a)
            yield 800
            cell(f"prefs {n}: {code} set -m {m} -a {a} by hand",
                 f"p{n}-a-{code}-set", {"-i": code, "-m": m, "-a": a})
            before = d.settings.get("i1pro_default_preset")
            open_prefs()
            yield 2500
            dlg = prefs_dialog()
            if dlg is None:
                d.note(f"prefs {n}: Preferences did NOT open")
                rec.setdefault("errors", []).append(f"prefs {n} no dialog")
                continue
            if preset is not None:
                pick_preset(dlg, preset)
                yield 800
                d.shot(dlg, f"p{n}-b-preferences-preset-{preset}")
            elif n == 0:
                d.shot(dlg, f"p{n}-b-preferences-open")
            ok = close_prefs(btn)
            d.settings.sync()
            after = d.settings.get("i1pro_default_preset")
            d.note(f"prefs {n}: closed Preferences with {btn} ({ok}); preset "
                   f"{before} -> {after}"
                   f"{' (chosen ' + preset + ')' if preset else ', nothing changed'}")
            yield 2000
            c = cell(f"prefs {n}: {code} after Preferences {btn}"
                     f"{' with ' + preset if preset else ''}",
                     f"p{n}-c-{code}-after-{btn}",
                     {"-i": code, "-m": want[0], "-a": want[1]})
            c["preset_before"], c["preset_after"] = before, after
        return

    if PHASE == "preset-save":
        user_mode("manual")
        yield 1500
        cell("preset-save: i1Pro as opened", "s0-opened",
             {"-i": "i1", "-m": 10, "-a": 0.95})
        tab._save_defaults_btn.click()
        yield 2000
        keys = ("manual_printtarg_-i_l", "manual_printtarg_-m_l",
                "manual_printtarg_-m_l_enabled", "manual_printtarg_-a_l",
                "i1pro_default_preset")
        rec["store"] = store_now(keys)
        d.note(f"store after Save as Defaults: {rec['store']}")
        open_prefs()
        yield 2500
        dlg = prefs_dialog()
        pick_preset(dlg, "m6_a1.0")
        yield 800
        d.shot(dlg, "s1-preferences-preset-m6")
        close_prefs("OK")
        yield 2000
        rec["store_after_ok"] = store_now(keys)
        d.note(f"store after Preferences OK: {rec['store_after_ok']}")
        cell("preset-save: after Preferences OK with -m 6 -a 1.0",
             "s2-after-prefs", {"-i": "i1", "-m": 6, "-a": 1.0})
        user_mode("guided")
        yield 1500
        rec["guided_after_prefs"] = _guided_margin(tab)
        g = rec["guided_after_prefs"]
        d.note(f"guided after prefs: {g}" + ("" if isinstance(g, dict) and (g["margin"], g["patch_scale"]) == (6, 1.0) else "   <-- WRONG Guided is not on -m 6 -a 1.0"))
        d.shot(tab, "s3-guided")
        return

    if PHASE == "preset-restart":
        d.note(f"store at restart: preset={d.settings.get('i1pro_default_preset')}"
               f" -m={d.settings.get('manual_printtarg_-m_l')}"
               f" -a={d.settings.get('manual_printtarg_-a_l')}")
        if tab._mode_name() != "manual":
            user_mode("manual")
            yield 1500
        cell("preset-restart: Manual after restart", "r0-manual",
             {"-i": "i1", "-m": 6, "-a": 1.0})
        user_mode("guided")
        yield 1500
        rec["guided_after_restart"] = _guided_margin(tab)
        g = rec["guided_after_restart"]
        d.note(f"guided after restart: {g}" + ("" if isinstance(g, dict) and (g["margin"], g["patch_scale"]) == (6, 1.0) else "   <-- WRONG Guided is not on -m 6 -a 1.0"))
        d.shot(tab, "r1-guided")
        return

    if PHASE == "recipe-control2":
        # CONTROL for a start with the engine on: the same instrument and
        # paper, never saved, no recipe in the store.
        user_mode("manual")
        yield 1500
        cell(f"recipe-control2: {INSTR} on {PAPER}, engine on, never saved",
             "c2-control-engine-on-at-start",
             {"-i": INSTR, "-p": PAPER, "engine_box": True,
              "panel_instr": INSTR, "panel_paper": PAPER, "recipe_dpi": 300,
              "recipe_instrument_margins": True})
        return

    if PHASE == "recipe-control":
        # CONTROL: the same instrument and paper, no Save as Defaults, no
        # recipe in the store; the engine ticked on as a person does. What a
        # restart after an engine-off save must look like.
        user_mode("manual")
        yield 1500
        cell(f"recipe-control: {INSTR} on {PAPER}, engine off, never saved",
             "c0-control", {"-i": INSTR, "-p": PAPER, "engine_box": False})
        tab._manual_engine_check.click()
        yield 2000
        cell("recipe-control: engine ticked on", "c1-control-engine-on",
             {"-i": INSTR, "-p": PAPER, "engine_box": True,
              "panel_instr": INSTR, "panel_paper": PAPER, "recipe_dpi": 300})
        return

    if PHASE == "recipe-save":
        user_mode("manual")
        yield 1500
        if PAPER != "A4":
            c = tab._manual_paper_pw._custom_combo
            i = c.findData(PAPER)
            assert i >= 0, f"{PAPER} is not in the Paper field"
            c.setCurrentIndex(i)
            c.activated.emit(i)
            yield 1200
        cell(f"recipe-save: {INSTR} on {PAPER}, engine off, Manual", "e0-save",
             {"-i": INSTR, "-p": PAPER, "engine_box": False})
        tab._save_defaults_btn.click()
        yield 2000
        d.settings.sync()
        r = d.settings.get("manual_engine_recipe")
        rec["store"] = {"-i": d.settings.get("manual_printtarg_-i_l"),
                        "-p": d.settings.get("manual_printtarg_-p_l"),
                        "engine": d.settings.get("use_chromiq_layout_engine")}
        if isinstance(r, dict):
            rec["store"].update({f"recipe.{k}": r.get(k) for k in (
                "instrument", "paper", "border", "pscale")})
        d.note(f"store: {rec['store']}")
        return

    if PHASE in ("recipe-restart", "recipe-restart2"):
        r = d.settings.get("manual_engine_recipe")
        d.note(f"store at restart: -i {d.settings.get('manual_printtarg_-i_l')}"
               f" engine {d.settings.get('use_chromiq_layout_engine')}"
               f" recipe.instrument "
               f"{r.get('instrument') if isinstance(r, dict) else None}")
        if tab._mode_name() != "manual":
            user_mode("manual")
            yield 1500
        want = {"-i": INSTR, "-p": PAPER}
        on = {"-i": INSTR, "-p": PAPER, "engine_box": True,
              "panel_instr": INSTR, "panel_paper": PAPER, "recipe_dpi": 300}
        if PHASE == "recipe-restart2":
            # a start with the engine on and no recipe for this instrument
            # opens on its layout preset, which uses the instrument margins
            # (ticking the engine on instead converts printtarg's -m into
            # explicit margins, the control shows the same)
            on["recipe_instrument_margins"] = True
            want = on
        cell(f"{PHASE}: Manual as opened", f"{PHASE}-0-manual", want)
        if PHASE == "recipe-restart":
            tab._manual_engine_check.click()      # a person ticks it
            yield 2000
            cell(f"{PHASE}: engine ticked on", f"{PHASE}-1-engine-on", on)
        user_mode("guided")
        yield 1500
        rec["guided"] = _guided_margin(tab)
        d.note(f"{PHASE}: Guided would build with {rec['guided']}")
        user_mode("manual")
        yield 1500
        cell(f"{PHASE}: Guided and back to Manual", f"{PHASE}-2-back", on)
        return

    raise SystemExit(f"unknown phase {PHASE}")


if __name__ == "__main__":
    drive = Drive(OUT, language=os.environ.get("B8_LANG", "en"),
                  size=(1500, 1000))
    rc = drive.run(script)
    (OUT / "cells.json").write_text(json.dumps(
        {k: drive.record.get(k) for k in (
            "cells", "store", "store_after_ok", "guided_after_prefs",
            "guided_after_restart", "guided", "watchdog", "errors",
            "log_warnings_and_errors", "window_on_screen")},
        indent=2, default=str), encoding="utf-8")
    sys.exit(rc or 0)
