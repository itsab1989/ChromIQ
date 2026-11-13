#!/usr/bin/env python3
"""Drive the same Create Chart sequence for every instrument ON SCREEN, and
lay the photographs side by side.

    python scripts/instrument_parity_drive.py OUT_DIR [--only CODE ...]

For each instrument the app lists (Beta instruments switched on), in the
REAL app in a REAL window, one fresh run of ChromIQ each:

   01 Guided, the instrument chosen        07 a layout preset loaded
   02 Guided, a chart generated            08 the first project opened again
   03 Manual                                  from disk
   04 Manual, three options changed        09 Run type Profiling
   05 Save as Defaults pressed             10 Run type Verification
   06 a new project typed in               11 Run type Calibration

Written to OUT_DIR:

* ``contact/<step>.png``: one picture per step with every instrument side by
  side (reference first), each photographed by its window id;
* ``summary.txt``: per step, what each instrument showed (mode, instrument,
  the three options, Generate) and the controls whose shown/greyed state
  differs from the reference at that step;
* ``<CODE>/``: that instrument's photographs, notes and sandbox.

Everything is sandboxed into OUT_DIR (settings, presets, logs, projects):
your own ChromIQ settings and projects are never read or written. Nothing is
printed; the window is never raised and never takes the keyboard.

What it needs: ArgyllCMS for step 02 (``targen``; without it the step says
so and the rest still runs). Photographs need macOS with Screen Recording
allowed for the terminal (System Settings > Privacy & Security > Screen
Recording). On Windows and Linux the drive runs and writes ``summary.txt``,
but takes no photographs (the window capture uses a macOS interface); the
summary says so on its first line.

The same checks without a window, as a test: ``tests/test_instrument_parity.py``.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

STEPS = ("01-guided", "02-guided-generated", "03-manual",
         "04-manual-three-options", "05-saved-as-defaults", "06-new-project",
         "07-preset-loaded", "08-reopened", "09-run-profiling",
         "10-run-verification", "11-run-calibration")

#: The three Manual options step 04 changes: the first three of these that
#: are shown and enabled for the instrument.
THREE = ("panel.dpi", "panel.randomize_cb", "panel.show_indicators",
         "panel.compression", "panel.bit16_cb", "panel.export_pdf_cb")


def instruments() -> list[str]:
    """Every instrument the app lists, reference first, with no window."""
    sys.path.insert(0, str(REPO))
    from scripts import instrument_parity as ip
    from data.patch_db import INSTRUMENT_LABELS
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    for m in ip.beta_support_modules():
        m.set_enabled_for_this_process(True)
    lists = {"printtarg": ip._printtarg_choices(),
             "layout_panel": [c for c, _ in LayoutOptionsPanel.instruments()],
             "labels": list(INSTRUMENT_LABELS)}
    return ip.all_instruments(lists)


# ---------------------------------------------------------------------------
# One instrument, in its own run of the app
# ---------------------------------------------------------------------------

def drive_one(out: Path, code: str) -> int:
    sb = out / "sandbox"
    for sub in ("presets", "logs"):
        (sb / sub).mkdir(parents=True, exist_ok=True)
    os.environ["CHROMIQ_SETTINGS_FILE"] = str(sb / "settings.ini")
    os.environ["CHROMIQ_PRESETS_DIR"] = str(sb / "presets")
    os.environ["CHROMIQ_LOG_DIR"] = str(sb / "logs")
    os.environ.pop("QT_QPA_PLATFORM", None)
    sys.path.insert(0, str(REPO))
    sys.path.insert(0, str(HERE))
    from scripts import instrument_parity as ip
    for m in ip.beta_support_modules():
        m.set_enabled_for_this_process(True)
        if getattr(m, "SETTING", None):
            os.environ.setdefault("_PARITY_BETA_" + m.SETTING, "1")
    from core.settings import AppSettings
    pre = AppSettings()
    pre.set("calibration_mode", True)       # Run type Calibration is offered
    pre.set("sound_enabled", False)
    for m in ip.beta_support_modules():
        if getattr(m, "SETTING", None):
            pre.set(m.SETTING, True)
    from userdrive import Drive

    d = Drive(out, size=(1500, 1000), time_limit_s=900)
    tab = d.win._tab_chart
    data: dict = {"instrument": code, "steps": {}}
    name = f"Parity-{code}"

    def record(step: str, mode: str) -> None:
        t = ip.control_table(tab, mode)
        shown = (tab._instr_combo.currentData() if mode == "guided"
                 else tab._shared_get("manual")["instrument"])
        data["steps"][step] = {
            "mode": tab._current_mode(), "instrument_shown": shown,
            "generate_enabled": tab._generate_btn.isEnabled(),
            "three": {n: t[n]["value"] for n in data.get("three", [])
                      if n in t},
            "controls": {k: [v["present"], v["enabled"]]
                         for k, v in t.items()},
            "run_type": d.ctl.target.run_type if d.ctl else None,
        }
        d.shot(tab, step)
        (out / "steps.json").write_text(json.dumps(data, indent=1,
                                                   default=str),
                                        encoding="utf-8")

    def answer_forward(tag: str) -> bool:
        """A question a Generate or an open asks: noted, photographed, and
        answered with the button that goes on (never one that prints)."""
        from PyQt6.QtWidgets import QAbstractButton, QApplication, QDialog
        for w in QApplication.topLevelWidgets():
            if (w.isVisible() and isinstance(w, QDialog)
                    and w is not d.win):
                btns = [b for b in w.findChildren(QAbstractButton)
                        if b.isVisible() and b.isEnabled() and b.text()]
                d.note(f"   question {type(w).__name__} "
                       f"{w.windowTitle()!r}: {[b.text() for b in btns]}")
                d.shot(w, f"q-{tag}")
                for word in ("and keep", "Replace", "Overwrite", "Make a new",
                             "new project", "Generate", "Continue", "Open",
                             "Yes", "OK"):
                    for b in btns:
                        t = b.text().lower()
                        if word.lower() in t and not any(
                                no in t for no in ("print", "delete",
                                                   "rename", "remove")):
                            b.click()
                            return True
        return False

    def script(d):
        # 01 Guided, the instrument chosen as a person does
        tab._guided_btn.click()
        yield 500
        if not ip.pick(tab, "guided", code):
            d.note(f"{code} is not offered in Guided")
        yield 700
        record("01-guided", "guided")
        # 02 a chart generated
        tab._target_name_edit.setText(name)
        tab._target_name_edit.editingFinished.emit()
        yield 400
        from shutil import which
        argyll = (Path(d.settings.get("argyll_bin_path", "")) / "targen")
        if not (argyll.exists() or which("targen")):
            d.note("02: ArgyllCMS targen not found, no chart generated")
        else:
            d.later(tab._on_generate)
            yield 1500
            for _ in range(3):
                if answer_forward("02"):
                    yield 1500
            t0 = time.monotonic()
            while time.monotonic() - t0 < 300 and d.win._runner.is_running:
                yield 500
            yield 2500
        record("02-guided-generated", "guided")
        # 03 Manual
        tab._manual_btn.click()
        yield 1200
        if code != tab._shared_get("manual")["instrument"]:
            ip.pick(tab, "manual", code)
            yield 600
        record("03-manual", "manual")
        # 04 three options changed
        t = ip.control_table(tab, "manual")
        three = [n for n in THREE if n in t and t[n]["present"]
                 and t[n]["enabled"]][:3]
        data["three"] = three
        for n in three:
            ip._change(t[n]["_w"])
            yield 300
        d.note(f"04: changed {three}")
        record("04-manual-three-options", "manual")
        # 05 Save as Defaults
        tab._save_defaults_btn.click()
        yield 1200
        answer_forward("05")
        record("05-saved-as-defaults", "manual")
        # 06 a new project typed in (the app asks what to do with the
        # first one: keep it)
        tab._manual_target_name_edit.setText(name + "-new")
        d.later(tab._manual_target_name_edit.editingFinished.emit)
        yield 1500
        answer_forward("06")
        yield 1200
        record("06-new-project", "manual")
        # 07 a layout preset loaded: the first built-in one in this
        # instrument's group of the preset list
        from data.patch_db import INSTRUMENT_LABELS
        combo = tab._preset_combo
        heading = INSTRUMENT_LABELS.get(code, code)
        idx, inside = -1, False
        for i in range(combo.count()):
            data_i, text_i = combo.itemData(i), combo.itemText(i)
            if data_i is None:
                inside = text_i == heading
                continue
            if inside and isinstance(data_i, str) \
                    and not data_i.startswith("__chromiq_more"):
                idx = i
                break
        if idx >= 0:
            d.note(f"07: preset {combo.itemText(idx)!r}")
            combo.setCurrentIndex(idx)
            d.later(lambda: combo.activated.emit(idx))
            yield 2000
            answer_forward("07")
            yield 800
        else:
            d.note(f"07: no built-in preset is listed for {heading!r}")
        record("07-preset-loaded", "manual")
        # 08 the first project opened again from disk
        if (d.work / name / "project.json").exists():
            d.open_project(name)
            yield 1500
            answer_forward("08")
        else:
            d.note("08: the project of step 02 is not on disk")
        record("08-reopened", tab._current_mode())
        # 09-11 each run type
        for step, rt in (("09-run-profiling", "profiling"),
                         ("10-run-verification", "verification"),
                         ("11-run-calibration", "calibration")):
            try:
                d.set_bar(run_type=rt)
            except AssertionError as exc:
                d.note(f"{step}: {exc}")
            yield 1200
            answer_forward(step)
            record(step, tab._current_mode())

    rc = d.run(script)
    data["rc"] = rc
    (out / "steps.json").write_text(json.dumps(data, indent=1, default=str),
                                    encoding="utf-8")
    return rc


# ---------------------------------------------------------------------------
# The contact sheets and the summary
# ---------------------------------------------------------------------------

def contact_sheets(out: Path, codes: list[str]) -> list[str]:
    from PIL import Image, ImageDraw
    made = []
    (out / "contact").mkdir(exist_ok=True)
    for step in STEPS:
        pics = []
        for c in codes:
            p = out / c / "photographs" / f"{step}.png"
            pics.append((c, Image.open(p).convert("RGB") if p.exists()
                         else None))
        if not any(im for _c, im in pics):
            continue
        h = 620
        tiles = []
        for c, im in pics:
            if im is None:
                tile = Image.new("RGB", (400, h + 40), "white")
            else:
                w = int(im.width * h / im.height)
                tile = Image.new("RGB", (w, h + 40), "white")
                tile.paste(im.resize((w, h)), (0, 40))
            ImageDraw.Draw(tile).text((8, 10), c + ("" if im else
                                                    "  (no photograph)"),
                                      fill="black")
            tiles.append(tile)
        sheet = Image.new("RGB", (sum(t.width for t in tiles) + 8 * len(tiles),
                                  h + 40), "white")
        x = 0
        for t in tiles:
            sheet.paste(t, (x, 0))
            x += t.width + 8
        path = out / "contact" / f"{step}.png"
        sheet.save(path)
        made.append(str(path))
    return made


def summary(out: Path, codes: list[str]) -> str:
    runs = {}
    for c in codes:
        p = out / c / "steps.json"
        runs[c] = json.loads(p.read_text(encoding="utf-8")) if p.exists() \
            else {"steps": {}, "rc": "did not run"}
    ref = codes[0]
    lines = []
    if sys.platform != "darwin":
        lines.append("NO PHOTOGRAPHS: the window capture needs macOS. The "
                     "text below is still what the app showed.")
    lines.append(f"Instrument parity drive: {', '.join(codes)} "
                 f"(reference {ref})")
    lines.append("return codes: " + ", ".join(
        f"{c}={runs[c].get('rc')}" for c in codes))
    for step in STEPS:
        lines.append("")
        lines.append(f"== {step}")
        rs = runs[ref]["steps"].get(step) or {}
        for c in codes:
            s = runs[c]["steps"].get(step)
            if not s:
                lines.append(f"  {c:5} (no record)")
                continue
            lines.append(
                f"  {c:5} mode={s['mode']} instrument={s['instrument_shown']}"
                f" run_type={s.get('run_type')} generate="
                f"{'on' if s['generate_enabled'] else 'GREYED'} "
                f"three={s.get('three')}")
            if c == ref:
                continue
            diff = []
            for k in sorted(set(rs.get("controls", {}))
                            | set(s["controls"])):
                a = (rs.get("controls") or {}).get(k)
                b = s["controls"].get(k)
                if a != b:
                    diff.append(f"{k} {a}->{b}")
            if diff:
                lines.append(f"        differs from {ref} in "
                             f"{len(diff)} control(s) [present, enabled]: "
                             + "; ".join(diff[:12])
                             + (" ..." if len(diff) > 12 else ""))
    text = "\n".join(lines) + "\n"
    (out / "summary.txt").write_text(text, encoding="utf-8")
    return text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("out", help="output folder (created; everything the "
                    "drive writes goes here)")
    ap.add_argument("--only", nargs="*", help="instrument codes (the "
                    "reference is always included)")
    ap.add_argument("--one", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if args.one:
        return drive_one(out / args.one, args.one)
    codes = instruments()
    if args.only:
        codes = [c for c in codes if c == codes[0] or c in args.only]
    print(f"instruments: {', '.join(codes)}", flush=True)
    for c in codes:
        print(f"-- {c}", flush=True)
        try:
            r = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                                str(out), "--one", c], timeout=1200)
            print(f"   {c}: rc={r.returncode}", flush=True)
        except subprocess.TimeoutExpired:
            print(f"   {c}: did not finish in 20 minutes", flush=True)
    made = contact_sheets(out, codes)
    print(summary(out, codes))
    print(f"contact sheets: {len(made)} in {out / 'contact'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
