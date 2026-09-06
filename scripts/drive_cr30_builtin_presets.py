#!/usr/bin/env python3
"""Drive the REAL ChromIQ window over Knut's twenty CR30 built-in presets.

Basti, 2026-09-06: *"i want them listed for the cr30 in both preset dropdowns /
speechbubble overlay before the scanner section"*.

What this proves, on screen and not in a fixture:

1. the **Presets dropdown** in Create Chart → Manual lists a CR30 group, with
   its heading above the twenty rows and the Scanner heading BELOW it;
2. the **★ Built-in presets overlay** (the speech bubble) shows the same group
   in the same place;
3. the **Compare with profile** list (#66, Tools and the TI2 editor) and the
   New-chart **"Load setup from preset"** list carry them too, because all four
   read one registry;
4. **every one of the twenty builds the chart its name promises** when it is
   picked from the dropdown the way a user picks it: the patch count, the page
   count, the paper and the patch shape are read back off the files the app
   actually wrote.

Basti's preferences are copied to a throwaway .ini and his ChromIQ root is
replaced by a sandbox. Nothing of his is touched. Check afterwards with

    defaults read com.chromiq.ChromIQ custom_output_path

Usage::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-ct.ini \
        python scripts/drive_cr30_builtin_presets.py [--quick]

``--quick`` builds three charts instead of twenty (the listings are unaffected).
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
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from core.resource_path import resource_path                    # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"
SHOTS = Path.home() / "Desktop" / "beta 9" / "cr30-builtin-presets"


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
    """Every page the app wrote for this chart.

    A one-page chart is written as ``<stem>.tif`` with no number, a multi-page
    one as ``<stem>_01.tif`` … — so globbing only the numbered form counts a
    single-sheet chart as zero pages, which is how this driver first reported
    twenty perfectly good charts as failures."""
    return sorted(run_dir.glob("*.tif"))


def _ti2_patches(ti2: Path) -> int:
    txt = ti2.read_text(encoding="latin-1", errors="ignore")
    m = re.search(r"NUMBER_OF_SETS\s+(\d+)", txt)
    return int(m.group(1)) if m else 0


def _contact_sheet(charts: list[dict], cols: int = 5, cell: int = 460) -> None:
    """One sheet showing the first page of every chart that was built, captioned
    with what its name promised and what came out. A table proves the counts;
    this is so somebody can SEE that twenty different charts were made and that
    the hexagonal ones really are honeycombs."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("    (Pillow not installed, no contact sheet)")
        return
    if not charts:
        return
    pad, cap = 14, 46
    rows = -(-len(charts) // cols)
    sheet = Image.new("RGB", (cols * (cell + pad) + pad,
                              rows * (cell + cap + pad) + pad), "white")
    draw = ImageDraw.Draw(sheet)
    for i, c in enumerate(charts):
        if not c["pages"]:
            continue
        x = pad + (i % cols) * (cell + pad)
        y = pad + (i // cols) * (cell + cap + pad)
        im = Image.open(c["pages"][0]).convert("RGB")
        im.thumbnail((cell, cell))
        sheet.paste(im, (x + (cell - im.width) // 2, y))
        ok = (c["built_patches"] == c["said_patches"]
              and c["built_pages"] == c["said_pages"])
        draw.text((x, y + cell + 6), c["name"], fill="black")
        draw.text((x, y + cell + 20),
                  f"{c['built_patches']}p / {c['built_pages']} sheet(s) / "
                  f"{c['built_paper']} / {c['built_patch_width_mm']} mm "
                  f"{'OK' if ok else 'MISMATCH'}",
                  fill=("black" if ok else "red"))
    out = SHOTS / "05-contact-sheet-all-twenty.png"
    sheet.save(out)
    print(f"    saved {out.name}  ({sheet.width}x{sheet.height})")


def run(app, quick: bool) -> int:
    from core.settings import AppSettings

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq-cr30-"))
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

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import (KNUT_PRESETS, TabChart,
                                   comparable_presets)
    from ui.builtin_preset_popup import BuiltinPresetPopup
    TabChart._confirm_displacing_results = lambda self, *a, **k: True

    cr30 = [p for p in KNUT_PRESETS if p.slug.startswith("cr30_")]
    print(f"    {len(cr30)} CR30 presets in the registry")

    win = MainWindow(settings)
    win.show()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 600)
    tab._user_switch_mode("manual")
    pump(app, 1200)

    report: dict = {"dropdown": [], "overlay": [], "compare": [],
                    "load_setup": [], "charts": []}

    # --- 1. the Presets dropdown -------------------------------------------
    combo = tab._preset_combo
    listing = []
    for i in range(combo.count()):
        txt = combo.itemText(i)
        if not txt and combo.itemData(i) is None:
            listing.append(("---separator---", None))
        else:
            listing.append((txt, combo.itemData(i)))
    report["dropdown"] = [t for t, _d in listing]
    heads = [i for i, (t, d) in enumerate(listing)
             if d is None and t and t != "---separator---"]
    print("\n    Presets dropdown, group headings in order:")
    for i in heads:
        print(f"        [{i:4d}] {listing[i][0]}")
    cr_i = next(i for i in heads if "CR30" in listing[i][0])
    sc_i = next(i for i in heads if "Scanner" in listing[i][0])
    print(f"\n    CR30 heading at {cr_i}, Scanner heading at {sc_i} -> "
          f"{'CR30 IS BEFORE SCANNER' if cr_i < sc_i else 'WRONG ORDER'}")
    if cr_i > sc_i:
        win.close()
        return 1
    print("    the 20 rows under the CR30 heading:")
    for i in range(cr_i + 1, sc_i):
        if listing[i][1] is not None:
            print(f"        {listing[i][0]}")

    # The popup itself, so Basti can see it rather than read it. Two shots,
    # because 20 rows plus two headings do not fit in one popup: the top of the
    # group (what comes before it) and the bottom (what comes after it).
    # THE INDEX IS LEFT ALONE. Moving the combo onto a built-in row selects it,
    # which is a real chart build with no name typed yet — the first run of this
    # script did exactly that and left the tab mid-build with every panel greyed.
    from PyQt6.QtWidgets import QAbstractItemView
    for tag, row, where in (
            ("a-top-of-the-group", cr_i - 3,
             QAbstractItemView.ScrollHint.PositionAtTop),
            ("b-scanner-comes-after", sc_i + 2,
             QAbstractItemView.ScrollHint.PositionAtBottom)):
        combo.showPopup()
        pump(app, 700)
        view = combo.view()
        view.scrollTo(combo.model().index(max(row, 0), 0), where)
        pump(app, 600)
        shot(view.window(), f"01{tag}-presets-dropdown")
        combo.hidePopup()
        pump(app, 400)

    # --- 2. the ★ speech-bubble overlay ------------------------------------
    from ui.tabs.tab_chart import BUILTIN_PRESET_GROUPS, _marked_overlay_label
    groups = [(g, [(_marked_overlay_label(k, lbl), k)
                   for (_c, lbl, k) in entries])
              for g, entries in BUILTIN_PRESET_GROUPS]
    report["overlay"] = [g for g, _e in groups]
    popup = BuiltinPresetPopup(groups, win)
    popup.move(win.geometry().center())
    popup.show()
    pump(app, 1200)
    o_head = [g for g, _e in groups]
    print(f"\n    ★ overlay headings: {o_head}")
    if o_head.index(next(g for g in o_head if "CR30" in g)) \
            > o_head.index("Scanner"):
        print("    -> WRONG ORDER in the overlay")
        win.close()
        return 1
    print("    -> CR30 IS BEFORE SCANNER in the overlay")
    # Same two shots as the dropdown: the overlay caps itself at ten rows, so
    # the group's top and its bottom are photographed separately.
    tops = {r.text: r.top for r in popup._rows if r.kind == "header"}
    for tag, head, lift in (("a-top-of-the-group",
                             next(g for g in o_head if "CR30" in g), 60),
                            ("b-scanner-comes-after", "Scanner", 320)):
        popup._scroll_y = max(0, min(popup._max_scroll, tops[head] - lift))
        popup.update()
        pump(app, 700)
        shot(popup, f"02{tag}-builtin-presets-overlay")
    popup.close()
    pump(app, 400)

    # --- 3. the other two lists --------------------------------------------
    cmp_groups = comparable_presets(settings)
    report["compare"] = [g for g, _i in cmp_groups]
    cr_rows = next((items for g, items in cmp_groups if "CR30" in g), [])
    print(f"\n    'Compare with profile' groups: {[g for g, _ in cmp_groups]}")
    print(f"    CR30 charts offered there: {len(cr_rows)}")

    from ui.dialogs.ti2_relayout_dialog import _NewChartDialog
    d = _NewChartDialog(work, settings)
    starred = [n for n in d._preset_recipes if n.startswith("★ CR30 ")]
    report["load_setup"] = starred
    print(f"    'Load setup from preset' CR30 entries: {len(starred)}")

    # --- 4. build every chart, from the dropdown ---------------------------
    todo = cr30[:3] if quick else cr30
    print(f"\n    building {len(todo)} chart(s) through the real dropdown\n")
    bad = 0
    for n, p in enumerate(todo, 1):
        target = f"CT-{p.slug}"
        tab._target_name_edit.setText(target)
        pump(app, 250)
        idx = combo.findData(p.key)
        assert idx >= 0, f"{p.key} is not in the dropdown"
        tab._margin_ti2 = None
        # EXACTLY WHAT A CLICK DOES, AND `setCurrentIndex` IS NOT IT. The tab
        # listens on `activated`, which Qt emits only for a real user pick, so a
        # programmatic index change applies no preset at all and builds nothing.
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
            print(f"    [{n:2d}/{len(todo)}] {p.name}: DID NOT BUILD")
            bad += 1
            continue
        pump(app, 500)
        ti2 = Path(tab._margin_ti2)
        run_dir = ti2.parent
        pages = _tif_pages(run_dir)
        patches = _ti2_patches(ti2)
        # The geometry the app WROTE for the run, not the recipe it was handed.
        recipe_file = run_dir / f"{ti2.stem}.channels.json"
        hexed = paper_written = None
        width_mm = 0.0
        if recipe_file.is_file():
            try:
                lay = json.loads(recipe_file.read_text(encoding="utf-8"))["layout"]
                rec = lay.get("recipe") or {}
                hexed = bool(rec.get("hflag"))
                paper_written = rec.get("paper")
                first = (lay.get("patches") or [{}])[0]
                if first.get("w"):
                    width_mm = round(first["w"] * 25.4 / lay["dpi"], 2)
            except Exception:       # noqa: BLE001
                pass
        said_paper, said_patches, said_pages = (
            p.layout_recipe["paper"], p.patches, p.pages)
        said_hex = "Hexagonal" in p.name
        good = (patches == said_patches and len(pages) == said_pages
                and hexed == said_hex and paper_written == said_paper)
        bad += 0 if good else 1
        print(f"    [{n:2d}/{len(todo)}] {p.name:<46} "
              f"built {patches:>5}p on {len(pages)} sheet(s) of "
              f"{paper_written}, hex={hexed}, patch {width_mm} mm  "
              f"{'OK' if good else '<<< MISMATCH'}")
        report["charts"].append({
            "name": p.name, "key": p.key, "target": target,
            "said_paper": said_paper, "built_paper": paper_written,
            "said_patches": said_patches, "built_patches": patches,
            "said_pages": said_pages, "built_pages": len(pages),
            "said_hexagonal": said_hex, "built_hexagonal": hexed,
            "built_patch_width_mm": width_mm,
            "run_dir": str(run_dir),
            "pages": [str(x) for x in pages],
        })
        if n in (1, 6):
            shot(win, f"03-window-after-{p.slug}")

    shot(win, "04-window-final")
    SHOTS.mkdir(parents=True, exist_ok=True)
    (SHOTS / "drive-report.json").write_text(json.dumps(report, indent=1),
                                             encoding="utf-8")
    _contact_sheet(report["charts"])
    print(f"\n    report: {SHOTS / 'drive-report.json'}")
    print(f"    mismatches: {bad}")
    win.close()
    pump(app, 400)
    return 1 if bad else 0


def main() -> int:
    quick = "--quick" in sys.argv
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)
    rc = run(app, quick)
    print(f"\nscreenshots in {SHOTS}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
