#!/usr/bin/env python3
"""K43 (Knut, #182 5833695633), driven ON SCREEN: the larger demo presets in
"Which presets can be used for verification?".

    CHROMIQ_DEMO_PACK=<built package folder> \\
    python drive_k43_larger_demo_presets.py <out> <en|de>

The demo verification presets of the built package are installed as a user
installs them (the folder's contents copied into the sandbox's Create Chart
preset folder). Report-Limits-Every-Metric is opened on run1, Verification,
and the window is opened from Create Chart. The drive waits for every row to
be laid out and answered (the window redraws itself), writes every row's count
to ``preset-counts.json``, and photographs R16 FAIL, R16 PASS, L1 and the
78-patch control with their evenness lines in view, under the opening choice
(Any report type, All metrics), then L1 and R16 PASS under Custom ISO 12647-7
and under the read-only ISO 12647-7 values.

**NOBODY HAS TO CLICK.** The drive answers its own windows; the watchdog of
`drive_b42_k36` cancels anything else after three seconds and photographs it.
The pack is copied, never written.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

TREE = os.environ.get("CHROMIQ_TREE") or str(Path(__file__).resolve().parents[1])
sys.path.insert(0, TREE + "/scripts")
sys.path.insert(0, TREE)

OUT = Path(sys.argv[1]).resolve()
LANG = sys.argv[2] if len(sys.argv) > 2 else "en"
PROJECT = "Report-Limits-Every-Metric"
FOLDER = "Create Chart presets (verification demos)"
R16_FAIL = "Verify R16 FAIL"
R16_PASS = "Verify R16 PASS"
L1 = "Verify L1 control"
CONTROL = "Verify 00 control"


def _install_presets() -> Path:
    presets = OUT / "sandbox" / "presets"
    dest = presets / "Create Chart"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    os.environ["CHROMIQ_PRESETS_DIR"] = str(presets)
    pack = Path(os.environ["CHROMIQ_DEMO_PACK"]) / FOLDER
    for p in sorted(pack.iterdir()):
        if p.suffix in (".json", ".ti1"):
            shutil.copy2(p, dest / p.name)
    return dest


def script(d):
    import drive_b42_k36 as K36
    # the K40 driver reads its own command line when it is imported
    sys.argv = [sys.argv[0], str(OUT), LANG, "presets"]
    import drive_k40_presets_and_every_metric as K40
    from core.i18n import tr
    rec = d.record
    rec.update({"language": LANG, "tree": TREE, "mode": "ON SCREEN"})
    K36._install_watchdog(d, rec)
    d.open_project(PROJECT)
    d.set_bar(run="run1", run_type="Verification")
    d.goto_tab("chart")
    tab = d.win._tab_chart
    try:
        tab._user_switch_mode("manual")
    except Exception:                                     # noqa: BLE001
        pass
    yield 2500
    t0 = time.monotonic()
    d.later(tab._preset_verify_btn.click)
    yield 300
    dlg = None
    for _ in range(60):
        dlg = d.top_dialog("PresetVerificationDialog")
        if dlg is not None:
            break
        yield 100
    if dlg is None:
        d.note("THE WINDOW DID NOT OPEN")
        return
    rec["opened_after_s"] = round(time.monotonic() - t0, 2)
    dlg.resize(1400, 900)
    K40._select(dlg, R16_PASS)
    yield 300
    d.shot(dlg, f"{LANG}-01-at-once")
    t1 = time.monotonic()
    for _ in range(900):
        if not dlg._still_laying_out():
            break
        yield 200
    rec["answered_after_s"] = round(time.monotonic() - t1, 2)
    rec["figures"] = dlg._figures.text()
    d.note(f"every row answered {rec['answered_after_s']} s later; "
           f"{rec['figures']}")

    def counts(tag):
        rows = [K40._row_record(r) for r in dlg._rows]
        (d.out / f"preset-counts-{tag}.json").write_text(json.dumps(
            {"type": dlg.current_type(), "set": dlg.current_set(),
             "current": (K40._row_record(dlg._current)
                         if dlg._current else None),
             "rows": rows}, indent=2, ensure_ascii=False), encoding="utf-8")
        demo = {r["label"]: f"{r['answered']} of {r['asked']}"
                for r in rows if r["label"].startswith("Verify ")}
        rec[f"counts_{tag}"] = demo
        for k in (CONTROL, R16_FAIL, R16_PASS, L1):
            hit = [f"{lab}: {v}" for lab, v in demo.items()
                   if lab.startswith(k)]
            d.note(f"[{tag}] {hit}")

    counts("opening")
    even = tr("Maximum ΔE00, between two of the nine sheet areas")
    for want, name in ((R16_FAIL, "02-r16-fail"), (R16_PASS, "03-r16-pass"),
                       (L1, "04-l1-650-two-pages"),
                       (CONTROL, "05-control-78")):
        ok = K40._select(dlg, want)
        yield 700
        for _ in range(3):
            K40._scroll_detail_to(dlg, even)
            yield 400
        rec[f"detail_{name}"] = K40._detail(dlg) if ok else "(no such row)"
        d.shot(dlg, f"{LANG}-{name}")
    for sid, tag in (("custom_iso_12647_7", "custom-iso-12647-7"),
                     ("iso_12647_7", "iso-12647-7-read-only")):
        i = dlg._set_combo.findData(sid)
        if i < 0:
            d.note(f"no limit set {sid} in the window")
            continue
        dlg._set_combo.setCurrentIndex(i)
        yield 1500
        for _ in range(300):
            if not dlg._still_laying_out():
                break
            yield 200
        counts(tag)
        for want, name in ((L1, "l1"), (R16_PASS, "r16-pass")):
            K40._select(dlg, want)
            yield 700
            for _ in range(3):
                K40._scroll_detail_to(dlg, even)
                yield 400
            rec[f"detail_{tag}_{name}"] = K40._detail(dlg)
            d.shot(dlg, f"{LANG}-06-{tag}-{name}")
    dlg.reject()
    d._modal_closed()
    yield 1000


if __name__ == "__main__":
    _install_presets()
    from userdrive import Drive
    drive = Drive(OUT, projects=[PROJECT], language=LANG, size=(1500, 1000))
    rc = drive.run(script)
    print(f"rc={rc}")
    sys.exit(rc)
