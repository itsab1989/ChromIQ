#!/usr/bin/env python3
"""K41 on screen: the paper filter in the gear window (Knut, #182 5832303551,
beta 43, B8-1131 to B8-1134).

    python scripts/drive_k41_preset_paper_filter.py OUT_DIR en
    python scripts/drive_k41_preset_paper_filter.py OUT_DIR de

Create Chart. With the filter OFF: "Select preset" and the Built-in presets
list on Manual A4. The gear: the new box, ticked and CLOSED (nothing stored),
then ticked and OK (stored). With it ON: Manual A4, Manual A3 Portrait, Manual
A3 Landscape, Manual Custom (100 x 150 mm), Guided A4, Guided A3 Landscape;
each time the pulldown (Manual) and the Built-in presets list are photographed
and what they list is recorded and checked: only the selected paper, the
Scanner group always, no heading over an empty group, the arrow counting what
it still holds, and the person's own presets by their stored paper (one A4,
one with no paper, both put in the sandboxed presets folder first).

**NOBODY HAS TO CLICK.** Every window the drive opens it closes itself; a
watchdog answers anything else (the auto-update-preview question included)
with No / Cancel / reject after a grace period, and a deadline ends the whole
run after four minutes.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

OUT, LANG = Path(sys.argv[1]), sys.argv[2]
DEADLINE_MS = 240_000
GRACE_S = 8.0

MY_A4 = "My A4 preset (driver)"
MY_NO_PAPER = "My preset without a paper (driver)"


def _seed_user_presets() -> None:
    """Two presets of the person's own, in the SANDBOXED presets folder (the
    Drive has not set the variable yet, so it is set here the same way)."""
    import os
    sb = OUT.resolve() / "sandbox"
    os.environ.setdefault("CHROMIQ_SETTINGS_FILE", str(sb / "settings.ini"))
    os.environ.setdefault("CHROMIQ_PRESETS_DIR", str(sb / "presets"))
    folder = Path(os.environ["CHROMIQ_PRESETS_DIR"]) / "Create Chart"
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in ((MY_A4, {"printtarg_-p": "A4"}),
                       (MY_NO_PAPER, {"auto_run": False})):
        (folder / (name + ".json")).write_text(json.dumps({
            "chromiq_preset_version": 1, "tab": "create_chart",
            "name": name, "data": data}), encoding="utf-8")


_seed_user_presets()
from userdrive import Drive                                   # noqa: E402

OURS = {"BuiltinPresetsShownDialog"}


def _install_watchdog(d) -> None:
    from PyQt6.QtCore import QObject, QTimer
    from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

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
            if w is None or not w.isVisible():
                self.seen.clear()
                return
            first = self.seen.setdefault(id(w), time.monotonic())
            if type(w).__name__ in OURS \
                    and time.monotonic() - first < GRACE_S:
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


def script(d):
    import core.curated_presets as cp
    from data.patch_db import PAPER_LABELS
    from ui.tabs.tab_chart import (
        BUILTIN_PRESET_GROUPS, BUILTIN_PRESET_KEYS, builtin_preset_paper)
    rec = d.record
    rec.update({"language": LANG, "checks": [], "scenes": {}})
    # The Scanner checks below describe K41's rule (Scanner never filtered),
    # which Knut withdrew on 2026-09-25 (#182 5840692243); see
    # scripts/drive_b8_1221_paper_filter_matrix.py for the rule since.
    scanner = next(h for h, _e in BUILTIN_PRESET_GROUPS if h == "Scanner")
    headings = [h for h, _e in BUILTIN_PRESET_GROUPS]

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

    def listed():
        return [(cb.itemText(r), cb.itemData(r)) for r in range(cb.count())
                if not view.isRowHidden(r)]

    def pulldown_shot(name):
        cb.showPopup()
        yield 900
        view.scrollToTop()
        yield 500
        if not d.shot(view, name):
            yield 1200
            d.shot(view, name)
        cb.hidePopup()
        yield 500

    def overlay_shot(name):
        tab._open_builtin_preset_overlay()
        yield 1000
        pop = tab._builtin_preset_popup
        groups = [(h, [k for _l, k in e]) for h, e in pop._groups]
        more = {h: [k for _l, k in e] for h, e in pop._more.items()}
        for _try in range(4):          # a popup is sometimes not painted yet
            if d.shot(pop, name):
                break
            pop.update()
            yield 1500
        pop.close()
        yield 500
        return groups, more

    def judge(scene, paper, mode, groups, more, pulldown=None):
        """Check what one scene lists against the rule, and record it."""
        want = cp.paper_class(paper)
        rec["scenes"][scene] = {
            "mode": mode, "paper": paper, "filtered_to": want,
            "overlay_groups": [h for h, _k in groups],
            "overlay_counts": {h: [len(k), len(more.get(h, []))]
                               for h, k in groups},
        }
        wrong = [k for h, ks in groups for k in ks + more.get(h, [])
                 if h != scanner and cp.paper_class(builtin_preset_paper(k))
                 != want]
        check(f"[{scene}] the Built-in presets list holds only {want}",
              not wrong, f"{len(wrong)} on another paper")
        check(f"[{scene}] the Scanner group is listed",
              scanner in [h for h, _k in groups])
        expected = [h for h, e in BUILTIN_PRESET_GROUPS
                    if h == scanner or any(
                        cp.paper_class(builtin_preset_paper(k)) == want
                        for _c, _o, k in e)]
        check(f"[{scene}] exactly the groups with a preset on it",
              [h for h, _k in groups] == expected,
              f"{[h for h, _k in groups]}")
        if pulldown is not None:
            texts = [t for t, _d in pulldown]
            keys = {dd for _t, dd in pulldown if isinstance(dd, str)}
            rec["scenes"][scene]["pulldown"] = texts
            shown_h = [h for h in headings if h in texts]
            check(f"[{scene}] the pulldown shows the same headings",
                  shown_h == expected, f"{shown_h}")
            check(f"[{scene}] the pulldown lists no built-in on another paper",
                  all(cp.paper_class(builtin_preset_paper(k)) == want
                      or k in {kk for _c, _o, kk in dict(
                          BUILTIN_PRESET_GROUPS)[scanner]}
                      for k in keys & BUILTIN_PRESET_KEYS))
            check(f"[{scene}] the person's preset without a paper is listed",
                  MY_NO_PAPER in keys)
            check(f"[{scene}] the person's A4 preset is listed only on A4",
                  (MY_A4 in keys) == (want == "A4"))

    def set_manual(code):
        tab._switch_mode("manual")
        tab._set_manual_value("printtarg", "-p", code)

    def set_guided(code):
        tab._switch_mode("guided")
        i = tab._paper_combo.findData(code)
        tab._paper_combo.setCurrentIndex(i)
        return i >= 0

    # ------------------------------------------------ OFF
    set_manual("A4")
    yield 1200
    full = listed()
    yield from pulldown_shot(f"{LANG}-01-off-manual-A4-select-preset")
    groups, more = yield from overlay_shot(
        f"{LANG}-02-off-manual-A4-builtin-presets")
    check("[off] the Built-in presets list shows every group",
          [h for h, _k in groups] == headings)
    set_manual("420x297")
    yield 1200
    check("[off] the pulldown does not move when the paper does",
          listed() == full)
    rec["scenes"]["off"] = {"pulldown": [t for t, _d in full],
                            "overlay_groups": [h for h, _k in groups]}

    # ------------------------------------------------ the box: Close, then OK
    def open_gear():
        d.later(tab._preset_shown_btn.click)
        yield 1800
        return d.top_dialog("BuiltinPresetsShownDialog")

    dlg = yield from open_gear()
    check("the gear opens the window", dlg is not None)
    if dlg is None:
        return
    box = dlg._paper_filter
    rec["box_text"] = box.text()
    rec["box_tooltip"] = box.toolTip()
    check("the box is there, unticked", box.isVisible() and not box.isChecked(),
          repr(box.text()))
    dlg._tree.scrollToBottom()
    d.shot(dlg, f"{LANG}-03-window-box-unticked")
    box.setChecked(True)
    yield 400
    if not d.shot(dlg, f"{LANG}-04-window-box-ticked"):
        yield 1200
        d.shot(dlg, f"{LANG}-04-window-box-ticked")
    dlg._close_btn.click()
    d._modal_closed()
    yield 1200
    check("Close: the box is not stored", not cp.paper_filter_on(d.settings))
    check("Close: the pulldown is unchanged", listed() == full)

    dlg = yield from open_gear()
    if dlg is None:
        return
    check("the box opens unticked again after Close",
          not dlg._paper_filter.isChecked())
    dlg._paper_filter.setChecked(True)
    dlg._ok_btn.click()
    d._modal_closed()
    yield 1200
    check("OK: the box is stored", cp.paper_filter_on(d.settings))

    # ------------------------------------------------ ON, Manual
    n = 5
    for code, tag in (("A4", "A4"), ("A3", "A3-portrait"),
                      ("420x297", "A3-landscape"),
                      ("100x150", "custom-100x150")):
        set_manual(code)
        yield 1500
        pd = listed()
        yield from pulldown_shot(f"{LANG}-{n:02d}-on-manual-{tag}-select-preset")
        n += 1
        groups, more = yield from overlay_shot(
            f"{LANG}-{n:02d}-on-manual-{tag}-builtin-presets")
        n += 1
        judge(f"manual {code}", code, "manual", groups, more, pd)
    check("[manual custom] the Paper field shows Custom",
          tab._manual_paper_pw._custom_combo.currentData() == "custom")
    photo = [k for k in BUILTIN_PRESET_KEYS
             if builtin_preset_paper(k) not in PAPER_LABELS]
    check("[manual custom] every custom-size built-in is in the pulldown, "
          "ticked listed or under its arrow",
          all(cb.findData(k) >= 0 for k in photo), f"{len(photo)}")

    # ------------------------------------------------ ON, Guided
    for code, tag in (("A4", "A4"), ("420x297", "A3-landscape")):
        ok = set_guided(code)
        yield 1500
        check(f"[guided] Paper size set to {code}", ok)
        pd = listed()
        groups, more = yield from overlay_shot(
            f"{LANG}-{n:02d}-on-guided-{tag}-builtin-presets")
        n += 1
        d.shot(tab, f"{LANG}-{n:02d}-on-guided-{tag}-window")
        n += 1
        judge(f"guided {code}", code, "guided", groups, more, pd)

    # Back to OFF so the sandbox ends as it began.
    tab._switch_mode("manual")
    d.settings.set(cp.PAPER_FILTER_KEY, False)
    d.settings.sync()


if __name__ == "__main__":
    drive = Drive(OUT, language=LANG, size=(1500, 1000))
    rc = drive.run(script)
    fails = [c for c in drive.record.get("checks", []) if not c["ok"]]
    print(f"checks: {len(drive.record.get('checks', []))}, failed: {len(fails)}")
    sys.exit(rc or (1 if fails else 0))
