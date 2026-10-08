"""On screen: Simulate paper white inside the preview's indicator (beta 14).

Drives the REAL app window (MainWindow, Fusion, the app's filters through
`capture_screens.build_app`) and photographs it with `capture_window` (the
window's own buffer; nothing is raised or activated, the keyboard is handed
back by FocusGiveBack). A PopupWatchdog answers any unscripted question.

The chart pages are loaded straight into the tabs' chart previews (the same
`TiffPreview.load_tiff` the tabs call), from COPIES of run folders in the
report folder: one with a profile, one without, and a verification chart
printed through the profile.

    CHROMIQ_SETTINGS_FILE=<report>/driver.ini \\
    python scripts/drive_beta14_paper_white.py <report-dir> <lang> \\
        <run-with-profile> <run-without-profile> [<verification-folder>]

Writes photographs, crops of the open indicator, the paper colour measured
in each photograph, and result-<lang>.json.
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
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
VERIFY = Path(sys.argv[5]) if len(sys.argv) > 5 else None
OUT.mkdir(parents=True, exist_ok=True)

from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt  # noqa: E402
from PyQt6.QtGui import QEnterEvent, QFocusEvent  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

import capture_screens as CS  # noqa: E402
from onscreen_capture import PopupWatchdog, capture_window  # noqa: E402

RESULT: dict = {"lang": LANG, "when": time.strftime("%Y-%m-%d %H:%M:%S"),
                "photos": {}, "steps": [], "paper": {}}


def note(msg: str) -> None:
    print("   ", msg, flush=True)
    RESULT["steps"].append(msg)


def _rect_in_photo(win, widget, png_size) -> "tuple[int, int, int, int]":
    """*widget*'s rectangle in a photograph of *win* (which may be 2x, and
    carries the title bar above the client area)."""
    from PIL import Image  # noqa: F401
    pw, ph = png_size
    sx = pw / max(1, win.frameGeometry().width())
    top = win.frameGeometry().height() - win.height()      # title bar
    o = widget.mapTo(win, QPoint(0, 0))
    x0 = int(o.x() * sx)
    y0 = int((o.y() + top) * sx)
    return (x0, y0, int(x0 + widget.width() * sx),
            int(y0 + widget.height() * sx))


def photo(win, name: str, pv=None, chip=None) -> None:
    p = OUT / name
    ok, why = capture_window(win, p)
    RESULT["photos"][name] = "OK" if ok else f"REFUSED: {why}"
    note(f"photo {name}: {'OK' if ok else 'REFUSED - ' + why}")
    if not ok:
        return
    from PIL import Image
    with Image.open(p) as im:
        im = im.convert("RGB")
        if pv is not None:
            # the image area: its most frequent colour is the paper (the
            # page's blank margin and the frame round it)
            box = _rect_in_photo(win, pv._img_label, im.size)
            area = im.crop(box)
            small = area.resize((max(1, area.width // 4),
                                 max(1, area.height // 4)), Image.NEAREST)
            common = Counter(list(small.get_flattened_data()) if hasattr(small, "get_flattened_data") else small.getdata()).most_common(3)
            RESULT["paper"][name] = {
                "most_common_in_image_area": [[list(c), n] for c, n in common],
                "frame_colour_set": pv._frame_color.name(),
            }
            note(f"  measured in {name}: most common colour in the image "
                 f"area {list(common[0][0])} ({common[0][1]} samples); "
                 f"frame colour set {pv._frame_color.name()}")
        if chip is not None and chip.isVisible():
            box = _rect_in_photo(win, chip, im.size)
            pad = 12
            crop = im.crop((max(0, box[0] - pad), max(0, box[1] - pad),
                            box[2] + pad, box[3] + pad))
            crop = crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS)
            crop.save(OUT / name.replace(".png", "-chip.png"))


def hover(chip, on: bool) -> None:
    """The pointer onto the chip, or away (synthetic: the driver never
    activates the window, so the window system's Enter/Leave are delivered
    to the chip directly, as in the beta-12 driver)."""
    if on:
        pt = QPointF(chip.width() - 8, chip.height() / 2)
        QApplication.sendEvent(chip, QEnterEvent(pt, pt, chip.mapToGlobal(pt)))
    else:
        QApplication.sendEvent(chip, QEvent(QEvent.Type.Leave))


def main() -> int:
    seed = CS.AppSettings()
    work = OUT / "work"
    work.mkdir(exist_ok=True)
    for k, v in (("language", LANG), ("appearance", "light"),
                 ("custom_output_path", str(work)),
                 ("restore_last_session", False), ("show_splash", False),
                 ("show_welcome_dialog", False),
                 ("preview_show_device_values", False),
                 ("preview_simulate_paper_white", False)):
        seed.set(k, v)
    from core.i18n import install_qt_translator, set_language
    set_language(LANG)
    app = CS.build_app()
    install_qt_translator(app)
    dog = PopupWatchdog(OUT, photograph=True, log=note).start()
    from ui.main_window import MainWindow
    from ui.theme import apply_appearance
    from ui import tiff_preview as TP
    from workflow import print_preview as PP
    apply_appearance(app, None, "light")
    win = MainWindow(CS.AppSettings())
    win.resize(1500, 950)
    win.show()
    app._chromiq_focus_give_back.give_back()
    CS.pump(2500)
    note(f"window on screen: {win.isVisible()} {win.width()}x{win.height()}")

    pages = sorted(WITH_PROFILE.glob("*.tif"))
    bare = sorted(NO_PROFILE.glob("*.tif"))
    bin_dir = TP.TiffPreview._argyll_bin_with("cctiff")

    for mode in ("light", "dark"):
        CS.set_theme(app, win, mode)
        CS.show_tab(win, "print")
        CS.pump(800)
        pv = win._tab_print._preview
        pv.load_tiff(pages)
        pv._update_display()
        CS.pump(900)
        chip = pv._print_chip
        v = pv.print_view()
        note(f"[{mode}] page as on paper: '{v['title']}', paper white "
             f"{v['paper_white']}, setting {TP.paper_white_chosen()}")
        photo(win, f"{LANG}-{mode}-1-off-collapsed.png", pv)
        hover(chip, True)
        CS.pump(500)
        btn = chip.paper_white_button()
        note(f"[{mode}] hovered: chip {chip.width()} px, button visible "
             f"{btn.isVisible()} at {btn.geometry().getRect()}, checked "
             f"{btn.isChecked()}, name '{btn.accessibleName()}'")
        photo(win, f"{LANG}-{mode}-2-off-hover.png", pv, chip)
        # a real mouse click on the button inside the open chip
        dev_before = TP.device_values_chosen()
        t = time.perf_counter()
        QTest.mouseClick(btn, Qt.MouseButton.LeftButton,
                         pos=QPoint(btn.width() // 2, btn.height() // 2))
        on_ms = 1000 * (time.perf_counter() - t)
        CS.pump(600)
        v = pv.print_view()
        paper = PP.paper_colour(PP.plan_for_page(pages[0], bin_dir=bin_dir),
                                bin_dir)
        note(f"[{mode}] click on Paper white ({on_ms:.0f} ms): setting "
             f"{TP.paper_white_chosen()}, view device {v['device']} (was "
             f"{dev_before}), button checked {btn.isChecked()}, chip name "
             f"'{chip.accessibleName()}', profile's paper colour {paper}")
        photo(win, f"{LANG}-{mode}-3-on-hover.png", pv, chip)
        hover(chip, False)
        CS.pump(500)
        photo(win, f"{LANG}-{mode}-4-on-collapsed.png", pv)
        # switching back and forth: kept renderings
        times = []
        for want in (False, True, False, True):
            t = time.perf_counter()
            pv.set_paper_white(want)
            QApplication.processEvents()
            times.append(round(1000 * (time.perf_counter() - t), 1))
        note(f"[{mode}] switch times off/on/off/on (kept): {times} ms")
        RESULT.setdefault("switch_ms", {})[mode] = {"first_on": on_ms,
                                                    "kept": times}
        # the same choice in Create Chart and Measure
        for key in ("chart", "measure"):
            CS.show_tab(win, key)
            CS.pump(700)
            other = CS.tabs(win)[key]._preview
            other.load_tiff(pages)
            other._update_display()
            CS.pump(600)
            ov = other.print_view() or {}
            note(f"[{mode}] {key} tab: paper white {ov.get('paper_white')}, "
                 f"frame {other._frame_color.name()}")
            photo(win, f"{LANG}-{mode}-5-{key}-on.png", other)
        CS.show_tab(win, "print")
        CS.pump(500)
        # keyboard: the chip opens on Tab focus and shows the button
        QApplication.sendEvent(chip, QFocusEvent(
            QEvent.Type.FocusIn, Qt.FocusReason.TabFocusReason))
        CS.pump(500)
        note(f"[{mode}] chip with Tab focus: open {chip.is_open()}, button "
             f"visible {btn.isVisible()}")
        photo(win, f"{LANG}-{mode}-6-keyboard-open.png", pv, chip)
        QApplication.sendEvent(chip, QFocusEvent(
            QEvent.Type.FocusOut, Qt.FocusReason.TabFocusReason))
        CS.pump(300)
        # device values: no button
        pv.toggle_print_view()
        CS.pump(500)
        hover(chip, True)
        CS.pump(500)
        v = pv.print_view()
        note(f"[{mode}] device values: paper white {v['paper_white']}, "
             f"button visible {btn.isVisible()}, frame "
             f"{pv._frame_color.name()}")
        photo(win, f"{LANG}-{mode}-7-device-hover.png", pv, chip)
        hover(chip, False)
        pv.toggle_print_view()
        CS.pump(400)
        # no profile: no button
        pv.load_tiff(bare)
        pv._update_display()
        CS.pump(500)
        hover(chip, True)
        CS.pump(500)
        v = pv.print_view()
        note(f"[{mode}] no profile: '{v['title']}', paper white "
             f"{v['paper_white']}, button visible {btn.isVisible()}")
        photo(win, f"{LANG}-{mode}-8-no-profile-hover.png", pv, chip)
        hover(chip, False)
        CS.pump(300)
        # a verification chart printed through the profile
        if VERIFY is not None:
            vpages = sorted(VERIFY.glob("*-verify*.tif"))
            plan = PP.plan_for_page(vpages[0], bin_dir=bin_dir)
            pv.load_tiff(vpages)
            pv._update_display()
            CS.pump(800)
            v = pv.print_view()
            note(f"[{mode}] verification page: plan {plan.kind} "
                 f"(intent {plan.intent}, source "
                 f"{Path(plan.source_profile).name}), '{v['title']}', "
                 f"paper white {v['paper_white']}, frame "
                 f"{pv._frame_color.name()}")
            photo(win, f"{LANG}-{mode}-9-verification-on.png", pv)
            pv.set_paper_white(False)
            CS.pump(500)
            photo(win, f"{LANG}-{mode}-9-verification-off.png", pv)
            pv.set_paper_white(True)
            CS.pump(300)
        # back to off for the next appearance
        pv.load_tiff(pages)
        pv._update_display()
        pv.set_paper_white(False)
        CS.pump(400)
        RESULT.setdefault("tooltips", {})[mode] = {
            "chip_off": chip.toolTip(), "button_off": btn.toolTip()}

    RESULT["unexpected_popups"] = dog.unexpected_events()
    RESULT["focus_handed_back"] = app._chromiq_focus_give_back.handed_back
    RESULT["setting_at_end"] = TP.paper_white_chosen()
    dog.stop()
    (OUT / f"result-{LANG}.json").write_text(
        json.dumps(RESULT, indent=1, ensure_ascii=False), encoding="utf-8")
    win.close()
    CS.pump(400)
    return 0


if __name__ == "__main__":
    code = main()
    os._exit(code)
