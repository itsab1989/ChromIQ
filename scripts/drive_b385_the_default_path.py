#!/usr/bin/env python3
"""B8-385 on the DEFAULT path: a chart that already HAS its measurement.

Round 23 photographed the window reading *"Progress: 100.0 %"* over a wholly
blank sheet. That is not an engine mode: it is what a user sees on opening a
project whose chart has been measured and ticking "Show only measured patches".
"Show overlay from existing measurement" ships OFF, so nothing draws over the
blank either.

The same driver runs on a pristine worktree of the parent commit (BEFORE) and
on the working tree (AFTER), so the two pictures are the same window in the
same state.

    CHROMIQ_SETTINGS_FILE=… CHROMIQ_PRESETS_DIR=… \\
        python scripts/drive_b385_the_default_path.py <project> <out>
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
    """How much of the photographed sheet is paper white, inside the preview."""
    try:
        import numpy as np
        from PIL import Image
        im = Image.open(shot).convert("RGB")
        tl = preview.mapTo(win, preview.rect().topLeft())
        sx, sy = im.width / max(1, win.width()), im.height / max(1, win.height())
        a = np.asarray(im)[int(tl.y() * sy):int((tl.y() + preview.height()) * sy),
                           int(tl.x() * sx):int((tl.x() + preview.width()) * sx)]
        a = a.astype(int)
        if a.size == 0:
            return {"measured": False}
        white = (np.abs(a - 255).max(axis=2) <= 6)
        return {"measured": True, "pixels": int(white.size / 3),
                "paper_white": int(white.sum()),
                "paper_white_share": round(float(white.mean()), 4)}
    except Exception as exc:                               # noqa: BLE001
        return {"measured": False, "why": str(exc)}


def main() -> int:
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
    work = Path(tempfile.mkdtemp(prefix="chromiq-b385-default-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    settings.set("language", "en")
    settings.set("measure_show_overlay", False)   # as it ships
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    dest = work / src.name
    shutil.copytree(src, dest)
    print(f"    tree: {ROOT}", flush=True)
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
    mt = win._tab_measure
    win._tabs.setCurrentWidget(mt)
    pump(app, 800)
    ti2 = sorted(dest.glob("runs/run1/*.ti2"))[0]
    ti3 = sorted(dest.glob("runs/run1/*.ti3"))[0]
    print(f"    chart {ti2.name} WITH its measurement {ti3.name}", flush=True)
    mt._switch_mode("manual")
    pump(app, 600)
    mt.set_ti1_path(ti2)
    pump(app, 3000)
    # exactly as the app ships: the overlay from an existing measurement OFF
    mt._m_overlay_cb.setChecked(False)
    pump(app, 800)
    mt._m_only_measured.setChecked(True)
    pump(app, 2000)
    pv = mt._preview
    res = {"tree": str(ROOT), "chart": ti2.name,
           "overlay_from_existing_measurement": bool(mt._m_overlay_cb.isChecked()),
           "show_only_measured": bool(pv._show_only_measured),
           "stripe_read_map": dict(pv._stripe_read_map),
           "strips_marked_read": sorted(k for k, v in
                                        (pv._stripe_read_map or {}).items() if v),
           "overlay_items_page0": len(pv._patch_overlay.get(0, []))}
    ok, why, tries, same = capture_settled(
        app, win, out / "C1-default-path-only-measured-on.png",
        out / "C1b-default-path-only-measured-on-again.png")
    res["photograph"] = {"taken": ok, "why": why, "identical_frames": same,
                         "attempts": tries}
    res["ink"] = ink_in_the_preview(
        out / "C1-default-path-only-measured-on.png", win, pv)
    print(f"    read map: {res['stripe_read_map']}", flush=True)
    print(f"    overlay items on page 1: {res['overlay_items_page0']}", flush=True)
    print(f"    paper-white share of the preview: "
          f"{res['ink'].get('paper_white_share')}", flush=True)
    print(f"    photograph: {ok} {why}; two identical frames: {same}", flush=True)
    (out / "the-default-path.json").write_text(json.dumps(res, indent=1),
                                               encoding="utf-8")
    win.close()
    pump(app, 500)
    shutil.rmtree(work, ignore_errors=True)
    print("    done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
