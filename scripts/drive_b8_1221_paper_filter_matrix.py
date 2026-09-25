#!/usr/bin/env python3
"""B8-1221: the paper filter's MATRIX, on screen (Knut, #182 5838170697 to
5838625234, beta 43).

    python scripts/drive_b8_1221_paper_filter_matrix.py OUT LANG PHASE [ENGINE [SANDBOX]]

PHASE ``fresh`` starts from a new sandbox that mimics Knut's settings
(ColorMunki, Manual, the ChromIQ layout engine ON, helper markers saved, the
paper filter at its default ON, the shipped ticks, a copy of a presets folder
with a person's own presets); ``restart`` starts the app again on the sandbox
the ``fresh`` phase left behind (after its "Save as Defaults"). ENGINE is
``on`` (Knut's setting, the default) or ``off`` (printtarg's own Paper field).

After EVERY step the driver reads what both lists hold, "Select preset" (the
rows not hidden) and the Built-in presets list (the popup's groups and the
rows under its arrows), and judges them against the rule of
docs/design/curated_presets.md C7, computed from the paper THE PERSON SEES:
the Paper field of the mode on screen (Guided's "Paper size"; Manual's
"Paper", which is the ChromIQ layout panel's when the engine is on). Every
step is a row of the matrix in ``OUT/matrix.json``.

Knut's four cases are photographed: the pulldown open and the Built-in presets
list open, by window id.

**NOBODY HAS TO CLICK.** A watchdog answers every modal the drive did not
open itself: a name question is accepted with the name the app offers (so a
preset really is applied, as a person pressing Return does), any other
question gets No / Cancel. A deadline ends the run.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

OUT = Path(sys.argv[1]).resolve()
LANG = sys.argv[2]
PHASE = sys.argv[3]
ENGINE = (sys.argv[4] if len(sys.argv) > 4 else "on") == "on"
DEADLINE_MS = 900_000
GRACE_S = 6.0
SRC = Path.home() / "Desktop" / "ChromIQ-beta44-proof" / "paper-filter-matrix" / "demo-src"
PROJECT = "Report-Limits-Threshold-Series"

#: The sandbox: a restart runs on the one a "fresh" run left (argv 5).
SB = Path(sys.argv[5]).resolve() if len(sys.argv) > 5 else OUT / "sandbox"
os.environ["CHROMIQ_SETTINGS_FILE"] = str(SB / "settings.ini")
os.environ["CHROMIQ_PRESETS_DIR"] = str(SB / "presets")
os.environ["CHROMIQ_DEMO_PACK"] = str(SRC)


def _seed_knut_like_sandbox() -> None:
    """A new sandbox shaped like Knut's: his instrument, Manual, the layout
    engine, his saved helper markers, the filter at its default (not written:
    a person who never touched the box has it ON), the shipped ticks, and a
    presets folder with a person's own presets (a READ-ONLY copy of Basti's
    two and the demo pack's verification presets)."""
    if SB.exists():
        shutil.rmtree(SB)
    folder = SB / "presets" / "Create Chart"
    folder.mkdir(parents=True)
    real = Path.home() / "Library/Preferences/ChromIQ/presets/presets/Create Chart"
    for src in [*real.glob("*.json"),
                *(SRC / "Create Chart presets (verification demos)").glob("*")]:
        if src.suffix in (".json", ".ti1"):
            shutil.copy2(src, folder / src.name)
    from core.settings import AppSettings
    s = AppSettings()
    for k, v in {
        "chart_instrument": "CM", "chart_paper": "A4", "chart_mode": "manual",
        "use_chromiq_layout_engine": ENGINE,
        "manual_printtarg_-i_l": "CM",
        "helper_markers_show": True, "helper_marker_edge_mm": 4.0,
        "helper_marker_len_mm": 2.0, "helper_marker_per_patch": 5,
        "helper_markers_top_bottom": True, "helper_markers_sides": False,
        "restore_last_session": False, "restore_last_tab": False,
        "update_notify": False, "show_splash": False,
        "confirm_before_printing": True,
    }.items():
        s.set(k, v)
    s.sync()


if PHASE in ("fresh", "knutstart"):
    _seed_knut_like_sandbox()
if PHASE == "knutstart":
    # KNUT'S START (his log: the panel is seeded from a saved
    # `manual_engine_recipe` at start-up, `_init_manual_layout_panel`'s first
    # branch). The recipe says A4; printtarg's own Paper value, which the
    # engine hides, says A3 Landscape, as a "Save as Defaults" taken while the
    # two disagreed leaves them.
    from core.settings import AppSettings
    from workflow.layout_engine.presets import default_recipe
    _s = AppSettings()
    _s.set("manual_engine_recipe", default_recipe("CM", "A4").to_dict())
    _s.set("manual_printtarg_-p_l", "420x297")
    _s.sync()

from userdrive import Drive                                   # noqa: E402

OURS = {"BuiltinPresetsShownDialog"}
#: Judge by Knut's workaround rule (#182 5839418461, B8-1227): a group with
#: presets on the paper and none ticked lists them directly. B8_1227=0 (the
#: default since K48, #182 5840677938, which withdrew that rule: such a group
#: shows its heading and "N more presets") judges by C7.
RULE_1227 = os.environ.get("B8_1227", "0") == "1"
#: The groups the paper filter never hides. Scanner was one until Knut's ruling
#: of 2026-09-25 (#182 5840692243); B8_SCANNER_ALWAYS=1 judges by the old rule.
PAPER_FILTER_ALWAYS_SHOWN = frozenset(
    {"Scanner"} if os.environ.get("B8_SCANNER_ALWAYS", "0") == "1" else ())


def _install_watchdog(d) -> None:
    from PyQt6.QtCore import QObject, QTimer
    from PyQt6.QtWidgets import (QApplication, QDialog, QInputDialog,
                                 QMessageBox)

    class Watchdog(QObject):
        def __init__(self):
            super().__init__(QApplication.instance())
            self.n = 0
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
            if type(w).__name__ in OURS \
                    and time.monotonic() - first < GRACE_S:
                return
            if time.monotonic() - first < 0.8:
                return
            self.n += 1
            text = d.modal_text(w)
            clicked = "(reject)"
            if isinstance(w, QInputDialog):
                clicked = "(accept the offered name)"
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
                # A name dialog of the app's own (not a QInputDialog): accept
                # it when it has a name box, the way Return does.
                from PyQt6.QtWidgets import QLineEdit
                box = w.findChild(QLineEdit)
                if box is not None and any(
                        s in (w.windowTitle() or "").lower()
                        for s in ("name", "chart", "preset")):
                    if not box.text().strip():
                        box.setText(f"Matrix drive {self.n}")
                    clicked = f"(typed {box.text()!r}, accept)"
                    w.accept()
                else:
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
    from ui.tabs.tab_chart import (
        BUILTIN_PRESET_GROUPS, BUILTIN_PRESET_KEYS, builtin_preset_paper)
    rec = d.record
    rec.update({"language": LANG, "phase": PHASE, "engine": ENGINE,
                "matrix": []})
    _install_watchdog(d)
    d.goto_tab("chart")
    yield 1500
    tab = d.win._tab_chart
    cb = tab._preset_combo
    view = cb.view()
    group_of = {k: h for h, es in BUILTIN_PRESET_GROUPS for *_x, k in es}
    shots = d.shots

    # ------------------------------------------------------------ reading
    def on_screen_paper() -> tuple[str, str, str]:
        """(mode, the Paper field's code, the text it shows) as the person
        sees it, read from the widget that is VISIBLE, never from the one the
        filter reads."""
        mode = tab._mode_name()
        if mode == "guided":
            c = tab._paper_combo
            return mode, str(c.currentData() or ""), c.currentText()
        panel = tab._manual_layout_panel
        if panel is not None and panel.paper is not None \
                and panel.paper.isVisible():
            code = panel.selection()[1]
            return mode, code, panel.paper.currentText()
        pw = tab._manual_paper_pw
        return mode, str(pw.get_raw_value() or ""), \
            pw._custom_combo.currentText()

    def expected(sel: str, current_key):
        shown = cp.shown_keys(d.settings, BUILTIN_PRESET_KEYS)
        on = cp.paper_filter_on(d.settings)
        exp = []
        for h, es in BUILTIN_PRESET_GROUPS:
            keys = [k for *_x, k in es]
            if on and h not in PAPER_FILTER_ALWAYS_SHOWN:
                keys = [k for k in keys
                        if cp.paper_matches(builtin_preset_paper(k), sel)]
            if keys:
                top = [k for k in keys if k in shown]
                rest = [k for k in keys if k not in shown]
                if on and RULE_1227 and not top \
                        and h not in PAPER_FILTER_ALWAYS_SHOWN:
                    # Knut's workaround rule (#182 5839418461, B8-1227)
                    top, rest = rest, []
                exp.append((h, top, rest))
        return on, exp

    def read_combo():
        """Headings shown, and per group the ticked keys listed and the
        number its arrow says."""
        groups: dict[str, dict] = {}
        headings = []
        for r in range(cb.count()):
            if view.isRowHidden(r):
                continue
            data = cb.itemData(r)
            grp = cb.itemData(r, cb.GROUP_ROLE)
            if not grp:
                continue
            g = groups.setdefault(grp, {"listed": [], "arrow": None})
            if cb.itemData(r, cb.MORE_ROLE):
                g["arrow"] = cb.itemData(r, Qt.ItemDataRole.UserRole + 44)
            elif data is None and cb.itemText(r) == grp:
                headings.append(grp)
            elif isinstance(data, str) and not cb.itemData(r, cb.MEMBER_ROLE):
                g["listed"].append(data)
            elif isinstance(data, str):
                g.setdefault("members", []).append(data)
        # A group with no arrow shown lists its visible members directly
        # (B8-1227: none of its presets on the paper ticked).
        for g in groups.values():
            if g["arrow"] is None:
                g["listed"] += g.pop("members", [])
        return headings, groups

    def read_popup():
        tab._open_builtin_preset_overlay()
        pop = tab._builtin_preset_popup
        groups = [(h, [k for _l, k in e], [k for _l, k in
                                             pop._more.get(h, [])])
                  for h, e in pop._groups]
        return pop, groups

    def judge(step: str, photo: str | None = None):
        mode, code, text = on_screen_paper()
        sel = cp.paper_class(code)
        cur = cb.currentData()
        cur_key = cur if isinstance(cur, str) and cur in BUILTIN_PRESET_KEYS \
            else None
        on, exp = expected(sel, cur_key)
        exp_heads = [h for h, _t, _r in exp]
        if cur_key and group_of.get(cur_key) not in exp_heads:
            # C7: the selected preset stays listed in its group, with heading
            exp_heads = [h for h, *_ in BUILTIN_PRESET_GROUPS
                         if h in exp_heads or h == group_of[cur_key]]
        # The group the selected preset is in keeps it (C7): off its paper
        # it is one more row, ticked or under the arrow.
        cur_off = bool(cur_key) and on and group_of[cur_key] \
            not in PAPER_FILTER_ALWAYS_SHOWN and not cp.paper_matches(
                builtin_preset_paper(cur_key), sel)
        cur_member = cur_off and cur_key not in cp.shown_keys(
            d.settings, BUILTIN_PRESET_KEYS)
        exp_full = list(exp)
        if cur_off and group_of[cur_key] not in [h for h, *_ in exp]:
            exp_full = [(h, t, r) for h, t, r in exp] + [
                (group_of[cur_key], [], [])]

        def combo_problems(label, heads, cgroups):
            out = []
            if heads != exp_heads:
                out.append(f"{label} headings {heads} != {exp_heads}")
            for h, top, rest in exp_full:
                got = cgroups.get(h, {"listed": [], "arrow": None})
                got_top = [k for k in got["listed"] if k != cur_key]
                if sorted(got_top) != sorted(k for k in top if k != cur_key):
                    out.append(f"{label} {h}: ticked {len(got_top)} != "
                               f"{len([k for k in top if k != cur_key])}")
                n = len(rest) + (1 if cur_member and h == group_of[cur_key]
                                 else 0)
                if (got["arrow"] or None) != (n or None):
                    out.append(f"{label} {h}: arrow {got['arrow']} != "
                               f"{n or None}")
            return out

        # CLOSED first (what Up, Down and the wheel step through), then
        # OPEN, which is what a person sees.
        c_heads, c_groups = read_combo()
        problems = combo_problems("closed pulldown", c_heads, c_groups)
        cb.showPopup()
        d.pump(350)
        heads, cgroups = read_combo()
        cb.hidePopup()
        d.pump(150)
        problems += combo_problems("pulldown", heads, cgroups)
        pop, pgroups = read_popup()
        p_heads = [h for h, _t, _r in pgroups]
        if p_heads != [h for h, _t, _r in exp]:
            problems.append(f"popup headings {p_heads} != "
                            f"{[h for h, _t, _r in exp]}")
        for (h, top, rest) in exp:
            got = next((g for g in pgroups if g[0] == h), None)
            if got is None:
                continue
            if sorted(got[1]) != sorted(top) or sorted(got[2]) != sorted(rest):
                problems.append(f"popup {h}: {len(got[1])}+{len(got[2])} != "
                                f"{len(top)}+{len(rest)}")
        row = {
            "step": step, "mode": mode, "paper_shown": text,
            "paper_code": code, "filter": on,
            "filter_reads": tab._preset_paper_selected(),
            "manual_printtarg_p": str(tab._manual_paper_pw.get_raw_value()),
            "guided_paper": str(tab._paper_combo.currentData()),
            "engine_panel_paper": (tab._manual_layout_panel.selection()[1]
                                   if tab._manual_layout_panel is not None
                                   else None),
            "project": bool(tab._file_mgr.has_project()),
            "current_preset": cb.currentText(),
            "expected_groups": exp_heads,
            "pulldown_groups": heads,
            "popup_groups": p_heads,
            "pulldown_counts": {h: [len(g["listed"]), g["arrow"]]
                                for h, g in cgroups.items()},
            "popup_counts": {h: [len(t), len(r)] for h, t, r in pgroups},
            "ok": not problems, "problems": problems,
        }
        rec["matrix"].append(row)
        d.note(f"{'OK  ' if not problems else 'FAIL'} [{step}] {mode} "
               f"{text!r} ({code}) filter={'on' if on else 'off'} reads "
               f"{row['filter_reads']!r}; pulldown {heads}; popup {p_heads}"
               + ("" if not problems else f"\n        {problems}"))
        if photo:
            for _try in range(3):
                if d.shot(pop, f"{photo}-builtin-presets"):
                    break
                pop.update()
                d.pump(800)
            if pop._max_scroll > 0:
                # the rest of a long list: its end, down to the note
                pop._scroll_y = pop._max_scroll
                pop.update()
                d.pump(500)
                d.shot(pop, f"{photo}-builtin-presets-end")
        pop.close()
        d.pump(200)
        return not problems

    def photo_pulldown(name):
        cb.showPopup()
        yield 900
        # The built-in part starts after the person's own presets: scroll to
        # its first heading that is listed, then to the end.
        heads = {h for h, _e in BUILTIN_PRESET_GROUPS}
        first = next((r for r in range(cb.count())
                      if not view.isRowHidden(r) and cb.itemText(r) in heads
                      and cb.itemData(r) is None), 0)
        view.scrollTo(cb.model().index(max(first - 1, 0), 0),
                      view.ScrollHint.PositionAtTop)
        yield 400
        if not d.shot(view, f"{name}-select-preset"):
            yield 1000
            d.shot(view, f"{name}-select-preset")
        view.scrollToBottom()
        yield 400
        d.shot(view, f"{name}-select-preset-end")
        cb.hidePopup()
        yield 400

    # ------------------------------------------------------------ acting
    def user_mode(mode):
        btn = tab._guided_btn if mode == "guided" else tab._manual_btn
        btn.click()

    def user_paper(code, dims=None):
        """Choose a paper in the Paper field ON SCREEN, as a click does."""
        mode = tab._mode_name()
        if mode == "guided":
            c = tab._paper_combo
            i = c.findData(code)
            if i < 0:
                return False
            c.setCurrentIndex(i)
            c.activated.emit(i)
            return True
        panel = tab._manual_layout_panel
        if panel is not None and panel.paper is not None \
                and panel.paper.isVisible():
            c = panel.paper
            want = "__custom__" if code == "custom" else code
            i = c.findData(want)
            if i < 0:
                return False
            c.setCurrentIndex(i)
            c.activated.emit(i)
            if dims:
                panel.custom_w.setValue(dims[0])
                panel.custom_h.setValue(dims[1])
            return True
        pw = tab._manual_paper_pw
        c = pw._custom_combo
        i = c.findData(code)
        if i < 0:
            return False
        c.setCurrentIndex(i)
        c.activated.emit(i)
        if dims:
            pw._custom_w_spin.setValue(dims[0])
            pw._custom_h_spin.setValue(dims[1])
        return True

    def gear(filter_on: bool):
        d.later(tab._preset_shown_btn.click)
        for _ in range(20):
            yield 300
            dlg = d.top_dialog("BuiltinPresetsShownDialog")
            if dlg is not None:
                break
        if dlg is None:
            d.note("   the gear window did not open")
            return
        dlg._paper_filter.setChecked(filter_on)
        yield 300
        dlg._ok_btn.click()
        d._modal_closed()
        yield 1200

    def pick_preset_from_pulldown(key):
        i = cb.findData(key)
        # A person opens the arrow if the preset waits under one; the combo
        # handler is what `activated` reaches, as a click in the list does.
        cb.setCurrentIndex(i)
        cb.activated.emit(i)

    MANUAL_PAPERS = [("A4", None), ("A3", None), ("420x297", None),
                     ("329x483", None), ("Letter", None), ("4x6", None),
                     ("127x178", None), ("custom", (100, 150)),
                     ("custom", (130, 180)), ("A4", None)]
    GUIDED_PAPERS = ["A4", "A3", "420x297", "329x483", "Letter", "4x6",
                     "127x178", "A4"]

    judge(f"{PHASE}: start, as the app opens (no project)",
          photo=None)
    yield 300

    if PHASE == "knutstart":
        judge("K1 as Knut starts: saved defaults, no project, Manual",
              photo=f"{LANG}-K1-knutstart-manual-A4-noproject")
        yield from photo_pulldown(f"{LANG}-K1-knutstart-manual-A4-noproject")
        user_paper("Letter")
        yield 1200
        judge("knutstart: Manual Letter by hand")
        user_paper("A4")
        yield 1200
        judge("knutstart: Manual back to A4 by hand")
        # KNUT'S CASE 1 AS IT HAPPENS: the paper on A3 Landscape, then a
        # ColorMunki A4 preset from the Built-in presets list (his log shows
        # `_apply_knut_preset` again and again). The preset loads its recipe
        # into the layout panel, which shows A4.
        user_paper("420x297")
        yield 1200
        judge("knutstart: Manual A3 Landscape by hand")
        a4_cm = next(k for k in BUILTIN_PRESET_KEYS
                     if group_of[k].startswith("ColorMunki")
                     and builtin_preset_paper(k) == "A4"
                     and k in cp.shown_keys(d.settings, BUILTIN_PRESET_KEYS))
        tab._open_builtin_preset_overlay()
        yield 800
        tab._builtin_preset_popup.selected.emit(a4_cm)
        yield 4000
        judge("K1 after a ColorMunki A4 preset from the Built-in presets "
              "list, no project", photo=f"{LANG}-K1-after-A4-preset")
        yield from photo_pulldown(f"{LANG}-K1-after-A4-preset")
        return

    if PHASE == "restart":
        user_mode("manual")
        yield 1200
        judge("restart: Manual")
        user_mode("guided")
        yield 1200
        judge("restart: Guided")
        user_mode("manual")
        yield 1000
        for code, dims in MANUAL_PAPERS[:3]:
            user_paper(code, dims)
            yield 1200
            judge(f"restart: Manual paper {code}{dims or ''}")
        return

    # Knut's case 1: filter ON, A4, Manual, no project, as he started.
    user_mode("manual")
    yield 1500
    judge("K1 filter ON, Manual, no project, as started",
          photo=f"{LANG}-K1-on-manual-A4-noproject")
    yield from photo_pulldown(f"{LANG}-K1-on-manual-A4-noproject")

    # Every paper, Manual.
    for code, dims in MANUAL_PAPERS:
        user_paper(code, dims)
        yield 1200
        tag = f"{code}{'-%dx%d' % dims if dims else ''}"
        photo = None
        if code == "custom" and dims == (100, 150):
            photo = f"{LANG}-K3-on-manual-custom-100x150"
        elif code in ("4x6", "127x178"):
            photo = f"{LANG}-K4-on-manual-{code}"
        judge(f"Manual paper {tag}", photo=photo)
        if photo:
            yield from photo_pulldown(photo)

    # Guided, every paper, then the switches.
    user_mode("guided")
    yield 1500
    judge("switch to Guided")
    for code in GUIDED_PAPERS:
        if not user_paper(code):
            d.note(f"   Guided has no {code}")
            continue
        yield 1200
        judge(f"Guided paper {code}")
    user_paper("A3")
    yield 800
    user_mode("manual")
    yield 1500
    judge("Guided A3 -> Manual (Manual shows A4)")
    user_mode("guided")
    yield 1500
    judge("Manual A4 -> Guided (Guided shows A3)")
    user_mode("manual")
    yield 1200

    # Filter OFF through the window, then Knut's case 2.
    yield from gear(False)
    judge("K2 filter OFF (window OK), Manual",
          photo=f"{LANG}-K2-off-manual-A4")
    yield from photo_pulldown(f"{LANG}-K2-off-manual-A4")
    user_paper("A3")
    yield 1000
    judge("filter OFF, Manual A3")
    user_mode("guided")
    yield 1000
    judge("filter OFF, Guided")
    user_mode("manual")
    yield 1000
    yield from gear(True)
    judge("filter back ON (window OK), Manual A3")
    user_paper("A4")
    yield 1000
    judge("filter ON, Manual A4 again")

    # A preset of another paper, from the pulldown and from the popup.
    a3_cm = next(k for k in BUILTIN_PRESET_KEYS
                 if group_of[k].startswith("ColorMunki")
                 and builtin_preset_paper(k) == "A3")
    pick_preset_from_pulldown(a3_cm)
    yield 4000
    judge("preset ColorMunki A3 from the pulldown")
    user_paper("A4")
    yield 1500
    judge("then the paper to A4 by hand")
    letter_i1 = next(k for k in BUILTIN_PRESET_KEYS
                     if group_of[k].startswith("i1Pro /")
                     and builtin_preset_paper(k) == "Letter")
    tab._open_builtin_preset_overlay()
    yield 800
    tab._builtin_preset_popup.selected.emit(letter_i1)
    yield 4000
    judge("preset i1Pro Letter from the Built-in presets list")
    photo_card = next(k for k in BUILTIN_PRESET_KEYS
                      if cp.paper_class(builtin_preset_paper(k)) == "custom")
    pick_preset_from_pulldown(photo_card)
    yield 4000
    judge("preset i1Pro photo card (custom) from the pulldown")
    user_paper("A4")
    yield 1500
    judge("then A4 by hand")
    user_mode("guided")
    yield 1200
    judge("Guided after the presets")
    user_mode("manual")
    yield 1200

    # A project loaded.
    d.open_project(PROJECT)
    yield 2500
    judge("project loaded, as it opens")
    for code, dims in [("A4", None), ("custom", (100, 150)), ("4x6", None),
                       ("A3", None)]:
        user_paper(code, dims)
        yield 1200
        judge(f"project loaded, Manual paper {code}{dims or ''}")
    user_mode("guided")
    yield 1200
    judge("project loaded, Guided")
    user_mode("manual")
    yield 1200

    # Save as Defaults on Manual Custom 130 x 180 mm: the restart phase must
    # open on what was saved, and list what that paper lists.
    tab._manual_engine_check.setChecked(True) \
        if tab._manual_engine_check is not None and ENGINE else None
    yield 1500
    user_paper("custom", (130, 180))
    yield 1200
    tab._save_defaults_btn.click()
    yield 2500
    rec["saved_defaults_on"] = on_screen_paper()
    judge("after Save as Defaults (Manual Custom 130x180)")
    d.settings.sync()


if __name__ == "__main__":
    drive = Drive(OUT, projects=((PROJECT,) if PHASE == "fresh" else ()),
                  language=LANG, size=(1500, 1000))
    rc = drive.run(script)
    m = drive.record.get("matrix", [])
    bad = [r for r in m if not r["ok"]]
    (OUT / "matrix.json").write_text(json.dumps(m, indent=2), encoding="utf-8")
    print(f"matrix: {len(m)} cells, {len(bad)} wrong")
    sys.exit(rc or 0)
