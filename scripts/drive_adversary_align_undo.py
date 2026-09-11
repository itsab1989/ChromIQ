#!/usr/bin/env python3
"""Does the Auto align undo let go when the PICTURE changes, or only when the
Patch sample area does?

Today's scanner round fixed one control: moving "Patch sample area" now ends
the one-step undo, because the number is an input to the alignment and the
button was otherwise offering to put back the corners the user had just decided
against. This driver asks the same question of the controls beside it: switching
to another scan of the same page, and loading a different scan into the slot.

Drives the REAL window, on screen, sandboxed settings/presets/working folder.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-adv.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-adv-presets
    python scripts/drive_adversary_align_undo.py --out DIR [--tag before]
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

PACK = Path("/tmp/chromiq-adv-sample/ChromIQ-hex-scanner-sample")
CHART = PACK / "chart" / "SquareChart.ti2"
SCAN_A = PACK / "scan" / "SquareChart-simulated-scan.tif"
SCAN_B = PACK / "scan" / "HexChart-simulated-scan.tif"
WORK = Path("/tmp/chromiq-adv-align-work")

modals: list = []
_timers: list = []


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def install_modal_watchdog(app, shots: Path):
    seen = {"n": 0}

    def check():
        w = app.activeModalWidget()
        if w is None:
            return
        text = ""
        for attr in ("text", "toPlainText"):
            f = getattr(w, attr, None)
            if callable(f):
                try:
                    text = str(f())
                    break
                except Exception:
                    pass
        seen["n"] += 1
        p = shots / f"align-modal-{seen['n']:02d}.png"
        ok, why = capture_window(w, p)
        modals.append({"title": w.windowTitle(), "text": text[:500],
                       "shot": p.name if ok else None, "capture": why or "ok"})
        print(f"    !! modal {seen['n']}: {text[:110]!r}")
        try:
            w.reject()
        except Exception:
            w.close()
    t = QTimer()
    t.setInterval(350)
    t.timeout.connect(check)
    t.start()
    _timers.append(t)


def shot(win, path: Path, res: dict, key: str) -> None:
    ok, why = capture_window(win, path)
    res.setdefault("shots", {})[key] = path.name if ok else f"REFUSED: {why}"
    print(f"    shot {key}: {'ok' if ok else 'REFUSED ' + why}")


def wait_for_align(dlg, app, seconds: float = 120.0) -> None:
    end = time.time() + seconds
    while time.time() < end and getattr(dlg, "_align_thread", None) is not None:
        app.processEvents()
        time.sleep(0.02)
    pump(app, 600)


def state(dlg) -> dict:
    u = getattr(dlg, "_align_undo", None)
    return {"button": dlg._auto_align_btn.text(),
            "undo_held": None if u is None else [[round(x, 1), round(y, 1)]
                                                 for x, y in u],
            "corners": [[round(x, 1), round(y, 1)]
                        for x, y in dlg._marquee.corners_image_px()]}


def main() -> int:
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else Path("/tmp/chromiq-adv-proof")
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "run"
    shots = out / "shots"
    shots.mkdir(parents=True, exist_ok=True)

    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert CHART.is_file(), f"build the sample pack first: {CHART}"

    res: dict = {"tag": tag, "modals": modals,
                 "screen_locked": session_is_locked()}
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

    from core.argyll_runner import ArgyllRunner
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    dlg = ScannerProfileDialog(ArgyllRunner(settings), settings)
    dlg.resize(1500, 1020)
    dlg.show()
    pump(app, 1500)
    install_modal_watchdog(app, shots)

    # "Profile my printer from this scan": the chart was printed, never measured.
    dlg._printer_cb.setChecked(True)
    pump(app, 600)
    dlg._set_chart(CHART)
    pump(app, 1500)

    # Pick the scan through the window's own handler, with the chooser answered
    # for it, so nothing about the load is special-cased here.
    import ui.dialogs.scanin_dialog as SD
    picks = [SCAN_A, SCAN_B]

    def _answer(*a, **k):
        return str(picks.pop(0)) if picks else ""
    SD.open_file_dialog = _answer
    dlg._pick_scan()
    pump(app, 1800)
    shot(dlg, shots / f"{tag}-10-loaded.png", res, "10-loaded")
    res["after_load"] = state(dlg)
    print(f"    after load : {res['after_load']['button']!r}")

    print("A  press Auto align")
    dlg._on_auto_align()
    wait_for_align(dlg, app)
    res["after_align"] = state(dlg)
    print(f"    button     : {res['after_align']['button']!r}")
    shot(dlg, shots / f"{tag}-11-aligned.png", res, "11-aligned")

    print("B  add a SECOND scan of the same page and switch to it")
    dlg._add_shot()          # "Add another scan to average" — a second shot
    pump(app, 800)
    dlg._pick_scan()         # the chooser answers with SCAN_B
    pump(app, 1800)
    res["after_second_scan"] = state(dlg)
    print(f"    button     : {res['after_second_scan']['button']!r}")
    print(f"    undo holds : {res['after_second_scan']['undo_held']}")
    shot(dlg, shots / f"{tag}-12-second-scan.png", res, "12-second-scan")

    print("C  press the button that is offered")
    before = state(dlg)
    dlg._on_auto_align()
    wait_for_align(dlg, app)
    after = state(dlg)
    res["after_press"] = after
    res["press_moved_grid"] = before["corners"] != after["corners"]
    print(f"    button     : {after['button']!r}")
    print(f"    grid moved : {res['press_moved_grid']}")
    shot(dlg, shots / f"{tag}-13-after-press.png", res, "13-after-press")

    (out / f"align-{tag}.json").write_text(json.dumps(res, indent=2),
                                           encoding="utf-8")
    print(f"\nwrote {out / f'align-{tag}.json'}")
    dlg.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
