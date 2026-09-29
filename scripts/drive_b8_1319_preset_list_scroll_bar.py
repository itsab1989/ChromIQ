#!/usr/bin/env python3
"""B8-1319: the open "Select preset" list's scroll bar, pressed with a REAL
mouse. ON SCREEN, real window, real pointer (Quartz CGEvents posted to the
HID tap), nothing patched out of the app.

    python scripts/drive_b8_1319_preset_list_scroll_bar.py OUT_DIR

Knut relayed a user on Windows (#182 5845615756): pressing or dragging the
scroll bar of the open preset list chose the first preset and closed the list;
only the wheel scrolled. Each cell opens the list, finds its vertical scroll
bar, and does one thing a person does with it: drag the handle, click the page
area below the handle, click the down arrow, press and hold the handle without
moving. After each: is the list still open, did the scroll position move, and
did the selected preset change?

Then the same for the Built-in presets list (the bubble from the button beside
the combo), which is a different widget.

Sandbox: userdrive's (settings, presets, ISO file forced to the repo's).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

_TREE = Path(os.environ.get("CHROMIQ_TREE")
             or Path(__file__).resolve().parents[1]).resolve()
sys.path.insert(0, str(_TREE / "scripts"))
sys.path.insert(0, str(_TREE))

OUT = Path(sys.argv[1]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
os.environ["CHROMIQ_SETTINGS_FILE"] = str(OUT / "sandbox" / "settings.ini")
os.environ["CHROMIQ_PRESETS_DIR"] = str(OUT / "sandbox" / "presets")
(OUT / "sandbox" / "presets").mkdir(parents=True, exist_ok=True)

from userdrive import Drive                                   # noqa: E402


def _post(kind, x, y):
    import Quartz
    pt = Quartz.CGPointMake(float(x), float(y))
    names = {"move": Quartz.kCGEventMouseMoved,
             "down": Quartz.kCGEventLeftMouseDown,
             "drag": Quartz.kCGEventLeftMouseDragged,
             "up": Quartz.kCGEventLeftMouseUp}
    ev = Quartz.CGEventCreateMouseEvent(None, names[kind], pt,
                                        Quartz.kCGMouseButtonLeft)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)


def shoot_popup_over_window(popup, main, path, pump) -> bool:
    """The main window with the open popup over it, composed by the window
    server from THOSE TWO WINDOWS ONLY (CGWindowListCreateImageFromArray), so
    nothing another application has on screen can get into the picture and
    the popup does not have to be hidden to prove anything (hiding a popup
    closes it). Refused when the picture is one flat colour."""
    import Quartz
    from CoreFoundation import (CFURLCreateWithFileSystemPath,
                                kCFURLPOSIXPathStyle)
    from onscreen_capture import _is_one_flat_colour, window_id_for
    for _attempt in range(4):
        pump(500)
        ids = [i for i in (window_id_for(popup) if popup.isVisible() else None,
                           window_id_for(main)) if i]
        if not ids:
            continue
        g = main.frameGeometry()
        rect = Quartz.CGRectMake(g.x(), g.y(), g.width(), g.height())
        if popup.isVisible():
            p = popup.frameGeometry()
            rect = Quartz.CGRectUnion(rect, Quartz.CGRectMake(
                p.x(), p.y(), p.width(), p.height()))
        img = Quartz.CGWindowListCreateImageFromArray(
            rect, ids, Quartz.kCGWindowImageBestResolution)
        if img is None:
            continue
        url = CFURLCreateWithFileSystemPath(None, str(path),
                                            kCFURLPOSIXPathStyle, False)
        dest = Quartz.CGImageDestinationCreateWithURL(url, "public.png", 1,
                                                      None)
        Quartz.CGImageDestinationAddImage(dest, img, None)
        if Quartz.CGImageDestinationFinalize(dest) \
                and not _is_one_flat_colour(path):
            return True
        path.unlink(missing_ok=True)
    return False


def script(d):
    from PyQt6.QtCore import QPoint
    from PyQt6.QtWidgets import QApplication, QScrollBar, QStyle, \
        QStyleOptionSlider
    d.goto_tab("chart")
    yield 2000
    tab = d.win._tab_chart
    tab._manual_btn.click()
    yield 1500
    cb = tab._preset_combo
    rec = d.record
    rec["cells"] = []

    def bar_of(view):
        sb = view.verticalScrollBar()
        return sb if sb is not None and sb.isVisible() else None

    def sub_rect(sb, sc):
        # initStyleOption is protected in PyQt: filled by hand, as
        # QScrollBar::initStyleOption fills it.
        from PyQt6.QtWidgets import QStyle as _S
        opt = QStyleOptionSlider()
        opt.initFrom(sb)
        opt.subControls = _S.SubControl.SC_All
        opt.activeSubControls = _S.SubControl.SC_None
        opt.orientation = sb.orientation()
        opt.minimum = sb.minimum()
        opt.maximum = sb.maximum()
        opt.sliderPosition = sb.sliderPosition()
        opt.sliderValue = sb.value()
        opt.singleStep = sb.singleStep()
        opt.pageStep = sb.pageStep()
        opt.upsideDown = sb.invertedAppearance()
        return sb.style().subControlRect(
            QStyle.ComplexControl.CC_ScrollBar, opt, sc, sb)

    def state(label):
        view = cb.view()
        sb = view.verticalScrollBar()
        c = {"step": label,
             "popup_open": bool(view.isVisible()),
             "scroll_value": sb.value() if sb is not None else None,
             "scroll_max": sb.maximum() if sb is not None else None,
             "combo_index": cb.currentIndex(),
             "combo_text": cb.currentText(),
             "preset_loaded": str(getattr(tab, "_active_preset_key", "")
                                  or "")}
        rec["cells"].append(c)
        d.note("CELL " + json.dumps(c))
        return c

    def shot(name):
        # THE POPUP'S OWN WINDOW, by id, and never capture_window's hide/show
        # fallback: hiding a popup closes it, which changes what is measured.
        path = d.shots / f"{name}.png"
        ok = shoot_popup_over_window(cb.view().window(), d.win, path, d.pump)
        d.record["photos"].append({"file": path.name, "ok": ok,
                                   "window": "the open list (popup)"})
        d.note(f"   [photo] {path.name}: {'ok' if ok else 'FAILED'}")

    # WHAT THE MOUSE REACHES: every press, move, release and hide in the
    # popup, with the widget that received it, so a closed list names its cause.
    from PyQt6.QtCore import QEvent, QObject

    class _Trace(QObject):
        def __init__(self):
            super().__init__()
            self.on = False
            self.lines = []

        def eventFilter(self, obj, ev):                   # noqa: N802
            if self.on and ev.type() in (
                    QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease,
                    QEvent.Type.MouseMove, QEvent.Type.Hide,
                    QEvent.Type.Show):
                try:
                    w = obj if hasattr(obj, "window") else None
                    if w is not None and (w.window() is cb.view().window()
                                          or type(w.window()).__name__
                                          == "BuiltinPresetPopup"):
                        pos = (ev.position().toPoint()
                               if hasattr(ev, "position") else None)
                        self.lines.append(
                            f"{ev.type().name} -> {type(obj).__name__}"
                            f"{'' if pos is None else f' at {pos.x()},{pos.y()}'}")
                except Exception:                          # noqa: BLE001
                    pass
            if self.on and ev.type() in (
                    QEvent.Type.ApplicationStateChange,
                    QEvent.Type.ApplicationDeactivate,
                    QEvent.Type.WindowDeactivate,
                    QEvent.Type.Close):
                self.lines.append(f"{ev.type().name} -> {type(obj).__name__}")
            return False

    trace = _Trace()
    QApplication.instance().installEventFilter(trace)

    def activate_app():
        # A POPUP CLOSES WHEN ITS APPLICATION STOPS BEING THE ACTIVE ONE, and
        # a driver's app is not: macOS keeps the terminal that launched it in
        # front (measured: the list closed right after it opened, with no
        # mouse event at all, on an ApplicationStateChange). A real click on
        # the main window's title bar makes ChromIQ the active application,
        # as a person's first click does, and changes nothing in the app.
        g = d.win.frameGeometry()
        x, y = g.x() + g.width() * 0.5, g.y() + 12
        _post("move", x, y)
        _post("down", x, y)
        _post("up", x, y)

    # A PRESET LOWER IN THE LIST IS SELECTED FIRST, so a jump to the first
    # row is visible as a change (row 0 is "none").
    start = next((r for r in range(8, cb.count())
                  if not cb.view().isRowHidden(r) and cb.itemData(r)
                  and not cb.itemData(r, cb.MORE_ROLE)), 0)
    if os.environ.get("B8_1319_START") == "none":
        start = 0          # "none", what a fresh session opens on

    SC = QStyle.SubControl
    actions = [
        ("drag-handle", "handle drag"),
        ("click-page-below", "page"),
        ("click-bar-bottom-end", "arrow"),
        ("hold-handle", "hold"),
        # THE EDGES AROUND THE BAR. The bar is 8 px wide (the app's style
        # sheet); a finger that misses it by a pixel lands on the list's own
        # frame (right of it, above it) or on the scroll strips Qt puts above
        # and below the rows, none of which is the bar.
        ("press-frame-right-of-bar", "edge:right"),
        ("press-frame-above-bar", "edge:top"),
        ("press-strip-below-bar", "edge:below"),
        ("press-strip-above-bar", "edge:above"),
        ("drag-from-frame-beside-handle", "edge:dragright"),
    ]
    only = [c for c in os.environ.get("B8_1319_CELLS", "").split(",") if c]
    if only:
        actions = [a for a in actions if a[0] in only]
    # A CELL THE SESSION INTERFERED WITH IS RUN AGAIN, NOT JUDGED. A popup
    # closes when its application stops being the active one, and on this
    # machine that happens under a driver (the terminal that launched it is
    # in front): the window system then CLOSES the popup's window, which the
    # trace shows as "Close -> QWindow" (Qt closing a list for a press shows
    # only "Hide", never that). Such a cell is INCONCLUSIVE and repeated, up
    # to four times; a list Qt itself closed is judged.
    queue = [(n, w, 1) for n, w in actions]
    while queue:
        name, what, attempt = queue.pop(0)
        cb.blockSignals(True)
        cb.setCurrentIndex(start)
        cb.blockSignals(False)
        trace.lines = []
        trace.on = True
        # open the list the way a click on the combo does
        activate_app()
        yield 700
        cb.showPopup()
        yield 1500
        view = cb.view()
        sb = bar_of(view)
        before = state(f"{name}-opened")
        if sb is None:
            for ln in trace.lines[:40]:
                d.note(f"   EVENT {ln}")
            d.note(f"   {name}: the list closed before the cell began "
                   f"(attempt {attempt}); INCONCLUSIVE, run again")
            cb.hidePopup()
            yield 600
            if attempt < 4:
                queue.insert(0, (name, what, attempt + 1))
            continue
        shot(f"{name}-01-open")
        handle = sub_rect(sb, SC.SC_ScrollBarSlider)
        page = sub_rect(sb, SC.SC_ScrollBarAddPage)
        arrow = sub_rect(sb, SC.SC_ScrollBarAddLine)
        rec.setdefault("geometry", {})[name] = {
            "bar": [sb.width(), sb.height()],
            "handle": [handle.x(), handle.y(), handle.width(), handle.height()],
            "page": [page.x(), page.y(), page.width(), page.height()],
            "arrow": [arrow.x(), arrow.y(), arrow.width(), arrow.height()]}
        g = lambda r: sb.mapToGlobal(r.center())              # noqa: E731
        if what == "handle drag":
            p = g(handle)
            _post("move", p.x(), p.y()); yield 250
            _post("down", p.x(), p.y()); yield 250
            for k in range(1, 13):
                _post("drag", p.x(), p.y() + 12 * k); yield 60
            yield 300
            state(f"{name}-while-held")
            shot(f"{name}-02-dragged-still-held")
            _post("up", p.x(), p.y() + 144); yield 800
        elif what == "page":
            if page.height() <= 2:
                d.note(f"   {name}: no page area below the handle")
            p = g(page)
            _post("move", p.x(), p.y()); yield 250
            _post("down", p.x(), p.y()); yield 150
            _post("up", p.x(), p.y()); yield 800
        elif what == "arrow":
            if arrow.height() <= 2:
                d.note(f"   {name}: the bar draws no down arrow")
            p = g(arrow)
            _post("move", p.x(), p.y()); yield 250
            for _ in range(3):
                _post("down", p.x(), p.y()); yield 120
                _post("up", p.x(), p.y()); yield 250
            yield 500
        elif what == "hold":
            p = g(handle)
            _post("move", p.x(), p.y()); yield 250
            _post("down", p.x(), p.y()); yield 1500
            _post("up", p.x(), p.y()); yield 800
        elif what.startswith("edge:"):
            where = what[5:]
            bar_g = sb.mapToGlobal(QPoint(0, 0))
            cx = bar_g.x() + sb.width() / 2.0
            view_g = view.mapToGlobal(QPoint(0, 0))
            cont = view.window()
            cont_g = cont.mapToGlobal(QPoint(0, 0))
            hp = g(handle)
            if where == "right":           # the view's right frame line
                x, y = view_g.x() + view.width() - 0.75, hp.y()
            elif where == "dragright":
                x, y = view_g.x() + view.width() - 0.75, hp.y()
            elif where == "top":           # the view's top frame line
                x, y = cx, view_g.y() + 0.5
            elif where == "below":         # the strip under the rows
                x, y = cx, bar_g.y() + sb.height() + 5
            else:                          # the strip above the rows
                x, y = cx, view_g.y() - 5
            rec.setdefault("edge_points", {})[name] = [x, y]
            _post("move", x, y); yield 300
            _post("down", x, y); yield 200
            if where == "dragright":
                for k in range(1, 10):
                    _post("drag", x, y + 12 * k); yield 60
                y += 108
            _post("up", x, y); yield 900
        trace.on = False
        after = state(f"{name}-after")
        # consecutive duplicates folded, so a drag reads as one line
        folded = []
        for ln in trace.lines:
            if folded and folded[-1][0] == ln:
                folded[-1][1] += 1
            else:
                folded.append([ln, 1])
        after["events"] = [f"{ln} x{n}" if n > 1 else ln for ln, n in folded]
        for ln in after["events"]:
            d.note(f"   EVENT {ln}")
        ok = (after["popup_open"] and after["combo_index"] == before["combo_index"]
              and (what == "hold" or what.startswith("edge:")
                   or after["scroll_value"] != before["scroll_value"]))
        after["verdict"] = "RIGHT" if ok else "WRONG"
        if not ok and any(ln.startswith("Close -> QWindow")
                          for ln in after["events"]):
            after["verdict"] = "INCONCLUSIVE"
            if attempt < 4:
                queue.insert(0, (name, what, attempt + 1))
        after["attempt"] = attempt
        d.note(f"VERDICT {name}: {after['verdict']} (attempt {attempt}; open {after['popup_open']}, "
               f"scroll {before['scroll_value']} -> {after['scroll_value']}, "
               f"index {before['combo_index']} -> {after['combo_index']})")
        if after["popup_open"]:
            shot(f"{name}-03-after")
            cb.hidePopup()
        else:
            d.shot(tab, f"{name}-03-after-list-closed")
        yield 1000
        # (the next cell puts the selection back, signals blocked)
        yield 800
    # ---- THE BUILT-IN PRESETS LIST (the bubble), a painted list -----------
    from ui.builtin_preset_popup import BuiltinPresetPopup
    bcells = [("bubble-drag-thumb", "drag"), ("bubble-page-below", "page"),
              ("bubble-press-left-of-thumb", "left")]
    bonly = [c for c in os.environ.get("B8_1319_BUBBLE", "").split(",") if c]
    if bonly:
        bcells = [b for b in bcells if b[0] in bonly]
    bqueue = [(n, w, 1) for n, w in bcells]
    while bqueue:
        name, what, attempt = bqueue.pop(0)
        trace.lines = []
        trace.on = True
        activate_app()
        yield 700
        tab._builtin_preset_btn.click()
        yield 1500
        pop = getattr(tab, "_builtin_preset_popup", None)
        if pop is None or not pop.isVisible():
            for ln in trace.lines:
                d.note(f"   EVENT {ln}")
            if attempt < 4:
                bqueue.insert(0, (name, what, attempt + 1))
            d.note(f"   {name}: the Built-in presets list did not open")
            continue
        chosen = []
        pop.selected.connect(chosen.append)
        th = pop._thumb_rect() if hasattr(pop, "_thumb_rect") else None
        if th is None or th.isEmpty():
            # before B8-1319 the thumb geometry lived in paintEvent only;
            # the same arithmetic, for the driver
            from PyQt6.QtCore import QRect
            vp = pop._viewport_rect()
            panel = pop._panel_rect()
            th_h = max(24, int(vp.height() * pop._viewport_h / pop._content_h))
            travel = vp.height() - th_h
            frac = pop._scroll_y / pop._max_scroll if pop._max_scroll else 0
            th = QRect(panel.right() - pop.SCROLLBAR_W - 3,
                       vp.top() + int(travel * frac), pop.SCROLLBAR_W, th_h)
        _r = lambda r: [r.x(), r.y(), r.width(), r.height()]    # noqa: E731
        d.note(f"   {name}: popup {_r(pop.rect())} panel {_r(pop._panel_rect())}"
               f" thumb {_r(th)}"
               + (f" strip {_r(pop._scroll_strip_rect())}"
                  if hasattr(pop, "_scroll_strip_rect") else ""))
        b_before = {"open": pop.isVisible(), "scroll": pop._scroll_y,
                    "max": pop._max_scroll}
        pshot = d.shots / f"{name}-01-open.png"
        shoot_popup_over_window(pop, d.win, pshot, d.pump)
        c = pop.mapToGlobal(th.center())
        if what == "drag":
            _post("move", c.x(), c.y()); yield 250
            _post("down", c.x(), c.y()); yield 250
            for k in range(1, 11):
                _post("drag", c.x(), c.y() + 10 * k); yield 60
            _post("up", c.x(), c.y() + 100); yield 800
        elif what == "page":
            y = pop.mapToGlobal(th.bottomLeft()).y() + 30
            _post("move", c.x(), y); yield 250
            _post("down", c.x(), y); yield 150
            _post("up", c.x(), y); yield 800
        else:
            x = pop.mapToGlobal(th.topLeft()).x() - 1.5
            _post("move", x, c.y()); yield 250
            _post("down", x, c.y()); yield 150
            _post("up", x, c.y()); yield 800
        vis = pop.isVisible()
        # A CHOICE SHOWS AS THE WINDOW IT OPENS: the tab's own slot runs the
        # name prompt's exec() before this spy's append can run.
        _m = QApplication.activeModalWidget()
        if _m is not None and not chosen:
            chosen.append(f"(chose a preset: {_m.windowTitle()!r} opened)")
        trace.on = False
        b_after = {"open": vis, "scroll": pop._scroll_y, "chosen": chosen,
                   "events": list(trace.lines)}
        for ln in trace.lines:
            d.note(f"   EVENT {ln}")
        ok = vis and not chosen and (what == "left"
                                     or b_after["scroll"] != b_before["scroll"])
        verdict = "RIGHT" if ok else "WRONG"
        if not ok and not chosen and any(ln.startswith("Close -> QWindow")
                                         for ln in trace.lines):
            verdict = "INCONCLUSIVE"
            if attempt < 4:
                bqueue.insert(0, (name, what, attempt + 1))
        rec.setdefault("bubble", []).append(
            {"cell": name, "before": b_before, "after": b_after,
             "verdict": verdict, "attempt": attempt})
        d.note(f"VERDICT {name}: {verdict} (attempt {attempt}) "
               f"(open {vis}, scroll {b_before['scroll']} -> "
               f"{b_after['scroll']}, chosen {chosen})")
        if vis:
            shoot_popup_over_window(pop, d.win, d.shots / f"{name}-02-after.png",
                                    d.pump)
            pop.close()
        else:
            yield 1500
            m = QApplication.activeModalWidget()
            if m is not None:
                # a chosen preset may ask for a name: photographed, cancelled
                d.shot(m, f"{name}-02b-what-the-choice-opened")
                d.note(f"   {name}: the choice opened {type(m).__name__} "
                       f"{m.windowTitle()!r}; cancelled")
                m.reject() if hasattr(m, "reject") else m.close()
                yield 1000
            d.shot(tab, f"{name}-02-after-list-closed")
        yield 1500
    # the pointer back out of the way
    _post("move", 20, 20)
    yield 200


if __name__ == "__main__":
    drive = Drive(OUT, language="en", size=(1500, 1000))
    rc = drive.run(script)
    (OUT / "cells.json").write_text(json.dumps(
        {k: drive.record.get(k) for k in ("cells", "geometry",
                                          "log_warnings_and_errors",
                                          "window_on_screen", "photos")},
        indent=2, default=str), encoding="utf-8")
    sys.exit(rc or 0)
