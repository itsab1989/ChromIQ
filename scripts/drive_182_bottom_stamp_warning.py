#!/usr/bin/env python3
"""Knut's bottom-stamp case, in the REAL Create Chart tab.

Knut, 2026-09-13, testing beta 8::

    When using "Stamp layout information along the bottom" (and no custom text)
    with font size 13 or 14 makes text that cross into the right clip-border
    text, but no warning is given. This happens regardless of the clip-border
    is on left of right side.

This picks a ColorMunki preset, switches the layout stamp on, leaves the custom
text box EMPTY, and walks Size 12, 13 and 14 with the clip border on each side,
recording for every combination:

* the panel's red message field, verbatim;
* the predicted width of the widest bottom line and the room it has;
* whether `text_edge_fit` says the line overflows, asked independently, so a
  warning and a real overflow can be told apart rather than assumed to agree.

It photographs the window on the combinations that overflow.

Run it::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-stamp.ini \\
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-stamp-presets \\
        python scripts/drive_182_bottom_stamp_warning.py <out-dir>

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

#: His sizes. 12 is the one he says is quiet on the custom-text line, so it is
#: here as the control: a warning at every size would prove nothing.
SIZES_PT = (12, 13, 14)
SIDES = ("left", "right")


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-stamp-"))
    settings = AppSettings()
    # PINNED, not merely sandboxed: an unset value in a fresh store still
    # points the app at the user's real ~/ChromIQ.
    settings.set("custom_output_path", str(work))
    settings.set("use_chromiq_layout_engine", True)
    settings.set("restore_last_session", False)
    settings.set("appearance", "dark")
    settings.set("margin_inspector_show", True)
    settings.set("margin_violation_notify", True)
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    print(f"    sandbox: {work}", flush=True)

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import BUILTIN_PRESET_GROUPS, TabChart
    from ui.theme import apply_appearance
    TabChart._confirm_displacing_results = lambda self, *a, **k: True

    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.resize(1620, 1060)
    win.show()
    win.raise_()
    win.activateWindow()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 800)
    tab._user_switch_mode("manual")
    pump(app, 1500)
    print(f"    window on screen: {win.isVisible()} "
          f"{win.frameGeometry().width()}x{win.frameGeometry().height()}",
          flush=True)

    # A ColorMunki preset, which is what he used, AND ONE THAT USES THE LAYOUT
    # ENGINE. The bottom sheet text, the layout stamp and the clip border are
    # all engine furniture, and `_engine_text_notes` returns at its first line
    # on a printtarg chart. The first ColorMunki entry in the dropdown is a
    # printtarg preset ("TC3.00 by Pharmacist"): driven against that one this
    # driver reported a real 2.99 mm overflow with the panel silent, which
    # looked like the fix having failed and was the driver measuring a chart
    # the feature does not apply to at all.
    combo = tab._preset_combo
    candidates = [(label, key)
                  for instr, entries in BUILTIN_PRESET_GROUPS
                  if ("munki" in str(instr).lower() or str(instr) == "CM")
                  for (label, _o, key) in entries
                  if combo.findData(key) >= 0]
    assert candidates, "no ColorMunki preset is in the dropdown"
    # THE NAME FIRST, OR THE PRESET REFUSES ITSELF. `_apply_prebuilt_preset`
    # asks for a project name while the box is empty, and a driver that stubs
    # every QMessageBox to 0 answers that question "no": the preset reverts,
    # the panel keeps its defaults, and the run reports a ColorMunki case it
    # never actually reached. The first run of this driver did exactly that and
    # said "i1Pro / 0 patches" on a 300-patch ColorMunki chart.
    pick = None
    for n, (label, key) in enumerate(candidates, 1):
        if tab._manual_target_name_edit is not None:
            tab._manual_target_name_edit.setText(f"StampCase{n}")
        pump(app, 200)
        combo.setCurrentIndex(combo.findData(key))
        combo.activated.emit(combo.findData(key))
        pump(app, 1200)
        on = bool(settings.get("use_chromiq_layout_engine", False))
        print(f"    tried {label[:52]:<52} engine={on}", flush=True)
        if on:
            pick = (label, key)
            break
    assert pick, ("no ColorMunki preset in the dropdown uses the layout "
                  "engine, so this case cannot be driven from one")
    print(f"    preset: {pick[0]}", flush=True)
    # WAIT FOR THE TIFFS, NOT JUST THE .ti2. `_onscreen_patch_total` needs
    # both, and the first run of this driver waited for one of them, read the
    # panel while the preset had not landed, and reported "0 patches" on a
    # 300-patch chart. A driver that reads too early measures the previous
    # state and calls it the answer.
    for _ in range(300):
        pump(app, 120)
        if getattr(tab, "_margin_ti2", None) and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 800)
    _r0 = panel_recipe = tab._manual_layout_panel.get_recipe()
    print(f"    after the preset: instrument={_r0.instrument} paper={_r0.paper} "
          f"clip={_r0.clip_border}/{_r0.clip_border_width_mm} "
          f"stamp={_r0.stamp_command}", flush=True)
    print(f"    mode: manual_btn={tab._manual_btn.isChecked() if tab._manual_btn else None} "
          f"engine_setting={settings.get('use_chromiq_layout_engine', False)} "
          f"panel={tab._manual_layout_panel is not None} "
          f"engine_check={tab._manual_engine_check.isChecked() if tab._manual_engine_check else None}",
          flush=True)
    print(f"    patch count: pending={tab._pending_patch_set_total()} "
          f"targen={tab._targen_patch_count()} "
          f"onscreen={tab._onscreen_patch_total()} "
          f"estimate={tab._estimate_patch_total()}", flush=True)

    panel = tab._manual_layout_panel
    rows: list = []
    for side in SIDES:
        for pt in SIZES_PT:
            # THE WIDGETS THE PERSON TOUCHES, NOT `set_recipe`. `set_recipe`
            # is the app FILLING the panel (applying a preset), and it
            # deliberately does not set off the refresh a keystroke does. Driven
            # through it, this driver read the right message out of
            # `_engine_text_notes` while the panel on screen still showed the
            # previous state, and the photograph proved the opposite of what the
            # numbers said. Each control is set the way a user sets it and the
            # panel's own signals do the rest.
            panel.chart_text.setText("")            # "and no custom text"
            panel.stamp_command.setChecked(True)
            panel.chart_text_size.setValue(float(pt))
            _i = panel.clip_side.findData(side)
            assert _i >= 0, f"no {side!r} entry in the clip-side pulldown"
            panel.clip_side.setCurrentIndex(_i)
            pump(app, 900)
            tab._update_margin_inspector()
            pump(app, 900)
            r = panel.get_recipe()

            lines = tab._bottom_sheet_text_lines(r)
            width = tab._sheet_text_width_mm(r)
            from workflow import text_edge_fit as tef
            from workflow.layout_engine import papers
            pw = float(papers.dimensions_mm(r.paper)[0])
            wo = tef.bottom_text_overflow(
                pw, float(getattr(r, "text_edge_clip_mm", 0.0) or 0.0), width,
                bool(getattr(r, "helper_markers", False)),
                float(getattr(r, "helper_marker_edge_mm", 0.0) or 0.0),
                float(getattr(r, "helper_marker_len_mm", 0.0) or 0.0),
                bool(getattr(r, "helper_markers_sides", True)),
                clip_border_mm=(float(getattr(r, "clip_border_width_mm", 0.0) or 0.0)
                                if getattr(r, "clip_border", False) else 0.0),
                clip_side=side)
            _all_over = TabChart._engine_text_notes(tab)[1]
            said = [m for m in _all_over
                    if "along the bottom is too wide" in m]
            # THE PANEL'S OWN CLIP FIGURE, which is the effective one and not
            # the typed one. When the panel and this driver disagree about
            # whether the line overflows, the disagreement is in here.
            _eff_clip = float(getattr(r, "effective_text_edge_clip_mm",
                                      getattr(r, "text_edge_clip_mm", 0.0)) or 0.0)
            _panel_room = tef.bottom_text_room_mm(
                pw, _eff_clip,
                bool(getattr(r, "helper_markers", False)),
                float(getattr(r, "helper_marker_edge_mm", 0.0) or 0.0),
                float(getattr(r, "helper_marker_len_mm", 0.0) or 0.0),
                bool(getattr(r, "helper_markers_sides", True)),
                clip_border_mm=(float(getattr(r, "clip_border_width_mm", 0.0) or 0.0)
                                if getattr(r, "clip_border", False) else 0.0),
                clip_side=side)
            rec = {
                "side": side, "size_pt": pt, "paper": r.paper,
                "clip_border_mm": float(getattr(r, "clip_border_width_mm", 0.0) or 0.0),
                "clip_mm": float(getattr(r, "text_edge_clip_mm", 0.0) or 0.0),
                "bottom_lines": lines,
                "predicted_width_mm": round(width, 2),
                "really_overflows": wo is not None,
                "overflow_mm": None if wo is None else round(wo.overlap_mm, 2),
                "panel_said": said,
                "all_overlap_warnings": _all_over,
                "effective_clip_mm": round(_eff_clip, 2),
                "panel_room_mm": round(float(_panel_room), 2),
                "clip_content_mode": str(getattr(r, "clip_content_mode", "")),
            }
            # THE ONE THING WORTH PHOTOGRAPHING is a real overflow, because a
            # picture of a quiet panel proves only that it is quiet.
            verdict = ("SILENT ON A REAL OVERFLOW" if (wo is not None and not said)
                       else "warned" if said
                       else "fits, quiet")
            if wo is not None:
                shot = out / f"{side}-{pt}pt.png"
                ok, why = capture_window(win, shot)
                rec["photo"] = shot.name if ok else f"REFUSED: {why}"
            rec["verdict"] = verdict
            rows.append(rec)
            print(f"    [{side:5s} {pt}pt] width={width:6.1f} mm  "
                  f"overflow={rec['overflow_mm']}  {verdict}", flush=True)
            if said:
                print(f"        {said[0][:150]}", flush=True)

    bad = [r for r in rows if r["verdict"] == "SILENT ON A REAL OVERFLOW"]
    (out / "bottom-stamp.json").write_text(
        json.dumps({"screen_locked": session_is_locked(),
                    "qt_qpa_platform": os.environ.get("QT_QPA_PLATFORM", "<unset>"),
                    "preset": pick[0], "silent_on_overflow": len(bad),
                    "rows": rows}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    print(f"\n    {len(bad)} combination(s) still silent on a real overflow",
          flush=True)
    print(f"    written {out / 'bottom-stamp.json'}", flush=True)
    win.close()
    pump(app, 300)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
