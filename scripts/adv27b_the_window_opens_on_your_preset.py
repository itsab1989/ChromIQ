#!/usr/bin/env python3
"""Round 27b: the window opens on the preset you chose, and the button's height.

Two things proved in one real window:

* a built-in preset is chosen in the Create Chart pulldown, the real button is
  pressed, and the window is photographed — the row it opens on must be that
  preset, scrolled into view, with its detail pane filled;
* the button's height is photographed beside beta 22's own button (same label,
  no size rule) so the two can be compared in a picture and not only in a
  number.

    python scripts/adv27b_the_window_opens_on_your_preset.py <out-dir>
"""
from __future__ import annotations

import json
import os
import shutil
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

from PyQt6.QtCore import Qt                                    # noqa: E402
from PyQt6.QtWidgets import QPushButton                        # noqa: E402

from adv27b_the_preset_button import app_like_main, pump        # noqa: E402
from drive_182_preset_verification_window import twice          # noqa: E402

WORK = Path("/tmp/chromiq-r27b/work-p")


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else
               Path.home() / "Desktop/ChromIQ-beta23-proof/round-27b-chart")
    shots = out / "shots"
    shots.mkdir(parents=True, exist_ok=True)
    assert "/tmp/" in os.environ.get("CHROMIQ_SETTINGS_FILE", ""), "SANDBOX"
    assert "/tmp/" in os.environ.get("CHROMIQ_PRESETS_DIR", ""), "SANDBOX"
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)

    app = app_like_main()
    from core.settings import AppSettings
    s = AppSettings()
    s.set("custom_output_path", str(WORK))
    from core.file_manager import Project
    from core.measurement_target import RUN_TYPE_VERIFICATION
    from ui.main_window import MainWindow
    proj = WORK / "R27b-P"
    Project.create(proj, "R27b-P").current_run().ensure_dir()
    win = MainWindow(s)
    win.resize(1500, 1020)
    win.show()
    pump(app, 1400)
    win._file_mgr.open_project_at(proj)
    win._target_ctl.changed.emit()
    pump(app, 700)
    tab = win._tab_chart
    win._tabs.setCurrentIndex(win._tabs.indexOf(tab))
    pump(app, 600)
    tab._manual_btn.click()
    pump(app, 800)
    win._target_ctl.set_run_type(RUN_TYPE_VERIFICATION)
    pump(app, 900)

    rec: dict = {"when": time.strftime("%Y-%m-%d %H:%M:%S")}
    log: "list[str]" = ["# round 27b — the window opens on your preset", "",
                        f"driven {rec['when']}",
                        "mode: ON SCREEN, a real window, capture_window by id",
                        ""]

    def say(x=""):
        print(x, flush=True)
        log.append(x)

    # ---- the height, photographed side by side ---------------------------
    from ui.fade_scroll import FadeScrollArea
    host = tab._preset_verify_btn.parent()
    while host is not None and not isinstance(host, FadeScrollArea):
        host = host.parent()
    if host is not None:
        host.ensureWidgetVisible(tab._preset_combo, 0, 120)
        pump(app, 700)
    row = tab._preset_verify_btn.parentWidget().layout()
    vr = None
    for i in range(row.count()):
        it = row.itemAt(i)
        if it.layout() is not None and it.layout().indexOf(
                tab._preset_verify_btn) >= 0:
            vr = it.layout()
    old = QPushButton(tab._preset_verify_btn.text(),
                      tab._preset_verify_btn.parentWidget())
    vr.insertWidget(1, old)
    old.show()
    pump(app, 900)
    say("## the height, in a picture")
    say("")
    say(f"    shipped now        : {tab._preset_verify_btn.height()} px "
        f"(left in the photograph)")
    say(f"    beta 22's button   : {old.height()} px (right)")
    rec["shipped_h"] = tab._preset_verify_btn.height()
    rec["beta22_h"] = old.height()
    ok, why, d = twice(app, win, shots / "05-height-after-the-fix.png")
    say(f"    photograph 05-height-after-the-fix.png: "
        f"{'kept' if ok else 'REFUSED: ' + why} (differ by {d} %)")
    rec["height_frame"] = [ok, why, d]
    vr.removeWidget(old)
    old.setParent(None)
    old.deleteLater()
    pump(app, 600)

    # ---- pick a real preset and press the real button --------------------
    combo = tab._preset_combo
    want = None
    for i in range(combo.count()):
        if combo.itemData(i) and combo.model().item(i).isEnabled():
            want = i
            break
    assert want is not None, "no selectable preset in the pulldown"
    combo.setCurrentIndex(want)
    pump(app, 1400)
    say("")
    say("## the window opens on the preset the pulldown is on")
    say("")
    say(f"    the pulldown is on : {combo.currentText()!r} "
        f"(userData {combo.currentData()!r})")
    rec["combo_text"] = combo.currentText()
    rec["combo_data"] = str(combo.currentData())
    rec["chosen_label"] = tab._chosen_preset_label()
    say(f"    the tab resolves it to the window's row label: "
        f"{rec['chosen_label']!r}")

    from ui.dialogs import preset_verification_dialog as PVD
    opened: list = []
    orig = PVD.PresetVerificationDialog.exec

    def _no_block(self):
        opened.append(self)
        self.show()
        return 0
    PVD.PresetVerificationDialog.exec = _no_block
    try:
        t = time.perf_counter()
        tab._preset_verify_btn.click()
        el = time.perf_counter() - t
        pump(app, 1200)
        assert opened, "the button did not open the window"
        dlg = opened[0]
        dlg.resize(1180, 760)
        pump(app, 900)
        cur = dlg._tree.currentItem()
        picked = cur.text(0) if cur is not None else None
        rect = dlg._tree.visualItemRect(cur) if cur is not None else None
        in_view = bool(rect is not None and rect.height() > 0
                       and dlg._tree.viewport().rect().intersects(rect))
        detail = []
        for i in range(dlg._detail_layout.count()):
            w = dlg._detail_layout.itemAt(i).widget()
            if w is not None and hasattr(w, "text"):
                detail.append(w.text())
        say(f"    click -> window in {el*1000:.0f} ms")
        say(f"    the window opens with this row selected: {picked!r}")
        say(f"    that row is scrolled into view            : {in_view}")
        say(f"    the detail pane's first line              : "
            f"{detail[0] if detail else '(empty)'}")
        rec.update({"open_ms": round(el * 1000), "selected_row": picked,
                    "row_in_view": in_view, "detail_first": detail[:3]})
        ok2, why2, d2 = twice(app, dlg, shots / "06-opens-on-your-preset.png")
        say(f"    photograph 06-opens-on-your-preset.png: "
            f"{'kept' if ok2 else 'REFUSED: ' + why2} (differ by {d2} %)")
        rec["frame"] = [ok2, why2, d2]
        # …and it must still be the reader's choice after they move
        for i in range(dlg._tree.topLevelItemCount()):
            head = dlg._tree.topLevelItem(i)
            if head.childCount() > 1:
                dlg._tree.setCurrentItem(head.child(1))
                break
        moved = dlg._tree.currentItem().text(0)
        dlg._type_combo.setCurrentIndex(
            (dlg._type_combo.currentIndex() + 1) % dlg._type_combo.count())
        pump(app, 900)
        after = dlg._tree.currentItem()
        say(f"    after the reader picks {moved!r} and changes the report "
            f"type, the window keeps: "
            f"{after.text(0) if after is not None else 'NOTHING'}")
        rec["kept_after_refresh"] = (after.text(0) if after is not None
                                     else None)
        dlg.close()
        pump(app, 500)
    finally:
        PVD.PresetVerificationDialog.exec = orig

    (out / "opens-on-your-preset.json").write_text(
        json.dumps(rec, indent=2), encoding="utf-8")
    (out / "opens-on-your-preset.md").write_text("\n".join(log) + "\n",
                                                 encoding="utf-8")
    win.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
