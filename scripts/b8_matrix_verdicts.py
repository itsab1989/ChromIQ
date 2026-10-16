#!/usr/bin/env python3
"""VERDICTS.md from the on-screen run of ``scripts/drive_b8_matrix.py``.

    python scripts/b8_matrix_verdicts.py <report folder>

One row per check (a patch of a scenario at one moment): the case, the
condition, the limits, the expected outline and card, what the window
showed, the photograph and the verdict. A check passes when the outline the
preview drew AND the colour in the photograph are the expected ones, every
sentence the specification names is on the card in its order (figures
within 0.01), nothing that must not be there is, and the demo data produced
the intended input (each test triggered or not). Verdicts the specification
does not decide are given by hand in ``JUDGED`` below, with the reason.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

#: Checks whose verdict is not PASS/FAIL by the table alone, (scenario,
#: stage, loc) -> (verdict, reason).
JUDGED: dict = {
    # ("E07-live", "right-after", "A1") was NOT COVERED BY SPEC until Basti
    # confirmed it on 2026-10-16 (item 11): a Preferences change during a
    # measurement takes effect from the next strip read. It is an ordinary
    # check now (UMM 10.12, "a Preferences change during a measurement").
}

#: Rows of 10.12.5 with no reachable state, and how they are covered.
IMPOSSIBLE = [
    ("17", "R* + Y-sim", "S17: the unsettled suspect A1 stays red as row 15 "
     "and is no similar patch for J1, which stays red (row 12)"),
    ("19", "Y-re + R/R*/Y-sim", "one re-read confirms both tests: S18 shows "
     "LIMIT_YELLOW and NB_YELLOW on one card"),
    ("20", "R/Y-sim/Y-learn + Y-re", "same as 19 (S18, S29)"),
]


def short(t: str, n: int = 90) -> str:
    t = " ".join(str(t).split())
    return t if len(t) <= n else t[:n - 1] + "…"


def main() -> int:
    report = Path(sys.argv[1]).resolve()
    data = json.loads((report / "results.json").read_text(encoding="utf-8"))
    rows, fails, notcov, details = [], [], [], []
    n_pass = 0
    for sc in data["scenarios"]:
        if "error" in sc:
            rows.append(f"| {sc['id']} | did not run | | | | | | FAIL |")
            fails.append((sc["id"], "", "the scenario raised", sc["error"][-300:]))
            continue
        lim = (f"{sc['kind']}, PE {sc['pe']:g}, NB {sc['nb']:g}"
               f"{'' if sc['nb_on'] else ' (off)'}, radius {sc['radius']:g}, "
               f"T {sc['tol']:g}, strip test {'on' if sc['strip_test'] else 'off'}"
               f"{', patch by patch' if sc['pbp'] else ''}"
               f"{', ' + sc['appearance'] if sc['appearance'] != 'light' else ''}"
               f"{', later profile' if sc['mode'] == 'later' else ''}")
        for o in sc["observed"]:
            key = (sc["id"], o["stage"], o["loc"])
            m = o["match"]
            verdict = "PASS" if o["pass"] else "FAIL"
            reason = ""
            if key in JUDGED:
                verdict, reason = JUDGED[key]
            elif not o["pass"]:
                bits = []
                if not o["outline_ok"]:
                    bits.append(f"outline {o['drawn']} / photo "
                                f"{o['photo_outline']}, expected "
                                f"{o['expect_outline']}")
                if not o["inputs_ok"]:
                    bits.append(f"DEMO DATA: inputs pe {o['pe_input']} nb "
                                f"{o['nb_input']}, wanted {o['want_pe']} "
                                f"{o['want_nb']}")
                for k, label in (("missing", "missing"), ("order", "out of order"),
                                 ("numbers", "other figures"),
                                 ("present_absent", "must not be there")):
                    if m.get(k):
                        bits.append(f"{label}: " + " | ".join(m[k]))
                if o.get("same_as_session") is False:
                    bits.append("card differs from the one in the session")
                reason = "; ".join(bits)
            if verdict == "PASS":
                n_pass += 1
            elif verdict == "FAIL":
                fails.append((sc["id"], o["loc"], o["stage"], reason))
            else:
                notcov.append((sc["id"], o["loc"], o["stage"], reason))
            exp_card = ("(not specified: outline only)" if m.get(
                "card_not_specified") else
                f"{len(o['expect_card'])} sentences" if o["expect_card"]
                else "no outline lines")
            observed = (f"{o['drawn']} (photo {o['photo_outline']}); "
                        f"PE {o['pe_state'] or '—'} / NB {o['nb_state'] or '—'}"
                        f"; card {'as specified' if m['ok'] else 'differs'}")
            shot = Path(o["card_shot"]).name
            case = (f"35 ({o['case']})" if o["stage"] == "reopened"
                    else o["case"])
            rows.append(
                f"| {case} | {sc['id']} {o['stage']} {o['loc']}: "
                f"{short(sc['title'], 70)}{(' — ' + short(o['note'], 60)) if o['note'] else ''} "
                f"| {lim} | {o['expect_outline']} | {exp_card} | {observed} "
                f"| {shot} | {verdict} |")
            details.append((sc["id"], o, verdict, reason))
        sc_sum = sc.get("summary_check")
        if sc_sum is not None:
            v = "PASS" if sc_sum["ok"] else "FAIL"
            if v == "PASS":
                n_pass += 1
            else:
                fails.append((sc["id"], "summary", "", str(sc_sum)))
            cw = sc.get("closing_window") or {}
            shot = Path(cw["shot"]).name if cw.get("shot") else "(text only)"
            rows.append(f"| closing | {sc['id']} closing window summary | {lim} "
                        f"| — | {short(' / '.join(sc_sum['lines']), 120) or '(no lines)'} "
                        f"| {'as specified' if sc_sum['ok'] else sc_sum} | {shot} | {v} |")
    for case, what, how in IMPOSSIBLE:
        rows.append(f"| {case} | impossible: {what} | | — | — | {how} | | PASS (impossible) |")
        n_pass += 1
    out = ["# Verdicts: every combination of the two misread tests, on screen",
           "",
           f"Run {data['started']} on `{data['tree']}`, by "
           "`scripts/drive_b8_matrix.py` with the demo data of "
           "`scripts/b8_matrix_demo.py`. Every check is a real window, "
           "photographed by its id (`shots/`).",
           "",
           f"**{n_pass} PASS, {len(fails)} FAIL, {len(notcov)} NOT COVERED BY "
           "SPEC.**", ""]
    if fails:
        out += ["## FAIL", ""]
        out += [f"* **{a} {b} {c}**: {d}" for a, b, c, d in fails]
        out.append("")
    if notcov:
        out += ["## NOT COVERED BY SPEC", ""]
        out += [f"* **{a} {b} {c}**: {d}" for a, b, c, d in notcov]
        out.append("")
    obs = report / "OBSERVATIONS.md"
    if obs.exists():
        out += [obs.read_text(encoding="utf-8").strip(), ""]
    out += ["## The table", "",
            "Case = row of UMM 10.12.5 (or E.. edge case). Expected card: "
            "the specification's sentences, in order (listed per check under "
            "*The cards* below).", "",
            "| case | check | limits | expected outline | expected card | "
            "observed | photograph | verdict |",
            "|---|---|---|---|---|---|---|---|"] + rows
    out += ["", "## The cards", ""]
    for sid, o, verdict, reason in details:
        out.append(f"### {sid} {o['stage']} {o['loc']} (case {o['case']}): {verdict}")
        if reason:
            out.append(f"*{reason}*")
        out.append("")
        if o["expect_card"]:
            out.append("Expected, in order:")
            out += [f"1. {short(x.replace(chr(0) + 'NUM' + chr(0), 'ΔE*ab #').replace(chr(0), '`'), 400)}"
                    for x in o["expect_card"]]
        if o["absent"]:
            out.append("")
            out.append("Must not be on it: " + "; ".join(f"“{a}”" for a in o["absent"]))
        out.append("")
        body = o["card_text"]
        i = body.find("──")
        out.append("Shown (from the outline section): "
                   + (short(body[i:], 1500) if i >= 0 else "(no outline section)"))
        out.append("")
    (report / "VERDICTS.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"{n_pass} PASS, {len(fails)} FAIL, {len(notcov)} NOT COVERED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
