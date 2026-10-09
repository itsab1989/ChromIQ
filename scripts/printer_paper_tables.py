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
    # beta 16 (report folder 2026-10-09_vendor_tests2): the second round of drivers
    "Canon iP8700 series": "CanonIJiP8700series.ppd.gz",
    "Canon iX6800 series": "CanonIJiX6800series.ppd.gz",
    "Canon PRO-10S series": "CanonIJPRO10Sseries.ppd.gz",
    "Canon PRO-2100": "CanonIJPRO2100.ppd.gz",
    "Canon PRO-4100": "CanonIJPRO4100.ppd.gz",
    "Canon PRO-2600": "CanonIJPRO2600.ppd.gz",
    "EPSON XP-8700 Series": "EPSON XP-8700 Series.gz",
    "EPSON XP-15000 Series": "EPSON XP-15000 Series.gz",
    "EPSON XP-970 Series": "EPSON XP-970 Series.gz",
    "EPSON XP-8600 Series": "EPSON XP-8600 Series.gz",
    "EPSON SC-P400 Series": "EPSON SC-P400 Series.gz",
    "EPSON SC-P600 Series": "EPSON SC-P600 Series.gz",
    "EPSON SC-P6000 Series": "EPSON SC-P6000 Series.gz",
    "EPSON SC-P7000 Series": "EPSON SC-P7000 Series.gz",
    "EPSON SC-P8000 Series": "EPSON SC-P8000 Series.gz",
    "EPSON SC-P9000 Series": "EPSON SC-P9000 Series.gz",
    "EPSON Stylus Photo 1400": "EPSON Stylus Photo 1400.gz",
    "EPSON Stylus Photo 1390": "EPSON Stylus Photo 1390.gz",
    "EPSON Stylus Photo R1900": "EPSON Stylus Photo R1900.gz",
    "EPSON Stylus Photo R2880": "EPSON Stylus Photo R2880.gz",
    "EPSON Stylus Photo R2400": "EPSON Stylus Photo R2400.gz",
    "EPSON Stylus Photo R1800": "EPSON Stylus Photo R1800.gz",
    "EPSON Stylus Photo 2200": "EPSON Stylus Photo 2200.gz",
    "EPSON Epson Stylus Pro 3880": "EPSON Epson Stylus Pro 3880.gz",
    "EPSON Stylus Pro 3800": "EPSON Stylus Pro 3800.gz",
    "EPSON L1800 Series": "EPSON L1800 Series.gz",
    "EPSON L800": "EPSON L800.gz",
    "EPSON L805 Series": "EPSON L805 Series.gz",
    "EPSON L810 Series": "EPSON L810 Series.gz",
    "EPSON L850 Series": "EPSON L850 Series.gz",
}

#: models whose dialogs were measured but which have no paper profiles to
#: choose (no EPIJProfileSpec/CNIJProfileID): the PictureMates keep the driver's
#: own colour mode, the DNP dye-subs have no option for it at all.  measure-dialog
#: records their whole ticket; nothing goes into the tables.
NO_PROFILE_MODELS: dict[str, str] = {
    "EPSON PM-400 Series": "EPSON PM-400 Series.gz",
    "EPSON PM-520 Series": "EPSON PM-520 Series.gz",
    "Dai Nippon Printing DP-DS620": "DNP-DS620.ppd.gz",
    "Dai Nippon Printing DP-DS820": "DNP-DS820.ppd.gz",
    "Dai Nippon Printing DP-QW410": "DNP-QW410.ppd.gz",
    "Dai Nippon Printing DS-RX1": "DNP-DS-RX1.ppd.gz",
    "Dai Nippon Printing DS40": "DNP-DS40.ppd.gz",
    "Dai Nippon Printing DS80": "DNP-DS80.ppd.gz",
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
    "Canon IJ": ("CNIJPrintQuality", "CNIJMediaSupply", "Resolution"),
    "Epson": ("EPIJ_Mode", "EPIJ_CMat", "EPIJ_CCor", "EPIJ_OSColMat", "EPIJ_OSCMProf",
              "EPIJ_HdofClSp", "EPIJ_Qual", "EPIJ_APri", "EPIJ_MeInSeNm", "EPIJ_MdGropID",
              "Resolution", "MediaType"),
}


def read_ppd(path: Path) -> str:
    raw = path.read_bytes()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw.decode("latin-1")


def installed_ppd(model: str) -> str | None:
    name = MODELS.get(model) or NO_PROFILE_MODELS.get(model)
    if name is None:
        return None
    p = PPD_DIR / name
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
        if isinstance(r.get("ticket"), dict):
            # the whole ticket (beta 16 probes; the print-fix probes kept only
            # it): Resolution and MediaType are not EPIJ/CNIJ keys
            keys = {**r["ticket"], **keys}
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
        if vendor == "Epson" and model in MODELS and "EPIJ_Qual" in extra:
            # Beta 16: a probe opens the dialog with the medium already chosen,
            # so the dialog's medium link never fires and it keeps the PPD's
            # default quality where the medium allows it (SC-P400 Archival
            # Matte: 49, where a user who picks the paper gets 46).  Such a
            # quality is not the dialog's choice for the paper: left out.
            text = installed_ppd(model)
            if text is not None:
                from workflow import ppd_color as pc
                emu = pc.epson_dialog_keys(text, str(mv)).get("EPIJ_Qual")
                if emu is not None and emu != extra["EPIJ_Qual"] \
                        and extra["EPIJ_Qual"] == pc._ppd_default(text, "EPIJ_Qual"):
                    extra.pop("EPIJ_Qual")
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
            for k in ("EPIJ_Mode", "EPIJ_CMat", "EPIJ_OSColMat", "EPIJ_OSCMProf",
                      "EPIJ_HdofClSp"):   # per medium: quality, CCor, black ink
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


def _with_defaults(text: str, presets: dict[str, str]) -> str:
    """*text* with ``*Default<key>`` set to each preset value it offers."""
    for k, v in presets.items():
        text = re.sub(rf"^\*Default{re.escape(k)}: .*$", f"*Default{k}: {v}", text, flags=re.M)
    return text


def measure_dialog(model: str, media: list[str], out: Path,
                   presets: dict[str, str] | None = None) -> None:
    """See the module docstring.  macOS only; real windows.

    *media* ``["none"]`` measures a model without a media option the tables
    know (DNP, PictureMate: ``NO_PROFILE_MODELS``) at its defaults.  *presets*
    (``--set KEY=VALUE,...``) are put into the PPD defaults and the print
    settings as well, to see what the dialog does with them (beta 16: which
    qualities a medium allows)."""
    if sys.platform != "darwin":
        raise SystemExit("measure-dialog needs macOS and the vendor driver")
    presets = dict(presets or {})
    text = installed_ppd(model)
    if text is None:
        raise SystemExit(f"{model}: no installed PPD")
    rule = _rule_for(text)
    media_option = rule.media_option if rule is not None else next(
        (k for k in ("EPIJ_Medi", "CNIJMediaType") if f"*OpenUI *{k}/" in text), "none")
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
    tag = "".join(f"_{k.strip('_')}{v}" for k, v in sorted(presets.items()))
    try:
        for mv in media:
            want = dict(presets)
            if media_option != "none" and mv != "none":
                want[media_option] = mv
            ppd = out / f"{queue}_{mv}{tag}.ppd"
            ppd.write_text(_with_defaults(_capture_ppd(text), want), encoding="latin-1")
            _run(["lpadmin", "-p", queue, "-P", str(ppd)])
            log(f"lpadmin -p {queue} -P <capture PPD with defaults {want}>")
            probe = out / f"{model.replace(' ', '_')}_{mv}{tag}"
            probe.mkdir(exist_ok=True)
            env = dict(os.environ, CHROMIQ_SETTINGS_FILE=str(out / "probe_settings.ini"))
            res = _run_probe_guarded(
                [sys.executable, __file__, "_probe", queue, display, media_option, mv,
                 str(probe), model, json.dumps(presets)], env, probe, log)
            (probe / "probe.log").write_text(res.stdout + res.stderr, encoding="utf-8")
            print(f"{model} {media_option}={mv}{tag}: rc={res.returncode} "
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


#: The sheet watcher (beta 16).  Vendor drivers raise their own alerts over the
#: print panel; the Canon PRO-2100's "The margin settings of the custom paper
#: size are less than the supported minimum values ... Click [OK] to start
#: printing." is one, and the in-process timer never sees it.  System Events
#: reaches every window of the probe's process by its pid, and AXPress presses a
#: button without the mouse and without taking focus.  OK (the default) is
#: pressed only when the panel's printer is a capture queue; otherwise Cancel.
_AX_JXA = r"""
function run(argv) {
  var pid = parseInt(argv[0]), act = argv[1] || '';
  var se = Application('System Events');
  var ps = se.processes.whose({unixId: pid});
  if (ps.length === 0) return JSON.stringify({gone: true});
  var p = ps[0];
  function g(e, f) { try { var v = e[f](); return v === null || v === undefined ? '' : String(v); } catch (x) { return ''; } }
  var popups = [], dialogs = [];
  function walk(e, d, acc) {
    var role = g(e, 'role');
    if (role === 'AXPopUpButton') popups.push(g(e, 'value'));
    if (role === 'AXStaticText' || role === 'AXTextField') { var t = g(e, 'value') || g(e, 'name'); if (t) acc.texts.push(t); }
    if (role === 'AXButton') acc.buttons.push(e);
    if (d > 9) return;
    var kids; try { kids = e.uiElements(); } catch (x) { return; }
    for (var i = 0; i < kids.length; i++) {
      var r = g(kids[i], 'role');
      if (r === 'AXSheet') { var s = {texts: [], buttons: []}; walk(kids[i], 0, s); dialogs.push(s); }
      else walk(kids[i], d + 1, acc);
    }
  }
  var ws = p.windows(), found = [];
  for (var w = 0; w < ws.length; w++) {
    var acc = {texts: [], buttons: []};
    walk(ws[w], 0, acc);
    var names = acc.buttons.map(function (b) { return g(b, 'name'); });
    var isPanel = names.indexOf('Drucken') >= 0 || names.indexOf('Print') >= 0;
    if (!isPanel && acc.buttons.length > 0 && acc.texts.length > 0) dialogs.push(acc);
  }
  var out = {popups: popups, dialogs: []};
  for (var k = 0; k < dialogs.length; k++) {
    var dg = dialogs[k], bn = dg.buttons.map(function (b) { return g(b, 'name'); });
    var rec = {texts: dg.texts, buttons: bn, pressed: ''};
    if (act) {
      var want = act === 'ok' ? ['OK', 'Drucken', 'Print', 'Fortfahren', 'Continue'] : ['Abbrechen', 'Cancel', 'OK'];
      for (var j = 0; j < want.length && !rec.pressed; j++) {
        var at = bn.indexOf(want[j]);
        if (at >= 0) { try { dg.buttons[at].actions['AXPress'].perform(); rec.pressed = want[j]; } catch (x) { rec.error = String(x); } }
      }
    }
    out.dialogs.push(rec);
  }
  return JSON.stringify(out);
}
"""


class _SheetWatcher(threading.Thread):
    """Answers every vendor alert or sheet the probe *pid* shows, within about a
    second: OK when its panel's printer is a capture queue (``CAPTURE_MARK``
    in the panel's printer popup), Cancel otherwise.  Every answer is logged."""

    CAPTURE_MARK = "(capture, no printer)"

    def __init__(self, pid: int, out: Path, log) -> None:
        super().__init__(daemon=True)
        self.pid, self.out, self.log = pid, out, log
        self.answered: list[dict] = []
        self.stop = threading.Event()
        self.script = out / "_sheet_watch.js"
        self.script.write_text(_AX_JXA, encoding="utf-8")

    def _ask(self, act: str = "") -> dict:
        r = subprocess.run(["osascript", "-l", "JavaScript", str(self.script), str(self.pid), act],
                           capture_output=True, text=True, timeout=20)
        try:
            return json.loads(r.stdout.strip() or "{}")
        except ValueError:
            return {"error": r.stderr.strip()[:300]}

    def run(self) -> None:
        first = None
        while not self.stop.is_set():
            seen = self._ask()
            if seen.get("gone"):
                return
            # the panel driver inside the probe answers first; this is the
            # backstop for a window it has not answered within 3 s
            first = (first or time.time()) if seen.get("dialogs") else None
            if first is not None and time.time() - first >= 3:
                shots = _photograph_windows_of(self.pid, self.out)
                capture = any(self.CAPTURE_MARK in p for p in seen.get("popups", []))
                done = self._ask("ok" if capture else "cancel")
                for d in done.get("dialogs", []):
                    if not d.get("pressed"):
                        continue
                    d.update(capture_queue=capture, shots=shots, at=time.strftime("%H:%M:%S"))
                    self.answered.append(d)
                    self.log(f"sheet answered '{d['pressed']}' (printer is "
                             f"{'a capture queue' if capture else 'NOT a capture queue'}): "
                             f"{' | '.join(d.get('texts', []))[:400]}")
            self.stop.wait(0.4)


#: a probe normally ends within 15 s; one still running after this is held by
#: a window nobody answers (2026-10-09: the Canon PRO-2100 driver's own
#: app-modal "margin settings of the custom paper size" alert, which the
#: in-process timer never saw).  It is photographed and ended: nothing is
#: released to the queue, and no window is left waiting for a person.
PROBE_GUARD_S = 30


def _run_probe_guarded(cmd: list[str], env: dict, probe: Path, log) -> subprocess.CompletedProcess:
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace")
    watcher = _SheetWatcher(proc.pid, probe, log)
    watcher.start()
    marker = probe / "REMOTE_ALERT"
    marker.unlink(missing_ok=True)
    t0 = time.time()
    while proc.poll() is None and time.time() - t0 < PROBE_GUARD_S:
        if marker.exists():
            time.sleep(0.3)   # let the photograph finish
            shots = _photograph_windows_of(proc.pid, probe)
            proc.kill()
            out, err = proc.communicate()
            watcher.stop.set()
            log(f"probe pid {proc.pid}: the driver raised its own alert "
                f"({marker.read_text(encoding='utf-8')}), which no program can answer; "
                f"photographed ({', '.join(shots)}) and the probe ended at once, "
                "no job released")
            return subprocess.CompletedProcess(cmd, -15, out, err + "\nREMOTE VENDOR ALERT")
        time.sleep(0.15)
    try:
        out, err = proc.communicate(timeout=0.1 if proc.poll() is not None else 0.01)
        watcher.stop.set()
        if watcher.answered:
            (probe / "sheets.json").write_text(json.dumps(watcher.answered, indent=1),
                                               encoding="utf-8")
        return subprocess.CompletedProcess(cmd, proc.returncode, out, err)
    except subprocess.TimeoutExpired:
        watcher.stop.set()
        shots = _photograph_windows_of(proc.pid, probe)
        proc.kill()
        out, err = proc.communicate()
        log(f"probe pid {proc.pid} still open after {PROBE_GUARD_S} s: a window nobody "
            f"answered; photographed ({', '.join(shots) or 'nothing'}) and ended, "
            "no job released")
        return subprocess.CompletedProcess(cmd, -9, out, err + "\nUNANSWERED WINDOW: "
                                           + ", ".join(shots))


def _photograph_windows_of(pid: int, out: Path) -> list[str]:
    """Every on-screen window of *pid*, from its own buffer (no focus taken)."""
    names = []
    try:
        for w in _Quartz.CGWindowListCopyWindowInfo(_Quartz.kCGWindowListOptionAll,
                                                    _Quartz.kCGNullWindowID):
            if w.get("kCGWindowOwnerPID") != pid or w.get("kCGWindowLayer", 1) != 0:
                continue
            wid = w["kCGWindowNumber"]
            img = _Quartz.CGWindowListCreateImage(
                _Quartz.CGRectNull, _Quartz.kCGWindowListOptionIncludingWindow, wid,
                _Quartz.kCGWindowImageBoundsIgnoreFraming)
            if img is None:
                continue
            path = out / f"unanswered_{wid}.png"
            dest = _Quartz.CGImageDestinationCreateWithURL(
                _Foundation.NSURL.fileURLWithPath_(str(path)), "public.png", 1, None)
            _Quartz.CGImageDestinationAddImage(dest, img, None)
            _Quartz.CGImageDestinationFinalize(dest)
            names.append(path.name)
    except Exception:  # noqa: BLE001 - not macOS, or no window server
        pass
    return names


_TICKET_SKIP = ("job-", "time-at-", "date-time-", "number-of-", "document-", "printer-",
                "attributes-", "compression", "time-", "date-")


def _probe(queue: str, display: str, media_option: str, mv: str, out: Path,
           model: str, presets_json: str = "{}") -> None:
    """One medium: the real print panel with the vendor PDE, driven in-process."""
    import cups
    if _PanelDriver is None:  # never open a print panel nothing will answer
        raise SystemExit("PyObjC panel driver unavailable")
    out = Path(out)
    presets = json.loads(presets_json or "{}")
    chart_mm = presets.pop("_chart_mm", "")
    conn = cups.Connection()
    info = conn.getPrinters()[queue]
    assert queue.startswith(QUEUE_PREFIX), "SAFETY: not a capture queue"
    assert info["device-uri"].startswith("socket://127.0.0.1:"), "SAFETY: not the sink"
    sys.path.insert(0, str(ROOT / "scripts"))
    from capture_screens import build_app
    app = build_app()
    from PyQt6.QtWidgets import QLabel
    lbl = QLabel(f"ChromIQ paper-profile table: {model}, {media_option}={mv} {presets}\n"
                 "(the macOS print panel is driven automatically)")
    lbl.resize(560, 80)
    lbl.show()
    app._chromiq_focus_give_back.give_back()
    import AppKit
    driver = _PanelDriver.alloc().initWithPrinter_out_(display, out).start()
    from workflow import native_print_macos as npm
    chart = out / "chart.tif"
    _make_chart(chart, chart_mm)
    before = set(conn.getJobs(which_jobs="all", my_jobs=True))
    AppKit.NSPrintInfo.sharedPrintInfo().setPrinter_(AppKit.NSPrinter.printerWithName_(display))
    settings = AppKit.NSPrintInfo.sharedPrintInfo().printSettings()
    if media_option != "none" and mv != "none":
        settings.setObject_forKey_(mv, media_option)
    for k, v in presets.items():
        settings.setObject_forKey_(v, k)
    res = {"model": model, "queue": queue, "media": f"{media_option}={mv}",
           "presets": presets, "measured": time.strftime("%Y-%m-%d")}
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
        res["ticket"] = {k: str(v) for k, v in a.items() if not k.startswith(_TICKET_SKIP)}
    res["panel"] = driver.events
    (out / "result.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    k = res.get("keys", {})
    print("RESULT", json.dumps({x: k.get(x) for x in (
        "CNIJMediaType", "CNIJProfileID", "CNIJPrintQuality", "CNIJMediaSupply", "EPIJ_Medi",
        "EPIJProfileSpec", "EPIJ_Qual", "EPIJ_Mode", "EPIJ_CCor", "EPIJ_MeInSeNm")}),
        flush=True)
    os._exit(0)


def _make_chart(path: Path, size_mm: str = "") -> None:
    """An A4 page at 300 dpi, as ChromIQ's own charts are.  Beta 16: the first
    probes printed a 30 x 20 mm page, a custom paper size with no margins, and
    the imagePROGRAF PRO-2100 driver stops every such job with its own alert
    ("The margin settings of the custom paper size are less than the supported
    minimum values")."""
    import numpy as np
    import tifffile
    if size_mm:   # e.g. "120x120", the disc tray's page (``--set _chart_mm=120x120``)
        w_mm, h_mm = (float(x) for x in size_mm.lower().split("x"))
        w, h = round(w_mm / 25.4 * 300), round(h_mm / 25.4 * 300)
    else:
        w, h = 2480, 3508
    a = np.full((h, w, 3), 255, np.uint8)
    step = max(w // 9, 20)
    for i, c in enumerate([(255, 0, 0), (0, 255, 0), (0, 0, 255), (0, 0, 0), (128, 128, 128),
                           (30, 200, 90)]):
        a[h // 2 - step // 2:h // 2 + step // 2, step + i * step:step + i * step + step * 4 // 5] = c
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

    def _press(button):
        """Click *button* from the run loop, not from inside this timer: a
        vendor extension can raise an alert inside the click (PrintingUI waits
        for it in a nested loop), and a timer whose callback is still running
        would never fire again to answer it (2026-10-09, Canon PRO-2100)."""
        button.performSelector_withObject_afterDelay_inModes_(
            "performClick:", None, 0.05,
            [_Foundation.NSDefaultRunLoopMode, _AppKit.NSModalPanelRunLoopMode,
             _AppKit.NSEventTrackingRunLoopMode])

    class _PanelDriver(_Foundation.NSObject):
        """Presses Print in the macOS print panel only when the selected printer
        is the capture queue (else Cancel); answers any alert or sheet with its
        safe button.  Runs on a timer in this process: no keyboard, no other
        application touched."""

        def initWithPrinter_out_(self, printer, out):  # noqa: N802
            self = _objc.super(_PanelDriver, self).init()
            self.printer, self.out = printer, Path(out)
            self.events, self.pressed, self.t0, self.chosen = [], set(), None, False
            self.printed_to_capture = False
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
                # A vendor alert drawn by the driver's extension service
                # (ViewBridge): no button of it lives in this process, and the
                # main thread blocks on it right after this tick.  Say so at
                # once; the parent ends the probe within half a second.
                if "ViewBridge" in str(w.className()) and w.isVisible() \
                        and not (self.out / "REMOTE_ALERT").exists():
                    _snap(self.out, w, "remote_alert.png")
                    (self.out / "REMOTE_ALERT").write_text(
                        time.strftime("%H:%M:%S ") + str(w.className()), encoding="utf-8")
            if os.environ.get("CHROMIQ_PANEL_DIAG"):
                with open(self.out / "panel_diag.log", "a", encoding="utf-8") as f:
                    f.write(time.strftime("%H:%M:%S ") + repr([
                        (str(w.className()), str(w.title()), bool(w.isVisible()),
                         w.windowNumber()) for w in _AppKit.NSApp.windows()])
                        + f" modal={_AppKit.NSApp.modalWindow()}\n")
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
                    # Beta 16: a vendor alert after Print (the Canon PRO-2100's
                    # "margin settings of the custom paper size" one) is answered
                    # with its default button only when Print went to the
                    # capture queue; anything else is cancelled.
                    order = (("OK", "Drucken", "Print", "Fortfahren", "Continue")
                             if self.printed_to_capture else ())
                    order += ("Abbrechen", "Cancel", "OK", "Schließen", "Close")
                    for title in order:
                        b = _buttons(target.contentView(), (title,))
                        if b and target.windowNumber() not in self.pressed:
                            _snap(self.out, target, f"alert_{len(self.events) + 1}.png")
                            texts = [str(v.stringValue()) for v in _find(
                                target.contentView(),
                                lambda v: isinstance(v, _AppKit.NSTextField))
                                if str(v.stringValue())]
                            self.events.append({"alert": str(target.className()),
                                                "texts": texts, "answered": title,
                                                "capture_queue": self.printed_to_capture,
                                                "at": time.strftime("%H:%M:%S")})
                            self.pressed.add(target.windowNumber())
                            _press(b[0])
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
                    self.printed_to_capture = bool(ok)
                    _press(b[0])
                return
except Exception:  # pragma: no cover - not macOS
    _PanelDriver = None  # type: ignore[assignment]


#: what make-fixtures copies: model -> media to keep (Canon media files and,
#: beta 16, the records of a binary Canon table)
FIXTURE_MODELS = {
    "Canon PRO-300 series": ("0", "51", "63", "28", "165", "162", "42"),
    "Canon PRO-1000 series": ("0", "28", "51", "78", "17448", "63"),
    "Canon PRO-100 series": (),
    "EPSON ET-8550 Series": (),
    "EPSON SC-P900 Series": (),
    "EPSON Epson Stylus Photo R3000": (),
    # beta 16: the binary media table of the 16.9x Canon drivers, an
    # imagePROGRAF, and the Epson models with one PDEData.dat per black ink
    "Canon PRO-10S series": ("0", "63", "42", "51", "45", "169", "28"),
    "Canon PRO-2100": ("0", "63", "17448"),
    "EPSON Stylus Photo R2400": (),
    "EPSON Stylus Photo 2200": (),
    "EPSON Stylus Photo 1400": (),      # an automatic dialog (Mode 0, EPIJAutoPreset)
    "EPSON PM-400 Series": (),          # no paper profiles at all
    "EPSON SC-P6000 Series": ("0", "101", "13", "14", "1950"),   # black ink per medium
}
_KEEP_OPTIONS = ("Resolution", "MediaType", "ColorModel", "CNIJMediaType", "CNIJProfileID", "CNIJPrintQuality", "CNIJIntent2",
                 "CNIJMediaSupply", "CNIJCartridge", "CNIJFitRollPaperWidth",
                 "EPIJ_Medi", "EPIJProfileSpec", "EPIJ_Qual", "EPIJ_Mode", "EPIJ_CMat",
                 "EPIJ_CCor", "EPIJ_OSColMat", "EPIJ_OSCMProf", "EPIJ_HdofClSp", "EPIJ_Ink_",
                 "EPIJ_MeInSeNm", "EPIJ_MdGropID", "EPIJ_APri", "EPIJ_ATon", "EPIJ_AGai", "EPIJ_ACam",
                 "EPIJ_AFil", "EPIJ_DCCT", "EPIJ_Thck", "EPIJ_PGDt", "EPIJ_Suct", "EPIJ_RpTn",
                 "EPIJ_PaFd", "EPIJ_DrTm", "EPIJ_IkDt", "EPIJ_Bi_D", "EPIJ_FDet", "EPIJ_FWea",
                 "EPIJ_Weav")


def trim_canon_tbl(data: bytes, cartridge: int, media: tuple[str, ...]) -> bytes:
    """A binary Canon media table (``cnb_NNNN.tbl``) cut down to what
    ``ppd_color._canon_media_tbl`` reads, for *media*: the directory, table
    2002 (print modes) and table 2004 (profile records), kept byte for byte."""
    import struct
    keep = {int(m) for m in media}
    n = struct.unpack_from("<I", data, 0x300)[0]
    tables = {}
    for i in range(n):
        _ln, tid, off = struct.unpack_from("<III", data, 0x304 + 12 * i)
        tables[tid] = off
    o = tables[2002]
    size, a, b, c, count = struct.unpack_from("<IIIII", data, o)
    stride = (size - 20) // count
    entries = [data[o + 20 + stride * i:o + 20 + stride * (i + 1)] for i in range(count)]
    entries = [e for e in entries if len(e) == stride
               and struct.unpack_from("<BBHHH", e, 4)[3] in keep
               and struct.unpack_from("<BBHHH", e, 4)[2] == cartridge]
    t2002 = struct.pack("<IIIII", 20 + stride * len(entries), a, b, c, len(entries)) \
        + b"".join(entries)
    o = tables[2004]
    end = o + struct.unpack_from("<I", data, o)[0]
    recs = []
    for m in re.finditer(rb"Canon [^\0]{2,60}\0", data[o:end]):
        k = o + m.start() - 8
        key = struct.unpack_from("<BBHHH", data, k)
        if key[3] in keep and key[2] == cartridge:
            recs.append(data[k:k + 0x80])
    t2004 = struct.pack("<I", 16 + 0x80 * len(recs)) + b"\0" * 12 + b"".join(recs)
    o = tables[2001]
    size, a1, b1, count = struct.unpack_from("<IIII", data, o)
    stride = round((size - 16) / count)
    ents = [data[o + 20 + stride * i:o + 20 + stride * (i + 1)] for i in range(count)]
    ents = [e for e in ents if len(e) == stride
            and struct.unpack_from("<BBHHH", e)[3] in keep
            and struct.unpack_from("<BBHHH", e)[2] == cartridge]
    t2001 = struct.pack("<IIII", 16 + stride * len(ents), a1, b1, len(ents)) \
        + data[o + 16:o + 20] + b"".join(ents)
    head = bytearray(0x300)
    d = struct.pack("<I", 3)
    off2001 = 0x300 + 4 + 36
    off2002 = off2001 + len(t2001)
    off2004 = off2002 + len(t2002)
    d += (struct.pack("<III", 8, 2001, off2001) + struct.pack("<III", 8, 2002, off2002)
          + struct.pack("<III", 8, 2004, off2004))
    return bytes(head) + d + t2001 + t2002 + t2004


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
                ib = re.search(r'<availableinputbinid[^>]*>[^<]*</availableinputbinid>', x)
                out = dest / rel / src.name
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<medium>'
                               f'{ib.group(0) if ib else ""}'
                               f'{cm.group(0) if cm else ""}</medium>\n', encoding="utf-8")
                written.append(str(rel / src.name))
            for tbl in sorted(db.glob("cnb_*.tbl")):
                cart = int(pc._ppd_default(text, "CNIJCartridge") or "0")
                out = dest / rel / tbl.name
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(trim_canon_tbl(tbl.read_bytes(), cart, media))
                written.append(str(rel / tbl.name))
        for _variant, pde in pc.epson_pde_variants(text):
            t = pde.read_text(encoding="latin-1")
            if media:   # an Epson cut to these media (the SC-P6000's file is 3 MB)
                keep_m = set(media)

                def _ok(line: str) -> bool:
                    found = re.findall(r"\*EPIJ_Medi (\d+)", line)
                    return not found or all(m in keep_m for m in found)
                t = "\n".join(ln for ln in t.split("\n") if _ok(ln))
                t = re.sub(r'^\*EPIJPreset (\w+),([^,/]*)[^/]*/[^:]*:\s*".*?"\n',
                           lambda m: m.group(0) if m.group(2) in keep_m or
                           m.group(1) == "EPIJAMMPreset" else "", t, flags=re.M | re.S)
            ui = re.search(r'^\*EPIJUIType:.*$', t, re.M)
            blocks = [m.group(0) for key in ("EPIJProfileSpec", "Resolution", "MediaType",
                                             "ColorModel")
                      if (m := re.search(rf'^\*EPIJConditionValue {key}/:\s*".*?"', t,
                                         re.S | re.M))]
            rel = pde.relative_to(pc.MAC_DRIVER_ROOT)
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            # the dialog's quality per medium (ppd_color.epson_driver_quality),
            # its automatic priority, and the black ink per medium group
            links = re.findall(r'^\*EPIJLinkValue:\s*\*EPIJ_Medi .*\*EPIJ_(?:Qual|APri) .*$'
                               r'|^\*EPIJLinkValue:\s*\*EPIJ_MdGropID .*\*EPIJ_MeInSeNm .*$', t, re.M)
            # the presets ppd_color.epson_dialog_keys reads, cut to its keys
            presets = []
            for name in ("EPIJColorControlPreset", "EPIJAMMPreset", "EPIJAutoPreset",
                         "EPIJMediaGroupPreset", "EPIJPaperConfigPreset"):
                order = re.search(rf'^\*EPIJPresetKeywordOrder {name}/:.*$', t, re.M)
                if order:
                    presets.append(order.group(0))
                for key, body in re.findall(rf'^\*EPIJPreset {name},([^/]*)/[^:]*:\s*"(.*?)"',
                                            t, re.M | re.S):
                    kept = [ln for ln in body.split("\n") if re.match(
                        r"EPIJ_(CCor|CMat|Qual|ATon|AGai|ACam|AFil|DCCT|MdGropID|MeInSeNm|Thck|"
                        r"PGDt|Suct|RpTn|PaFd|DrTm|IkDt|Bi_D|FDet|FWea|Weav) ", ln.strip())]
                    if kept:
                        presets.append(f'*EPIJPreset {name},{key}/: "\n' + "\n".join(kept) + '"')
            out.write_text((ui.group(0) if ui else "") + "\n\n" + "\n\n".join(blocks)
                           + "\n" + "".join(line + "\n" for line in links)
                           + "\n" + "\n\n".join(presets) + "\n", encoding="latin-1")
            written.append(str(rel))
    return written


def main(argv: list[str]) -> int:
    if argv[:1] == ["_probe"]:
        _probe(argv[1], argv[2], argv[3], argv[4], Path(argv[5]), argv[6],
               argv[7] if len(argv) > 7 else "{}")
        return 0
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("from-drivers")
    a.add_argument("--write", action="store_true")
    sub.add_parser("check")
    m = sub.add_parser("measure-dialog")
    m.add_argument("model", choices=sorted({**MODELS, **NO_PROFILE_MODELS}))
    m.add_argument("--media", required=True)
    m.add_argument("--out", required=True, type=Path)
    m.add_argument("--set", default="", help="KEY=VALUE,... preset in the dialog too")
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
        presets = dict(x.split("=", 1) for x in args.set.split(",") if "=" in x)
        measure_dialog(args.model, [x for x in args.media.split(",") if x], args.out, presets)
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
