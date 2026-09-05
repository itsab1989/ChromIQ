"""B10 — timing as felt (S04). One FRESH app launch per run.

    drive_B10_timing.py <fast|argyll|accurate> <m|h>

Manual, gamut source -S ClayRGB1998.icm (the mapping is what costs time),
924p chart. Every log line is stamped with its arrival time; afterwards the
percentage/ETA sequence is checked: does the number ever go backwards, how
long does each percentage sit, how long does "almost done" last, and how
far off is each ETA from the real remaining time.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.engine_challenge.harness import Harness            # noqa: E402
from scripts.engine_challenge.drive_B_common import (            # noqa: E402
    CHART_924, WORK_B, active_modal, button_named, buttons_of, click, grab,
    pick, sandbox, say, run_journey)

OUT = WORK_B / "B10"
OUT.mkdir(parents=True, exist_ok=True)
CLAY = "/Applications/Argyll/ref/ClayRGB1998.icm"
SEEN: list[tuple[str, str]] = []
PCT = re.compile(r"^(\d+)% · (?:(~\d+s left|~\d+ min left|almost done) · )?")


def journey(h, mode: str, quality: str):
    win, prof = h.win, h.win._tab_profile
    h.go_profile_tab("manual")
    yield 400
    pick(prof._m_gam_mode_combo, prof._m_gam_mode_combo.itemText(2)); prof._m_gam_path_edit.setText(CLAY)
    qi = [i for i in range(prof._m_qual_combo.count()) if prof._m_qual_combo.itemData(i) == quality][0]
    pick(prof._m_qual_combo, prof._m_qual_combo.itemText(qi))
    yield 200
    say(f"mode={mode} quality={prof._m_qual_combo.currentData()} gam={prof._m_gam_mode_combo.currentData()} {prof._m_gam_path_edit.text()}")
    prof._log.clear()
    t0 = time.monotonic()
    click(prof._build_btn)
    stamped: list[tuple[float, str]] = []
    n = 0
    title = None
    while True:
        el = time.monotonic() - t0
        lines = prof._log.toPlainText().splitlines()
        for ln in lines[n:]:
            stamped.append((round(el, 1), ln))
        n = len(lines)
        m = active_modal(h)
        if m is not None:
            yield 300
            title = m.windowTitle()
            grab(m, OUT / f"{mode}-{quality}-modal.png")
            b = button_named(m, "Done") or button_named(m, "Close") or (buttons_of(m) or [None])[-1]
            SEEN.append((title, b.text() if b else "?"))
            if b is not None:
                click(b)
            yield 300
            break
        if prof._build_btn.isEnabled() and not prof._engine_builder.is_running and not prof._runner.is_running and el > 2:
            break
        if el > 1500:
            say("!! timeout")
            break
        yield 100
    total = time.monotonic() - t0
    say(f"TOTAL {mode} q={quality}: {total:.1f}s; modal={title!r}; lines={len(stamped)}")
    (OUT / f"{mode}-{quality}-stamped.json").write_text(json.dumps(stamped, indent=0, ensure_ascii=False), encoding="utf-8")
    # analysis
    last_pct, backwards, dwell, etas = -1, [], {}, []
    prev_t, prev_p = None, None
    for t, ln in stamped:
        m = PCT.match(ln)
        if not m:
            continue
        p = int(m.group(1))
        if p < last_pct:
            backwards.append((t, last_pct, p))
        if prev_p is not None and p != prev_p:
            dwell[prev_p] = dwell.get(prev_p, 0.0) + (t - prev_t)
            prev_t = t
        if prev_p is None:
            prev_t = t
        prev_p = p
        last_pct = max(last_pct, p)
        if m.group(2):
            etas.append((t, p, m.group(2)))
    if prev_p is not None:
        dwell[prev_p] = dwell.get(prev_p, 0.0) + (total - prev_t)
    say(f"  percent went backwards: {backwards or 'never'}")
    say(f"  dwell per percentage (s): {json.dumps({k: round(v, 1) for k, v in sorted(dwell.items())})}")
    say(f"  final percentage before the modal: {last_pct}")
    ad = [t for t, p, e in etas if e == "almost done"]
    say(f"  'almost done' first at {ad[0] if ad else None}s, real remaining then {round(total - ad[0], 1) if ad else None}s")
    say("  ETA vs truth (t, pct, eta, real remaining):")
    seen_e = set()
    for t, p, e in etas:
        if (p, e) in seen_e:
            continue
        seen_e.add((p, e))
        say(f"    {t:6.1f}s  {p:3d}%  {e:>12}  real {total - t:5.1f}s")
    heads = [ln for t, ln in stamped if ln and not PCT.match(ln)]
    say(f"  non-percent lines: {heads[:4]} … {heads[-3:]}")


def main() -> int:
    mode, quality = sys.argv[1], sys.argv[2]
    h = Harness(sandbox(f"B10-{mode}-{quality}"))
    h.boot()
    h.make_project("Real-924", CHART_924)
    h.enable_engine(mode)
    h.open_project("Real-924")
    run_journey(h, journey(h, mode, quality), timeout=1600)
    say(f"dialogs I clicked: {SEEN}; watchdog: {h.modals_answered}; sandbox: {h.sandbox}")
    h.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
