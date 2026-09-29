#!/usr/bin/env python3
"""B8-1620 on screen: the "by Pharmacist" charts with a page layout.

In a real window, sandboxed (userdrive): Create Chart > Manual, the preset
list opened at the ColorMunki and at the i1Pro block, showing the new rows and
their markers; "Settings for built-in presets" with the ticks and the paper
filter as a fresh install has them; then two of the new presets generated (one
i1Pro, one ColorMunki), each chart's patches compared with the sender's .ti1.

    CHROMIQ_LOG_DIR=<sandbox> python scripts/drive_b8_1620_pharmacist_presets.py <out>
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

TREE = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, TREE + "/scripts")
sys.path.insert(0, TREE)
from userdrive import Drive                                    # noqa: E402
import drive_b42_k36 as K36                                    # noqa: E402

K36.DEADLINE_S = 900
# The "Auto-update preview is on" window is ChromIQ's own _InfoDialog, which
# the shared watchdog would let through; this driver never ticks that box, and
# if the window appears anyway the watchdog answers it (Close) and records it.
K36.OURS = set(K36.OURS) - {"_InfoDialog"}
# The settings window below is opened on purpose and closed by the driver.
K36.EXPECTED = set(K36.EXPECTED) | {"BuiltinPresetsShownDialog"}

LAYOUT_ONLY = "__chromiq_knut_pharm_cm_a4r_300p_1page_landscape_w9_0mm_tc300__"
I1_648 = "__chromiq_knut_pharm_i1_a4_648p_1page_portrait_w7_5mm_real_world__"
GENERATE = (
    ("04-generated-i1pro-a4-648p", I1_648, "PharmacistI1B81620"),
    ("05-generated-colormunki-a4-600p",
     "__chromiq_knut_pharm_cm_a4r_600p_2pages_landscape_w9_0mm_abw__",
     "PharmacistCMB81620"),
)


def _rgb_rows(path: Path) -> list[tuple]:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    fmt = text.split("\nBEGIN_DATA_FORMAT\n", 1)[1].split("\nEND_DATA_FORMAT", 1)[0].split()
    body = text.split("\nBEGIN_DATA\n", 1)[1].split("\nEND_DATA", 1)[0]
    i = fmt.index("RGB_R")
    return sorted(tuple(round(float(v), 4) for v in ln.split()[i:i + 3])
                  for ln in body.splitlines() if ln.strip())


def _show_row(d, combo, key, qapp):
    combo.showPopup()
    d.pump(1500)
    view = combo.view()
    idx = combo.findData(key)
    view.scrollTo(combo.model().index(idx, 0), view.ScrollHint.PositionAtCenter)
    d.pump(1500)
    return view


def script(d):
    rec = d.record
    assert os.environ.get("CHROMIQ_LOG_DIR"), "SANDBOX THE LOG FIRST"
    K36._install_watchdog(d, rec)
    from PyQt6.QtWidgets import QApplication
    qapp = QApplication.instance()
    rec["tree"] = TREE
    yield 600
    d.goto_tab("chart")
    tab = d.win._tab_chart
    yield 800
    tab._user_switch_mode("manual")
    yield 1500
    combo = tab._preset_combo
    import ui.tabs.tab_chart as TC
    rec["rows"] = {p.key: combo.itemText(combo.findData(p.key))
                   for p in TC.KNUT_PRESETS if p.slug.startswith("pharm_")}
    rec["rows_listed_directly"] = {k: combo.findData(k) >= 0
                                   for k in rec["rows"]}
    # The first popup of a session is still being mapped when it is
    # photographed; open and close it once before the photographs.
    combo.showPopup()
    yield 1500
    combo.hidePopup()
    yield 800
    for shot, key in (("01-preset-list-i1pro", I1_648),
                      ("02-preset-list-colormunki", LAYOUT_ONLY),
                      ("02b-preset-list-colormunki-again", LAYOUT_ONLY)):
        if combo.findData(key) < 0:
            rec[shot] = "not listed"
            continue
        view = _show_row(d, combo, key, qapp)
        d.shot(view, shot)
        combo.hidePopup()
        yield 600

    # "Settings for built-in presets", built as the gear button builds it, and
    # shown instead of exec()'d so this driver never blocks on it.
    from core.curated_presets import paper_filter_on, shown_keys
    from ui.dialogs.builtin_presets_shown_dialog import BuiltinPresetsShownDialog
    dlg = BuiltinPresetsShownDialog(
        tab._curated_dialog_groups(),
        shown_keys(tab._settings, TC.BUILTIN_PRESET_KEYS), tab,
        facts=TC.builtin_preset_facts(), folder=tab._file_mgr.root_dir(),
        paper_filter=paper_filter_on(tab._settings))
    dlg.show()
    yield 1200
    ticked = dlg.ticked()
    rec["settings_window"] = {
        "paper_filter": dlg.paper_filter(),
        "new_ticked": {k: (k in ticked) for k in rec["rows"]},
    }
    for c in dlg._items():
        if str(c.data(0, Qt_KEY())) == LAYOUT_ONLY:
            dlg._tree.scrollToItem(c, dlg._tree.ScrollHint.PositionAtCenter)
            break
    yield 800
    d.shot(dlg, "03-settings-for-built-in-presets")
    dlg.reject()
    yield 800

    for shot, key, name in GENERATE:
        entry = rec.setdefault("generated", {}).setdefault(shot, {})
        if tab._manual_target_name_edit is not None:
            tab._manual_target_name_edit.setText(name)
        yield 300
        before = time.time()
        idx = combo.findData(key)
        entry["found"] = idx >= 0
        if idx < 0:
            continue
        combo.setCurrentIndex(idx)
        combo.activated.emit(idx)
        yield 30000
        ti2s = sorted((p for p in d.work.rglob("*.ti2")
                       if p.stat().st_mtime >= before and name in str(p)),
                      key=lambda p: p.stat().st_mtime)
        entry["ti2"] = str(ti2s[-1]) if ti2s else None
        preset = TC.KNUT_PRESETS_BY_KEY[key]
        from core.resource_path import resource_path
        sender = _rgb_rows(Path(resource_path(preset.ti1_asset)))
        if ti2s:
            got = _rgb_rows(ti2s[-1])
            entry.update({"patches": len(got), "sender": len(sender),
                          "same_patches": got == sender})
            tifs = sorted(ti2s[-1].parent.glob(ti2s[-1].stem + "_*.tif"))
            entry["pages"] = len(tifs) or (1 if ti2s[-1].with_suffix(".tif").exists() else 0)
        entry["stamp_settings"] = bool(tab._manual_stamp_cmd_check.isChecked()) \
            if getattr(tab, "_manual_stamp_cmd_check", None) is not None else None
        d.shot(d.win, shot)
        yield 800


def Qt_KEY():
    from ui.dialogs.builtin_presets_shown_dialog import _KEY_ROLE
    return _KEY_ROLE


def main() -> int:
    out = Path(sys.argv[1])
    d = Drive(out, projects=[], language="en", appearance="light")
    rc = d.run(script)
    (out / "record.json").write_text(
        json.dumps(d.record, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8")
    print(f"rc={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
