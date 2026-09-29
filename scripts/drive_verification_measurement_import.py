#!/usr/bin/env python3
"""On-screen reproduction and proof for the Measure tab's IMPORT module.

Drives the REAL ChromIQ window, on screen, against a sandboxed settings file, a
sandboxed presets folder and a sandboxed working folder, using a user's own
i1Profiler measurement export.

It answers, with the app's own words on screen:

  V1  An i1Profiler CGATS export of SPECTRAL ONLY, no device values and no CIE
      columns. Does the verification import take it, or does it refuse it as
      "No device RGB columns"?
  V2  Her chart: 408 designed patches, a 420-row `.ti2` (20 strips of 21 on
      Letter with an i1Pro). Her measurement holds 420 — every patch the sheet
      actually carries. Which count does the refusal quote, and which does the
      preview quote?
  V3  The log printed `[OK] Converted … to Argyll's .ti3 format.` twice. Does
      ONE press of Import Measurement print it once or twice?
  V4  A measurement of a DIFFERENT chart must still be refused.

THE REPORTER'S FILE IS NOT IN THIS REPO AND HER FOLDER IS NOT ANYBODY'S.
Point CHROMIQ_I1P_SAMPLES at a folder holding an i1Profiler measurement export
and CHROMIQ_I1P_MEASUREMENT at its file name; the driver says what it needs and
stops if it is not there, rather than carrying somebody's desktop path around in
the history.

Usage:

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-verimport.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-verimport-presets
    export CHROMIQ_I1P_SAMPLES=/path/to/folder
    export CHROMIQ_I1P_MEASUREMENT=i1measurement.txt
    python scripts/drive_verification_measurement_import.py --out DIR --tag before
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

sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window, session_is_locked     # noqa: E402

SAMPLES = Path(os.environ["CHROMIQ_I1P_SAMPLES"]) if os.environ.get(
    "CHROMIQ_I1P_SAMPLES") else None
MEASUREMENT = (SAMPLES / os.environ.get("CHROMIQ_I1P_MEASUREMENT", "")) \
    if SAMPLES else None
PROJECT = "printer-test"
WORK = Path(os.environ.get("CHROMIQ_VERIMPORT_WORK",
                           "/tmp/chromiq-verimport-work"))

modals: list = []
_timers: list = []


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


#: Titles whose window the driver ANSWERS YES to instead of dismissing. A
#: watchdog that rejects everything would cancel the very confirmation this
#: import now asks for, and the run would then prove only that Cancel works.
SAY_YES_TO: "list[str]" = []


def install_modal_watchdog(app, shots: Path):
    """Photograph every modal that opens, record its words, then close it.

    A driver that blocks on a modal gets clicked by the owner, and every result
    after that point is his and not the run's.
    """
    seen = {"n": 0}

    def check():
        w = app.activeModalWidget()
        if w is None:
            return
        title = w.windowTitle()
        text = ""
        for attr in ("text", "toPlainText"):
            f = getattr(w, attr, None)
            if callable(f):
                try:
                    text = str(f())
                    break
                except Exception:      # noqa: BLE001
                    pass
        info = getattr(w, "informativeText", None)
        if callable(info):
            try:
                text += "\n" + str(info())
            except Exception:          # noqa: BLE001
                pass
        seen["n"] += 1
        p = shots / f"modal-{seen['n']:02d}.png"
        ok, why = capture_window(w, p)
        answer = "dismissed"
        for needle in SAY_YES_TO:
            if needle.lower() in text.lower() or needle.lower() in title.lower():
                answer = "accepted"
                break
        modals.append({"title": title, "text": text[:900], "answer": answer,
                       "buttons": _button_labels(w),
                       "shot": p.name if ok else None, "capture": why or "ok"})
        print(f"    !! modal {seen['n']}: {title!r} -> {answer}")
        if answer == "accepted" and _click_accept(w):
            return
        try:
            w.reject()
        except Exception:              # noqa: BLE001
            w.close()
    t = QTimer()
    t.setInterval(300)
    t.timeout.connect(check)
    t.start()
    _timers.append(t)


def _button_labels(w) -> "list[str]":
    try:
        return [b.text().replace("&", "") for b in w.buttons()]
    except Exception:                  # noqa: BLE001
        return []


def _click_accept(w) -> bool:
    """Press the window's confirming button, the way a person would."""
    from PyQt6.QtWidgets import QMessageBox
    try:
        for b in w.buttons():
            if w.buttonRole(b) == QMessageBox.ButtonRole.AcceptRole:
                b.click()
                return True
    except Exception:                  # noqa: BLE001
        pass
    return False


def shot(win, path: Path, res: dict, key: str) -> None:
    ok, why = capture_window(win, path)
    res.setdefault("shots", {})[key] = path.name if ok else f"REFUSED: {why}"
    print(f"    shot {key}: {'ok' if ok else 'REFUSED ' + why}")


def _sets(p: Path):
    import re
    try:
        m = re.search(r"NUMBER_OF_SETS\s+(\d+)",
                      p.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    return int(m.group(1)) if m else None


def main() -> int:
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else Path("/tmp/chromiq-verimport-proof")
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "run"
    shots = out / "shots"
    shots.mkdir(parents=True, exist_ok=True)

    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    if MEASUREMENT is None or not MEASUREMENT.is_file():
        print("Set CHROMIQ_I1P_SAMPLES and CHROMIQ_I1P_MEASUREMENT to a folder "
              "and file holding an i1Profiler CGATS measurement export.")
        return 2
    if not (WORK / PROJECT).is_dir():
        print(f"{WORK / PROJECT} is not there — run the staging step first.")
        return 2

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
    settings.set("custom_output_path", str(WORK))
    settings.set("appearance", "dark")
    settings.set("argyll_bin_path", "/Applications/Argyll/bin")
    from ui import theme as ui_theme
    ui_theme.apply_appearance(app, None, "dark")
    assert settings.get("custom_output_path", "") == str(WORK), "SANDBOX FAILED"
    print(f"00 sandbox: settings {os.environ['CHROMIQ_SETTINGS_FILE']}, "
          f"work {WORK}")

    run_dir = WORK / PROJECT / "runs" / "run1"
    vdir = run_dir / "verifications"
    ti1, ti2 = vdir / f"{PROJECT}-verify.ti1", vdir / f"{PROJECT}-verify.ti2"
    from workflow.measurement_state import expected_patches
    res["counts"] = {
        "chart_ti1_designed_sets": _sets(ti1),
        "chart_ti2_sheet_rows": _sets(ti2),
        "expected_patches_designed": expected_patches(ti2),
        "measurement_sets": _sets(MEASUREMENT),
    }
    print(f"00 counts: {res['counts']}")

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1680, 1060)
    win.show()
    pump(app, 1800)
    SAY_YES_TO.append("Only you can confirm this is a measurement of this "
                      "chart")
    install_modal_watchdog(app, shots)

    # Open the staged project the way the app opens one.
    tab = win._tab_measure
    ctl = getattr(tab, "_target_ctl", None)
    fm = getattr(ctl, "_fm", None)
    from ui.measurement_filing import open_the_project
    open_the_project(tab, fm, PROJECT, WORK / PROJECT)
    pump(app, 1200)

    from core.measurement_target import RUN_TYPE_VERIFICATION
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    pump(app, 900)
    win._tabs.setCurrentWidget(tab)
    pump(app, 600)
    res["import_button_visible"] = tab._import_btn.isVisible()
    tab._import_btn.click()
    pump(app, 900)
    res["import_panel_shown"] = tab._stack.currentIndex()
    shot(win, shots / f"{tag}-00-import-mode.png", res, "00-import-mode")

    def press(label: str, path: Path) -> dict:
        """Choose a file, press Import Measurement ONCE, and record what the
        app said. One press per call, so the log line count means something."""
        print(f"{label}: {path.name}")
        tab._import_path = path
        tab._update_import_panel()
        pump(app, 600)
        before_log = tab._log.toPlainText()
        before_modals = len(modals)
        tab._import_go_btn.click()
        pump(app, 3000)
        new_log = tab._log.toPlainText()[len(before_log):]
        rec = {"file": path.name,
               "info_box": tab._import_box_body.text(),
               "log": new_log,
               "converted_lines": new_log.count("to Argyll's .ti3 format"),
               "modals": modals[before_modals:]}
        for m in rec["modals"]:
            print(f"    modal: {m['title']!r} -> {m['answer']}")
        print(f"    converted lines: {rec['converted_lines']}")
        return rec

    # THE REFUSALS FIRST, while the run still holds no measurement — an import
    # that has already succeeded would meet M-IMPORT-DATE-TAKEN instead.
    # ------------------------------------------------------------------ V4 --
    other = WORK / "other-chart-measurement.txt"
    _relabel(MEASUREMENT, other, lambda n: "Z" + n)
    res["V4_foreign_chart"] = press(
        "V4 a measurement of a DIFFERENT chart is still refused", other)
    shot(win, shots / f"{tag}-01-foreign.png", res, "01-foreign")

    # ------------------------------------------------------------------ V5 --
    short = WORK / "short-measurement.txt"
    _truncate(MEASUREMENT, short, 300)
    res["V5_short"] = press(
        "V5 a genuinely SHORT measurement is still refused", short)

    # ------------------------------------------------------------------ V6 --
    twice = WORK / "one-patch-twice.txt"
    _duplicate_one(MEASUREMENT, twice)
    res["V6_duplicate_name"] = press(
        "V6 one patch measured twice is refused", twice)

    # ------------------------------------------------------------ V1..V3 ----
    res["V1_hers"] = press(
        "V1/V2/V3 her own spectral-only measurement, ONE press", MEASUREMENT)
    shot(win, shots / f"{tag}-02-after-press.png", res, "02-after-press")

    vid = ctl.target.verification_id
    from core.measurement_target import resolve_run
    run = resolve_run(fm.project(), ctl.target)
    filed = run.verification(vid).measurement_ti3 if vid else None
    res["filed"] = {
        "verification_id": vid,
        "path": str(filed) if filed else None,
        "exists": bool(filed and filed.exists()),
        "sets": _sets(filed) if filed and filed.exists() else None,
    }
    if filed and filed.exists():
        from workflow.measurement_pairing import device_came_from_chart
        from workflow.measurement_report import verify_patch_identity
        from workflow.measurement_state import classify
        from workflow.ti3_analysis import parse_ti3
        d = parse_ti3(filed)
        res["filed"]["has_device"] = d.has_device
        res["filed"]["device_from_chart"] = device_came_from_chart(filed)
        res["filed"]["locs_first_5"] = d.sample_locs[:5]
        res["filed"]["state"] = classify(filed, run.verify_chart_ti2).state.value
        res["filed"]["identity"] = verify_patch_identity(d, run.verify_chart_ti2)
        # The report the import exists for must build from it.
        from workflow.measurement_report import build_report
        try:
            rep = build_report(filed)
            res["filed"]["report_patches"] = rep.get("n_patches") or rep.get(
                "patches")
            res["filed"]["report_keys"] = sorted(rep)[:12]
        except Exception as exc:                              # noqa: BLE001
            res["filed"]["report_error"] = f"{type(exc).__name__}: {exc}"
    print(f"    filed: {res['filed']}")

    # ------------------------------------------------------------------ V3 --
    # Press it a SECOND time, on a fresh verification, to show what two
    # presses look like in the log — the reporter's screenshot has two lines.
    print("V3 a SECOND press, to see what two presses look like")
    ctl.set_verification_id("")
    pump(app, 500)
    res["V3_second_press"] = press("V3 second press", MEASUREMENT)
    shot(win, shots / f"{tag}-03-second-press.png", res, "03-second-press")

    (out / f"result-{tag}.json").write_text(json.dumps(res, indent=2),
                                            encoding="utf-8")
    print(f"\nwrote {out / f'result-{tag}.json'}")
    win.close()
    pump(app, 500)
    return 0


def _rows(src: Path):
    text = src.read_text(encoding="utf-8", errors="replace")
    head, rest = text.split("BEGIN_DATA\n", 1)
    body, tail = rest.split("END_DATA", 1)
    return head, [ln for ln in body.splitlines() if ln.strip()], tail


def _write(dst: Path, head: str, rows: "list[str]", tail: str) -> None:
    import re
    head = re.sub(r"NUMBER_OF_SETS\s+\d+", f"NUMBER_OF_SETS\t{len(rows)}", head)
    dst.write_text(head + "BEGIN_DATA\n" + "\n".join(rows) + "\nEND_DATA"
                   + tail, encoding="utf-8")


def _relabel(src: Path, dst: Path, f) -> None:
    """The same readings, under patch names this chart does not have — what a
    measurement of somebody else's chart looks like: the right size, the wrong
    patches."""
    head, rows, tail = _rows(src)
    out = []
    for ln in rows:
        c = ln.split("\t")
        c[1] = f(c[1])
        out.append("\t".join(c))
    _write(dst, head, out, tail)


def _truncate(src: Path, dst: Path, n: int) -> None:
    """The first *n* readings only: a sheet somebody stopped part way down."""
    head, rows, tail = _rows(src)
    _write(dst, head, rows[:n], tail)


def _duplicate_one(src: Path, dst: Path) -> None:
    """The same patch name on two rows, which makes the pairing ambiguous."""
    head, rows, tail = _rows(src)
    c = rows[5].split("\t")
    c[1] = rows[0].split("\t")[1]
    rows = list(rows)
    rows[5] = "\t".join(c)
    _write(dst, head, rows, tail)


if __name__ == "__main__":
    raise SystemExit(main())
