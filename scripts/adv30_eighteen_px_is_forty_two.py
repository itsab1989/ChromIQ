#!/usr/bin/env python3
"""Round 30: `setFixedHeight(18)` gives a 42 px button under ChromIQ's stylesheet.

Basti asked TWICE for the reference-values buttons to be shorter. Beta 26 set
`setFixedHeight(22)`; the replacement sets `setFixedHeight(18)`; the guard
asserts `.height() == 18` and passes. **On screen both are 42 px**, which is
what he was looking at when he said they were still too big.

`ui/styles.py` sets, for every QPushButton in the app:

    QPushButton { padding: 6px 18px; min-height: 28px; ... }

28 + 6 + 6 + 1 + 1 = 42.  Qt's stylesheet style folds `min-height` and the box
model into `minimumSizeHint`, and a layout honours a minimum size hint over a
fixed height.  `setFixedHeight` therefore cannot make a button in this app
shorter than 42 px, and a test that reads `.height()` off a widget that was
never shown and never laid out reads back the 18 nobody sees.

The idiom that DOES work is already in `thresholds_dialog.py`, on its
"Restore this column" button: a per-widget stylesheet that puts `min-height`
down as well as capping `max-height`.

Measured here, on screen, four ways.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from PyQt6.QtWidgets import (QApplication, QDialog, QPushButton,   # noqa: E402
                             QVBoxLayout)
from onscreen_capture import capture_window                        # noqa: E402


def main() -> int:
    assert not os.environ.get("QT_QPA_PLATFORM"), "this DRIVER opens a window"
    out = Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from ui.theme import apply_appearance
    apply_appearance(app, None, "light")

    res = {}
    d = QDialog(); d.resize(520, 300)
    lay = QVBoxLayout(d)

    a = QPushButton("setFixedHeight(18)", d); a.setFixedHeight(18); lay.addWidget(a)
    b = QPushButton("setFixedHeight(22) - beta 26", d); b.setFixedHeight(22); lay.addWidget(b)
    c = QPushButton("plain", d); lay.addWidget(c)
    e = QPushButton("the working idiom", d)
    e.setStyleSheet("QPushButton { padding: 1px 6px; font-size: 10px;"
                    " min-height: 18px; max-height: 18px; min-width: 0; }")
    lay.addWidget(e)

    res["before_show"] = {k: w.height() for k, w in
                          (("fixed18", a), ("fixed22", b), ("plain", c),
                           ("stylesheet18", e))}
    d.show(); d.raise_(); d.activateWindow()
    for _ in range(200):
        app.processEvents()
    res["on_screen"] = {k: w.height() for k, w in
                        (("fixed18", a), ("fixed22", b), ("plain", c),
                         ("stylesheet18", e))}
    res["minimumSizeHint"] = {k: w.minimumSizeHint().height() for k, w in
                              (("fixed18", a), ("fixed22", b), ("plain", c),
                               ("stylesheet18", e))}
    ok, why = capture_window(d, out / "H-eighteen-is-forty-two-1.png")
    for _ in range(80):
        app.processEvents()
    ok2, _ = capture_window(d, out / "H-eighteen-is-forty-two-2.png")
    res["photo"] = {"taken": ok and ok2, "why": why}
    (out / "eighteen-px-is-forty-two.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))
    d.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
