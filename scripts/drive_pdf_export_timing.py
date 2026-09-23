#!/usr/bin/env python3
"""#182 beta 38: WHEN is "Save report as PDF…" on disk? Driven ON SCREEN.

Two drive rounds saw the PDF appear only when the report window closed. This
drives the real button the way a user does, several exports in a row in one
window, after a change of report type and after a change of ticks, and after
each one looks at the disk straight away: the file, its size, its %%EOF.

It also records, at the moment the file chooser is answered, which Python
frames are on the stack under the answer: an event loop the chooser's own
exec() cannot return through is what "written only later" would need.

    python scripts/drive_pdf_export_timing.py <out-dir> [en|de]
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import Drive                                   # noqa: E402

PROJECT = "Report-Limits-Threshold-Series"


def _pdf_state(p: Path) -> dict:
    if not p.exists():
        return {"exists": False}
    b = p.read_bytes()
    return {"exists": True, "size": len(b),
            "eof": b.rstrip().endswith(b"%%EOF")}


def _loops_on_stack() -> "list[str]":
    """The frames under this call that sit in an event loop or a handler
    that runs one: the order says which loop must unwind first."""
    keep = ("exec", "_export_pdf", "save_file_dialog", "pump", "step",
            "answer", "processEvents", "_generate", "answer_file")
    out = []
    for fr in traceback.extract_stack()[:-1]:
        if any(k in fr.name for k in keep) or "exec" in (fr.line or ""):
            out.append(f"{Path(fr.filename).name}:{fr.lineno} {fr.name}: "
                       f"{(fr.line or '').strip()[:70]}")
    return out


def _ours_on_top_at(x: float, y: float) -> "tuple[bool, str]":
    """Whether the frontmost window under the global point (x, y) belongs to
    this process: a real click posted there must not land on anything else
    (a terminal, an editor)."""
    import os
    try:
        import Quartz
    except Exception as exc:                                # noqa: BLE001
        return False, f"no Quartz ({exc})"
    wins = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly
        | Quartz.kCGWindowListExcludeDesktopElements, Quartz.kCGNullWindowID)
    for w in wins or []:                       # front to back
        if int(w.get("kCGWindowLayer", 0)) != 0:
            continue
        b = w.get("kCGWindowBounds") or {}
        if (b.get("X", 0) <= x < b.get("X", 0) + b.get("Width", 0)
                and b.get("Y", 0) <= y < b.get("Y", 0) + b.get("Height", 0)):
            owner = str(w.get("kCGWindowOwnerName", ""))
            return (int(w.get("kCGWindowOwnerPID", -1)) == os.getpid(),
                    f"frontmost window there: {owner!r}")
    return False, "no window under the point"


def _real_click(x: float, y: float) -> None:
    import Quartz
    pt = Quartz.CGPointMake(x, y)
    Quartz.CGWarpMouseCursorPosition(pt)
    for kind in (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp):
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, Quartz.CGEventCreateMouseEvent(
            None, kind, pt, Quartz.kCGMouseButtonLeft))


def script(d):
    rec = d.record
    rec["exports"] = []

    def tick(dlg, dates):
        from PyQt6.QtCore import Qt
        lst = dlg._profile_list
        for i in range(lst.count()):
            it = lst.item(i)
            if not (it.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                continue
            on = dates is None or any(x in it.text() for x in dates)
            it.setCheckState(Qt.CheckState.Checked if on
                             else Qt.CheckState.Unchecked)
            d.pump(150)

    def dates_of(dlg):
        from PyQt6.QtCore import Qt
        lst = dlg._profile_list
        return [lst.item(i).text() for i in range(lst.count())
                if lst.item(i).flags() & Qt.ItemFlag.ItemIsUserCheckable]

    def generate(dlg, dates=None):
        dlg._saved_combo.setCurrentIndex(0)
        d.pump(1200)
        tick(dlg, dates)
        d.pump(800)
        d.later(dlg._generate_btn.click)
        yield 400
        d.answer("New", name=None, within_ms=2500)
        before = dlg._view.toPlainText()
        for _ in range(60):
            yield 700
            if dlg._view.toPlainText() and dlg._view.toPlainText() != before:
                break
        yield 1500

    def real_save(target, name):
        """Type the path into ChromIQ's own chooser and press its Save button
        with the REAL pointer, when the chooser is the frontmost window at
        that point; otherwise say so and do not click."""
        from PyQt6.QtWidgets import (QDialogButtonBox, QFileDialog,
                                     QLineEdit)
        w = d.modal()
        if not isinstance(w, QFileDialog):
            return False, "no chooser"
        w.setDirectory(str(target.parent))
        d.pump(800)
        box = w.findChild(QLineEdit, "fileNameEdit")
        box.setText(str(target))
        d.pump(400)
        d.shot(w, f"{name}-chooser")
        bb = w.findChild(QDialogButtonBox)
        btn = bb.button(QDialogButtonBox.StandardButton.Save) or next(
            (b for b in bb.buttons()
             if bb.buttonRole(b) == QDialogButtonBox.ButtonRole.AcceptRole),
            None)
        g = btn.mapToGlobal(btn.rect().center())
        ours, why = _ours_on_top_at(g.x(), g.y())
        if not ours:
            return False, f"not clicked: {why}"
        _real_click(g.x(), g.y())
        return True, f"real pointer click on {btn.text()!r} ({why})"

    def save_pdf(dlg, name, real_click=False):
        """Click the real button, answer ChromIQ's own chooser, then look at
        the disk every 250 ms without the driver holding any loop open."""
        target = d.out / "pdf" / f"{name}.pdf"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target.unlink()
        t_click = time.monotonic()
        d.later(dlg._pdf_btn.click)
        yield 1500
        stack = _loops_on_stack()
        how = "answer_file (accept, then back to the loop)"
        if real_click:
            ok, how = real_save(target, name)
            if not ok:
                d.note(f"   REAL CLICK {name}: {how}; answered in code")
                ok = d.answer_file(target)
        else:
            ok = d.answer_file(target, name=f"{name}-chooser")
        t_ans = time.monotonic()
        state_at_answer = _pdf_state(target)
        first_seen = complete = None
        for _ in range(240):                     # 60 s, 250 ms at a time
            yield 250
            s = _pdf_state(target)
            now = time.monotonic() - t_ans
            if s["exists"] and first_seen is None:
                first_seen = round(now, 2)
            if s.get("eof"):
                complete = round(now, 2)
                break
        yield 1200
        s = _pdf_state(target)
        entry = {"name": name, "chooser_answered": ok, "how": how,
                 "stack_when_answered": stack,
                 "at_answer": state_at_answer,
                 "first_seen_s_after_answer": first_seen,
                 "complete_s_after_answer": complete,
                 "final": s, "window_open": dlg.isVisible(),
                 "click_to_answer_s": round(t_ans - t_click, 2)}
        rec["exports"].append(entry)
        d.note(f"   EXPORT {name}: answered={ok} complete after "
               f"{complete} s (window open={dlg.isVisible()}) final={s}")
        dlg.raise_()
        d.pump(400)
        d.shot(dlg, f"{name}-after-export")

    d.open_project(PROJECT)
    d.set_bar(run_type="Verification", run="run1")
    yield 800
    d.launch_tool("measurement_report")
    yield 5000
    dlg = d.top_dialog("MeasurementReportDialog")
    d.note(f"window: {dlg is not None}; dates: {dates_of(dlg)}")
    yield from generate(dlg)
    d.shot(dlg, "P0-generated-all-dates")

    # three in a row, one window, nothing changed between them; the first
    # through the REAL pointer on the chooser's Save button when it is the
    # frontmost window there
    for i in (1, 2, 3):
        yield from save_pdf(dlg, f"P{i}-row-{i}", real_click=(i == 1))

    # the report type changed, then export
    tc = dlg._type_combo
    types = [tc.itemText(i) for i in range(tc.count())]
    d.note(f"report types: {types}")
    for idx in range(tc.count()):
        if idx == tc.currentIndex():
            continue
        tc.setCurrentIndex(idx)
        d.pump(1500)
        yield from generate(dlg)
        yield from save_pdf(dlg, f"P4-type-{idx}")
        break

    # the ticks changed, then export straight after Generate
    all_dates = dates_of(dlg)
    first_two = [t.split()[0] for t in all_dates[:2]] if all_dates else None
    yield from generate(dlg, first_two)
    yield from save_pdf(dlg, "P5-two-dates")
    yield from generate(dlg, None)
    yield from save_pdf(dlg, "P6-all-dates-again")
    # the case two rounds reported: a tooltip hovered on a graph, the pointer
    # moved to the button, then the export
    ch = dlg._trend_de
    dlg._trend_tabs.setCurrentIndex(dlg._trend_tabs.indexOf(ch))
    d.pump(600)
    hit = next(iter(getattr(ch, "_hits", []) or []), None)
    if hit is not None:
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QHelpEvent
        from PyQt6.QtWidgets import QApplication
        lp = hit[0].center().toPoint()
        QApplication.sendEvent(ch, QHelpEvent(QEvent.Type.ToolTip, lp,
                                              ch.mapToGlobal(lp)))
        d.pump(800)
        d.shot(dlg, "P7-tooltip-before-export")
    for i in (7, 8, 9):
        yield from save_pdf(dlg, f"P{i}-after-tooltip-{i}")

    d.shot(dlg, "P9-before-close")
    rec["closed_at_monotonic"] = time.monotonic()
    dlg.close()
    yield 1500
    rec["after_close"] = {e["name"]: _pdf_state(d.out / "pdf" / f"{e['name']}.pdf")
                          for e in rec["exports"]}
    yield 300


if __name__ == "__main__":
    lang = sys.argv[2] if len(sys.argv) > 2 else "en"
    d = Drive(Path(sys.argv[1]), projects=[PROJECT], language=lang)
    rc = d.run(script)
    (d.out / "exports.json").write_text(json.dumps(
        {"exports": d.record.get("exports"),
         "after_close": d.record.get("after_close")}, indent=1, default=str))
    sys.exit(rc)
