#!/usr/bin/env python3
"""Drive the REAL ChromIQ window over Knut's two i1Pro photo-card presets.

His message, sending them:

    *"Here are both the preset for the 10x15cm and 13x18cm charts. I had to
    adjust the margins a bit to assure space for starting and ending a strip
    reading. Thus the measurements are very slightly different from the
    original pharmacist presets."*

What this proves, on screen and not in a fixture:

1. the **Presets dropdown** in Create Chart → Manual lists both cards under the
   existing **i1Pro / i1Pro 2 / i1Pro 3** heading, directly after the two
   "by Pharmacist" photo cards, which are still there and unchanged;
2. the **★ Built-in presets overlay** (the speech bubble) shows the same rows in
   the same place;
3. picking one from the dropdown the way a user picks it **builds the chart its
   name promises** — the paper, the patch count, the page count and the patch
   width are read back off the files the app actually wrote;
4. the layout panel comes back seeded with **his** margins, not an A4 jig's.

Basti's preferences are copied to a throwaway .ini and his ChromIQ root is
replaced by a sandbox. Nothing of his is touched. Check afterwards with

    defaults read com.chromiq.ChromIQ custom_output_path

Usage::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-presets.ini \
        python scripts/drive_i1pro_photocard_presets.py
"""
from __future__ import annotations

import json
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

from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtGui import QFontDatabase                           # noqa: E402
from PyQt6.QtWidgets import (QAbstractItemView, QApplication,   # noqa: E402
                             QDialog, QMessageBox)

from core.resource_path import resource_path                    # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"
SHOTS = Path.home() / "Desktop" / "ChromIQ-beta3-proof" / "photocard-presets"

#: The two Pharmacist photo cards, which must still be there and must still
#: open the i1Pro group. Knut's charts stand BESIDE them, they do not replace
#: them.
PHARMACIST = ["10x15cm-600p-4pages by Pharmacist",
              "13x18cm-648p-3pages by Pharmacist"]


def pump(app, ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def shot(w, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    p = SHOTS / f"{name}.png"
    w.grab().save(str(p))
    print(f"    saved {p.name}")
    return p


def _tif_pages(run_dir: Path) -> list[Path]:
    """Every page the app wrote for this chart. A one-page chart is written as
    ``<stem>.tif`` with no number, a multi-page one as ``<stem>_01.tif`` …"""
    return sorted(run_dir.glob("*.tif"))


def _ti2_patches(ti2: Path) -> int:
    txt = ti2.read_text(encoding="latin-1", errors="ignore")
    m = re.search(r"NUMBER_OF_SETS\s+(\d+)", txt)
    return int(m.group(1)) if m else 0


def _sheets(charts: list[dict], cell: int = 620) -> None:
    """Every page of both charts, side by side, captioned with what the name
    promised and what came out. A table proves the counts; this is so somebody
    can SEE that the sheets are photo cards with a wide band down the left."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("    (Pillow not installed, no sheet montage)")
        return
    pages = [(c, p) for c in charts for p in c["pages"]]
    if not pages:
        return
    pad, cap, cols = 16, 44, 4
    rows = -(-len(pages) // cols)
    sheet = Image.new("RGB", (cols * (cell + pad) + pad,
                              rows * (cell + cap + pad) + pad), "white")
    draw = ImageDraw.Draw(sheet)
    for i, (c, path) in enumerate(pages):
        x = pad + (i % cols) * (cell + pad)
        y = pad + (i // cols) * (cell + cap + pad)
        im = Image.open(path).convert("RGB")
        im.thumbnail((cell, cell))
        sheet.paste(im, (x + (cell - im.width) // 2, y))
        ok = (c["built_patches"] == c["said_patches"]
              and c["built_pages"] == c["said_pages"]
              and c["built_paper"] == c["said_paper"])
        draw.text((x, y + cell + 6), f'{c["name"]}  ·  {Path(path).name}',
                  fill="black")
        draw.text((x, y + cell + 22),
                  f'{c["built_patches"]}p / {c["built_pages"]} sheet(s) / '
                  f'{c["built_paper"]} mm / {c["built_patch_width_mm"]} mm '
                  f'patches  {"OK" if ok else "MISMATCH"}',
                  fill=("black" if ok else "red"))
    out = SHOTS / "06-every-sheet-both-charts.png"
    sheet.save(out)
    print(f"    saved {out.name}  ({sheet.width}x{sheet.height})")


def run(app) -> int:
    from core.settings import AppSettings

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq-photocard-"))
    src = QSettings(str(REAL_PLIST), QSettings.Format.NativeFormat)
    dst = QSettings(str(sandbox / "settings.ini"), QSettings.Format.IniFormat)
    for k in src.allKeys():
        dst.setValue(k, src.value(k))
    dst.sync()
    settings = AppSettings()
    settings._qs = dst
    work = sandbox / "ChromIQ"
    work.mkdir()
    settings.set("custom_output_path", str(work))
    settings.set("restore_last_session", False)
    print(f"    sandbox: {sandbox}")

    QDialog.exec = lambda self: 1                      # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from data.patch_db import INSTRUMENT_LABELS
    from ui.builtin_preset_popup import BuiltinPresetPopup
    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import (BUILTIN_PRESET_GROUPS, KNUT_PRESETS,
                                   TabChart, _marked_overlay_label,
                                   comparable_presets)
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

    report: dict = {"dropdown_i1pro_block": [], "overlay_headings": [],
                    "compare": [], "load_setup": [], "charts": []}
    bad = 0

    # --- 1. the Presets dropdown -------------------------------------------
    combo = tab._preset_combo
    listing = []
    for i in range(combo.count()):
        txt = combo.itemText(i)
        listing.append((txt, combo.itemData(i)))
    heads = [i for i, (t, d) in enumerate(listing) if d is None and t]
    i1_i = next(i for i in heads if listing[i][0] == INSTRUMENT_LABELS["i1"])
    nxt = next((i for i in heads if i > i1_i), len(listing))
    block = [listing[i] for i in range(i1_i + 1, nxt) if listing[i][1] is not None]
    report["dropdown_i1pro_block"] = [t for t, _d in block[:12]]
    print(f"\n    i1Pro heading at row {i1_i}: {listing[i1_i][0]!r}")
    print("    first rows under it:")
    for t, d in block[:10]:
        mark = "  <== NEW" if d in {p.key for p in photo} else ""
        print(f"        {t}{mark}")

    # Both Pharmacist photo cards must still open the group…
    for want in PHARMACIST:
        if not any(want in t for t, _d in block[:2]):
            print(f"    -> {want!r} NO LONGER OPENS THE GROUP")
            bad += 1
    # …and Knut's two must be the first rows of his own block.
    knut_keys = {p.key for p in KNUT_PRESETS}
    first_knut = next(i for i, (_t, d) in enumerate(block) if d in knut_keys)
    got = [block[first_knut][1], block[first_knut + 1][1]]
    if got != [p.key for p in photo]:
        print("    -> the two cards do NOT open the Knut block")
        bad += 1
    else:
        print(f"    -> both cards open the Knut block, at rows "
              f"{first_knut} and {first_knut + 1} of it")

    # The popup itself, so Basti can see it rather than read it.
    # THE INDEX IS LEFT ALONE while the popup is open: moving the combo onto a
    # built-in row selects it, which is a real chart build with no name typed.
    combo.showPopup()
    pump(app, 900)
    view = combo.view()
    view.scrollTo(combo.model().index(max(i1_i - 1, 0), 0),
                  QAbstractItemView.ScrollHint.PositionAtTop)
    pump(app, 700)
    shot(view.window(), "01-presets-dropdown-i1pro-group")
    combo.hidePopup()
    pump(app, 400)

    # --- 2. the ★ speech-bubble overlay ------------------------------------
    groups = [(g, [(_marked_overlay_label(k, lbl), k)
                   for (_c, lbl, k) in entries])
              for g, entries in BUILTIN_PRESET_GROUPS]
    report["overlay_headings"] = [g for g, _e in groups]
    popup = BuiltinPresetPopup(groups, win)
    popup.move(win.geometry().center())
    popup.show()
    pump(app, 1200)
    # The overlay caps itself at ten rows and the i1Pro group opens with seven
    # Pharmacist ones, so the heading and the two new cards do not fit in one
    # picture. Two shots: where the group starts, and where the cards are.
    tops = {r.text: r.top for r in popup._rows if r.kind == "header"}
    for tag, lift in (("a-where-the-i1pro-group-starts", 8),
                      ("b-both-cards-after-the-pharmacist-ones", 165)):
        popup._scroll_y = max(0, min(popup._max_scroll,
                                     tops[INSTRUMENT_LABELS["i1"]] - 8 + lift))
        popup.update()
        pump(app, 700)
        shot(popup, f"02{tag}-builtin-presets-overlay")
    popup.close()
    pump(app, 400)

    # --- 3. the other two lists --------------------------------------------
    cmp_groups = comparable_presets(settings)
    report["compare"] = [g for g, _i in cmp_groups]
    from ui.dialogs.ti2_relayout_dialog import _NewChartDialog
    d = _NewChartDialog(work, settings)
    # Keyed for display as "<instrument> <name>", so a photo card reads
    # "★ i1Pro 100x150mm-600p-4pages-Portrait-w7.5mm".
    starred = [n for n in d._preset_recipes
               if any(p.name in n for p in photo)]
    report["load_setup"] = starred
    if len(starred) != len(photo):
        print("    -> a photo card is MISSING from 'Load setup from preset'")
        bad += 1
    print(f"\n    'Compare with profile' groups: {report['compare']}")
    print(f"    'Load setup from preset' photo-card entries: {starred}")

    # --- 4. build both charts, from the dropdown ---------------------------
    print(f"\n    building {len(photo)} chart(s) through the real dropdown\n")
    for n, p in enumerate(photo, 1):
        target = f"PC-{p.slug}"
        tab._target_name_edit.setText(target)
        pump(app, 250)
        idx = combo.findData(p.key)
        assert idx >= 0, f"{p.key} is not in the dropdown"
        tab._margin_ti2 = None
        # EXACTLY WHAT A CLICK DOES, AND `setCurrentIndex` IS NOT IT. The tab
        # listens on `activated`, which Qt emits only for a real user pick.
        combo.setCurrentIndex(idx)
        combo.activated.emit(idx)
        pump(app, 300)
        ok = False
        for _ in range(240):
            pump(app, 250)
            if getattr(tab, "_margin_ti2", None):
                ok = True
                break
        if not ok:
            print(f"    [{n}/{len(photo)}] {p.name}: DID NOT BUILD")
            bad += 1
            continue
        pump(app, 900)

        # The layout panel, seeded from the preset — HIS margins, on screen.
        panel = tab._manual_layout_panel.get_recipe().to_dict()
        seeded = {k: panel.get(k) for k in
                  ("paper", "area_cols", "area_rows", "margin_top",
                   "margin_right", "margin_bottom", "margin_left",
                   "clip_border_width_mm")}
        want = {k: p.layout_recipe[k] for k in seeded}
        if seeded != want:
            print(f"    the layout panel came back wrong: {seeded} != {want}")
            bad += 1
        shot(win, f"0{2 + n}a-window-after-{p.slug}")
        shot(tab._manual_layout_panel, f"0{2 + n}b-layout-panel-{p.slug}")

        ti2 = Path(tab._margin_ti2)
        run_dir = ti2.parent
        pages = _tif_pages(run_dir)
        patches = _ti2_patches(ti2)
        # The geometry the app WROTE for the run, not the recipe it was handed.
        recipe_file = run_dir / f"{ti2.stem}.channels.json"
        paper_written, width_mm, height_mm = None, 0.0, 0.0
        if recipe_file.is_file():
            lay = json.loads(recipe_file.read_text(encoding="utf-8"))["layout"]
            rec = lay.get("recipe") or {}
            paper_written = rec.get("paper")
            first = (lay.get("patches") or [{}])[0]
            if first.get("w"):
                width_mm = round(first["w"] * 25.4 / lay["dpi"], 2)
                height_mm = round(first["h"] * 25.4 / lay["dpi"], 2)
        said_paper, said_patches, said_pages = (
            p.layout_recipe["paper"], p.patches, p.pages)
        said_width = p.patch_width_mm
        good = (patches == said_patches and len(pages) == said_pages
                and paper_written == said_paper
                and abs(width_mm - said_width) <= 0.5)
        bad += 0 if good else 1
        print(f"    [{n}/{len(photo)}] {p.name:<40} "
              f"built {patches:>4}p on {len(pages)} sheet(s) of "
              f"{paper_written} mm, patch {width_mm} x {height_mm} mm "
              f"(name says {said_width})  {'OK' if good else '<<< MISMATCH'}")
        report["charts"].append({
            "name": p.name, "key": p.key, "target": target,
            "said_paper": said_paper, "built_paper": paper_written,
            "said_patches": said_patches, "built_patches": patches,
            "said_pages": said_pages, "built_pages": len(pages),
            "said_patch_width_mm": said_width,
            "built_patch_width_mm": width_mm,
            "built_patch_height_mm": height_mm,
            "seeded_layout_panel": seeded,
            "run_dir": str(run_dir),
            "pages": [str(x) for x in pages],
        })

    shot(win, "05-window-final")
    SHOTS.mkdir(parents=True, exist_ok=True)
    (SHOTS / "drive-report.json").write_text(json.dumps(report, indent=1),
                                             encoding="utf-8")
    _sheets(report["charts"])
    print(f"\n    report: {SHOTS / 'drive-report.json'}")
    print(f"    mismatches: {bad}")
    win.close()
    pump(app, 400)
    return 1 if bad else 0


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)
    rc = run(app)
    print(f"\nscreenshots in {SHOTS}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
