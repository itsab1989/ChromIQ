#!/usr/bin/env python3
"""The saved-report selector and the delete rule, on a real project — round 4.

The delete rule has been repaired three times in two rounds (B8-250, and the
two entries about counting on the folder rather than on the window's memory),
so it is driven again on a project that arrived from outside this repo: two
readable reports on one dated verification, plus an `old/` archive beside them,
which is the shape the glob and the snapshot each have to agree about.

What it asks:

* does the selector really show every saved report of the date, and does
  picking one below the top STAY picked (the QVariant-compare fault);
* does the archive under `reports/old/` count as a spare (it must not);
* does the refusal fire on the last readable report, and does the confirmation
  say the same number the rule counted;
* does the button's enabled state survive a change made behind the window.

    CHROMIQ_SETTINGS_FILE=… CHROMIQ_PRESETS_DIR=… \\
        python scripts/adv_b20r4_saved_reports_and_delete.py <project> <out>

**Never set QT_QPA_PLATFORM=offscreen for this** (CLAUDE.md).
"""
from __future__ import annotations

import json
import os
import re
import shutil
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


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:                                      # noqa: C901
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert not os.environ.get("QT_QPA_PLATFORM"), \
        "this is a DRIVER: it opens a real window (CLAUDE.md)"
    src = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    crashes: list = []
    prev = sys.excepthook
    sys.excepthook = lambda t, v, tb: (
        crashes.append("".join(traceback.format_exception(t, v, tb))),
        prev(t, v, tb))

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-b20r4-del-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    dest = work / src.name
    shutil.copytree(src, dest)
    print(f"    project copied to {dest}", flush=True)
    print(f"    screen locked at start: {session_is_locked()}", flush=True)

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from core.file_manager import FileManager
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from ui.theme import apply_appearance

    # THE CONFIRMATION IS THE THING UNDER TEST, so it is captured rather than
    # auto-accepted blind: a rule and a sentence that count different things
    # is exactly the fault the last two rounds found here.
    said: list = []

    def confirm(self, title, body):
        said.append({"title": title, "body": body})
        return True
    MeasurementReportDialog._confirm = confirm        # type: ignore[assignment]
    apply_appearance(app, None, "dark")
    fm = FileManager(settings); del fm

    # EVERY dated verification of the run, because the window lists them all
    # when "Show all measurement runs" is on and the selector's top entry need
    # not belong to the date whose .ti3 opened it. The first cut of this driver
    # watched ONE folder, saw "removed []" after a delete that had really taken
    # a file out of the OTHER date, and would have reported a delete that does
    # nothing.
    dates = sorted(d for d in (dest / "runs" / "run1" / "verifications").iterdir()
                   if d.is_dir())
    ti3 = next(dates[0].glob("*.ti3"))

    def live(d: Path) -> "list[str]":
        """The readable reports of one date, which is what the rule counts."""
        outp = []
        for f in sorted((d / "reports").glob("report_*.json")):
            try:
                json.loads(f.read_text(encoding="utf-8"))
            except Exception:                        # noqa: BLE001
                continue
            outp.append(f.name)
        return outp

    def archived(d: Path) -> "list[str]":
        return sorted(str(f.relative_to(d / "reports"))
                      for f in (d / "reports").glob("old/**/report_*.json"))

    print("    before:", flush=True)
    for d in dates:
        print(f"        {d.name}: live={live(d)} archived={archived(d)}",
              flush=True)

    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    dlg.resize(1500, 1060); dlg.show(); dlg.raise_(); dlg.activateWindow()
    pump(app, 3000)
    print(f"    window on screen: {dlg.isVisible()}", flush=True)

    res: dict = {"crashes": crashes,
                 "before": {d.name: {"live": live(d), "archived": archived(d)}
                            for d in dates}}
    c = dlg._saved_combo
    res["selector_entries"] = [c.itemText(i) for i in range(c.count())]
    print(f"    selector offers {c.count()}:", flush=True)
    for t in res["selector_entries"]:
        print(f"        {t}", flush=True)
    res["selector_count_matches_disk"] = (
        c.count() == sum(len(live(d)) for d in dates))

    # -- A: pick each entry in turn; it must STAY picked and show that file.
    a = []
    for i in range(c.count()):
        c.setCurrentIndex(i)
        pump(app, 1600)
        # **THE FILE NAME ALONE CANNOT SAY WHICH REPORT IS SHOWING.** Both
        # dated verifications of this run hold a `report_2026-09-17_03-18-40
        # .json`, because both were regenerated in the same second, so a probe
        # that reads `_report_file` sees one name under two different picks
        # and reports a selector that ignores the reader. The DATE FOLDER is
        # the other half of the identity, and it is what `_run_key` uses.
        # AND WHAT THE READER ACTUALLY SEES, which is the document, not the
        # window's idea of a subject. With "Show all measurement runs" on, a
        # row belonging to the OTHER date cannot move `self._report` -- that
        # stays the measurement the window was opened on -- so the only honest
        # test of "did my pick do anything" is whether the rendered page
        # changed.
        import hashlib as _hl
        _doc = dlg._view.toHtml()
        _dh = _hl.sha256(_doc.encode("utf-8")).hexdigest()[:12]
        rep = dlg._report or {}
        origin = Path(str(rep.get("_origin_dir") or "")).name
        a.append({"asked": i, "index_after": c.currentIndex(),
                  "text": c.currentText(),
                  "showing_file": str(rep.get("_report_file") or ""),
                  "showing_date": origin,
                  "showing": f"{origin}/{rep.get('_report_file')}",
                  "doc_sha": _dh,
                  # WHAT THE PICK RECORDED. `self._report` is the measurement
                  # the WINDOW is about and cannot move when the row belongs
                  # to another dated verification; `_chosen_reports` is where
                  # the pick actually lands, keyed by run. Reading only the
                  # first made two different picks look like one.
                  "chosen": dict(getattr(dlg, "_chosen_reports", {}) or {}),
                  "stayed": c.currentIndex() == i})
        print(f"    A{i}: stayed={a[-1]['stayed']} doc={_dh} "
              f"showing={a[-1]['showing']}", flush=True)
        for _k, _v in sorted(a[-1]["chosen"].items()):
            print(f"         chosen[{_k[-46:]}] = {_v}", flush=True)
    res["A_picks"] = a
    res["A_all_stayed"] = all(x["stayed"] for x in a)
    # FOUR ENTRIES MUST SHOW FOUR DIFFERENT REPORTS. That is the whole point
    # of the selector, and a duplicate here is the QVariant-compare fault
    # coming back in another shape.
    res["A_distinct_reports_shown"] = len({x["showing"] for x in a})
    res["A_distinct_documents"] = len({x["doc_sha"] for x in a})
    res["A_each_pick_showed_its_own"] = (
        res["A_distinct_reports_shown"] == c.count())
    ok, why = capture_window(dlg, out / "A-selector.png")
    print(f"       photo: {'OK' if ok else why}", flush=True)

    # -- B..E: press Delete until the rule refuses, and watch the disk.
    presses = []
    for n in range(8):
        enabled = dlg._delete_report_btn.isEnabled()
        note = dlg._saved_note.text()
        picked = c.currentText()
        before = {d.name: live(d) for d in dates}
        said.clear()
        dlg._on_delete_report()
        pump(app, 2500)
        after = {d.name: live(d) for d in dates}
        gone = sorted(set(sum(before.values(), []))
                      - set(sum(after.values(), [])))
        body = said[-1]["body"] if said else ""
        # WHAT THE CONFIRMATION PROMISED, against what the disk then held.
        promised = None
        m = re.search(r"(\d+)\s+saved report", body)
        if m:
            promised = int(m.group(1))
        elif "One saved report" in body or "one saved report" in body:
            promised = 1
        which = next((d.name for d in dates
                      if set(before[d.name]) - set(after[d.name])), None)
        presses.append({
            "press": n, "was_enabled": enabled, "note": note,
            "picked": picked, "asked": bool(said), "removed": gone,
            "from_date": which,
            "promised_left": promised,
            "really_left": (len(after[which]) if which else None),
            "live_after": after,
        })
        print(f"    press {n}: enabled={enabled} removed={gone or '-'} "
              f"from={which} promised_left={promised} "
              f"really_left={presses[-1]['really_left']} note={note!r}",
              flush=True)
        if not gone:
            break
    res["presses"] = presses
    res["after"] = {d.name: {"live": live(d), "archived": archived(d)}
                    for d in dates}
    # THE RULE: every dated verification keeps at least one readable report.
    res["every_date_kept_a_report"] = all(len(live(d)) >= 1 for d in dates)
    # AND THE SENTENCE AGREED WITH THE DISK, EVERY TIME.
    res["confirmation_matched_the_disk"] = all(
        p["promised_left"] is None or p["promised_left"] == p["really_left"]
        for p in presses if p["removed"])
    print(f"    every date kept a report: {res['every_date_kept_a_report']}",
          flush=True)
    print(f"    the confirmation matched the disk every time: "
          f"{res['confirmation_matched_the_disk']}", flush=True)
    print(f"    archives untouched: "
          f"{ {d.name: archived(d) for d in dates} }", flush=True)
    ok, why = capture_window(dlg, out / "E-after-the-last-refusal.png")
    print(f"       photo: {'OK' if ok else why}", flush=True)

    (out / "result.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"    crashes: {len(crashes)}", flush=True)
    for x in crashes:
        print(x, flush=True)
    dlg.close(); pump(app, 500)
    return 0


if __name__ == "__main__":
    sys.exit(main())
