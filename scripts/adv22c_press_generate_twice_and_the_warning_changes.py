#!/usr/bin/env python3
"""Adversary 22c — press Generate twice, change nothing, and the warning
reports a different number of cut characters.

`_engine_text_notes` predicts the line that will be stamped down the right edge
with

    _pm.chart_layout_name = self._active_layout_name()

but `_on_generate` — Manual's ordinary targen build — never sets that field, so
the sheet stamps the targen command. `_active_layout_name()` answers with
`Path(self._current_ti1_path).stem` for ANY chart that has been built, so from
the first build onwards the panel predicts "Chart layout <stem>" for a sheet
that will carry "targen -d2 -f… -e… -B… -G -g… <stem>".

Two consecutive builds with nothing touched between them cannot cut a different
number of characters off the same note. This drives exactly that, and crops the
right margin of both rendered sheets to show the printed line is the same one.
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
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import (QApplication, QDialog,       # noqa: E402
                             QMessageBox, QAbstractScrollArea)
from onscreen_capture import capture_window                # noqa: E402


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.005)


def crop_right_margin(tiff: Path, dest: Path, mm: float = 22.0) -> str:
    try:
        from PIL import Image
        im = Image.open(tiff)
        w, h = im.size
        dpi = im.info.get("dpi", (300, 300))[0] or 300
        px = int(mm / 25.4 * float(dpi))
        strip = im.crop((max(0, w - px), 0, w, h)).convert("L")
        strip = strip.rotate(-90, expand=True)
        strip.save(dest)
        return f"{dest.name} {strip.size} dpi={dpi}"
    except Exception as exc:                       # noqa: BLE001
        return f"crop failed: {exc}"


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert os.environ.get("QT_QPA_PLATFORM") != "offscreen", "ON SCREEN"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv22c-"))
    settings = AppSettings()
    for k, v in (("custom_output_path", str(work)), ("language", "en"),
                 ("use_chromiq_layout_engine", True),
                 ("restore_last_session", False), ("appearance", "dark"),
                 ("margin_inspector_show", True),
                 ("auto_update_preview", False)):
        settings.set(k, v)
    QDialog.exec = lambda self: 1                    # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore
    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    from ui.theme import apply_appearance
    TabChart._confirm_displacing_results = lambda self, *a, **k: True
    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.resize(1620, 1080)
    win.show()
    win.raise_()
    pump(app, 2200)
    print("    window on screen:", win.isVisible(), flush=True)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 700)
    tab._user_switch_mode("manual")
    pump(app, 1400)
    tab._manual_target_name_edit.setText("adv22c")
    pump(app, 400)
    p = tab._manual_layout_panel
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    pump(app, 900)
    if p.use_instr_margins.isChecked():
        p.use_instr_margins.setChecked(False)
        pump(app, 300)
    for k, v in (("t", 12.0), ("b", 14.0), ("l", 12.0), ("r", 12.0)):
        p.margins[k].setValue(v)
    p.helper_markers_cb.setChecked(False)
    p.text_edge.setValue(4.0)
    p.chart_text.setText("")
    p.stamp_command.setChecked(False)
    p.chart_text_size.setValue(14.0)
    tab._manual_stamp_cmd_check.setChecked(True)
    tab._manual_chart_notes_edit.setText("Canon Pro-1000 / Photo Rag 308")
    pump(app, 1500)

    def predicted():
        pm = tab._collect_manual()
        pm.chart_notes = (tab._manual_chart_notes_edit.text() or "").strip()
        pm.stamp_commands = True
        pm.chart_layout_name = tab._active_layout_name()
        np_ = tab._estimate_patch_total() or int(getattr(pm, "patches", 0) or 0)
        from workflow import tiff_metadata as _tmeta
        return _tmeta._JOIN.join(tab._creator.stamp_lines(pm, int(np_)))

    def built_line():
        """The line the sheet really carries: `_stamp_tiff_metadata`'s own
        call, on the params the build used and the count it counted."""
        pm = tab._last_params
        stem = tab._file_mgr.chart_stem(cal_target=getattr(pm, "cal_target", False))
        t = tab._margin_tiffs[0]
        n = tab._creator._count_patches_in_ti1(t.parent / f"{stem}.ti1") \
            or getattr(pm, "patches", 0) or 0
        from workflow import tiff_metadata as _tmeta
        return (_tmeta._JOIN.join(tab._creator.stamp_lines(pm, n)),
                getattr(pm, "chart_layout_name", None), n)

    def notes_notice():
        a, _ = TabChart._engine_text_notes(tab)
        for s in a:
            if "cut off and replaced" in s:
                return s
        return ""

    def build(tag):
        tab._generate_btn.click()
        for _ in range(900):
            pump(app, 200)
            if tab._generate_btn.isEnabled() and getattr(tab, "_margin_tiffs", None):
                break
        pump(app, 2500)
        line, cln, n = built_line()
        rec = {"predicted": predicted(),
               "predicted_len": len(predicted()),
               "built_stamp": line, "built_len": len(line),
               "build_chart_layout_name": cln,
               "build_patch_count": n,
               "_active_layout_name": tab._active_layout_name(),
               "notice": notes_notice(),
               "tiff": str(tab._margin_tiffs[0])}
        rec["crop"] = crop_right_margin(Path(rec["tiff"]),
                                        out / f"C-{tag}-right-margin.png")
        return rec

    rec = {}
    rec["first"] = build("first")
    print("    FIRST  _active_layout_name:", rec["first"]["_active_layout_name"],
          flush=True)
    print("      predicted:", rec["first"]["predicted"], flush=True)
    print("      built    :", rec["first"]["built_stamp"], flush=True)
    print("      notice   :", rec["first"]["notice"][:150], flush=True)

    rec["second"] = build("second")
    print("    SECOND _active_layout_name:", rec["second"]["_active_layout_name"],
          flush=True)
    print("      predicted:", rec["second"]["predicted"], flush=True)
    print("      built    :", rec["second"]["built_stamp"], flush=True)
    print("      notice   :", rec["second"]["notice"][:150], flush=True)
    print("    SAME SHEET, SAME SETTINGS, SAME BUILT STAMP:",
          rec["first"]["built_stamp"] == rec["second"]["built_stamp"], flush=True)
    print("    NOTICE CHANGED:", rec["first"]["notice"] != rec["second"]["notice"],
          flush=True)

    ok, why = capture_window(win, out / "C1-the-second-build.png")
    print("    photograph:", ok, why, flush=True)
    (out / "adv22c.json").write_text(
        json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
    win.close()
    pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
