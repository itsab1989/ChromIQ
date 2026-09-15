#!/usr/bin/env python3
"""Adversary 23e — is the notice ON THE PANEL the notice this state has earned?

Every previous round set values in code. A person does not: they hold an arrow
key, they select the number and type over it and tab away, they paste, they
spin the wheel. Each of those is a different Qt signal, and a panel that
refreshes on one and not another shows a sentence about a sheet that is no
longer on screen.

After every gesture this reads the text the "Measured from Preview" frame is
REALLY SHOWING (`panel._status.text()`) and compares it with the notice the
state has earned, recomputed from the panel's own widgets.
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
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtCore import Qt, QPoint, QPointF                   # noqa: E402
from PyQt6.QtGui import QWheelEvent                            # noqa: E402
from PyQt6.QtTest import QTest                                 # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402
from onscreen_capture import capture_window                    # noqa: E402


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.005)


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert os.environ.get("QT_QPA_PLATFORM") != "offscreen", "ON SCREEN ONLY"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv23e-"))
    settings = AppSettings()
    for k, v in (("custom_output_path", str(work)), ("language", "en"),
                 ("use_chromiq_layout_engine", True),
                 ("restore_last_session", False), ("appearance", "dark"),
                 ("margin_inspector_show", True),
                 ("auto_update_preview", False)):
        settings.set(k, v)
    QDialog.exec = lambda self: 1                    # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore
    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    from ui.theme import apply_appearance
    TabChart._confirm_displacing_results = lambda self, *a, **k: True
    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.resize(1680, 1100)
    win.show()
    win.raise_()
    pump(app, 2400)
    print("    window on screen:", win.isVisible(), flush=True)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 700)
    tab._user_switch_mode("manual")
    pump(app, 1400)
    tab._manual_target_name_edit.setText("adv23e")
    pump(app, 400)
    p = tab._manual_layout_panel
    panel = tab._margin_panel
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    pump(app, 900)
    if p.use_instr_margins.isChecked():
        p.use_instr_margins.setChecked(False)
        pump(app, 400)
    p.layout_mode.setCurrentIndex(0)
    p.paper.setCurrentIndex(p.paper.findData("A4"))
    for k, v in (("t", 12.0), ("l", 10.0), ("r", 10.0), ("b", 8.0)):
        p.margins[k].setValue(v)
    p.helper_markers_cb.setChecked(False)
    p.text_edge.setValue(4.0)
    p.chart_text.setText("ChromIQ demo sheet")
    p.chart_text_size.setValue(24.0)
    p.stamp_command.setChecked(False)
    pump(app, 1600)

    # one real build, so the panel has a chart to describe
    tab._generate_btn.click()
    for _ in range(900):
        pump(app, 200)
        if tab._generate_btn.isEnabled() and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 2600)
    print("    built:", bool(getattr(tab, "_margin_tiffs", None)), flush=True)

    def earned():
        _a, over = TabChart._engine_text_notes(tab)
        return [s for s in over
                if "runs into the patches" in s or "run into the patches" in s]

    def on_screen():
        t = panel._status.text() or ""
        return [ln for ln in t.split("\n")
                if "runs into the patches" in ln or "run into the patches" in ln]

    recs = []

    def check(name, box=None):
        pump(app, 900)
        e, s = earned(), on_screen()
        rec = {"gesture": name,
               "b_box": p.margins["b"].value(),
               "b_box_text": p.margins["b"].text(),
               "size_box": p.chart_text_size.text(),
               "earned": e, "on_screen": s,
               "matches": ([x.strip() for x in e] == [x.strip() for x in s])}
        recs.append(rec)
        flag = "" if rec["matches"] else "   <<< MISMATCH"
        print(f"  {name:38} b={rec['b_box']:5} size={rec['size_box']:>6} "
              f"earned={len(e)} shown={len(s)}{flag}", flush=True)
        if not rec["matches"]:
            print("      earned   :", (e[0] if e else "(none)")[:150], flush=True)
            print("      on screen:", (s[0] if s else "(none)")[:150], flush=True)
        return rec

    box = p.margins["b"]
    check("0 start (b=8, 24 pt)")

    # 1. HOLD THE ARROW KEY
    box.setFocus(Qt.FocusReason.MouseFocusReason)
    pump(app, 300)
    for _ in range(12):
        QTest.keyClick(box, Qt.Key.Key_Up)
        pump(app, 30)
    check("1 twelve x Up held")

    # 2. SELECT ALL, TYPE, TAB AWAY
    box.setFocus(Qt.FocusReason.MouseFocusReason)
    QTest.keySequence(box, "Ctrl+A") if hasattr(QTest, "keySequence") else None
    box.selectAll()
    pump(app, 200)
    QTest.keyClicks(box, "8")
    pump(app, 400)
    check("2a typed 8, not yet left")
    QTest.keyClick(box, Qt.Key.Key_Tab)
    check("2b typed 8 then Tab away")

    # 3. PASTE
    cb = app.clipboard()
    cb.setText("20")
    box.setFocus(Qt.FocusReason.MouseFocusReason)
    box.selectAll()
    pump(app, 200)
    QTest.keyClick(box, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    pump(app, 300)
    if box.text().strip().replace(",", ".").rstrip(" mm") not in ("20", "20.0"):
        # macOS uses Cmd for paste
        QTest.keyClick(box, Qt.Key.Key_V, Qt.KeyboardModifier.MetaModifier)
    check("3a pasted 20, not yet left")
    QTest.keyClick(box, Qt.Key.Key_Tab)
    check("3b pasted 20 then Tab away")

    # 4. THE WHEEL
    before = box.value()
    ev = QWheelEvent(QPointF(box.rect().center()),
                     box.mapToGlobal(box.rect().center()).toPointF()
                     if hasattr(box.mapToGlobal(box.rect().center()), "toPointF")
                     else QPointF(box.mapToGlobal(box.rect().center())),
                     QPoint(0, 0), QPoint(0, 120),
                     Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                     Qt.ScrollPhase.NoScrollPhase, False)
    app.sendEvent(box, ev)
    pump(app, 400)
    r = check("4 wheel over the Bottom box")
    r["wheel_moved_the_box"] = (box.value() != before)
    print(f"      the wheel moved the box: {r['wheel_moved_the_box']} "
          f"({before} -> {box.value()})", flush=True)

    # 5. DOWN TO THE FLOOR
    box.setFocus(Qt.FocusReason.MouseFocusReason)
    for _ in range(60):
        QTest.keyClick(box, Qt.Key.Key_Down)
        pump(app, 20)
    check("5 held Down to the floor")

    # 6. THE SIZE BOX, typed and tabbed
    sz = p.chart_text_size
    sz.setFocus(Qt.FocusReason.MouseFocusReason)
    sz.selectAll()
    pump(app, 200)
    QTest.keyClicks(sz, "60")
    QTest.keyClick(sz, Qt.Key.Key_Tab)
    check("6 Size typed 60 pt and tabbed")

    # 7. THE TEXT ITSELF, typed character by character
    te = p.chart_text
    te.setFocus(Qt.FocusReason.MouseFocusReason)
    te.selectAll()
    QTest.keyClicks(te, "A much longer line of sheet text than before")
    check("7 the text typed out")

    # 8. Size back to auto with the arrow keys
    sz.setFocus(Qt.FocusReason.MouseFocusReason)
    for _ in range(200):
        QTest.keyClick(sz, Qt.Key.Key_Down)
        pump(app, 5)
    check("8 Size held Down to auto")

    ok, why = capture_window(win, out / "E-after-the-gestures.png")
    print("    photograph:", ok, why, flush=True)
    (out / "adv23e.json").write_text(
        json.dumps(recs, indent=2, ensure_ascii=False), encoding="utf-8")
    bad = [r for r in recs if not r["matches"]]
    print(f"    MISMATCHES: {len(bad)} of {len(recs)}", flush=True)
    win.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
