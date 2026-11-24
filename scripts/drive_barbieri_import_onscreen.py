#!/usr/bin/env python3
"""Drive the Barbieri Beta's Spectro32 IMPORT ON SCREEN, in the real window.

The real, fully styled main window (``userdrive.Drive``), sandboxed settings
and presets, a fresh project under the drive's own folder. Nothing is
printed. The Spectro32 files are SYNTHETIC, written here in the shape of an
owner's real run (`tests._barbieri_fixture`): no tester data.

1. Create Chart > Manual, "Barbieri Spectro 100xy", Generate with the
   defaults (a profiling run with a Barbieri chart and its side file);
2. Measure > IMPORT with a Spectro32 file of a MIRRORED sheet: the panel,
   then Import Measurement and the refusal window; nothing filed;
3. the same with the file of the sheet as it should lie: the panel, Import
   Measurement, the "done" window; the log.

With ``--review`` (the fix round of 2026-11-24) instead:

1. a 24-patch chart printed with strong tone distortion (gamma 3), laid
   correctly: the question window (no refusal), answered Import, the copy
   records the answer;
2. a chart for the 3 mm transmission opening: the "done" window with its
   note, then Build Profile > Manual with Media Type preselected
   "Transparent".

    python scripts/drive_barbieri_import_onscreen.py <out> [--language de]
        [--review]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--language", default="en")
ap.add_argument("--appearance", default="dark")
ap.add_argument("--review", action="store_true")
args = ap.parse_args()

OUT = Path(args.out).resolve()
SB = OUT / "sandbox"
(SB / "presets").mkdir(parents=True, exist_ok=True)
os.environ["CHROMIQ_SETTINGS_FILE"] = str(SB / "settings.ini")
os.environ["CHROMIQ_PRESETS_DIR"] = str(SB / "presets")
os.environ.setdefault("CHROMIQ_LOG_DIR", str(SB / "logs"))
os.environ.pop("QT_QPA_PLATFORM", None)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core.settings import AppSettings  # noqa: E402

_pre = AppSettings()
_pre.set("barbieri_chart_beta", True)
_pre.set("restore_last_session", False)
_pre.set("session_project", "")
_pre.set("auto_update_preview", False)
from workflow.barbieri import support as _bs  # noqa: E402

_bs.latch_from(_pre)
assert _bs.barbieri_enabled()

from userdrive import Drive  # noqa: E402

PROJECT = "Barbieri-Import-Proof"


def main() -> int:
    d = Drive(OUT, language=args.language, appearance=args.appearance,
              size=(1600, 1000), time_limit_s=900)
    win = d.win
    tc = win._tab_chart
    tm = win._tab_measure
    files = OUT / "spectro32"
    files.mkdir(parents=True, exist_ok=True)

    def newest_side():
        # a run's own chart only, not the snapshot a filed import keeps
        found = sorted((p for p in win._file_mgr.project().root.rglob(
            "*.barbieri.json") if p.parent.parent.name == "runs"),
            key=lambda p: p.stat().st_mtime_ns)
        return found[-1] if found else None

    def import_file(path, tag):
        tm._switch_mode("import")
        tm._use_import_files([path])
        yield 900
        d.shot(win, f"{tag}-panel")
        d.later(tm._import_go_btn.click)
        yield 300

    def script(d):
        win._file_mgr.set_target_name(PROJECT)
        win._file_mgr.project().current_run().ensure_dir()
        d.goto_tab("chart")
        tc._switch_mode("manual")
        yield 600
        if tc._manual_target_name_edit is not None:
            tc._manual_target_name_edit.setText(PROJECT)
        tc._init_manual_layout_panel()
        yield 600
        p = tc._manual_layout_panel
        k = p.instr.findData("B100XY")
        p.instr.setCurrentIndex(k)
        p.instr.activated.emit(k)
        yield 1200
        d.later(tc._on_generate)
        side = None
        for _ in range(600):
            yield 200
            side = newest_side()
            if side is not None and tc._generate_btn.isEnabled() \
                    and not win._runner.is_running:
                break
        yield 1500
        d.shot(win, "01-barbieri-chart")
        doc = json.loads(side.read_text(encoding="utf-8"))
        ti2 = side.with_name(side.name[:-len(".barbieri.json")] + ".ti2")
        pg = doc["pages_detail"][0]
        d.note(f"chart {ti2.name}: {pg['columns']} x {pg['rows']}, "
               f"{pg['spectro32']}, first {pg['first_patch']}, aim "
               f"{pg['aim_patch']}")
        from tests._barbieri_fixture import readings_for, write_spectro32
        mirrored = write_spectro32(
            files / "proof-mirrored_measurements.txt",
            readings_for(ti2, doc, arrangement="mirrored"),
            template="proof-reflection.TXT")
        straight = write_spectro32(
            files / "proof_measurements.txt", readings_for(ti2, doc),
            template="proof-reflection.TXT")
        write_spectro32(files / "proof_VAL.txt", readings_for(ti2, doc),
                        kind="val", template="proof-reflection.TXT")
        d.goto_tab("measure")
        yield 1200
        # a sheet laid mirrored: refused
        yield from import_file(mirrored, "02-mirrored")
        d.answer("OK", name="03-mirrored-refused")
        yield 600
        run = win._file_mgr.project().current_run()
        d.note(f"after the refusal, measurement filed: "
               f"{run.measurement_ti3.exists()}")
        # the sheet as it should lie: filed
        yield from import_file(straight, "04-straight")
        for _ in range(60):
            yield 200
            m = d.modal()
            if m is not None and m.isVisible():
                break
        m = d.modal()
        if m is not None:
            said = d.modal_text(m)
            d.note("window: " + said[:300].replace("\n", " / "))
            d.shot(m, "05-done-window")
            d.dog.claim(m) if d.dog is not None else None
            d.later(m.reject)
            yield 900
        else:
            d.note("no window after the import")
        run = win._file_mgr.project().current_run()
        d.note(f"measurement filed: {run.measurement_ti3.exists()} "
               f"({run.measurement_ti3})")
        if run.measurement_ti3.exists():
            head = run.measurement_ti3.read_text(encoding="utf-8")[:900]
            d.note("filed header: " + " | ".join(
                ln for ln in head.splitlines() if "BARBIERI" in ln
                or "TARGET_INSTRUMENT" in ln or "NUMBER_OF_SETS" in ln))
        yield 600
        d.shot(win, "06-after-import-log")
        d.end(0, "done")

    def generate_manual(head: str):
        d.goto_tab("chart")
        tc._switch_mode("manual")
        yield 600
        if tc._manual_target_name_edit is not None:
            tc._manual_target_name_edit.setText(PROJECT)
        tc._init_manual_layout_panel()
        yield 600
        p = tc._manual_layout_panel
        k = p.instr.findData("B100XY")
        p.instr.setCurrentIndex(k)
        p.instr.activated.emit(k)
        yield 1200
        p.barbieri_head.setCurrentIndex(p.barbieri_head.findData(head))
        yield 900
        was = newest_side()
        was_t = was.stat().st_mtime_ns if was is not None else 0
        d.later(tc._on_generate)
        for _ in range(600):
            yield 200
            side = newest_side()
            if side is not None and side.stat().st_mtime_ns != was_t and \
                    tc._generate_btn.isEnabled() \
                    and not win._runner.is_running:
                break
        yield 1500

    def review(d):
        win._file_mgr.set_target_name(PROJECT)
        run = win._file_mgr.project().current_run()
        run.ensure_dir()
        # 1. a small chart, printed with gamma 3, laid correctly
        from tests._barbieri_fixture import (readings_for, write_spectro32,
                                             write_ti1)
        from workflow.layout_engine import presets
        from workflow.layout_engine.chart import build_chart
        stem = run.chart_ti2.name[:-4]
        ti1 = write_ti1(files / "small.ti1", 24)
        build_chart(ti1, run.chart_ti2.parent / stem,
                    **presets.default_recipe("B100XY", "A4R").build_kwargs())
        doc = json.loads(run.chart_ti2.with_name(
            stem + ".barbieri.json").read_text(encoding="utf-8"))
        small = write_spectro32(files / "small-gamma3_measurements.txt",
                                readings_for(run.chart_ti2, doc, gamma=3.0),
                                template="small.TXT")
        # opened as Load opens a project, so the bar lists the run
        d.open_project(PROJECT)
        d.set_bar(run=run.id)
        tm.set_ti1_path(run.chart_ti2)
        d.goto_tab("measure")
        yield 1200
        yield from import_file(small, "20-small-gamma3")
        d.answer("Import", name="21-small-asked-not-refused")
        for _ in range(60):
            yield 200
            m = d.modal()
            if m is not None and m.isVisible():
                break
        m = d.modal()
        if m is not None:
            d.shot(m, "22-small-done")
            d.later(m.reject)
            yield 900
        filed = win._file_mgr.project().current_run().measurement_ti3
        txt = filed.read_text(encoding="utf-8") if filed.exists() else ""
        d.note("small chart filed: " + str(filed.exists()) + "; " + " | ".join(
            ln for ln in txt.splitlines()[:40] if "UNVERIFIED" in ln))
        # 2. transmission: Transparent preselected in Build Profile, in a
        #    NEW run (run 1 keeps the small chart and its import)
        combo = d.bar._run_combo
        combo.setCurrentIndex(combo.count() - 1)
        yield 1200
        d.note("bar before the film chart: " + combo.currentText())
        yield from generate_manual("transmission-3")
        side = newest_side()
        doc = json.loads(side.read_text(encoding="utf-8"))
        ti2 = side.with_name(side.name[:-len(".barbieri.json")] + ".ti2")
        d.note(f"film chart {ti2}: mode {doc.get('mode')}")
        film = write_spectro32(files / "film_measurements.txt",
                               readings_for(ti2, doc),
                               template="film-transmission.TXT")
        d.goto_tab("measure")
        yield 1200
        yield from import_file(film, "23-film")
        for _ in range(60):
            yield 200
            m = d.modal()
            if m is not None and m.isVisible():
                break
        m = d.modal()
        if m is not None:
            d.note("window: " + d.modal_text(m)[-600:].replace("\n", " / "))
            d.shot(m, "24-film-done-with-note")
            d.later(m.accept)               # "Build the profile"
            yield 1500
        tp = win._tab_profile
        tp._switch_mode("manual")
        yield 900
        combo = tp._m_z_media_type_combo
        d.note(f"Build Profile Media Type: {combo.currentText()!r} "
               f"({combo.currentData()!r}); polarity "
               f"{tp._m_z_polarity_combo.currentText()!r}")
        try:
            w = combo.parentWidget()
            while w is not None and not hasattr(w, "ensureWidgetVisible"):
                w = w.parentWidget()
            if w is not None:
                w.ensureWidgetVisible(combo)
        except Exception:                               # noqa: BLE001
            pass
        yield 900
        d.shot(win, "25-build-profile-transparent-preselected")
        d.end(0, "done")

    return d.run(review if args.review else script)


if __name__ == "__main__":
    sys.exit(main())
