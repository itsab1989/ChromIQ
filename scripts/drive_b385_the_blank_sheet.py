#!/usr/bin/env python3
"""B8-385 — "Show only measured patches" in the two reading modes that are not
strips, driven in a REAL window on a REAL screen.

`ui/tabs/tab_measure.py::_update_engine_read_map` is the only thing that tells
the preview which strips have been read, and it is called from two places, both
on the strip path. Neither `_on_chart_measured` (the engine's XY and CHART
modes) nor `_on_patch_measured` (spot mode) reaches it, so with the feature on
the sheet is blanked and never un-blanked.

WHAT IS REAL AND WHAT IS NOT. The window, the Measure tab, the chart, its
geometry sidecar, the preview and every pixel photographed are the app's own.
The INSTRUMENT is the only thing faked, and it is faked at the one seam the
manager itself uses: the driver emits `MeasureManager`'s own `session_map`,
`chart_measured` and `patch_measured` signals with patches read out of a REAL
measurement on disk (`per_patch_overlay`), which is exactly what the engine
emits when a real instrument reports. Everything downstream of that signal is
the shipped code.

    CHROMIQ_SETTINGS_FILE=… CHROMIQ_PRESETS_DIR=… \\
        python scripts/drive_b385_the_blank_sheet.py <project> <out>
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402
from onscreen_capture import capture_window, session_is_locked   # noqa: E402


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def _frames_match(a: Path, b: Path, tol: int = 8) -> bool:
    try:
        import numpy as np
        from PIL import Image
        x = np.asarray(Image.open(a).convert("RGB")).astype(int)
        y = np.asarray(Image.open(b).convert("RGB")).astype(int)
        if x.shape != y.shape:
            return False
        return bool((np.abs(x - y).sum(axis=2) > tol).sum() == 0)
    except Exception:                                      # noqa: BLE001
        return False


def capture_settled(app, win, first: Path, second: Path, tries: int = 6):
    """Photograph *win* twice and keep going until two frames agree.

    ANOTHER AGENT IS DRIVING THIS MACHINE AT THE SAME TIME, so a single frame
    cannot tell a settled window from one caught mid-repaint.
    """
    ok = ok2 = False
    why = ""
    for n in range(1, tries + 1):
        pump(app, 900)
        ok, why = capture_window(win, first)
        pump(app, 900)
        ok2, why2 = capture_window(win, second)
        why = why or why2
        if ok and ok2 and _frames_match(first, second):
            return True, why, n, True
    return bool(ok and ok2), why, tries, False


def ink_in_the_preview(shot: Path, win, preview) -> dict:
    """How much of the photographed SHEET is still paper-white.

    Measured on the photograph itself, inside the preview's own rectangle
    mapped into the window and scaled by whatever the capture's resolution
    turned out to be. "Blank" is what the blank paints: a pixel within 6 of
    255 on all three channels.
    """
    try:
        import numpy as np
        from PIL import Image
        im = Image.open(shot).convert("RGB")
        tl = preview.mapTo(win, preview.rect().topLeft())
        sx = im.width / max(1, win.width())
        sy = im.height / max(1, win.height())
        x0, y0 = int(tl.x() * sx), int(tl.y() * sy)
        x1 = int((tl.x() + preview.width()) * sx)
        y1 = int((tl.y() + preview.height()) * sy)
        a = np.asarray(im)[max(0, y0):y1, max(0, x0):x1].astype(int)
        if a.size == 0:
            return {"measured": False}
        white = (np.abs(a - 255).max(axis=2) <= 6)
        return {"measured": True, "rect": [x0, y0, x1, y1],
                "pixels": int(white.size / 3),
                "paper_white": int(white.sum()),
                "paper_white_share": round(float(white.mean()), 4)}
    except Exception as exc:                               # noqa: BLE001
        return {"measured": False, "why": str(exc)}


def main() -> int:                                          # noqa: C901
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert not os.environ.get("QT_QPA_PLATFORM"), "this DRIVER opens a window"
    src, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from core.resource_path import resource_path
    from PyQt6.QtGui import QFontDatabase
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-b385-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    settings.set("language", "en")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    dest = work / src.name
    shutil.copytree(src, dest)
    print(f"    project copied to {dest}", flush=True)
    print(f"    screen locked at start: {session_is_locked()}", flush=True)
    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    from ui.theme import apply_appearance
    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.resize(1500, 1000)
    win.show(); win.raise_(); win.activateWindow()
    pump(app, 3000)
    print(f"    window on screen: {win.isVisible()}", flush=True)

    mt = win._tab_measure
    win._tabs.setCurrentWidget(mt)
    pump(app, 800)

    # the chart, and a REAL measurement of it to read patches out of.
    #
    # **THE MEASUREMENT IS MOVED OUT OF THE PROJECT FIRST**, and the first cut
    # of this driver did not do that. `set_ti1_path` paints the overlay from
    # whatever the run's .ti3 already holds, so the sheet arrived with all 240
    # patches already split and the blank had nothing left to blank: the
    # photographs before and after the read came out byte-identical and proved
    # nothing. A chart about to be measured has no measurement.
    ti2 = sorted(dest.glob("runs/run1/*.ti2"))[0]
    ti3 = work / "the-measurement-to-replay.ti3"
    shutil.move(str(sorted(dest.glob("runs/run1/*.ti3"))[0]), ti3)
    mt.set_ti1_path(ti2)
    pump(app, 3000)
    from workflow.measurement_report import per_patch_overlay
    patches = per_patch_overlay(ti3, ti2)
    pages = len(mt._patch_boxes)
    locs = sorted({loc for d in mt._patch_boxes for loc in d})
    letters = sorted({"".join(c for c in loc if c.isalpha()) for loc in locs})
    print(f"    chart {ti2.name}: {pages} page(s), {len(locs)} patches with "
          f"geometry, strips {letters}", flush=True)
    print(f"    measurement {ti3.name}: {len(patches)} patches", flush=True)

    res: dict = {"project": str(src), "chart": str(ti2.name),
                 "pages": pages, "patches_with_geometry": len(locs),
                 "strips": letters, "patches_measured": len(patches)}

    mt._switch_mode("manual")
    pump(app, 800)
    mt._m_overlay_cb.setChecked(True)
    mt._m_only_measured.setChecked(True)
    pump(app, 1200)
    pv = mt._preview

    strips = [{"strip": s, "read": False, "verifiable": True} for s in letters]

    def state(tag: str) -> dict:
        return {"tag": tag,
                "stripe_read_map": dict(pv._stripe_read_map),
                "strips_marked_read": sorted(
                    k for k, v in (pv._stripe_read_map or {}).items() if v),
                "overlay_items_page0": len(pv._patch_overlay.get(0, [])),
                "show_only_measured": bool(pv._show_only_measured)}

    # ---------------------------------------------------------------- CHART
    print("\n    [A] XY / CHART mode: the whole sheet is read at once",
          flush=True)
    mt._spot_session = False
    mt._manager.session_map.emit(strips)
    pump(app, 2500)
    a0 = state("chart-mode, session started, nothing read")
    ok, why, tries, same = capture_settled(
        app, win, out / "A1-chart-mode-before-the-read.png",
        out / "A1b-chart-mode-before-the-read-again.png")
    a0["photograph"] = {"taken": ok, "why": why, "identical_frames": same,
                        "attempts": tries}
    a0["ink"] = ink_in_the_preview(
        out / "A1-chart-mode-before-the-read.png", win, pv)
    print(f"        {a0['tag']}: read map {a0['stripe_read_map']}, "
          f"paper-white share {a0['ink'].get('paper_white_share')}", flush=True)

    mt._manager.chart_measured.emit({"patches": patches})
    pump(app, 3000)
    a1 = state("chart-mode, the whole chart reported")
    ok, why, tries, same = capture_settled(
        app, win, out / "A2-chart-mode-after-the-read.png",
        out / "A2b-chart-mode-after-the-read-again.png")
    a1["photograph"] = {"taken": ok, "why": why, "identical_frames": same,
                        "attempts": tries}
    a1["ink"] = ink_in_the_preview(
        out / "A2-chart-mode-after-the-read.png", win, pv)
    print(f"        {a1['tag']}: read map {a1['stripe_read_map']}, "
          f"overlay items {a1['overlay_items_page0']}, "
          f"paper-white share {a1['ink'].get('paper_white_share')}", flush=True)
    res["A_chart_mode"] = [a0, a1]

    # ----------------------------------------------------------------- SPOT
    print("\n    [B] SPOT mode: patch by patch", flush=True)
    mt._preview.clear_patch_overlay()
    mt._spot_session = True
    mt._manager.session_map.emit(strips)
    pump(app, 2500)
    b0 = state("spot-mode, session started, nothing read")
    ok, why, tries, same = capture_settled(
        app, win, out / "B1-spot-mode-before-the-read.png",
        out / "B1b-spot-mode-before-the-read-again.png")
    b0["photograph"] = {"taken": ok, "why": why, "identical_frames": same,
                        "attempts": tries}
    b0["ink"] = ink_in_the_preview(
        out / "B1-spot-mode-before-the-read.png", win, pv)
    print(f"        {b0['tag']}: read map {b0['stripe_read_map']}, "
          f"paper-white share {b0['ink'].get('paper_white_share')}", flush=True)

    # the first two strips, patch by patch, in the order a reader takes them
    first_two = letters[:2]
    sent = 0
    for p in patches:
        loc = str(p.get("loc", ""))
        if "".join(c for c in loc if c.isalpha()) not in first_two:
            continue
        mt._manager.patch_measured.emit(p)
        sent += 1
        if sent % 10 == 0:
            pump(app, 60)
    pump(app, 3000)
    b1 = state(f"spot-mode, strips {first_two} read patch by patch")
    b1["patches_sent"] = sent
    ok, why, tries, same = capture_settled(
        app, win, out / "B2-spot-mode-two-strips-read.png",
        out / "B2b-spot-mode-two-strips-read-again.png")
    b1["photograph"] = {"taken": ok, "why": why, "identical_frames": same,
                        "attempts": tries}
    b1["ink"] = ink_in_the_preview(
        out / "B2-spot-mode-two-strips-read.png", win, pv)
    print(f"        {b1['tag']}: {sent} patches, read map "
          f"{b1['stripe_read_map']}, overlay items {b1['overlay_items_page0']}, "
          f"paper-white share {b1['ink'].get('paper_white_share')}", flush=True)

    # half a strip: the flicker question. The third strip, partly read.
    if len(letters) > 2:
        half = letters[2]
        mine = [p for p in patches
                if "".join(c for c in str(p.get("loc", "")) if c.isalpha()) == half]
        for p in mine[:max(1, len(mine) // 2)]:
            mt._manager.patch_measured.emit(p)
        pump(app, 2500)
        b2 = state(f"spot-mode, strip {half} HALF read")
        b2["ink"] = ink_in_the_preview(
            out / "B2-spot-mode-two-strips-read.png", win, pv)
        capture_window(win, out / "B3-spot-mode-half-a-strip.png")
        print(f"        {b2['tag']}: read map {b2['stripe_read_map']}",
              flush=True)
        res["B_spot_mode_half_strip"] = b2
    res["B_spot_mode"] = [b0, b1]

    (out / "the-blank-sheet.json").write_text(json.dumps(res, indent=1),
                                              encoding="utf-8")
    win.close()
    pump(app, 500)
    shutil.rmtree(work, ignore_errors=True)
    print("\n    done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
