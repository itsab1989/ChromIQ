#!/usr/bin/env python3
"""ON SCREEN: what do the two Custom ISO columns actually hold, cell by cell?

Their pulldown blurbs say "The rows ISO 12647-7:2016 writes a limit over" and
"The rows ISO 12647-8:2021 writes a limit over".  This reads the real cells out
of the real Report limits window and compares the two columns with each other
and with the row list each set's parent is declared to limit.
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

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtGui import QFontDatabase            # noqa: E402
from PyQt6.QtWidgets import QApplication, QLabel  # noqa: E402

from onscreen_capture import capture_window, session_is_locked   # noqa: E402


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else Path("/tmp/chromiq-adv2-proof")
    shots = out / "shots"
    shots.mkdir(parents=True, exist_ok=True)
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"

    res: dict = {"screen_locked": session_is_locked(),
                 "mode": "on screen (cocoa), real Report limits window"}
    print("00 screen locked:", res["screen_locked"])

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from core.resource_path import resource_path
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))

    from core.settings import AppSettings
    settings = AppSettings()
    settings.set("appearance", "dark")
    from ui import theme as ui_theme
    ui_theme.apply_appearance(app, None, "dark")

    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    td = ThresholdsDialog(settings, None)
    td.show()
    pump(app, 1500)
    ok, why = capture_window(td, shots / "custom-columns.png")
    res["shot"] = "custom-columns.png" if ok else f"REFUSED: {why}"
    print("01 shot:", "ok" if ok else "REFUSED " + (why or ""))

    def cell(col, rid):
        w = td._cells.get((col, rid))
        if w is None:
            return None
        if isinstance(w, QLabel):
            return w.text()
        try:
            return f"spin {w.value()}"
        except Exception:              # noqa: BLE001
            return type(w).__name__

    from workflow.compliance_sets import ROWS, _ISO_ROWS
    a, b = "custom_iso_12647_7", "custom_iso_12647_8"
    table = {}
    for r in ROWS:
        table[r.id] = {"status": r.status, a: cell(a, r.id), b: cell(b, r.id)}
    res["cells"] = table
    res["identical"] = all(v[a] == v[b] for v in table.values())

    # Which rows carry a NUMBER in each column, and whether the parent standard
    # is declared to write a limit over that row at all.
    def numeric(col):
        return sorted(rid for rid, v in table.items()
                      if v[col] and str(v[col]).strip("()")
                      .replace(".", "").replace("spin ", "").isdigit())
    res["numeric_rows"] = {a: numeric(a), b: numeric(b)}
    res["outside_the_parents_row_list"] = {
        a: [r for r in numeric(a) if r not in _ISO_ROWS["iso_12647_7"]],
        b: [r for r in numeric(b) if r not in _ISO_ROWS["iso_12647_8"]],
    }
    print("02 the two Custom columns are identical cell for cell:",
          res["identical"])
    print("03 numeric rows OUTSIDE the parent standard's own row list:")
    for k, v in res["outside_the_parents_row_list"].items():
        print(f"     {k}: {v}")

    (out / "custom-columns.json").write_text(json.dumps(res, indent=2),
                                             encoding="utf-8")
    td.reject()
    pump(app, 300)
    return 0


if __name__ == "__main__":
    sys.exit(main())
