#!/usr/bin/env python3
"""B8-1097 on screen: the gear window's OK and Close (Basti, 2026-09-25).

    python scripts/drive_b8_1097_presets_ok_close.py OUT_DIR en after
    CHROMIQ_TREE=<the tree before> python scripts/drive_b8_1097_presets_ok_close.py OUT_DIR en before

``after`` opens the window behind the gear in Create Chart > Manual > Presets
five times, each time ticking one preset and clearing another, and ends it
five ways: the Close button, Escape, the window's close box (a close event,
which is what that box sends), Return (OK is the default button) and the OK
button. After each it reads the stored setting and the pulldown. The first
three must store nothing; the last two must store the change. It also records
where OK and Close sit in the window, and which button layout the app's style
asks for.

``before`` does the same first ending (the Close button) on the tree before
the change, where Close stored the ticks (Knut's K35 rule), and photographs the
window with its single button.

**NOBODY HAS TO CLICK.** A watchdog answers every other question the app asks
with its No / Cancel / reject button, records and photographs it, and a second
timer ends the whole run after four minutes whatever happens. Keys are QTest
key events delivered to the list, because macOS does not let a process it never
activated take the keyboard focus.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

OUT, LANG, PHASE = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
DEADLINE_MS = 240_000

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
            # the gear window's own exec() must end too
            w = QApplication.activeModalWidget()
            if w is not None:
                w.done(99)
            QApplication.instance().quit()

    d._watchdog = Watchdog()


def script(d):
    from PyQt6.QtCore import QPoint, Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import (
        QAbstractItemView, QApplication, QPushButton, QStyle)
    rec = d.record
    rec.update({"language": LANG, "phase": PHASE, "checks": [], "endings": []})

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
    from core.curated_presets import user_choices
    style = QApplication.style()
    rec["app_style"] = type(style).__name__ + " / " + style.name()
    rec["SH_DialogButtonLayout"] = style.styleHint(
        QStyle.StyleHint.SH_DialogButtonLayout)
    d.note(f"app style {rec['app_style']}, SH_DialogButtonLayout "
           f"{rec['SH_DialogButtonLayout']} (0 = Windows order)")

    arrows = [r for r in range(cb.count()) if cb.itemData(r, cb.MORE_ROLE)]
    first_arrow = arrows[0]
    tick_key = next(cb.itemData(r) for r in range(1, cb.count())
                    if "A3-180p" in cb.itemText(r))
    untick_key = cb.itemData(first_arrow - 1)
    rec["tick_key"], rec["untick_key"] = tick_key, untick_key

    def open_window():
        d.later(tab._preset_shown_btn.click)
        yield 1800

    def dialog():
        return d.top_dialog("BuiltinPresetsShownDialog")

    def show_row(dlg, key):
        from ui.dialogs.builtin_presets_shown_dialog import _KEY_ROLE
        for gi in range(dlg._tree.topLevelItemCount()):
            g = dlg._tree.topLevelItem(gi)
            for i in range(g.childCount()):
                if g.child(i).data(0, _KEY_ROLE) == key:
                    dlg._tree.setCurrentItem(g.child(i))
                    dlg._tree.scrollToItem(g.child(i))

    def pulldown_shot(name):
        row = cb.findData(tick_key)
        cb.showPopup()
        yield 900
        target = row if not view.isRowHidden(row) else first_arrow
        view.scrollTo(cb.model().index(target, 0),
                      QAbstractItemView.ScrollHint.PositionAtCenter)
        view.setCurrentIndex(cb.model().index(target, 0))
        yield 500
        d.shot(view, name)
        cb.hidePopup()
        yield 500

    def buttons_of(dlg):
        out = []
        for b in dlg.findChildren(QPushButton):
            if b.isVisibleTo(dlg):
                p = b.mapTo(dlg, QPoint(0, 0))
                out.append({"text": b.text(), "x": p.x(), "y": p.y(),
                            "w": b.width(), "h": b.height(),
                            "default": b.isDefault()})
        return sorted(out, key=lambda b: b["x"])

    # ---------------------------------------------------------------- before
    if PHASE == "before":
        yield from open_window()
        dlg = dialog()
        check("the gear opens the window", dlg is not None)
        if dlg is None:
            return
        rec["window_intro"] = dlg._intro.text()
        rec["buttons"] = buttons_of(dlg)
        d.note(f"buttons: {rec['buttons']}")
        d.shot(dlg, f"{LANG}-before-01-window")
        dlg.set_ticked(tick_key, True)
        dlg.set_ticked(untick_key, False)
        show_row(dlg, tick_key)
        yield 600
        d.shot(dlg, f"{LANG}-before-02-one-ticked-one-cleared")
        dlg._close_btn.click()
        d._modal_closed()
        yield 1500
        ch = user_choices(d.settings)
        rec["endings"].append({"ending": "Close button", "stored": ch})
        check("BEFORE: the Close button STORED the two changes (Knut's K35)",
              ch == {tick_key: True, untick_key: False}, str(ch))
        yield from pulldown_shot(f"{LANG}-before-03-pulldown-after-close")
        d.settings.sync()
        return

    # ----------------------------------------------------------------- after
    endings = [("close", "Close button", False), ("escape", "Escape", False),
               ("closebox", "the close box", False),
               ("return", "Return (OK is the default)", True),
               ("ok", "OK button", True)]
    n = 0
    for code, label, applies in endings:
        n += 1
        # Every discarding ending starts from the shipped list (nothing
        # stored), so a change that leaks through shows up as one.
        before_ch = user_choices(d.settings)
        yield from open_window()
        dlg = dialog()
        check(f"[{label}] the gear opens the window", dlg is not None)
        if dlg is None:
            return
        if n == 1:
            rec["window_intro"] = dlg._intro.text()
            rec["buttons"] = buttons_of(dlg)
            d.note(f"buttons: {rec['buttons']}")
            b = rec["buttons"]
            from core.i18n import tr
            check("two buttons, OK left of Close",
                  [x["text"] for x in b] == [tr("OK"), tr("Close")], str(b))
            check("OK is the default button",
                  b[0]["default"] and not b[1]["default"], str(b))
            right_gap = dlg.width() - (b[-1]["x"] + b[-1]["w"])
            rec["close_right_gap_px"] = right_gap
            check("the pair sits at the bottom right",
                  b[0]["x"] > dlg.width() // 2 and right_gap <= 24
                  and b[0]["y"] > dlg._tree.geometry().bottom(),
                  f"window {dlg.width()}x{dlg.height()}, gap {right_gap}")
            d.shot(dlg, f"{LANG}-after-01-window")
        # the change: one ticked, one cleared, relative to what is shown now
        want = {tick_key: True, untick_key: False}
        if code == "ok":
            # Return already stored `want`; OK stores the reverse, back to
            # the shipped list, which must then leave nothing stored.
            want = {tick_key: False, untick_key: True}
        for k, v in want.items():
            dlg.set_ticked(k, v)
        show_row(dlg, tick_key)
        yield 500
        if n in (1, 5):
            d.shot(dlg, f"{LANG}-after-{n + 1:02d}-changed-before-{code}")
        if code == "close":
            dlg._close_btn.click()
        elif code == "ok":
            dlg._ok_btn.click()
        elif code == "escape":
            QTest.keyClick(dlg._tree, Qt.Key.Key_Escape)
        elif code == "return":
            dlg._tree.setFocus()
            QTest.keyClick(dlg._tree, Qt.Key.Key_Return)
        elif code == "closebox":
            dlg.close()
        d._modal_closed()
        yield 1500
        still_open = dialog() is not None
        check(f"[{label}] the window closed", not still_open)
        if still_open:
            dialog().done(0)
            d._modal_closed()
            yield 1000
        ch = user_choices(d.settings)
        rec["endings"].append({"ending": label, "stored_before": before_ch,
                               "stored_after": ch})
        if applies and code == "return":
            check(f"[{label}] stored the change",
                  ch == {tick_key: True, untick_key: False}, str(ch))
        elif applies:
            check(f"[{label}] stored the change (back to the shipped list, "
                  f"so nothing is left stored)", ch == {}, str(ch))
        else:
            check(f"[{label}] stored NOTHING", ch == before_ch == {}, str(ch))
        listed = not view.isRowHidden(cb.findData(tick_key))
        check(f"[{label}] the pulldown "
              + ("lists" if (applies and code == "return") else "does not list")
              + " the ticked preset directly",
              listed == (applies and code == "return"))
        if code in ("close", "return", "ok"):
            yield from pulldown_shot(
                f"{LANG}-after-{10 + n:02d}-pulldown-after-{code}")
    d.settings.sync()


if __name__ == "__main__":
    drive = Drive(OUT, language=LANG, size=(1500, 1000))
    rc = drive.run(script)
    fails = [c for c in drive.record.get("checks", []) if not c["ok"]]
    print(f"checks: {len(drive.record.get('checks', []))}, failed: {len(fails)}")
    sys.exit(rc or (1 if fails else 0))
