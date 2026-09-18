#!/usr/bin/env python3
"""#182, beta 22: the preset eligibility window, driven in a REAL window.

Knut asked for a button under the Create Chart presets dropdown that opens a
window listing the presets that fulfil the requirements for verification on a
chosen report type and limit set, with the charts suited to verification
highlighted and a reason given for every one that falls short.

What this photographs, all of it through the app's own sequence (build the
real `TabChart`, click the real button, let the real handler open the real
dialog):

1. the Create Chart tab with the new button in place under the dropdown;
2. the window in its BEST case: Full colour check judged against ChromIQ
   default, where every preset answers every row;
3. the window in its WORST case: Full colour check judged against Custom ISO
   12647-7, where NO preset answers every row. This is the case that decided
   the window marks rather than filters, so it is the one that has to be seen;
4. the "Show only the presets made for verification" tick box, narrowing the
   list to the starred charts;
5. the detail pane of a preset that falls short, showing the reason and the
   metric's own lever;
6. a USER preset saved WITHOUT its patch set, which cannot be judged, and what
   the window says about it. The preset is written into the sandboxed presets
   folder by this script, so the case is a real one and not a mock.

TWO PIXEL-IDENTICAL FRAMES of every window, because more than one agent drives
this machine. Run it::

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-presets/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-presets/presets
    python scripts/drive_182_preset_verification_window.py <out-dir>

Never set QT_QPA_PLATFORM=offscreen for this. It is a driver, not a test.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from PyQt6.QtWidgets import QApplication                       # noqa: E402
from onscreen_capture import capture_window, _difference       # noqa: E402


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def twice(app, win, path: Path) -> "tuple[bool, str, float]":
    """Photograph *win* twice; the CLIENT AREA must be identical.

    Lifted from `drive_182_the_five_rows.py`, whose comment records what the
    chrome band and the two rounded corners are and why they are excluded by
    measurement rather than by a widened tolerance.
    """
    other = path.with_name(path.stem + "__retake.png")
    ok1 = why1 = ok2 = why2 = None
    for _ in range(3):
        ok1, why1 = capture_window(win, path)
        if ok1:
            break
        pump(app, 900)
    if not ok1:
        return False, str(why1), -1.0
    pump(app, 1300)
    for _ in range(3):
        ok2, why2 = capture_window(win, other)
        if ok2:
            break
        pump(app, 900)
    if not ok2:
        return False, f"the retake failed: {why2}", -1.0
    d = _difference(path, other)
    if d <= 0.0:
        other.unlink(missing_ok=True)
        return True, "the two frames are identical", d
    from PyQt6.QtGui import QImage
    a, b = QImage(str(path)), QImage(str(other))
    xs, ys, n = [], [], 0
    for y in range(a.height()):
        for x in range(a.width()):
            if a.pixel(x, y) != b.pixel(x, y):
                n += 1
                xs.append(x)
                ys.append(y)
    g, fg = win.geometry(), win.frameGeometry()
    r = win.devicePixelRatioF()
    top = int(round((g.y() - fg.y()) * r))
    left = int(round((g.x() - fg.x()) * r))
    right = a.width() - int(round((fg.right() - g.right()) * r))
    bottom = a.height() - 24
    below = [(x, y) for x, y in zip(xs, ys)
             if top <= y < bottom and left <= x < right]
    other.unlink(missing_ok=True)
    if below:
        box = (min(x for x, _ in below), min(y for _, y in below),
               max(x for x, _ in below), max(y for _, y in below))
        return False, (f"{len(below)} pixels differ INSIDE the client area, "
                       f"box {box}"), d
    return True, (f"the client area is identical; {n} chrome pixels differ"), d


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    record: dict = {"frames": {}, "measured": {}}

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    # A USER PRESET WITH NO PATCH SET, written into the sandboxed store so the
    # window meets the real case rather than a mock of it.
    from core.preset_store import save_presets, tab_dir
    save_presets("create_chart", {
        "Settings only, no chart": {"auto_run": False, "attached_ti1": False},
    })
    print(f"user preset written to {tab_dir('create_chart')}", flush=True)

    from core.settings import AppSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from ui.tabs.tab_chart import TabChart

    settings = AppSettings()
    tab = TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    tab.resize(1280, 900)
    tab.setWindowTitle("ChromIQ — Create Chart")
    tab.show()
    pump(app, 1600)

    # -- 1. the button is there, under the dropdown -----------------------
    # The presets group lives in MANUAL mode, which is where Knut asked for the
    # button. Guided hides the whole panel, and a widget in a hidden panel has
    # no laid-out position: the first run of this driver measured the button at
    # y=115 against a dropdown at y=144 for exactly that reason.
    tab._manual_btn.click()
    pump(app, 1200)
    btn = tab._preset_verify_btn
    combo = tab._preset_combo
    from ui.fade_scroll import FadeScrollArea
    host = btn.parent()
    while host is not None and not isinstance(host, FadeScrollArea):
        host = host.parent()
    if host is not None:
        host.ensureWidgetVisible(btn, 0, 80)
        pump(app, 900)
    bg = btn.mapTo(tab, btn.rect().topLeft())
    cg = combo.mapTo(tab, combo.rect().bottomLeft())
    record["measured"]["button_text"] = btn.text()
    record["measured"]["button_is_below_the_dropdown"] = bool(bg.y() >= cg.y())
    record["measured"]["button_top_y"] = bg.y()
    record["measured"]["dropdown_bottom_y"] = cg.y()
    print(f"button {btn.text()!r} top y={bg.y()}, dropdown bottom y={cg.y()}",
          flush=True)
    assert record["measured"]["button_is_below_the_dropdown"], (
        "the button is NOT below the dropdown")
    ok, why, d = twice(app, tab, out / "1-the-button-under-the-dropdown.png")
    record["frames"]["1-the-button-under-the-dropdown.png"] = [ok, why, d]
    print("  frame 1:", ok, why, flush=True)

    # -- open it through the app's own handler ----------------------------
    from ui.dialogs.preset_verification_dialog import PresetVerificationDialog
    opened: list = []
    orig_exec = PresetVerificationDialog.exec

    def _no_block(self):
        opened.append(self)
        self.show()
        return 0
    PresetVerificationDialog.exec = _no_block
    try:
        btn.click()                       # the real click, the real handler
        pump(app, 1500)
    finally:
        PresetVerificationDialog.exec = orig_exec
    assert opened, "the button did not open the window"
    dlg = opened[0]
    dlg.resize(1100, 720)
    pump(app, 800)

    def choose(type_id: str, set_id: str) -> None:
        dlg._type_combo.setCurrentIndex(dlg._type_combo.findData(type_id))
        dlg._set_combo.setCurrentIndex(dlg._set_combo.findData(set_id))
        pump(app, 700)

    def counted() -> dict:
        rows = dlg._rows
        return {"listed": len(rows),
                "starred": sum(1 for r in rows if r.starred),
                "complete": sum(1 for r in rows
                                if r.assessment.answers_everything),
                "unchecked": sum(1 for r in rows if not r.assessment.checked),
                "rows_asked": len(dlg._rows[0].assessment.asked)}

    # -- 2. the best case -------------------------------------------------
    choose("t2_full_colour_check", "chromiq_default")
    record["measured"]["best_case"] = counted()
    print("  best case:", counted(), flush=True)
    ok, why, d = twice(app, dlg, out / "2-best-case-chromiq-default.png")
    record["frames"]["2-best-case-chromiq-default.png"] = [ok, why, d]
    print("  frame 2:", ok, why, flush=True)

    # -- 3. the worst case ------------------------------------------------
    choose("t2_full_colour_check", "custom_iso_12647_7")
    record["measured"]["worst_case"] = counted()
    print("  worst case:", counted(), flush=True)
    # Select a preset so the detail pane shows the reasons in the same frame.
    top = dlg._tree.topLevelItem(0)
    if top is not None and top.childCount():
        dlg._tree.setCurrentItem(top.child(0))
        pump(app, 500)
        row = top.child(0).data(0, 0x0100)
        record["measured"]["worst_case_example"] = {
            "preset": row.label,
            "answered": list(row.assessment.answered),
            "missing": [list(m) for m in row.assessment.missing],
        }
        print("  worst-case example:",
              record["measured"]["worst_case_example"], flush=True)
    ok, why, d = twice(app, dlg, out / "3-worst-case-custom-iso-12647-7.png")
    record["frames"]["3-worst-case-custom-iso-12647-7.png"] = [ok, why, d]
    print("  frame 3:", ok, why, flush=True)

    # -- 4. only the starred ----------------------------------------------
    dlg._only_star.setChecked(True)
    pump(app, 800)
    record["measured"]["only_starred_visible"] = sum(
        dlg._tree.topLevelItem(i).childCount()
        for i in range(dlg._tree.topLevelItemCount()))
    print("  starred rows visible:",
          record["measured"]["only_starred_visible"], flush=True)
    ok, why, d = twice(app, dlg, out / "4-only-the-starred.png")
    record["frames"]["4-only-the-starred.png"] = [ok, why, d]
    print("  frame 4:", ok, why, flush=True)
    dlg._only_star.setChecked(False)
    pump(app, 600)

    # -- 5. the user preset with no patch set ------------------------------
    target = None
    for i in range(dlg._tree.topLevelItemCount()):
        head = dlg._tree.topLevelItem(i)
        for j in range(head.childCount()):
            r = head.child(j).data(0, 0x0100)
            if r is not None and not r.assessment.checked:
                target = head.child(j)
                break
        if target is not None:
            break
    if target is not None:
        dlg._tree.scrollToItem(target)
        dlg._tree.setCurrentItem(target)
        pump(app, 600)
        record["measured"]["unjudgeable_preset"] = \
            target.data(0, 0x0100).label
        print("  unjudgeable preset:",
              record["measured"]["unjudgeable_preset"], flush=True)
        ok, why, d = twice(app, dlg, out / "5-a-preset-with-no-patch-set.png")
        record["frames"]["5-a-preset-with-no-patch-set.png"] = [ok, why, d]
        print("  frame 5:", ok, why, flush=True)
    else:
        record["measured"]["unjudgeable_preset"] = None
        print("  NO unjudgeable preset was found", flush=True)

    # -- 6. the report type that judges nothing ----------------------------
    choose("t4_printing_record", "custom_iso_12647_7")
    record["measured"]["record_type"] = counted()
    print("  printing record:", counted(), flush=True)
    ok, why, d = twice(app, dlg, out / "6-a-report-type-that-judges-nothing.png")
    record["frames"]["6-a-report-type-that-judges-nothing.png"] = [ok, why, d]
    print("  frame 6:", ok, why, flush=True)

    (out / "measured.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    bad = [k for k, v in record["frames"].items() if not v[0]]
    print("\nframes refused:", bad or "none", flush=True)
    dlg.close()
    tab.close()
    pump(app, 400)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
