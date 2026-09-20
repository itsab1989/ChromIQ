#!/usr/bin/env python3
"""Knut's beta 26 review of the "Which presets can be used for verification?"
button, MEASURED AND PHOTOGRAPHED IN A REAL WINDOW.

Knut, #182, comment 5746561692, on beta 26:

    *"The button is still too tall, and not reduced in height as I previously
    very thoroughly gave examples how it should look. There is also still the
    frame overlapping with the bottom edge of the button, although I gave
    examples how it should look.. One more thing; Move the position of the
    button so that the left edge of the button is aligned with the left edge of
    the dropdown input box for the 'Select preset'."*

and, in comment 5744704621, what "examples" meant — two named reference
controls, not pictures:

* *"Use the button height similar to 'New Seed' or 'Reset to Preset'"*
* *"Make sure there is a distance between the bottom edge of the button and the
  frame edge, as done for other frames, such as the 'Randomisation' or
  'Layout' frames."*

Three claims, three numbers. This driver takes all three off the SHOWN window
and photographs them, because the last two rounds on this button disagreed with
each other on paper: B8-445 measured 22 px against 24 and 24 and called it
already shorter, and round 30 then found that `setFixedHeight` cannot shorten
ANY button in this app, because `ui/styles.py` sets
`QPushButton { min-height: 28px; padding: 6px 18px }` for the whole app and Qt
folds that into `minimumSizeHint`. Only a real layout, in a real window, can
say which of those two is true here.

It records, for each of the preset-verification button, "New seed", "Reset to
preset", "Update preset", "Edit defaults…", the "Select preset" combo box and
the Presets group box: `height()`, `minimumSizeHint().height()`, `sizeHint()`,
`geometry()`, the widget's origin in WINDOW coordinates, its per-widget
stylesheet and its device pixel ratio; plus the gap between the last widget of
the Presets / Randomisation / Layout frames and each frame's bottom edge.

It photographs the window TWICE and keeps the pair only when the two frames are
pixel-identical, and it cuts a MAGNIFIED comparison out of that photograph: the
three buttons Knut named, side by side at 4x nearest-neighbour, plus the bottom
edge of the Presets frame on its own.

NEVER `widget.grab()`, never `screencapture -R` aimed at a window: the picture
comes from `scripts/onscreen_capture.py::capture_window`, which reads the
window's own buffer through `CGWindowListCreateImage` at BEST resolution. That
means the image is at the device pixel ratio (2x here), so every widget
rectangle is multiplied by a scale this driver measures and writes into the
JSON rather than assuming.

    source .venv/bin/activate
    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-k26-btn/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-k26-btn/presets
    unset QT_QPA_PLATFORM
    python scripts/drive_k26_preset_button_geometry.py <out-dir>
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QPoint, QRect, Qt                    # noqa: E402
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter  # noqa: E402
from PyQt6.QtWidgets import QApplication, QGroupBox           # noqa: E402

from drive_182_preset_verification_window import pump, twice  # noqa: E402

WORK = Path("/tmp/chromiq-k26-btn/work")
PROJECT = "K26-Button"

LOG: list[str] = []


def say(line: str = "") -> None:
    print(line, flush=True)
    LOG.append(line)


def app_like_main() -> QApplication:
    """The QApplication `main.py` builds, not a bare one.

    The style and the application-wide event filter both change what a button
    measures: `ButtonFontFilter` gives every button the Menlo/uppercase font
    and owns its WIDTH, and Fusion is what `main.py:147` sets on every
    platform.
    """
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    app.setOrganizationName("ChromIQ")
    from core.resource_path import resource_path
    from PyQt6.QtGui import QFontDatabase
    try:
        for f in resource_path("assets/fonts").glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(f))
    except Exception:                                         # noqa: BLE001
        pass
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from ui.theme import apply_appearance
    apply_appearance(app, None, "light")
    from ui.widgets import CompositeAppFilter
    app._k26_filter = CompositeAppFilter(app)                 # keep it alive
    app.installEventFilter(app._k26_filter)
    return app


def geom(w, win) -> dict:
    """Everything about one widget's box, in its own and the window's frame."""
    if w is None:
        return {"exists": False}
    g = w.geometry()
    o = w.mapTo(win, QPoint(0, 0))
    og = w.mapToGlobal(QPoint(0, 0))
    fm = QFontMetrics(w.font())
    return {
        "exists": True,
        "visible": bool(w.isVisible()),
        "class": type(w).__name__,
        "objectName": w.objectName(),
        "text": (w.text() if hasattr(w, "text") else
                 (w.currentText() if hasattr(w, "currentText") else
                  (w.title() if hasattr(w, "title") else ""))),
        "height": int(w.height()),
        "width": int(w.width()),
        "min_hint_h": int(w.minimumSizeHint().height()),
        "hint_h": int(w.sizeHint().height()),
        "min_hint_w": int(w.minimumSizeHint().width()),
        "hint_w": int(w.sizeHint().width()),
        "min_h": int(w.minimumHeight()),
        "max_h": int(w.maximumHeight()),
        "geometry": [int(g.x()), int(g.y()), int(g.width()), int(g.height())],
        "in_window": [int(o.x()), int(o.y())],
        "global": [int(og.x()), int(og.y())],
        "dpr": float(w.devicePixelRatioF()),
        "font": f"{w.font().family()} {w.font().pointSizeF():g}pt",
        "fm_height": int(fm.height()),
        "stylesheet": w.styleSheet().replace("\n", " "),
    }


def _margins(grp) -> "list[int] | None":
    lay = grp.layout()
    if lay is None:
        return None
    m = lay.contentsMargins()
    return [m.left(), m.top(), m.right(), m.bottom()]


def frame_gap(grp, win) -> dict:
    """How far the LAST widget inside *grp* sits above the frame's bottom.

    "Last" is decided by geometry, not by layout order: the widget whose
    bottom edge is lowest. The gap is measured to the group box's own bottom
    edge, which is where Fusion draws the one-pixel frame line.
    """
    if grp is None:
        return {"exists": False}
    lowest, low_w = None, None
    for c in grp.findChildren(object):
        if not hasattr(c, "isWidgetType") or not c.isWidgetType():
            continue
        if not c.isVisible() or c.parentWidget() is not grp:
            continue
        b = c.mapTo(grp, QPoint(0, c.height()))
        if lowest is None or b.y() > lowest:
            lowest, low_w = b.y(), c
    if lowest is None:
        return {"exists": True, "title": grp.title(), "last": None}
    return {
        "exists": True,
        "title": grp.title(),
        "group_height": int(grp.height()),
        "last_widget": type(low_w).__name__,
        "last_text": (low_w.text() if hasattr(low_w, "text") else ""),
        "last_bottom_in_group": int(lowest),
        "gap_px": int(grp.height() - lowest),
        "contents_margins": _margins(grp),
    }


# --------------------------------------------------------------------------
# the photograph, and the cuts taken out of it
# --------------------------------------------------------------------------

def image_scale(img: QImage, win) -> dict:
    """How many IMAGE pixels one logical window pixel is worth.

    `capture_window` photographs the window's own buffer at BEST resolution, so
    on a 2x display the picture is twice the logical size. Nothing here assumes
    2: the factor is measured from the picture against the window's frame, both
    ways, and written into the JSON.
    """
    fg = win.frameGeometry()
    sx = img.width() / float(fg.width()) if fg.width() else 0.0
    sy = img.height() / float(fg.height()) if fg.height() else 0.0
    return {"image_w": img.width(), "image_h": img.height(),
            "frame": [fg.x(), fg.y(), fg.width(), fg.height()],
            "scale_from_width": round(sx, 4),
            "scale_from_height": round(sy, 4),
            "scale_used": round(sx, 4),
            "window_dpr": float(win.devicePixelRatioF())}


def widget_rect_in_image(w, win, scale: float) -> QRect:
    """*w*'s box in the photograph's own pixels."""
    fg = win.frameGeometry()
    og = w.mapToGlobal(QPoint(0, 0))
    return QRect(int(round((og.x() - fg.x()) * scale)),
                 int(round((og.y() - fg.y()) * scale)),
                 int(round(w.width() * scale)),
                 int(round(w.height() * scale)))


def magnified_strip(img: QImage, cuts: list[tuple[str, QRect]],
                    path: Path, factor: int = 4) -> dict:
    """Stack *cuts* out of ONE photograph, each labelled, at *factor* x.

    Nearest-neighbour, because the point of the picture is which row of pixels
    the button's border is on. A smooth scale invents rows.
    """
    pad, label_w, gap = 8, 260, 10
    pieces = []
    for name, r in cuts:
        rr = r.intersected(img.rect())
        if rr.isEmpty():
            continue
        big = img.copy(rr).scaled(rr.width() * factor, rr.height() * factor,
                                  Qt.AspectRatioMode.IgnoreAspectRatio,
                                  Qt.TransformationMode.FastTransformation)
        pieces.append((name, rr, big))
    if not pieces:
        return {"written": False, "why": "every cut fell outside the picture"}
    w = label_w + max(p[2].width() for p in pieces) + pad * 2
    h = sum(p[2].height() + gap for p in pieces) + pad * 2
    out = QImage(w, h, QImage.Format.Format_RGB32)
    out.fill(QColor(250, 250, 250))
    p = QPainter(out)
    f = QFont("Menlo")
    f.setPointSizeF(11.0)
    p.setFont(f)
    y = pad
    for name, rr, big in pieces:
        p.drawImage(label_w, y, big)
        p.setPen(QColor(200, 40, 40))
        p.drawRect(label_w - 1, y - 1, big.width() + 1, big.height() + 1)
        p.setPen(QColor(20, 20, 20))
        p.drawText(QRect(pad, y, label_w - pad * 2, big.height()),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                       | Qt.TextFlag.TextWordWrap),
                   f"{name}\n{rr.height() // 1} img px "
                   f"({rr.height() / 2:g} logical)")
        y += big.height() + gap
    p.end()
    out.save(str(path))
    return {"written": True, "path": str(path), "factor": factor,
            "cuts": [{"name": n, "image_rect": [r.x(), r.y(), r.width(),
                                                r.height()]}
                     for n, r, _ in pieces]}


def magnified_cut(img: QImage, rect: QRect, path: Path,
                  factor: int = 4) -> dict:
    rr = rect.intersected(img.rect())
    if rr.isEmpty():
        return {"written": False, "why": "the cut fell outside the picture"}
    big = img.copy(rr).scaled(rr.width() * factor, rr.height() * factor,
                              Qt.AspectRatioMode.IgnoreAspectRatio,
                              Qt.TransformationMode.FastTransformation)
    big.save(str(path))
    return {"written": True, "path": str(path), "factor": factor,
            "image_rect": [rr.x(), rr.y(), rr.width(), rr.height()]}


def main() -> int:
    if os.environ.get("QT_QPA_PLATFORM"):
        print("REFUSING: QT_QPA_PLATFORM is set. This is a DRIVER: it opens a "
              "REAL window. offscreen belongs to the test suite.",
              file=sys.stderr)
        return 2
    if "/tmp/" not in os.environ.get("CHROMIQ_SETTINGS_FILE", ""):
        print("REFUSING: CHROMIQ_SETTINGS_FILE is not sandboxed under /tmp",
              file=sys.stderr)
        return 2
    if "/tmp/" not in os.environ.get("CHROMIQ_PRESETS_DIR", ""):
        print("REFUSING: CHROMIQ_PRESETS_DIR is not sandboxed under /tmp",
              file=sys.stderr)
        return 2

    out = Path(sys.argv[1]).resolve()
    shots = out / "shots"
    shots.mkdir(parents=True, exist_ok=True)
    phase = out.name

    measured: dict = {"phase": phase,
                      "driven": time.strftime("%Y-%m-%d %H:%M:%S"),
                      "mode": "ON SCREEN, a real window, capture_window by "
                              "CGWindowID at best resolution"}

    app = app_like_main()

    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)

    from core.settings import AppSettings
    s = AppSettings()
    s.set("custom_output_path", str(WORK))
    s.set("argyll_bin_path", "/Applications/Argyll/bin")
    # The engine panel is what carries "New seed", "Reset to preset",
    # "Update preset" and "Edit defaults…" — the controls Knut named.
    s.set("use_chromiq_layout_engine", True)

    from core.file_manager import Project
    from core.measurement_target import RUN_TYPE_VERIFICATION
    from ui.main_window import MainWindow

    proj = WORK / PROJECT
    Project.create(proj, PROJECT).current_run().ensure_dir()

    say(f"# the preset-verification button, ON SCREEN — {phase}")
    say("")
    say(f"driven   : {measured['driven']}")
    say(f"mode     : {measured['mode']}")
    say(f"settings : {os.environ['CHROMIQ_SETTINGS_FILE']}")
    say(f"presets  : {os.environ['CHROMIQ_PRESETS_DIR']}")
    say("")

    win = MainWindow(s)
    scr = app.primaryScreen().availableGeometry()
    win.resize(min(1500, scr.width() - 40), min(1300, scr.height() - 60))
    win.move(scr.x() + 10, scr.y() + 10)
    win.show()
    pump(app, 1600)

    tab, ctl = win._tab_chart, win._target_ctl
    win._file_mgr.open_project_at(proj)
    ctl.changed.emit()
    pump(app, 700)
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    pump(app, 700)
    win._tabs.setCurrentIndex(win._tabs.indexOf(tab))
    pump(app, 600)
    tab._manual_btn.click()
    pump(app, 1400)
    tab._manual_layout_grp.set_collapsed(False)
    tab._manual_preset_bar.setVisible(True)
    pump(app, 1400)

    btn = tab._preset_verify_btn
    combo = tab._preset_combo
    grp = btn.parentWidget()
    while grp is not None and not isinstance(grp, QGroupBox):
        grp = grp.parentWidget()

    boxes = {g.title(): g for g in tab.findChildren(QGroupBox) if g.isVisible()}
    rand_grp = boxes.get("Randomisation")
    lay_grp = boxes.get("Layout")

    # Bring the engine panel's own buttons into the viewport so they are in
    # the SAME photograph as the preset button. A cut can only compare what
    # one frame contains.
    # **THE SCROLL AREA IS NOT AN ANCESTOR OF THE BUTTON.** The Presets group
    # sits ABOVE the scroll area, in the manual panel's own column, so walking
    # up from the button never finds one and the first run of this driver
    # silently scrolled nothing: "New seed" was at window y=1341 in a 1047 px
    # window and both its cuts fell outside the picture. Walk up from the
    # engine panel instead, which really is inside it.
    panel = getattr(tab, "_manual_layout_panel", None)
    from ui.fade_scroll import FadeScrollArea
    host = panel
    while host is not None and not isinstance(host, FadeScrollArea):
        host = host.parentWidget()
    if host is not None and panel is not None:
        # Put the preset BAR at the bottom of the viewport: it is the lowest of
        # the three controls, and everything Knut named is then in one frame.
        host.ensureWidgetVisible(tab._manual_preset_bar, 0, 30)
        pump(app, 900)
        host.ensureWidgetVisible(panel.new_seed_btn, 0, 30)
        pump(app, 900)
        bar_y = tab._manual_preset_bar.mapTo(win, QPoint(0, 0)).y()
        seed_y = panel.new_seed_btn.mapTo(win, QPoint(0, 0)).y()
        vbar = host.verticalScrollBar()
        # Nudge until both are inside the window, or until the bar runs out.
        for _ in range(40):
            bar_y = tab._manual_preset_bar.mapTo(win, QPoint(0, 0)).y()
            seed_y = panel.new_seed_btn.mapTo(win, QPoint(0, 0)).y()
            if (bar_y + 30 < win.height() and seed_y > 0
                    and bar_y + 30 > 0):
                break
            vbar.setValue(vbar.value() + 40)
            pump(app, 60)
        pump(app, 700)

    widgets = {
        "preset_verify_btn": btn,
        "new_seed": getattr(panel, "new_seed_btn", None),
        "reset_to_preset": tab._manual_preset_reset_btn,
        "update_preset": tab._manual_preset_update_btn,
        "edit_defaults": tab._manual_preset_edit_btn,
        "select_preset_combo": combo,
        "presets_group": grp,
    }
    measured["widgets"] = {k: geom(v, win) for k, v in widgets.items()}
    measured["frames"] = {
        "Presets": frame_gap(grp, win),
        "Randomisation": frame_gap(rand_grp, win),
        "Layout": frame_gap(lay_grp, win),
    }

    # WHO SQUEEZES THE PRESETS FRAME. The first run measured the group box at
    # 94 px with a minimumSizeHint of 117, which is why the button's bottom
    # border is not drawn: the frame is smaller than its own contents. The
    # answer is in one of its ancestors, so every one of them is recorded.
    chain, node = [], grp
    while node is not None and node is not win:
        lay = node.layout()
        chain.append({
            "class": type(node).__name__,
            "objectName": node.objectName(),
            "height": int(node.height()),
            "min_hint_h": int(node.minimumSizeHint().height()),
            "hint_h": int(node.sizeHint().height()),
            "min_h": int(node.minimumHeight()),
            "max_h": int(node.maximumHeight()),
            "layout": type(lay).__name__ if lay is not None else None,
            "layout_min_h": int(lay.minimumSize().height()) if lay is not None
            else None,
            "width": int(node.width()),
            "min_hint_w": int(node.minimumSizeHint().width()),
            "layout_min_w": int(lay.minimumSize().width()) if lay is not None
            else None,
            "v_policy": str(node.sizePolicy().verticalPolicy()).split(".")[-1],
        })
        node = node.parentWidget()
    measured["presets_ancestry"] = chain
    measured["presets_squeezed_by_px"] = int(
        grp.minimumSizeHint().height() - grp.height())

    # The alignment Knut asked for, as one number.
    bx = btn.mapTo(win, QPoint(0, 0)).x()
    cx = combo.mapTo(win, QPoint(0, 0)).x()
    measured["alignment"] = {
        "button_left_in_window": int(bx),
        "combo_left_in_window": int(cx),
        "delta_px": int(bx - cx),
        "aligned": bool(bx == cx),
    }

    say("## the three claims, as numbers")
    say("")
    say("| control | height | minimumSizeHint | sizeHint | left edge (window) |")
    say("|---|---|---|---|---|")
    for k in ("preset_verify_btn", "new_seed", "reset_to_preset",
              "update_preset", "edit_defaults", "select_preset_combo"):
        g = measured["widgets"][k]
        if not g.get("exists"):
            say(f"| {k} | NOT FOUND | | | |")
            continue
        say(f"| {k} | {g['height']} | {g['min_hint_h']} | {g['hint_h']} "
            f"| {g['in_window'][0]} |")
    say("")
    for name, fr in measured["frames"].items():
        if fr.get("exists") and fr.get("gap_px") is not None:
            say(f"    {name:<14} last widget {fr['last_widget']:<12} "
                f"sits {fr['gap_px']} px above the frame's bottom edge "
                f"(margins {fr['contents_margins']})")
    say("")
    say(f"    the Presets group box is {grp.height()} px tall against a "
        f"minimumSizeHint of {grp.minimumSizeHint().height()} px  ->  "
        f"squeezed by {measured['presets_squeezed_by_px']} px")
    for a in measured["presets_ancestry"]:
        say(f"        {a['class']:<22} {a['objectName']:<18} "
            f"h={a['height']:<5} minHint={a['min_hint_h']:<5} "
            f"hint={a['hint_h']:<5} layoutMin={str(a['layout_min_h']):<5} | "
            f"w={a['width']:<5} minHintW={a['min_hint_w']:<5} "
            f"layoutMinW={a['layout_min_w']} {a['v_policy']}")
    say("")
    say(f"    button left edge {bx} px, 'Select preset' combo left edge {cx} px"
        f"  ->  delta {bx - cx} px")
    say("")

    # ---- the photograph, twice -------------------------------------------
    main_png = shots / f"{phase}-01-window.png"
    ok, why, d = twice(app, win, main_png)
    say(f"photograph {main_png.name}: {'kept' if ok else 'REFUSED: ' + why} "
        f"(the two frames differ by {d} %)")
    measured["photograph"] = {"path": str(main_png), "ok": ok, "why": why,
                              "frames_differ_pct": d}
    if not ok:
        say("")
        say("!! NO PICTURE. Everything below is numbers only.")
    else:
        img = QImage(str(main_png))
        sc = image_scale(img, win)
        measured["image_scale"] = sc
        f = sc["scale_used"]
        say(f"    the picture is {img.width()}x{img.height()} for a "
            f"{sc['frame'][2]}x{sc['frame'][3]} window frame, so one logical "
            f"pixel is {f} image pixels (window devicePixelRatio "
            f"{sc['window_dpr']})")

        def padded(w, px=10, py=10):
            r = widget_rect_in_image(w, win, f)
            return r.adjusted(int(-px * f), int(-py * f),
                              int(px * f), int(py * f))

        cuts = [("Which presets can be used\nfor verification?", padded(btn))]
        if panel is not None and panel.new_seed_btn.isVisible():
            cuts.append(("New seed", padded(panel.new_seed_btn)))
        if tab._manual_preset_reset_btn.isVisible():
            cuts.append(("Reset to preset",
                         padded(tab._manual_preset_reset_btn)))
        strip = shots / f"{phase}-02-three-buttons-4x.png"
        measured["magnified_strip"] = magnified_strip(img, cuts, strip)
        say(f"    magnified cut (4x, nearest neighbour): {strip}")

        # the union crop, the three in one rectangle out of the same frame
        union = None
        for _n, r in cuts:
            union = r if union is None else union.united(r)
        if union is not None:
            u = shots / f"{phase}-03-union-2x.png"
            measured["union_cut"] = magnified_cut(img, union, u, 2)
            say(f"    the three in ONE rectangle (2x): {u}")

        # the bottom edge of the Presets frame, on its own
        gr = widget_rect_in_image(grp, win, f)
        bot = QRect(gr.x(), gr.y() + gr.height() - int(70 * f),
                    gr.width(), int(80 * f))
        b = shots / f"{phase}-04-presets-frame-bottom-4x.png"
        measured["frame_bottom_cut"] = magnified_cut(img, bot, b, 4)
        say(f"    the Presets frame's bottom edge (4x): {b}")

        # the left edges, button against combo, one tall thin cut
        cr = widget_rect_in_image(combo, win, f)
        br = widget_rect_in_image(btn, win, f)
        left = min(cr.x(), br.x()) - int(24 * f)
        al = QRect(left, cr.y() - int(6 * f),
                   int(240 * f), (br.y() + br.height()) - cr.y() + int(12 * f))
        a = shots / f"{phase}-05-left-edges-4x.png"
        measured["left_edges_cut"] = magnified_cut(img, al, a, 4)
        say(f"    the two left edges (4x): {a}")

    (out / f"{phase}-measured.json").write_text(
        json.dumps(measured, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / f"{phase}-log.md").write_text("\n".join(LOG) + "\n",
                                         encoding="utf-8")
    say("")
    say(f"written: {out / (phase + '-measured.json')}")
    win.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
