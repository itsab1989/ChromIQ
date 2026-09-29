#!/usr/bin/env python3
"""A COMPLETE verification measurement of a padded chart: taken, or turned away?

Today's measurement-import round put the profile-build import's patch count
through `measurement_state.expected_patches`, which discounts the rows a chart
adds to fill out its last strip. The Measure tab's own copy of that count, which
the round's comment named, was left reading the raw `NUMBER_OF_SETS` — and it is
the door that REFUSES rather than the one that labels.

Drives the REAL window, on screen, sandboxed settings/presets/working folder.
It asks the tab the same question `_on_import_measurement` asks, and shows the
same refusal window that handler shows, with the app's own words.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-adv.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-adv-presets
    python scripts/drive_adversary_padded_chart_refusal.py --out DIR --tag after
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QTimer                                   # noqa: E402
from PyQt6.QtGui import QFontDatabase                             # noqa: E402
from PyQt6.QtWidgets import QApplication                          # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))                         # noqa: E402
from onscreen_capture import capture_window, session_is_locked     # noqa: E402

WORK = Path("/tmp/chromiq-adv-count-work")
FIELDS = "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z"
DESIGNED, PAD = 400, 14

modals: list = []
_timers: list = []


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def write_chart(ti2: Path) -> None:
    rows = [f'{i} "A{i}" 50.0 50.0 50.0 50.0 50.0 50.0'
            for i in range(1, DESIGNED + 1)]
    rows += [f'{DESIGNED + k} "A{DESIGNED + k}" 100.0 100.0 100.0 95.0 100.0 108.0'
             for k in range(1, PAD + 1)]
    ti2.write_text(
        'CTI2\n\nDESCRIPTOR "x"\nORIGINATOR "ChromIQ layout engine"\n'
        'STEPS_IN_PASS "20"\n\n'
        f"NUMBER_OF_FIELDS {len(FIELDS.split())}\n"
        f"BEGIN_DATA_FORMAT\n{FIELDS}\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n" + "\n".join(rows)
        + "\nEND_DATA\n", encoding="utf-8")
    d = [f"{i} 50.0 50.0 50.0" for i in range(1, DESIGNED + 1)]
    ti2.with_suffix(".ti1").write_text(
        'CTI1\n\nDESCRIPTOR "x"\n\nNUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n'
        "SAMPLE_ID RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {DESIGNED}\nBEGIN_DATA\n" + "\n".join(d)
        + "\nEND_DATA\n", encoding="utf-8")


def write_measurement(ti3: Path) -> None:
    """A COMPLETE measurement of that chart: one reading per designed patch."""
    rows = [f'{i} "A{i}" 50.0 50.0 50.0 50.0 50.0 50.0'
            for i in range(1, DESIGNED + 1)]
    ti3.write_text(
        'CTI3\n\nDESCRIPTOR "x"\nDEVICE_CLASS "OUTPUT"\nCOLOR_REP "RGB_XYZ"\n\n'
        f"NUMBER_OF_FIELDS {len(FIELDS.split())}\n"
        f"BEGIN_DATA_FORMAT\n{FIELDS}\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n" + "\n".join(rows)
        + "\nEND_DATA\n", encoding="utf-8")


def main() -> int:
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else Path("/tmp/chromiq-adv-proof")
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "run"
    shots = out / "shots"
    shots.mkdir(parents=True, exist_ok=True)

    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"

    res: dict = {"tag": tag, "screen_locked": session_is_locked()}
    print(f"00 screen locked: {res['screen_locked']}")

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from core.resource_path import resource_path
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))

    from core.settings import AppSettings
    settings = AppSettings()
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True, exist_ok=True)
    settings.set("custom_output_path", str(WORK))
    settings.set("appearance", "dark")
    from ui import theme as ui_theme
    ui_theme.apply_appearance(app, None, "dark")
    assert settings.get("custom_output_path", "") == str(WORK), "SANDBOX FAILED"
    print(f"00 sandbox: settings {os.environ['CHROMIQ_SETTINGS_FILE']}, work {WORK}")

    chart = WORK / "verify.ti2"
    meas = WORK / "measured.ti3"
    write_chart(chart)
    write_measurement(meas)
    print(f"00 chart: {DESIGNED} designed + {PAD} fill-up rows; "
          f"measurement: {DESIGNED} readings")

    from core.argyll_runner import ArgyllRunner
    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1620, 1040)
    win.show()
    pump(app, 1800)
    tab = win._tab_measure
    try:
        win._tabs.setCurrentWidget(tab)
    except Exception:
        pass
    pump(app, 700)

    from workflow.measurement_state import expected_patches
    res["counts"] = {
        "expected_patches": expected_patches(chart),
        "tab_chart_patch_count": tab._chart_patch_count(chart),
    }
    print(f"01 counts: {res['counts']}")

    # The exact question `_on_import_measurement` asks before it files anything.
    reason = tab._import_mismatch_reason(meas, chart)
    res["refusal_reason"] = reason
    print(f"02 refusal reason: {reason!r}")

    if reason:
        # …and the exact window it then shows, with the catalogue's own words.
        from workflow import measurement_messages as M
        title, body = M.M_IMPORT_MISMATCH.render(reason=reason)
        res["refusal_window"] = {"title": title, "body": body}
        print(f"03 window: {title!r}\n   {body!r}")

        def snap():
            w = app.activeModalWidget()
            if w is None:
                return
            ok, why = capture_window(w, shots / f"{tag}-20-refusal.png")
            res["shot"] = ("20-refusal.png" if ok else f"REFUSED: {why}")
            print(f"    shot: {'ok' if ok else 'REFUSED ' + why}")
            w.accept()
        t = QTimer()
        t.setInterval(600)
        t.timeout.connect(snap)
        t.start()
        _timers.append(t)
        tab._show_import_refusal(M.M_IMPORT_MISMATCH, reason=reason)
        pump(app, 800)
    else:
        ok, why = capture_window(win, shots / f"{tag}-20-no-refusal.png")
        res["shot"] = ("20-no-refusal.png" if ok else f"REFUSED: {why}")
        print(f"    shot: {'ok' if ok else 'REFUSED ' + why}")

    (out / f"count-{tag}.json").write_text(json.dumps(res, indent=2),
                                           encoding="utf-8")
    print(f"\nwrote {out / f'count-{tag}.json'}")
    win.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
