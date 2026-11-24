#!/usr/bin/env python3
"""Drive the Barbieri Spectro 100xy chart Beta ON SCREEN, in the real window.

The real, fully styled main window (``userdrive.Drive``: ``build_app``, the
appearance as ``main()`` applies it, the keyboard handed back), sandboxed
settings and presets, a fresh project under the drive's own folder. Nothing
is printed: the drive never opens a print dialog.

Steps, each photographed by window id:

1. Create Chart > Manual, the instrument "Barbieri Spectro 100xy": its group
   with the ready-made sizes, the opening, the check patches and the marks;
2. Generate with the defaults: the chart in the preview with its corner marks
   and check patches, and the grid numbers beside it;
3. every ready-made size that is drawn in reasonable time (A4, Letter,
   Barbieri standard, full reading area, the 35 mm film frame), generated
   and photographed; the large film frame is chosen and photographed in the
   panel only (a 2032 ppi page of 296 megapixels is not drawn here);
4. the Measure tab's Start: the Spectro32 steps window;
5. Guided with the Barbieri and its "Measuring opening";
6. a narrow window.

    python scripts/drive_barbieri_chart_onscreen.py <out> [--language de]

Writes ``<out>/photographs/*.png``, ``<out>/driver-notes.txt`` and, beside
them, a full-resolution crop of the upper-right corner of each chart drawn
(``<out>/crops/``), so the marks can be looked at closely.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--language", default="en")
ap.add_argument("--appearance", default="dark")
ap.add_argument("--quick", action="store_true",
                help="only the default chart, the steps window and Guided")
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

# THE BETAS, AS main() LATCHES THEM: written into the sandbox first, then
# fixed for this process before any window is built.
from core.settings import AppSettings  # noqa: E402

_pre = AppSettings()
_pre.set("barbieri_chart_beta", True)
_pre.set("page_output_beta", True)
_pre.set("restore_last_session", False)
_pre.set("session_project", "")
_pre.set("auto_update_preview", False)
from workflow.barbieri import support as _bs  # noqa: E402
from workflow.page_output import support as _po  # noqa: E402

_bs.latch_from(_pre)
_po.latch_from(_pre)
assert _bs.barbieri_enabled() and _po.page_output_enabled()

from userdrive import Drive  # noqa: E402

PROJECT = "Barbieri-Proof"


def main() -> int:
    d = Drive(OUT, language=args.language, appearance=args.appearance,
              size=(1600, 1000), time_limit_s=900)
    win = d.win
    tc = win._tab_chart
    crops = OUT / "crops"
    crops.mkdir(parents=True, exist_ok=True)

    def newest_side():
        found = sorted(win._file_mgr.project().root.rglob("*.barbieri.json"),
                       key=lambda p: p.stat().st_mtime_ns)
        return found[-1] if found else None

    def generate(name: str):
        # the build may go to a new run (a run that has a chart is kept), so
        # the chart is found by the newest side file of the project
        was = newest_side()
        before = was.stat().st_mtime_ns if was is not None else None
        d.later(tc._on_generate)
        side = None
        for _ in range(600):
            yield 200
            side = newest_side()
            if (side is not None and side.stat().st_mtime_ns != before
                    and tc._generate_btn.isEnabled()
                    and not win._runner.is_running):
                break
        yield 1500
        from types import SimpleNamespace
        run = SimpleNamespace(chart_ti2=(side.with_name(
            side.name[:-len(".barbieri.json")] + ".ti2") if side else
            win._file_mgr.project().current_run().chart_ti2))
        side = side or run.chart_ti2.with_name("none.barbieri.json")
        d.note(f"{name}: chart {'made' if side.exists() else 'NOT made'}")
        if side.exists():
            import json
            doc = json.loads(side.read_text(encoding="utf-8"))
            for pg in doc.get("pages_detail", []):
                d.note(f"   page {pg['page']}: {pg['columns']} x "
                       f"{pg['rows']}, {pg['spectro32']}, aim "
                       f"{pg['aim_patch']}, area {pg['patch_area_mm']}")
            try:
                from PIL import Image
                Image.MAX_IMAGE_PIXELS = None
                tifs = sorted(run.chart_ti2.parent.glob(
                    run.chart_ti2.name[:-4] + "*.tif"))
                if tifs:
                    im = Image.open(tifs[0])
                    dpi = float(doc.get("dpi") or 300)
                    s = dpi / 25.4
                    pg = doc["pages_detail"][0]
                    left, top, right, _b = pg["grid_mm"]
                    box = (max(0, int((right - 30) * s)), 0,
                           min(im.width, int((right + 15) * s)),
                           min(im.height, int((top + 25) * s)))
                    im.crop(box).convert("RGB").save(
                        crops / f"{name}-upper-right.png")
                    box = (0, 0, min(im.width, int((left + 30) * s)),
                           min(im.height, int((top + 25) * s)))
                    im.crop(box).convert("RGB").save(
                        crops / f"{name}-upper-left.png")
            except Exception as exc:                     # noqa: BLE001
                d.note(f"   crop failed: {exc}")

    def pick_size(key: str) -> bool:
        p = tc._manual_layout_panel
        i = p.barbieri_size.findData(key)
        if i < 0:
            return False
        p.barbieri_size.setCurrentIndex(i)
        p.barbieri_size.activated.emit(i)
        return True

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
        d.note(f"Barbieri offered in Manual: {k >= 0}")
        p.instr.setCurrentIndex(k)
        p.instr.activated.emit(k)
        yield 1200
        grp = p._barbieri_group
        try:
            area = grp.parentWidget()
            while area is not None and not hasattr(area, "ensureWidgetVisible"):
                area = area.parentWidget()
            if area is not None:
                area.ensureWidgetVisible(grp)
        except Exception:                                # noqa: BLE001
            pass
        yield 600
        d.shot(win, "01-manual-barbieri-group")
        yield from generate("02-default")
        d.shot(win, "02-default-chart-and-numbers")
        if not args.quick:
            for n, key in enumerate(("a4", "letter", "standard", "full",
                                     "film_35"), start=3):
                ok = pick_size(key)
                d.note(f"ready-made size {key}: picked {ok}")
                yield 900
                yield from generate(f"{n:02d}-{key}")
                d.shot(win, f"{n:02d}-size-{key}")
            pick_size("film_large")
            yield 900
            d.shot(win, "08-size-film_large-chosen-not-drawn")
            pick_size("a4")
            yield 900
            yield from generate("09-a4-again")
        # the Measure tab's Start: the Spectro32 steps
        d.goto_tab("measure")
        yield 1200
        tm = win._tab_measure
        d.later(tm._start_btn.click)
        for _ in range(40):
            yield 200
            if d.modal() is not None:
                break
        m = d.modal()
        if m is not None:
            d.note("Start window: " + (m.text() if hasattr(m, "text")
                                       else type(m).__name__))
            d.dog.claim(m) if d.dog is not None else None
            d.shot(m, "10-start-spectro32-steps")
            d.later(m.accept)
            yield 800
        else:
            d.note("Start window: NONE")
        # Guided with the Barbieri and its opening
        d.goto_tab("chart")
        tc._switch_mode("guided")
        yield 900
        i = tc._instr_combo.findData("B100XY")
        d.note(f"Barbieri offered in Guided: {i >= 0}")
        tc._instr_combo.setCurrentIndex(i)
        yield 1200
        d.shot(win, "11-guided-barbieri-opening")
        # a narrow window
        tc._switch_mode("manual")
        yield 600
        win.resize(1100, 820)
        yield 1500
        d.shot(win, "12-narrow-window")
        win.resize(1600, 1000)
        yield 800
        d.end(0, "done")

    return d.run(script)


if __name__ == "__main__":
    sys.exit(main())
