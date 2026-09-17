#!/usr/bin/env python3
"""B8-290 reproduced and then re-measured in a REAL Measurement Report window.

The design authority opened a demo project's run 1, run type verification, set
"Judged against" to a custom set and pressed Generate report. The Report Scope
warned that Red, Blue and Cyan are missing from the chart, and the Cube corners
table in the same document then printed a colour swatch and a DeltaE00 for each
of them anyway: Red and Blue both grey and both 2.46, from ONE patch, and Cyan
green.

This driver copies his project (never opens it in place), drives the real
window, and reads the cube-corners table out of the rendered document. It
measures three things the panel's prose cannot settle:

* which patch each corner row NAMES,
* which colours the row's two swatches carry, and
* whether a corner the Report Scope has just called missing still carries a
  number.

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-b20r4.ini \\
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-b20r4-presets \\
        python scripts/adv_b20r4_cube_corners_on_screen.py <project-dir> <out-dir>

**Never set QT_QPA_PLATFORM=offscreen for this** (CLAUDE.md).
"""
from __future__ import annotations

import html as _html
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


CORNERS = ("White", "Black", "Red", "Green", "Blue", "Cyan", "Magenta",
           "Yellow")


def read_corner_table(doc_html: str) -> "list[dict]":
    """One row per corner, as the reader sees it: name, patch, swatches, ΔE00.

    **PARSED OUT OF QT'S OWN NORMALISED MARKUP**, which is what the window
    really holds, not out of the string the dialog built. `QTextBrowser.toHtml`
    rewrites every tag: `<td>` becomes `<td bgcolor=…>`, the swatch's three
    spans each carry a full font declaration, and an attribute-free `<td>` test
    matches nothing at all. The first run of this driver reported a clean table
    for that reason and for no other, on a document whose Red row still said
    2.46 -- a parser that finds nothing looks exactly like a fault that is
    fixed.
    """
    i = doc_html.find("eight ink extremes")
    if i < 0:
        return []
    body = doc_html[i:]
    end = body.find("</table>")
    if end < 0:
        return []
    out = []
    for raw in body[:end].split("<tr")[1:]:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", raw, re.S)
        if len(cells) < 4:
            continue
        def text(cell: str) -> str:
            return _html.unescape(re.sub(r"<[^>]+>", "", cell)).strip()
        head = text(cells[0])
        name = next((c for c in CORNERS if head.startswith(c)), None)
        if name is None:
            continue

        def swatch(cell: str) -> "str | None":
            """The FILL, which is the middle of the swatch's three spans.

            The outer two carry the edge colour (`_swatch` draws the border as
            a second span because Qt ignores `border` on an inline one), so
            taking the first or the last reports #6a6a6a for every patch on
            the sheet.
            """
            bg = re.findall(r"background-color:(#[0-9a-fA-F]{6})", cell)
            if len(bg) >= 3:
                return bg[1].lower()
            return bg[0].lower() if bg else None

        loc = re.search(r"\((\d+)\)", head)
        de_text = text(cells[3])
        m = re.search(r"([0-9]+\.[0-9]+)", de_text)
        out.append({
            "corner": name,
            "marked_missing": "missing" in head,
            "names_patch": loc.group(1) if loc else None,
            "header_text": head,
            "expected_swatch": swatch(cells[1]),
            "measured_swatch": swatch(cells[2]),
            "measured_cell_text": text(cells[2]),
            "delta_e": m.group(1) if m else None,
            "delta_e_cell_text": de_text,
        })
    return out


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-b20r4-cube-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    # COPY, NEVER OPEN IN PLACE: `Project.load` migrates on disk.
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
    MeasurementReportDialog._confirm = (lambda self, t, b: True)  # type: ignore
    apply_appearance(app, None, "dark")
    fm = FileManager(settings); del fm

    ti3s = sorted((dest / "runs" / "run1" / "verifications").glob("*/*.ti3"))
    print(f"    verification measurements: {[p.parent.name for p in ti3s]}",
          flush=True)
    ti3 = ti3s[0]
    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    dlg.resize(1500, 1060); dlg.show(); dlg.raise_(); dlg.activateWindow()
    pump(app, 3000)
    print(f"    window on screen: {dlg.isVisible()} "
          f"{dlg.frameGeometry().width()}x{dlg.frameGeometry().height()}",
          flush=True)

    res: dict = {"crashes": crashes}
    sc = getattr(dlg, "_set_combo", None)
    if sc is not None:
        res["sets_offered"] = [sc.itemText(i) for i in range(sc.count())]
        print(f"    'Judged against' offers: {res['sets_offered']}", flush=True)
        want = next((i for i in range(sc.count())
                     if "12647-7" in sc.itemText(i)), None)
        if want is not None and sc.isEnabled():
            sc.setCurrentIndex(want)
            pump(app, 3000)
            res["set_chosen"] = sc.currentText()
        else:
            res["set_chosen"] = (f"NOT CHOSEN (enabled={sc.isEnabled()}, "
                                 f"found={want is not None})")
        print(f"    set: {res['set_chosen']}", flush=True)

    # **THE CUBE-CORNERS TABLE IS IN THE OPT-IN DETAIL SECTION**, and the
    # first run of this driver reported a clean table by measuring a document
    # that had none: "Show detailed data for each run" is what puts
    # `_run_detail_html` on the page, and it is the section he quoted.
    if getattr(dlg, "_detail_check", None) is not None:
        res["detail_was_checked"] = dlg._detail_check.isChecked()
        dlg._detail_check.setChecked(True)
        pump(app, 1200)
        print(f"    'Show detailed data for each run' was "
              f"{res['detail_was_checked']}, now "
              f"{dlg._detail_check.isChecked()}", flush=True)

    dlg._on_generate_report()
    pump(app, 5000)

    doc = dlg._view.toHtml() if hasattr(dlg, "_view") else ""
    if not doc:
        for attr in ("_view", "_results", "_result_view", "_doc", "_text"):
            w = getattr(dlg, attr, None)
            if w is not None and hasattr(w, "toHtml"):
                doc = w.toHtml(); break
    (out / "document.html").write_text(doc, encoding="utf-8")
    plain = _html.unescape(re.sub(r"<[^>]+>", " ", doc))
    res["scope_says_missing"] = bool(re.search(
        r"missing cube colours", plain, re.I))
    m = re.search(r"missing ([A-Za-z, ]+)", plain)
    res["scope_missing_names"] = m.group(1).strip() if m else None
    res["corner_table"] = read_corner_table(doc)
    print(f"    Report Scope warns about missing cube colours: "
          f"{res['scope_says_missing']} ({res['scope_missing_names']})",
          flush=True)
    print("    the Cube corners table, as the reader sees it:", flush=True)
    for r in res["corner_table"]:
        print(f"      {r['corner']:8s} missing={str(r['marked_missing']):5s} "
              f"patch={str(r['names_patch']):5s} "
              f"expected={str(r['expected_swatch']):8s} "
              f"measured={str(r['measured_swatch'] or r['measured_cell_text']):8s} "
              f"dE={str(r['delta_e'] or r['delta_e_cell_text'])}", flush=True)

    # The patch a missing corner names, and whether two corners share one.
    named = [r["names_patch"] for r in res["corner_table"] if r["names_patch"]]
    res["two_corners_share_one_patch"] = len(named) != len(set(named))
    res["missing_rows_with_a_number"] = [
        r["corner"] for r in res["corner_table"]
        if r["marked_missing"] and r["delta_e"]]
    res["missing_rows_naming_a_patch"] = [
        r["corner"] for r in res["corner_table"]
        if r["marked_missing"] and r["names_patch"]]
    print(f"    two corners sharing one patch: "
          f"{res['two_corners_share_one_patch']}", flush=True)
    print(f"    missing corners still carrying a DeltaE00: "
          f"{res['missing_rows_with_a_number']}", flush=True)
    print(f"    missing corners still naming a patch: "
          f"{res['missing_rows_naming_a_patch']}", flush=True)

    ok, why = capture_window(dlg, out / "report-window.png")
    res["photograph"] = str(out / "report-window.png") if ok else None
    res["photograph_refused"] = None if ok else why
    print(f"    photo: {'OK' if ok else why}", flush=True)

    # …and the SAME document scrolled to the cube-corners table, so the
    # photograph shows the rows rather than the top of the report.
    if hasattr(dlg, "_view"):
        from PyQt6.QtGui import QTextCursor
        cur = dlg._view.document().find("Cube corners (the eight ink")
        if not cur.isNull():
            dlg._view.setTextCursor(cur)
            dlg._view.ensureCursorVisible()
            pump(app, 600)
            # `ensureCursorVisible` puts the heading on the LAST line, so the
            # eight rows under it are below the fold and the photograph shows
            # the table's title and none of its content. Nudge past it.
            sb = dlg._view.verticalScrollBar()
            # Eight rows at roughly 26 px plus the heading, measured on this
            # window: 260 px puts the whole table on screen. A scroll by
            # `singleStep` units overshot into the NEXT run's section.
            sb.setValue(min(sb.maximum(), sb.value() + 260))
            pump(app, 1200)
            ok2, why2 = capture_window(dlg, out / "report-cube-corners.png")
            res["photograph_table"] = (str(out / "report-cube-corners.png")
                                       if ok2 else None)
            res["photograph_table_refused"] = None if ok2 else why2
            print(f"    photo of the table: {'OK' if ok2 else why2}", flush=True)

    (out / "result.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"    crashes: {len(crashes)}", flush=True)
    for c in crashes:
        print(c, flush=True)
    dlg.close(); pump(app, 500)
    return 0


if __name__ == "__main__":
    sys.exit(main())
