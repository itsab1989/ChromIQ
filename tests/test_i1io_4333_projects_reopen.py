"""AN i1iO PROJECT MADE BY 4.3.33 OPENS AND GENERATES (owner, 2026-11-13).

The owner: the i1iO is a Beta released a few hours before this, so a chart
4.3.33 made need not print as it did; it must open, show a panel that says
what prints, and build without error. Two projects made by 4.3.33 itself on
screen (`tests/data/i1io_4333_projects`, see its README) are opened on the
REAL main window with a Preferences label style set, walked through the
modes, and built at every stop:

* the build succeeds, and in Manual the label style the panel shows is the
  one the build draws (Preferences' style for a recipe without its own);
* a chart 4.3.33 made with the aiming crosses OFF comes back with them off
  and with its smaller right margin, so more strips than a sheet with
  crosses (review 3, item 7, a bug 4.3.33 had too).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "tests" / "data" / "i1io_4333_projects"

PROBE = r"""
import json, os, sys, time
from pathlib import Path
sys.path.insert(0, os.environ["CHROMIQ_ROOT"])
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
app = QApplication([])
from ui.styles import WinButtonLayoutStyle
app.setStyle(WinButtonLayoutStyle("Fusion"))
from core.numeric_locale import pin_c_numeric_locale
pin_c_numeric_locale()
from core.settings import AppSettings
s = AppSettings()
out = Path(os.environ["CHROMIQ_PROBE_OUT"])
s.set("custom_output_path", str(out))
s.set("restore_last_session", False)
s.set("session_project", "")
s.set("sound_enabled", False)
s.set("i1io_support_beta", True)
s.set("strip_underline_mode", "black")
s.set("strip_indicator_font", "Inter")
s.set("strip_indicator_bold", True)
s.set("strip_indicator_align", "center")
from workflow.i1io.support import latch_from
assert latch_from(s) is True
from ui.main_window import MainWindow
win = MainWindow(s)
win.resize(1400, 900)
win.show()

def close_modals():
    w = QApplication.activeModalWidget()
    if w is not None:
        w.reject() if hasattr(w, "reject") else w.close()

guard = QTimer()
guard.timeout.connect(close_modals)
guard.start(300)

def pump(ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)

name = os.environ["CHROMIQ_PROBE_NAME"]
tab = win._tab_chart
pump(500)
QTimer.singleShot(0, lambda: tab.open_project_manifest(
    out / name / "project.json"))
pump(3000)

from workflow.i1io import chart as C
from workflow.layout_engine import chart as E
ti1 = out / name / "runs" / "run1" / (name + ".ti1")
stops = []

def stop(tag):
    params = tab._collect_params()
    kw = tab._creator._engine_kwargs(params)   # what Generate builds
    folder = out / ("build-%d-%s" % (len(stops), tag))
    folder.mkdir()
    kw = {k: v for k, v in kw.items() if k not in ("seed", "chart_date", "project")}
    E.build_chart(ti1, folder / "c", seed=11, project=name,
                  chart_date="2026-11-13", **kw)
    side = json.loads((folder / "c.i1io.json").read_text(encoding="utf-8"))
    panel = getattr(tab, "_manual_layout_panel", None)
    rec = tab._current_layout_recipe() if panel is not None else None
    lab = C.label_wishes(kw)
    stops.append({
        "tag": tag, "mode": tab._current_mode(),
        "printed_underline": lab.underline, "printed_align": lab.align,
        "shown_underline": (panel.underline_mode.currentData()
                            if panel is not None else None),
        "shown_align": (("left", "center", "right")[
            [panel.ind_align_left.isChecked(),
             panel.ind_align_center.isChecked(),
             panel.ind_align_right.isChecked()].index(True)]
            if panel is not None else None),
        "panel_crosses": None if rec is None else rec.i1io_crosses,
        "side": side})

first = tab._current_mode()
other = "guided" if first == "manual" else "manual"
stop("opened-" + first)
for m in (other, first, other):
    tab._switch_mode(m)
    pump(1500)
    stop("then-" + m)
(out / "stops.json").write_text(json.dumps(stops), encoding="utf-8")
"""


@pytest.mark.slow
@pytest.mark.parametrize("name,patches", [("m-style", None),
                                          ("m-lock-nox", 552)])
def test_a_4333_project_opens_and_generates(tmp_path, name, patches):
    out = tmp_path / "out"
    shutil.copytree(DATA / name, out / name)
    env = dict(os.environ, CHROMIQ_ROOT=str(ROOT),
               CHROMIQ_PROBE_OUT=str(out), CHROMIQ_PROBE_NAME=name,
               CHROMIQ_SETTINGS_FILE=str(tmp_path / "s.ini"),
               CHROMIQ_PRESETS_DIR=str(tmp_path / "presets"),
               CHROMIQ_LOG_DIR=str(tmp_path / "logs"))
    proc = subprocess.run([sys.executable, "-c", PROBE], env=env, cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=600)
    assert proc.returncode == 0, proc.stderr[-3000:]
    stops = json.loads((out / "stops.json").read_text(encoding="utf-8"))
    assert len(stops) == 4
    for st in stops:
        where = f"{name} " + str({k: v for k, v in st.items() if k != "side"})
        if st["mode"] == "manual":
            assert st["shown_underline"] == st["printed_underline"], where
            assert st["shown_align"] == st["printed_align"], where
        n = sum(len(s["patches"]) for s in st["side"]["pages"][0]["strips"])
        assert n > 0, where
        if patches is not None and st["mode"] == "manual":
            # crosses off as stored, and their room given to patches: more
            # strips than a sheet with crosses holds (12 x 22 = 528)
            assert st["panel_crosses"] is False, where
            assert st["side"]["pages"][0]["aim"] != "crosses", where
            assert len(st["side"]["pages"][0]["strips"]) > 22, where
