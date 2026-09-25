#!/usr/bin/env python3
"""B8-1226 on screen: the paper-filter note PINNED under both preset lists
(Knut, #182 5839478031: *"not visible before scrolling to the bottom. Can the
message be made to always stay visible at the bottom"*).

    python scripts/drive_b8_1226_pinned_note.py OUT LANG APPEARANCE

Create Chart, Manual. At a narrow and a wide window, "Select preset" is opened
and photographed scrolled to the TOP and to the END, then the Built-in presets
list likewise; each time the driver checks that the note is shown, inside the
list's frame, under the rows, whole, and that the last row can still be
scrolled fully into view above it. Filter on, then off (the other text).
Nobody has to click: every window it opens it closes itself.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import Drive                                   # noqa: E402

OUT, LANG, LOOK = Path(sys.argv[1]).resolve(), sys.argv[2], sys.argv[3]


def script(d):
    import core.curated_presets as cp
    rec = d.record
    rec.update({"language": LANG, "appearance": LOOK, "checks": []})

    def check(what, ok, detail=""):
        rec["checks"].append({"what": what, "ok": bool(ok), "detail": detail})
        d.note(f"   {'OK  ' if ok else 'FAIL'} {what} {detail}")

    d.goto_tab("chart")
    tab = d.win._tab_chart
    tab._user_switch_mode("manual")
    yield 1500
    cb = tab._preset_combo
    view = cb.view()
    for filt in (True, False):
        tab._apply_builtin_presets_shown(
            cp.shown_keys(d.settings, []) or set(), paper_filter=filt)
        tag_f = "on" if filt else "off"
        for width, tag_w in ((1100, "narrow"), (1900, "wide")):
            d.win.resize(width, 1000)
            yield 1200
            for where in ("top", "end"):
                # EACH SCENE OPENS ITS LIST AFRESH. Waking the screen for a
                # photograph can take the focus, and a popup closes when its
                # window loses it; the list is opened again until it is
                # really shown, and a photograph that did not take is taken
                # again on a list opened again.
                scene = f"select-preset {tag_f} {tag_w} {where}"
                name = f"{LANG}-{LOOK}-{tag_f}-{tag_w}-select-preset-{where}"
                took = ok_shown = ok_place = ok_whole = False
                frame, g = view.window(), cb._note_footer.geometry()
                for _try in range(4):
                    cb.hidePopup()
                    yield 300
                    cb.showPopup()
                    yield 1000
                    frame = view.window()
                    foot = cb._note_footer
                    bar = view.verticalScrollBar()
                    bar.setValue(0 if where == "top" else bar.maximum())
                    yield 400
                    if not (frame.isVisible() and foot.isVisible()):
                        continue
                    g = foot.geometry()
                    if _try == 0 or not took:
                        ok_shown = foot.isVisible() and \
                            foot.text() == cp_note(filt)
                        ok_place = frame.rect().contains(g) and \
                            g.top() >= view.geometry().bottom()
                        ok_whole = g.height() >= foot.heightForWidth(
                            g.width()) - 1
                    took = d.shot(view, name)
                    if took:
                        break
                check(f"[{scene}] the note is shown", ok_shown)
                check(f"[{scene}] inside the frame, under the rows", ok_place,
                      f"note {g.getRect()} view {view.geometry().getRect()} "
                      f"frame {frame.rect().getRect()}")
                check(f"[{scene}] whole", ok_whole)
                check(f"[{scene}] photographed", took)
            if not view.window().isVisible():
                cb.showPopup()
                yield 1000
            last = max(r for r in range(cb.count()) if not view.isRowHidden(r))
            idx = cb.model().index(last, 0)
            view.scrollTo(idx)
            yield 300
            check(f"[select-preset {tag_f} {tag_w}] the last row scrolls fully "
                  f"into view", view.viewport().rect().contains(
                      view.visualRect(idx)))
            cb.hidePopup()
            yield 500
            for where in ("top", "end"):
                scene = f"built-in presets {tag_f} {tag_w} {where}"
                name = f"{LANG}-{LOOK}-{tag_f}-{tag_w}-builtin-presets-{where}"
                took = ok = False
                n = None
                for _try in range(4):
                    tab._open_builtin_preset_overlay()
                    yield 900
                    pop = tab._builtin_preset_popup
                    pop._scroll_y = 0 if where == "top" else pop._max_scroll
                    pop.update()
                    yield 400
                    if not pop.isVisible():
                        continue
                    n = pop._note_rect()
                    ok = (pop._panel_rect().contains(n)
                          and n.top() >= pop._viewport_rect().bottom()
                          and pop._note == cp_note(filt))
                    took = d.shot(pop, name)
                    pop.close()
                    yield 400
                    if took:
                        break
                check(f"[{scene}] the note is inside the panel, under the "
                      f"rows", ok, f"{n.getRect() if n is not None else None}")
                check(f"[{scene}] photographed", took)
    tab._apply_builtin_presets_shown(
        cp.shown_keys(d.settings, []) or set(), paper_filter=True)


def cp_note(on: bool) -> str:
    from ui.tabs.tab_chart import preset_list_note
    return preset_list_note(on)


if __name__ == "__main__":
    drive = Drive(OUT, language=LANG, appearance=LOOK, size=(1500, 1000))
    rc = drive.run(script)
    fails = [c for c in drive.record.get("checks", []) if not c["ok"]]
    print(f"checks: {len(drive.record.get('checks', []))}, failed: {len(fails)}")
    sys.exit(rc or (1 if fails else 0))
