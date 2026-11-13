"""AN i1iO PROJECT 4.3.33 MADE IS LAID OUT AS 4.3.33 LAID IT OUT (review 3,
items 1 and 7).

Three projects made by 4.3.33 itself on screen (`tests/data/i1io_4333_
projects`, see its README) are opened on the REAL main window with the i1iO
switch on and a Preferences label style set (black underline, Inter bold,
centred), and walked through the modes as a person does: as stored, to the
other mode, and back. At every stop the chart a Generate would build is
built and compared with the one 4.3.33 built, strip by strip and patch by
patch (positions, counts, what is printed; not the shuffle):

* the recipe read from the project keeps its "made before the label
  options" mark through every apply on open, Guided and Manual alike, so
  nothing the Preferences style or Job D added reaches the sheet (item 1);
* a chart 4.3.33 made with the aiming crosses OFF comes back with them off
  and with its smaller right margin: 552 patches, not 528 (item 7).

THE MARK, BY DESIGN: a recipe this version makes in memory is stamped
modern by the constructor (`LayoutRecipe.i1io_label_options = True`); every
reader of a stored recipe (`from_dict`, and through it channels.json, the
target's state, presets and saved defaults) reads a missing mark as "made
before", and never invents one. Held for the readers by
`tests/test_i1io_label_mark.py`; held here end to end.
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
    stops.append({
        "tag": tag, "mode": tab._current_mode(),
        "legacy": C.legacy_labels(kw),
        "default_labels": C.label_wishes(kw) == C.Labels(),
        "panel_mark": None if rec is None else rec.i1io_label_options,
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


def _geometry(side: dict) -> dict:
    """What a person sees on the sheet, without the shuffle."""
    pages = []
    for p in side["pages"]:
        pages.append({
            "strips": [(s["x_mm"], tuple(s["run_mm"]),
                        [tuple(c["centre_mm"]) for c in s["patches"]],
                        [c["loc"] for c in s["patches"]])
                       for s in p["strips"]],
            "aim": p["aim"], "digits": p.get("digits_printed"),
            "aim_points": [a["page_mm"] for a in p.get("aim_points", [])]})
    return {"paper": side["paper_mm"], "patch": side["patch_mm"],
            "spacer": side["spacer_mm"], "gap": side["strip_gap_mm"],
            "labels": side.get("labels_printed"), "pages": pages}


@pytest.mark.slow
@pytest.mark.parametrize("name,patches", [
    ("m-style", 528), ("g-style", None), ("m-lock-nox", 552)])
def test_a_4333_project_reopens_as_4333_made_it(tmp_path, name, patches):
    out = tmp_path / "out"
    shutil.copytree(DATA / name, out / name)
    made = json.loads((DATA / name / "runs" / "run1" /
                       f"{name}.i1io.json").read_text(encoding="utf-8"))
    want = _geometry(made)
    if patches is not None:
        assert sum(len(s["patches"]) for s in made["pages"][0]["strips"]) \
            == patches
    env = dict(os.environ, CHROMIQ_ROOT=str(ROOT),
               CHROMIQ_PROBE_OUT=str(out), CHROMIQ_PROBE_NAME=name,
               CHROMIQ_SETTINGS_FILE=str(tmp_path / "s.ini"),
               CHROMIQ_PRESETS_DIR=str(tmp_path / "presets"),
               CHROMIQ_LOG_DIR=str(tmp_path / "logs"))
    proc = subprocess.run([sys.executable, "-c", PROBE], env=env, cwd=ROOT,
                          capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, proc.stderr[-3000:]
    stops = json.loads((out / "stops.json").read_text(encoding="utf-8"))
    assert len(stops) == 4
    for st in stops:
        where = f"{name} " + str({k: v for k, v in st.items() if k != "side"})
        if st["mode"] == "manual":
            # Manual builds from the recipe read from the project
            assert st["legacy"] is True, where
        # Guided builds from its own live choices, never a stored recipe:
        # what it prints with no label options is 4.3.33's (geometry below)
        assert st["default_labels"] is True, where
        if st["panel_mark"] is not None:
            assert st["panel_mark"] is False, where
        if name == "m-lock-nox" and st["mode"] == "guided":
            # the crosses were switched off in MANUAL; Guided keeps its own
            # answer (on), as 4.3.33 stored it, so its sheet has crosses
            assert st["side"]["pages"][0]["aim"] == "crosses", where
            continue
        assert _geometry(st["side"]) == want, where
    if name == "m-lock-nox":
        manual = [st for st in stops if st["mode"] == "manual"]
        assert manual and all(st["panel_crosses"] is False for st in manual)
