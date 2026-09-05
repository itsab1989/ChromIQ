"""B1b — restart on the B1 sandbox (settings.ini already carries the beta
switch + Maximum accuracy from B1's Preferences → OK) and photograph what
the user sees: (a) Build Profile → MANUAL with the panel scrolled so the four
engine rows are in the picture, (b) the Accuracy dropdown POPUP, grabbed as a
top-level widget (``view.window().grab()``) because ``screencapture`` sees
another Space on this machine.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.engine_challenge.harness import Harness            # noqa: E402
from scripts.engine_challenge.drive_B_common import (            # noqa: E402
    WORK_B, active_modal, click, click_tab, grab, run_journey, sandbox, say,
    screencapture)

OUT = WORK_B / "B1"
SEEN: list[tuple[str, str]] = []


def journey(h):
    from PyQt6.QtWidgets import QScrollArea, QDialogButtonBox
    win, prof = h.win, h.win._tab_profile
    say(f"settings after restart: beta={h.settings.get('profile_engine_beta')} mode={h.settings.get('gammap_mode')}")
    h.go_profile_tab("manual")
    yield 500
    rows = prof._m_engine_rows_widget
    say(f"rows visible={rows.isVisible()} region_empty={rows.visibleRegion().isEmpty()}")
    # find the scroll area the Manual panel lives in and bring the rows into view
    p = rows.parent()
    area = None
    while p is not None:
        if isinstance(p, QScrollArea):
            area = p
            break
        p = p.parent()
    say(f"scroll area: {area.__class__.__name__ if area else None} objectName={area.objectName() if area else None}")
    if area is not None:
        area.ensureWidgetVisible(rows, 0, 40)
        yield 400
        sb = area.verticalScrollBar()
        say(f"  scrolled to {sb.value()}/{sb.maximum()}; rows region_empty={rows.visibleRegion().isEmpty()}")
    grab(win, OUT / "11-manual-rows-scrolled.png")
    for name in ("_m_spectral_cb", "_m_iccver_combo", "_m_noise_cb", "_m_render_combo"):
        w = getattr(prof, name)
        say(f"  {name}: region_empty={w.visibleRegion().isEmpty()} text={getattr(w, 'text', lambda: w.currentText())()!r}")

    say("Preferences → Beta → open the Accuracy dropdown, grab the popup widget")
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(0, win._open_settings)
    for _ in range(50):
        yield 100
        if active_modal(h) is not None:
            break
    dlg = active_modal(h)
    click_tab(dlg._tabs, "Beta")
    yield 400
    combo = dlg._gammap_mode_combo
    say(f"  combo shows {combo.currentText()!r} (persisted from B1)")
    click(combo)
    yield 700
    view = combo.view()
    pop = view.window()
    say(f"  popup visible={pop.isVisible()} class={pop.__class__.__name__} size={pop.width()}x{pop.height()}")
    grab(pop, OUT / "12-accuracy-popup-widget.png")
    screencapture(OUT / "12-accuracy-popup-screen.png")
    combo.hidePopup()
    yield 300
    grab(dlg, OUT / "13-prefs-beta-restart.png")
    bb = dlg.findChild(QDialogButtonBox)
    cancel = bb.button(QDialogButtonBox.StandardButton.Cancel)
    SEEN.append((dlg.windowTitle(), cancel.text()))
    click(cancel)
    yield 400
    say(f"modal after Cancel: {active_modal(h)}")


def main() -> int:
    h = Harness(sandbox("B1"))          # SAME sandbox as B1: a restart
    h.boot()
    h.open_project("Real-924")
    run_journey(h, journey(h), timeout=300)
    say(f"dialogs I clicked: {SEEN}; watchdog: {h.modals_answered}")
    say(f"sandbox: {h.sandbox}")
    h.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
