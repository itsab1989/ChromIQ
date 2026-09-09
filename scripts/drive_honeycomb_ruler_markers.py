#!/usr/bin/env python3
"""Drive the REAL window: a honeycomb can now carry ruler markers.

Basti, 2026-09-09: *"can't they be turned on by the user if he wants? they are
optional anyway and benefitial here but only as an option i think."*

Before this change `geometry.py` returned NO markers for any hexagonal chart,
and the six marker controls were greyed out, so the user could not switch them
on even if they wanted to. The premise was that "a honeycomb has no rows to line
a ruler up with"; measured on a real CR30 sheet, that is false. A honeycomb's
patch centres lie on straight lines along three directions, and on any page
exactly one of the two page axes is one of them. Today it is the axis ACROSS the
page, where `dy = 0.0000` between strips at a 12.0000 mm pitch.

So the top and bottom comb lands on every patch and stays; the side comb, which
steps down the page, would point at the gaps between patches and is dropped.

What this photographs, in the order a user meets it:
  1. a CR30 with square patches: every marker control live, both combs draw;
  2. the same with Hexagon patches on: the group is STILL live, the side switch
     is greyed with its own reason, and the dashes appear on the sheet;
  3. the built page, so the dashes can be seen against the honeycomb;
  4. the numbers read back off the layout the app actually used.

Settings and the ChromIQ root are sandboxed. Nothing of the user's is touched:

    defaults read com.chromiq.ChromIQ custom_output_path

Usage::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-markers.ini \
        python scripts/drive_honeycomb_ruler_markers.py
"""
from __future__ import annotations

import json
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

from PyQt6.QtCore import QSettings, Qt                          # noqa: E402
from PyQt6.QtGui import QFontDatabase                           # noqa: E402
from PyQt6.QtTest import QTest                                  # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog,             # noqa: E402
                             QMessageBox)

from core.resource_path import resource_path                    # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"
SHOTS = Path.home() / "Desktop" / "ChromIQ-hex-proof" / "01-markers"


def pump(app, ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def shot(w, name):
    """Grab a widget, and SAY SO WHEN THE GRAB IS EMPTY.

    `QWidget.grab()` on a widget inside a collapsed section returns a null
    pixmap and `save()` then returns False without raising. The first version
    of this driver printed "saved 03-...png" for a file that was never written,
    which is the one kind of proof worse than none.
    """
    SHOTS.mkdir(parents=True, exist_ok=True)
    pm = w.grab()
    ok = (not pm.isNull()) and pm.save(str(SHOTS / f"{name}.png"))
    if ok:
        print(f"        saved {name}.png  ({pm.width()}x{pm.height()})")
    else:
        print(f"        >>> {name}.png WAS NOT WRITTEN: the widget grabbed "
              f"{pm.width()}x{pm.height()}")
    return bool(ok)


def run(app) -> int:
    from core.settings import AppSettings
    from workflow.layout_engine import geometry, instruments

    sb = Path(tempfile.mkdtemp(prefix="chromiq-markers-"))
    src = QSettings(str(REAL_PLIST), QSettings.Format.NativeFormat)
    dst = QSettings(str(sb / "settings.ini"), QSettings.Format.IniFormat)
    for k in src.allKeys():
        dst.setValue(k, src.value(k))
    dst.sync()
    s = AppSettings()
    s._qs = dst
    work = sb / "ChromIQ"
    work.mkdir()
    s.set("custom_output_path", str(work))
    s.set("restore_last_session", False)
    s.set("use_chromiq_layout_engine", True)

    QDialog.exec = lambda self: 1                  # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    TabChart._confirm_displacing_results = lambda self, *a, **k: True

    win = MainWindow(s)
    win.show()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 600)
    tab._user_switch_mode("manual")
    pump(app, 1500)

    panel = tab._manual_layout_panel
    if panel is None:
        print("        no layout panel in this build")
        return 1

    def pick_instrument(code):
        c = tab._instr_combo
        i = c.findData(code)
        c.showPopup(); pump(app, 300)
        v = c.view(); v.setCurrentIndex(c.model().index(i, 0)); pump(app, 120)
        QTest.keyClick(v, Qt.Key.Key_Return); pump(app, 600)
        if c.currentData() != code:
            c.hidePopup(); c.setCurrentIndex(i); c.activated.emit(i); pump(app, 400)

    def state(tag):
        # TICK THE MASTER BOX FIRST, because that is the order a user works in
        # and the two edge switches are greyed until it is on. An earlier run
        # of this driver read them while it was off, reported both dead, and
        # very nearly filed a working feature as broken -- and then ticking it
        # exposed a real defect underneath: the tick handed the side comb back.
        panel.helper_markers_cb.setChecked(True)
        pump(app, 300)
        print(f"            [panel instrument={panel.instr.currentData()!r} "
              f"shape={panel.mode.currentData()!r} "
              f"tab-says-hex={tab._chart_is_hexagonal()}]")
        g = panel._helper_markers_grp
        st = {
            "group enabled": g.isEnabled(),
            "markers ticked": panel.helper_markers_cb.isChecked(),
            "top/bottom switch enabled": panel.helper_markers_top_bottom.isEnabled(),
            "side switch enabled": panel.helper_markers_sides.isEnabled(),
            "side switch still ticked": panel.helper_markers_sides.isChecked(),
        }
        print(f"        {tag}")
        for k, v in st.items():
            print(f"            {k:<28} {v}")
        return st

    report = {}
    bad = 0
    tab._user_switch_mode("manual")
    pump(app, 1200)

    def set_shape(code):
        """Set the patch shape ON THE MANUAL PANEL, which is where the markers
        live and where the user setting them is standing.

        NOT through the Guided hexagon tick: measured here, that tick never
        reaches this combo (`panel.mode` stays 'flat' with Guided showing
        Hexagon), which is the recording-end defect already carried as an
        xfail in test_a_run_reopens_on_its_own_instrument.py. Driving Guided
        would prove nothing about the markers and everything about that.
        """
        c = panel.mode
        i = c.findData(code)
        c.setCurrentIndex(i)
        c.activated.emit(i)
        pump(app, 700)

    def set_panel_instrument(code):
        c = panel.instr
        i = c.findData(code)
        c.setCurrentIndex(i)
        c.activated.emit(i)
        pump(app, 700)

    print("\n  1. CR30, square patches")
    set_panel_instrument("CR30")
    set_shape("flat")
    report["square"] = state("with square patches:")
    shot(win, "01-cr30-square-markers-available")

    print("\n  2. the same chart with Hexagon patches on")
    set_shape("hex")
    report["honeycomb"] = state("with the honeycomb:")
    shot(win, "02-cr30-honeycomb-markers-still-available")

    if not report["honeycomb"]["group enabled"]:
        print("        >>> the marker group is still greyed on a honeycomb"); bad += 1
    if not report["honeycomb"]["top/bottom switch enabled"]:
        print("        >>> the straight comb is unreachable"); bad += 1

    print("\n  3. what the engine draws for that layout")
    for hf, label in ((False, "square"), (True, "honeycomb")):
        g = instruments.build("CR30", hflag=hf, spacer_on=False)
        lay = geometry.compute(g, 210.0, 297.0, 300)
        counts = {}
        for tb, sd, nm in ((True, False, "top and bottom only"),
                           (False, True, "sides only"),
                           (True, True, "both asked for")):
            counts[nm] = len(geometry.helper_marker_lines_mm(
                g, 210.0, 297.0, lay, top_bottom=tb, sides=sd))
        print(f"        {label:10} " + "  ".join(
            f"{k}: {v}" for k, v in counts.items()))
        report[f"dashes_{label}"] = counts
    if report["dashes_honeycomb"]["sides only"] != 0:
        print("        >>> the engine drew the comb that marks the gaps"); bad += 1
    if report["dashes_honeycomb"]["top and bottom only"] == 0:
        print("        >>> the engine drew nothing for the straight axis"); bad += 1

    # ---- 4. the controls themselves, not the window they are lost in ----
    print("\n  4. the ruler-marker section, close up")
    # The markers live in "Expert Options", which ships collapsed. Open it, or
    # the grab is of a widget with no size and the proof is a blank file.
    ef = getattr(panel, "_expert_frame", None)
    if ef is not None and ef.is_collapsed():
        ef.set_collapsed(False)
        pump(app, 700)
    grp = panel._helper_markers_grp
    pump(app, 500)
    if not shot(grp, "03-the-marker-controls-on-a-honeycomb"):
        bad += 1
    print("        side switch tooltip:")
    tip = panel.helper_markers_sides.toolTip()
    for line in (tip[:300] + ("..." if len(tip) > 300 else "")).split(". "):
        print(f"            {line.strip()}")
    report["side_tooltip"] = tip
    if not tip:
        print("        >>> greyed with no explanation, which is what #152 forbids")
        bad += 1

    # ---- 5. a real page, judged AGAINST A CONTROL ----
    #
    # ABSOLUTE COUNTS LIE ON THIS SHEET, and the first run of this driver was
    # taken in by them: it counted 30 dark runs down the left margin and
    # reported the side comb had reached paper. It had not. Those 30 were the
    # ROW NUMBERS 1..23, which the chart prints in that margin. The same trap
    # sits across the top (nine registration marks before any comb exists) and
    # in the middle (22 long black rules, which are the CR30's own strip
    # guides and are drawn whether or not markers are asked for).
    #
    # So build the sheet TWICE, once with the markers off, and report only what
    # CHANGED. What the change is responsible for is the difference.
    print("\n  5. a real CR30 honeycomb page, against a control")
    import numpy as np
    from PIL import Image
    from workflow.layout_engine import chart as le_chart

    n = 210
    lines = ["CTI1", "", 'DESCRIPTOR "honeycomb marker probe"',
             'ORIGINATOR "ChromIQ"', 'KEYWORD "SAMPLE_LOC"',
             "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
             "END_DATA_FORMAT", f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    for i in range(n):
        lines.append(f"{i+1} 78.0 78.0 78.0 40.0 45.0 50.0")
    lines += ["END_DATA", ""]

    def build(tag, **kw):
        proj = work / tag
        proj.mkdir(parents=True, exist_ok=True)
        ti1 = proj / "probe.ti1"
        ti1.write_text("\n".join(lines), encoding="utf-8")
        res = le_chart.build_chart(ti1, proj / "c", instrument="CR30",
                                   paper="A4", hflag=True, dpi=200,
                                   randomize=False, **kw)
        tif = sorted(proj.glob("*.tif"))[0]
        im = Image.open(tif).convert("RGB")
        im.save(str(SHOTS / f"04-page-{tag}.png"))
        a = np.asarray(im).astype(int)
        h, w = a.shape[:2]
        dark = a.sum(axis=2) < 200
        # the top margin, past the column where the row numbers are printed
        band = dark[0:int(h * 0.05), int(w * 0.15):]
        c = band.any(axis=0)
        top = int(np.sum(c[1:] & ~c[:-1])) + int(c[0])
        # the left margin, between the two combs so the corners cannot count
        lb = dark[int(h * 0.08):int(h * 0.92), 0:int(w * 0.04)]
        r = lb.any(axis=1)
        side = int(np.sum(r[1:] & ~r[:-1])) + int(r[0])
        return res, top, side

    ctl, ctl_top, ctl_side = build("markers-off", helper_markers=False)
    run, run_top, run_side = build("markers-on", helper_markers=True,
                                   helper_markers_top_bottom=True,
                                   helper_markers_sides=True)
    print(f"        built {run.layout.total_patches} hexagons, "
          f"{run.layout.passes} strips x {run.layout.steps_in_pass}")
    print(f"        top margin   markers off {ctl_top:3}  ->  on {run_top:3}"
          f"   (+{run_top - ctl_top})")
    print(f"        left margin  markers off {ctl_side:3}  ->  on {run_side:3}"
          f"   (+{run_side - ctl_side})")
    report["paper"] = {"top_off": ctl_top, "top_on": run_top,
                       "side_off": ctl_side, "side_on": run_side}
    if run_top <= ctl_top:
        print("        >>> ticking the markers on printed nothing new"); bad += 1
    if run_side != ctl_side:
        print("        >>> the side comb reached paper, marking the gaps"); bad += 1
    if run.layout.total_patches != ctl.layout.total_patches:
        print("        >>> the markers cost patches on the sheet"); bad += 1

    SHOTS.mkdir(parents=True, exist_ok=True)
    (SHOTS / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"\n  problems: {bad}")
    print(f"  proof in {SHOTS}")
    win.close()
    pump(app, 400)
    return 1 if bad else 0


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)
    return run(app)


if __name__ == "__main__":
    raise SystemExit(main())
