#!/usr/bin/env python3
"""Round 27b: how much vertical space the presets group really takes, on screen.

Run it before and after a change and compare the two JSON files. It opens a
REAL window (never offscreen), puts the Create Chart tab in Manual mode, and
measures the Presets group box with Run type = Profiling (the pair hidden) and
= Verification (the pair shown), plus the button's own height against a plain
`QPushButton` carrying the same label in the same row.

    python scripts/adv27b_presets_group_height.py <out.json> [tag]
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

from PyQt6.QtWidgets import QPushButton                       # noqa: E402

from adv27b_the_preset_button import app_like_main, pump       # noqa: E402

WORK = Path("/tmp/chromiq-r27b/work-h")


def main() -> int:
    outp = Path(sys.argv[1])
    tag = sys.argv[2] if len(sys.argv) > 2 else "run"
    assert "/tmp/" in os.environ.get("CHROMIQ_SETTINGS_FILE", ""), "SANDBOX"
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)

    app = app_like_main()
    from core.settings import AppSettings
    s = AppSettings()
    s.set("custom_output_path", str(WORK))
    from core.file_manager import Project
    from core.measurement_target import (RUN_TYPE_PROFILING,
                                         RUN_TYPE_VERIFICATION)
    from ui.main_window import MainWindow
    proj = WORK / "R27b-H"
    Project.create(proj, "R27b-H").current_run().ensure_dir()
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
    pump(app, 900)

    grp = tab._preset_verify_btn.parentWidget()      # the Presets QGroupBox
    rec: dict = {"tag": tag, "when": time.strftime("%Y-%m-%d %H:%M:%S"),
                 "group_class": type(grp).__name__}

    for name, rt in (("profiling", RUN_TYPE_PROFILING),
                     ("verification", RUN_TYPE_VERIFICATION)):
        win._target_ctl.set_run_type(rt)
        pump(app, 900)
        rec[name] = {
            "presets_group_height": int(grp.height()),
            "presets_group_hint": int(grp.sizeHint().height()),
            "button_visible": bool(tab._preset_verify_btn.isVisible()),
            "button_height": int(tab._preset_verify_btn.height()),
            "help_visible": bool(
                getattr(tab, "_preset_verify_help", None) is not None
                and tab._preset_verify_help.isVisible()),
        }

    # beta 22's button: same label, same parent, no size rule at all
    plain = QPushButton(tab._preset_verify_btn.text(), grp)
    plain.show()
    pump(app, 500)
    rec["plain_button_hint_h"] = int(plain.sizeHint().height())
    rec["shipped_button_hint_h"] = int(tab._preset_verify_btn.sizeHint().height())
    rec["combo_h"] = int(tab._preset_combo.height())
    from PyQt6.QtGui import QFontMetrics
    fm = QFontMetrics(tab._preset_verify_btn.font())
    rec["label_line_h"] = int(fm.height())
    rec["label_w"] = int(fm.horizontalAdvance(
        tab._preset_verify_btn.text().upper()))
    rec["button_w"] = int(tab._preset_verify_btn.width())
    plain.setParent(None)
    plain.deleteLater()

    outp.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    print(json.dumps(rec, indent=2))
    win.close()
    pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
