#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Compare every line a recording shows the maker's program sending with the APP's allow-list.

Used twice in a driven-instrument integration (docs/adding_an_instrument.md, section 12b):

* before building: which recorded lines would the allow-list you drafted refuse, and which of
  them does the job need? (A line the job needs and the list refuses is a design question, not
  a reason to widen the list in passing.)
* when an owner's results arrive: does everything the maker's program did in that session fit
  what the app may send, and does the app's own builder make every computed line byte for byte
  the same from the same numbers?

For every host line it prints: the time, the line, the allow-list's verdict (its label, or
REFUSED with the reason), "rebuilt" (same / DIFFERENT / refused by the builder / -), and, with
--second-list, whether that list holds it too (a tester program's list, one line per row).

    python scripts/recording_vs_allowlist.py RECORDING.pcap
    python scripts/recording_vs_allowlist.py RECORDING.pcap --second-list tester_lines.txt
    python scripts/recording_vs_allowlist.py RECORDING.pcap --json verdicts.json

Exit code: 0 when every recorded host line is allowed and every computed line rebuilds byte for
byte, 1 when not (so a script can use it as a check), 2 when the file is not a recording.
A recording is private evidence: keep the output outside the repository. Reads the file only.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from recordings import capture  # noqa: E402
from recordings.plugins import plugin_names  # noqa: E402
from recording_timeline import load, paired  # noqa: E402


def verdicts(plugin, lines, second=None):
    out = []
    for ln, took in paired(plugin, lines):
        v = plugin.check(ln)
        try:
            built = plugin.rebuild(ln)
            rebuilt = "-" if built is None else ("same" if built == ln.text else "DIFFERENT")
            rebuilt_line = built
        except ValueError as exc:
            rebuilt, rebuilt_line = "refused", f"the app's builder refuses it: {exc}"
        out.append({
            "t": round(ln.t, 4), "line": ln.text, "allowed": v.allowed,
            "label": v.label, "motion": v.motion, "reason": v.reason, "notes": v.notes,
            "rebuilt": rebuilt, "rebuilt_line": rebuilt_line,
            "took_s": None if took is None else round(took, 4),
            "in_second_list": None if second is None else ln.text in second,
        })
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("recording", help="a .pcap / .pcapng USB recording")
    ap.add_argument("--plugin", default="i1io2-table",
                    help=f"device plug-in: {', '.join(plugin_names())}, module:Class or "
                         "file.py:Class (default i1io2-table)")
    ap.add_argument("--second-list", metavar="FILE",
                    help="a text file with one allowed line per row (a tester program's list), "
                         "compared as well")
    ap.add_argument("--json", metavar="FILE", help="also write every verdict as JSON")
    a = ap.parse_args(argv)
    second = None
    if a.second_list:
        second = {r.strip() for r in Path(a.second_list).read_text(encoding="utf-8").splitlines()
                  if r.strip() and not r.startswith("#")}
    try:
        plugin, _t0, _events, lines = load(a.recording, a.plugin)
    except capture.NotARecording as exc:
        print(str(exc), file=sys.stderr)
        return 2
    rows = verdicts(plugin, lines, second)
    print(f"# {Path(a.recording).name}: {len(rows)} host lines against {plugin.description}")
    print(f"{'t s':>9}  {'line':<22} {'second':6} {'rebuilt':<10} verdict")
    for r in rows:
        verdict = (r["label"] + (" (moves)" if r["motion"] else "")) if r["allowed"] \
            else f"REFUSED: {r['reason']}"
        sec = "-" if r["in_second_list"] is None else ("yes" if r["in_second_list"] else "NO")
        print(f"{r['t']:9.3f}  {r['line']:<22} {sec:6} {r['rebuilt'][:10]:<10} {verdict}")
        for n in r["notes"]:
            print(f"{'':11} note: {n}")
        if r["rebuilt"] in ("DIFFERENT", "refused"):
            print(f"{'':11} rebuilt: {r['rebuilt_line']}")
    refused = [r for r in rows if not r["allowed"]]
    different = [r for r in rows if r["rebuilt"] == "DIFFERENT"
                 or (r["allowed"] and r["rebuilt"] == "refused")]
    counts = Counter(r["label"] for r in rows if r["allowed"])
    print(f"\n# allowed: {len(rows) - len(refused)} of {len(rows)} "
          f"({', '.join(f'{k} x{v}' for k, v in sorted(counts.items()))})")
    print(f"# refused: {len(refused)}"
          + "".join(f"\n#   {r['t']:.3f} {r['line']}: {r['reason']}" for r in refused))
    print(f"# computed lines not rebuilt byte for byte: {len(different)}")
    if second is not None:
        print(f"# not in the second list: {sum(1 for r in rows if not r['in_second_list'])}")
    if a.json:
        Path(a.json).write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
        print(f"# written: {a.json}")
    return 1 if refused or different else 0


if __name__ == "__main__":
    sys.exit(main())
