#!/usr/bin/env python3
"""AGENT CQ: drive the REAL windows, and build a REAL profile from every entry.

Two things a list check cannot do, and this does both on screen:

1. reads the Algorithm / Profile type combos off the live widgets, in both
   modes of the scanner window, and shows what a project saved with an entry
   that has gone now says;
2. takes the parameters the LIVE WIDGETS produce, hands them to the app's own
   `ProfileBuilder`, and runs the real ArgyllCMS `colprof` once per entry, in
   both windows, printer mode included. A profile file has to appear.

SANDBOX THE SETTINGS FIRST. This builds a real `AppSettings`, which IS the
user's preferences store:

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-cq.ini
    python scripts/drive_colprof_algorithm_lists.py

Nothing is written inside the user's projects: every measurement is copied to a
temp folder first, and the profiles are built there.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

assert os.environ.get("CHROMIQ_SETTINGS_FILE"), \
    "SANDBOX THE SETTINGS FIRST: export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-cq.ini"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = Path("/Users/Basti/Desktop/beta 9/colprof-and-help-cards")
OUT.mkdir(parents=True, exist_ok=True)

try:                                   # same import order main.py uses
    import PyQt6.QtWebEngineWidgets    # noqa: F401
except ImportError:
    pass
from PyQt6.QtCore import QEventLoop, QTimer                    # noqa: E402
from PyQt6.QtWidgets import QApplication                       # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
from main import WinButtonLayoutStyle                          # noqa: E402
app.setStyle(WinButtonLayoutStyle("Fusion"))                   # what ships

LOG: list[str] = []


def say(s: str = "") -> None:
    print(s, flush=True)
    LOG.append(str(s))


def settle(seconds: float = 0.6) -> None:
    app.processEvents()
    time.sleep(seconds)
    app.processEvents()


def shot(widget, name: str) -> None:
    widget.raise_()
    widget.activateWindow()
    settle(0.7)
    path = OUT / name
    widget.grab().save(str(path))
    say(f"   [screenshot] {path.name}")


def dump(combo, title: str) -> None:
    say(f"  {title}  ({combo.count()} items, current={combo.currentData()!r}, "
        f"enabled={combo.isEnabled()})")
    for i in range(combo.count()):
        say(f"    [{i}] data={combo.itemData(i)!r:<5} text={combo.itemText(i)!r}")


def reveal(widget) -> bool:
    """Scroll *widget* into view inside whatever scroll area holds it.

    Agent CP's caveat, and it is worth repeating: two of that round's
    screenshots were byte-identical because the row under test was scrolled out
    of sight in both, so changing the selection changed no visible pixel. A
    picture of a control you cannot see proves nothing.
    """
    from PyQt6.QtWidgets import QAbstractScrollArea
    node = widget.parentWidget()
    while node is not None:
        if isinstance(node, QAbstractScrollArea):
            node.ensureWidgetVisible(widget, 60, 160)
            settle(0.4)
            return True
        node = node.parentWidget()
    return False


def tail(widget, n: int = 4) -> list[str]:
    lines = [ln for ln in widget.toPlainText().splitlines() if ln.strip()]
    return lines[-n:]


# ---------------------------------------------------------------------------
# Measurements, copied OUT of the user's projects before anything is built
# ---------------------------------------------------------------------------
WORK = Path(tempfile.mkdtemp(prefix="chromiq-cq-"))
SOURCES = {
    "OUTPUT": Path.home() / "ChromIQ/Demo-Switching/runs/run2/Demo-Switching.ti3",
    "INPUT": Path.home() / "ChromIQ/scanner-test-targets/real/ScannedIT8LSTarget01-8bit.ti3",
}
TI3: dict[str, Path] = {}
for cls, src in SOURCES.items():
    if not src.is_file():
        say(f"!! missing {cls} measurement: {src}")
        continue
    dst = WORK / cls.lower() / f"cq-{cls.lower()}.ti3"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dst)
    TI3[cls] = dst

say("=" * 74)
say("AGENT CQ - the colprof algorithm lists, on screen and through the tool")
say("=" * 74)
say(f"work folder      : {WORK}")
for cls, p in TI3.items():
    head = p.read_text(encoding="utf-8", errors="replace")
    dc = next((ln.strip() for ln in head.splitlines()[:60]
               if ln.startswith("DEVICE_CLASS")), "?")
    n = len(head.splitlines())
    say(f"{cls:<7} measurement: {p.name}  ({dc}, {n} lines)  from {SOURCES[cls]}")

from core.settings import AppSettings                          # noqa: E402
from core.argyll_runner import ArgyllRunner                    # noqa: E402
from workflow.profile_builder import ProfileBuilder            # noqa: E402
from workflow import profile_builder as PB                     # noqa: E402

settings = AppSettings()
say(f"settings store   : {settings._qs.fileName()}")
assert "chromiq-cq" in settings._qs.fileName(), "NOT SANDBOXED - stopping"


def run_colprof(builder: ProfileBuilder, params) -> "tuple[int, Path | None, str]":
    """Run the app's own build path and WAIT for the real tool to finish."""
    loop = QEventLoop()
    state: dict = {"code": None, "log": []}

    def _line(ln: str) -> None:
        state["log"].append(ln)

    def _done(code: int) -> None:
        state["code"] = code
        loop.quit()

    icc = builder.expected_icc_path(params)
    if icc.exists():
        icc.unlink()
    builder.build(params, _line, _done)
    QTimer.singleShot(600_000, loop.quit)          # never hang the driver
    loop.exec()
    err = " | ".join(ln for ln in state["log"] if "rror" in ln)[:150]
    return state["code"], (icc if icc.exists() else None), err


def fingerprint(icc: "Path | None") -> str:
    """A short hash of the profile with its creation time zeroed.

    Two builds a second apart differ in the ICC header's date-time and nowhere
    else, so a raw hash would say "different" about two identical profiles.
    And without a hash at all, a probe that quietly built the same thing twice
    reports two successes: the byte count alone is what let the first run of
    this driver look like it had proved something."""
    if icc is None:
        return "-"
    import hashlib
    raw = bytearray(icc.read_bytes())
    raw[24:36] = b"\0" * 12
    return hashlib.sha256(bytes(raw)).hexdigest()[:10]


# ---------------------------------------------------------------------------
# A. Build Profile -> Manual and Guided -> "Algorithm (-a)"
# ---------------------------------------------------------------------------
say("")
say("=" * 74)
say("A. Build Profile tab: the Algorithm (-a) lists")
say("=" * 74)
from ui.main_window import MainWindow                          # noqa: E402

mw = MainWindow(settings)
mw.resize(1500, 1000)
mw.show()
settle(1.2)
tab = None
for i in range(mw._tabs.count()):
    if type(mw._tabs.widget(i)).__name__ == "TabProfile":
        tab = mw._tabs.widget(i)
        mw._tabs.setCurrentIndex(i)
        break
settle(1.0)
say(f"OUTPUT_ALGORITHM_CHOICES = {PB.OUTPUT_ALGORITHM_CHOICES!r}")
say(f"legal for OUTPUT per colprof = "
    f"{sorted(PB.COLPROF_ALGORITHMS_BY_DEVICE_CLASS['OUTPUT'])}")
say("")
dump(tab._m_algo_combo, "Manual  _m_algo_combo")
say("")
dump(tab._algo_combo,
     f"Guided  _algo_combo (visible={tab._algo_combo.isVisible()})")
tab._switch_mode("manual")
settle(0.6)
say(f"  Manual module shown: _current_mode()={tab._current_mode()}")
say(f"  Algorithm row revealed: {reveal(tab._m_algo_combo)}")
shot(mw, "CQ-A1-profile-tab-algorithm-list.png")

# ---- a project saved with an entry that has gone --------------------------
say("")
say("A2. A stored algorithm this list no longer offers")
for stored in ("m", "s", "X", "x"):
    tab._log.clear()
    tab._algo_moves_said = set()
    tab._m_apply_preset_data({"algorithm": stored, "quality": "l"})
    settle(0.2)
    said = tail(tab._log, 3)
    say(f"  stored -a{stored} -> combo now {tab._m_algo_combo.currentData()!r} "
        f"({tab._m_algo_combo.currentText()!r})")
    say(f"      log: {said if said else '(nothing said, and nothing moved)'}")
tab._log.clear()
tab._algo_moves_said = set()
tab._m_apply_preset_data({"algorithm": "m", "quality": "l"})
settle(0.4)
reveal(tab._m_algo_combo)
shot(mw, "CQ-A2-stored-matrix-only-was-moved.png")

# ---- every entry, through the tool ---------------------------------------
say("")
say("A3. A REAL profile from every entry BOTH modules keep")
# BOTH MODULES, AND THE MODULE HAS TO BE SWITCHED FIRST. `_collect_params`
# reads Guided's widgets or Manual's depending on which page the stack is on,
# so setting the Manual combo while the tab shows Guided builds from the
# Guided one and answers a question nobody asked. The first run of this driver
# did exactly that, and the tell was two entries producing the same command
# and the same byte count.
if "OUTPUT" in TI3:
    tab.set_ti3_path(TI3["OUTPUT"])
    settle(0.4)
    for mode, combo, qual in (("guided", tab._algo_combo, tab._qual_combo),
                              ("manual", tab._m_algo_combo, tab._m_qual_combo)):
        tab._switch_mode(mode)
        settle(0.6)
        assert tab._current_mode() == mode, tab._current_mode()
        i = qual.findData("l")
        if i >= 0:
            qual.setCurrentIndex(i)       # Low: this is a proof, not a build
        settle(0.3)
        say(f"  --- {mode.upper()} module (_current_mode()={tab._current_mode()})")
        for i in range(combo.count()):
            combo.setCurrentIndex(i)
            settle(0.3)
            letter = combo.currentData()
            params = tab._collect_params()
            assert params.algorithm == letter, (
                f"the tab collected -a{params.algorithm} while the {mode} "
                f"combo showed -a{letter}")
            args = tab._builder._build_args(params)
            code, icc, err = run_colprof(tab._builder, params)
            say(f"    -a{letter} ({combo.currentText()})")
            say(f"        colprof {' '.join(args)}")
            say(f"        exit={code}  profile={icc.name if icc else 'NONE'}"
                f"  {(icc.stat().st_size if icc else 0)} bytes"
                f"  sha={fingerprint(icc)}  {err}")
    tab._switch_mode("manual")
    settle(0.5)
else:
    say("  !! no OUTPUT measurement available, nothing built")

# ---------------------------------------------------------------------------
# B. The scanner and camera window
# ---------------------------------------------------------------------------
say("")
say("=" * 74)
say("B. Tools -> Build profile with scanner or camera")
say("=" * 74)
from ui.dialogs import scanner_colprof as SC                   # noqa: E402
from ui.dialogs.scanin_dialog import ScannerProfileDialog      # noqa: E402

say(f"PTYPE_CHOICES         = {[d for d, _ in SC.PTYPE_CHOICES]}")
say(f"PTYPE_CHOICES_BY_MODE = {SC.PTYPE_CHOICES_BY_MODE}")
say(f"PTYPE_DEFAULT         = {SC.PTYPE_DEFAULT}")

runner = getattr(mw, "runner", None) or getattr(mw, "_runner", None) \
    or ArgyllRunner(settings)
dlg = ScannerProfileDialog(runner, settings, mw)
dlg.show()
settle(1.2)


def show_ptype_row(name: str, window=None) -> None:
    win = window if window is not None else dlg
    reveal(win._ptype)
    shot(win, name)


say("")
say(f"B1. SCANNER / CAMERA mode  (_printer_mode()={dlg._printer_mode()})")
dump(dlg._ptype, "Profile type (-a)")
say(f"  Quality (-q) enabled = {dlg._pq.isEnabled()}  "
    f"label enabled = {dlg._q_label.isEnabled()}")
show_ptype_row("CQ-B1-scanner-mode-profile-type.png")

# THE PICTURE OF THE QUALITY DEFECT. "Matrix only" is a matrix type, and this
# row used to grey Quality out for it while `make_profile_params` put the
# greyed value on the command line regardless.
i = dlg._ptype.findData("m")
dlg._ptype.setCurrentIndex(i)
settle(0.6)
say("")
say("B1b. 'Matrix only' chosen in scanner mode: is Quality still live?")
say(f"  Profile type = {dlg._ptype.currentData()!r} "
    f"({dlg._ptype.currentText()!r})")
say(f"  Quality (-q) enabled = {dlg._pq.isEnabled()}  "
    f"label enabled = {dlg._q_label.isEnabled()}  "
    f"value = {dlg._pq.currentData()!r}")
say("  command preview (the window's own box):")
for ln in dlg._cmd_preview.text().splitlines():
    say("    " + ln)
show_ptype_row("CQ-B1b-matrix-only-quality-is-live.png")
dlg._ptype.setCurrentIndex(dlg._ptype.findData("s"))
settle(0.4)

dlg._printer_cb.setChecked(True)
settle(1.0)
say("")
say(f"B2. PRINTER mode  (_printer_mode()={dlg._printer_mode()})")
dump(dlg._ptype, "Profile type (-a)")
say(f"  Quality (-q) enabled = {dlg._pq.isEnabled()}  "
    f"label enabled = {dlg._q_label.isEnabled()}")
say(f"  'Matrix only' findData('m') = {dlg._ptype.findData('m')}  "
    f"(-1 means it is not offered)")
say(f"  'Shaper + matrix' findData('s') = {dlg._ptype.findData('s')}")
show_ptype_row("CQ-B2-printer-mode-profile-type.png")

# ---- every entry, in both modes, through the tool -------------------------
for mode, on, cls in (("SCANNER / CAMERA", False, "INPUT"),
                      ("PRINTER", True, "OUTPUT")):
    say("")
    say(f"B3. A REAL profile from every entry offered in {mode} mode")
    if cls not in TI3:
        say(f"  !! no {cls} measurement available, nothing built")
        continue
    dlg._printer_cb.setChecked(on)
    settle(0.8)
    i = dlg._pq.findData("l")
    if i >= 0:
        dlg._pq.setCurrentIndex(i)
    settle(0.3)
    for idx in range(dlg._ptype.count()):
        dlg._ptype.setCurrentIndex(idx)
        settle(0.3)
        letter = dlg._ptype.currentData()
        stem = TI3[cls].with_name(f"cq-{cls.lower()}-{letter}.ti3")
        shutil.copy(TI3[cls], stem)
        params = SC.make_profile_params(stem, f"CQ {mode.lower()} {letter}",
                                        dlg._current_main_vals(),
                                        dlg._effective_adv())
        args = dlg._profiler._build_args(params)
        code, icc, err = run_colprof(dlg._profiler, params)
        say(f"  -a{letter} ({dlg._ptype.currentText()})")
        say(f"      colprof {' '.join(args)}")
        say(f"      exit={code}  profile={icc.name if icc else 'NONE'}"
            f"  {(icc.stat().st_size if icc else 0)} bytes"
            f"  sha={fingerprint(icc)}  {err}")

# ---- a printer bucket saved with a type that has gone ---------------------
say("")
say("B4. A printer settings bucket saved with 'Matrix only', reopened")
cfg = settings.get("scanner_colprof_configs", {}) or {}
cfg = dict(cfg)
cfg["printer"] = {"main": {"ptype": "m", "quality": "h", "description": ""},
                  "adv": {}, "scenario": None}
settings.set("scanner_colprof_configs", cfg)
dlg2 = ScannerProfileDialog(runner, settings, mw)
dlg2.show()
settle(1.0)
dlg2._printer_cb.setChecked(True)
settle(1.0)
say(f"  stored printer bucket ptype was 'm'; combo now "
    f"{dlg2._ptype.currentData()!r} ({dlg2._ptype.currentText()!r})")
say(f"  window log says: {tail(dlg2._log, 2)}")
show_ptype_row("CQ-B4-stored-matrix-only-in-printer-bucket.png", dlg2)

(OUT / "CQ-onscreen-log.txt").write_text("\n".join(LOG) + "\n", encoding="utf-8")
say("")
say(f"WROTE {OUT / 'CQ-onscreen-log.txt'}")
say(f"(the work folder {WORK} is left in place for inspection)")
QTimer.singleShot(400, app.quit)
app.exec()
