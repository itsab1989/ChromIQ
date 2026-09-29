#!/usr/bin/env python3
"""Combined round 1: the highest resolution the box offers, in a real window.

B8-244 was "at 1200 dpi the chart has no preview at all and the panel prints an
internal error in its place". This walks every resolution the box offers,
generates, and asks the preview whether it has a page — plus the notices, which
all divide by the dpi somewhere.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))
from onscreen_capture import capture_window, session_is_locked   # noqa: E402


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:                                   # noqa: C901
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    crashes: list = []
    prev = sys.excepthook
    sys.excepthook = lambda t, e, tb: (
        crashes.append("".join(traceback.format_exception(t, e, tb))),
        prev(t, e, tb))

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-b20r1d-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("use_chromiq_layout_engine", True)
    settings.set("restore_last_session", False)
    settings.set("appearance", "dark")
    settings.set("margin_inspector_show", True)
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    print(f"    screen locked at start: {session_is_locked()}", flush=True)

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    from ui.theme import apply_appearance
    TabChart._confirm_displacing_results = lambda self, *a, **k: True
    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.resize(1680, 1060)
    win.show()
    win.raise_()
    win.activateWindow()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 800)
    tab._user_switch_mode("manual")
    pump(app, 1500)
    panel = tab._manual_layout_panel
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("B20R1Dpi")
    pump(app, 400)

    box = panel.dpi if hasattr(panel, "dpi") else None
    if box is None:
        for n in ("dpi_combo", "resolution", "res_combo"):
            box = getattr(panel, n, None)
            if box is not None:
                break
    assert box is not None, "no resolution control on the panel"
    lo, hi = box.minimum(), box.maximum()
    offered = [lo, 200, 300, 600, hi]
    print(f"    the box offers {lo}..{hi}; walking {offered}", flush=True)

    rows = []
    for value in offered:
        label = f"{value}dpi"
        box.setValue(int(value))
        pump(app, 500)
        assert box.value() == int(value), f"the box would not take {value}"
        tab._margin_report = None
        t0 = time.monotonic()
        tab._generate_btn.click()
        for _ in range(3000):
            pump(app, 150)
            if getattr(tab, "_margin_report", None) is not None:
                break
        wall = time.monotonic() - t0
        rep = getattr(tab, "_margin_report", None)
        prev_w = getattr(tab, "_preview", None)
        pm = None
        try:
            pm = prev_w.current_pixmap() if hasattr(prev_w, "current_pixmap") \
                else None
        except Exception:                            # noqa: BLE001
            pm = None
        tiffs = list(getattr(tab, "_margin_tiffs", []) or [])
        warns, over = TabChart._engine_text_notes(tab, rep)
        row = {
            "dpi_label": label,
            "generated_s": round(wall, 1),
            "measured": (None if rep is None else
                         {k: round(float(getattr(rep, k)), 3)
                          for k in ("left_mm", "right_mm", "top_mm",
                                    "bottom_mm")}),
            "tiffs": len(tiffs),
            "tiff_bytes": (Path(tiffs[0]).stat().st_size if tiffs else 0),
            "preview_has_page": bool(pm is not None and not pm.isNull())
                                 if pm is not None else None,
            "preview_label": (tab._preview.text()
                              if hasattr(tab._preview, "text") else ""),
            "warnings": list(over),
            "notes": [w for w in warns if w not in over],
        }
        rows.append(row)
        print(f"    [{label}] {wall:.1f}s  tiffs={row['tiffs']} "
              f"bytes={row['tiff_bytes']} measured={row['measured']} "
              f"warnings={len(over)}", flush=True)
        for m in over:
            print(f"        {m[:160]}", flush=True)
        ok, why = capture_window(win, out / f"D-{label.replace(' ', '_')}.png")
        row["photograph"] = "OK" if ok else f"REFUSED: {why}"

    (out / "dpi-walk.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "crashes-dpi.txt").write_text("\n\n".join(crashes) or "none",
                                         encoding="utf-8")
    print(f"    crashes: {len(crashes)}", flush=True)
    win.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
