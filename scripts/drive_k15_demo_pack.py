#!/usr/bin/env python3
"""K15 (Knut, beta 34): the rebuilt demo pack, opened as a user opens it.

Knut: *"The demo projects package must be updated to follow all the rules"*.
Every claim the rebuild makes is looked at here in the real window, with the
real pack copied into a sandbox the way a user unzips it (the project has
MOVED, which is the state every download is in):

A. Threshold-Series, Verification, run1: the "Report shown" list names each
   saved report "<created> · <type> · <set> · One date"; the 2026-01-05
   report reads PASS and the 2026-01-19 report reads FAIL, as the README
   says; selecting one ticks exactly its own measurement; the paper white
   line is a neutral paper below L* 100, not the blue D65 white.
B. Threshold-Series, Profiling, run1: the only report type offered is the
   Printing record and the saved report IS one.
C. Threshold-Series, Verification, run3 (Quick check, one date): no note
   about "the standard" anywhere on the page.
D. The demo presets, installed as a user installs them: a tagged FAIL preset
   reads the same as its PASS at the window's opening choice, and FAIL
   against PASS under the set its name gives.

    CHROMIQ_DEMO_PACK=<pack> python scripts/drive_k15_demo_pack.py <out-dir>
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import DEMO_PACK, Drive                          # noqa: E402

NAME = "Report-Limits-Threshold-Series"


def _text(dlg) -> str:
    return dlg._view.toPlainText()


def _save(d, tag: str, dlg) -> str:
    t = _text(dlg)
    (d.out / f"{tag}.txt").write_text(t, encoding="utf-8")
    return t


def _pick_report(d, dlg, needle: str) -> str:
    c = dlg._saved_combo
    for i in range(c.count()):
        if needle in c.itemText(i):
            c.setCurrentIndex(i)
            c.activated.emit(i)
            return c.itemText(i)
    return ""


def _ticked(dlg) -> "list[str]":
    return sorted(str(r.get("created") or "") for r in dlg._runs_for_report())


def _verdict_lines(text: str) -> "list[str]":
    """The column's Overall word and the sentence under it, as the page
    prints them ("Overall" on one line, the word on the next)."""
    lines = [ln.strip() for ln in text.splitlines()]
    for i, ln in enumerate(lines):
        if ln == "Overall":
            return [w for w in lines[i + 1:i + 4] if w]
    return []


def part_a(d):
    d.set_bar(run_type="Verification", run="run1")
    yield 800
    d.launch_tool("measurement_report")
    yield 4500
    dlg = d.top_dialog("MeasurementReportDialog")
    d.note(f"[A] report window open: {dlg is not None}")
    if dlg is None:
        return
    dlg.resize(1400, 1150)
    yield 900
    labels = [dlg._saved_combo.itemText(i)
              for i in range(dlg._saved_combo.count())]
    d.record["A_report_list"] = labels
    d.note(f"[A] 'Report shown' has {len(labels)} entries; first four: "
           f"{labels[:4]}")
    d.shot(dlg, "A1-report-window")
    for tag, day in (("A2-2026-01-05", "2026-01-05"),
                     ("A3-2026-01-19", "2026-01-19"),
                     ("A4-2026-02-02", "2026-02-02")):
        picked = _pick_report(d, dlg, day)
        yield 2500
        t = _save(d, tag, dlg)
        d.note(f"[A] picked {picked!r}; ticked measurements {_ticked(dlg)}")
        d.note(f"[A]   verdict lines: {_verdict_lines(t)}")
        d.record[tag] = {"picked": picked, "ticked": _ticked(dlg),
                         "verdicts": _verdict_lines(t)}
        d.shot(dlg, tag)
    # THE PAPER WHITE LINE is in the detailed section, so do what a user
    # does: "New report…" (the 2026-02-02 measurement stays ticked), tick
    # "Show detailed data for each run", Generate. From "New report…" no
    # question is asked.
    d.pick(dlg._saved_combo, "new report")
    yield 1500
    from PyQt6.QtWidgets import QCheckBox, QPushButton
    box = next(c for c in dlg.findChildren(QCheckBox)
               if c.text().startswith("Show detailed data"))
    if not box.isChecked():
        box.click()
    yield 1200
    gen = next(b for b in dlg.findChildren(QPushButton)
               if b.text().replace("&", "").lower() == "generate report")
    d.note(f"[A] generating from 'New report…' with ticked {_ticked(dlg)}, "
           f"button enabled={gen.isEnabled()}")
    d.later(gen.click)
    yield 300
    d.record["A_generate_question"] = d.answer(
        "create new", name="A-generate-question", within_ms=2500)
    # wait for the page to be the new document, not a fixed time
    for _ in range(40):
        yield 500
        if "Paper white & darkest black" in _text(dlg):
            break
    yield 800
    from PyQt6.QtGui import QTextCursor
    view = dlg._view
    view.moveCursor(QTextCursor.MoveOperation.Start)
    found = view.find("Paper white")
    view.ensureCursorVisible()
    yield 700
    t = _text(dlg)
    i = t.find("Paper white & darkest black")
    d.record["A_paper_white"] = t[i:i + 160] if i >= 0 else None
    d.note(f"[A] paper white section found={found}: "
           f"{t[i:i + 160]!r}" if i >= 0 else "[A] paper white NOT on page")
    d.shot(dlg, "A5-paper-white")
    dlg.close()
    yield 800


def part_b(d):
    d.set_bar(run_type="Profiling", run="run1")
    yield 900
    d.launch_tool("measurement_report")
    yield 4500
    dlg = d.top_dialog("MeasurementReportDialog")
    d.note(f"[B] report window open: {dlg is not None}")
    if dlg is None:
        return
    dlg.resize(1400, 1100)
    yield 900
    c, m = dlg._type_combo, dlg._type_combo.model()
    ents = [(c.itemText(i), bool(m.item(i).isEnabled()))
            for i in range(c.count()) if c.itemData(i)]
    labels = [dlg._saved_combo.itemText(i)
              for i in range(dlg._saved_combo.count())]
    d.record["B_types"] = ents
    d.record["B_report_list"] = labels
    d.note(f"[B] type offered: current={c.currentText()!r}; pickable="
           f"{[t for t, on in ents if on]}")
    d.note(f"[B] saved reports: {labels}")
    t = _save(d, "B-profiling-run1", dlg)
    d.note(f"[B] page opens: {t[:160]!r}")
    d.shot(dlg, "B1-profiling-printing-record")
    dlg.close()
    yield 800


def part_c(d):
    d.set_bar(run_type="Verification", run="run3")
    yield 900
    d.launch_tool("measurement_report")
    yield 4500
    dlg = d.top_dialog("MeasurementReportDialog")
    d.note(f"[C] report window open: {dlg is not None}")
    if dlg is None:
        return
    dlg.resize(1400, 1100)
    yield 900
    t = _save(d, "C-run3-quick-check", dlg)
    bad = [ln for ln in t.splitlines()
           if "the standard calls this metric" in ln.lower()]
    d.record["C_standard_note_lines"] = bad
    d.note(f"[C] set shown: {dlg._set_combo.currentText()!r}; lines about "
           f"'the standard': {bad}")
    d.note(f"[C]   verdict lines: {_verdict_lines(t)}")
    d.shot(dlg, "C1-run3-quick-check")
    dlg.close()
    yield 800


def _choose(d, dlg, type_id, set_id):
    dlg._type_combo.setCurrentIndex(dlg._type_combo.findData(type_id))
    dlg._set_combo.setCurrentIndex(dlg._set_combo.findData(set_id))


def _select_preset(dlg, label):
    from PyQt6.QtCore import Qt
    for i in range(dlg._tree.topLevelItemCount()):
        head = dlg._tree.topLevelItem(i)
        for j in range(head.childCount()):
            child = head.child(j)
            row = child.data(0, Qt.ItemDataRole.UserRole)
            if row is not None and row.label.split(" [")[0] == label.split(" [")[0]:
                dlg._tree.setCurrentItem(child)
                dlg._tree.scrollToItem(child)
                return row
    return None


def part_d(d):
    import make_verification_preset_demos as GEN
    d.goto_tab("chart")
    yield 800
    tab = d.win._tab_chart
    if hasattr(tab, "_manual_btn"):
        tab._manual_btn.click()
        yield 800
    d.later(tab._preset_verify_btn.click)
    yield 4500
    dlg = d.top_dialog("PresetVerificationDialog")
    d.note(f"[D] presets window open: {dlg is not None}")
    if dlg is None:
        return
    dlg.resize(1400, 950)
    yield 800
    opened = (dlg.current_type(), dlg.current_set())
    d.note(f"[D] the window opens on {opened}")
    req = GEN.REQ_BY_KEY["R11"]
    fail = next(x for x in GEN.DEMOS if x.key == "R11" and x.kind == "FAIL")
    ok = next(x for x in GEN.DEMOS if x.key == "R11" and x.kind == "PASS")
    for tag, choice in (("D1-opening-choice", opened),
                        ("D2-named-choice", GEN.shown_under(req))):
        _choose(d, dlg, *choice)
        yield 1500
        for side, demo in (("FAIL", fail), ("PASS", ok)):
            row = _select_preset(dlg, demo.name)
            yield 900
            missing = dict(row.assessment.missing) if row else None
            missing = {k: v for k, v in (missing or {}).items()
                       if v != "needs_reference_file"}
            d.record[f"{tag}-{side}"] = {"choice": list(choice),
                                          "preset": row.label if row else None,
                                          "missing": missing}
            d.note(f"[D] {tag} {side}: {(row.label if row else demo.name)!r} withholds {missing}")
            d.shot(dlg, f"{tag}-{side}")
    dlg.close()
    yield 800


def part_e(d):
    """Every project of the pack, opened through Load's own path: a project
    the app cannot open, or one that opens with no runs, is a rule broken."""
    names = sorted(p.parent.name for p in DEMO_PACK.glob("*/project.json"))
    opened = {}
    for name in names:
        d.open_project(name)
        yield 600
        combo = d.bar._run_combo
        opened[name] = [combo.itemText(i) for i in range(combo.count())]
    d.record["E_projects"] = opened
    d.shot(d.win, "E-last-project-open")


def script(d):
    d.open_project(NAME)
    yield 500
    yield from part_a(d)
    yield from part_b(d)
    yield from part_c(d)
    yield from part_d(d)
    yield from part_e(d)


def install_presets(out: Path) -> None:
    """Copy the pack's demo presets into the sandbox's Create Chart folder,
    the way a user copies them (the README's own instruction)."""
    src = DEMO_PACK / "Create Chart presets (verification demos)"
    dest = out / "sandbox" / "presets" / "Create Chart"
    dest.mkdir(parents=True, exist_ok=True)
    for f in sorted(src.iterdir()):
        if f.suffix in (".json", ".ti1"):
            shutil.copy2(f, dest / f.name)


if __name__ == "__main__":
    out = Path(sys.argv[1]).resolve()
    install_presets(out)
    d = Drive(out, projects=sorted(p.parent.name
                                   for p in DEMO_PACK.glob("*/project.json")))
    sys.exit(d.run(script))
