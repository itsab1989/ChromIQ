#!/usr/bin/env python3
"""Challenge 3: attack round two's button check on the margin-warning fold.

`dd6251d7` made `MarginInspectorPanel._on_warn_toggle_clicked` act on the LEFT
button only and hand everything else back to `QLabel.mousePressEvent`. Round
two proved the right and middle buttons no longer fold. Nobody has attacked the
CHECK itself, so this drives the REAL `MainWindow` in a REAL window and asks:

1. a press with NO button at all, which no mouse can send but Qt can;
2. a real DOUBLE click, whose second half Qt routes back into
   `mousePressEvent` through `QWidget::mouseDoubleClickEvent`;
3. a press delivered WHILE the panel is rebuilding, from inside
   `update_report`, which is the one moment the header text and the fold can
   disagree;
4. a press while the paragraph is already hidden by something else, so the
   handler's idea of the state and the screen's disagree before the click;
5. what handing the event back to `QLabel` actually DOES: whether the press is
   left accepted or ignored, and which ancestor sees it now that it is no
   longer swallowed. Before the fix nothing above the label ever saw a right
   click on it; after the fix it propagates, and that is a change in its own
   right.

The events are real `QTest` clicks and real `QMouseEvent`s through
`QApplication.sendEvent`, on a window that is on the screen.

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-c3-fold.ini \
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-c3-fold-presets \
    CHROMIQ_C3_WORK=/tmp/chromiq-c3-work \
        python scripts/drive_182_c3_fold_buttons.py --out DIR
"""
from __future__ import annotations

import argparse
import json
import os
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

from PyQt6.QtCore import QEvent, QObject, QPointF, Qt          # noqa: E402
from PyQt6.QtGui import QMouseEvent                            # noqa: E402
from PyQt6.QtTest import QTest                                 # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog,             # noqa: E402
                             QMessageBox)

from onscreen_capture import (capture_window, session_is_locked,  # noqa: E402
                              wake_the_screen)

CLAIMS: list[dict] = []
SHOTS: list[str] = []


def pump(app, ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def claim(name: str, ok: bool, detail: str) -> None:
    CLAIMS.append({"claim": name, "ok": bool(ok), "detail": detail})
    print(f"    [{'PASS' if ok else 'FAIL'}] {name}: {detail}", flush=True)


def note(name: str, detail: str) -> None:
    CLAIMS.append({"claim": name, "ok": None, "detail": detail})
    print(f"    [NOTE] {name}: {detail}", flush=True)


def shoot(win, out: Path, name: str) -> None:
    ok, why = capture_window(win, out / name)
    SHOTS.append(f"{name}: {'taken' if ok else 'REFUSED - ' + why}")
    print(f"    photo {name}: {'taken' if ok else 'REFUSED - ' + why}",
          flush=True)


class Watcher(QObject):
    """Records every mouse press an ancestor is offered."""

    def __init__(self):
        super().__init__()
        self.seen: list[str] = []
        self.on = False

    def eventFilter(self, obj, ev):                      # noqa: N802 (Qt)
        if self.on and ev.type() == QEvent.Type.MouseButtonPress:
            self.seen.append(f"{type(obj).__name__}"
                             f"({obj.objectName() or '-'})")
        return False


def press(widget, button, *, dbl=False):
    kind = (QEvent.Type.MouseButtonDblClick if dbl
            else QEvent.Type.MouseButtonPress)
    ev = QMouseEvent(kind, QPointF(4.0, 4.0), QPointF(4.0, 4.0),
                     button, button, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(widget, ev)
    return ev


def run(app, out: Path) -> int:
    from core.settings import AppSettings
    from ui.main_window import MainWindow
    from ui.margin_inspector_panel import MarginInspectorPanel
    from ui.tabs.tab_chart import TabChart
    from ui.theme import apply_appearance

    settings = AppSettings()
    work = Path(os.environ["CHROMIQ_C3_WORK"])
    work.mkdir(parents=True, exist_ok=True)
    settings.set("custom_output_path", str(work))
    settings.set("restore_last_session", False)
    settings.set("appearance", "dark")
    settings.set("margin_inspector_show", True)
    settings.set("margin_violation_notify", True)
    settings.set("auto_update_preview", True)
    print(f"    settings file: {settings._qs.fileName()}", flush=True)

    QDialog.exec = lambda self: 1                    # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore
    TabChart._confirm_displacing_results = lambda self, *a, **k: True

    spy: dict = {}
    hook: dict = {"fn": None}
    _orig = MarginInspectorPanel.update_report

    def _spy(self, report, violations, **kw):
        spy.clear()
        spy.update({
            "violations": [f"{v.edge}" for v in violations],
            "overlap_warnings": list(kw.get("overlap_warnings") or []),
        })
        if hook["fn"] is not None:
            fn, hook["fn"] = hook["fn"], None
            fn(self)                 # a click delivered mid-rebuild
        return _orig(self, report, violations, **kw)

    MarginInspectorPanel.update_report = _spy        # type: ignore[assignment]

    if session_is_locked():
        print("    screen reported locked; waking it", flush=True)
        wake_the_screen()

    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.show()
    win.raise_()
    win.activateWindow()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 600)
    tab._user_switch_mode("manual")
    pump(app, 1200)
    print(f"    window on screen: {win.isVisible()} "
          f"{win.frameGeometry().width()}x{win.frameGeometry().height()}, "
          f"screen locked: {session_is_locked()}", flush=True)

    panel = tab._margin_panel

    # -- build a chart that really does warn, the way a person does ---------
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("C3FoldButtons")
    if not tab._manual_engine_check.isChecked():
        tab._manual_engine_check.setChecked(True)
        pump(app, 1200)
    pnl = tab._manual_layout_panel
    if pnl.use_instr_margins.isChecked():
        pnl.use_instr_margins.setChecked(False)
        pump(app, 400)
    for k in ("t", "r", "b", "l"):
        pnl.margins[k].setValue(0.0)
    pump(app, 500)
    spy.clear()
    tab._margin_ti2 = None
    tab._generate_btn.click()
    end = time.monotonic() + 180.0
    while time.monotonic() < end:
        pump(app, 200)
        if getattr(tab, "_margin_ti2", None) and spy:
            pump(app, 1200)
            break
    n = len(spy.get("violations") or []) + len(spy.get("overlap_warnings") or [])
    panel.set_warnings_expanded(True)
    pump(app, 400)
    claim("a real chart with a real warning is on screen to fold",
          panel._warn_toggle.isVisible() and n >= 1,
          f"header={panel._warn_toggle.text()!r}, warnings the app passed={n}, "
          f"paragraph visible={panel._status.isVisible()}")
    shoot(win, out, "01-warning-unfolded.png")

    changes: list = []
    panel.warnings_expanded_changed.connect(changes.append)

    # -- 1. a press with NO button -----------------------------------------
    panel.set_warnings_expanded(True)
    pump(app, 200)
    changes.clear()
    before = panel.warnings_expanded()
    press(panel._warn_toggle, Qt.MouseButton.NoButton)
    pump(app, 300)
    claim("a press carrying NO button does not fold the paragraph",
          panel.warnings_expanded() == before and changes == [],
          f"expanded {before} -> {panel.warnings_expanded()}, "
          f"changes emitted {changes}")

    # -- 2. a real DOUBLE click --------------------------------------------
    # MEASURED, NOT PREDICTED. `QWidget::mouseDoubleClickEvent`'s documented
    # default calls `mousePressEvent`, which would make a double click toggle
    # TWICE and write the setting twice. So count the handler's calls and log
    # every event type the label is offered, rather than reading the net state.
    seen_types: list[str] = []
    calls = [0]
    _real_handler = panel._warn_toggle.mousePressEvent

    class TypeLog(QObject):
        def eventFilter(self, obj, ev):                  # noqa: N802 (Qt)
            t = ev.type()
            if t in (QEvent.Type.MouseButtonPress,
                     QEvent.Type.MouseButtonDblClick,
                     QEvent.Type.MouseButtonRelease):
                seen_types.append(t.name)
            return False

    tl = TypeLog()
    panel._warn_toggle.installEventFilter(tl)

    def _counting(ev):
        calls[0] += 1
        return _real_handler(ev)

    panel._warn_toggle.mousePressEvent = _counting
    panel.set_warnings_expanded(True)
    pump(app, 300)
    changes.clear()
    QTest.mouseDClick(panel._warn_toggle, Qt.MouseButton.LeftButton)
    pump(app, 500)
    dbl_state = panel.warnings_expanded()
    note("what QTest's double click does",
         f"the label was offered {seen_types}; the handler ran {calls[0]} "
         f"time(s); expanded is {dbl_state}; changes emitted {changes}. "
         "`QTest.mouseDClick` sends only the DblClick, so this measures Qt's "
         "shortcut and NOT what a mouse sends.")

    # THE FOUR EVENTS A REAL DOUBLE CLICK SENDS. The window server delivers
    # Press, Release, DblClick, Release, and `QWidget::mouseDoubleClickEvent`
    # routes the third back into `mousePressEvent`. QTest's shortcut above
    # skips the first, so it cannot answer this and is not allowed to.
    seen_types.clear()
    calls[0] = 0
    panel.set_warnings_expanded(True)
    pump(app, 300)
    changes.clear()
    for kind in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease,
                 QEvent.Type.MouseButtonDblClick,
                 QEvent.Type.MouseButtonRelease):
        ev = QMouseEvent(kind, QPointF(4.0, 4.0), QPointF(4.0, 4.0),
                         Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(panel._warn_toggle, ev)
        pump(app, 60)
    pump(app, 400)
    real_state = panel.warnings_expanded()
    panel._warn_toggle.mousePressEvent = _real_handler
    panel._warn_toggle.removeEventFilter(tl)
    claim("a REAL double click toggles twice and lands back where it started, "
          "writing the setting twice",
          calls[0] == 2 and len(changes) == 2 and real_state is True,
          f"the label was offered {seen_types}; the handler ran {calls[0]} "
          f"time(s); expanded is {real_state}; changes emitted {changes}. "
          "The second toggle is `QWidget::mouseDoubleClickEvent` calling "
          "`mousePressEvent`, which the assignment idiom routes straight back "
          "into the panel's handler.")
    # And a double click on a button the handler ignores.
    panel.set_warnings_expanded(True)
    pump(app, 300)
    changes.clear()
    QTest.mouseDClick(panel._warn_toggle, Qt.MouseButton.RightButton)
    pump(app, 500)
    claim("a double RIGHT click does not fold the paragraph",
          panel.warnings_expanded() and changes == [],
          f"expanded={panel.warnings_expanded()}, changes={changes}")

    # -- 3. a press delivered WHILE the panel is rebuilding -----------------
    panel.set_warnings_expanded(True)
    pump(app, 300)
    changes.clear()
    mid: dict = {}

    def _click_mid_rebuild(p):
        mid["expanded_before"] = p.warnings_expanded()
        mid["header_before"] = p._warn_toggle.text()
        press(p._warn_toggle, Qt.MouseButton.LeftButton)
        mid["expanded_after"] = p.warnings_expanded()
        mid["header_after"] = p._warn_toggle.text()

    hook["fn"] = _click_mid_rebuild
    tab._margin_ti2 = None
    spy.clear()
    tab._generate_btn.click()
    end = time.monotonic() + 180.0
    while time.monotonic() < end:
        pump(app, 200)
        if getattr(tab, "_margin_ti2", None) and spy and mid:
            pump(app, 1200)
            break
    after = {"expanded": panel.warnings_expanded(),
             "header": panel._warn_toggle.text(),
             "paragraph_visible": panel._status.isVisible()}
    agrees = (after["expanded"] == after["paragraph_visible"]
              and (("▼" in after["header"]) == after["expanded"]))
    claim("a click that lands mid-rebuild leaves header, arrow and paragraph "
          "agreeing", bool(mid) and agrees,
          f"during: {json.dumps(mid, ensure_ascii=False)}; "
          f"after the rebuild: {json.dumps(after, ensure_ascii=False)}")
    shoot(win, out, "02-after-a-click-mid-rebuild.png")

    # -- 4. a press while the paragraph is hidden by something else ---------
    panel.set_warnings_expanded(True)
    pump(app, 300)
    changes.clear()
    panel._status.setVisible(False)          # hidden behind the panel's back
    pump(app, 200)
    QTest.mouseClick(panel._warn_toggle, Qt.MouseButton.LeftButton)
    pump(app, 400)
    s1 = {"expanded": panel.warnings_expanded(),
          "paragraph_visible": panel._status.isVisible(),
          "header": panel._warn_toggle.text()}
    QTest.mouseClick(panel._warn_toggle, Qt.MouseButton.LeftButton)
    pump(app, 400)
    s2 = {"expanded": panel.warnings_expanded(),
          "paragraph_visible": panel._status.isVisible(),
          "header": panel._warn_toggle.text()}
    claim("one more click brings a paragraph hidden behind the panel's back "
          "into agreement again",
          s2["expanded"] and s2["paragraph_visible"],
          f"after hiding it and clicking once: {json.dumps(s1)}; "
          f"after clicking again: {json.dumps(s2)}")

    # the whole panel hidden, which is what `margin_inspector_show` does
    panel.set_warnings_expanded(True)
    pump(app, 200)
    changes.clear()
    panel.setVisible(False)
    pump(app, 200)
    press(panel._warn_toggle, Qt.MouseButton.LeftButton)
    pump(app, 300)
    hidden_state = panel.warnings_expanded()
    panel.setVisible(True)
    panel.set_warnings_expanded(True)
    pump(app, 300)
    claim("a press on a header inside a HIDDEN panel still only toggles state, "
          "and nothing crashes", hidden_state is False,
          f"expanded became {hidden_state}; a hidden widget receives no real "
          "click from the window server, so this is the synthetic case only")

    # -- 5. what handing the event back to QLabel does ----------------------
    watcher = Watcher()
    for anc in (panel, panel.parentWidget(), tab, win):
        if anc is not None:
            anc.installEventFilter(watcher)
    panel.set_warnings_expanded(True)
    pump(app, 300)
    changes.clear()

    watcher.seen.clear()
    watcher.on = True
    ev_left = press(panel._warn_toggle, Qt.MouseButton.LeftButton)
    pump(app, 200)
    left_accepted, left_seen = ev_left.isAccepted(), list(watcher.seen)

    watcher.seen.clear()
    ev_right = press(panel._warn_toggle, Qt.MouseButton.RightButton)
    pump(app, 200)
    right_accepted, right_seen = ev_right.isAccepted(), list(watcher.seen)
    watcher.on = False
    for anc in (panel, panel.parentWidget(), tab, win):
        if anc is not None:
            anc.removeEventFilter(watcher)

    note("what QLabel does with the buttons the handler ignores",
         f"LEFT press: accepted={left_accepted}, ancestors offered it "
         f"{left_seen}. RIGHT press: accepted={right_accepted}, ancestors "
         f"offered it {right_seen}. `QWidget::mousePressEvent` ignores the "
         "event, so a right click on the header is no longer swallowed and "
         "walks up the parent chain.")
    claim("no ancestor turns the ignored right click into anything",
          panel.warnings_expanded() is not None
          and not any("Menu" in s for s in right_seen),
          f"after the right press the fold is expanded={panel.warnings_expanded()}, "
          f"and the widgets offered the press were {right_seen}")

    panel.set_warnings_expanded(True)
    pump(app, 300)
    shoot(win, out, "03-after-every-button-probe.png")

    # a real right click at the header's own place on the screen
    QTest.mouseClick(panel._warn_toggle, Qt.MouseButton.RightButton)
    pump(app, 700)
    popups = [type(w).__name__ for w in QApplication.topLevelWidgets()
              if w.isVisible() and w is not win]
    claim("a real right click on the header opens no menu and folds nothing",
          panel.warnings_expanded() and not popups,
          f"expanded={panel.warnings_expanded()}, other visible top levels="
          f"{popups}")
    shoot(win, out, "04-after-a-real-right-click.png")

    # -- the handler's own escape hatch -------------------------------------
    note("the handler still toggles when it is called with no event at all",
         "`if event is not None and event.button() != LeftButton` means "
         "`_on_warn_toggle_clicked(None)` folds. Nothing in the app calls it "
         "that way; the tests do not either. Reported, not changed.")

    win.close()
    pump(app, 600)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        print("REFUSING: QT_QPA_PLATFORM=offscreen. This driver is on screen.")
        return 2

    app = QApplication(sys.argv)
    rc = run(app, out)

    report = {"claims": CLAIMS, "photographs": SHOTS}
    (out / "fold-buttons-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    fails = [c for c in CLAIMS if c["ok"] is False]
    print(f"\n  {len(CLAIMS)} claims, {len(fails)} FAILED")
    for c in fails:
        print(f"    FAIL {c['claim']}")
    return rc or (1 if fails else 0)


if __name__ == "__main__":
    sys.exit(main())
