#!/usr/bin/env python3
"""Write and check ``data/printer_paper_profiles.json``: per printer model, the
paper profile (and the other keys) its macOS print dialog writes for each medium
in application colour matching ("Photoshop manages colours").

ChromIQ's direct ``lp`` route sends those keys itself (``workflow/ppd_color.py``).
It reads them from the installed driver first; this file is the fallback and the
test oracle for the models measured on 2026-10-08 (report folders
``2026-10-08_vendor_tests`` and ``2026-10-08_beta15_print_builder``).

Commands (run from the repository root, macOS, with the vendor drivers installed):

  from-drivers [--write]
      Read every listed model's installed PPD and the driver's own table (Canon:
      the media database's <output_icc>; Epson: PDEData.dat EPIJProfileSpec) and
      merge them into the file.  Dialog measurements already in it are kept and
      win.  Without --write it only prints what would change.

  check
      Exit 1 when an installed driver's table differs from the file (what
      tests/test_printer_paper_tables.py asserts, skipped where no driver is).

  measure-dialog MODEL --media V1,V2,... --out DIR
      Drive the model's REAL macOS print dialog once per medium and record what
      it writes.  A capture queue ``ChromIQ_PT_<model>`` is added with the vendor
      PPD whose raster filter is replaced by a pass-through, pointing at a
      discard sink on 127.0.0.1 that this script runs: nothing reaches a
      printer.  The panel is pressed only when its selected printer is that
      capture queue; otherwise Cancel.  The default printer, ~/.cups/lpoptions,
      org.cups.PrintingPrefs and the queue's preset file are backed up first and
      restored afterwards; every system change is logged with its time in
      DIR/system_changes.log.  One result.json per medium in DIR.

  import-measurements DIR [--write]
      Merge the result.json files of measure-dialog runs (or of the vendor-test
      probes, same format) into the file as dialog measurements.

  make-fixtures DIR
      Copy small, trimmed extracts of the installed drivers' files (PPDs, Canon
      media files, Epson PDEData.dat) into DIR, laid out as under
      /Library/Printers, for tests/test_printer_paper_tables.py.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DATA = ROOT / "data" / "printer_paper_profiles.json"
PPD_DIR = Path("/Library/Printers/PPDs/Contents/Resources")

#: the models measured on 2026-10-08: *ModelName -> installed PPD file name
MODELS: dict[str, str] = {
    "Canon PRO-300 series": "CanonIJPRO300series.ppd.gz",
    "Canon PRO-310 series": "CanonIJPRO310series.ppd.gz",
    "Canon PRO-200S series": "CanonIJPRO200Sseries.ppd.gz",
    "Canon PRO-1000 series": "CanonIJPRO1000series.ppd.gz",
    "Canon PRO-1100 series": "CanonIJPRO1100series.ppd.gz",
    "Canon PRO-100 series": "CanonIJPRO100series.ppd.gz",
    "EPSON ET-8550 Series": "EPSON ET-8550 Series.gz",
    "EPSON ET-18100 Series": "EPSON ET-18100 Series.gz",
    "EPSON SC-P700 Series": "EPSON SC-P700 Series.gz",
    "EPSON SC-P900 Series": "EPSON SC-P900 Series.gz",
    "EPSON SC-P5300 Series": "EPSON SC-P5300 Series.gz",
    "EPSON SC-P800 Series": "EPSON SC-P800 Series.gz",
    "EPSON Epson Stylus Photo R2000": "EPSON Epson Stylus Photo R2000.gz",
    "EPSON Epson Stylus Photo R3000": "EPSON Epson Stylus Photo R3000.gz",
}

#: the vendor-test capture queues, for import-measurements of their probes
_VT_QUEUES = {
    "PRO1000": "Canon PRO-1000 series", "PRO1100": "Canon PRO-1100 series",
    "PRO200S": "Canon PRO-200S series", "PRO310": "Canon PRO-310 series",
    "PRO100": "Canon PRO-100 series", "PRO300": "Canon PRO-300 series",
    "ET8550": "EPSON ET-8550 Series", "ET18100": "EPSON ET-18100 Series",
    "P900": "EPSON SC-P900 Series", "P700": "EPSON SC-P700 Series",
    "P5300": "EPSON SC-P5300 Series", "P800": "EPSON SC-P800 Series",
    "R3000": "EPSON Epson Stylus Photo R3000", "R2000": "EPSON Epson Stylus Photo R2000",
}

#: keys a dialog measurement records besides the medium and the profile
_DIALOG_KEYS = {
    "Canon IJ": ("CNIJPrintQuality",),
    "Epson": ("EPIJ_Mode", "EPIJ_CMat", "EPIJ_CCor", "EPIJ_OSColMat", "EPIJ_OSCMProf",
              "EPIJ_HdofClSp"),
}


def read_ppd(path: Path) -> str:
    raw = path.read_bytes()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw.decode("latin-1")


def installed_ppd(model: str) -> str | None:
    p = PPD_DIR / MODELS[model]
    return read_ppd(p) if p.is_file() else None


def load() -> dict:
    try:
        return json.loads(DATA.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"models": {}}


def save(data: dict) -> None:
    data["_about"] = (
        "Per printer model, what its macOS print dialog writes for each medium in "
        "application colour matching: the paper profile (CNIJProfileID / "
        "EPIJProfileSpec) and, where measured, the other keys. 'from': 'driver' = "
        "the installed driver's own table, 'dialog' = measured on the real dialog. "
        "Written by scripts/printer_paper_tables.py; read by workflow/ppd_color.py "
        "after the installed driver's table.")
    DATA.write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def _rule_for(ppd_text: str):
    from workflow import ppd_color as pc
    blocks = {k for k, _l, _v in pc.parse_ppd_options(ppd_text)}
    for rule in pc.PAPER_PROFILE_RULES:
        if rule.media_option in blocks and rule.profile_option in blocks:
            return rule
    return None


def driver_media(ppd_text: str) -> dict[str, dict]:
    """{medium: {"profile", "label", "from": "driver"}} from the driver's table."""
    from workflow import ppd_color as pc
    rule = _rule_for(ppd_text)
    if rule is None:
        return {}
    values = dict(next(v for k, _l, v in pc.parse_ppd_options(ppd_text)
                       if k == rule.profile_option))
    out = {}
    if rule.driver_table == "canon-db":
        by_label = {label: val for val, label in values.items()}
        for mv, icc in pc.canon_driver_table(ppd_text).items():
            if icc in by_label:
                out[mv] = {"profile": by_label[icc], "label": icc, "from": "driver"}
    elif rule.driver_table == "epson-pde":
        for mv, v in pc.epson_driver_table(ppd_text).items():
            if v in values:
                out[mv] = {"profile": v, "label": values[v], "from": "driver"}
    return out


def merge_driver_tables(data: dict) -> list[str]:
    """Bring every installed model's driver table into *data*.  Returns the
    changes, one line each."""
    changes = []
    models = data.setdefault("models", {})
    for model in MODELS:
        text = installed_ppd(model)
        if text is None:
            continue
        rule = _rule_for(text)
        entry = models.setdefault(model, {"vendor": rule.vendor, "media": {}})
        entry["vendor"] = rule.vendor
        entry["ppd"] = MODELS[model]
        media = entry.setdefault("media", {})
        for mv, row in driver_media(text).items():
            old = media.get(mv)
            if old and old.get("from") == "dialog":
                if old.get("profile") != row["profile"]:
                    changes.append(f"CONFLICT {model} medium {mv}: dialog wrote "
                                   f"{old.get('profile')}, driver table says {row['profile']} "
                                   "(dialog kept)")
                continue
            if old != row:
                changes.append(f"{model} medium {mv}: {old and old.get('profile')} -> "
                               f"{row['profile']} ({row['label']})")
                media[mv] = row
    return changes


def check() -> list[str]:
    """Differences between the installed drivers' tables and the file."""
    data = load()
    problems = []
    for model in MODELS:
        text = installed_ppd(model)
        if text is None:
            continue
        built = (data.get("models") or {}).get(model, {}).get("media", {})
        for mv, row in driver_media(text).items():
            have = built.get(mv)
            if have is None or have.get("profile") != row["profile"]:
                problems.append(f"{model} medium {mv}: driver {row['profile']}, file "
                                f"{have and have.get('profile')}")
    return problems


# ---- dialog measurements --------------------------------------------------------

def import_measurements(folder: Path, data: dict) -> list[str]:
    """Merge measure-dialog (or vendor-test) result.json files into *data*."""
    changes = []
    models = data.setdefault("models", {})
    seen: dict[str, dict[str, dict]] = {}
    for f in sorted(folder.glob("*/result.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        keys = r.get("keys") or {}
        if not keys and isinstance(r.get("ticket"), dict):
            keys = r["ticket"]  # the print-fix probes (2026-10-08_print_fix)
        model = r.get("model")
        if not model:
            m = re.match(r"ChromIQ_(?:VT_D|Cap)_(\w+)$", r.get("queue", ""))
            model = _VT_QUEUES.get(m.group(1)) if m else None
        if not model or keys.get("AP_ColorMatchingMode") != "AP_ApplicationColorMatching":
            continue
        if "CNIJMediaType" in keys and "CNIJProfileID" in keys:
            vendor, mv, prof = "Canon IJ", keys["CNIJMediaType"], keys["CNIJProfileID"]
        elif "EPIJ_Medi" in keys and "EPIJProfileSpec" in keys:
            vendor, mv, prof = "Epson", keys["EPIJ_Medi"], keys["EPIJProfileSpec"]
        else:
            continue
        # The medium is the one the dialog WROTE (the SC-P900/P700/P5300 dialogs
        # ignore a preset medium): that is the medium this profile goes with.
        extra = {k: str(keys[k]) for k in _DIALOG_KEYS[vendor] if k in keys}
        seen.setdefault(model, {})[str(mv)] = {
            "profile": str(prof), "from": "dialog", "keys": extra,
            "measured": r.get("measured") or r.get("label", "")}
        models.setdefault(model, {"vendor": vendor, "media": {}})["vendor"] = vendor
    for model, media in seen.items():
        entry = models[model]
        text = installed_ppd(model) if model in MODELS else None
        labels: dict[str, str] = {}
        if text:
            from workflow import ppd_color as pc
            rule = _rule_for(text)
            labels = dict(next((v for k, _l, v in pc.parse_ppd_options(text)
                                if k == rule.profile_option), []))
        rows = entry.setdefault("media", {})
        for mv, row in media.items():
            old = rows.get(mv)
            if old and old.get("from") == "dialog" and old.get("profile") == row["profile"]:
                # a probe that kept fewer keys adds to an earlier one, never
                # takes keys away
                row["keys"] = {**(old.get("keys") or {}), **row["keys"]}
            label = (old or {}).get("label", "") or labels.get(row["profile"], "")
            if label:
                row["label"] = label
            if old != row:
                changes.append(f"{model} medium {mv}: {old and old.get('profile')} -> "
                               f"{row['profile']} (dialog) keys {row['keys']}")
                rows[mv] = row
        if entry["vendor"] == "Epson":
            # The model's keys are what most measured media got; a medium never
            # measured gets those, a measured one keeps its own (full) keys.
            measured = [r["keys"] for r in rows.values() if r.get("from") == "dialog"]
            common = {}
            for k in _DIALOG_KEYS["Epson"]:
                vals = [m[k] for m in measured if k in m]
                if vals:
                    common[k] = max(sorted(set(vals)), key=vals.count)
            entry["dialog_keys"] = common
    return changes


QUEUE_PREFIX = "ChromIQ_PT_"


class _DiscardSink:
    """A socket listener on 127.0.0.1 that reads every job and throws it away."""

    def __init__(self) -> None:
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(4)
        self.port = self.sock.getsockname()[1]
        self.received = 0
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        while True:
            try:
                c, _ = self.sock.accept()
            except OSError:
                return
            with c:
                while True:
                    b = c.recv(1 << 16)
                    if not b:
                        break
                    self.received += len(b)


class _Log:
    def __init__(self, out: Path) -> None:
        self.path = out / "system_changes.log"

    def __call__(self, msg: str) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
        print(msg, flush=True)


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                          encoding="utf-8", errors="replace")


def _capture_ppd(text: str) -> str:
    """The vendor PPD with its command filter gone and its raster/PS filter
    replaced by a pass-through: the job leaves cupsd as CUPS raster."""
    text = re.sub(r'^\*cupsFilter2?:\s*"application/vnd\.cups-command[^"]*"\s*$\n', "",
                  text, flags=re.M)
    text = re.sub(r'^\*cupsFilter2?:\s*"application/vnd\.cups-raster[^"]*"',
                  '*cupsFilter: "application/vnd.cups-raster 0 -"', text, flags=re.M)
    return text


def measure_dialog(model: str, media: list[str], out: Path) -> None:
    """See the module docstring.  macOS only; real windows."""
    if sys.platform != "darwin":
        raise SystemExit("measure-dialog needs macOS and the vendor driver")
    text = installed_ppd(model)
    if text is None:
        raise SystemExit(f"{model}: no installed PPD {MODELS[model]}")
    rule = _rule_for(text)
    out.mkdir(parents=True, exist_ok=True)
    log = _Log(out)
    queue = QUEUE_PREFIX + re.sub(r"[^A-Za-z0-9]", "", model)[:40]
    display = f"ChromIQ PT {model} (capture, no printer)"
    home = Path.home()
    backups = {
        "lpoptions": (home / ".cups" / "lpoptions"),
        "presets": home / "Library" / "Preferences" / f"com.apple.print.custompresets.forprinter.{queue}.plist",
    }
    saved_lpoptions = backups["lpoptions"].read_bytes() if backups["lpoptions"].exists() else None
    prefs_backup = out / "org.cups.PrintingPrefs.backup.plist"
    _run(["defaults", "export", "org.cups.PrintingPrefs", str(prefs_backup)])
    default = (_run(["lpstat", "-d"]).stdout.strip().rsplit(":", 1)[-1].strip())
    log(f"backed up: default printer {default!r}, ~/.cups/lpoptions, org.cups.PrintingPrefs")
    sink = _DiscardSink()
    base_ppd = out / f"{queue}.ppd"
    base_ppd.write_text(_capture_ppd(text), encoding="latin-1")
    r = _run(["lpadmin", "-p", queue, "-E", "-v", f"socket://127.0.0.1:{sink.port}",
              "-P", str(base_ppd), "-D", display])
    log(f"lpadmin -p {queue} (socket://127.0.0.1:{sink.port}, discard sink) rc={r.returncode}")
    try:
        for mv in media:
            ppd = out / f"{queue}_{mv}.ppd"
            ppd.write_text(re.sub(rf"^\*Default{rule.media_option}: .*$",
                                  f"*Default{rule.media_option}: {mv}",
                                  _capture_ppd(text), flags=re.M), encoding="latin-1")
            _run(["lpadmin", "-p", queue, "-P", str(ppd)])
            log(f"lpadmin -p {queue} -P <capture PPD with *Default{rule.media_option}: {mv}>")
            probe = out / f"{model.replace(' ', '_')}_{mv}"
            probe.mkdir(exist_ok=True)
            env = dict(os.environ, CHROMIQ_SETTINGS_FILE=str(out / "probe_settings.ini"))
            res = subprocess.run(
                [sys.executable, __file__, "_probe", queue, display, rule.media_option, mv,
                 str(probe), model], env=env, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=300)
            (probe / "probe.log").write_text(res.stdout + res.stderr, encoding="utf-8")
            print(f"{model} {rule.media_option}={mv}: rc={res.returncode} "
                  f"{(res.stdout.strip().splitlines() or [''])[-1][:300]}", flush=True)
    finally:
        _run(["lpadmin", "-x", queue])
        log(f"lpadmin -x {queue} (capture queue removed)")
        if default:
            _run(["lpadmin", "-d", default])
            log(f"lpadmin -d {default} (default printer restored)")
        if saved_lpoptions is not None:
            backups["lpoptions"].write_bytes(saved_lpoptions)
            log("~/.cups/lpoptions restored from the backup")
        _run(["defaults", "import", "org.cups.PrintingPrefs", str(prefs_backup)])
        log("org.cups.PrintingPrefs restored from the backup")
        if backups["presets"].exists():
            backups["presets"].unlink()
            log(f"removed {backups['presets'].name} (macOS made it for the capture queue)")
        sink.sock.close()


def _probe(queue: str, display: str, media_option: str, mv: str, out: Path,
           model: str) -> None:
    """One medium: the real print panel with the vendor PDE, driven in-process."""
    import cups
    if _PanelDriver is None:  # never open a print panel nothing will answer
        raise SystemExit("PyObjC panel driver unavailable")
    out = Path(out)
    conn = cups.Connection()
    info = conn.getPrinters()[queue]
    assert queue.startswith(QUEUE_PREFIX), "SAFETY: not a capture queue"
    assert info["device-uri"].startswith("socket://127.0.0.1:"), "SAFETY: not the sink"
    sys.path.insert(0, str(ROOT / "scripts"))
    from capture_screens import build_app
    app = build_app()
    from PyQt6.QtWidgets import QLabel
    lbl = QLabel(f"ChromIQ paper-profile table: {model}, {media_option}={mv}\n"
                 "(the macOS print panel is driven automatically)")
    lbl.resize(560, 80)
    lbl.show()
    app._chromiq_focus_give_back.give_back()
    import AppKit
    driver = _PanelDriver.alloc().initWithPrinter_out_(display, out).start()
    from workflow import native_print_macos as npm
    chart = out / "chart.tif"
    _make_chart(chart)
    before = set(conn.getJobs(which_jobs="all", my_jobs=True))
    AppKit.NSPrintInfo.sharedPrintInfo().setPrinter_(AppKit.NSPrinter.printerWithName_(display))
    AppKit.NSPrintInfo.sharedPrintInfo().printSettings().setObject_forKey_(mv, media_option)
    res = {"model": model, "queue": queue, "media": f"{media_option}={mv}",
           "measured": time.strftime("%Y-%m-%d")}
    try:
        res["submitted"] = bool(npm.print_frames([(chart, 0)]))
    except Exception as exc:  # noqa: BLE001
        res["submitted"] = f"EXC {type(exc).__name__}: {exc}"
    t0 = time.time()
    new: list[int] = []
    while res["submitted"] is True and time.time() - t0 < 120:
        new = [j for j in sorted(set(conn.getJobs(which_jobs="all", my_jobs=True)) - before)
               if conn.getJobAttributes(j)["job-printer-uri"].endswith("/" + queue)]
        if new and all(conn.getJobAttributes(j)["job-state"] >= 7 for j in new):
            break
        time.sleep(1)
    for j in sorted(set(conn.getJobs(which_jobs="all", my_jobs=True)) - before):
        assert conn.getJobAttributes(j)["job-printer-uri"].endswith("/" + queue), \
            "SAFETY: a job went to another queue"
    if new:
        a = conn.getJobAttributes(new[-1])
        res["job"] = new[-1]
        res["keys"] = {k: str(v) for k, v in a.items()
                       if k.startswith(("AP_", "CNIJ", "EPIJ"))}
    res["panel"] = driver.events
    (out / "result.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    k = res.get("keys", {})
    print("RESULT", json.dumps({x: k.get(x) for x in (
        "CNIJMediaType", "CNIJProfileID", "CNIJPrintQuality", "EPIJ_Medi",
        "EPIJProfileSpec", "EPIJ_Mode", "EPIJ_CCor")}), flush=True)
    os._exit(0)


def _make_chart(path: Path) -> None:
    import numpy as np
    import tifffile
    a = np.full((240, 360, 3), 255, np.uint8)
    for i, c in enumerate([(255, 0, 0), (0, 255, 0), (0, 0, 255), (0, 0, 0), (128, 128, 128),
                           (30, 200, 90)]):
        a[60:180, 20 + i * 55:70 + i * 55] = c
    tifffile.imwrite(str(path), a, photometric="rgb", resolution=(300, 300),
                     resolutionunit="INCH")


try:  # the panel driver needs PyObjC (macOS)
    import AppKit as _AppKit
    import Foundation as _Foundation
    import Quartz as _Quartz
    import objc as _objc

    def _find(view, pred, acc=None):
        acc = [] if acc is None else acc
        try:
            if pred(view):
                acc.append(view)
            for sub in view.subviews():
                _find(sub, pred, acc)
        except Exception:  # noqa: BLE001
            pass
        return acc

    def _buttons(view, titles):
        return _find(view, lambda v: isinstance(v, _AppKit.NSButton)
                     and str(v.title()) in titles)

    def _snap(out, win, name):
        """Photograph *win* itself (its own buffer, not the screen)."""
        img = _Quartz.CGWindowListCreateImage(
            _Quartz.CGRectNull, _Quartz.kCGWindowListOptionIncludingWindow,
            win.windowNumber(), _Quartz.kCGWindowImageBoundsIgnoreFraming)
        if img is None:
            return
        url = _Foundation.NSURL.fileURLWithPath_(str(out / name))
        dest = _Quartz.CGImageDestinationCreateWithURL(url, "public.png", 1, None)
        _Quartz.CGImageDestinationAddImage(dest, img, None)
        _Quartz.CGImageDestinationFinalize(dest)

    class _PanelDriver(_Foundation.NSObject):
        """Presses Print in the macOS print panel only when the selected printer
        is the capture queue (else Cancel); answers any alert or sheet with its
        safe button.  Runs on a timer in this process: no keyboard, no other
        application touched."""

        def initWithPrinter_out_(self, printer, out):  # noqa: N802
            self = _objc.super(_PanelDriver, self).init()
            self.printer, self.out = printer, Path(out)
            self.events, self.pressed, self.t0, self.chosen = [], set(), None, False
            return self

        def start(self):
            t = _Foundation.NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(
                0.3, self, "tick:", None, True)
            rl = _Foundation.NSRunLoop.mainRunLoop()
            for mode in (_Foundation.NSRunLoopCommonModes, _AppKit.NSModalPanelRunLoopMode,
                         _AppKit.NSEventTrackingRunLoopMode):
                rl.addTimer_forMode_(t, mode)
            self._timer = t
            return self

        def tick_(self, _timer):  # noqa: N802
            print_btn, cancel_btn = ("Drucken", "Print"), ("Abbrechen", "Cancel")
            for w in _AppKit.NSApp.windows():
                if not (w.isVisible() and w.contentView()):
                    continue
                is_panel = bool(_buttons(w.contentView(), print_btn))
                sheet = w.attachedSheet()
                # the print progress window is the job itself: never answer it
                target = sheet if (is_panel and sheet is not None) else (
                    None if is_panel or "QNS" in str(w.className())
                    or "Progress" in str(w.className()) else w)
                if target is not None and target.contentView() is not None:
                    for title in ("Abbrechen", "Cancel", "OK", "Schließen", "Close"):
                        b = _buttons(target.contentView(), (title,))
                        if b and target.windowNumber() not in self.pressed:
                            _snap(self.out, target, f"alert_{len(self.events) + 1}.png")
                            self.events.append({"alert": str(target.className()),
                                                "answered": title})
                            self.pressed.add(target.windowNumber())
                            b[0].performClick_(None)
                            return
                if not is_panel or w.windowNumber() in self.pressed:
                    continue
                if self.t0 is None:
                    self.t0 = time.time()
                    return
                if time.time() - self.t0 < 2.5:  # let the vendor extension load
                    return
                pops = _find(w.contentView(),
                                  lambda v: isinstance(v, _AppKit.NSPopUpButton))
                if not self.chosen:
                    for p in pops:
                        if self.printer in [str(x) for x in p.itemTitles()]:
                            if str(p.titleOfSelectedItem()) != self.printer:
                                p.selectItemWithTitle_(self.printer)
                                p.sendAction_to_(p.action(), p.target())
                                self.t0 = time.time()
                            self.chosen = True
                            return
                selected = [str(p.titleOfSelectedItem()) for p in pops
                            if p.titleOfSelectedItem()]
                ok = self.printer in selected and "(capture, no printer)" in self.printer
                _snap(self.out, w, "panel.png")
                self.events.append({"panel": selected, "pressed": "Print" if ok else "Cancel"})
                self.pressed.add(w.windowNumber())
                b = _buttons(w.contentView(), print_btn if ok else cancel_btn)
                if b:
                    b[0].performClick_(None)
                return
except Exception:  # pragma: no cover - not macOS
    _PanelDriver = None  # type: ignore[assignment]


#: what make-fixtures copies: model -> media to keep (Canon media files)
FIXTURE_MODELS = {
    "Canon PRO-300 series": ("0", "51", "63", "28", "165", "162"),
    "Canon PRO-1000 series": ("0", "28", "51", "78", "17448", "63"),
    "Canon PRO-100 series": (),
    "EPSON ET-8550 Series": (),
    "EPSON SC-P900 Series": (),
    "EPSON Epson Stylus Photo R3000": (),
}
_KEEP_OPTIONS = ("CNIJMediaType", "CNIJProfileID", "CNIJPrintQuality", "CNIJIntent2",
                 "EPIJ_Medi", "EPIJProfileSpec", "EPIJ_Qual", "EPIJ_Mode", "EPIJ_CMat",
                 "EPIJ_CCor", "EPIJ_OSColMat", "EPIJ_OSCMProf", "EPIJ_HdofClSp", "EPIJ_Ink_")


def trim_ppd(text: str) -> str:
    """The lines of a vendor PPD that ``ppd_color`` reads, nothing else."""
    keep, inside = [], None
    head = ("*PPD-Adobe", "*ModelName", "*NickName", "*CNIJNameTblPath",
            "*EPIJMachineBundleName", "*cupsICCProfile", "*cupsICCQualifier",
            "*CNIJMediaTypeIVEC")
    for line in text.splitlines():
        m = re.match(r"^\*OpenUI\s+\*(\w+)", line)
        if m:
            inside = m.group(1) if m.group(1) in _KEEP_OPTIONS else None
        if inside:
            if (line.startswith(("*OpenUI", "*CloseUI", f"*Default{inside}:"))
                    or re.match(rf"^\*{inside}\s", line)):
                keep.append(line.split('"')[0] + '""' if re.match(rf"^\*{inside}\s", line)
                            else line)
            if line.startswith("*CloseUI"):
                inside = None
            continue
        if line.startswith(head) or any(line.startswith(f"*Default{k}:") for k in _KEEP_OPTIONS):
            keep.append(line)
    return "\n".join(keep) + "\n"


def make_fixtures(dest: Path) -> list[str]:
    from workflow import ppd_color as pc
    written = []
    for model, media in FIXTURE_MODELS.items():
        text = installed_ppd(model)
        if text is None:
            continue
        name = re.sub(r"[^A-Za-z0-9]+", "_", model).strip("_") + ".ppd"
        (dest / "PPDs").mkdir(parents=True, exist_ok=True)
        (dest / "PPDs" / name).write_text(trim_ppd(text), encoding="latin-1")
        written.append(f"PPDs/{name}")
        db = pc.canon_media_database(text)
        if db is not None and media:
            rel = db.relative_to(pc.MAC_DRIVER_ROOT)
            ivec = dict(re.findall(r'^\*CNIJMediaTypeIVEC\s+(\S+):\s*'
                                   r'"custom-media-type-canon-([0-9A-Fa-f-]+)"', text, re.M))
            for mv in media:
                src = db / f"{ivec.get(mv, '')}.hmi"
                if not src.is_file():
                    continue
                x = src.read_text(encoding="utf-8", errors="replace")
                cm = re.search(r'<printcolormode type="color">.*?</printcolormode>', x, re.S)
                out = dest / rel / src.name
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<medium>'
                               f'{cm.group(0) if cm else ""}</medium>\n', encoding="utf-8")
                written.append(str(rel / src.name))
        pde = pc.epson_pde_path(text)
        if pde is not None and pde.is_file():
            t = pde.read_text(encoding="latin-1")
            ui = re.search(r'^\*EPIJUIType:.*$', t, re.M)
            blk = re.search(r'^\*EPIJConditionValue EPIJProfileSpec/:\s*".*?"', t, re.S | re.M)
            rel = pde.relative_to(pc.MAC_DRIVER_ROOT)
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text((ui.group(0) if ui else "") + "\n\n" + (blk.group(0) if blk else "")
                           + "\n", encoding="latin-1")
            written.append(str(rel))
    return written


def main(argv: list[str]) -> int:
    if argv[:1] == ["_probe"]:
        _probe(argv[1], argv[2], argv[3], argv[4], Path(argv[5]), argv[6])
        return 0
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("from-drivers")
    a.add_argument("--write", action="store_true")
    sub.add_parser("check")
    m = sub.add_parser("measure-dialog")
    m.add_argument("model", choices=sorted(MODELS))
    m.add_argument("--media", required=True)
    m.add_argument("--out", required=True, type=Path)
    f = sub.add_parser("make-fixtures")
    f.add_argument("folder", type=Path)
    i = sub.add_parser("import-measurements")
    i.add_argument("folder", type=Path)
    i.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "check":
        problems = check()
        print("\n".join(problems) or "the installed drivers agree with the file")
        return 1 if problems else 0
    if args.cmd == "make-fixtures":
        print("\n".join(make_fixtures(args.folder)))
        return 0
    if args.cmd == "measure-dialog":
        measure_dialog(args.model, [x for x in args.media.split(",") if x], args.out)
        return 0
    data = load()
    changes = (merge_driver_tables(data) if args.cmd == "from-drivers"
               else import_measurements(args.folder, data))
    print("\n".join(changes) or "no change")
    if args.write and changes:
        save(data)
        print(f"written: {DATA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
