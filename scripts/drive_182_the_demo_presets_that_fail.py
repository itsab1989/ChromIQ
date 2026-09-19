#!/usr/bin/env python3
"""#182, beta 23: the demo presets built to fail one metric each, ON SCREEN.

Knut, 2026-09-19: *"a user can place the presets in the
'…/Library/Preferences/ChromIQ/presets/Create Chart' folder (on mac), and
restart the app. The demo presets shall then be visible in the preset pulldown,
and when opening the 'Which presets can be verified?' window."*

So that is what this does, in that order and with nothing skipped: it builds
the downloadable folder with the package's own generator, COPIES ITS CONTENTS
into the presets folder the way a user copies them, starts the app, and
photographs

1. the Create Chart tab with a demo preset chosen in the pulldown;
2. one frame per demo preset, selected in the real window, with the real detail
   pane saying which metric it falls short of and what to do about it.

TWO PIXEL-IDENTICAL FRAMES of every window. Never QT_QPA_PLATFORM=offscreen:
this is a driver, not a test. Run it::

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-17/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-17/presets
    python scripts/drive_182_the_demo_presets_that_fail.py <out-dir>
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
sys.path.insert(0, str(ROOT / "scripts"))

from PyQt6.QtCore import Qt                                    # noqa: E402
from PyQt6.QtWidgets import QApplication                       # noqa: E402

import make_verification_preset_demos as GEN                   # noqa: E402
from drive_182_preset_verification_window import pump, twice    # noqa: E402

STRICT = ("t2_full_colour_check", "custom_iso_12647_7")


def install_like_a_user(pack: Path) -> "tuple[Path, list[str]]":
    """Copy the pack's files into the Create Chart preset folder, and nothing
    else. No app code is asked to import anything, because a user has no such
    door."""
    from core.preset_store import tab_dir
    dest = tab_dir("create_chart")
    dest.mkdir(parents=True, exist_ok=True)
    names = []
    for src in sorted(pack.iterdir()):
        if src.suffix in (".json", ".ti1"):
            shutil.copy2(src, dest / src.name)
            names.append(src.name)
    return dest, names


def detail_lines(dlg) -> "list[str]":
    out = []
    for i in range(dlg._detail_layout.count()):
        w = dlg._detail_layout.itemAt(i).widget()
        if w is not None and hasattr(w, "text"):
            out.append(w.text())
    return out


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    record: dict = {"frames": {}, "install": {}, "presets": {}}

    pack = Path(os.environ.get("CHROMIQ_DEMO_PRESET_PACK",
                               "/tmp/chromiq-17/pack")) / GEN.FOLDER
    GEN.build(pack)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    dest, names = install_like_a_user(pack)
    record["install"] = {"folder": str(dest), "files": names}
    print(f"installed {len(names)} files into {dest}", flush=True)

    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart

    settings = AppSettings()
    tab = TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    tab.resize(1280, 900)
    tab.setWindowTitle("ChromIQ, Create Chart")
    tab.show()
    pump(app, 1600)
    tab._manual_btn.click()
    pump(app, 1200)

    # -- 1. the pulldown holds them ---------------------------------------
    combo = tab._preset_combo
    listed = [combo.itemText(i) for i in range(combo.count())]
    mine = [t for t in listed if "Verify demo" in t]
    record["presets"]["in_the_pulldown"] = mine
    print(f"  {len(mine)} demo presets in the pulldown", flush=True)
    assert len(mine) == len(GEN.DEMOS), (len(mine), len(GEN.DEMOS))
    idx = next(i for i in range(combo.count())
               if GEN.DEMOS[1].name in combo.itemText(i))
    combo.setCurrentIndex(idx)
    pump(app, 900)
    from ui.fade_scroll import FadeScrollArea
    host = tab._preset_verify_btn.parent()
    while host is not None and not isinstance(host, FadeScrollArea):
        host = host.parent()
    if host is not None:
        host.ensureWidgetVisible(tab._preset_verify_btn, 0, 80)
        pump(app, 900)
    ok, why, d = twice(app, tab, out / "1-the-demos-in-the-pulldown.png")
    record["frames"]["1-the-demos-in-the-pulldown.png"] = [ok, why, d]
    print("  frame 1:", ok, why, flush=True)

    # -- the window, through the real button ------------------------------
    from ui.dialogs import preset_verification_dialog as PVD
    opened: list = []
    orig = PVD.PresetVerificationDialog.exec

    def _no_block(self):
        opened.append(self)
        self.show()
        return 0
    PVD.PresetVerificationDialog.exec = _no_block
    try:
        tab._preset_verify_btn.click()
        pump(app, 2500)
    finally:
        PVD.PresetVerificationDialog.exec = orig
    assert opened, "the button did not open the window"
    dlg = opened[0]
    dlg.resize(1180, 760)
    dlg._type_combo.setCurrentIndex(dlg._type_combo.findData(STRICT[0]))
    dlg._set_combo.setCurrentIndex(dlg._set_combo.findData(STRICT[1]))
    pump(app, 1200)

    def find(label):
        for i in range(dlg._tree.topLevelItemCount()):
            head = dlg._tree.topLevelItem(i)
            for j in range(head.childCount()):
                child = head.child(j)
                r = child.data(0, Qt.ItemDataRole.UserRole)
                if r is not None and r.label == label:
                    return head, child, r
        return None, None, None

    for k, demo in enumerate(GEN.DEMOS, start=2):
        head, item, row = find(demo.name)
        assert item is not None, demo.name
        from PyQt6.QtWidgets import QAbstractItemView
        dlg._tree.scrollToItem(
            item, QAbstractItemView.ScrollHint.PositionAtCenter)
        dlg._tree.setCurrentItem(item)
        pump(app, 700)
        lines = detail_lines(dlg)
        # BRING THE FAULT INTO THE PICTURE. The detail pane opens at the top,
        # and the "cannot answer" block is below the fold on a chart that
        # answers twelve rows first: the first run of this driver photographed
        # fifteen windows in which the sentence being proved was not visible.
        want = PVD.reason_line(demo.reason) if demo.reason else None
        for i in range(dlg._detail_layout.count()):
            w = dlg._detail_layout.itemAt(i).widget()
            if w is None or not hasattr(w, "text"):
                continue
            if (want is not None and w.text() == want) or (
                    want is None and w.text().startswith("Cannot be checked")):
                dlg._detail_scroll.ensureWidgetVisible(w, 0, 90)
                break
        pump(app, 500)
        rec = {
            "group": head.text(0),
            "patches": row.patches,
            "verdict_chip": item.text(3),
            "checked": row.assessment.checked,
            "claims": ([demo.reason] + list(demo.also)) if demo.reason else [],
            "window_said": sorted({w for _r, w in row.assessment.missing}),
            "rows_short": {r: w for r, w in row.assessment.missing},
            "detail_pane": lines,
        }
        record["presets"][demo.name] = rec
        print(f"  {demo.n:02d} {demo.name}: chip={item.text(3)!r} "
              f"said={rec['window_said']}", flush=True)
        name = out / f"{k}-demo-{demo.n:02d}.png"
        ok, why, d = twice(app, dlg, name)
        record["frames"][name.name] = [ok, why, d]
        print(f"    frame {k}:", ok, why, flush=True)

    (out / "measured.json").write_text(json.dumps(record, indent=2),
                                       encoding="utf-8")
    bad = [k for k, v in record["frames"].items() if not v[0]]
    print(f"\n{len(record['frames']) - len(bad)} of {len(record['frames'])} "
          f"frames proved; refused: {bad}", flush=True)
    dlg.close()
    tab.close()
    pump(app, 400)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
