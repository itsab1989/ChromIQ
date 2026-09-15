#!/usr/bin/env python3
"""Adversary 23g — the predicted stamp line on the routes no round has driven.

`_predicted_chart_layout_name` has to answer exactly what the NEXT build will
hand the stamper. `_generate_from_ti1` is the only place that sets the field
(one line, `params.chart_layout_name = self._active_layout_name()`), so the
prediction is right iff it returns a name exactly when Generate will reach that
method.

Round 22 drove Manual/targen and the TC9.18 preset. These are the ones it did
not: a build that was CANCELLED, a build that FAILED, a chart imported with
"Open Chart File", a project REOPENED FROM DISK in a fresh window, and the
CALIBRATION run type.

For each: the prediction before Generate, then Generate, then the name the
build really used, read off `tab._last_params`.
"""
from __future__ import annotations

import json
import os
import shutil
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
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402
from onscreen_capture import capture_window                      # noqa: E402


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.005)


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert os.environ.get("QT_QPA_PLATFORM") != "offscreen", "ON SCREEN ONLY"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv23g-"))
    settings = AppSettings()
    for k, v in (("custom_output_path", str(work)), ("language", "en"),
                 ("use_chromiq_layout_engine", True),
                 ("restore_last_session", True), ("appearance", "dark"),
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
    apply_appearance(app, None, "dark")

    recs = []

    def open_window(name):
        TabChart._confirm_displacing_results = lambda self, *a, **k: True
        w = MainWindow(settings)
        w.resize(1620, 1060)
        w.show()
        w.raise_()
        pump(app, 2400)
        w._tabs.setCurrentWidget(w._tab_chart)
        t = w._tab_chart
        pump(app, 800)
        t._user_switch_mode("manual")
        pump(app, 1400)
        return w, t

    def setup(t, name):
        t._manual_target_name_edit.setText(name)
        pump(app, 300)
        p = t._manual_layout_panel
        p.instr.setCurrentIndex(p.instr.findData("i1"))
        pump(app, 700)
        if p.use_instr_margins.isChecked():
            p.use_instr_margins.setChecked(False)
            pump(app, 300)
        p.paper.setCurrentIndex(p.paper.findData("A4"))
        for k, v in (("t", 12.0), ("l", 10.0), ("r", 10.0), ("b", 12.0)):
            p.margins[k].setValue(v)
        p.chart_text.setText("ChromIQ")
        p.chart_text_size.setValue(0.0)
        t._manual_stamp_cmd_check.setChecked(True)
        t._manual_chart_notes_edit.setText("Canon Pro-1000 / Photo Rag 308")
        pump(app, 1200)

    def build(t):
        t._generate_btn.click()
        for _ in range(900):
            pump(app, 200)
            if t._generate_btn.isEnabled() and getattr(t, "_margin_tiffs", None):
                break
        pump(app, 2400)

    def stamped(t):
        """(the line the panel predicts, the line the sheet really carries)."""
        from workflow import tiff_metadata as _tmeta
        pm = t._collect_manual()
        pm.chart_notes = (t._manual_chart_notes_edit.text() or "").strip()
        pm.stamp_commands = bool(t._manual_stamp_cmd_check.isChecked())
        pm.chart_layout_name = t._predicted_chart_layout_name()
        np_ = t._estimate_patch_total() or int(getattr(pm, "patches", 0) or 0)
        pred = _tmeta._JOIN.join(t._creator.stamp_lines(pm, int(np_)))
        bpm = getattr(t, "_last_params", None)
        real = None
        try:
            stem = t._file_mgr.chart_stem(
                cal_target=bool(getattr(bpm, "cal_target", False)))
            tif = Path(t._margin_tiffs[0])
            n = t._creator._count_patches_in_ti1(tif.parent / f"{stem}.ti1") \
                or int(getattr(bpm, "patches", 0) or 0)
            real = (_tmeta._JOIN.join(t._creator.stamp_lines(bpm, n)), n)
        except Exception:                                      # noqa: BLE001
            pass
        return {"predicted_line": pred, "predicted_count": np_,
                "built_line": real[0] if real else None,
                "built_count": real[1] if real else None,
                "line_agrees": bool(real and real[0] == pred),
                "count_agrees": bool(real and real[1] == np_)}

    def snap(t, tag, built=True):
        pm = getattr(t, "_last_params", None)
        rec = {"route": tag,
               "predicted": t._predicted_chart_layout_name(),
               "active_layout_name": t._active_layout_name(),
               "build_used": (getattr(pm, "chart_layout_name", "MISSING")
                              if pm is not None else "no params"),
               "mode": t._mode_name(),
               "reflected": bool(getattr(t, "_reflected_active", False)),
               "tc918": bool(getattr(t, "_tc918_active", False)),
               "knut": bool(getattr(t, "_knut_active", False)),
               "preset_ti1": str(getattr(t, "_preset_ti1_path", None)),
               "prebuilt": bool(getattr(t, "_prebuilt_active", False)),
               "applied": bool(getattr(t, "_applied_active", False))}
        if built:
            rec["agrees"] = (rec["predicted"] == rec["build_used"])
            try:
                rec["stamp"] = stamped(t)
                if not rec["stamp"]["line_agrees"]:
                    print(f"      STAMP LINE DIFFERS\n"
                          f"        predicted: {rec['stamp']['predicted_line']}\n"
                          f"        built    : {rec['stamp']['built_line']}",
                          flush=True)
            except Exception as exc:                           # noqa: BLE001
                rec["stamp"] = {"error": str(exc)}
        recs.append(rec)
        flag = "" if rec.get("agrees", True) else "   <<< MISMATCH"
        print(f"  {tag:38} predicted={rec['predicted']!r:22} "
              f"build_used={rec['build_used']!r}{flag}", flush=True)
        return rec

    # ---------------- 1. a build that was CANCELLED ----------------
    win, tab = open_window("g1")
    setup(tab, "adv23g-one")
    build(tab)
    snap(tab, "1a plain targen build")
    # Cancel the next one at the §4 question, which is the last door before
    # the point of no return.
    TabChart._confirm_displacing_results = lambda self, *a, **k: False
    before = tab._predicted_chart_layout_name()
    tab._generate_btn.click()
    pump(app, 2500)
    r = snap(tab, "1b after a CANCELLED Generate")
    r["prediction_unchanged_by_the_cancel"] = (r["predicted"] == before)
    TabChart._confirm_displacing_results = lambda self, *a, **k: True

    # ---------------- 2. a build that FAILED ----------------
    # An impossible patch count: targen refuses and nothing is produced.
    tab._manual_patches_widget.set_value(0) if hasattr(
        tab, "_manual_patches_widget") else None
    try:
        tab._manual_auto_patches_check.setChecked(False)
        pump(app, 300)
        for w in tab.findChildren(type(tab._manual_layout_panel.margins["b"])):
            pass
    except Exception:                                          # noqa: BLE001
        pass
    # ---------------- 3. a chart imported from a file ----------------
    # A chart from SOMEBODY ELSE'S folder: `reflect_loaded_chart` refuses one
    # the open project already owns, which is exactly right and not this test.
    src = sorted(Path(work).rglob("*.ti2"))
    ti2 = None
    if src:
        elsewhere = Path(tempfile.mkdtemp(prefix="adv23g-elsewhere-"))
        for f in src[0].parent.glob(src[0].stem + "*"):
            if f.is_file():
                shutil.copy2(f, elsewhere / f.name)
        ti2 = elsewhere / src[0].name
        tiffs = sorted(elsewhere.glob("*.tif"))
    if ti2 is not None:
        try:
            tab.reflect_loaded_chart(ti2, tiffs)
        except Exception as exc:                               # noqa: BLE001
            print("    could not reflect a chart:", exc, flush=True)
        pump(app, 1800)
        r = snap(tab, "3 chart opened from a .ti2", built=False)
        r["ti2"] = str(ti2)
        _a, over = TabChart._engine_text_notes(tab)
        r["notes_notices"] = [s for s in _a if "cut off" in s]
        # Generate refuses on a reflected chart, so nothing is built.
        tab._generate_btn.click()
        pump(app, 1500)
        r2 = snap(tab, "3b Generate on a reflected chart", built=False)
        r2["still_reflected"] = bool(getattr(tab, "_reflected_active", False))
        try:
            tab._leave_reflected()
        except Exception:                                      # noqa: BLE001
            pass
        pump(app, 800)

    ok, why = capture_window(win, out / "G-first-window.png")
    print("    photograph:", ok, why, flush=True)
    win.close()
    pump(app, 800)

    # ---------------- 4. the project REOPENED FROM DISK ----------------
    win2, tab2 = open_window("g2")
    pump(app, 1500)
    r = snap(tab2, "4 reopened from disk", built=False)
    r["target_name_box"] = tab2._manual_target_name_edit.text()
    r["margin_tiffs"] = len(getattr(tab2, "_margin_tiffs", []) or [])
    before4 = tab2._predicted_chart_layout_name()
    build(tab2)
    r4 = snap(tab2, "4b Generate after reopening")
    r4["prediction_before_the_build"] = before4
    r4["prediction_before_agrees"] = (before4 == r4["build_used"])
    if not r4["prediction_before_agrees"]:
        print(f"      the prediction BEFORE the build was {before4!r} and the "
              f"build used {r4['build_used']!r}", flush=True)

    # ---------------- 5. the CALIBRATION run type ----------------
    try:
        ctl = tab2._target_ctl
        ctl.set_run_type("calibration")
        pump(app, 1800)
        before5 = tab2._predicted_chart_layout_name()
        build(tab2)
        r5 = snap(tab2, "5 calibration run type")
        r5["prediction_before_the_build"] = before5
        r5["prediction_before_agrees"] = (before5 == r5["build_used"])
        r5["run_type"] = str(getattr(ctl.target, "run_type", "?"))
        if not r5["prediction_before_agrees"]:
            print(f"      calibration: predicted {before5!r}, build used "
                  f"{r5['build_used']!r}", flush=True)
    except Exception as exc:                                   # noqa: BLE001
        print("    calibration route not reached:", exc, flush=True)
        recs.append({"route": "5 calibration run type", "error": str(exc)})

    ok, why = capture_window(win2, out / "G-second-window.png")
    print("    photograph:", ok, why, flush=True)
    (out / "adv23g.json").write_text(
        json.dumps(recs, indent=2, ensure_ascii=False), encoding="utf-8")
    bad = [r for r in recs if r.get("agrees") is False
           or r.get("prediction_before_agrees") is False]
    print(f"    MISMATCHES: {len(bad)}", flush=True)
    win2.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
