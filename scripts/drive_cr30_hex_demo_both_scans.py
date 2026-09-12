#!/usr/bin/env python3
"""Walk the ChromIQ-CR30-hex-demo pack through the REAL scanner window, twice.

One chart, two scans. The first should go all the way through and build a
profile; the second should stop on "Part of this scan has no colour left in
it". This drives the real app in a real window, photographs what happens, and
writes down what each scan actually did.

Sandbox the settings and the presets FIRST, or this writes into the store the
owner works in every day::

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-cr30demo.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-cr30demo-presets
    python scripts/drive_cr30_hex_demo_both_scans.py --pack DIR --out DIR
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
from onscreen_capture import capture_window, session_is_locked    # noqa: E402

SRGB = Path("/Applications/Argyll/ref/sRGB.icm")

modals: list = []
_timers: list = []


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def install_modal_watchdog(app, shots: Path, answer: dict):
    """Photograph every modal that appears, write down what it says, and press
    a button so the driver never blocks on an `.exec()`.

    ONE watchdog for the whole run. Two of them would photograph and answer the
    same window twice, and the second press would land on a dialog that had
    already gone.
    """
    seen = {"n": 0}

    def check():
        w = app.activeModalWidget()
        if w is None:
            return
        seen["n"] += 1
        parts = []
        for attr in ("windowTitle", "text", "informativeText", "toPlainText"):
            f = getattr(w, attr, None)
            if callable(f):
                try:
                    v = str(f())
                except Exception:                              # noqa: BLE001
                    continue
                if v:
                    parts.append(v)
        p = shots / f"modal-{seen['n']:02d}.png"
        ok, why = capture_window(w, p)
        pressed = None
        try:
            for b in w.buttons():
                if b.text().replace("&", "") == answer["press"]:
                    pressed = b.text()
                    b.click()
                    break
        except Exception:                                      # noqa: BLE001
            pass
        if pressed is None:
            try:
                w.reject()
            except Exception:                                  # noqa: BLE001
                w.close()
        modals.append({"tag": answer.get("tag", ""),
                       "title": parts[0] if parts else "",
                       "said": parts, "pressed": pressed,
                       "shot": p.name if ok else None,
                       "capture": why or "ok"})
        print(f"    !! modal {seen['n']}: {parts[:2]}  -> pressed {pressed!r}")
    t = QTimer()
    t.setInterval(400)
    t.timeout.connect(check)
    t.start()
    _timers.append(t)


def shot(win, path: Path, res: dict, key: str) -> None:
    ok, why = capture_window(win, path)
    res.setdefault("shots", {})[key] = path.name if ok else f"REFUSED: {why}"
    print(f"    shot {key}: {'ok' if ok else 'REFUSED ' + why}")


def wait_while(pred, app, seconds: float) -> bool:
    end = time.time() + seconds
    while time.time() < end and pred():
        app.processEvents()
        time.sleep(0.02)
    return not pred()


def settle(dlg, app, quiet: float, cap: float) -> None:
    """Run until the window's log has been silent for *quiet* seconds, or *cap*
    seconds have gone by. A build ends in several different places - a refusal,
    a modal answered Stop, colprof finishing - and going quiet is the one
    condition all of them reach."""
    end = time.time() + cap
    last, changed = "", time.time()
    while time.time() < end:
        app.processEvents()
        time.sleep(0.05)
        now = dlg._log.toPlainText()
        if now != last:
            last, changed = now, time.time()
        elif time.time() - changed > quiet:
            return
    print("    (the build did not go quiet inside its cap)")


def one_scan(app, main, settings, chart, scan, out, shots, tag):
    from core.argyll_runner import ArgyllRunner
    import ui.dialogs.scanin_dialog as SD
    res: dict = {"tag": tag, "scan": scan.name}

    dlg = SD.ScannerProfileDialog(ArgyllRunner(settings), settings, main)
    dlg.resize(1500, 1020)
    dlg.show()
    pump(app, 1500)
    shot(dlg, shots / f"{tag}-01-open.png", res, "01-open")

    # The README's order, exactly: the chart first, with "Profile my printer
    # from this scan" left alone.
    dlg._set_chart(chart)
    pump(app, 1500)
    res["chart_note"] = dlg._chart_note.text()
    print(f"    chart note : {res['chart_note']!r}")

    picks = [scan]
    SD.open_file_dialog = lambda *a, **k: (str(picks.pop(0)) if picks else "")
    dlg._pick_scan()
    pump(app, 2000)
    res["sample_area"] = {"value": dlg._sample_area.value(),
                          "max": dlg._sample_area.maximum()}
    print(f"    sample area: {res['sample_area']}")
    shot(dlg, shots / f"{tag}-02-loaded.png", res, "02-loaded")

    print("    auto align")
    dlg._on_auto_align()
    wait_while(lambda: getattr(dlg, "_align_thread", None) is not None,
               app, 180)
    pump(app, 800)
    res["corners"] = [[round(x, 1), round(y, 1)]
                      for x, y in dlg._marquee.corners_image_px()]
    shot(dlg, shots / f"{tag}-03-aligned.png", res, "03-aligned")

    # Check alignment, TWICE on the same scan and the same corners: once with
    # "Profile my printer from this scan" on, where the window reads through
    # `scanin -c`, and once with it off, where it reads against the chart's own
    # .cie. Both are the app's own Check alignment; if the two disagree about
    # how much of the scan ran out of scale, one of them is not looking at the
    # scan.
    for label, printer in (("scanner", False), ("printer", True)):
        dlg._printer_cb.setChecked(printer)
        if printer:
            # The scanner ICC that path needs. Any input profile lets it run,
            # and this one ships with ArgyllCMS.
            dlg._printer_scan_profile = SRGB if SRGB.is_file() else None
        pump(app, 500)
        mark = len(dlg._log.toPlainText())
        dlg._on_check_alignment()
        settle(dlg, app, quiet=4.0, cap=300.0)
        said = dlg._log.toPlainText()[mark:]
        res[f"check_alignment_{label}"] = said[-3000:]
        print(f"    check ({label}): "
              + " | ".join(l.strip() for l in said.splitlines()
                           if l.strip().startswith(("⚠", "✓")))[:300])
    dlg._printer_cb.setChecked(True)
    pump(app, 500)

    res["can_run"] = dlg._can_run()
    print(f"    can run    : {res['can_run']}")
    print("    build")
    dlg._execute()
    settle(dlg, app, quiet=6.0, cap=900.0)
    shot(dlg, shots / f"{tag}-04-built.png", res, "04-built")

    res["findings"] = [{"page": pg, "title": t, "body": b}
                       for pg, t, b in getattr(dlg, "_read_findings", [])]
    res["log"] = dlg._log.toPlainText()[-8000:]
    made = sorted(p.name for p in scan.parent.iterdir()
                  if p.suffix.lower() in (".icc", ".icm", ".ti3"))
    res["written_beside_the_scan"] = made
    print(f"    findings   : {[f['title'] for f in res['findings']]}")
    print(f"    written    : {made}")
    dlg.close()
    pump(app, 600)
    (out / f"{tag}.json").write_text(json.dumps(res, indent=2),
                                     encoding="utf-8")
    return res


def main() -> int:
    a = sys.argv
    # ABSOLUTE, both of them: scanin is run from a working directory of the
    # window's choosing, and a relative path handed to it opens nothing.
    pack = Path(a[a.index("--pack") + 1]).resolve() if "--pack" in a else None
    out = (Path(a[a.index("--out") + 1]) if "--out" in a
           else Path("./drive-out")).resolve()
    assert pack and pack.is_dir(), "--pack must name the built demo pack"
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    shots = out / "shots"
    shots.mkdir(parents=True, exist_ok=True)

    locked = session_is_locked()
    print(f"00 screen locked: {locked}")

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))    # what main.py paints with
    from core.resource_path import resource_path
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))

    from core.settings import AppSettings
    settings = AppSettings()
    work = out / "work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    settings.set("custom_output_path", str(work))
    settings.set("scanner_hex_charts", True)
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    print(f"00 sandbox: {os.environ['CHROMIQ_SETTINGS_FILE']}, work {work}")

    from ui.main_window import MainWindow
    main_win = MainWindow(settings)
    main_win.resize(1400, 900)
    main_win.show()
    pump(app, 2500)
    ok, why = capture_window(main_win, shots / "00-main.png")
    print(f"    main window shot: {'ok' if ok else 'REFUSED ' + why}")

    answer = {"press": "Build anyway", "tag": ""}
    install_modal_watchdog(app, shots, answer)
    results = {"screen_locked": locked, "main_window_shot": ok,
               "main_window_why": why, "modals": modals}
    chart = pack / "chart" / "CR30HexDemo.ti2"
    # Each scan gets its own copy, because the window names its outputs after
    # the scan and writes them beside it.
    for tag, name, press in (
            ("in-range", "CR30HexDemo-scan-1-in-range.tif", "Build anyway"),
            ("out-of-scale", "CR30HexDemo-scan-2-out-of-scale.tif", "Stop")):
        room = work / tag
        room.mkdir(parents=True, exist_ok=True)
        scan = room / name
        shutil.copy2(pack / "scan" / name, scan)
        answer["press"], answer["tag"] = press, tag
        print(f"\n== {tag} ==")
        results[tag] = one_scan(app, main_win, settings, chart, scan, out,
                                shots, tag)

    (out / "drive.json").write_text(json.dumps(results, indent=2),
                                    encoding="utf-8")
    print(f"\nwrote {out / 'drive.json'}")
    main_win.close()
    pump(app, 500)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
