#!/usr/bin/env python3
"""#182 beta 39, K28a, driven ON SCREEN as a user (scripts/userdrive.py).

On the project `scripts/make_evenness_demo.py` builds (Report-Limits-Evenness)
and the verification-preset demo pack (`make_verification_preset_demos.py`):

    E  E8: the Measurement Report on run8 (the 837-patch chart printed
       RELATIVE on a paper of L* 95.5): the colour accuracy rows read relative
       to the paper white, the two evenness rows judged, dates 2 and 3;
       and the same dates on run1 (absolute) beside it;
    G  B8-483: "Which presets can be used for verification?" on the R14 FAIL
       (a bunched grey ramp) and R14 PASS presets, and on the control; the
       picked steps of each chart, from the app's own `grey_balance_block`;
    P  R2: the Measure tab's pre-flight on run3 (837 patches, not measured),
       photographed whole, its box and frame measured;
    H  the "Where are my files?" card, scrolled to the ChromIQ folder rows.

    export CHROMIQ_DEMO_PACK=<folder holding Report-Limits-Evenness>
    python scripts/drive_beta39_k28a.py <out-dir> [--lang de] [--only P]
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import Drive                                   # noqa: E402
from drive_evenness import (NAME, ROWS, _all_items, _detail,   # noqa: E402
                            _report_text, _scroll_to)


def _install_demo_presets(d) -> None:
    """The pack, copied into the SANDBOXED Create Chart preset folder the way
    a user installs it."""
    import make_verification_preset_demos as GEN
    from core.preset_store import tab_dir
    pack = d.out / "preset-pack" / GEN.FOLDER
    if pack.exists():
        shutil.rmtree(pack)
    GEN.build(pack)
    dest = tab_dir("create_chart")
    assert str(d.out) in str(dest), f"presets NOT sandboxed: {dest}"
    dest.mkdir(parents=True, exist_ok=True)
    for src in sorted(pack.iterdir()):
        if src.suffix in (".json", ".ti1"):
            shutil.copy2(src, dest / src.name)
    d.note(f"demo presets installed into {dest}")


def _report(d, run: str, date: str, tag: str):
    d.set_bar(run_type="Verification", run=run)
    yield 900
    d.launch_tool("measurement_report")
    yield 5000
    dlg = d.top_dialog("MeasurementReportDialog")
    combo = dlg._saved_combo
    for i in range(combo.count()):
        if combo.itemText(i).startswith(date):
            d.pick(combo, combo.itemText(i))
            break
    yield 3500
    text = _report_text(dlg)
    lines = [ln.strip() for ln in text.splitlines()
             if ln.strip().startswith(ROWS)
             or "How the colours were judged" in ln]
    d.record[tag] = {"shown": combo.currentText(), "lines": lines}
    d.note(f"{tag} {run} {combo.currentText()!r}")
    for ln in lines:
        d.note(f"   {tag} | {ln[:260]}")
    _scroll_to(dlg, "How the colours were judged")
    yield 700
    d.shot(dlg, f"{tag}-{run}-{date}-how-judged")
    _scroll_to(dlg, "Report Results")
    dlg._view.find(ROWS[0])
    dlg._view.ensureCursorVisible()
    sb = dlg._view.verticalScrollBar()
    sb.setValue(sb.value() + 260)
    yield 700
    d.shot(dlg, f"{tag}-{run}-{date}-evenness-rows")
    dlg.reject()
    yield 1200


def _grey_steps(chart: Path) -> dict:
    """What the report's own grey block says about *chart* read as a
    flawless print."""
    import numpy as np
    import workflow.measurement_report as MR
    from workflow.ti3_analysis import parse_ti3
    data = parse_ti3(chart)
    rgb = MR._rgb_to_0_100(np.asarray(data.rgb, float))
    lab = [MR.xyz_to_lab((x / 100, y / 100, z / 100)) for x, y, z in data.xyz]
    ref = {sid: tuple(lab[i]) for i, sid in enumerate(data.sample_ids)}
    b = MR.grey_balance_block(rgb, lab, ref, data.sample_ids)
    levels = sorted({round(float(r.mean()), 1) for r in rgb
                     if r.max() - r.min() <= MR.GREY_SPREAD_TOL}, reverse=True)
    return {"grey_levels_on_chart": levels, "picked": b.get("picked_levels"),
            "reason": b.get("reason"), "missing_level": b.get("missing_level")}


def script(d, only: str = ""):
    rec = d.record
    want = (lambda k: not only or k in only)
    d.open_project(NAME)
    yield 800

    if want("E"):
        yield from _report(d, "run8", "2026-10-08", "E1")
        yield from _report(d, "run8", "2026-10-15", "E2")
        yield from _report(d, "run1", "2026-10-15", "E3")

    if want("G"):
        _install_demo_presets(d)
        d.set_bar(run_type="Profiling", run="run1")
        d.goto_tab("chart")
        yield 1500
        d.later(d.win._tab_chart._open_preset_verification_window)
        yield 6000
        pdlg = d.top_dialog("PresetVerificationDialog")
        from core.preset_store import sidecar_path
        rec["G"] = {}
        for tag, label in (("G1-R14-FAIL", "Verify R14 FAIL"),
                           ("G2-R14-PASS", "Verify R14 PASS"),
                           ("G3-control", "Verify 00 control")):
            item = next((it for it in _all_items(pdlg._tree)
                         if label in it.text(0) and it.parent() is not None),
                        None)
            if item is None:
                d.note(f"   G {tag}: NO ITEM {label!r}")
                continue
            pdlg._tree.scrollToItem(item)
            pdlg._tree.setCurrentItem(item)
            yield 1500
            lines = [ln for ln in _detail(pdlg) if "grey" in ln.lower()
                     or "Grey" in ln or "Grau" in ln]
            chart = sidecar_path("create_chart", item.text(0).strip(), ".ti1")
            steps = _grey_steps(chart) if chart.is_file() else {"chart": None}
            rec["G"][tag] = {"item": item.text(0), "lines": lines, **steps}
            d.note(f"   G {tag}: {item.text(0)!r}")
            for ln in lines:
                d.note(f"      {ln[:220]}")
            d.note(f"      grey levels on the chart: "
                   f"{steps.get('grey_levels_on_chart')}")
            d.note(f"      picked: {steps.get('picked')}  reason: "
                   f"{steps.get('reason')}  nothing near: "
                   f"{steps.get('missing_level')}")
            d.shot(pdlg, tag)
        pdlg.reject()
        yield 1500

    if want("P"):
        if "small" in only:
            # A 13-inch Air with the Dock at the bottom has about 860 px of
            # work area; this screen has 1079. The guard is handed 860 so the
            # fallback can be seen ON SCREEN; nothing else is changed.
            from ui.tabs import tab_measure as _TM
            _TM._preflight_work_height = lambda _b: 860
            d.note("P: the guard is told the work area is 860 px (13-inch "
                   "Air, Dock at the bottom)")
        d.goto_tab("chart")
        d.set_bar(run_type="Verification", run="run3")
        yield 1200
        d.win._tab_measure._preflight_silenced.clear()
        d.later(lambda: d.win._tabs.setCurrentIndex(2))
        yield 2500
        from PyQt6.QtGui import QGuiApplication
        from PyQt6.QtWidgets import QMessageBox
        from ui.tabs import tab_measure as TM
        box = d.modal()
        if isinstance(box, QMessageBox):
            yield 800
            fg, g = box.frameGeometry(), box.geometry()
            scr = box.screen() or QGuiApplication.primaryScreen()
            need = max(box.sizeHint().height(), box.minimumSizeHint().height())
            rec["P"] = {
                "language": d.settings.get("language", "en"),
                "box_w": g.width(), "box_h": g.height(),
                "frame_w": fg.width(), "frame_h": fg.height(),
                "caption": fg.height() - g.height(),
                "guard_need_plus_caption": need + TM._PREFLIGHT_CAPTION,
                "spacer": TM.preflight_text_width(box),
                "screen_work_area": [scr.availableGeometry().width(),
                                     scr.availableGeometry().height()],
                "full_paragraph": "threshold to zero" in box.text(),
                "ok_bottom_inside": box.mapToGlobal(
                    box.buttons()[0].geometry().bottomLeft()).y()
                <= fg.y() + fg.height(),
                "fits_13in_dock_hidden_918": fg.height() <= 918,
                "fits_13in_dock_bottom_860": fg.height() <= 860,
            }
            for k, v in rec["P"].items():
                d.note(f"   P {k}: {v}")
        said = d.answer("OK", name=f"P-preflight-run3-{d.settings.get('language', 'en')}"
                        + ("-860" if "small" in only else ""),
                        within_ms=9000)
        rec["P_text"] = said
        yield 1200

    if want("H"):
        from PyQt6.QtWidgets import QLabel

        from ui.dialogs.welcome_dialog import WelcomeDialog
        from onscreen_capture import capture_window
        dlg = WelcomeDialog(d.settings, d.win,
                            initial_mode="light")
        dlg.resize(1100, 950)
        dlg.show()
        yield 1500
        dlg._on_card_clicked("file_guide")
        yield 1500
        # scroll to the "Your ChromIQ folder/" rows
        body = next((w for w in dlg._steps_host.findChildren(QLabel)
                     if "Your ChromIQ folder/" in w.text()
                     or "Dein ChromIQ" in w.text()), None)
        bar = dlg._detail_scroll.verticalScrollBar()
        if body is not None:
            doc_frac = body.text().find("Your ChromIQ folder/")
            if doc_frac < 0:
                doc_frac = body.text().find("ChromIQ-Ordner")
            frac = max(0.0, doc_frac / max(1, len(body.text())) - 0.03)
            bar.setValue(int(body.y() + body.height() * frac))
        yield 1200
        for i in range(2):
            ok, why = capture_window(dlg, d.shots / f"H-file-guide-{i + 1}.png")
            d.note(f"   [photo] H-file-guide-{i + 1}.png: {'ok' if ok else why}")
            bar.setValue(bar.value() + 350)
            yield 900
        rec["H_rows"] = [ln for ln in (body.text() if body else "").split("<")
                         if "ChromIQ folder" in ln or "more than one project" in ln
                         or "several projects" in ln][:6]
        dlg.close()
        yield 800
    yield 300


if __name__ == "__main__":
    args = sys.argv[1:]
    lang = args[args.index("--lang") + 1] if "--lang" in args else "en"
    only = args[args.index("--only") + 1] if "--only" in args else ""
    d = Drive(Path(args[0]), projects=[NAME], language=lang)
    rc = d.run(lambda dd: script(dd, only))
    print(json.dumps({k: v for k, v in d.record.items()
                      if k[:1] in "EGPH"}, indent=1, default=str)[:8000])
    sys.exit(rc)
