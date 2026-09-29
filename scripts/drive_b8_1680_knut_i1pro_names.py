#!/usr/bin/env python3
"""B8-1680 on screen: Knut's new i1Pro and i1Pro 3 Plus preset names.

In a real window, sandboxed (userdrive): Create Chart > Manual, the preset
list opened at the i1Pro and at the i1Pro 3 Plus block, showing the renamed
rows and their markers; "Settings for built-in presets" with the ticks as a
fresh install has them; then one renamed preset of each instrument generated,
each chart's patches compared with the .ti1 Knut sent (#182 5872273862).

    CHROMIQ_LOG_DIR=<sandbox> CHROMIQ_KNUT_NEW=<folder of his exports> \\
        python scripts/drive_b8_1680_knut_i1pro_names.py <out>
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

I1 = "__chromiq_knut_i1_w75_a4_648p_1page_portrait_w7_5mm__"
P3 = "__chromiq_knut_p3_a4_308p_2pages_portrait_w16_0mm__"
#: The folder of Knut's exports: the .ti1 each generated chart is held to.
KNUT_NEW = Path(os.environ.get("CHROMIQ_KNUT_NEW") or (
    Path.home() / "Desktop/ChromIQ-430-stable-prep/knut-i1pro-names/new"))
GENERATE = (
    ("04-generated-i1pro-a4-648p", I1, "KnutI1B81680",
     "i1Pro-A4-648p-1page-Portrait-w7.5mm-Uniform 6x6x6-Edge Emphasis.ti1"),
    ("05-generated-i1pro3plus-a4-308p", P3, "KnutP3B81680",
     "i1Pro3 Plus-A4-308p-2pages-Portrait-w16.0mm-Uniform 5x5x5.ti1"),
)


def _rgb_rows(path: Path) -> list[tuple]:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    fmt = text.split("\nBEGIN_DATA_FORMAT\n", 1)[1].split("\nEND_DATA_FORMAT", 1)[0].split()
    body = text.split("\nBEGIN_DATA\n", 1)[1].split("\nEND_DATA", 1)[0]
    i = fmt.index("RGB_R")
    return sorted(tuple(round(float(v), 4) for v in ln.split()[i:i + 3])
                  for ln in body.splitlines() if ln.strip())


def _show_row(d, combo, key):
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
                   for p in TC.KNUT_PRESETS
                   if p.file_group in ("i1Pro", "i1Pro 3 Plus")
                   and not p.slug.startswith("pharm_")}
    # The first popup of a session is still being mapped when it is
    # photographed; open and close it once before the photographs.
    combo.showPopup()
    yield 1500
    combo.hidePopup()
    yield 800
    for shot, key in (("01-preset-list-i1pro", I1),
                      ("02-preset-list-i1pro3plus", P3)):
        if combo.findData(key) < 0:
            rec[shot] = "not listed"
            continue
        view = _show_row(d, combo, key)
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
    dlg.resize(1100, 820)
    dlg.show()
    yield 1200
    ticked = dlg.ticked()
    rec["settings_window"] = {
        "paper_filter": dlg.paper_filter(),
        "ticked": {k: (k in ticked) for k in rec["rows"]},
        "row_text": {},
    }
    for shot, key in (("03-settings-for-built-in-presets-i1pro", I1),
                      ("03b-settings-for-built-in-presets-i1pro3plus", P3)):
        for c in dlg._items():
            if str(c.data(0, Qt_KEY())) == key:
                dlg._tree.scrollToItem(c, dlg._tree.ScrollHint.PositionAtCenter)
                rec["settings_window"]["row_text"][key] = c.text(0)
                break
        yield 800
        d.shot(dlg, shot)
    dlg.reject()
    yield 800

    for shot, key, name, sent in GENERATE:
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
        sender = _rgb_rows(KNUT_NEW / sent)
        entry["preset_name"] = preset.name
        entry["combo_text"] = combo.currentText()
        entry["asset_is_his_file"] = (
            Path(resource_path(preset.ti1_asset)).read_bytes()
            == (KNUT_NEW / sent).read_bytes())
        if ti2s:
            got = _rgb_rows(ti2s[-1])
            entry.update({"patches": len(got), "sender": len(sender),
                          "same_patches": got == sender})
            tifs = sorted(ti2s[-1].parent.glob(ti2s[-1].stem + "_*.tif"))
            entry["pages"] = len(tifs) or (1 if ti2s[-1].with_suffix(".tif").exists() else 0)
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
