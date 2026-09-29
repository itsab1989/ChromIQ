#!/usr/bin/env python3
"""B8-1652 on screen: the standard buttons of Preferences in another language.

Opens Preferences non-modally in the given language and records the text of
every QDialogButtonBox button, then photographs the window.

    CHROMIQ_LOG_DIR=<sandbox> python scripts/drive_b8_1652_standard_buttons.py <out> <lang>
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

TREE = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, TREE + "/scripts")
sys.path.insert(0, TREE)
from userdrive import Drive                                    # noqa: E402
import drive_b42_k36 as K36                                    # noqa: E402

K36.DEADLINE_S = 300


def script(d):
    from PyQt6.QtWidgets import QDialogButtonBox
    from ui.dialogs.settings_dialog import SettingsDialog
    rec = d.record
    assert os.environ.get("CHROMIQ_LOG_DIR"), "SANDBOX THE LOG FIRST"
    K36._install_watchdog(d, rec)
    yield 600
    dlg = SettingsDialog(d.win._settings, d.win)
    dlg.show()
    yield 1200
    rec["buttons"] = []
    for bb in dlg.findChildren(QDialogButtonBox):
        for b in bb.buttons():
            rec["buttons"].append({"text": b.text(),
                                   "role": str(bb.buttonRole(b))})
    d.shot(dlg, "01-preferences")
    dlg.reject()
    yield 400


def main() -> int:
    out = Path(sys.argv[1])
    lang = sys.argv[2]
    d = Drive(out, projects=[], language=lang, appearance="light")
    rc = d.run(script)
    (out / "record.json").write_text(
        json.dumps(d.record, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8")
    print(f"rc={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
