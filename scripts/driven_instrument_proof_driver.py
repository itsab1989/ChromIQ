#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""TEMPLATE: an on-screen proof driver for an instrument ChromIQ drives itself.

Runnable as it is against the SIMULATED i1iO 2 table (no USB device, no instrument is ever
opened). Copy it for your own device and replace the block marked INSTRUMENT-SPECIFIC; keep the
rest, because each part is there for a reason that cost a round to learn
(docs/adding_an_instrument.md, section 12b, "Proof"):

* the REAL app, fully styled, built as the app builds itself (``scripts/userdrive.py::Drive``:
  ``capture_screens.build_app``, the theme, the pop-up watchdog, focus given back, the display
  kept awake only while it runs, a hard time limit);
* settings, presets, logs and projects in a sandbox inside OUTDIR (it refuses to start without
  ``CHROMIQ_SETTINGS_FILE``, so it can never write the settings you work with);
* the device simulated behind the app's ONE seam (``ui/i1io_table_window.py::JOB_FACTORY``), and
  a guard that refuses any ArgyllCMS instrument program for the whole run;
* a REAL chart, made by the Create Chart tab as a person makes it;
* simulated readings near each patch's expected colour with a small visible deviation, at a
  human pace, so the pictures look like a real measurement (grey readings and a pace far faster
  than the device's made the first proof look broken although the code was right);
* every photograph taken of the window itself (``onscreen_capture.capture_window`` through
  ``Drive.shot``), checked for an empty or black buffer and retaken after waking the display;
* one function per PASS, and an INDEX.md that says what each picture must show, for the
  person who checks them.

It never prints, never takes the keyboard (no raise, no activate), and never deletes anything
outside the new OUTDIR it creates.

    export CHROMIQ_SETTINGS_FILE=/path/to/new/folder/settings.ini
    python scripts/driven_instrument_proof_driver.py /path/to/new/folder/proof --pass first
    python scripts/driven_instrument_proof_driver.py /path/to/new/folder/proof-de --pass first --language de
    python scripts/driven_instrument_proof_driver.py /path/to/new/folder/proof-stop --pass stop

Needs: macOS with a display and Screen Recording allowed for the terminal (on another system it
runs, and the pictures may be missing: say so in your report), ArgyllCMS (``targen`` builds the
chart), the project's .venv. A pass takes one to five minutes.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

PASSES = ("first", "stop")


def _args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("outdir", help="a NEW folder for the pictures, the index and the sandbox")
    ap.add_argument("--pass", dest="pass_", choices=PASSES, default="first")
    ap.add_argument("--language", default="en", help="UI language code, e.g. en or de")
    ap.add_argument("--size", default="1500x1000", help="window size, e.g. 1500x1000 or 900x650")
    return ap.parse_args(argv)


A = _args()                       # --help ends here, before anything is imported or written
if not os.environ.get("CHROMIQ_SETTINGS_FILE"):
    sys.exit("Set CHROMIQ_SETTINGS_FILE to a scratch .ini first (see scripts/README.md): this "
             "driver builds a real AppSettings and must never reach your own settings.")
OUT = Path(A.outdir).resolve()
if OUT.exists():
    sys.exit(f"{OUT} exists already: give a NEW folder")
ROOT = Path(__file__).resolve().parent.parent
(OUT / "sandbox" / "presets").mkdir(parents=True)
(OUT / "sandbox" / "logs").mkdir(parents=True)
(OUT / "tmp").mkdir()
os.environ.setdefault("CHROMIQ_PRESETS_DIR", str(OUT / "sandbox" / "presets"))
os.environ.setdefault("CHROMIQ_LOG_DIR", str(OUT / "sandbox" / "logs"))
os.environ["TMPDIR"] = str(OUT / "tmp")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

# ==== INSTRUMENT-SPECIFIC (1 of 2): switch the Beta on for this process ====================
from workflow.i1io import support  # noqa: E402

support.set_enabled_for_this_process(True)
# ===========================================================================================

from userdrive import Drive  # noqa: E402

W_, H_ = (int(v) for v in A.size.lower().split("x"))
d = Drive(OUT, language=A.language, size=(W_, H_), time_limit_s=1200)
d.shots = OUT
d.settings.set("sound_enabled", False)

from PyQt6.QtGui import QImage  # noqa: E402
from core.file_manager import Project  # noqa: E402
from core.i18n import tr  # noqa: E402
import onscreen_capture  # noqa: E402

# ---- safety: no ArgyllCMS instrument program may start during a proof run ------------------
from core import argyll_runner as _AR  # noqa: E402

REFUSED = []
_ORIG_RUN = _AR.ArgyllRunner.run
_INSTRUMENT_TOOLS = {"chartread", "spotread", "dispcal", "dispread", "illumread", "ccxxmake",
                     "i1d3ccss", "oeminst", "spec2cie_inst"}


def _guarded_run(self, tool, args, cwd, *a, **k):
    if Path(str(tool)).name.split(".")[0] in _INSTRUMENT_TOOLS:
        REFUSED.append(str(tool))
        d.note(f"   [guard] refused to start the instrument program {tool!r}")
        return None
    return _ORIG_RUN(self, tool, args, cwd, *a, **k)


_AR.ArgyllRunner.run = _guarded_run

# ---- every photograph checked: not an empty, black or one-colour buffer ---------------------
INDEX: "list[tuple[str, str]]" = []
_ORIG_SHOT = d.shot


def _why_blank(path: Path) -> str:
    im = QImage(str(path))
    if im.isNull():
        return "no image"
    colours, lum = set(), 0.0
    for i in range(32):
        for j in range(32):
            c = im.pixelColor(int((i + 0.5) * im.width() / 32), int((j + 0.5) * im.height() / 32))
            colours.add(c.rgb())
            lum += 0.3 * c.red() + 0.59 * c.green() + 0.11 * c.blue()
    if len(colours) < 8:
        return f"only {len(colours)} colours"
    return "black" if lum / 1024 < 10 else ""


def shot(name: str, what: str, widget=None) -> bool:
    """Photograph *widget* (default: the main window) and say in INDEX.md what it must show."""
    name = f"{A.language}-{name}"
    ok = False
    for attempt in range(3):
        ok = _ORIG_SHOT(widget or d.win, name)
        why = _why_blank(OUT / f"{name}.png") if ok else "capture failed"
        if not why:
            break
        ok = False
        d.note(f"   [photo] {name}: {why}; waking the display, try {attempt + 2}")
        onscreen_capture.wake_the_display()
        d.pump(1500)
    INDEX.append((f"{name}.png", what + ("" if ok else " (PHOTOGRAPH FAILED)")))
    return ok


# ==== INSTRUMENT-SPECIFIC (2 of 2): the i1iO 2 table on its simulator ======================
import ui.i1io_table_window as W  # noqa: E402
from tests.i1io_table import reader_sim as RS  # noqa: E402
from tests.i1io_table.window_sim import WindowSim  # noqa: E402

d.settings.set("i1io_support_beta", True)
d.settings.set("i1io_table_consent_given", 0)            # a first drive on this computer
d.settings.set("i1io_table_ask_after_each_step", A.pass_ == "first")
SIM = WindowSim(cold=(A.pass_ == "first"))
W.JOB_FACTORY = SIM.factory                              # the app's one seam: no USB, ever
NAME = "Driven-Proof"
_proj = Project.create(d.work / NAME, NAME)
RUN = _proj.current_run()
RUN.ensure_dir()

#: The person's answer to every page, by the page's id (pressed by their ENGLISH label).
ANSWERS = {
    "consent": "I understand, drive my table", "prepare": "Start", "ready_to_open": "Start",
    "pending_marker": "I switched it off and on",
    "start_up": "Start the table, my hands are away", "go": "Go",
    "sheet_laid": "The page is laid, and my hands are away from the table",
    "arm_felt": "It moves freely", "aimed": "Aimed",
    "reader_consent": "Open the instrument", "calibration_place": "Table's tile",
    "calibration_own_tile": "Ready", "calibration_reseated": "Seated",
    "report_after_step": "As described, my hands are away",
    "front_choice": "I will move the sheet", "first_visit": "Make this move, my hands are away",
    "row_failed": "Read it again", "next_page": "Go on", "home_offered": "Bring the arm home",
    "home_at_end": "Bring the arm home, my hands are away",
    "cal_choice": "Table's tile", "stored_white_refused": "Go on",
}
TICKED = ("consent", "ready_to_open")
PACE = {"s": 0.0}
_EXPECTED: dict = {}


def _expected_for(loc):
    if not _EXPECTED:
        tm = d.win._tab_measure
        _EXPECTED.update(tm._table_chart_expected(tm._chart_file_for(tm._ti1_path)))
    return _EXPECTED.get(loc)


_ORIG_XYZ = RS.FakeHelperProc._xyz_here


def _like_a_real_device(self):
    """A reading near the patch's expected colour, a little off, at a human pace. A reading
    with the arm at rest is the table's own tile: left as the simulator makes it."""
    xyz, spec = _ORIG_XYZ(self)
    try:
        if float(self.helper.sim.pos[1]) < 300:
            return xyz, spec
        _sid, loc = self.patches[self.at]
    except Exception:  # noqa: BLE001 - not a patch reading: keep the simulator's answer
        return xyz, spec
    if PACE["s"]:
        time.sleep(PACE["s"])
    e = _expected_for(loc)
    if e is None:
        return xyz, spec
    shift = (1.04, 1.0, 0.95)
    return [round(max(0.5, min(120.0, v * shift[i])), 4) for i, v in enumerate(e)], spec


RS.FakeHelperProc._xyz_here = _like_a_real_device


def pshot(w, name: str, what: str) -> bool:
    """Photograph the device's PANEL (its own top-level window), not the main window: the
    4.3.49 safety review found the panel's question pages photographed as the Create Chart tab
    because the main window was the default (review 449, SHOULD-7)."""
    return shot(name, what, w.window() if w is not None else None)


def panel():
    w = getattr(d.win._tab_measure, "_table_window", None)
    if w is not None and d.dog is not None and w.popup() is not None:
        d.dog.claim(w.popup())                # the pop-up is the driver's, not a stray window
    return w


def wait_idle(w, limit_s=120):
    end = time.monotonic() + limit_s
    while w._busy and time.monotonic() < end:
        d.pump(40)
    d.pump(150)


def press(w, english, wait=True):
    """Press an answer by its English label, as a person would, once it is pressable (a
    hands-off answer is held for a moment after its page appears)."""
    wait_idle(w)
    want = tr(english)
    end = time.monotonic() + 3.0
    found = []
    while time.monotonic() < end:
        found = [b for b in w._buttons if b.text() == want and b.isEnabled()]
        if found:
            break
        d.pump(100)
    if not found:
        raise AssertionError(f"no button {english!r}; buttons: {[b.text() for b in w._buttons]}")
    found[0].click()
    if wait:
        wait_idle(w)


SEEN: set = set()


def answer(w, page):
    if page not in SEEN:                  # every page photographed the first time it shows
        SEEN.add(page)
        pshot(w, f"{len(SEEN):02d}-{page}", f"the table's page '{page}' the first time it is shown: "
             "the whole text readable, no button cut or overlapping, no default button, one "
             "red Stop")
    if page in TICKED:
        for cb in w._tick_widgets:
            cb.setChecked(True)
    if page == "aimed":
        SIM.aim(w._last.detail["mark"])   # the simulated person puts the sight on the mark
    press(w, ANSWERS[page])


def _at_the_rows(w, page) -> bool:
    """4.3.50: the hands-off GO before the first move of a row (the mark-3 check is gone)."""
    last = getattr(w, "_last", None)
    return page == "go" and last is not None and (last.detail or {}).get("step") == "read_row"


def drive_until(w, stop, limit=1500):
    stop = (stop,) if isinstance(stop, str) else tuple(stop)
    for _ in range(limit):
        wait_idle(w)
        page = w.pages_shown[-1]
        if page in stop:
            return page
        if "rows" in stop and _at_the_rows(w, page):
            return "rows"
        answer(w, page)
    raise AssertionError(f"never reached {stop}; last pages {w.pages_shown[-8:]}")


def into_a_running_row(w, limit_s=120):
    """Answer the pages that still come (a first visit, a consent) until a row is being read,
    then give it a moment, so the picture shows a row in progress and not a question."""
    end = time.monotonic() + limit_s
    while time.monotonic() < end:
        d.pump(200)
        if w._busy:
            d.pump(3000)
            if w._busy:
                return True
            continue
        page = w.pages_shown[-1]
        if page in ANSWERS and page != "row_failed":
            answer(w, page)
        else:
            return False
    return False


def make_chart(patches=60):
    """A REAL chart for the instrument, made by Create Chart (Manual) as a person makes it."""
    tc = d.win._tab_chart
    d.goto_tab("chart")
    tc._switch_mode("manual")
    tc._init_manual_layout_panel()
    p = tc._manual_layout_panel
    k = p.instr.findData("IO2")
    assert k >= 0, "the instrument is not offered: is its Beta on?"
    p.instr.setCurrentIndex(k)
    p.instr.activated.emit(k)
    d.pump(800)
    for pw in tc._manual_widgets.get("targen", []):
        if pw.flag == "-f":
            pw.set_value(patches)
    d.pump(500)
    d.note(f"Create Chart: targen -f = {tc._manual_value('targen', '-f')}")
    d.later(tc._on_generate)
    t0 = time.monotonic()
    while time.monotonic() - t0 < 300:
        d.pump(300)
        if not d.win._runner.is_running and tc._generate_btn.isEnabled() \
                and RUN.chart_ti2.is_file():
            break
    d.pump(1500)
    shot("00-create-chart", "Create Chart after Generate: the chart the device will read")


def start():
    """To the Measure tab, the chart loaded, START pressed; the hand path's guards answered."""
    d.open_project(NAME)
    d.pump(1200)
    d.set_bar(run="run1", run_type="Profiling")
    make_chart()
    d.goto_tab("measure")
    d.pump(1200)
    tm = d.win._tab_measure
    tm._manual_btn.click()
    d.pump(600)
    tm.set_ti1_path(RUN.chart_ti2)
    d.pump(1200)
    d.later(tm._start_btn.click)
    return tm
# ===========================================================================================


def pass_first():
    """A whole first measurement in the asking mode: every page, a row running, the ending."""
    start()
    yield 1500
    w = panel()
    drive_until(w, "rows")
    pshot(w, "first-row-go", "the hands-off question before the first row (no mark-3 check)")
    SIM.transport.delay_s, PACE["s"] = 0.06, 0.6     # a human pace while photographed
    press(w, "Go", wait=False)
    into_a_running_row(w)
    pshot(w, "row-running", "a row being read: the current patch marked strongly, read patches "
         "calmly, expected and measured side by side, one red Stop")
    wait_idle(w, 240)
    SIM.transport.delay_s, PACE["s"] = 0.0, 0.0
    drive_until(w, "end_of_session")
    pshot(w, "ending", "every row read: Save and stop / Discard and stop / Keep measuring")
    press(w, "Save and stop")
    while w.pages_shown[-1] in ("home_offered", "go", "home_at_end"):
        press(w, {"home_offered": "Bring the arm home", "go": "Go",
                  "home_at_end": "Bring the arm home, my hands are away"}[w.pages_shown[-1]])
    pshot(w, "done", "the panel's last page after the Save")
    d.later([b for b in w._buttons if b.text() == tr("Close")][0].click)
    yield 800
    d.answer("Close", name=f"{A.language}-completion-window", within_ms=8000)
    INDEX.append((f"{A.language}-completion-window.png",
                  "the same completion window as after a hand measurement"))
    yield 1500
    shot("after-save", "the Measure tab after Save: the measurement in place, the tab unlocked")


def pass_stop():
    """Stop while a row runs: the move finishes, the Stopped page, Next step asks GO again."""
    start()
    yield 1500
    w = panel()
    drive_until(w, "rows")
    SIM.transport.delay_s, PACE["s"] = 0.09, 0.6
    press(w, "Go", wait=False)
    into_a_running_row(w)
    SIM.transport.delay_s = 3.0                       # a move still under way when Stop comes
    d.pump(300)
    w._stop_btn.click()
    d.pump(150)
    pshot(w, "stop-pressed", "Stop pressed while a row runs: the state says the move under way "
         "finishes first, then ChromIQ stops")
    wait_idle(w, 240)
    SIM.transport.delay_s, PACE["s"] = 0.0, 0.0
    pshot(w, "stopped", f"after Stop: page '{w.pages_shown[-1]}' with Next step / Bring the arm home")
    press(w, "Next step")
    pshot(w, "go-after-carry-on", "Next step asks the hands-off GO before anything moves again")
    w._on_end_pressed()
    wait_idle(w)
    if w.pages_shown[-1] == "end_of_session":
        press(w, "Discard and stop")
    yield 1000


def script(drive):
    if drive.dog is not None:
        drive.dog.grace_s = 900.0         # the driver answers the table's own pop-ups itself
    try:
        yield from {"first": pass_first, "stop": pass_stop}[A.pass_]()
    finally:
        (OUT / "INDEX.md").write_text(
            f"# Proof pictures, pass '{A.pass_}', language {A.language}, ON SCREEN\n\n"
            "Check every picture against its line before you report it as proof.\n\n"
            + "\n".join(f"* `{n}`: {what}" for n, what in INDEX) + "\n"
            + f"\nInstrument programs refused during the run: {REFUSED or 'none'}\n",
            encoding="utf-8")
    drive.end(0, "done")


sys.exit(d.run(script))
