#!/usr/bin/env python3
"""Drive the REAL ChromIQ window for report 46 (aiming overlay design review).

Phases (all in a sandbox; Basti's preferences are copied to a throwaway .ini
and his ChromIQ root replaced — nothing of his is touched):

  A. Task 3b BEFORE: where the patch-size/scale boxes live today (Manual + gamut).
  B. Task 3a BEFORE: CR30 hex area-first chart at margins 1/6/2/1 — measured
     margins, patch count/size, row-number band position.
  C. Task 3a AFTER: same build with the proposed law-mode fix monkeypatched
     into geometry.compute/placement (rlwi dropped when margins_are_law).
     The working tree is NOT modified — the patch lives in this process only.
  D. Task 2 AFTER-fix flag rings: the chart from B in the real Measure tab,
     with flags produced by the tab's own _on_strip_measured thresholding.
     (Run this same script in a worktree at 6428fd2c^ for the BEFORE shots.)
  E. Gamut-mode verification (coordinator): same LayoutOptionsPanel instance,
     same margins-are-law path, screenshots.
  F. Task 3b AFTER mock: the two rows MOVED into the Layout group at runtime.

    python scripts/drive_46_aiming_overlay_report.py [--phases ABCDEF] [--tag X]
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QPoint, QSettings                       # noqa: E402
from PyQt6.QtGui import QFontDatabase                            # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402

from core.resource_path import resource_path                     # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"
RINGS = Path.home() / "Desktop" / "cr30-flag-ring-proof-real"
CTRLS = Path.home() / "Desktop" / "cr30-layout-controls"
LEFT_MM, TOP_MM, RIGHT_MM, BOTTOM_MM = 1.0, 6.0, 2.0, 1.0
DEMO_CACHE = Path(tempfile.gettempdir()) / "chromiq-demo-projects-cache"

TAG = ""            # filename prefix, e.g. "before_" in the worktree run


def pump(app, ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def shot(w, name, where):
    where.mkdir(parents=True, exist_ok=True)
    p = where / f"{TAG}{name}.png"
    w.grab().save(str(p))
    print(f"    saved {p}")
    return p


def crop_tiff(tif, box, name, where):
    from PIL import Image
    where.mkdir(parents=True, exist_ok=True)
    im = Image.open(tif)
    im.crop(box).save(where / f"{TAG}{name}.png")
    print(f"    saved {where / (TAG + name + '.png')} (crop {box} of {Path(tif).name})")


def first_tiff(ti2: Path) -> "Path | None":
    cands = sorted(ti2.parent.glob(f"{ti2.stem}_01.tif")) or \
            [ti2.with_suffix(".tif")]
    return cands[0] if cands[0].exists() else None


def srgb8_to_xyz100_d50(rgb):
    """Inverse of the tab's display conversion, for realistic event colours."""
    def lin(c):
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(float(c)) for c in rgb)
    # sRGB D65 matrix, then Bradford D65->D50 (combined, standard values)
    x = 0.4360747 * r + 0.3850649 * g + 0.1430804 * b
    y = 0.2225045 * r + 0.7168786 * g + 0.0606169 * b
    z = 0.0139322 * r + 0.0971045 * g + 0.7141733 * b
    return [x * 100.0, y * 100.0, z * 100.0]


def build_chart(app, win, tab, name, expect_law_left=None):
    """Generate a CR30 hex area-first chart at margins 1/6/2/1; return facts."""
    from ui.tabs.tab_chart import TabChart
    TabChart._prompt_target_name = lambda self, *a, **k: name
    tab._target_name_edit.setText(name)
    pnl = tab._manual_layout_panel
    i = pnl.instr.findData("CR30")
    assert i >= 0, "the CR30 is not offered"
    pnl.instr.setCurrentIndex(i)
    pump(app, 600)
    j = pnl.mode.findData("hex")
    assert j >= 0, "no hexagonal shape offered for the CR30"
    pnl.mode.setCurrentIndex(j)
    pump(app, 300)
    k = pnl.layout_mode.findData("area_first")
    assert k >= 0
    pnl.layout_mode.setCurrentIndex(k)
    pump(app, 500)
    for key, val in (("t", TOP_MM), ("r", RIGHT_MM),
                     ("b", BOTTOM_MM), ("l", LEFT_MM)):
        pnl.margins[key].setValue(val)
    pump(app, 400)
    tab._margin_ti2 = None
    tab._on_generate()
    for _ in range(240):
        pump(app, 500)
        if getattr(tab, "_margin_ti2", None):
            break
    ti2 = getattr(tab, "_margin_ti2", None)
    print(f"    generated: {ti2}")
    if not ti2:
        return None
    pump(app, 2000)
    ch = Path(ti2).with_suffix(".channels.json")
    lay = json.loads(ch.read_text(encoding="utf-8"))["layout"]
    dpi = float(lay.get("dpi") or 300)
    pats = [p for p in lay["patches"] if p.get("page") == 0]
    allp = lay["patches"]
    w_mm = pats[0]["w"] * 25.4 / dpi
    h_mm = pats[0]["h"] * 25.4 / dpi
    x0_mm = min(p["x"] for p in pats) * 25.4 / dpi
    from workflow.margin_inspector import measure_from_engine
    eng = measure_from_engine(ch, 0)
    rep = eng[0] if eng else None
    print(f"    patches total={len(allp)} page0={len(pats)} "
          f"size={w_mm:.2f}x{h_mm:.2f} mm  first-patch x={x0_mm:.2f} mm")
    if rep:
        print(f"    MEASURED l/r/t/b = {rep.left_mm:.2f}/{rep.right_mm:.2f}/"
              f"{rep.top_mm:.2f}/{rep.bottom_mm:.2f} mm (set 1/2/6/1)")
    return {"ti2": Path(ti2), "channels": ch, "dpi": dpi, "n": len(allp),
            "n0": len(pats), "w_mm": w_mm, "h_mm": h_mm, "x0_mm": x0_mm,
            "rep": rep}


def main() -> int:
    global TAG
    ap = argparse.ArgumentParser()
    ap.add_argument("--phases", default="ABCDEF")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    TAG = args.tag
    phases = args.phases.upper()

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq_46_"))
    from core.settings import AppSettings
    src = QSettings(str(REAL_PLIST), QSettings.Format.NativeFormat)
    dst = QSettings(str(sandbox / "settings.ini"), QSettings.Format.IniFormat)
    for k in src.allKeys():
        dst.setValue(k, src.value(k))
    dst.sync()
    settings = AppSettings()
    settings._qs = dst
    work = sandbox / "ChromIQ"
    work.mkdir()
    # A demo project WITH a built profile, for the gamut module (phase E).
    import shutil
    demo = None
    for d in sorted(DEMO_CACHE.glob("*/Demo-Full-RGB")):
        demo = d
    if demo is not None:
        shutil.copytree(demo, work / "Demo-Full-RGB")
        print(f"    demo project copied from {demo}")
    settings.set("custom_output_path", str(work))
    if "E" in phases and demo is not None:
        settings.set("restore_last_session", True)
        settings.set("session_target_name", "Demo-Full-RGB")
        settings.set("session_project_root", str(work))
    else:
        settings.set("restore_last_session", False)
    print(f"Sandbox: {sandbox}")

    QDialog.exec = lambda self: 1                      # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    TabChart._confirm_displacing_results = lambda self, *a, **k: True

    win = MainWindow(settings)
    win.show()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 600)
    tab._user_switch_mode("manual")
    pump(app, 800)
    pnl = tab._manual_layout_panel

    # ---------------- A: Task 3b BEFORE ----------------
    if "A" in phases:
        print("\nPHASE A — where the sizing controls live today")
        i = pnl.instr.findData("CR30")
        pnl.instr.setCurrentIndex(i)
        pump(app, 500)
        pf = pnl.layout_mode.findData("patch_first")
        pnl.layout_mode.setCurrentIndex(pf)
        pump(app, 500)
        print(f"    patch-first: patch_x visible={pnl.patch_x.isVisible()} "
              f"(Expert collapsed)")
        shot(win, "3b_A1_patchfirst_basic_expert_collapsed", CTRLS)
        pnl._expert_frame.set_collapsed(False) if hasattr(pnl._expert_frame, "set_collapsed") else None
        try:
            pnl._expert_frame.toggle_btn.setChecked(True)
        except Exception:
            pass
        try:
            pnl._expert_frame.setChecked(True)
        except Exception:
            pass
        pump(app, 600)
        print(f"    patch-first: patch_x visible={pnl.patch_x.isVisible()} "
              f"(Expert expanded)")
        shot(win, "3b_A2_patchfirst_expert_expanded", CTRLS)
        shot(pnl, "3b_A2b_panel_patchfirst_expert_expanded", CTRLS)
        af = pnl.layout_mode.findData("area_first")
        pnl.layout_mode.setCurrentIndex(af)
        pump(app, 500)
        shot(win, "3b_A3_areafirst_basic", CTRLS)
        shot(pnl, "3b_A3b_panel_areafirst", CTRLS)
        print(f"    area-first: area fields visible="
              f"{pnl._area_fields_w.isVisible()}, patch_x visible="
              f"{pnl.patch_x.isVisible()}")

    # ---------------- B: Task 3a BEFORE ----------------
    factsB = None
    if "B" in phases:
        print("\nPHASE B — the chart as the engine builds it TODAY")
        factsB = build_chart(app, win, tab, "cr30-aim")
        if factsB:
            shot(win, "3a_B1_full_window_after_generate", CTRLS)
            mp = getattr(tab, "_margin_panel", None)
            if mp is not None:
                shot(mp, "3a_B2_measured_from_preview_panel", CTRLS)
            tif = first_tiff(factsB["ti2"])
            if tif:
                px = int(20 * factsB["dpi"] / 25.4)
                py = int(80 * factsB["dpi"] / 25.4)
                crop_tiff(tif, (0, 0, px, py), "3a_B3_left_edge_today", CTRLS)

    # ---------------- C: Task 3a AFTER (monkeypatched fix) ----------------
    if "C" in phases:
        print("\nPHASE C — the same build with the proposed law-mode fix")
        from workflow.layout_engine import geometry as GEO
        orig_compute, orig_place = GEO.compute, GEO.placement

        def compute_fix(g, w, h, n, *a, **k):
            if getattr(g, "margins_are_law", False) and g.rlwi:
                g = replace(g, rlwi=0.0)
            return orig_compute(g, w, h, n, *a, **k)

        def place_fix(g, w, h, lay, *a, **k):
            if getattr(g, "margins_are_law", False) and g.rlwi:
                g = replace(g, rlwi=0.0)
            return orig_place(g, w, h, lay, *a, **k)

        GEO.compute, GEO.placement = compute_fix, place_fix
        try:
            factsC = build_chart(app, win, tab, "cr30-aim-fix")
        finally:
            GEO.compute, GEO.placement = orig_compute, orig_place
        if factsC:
            shot(win, "3a_C1_full_window_after_generate_FIX", CTRLS)
            mp = getattr(tab, "_margin_panel", None)
            if mp is not None:
                shot(mp, "3a_C2_measured_from_preview_panel_FIX", CTRLS)
            tif = first_tiff(factsC["ti2"])
            if tif:
                px = int(20 * factsC["dpi"] / 25.4)
                py = int(80 * factsC["dpi"] / 25.4)
                crop_tiff(tif, (0, 0, px, py), "3a_C3_left_edge_FIX", CTRLS)
        if factsB and factsC:
            print("    BEFORE vs FIX: patches "
                  f"{factsB['n']} -> {factsC['n']}, size "
                  f"{factsB['w_mm']:.2f} -> {factsC['w_mm']:.2f} mm, "
                  f"first-patch x {factsB['x0_mm']:.2f} -> {factsC['x0_mm']:.2f} mm")

    # ---------------- D: Task 2 — flag rings in the REAL Measure tab -------
    if "D" in phases and factsB:
        print("\nPHASE D — flagged rings on the real Measure tab")
        ti1 = factsB["ti2"].with_suffix(".ti1")
        mt = win._tab_measure
        win._tabs.setCurrentWidget(mt)
        pump(app, 800)
        mt.set_ti1_path(ti1)
        pump(app, 2000)
        boxes_pages = mt._patch_boxes
        n_boxes = sum(len(d) for d in boxes_pages)
        print(f"    patch boxes loaded: {n_boxes} across {len(boxes_pages)} pages")
        assert n_boxes > 0, "no patch geometry — cannot drive the overlay"
        # Build strip events from the chart's own geometry + its printed colours
        from PIL import Image
        im = Image.open(first_tiff(factsB["ti2"])).convert("RGB")
        page0 = boxes_pages[0]
        import re as _re
        strips: dict[str, list] = {}
        for loc, box in page0.items():
            mm = _re.match(r"([A-Z]+)(\d+)", loc)
            if not mm:
                continue
            strips.setdefault(mm.group(1), []).append((int(mm.group(2)), loc, box))
        letters = sorted(strips)
        # Flag two vertically ADJACENT patches in a middle column — the exact
        # geometry of the fault ("one ring loses either way round") — plus a
        # scattering elsewhere, to judge ring weight at density.
        mid = letters[len(letters) // 2]
        rows_mid = sorted(strips[mid])
        flag = {(mid, rows_mid[4][1]), (mid, rows_mid[5][1])}
        for li in (2, len(letters) - 3):
            rs = sorted(strips[letters[li]])
            flag.add((letters[li], rs[7][1]))
        print(f"    flagged: {sorted(l for _c, l in flag)}")
        for letter in letters:
            evp = []
            for _n, loc, box in sorted(strips[letter]):
                cx, cy = box.x() + box.width() // 2, box.y() + box.height() // 2
                rgb = im.getpixel((cx, cy))
                exyz = srgb8_to_xyz100_d50(rgb)
                if (letter, loc) in flag:
                    mrgb = tuple(min(255, c + 120) if i == 0 else max(0, c - 90)
                                 for i, c in enumerate(rgb))
                    xyz = srgb8_to_xyz100_d50(mrgb)
                    de = 62.0
                else:
                    xyz, de = exyz, 0.8
                evp.append({"loc": loc, "de": de, "exyz": exyz, "xyz": xyz})
            mt._on_strip_measured({"strip": letter, "patches": evp})
            app.processEvents()
        pump(app, 1200)
        shot(win, "D1_measure_tab_full", RINGS)
        pv = mt._preview
        shot(pv, "D2_preview_widget", RINGS)
        # Close-up: zoom the preview onto the adjacent flagged pair.
        try:
            s, ox, oy = pv._paint_geom
            b = page0[rows_mid[4][1]]
            focus = QPoint(int(b.center().x() * s + ox), int(b.center().y() * s + oy))
            pv._apply_zoom(4.0, focus)
            pump(app, 600)
            shot(pv, "D3_preview_zoom_on_adjacent_flagged_pair", RINGS)
            pv._apply_zoom(1.0 / 8.0, None)
            pump(app, 300)
        except Exception as e:      # noqa: BLE001
            print(f"    zoom close-up failed: {e}")

    # ---------------- E: gamut-mode verification ----------------
    if "E" in phases and demo is not None:
        print("\nPHASE E — FROM PROFILE GAMUT shares the panel and the path")
        # The session restore above opened Demo-Full-RGB.
        pump(app, 1500)
        from core.measurement_target import RUN_TYPE_VERIFICATION
        ctl = tab._target_ctl
        ctl.set_profile_run("run2")
        pump(app, 600)
        ctl.set_run_type(RUN_TYPE_VERIFICATION)
        pump(app, 1500)
        prof = tab._gamut_profile()
        print(f"    gamut profile: {prof}")
        tab._user_switch_mode("manual")
        pump(app, 600)
        pnl2 = tab._manual_layout_panel
        i = pnl2.instr.findData("CR30")
        pnl2.instr.setCurrentIndex(i)
        pump(app, 400)
        af = pnl2.layout_mode.findData("area_first")
        pnl2.layout_mode.setCurrentIndex(af)
        pnl2.margins["l"].setValue(3.7)      # a sentinel value to read back
        pump(app, 400)
        tab._user_switch_mode("gamut")
        pump(app, 1200)
        pnl3 = tab._manual_layout_panel
        same = pnl3 is pnl2
        print(f"    same LayoutOptionsPanel instance in gamut mode: {same}")
        print(f"    sentinel left margin reads back: {pnl3.margins['l'].value()}")
        print(f"    instrument reads back: {pnl3.instr.currentData()}, "
              f"layout mode: {pnl3.layout_mode.currentData()}, "
              f"panel visible: {pnl3.isVisible()}")
        shot(win, "E1_gamut_mode_layout_panel", CTRLS)
        # Build in gamut mode at 1 mm left, compare first-patch x with Manual's.
        pnl3.margins["l"].setValue(LEFT_MM)
        pnl3.margins["t"].setValue(TOP_MM)
        pnl3.margins["r"].setValue(RIGHT_MM)
        pnl3.margins["b"].setValue(BOTTOM_MM)
        j = pnl3.mode.findData("hex")
        if j >= 0:
            pnl3.mode.setCurrentIndex(j)
        pump(app, 500)
        tab._margin_ti2 = None
        gen = getattr(tab, "_on_generate", None)
        gen()
        for _ in range(240):
            pump(app, 500)
            if getattr(tab, "_margin_ti2", None):
                break
        ti2g = getattr(tab, "_margin_ti2", None)
        print(f"    gamut-module chart: {ti2g}")
        if ti2g:
            chg = Path(ti2g).with_suffix(".channels.json")
            layg = json.loads(chg.read_text(encoding="utf-8"))["layout"]
            dpig = float(layg.get("dpi") or 300)
            p0 = [p for p in layg["patches"] if p.get("page") == 0]
            x0g = min(p["x"] for p in p0) * 25.4 / dpig
            print(f"    gamut first-patch x = {x0g:.2f} mm "
                  f"(Manual build was {factsB['x0_mm']:.2f} mm)" if factsB
                  else f"    gamut first-patch x = {x0g:.2f} mm")
            from workflow.margin_inspector import measure_from_engine
            eng = measure_from_engine(chg, 0)
            if eng:
                r = eng[0]
                print(f"    gamut MEASURED l/r/t/b = {r.left_mm:.2f}/"
                      f"{r.right_mm:.2f}/{r.top_mm:.2f}/{r.bottom_mm:.2f}")
            shot(win, "E2_gamut_mode_after_generate", CTRLS)

    # ---------------- F: Task 3b AFTER mock ----------------
    if "F" in phases:
        print("\nPHASE F — the proposed placement, mocked at runtime")
        tab._user_switch_mode("manual")
        pump(app, 600)
        pnlF = tab._manual_layout_panel
        pf = pnlF.layout_mode.findData("patch_first")
        pnlF.layout_mode.setCurrentIndex(pf)
        pump(app, 400)
        # Move the two rows' widgets into the Layout group's grid, right where
        # _area_fields_w sits (report 44's exact proposal), runtime-only.
        try:
            lgg = pnlF._area_fields_w.parentWidget().layout()
            from PyQt6.QtWidgets import QGridLayout, QWidget, QHBoxLayout
            holder = QWidget(pnlF)
            g = QGridLayout(holder)
            g.setContentsMargins(0, 0, 0, 0)
            row = 0
            for rowws in (pnlF._patch_size_row, pnlF._patch_scale_row):
                col = 0
                for w in rowws:
                    w.setParent(holder)
                    g.addWidget(w, row, col)
                    w.setVisible(True)
                    col += 1
                row += 1
            lgg.addWidget(holder, 2, 0, 1, 3)
            holder.show()
            pump(app, 600)
            shot(win, "3b_F1_patchfirst_with_rows_in_layout_group_MOCK", CTRLS)
            shot(pnlF, "3b_F1b_panel_patchfirst_rows_in_layout_MOCK", CTRLS)
            print("    mock applied (runtime only; the tree is untouched)")
        except Exception as e:      # noqa: BLE001
            print(f"    mock failed: {e}")

    win.close()
    pump(app, 500)
    print("\ndone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
