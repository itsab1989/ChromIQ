#!/usr/bin/env python3
"""K48 (Knut, #182 5840677938 and 5840692243), on screen.

    python scripts/drive_k48_preset_lists.py OUT

A fresh sandbox, no project, English, i1Pro, Manual, the ChromIQ layout engine
on, the paper filter at its default (on), the shipped ticks. Every scene reads
both lists, "Select preset" (the rows not hidden, arrows closed) and the
Built-in presets list (the popup's groups and what waits under its arrows),
judges them against the rule the gear window's help now states, and
photographs both open lists by window id:

* case 2 of Knut's first log: fresh start, A4, then the filter OFF and ON
  again through the gear window (OK), the two lists must agree each time;
* A3 Landscape: ColorMunki has presets there and none ticked, so its heading
  and "8 more presets" only (K48-1); no Scanner (its presets are A4 and
  Letter Landscape, the addendum);
* Custom 210 x 297 after A3 Landscape: every custom-size built-in, whatever
  the boxes say (K48-2), never A3 Landscape's lists;
* A4 Landscape: the Scanner presets on that paper;
* the gear window, and both of its help windows, photographed (K48-3, K48-4).

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

OURS = {"BuiltinPresetsShownDialog", "_InfoDialog"}


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
    import core.curated_presets as cp
    from PyQt6.QtCore import Qt
    from ui.tabs.tab_chart import (BUILTIN_PRESET_GROUPS, BUILTIN_PRESET_KEYS,
                                   builtin_preset_paper)
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
    heads = {h for h, _e in BUILTIN_PRESET_GROUPS}

    # THE EXPECTED PAPER IS NOT ASKED OF THE CODE UNDER TEST (beta 44
    # challenge F1). This driver used to take the paper from
    # `tab._preset_paper_selected()` and match presets through
    # `cp.paper_matches`, the very functions the filter runs, so a Custom
    # 420 x 297 that the filter read as A3 Landscape was judged "ok". The
    # paper now comes from the ENTRY the Paper field shows ("Custom…" is the
    # Custom class whatever the boxes hold, C7), and a preset's class from
    # the named entries the Paper fields offer.
    NAMED = set()
    for _c in (panel.paper, tab._manual_paper_pw._custom_combo,
               tab._paper_combo):
        NAMED |= {str(_c.itemData(i)) for i in range(_c.count())}
    NAMED -= {"custom", "__custom__", "None", ""}

    def preset_class(paper):
        paper = str(paper or "")
        return paper if paper in NAMED else "custom"

    def expected_paper():
        if not cp.paper_filter_on(d.settings):
            return ""
        data = str(panel.paper.currentData() or "")
        return "custom" if data == "__custom__" else data

    def expected():
        """(heading, ticked keys listed directly, the count under its arrow)
        for every group the rule lists: the paper filter by the paper on
        screen, Scanner too, Custom as one class, ticked directly, the rest
        under the arrow, a group with none ticked its heading and arrow."""
        shown = cp.shown_keys(d.settings, BUILTIN_PRESET_KEYS)
        sel = expected_paper()
        out = []
        for h, es in BUILTIN_PRESET_GROUPS:
            keys = [k for *_x, k in es]
            if sel:
                keys = [k for k in keys
                        if preset_class(builtin_preset_paper(k)) == sel]
            if keys:
                out.append((h, [k for k in keys if k in shown],
                            len([k for k in keys if k not in shown])))
        return out

    def read_pulldown():
        tab._reveal_current_preset_group()
        out, cur = [], None
        for r in range(cb.count()):
            if view.isRowHidden(r):
                continue
            text, key = cb.itemText(r), cb.itemData(r)
            if key is None and text in heads:
                cur = [text, [], 0]
                out.append(cur)
            elif cur is not None and cb.itemData(r, cb.MORE_ROLE):
                cur[2] = int(cb.itemData(r, Qt.ItemDataRole.UserRole + 44)
                             or 0)
            elif cur is not None and isinstance(key, str):
                cur[1].append(key)
        return [tuple(x) for x in out]

    def read_popup():
        tab._open_builtin_preset_overlay()
        pop = tab._builtin_preset_popup
        got = [(h, [k for _l, k in e], len(pop._more.get(h, [])))
               for h, e in pop._groups]
        return pop, got

    def scene(name, photo=True):
        exp = [(h, top, n) for h, top, n in expected()]
        pull = read_pulldown()
        pop, popg = read_popup()
        ok_pull = pull == exp
        ok_pop = popg == exp
        s = {"scene": name, "paper_on_screen": tab._manual_paper_on_screen(),
             "paper_entry_on_screen": panel.paper.currentText(),
             "expected_paper": expected_paper(),
             "filter_paper": tab._preset_paper_selected(),
             "filter_on": cp.paper_filter_on(d.settings),
             "expected": exp, "pulldown": pull, "popup": popg,
             "pulldown_ok": ok_pull, "popup_ok": ok_pop}
        rec["scenes"].append(s)
        d.note(f"{name}: paper {s['paper_on_screen']!r} filter "
               f"{s['filter_paper']!r}: pulldown "
               f"{'ok' if ok_pull else 'WRONG'}, popup "
               f"{'ok' if ok_pop else 'WRONG'}; groups "
               f"{[(h, len(t), n) for h, t, n in popg]}")
        if photo:
            d.shot(pop, f"{name}-builtin-presets-list")
        pop.close()

    def choose(code, dims=None):
        c = panel.paper
        i = c.findData(code)
        if dims:
            panel.custom_w.setValue(dims[0])
            panel.custom_h.setValue(dims[1])
        assert i >= 0, code
        c.setCurrentIndex(i)
        c.activated.emit(i)

    # A list that has only just opened is sometimes not yet a window the
    # server will hand over; the photograph is tried again (three times at
    # most) after a longer wait, and every attempt is in driver-notes.txt.
    def pulldown_photo(name):
        for attempt in range(3):
            cb.showPopup()
            yield 1200 + 800 * attempt
            view.scrollToTop()
            yield 400
            ok = d.shot(view, f"{name}-select-preset")
            cb.hidePopup()
            yield 500
            if ok:
                return

    def popup_photo(name):
        for attempt in range(3):
            tab._open_builtin_preset_overlay()
            yield 1200 + 800 * attempt
            ok = d.shot(tab._builtin_preset_popup,
                        f"{name}-builtin-presets-list")
            tab._builtin_preset_popup.close()
            yield 500
            if ok:
                return

    def gear(filter_on=None, photos=None):
        d.later(tab._preset_shown_btn.click)
        dlg = None
        for _ in range(20):
            yield 300
            dlg = d.top_dialog("BuiltinPresetsShownDialog")
            if dlg is not None:
                break
        if dlg is None:
            d.note("   the gear window did not open")
            return
        yield 800
        if photos:
            for attempt in range(3):
                if d.shot(dlg, f"{photos}-gear-window"):
                    break
                yield 1000
            for btn, tag in ((dlg._help, "window-help"),
                             (dlg._paper_filter_help, "paper-filter-help")):
                d.later(btn.click)
                info = None
                for _ in range(20):
                    yield 300
                    info = d.top_dialog("_InfoDialog")
                    if info is not None:
                        break
                if info is None:
                    d.note(f"   {tag}: the help window did not open")
                    continue
                yield 800
                d.shot(info, f"{photos}-{tag}")
                rec.setdefault("help_texts", {})[tag] = btn.dialog_body() \
                    if hasattr(btn, "dialog_body") else btn._body
                info.reject()
                yield 600
        if filter_on is not None:
            dlg._paper_filter.setChecked(filter_on)
            dlg._ok_btn.click()
        else:
            dlg._close_btn.click()
        yield 1200

    # Case 2 of Knut's first log: fresh start, no project, A4.
    choose("A4")
    yield 1500
    scene("1-fresh-A4-filter-on", photo=False)
    yield from pulldown_photo("1-fresh-A4-filter-on")
    yield from popup_photo("1-fresh-A4-filter-on")
    yield from gear(filter_on=False)
    scene("2-fresh-A4-filter-off", photo=False)
    yield from pulldown_photo("2-fresh-A4-filter-off")
    yield from popup_photo("2-fresh-A4-filter-off")
    yield from gear(filter_on=True)
    scene("3-fresh-A4-filter-on-again", photo=False)
    yield from pulldown_photo("3-fresh-A4-filter-on-again")
    yield from popup_photo("3-fresh-A4-filter-on-again")

    # A3 Landscape: ColorMunki none ticked, no Scanner.
    choose("420x297")
    yield 1500
    scene("4-A3-landscape", photo=False)
    yield from pulldown_photo("4-A3-landscape")
    yield from popup_photo("4-A3-landscape")

    # Custom 210 x 297 after A3 Landscape (Knut's screenshot).
    choose("__custom__", (210, 297))
    yield 1500
    scene("5-custom-210x297", photo=False)
    yield from pulldown_photo("5-custom-210x297")
    yield from popup_photo("5-custom-210x297")

    # F1: Custom sizes that spell a named paper's code, each after the
    # named paper it spells, so a filter reading the size shows that paper.
    for named, dims in (("420x297", (420, 297)), ("127x178", (127, 178)),
                        ("594x420", (594, 420)), ("329x483", (329, 483)),
                        ("483x329", (483, 329)), ("203x254", (203, 254))):
        if panel.paper.findData(named) >= 0:
            choose(named)
            yield 1200
            scene(f"F1-named-{named}", photo=False)
        choose("__custom__", dims)
        yield 1500
        tag = f"F1-custom-{dims[0]}x{dims[1]}"
        scene(tag, photo=False)
        if dims == (420, 297):
            # the Paper field itself, so the picture shows it IS Custom
            from PyQt6.QtWidgets import QScrollArea
            sa = panel.paper.parentWidget()
            while sa is not None and not isinstance(sa, QScrollArea):
                sa = sa.parentWidget()
            if sa is not None:
                sa.ensureWidgetVisible(panel.custom_h, 50, 200)
            yield 800
            for _attempt in range(3):
                if d.shot(d.win, f"{tag}-window-paper-field"):
                    break
                yield 1000
            yield from pulldown_photo(tag)
            yield from popup_photo(tag)

    # A4 Landscape: the Scanner presets on it.
    if panel.paper.findData("A4R") >= 0:
        choose("A4R")
        yield 1500
        scene("6-A4-landscape", photo=False)
        yield from pulldown_photo("6-A4-landscape")
        yield from popup_photo("6-A4-landscape")

    # The gear window and its two help windows.
    yield from gear(photos="7")


if __name__ == "__main__":
    drive = Drive(OUT, language="en", size=(1500, 1000))
    rc = drive.run(script)
    (OUT / "scenes.json").write_text(json.dumps(
        {"scenes": drive.record.get("scenes", []),
         "help_texts": drive.record.get("help_texts", {}),
         "watchdog": drive.record.get("watchdog", [])}, indent=2),
        encoding="utf-8")
    sys.exit(rc or 0)
