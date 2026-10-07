"""On screen: the preview's indicator as a switch (beta 12 build C, Basti).

Drives the REAL app window (MainWindow, Fusion, the app's filters through
`capture_screens.build_app`) and photographs it with `capture_window` (the
window's own buffer; nothing is raised or activated, the keyboard is handed
back by FocusGiveBack). A PopupWatchdog answers any unscripted question.

The chart pages are loaded straight into the tabs' chart previews (the same
`TiffPreview.load_tiff` the tabs call), from a run folder that holds a
profile, and from one that does not.

    CHROMIQ_SETTINGS_FILE=<report>/driver.ini \\
    python scripts/drive_beta12_c_preview_switch.py <report-dir> <lang> \\
        <run-with-profile> <run-without-profile>

Writes photographs, a frame sequence of the indicator opening and closing,
and result-<lang>.json (states, toggle times, the remembered setting).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

if not os.environ.get("CHROMIQ_SETTINGS_FILE"):
    raise SystemExit("set CHROMIQ_SETTINGS_FILE first: a driver never touches "
                     "the real preferences")

OUT = Path(sys.argv[1])
LANG = sys.argv[2]
WITH_PROFILE = Path(sys.argv[3])
NO_PROFILE = Path(sys.argv[4])
OUT.mkdir(parents=True, exist_ok=True)

from PyQt6.QtCore import QPoint, Qt  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

import capture_screens as CS  # noqa: E402
from onscreen_capture import (PopupWatchdog, _grab_window_id,  # noqa: E402
                              capture_window, window_id_for)

RESULT: dict = {"lang": LANG, "when": time.strftime("%Y-%m-%d %H:%M:%S"),
                "photos": {}, "steps": []}


def note(msg: str) -> None:
    print("   ", msg, flush=True)
    RESULT["steps"].append(msg)


def photo(win, name: str) -> None:
    ok, why = capture_window(win, OUT / name)
    RESULT["photos"][name] = "OK" if ok else f"REFUSED: {why}"
    note(f"photo {name}: {'OK' if ok else 'REFUSED - ' + why}")


def frames(win, chip, name: str, n: int = 14) -> list[str]:
    """Grab the window buffer as fast as it allows while the chip animates."""
    wid = window_id_for(win)
    got = []
    if wid is None:
        return got
    t0 = time.perf_counter()
    for i in range(n):
        QApplication.processEvents()
        p = OUT / f"{name}-{i:02d}.png"
        if _grab_window_id(wid, p):
            got.append(f"{p.name} t={1000 * (time.perf_counter() - t0):.0f}ms "
                       f"w={chip.width()}")
    return got


def hover(chip, on: bool) -> None:
    """The pointer onto the chip, or away. QTest.mouseMove does not reach a
    window macOS has not activated (and the driver never activates one), so
    the Enter / Leave events the window system would send are delivered to
    the chip instead."""
    from PyQt6.QtCore import QEvent, QPointF
    from PyQt6.QtGui import QEnterEvent
    if on:
        p = QPointF(chip.width() - 8, chip.height() / 2)
        QApplication.sendEvent(chip, QEnterEvent(p, p, chip.mapToGlobal(p)))
    else:
        QApplication.sendEvent(chip, QEvent(QEvent.Type.Leave))


def main() -> int:
    settings_seed = CS.AppSettings()
    work = OUT / "work"
    work.mkdir(exist_ok=True)
    for k, v in (("language", LANG), ("appearance", "light"),
                 ("custom_output_path", str(work)),
                 ("restore_last_session", False), ("show_splash", False),
                 ("show_welcome_dialog", False),
                 ("preview_show_device_values", False)):
        settings_seed.set(k, v)
    from core.i18n import install_qt_translator, set_language
    set_language(LANG)
    app = CS.build_app()
    install_qt_translator(app)
    dog = PopupWatchdog(OUT, photograph=True, log=note).start()
    from ui.main_window import MainWindow
    from ui.theme import apply_appearance
    from ui import tiff_preview as TP
    apply_appearance(app, None, "light")
    win = MainWindow(CS.AppSettings())
    win.resize(1500, 950)
    win.show()
    app._chromiq_focus_give_back.give_back()
    CS.pump(2500)
    note(f"window on screen: {win.isVisible()} {win.width()}x{win.height()}")

    pages = sorted(WITH_PROFILE.glob("*.tif"))
    bare = sorted(NO_PROFILE.glob("*.tif"))
    from ui.keyboard_help import BINDINGS
    from PyQt6.QtGui import QKeySequence, QShortcut
    sc = [s for s in win.findChildren(QShortcut)
          if s.key() == QKeySequence(BINDINGS["preview_view"])]
    note(f"Ctrl+Y shortcuts on the main window: {len(sc)}, context "
         f"{[s.context().name for s in sc]}")

    def shortcut_toggle() -> float:
        t = time.perf_counter()
        sc[0].activated.emit()            # the binding's own signal
        QApplication.processEvents()
        return 1000 * (time.perf_counter() - t)

    for mode in ("light", "dark"):
        CS.set_theme(app, win, mode)
        CS.show_tab(win, "print")
        CS.pump(800)
        tab = win._tab_print
        pv = tab._preview
        t = time.perf_counter()
        pv.load_tiff(pages)
        pv._update_display()
        first_ms = 1000 * (time.perf_counter() - t)
        CS.pump(900)
        chip = pv._print_chip
        v = pv.print_view()
        note(f"[{mode}] first render of page 1 as on paper: {first_ms:.0f} ms; "
             f"view {v['icon']} '{v['title']}' switchable={v['switchable']}")
        photo(win, f"{LANG}-{mode}-1-paper-collapsed.png")
        # hover: a synthetic pointer move onto the chip, then away
        hover(chip, True)
        seq = frames(win, chip, f"{LANG}-{mode}-open")
        CS.pump(300)
        note(f"[{mode}] hovered: width {chip.width()} (collapsed "
             f"{chip.collapsed_width()}, expanded {chip.expanded_width()}); "
             f"frames {seq}")
        photo(win, f"{LANG}-{mode}-2-paper-hover.png")
        hover(chip, False)
        seq = frames(win, chip, f"{LANG}-{mode}-close")
        CS.pump(300)
        note(f"[{mode}] pointer away: width {chip.width()}; frames {seq}")
        # the shortcut: device values, then back, then the swaps
        times = [shortcut_toggle()]
        CS.pump(400)
        v = pv.print_view()
        note(f"[{mode}] Ctrl+Y -> {v['icon']} '{v['title']}', setting "
             f"{TP.device_values_chosen()}")
        hover(chip, True)
        CS.pump(400)
        photo(win, f"{LANG}-{mode}-3-device-hover.png")
        hover(chip, False)
        CS.pump(400)
        photo(win, f"{LANG}-{mode}-4-device-collapsed.png")
        # the same choice in Create Chart and Measure
        for key in ("chart", "measure"):
            CS.show_tab(win, key)
            CS.pump(700)
            other = CS.tabs(win)[key]._preview
            other.load_tiff(pages)
            other._update_display()
            CS.pump(500)
            ov = other.print_view() or {}
            note(f"[{mode}] {key} tab shows {ov.get('icon')} "
                 f"'{ov.get('title')}'")
            photo(win, f"{LANG}-{mode}-5-{key}-device.png")
        CS.show_tab(win, "print")
        CS.pump(500)
        for _ in range(6):
            times.append(shortcut_toggle())
        note(f"[{mode}] toggle times ms (first, then cached): "
             f"{[round(x, 1) for x in times]}")
        RESULT.setdefault("toggle_ms", {})[mode] = times
        # click the chip itself (a real mouse click event on the widget)
        before = pv.print_view()["device"]
        QTest.mouseClick(chip, Qt.MouseButton.LeftButton,
                         pos=QPoint(chip.width() - 8, chip.height() // 2))
        CS.pump(400)
        note(f"[{mode}] click on the chip: device {before} -> "
             f"{pv.print_view()['device']}")
        if pv.print_view()["device"]:
            shortcut_toggle()
        # keyboard focus ring (focus INSIDE the app's own window only)
        # Qt gives a widget keyboard focus only inside the ACTIVE window, and
        # the driver never activates one (Basti types elsewhere), so the
        # focus event Tab would bring is delivered to the chip directly.
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QFocusEvent
        QApplication.sendEvent(chip, QFocusEvent(QEvent.Type.FocusIn,
                                                 Qt.FocusReason.TabFocusReason))
        CS.pump(400)
        photo(win, f"{LANG}-{mode}-6-keyboard-focus.png")
        QTest.keyClick(chip, Qt.Key.Key_Space)
        CS.pump(300)
        note(f"[{mode}] Space on the focused chip -> device "
             f"{pv.print_view()['device']}")
        QTest.keyClick(chip, Qt.Key.Key_Return)
        CS.pump(300)
        note(f"[{mode}] Enter -> device {pv.print_view()['device']}")
        QApplication.sendEvent(chip, QFocusEvent(QEvent.Type.FocusOut,
                                                 Qt.FocusReason.TabFocusReason))
        # no profile: the screen icon, a click that does nothing
        pv.load_tiff(bare)
        pv._update_display()
        CS.pump(500)
        hover(chip, True)
        CS.pump(400)
        v = pv.print_view()
        photo(win, f"{LANG}-{mode}-7-no-profile-hover.png")
        did = shortcut_toggle()
        QTest.mouseClick(chip, Qt.MouseButton.LeftButton,
                         pos=QPoint(chip.width() - 8, chip.height() // 2))
        CS.pump(300)
        note(f"[{mode}] no profile: {v['icon']} '{v['title']}' switchable="
             f"{v['switchable']}; after Ctrl+Y and a click the setting is "
             f"{TP.device_values_chosen()} (unchanged)")
        RESULT.setdefault("tooltips", {})[mode] = {
            "no_profile": v["tooltip"]}
        hover(chip, False)
        CS.pump(300)
        pv.load_tiff(pages)
        pv._update_display()
        CS.pump(300)
        RESULT["tooltips"][mode]["paper"] = pv.print_view()["tooltip"]

    RESULT["unexpected_popups"] = dog.unexpected_events()
    RESULT["focus_handed_back"] = app._chromiq_focus_give_back.handed_back
    dog.stop()
    (OUT / f"result-{LANG}.json").write_text(
        json.dumps(RESULT, indent=1, ensure_ascii=False), encoding="utf-8")
    win.close()
    CS.pump(400)
    return 0


if __name__ == "__main__":
    code = main()
    os._exit(code)
