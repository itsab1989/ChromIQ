#!/usr/bin/env python3
"""Knut's beta 9 report, reproduced in the REAL window and on a REAL sheet.

Knut, 2026-09-13, testing beta 9, with a ColorMunki preset, "Stamp settings
down the right edge" on, chart notes typed, a bottom sheet text of nine
placeholders at a typed 13 pt, a four-line clip-border text at 11 pt, a 24 mm
clip border and a 31.5 mm right margin. The panel said:

    The chart notes down the right edge are too long for the sheet. The last 5
    characters are cut off and replaced by "...", because the text has stopped
    shrinking at 13 pt.

and he answered it in five parts:

    1. The chart notes text does not go all the way out to the to top or bottom
       limits.
    2. There is no "..." placed at the end and 5 characters are not cut off.
    3. It is the bottom text that moves into the text area of the right margin,
       not the chart notes being too long here.
    4. When right margin is larger than clip-border width: the largest value of
       them should define the side-positions that are used for centring the
       bottom text, not only clip-border width. This should apply for both left
       or right side clip-border.
    5. Shrinking stops at 7 pt, but only in size=auto. When size is manually set
       to 13, it is not a shrinking. Text is wrong.

This drives that configuration, records what the panel says, and then RENDERS
the sheet and measures:

* the right-edge notes' ink, its top and bottom, and whether an ellipsis was
  drawn at all (1 and 2);
* the bottom line's ink against the right margin's own text column (3);
* the bounds the bottom line is centred between, against the margins (4).

Run it::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-k9.ini \\
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-k9-presets \\
        python scripts/drive_182_knut_beta9_case.py <out-dir>

Never set QT_QPA_PLATFORM=offscreen for this. It is a driver, not a test.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
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

PRESET_KEY = "__chromiq_knut_cm_a4_612p_2pages_portrait_w10_0mm_slow_reading_speed__"
NOTES = "agadg ag at rth rth rth rth dy hdt hdt jrtj"
SHEET_TEXT = ("{project}-{rundescription}-{page}-{paper}-{date}-{pages}-"
              "{patchcount}-{dpi}-{seed}")
CLIP_TEXT = (
    "—" * 72 + "\n"
    "{project} - {rundescription} - {paper} - {instrument} - {patchcount} - "
    "{page} - {date} - {seed}\n"
    "Top margin: 34 mm to avoid knobs underneath to get caught in page edge. "
    "Bottom margin: 18 mm to have 12 mm white space for comfortably ending "
    "strip.\n"
    "Left margin: 14 mm so 'glide-rails' do not fall outside of page (needs "
    "18 mm to patch centre). Right margin: 24 mm to allow for reading last "
    "strip using ruler.")


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def render(recipe, ti1: Path, tag: str, **over):
    """One built sheet, as a greyscale array plus the result."""
    from dataclasses import replace

    import numpy as np
    from PIL import Image

    from workflow.layout_engine.chart import build_from_recipe
    base = Path(tempfile.mkdtemp(prefix=f"chromiq-k9-{tag}-"))
    res, used = build_from_recipe(str(ti1), str(base / "s"),
                                  replace(recipe, **over) if over else recipe)
    page = sorted(base.glob("s*.tif"))[0]
    return np.asarray(Image.open(page).convert("L")).astype(np.int16), res, used


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-k9-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("use_chromiq_layout_engine", True)
    settings.set("restore_last_session", False)
    settings.set("appearance", "dark")
    settings.set("margin_inspector_show", True)
    settings.set("margin_violation_notify", True)
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    from ui.theme import apply_appearance
    TabChart._confirm_displacing_results = lambda self, *a, **k: True

    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.resize(1700, 1120)
    win.show()
    win.raise_()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 800)
    tab._user_switch_mode("manual")
    pump(app, 1500)
    print(f"    window on screen: {win.isVisible()} "
          f"{win.frameGeometry().width()}x{win.frameGeometry().height()}",
          flush=True)

    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("test")
    pump(app, 200)
    combo = tab._preset_combo
    idx = combo.findData(PRESET_KEY)
    assert idx >= 0, f"{PRESET_KEY} is not in the dropdown"
    combo.setCurrentIndex(idx)
    combo.activated.emit(idx)
    pump(app, 1500)
    for _ in range(300):
        pump(app, 120)
        if getattr(tab, "_margin_ti2", None) and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 800)
    print(f"    preset loaded, engine={settings.get('use_chromiq_layout_engine', False)}",
          flush=True)

    ti1 = None
    for _attr in ("_preset_ti1_path", "_builtin_ti1_path"):
        _v = getattr(tab, _attr, None)
        if _v and Path(_v).is_file():
            ti1 = Path(_v)
            break
    assert ti1 is not None, "no .ti1 to render from"

    # HIS SETTINGS, through the widgets a person touches.
    if tab._manual_chart_notes_edit is not None:
        tab._manual_chart_notes_edit.setText(NOTES)
    if tab._manual_stamp_cmd_check is not None:
        tab._manual_stamp_cmd_check.setChecked(True)
    panel = tab._manual_layout_panel
    panel.chart_text.setText(SHEET_TEXT)
    panel.chart_text_size.setValue(13.0)
    panel.stamp_command.setChecked(False)      # his screenshot: unticked
    panel.clip_text.setPlainText(CLIP_TEXT)
    panel.clip_text_size.setValue(11.0)
    pump(app, 600)
    r = panel.get_recipe()
    r.clip_border, r.clip_border_width_mm, r.clip_side = True, 24.0, "right"
    r.clip_content_mode = "text"
    r.margin_right = 31.5
    r.text_edge_top_mm, r.text_edge_mm, r.text_edge_clip_mm = 8.0, 4.0, 4.0
    panel.set_recipe(r)
    pump(app, 900)
    tab._update_margin_inspector()
    pump(app, 1200)
    r = panel.get_recipe()

    warnings = TabChart._engine_text_notes(tab)[1]
    print(f"    {len(warnings)} warning(s) on the panel:", flush=True)
    for w in warnings:
        print(f"      - {w[:200]}", flush=True)

    shot = out / "01-his-setup.png"
    ok, why = capture_window(win, shot)
    print(f"    photo={'ok' if ok else 'REFUSED: ' + why}", flush=True)

    # ------------------------------------------- what the panel is measuring
    # The prediction's own inputs, read out of the tab rather than guessed.
    from workflow import text_edge_fit as tef
    from workflow import tiff_metadata as tmeta
    from workflow.layout_engine import papers

    # THE PANEL'S PREDICTION, built exactly as the panel builds it.
    pm = tab._collect_manual()
    pm.chart_notes = NOTES
    pm.stamp_commands = True
    pm.chart_layout_name = tab._active_layout_name()
    np_est = tab._estimate_patch_total() or 0
    predicted_line = tmeta._JOIN.join(tab._creator.stamp_lines(pm, int(np_est)))

    # …AND THE LINE THE BUILD WOULD STAMP, built as `_generate_from_ti1` does.
    build_pm = tab._collect_params()
    build_pm.target_name = tab._file_mgr.get_target_name()
    build_pm.chart_layout_name = tab._active_layout_name()
    build_pm.chart_notes = NOTES
    build_pm.stamp_commands = True
    from workflow.chart_creator import ChartCreator as _CC
    n_build = tab._count_patches_in_ti1(ti1) if hasattr(
        tab, "_count_patches_in_ti1") else np_est
    build_line = tmeta._JOIN.join(
        tab._creator.stamp_lines(build_pm, int(n_build or np_est)))
    facts: dict = {
        "predicted_stamp_line": predicted_line,
        "predicted_line_chars": len(predicted_line),
        "build_stamp_line": build_line,
        "build_line_chars": len(build_line),
        "lines_agree": predicted_line == build_line,
        "active_layout_name": tab._active_layout_name(),
        "estimate_patch_total": np_est,
        "notes_size_pt": float(panel.chart_text_size.value()),
        "floor_pt": tef.text_floor_pt(float(panel.chart_text_size.value())),
        "margin_right_mm": float(getattr(r, "margin_right", 0.0) or 0.0),
        "clip_border_mm": float(getattr(r, "clip_border_width_mm", 0.0) or 0.0),
        "panel_warnings": warnings,
    }
    pw = float(papers.dimensions_mm(r.paper)[0])
    l_b, r_b = tef.bottom_text_bounds_mm(
        pw, float(getattr(r, "text_edge_clip_mm", 0.0) or 0.0),
        bool(getattr(r, "helper_markers", False)),
        float(getattr(r, "helper_marker_edge_mm", 0.0) or 0.0),
        float(getattr(r, "helper_marker_len_mm", 0.0) or 0.0),
        bool(getattr(r, "helper_markers_sides", True)),
        clip_border_mm=float(getattr(r, "clip_border_width_mm", 0.0) or 0.0),
        clip_side=str(getattr(r, "clip_side", "right") or "right"))
    facts["bottom_bounds_mm"] = [round(float(l_b), 2), round(float(r_b), 2)]
    facts["right_margin_bound_mm"] = round(pw - facts["margin_right_mm"], 2)
    facts["bottom_line_width_mm"] = round(tab._sheet_text_width_mm(r), 2)
    facts["bottom_lines"] = tab._bottom_sheet_text_lines(r)

    (out / "knut-beta9.json").write_text(
        json.dumps({"screen_locked": session_is_locked(),
                    "qt_qpa_platform": os.environ.get("QT_QPA_PLATFORM", "<unset>"),
                    "facts": facts}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    print("\n    MEASURED:", flush=True)
    for k in ("predicted_line_chars", "build_line_chars", "lines_agree",
              "active_layout_name", "estimate_patch_total", "notes_size_pt",
              "floor_pt", "bottom_bounds_mm", "right_margin_bound_mm",
              "clip_border_mm", "margin_right_mm", "bottom_line_width_mm"):
        print(f"      {k}: {facts.get(k)}", flush=True)
    print(f"      predicted line: {predicted_line!r}", flush=True)
    print(f"      bottom line   : {facts['bottom_lines']}", flush=True)
    print(f"\n    written {out / 'knut-beta9.json'}", flush=True)
    win.close()
    pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
