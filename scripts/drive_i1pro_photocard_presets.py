#!/usr/bin/env python3
"""Drive the REAL ChromIQ window over Knut's fifteen i1Pro photo-card presets.

**This REPLACES the two-card version of this file** (2026-09-09). It covers the
same four things and then the eleven charts that arrived afterwards, and it
photographs the window through `scripts/onscreen_capture.py` where the old one
called `widget.grab()` — which CLAUDE.md rules is not a screenshot — and copied
Basti's real preferences into its sandbox, which measures the owner's machine
rather than a fresh install.

Knut, 2026-09-17 (issue #182): *"I also created a few more presets to be added
as built-in as the other built-in presets."* Thirteen new charts on the 10 x 15
cm and 13 x 18 cm cards, seven of them a new "Maximised - No Clip-border" cut.

What this proves ON SCREEN, in a real window, and not in a fixture:

1. the **Presets dropdown** in Create Chart → Manual lists all fifteen under
   the i1Pro heading, in the order the registry holds them;
2. the **★ Built-in presets overlay** (the speech bubble) shows the same rows;
3. **picking one the way a user picks it** seeds the Manual layout panel with
   the sheet, the grid, the margins and the clip band the preset carries, and
   builds the chart right there;
4. **the chart that comes out is the one the name promises**: the patch count,
   the page count, the sheet and the patch width are read back off the files
   the app itself wrote, not off the recipe it was handed.

Every picture is a PHOTOGRAPH of the window taken through
``scripts/onscreen_capture.py`` (``CGWindowListCreateImage``), never a
``widget.grab()`` render. A capture that cannot be proved is reported, loudly,
and its file is not kept.

**THE SETTINGS ARE SANDBOXED AND HIS PLIST IS NEVER READ.** Copying the real
preferences into a scratch .ini measures the OWNER's machine, not the product,
and it has produced six green checks that were red on a fresh install. So this
starts from a bare store. Set both before running::

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-photocards/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-photocards/presets
    python scripts/drive_i1pro_photocard_presets.py --shots <folder>

Afterwards, check the VALUE rather than the file::

    defaults read com.chromiq.ChromIQ custom_output_path
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtGui import QFontDatabase                           # noqa: E402
from PyQt6.QtWidgets import (QAbstractItemView, QApplication,   # noqa: E402
                             QDialog, QMessageBox)

from core.resource_path import resource_path                    # noqa: E402
from scripts.onscreen_capture import capture_window             # noqa: E402

FAILED_CAPTURES: list[str] = []


def pump(app, ms: int) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def shot(shots: Path, w, name: str) -> Path | None:
    """Photograph *w*. A capture that cannot be proved is a FINDING, said here
    and repeated at the top of the summary — never a silent fallback."""
    shots.mkdir(parents=True, exist_ok=True)
    p = shots / f"{name}.png"
    ok, why = capture_window(w, p)
    if ok:
        print(f"    photographed {p.name}")
        return p
    print(f"    *** NO PHOTOGRAPH of {p.name}: {why}")
    FAILED_CAPTURES.append(f"{p.name}: {why}")
    return None


def _tif_pages(run_dir: Path) -> list[Path]:
    """Every page the app wrote. A one-page chart is ``<stem>.tif`` with no
    number, a multi-page one ``<stem>_01.tif`` …, so both forms are counted."""
    return sorted(run_dir.glob("*.tif"))


def _ti2_patches(ti2: Path) -> int:
    txt = ti2.read_text(encoding="latin-1", errors="ignore")
    m = re.search(r"NUMBER_OF_SETS\s+(\d+)", txt)
    return int(m.group(1)) if m else 0


def run(app, shots: Path, only: int | None) -> int:
    from core.settings import AppSettings

    settings = AppSettings()
    store = Path(settings._qs.fileName())
    if "Preferences" in str(store):
        print(f"    *** REFUSING TO RUN: settings would go to {store}\n"
              f"        set CHROMIQ_SETTINGS_FILE first (see the docstring)")
        return 2
    work = Path(tempfile.mkdtemp(prefix="chromiq-photocards-"))
    settings.set("custom_output_path", str(work))
    settings.set("restore_last_session", False)
    print(f"    settings store : {store}")
    print(f"    presets dir    : {os.environ.get('CHROMIQ_PRESETS_DIR', '(real!)')}")
    print(f"    chart output   : {work}")

    # A modal that blocks is a modal Basti ends up clicking, and every result
    # after that point is his rather than the product's.
    QDialog.exec = lambda self: 1                      # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.builtin_preset_popup import BuiltinPresetPopup
    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import (BUILTIN_PRESET_GROUPS, KNUT_PRESETS,
                                   TabChart, _marked_overlay_label)
    TabChart._confirm_displacing_results = lambda self, *a, **k: True

    photo = [p for p in KNUT_PRESETS if p.slug.startswith("i1_photo_")]
    print(f"    {len(photo)} photo-card presets in the registry")

    win = MainWindow(settings)
    win.show()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 600)
    tab._user_switch_mode("manual")
    pump(app, 1200)

    report: dict = {"dropdown_rows": [], "overlay_rows": [], "charts": [],
                    "failed_captures": FAILED_CAPTURES}

    # --- 1. the Presets dropdown -------------------------------------------
    combo = tab._preset_combo
    rows = [(combo.itemText(i), combo.itemData(i))
            for i in range(combo.count())]
    keys = {p.key: p for p in photo}
    listed = [t for t, d in rows if d in keys]
    report["dropdown_rows"] = listed
    print(f"\n    the dropdown lists {len(listed)} of the {len(photo)} cards")
    for t in listed:
        print(f"        {t}")
    if len(listed) != len(photo):
        print("    *** not every card is in the dropdown")

    first = next(i for i, (_t, d) in enumerate(rows) if d in keys)
    # THE INDEX IS LEFT ALONE while photographing. Moving the combo onto a
    # built-in row SELECTS it, which is a real chart build with no name typed.
    for tag, row, where in (
            ("a-top-of-the-cards", max(first - 3, 0),
             QAbstractItemView.ScrollHint.PositionAtTop),
            ("b-bottom-of-the-cards", first + len(photo),
             QAbstractItemView.ScrollHint.PositionAtBottom)):
        combo.showPopup()
        pump(app, 800)
        combo.view().scrollTo(combo.model().index(row, 0), where)
        pump(app, 700)
        shot(shots, combo.view().window(), f"01{tag}-presets-dropdown")
        combo.hidePopup()
        pump(app, 400)

    # --- 2. the ★ speech-bubble overlay ------------------------------------
    groups = [(g, [(_marked_overlay_label(k, lbl), k)
                   for (_c, lbl, k) in entries])
              for g, entries in BUILTIN_PRESET_GROUPS]
    # The heading is the Instrument field's own words, not "i1Pro":
    # INSTRUMENT_LABELS["i1"] is "i1Pro / i1Pro 2 / i1Pro 3". Asked for by
    # the key rather than spelled out, so a renamed label cannot break this.
    from data.patch_db import INSTRUMENT_LABELS
    i1 = INSTRUMENT_LABELS["i1"]
    report["overlay_rows"] = [lbl for g, e in groups if g == i1
                              for (lbl, k) in e if k in keys]
    popup = BuiltinPresetPopup(groups, win)
    popup.move(win.geometry().center())
    popup.show()
    pump(app, 1400)
    tops = {r.text: r.top for r in popup._rows if r.kind == "header"}
    for tag, lift in (("a-top", 40), ("b-further-down", 300)):
        popup._scroll_y = max(0, min(popup._max_scroll, tops[i1] - lift))
        popup.update()
        pump(app, 800)
        shot(shots, popup, f"02{tag}-builtin-presets-overlay")
    popup.close()
    pump(app, 400)

    # --- 3. pick every card the way a user picks one -----------------------
    todo = photo[:only] if only else photo
    print(f"\n    building {len(todo)} chart(s) through the real dropdown\n")
    bad = 0
    for n, p in enumerate(todo, 1):
        target = f"PC-{p.slug}"
        tab._target_name_edit.setText(target)
        pump(app, 250)
        idx = combo.findData(p.key)
        if idx < 0:
            print(f"    [{n:2d}] {p.name}: NOT IN THE DROPDOWN")
            bad += 1
            continue
        tab._margin_ti2 = None
        # EXACTLY WHAT A CLICK DOES. The tab listens on `activated`, which Qt
        # emits only for a real user pick, so `setCurrentIndex` alone applies
        # no preset and builds nothing.
        combo.setCurrentIndex(idx)
        combo.activated.emit(idx)
        pump(app, 300)
        ok = False
        for _ in range(360):
            pump(app, 250)
            if getattr(tab, "_margin_ti2", None):
                ok = True
                break
        if not ok:
            print(f"    [{n:2d}] {p.name}: DID NOT BUILD")
            bad += 1
            continue
        pump(app, 500)

        # What the PANEL now shows — the parameters the preset filled in, read
        # off the live widgets rather than off the row that seeded them.
        panel = tab._manual_layout_panel.get_recipe().to_dict()
        ti2 = Path(tab._margin_ti2)
        run_dir = ti2.parent
        pages = _tif_pages(run_dir)
        patches = _ti2_patches(ti2)
        width_mm = 0.0
        written_paper = None
        geom = run_dir / f"{ti2.stem}.channels.json"
        if geom.is_file():
            try:
                lay = json.loads(geom.read_text(encoding="utf-8"))["layout"]
                written_paper = (lay.get("recipe") or {}).get("paper")
                q = (lay.get("patches") or [{}])[0]
                if q.get("w"):
                    width_mm = round(q["w"] * 25.4 / lay["dpi"], 2)
            except Exception:       # noqa: BLE001
                pass
        said_w = float(re.search(r"-w([\d.]+)mm", p.name).group(1))
        maximised = p.name.endswith("-Maximised-No Clip-border")
        good = (patches == p.patches and len(pages) == p.pages
                and written_paper == p.layout_recipe["paper"]
                and abs(width_mm - said_w) <= 0.5
                and panel["paper"] == p.layout_recipe["paper"]
                and panel["area_cols"] == p.layout_recipe["area_cols"]
                and panel["area_rows"] == p.layout_recipe["area_rows"]
                and panel["margin_left"] == p.layout_recipe["margin_left"]
                and panel["clip_border"] is not maximised)
        bad += 0 if good else 1
        print(f"    [{n:2d}] {p.name:<62} built {patches:>5}p on "
              f"{len(pages)} sheet(s) of {written_paper}, patch {width_mm} mm, "
              f"panel {panel['area_cols']}x{panel['area_rows']} "
              f"clip={panel['clip_border']}  {'OK' if good else '<<< MISMATCH'}")
        report["charts"].append({
            "name": p.name, "key": p.key, "maximised": maximised,
            "said_paper": p.layout_recipe["paper"], "built_paper": written_paper,
            "said_patches": p.patches, "built_patches": patches,
            "said_pages": p.pages, "built_pages": len(pages),
            "said_patch_width_mm": said_w, "built_patch_width_mm": width_mm,
            "panel_paper": panel["paper"],
            "panel_grid": [panel["area_cols"], panel["area_rows"]],
            "panel_margins": {k: panel[k] for k in
                              ("margin_top", "margin_right", "margin_bottom",
                               "margin_left")},
            "panel_clip_border": panel["clip_border"],
            "panel_clip_content_mode": panel["clip_content_mode"],
            "panel_clip_border_width_mm": panel["clip_border_width_mm"],
            "run_dir": str(run_dir),
            "pages": [str(x) for x in pages],
            "ok": good,
        })
        # ONE PHOTOGRAPH PER CARD, THE TWO OLD ONES INCLUDED. They are the
        # control: anything the new cards show that those two show as well is
        # not something this change introduced, and the first run of this
        # driver skipped them and nearly reported a pre-existing warning as a
        # new fault.
        shot(shots, win, f"03-panel-after-{p.slug}")

    shot(shots, win, "04-window-final")
    shots.mkdir(parents=True, exist_ok=True)
    (shots / "drive-report.json").write_text(json.dumps(report, indent=1),
                                             encoding="utf-8")
    print(f"\n    report: {shots / 'drive-report.json'}")
    print(f"    mismatches: {bad}")
    if FAILED_CAPTURES:
        print("    *** CAPTURES THAT COULD NOT BE PROVED:")
        for f in FAILED_CAPTURES:
            print(f"        {f}")
    win.close()
    pump(app, 400)
    return 1 if (bad or FAILED_CAPTURES) else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--shots", type=Path,
                    default=Path.home() / "Desktop" / "ChromIQ-beta21-proof"
                    / "knut-new-presets" / "photographs")
    ap.add_argument("--only", type=int, default=None,
                    help="build only the first N cards (the listings are "
                         "photographed either way)")
    args = ap.parse_args()
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        print("*** QT_QPA_PLATFORM=offscreen belongs to the TEST SUITE. "
              "This driver opens a REAL window; unset it and run again.")
        return 2
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)
    rc = run(app, args.shots, args.only)
    print(f"\nphotographs in {args.shots}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
