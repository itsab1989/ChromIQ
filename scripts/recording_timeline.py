#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Turn a USB recording of an instrument's own program into a timeline and a command list.

Step 2 of a driven-instrument integration (docs/adding_an_instrument.md, section 12b): before
anything is designed, see exactly what the maker's program sent, what the device answered and
how long each command took. Reads the recording only; never opens a device.

    python scripts/recording_timeline.py RECORDING.pcap                 # the whole timeline
    python scripts/recording_timeline.py RECORDING.pcap --brief         # polls hidden
    python scripts/recording_timeline.py RECORDING.pcap --commands      # one row per command
    python scripts/recording_timeline.py RECORDING.pcap --json out.json # lines as JSON
    python scripts/recording_timeline.py RECORDING.pcap --plugin path/to/my_device.py:MyDevice

--commands is where an allow-list starts: every distinct host line with how often it was sent,
when first, and the time from the line to its done answer (fewest, median, most). Build the
allow-list and the timeouts from THAT, never from a guess.

What is never printed: memory answers that hold a serial number and any data an instrument
sends (the plug-in redacts them). The output is still private evidence, because the timing and
the sequence belong to one person's session: keep it outside the repository.

Try it on an invented recording:

    python scripts/recordings/synthetic.py /path/to/new/folder/example.pcap
    python scripts/recording_timeline.py /path/to/new/folder/example.pcap
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from recordings import capture  # noqa: E402
from recordings.plugins import load_plugin, plugin_names  # noqa: E402


def load(path, plugin_spec):
    plugin = load_plugin(plugin_spec)
    t0, events = capture.read_events(path)
    plugin.assign_roles(events)
    return plugin, t0, events, plugin.lines(events, t0)


def paired(plugin, lines):
    """[(line, seconds from the host line to its done answer or None)] for host lines: the
    first answer with the same command id before that id is sent again."""
    res = []
    for i, ln in enumerate(lines):
        if ln.who != "host":
            continue
        cid = plugin.command_id(ln)
        took = None
        for later in lines[i + 1:]:
            if later.who == "host" and plugin.command_id(later) == cid:
                break
            if plugin.answer_to(later) == cid:
                took = later.t_end - ln.t
                break
        res.append((ln, took))
    return res


def timeline(plugin, events, lines, t0, brief=False):
    items = []
    for ln in lines:
        if brief and plugin.is_routine(ln):
            continue
        if brief and ln.who == "device" and ln.text.startswith(":!"):
            continue
        who = "HOST " if ln.who == "host" else "DEVICE"
        items.append((ln.t if ln.who == "host" else ln.t_end, who,
                      f"{ln.text:<24} {plugin.describe(ln)}"))
    if not brief:
        for ev in events:
            if ev.get("role") == "instrument":
                d = plugin.describe_instrument(ev)
                if d:
                    items.append((ev["t"] - t0, "INSTR", d))
    items.sort(key=lambda x: x[0])
    return [f"{t:9.3f}  {who:6} {text}".rstrip() for t, who, text in items]


def commands(plugin, lines):
    rows = {}
    for ln, took in paired(plugin, lines):
        r = rows.setdefault(ln.text, {"line": ln.text, "count": 0, "first_s": ln.t, "took": []})
        r["count"] += 1
        if took is not None:
            r["took"].append(took)
    out = []
    for r in sorted(rows.values(), key=lambda r: r["first_s"]):
        took = r.pop("took")
        r["took_min_s"] = round(min(took), 3) if took else None
        r["took_median_s"] = round(statistics.median(took), 3) if took else None
        r["took_max_s"] = round(max(took), 3) if took else None
        r["no_answer"] = r["count"] - len(took)
        out.append(r)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("recording", help="a .pcap / .pcapng USB recording")
    ap.add_argument("--plugin", default="i1io2-table",
                    help=f"device plug-in: {', '.join(plugin_names())}, module:Class or "
                         "file.py:Class (default i1io2-table)")
    ap.add_argument("--brief", action="store_true", help="hide polls and 'accepted' answers")
    ap.add_argument("--commands", action="store_true",
                    help="one row per distinct host line: count, first time, answer times")
    ap.add_argument("--json", metavar="FILE", help="also write the lines (or --commands) as JSON")
    a = ap.parse_args(argv)
    try:
        plugin, t0, events, lines = load(a.recording, a.plugin)
    except capture.NotARecording as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"# {Path(a.recording).name}: {len(events)} USB events, {len(lines)} device lines "
          f"({sum(1 for ln in lines if ln.who == 'host')} sent by the program), "
          f"plug-in {plugin.name}")
    if a.commands:
        rows = commands(plugin, lines)
        print(f"{'first s':>9}  {'count':>5}  {'answer s (min / median / max)':<30} line")
        for r in rows:
            took = ("-" if r["took_min_s"] is None else
                    f"{r['took_min_s']:.3f} / {r['took_median_s']:.3f} / {r['took_max_s']:.3f}")
            miss = f"  ({r['no_answer']} without a done answer)" if r["no_answer"] else ""
            print(f"{r['first_s']:9.3f}  {r['count']:5d}  {took:<30} {r['line']}{miss}")
        data = rows
    else:
        for row in timeline(plugin, events, lines, t0, brief=a.brief):
            print(row)
        data = [ln.__dict__ for ln in lines]
    if a.json:
        Path(a.json).write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
        print(f"# written: {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
