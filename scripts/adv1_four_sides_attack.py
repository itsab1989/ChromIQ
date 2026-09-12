#!/usr/bin/env python3
"""ADVERSARY ONE — the sheet's four sides, on screen, measured off the TIFF.

Drives the REAL ChromIQ window against a sandboxed settings file, a sandboxed
presets folder and a sandboxed working folder, and for each state records BOTH
what the "Measured from Preview" frame says and where the ink actually lands on
the sheet the app writes.

The three questions it asks are the ones the four-side audit's own driver
(`scripts/drive_182_four_side_symmetry.py`) named in its comments and that
nothing in the tree answers:

  A  The bottom sheet text at a TYPED Size. The panel predicts 4.2 mm a line
     whatever the Size is, because that is the renderer's LINE PITCH, not its
     type height. Does the ink cross the "B" text-edge reserve, and does the
     panel say anything?
  B  A long bottom line. Does it run off the right edge of the paper, and is
     anything said?
  C  A long clip-border line. Is it cut at the page's top and bottom edges, and
     is anything said?

Usage:
    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-adv1.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-adv1-presets
    python scripts/adv1_four_sides_attack.py --out DIR [--only a,b,c]
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

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QTimer                                   # noqa: E402
from PyQt6.QtGui import QFontDatabase                             # noqa: E402
from PyQt6.QtWidgets import QApplication                          # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window, session_is_locked    # noqa: E402

WORK = Path("/tmp/chromiq-adv1-work")
TARGET = "Adv1Sides"

modals: list[dict] = []
_timers: list = []


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def install_modal_watchdog(app):
    def check():
        w = app.activeModalWidget()
        if w is None:
            return
        text = ""
        for attr in ("text", "toPlainText"):
            f = getattr(w, attr, None)
            if callable(f):
                try:
                    text = str(f())
                    break
                except Exception:
                    pass
        modals.append({"title": w.windowTitle(), "text": text[:300]})
        print(f"    !! modal: {w.windowTitle()!r} -> closing")
        try:
            w.reject()
        except Exception:
            w.close()
    t = QTimer()
    t.setInterval(400)
    t.timeout.connect(check)
    t.start()
    _timers.append(t)


def wait_for_build(app, tab, timeout=300) -> bool:
    end = time.time() + timeout
    pump(app, 800)
    while time.time() < end:
        app.processEvents()
        time.sleep(0.05)
        if tab._generate_btn.isEnabled() and not tab._runner.is_running:
            pump(app, 1500)
            if tab._generate_btn.isEnabled() and not tab._runner.is_running:
                return True
    return False


def _read_gray(path: Path):
    import numpy as np
    import tifffile
    with tifffile.TiffFile(str(path)) as tf:
        page = tf.pages[0]
        arr = np.array(page.asarray())
        try:
            xres = page.tags["XResolution"].value
            dpi = float(xres[0]) / float(xres[1])
            if int(page.tags["ResolutionUnit"].value) == 3:      # centimetres
                dpi *= 2.54
        except Exception:
            dpi = 200.0
    return (arr.min(axis=2) if arr.ndim == 3 else arr), dpi


def ink_box(control: Path, withtext: Path) -> dict:
    """Bounding box of every pixel the two sheets differ on: the text's OWN ink."""
    import numpy as np
    a, dpi = _read_gray(control)
    b, _ = _read_gray(withtext)
    if a.shape != b.shape:
        return {"error": f"shapes differ {a.shape} vs {b.shape}"}
    d = (a.astype(np.int32) - b.astype(np.int32)) > 8          # darker than control
    if not d.any():
        return {"pixels": 0}
    ys, xs = np.where(d)
    H, W = a.shape
    mm = 25.4 / dpi
    return {
        "pixels": int(d.sum()), "dpi": round(dpi, 2),
        "page_w_mm": round(W * mm, 2), "page_h_mm": round(H * mm, 2),
        "x0_px": int(xs.min()), "x1_px": int(xs.max()),
        "y0_px": int(ys.min()), "y1_px": int(ys.max()),
        "left_mm": round(float(xs.min()) * mm, 2),
        "right_edge_gap_mm": round((W - 1 - float(xs.max())) * mm, 2),
        "top_mm": round(float(ys.min()) * mm, 2),
        "bottom_edge_gap_mm": round((H - 1 - float(ys.max())) * mm, 2),
        "touches_right_edge": bool(int(xs.max()) >= W - 2),
        "touches_left_edge": bool(int(xs.min()) <= 1),
        "touches_top_edge": bool(int(ys.min()) <= 1),
        "touches_bottom_edge": bool(int(ys.max()) >= H - 2),
    }


def main() -> int:
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else Path("/tmp/chromiq-adv1-proof/onscreen")
    out.mkdir(parents=True, exist_ok=True)
    only = (sys.argv[sys.argv.index("--only") + 1].split(",")
            if "--only" in sys.argv else None)

    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"

    locked = session_is_locked()
    res: dict = {"screen_locked_at_start": locked, "modals": modals, "steps": []}
    print(f"00 screen locked: {locked}")

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from core.resource_path import resource_path
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))

    from core.settings import AppSettings
    settings = AppSettings()
    WORK.mkdir(parents=True, exist_ok=True)
    settings.set("custom_output_path", str(WORK))
    settings.set("use_chromiq_layout_engine", True)
    settings.set("appearance", "dark")
    from ui import theme as ui_theme
    ui_theme.apply_appearance(app, None, "dark")
    assert settings.get("custom_output_path", "") == str(WORK), "SANDBOX FAILED"
    print(f"00 sandbox ok: {os.environ['CHROMIQ_SETTINGS_FILE']} / {WORK}")

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1660, 1080)
    win.show()
    pump(app, 1500)
    install_modal_watchdog(app)

    tab = win._tab_chart
    if tab._current_mode() != "manual":
        tab._switch_mode("manual")
    pump(app, 700)
    tab._manual_target_name_edit.setText(TARGET)
    pump(app, 900)

    panel = tab._manual_layout_panel
    panel._expert_frame.set_collapsed(False)
    pump(app, 600)

    dst = WORK / TARGET
    from workflow.layout_engine.presets import LayoutRecipe

    BASE = dict(instrument="i1", paper="A4", dpi=200,
                layout_mode="area_first", use_instrument_margins=False,
                clip_border=False, clip_content_mode="off",
                patches=120,
                margin_top=20.0, margin_right=20.0,
                margin_bottom=30.0, margin_left=20.0,
                text_edge_top_mm=8.0, text_edge_mm=4.0, text_edge_clip_mm=4.0,
                show_strip_indicators=True, show_row_indicators=True,
                chart_text="", stamp_command=False,
                randomize=True, seed_fixed=True, seed=4242,
                chart_text_size_mm=0.0, clip_text_size_mm=0.0)

    def apply(**over):
        r = LayoutRecipe.from_dict({**BASE, **over})
        panel.set_recipe(r)
        pump(app, 900)
        tab._update_margin_inspector()
        pump(app, 500)

    def build():
        if dst.exists():
            for t in dst.rglob("*.tif"):
                t.unlink()
        tab._generate_btn.click()
        okb = wait_for_build(app, tab)
        pump(app, 1200)
        return okb, sorted(dst.rglob("*.tif"))

    def field_text() -> str:
        mp = getattr(tab, "_margin_panel", None)
        if mp is None:
            return "<no margin panel>"
        try:
            return str(mp.status_message())
        except Exception as exc:                                  # noqa: BLE001
            return f"<raised {exc!r}>"

    def snap(name: str, comment: str, control_over: "dict | None" = None,
             shot: bool = False) -> dict:
        """Record what the panel says, then build with and without the text."""
        pump(app, 700)
        try:
            warns, over = type(tab)._engine_text_notes(tab)
        except Exception as exc:                                  # noqa: BLE001
            warns, over = [f"<raised {exc!r}>"], []
        r = tab._current_layout_recipe()
        st = {"step": name, "comment": comment,
              "recipe": {"margin_bottom": r.margin_bottom,
                         "margin_left": r.margin_left,
                         "margin_right": r.margin_right,
                         "B": r.text_edge_mm, "Clip": r.text_edge_clip_mm,
                         "chart_text_len": len(r.chart_text or ""),
                         "chart_text_size_pt":
                             round(r.chart_text_size_mm * 72 / 25.4, 2),
                         "clip_border_width_mm": r.clip_border_width_mm,
                         "clip_content_mode": r.clip_content_mode,
                         "clip_text_len": len(r.clip_text or ""),
                         "clip_text_size_pt":
                             round(r.clip_text_size_mm * 72 / 25.4, 2)},
              "panel_message_field": field_text(),
              "red_overlap_notices": over}
        if shot:
            p = out / f"{name}.png"
            ok, why = capture_window(win, p)
            st["screenshot"] = str(p) if ok else f"REFUSED: {why}"
            print(f"      photo: {st['screenshot']}")
        if control_over is not None:
            cur = panel.get_recipe().to_dict()
            panel.set_recipe(LayoutRecipe.from_dict({**cur, **control_over}))
            pump(app, 800)
            _ok0, tifs0 = build()
            ctrl = None
            if tifs0:
                ctrl = out / f"{name}__control.tif"
                shutil.copy(tifs0[0], ctrl)
            panel.set_recipe(LayoutRecipe.from_dict(cur))
            pump(app, 800)
            st["built"], tifs = build()
            if tifs:
                shutil.copy(tifs[0], out / f"{name}__sheet.tif")
                if ctrl is not None:
                    st["ink"] = ink_box(ctrl, tifs[0])
        res["steps"].append(st)
        print(f"  [{name}] red notices: {len(over)}")
        for o in over:
            print(f"      · {o[:170]}")
        if st.get("ink"):
            print("      INK: " + json.dumps(st["ink"]))
        return st

    if getattr(tab, "_manual_chart_notes_edit", None) is not None:
        tab._manual_chart_notes_edit.setText("")
    if getattr(tab, "_manual_stamp_cmd_check", None) is not None:
        tab._manual_stamp_cmd_check.setChecked(False)
    pump(app, 500)

    def want(k: str) -> bool:
        return only is None or k in only

    TXT = "ChromIQ adversary one bottom sheet text"

    # ---- A: the bottom sheet text at a TYPED Size --------------------------
    if want("a"):
        for pt in (0.0, 12.0, 18.0, 28.0):
            apply(margin_bottom=12.0, chart_text=TXT,
                  chart_text_size_mm=(pt * 25.4 / 72.0) if pt else 0.0)
            snap(f"A_bottom_{pt:g}pt",
                 f"bottom margin 12 mm, B 4 mm, Sheet text Size "
                 f"{'auto' if not pt else f'{pt:g} pt'}",
                 control_over={"chart_text": ""}, shot=(pt in (0.0, 28.0)))

    # ---- B: a bottom line longer than the sheet ----------------------------
    if want("b"):
        apply(margin_bottom=30.0, chart_text="B" * 400,
              chart_text_size_mm=0.0)
        snap("B_bottom_400_chars", "a 400-character bottom line, Size auto",
             control_over={"chart_text": ""}, shot=True)

    # ---- C: a clip-border line longer than the page ------------------------
    if want("c"):
        apply(margin_top=20.0, margin_left=40.0, margin_bottom=30.0,
              chart_text="",
              clip_border=True, clip_border_width_mm=30.0, clip_side="left",
              clip_content_mode="text", clip_text="X" * 200)
        snap("C_clip_200_chars", "a 200-character clip line on a 30 mm band",
             control_over={"clip_text": ""}, shot=True)

        apply(margin_top=20.0, margin_left=40.0, margin_bottom=30.0,
              chart_text="",
              clip_border=True, clip_border_width_mm=30.0, clip_side="left",
              clip_content_mode="text", clip_text="X" * 60)
        snap("C_clip_60_chars", "a 60-character clip line on a 30 mm band",
             control_over={"clip_text": ""})

    # ---- D: a clip line half again as long as the page --------------------
    if want("d"):
        for n in (400, 800):
            apply(margin_top=20.0, margin_left=40.0, margin_bottom=30.0,
                  chart_text="",
                  clip_border=True, clip_border_width_mm=30.0,
                  clip_side="left", clip_content_mode="text",
                  clip_text="X" * n)
            snap(f"D_clip_{n}_chars",
                 f"a {n}-character clip line on a 30 mm band",
                 control_over={"clip_text": ""}, shot=(n == 400))

    (out / "onscreen.json").write_text(
        json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out/'onscreen.json'}")
    print(f"screen locked at end: {session_is_locked()}")
    win.close()
    pump(app, 500)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
