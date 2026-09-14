#!/usr/bin/env python3
"""ADVERSARY 15 — thirty new icons in the Report limits window, ON SCREEN.

Opens the REAL Report limits window in a REAL window, in English, German and
Norwegian, at a WIDE and a NARROW size, photographs each, and MEASURES:

* one icon per row, and whether they line up in a column of their own;
* a metric name clipped by its label (fontMetrics vs the label's own width);
* a row that grew taller than the spin box beside it;
* the window's own minimum height against an 800 px screen;
* how long the window takes to build, and how much of that is the icons.

Never sets QT_QPA_PLATFORM. It is a driver, not a test.

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-adv15.ini \
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-adv15-presets \
        python scripts/adversary15_limits_window_layout.py <out-dir>
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

assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
assert "QT_QPA_PLATFORM" not in os.environ, "a driver must not go offscreen"

from PyQt6.QtWidgets import QApplication, QLabel                 # noqa: E402
from onscreen_capture import capture_window, session_is_locked   # noqa: E402

OUT = Path(sys.argv[1]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
findings: list[str] = []


def pump(app, ms=350):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    from core.settings import AppSettings
    from core import i18n
    from ui.tooltip_button import TooltipButton
    from workflow import compliance_sets as cs

    settings = AppSettings()
    import tempfile
    outdir = tempfile.mkdtemp(prefix="chromiq-adv15-out-")
    settings.set("custom_output_path", outdir)
    print("sandboxed output path:", outdir)

    report: dict = {"locked_at_start": session_is_locked(), "langs": {}}

    for lang in ("en", "de", "no"):
        i18n.set_language(lang)
        # the row text is read through tr() at build time
        import importlib
        from ui.dialogs import thresholds_dialog as td
        importlib.reload(td)

        t0 = time.perf_counter()
        dlg = td.ThresholdsDialog(AppSettings(), None)
        build_ms = (time.perf_counter() - t0) * 1000.0

        entry = {"build_ms": round(build_ms, 1), "sizes": {}}
        dlg.setWindowTitle(f"ADV15 limits — {lang}")
        dlg.show()
        pump(app, 700)

        for tag, (w, h) in (("wide", (1500, 950)), ("narrow", (820, 560))):
            dlg.resize(w, h)
            pump(app, 600)
            g = dlg._grid
            xs, clipped, tall, n_rows = [], [], [], 0
            for i in range(g.count()):
                it = g.itemAt(i)
                wgt = it.widget() if it else None
                if wgt is None:
                    continue
                if g.getItemPosition(i)[1] != 0:
                    continue
                kids = wgt.findChildren(TooltipButton)
                if len(kids) != 1:
                    continue
                n_rows += 1
                btn = kids[0]
                xs.append(btn.pos().x())
                labs = [c for c in wgt.findChildren(QLabel)]
                for lab in labs:
                    need = lab.fontMetrics().horizontalAdvance(lab.text())
                    if need > lab.width() + 1:
                        clipped.append((lab.text(), need, lab.width()))
                if wgt.height() > 34:
                    tall.append((labs[0].text() if labs else "?", wgt.height()))
            gx = dlg.mapFromGlobal(dlg.mapToGlobal(dlg.pos()))
            entry["sizes"][tag] = {
                "window": [dlg.width(), dlg.height()],
                "rows_with_an_icon": n_rows,
                "distinct_icon_x": sorted(set(xs)),
                "clipped_names": clipped[:8],
                "n_clipped": len(clipped),
                "rows_taller_than_34px": tall[:8],
                "minimumSizeHint": [dlg.minimumSizeHint().width(),
                                    dlg.minimumSizeHint().height()],
                "minimumSize": [dlg.minimumWidth(), dlg.minimumHeight()],
            }
            ok, why = capture_window(dlg, OUT / f"limits-{lang}-{tag}.png")
            entry["sizes"][tag]["photo"] = "ok" if ok else f"FAILED: {why}"
            print(f"[{lang}/{tag}] {entry['sizes'][tag]}")

        # open ONE info dialog for real, non-modally, and photograph it
        if lang == "de":
            row = cs.ROW_BY_ID["grey_balance_neutral_ramp_avg"]
            from ui.tooltip_button import TooltipButton as TB
            btns = dlg.findChildren(TB)
            tgt = None
            for b in btns:
                if b._title == i18n.tr(row.label):
                    tgt = b
                    break
            if tgt is not None:
                d = tgt.build_dialog() if hasattr(tgt, "build_dialog") else None
                if d is None:
                    # build the same dialog the click builds, without exec()
                    import inspect
                    src = inspect.getsource(type(tgt)._show_dialog)
                    entry["show_dialog_src_head"] = src.split("\n")[0]
                entry["de_grey_help_text"] = tgt._body

        dlg.close()
        pump(app, 200)
        report["langs"][lang] = entry

    # --- the dialog's own rule: no self-capturing lambda as a slot
    import re
    src = (ROOT / "ui/dialogs/thresholds_dialog.py").read_text(
        encoding="utf-8")
    lam = [ln.strip() for ln in src.splitlines()
           if ".connect(" in ln and "lambda" in ln]
    report["lambda_slots_in_thresholds_dialog"] = lam

    # --- how much of the build is the icons
    from ui.tooltip_button import TooltipButton
    from PyQt6.QtWidgets import QWidget
    host = QWidget()
    t0 = time.perf_counter()
    for r in cs.ROWS:
        TooltipButton("t", "b" * 400, host, min_width=460, color="#7ED321")
    report["thirty_icons_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
    t0 = time.perf_counter()
    for r in cs.ROWS:
        TooltipButton("t", "b" * 400, host, min_width=460, color="#7ED321")
    report["thirty_icons_ms_warm_cache"] = round(
        (time.perf_counter() - t0) * 1000.0, 2)

    (OUT / "adv15-layout.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False)[:4000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
