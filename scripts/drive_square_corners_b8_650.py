#!/usr/bin/env python3
"""B8-650: photograph the three bare-StyledPanel frames, on screen.

Sebastian photographed square corners on the section frames in the Reference
values window; the same cause (`QFrame(StyledPanel)` with no stylesheet)
exists in exactly two other places (`ui/dialogs/preflight_dialog.py`,
`ui/dialogs/ti2_relayout_dialog.py`'s single-colour swatch). This drives all
three, in both Light and Dark, and photographs each with `capture_window` so
the corner can be read from the painted pixels rather than from the
stylesheet text.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-corners/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-corners/presets
    python scripts/drive_square_corners_b8_650.py <out-dir> <tag>

`<tag>` names the output files (e.g. "before" / "after") so the same script
runs twice, once against the unpatched tree and once against the fix.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from PyQt6.QtWidgets import QApplication                          # noqa: E402
from onscreen_capture import capture_window, session_is_locked    # noqa: E402


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert not os.environ.get("QT_QPA_PLATFORM"), "this DRIVER opens a window"

    out = Path(sys.argv[1]).resolve()
    tag = sys.argv[2] if len(sys.argv) > 2 else "run"
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    print("locked at start:", session_is_locked())

    from ui.theme import apply_appearance

    results = {}
    for mode in ("light", "dark"):
        apply_appearance(app, None, mode)
        pump(app, 200)

        from ui.dialogs.reference_values_dialog import ReferenceValuesDialog
        rv = ReferenceValuesDialog(None)
        rv.resize(900, rv.sizeHint().height())
        rv.show()
        rv.raise_()
        rv.activateWindow()
        pump(app, 900)
        p1 = out / f"{tag}-reference_values-{mode}.png"
        ok1, why1 = capture_window(rv, p1)
        results[f"reference_values-{mode}"] = {"ok": ok1, "why": why1, "path": str(p1)}
        rv.close()
        pump(app, 150)

        from ui.dialogs.preflight_dialog import PreflightDialog
        pf = PreflightDialog(
            [("Printer", "Canon PRO-300"), ("Paper", "Photo Rag 308"),
             ("Media size", "A3"), ("Quality", "Highest"),
             ("Orientation", "Portrait"), ("Borderless", "No")],
            [], 1, None,
        )
        pf.resize(pf.sizeHint())
        pf.show()
        pf.raise_()
        pf.activateWindow()
        pump(app, 900)
        p2 = out / f"{tag}-preflight-{mode}.png"
        ok2, why2 = capture_window(pf, p2)
        results[f"preflight-{mode}"] = {"ok": ok2, "why": why2, "path": str(p2)}
        pf.close()
        pump(app, 150)

        from ui.dialogs.ti2_relayout_dialog import _AddPatchesDialog
        ap = _AddPatchesDialog(None, None)
        ap.resize(680, ap.sizeHint().height())
        ap.show()
        ap.raise_()
        ap.activateWindow()
        pump(app, 900)
        p3 = out / f"{tag}-addpatches-{mode}.png"
        ok3, why3 = capture_window(ap, p3)
        results[f"addpatches-{mode}"] = {"ok": ok3, "why": why3, "path": str(p3)}
        ap.close()
        pump(app, 150)

    import json
    print(json.dumps(results, indent=2))
    all_ok = all(r["ok"] for r in results.values())
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
