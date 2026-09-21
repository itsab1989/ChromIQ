#!/usr/bin/env python3
"""Open the real Welcome window on screen and photograph help cards.

CLAUDE.md: ON SCREEN IS THE DEFAULT. This driver never sets
``QT_QPA_PLATFORM=offscreen`` and never calls ``widget.grab()`` — every
picture comes from ``scripts.onscreen_capture.capture_window``, which
photographs the WINDOW's own buffer and refuses rather than handing back
wallpaper.

    python scripts/drive_help_cards_onscreen.py --out DIR [--card KEY ...]
                                                [--open-notes]

``--open-notes`` clicks every ▶ disclosure open before the photograph, so the
second register can be seen as well as the first.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
    raise SystemExit("REFUSING: QT_QPA_PLATFORM=offscreen is not a screen.")
os.environ.setdefault("CHROMIQ_SETTINGS_FILE", "/tmp/chromiq-help/settings.ini")
os.environ.setdefault("CHROMIQ_PRESETS_DIR", "/tmp/chromiq-help/presets")

from PyQt6.QtGui import QFontDatabase                       # noqa: E402
from PyQt6.QtWidgets import QApplication, QPushButton       # noqa: E402

from core.resource_path import resource_path                # noqa: E402
from core.settings import AppSettings                       # noqa: E402
from ui.styles import WinButtonLayoutStyle                 # noqa: E402
from scripts.onscreen_capture import capture_window         # noqa: E402


def _size(path: Path) -> str:
    from PyQt6.QtGui import QImage
    im = QImage(str(path))
    return f"{im.width()}x{im.height()}"


def _content_identical(a: Path, b: Path):
    """Are the two frames the same BELOW the title bar? True, or a count."""
    from PyQt6.QtGui import QImage
    ia, ib = QImage(str(a)), QImage(str(b))
    if ia.size() != ib.size():
        return f"DIFFERENT SIZES {ia.width()}x{ia.height()} vs {ib.width()}x{ib.height()}"
    top = 60 if ia.height() > 400 else 0       # the macOS title bar, at 2x
    n = 0
    for y in range(top, ia.height() - 12):
        for x in range(0, ia.width(), 3):      # every third column is plenty
            if ia.pixel(x, y) != ib.pixel(x, y):
                n += 1
    return True if n == 0 else f"{n} differing samples"


def main() -> int:
    args = sys.argv[1:]
    out = Path(args[args.index("--out") + 1]) if "--out" in args else \
        Path.home() / "Desktop" / "ChromIQ-beta30-proof" / "help-cards" / "onscreen"
    open_notes = "--open-notes" in args
    cards = [args[i + 1] for i, a in enumerate(args) if a == "--card"]
    frac = float(args[args.index("--scroll") + 1]) if "--scroll" in args else 0.0
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    # main.py:147 — the suite and every driver must paint through what ships.
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    # THE APP-WIDE SHEET, BECAUSE THE WINDOW IS PAINTED BY IT. Without this
    # the scroll pane keeps Fusion's light viewport while the dialog paints
    # dark, and a driver reports a contrast fault the product does not have.
    from ui.theme import apply_appearance
    mode = args[args.index("--mode") + 1] if "--mode" in args else "dark"
    mode = apply_appearance(app, None, mode)

    from ui.dialogs.welcome_dialog import WelcomeDialog, WORKFLOWS

    dlg = WelcomeDialog(AppSettings(), None, initial_mode=mode)
    dlg.resize(980, 900)
    dlg.show()
    app.processEvents()
    time.sleep(1.2)

    keys = cards or [w["key"] for w in WORKFLOWS]
    report: list[str] = []
    for key in keys:
        dlg._on_card_clicked(key)
        app.processEvents()
        if open_notes:
            for btn in dlg._steps_host.findChildren(QPushButton):
                if btn.objectName() == "welcome_note_head" or \
                        btn.text().startswith(("▶", "▼")):
                    btn.click()
                    app.processEvents()
        # Scroll the detail pane. 0.0 (the default) starts the photograph at
        # step 1; --scroll takes a fraction so a long card's lower half can be
        # photographed too.
        try:
            bar = dlg._detail_scroll.verticalScrollBar()
            bar.setValue(int(bar.maximum() * frac))
        except Exception:
            pass
        app.processEvents()
        time.sleep(0.5)
        # TWO PIXEL-IDENTICAL FRAMES: a single frame can catch a half-painted
        # window, and two that differ say the window was still settling.
        tag = key if frac == 0.0 else f"{key}-at{int(frac * 100)}"
        a = out / f"{tag}-1.png"
        b = out / f"{tag}-2.png"
        ok_a, why_a = capture_window(dlg, a)
        time.sleep(0.4)
        ok_b, why_b = capture_window(dlg, b)
        if not (ok_a and ok_b):
            report.append(f"{tag}: CAPTURE FAILED — {why_a or why_b}")
            continue
        # TWO FRAMES, COMPARED ON THE CONTENT AND NOT ON THE TITLE BAR.
        # Measured 2026-09-21: the window's own buffer is pixel-identical
        # below the title bar between two captures, while the traffic-light
        # buttons and the rounded corner alpha move by a few hundred pixels
        # as macOS re-draws the chrome. Comparing the whole frame reports
        # "DIFFER" on a window that has completely settled, which is a false
        # negative, so the band that carries the CARD is what is compared and
        # the whole-frame figure is reported beside it.
        whole = a.read_bytes() == b.read_bytes()
        content = _content_identical(a, b)
        report.append(
            f"{tag}: photographed at {_size(a)}, card area "
            f"{'IDENTICAL' if content is True else content}, whole frame "
            f"{'identical' if whole else 'differs (window chrome)'}")
    dlg.close()
    print("\n".join(report))
    return 0 if all("FAILED" not in r for r in report) else 1


if __name__ == "__main__":
    raise SystemExit(main())
