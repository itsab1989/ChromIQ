"""Knut's Patch Set editor batch (#182), reproduced and re-photographed in the
REAL app, in a REAL window.

His report, on the editor's **Add** window:

  * the bottom checkboxes overlap and "Ensure unique colours" cannot be clicked
  * "Fill remaining gaps" shows 0 while the fill-to value is above the total
  * "Pure white & black" with each=2 shows 2 while the chart grows by 4

Usage:  python scripts/drive_182_add_window_counts.py [out_dir] [chart.ti2]
"""
from __future__ import annotations

import os
import shutil
import signal
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

HARD_STOP_S = 240


def _arm_hard_stop() -> None:
    def _die() -> None:
        print(f"\n!! hard stop after {HARD_STOP_S}s", flush=True)
        os.kill(os.getpid(), signal.SIGKILL)
    t = threading.Timer(HARD_STOP_S, _die)
    t.daemon = True
    t.start()


_arm_hard_stop()

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else
           Path.home() / "Desktop/ChromIQ-beta21-proof/knut-patchset-editor-batch")
SRC_TI2 = Path(sys.argv[2] if len(sys.argv) > 2 else
               Path.home() / "ChromIQ/ChromIQ-Update/runs/run1/ChromIQ-Update.ti2")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    shots = OUT / "shots"
    shots.mkdir(exist_ok=True)

    # The chart is COPIED: an on-screen driver may never write in the owner's
    # own project folder.
    work = Path(tempfile.mkdtemp(prefix="add-counts-"))
    chart = work / SRC_TI2.name
    shutil.copy2(SRC_TI2, chart)

    from PyQt6.QtCore import QSettings as _QS
    from PyQt6.QtGui import QFontDatabase
    from PyQt6.QtWidgets import QApplication

    from core.freetype_bootstrap import ensure_freetype_library
    ensure_freetype_library()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    app.setOrganizationName("ChromIQ")

    from core.resource_path import resource_path
    from ui.styles import WinButtonLayoutStyle
    from ui.theme import apply_appearance
    from ui.widgets import (ButtonFontFilter, DialogFocusFilter,
                            GroupBoxSurfaceFilter, TooltipWrapFilter)
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    for F in (ButtonFontFilter, GroupBoxSurfaceFilter, TooltipWrapFilter,
              DialogFocusFilter):
        app.installEventFilter(F(app))

    import core.settings as cs
    ini = Path(tempfile.mkdtemp(prefix="chromiq-drive-")) / "drive.ini"
    cs.QSettings = lambda *a, **k: _QS(str(ini), _QS.Format.IniFormat)
    s = cs.AppSettings()
    s.set("custom_output_path", str(work))
    apply_appearance(app, None, "light")

    from scripts.onscreen_capture import capture_window
    from ui.dialogs.ti2_relayout_dialog import _AddPatchesDialog
    from workflow.ti2_relayout import load_rgb_program
    import workflow.patch_generators as G

    existing = load_rgb_program(chart)
    w, b = G.count_white_black(existing)
    lines: list[str] = []

    def say(msg: str = "") -> None:
        print(msg, flush=True)
        lines.append(msg)

    say(f"chart   : {chart.name}")
    say(f"patches : {len(existing)}   pure white {w}, pure black {b}")

    dlg = _AddPatchesDialog(s, None, existing_patches=existing)
    dlg.resize(1360, 900)
    dlg.show()
    for _ in range(80):
        app.processEvents()
    dlg._add_mode_gen.setChecked(True)
    dlg._refresh_add_mode()

    # Knut's own selection, as far as this chart allows: the cube, the corners,
    # skin tones and the two grey sets, unique colours ON.
    for n in dlg._GEN_CHECKS:
        if n != "unique":
            getattr(dlg, f"_gen_{n}").setChecked(False)
    dlg._gen_unique.setChecked(True)
    dlg._gen_cube.setChecked(True)
    dlg._gen_cube_n.setValue(7)
    dlg._gen_corners.setChecked(True)
    dlg._gen_corners_edge.setValue(2)
    dlg._gen_skin.setChecked(True)
    dlg._gen_skin_n.setValue(3)
    dlg._gen_skin_ranges.setValue(2)
    dlg._gen_neutral.setChecked(True)
    dlg._gen_neutral_n.setValue(20)
    dlg._gen_nearneutral.setChecked(True)
    dlg._gen_nearneutral_n.setValue(20)
    dlg._gen_nearneutral_off.setValue(6)
    dlg._gen_whiteblack_n.setValue(2)
    dlg._gen_fill.setChecked(True)
    dlg._gen_fill_to.setValue(len(existing))      # the recipe's own figure

    def settle(seconds: float = 1.2) -> None:
        """Let the 300 ms preview debounce fire and the window repaint."""
        end = time.time() + seconds
        while time.time() < end:
            app.processEvents()
            time.sleep(0.02)

    def shot(name: str) -> None:
        ok, why = capture_window(dlg, shots / f"{name}.png")
        say(f"  photograph {name}: {'taken' if ok else 'REFUSED: ' + why}")

    def state(tag: str) -> None:
        say(f"\n{tag}")
        say(f"  white & black row : {dlg._gen_whiteblack_count.text()!r}"
            f"   (strike-through: "
            f"{dlg._gen_whiteblack_count.font().strikeOut()})")
        say(f"  fill row          : {dlg._gen_fill_count.text()!r}")
        say(f"  fill row label    : {dlg._gen_fill_prefix.text()!r}")
        say(f"  {dlg._gen_total.text()}")
        say(f"  {dlg._gen_after_total.text()}")

    # --- the overlap ------------------------------------------------------
    settle()
    uniq = dlg._gen_unique.geometry()
    after = dlg._gen_after_total.geometry()
    panel = dlg._gen_unique.parentWidget()
    hit = panel.childAt(uniq.center())
    say("\n--- 1. the two bottom rows ---")
    say(f"  'Ensure unique colours'  : {uniq.getRect()}")
    say(f"  'Chart after adding'     : {after.getRect()}")
    say(f"  they overlap             : {uniq.intersects(after)}")
    say(f"  widget under the checkbox: {type(hit).__name__} "
        f"{getattr(hit, 'text', lambda: '')()!r}")
    say(f"  the checkbox can be clicked: {hit is dlg._gen_unique}")

    # And really click it, twice, through the widget's own hit path.
    from PyQt6.QtCore import QPoint, Qt
    from PyQt6.QtTest import QTest
    # The click lands where a user clicks a checkbox: on the box and its
    # label, which is what QStyle.SE_CheckBoxClickRect covers. (The empty
    # space to the right of the text is NOT the button, in any style.)
    from PyQt6.QtWidgets import QStyle, QStyleOptionButton
    opt = QStyleOptionButton()
    dlg._gen_unique.initStyleOption(opt)
    click_rect = dlg._gen_unique.style().subElementRect(
        QStyle.SubElement.SE_CheckBoxClickRect, opt, dlg._gen_unique)
    say(f"  the style's click area   : {click_rect.getRect()}")
    before = dlg._gen_unique.isChecked()
    QTest.mouseClick(dlg._gen_unique, Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, click_rect.center())
    settle(0.4)
    toggled = dlg._gen_unique.isChecked() != before
    QTest.mouseClick(dlg._gen_unique, Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, click_rect.center())
    settle(0.4)
    say(f"  a real click toggles it  : {toggled}, and back: "
        f"{dlg._gen_unique.isChecked() == before}")
    # ...and the window server agrees the checkbox owns those pixels: the
    # widget under the click point, in the panel's own coordinates.
    hit2 = panel.childAt(uniq.topLeft() + click_rect.center())
    say(f"  widget under that point  : {type(hit2).__name__} "
        f"{getattr(hit2, 'text', lambda: '')()!r}")

    # --- the counts -------------------------------------------------------
    dlg._gen_whiteblack.setChecked(False)
    settle()
    before_total = len(dlg._build_generated_program())
    state("--- 2. 'Pure white & black' UNticked, each = 2 ---")
    say(f"  the build really holds   : {before_total} patches")
    shot("01-white-black-off")

    dlg._gen_whiteblack.setChecked(True)
    settle()
    after_total = len(dlg._build_generated_program())
    state("--- 3. 'Pure white & black' ticked, each = 2 ---")
    say(f"  the build really holds   : {after_total} patches "
        f"(+{after_total - before_total})")
    shot("02-white-black-on")

    row = dlg._gen_whiteblack_count.text()
    grew = after_total - before_total
    say(f"\n  KNUT'S FAULT: row says {row!r}, the chart grew by {grew}. "
        f"{'AGREE' if str(grew) in row else 'DISAGREE'}")

    # --- the fill target --------------------------------------------------
    state("--- 4. 'Fill remaining gaps' to the chart's own size ---")
    # Above the WHOLE chart, which is the existing patches plus the sets: the
    # figure the "Chart after adding" line underneath shows.
    target = len(existing) + len(dlg._build_generated_program()) + 250
    dlg._gen_fill_to.setValue(target)
    settle()
    state(f"--- 5. ...and raised to {target}, 250 above the finished chart ---")
    say(f"  the build really holds   : {len(dlg._build_generated_program())}")
    shot("03-fill-raised")

    (OUT / "RESULT.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    say(f"\nwritten: {OUT / 'RESULT.txt'}")
    dlg.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
