#!/usr/bin/env python3
"""Why a loaded preset shows no "Margins: OK" and no warning either.

The design authority, 2026-09-16: *"I mentioned before that some presets when
loaded are missing the 'Margins: OK' message, and instead have no message at
all. Why is that, for what kind of circumstances does this happen, and is that
a bug? Can it be fixed, so that all presets loaded end up showing the
'Margins: OK' message?"*

A survey of all 149 built-in presets (`drive_182_survey_every_builtin_preset`)
found exactly 15 in that state, and they are not scattered: they are the
**A4 and A3** i1Pro 3 Plus charts, while their nine **Letter** siblings, with
the same recipe shape and margins within a tenth of a millimetre, show the
green line. This driver takes one of each and records what the inspector is
actually holding when it decides, so the answer is measured rather than read
off the source.

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-b20p.ini \\
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-b20p-presets \\
        python scripts/drive_182_why_some_presets_say_nothing.py <out-dir>
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window, session_is_locked   # noqa: E402

#: One silent chart and one talking one, same family, same author, same
#: recipe shape. The only difference the survey could see is the paper.
CASES = [
    ("__chromiq_knut_p3_a4_84p_1page_portrait_w25_0mm__", "SILENT (A4)"),
    ("__chromiq_knut_p3_letter_84p_1page_portrait_w25_0mm__", "TALKS (Letter)"),
]


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:                                      # noqa: C901
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    crashes: list = []
    prev = sys.excepthook

    def hook(t, e, tb):
        crashes.append("".join(traceback.format_exception(t, e, tb)))
        prev(t, e, tb)
    sys.excepthook = hook

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-b20p-why-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("use_chromiq_layout_engine", True)
    settings.set("restore_last_session", False)
    settings.set("appearance", "dark")
    settings.set("margin_inspector_show", True)
    settings.set("chart_stamp_commands", False)
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    print(f"    sandbox: {work}", flush=True)
    print(f"    screen locked at start: {session_is_locked()}", flush=True)

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart, KNUT_PRESETS_BY_KEY
    from ui.theme import apply_appearance
    TabChart._confirm_displacing_results = lambda self, *a, **k: True

    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.resize(1680, 1060)
    win.show(); win.raise_(); win.activateWindow()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 800)
    tab._user_switch_mode("manual")
    pump(app, 1500)
    panel = tab._margin_panel
    print(f"    window on screen: {win.isVisible()}", flush=True)

    rows = []
    for key, tag in CASES:
        p = KNUT_PRESETS_BY_KEY[key]
        if tab._manual_target_name_edit is not None:
            tab._manual_target_name_edit.setText("B20PWhy")
        tab._margin_report = None
        tab._margin_tiffs = []
        tab._activate_builtin_preset(key)
        pump(app, 1500)
        tab._generate_btn.click()
        waited = 0.0
        while waited < 240.0:
            pump(app, 150)
            waited += 0.15
            if getattr(tab, "_margin_report", None) is not None:
                break
        # **WHAT THE INSPECTOR IS HOLDING WHEN IT DECIDES.** `_margin_tiffs` is
        # the list of rendered pages; `_update_margin_inspector` shows the
        # placeholder and drops the report when it is empty, which produces an
        # empty, hidden status line rather than any message at all.
        before = {
            "margin_tiffs": len(getattr(tab, "_margin_tiffs", []) or []),
            "report": getattr(tab, "_margin_report", None) is not None,
            "preview_pages": int(tab._preview.page_count())
            if hasattr(tab._preview, "page_count") else None,
            "seconds_to_report": round(waited, 2),
        }
        tab._update_margin_inspector()
        pump(app, 800)
        # **THE THREE LISTS THE PANEL IS HANDED**, reconstructed exactly as
        # `_update_margin_inspector` builds them, because the difference
        # between "no message" and "Margins: OK" is decided by which of them
        # is non-empty and nothing else.
        _rep = getattr(tab, "_margin_report", None)
        _warns, _over = TabChart._engine_text_notes(tab, _rep)
        _warns = list(_warns)
        _ruler = getattr(tab, "_ruler_over_mm", None)
        if _ruler:
            _warns = _warns + ["<the strip-length-exceeds-ruler line>"]
        after = {
            "text_warnings": _warns,
            "overlap_warnings": list(_over),
            "ruler_over_mm": _ruler,
            "strip_length_mm": (None if _rep is None
                                else round(float(_rep.strip_length_mm or 0.0), 2)),
            "margin_tiffs": len(getattr(tab, "_margin_tiffs", []) or []),
            "report": getattr(tab, "_margin_report", None) is not None,
            "status_text": panel._status.text(),
            "status_visible": bool(panel._status.isVisible()),
        }
        r = p.layout_recipe or {}
        row = {
            "case": tag, "key": key, "name": p.name,
            "paper": r.get("paper"), "instrument": r.get("instrument"),
            "declared_pages": p.pages, "declared_patches": p.patches,
            "before_update": before, "after_update": after,
        }
        rows.append(row)
        print(f"  == {tag}  {p.name}", flush=True)
        print(f"     paper={row['paper']}  tiffs_before={before['margin_tiffs']} "
              f"report_before={before['report']} "
              f"secs={before['seconds_to_report']}", flush=True)
        print(f"     after: tiffs={after['margin_tiffs']} "
              f"report={after['report']} status={after['status_text']!r} "
              f"visible={after['status_visible']}", flush=True)
        shot = out / f"{tag.split()[0].lower()}-{row['paper']}.png"
        ok, why = capture_window(win, shot)
        row["photograph"] = str(shot) if ok else None
        row["photograph_refused"] = None if ok else why
        print(f"     photo: {'OK' if ok else why}", flush=True)

    (out / "why.json").write_text(
        json.dumps({"rows": rows, "crashes": crashes}, indent=2,
                   ensure_ascii=False), encoding="utf-8")
    print(f"    crashes: {len(crashes)}", flush=True)
    for c in crashes:
        print(c[:3000], flush=True)
    win.close()
    pump(app, 500)
    return 0


if __name__ == "__main__":
    sys.exit(main())
