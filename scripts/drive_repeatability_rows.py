"""ChromIQ's own two repeatability rows, on screen, in a real window.

Photographs the Report limits window (both rows, every column, and the `–` the
two read-only ISO columns must show), each row's help icon, and the
Measurement Report with the rows JUDGED and REFUSED.

Run it::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-repeat/settings.ini \
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-repeat/presets \
    CHROMIQ_COMPLIANCE_ISO_FILE=<repo>/data/compliance_sets/iso12647.json \
        python scripts/drive_repeatability_rows.py <out-dir>

Never set QT_QPA_PLATFORM=offscreen for this. It is a driver, not a test.

**The ISO file is forced to the repository's own, which ships empty**, because
this machine has a licence holder's real values beside the presets and
`_iso_data_path` prefers them. No photograph here may show a number in either
read-only ISO column.
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

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtGui import QTextCursor                              # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window, session_is_locked   # noqa: E402


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


CHROME_BOTTOM = 24


def twice(app, win, path: Path):
    """Photograph *win* twice and require the two frames to be identical.

    **`capture_window` returns the window FRAME, title bar included**, so the
    only part that moves between two frames is the chrome: macOS repaints the
    title bar, and the rounded bottom corner and its shadow change a handful of
    pixels. The window's CLIENT AREA is what the frame is evidence of, and that
    is required to be identical pixel for pixel. The same offset is why any
    widget rectangle mapped into this picture has to have the frame origin
    taken off it first.
    """
    from PyQt6.QtGui import QImage
    from onscreen_capture import _difference
    other = path.with_name(path.stem + "__retake.png")
    ok1 = why1 = None
    for _ in range(3):
        ok1, why1 = capture_window(win, path)
        if ok1:
            break
        pump(app, 900)
    if not ok1:
        return False, why1, -1.0
    pump(app, 1300)
    ok2 = why2 = None
    for _ in range(3):
        ok2, why2 = capture_window(win, other)
        if ok2:
            break
        pump(app, 900)
    if not ok2:
        return False, f"the retake failed: {why2}", -1.0
    d = _difference(path, other)
    if d <= 0.0:
        other.unlink(missing_ok=True)
        return True, "", d
    a, b = QImage(str(path)), QImage(str(other))
    if a.size() != b.size():
        return False, "the two frames are different sizes", d
    g, fg = win.geometry(), win.frameGeometry()
    r = win.devicePixelRatioF()
    top = int(round((g.y() - fg.y()) * r))
    left = int(round((g.x() - fg.x()) * r))
    right = a.width() - int(round((fg.right() - g.right()) * r))
    bottom = a.height() - CHROME_BOTTOM
    moved = 0
    for y in range(max(0, top), max(0, bottom)):
        for x in range(max(0, left), max(0, right)):
            if a.pixel(x, y) != b.pixel(x, y):
                moved += 1
    if moved:
        return False, f"{moved} client-area pixels moved between the frames", d
    other.unlink(missing_ok=True)
    return True, (f"the whole frame differs by {d:.1%}, all of it window "
                  f"chrome; the client area is identical"), d


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    iso = os.environ.get("CHROMIQ_COMPLIANCE_ISO_FILE", "")
    assert iso and Path(iso).resolve() == (
        ROOT / "data/compliance_sets/iso12647.json").resolve(), (
        "FORCE THE REPOSITORY'S OWN ISO FILE: this machine has a licence "
        "holder's real values and `_iso_data_path` prefers them")

    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    record: dict = {"frames": {}, "measured": {}, "mode": "ON SCREEN"}
    record["screen_locked_at_start"] = session_is_locked()

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-repeat-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    record["sandbox"] = str(work)
    print(f"    sandbox: {work}", flush=True)

    # **SHOW, do not swallow.** A blanket `QDialog.exec = lambda self: 1`
    # keeps a modal from blocking the driver AND keeps it off the screen, so
    # the first run of this driver photographed two empty desktops and
    # reported "no popup". The help icons ARE the evidence here, so exec puts
    # the window up non-modally and returns instead of never drawing it.
    def _show_instead(self):
        self.setModal(False)
        self.show()
        self.raise_()
        QApplication.instance().processEvents()
        return 1
    QDialog.exec = _show_instead                      # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from core.file_manager import FileManager
    from ui.theme import apply_appearance
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from ui.tooltip_button import TooltipButton, _InfoDialog
    from workflow import compliance_sets as cs
    from workflow import measurement_report as mr
    apply_appearance(app, None, "dark")
    cs.reset_iso_cache()

    ROW_A = "repeat_patches_de00_max"
    ROW_B = "repeat_measurement_de00_max"

    # ---------------------------------------------------- 1. the limits window
    td = ThresholdsDialog(settings, None)
    td.resize(1560, 1000)
    td.show()
    td.raise_()
    pump(app, 1800)
    print(f"    limits window on screen: {td.isVisible()} "
          f"{td.frameGeometry().width()}x{td.frameGeometry().height()}",
          flush=True)

    scroller = None
    for w in td.findChildren(object):
        if w.__class__.__name__.endswith("ScrollArea"):
            scroller = w
            break
    cell = td._cells.get(("chromiq_default", ROW_B))
    if scroller is not None and cell is not None:
        scroller.ensureWidgetVisible(cell, 0, 300)
        pump(app, 900)

    ok, why, d = twice(app, td, out / "01-limits-window-repeatability.png")
    record["frames"]["01-limits-window-repeatability.png"] = (
        f"ok{'; ' + why if why else ''}" if ok else f"REFUSED: {why}")
    print(f"    photo 01: {'ok' if ok else 'REFUSED: ' + why}", flush=True)

    # what the two rows really read in every column, off the live widgets
    cols = td._column_ids()
    for rid in (ROW_A, ROW_B):
        row_cells = {}
        for col in cols:
            w = td._cells.get((col, rid))
            row_cells[col] = (w.text() if hasattr(w, "text") else
                              (f"{w.value():.2f}" if hasattr(w, "value")
                               else repr(w)))
        record["measured"][f"limits/{rid}"] = row_cells
    record["measured"]["limits/columns"] = list(cols)
    # AND THE FACTORY TRUTH BEHIND THE WIDGETS, so a spin box that renders its
    # own text cannot hide what the set actually holds.
    for rid in (ROW_A, ROW_B):
        record["measured"][f"factory/{rid}"] = {
            sid: cs.limit_text(cs.factory_limits(sid)[rid])
            for sid in cs.SET_IDS}

    # ------------------------------------------------- 2. the two help icons
    for n, rid in (("02", ROW_A), ("03", ROW_B)):
        row = cs.ROW_BY_ID[rid]
        btn = None
        for b in td.findChildren(TooltipButton):
            if getattr(b, "_title", "") == row.label or \
                    b.toolTip() == row.label:
                btn = b
                break
        if btn is None:
            for b in td.findChildren(TooltipButton):
                if row.label in (getattr(b, "_body", "") or ""):
                    btn = b
                    break
        if btn is None:
            record["frames"][f"{n}-help-{rid}.png"] = "REFUSED: no icon found"
            continue
        btn.click()
        pump(app, 1200)
        popup = None
        for w in app.topLevelWidgets():
            if isinstance(w, _InfoDialog) and w.isVisible():
                popup = w
        if popup is None:
            record["frames"][f"{n}-help-{rid}.png"] = "REFUSED: no popup"
            continue
        ok, why, d = twice(app, popup, out / f"{n}-help-{rid}.png")
        record["frames"][f"{n}-help-{rid}.png"] = (
            f"ok{'; ' + why if why else ''}" if ok else f"REFUSED: {why}")
        print(f"    photo {n}: {'ok' if ok else 'REFUSED: ' + why}", flush=True)
        popup.close()
        pump(app, 400)
    td.close()
    pump(app, 500)

    # --------------------------------------- 3. the report, judged and refused
    src = ROOT / "demo-projects" / "Demo-Report-Matrix"
    proj = work / "Demo-Report-Matrix"
    shutil.copytree(src, proj, dirs_exist_ok=True)
    vdir = proj / "runs" / "run1" / "verifications"
    dates = sorted(d.name for d in vdir.iterdir()
                   if d.is_dir() and d.name[:4].isdigit())

    # a sheet with NO repeat patches at all, so Row A's other refusal is on
    # screen too: the demo chart repeats paper and black, so one is built by
    # giving every patch of a real measured sheet its own device value.
    plain = vdir / "2026-09-22_120000"
    plain.mkdir(parents=True, exist_ok=True)
    srcf = vdir / dates[-1] / "Demo-Report-Matrix-verify.ti3"
    lines, n = [], 0
    in_data = False
    for line in srcf.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s == "BEGIN_DATA":
            in_data = True
            lines.append(line)
            continue
        if s == "END_DATA":
            in_data = False
        if in_data and s and not s.startswith("END_DATA"):
            p = s.split()
            n += 1
            p[1] = f"{(n * 0.37) % 100:.4f}"
            p[2] = f"{(n * 0.61) % 100:.4f}"
            p[3] = f"{(n * 0.83) % 100:.4f}"
            lines.append(" ".join(p))
            continue
        lines.append(line)
    (plain / "Demo-Report-Matrix-verify.ti3").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")

    # (label, which .ti3 opens the window, which results table to scroll to,
    #  what that table shows). One document holds every measurement, so the
    # three shots differ by the TABLE they are scrolled to, not by the file.
    shots = [("04", dates[0], "N-A", "Row B refused: this is the first measurement"),
             ("05", dates[0], "PASS", "both rows judged, on a later measurement"),
             ("06", "2026-09-22_120000", "__REASONS__",
              "Row A refused: this chart repeats no colour")]
    fm = FileManager(settings)
    fm.set_target_name("Demo-Report-Matrix")
    for n_, date, want, what in shots:
        t3 = vdir / date / "Demo-Report-Matrix-verify.ti3"
        rep = mr.build_report(t3)
        vals = mr.row_values(rep)
        record["measured"][f"report/{date}"] = {
            "what": what,
            ROW_A: vals.get(ROW_A), ROW_B: vals.get(ROW_B),
            "repeat_within_sheet": rep.get("repeat_within_sheet"),
            "repeat_across_sheets": rep.get("repeat_across_sheets"),
        }
        dlg = MeasurementReportDialog(settings, None, initial_ti3=t3)
        dlg.resize(1500, 1020)
        dlg.show()
        dlg.raise_()
        pump(app, 2200)
        # SCROLL TO THE TABLE THAT CARRIES THE VERDICT, not to the first time
        # the label is mentioned. The document holds one results table per
        # measurement and the label also appears once in the "how to read
        # this" list at the top, so occurrence 1 is prose and occurrence
        # 1 + n is measurement n's table. The first version of this driver
        # took occurrence 1 and photographed an explainer three times.
        try:
            dlg._view.moveCursor(QTextCursor.MoveOperation.Start)
            # OCCURRENCE COUNTING WAS NOT ENOUGH, because the document also
            # carries a summary table and a "not computed" paragraph that
            # mention the row. So walk the occurrences and stop at the first
            # whose own table says *want*: the picture is then guaranteed to
            # be of a table in the state it claims to show.
            plain = dlg._view.toPlainText()
            hit = 0
            needle = ("never asks for the same colour twice"
                      if want == "__REASONS__"
                      else "Repeat patches on one sheet")
            while dlg._view.find(needle):
                hit += 1
                pos = dlg._view.textCursor().position()
                near = plain[pos:pos + 240]
                if want in (None, "__REASONS__") or want in near:
                    break
                if hit > 40:
                    break
            dlg._view.ensureCursorVisible()
            pump(app, 400)
            # …and lift it off the bottom edge, where `ensureCursorVisible`
            # leaves it: the row under it is the second of the pair.
            sb = dlg._view.verticalScrollBar()
            sb.setValue(min(sb.maximum(), sb.value() + 240))
            pump(app, 500)
        except Exception as exc:                          # noqa: BLE001
            record["frames"][f"{n_}-scroll"] = f"scroll failed: {exc!r}"
        # WHAT THE WINDOW ITSELF SAYS, per measurement it is showing, so the
        # picture and the numbers cannot disagree. Read from `_verdict_rows`,
        # which is what draws the table.
        seen = []
        try:
            for rr in (dlg._runs_for_report() or []):
                rows_, _rec = dlg._verdict_rows(rr)
                w = {x.get("row_id"): (x.get("word"), x.get("value"))
                     for x in rows_ if x.get("row_id") in (ROW_A, ROW_B)}
                seen.append({"created": rr.get("created"), **w})
        except Exception as exc:                          # noqa: BLE001
            seen = [{"error": repr(exc)[:120]}]
        record["measured"][f"window/{date}"] = seen

        ok, why, d = twice(app, dlg, out / f"{n_}-report-{date}.png")
        record["frames"][f"{n_}-report-{date}.png"] = (
            f"{what} | " + (f"ok{'; ' + why if why else ''}" if ok
                            else f"REFUSED: {why}"))
        print(f"    photo {n_} ({what}): "
              f"{'ok' if ok else 'REFUSED: ' + why}", flush=True)
        dlg.close()
        pump(app, 600)

    # NO ISO NUMBER MAY BE ON ANY OF THESE PICTURES. Asked of the data the
    # window drew from, not of the picture, because a picture cannot be
    # grepped: the two read-only columns must hold no numeric limit at all.
    leaked = {sid: [rid for rid, lim in cs.factory_limits(sid).items()
                    if lim.is_numeric] for sid in cs.ISO_SET_IDS}
    record["iso_columns_hold_no_numbers"] = not any(leaked.values())
    record["iso_leak_check"] = leaked

    (out / "run.json").write_text(json.dumps(record, indent=1, default=str),
                                  encoding="utf-8")
    print(f"\n    wrote {out / 'run.json'}", flush=True)
    refused = [k for k, v in record["frames"].items() if "REFUSED" in str(v)]
    print(f"    frames refused: {len(refused)} {refused}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
