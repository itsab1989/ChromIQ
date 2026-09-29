#!/usr/bin/env python3
"""K39-7 on screen: Export list and Import list in the gear window (Knut, #182
5831246553, beta 43, B8-1101 to B8-1104).

    python scripts/drive_k39_preset_list_export_import.py OUT_DIR en after
    CHROMIQ_TREE=<the tree before> python scripts/drive_k39_preset_list_export_import.py OUT_DIR en before

``after``: Create Chart > Manual > the gear. Tick one preset the window shows
unticked (an unsaved change) and press Export list; the file window must open
in the ChromIQ folder offering "ChromIQ built-in presets shown.csv", and is
accepted as offered. The written file is then READ BACK IN CODE (never in a
spreadsheet): its header, its 185 rows, the unsaved tick, and the script's
``--from-table`` reading it to the same ticks. An edited copy is written
(answers flipped, a key ChromIQ does not have, an empty answer, "maybe", one
row left out) and imported through Import list, whose file window must be
filtered to .csv; the summary is photographed and answered. Then Close: the
setting and the pulldown must be unchanged. Then the gear again, the same
import, and OK: the setting must hold exactly the imported differences and the
pulldown must list the newly ticked preset.

``before``: the tree before the change, the same window, photographed with its
two buttons.

**NOBODY HAS TO CLICK.** The drive answers its own file windows (the path is
typed into ChromIQ's own file dialog) and its own summary. A watchdog answers
anything else with No / Cancel / reject after a grace period (the drive's own
windows get eight seconds before it steps in), and a deadline ends the whole
run after four minutes.
"""
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

OUT, LANG, PHASE = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
DEADLINE_MS = 240_000
GRACE_S = 8.0

from userdrive import Drive                                   # noqa: E402

OURS = {"BuiltinPresetsShownDialog"}


def _install_watchdog(d) -> None:
    from PyQt6.QtCore import QObject, QTimer
    from PyQt6.QtWidgets import (
        QApplication, QDialog, QFileDialog, QMessageBox)

    class Watchdog(QObject):
        def __init__(self):
            super().__init__(QApplication.instance())
            self.n = 0
            self.seen: dict[int, float] = {}
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
                # Forget what was seen: a later window can get the same id().
                self.seen.clear()
                return
            # The drive's own file windows and the import summary are the
            # drive's to answer; they get a grace period before the watchdog
            # decides the drive is stuck on them.
            mine = isinstance(w, QFileDialog) or (
                w.objectName() == "builtin_presets_shown_message")
            first = self.seen.setdefault(id(w), time.monotonic())
            if mine and time.monotonic() - first < GRACE_S:
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
            for _ in range(4):
                w = QApplication.activeModalWidget()
                if w is not None:
                    w.done(99)
            QApplication.instance().quit()

    d._watchdog = Watchdog()


def _rows(path: Path) -> list[list[str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.reader(fh))


def script(d):
    from PyQt6.QtCore import QPoint
    from PyQt6.QtWidgets import QFileDialog, QLineEdit, QPushButton
    from core.i18n import tr
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
    from core.curated_presets import user_choices

    def open_window():
        d.later(tab._preset_shown_btn.click)
        yield 1800

    def dialog():
        return d.top_dialog("BuiltinPresetsShownDialog")

    def buttons_of(dlg):
        out = []
        for b in dlg.findChildren(QPushButton):
            if b.isVisibleTo(dlg):
                p = b.mapTo(dlg, QPoint(0, 0))
                out.append({"text": b.text(), "x": p.x(), "y": p.y(),
                            "w": b.width(), "default": b.isDefault()})
        return sorted(out, key=lambda b: b["x"])

    def pulldown_shot(key, name):
        """The pulldown open on `key`'s row, photographed; one retry, since
        the popup window is sometimes not yet on screen for the capture."""
        from PyQt6.QtWidgets import QAbstractItemView
        row = cb.findData(key)
        cb.showPopup()
        yield 900
        view.scrollTo(cb.model().index(row, 0),
                      QAbstractItemView.ScrollHint.PositionAtCenter)
        view.setCurrentIndex(cb.model().index(row, 0))
        yield 700
        if not d.shot(view, name):
            yield 1200
            d.shot(view, name)
        cb.hidePopup()
        yield 500

    def show_row(dlg, key):
        from ui.dialogs.builtin_presets_shown_dialog import _KEY_ROLE
        for c in dlg._items():
            if c.data(0, _KEY_ROLE) == key:
                dlg._tree.setCurrentItem(c)
                dlg._tree.scrollToItem(c)

    def file_dialog(within=6.0):
        end = time.monotonic() + within
        while time.monotonic() < end:
            d.pump(100)
            m = d.modal()
            if isinstance(m, QFileDialog) and m.isVisible():
                return m
        return None

    yield from open_window()
    dlg = dialog()
    check("the gear opens the window", dlg is not None)
    if dlg is None:
        return
    rec["window_intro"] = dlg._intro.text()
    rec["buttons"] = buttons_of(dlg)
    d.note(f"buttons: {rec['buttons']}")

    # ---------------------------------------------------------------- before
    if PHASE == "before":
        d.shot(dlg, f"{LANG}-before-01-window")
        check("BEFORE: only OK and Close",
              [b["text"] for b in rec["buttons"]] == [tr("OK"), tr("Close")],
              str(rec["buttons"]))
        dlg._close_btn.click()
        d._modal_closed()
        yield 1200
        return

    # ----------------------------------------------------------------- after
    b = rec["buttons"]
    check("four buttons: Export list, Import list at the left; OK, Close at "
          "the right",
          [x["text"] for x in b] == [tr("Export list"), tr("Import list"),
                                     tr("OK"), tr("Close")]
          and b[1]["x"] + b[1]["w"] < dlg.width() // 2 < b[2]["x"]
          and b[3]["default"] is False and b[2]["default"] is True,
          str(b))
    d.shot(dlg, f"{LANG}-after-01-window")

    from ui.dialogs.builtin_presets_shown_dialog import _KEY_ROLE
    import core.curated_presets as cp
    keys = [str(c.data(0, _KEY_ROLE)) for c in dlg._items()]
    opened = dlg.ticked()
    unsaved = next(k for k in keys if k not in opened
                   and "A3-180p" in cb.itemText(cb.findData(k)))
    dlg.set_ticked(unsaved, True)
    show_row(dlg, unsaved)
    rec["unsaved_tick"] = unsaved
    yield 500
    d.shot(dlg, f"{LANG}-after-02-one-unsaved-tick")

    # -------------------------------------------------------------- export
    root = Path(d.settings.get("custom_output_path"))
    d.later(dlg._export_btn.click)
    yield 1500          # the file window's exec() runs; this resumes inside it
    fd = file_dialog()
    check("Export list opens a file window", fd is not None)
    if fd is None:
        return
    d.pump(700)
    box = fd.findChild(QLineEdit, "fileNameEdit")
    info = {"dir": fd.directory().absolutePath(),
            "name_box": box.text() if box is not None else None,
            "title": fd.windowTitle(), "filters": fd.nameFilters()}
    rec["export_file_window"] = info
    check("it opens in the ChromIQ folder",
          Path(info["dir"]).resolve() == root.resolve(),
          f"{info['dir']} (ChromIQ folder {root})")
    check("it offers the name 'ChromIQ built-in presets shown.csv'",
          (info["name_box"] or "").endswith(cp.EXPORT_FILENAME),
          repr(info["name_box"]))
    check("it is filtered to .csv", info["filters"] == [tr("CSV files (*.csv)")],
          str(info["filters"]))
    d.shot(fd, f"{LANG}-after-03-export-file-window")
    fd.accept()
    d._modal_closed()
    yield 1200
    exported = root / cp.EXPORT_FILENAME
    check("the file is written where offered", exported.is_file(),
          str(exported))
    d.shot(dlg, f"{LANG}-after-04-exported-status-line")
    rec["status_after_export"] = dlg._status.text()

    # ------------------------------------------------ read it back in code
    rows = _rows(exported)
    rec["export_header"] = rows[0]
    rec["export_rows"] = len(rows) - 1
    yes = {r[4] for r in rows[1:] if r[2] == "yes"}
    no = {r[4] for r in rows[1:] if r[2] == "no"}
    rec["export_yes"], rec["export_no"] = len(yes), len(no)
    check("header is the --table header", rows[0] == cp.TABLE_HEADER,
          str(rows[0]))
    check("one row per built-in, every answer yes or no",
          len(rows) - 1 == len(keys) and len(yes) + len(no) == len(keys),
          f"{len(rows) - 1} rows, {len(yes)} yes, {len(no)} no")
    check("the UNSAVED tick is exported as yes", unsaved in yes)
    check("yes is exactly what the window shows", yes == dlg.ticked())
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import make_preset_defaults as mpd
    doc = mpd.from_table(exported)
    check("make_preset_defaults --from-table reads it to the same ticks",
          set(doc["shown"]) == dlg.ticked(),
          f"{len(doc['shown'])} shown")
    blank = OUT / "table-from-the-script.csv"
    mpd.write_table(blank)
    b_rows = _rows(blank)
    same = all((x[0], x[1], x[4]) == (y[0], y[1], y[4])
               for x, y in zip(b_rows[1:], rows[1:])) and \
        len(b_rows) == len(rows)
    check("same groups, names and keys, in the same order, as "
          "make_preset_defaults --table", same)
    (OUT / f"{LANG}-exported.csv").write_bytes(exported.read_bytes())

    # --------------------------------------------------- the edited copy
    yes_list = [r[4] for r in rows[1:] if r[2] == "yes"]
    no_list = [r[4] for r in rows[1:] if r[2] == "no"]
    flip_off = yes_list[:3]                   # yes -> no
    flip_on = no_list[:2]                     # no -> yes
    blank_key, maybe_key, dropped_key = yes_list[3], no_list[2], yes_list[4]
    edited = [rows[0]]
    for r in rows[1:]:
        r = list(r)
        if r[4] == dropped_key:
            continue
        if r[4] in flip_off:
            r[2] = "no"
            r[3] = "too many patches for me"
        elif r[4] in flip_on:
            r[2] = "YES"
        elif r[4] == blank_key:
            r[2] = ""
        elif r[4] == maybe_key:
            r[2] = "maybe"
        edited.append(r)
    edited.append(["Somebody's own", "A preset from a newer ChromIQ", "yes",
                   "", "__chromiq_from_the_future__"])
    edited_path = root / "edited list from a user.csv"
    with edited_path.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(edited)
    (OUT / f"{LANG}-edited.csv").write_bytes(edited_path.read_bytes())
    expected = (set(yes) - set(flip_off)) | set(flip_on)
    rec["edit"] = {"flip_off": flip_off, "flip_on": flip_on,
                   "blank": blank_key, "maybe": maybe_key,
                   "dropped": dropped_key}

    def do_import(tag):
        d.later(dlg_now()._import_btn.click)
        yield 1500      # the file window's exec() runs; this resumes inside it
        fd = file_dialog()
        check(f"[{tag}] Import list opens a file window", fd is not None)
        if fd is None:
            return False
        d.pump(700)
        filters = fd.nameFilters()
        rec.setdefault("import_file_window", []).append(
            {"dir": fd.directory().absolutePath(), "filters": filters})
        check(f"[{tag}] it opens in the ChromIQ folder, filtered to .csv",
              Path(fd.directory().absolutePath()).resolve() == root.resolve()
              and filters == [tr("CSV files (*.csv)")],
              f"{fd.directory().absolutePath()} {filters}")
        yield 200
        ok = d.answer_file(edited_path, name=f"{LANG}-after-{tag}-a-import-"
                           "file-window")
        check(f"[{tag}] the edited file is chosen", ok)
        yield 1200
        said = d.answer(tr("Back to the list"),
                        name=f"{LANG}-after-{tag}-b-import-summary")
        rec.setdefault("import_summary", []).append(said)
        n_yes = sum(1 for r in edited[1:]
                    if r[4] in keys and r[2].lower() == "yes")
        check(f"[{tag}] a summary came, with the counts and the problems",
              bool(said) and tr("Ticked: {count}").format(count=n_yes)
              in said and tr("Skipped: {count}").format(count=3) in said
              and "__chromiq_from_the_future__" in said
              and "maybe" in said, (said or "")[:400])
        yield 1200
        return True

    def dlg_now():
        return dialog()

    # ---------------------------------------------------- import + Close
    before_setting = d.settings.get("builtin_presets_shown")
    before_choices = user_choices(d.settings)
    r = yield from do_import("05")
    if not r:
        return
    dlg = dialog()
    got = dlg.ticked()
    check("[05] the window now shows the imported ticks; the empty, 'maybe' "
          "and left-out rows keep theirs",
          got == expected, f"diff {sorted(got ^ expected)[:6]}")
    show_row(dlg, flip_on[0])
    yield 500
    d.shot(dlg, f"{LANG}-after-05-c-window-after-import")
    rec["status_after_import"] = dlg._status.text()
    dlg._close_btn.click()
    d._modal_closed()
    yield 1500
    check("[05] Close: the setting is unchanged",
          d.settings.get("builtin_presets_shown") == before_setting
          and user_choices(d.settings) == before_choices,
          str(user_choices(d.settings)))
    check("[05] Close: the pulldown still hides a preset the import ticked",
          view.isRowHidden(cb.findData(flip_on[0])))
    yield from pulldown_shot(flip_off[0],
                             f"{LANG}-after-05-d-pulldown-after-close")

    # ------------------------------------------------------- import + OK
    yield from open_window()
    dlg = dialog()
    check("[06] the gear opens again, with the unsaved tick gone",
          dlg is not None and unsaved not in dlg.ticked())
    r = yield from do_import("06")
    if not r:
        return
    dlg = dialog()
    # the exported file carried the unsaved tick; the edited copy kept it
    want = expected
    check("[06] the window shows the imported ticks", dlg.ticked() == want)
    dlg._ok_btn.click()
    d._modal_closed()
    yield 1500
    stored = user_choices(d.settings)
    want_stored = cp.choices_to_store(want, keys, {})
    rec["stored_after_ok"] = stored
    check("[06] OK: the setting holds exactly the imported differences",
          stored == want_stored, f"{len(stored)} stored")
    check("[06] OK: the pulldown lists a preset the import ticked",
          not view.isRowHidden(cb.findData(flip_on[0])))
    check("[06] OK: the pulldown hides a preset the import cleared",
          view.isRowHidden(cb.findData(flip_off[0])))
    yield from pulldown_shot(flip_on[0], f"{LANG}-after-07-pulldown-after-ok")
    d.settings.sync()


if __name__ == "__main__":
    drive = Drive(OUT, language=LANG, size=(1500, 1000))
    rc = drive.run(script)
    fails = [c for c in drive.record.get("checks", []) if not c["ok"]]
    print(f"checks: {len(drive.record.get('checks', []))}, failed: {len(fails)}")
    sys.exit(rc or (1 if fails else 0))
