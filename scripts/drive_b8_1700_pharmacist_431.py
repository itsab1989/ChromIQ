#!/usr/bin/env python3
"""B8-1700 on screen: the five "by Pharmacist" charts of 4.3.1.

In a real window, sandboxed (userdrive): Create Chart > Manual, the preset list
opened at each new row, then each of the five chosen from the list and built,
each chart's patches compared with the .ti1 Knut attached (the SENDER'S file,
not the bundled copy), and the four withdrawn prebuilt images looked for in
the list.

    CHROMIQ_LOG_DIR=<sandbox> python scripts/drive_b8_1700_pharmacist_431.py <out> <sender-folder>
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
K36.OURS = set(K36.OURS) - {"_InfoDialog"}

SENDER = Path(sys.argv[2]) if len(sys.argv) > 2 else None

#: (photograph, key, project name, the sender's file stem)
FIVE = (
    ("01-colormunki-a3plus-924p",
     "__chromiq_knut_pharm_cm_a3plus_924p_1page_landscape_w14_0mm_ergonomical__",
     "PharmCMA3Plus924",
     "ColorMunki-A3Plus-924p-1page-Landscape-w14.0mm-Ergonomical target by Pharmacist"),
    ("02-colormunki-a4-624p",
     "__chromiq_knut_pharm_cm_a4_624p_2pages_portrait_w14_0mm_ergonomical__",
     "PharmCMA4624",
     "ColorMunki-A4-624p-2pages-Portrait-w14.0mm-Ergonomical target by Pharmacist"),
    ("03-colormunki-a3-725p",
     "__chromiq_knut_pharm_cm_a3_725p_1page_landscape_w14_0mm_ergonomical__",
     "PharmCMA3725",
     "ColorMunki-A3-725p-1page-Landscape-w14.0mm-Ergonomical target by Pharmacist"),
    ("04-i1pro-4x6in-600p",
     "__chromiq_knut_pharm_i1_4x6in_600p_4pages_w7_5mm_real_world__",
     "PharmI14x6600",
     "i1Pro-4x6in-600p-4pages-w7.5mm-(standard quality)-Real World Target-by Pharmacist"),
    ("05-i1pro-5x7in-702p",
     "__chromiq_knut_pharm_i1_5x7in_702p_3pages_w8_0mm_real_world__",
     "PharmI15x7702",
     "i1Pro-5x7in-702p-3pages-w8.0mm-(standard quality)-Real World Target-by Pharmacist"),
)
REMOVED = ("__chromiq_photocard600_builtin__", "__chromiq_photocard648_builtin__",
           "__chromiq_tc924_cm_a3_builtin__", "__chromiq_abw702_builtin__")


def _rgb_rows(path: Path) -> list[tuple]:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    fmt = text.split("\nBEGIN_DATA_FORMAT\n", 1)[1].split("\nEND_DATA_FORMAT", 1)[0].split()
    body = text.split("\nBEGIN_DATA\n", 1)[1].split("\nEND_DATA", 1)[0]
    i = fmt.index("RGB_R")
    return sorted(tuple(round(float(v), 4) for v in ln.split()[i:i + 3])
                  for ln in body.splitlines() if ln.strip())


def script(d):
    rec = d.record
    assert os.environ.get("CHROMIQ_LOG_DIR"), "SANDBOX THE LOG FIRST"
    assert SENDER is not None and SENDER.is_dir(), "name the sender's folder"
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
    rec["removed_rows_found"] = {k: combo.findData(k) for k in REMOVED}
    rec["new_rows"] = {key: combo.itemText(combo.findData(key))
                       for _s, key, _n, _f in FIVE}
    # The first popup of a session is still being mapped when it is
    # photographed; open and close it once before the photographs.
    combo.showPopup()
    yield 1500
    combo.hidePopup()
    yield 800
    for shot, key in (("00a-preset-list-colormunki", FIVE[1][1]),
                      ("00b-preset-list-colormunki-a3", FIVE[2][1]),
                      ("00c-preset-list-i1pro", FIVE[3][1])):
        idx = combo.findData(key)
        if idx < 0:
            rec[shot] = "not listed"
            continue
        combo.showPopup()
        yield 1500
        view = combo.view()
        view.scrollTo(combo.model().index(idx, 0), view.ScrollHint.PositionAtCenter)
        yield 1200
        d.shot(view, shot)
        combo.hidePopup()
        yield 600

    for shot, key, name, stem in FIVE:
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
        sender = _rgb_rows(SENDER / f"{stem}.ti1")
        preset = TC.KNUT_PRESETS_BY_KEY[key]
        entry["preset_row"] = combo.itemText(combo.currentIndex())
        entry["paper_field"] = tab._manual_get("printtarg", "-p", None)
        entry["instrument_field"] = tab._manual_get("printtarg", "-i", None)
        entry["pages_named"] = preset.pages
        if ti2s:
            got = _rgb_rows(ti2s[-1])
            entry.update({"patches": len(got), "sender": len(sender),
                          "same_patches": got == sender})
            tifs = sorted(ti2s[-1].parent.glob(ti2s[-1].stem + "_*.tif"))
            entry["pages"] = len(tifs) or (
                1 if ti2s[-1].with_suffix(".tif").exists() else 0)
            txt = ti2s[-1].read_text(encoding="utf-8", errors="replace")
            for kw in ("PAPER_SIZE", "TARGET_INSTRUMENT"):
                for ln in txt.splitlines():
                    if ln.startswith(kw):
                        entry[kw] = ln.split(None, 1)[1].strip('"')
        d.shot(d.win, shot)
        yield 800


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
