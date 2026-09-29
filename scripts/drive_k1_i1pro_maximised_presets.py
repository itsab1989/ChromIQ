#!/usr/bin/env python3
"""K1 (Knut, beta 34): his eight 7.5 mm i1Pro "Maximised - No Clip-border"
presets, driven ON SCREEN as a user picks them.

For each chart: Create Chart > Manual, type a printer-profile name, pick the
preset from the Presets pulldown, answer every window the app asks by its own
button, wait for the build, photograph the window with the preview, and read
back off the files the APP wrote (not off the recipe) the paper, patch count,
page count and patch width, against what the name promises. Then open "Which
presets can be used for verification?" and photograph the eight in its list.

    python scripts/drive_k1_i1pro_maximised_presets.py <out-dir> [N]

N limits the run to the first N charts (a probe). Nothing is patched out of
the app: a modal is answered by clicking its button (scripts/userdrive.py).
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import Drive                                   # noqa: E402

#: The button a user presses on each kind of question, in order of preference.
#: Whatever is asked is recorded and photographed; this only says which answer
#: carries the task forward (build the chart the user just picked).
PREFER = ("Create", "Build", "Generate", "Continue", "OK", "Yes")


def _answer_any(d, tag: str, seen: set) -> bool:
    """If a NEW modal is up, photograph it, record it, click the preferred
    button. Returns True if one was answered."""
    from PyQt6.QtWidgets import QAbstractButton
    w = d.modal()
    if w is None or not w.isVisible() or id(w) in seen:
        return False
    seen.add(id(w))
    d.pump(500)
    said = d.modal_text(w)
    d.shot(w, f"{tag}-modal-{len(seen)}")
    buttons = [b for b in w.findChildren(QAbstractButton)
               if b.isVisible() and b.text()]
    choice = None
    for want in PREFER:
        choice = next((b for b in buttons if b.text().replace("&", "")
                       .lower().startswith(want.lower())), None)
        if choice is not None:
            break
    d.record["modals"].append({"tag": tag, "class": type(w).__name__,
                               "text": said,
                               "buttons": [b.text() for b in buttons],
                               "clicked": choice.text() if choice else None})
    d.note(f"   [modal] {type(w).__name__}: "
           f"{said[:200].replace(chr(10), ' / ')!r} buttons="
           f"{[b.text() for b in buttons]} -> "
           f"{choice.text() if choice else 'NOTHING CLICKED'}")
    if choice is not None:
        choice.click()
    d.pump(500)
    return True


def _facts(ti2: Path) -> dict:
    run = ti2.parent
    txt = ti2.read_text(encoding="latin-1", errors="ignore")
    m = re.search(r"NUMBER_OF_SETS\s+(\d+)", txt)
    out = {"run_dir": str(run), "ti2": ti2.name,
           "patches": int(m.group(1)) if m else 0,
           "pages": len(sorted(run.glob(f"{ti2.stem}*.tif"))),
           "paper": None, "width_mm": None}
    geom = run / f"{ti2.stem}.channels.json"
    if geom.is_file():
        lay = json.loads(geom.read_text(encoding="utf-8")).get("layout") or {}
        out["paper"] = (lay.get("recipe") or {}).get("paper")
        q = (lay.get("patches") or [{}])[0]
        if q.get("w") and lay.get("dpi"):
            out["width_mm"] = round(q["w"] * 25.4 / lay["dpi"], 2)
    return out


def script(d, limit):
    from ui.tabs.tab_chart import KNUT_PRESETS
    todo = [p for p in KNUT_PRESETS if p.slug.startswith("i1_w75max_")]
    if limit:
        todo = todo[:limit]
    d.goto_tab("chart")
    tab = d.win._tab_chart
    tab._user_switch_mode("manual")
    yield 1500
    combo = tab._preset_combo
    listed = [combo.itemText(i) for i in range(combo.count())
              if combo.itemData(i) in {p.key for p in todo}]
    d.note(f"Presets pulldown lists {len(listed)} of {len(todo)}:")
    for t in listed:
        d.note(f"   {t}")
    # The pulldown opened on the eight, photographed.
    from PyQt6.QtWidgets import QAbstractItemView
    first = min(combo.findData(p.key) for p in todo)
    combo.showPopup()
    yield 800
    combo.view().scrollTo(combo.model().index(first, 0),
                          QAbstractItemView.ScrollHint.PositionAtTop)
    yield 700
    d.shot(combo.view(), "00-presets-pulldown")
    combo.hidePopup()
    yield 500

    results = []
    for n, p in enumerate(todo, 1):
        tag = f"{n:02d}-{p.paper}-{p.patches}p"
        d.note(f"\n[{n}] {p.name}")
        tab._target_name_edit.setText(f"K1-{p.paper}-{p.patches}p")
        yield 300
        before = tab._margin_ti2
        tab._margin_ti2 = None
        idx = combo.findData(p.key)
        assert idx >= 0, f"{p.name} not in the pulldown"
        # A click, queued so the app's own modal exec() runs for real.
        d.later(lambda i=idx: (combo.setCurrentIndex(i),
                               combo.activated.emit(i)))
        seen: set = set()
        t0 = time.monotonic()
        built = None
        while time.monotonic() - t0 < 120:
            yield 250
            if _answer_any(d, tag, seen):
                continue
            ti2 = tab._margin_ti2
            if ti2 and ti2 != before and not tab._runner.is_running \
                    and d.modal() is None:
                built = Path(ti2)
                break
        if built is None:
            d.note(f"   DID NOT BUILD within 120 s")
            results.append({"name": p.name, "built": False})
            continue
        yield 1500
        f = _facts(built)
        panel = tab._manual_layout_panel.get_recipe().to_dict()
        # What the panel WARNS about, asked of the app, and the stamp box.
        try:
            _all, overlaps = tab._engine_text_notes()
        except Exception as exc:                          # noqa: BLE001
            _all, overlaps = [f"(could not be read: {exc})"], []
        stamp_on = tab._manual_stamp_cmd_check.isChecked()
        f["stamp_settings_ticked"] = stamp_on
        f["layout_warnings"] = list(overlaps)
        d.note(f"   stamp ticked={stamp_on}; layout warnings={len(overlaps)}"
               + "".join(f"\n      ! {w[:160]}" for w in overlaps))
        ok = (f["patches"] == p.patches and f["pages"] == p.pages
              and f["paper"] == p.layout_recipe["paper"]
              and f["width_mm"] is not None
              and abs(f["width_mm"] - 7.5) <= 0.5
              and panel["clip_border"] is False
              and (panel["area_cols"], panel["area_rows"])
              == (p.layout_recipe["area_cols"], p.layout_recipe["area_rows"]))
        d.note(f"   built {f['patches']}p on {f['pages']} sheet(s) of "
               f"{f['paper']}, patch {f['width_mm']} mm; panel "
               f"{panel['paper']} {panel['area_cols']}x{panel['area_rows']} "
               f"margins T{panel['margin_top']} R{panel['margin_right']} "
               f"B{panel['margin_bottom']} L{panel['margin_left']} "
               f"clip={panel['clip_border']} -> {'OK' if ok else 'MISMATCH'}")
        results.append({"name": p.name, "built": True, "ok": ok,
                        "promised": {"paper": p.layout_recipe["paper"],
                                     "patches": p.patches, "pages": p.pages,
                                     "width_mm": 7.5},
                        "written": f,
                        "panel": {k: panel[k] for k in (
                            "paper", "area_cols", "area_rows", "margin_top",
                            "margin_right", "margin_bottom", "margin_left",
                            "clip_border", "clip_content_mode")}})
        d.record["charts"] = results
        d.shot(d.win, f"{tag}-preview")

    # -- "Which presets can be used for verification?" ---------------------
    d.note("\nWhich presets can be used for verification?")
    d.later(tab._open_preset_verification_window)
    yield 4000
    dlg = d.top_dialog("PresetVerificationDialog")
    if dlg is None:
        d.note("   the window did not open")
        return
    from PyQt6.QtCore import Qt
    tree = dlg._tree
    keys = {p.key: p for p in todo}
    found, first_item = [], None
    for i in range(tree.topLevelItemCount()):
        head = tree.topLevelItem(i)
        for j in range(head.childCount()):
            it = head.child(j)
            r = it.data(0, Qt.ItemDataRole.UserRole)
            if r is not None and getattr(r, "key", None) in keys:
                found.append([head.text(0), it.text(0), it.text(1),
                              it.text(2), it.text(3)])
                first_item = first_item or it
    d.record["verification_window_rows"] = found
    d.note(f"   lists {len(found)} of {len(todo)}:")
    for row in found:
        d.note(f"   {row}")
    if first_item is not None:
        tree.setCurrentItem(first_item)
        tree.scrollToItem(first_item,
                          tree.ScrollHint.PositionAtTop)
        yield 1200
    d.shot(dlg, "90-verification-window")
    dlg.reject()
    yield 800


if __name__ == "__main__":
    out = Path(sys.argv[1])
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    d = Drive(out)
    sys.exit(d.run(lambda dd: script(dd, limit)))
