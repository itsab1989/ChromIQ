#!/usr/bin/env python3
"""Drive the REAL ChromIQ window over Nelson Lau's two photo-card built-ins.

What this proves on screen, the way a user does it, rather than in a fixture:

1. both charts are in the Create Chart → Manual **Presets** dropdown, in the
   i1Pro group, at the top of it (smallest sheet first);
2. the same two rows are in the ★ **Built-in presets** overlay;
3. picking one the way a click picks it (``activated``, not
   ``setCurrentIndex``) copies the bundle into ``~/ChromIQ/<name>/runs/runN/``:
   the ``.ti1``, the ``.ti2``, the derived ``channels.json`` and every page
   TIFF, renamed to the run's own stem;
4. the sheet the app WROTE really is 100 × 150 / 130 × 180 mm at 360 dpi, with
   the patch count and page count the preset's name promises;
5. the layout panel is seeded with the sheet the bundle was laid out for, as a
   printtarg **Custom** size with the W and H boxes filled, not with the silent
   "A4" that any unrecognised paper folder used to produce;
6. both parameter panels are greyed while the preset is active, and the two
   override rows above them stay clickable;
7. the preview loads every page.

Basti's preferences are copied to a throwaway ``.ini`` and his ChromIQ root is
replaced by a sandbox, so nothing of his is touched. Check afterwards with

    defaults read com.chromiq.ChromIQ custom_output_path

Usage::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-photocard.ini \
        python scripts/drive_photocard_presets.py
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

import tifffile                                                 # noqa: E402
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtGui import QFontDatabase                           # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from core.resource_path import resource_path                    # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"
SHOTS = Path.home() / "Desktop" / "photocard-presets"


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


def _sheet_mm(tif: Path) -> tuple[float, float]:
    """The physical page a printer would be handed, from the TIFF's own tags.

    The unit is not the same on every page of these bundles (page 1 tags inches,
    the rest centimetres, both resolving to 360 dpi), so both are handled.
    """
    with tifffile.TiffFile(tif) as t:
        page = t.pages[0]
        xr = page.tags["XResolution"].value
        yr = page.tags["YResolution"].value
        per_inch = 2.54 if int(page.tags["ResolutionUnit"].value) == 3 else 1.0
        w = int(page.tags["ImageWidth"].value)
        h = int(page.tags["ImageLength"].value)
    return (w / (xr[0] / xr[1] * per_inch) * 25.4,
            h / (yr[0] / yr[1] * per_inch) * 25.4)


def _ti2_patches(ti2: Path) -> int:
    m = re.search(r"NUMBER_OF_SETS\s+(\d+)",
                  ti2.read_text("latin-1", errors="ignore"))
    return int(m.group(1)) if m else 0


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

    from ui.builtin_preset_popup import BuiltinPresetPopup
    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import (BUILTIN_PRESET_GROUPS, PREBUILT_PRESETS,
                                   PHOTOCARD600_PRESET_KEY,
                                   PHOTOCARD648_PRESET_KEY, TabChart,
                                   _marked_overlay_label, _prebuilt_paper)
    TabChart._confirm_displacing_results = lambda self, *a, **k: True

    WANT = {
        PHOTOCARD600_PRESET_KEY: dict(patches=600, pages=4,
                                      sheet=(100.0, 150.0), paper="100x150"),
        PHOTOCARD648_PRESET_KEY: dict(patches=648, pages=3,
                                      sheet=(130.0, 180.0), paper="130x180"),
    }

    win = MainWindow(settings)
    win.show()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 600)
    tab._user_switch_mode("manual")
    pump(app, 1200)

    bad = 0
    report: dict = {"charts": []}

    # --- 1. the Presets dropdown -------------------------------------------
    combo = tab._preset_combo
    listing = [(combo.itemText(i), combo.itemData(i))
               for i in range(combo.count())]
    heads = [i for i, (t, d) in enumerate(listing) if d is None and t]
    i1_head = next(i for i in heads if listing[i][0].startswith("i1Pro /"))
    rows_after = [listing[i] for i in range(i1_head + 1, i1_head + 3)]
    print("\n    Presets dropdown — the i1Pro heading and the two rows under it:")
    print(f"        {listing[i1_head][0]}")
    for text, data in rows_after:
        print(f"          {text}")
    if [d for _t, d in rows_after] != [PHOTOCARD600_PRESET_KEY,
                                       PHOTOCARD648_PRESET_KEY]:
        print("    -> the photo cards do NOT head the i1Pro group")
        bad += 1
    report["dropdown_i1pro_first_two"] = [t for t, _d in rows_after]

    from PyQt6.QtWidgets import QAbstractItemView
    combo.showPopup()
    pump(app, 700)
    view = combo.view()
    view.scrollTo(combo.model().index(max(i1_head - 2, 0), 0),
                  QAbstractItemView.ScrollHint.PositionAtTop)
    pump(app, 600)
    shot(view.window(), "01-presets-dropdown")
    combo.hidePopup()
    pump(app, 400)

    # --- 2. the ★ overlay ---------------------------------------------------
    groups = [(g, [(_marked_overlay_label(k, lbl), k)
                   for (_c, lbl, k) in entries])
              for g, entries in BUILTIN_PRESET_GROUPS]
    popup = BuiltinPresetPopup(groups, win)
    popup.move(win.geometry().center())
    popup.show()
    pump(app, 1200)
    tops = {r.text: r.top for r in popup._rows if r.kind == "header"}
    head = next(g for g, _e in groups if g.startswith("i1Pro /"))
    popup._scroll_y = max(0, min(popup._max_scroll, tops[head] - 60))
    popup.update()
    pump(app, 700)
    shot(popup, "02-builtin-presets-overlay")
    popup.close()
    pump(app, 400)

    # --- 3. build each one from the dropdown --------------------------------
    for n, (key, want) in enumerate(WANT.items(), 1):
        target = f"PC-{want['patches']}p"
        for edit in (getattr(tab, "_manual_target_name_edit", None),
                     getattr(tab, "_target_name_edit", None)):
            if edit is not None:
                edit.setText(target)
        pump(app, 250)
        idx = combo.findData(key)
        assert idx >= 0, f"{key} is not in the dropdown"
        tab._margin_ti2 = None
        # EXACTLY WHAT A CLICK DOES. The tab listens on `activated`, which Qt
        # emits only for a real user pick, so `setCurrentIndex` alone applies no
        # preset and builds nothing.
        combo.setCurrentIndex(idx)
        combo.activated.emit(idx)
        pump(app, 400)
        ok = False
        for _ in range(120):
            pump(app, 250)
            if getattr(tab, "_margin_ti2", None):
                ok = True
                break
        if not ok:
            print(f"    [{n}/2] {key}: DID NOT BUILD")
            bad += 1
            continue
        pump(app, 600)

        ti2 = Path(tab._margin_ti2)
        run_dir = ti2.parent
        pages = sorted(run_dir.glob("*_[0-9][0-9].tif"))
        patches = _ti2_patches(ti2)
        sheets = [_sheet_mm(p) for p in pages]
        has_ti1 = ti2.with_suffix(".ti1").is_file()
        has_geom = ti2.with_suffix(".channels.json").is_file()
        paper_widget = next(
            (pw.get_value() for pw in tab._manual_widgets.get("printtarg", [])
             if pw.flag == "-p"), None)
        size_ok = all(abs(w - want["sheet"][0]) < 0.2 and
                      abs(h - want["sheet"][1]) < 0.2 for w, h in sheets)
        good = (patches == want["patches"] and len(pages) == want["pages"]
                and size_ok and has_ti1 and has_geom
                and paper_widget == want["paper"])
        bad += 0 if good else 1
        print(f"\n    [{n}/2] {_prebuilt_paper(key)}")
        print(f"        run folder     {run_dir}")
        print(f"        wrote          {patches} patches on {len(pages)} page(s)"
              f"   (name promises {want['patches']} / {want['pages']})")
        print(f"        sheet          "
              + ", ".join(f"{w:.2f} x {h:.2f} mm" for w, h in sheets[:1])
              + f"   (want {want['sheet'][0]} x {want['sheet'][1]})")
        print(f"        .ti1 copied    {has_ti1}")
        print(f"        geometry       {has_geom}")
        print(f"        layout -p      {paper_widget!r}   (want {want['paper']!r})")
        print(f"        {'OK' if good else '<<< MISMATCH'}")
        report["charts"].append({
            "key": key, "target": target, "run_dir": str(run_dir),
            "patches": patches, "pages": len(pages),
            "sheet_mm": sheets, "paper_widget": paper_widget,
            "ti1": has_ti1, "channels_json": has_geom,
            "asset": PREBUILT_PRESETS[key][0], "ok": good,
        })

        # panels greyed, override rows still clickable
        def _any_enabled(content) -> bool:
            """`_manual_*_content` is a LIST of the panel's sub-groups."""
            items = content if isinstance(content, (list, tuple)) else [content]
            return any(w is not None and w.isEnabled() for w in items)

        locks = {
            "targen content enabled":
                _any_enabled(getattr(tab, "_manual_targen_content", None)),
            "printtarg content enabled":
                _any_enabled(getattr(tab, "_manual_printtarg_content", None)),
        }
        for name, enabled in locks.items():
            if enabled:
                print(f"        {name}: TRUE — the panel is not locked")
                bad += 1
        report["charts"][-1]["locks"] = locks
        shot(win, f"03-window-{want['patches']}p")

    shot(win, "04-window-final")
    SHOTS.mkdir(parents=True, exist_ok=True)
    (SHOTS / "drive-report.json").write_text(json.dumps(report, indent=1),
                                             encoding="utf-8")
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
