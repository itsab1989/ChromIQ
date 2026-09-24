#!/usr/bin/env python3
"""K35 on screen: the gear, the window, the arrow rows (Knut, #182 5818659478).

    python scripts/drive_k35_curated_presets.py OUT_DIR en first
    python scripts/drive_k35_curated_presets.py OUT_DIR en restart
    CHROMIQ_TREE=<the tree before> python scripts/drive_k35_curated_presets.py OUT_DIR en before

``first`` drives a fresh sandbox: the Presets frame with its gear, the "Select
preset" pulldown with the first arrow closed, opened with the Right arrow key
and closed with Left, the Built-in presets list the same way, the window behind
the gear (one preset ticked, one cleared, closed with its Close button) and the
pulldown after it. ``restart`` is a second process on the SAME sandbox
settings: the choice must still be there. ``before`` photographs the frame, the
pulldown and the list on a tree without the feature.

Two user presets are written into the sandboxed presets folder first, to show
they stay on top of the pulldown.

**NOBODY HAS TO CLICK.** A watchdog answers every question the app asks while
this runs (the auto-update-preview question included) with its No / Cancel /
reject button, records it and photographs it. A second timer ends the whole
run after four minutes whatever happens.

The keys are Qt key events delivered to the list (QTest), because macOS does
not let a process that it never activated take the keyboard focus; the list
receives exactly the event a key press produces.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

OUT, LANG, PHASE = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
DEADLINE_MS = 240_000

# The sandbox is made by userdrive; the user presets must be in place before
# the window is built.
_presets = OUT.resolve() / "sandbox" / "presets" / "Create Chart"
_presets.mkdir(parents=True, exist_ok=True)
for _name, _data in (("My A4 test 400", {"targen_-f": 400, "printtarg_-p": "A4"}),
                     ("Studio Letter 800", {"targen_-f": 800,
                                            "printtarg_-p": "Letter"})):
    (_presets / f"{_name}.json").write_text(json.dumps(
        {"chromiq_preset_version": 1, "tab": "create_chart", "name": _name,
         "data": _data}, indent=2), encoding="utf-8")

from userdrive import Drive                                   # noqa: E402

OURS = {"BuiltinPresetsShownDialog"}


def _install_watchdog(d) -> None:
    from PyQt6.QtCore import QObject, QTimer
    from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

    class Watchdog(QObject):
        def __init__(self):
            super().__init__(QApplication.instance())
            self.n = 0
            self._t = QTimer(self)
            self._t.setInterval(400)
            self._t.timeout.connect(self.tick)
            self._t.start()
            self._end = QTimer(self)
            self._end.setSingleShot(True)
            self._end.timeout.connect(self.deadline)
            self._end.start(DEADLINE_MS)

        def tick(self):
            w = QApplication.activeModalWidget()
            if w is None or not w.isVisible() or type(w).__name__ in OURS:
                return
            self.n += 1
            text = d.modal_text(w)
            try:
                from onscreen_capture import capture_window
                capture_window(w, d.shots / f"watchdog-{self.n:02d}.png")
            except Exception:                              # noqa: BLE001
                pass
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
                {"class": type(w).__name__, "text": text, "clicked": clicked})
            d.note(f"   [watchdog] {type(w).__name__}: "
                   f"{text[:160].replace(chr(10), ' / ')!r} -> {clicked}")

        def deadline(self):
            d.note("DEADLINE: the drive ran past four minutes and was ended")
            d.record["deadline_hit"] = True
            d._flush()
            QApplication.instance().quit()

    d._watchdog = Watchdog()


def script(d):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QAbstractItemView
    rec = d.record
    rec.update({"language": LANG, "phase": PHASE, "checks": []})

    def check(what, ok, detail=""):
        rec["checks"].append({"what": what, "ok": bool(ok), "detail": detail})
        d.note(f"   {'OK  ' if ok else 'FAIL'} {what} {detail}")

    _install_watchdog(d)
    d.goto_tab("chart")
    tab = d.win._tab_chart
    tab._user_switch_mode("manual")
    yield 1500
    cb = tab._preset_combo
    view = cb.view()
    curated = hasattr(cb, "MORE_ROLE")
    rec["tree_has_the_feature"] = curated

    def visible_rows():
        return [cb.itemText(r) for r in range(cb.count())
                if not view.isRowHidden(r)]

    user_rows = [cb.itemText(r) for r in (1, 2)]
    check("the two user presets are the first two rows",
          user_rows == ["My A4 test 400", "Studio Letter 800"], str(user_rows))
    rec["rows_total"] = cb.count()
    rec["rows_visible"] = len(visible_rows())

    if PHASE == "before":
        d.shot(d.win, f"{LANG}-before-01-presets-frame")
        cb.showPopup()
        yield 900
        view.scrollTo(cb.model().index(0, 0),
                      QAbstractItemView.ScrollHint.PositionAtTop)
        yield 400
        d.shot(view, f"{LANG}-before-02-pulldown")
        cb.hidePopup()
        yield 500
        tab._open_builtin_preset_overlay()
        yield 900
        d.shot(tab._builtin_preset_popup, f"{LANG}-before-03-builtin-list")
        tab._builtin_preset_popup.close()
        yield 500
        return

    from core.curated_presets import user_choices
    arrows = [r for r in range(cb.count()) if cb.itemData(r, cb.MORE_ROLE)]
    first_arrow = arrows[0]
    group = cb.itemData(first_arrow, cb.MORE_ROLE)
    tick_key = next(cb.itemData(r) for r in range(1, cb.count())
                    if "A3-180p" in cb.itemText(r))
    untick_key = cb.itemData(first_arrow - 1)
    rec["group"] = group

    if PHASE == "restart":
        ch = user_choices(d.settings)
        # the one cleared in the first phase, whatever sits above the arrow now
        untick_key = next((k for k, v in ch.items() if v is False), untick_key)
        rec["stored_choice"] = ch
        check("the choice survived the restart",
              ch.get(tick_key) is True and ch.get(untick_key) is False, str(ch))
        check("the ticked preset is listed directly",
              not view.isRowHidden(cb.findData(tick_key)))
        check("the cleared preset waits under the arrow",
              view.isRowHidden(cb.findData(untick_key)))
        cb.showPopup()
        yield 900
        row = cb.findData(tick_key)
        view.scrollTo(cb.model().index(row, 0),
                      QAbstractItemView.ScrollHint.PositionAtCenter)
        view.setCurrentIndex(cb.model().index(row, 0))
        yield 500
        d.shot(view, f"{LANG}-11-pulldown-after-restart")
        cb.hidePopup()
        yield 500
        return

    # 01 the frame with the gear
    rec["gear_tooltip"] = tab._preset_shown_btn.toolTip()
    d.note(f"gear tooltip: {tab._preset_shown_btn.toolTip()!r}")
    d.shot(d.win, f"{LANG}-01-presets-frame-with-gear")

    # 02 the pulldown, the first arrow closed
    cb.showPopup()
    yield 900
    view.setCurrentIndex(cb.model().index(first_arrow, 0))
    view.scrollTo(cb.model().index(first_arrow, 0),
                  QAbstractItemView.ScrollHint.PositionAtCenter)
    yield 500
    check("the arrow row points right while closed",
          cb.itemText(first_arrow).startswith("▸"), cb.itemText(first_arrow))
    check("the rows under it are hidden", view.isRowHidden(first_arrow + 1))
    d.shot(view, f"{LANG}-02-pulldown-arrow-closed")

    # 03 Right opens it, the list stays open, nothing is chosen
    before_index = cb.currentIndex()
    QTest.keyClick(view, Qt.Key.Key_Right)
    yield 600
    check("Right opens the group", cb.itemText(first_arrow).startswith("▾")
          and not view.isRowHidden(first_arrow + 1), cb.itemText(first_arrow))
    check("the list stays open", view.window().isVisible())
    check("nothing was chosen", cb.currentIndex() == before_index)
    d.shot(view, f"{LANG}-03-pulldown-arrow-opened-with-right-key")

    # 04 Down twice into the revealed presets, Left goes back up to the arrow
    QTest.keyClick(view, Qt.Key.Key_Down)
    QTest.keyClick(view, Qt.Key.Key_Down)
    yield 400
    d.shot(view, f"{LANG}-04-pulldown-down-into-the-revealed-rows")
    QTest.keyClick(view, Qt.Key.Key_Left)
    yield 300
    check("Left on a revealed preset goes back to the arrow",
          view.currentIndex().row() == first_arrow)
    QTest.keyClick(view, Qt.Key.Key_Left)
    yield 500
    check("Left closes the group", cb.itemText(first_arrow).startswith("▸"))
    d.shot(view, f"{LANG}-05-pulldown-closed-with-left-key")
    QTest.keyClick(view, Qt.Key.Key_Return)
    yield 500
    check("Return opens it too, and the list stays open",
          cb.itemText(first_arrow).startswith("▾") and view.window().isVisible())
    QTest.keyClick(view, Qt.Key.Key_Return)
    yield 300
    cb.hidePopup()
    yield 500
    check("the arrow was never the selection",
          not str(cb.currentData() or "").startswith("__chromiq_more"))

    # 06-07 the Built-in presets list
    tab._open_builtin_preset_overlay()
    yield 900
    pop = tab._builtin_preset_popup
    for _ in range(80):
        QTest.keyClick(pop, Qt.Key.Key_Down)
        if pop._rows[pop._hover_index].kind == "more":
            break
    yield 500
    check("the list reaches its first arrow by keyboard",
          pop._rows[pop._hover_index].kind == "more",
          pop._rows[pop._hover_index].text)
    d.shot(pop, f"{LANG}-06-builtin-list-arrow-closed")
    d.note(f"   list before Right: visible={pop.isVisible()} "
           f"hover={pop._rows[pop._hover_index].text!r}")
    QTest.keyClick(pop, Qt.Key.Key_Right)
    yield 500
    d.note(f"   list after Right: visible={pop.isVisible()} "
           f"open={pop.is_open(group)} group={group!r} "
           f"groups-with-arrows={list(pop._more)}")
    check("Right opens it in the list", pop.is_open(group) and pop.isVisible())
    QTest.keyClick(pop, Qt.Key.Key_Down)
    yield 400
    d.shot(pop, f"{LANG}-07-builtin-list-arrow-opened")
    pop.close()
    yield 500

    # 08-09 the window behind the gear
    d.later(tab._preset_shown_btn.click)
    yield 1800
    dlg = d.top_dialog("BuiltinPresetsShownDialog")
    check("the gear opens the window", dlg is not None)
    if dlg is None:
        return
    rec["window_title"] = dlg.windowTitle()
    rec["window_intro"] = dlg._intro.text()
    d.shot(dlg, f"{LANG}-08-window")
    dlg.set_ticked(tick_key, True)
    dlg.set_ticked(untick_key, False)
    # show the changed row
    from ui.dialogs.builtin_presets_shown_dialog import _KEY_ROLE
    g = dlg._tree.topLevelItem(0)
    for i in range(g.childCount()):
        if g.child(i).data(0, _KEY_ROLE) == tick_key:
            dlg._tree.setCurrentItem(g.child(i))
            dlg._tree.scrollToItem(g.child(i))
    yield 600
    d.shot(dlg, f"{LANG}-09-window-one-ticked-one-cleared")
    dlg._close_btn.click()
    d._modal_closed()
    yield 1500

    ch = user_choices(d.settings)
    rec["stored_choice"] = ch
    check("Close stored exactly the two changes",
          ch == {tick_key: True, untick_key: False}, str(ch))
    row = cb.findData(tick_key)
    check("the ticked preset is now listed directly", not view.isRowHidden(row))
    cb.showPopup()
    yield 900
    view.setCurrentIndex(cb.model().index(row, 0))
    view.scrollTo(cb.model().index(row, 0),
                  QAbstractItemView.ScrollHint.PositionAtCenter)
    yield 500
    d.shot(view, f"{LANG}-10-pulldown-after-the-window")
    cb.hidePopup()
    yield 500
    d.settings.sync()


if __name__ == "__main__":
    drive = Drive(OUT, language=LANG, size=(1500, 1000))
    rc = drive.run(script)
    fails = [c for c in drive.record.get("checks", []) if not c["ok"]]
    print(f"checks: {len(drive.record.get('checks', []))}, failed: {len(fails)}")
    sys.exit(rc or (1 if fails else 0))
