#!/usr/bin/env python3
"""Round 27b, the last two border conditions, on screen.

1. **GERMAN.** The button's height is now pinned at 22 px, and a pinned height
   is exactly the kind of number that survives an English screen and clips a
   German one. The app is started in German and the Presets group photographed,
   with the label's own width and line height measured against the button's.
2. **The demo pack's "Verify demo 13, the patch set cannot be read"**, in the
   real detail pane, after the fix that stopped it blaming the page count.

    python scripts/adv27b_german_and_demo13.py <out-dir>
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
from PyQt6.QtGui import QFontMetrics                           # noqa: E402

from adv27b_the_preset_button import app_like_main, pump        # noqa: E402
from drive_182_preset_verification_window import twice          # noqa: E402

PACK = (Path.home() / "Desktop/ChromIQ-beta23-proof/demo-pack"
        / "ChromIQ-Report-Limit-Demos"
        / "Create Chart presets (verification demos)")
WORK = Path("/tmp/chromiq-r27b/work-de")


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else
               Path.home() / "Desktop/ChromIQ-beta23-proof/round-27b-chart")
    shots = out / "shots-de"
    shots.mkdir(parents=True, exist_ok=True)
    assert "/tmp/" in os.environ.get("CHROMIQ_SETTINGS_FILE", ""), "SANDBOX"
    assert "/tmp/" in os.environ.get("CHROMIQ_PRESETS_DIR", ""), "SANDBOX"
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)

    log: "list[str]" = []
    rec: dict = {}

    def say(x=""):
        print(x, flush=True)
        log.append(x)

    app = app_like_main()
    from core.preset_store import tab_dir
    dest = tab_dir("create_chart")
    dest.mkdir(parents=True, exist_ok=True)
    for src in sorted(PACK.iterdir()):
        if src.suffix in (".json", ".ti1"):
            shutil.copy2(src, dest / src.name)

    from core.settings import AppSettings
    s = AppSettings()
    s.set("custom_output_path", str(WORK))
    s.set("language", "de")
    from core.i18n import set_language, tr
    set_language("de")
    from core.file_manager import Project
    from core.measurement_target import RUN_TYPE_VERIFICATION
    from ui.main_window import MainWindow
    proj = WORK / "R27b-DE"
    Project.create(proj, "R27b-DE").current_run().ensure_dir()
    win = MainWindow(s)
    win.resize(1500, 1020)
    win.show()
    pump(app, 1500)
    win._file_mgr.open_project_at(proj)
    win._target_ctl.changed.emit()
    pump(app, 700)
    tab = win._tab_chart
    win._tabs.setCurrentIndex(win._tabs.indexOf(tab))
    pump(app, 600)
    tab._manual_btn.click()
    pump(app, 900)
    win._target_ctl.set_run_type(RUN_TYPE_VERIFICATION)
    pump(app, 1000)
    from ui.fade_scroll import FadeScrollArea
    host = tab._preset_verify_btn.parent()
    while host is not None and not isinstance(host, FadeScrollArea):
        host = host.parent()
    if host is not None:
        host.ensureWidgetVisible(tab._preset_combo, 0, 120)
        pump(app, 700)

    btn = tab._preset_verify_btn
    fm = QFontMetrics(btn.font())
    label = btn.text()
    need_w = fm.horizontalAdvance(label.upper())
    say("# round 27b — German, and the demo the pane used to misdirect")
    say("")
    say(f"driven {time.strftime('%Y-%m-%d %H:%M:%S')}")
    say("mode   : ON SCREEN, a real window, capture_window by id")
    say("")
    say("## the button in German")
    say("")
    say(f"    the label            : {label!r}")
    say(f"    it needs             : {need_w} px wide, {fm.height()} px of "
        f"line height")
    say(f"    the button gives it  : {btn.width()} px x {btn.height()} px")
    say(f"    the label fits       : "
        f"{need_w <= btn.width() and fm.height() <= btn.height()}")
    say(f"    still visible only on a verification run: {btn.isVisible()}")
    rec["german"] = {"label": label, "need_w": need_w, "line": fm.height(),
                     "w": btn.width(), "h": btn.height(),
                     "fits": bool(need_w <= btn.width()
                                  and fm.height() <= btn.height())}
    ok, why, d = twice(app, win, shots / "de-01-the-button.png")
    say(f"    photograph de-01-the-button.png: "
        f"{'kept' if ok else 'REFUSED: ' + why} (differ by {d} %)")

    from ui.dialogs import preset_verification_dialog as PVD
    opened: list = []
    orig = PVD.PresetVerificationDialog.exec

    def _no_block(self):
        opened.append(self)
        self.show()
        return 0
    PVD.PresetVerificationDialog.exec = _no_block
    try:
        btn.click()
        pump(app, 2500)
        dlg = opened[0]
        dlg.resize(1220, 780)
        pump(app, 900)
        say("")
        say("## the window in German, on the demo whose patch set cannot be "
            "read")
        item = None
        for i in range(dlg._tree.topLevelItemCount()):
            h = dlg._tree.topLevelItem(i)
            for j in range(h.childCount()):
                c = h.child(j)
                r = c.data(0, Qt.ItemDataRole.UserRole)
                if r is not None and "demo 13" in r.label:
                    item = c
        assert item is not None, "demo 13 is not in the window"
        from PyQt6.QtWidgets import QAbstractItemView
        dlg._tree.scrollToItem(
            item, QAbstractItemView.ScrollHint.PositionAtCenter)
        dlg._tree.setCurrentItem(item)
        pump(app, 800)
        shown = []
        for i in range(dlg._detail_layout.count()):
            w = dlg._detail_layout.itemAt(i).widget()
            if w is not None and hasattr(w, "text"):
                shown.append(w.text())
        for line in shown:
            say(f"    | {line}")
        blames_pages = any("Seiten" in t or "pages" in t for t in shown)
        say("")
        say(f"    the pane still blames the page count: {blames_pages}")
        rec["demo13"] = {"lines": shown, "blames_pages": blames_pages}
        ok2, why2, d2 = twice(app, dlg, shots / "de-02-demo-13.png")
        say(f"    photograph de-02-demo-13.png: "
            f"{'kept' if ok2 else 'REFUSED: ' + why2} (differ by {d2} %)")
        dlg.close()
        pump(app, 500)
    finally:
        PVD.PresetVerificationDialog.exec = orig

    (out / "german-and-demo13.md").write_text("\n".join(log) + "\n",
                                              encoding="utf-8")
    (out / "german-and-demo13.json").write_text(json.dumps(rec, indent=2),
                                                encoding="utf-8")
    win.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
