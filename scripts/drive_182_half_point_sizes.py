#!/usr/bin/env python3
"""Every Size box steps half a point, in the REAL window.

Knut, 2026-09-13: *"All the places where font size is defined, the side pt
number should have one decimal and jump half a point at a time when scrolling
on the input box (increments of 0,5 pt)."*

Four boxes: Sheet text, Clip-border content, Strip & row labels (all three from
`layout_options_panel.small_pt`) and Preferences → Chart Layout. This opens the
real window, steps each box the way a scroll wheel does, and reads back what it
shows, so "decimals(1)" is proved by the text a person sees rather than by the
property.

Run it::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-hp.ini \\
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-hp-presets \\
        python scripts/drive_182_half_point_sizes.py <out-dir>

Never set QT_QPA_PLATFORM=offscreen for this. It is a driver, not a test.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window, session_is_locked   # noqa: E402


def pump(app, ms: int = 250) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def scroll_into_view(widget, app) -> bool:
    """Put *widget* on screen inside whatever scroll area holds it.

    A PHOTOGRAPH OF THE RIGHT WINDOW IS NOT A PHOTOGRAPH OF THE CONTROL. Both
    windows here open scrolled to the top, so the first run of this driver
    proved four boxes by their values and then photographed two pages that do
    not contain any of them. Same fault as the report driver's note list
    earlier the same day.
    """
    from PyQt6.QtWidgets import QScrollArea

    # EXPAND WHAT IT IS FOLDED INSIDE FIRST. `ensureWidgetVisible` cannot show
    # a widget in a COLLAPSED group: the second run of this driver scrolled
    # neatly to the Randomise section and photographed that instead, because
    # the Sheet text frame lives under "Expert Options" and it was shut.
    w = widget.parentWidget()
    while w is not None:
        setter = getattr(w, "setChecked", None)
        if setter is not None and getattr(w, "isCheckable", lambda: False)() \
                and not w.isChecked():
            setter(True)
            pump(app, 200)
        # `ui.widgets.CollapsibleGroupBox` says `set_collapsed`, not any of the
        # Qt-ish names guessed first. Guessing an API and moving on is how the
        # previous run scrolled to the wrong place and photographed it.
        fn = getattr(w, "set_collapsed", None)
        if callable(fn) and getattr(w, "is_collapsed", lambda: False)():
            fn(False)
            pump(app, 250)
        w = w.parentWidget()

    w = widget.parentWidget()
    while w is not None:
        if isinstance(w, QScrollArea):
            w.ensureWidgetVisible(widget, 50, 120)
            pump(app, 350)
            return True
        w = w.parentWidget()
    return False


def probe(box, label: str, app) -> dict:
    """Set 10 pt, step up once and down twice, reading the TEXT each time."""
    box.setValue(10.0)
    pump(app, 120)
    seen = [box.text()]
    box.stepBy(1)
    pump(app, 120)
    seen.append(box.text())
    box.stepBy(-1)
    box.stepBy(-1)
    pump(app, 120)
    seen.append(box.text())
    return {"box": label, "decimals": box.decimals(),
            "single_step": box.singleStep(), "texts": seen,
            "value_after": box.value()}


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-hp-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("use_chromiq_layout_engine", True)
    settings.set("restore_last_session", False)
    settings.set("appearance", "dark")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    from ui.theme import apply_appearance
    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.resize(1700, 1120)
    win.show()
    win.raise_()
    pump(app, 2200)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 700)
    tab._user_switch_mode("manual")
    pump(app, 1200)
    print(f"    window on screen: {win.isVisible()} "
          f"{win.frameGeometry().width()}x{win.frameGeometry().height()}",
          flush=True)

    panel = tab._manual_layout_panel
    rows = [probe(panel.chart_text_size, "Sheet text", app),
            probe(panel.clip_text_size, "Clip-border content", app),
            probe(panel.indicator_size, "Strip & row labels", app)]

    scroll_into_view(panel.chart_text_size, app)
    shot = out / "01-create-chart-sizes.png"
    ok, why = capture_window(win, shot)
    print(f"    photo={'ok' if ok else 'REFUSED: ' + why}", flush=True)

    # Preferences → Chart Layout, in its own window.
    from ui.dialogs.settings_dialog import SettingsDialog
    dlg = SettingsDialog(settings, win)
    dlg.show()
    dlg.raise_()
    pump(app, 1200)
    # SHOW THE TAB THE BOX IS ON. The dialog opens on "General", so the first
    # run photographed a page that does not contain the control it had just
    # proved: the numbers were right and the picture was of something else.
    from PyQt6.QtWidgets import QTabWidget
    for tabs in dlg.findChildren(QTabWidget):
        for i in range(tabs.count()):
            if "chart layout" in tabs.tabText(i).strip().lower():
                tabs.setCurrentIndex(i)
                pump(app, 500)
                print(f"    settings tab: {tabs.tabText(i)!r}", flush=True)
                break
    print(f"    settings on screen: {dlg.isVisible()} "
          f"{dlg.frameGeometry().width()}x{dlg.frameGeometry().height()}",
          flush=True)
    rows.append(probe(dlg._isty_size, "Preferences, Chart Layout", app))
    scroll_into_view(dlg._isty_size, app)
    shot2 = out / "02-preferences-chart-layout.png"
    ok2, why2 = capture_window(dlg, shot2)
    print(f"    photo={'ok' if ok2 else 'REFUSED: ' + why2}", flush=True)
    dlg.close()
    pump(app, 200)

    # THE VALUES, NOT THE STRINGS. The first version compared the shown text
    # against `"10.0" -> "10.5"` and every box "failed": Qt renders the
    # separator the LOCALE asks for, and on this machine that is a comma, so
    # the boxes read "10,0" and the replace never matched. Knut writes "0,5 pt"
    # himself, so the comma is right and the check was wrong. The text is still
    # required to carry a separator with one digit after it, which is the half
    # of this he can see.
    import re as _re

    def _wrong(r) -> bool:
        if r["decimals"] != 1 or abs(r["single_step"] - 0.5) > 1e-9:
            return True
        if abs(r["value_after"] - 9.5) > 1e-9:
            return True
        return not all(_re.search(r"\d[.,]\d(?!\d)", t) for t in r["texts"])

    bad = [r for r in rows if _wrong(r)]
    for r in rows:
        print(f"    {r['box']:26s} decimals={r['decimals']} "
              f"step={r['single_step']}  10 pt -> up -> down twice: "
              f"{r['texts']}", flush=True)
    (out / "half-point-sizes.json").write_text(
        json.dumps({"screen_locked": session_is_locked(),
                    "qt_qpa_platform": os.environ.get("QT_QPA_PLATFORM", "<unset>"),
                    "boxes": rows, "wrong": len(bad)}, indent=2,
                   ensure_ascii=False), encoding="utf-8")
    print(f"\n    {len(bad)} box(es) not on a half-point grid", flush=True)
    win.close()
    pump(app, 200)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
