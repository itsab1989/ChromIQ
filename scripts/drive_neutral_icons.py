"""Census of every non-grey pixel in the Neutral appearance, icon-first.

Sandboxed: writes its settings, presets and output into /tmp and refuses to
start if the store it actually opened is not the sandbox file.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

TAG  = os.environ.get("ICONS_TAG", "after")
WORK = pathlib.Path("/tmp/icons-agent-work"); WORK.mkdir(parents=True, exist_ok=True)
INI  = pathlib.Path("/tmp/icons-agent.ini")
PRE  = pathlib.Path("/tmp/icons-agent-presets"); PRE.mkdir(parents=True, exist_ok=True)
INI.write_text(f"[General]\ncustom_output_path={WORK}\nappearance=neutral\n",
               encoding="utf-8")
os.environ["CHROMIQ_SETTINGS_FILE"] = str(INI)
os.environ["CHROMIQ_PRESETS_DIR"]   = str(PRE)
os.chdir(str(WORK))                       # a stable cwd: the Paths tab shows it

MODE = os.environ.get("ICONS_MODE", "neutral")
OUT  = pathlib.Path(os.environ.get("ICONS_OUT", f"/tmp/icons-census/{TAG}-{MODE}"))
OUT.mkdir(parents=True, exist_ok=True)

from PyQt6.QtCore import QPoint, Qt                       # noqa: E402
from PyQt6.QtGui import QCursor                           # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

app = QApplication(sys.argv[:1])
from main import WinButtonLayoutStyle                     # noqa: E402
app.setStyle(WinButtonLayoutStyle("Fusion"))
# The mouse sitting over a widget paints a hover state and shows up as a
# difference that is not one. Park it in the corner before anything is grabbed.
QCursor.setPos(QPoint(0, 0))

from core.settings import AppSettings                     # noqa: E402
s = AppSettings()
store = getattr(s, "_qs", None)
fn = store.fileName() if store is not None else ""
if str(INI) not in str(fn):
    raise SystemExit(f"REFUSING TO RUN: settings opened {fn!r}, not {INI}")
s.set("custom_output_path", str(WORK))
s.set("appearance", MODE)

from ui.main_window import MainWindow                     # noqa: E402
from ui.theme import apply_appearance, active_mode        # noqa: E402
from scripts.find_non_neutral_pixels import scan_widget   # noqa: E402

w = MainWindow(s)
resolved = apply_appearance(app, w, MODE)
w.resize(1500, 1000)
w.show()
for _ in range(80):
    app.processEvents()
assert active_mode() == MODE, f"appearance is {active_mode()}, wanted {MODE}"

# The viewers show the user's own colours and are excluded by design.
SKIP = ("TiffPreview", "GamutPanel", "PatchCubePanel", "SpectrumPreview",
        "OverlayView", "QWebEngineView")


def census(root, label: str, save: bool = True) -> list:
    for _ in range(30):
        app.processEvents()
    if save:
        root.grab().save(str(OUT / f"{label}.png"))
    if MODE != "neutral":
        return []
    hits = scan_widget(root, tolerance=6, min_pixels=12, skip=SKIP)
    # scan_widget reports a container as well as the child that painted inside
    # it, so the same pixels are counted twice. A hit's `path` runs
    # innermost-first, so A is an ANCESTOR of B exactly when A.path is a suffix
    # of B.path -- drop those and only the widget that actually painted stays.
    paths = [h.path for h in hits]
    leaf = [h for h in hits
            if not any(o != h.path and o.endswith(" < " + h.path) for o in paths)]
    return [{"where": label, "widget": h.widget, "name": h.object_name,
             "px": h.pixels, "share": round(h.share, 2),
             "colours": [[c, n] for c, n in h.colours[:4]], "path": h.path}
            for h in leaf]


report: list = []
tabs = w._tabs
for i in range(tabs.count()):
    tabs.setCurrentIndex(i)
    for _ in range(50):
        app.processEvents()
    name = f"{i}-{tabs.tabText(i).strip().replace(' ', '-').replace('.', '')}"
    report += census(w, name)
tabs.setCurrentIndex(0)
for _ in range(40):
    app.processEvents()

(OUT / "census.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
tot = sum(r["px"] for r in report)
print(f"[{TAG}/{MODE}] windows={tabs.count()} hits={len(report)} px={tot}")
for r in sorted(report, key=lambda r: -r["px"])[:25]:
    print(f'  {r["px"]:6d}  {r["widget"]}#{r["name"]:20s} {r["colours"][:2]}  ({r["where"]})')
