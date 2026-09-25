#!/usr/bin/env python3
"""#182 K46 (Knut, 5834773589), driven ON SCREEN.

    python scripts/drive_k46.py <out> <en|de> <light|dark|neutral>

Create Chart on Manual A4, a fresh sandboxed settings file (so the paper
filter is ON, its default):

    01  "Select preset" open and scrolled to its end: the note, filter ON
    02  the Built-in presets list scrolled to its end: the note, filter ON
    03  the gear's tooltip, which names the window
    04  the window, "Settings for built-in presets", its box ticked
        the box unticked, OK
    05  "Select preset" at its end: the note, filter OFF
    06  the Built-in presets list at its end: the note, filter OFF

and checks, on the real widgets: the note is the last row of both lists with
the text for the state, it is disabled and not selectable, Down / End /
PageDown / the wheel / type-ahead on the closed combo and Down / End in the
open list never land on it, the preset handler refuses it, and the Built-in
presets list's keyboard rows never include it.

**A WATCHDOG ANSWERS WHAT THE SCRIPT DID NOT EXPECT.** Every 500 ms it looks
for a modal window that is not ours; one left up for 4 s is recorded and
closed with Cancel / Close / OK (English or German), or Escape. A hard
deadline quits the app. Basti never has to click.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

DEADLINE_S = 300


def script_for(language, look):
    def script(d):
        from PyQt6.QtCore import QPoint, QPointF, Qt, QTimer
        from PyQt6.QtGui import QWheelEvent
        from PyQt6.QtTest import QTest
        from PyQt6.QtWidgets import QApplication, QToolTip
        from core import curated_presets as cp
        from ui.tabs.tab_chart import preset_list_note
        rec = d.record
        rec.update({"language": language, "appearance": look, "checks": [],
                    "found": {}})
        tag = f"{language}-{look}"
        started = time.monotonic()
        expecting = {"on": False}
        seen_since: dict = {}

        def watchdog():
            if time.monotonic() - started > DEADLINE_S:
                d.note("WATCHDOG: deadline reached, quitting")
                QApplication.instance().quit()
                return
            m = QApplication.activeModalWidget()
            if (m is None or not m.isVisible() or expecting["on"]
                    or type(m).__name__ == "BuiltinPresetsShownDialog"):
                seen_since.clear()
                return
            first = seen_since.setdefault(id(m), time.monotonic())
            if time.monotonic() - first < 4:
                return
            seen_since.pop(id(m), None)
            from PyQt6.QtWidgets import QAbstractButton
            said = d.modal_text(m)
            d.note(f"WATCHDOG: unexpected {type(m).__name__}: {said[:200]!r}")
            rec.setdefault("watchdog", []).append(
                {"class": type(m).__name__, "text": said})
            for word in ("Cancel", "Abbrechen", "Close", "Schließen", "OK"):
                for b in m.findChildren(QAbstractButton):
                    if b.isVisible() and b.text().replace("&", "") == word:
                        b.click()
                        return
            m.close()

        dog = QTimer()
        dog.timeout.connect(watchdog)
        dog.start(500)
        rec["_dog"] = str(dog)

        def check(what, ok, detail=""):
            rec["checks"].append({"what": what, "ok": bool(ok),
                                  "detail": detail})
            d.note(f"   {'OK  ' if ok else 'FAIL'} {what} {detail}")

        d.goto_tab("chart")
        yield 1500
        tab = d.win._tab_chart
        tab._user_switch_mode("manual")
        yield 1200
        tab._set_manual_value("printtarg", "-p", "A4")
        yield 1500
        cb = tab._preset_combo
        view = cb.view()

        def note_rows():
            return [r for r in range(cb.count())
                    if cb.itemData(r, cb.NOTE_ROLE)]

        def last_preset():
            return max(r for r in range(cb.count())
                       if isinstance(cb.itemData(r), str)
                       and not cp.is_not_a_preset(cb.itemData(r))
                       and not view.isRowHidden(r)
                       and cb.model().item(r).isEnabled())

        def the_combo(state, photo):
            want = preset_list_note(state)
            rows = note_rows()
            check(f"[{state and 'ON' or 'OFF'}] Select preset: one note, "
                  "the last row", rows == [cb.count() - 1], repr(rows))
            if not rows:
                return
            row = rows[0]
            check(f"[{state and 'ON' or 'OFF'}] Select preset: the note's "
                  "text", cb.itemText(row) == want, repr(cb.itemText(row)))
            rec["found"][f"select_preset_note_{'on' if state else 'off'}"] = \
                cb.itemText(row)
            flags = cb.model().item(row).flags()
            check("the note is disabled and not selectable",
                  not flags & Qt.ItemFlag.ItemIsEnabled
                  and not flags & Qt.ItemFlag.ItemIsSelectable)
            # the closed combo: keys, wheel, type-ahead
            last = last_preset()
            landed = []
            for key in (Qt.Key.Key_Down, Qt.Key.Key_End, Qt.Key.Key_PageDown):
                cb.setCurrentIndex(last)
                QTest.keyClick(cb, key)
                landed.append(cb.currentIndex())
            cb.setCurrentIndex(last)
            for _ in range(3):
                QApplication.sendEvent(cb, QWheelEvent(
                    QPointF(5, 5), QPointF(cb.mapToGlobal(QPoint(5, 5))),
                    QPoint(0, 0), QPoint(0, -120), Qt.MouseButton.NoButton,
                    Qt.KeyboardModifier.NoModifier,
                    Qt.ScrollPhase.NoScrollPhase, False))
                landed.append(cb.currentIndex())
            for words in (want[:9], want[:1]):
                cb.setCurrentIndex(last)
                QTest.keyClicks(cb, words)
                landed.append(cb.currentIndex())
            check("closed combo: Down, End, PageDown, the wheel and "
                  "type-ahead never land on the note", row not in landed,
                  repr(landed))
            before = cb.currentIndex()
            cb.blockSignals(True)
            cb.setCurrentIndex(row)
            cb.blockSignals(False)
            tab._on_preset_selected(row)
            check("the preset handler refuses the note (the pulldown goes "
                  "back to the last real choice)",
                  cb.currentIndex() != row
                  and not cp.is_not_a_preset(cb.currentData()),
                  f"{before} -> {cb.currentIndex()}")
            # the open list, scrolled to its end, photographed
            cb.setCurrentIndex(last)
            cb.showPopup()
            yield 900
            view.setCurrentIndex(cb.model().index(last, 0))
            open_landed = []
            for key in (Qt.Key.Key_Down, Qt.Key.Key_End):
                QTest.keyClick(view, key)
                open_landed.append(view.currentIndex().row())
            check("open list: Down and End never land on the note",
                  row not in open_landed, repr(open_landed))
            view.setCurrentIndex(cb.model().index(last, 0))
            view.scrollToBottom()
            yield 600
            if not d.shot(view, photo):
                yield 1500                     # once more, the popup settled
                d.shot(view, photo)
            cb.hidePopup()
            yield 600

        def the_overlay(state, photo):
            tab._open_builtin_preset_overlay()
            yield 1200
            pop = getattr(tab, "_builtin_preset_popup", None)
            check(f"[{state and 'ON' or 'OFF'}] the Built-in presets list "
                  "opens", pop is not None and pop.isVisible())
            if pop is None:
                return
            rows = pop._rows
            want = preset_list_note(state)
            check(f"[{state and 'ON' or 'OFF'}] Built-in presets list: the "
                  "note is the last row, with its text",
                  bool(rows) and rows[-1].kind == "note"
                  and rows[-1].text == want)
            check("Built-in presets list: the keyboard's rows skip the note",
                  (len(rows) - 1) not in pop._selectable())
            for _ in range(len(rows) + 2):
                QTest.keyClick(pop, Qt.Key.Key_Down)
            check("Built-in presets list: Down to the end stops before the "
                  "note", pop._hover_index != len(rows) - 1,
                  str(pop._hover_index))
            pop._scroll_y = pop._max_scroll
            pop.update()
            yield 500
            d.shot(pop, photo)
            pop.close()
            yield 600

        # ---- filter ON (a fresh settings file: the default) --------------
        check("the paper filter is ON (the default)",
              cp.paper_filter_on(d.settings))
        yield from the_combo(True, f"{tag}-01-select-preset-filter-on")
        yield from the_overlay(True, f"{tag}-02-builtin-list-filter-on")

        # ---- the gear's tooltip -------------------------------------------
        btn = tab._preset_shown_btn
        tip = btn.toolTip()
        rec["found"]["gear_tooltip"] = tip
        name = cp  # noqa: F841 (keeps the import obvious)
        from core.i18n import tr
        window_name = tr("Settings for built-in presets")
        rec["found"]["window_name"] = window_name
        check("the gear's tooltip starts with the window's name",
              tip.split("\n")[0] == window_name, repr(tip[:60]))
        # THE REAL POINTER over the gear, so Qt shows its own tooltip the way
        # a hover does (a tooltip shown from code is hidden again as soon as
        # the pointer is not over the button). Nothing is clicked.
        from PyQt6.QtGui import QCursor
        saved_pos = QCursor.pos()
        QCursor.setPos(btn.mapToGlobal(btn.rect().center()))
        yield 2500
        tips = [w for w in QApplication.topLevelWidgets()
                if w.objectName() == "qtooltip_label" and w.isVisible()]
        if tips:
            rec["found"]["gear_tooltip_on_screen"] = tips[0].text()
            try:
                d.shot(tips[0], f"{tag}-03-gear-tooltip")
            except RuntimeError as exc:
                d.note(f"   (the tooltip closed before its photograph: {exc})")
        else:
            d.note("   (the tooltip window was not found)")
        QCursor.setPos(saved_pos)
        QToolTip.hideText()
        yield 500

        # ---- the window: title, box off, OK -------------------------------
        d.later(btn.click)
        yield 1800
        g = d.top_dialog("BuiltinPresetsShownDialog")
        check("the gear opens the window", g is not None)
        if g is not None:
            rec["found"]["window_title"] = g.windowTitle()
            check("the window's title is its name",
                  g.windowTitle() == window_name, repr(g.windowTitle()))
            d.shot(g, f"{tag}-04-settings-window")
            g._paper_filter.setChecked(False)
            yield 400
            g._ok_btn.click()
            d._modal_closed()
            yield 1500
        check("OK stored the filter OFF", not cp.paper_filter_on(d.settings))

        # ---- filter OFF ---------------------------------------------------
        yield from the_combo(False, f"{tag}-05-select-preset-filter-off")
        yield from the_overlay(False, f"{tag}-06-builtin-list-filter-off")

        dog.stop()
        rec.pop("_dog", None)
        (d.out / "k46-found.json").write_text(
            json.dumps({k: rec.get(k) for k in ("checks", "found",
                                                 "language", "appearance",
                                                 "watchdog")},
                       indent=2, ensure_ascii=False, default=str),
            encoding="utf-8")
    return script


def main() -> int:
    out = Path(sys.argv[1])
    language = sys.argv[2] if len(sys.argv) > 2 else "en"
    look = sys.argv[3] if len(sys.argv) > 3 else "light"
    from userdrive import Drive
    d = Drive(out, projects=[], language=language, appearance=look)
    return d.run(script_for(language, look))


if __name__ == "__main__":
    raise SystemExit(main())
