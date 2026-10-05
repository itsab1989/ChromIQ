#!/usr/bin/env python3
"""F-10 (#182 5985477496): Create Chart with Total Ink Limit 300 and grey steps, ON SCREEN.

    python scripts/drive_f10_ink_limit_corner.py OUT_DIR

Manual mode, CMYK (-d4), the Total Ink Limit row ticked (it pre-fills 300),
Grey Axis Steps 11, Generate. ArgyllCMS 3.5.0 targen used to abort here with
"ofps: assert"; with the guard it is handed 300.1 and the chart is built. The
driver photographs the settings and the finished preview with
``capture_window``, reads targen's argv and the chart's recorded
TOTAL_INK_LIMIT from the run folder, and saves the app log of the drive.

Run with CHROMIQ_TREE pointing at a tree without the guard for the "before"
pictures. Sandbox: userdrive's (settings, presets, projects under OUT_DIR).
Never opens an instrument: export ARGYLL_EXCLUDE_SERIAL_SCAN first.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_TREE = Path(os.environ.get("CHROMIQ_TREE")
             or Path(__file__).resolve().parents[1]).resolve()
sys.path.insert(0, str(_TREE / "scripts"))
sys.path.insert(0, str(_TREE))
sys.path.insert(0, str(Path(__file__).resolve().parent))

OUT = Path(sys.argv[1]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
os.environ["CHROMIQ_SETTINGS_FILE"] = str(OUT / "sandbox" / "settings.ini")
os.environ["CHROMIQ_PRESETS_DIR"] = str(OUT / "sandbox" / "presets")
os.environ.setdefault("ARGYLL_EXCLUDE_SERIAL_SCAN", "/dev/cu.Bluetooth-Incoming-Port")
(OUT / "sandbox" / "presets").mkdir(parents=True, exist_ok=True)

from userdrive import Drive                                   # noqa: E402
from onscreen_capture import PopupWatchdog                    # noqa: E402

NAME = "F10-ink-limit"


def _row(tab, flag):
    for pw in tab._manual_widgets.get("targen", []):
        if pw.flag == flag:
            return pw
    raise LookupError(flag)


def script(d):
    rec = d.record
    dog = PopupWatchdog(d.out, photograph=True, policy="dismiss")
    dog.start()
    d.goto_tab("chart")
    yield 1500
    tab = d.win._tab_chart
    tab._user_switch_mode("manual")
    yield 1500
    tab._manual_target_name_edit.setText(NAME)
    yield 400

    dev = _row(tab, "-d")
    dev.set_value("4")                          # CMYK
    yield 1200
    lim = _row(tab, "-l")
    if not lim._enable_check.isChecked():
        lim._enable_check.click()               # what a user's tick does
    yield 600
    grey = _row(tab, "-g")
    # Grey Axis Steps starts on Auto (the spin box greyed out, 525 patches ->
    # -g30). Writing 11 into the greyed row without unticking Auto showed "11"
    # on screen while targen got -g30, which no user can do (the row is
    # disabled). Untick Auto first, as a user would.
    auto = getattr(tab, "_manual_auto_grey_check", None)
    if auto is not None and auto.isChecked():
        auto.click()
        yield 600
    grey.set_value(11)
    yield 800
    rec["settings_before"] = {"-d": dev.get_raw_value(),
                              "-l enabled": lim.is_enabled_by_user,
                              "-l": lim.get_raw_value(),
                              "-g": grey.get_raw_value()}
    d.note("SETTINGS " + json.dumps(rec["settings_before"]))
    # Open the targen frame (what a click on its title does) and bring the
    # ink-limit row into view for the photograph.
    grp = getattr(tab, "_manual_targen_grp", None)
    if grp is not None and grp.is_collapsed():
        grp.toggle()
        yield 1000
    from PyQt6.QtWidgets import QScrollArea
    w = lim.parentWidget()
    while w is not None:                        # the Expert Options fold too
        if hasattr(w, "is_collapsed") and w.is_collapsed():
            w.toggle()
            yield 800
        w = w.parentWidget()
    w = lim
    while w is not None and not isinstance(w, QScrollArea):
        w = w.parentWidget()
    if w is not None:
        w.ensureWidgetVisible(lim, 50, 200)
    yield 800
    d.shot(d.win, "01-settings-cmyk-ink-limit-300-grey-11")

    tab._generate_btn.click()
    run_dir = d.work / NAME / "runs" / "run1"
    for _ in range(300):                        # up to 5 minutes
        yield 1000
        busy = bool(tab._creator._runner
                    and tab._creator._runner.is_running)
        tif = list(run_dir.glob("*.tif")) if run_dir.is_dir() else []
        if tif and not busy:
            break
    yield 3000
    d.shot(d.win, "02-after-generate")

    ti1 = run_dir / f"{NAME}.ti1"
    ti2 = run_dir / f"{NAME}.ti2"

    def kw(p):
        if not p.exists():
            return None
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("TOTAL_INK_LIMIT"):
                return line.strip()
        return "(no TOTAL_INK_LIMIT)"

    rec["result"] = {
        "run_folder": sorted(p.name for p in run_dir.iterdir()) if run_dir.is_dir() else [],
        "ti1_TOTAL_INK_LIMIT": kw(ti1),
        "ti2_TOTAL_INK_LIMIT": kw(ti2),
        "settings_after": {"-l": lim.get_raw_value(), "-l enabled": lim.is_enabled_by_user},
    }
    d.note("RESULT " + json.dumps(rec["result"]))
    dog.stop()
    rec["popups"] = dog.events


if __name__ == "__main__":
    drive = Drive(OUT, language="en", size=(1500, 1000))
    rc = drive.run(script)
    text = (OUT / "chromiq-log-during-drive.txt").read_text(encoding="utf-8")
    drive.record["targen_lines"] = [ln for ln in text.splitlines()
                                    if "targen" in ln and ("args" in ln or "ink limit" in ln
                                                           or "assert" in ln or "exited" in ln)]
    (OUT / "result.json").write_text(json.dumps(drive.record, indent=2, default=str),
                                     encoding="utf-8")
    sys.exit(rc or 0)
