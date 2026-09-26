#!/usr/bin/env python3
"""B8-1260, B8-1262 and B8-1263 (beta 44 challenge F1, F6, F7), on screen.

    python scripts/drive_b8_1260_to_1263_fixes.py OUT

A fresh sandbox, no project, English, i1Pro, Manual, the paper filter at its
default (on), the shipped ticks.

* F1: Custom 420 x 297 (A3 Landscape's own size) with the layout engine ON,
  then with it OFF (printtarg's own Paper field): the Paper field and the open
  "Select preset" list photographed. Judged against what THE DRIVE CHOSE:
  Custom, so every built-in listed must be on a size the Paper field does not
  name (read from ``data/parameters.yaml``, never from ``paper_class``).
* F7: End and Home in the open "Select preset" list, photographed after each;
  judged against the last and first rows Up and Down can reach. The keys are
  sent to the list's view as Qt key events (macOS does not let a process it
  never activated take the keyboard, so a real key press would go to the
  terminal); they pass through the same event filter a real press does.
* F6: a ``preset_layout.request`` from a thread that is not the GUI thread,
  then ONLY the app's event loop for 12 s (no ``pending()``): whether
  automatic collection came back, sampled every second.

Sandboxed settings, presets and output folder; the ISO file forced to the
repo's copy (userdrive). A watchdog answers every modal the drive did not open
itself, and a deadline ends the run.
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
SB = OUT / "sandbox"
DEADLINE_MS = 300_000
GRACE_S = 20.0
if SB.exists():
    shutil.rmtree(SB)
(SB / "presets").mkdir(parents=True)
os.environ["CHROMIQ_SETTINGS_FILE"] = str(SB / "settings.ini")
os.environ["CHROMIQ_PRESETS_DIR"] = str(SB / "presets")
os.environ["CHROMIQ_COMPLIANCE_ISO_FILE"] = str(
    _TREE / "data" / "compliance_sets" / "iso12647.json")

from core.settings import AppSettings                         # noqa: E402
_s = AppSettings()
for _k, _v in {"chart_instrument": "i1", "chart_paper": "A4",
               "chart_mode": "manual", "manual_printtarg_-i_l": "i1",
               "use_chromiq_layout_engine": True,
               "restore_last_session": False, "restore_last_tab": False,
               "update_notify": False, "show_splash": False}.items():
    _s.set(_k, _v)
_s.sync()

from userdrive import Drive                                   # noqa: E402

OURS: set = set()


def _named_papers() -> set:
    import yaml
    data = yaml.safe_load((_TREE / "data" / "parameters.yaml").read_text(
        encoding="utf-8"))
    return next({c for c in p["choices"] if c != "custom"}
                for p in data["parameters"]["printtarg"]
                if p.get("flag") == "-p")


def _install_watchdog(d) -> None:
    from PyQt6.QtCore import QObject, QTimer
    from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

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
            wait = GRACE_S if type(w).__name__ in OURS else 0.8
            if time.monotonic() - first < wait:
                return
            text = d.modal_text(w)
            clicked = "(reject)"
            if isinstance(w, QMessageBox):
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
    import gc
    import threading
    from PyQt6.QtCore import QEvent, Qt
    from PyQt6.QtGui import QKeyEvent
    from PyQt6.QtWidgets import QApplication, QScrollArea
    from ui.tabs.tab_chart import BUILTIN_PRESET_KEYS, builtin_preset_paper
    from workflow import preset_layout as PL

    rec = d.record
    rec["scenes"] = []
    _install_watchdog(d)
    d.goto_tab("chart")
    yield 1500
    tab = d.win._tab_chart
    tab._manual_btn.click()
    yield 1500
    cb = tab._preset_combo
    view = cb.view()
    panel = tab._manual_layout_panel
    named = _named_papers()

    def listed_builtins():
        """The built-in presets the open list shows (not hidden)."""
        return [cb.itemData(r) for r in range(cb.count())
                if not view.isRowHidden(r)
                and cb.itemData(r) in BUILTIN_PRESET_KEYS]

    def reachable():
        m = cb.model()
        out = []
        for r in range(cb.count()):
            if view.isRowHidden(r):
                continue
            f = m.flags(m.index(r, 0))
            if f & Qt.ItemFlag.ItemIsEnabled \
                    and f & Qt.ItemFlag.ItemIsSelectable:
                out.append(r)
        return out

    def scroll_to(w):
        sa = w.parentWidget()
        while sa is not None and not isinstance(sa, QScrollArea):
            sa = sa.parentWidget()
        if sa is not None:
            sa.ensureWidgetVisible(w, 50, 200)

    def shoot(widget, name):
        for _attempt in range(3):
            if d.shot(widget, name):
                return True
            d.pump(1000)
        return False

    def open_list():
        cb.showPopup()
        d.pump(1200)
        view.scrollToTop()
        d.pump(300)

    def f1_scene(name, engine):
        cb.hidePopup()
        d.pump(300)
        keys = listed_builtins()
        on_named = [k for k in keys if str(builtin_preset_paper(k)) in named]
        s = {"scene": name, "engine": engine,
             "paper_on_screen": tab._manual_paper_on_screen(),
             "filter_reads": tab._preset_paper_selected(),
             "builtins_listed": len(keys),
             "builtins_on_a_named_paper": on_named,
             "ok": bool(keys) and not on_named}
        rec["scenes"].append(s)
        d.note(f"{name}: engine {'on' if engine else 'off'}, paper "
               f"{s['paper_on_screen']!r}, filter reads "
               f"{s['filter_reads']!r}, {len(keys)} built-ins listed, "
               f"{len(on_named)} on a named paper: "
               f"{'ok' if s['ok'] else 'WRONG'}")

    # ---------------------------------------------------------------- F1
    i = panel.paper.findData("420x297")
    panel.paper.setCurrentIndex(i)
    panel.paper.activated.emit(i)
    yield 1200
    panel.custom_w.setValue(420)
    panel.custom_h.setValue(297)
    i = panel.paper.findData("__custom__")
    panel.paper.setCurrentIndex(i)
    panel.paper.activated.emit(i)
    yield 1500
    f1_scene("F1 engine on, Custom 420 x 297 after A3 Landscape", True)
    scroll_to(panel.custom_h)
    yield 600
    shoot(d.win, "F1-engine-on-custom-420x297-window")
    open_list()
    shoot(view, "F1-engine-on-custom-420x297-select-preset-open")

    # ---------------------------------------------------------------- F7
    def key(k):
        QApplication.sendEvent(view, QKeyEvent(
            QEvent.Type.KeyPress, k, Qt.KeyboardModifier.NoModifier))
        d.pump(400)
        return view.currentIndex().row()

    for label, k, want in (("End", Qt.Key.Key_End, "last"),
                           ("Home", Qt.Key.Key_Home, "first"),
                           ("End again", Qt.Key.Key_End, "last")):
        rows = reachable()
        before = view.currentIndex().row()
        got = key(k)
        exp = rows[-1] if want == "last" else rows[0]
        s = {"scene": f"F7 {label}", "row_before": before, "row_after": got,
             "text_after": cb.itemText(got), "expected_row": exp,
             "expected_text": cb.itemText(exp), "ok": got == exp}
        rec["scenes"].append(s)
        d.note(f"F7 {label}: row {before} -> {got} {cb.itemText(got)!r}; "
               f"expected {exp} {cb.itemText(exp)!r}: "
               f"{'ok' if s['ok'] else 'WRONG'}")
        shoot(view, f"F7-{label.replace(' ', '-').lower()}-select-preset")
    cb.hidePopup()
    yield 600

    # F1 with the engine OFF: printtarg's own Paper field on screen
    tab._manual_engine_check.setChecked(False)
    yield 1500
    pw = tab._manual_paper_pw
    c = pw._custom_combo
    i = c.findData("420x297")
    c.setCurrentIndex(i)
    c.activated.emit(i)
    yield 1000
    pw._custom_w_spin.setValue(420)
    pw._custom_h_spin.setValue(297)
    i = c.findData("custom")
    c.setCurrentIndex(i)
    c.activated.emit(i)
    yield 1500
    f1_scene("F1 engine off, Custom 420 x 297 after A3 Landscape", False)
    scroll_to(pw._custom_h_spin)
    yield 600
    shoot(d.win, "F1-engine-off-custom-420x297-window")
    open_list()
    shoot(view, "F1-engine-off-custom-420x297-select-preset-open")
    cb.hidePopup()
    yield 500
    tab._manual_engine_check.setChecked(True)
    yield 1000

    # ---------------------------------------------------------------- F6
    PL.settle(30)
    samples = [{"t": 0, "gc_enabled": gc.isenabled(),
                "held": PL.gc_held()}]

    def caller():
        PL.request(("drive-f6", time.time()),
                   lambda: [object() for _ in range(5000)])
    t = threading.Thread(target=caller, name="drive-f6-caller")
    t.start()
    t.join(5)
    t0 = time.monotonic()
    for sec in range(1, 13):
        yield 1000                    # only the app's own event loop runs
        samples.append({
            "t": round(time.monotonic() - t0, 1),
            "gc_enabled": gc.isenabled(), "held": PL.gc_held(),
            "layout_threads": [x.name for x in threading.enumerate()
                               if x.name == "chromiq-preset-layout"]})
    back = next((s["t"] for s in samples[1:] if s["gc_enabled"]), None)
    s = {"scene": "F6 request from a worker thread, no pending()",
         "samples": samples, "gc_back_after_s": back,
         "ok": samples[-1]["gc_enabled"] and not samples[-1]["held"]}
    rec["scenes"].append(s)
    d.note(f"F6: collection back after {back} s; at 12 s enabled="
           f"{samples[-1]['gc_enabled']} held={samples[-1]['held']}: "
           f"{'ok' if s['ok'] else 'WRONG'}")


if __name__ == "__main__":
    drive = Drive(OUT, language="en", size=(1500, 1000))
    rc = drive.run(script)
    (OUT / "scenes.json").write_text(json.dumps(
        {"scenes": drive.record.get("scenes", []),
         "watchdog": drive.record.get("watchdog", [])}, indent=2,
        default=str), encoding="utf-8")
    sys.exit(rc or 0)
