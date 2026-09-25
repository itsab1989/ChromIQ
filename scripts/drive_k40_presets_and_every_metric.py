#!/usr/bin/env python3
"""K40 (Knut, #182 5832026677), driven ON SCREEN, on any tree.

    CHROMIQ_DEMO_PACK=<built package folder> K40_DEMO_PRESETS=<preset pack> \\
    CHROMIQ_TREE=<tree> python drive_k40_presets_and_every_metric.py \\
        <out> <en|de> <presets|report>

Scenes:

  presets  Report-Limits-Every-Metric, Verification. Installed as a user
           installs them: the demo verification presets, a printtarg preset
           of 500 patches ("K40 printtarg 500 patches") and one whose patch
           set printtarg refuses ("K40 printtarg refused"). A second run
           (run2) is added to the drive's copy with a FROM PROFILE GAMUT
           chart of 216 patches through run1's profile, on which the tone row
           differs between the rule before K40-2 (device greys) and after
           (neutral aims). "Which presets can be used for verification?" is
           opened from Create Chart on run1 and photographed AT ONCE (K40-1:
           the "Working…" rows), then when every row is answered, then with
           the current chart, the 500-patch preset, the refused preset, a
           demo preset and a Full-layout-setup engine preset selected. The
           per-preset counts are written to ``preset-counts.json``. Then run2:
           the current chart's line (K40-2).
  report   Report-Limits-Every-Metric/run1 in the Measurement Report: each of
           the three dates' saved reports, Report Results photographed and
           every row's word read off the page (K40-3).

**NOBODY HAS TO CLICK.** The drive answers its own windows; the watchdog of
`drive_b42_k36` cancels anything else after three seconds and photographs it;
a deadline ends the run. The pack and the preset folder are copied, never
written.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

TREE = os.environ.get("CHROMIQ_TREE") or str(Path(__file__).resolve().parents[1])
sys.path.insert(0, TREE + "/scripts")
sys.path.insert(0, TREE)

OUT = Path(sys.argv[1]).resolve()
LANG, SCENE = sys.argv[2], sys.argv[3]
PROJECT = "Report-Limits-Every-Metric"
BIG = "K40 printtarg 500 patches"
BARE = "K40 printtarg refused"
FLS = "A4-484p-1page-Portrait-w7.5mm"
DEMO_CONTROL = "Verify 00 control, every row answered"
ARGYLL = Path("/Applications/Argyll/bin")
_WORDS = re.compile(r"\b(PASS|FAIL|COND|INFO|N-A)\b")


# ---------------------------------------------------------------------------
# Before the app starts: the presets, as a user installs them
# ---------------------------------------------------------------------------
def _payload() -> dict:
    return {"printtarg_-i": "i1", "printtarg_-p": "A4", "printtarg_-t": 300,
            "printtarg_-L": True, "printtarg_-a": 1.0, "auto_patches": False,
            "pages": 1, "attached_ti1": True}


def _install_presets() -> Path:
    presets = OUT / "sandbox" / "presets"
    dest = presets / "Create Chart"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    os.environ["CHROMIQ_PRESETS_DIR"] = str(presets)
    pack = Path(os.environ["K40_DEMO_PRESETS"])
    for p in sorted(pack.iterdir()):
        if p.suffix in (".json", ".ti1"):
            shutil.copy2(p, dest / p.name)
    from workflow.i1profiler_import import RgbPatch, write_ti1
    lv = [0, 12.5, 25, 37.5, 50, 62.5, 75, 87.5, 100]
    pts = [RgbPatch(r, g, b) for r in lv for g in lv for b in lv][:500]
    write_ti1(pts, dest / f"{BIG}.ti1")
    full = (dest / f"{BIG}.ti1").read_text(encoding="utf-8")
    # only the colour table: what printtarg refuses
    (dest / f"{BARE}.ti1").write_text(
        full.split("\nEND_DATA\n", 1)[0] + "\nEND_DATA\n", encoding="utf-8")
    for name in (BIG, BARE):
        (dest / f"{name}.json").write_text(json.dumps(
            {"chromiq_preset_version": 1, "tab": "create_chart", "name": name,
             "data": _payload()}, indent=2), encoding="utf-8")
    return dest


def _add_run2(work: Path) -> dict:
    """run2 of the drive's copy: run1's profile, and a FROM PROFILE GAMUT
    chart of 200 colours and the 8 corners laid out as run1's is."""
    from dataclasses import replace
    from workflow.gamut_target import (select_gamut_targets,
                                       write_colorimetric_reference,
                                       write_gamut_ti1)
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import LayoutRecipe
    proj = work / PROJECT
    r1, r2 = proj / "runs" / "run1", proj / "runs" / "run2"
    if r2.exists():
        shutil.rmtree(r2)
    (r2 / "verifications").mkdir(parents=True)
    for p in r1.iterdir():
        if p.is_file():
            shutil.copy2(p, r2 / p.name)
    shutil.copy2(r1 / "verifications" / "meta.json",
                 r2 / "verifications" / "meta.json")
    stem = f"{PROJECT}-verify"
    v = r2 / "verifications"
    sel = select_gamut_targets(r2 / f"{PROJECT}.icc", 200, "safe", "absolute",
                               bin_dir=ARGYLL)
    write_gamut_ti1(sel, v / f"{stem}.ti1")
    write_colorimetric_reference(sel, v / f"{stem}-reference.ti3")
    meta = json.loads((v / "meta.json").read_text(encoding="utf-8"))
    rec = LayoutRecipe.from_dict(meta["create_chart_ui"]["engine_recipe"])
    rec = replace(rec, seed=182, randomize=True)
    res, _ = build_from_recipe(str(v / f"{stem}.ti1"), str(v / stem), rec)
    lay = json.loads((v / f"{stem}.strips.json").read_text(encoding="utf-8"))
    from dataclasses import asdict
    lay.update({"engine": "chromiq", "engine_version": 1, "seed": res.seed,
                "recipe": asdict(rec)})
    (v / f"{stem}.channels.json").write_text(
        json.dumps({"layout": lay, "colorimetric_reference": True}),
        encoding="utf-8")
    pj = json.loads((proj / "project.json").read_text(encoding="utf-8"))
    pj["runs"] = ["run1", "run2"]
    (proj / "project.json").write_text(json.dumps(pj, indent=2),
                                       encoding="utf-8")
    return {"run2_patches": len(sel.targets) + len(sel.corners)}


# ---------------------------------------------------------------------------
# The window
# ---------------------------------------------------------------------------
def _items(dlg):
    from PyQt6.QtCore import Qt
    out = []
    stack = [dlg._tree.topLevelItem(i)
             for i in range(dlg._tree.topLevelItemCount())]
    while stack:
        it = stack.pop(0)
        out.append((it, it.data(0, Qt.ItemDataRole.UserRole)))
        stack += [it.child(j) for j in range(it.childCount())]
    return out


def _select(dlg, want) -> bool:
    """The row whose label starts with *want* (or the current chart row for
    ``None``), selected and scrolled to."""
    from PyQt6.QtWidgets import QAbstractItemView
    for it, row in _items(dlg):
        if row is None:
            continue
        hit = (getattr(row, "is_current_chart", False) if want is None
               else str(getattr(row, "label", "")).startswith(want))
        if hit:
            dlg._tree.setCurrentItem(it)
            dlg._tree.scrollToItem(
                it, QAbstractItemView.ScrollHint.PositionAtCenter)
            return True
    return False


def _detail(dlg) -> str:
    from PyQt6.QtWidgets import QLabel
    return "\n".join(w.text() for w in dlg._detail.findChildren(QLabel)
                     if w.isVisible())


def _scroll_detail_to(dlg, text: str) -> bool:
    """Scroll the detail pane so the first line containing *text* is near
    the top (the evenness lines sit below the fold)."""
    from PyQt6.QtCore import QPoint
    from PyQt6.QtWidgets import QLabel
    sa = getattr(dlg, "_detail_scroll", None)
    if sa is None or not text:
        return False
    for w in dlg._detail.findChildren(QLabel):
        if text in w.text() and w.isVisible():
            y = w.mapTo(dlg._detail, QPoint(0, 0)).y()
            sa.verticalScrollBar().setValue(max(0, y - 60))
            return True
    return False


def _row_record(row) -> dict:
    a = row.assessment
    return {"label": row.label, "builtin": row.builtin,
            "group": row.group, "patches": row.patches, "pages": row.pages,
            "checked": a.checked, "answered": len(a.answered),
            "asked": len(a.asked), "starred": row.starred,
            "pending": bool(getattr(row, "pending", False)),
            "missing": [list(m) for m in a.missing]}


def _presets(d, rec):
    from core.i18n import tr
    import drive_b42_k36 as K36
    rec.update(_add_run2(d.work))
    d.open_project(PROJECT)
    d.set_bar(run="run1", run_type="Verification")
    d.goto_tab("chart")
    tab = d.win._tab_chart
    try:
        tab._user_switch_mode("manual")
    except Exception:                                     # noqa: BLE001
        pass
    yield 2500
    btn = tab._preset_verify_btn
    rec["button"] = btn.text()
    t0 = time.monotonic()
    d.later(btn.click)
    yield 300
    dlg = None
    for _ in range(60):
        dlg = d.top_dialog("PresetVerificationDialog")
        if dlg is not None:
            break
        yield 100
    rec["opened_after_s"] = round(time.monotonic() - t0, 2)
    if dlg is None:
        d.note("THE WINDOW DID NOT OPEN")
        return
    dlg.resize(1400, 860)
    rec["working_at_open"] = (dlg.waiting_count()
                              if hasattr(dlg, "waiting_count") else None)
    rec["figures_at_open"] = dlg._figures.text()
    d.note(f"opened after {rec['opened_after_s']} s; working "
           f"{rec['working_at_open']}; {rec['figures_at_open']}")
    _select(dlg, BIG)
    yield 200
    d.shot(dlg, f"{LANG}-{PHASE}-01-at-once")
    rec["detail_big_at_open"] = _detail(dlg)
    # every row answered: the window redraws itself; the drive only waits
    t1 = time.monotonic()
    for _ in range(600):
        still = (dlg._still_laying_out() if hasattr(dlg, "_still_laying_out")
                 else False)
        if not still:
            break
        yield 200
    rec["answered_after_s"] = round(time.monotonic() - t1, 2)
    rec["figures_done"] = dlg._figures.text()
    d.note(f"every row answered {rec['answered_after_s']} s later; "
           f"{rec['figures_done']}")
    counts = {"current": _row_record(dlg._current) if dlg._current else None,
              "rows": [_row_record(r) for r in dlg._rows],
              "type": dlg.current_type(), "set": dlg.current_set()}
    (d.out / "preset-counts.json").write_text(
        json.dumps(counts, indent=2, ensure_ascii=False), encoding="utf-8")
    even = tr("Maximum ΔE00, between two of the nine sheet areas")
    shots = [(None, "02-current-chart", even), (BIG, "03-printtarg-500", even),
             (BARE, "04-printtarg-refused",
              tr("printtarg, which lays this preset's page out, could not "
                 "lay it out, so where its patches will sit on the page is "
                 "not known.")[:40]),
             (DEMO_CONTROL, "05-demo-control", even),
             (FLS, "06-full-layout-setup-engine", even)]
    for want, name, anchor in shots:
        ok = _select(dlg, want)
        yield 700
        for _ in range(3):
            # again, while the pane's range catches up with its new lines
            _scroll_detail_to(dlg, anchor)
            yield 400
        sb = dlg._detail_scroll.verticalScrollBar() \
            if hasattr(dlg, "_detail_scroll") else None
        if sb is not None:
            d.note(f"   detail pane scrolled to {sb.value()} of {sb.maximum()}")
        rec[f"detail_{name}"] = _detail(dlg) if ok else "(no such row)"
        d.note(f"{name}: {rec[f'detail_{name}'][:300]!r}")
        d.shot(dlg, f"{LANG}-{PHASE}-{name}")
    dlg.reject()
    d._modal_closed()
    yield 1500
    # K40-2: the current chart of run2, a 216-patch FROM PROFILE GAMUT chart
    d.set_bar(run="run2", run_type="Verification")
    d.goto_tab("chart")
    yield 3000
    d.later(tab._preset_verify_btn.click)
    yield 1500
    dlg = K36._wait(d, "PresetVerificationDialog")
    if dlg is None:
        d.note("THE WINDOW DID NOT OPEN ON RUN2")
        return
    dlg.resize(1400, 860)
    _select(dlg, None)
    yield 900
    for _ in range(3):
        _scroll_detail_to(dlg,
                          tr("Maximum ΔL*, single-colour ramps 30 % to 70 %"))
        yield 400
    rec["run2_current"] = _row_record(dlg._current) if dlg._current else None
    rec["detail_run2_current"] = _detail(dlg)
    tone = tr("Maximum ΔL*, single-colour ramps 30 % to 70 %")
    rec["run2_tone_answered"] = (
        "ramps_30_70_dl_max" in (dlg._current.assessment.answered
                                 if dlg._current else ()))
    d.note(f"run2 current chart: {rec['run2_current']}; tone row answered: "
           f"{rec['run2_tone_answered']} ({tone})")
    d.shot(dlg, f"{LANG}-{PHASE}-07-run2-current-chart")
    dlg.reject()
    d._modal_closed()
    yield 1000


def _words_of(page: str, names: dict) -> dict:
    """Report Results prints a row's name on one line and its word on the
    next, perhaps with note markers; the reading guide above it names the
    rows too, followed by prose."""
    lines = [ln.strip() for ln in page.splitlines()]
    words = {}
    for rid, name in names.items():
        for i, ln in enumerate(lines[:-1]):
            # the word may carry note markers after it: "FAIL 2) 3)"
            m = re.fullmatch(r"(PASS|FAIL|COND|INFO|N-A)(?:\s*\d+\))*",
                             lines[i + 1])
            if ln == name and m:
                words[rid] = m.group(1)
                break
    return words


def _report(d, rec):
    import drive_b42_k36 as K36
    from core.i18n import tr
    from workflow.compliance_sets import ROWS
    d.open_project(PROJECT)
    d.set_bar(run="run1", run_type="Verification")
    d.pump(1200)
    d.launch_tool("measurement_report")
    yield 4500
    dlg = K36._wait(d, "MeasurementReportDialog")
    if dlg is None:
        d.note("NO REPORT WINDOW")
        return
    dlg.resize(1400, 980)
    yield 1500
    combo = dlg._saved_combo
    rec["saved_list"] = [combo.itemText(i) for i in range(combo.count())]
    names = {r.id: tr(r.label) for r in ROWS
             if r.status in ("now", "build", "ref")}
    rec["dates"] = {}
    for k, date in enumerate(("2026-11-02", "2026-11-09", "2026-11-16"), 1):
        idx = next((i for i in range(combo.count())
                    if date in combo.itemText(i)), None)
        if idx is None:
            d.note(f"no saved report of {date}")
            continue
        combo.setCurrentIndex(idx)
        combo.activated.emit(idx)
        yield 4000
        page = K36._view_text(dlg)
        (d.out / f"{LANG}-report-{date}.txt").write_text(page,
                                                         encoding="utf-8")
        words = _words_of(page, names)
        rec["dates"][date] = words
        d.note(f"{date}: {len(words)} of {len(names)} rows read: {words}")
        if K36._scroll_to(dlg, tr("Report Results")):
            # …and on, so the twenty rows of Report Results fill the view
            from PyQt6.QtWidgets import QTextBrowser, QTextEdit
            for v in dlg.findChildren((QTextBrowser, QTextEdit)):
                if v.isVisible() and len(v.toPlainText()) > 200:
                    sb = v.verticalScrollBar()
                    sb.setValue(min(sb.maximum(),
                                    sb.value() + int(v.height() * 0.6)))
            yield 900
        d.shot(dlg, f"{LANG}-after-report-{k}-{date}")
    dlg.reject()
    d._modal_closed()
    yield 1000


def script(d):
    import drive_b42_k36 as K36
    rec = d.record
    rec.update({"scene": SCENE, "language": LANG, "phase": PHASE,
                "tree": TREE, "mode": "ON SCREEN"})
    K36._install_watchdog(d, rec)
    if SCENE == "presets":
        yield from _presets(d, rec)
    elif SCENE == "report":
        yield from _report(d, rec)
    yield 800


PHASE = os.environ.get("K40_PHASE", "after")

if __name__ == "__main__":
    if SCENE == "presets":
        _install_presets()
    from userdrive import Drive
    drive = Drive(OUT, projects=[PROJECT], language=LANG, size=(1500, 1000))
    rc = drive.run(script)
    print(f"rc={rc}")
    sys.exit(rc)
