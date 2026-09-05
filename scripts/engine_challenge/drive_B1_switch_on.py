"""B1 — the switch-on journey through the real Preferences window.

Fresh sandbox, engine OFF. Build Profile → Manual first (rows must be
hidden), then Preferences (the masthead's gear) → Beta → tick the engine →
read the consent box → Enable → Accuracy dropdown open (screencapture) →
Maximum accuracy → OK. Then: are the four engine rows visible WITHOUT
leaving the Build Profile tab? Every tooltip text is dumped for reading.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.engine_challenge.harness import Harness            # noqa: E402
from scripts.engine_challenge.drive_B_common import (            # noqa: E402
    CHART_924, WORK_B, active_modal, button_named, buttons_of, click,
    click_tab, grab, modal_title, run_journey, sandbox, say, screencapture,
    text_fits, tooltip_bodies)

OUT = WORK_B / "B1"
OUT.mkdir(parents=True, exist_ok=True)
SEEN: list[tuple[str, str]] = []          # (dialog title, what I clicked)


def journey(h):
    from PyQt6.QtWidgets import QAbstractButton, QComboBox, QMessageBox, QDialogButtonBox
    win, app = h.win, h.app
    prof = win._tab_profile

    say("step 1: Build Profile tab → MANUAL, engine off")
    h.go_profile_tab("manual")
    yield 400
    rows = prof._m_engine_rows_widget
    say(f"  rows.isVisible()={rows.isVisible()} isHidden={rows.isHidden()} "
        f"visibleRegion.empty={rows.visibleRegion().isEmpty()}")
    grab(win, OUT / "01-manual-before.png")

    say("step 2: open Preferences through the masthead gear")
    gear = None
    for b in win._masthead.findChildren(QAbstractButton):
        tip = (b.toolTip() or "") + " " + (b.accessibleName() or "") + " " + b.objectName()
        if any(k in tip.lower() for k in ("preference", "setting")):
            gear = b
            break
    if gear is not None and gear.isVisible():
        say(f"  clicking masthead button objectName={gear.objectName()!r} tip={gear.toolTip()!r}")
        click(gear)
    else:
        say("  no gear button found by tooltip — using the ⌘, slot win._open_settings()")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, win._open_settings)
    for _ in range(50):
        yield 100
        if active_modal(h) is not None:
            break
    dlg = active_modal(h)
    say(f"  modal now: {dlg.__class__.__name__} title={dlg.windowTitle()!r}")
    if dlg is None or "Settings" not in dlg.__class__.__name__:
        say("!! Preferences did not open as a modal")
        return
    yield 400

    say("step 3: click the Beta tab")
    idx = click_tab(dlg._tabs, "Beta")
    yield 400
    say(f"  Beta tab index {idx}, current={dlg._tabs.currentIndex()}")
    say(f"  engine check: checked={dlg._profile_engine_check.isChecked()} "
        f"accuracy cell visible={dlg._gammap_mode_cell.isVisible()}")
    grab(dlg, OUT / "02-prefs-beta-before.png")
    screencapture(OUT / "02-prefs-beta-before-screen.png")
    accuracy_tip = tooltip_bodies(dlg._gammap_mode_cell)
    engine_tips = tooltip_bodies(dlg._beta_page)
    (OUT / "beta-tooltips.json").write_text(json.dumps(engine_tips, indent=1, ensure_ascii=False), encoding="utf-8")

    say("step 4: tick 'ChromIQ profile engine (beta)' with the mouse")
    click(dlg._profile_engine_check)
    for _ in range(50):
        yield 100
        m = active_modal(h)
        if m is not None and m is not dlg:
            break
    box = active_modal(h)
    if box is dlg or box is None:
        say("!! no consent dialog appeared after ticking the box")
    else:
        say(f"  consent modal: {box.__class__.__name__} title={box.windowTitle()!r} "
            f"size={box.width()}x{box.height()}")
        yield 500
        grab(box, OUT / "03-consent.png")
        screencapture(OUT / "03-consent-screen.png")
        if isinstance(box, QMessageBox):
            text = box.text()
            (OUT / "consent-text.txt").write_text(text, encoding="utf-8")
            say(f"  consent text length={len(text)} chars, ends with: {text[-60:]!r}")
            # is the label fully shown (not elided/clipped)?
            from PyQt6.QtWidgets import QLabel
            lbl = box.findChild(QLabel, "qt_msgbox_label")
            if lbl is not None:
                say(f"  label size={lbl.width()}x{lbl.height()} sizeHint={lbl.sizeHint().width()}x{lbl.sizeHint().height()} "
                    f"wordWrap={lbl.wordWrap()} visibleRegion.empty={lbl.visibleRegion().isEmpty()}")
            for b in box.buttons():
                fits, need, have = text_fits(b)
                say(f"  button {b.text()!r}: {b.width()}x{b.height()} fits={fits} need={need} have={have} "
                    f"role={box.buttonRole(b)}")
        ok = button_named(box, "Enable the engine")
        say(f"  clicking {'Enable the engine' if ok else 'nothing found!'}")
        SEEN.append((box.windowTitle(), ok.text() if ok else "?"))
        if ok is not None:
            click(ok)
        yield 500
    say(f"  after consent: check={dlg._profile_engine_check.isChecked()} "
        f"accuracy cell visible={dlg._gammap_mode_cell.isVisible()} modal={modal_title(h)}")
    grab(dlg, OUT / "04-prefs-after-consent.png")

    say("step 5: open the Accuracy dropdown")
    combo: QComboBox = dlg._gammap_mode_combo
    say(f"  combo current={combo.currentText()!r} items={[combo.itemText(i) for i in range(combo.count())]}")
    click(combo)
    yield 600
    shot = screencapture(OUT / "05-accuracy-popup-screen.png")
    view = combo.view()
    say(f"  popup visible={view.isVisible()} popup window={view.window().isVisible()}")
    # pick "Maximum accuracy" by clicking the row in the popup list
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    row = combo.findText("Maximum accuracy")
    if view.isVisible():
        r = view.visualRect(combo.model().index(row, 0))
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=r.center())
    else:
        say("  popup not visible — selecting by index (assisted)")
        combo.setCurrentIndex(row)
    yield 400
    say(f"  combo now={combo.currentText()!r} data={combo.currentData()!r}")
    grab(dlg, OUT / "06-prefs-max-accuracy.png")

    say("step 5b: click the Accuracy ⓘ to read its help on screen")
    from ui.tooltip_button import TooltipButton
    tip_btn = dlg._gammap_mode_cell.findChild(TooltipButton)
    click(tip_btn)
    for _ in range(30):
        yield 100
        m = active_modal(h)
        if m is not None and m is not dlg:
            break
    tipdlg = active_modal(h)
    if tipdlg is not None and tipdlg is not dlg:
        yield 400
        grab(tipdlg, OUT / "07-accuracy-help.png")
        screencapture(OUT / "07-accuracy-help-screen.png")
        say(f"  help dialog {tipdlg.windowTitle()!r} size={tipdlg.width()}x{tipdlg.height()} buttons={[b.text() for b in buttons_of(tipdlg)]}")
        b = buttons_of(tipdlg)
        SEEN.append((tipdlg.windowTitle() or "Accuracy help", b[-1].text() if b else "?"))
        if b:
            click(b[-1])
        yield 300

    say("step 6: OK (save and close)")
    bb = dlg.findChild(QDialogButtonBox)
    okb = bb.button(QDialogButtonBox.StandardButton.Ok)
    say(f"  OK button text={okb.text()!r}")
    click(okb)
    for _ in range(50):
        yield 100
        if active_modal(h) is None:
            break
    say(f"  modal after OK: {modal_title(h)}; settings beta={h.settings.get('profile_engine_beta')} "
        f"mode={h.settings.get('gammap_mode')}")
    yield 500

    say("step 7: Build Profile tab is still the current tab — are the rows visible NOW?")
    say(f"  current tab widget is profile: {win._tabs.currentWidget() is prof}; mode={prof._current_mode()}")
    say(f"  rows.isVisible()={rows.isVisible()} isHidden={rows.isHidden()} "
        f"visibleRegion.empty={rows.visibleRegion().isEmpty()} geometry={rows.geometry()}")
    grab(win, OUT / "08-manual-after.png")
    screencapture(OUT / "08-manual-after-screen.png")
    # is each of the four rows actually inside the painted viewport?
    for name in ("_m_spectral_cb", "_m_iccver_combo", "_m_noise_cb", "_m_render_combo"):
        w = getattr(prof, name)
        say(f"  {name}: visible={w.isVisible()} region_empty={w.visibleRegion().isEmpty()} "
            f"global_y={w.mapToGlobal(w.rect().topLeft()).y()} win_h={win.height()}")
    tips = tooltip_bodies(rows)
    (OUT / "engine-row-tooltips.json").write_text(json.dumps(tips, indent=1, ensure_ascii=False), encoding="utf-8")
    say(f"  four-row tooltips captured: {list(tips)}")

    say("step 8: click one row's ⓘ (Spectral physics) on screen")
    tb = rows.findChildren(TooltipButton)[0]
    click(tb)
    for _ in range(30):
        yield 100
        if active_modal(h) is not None:
            break
    td = active_modal(h)
    if td is not None:
        yield 400
        grab(td, OUT / "09-spectral-help.png")
        b = buttons_of(td)
        SEEN.append((td.windowTitle() or "row help", b[-1].text() if b else "?"))
        if b:
            click(b[-1])
        yield 300

    say("step 9: switch to GUIDED — anything engine-ish visible there?")
    h.go_profile_tab("guided")
    yield 400
    grab(win, OUT / "10-guided-after.png")
    say(f"  guided: rows visible={rows.isVisible()} (rows live in the Manual group)")


def main() -> int:
    h = Harness(sandbox("B1"))
    h.boot()
    h.make_project("Real-924", CHART_924)
    h.open_project("Real-924")
    say(f"engine before: beta={h.settings.get('profile_engine_beta')} mode={h.settings.get('gammap_mode')}")
    run_journey(h, journey(h), timeout=600)
    say(f"dialogs I clicked: {SEEN}")
    say(f"harness watchdog answered: {h.modals_answered}")
    say(f"sandbox: {h.sandbox}  out: {OUT}")
    h.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
