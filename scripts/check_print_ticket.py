"""What did the printer driver actually receive? Read the CUPS job tickets.

Every job CUPS spools on macOS (and Linux) leaves a control file,
``/var/spool/cups/c<job-id>``, holding the job's attributes in IPP encoding.
That file is what the driver acts on, which is not necessarily what the print
dialog showed or what ChromIQ wrote (#200: a greyed-out Color Matching pane
proved nothing on a Canon PRO-4600 whose ticket still asked for vendor
matching).

For each recent job this script names the printer queue it went to, works out
which settings ChromIQ should have sent to THAT printer to keep its driver out
of colour management, and shows what arrived:

* ``AP_ColorMatchingMode = AP_ApplicationColorMatching``, Apple's key, on every
  printer;
* the printer's own "no colour management" option(s), found in its PPD by the
  same code the print paths use (``workflow.ppd_color.vendor_no_cm_settings``):
  Canon ``CNIJIntent2=1001``, the three HP "RGB Color" options, and so on.

Each is marked ``ok``, ``WRONG`` or ``MISSING``. The dotted
``AP.ColorMatchingMode`` (a PyObjC write that no driver reads) is flagged, and
every other colour-looking option in the job is listed, so a vendor spelling
ChromIQ does not know yet shows up instead of passing in silence.

The control files are readable by root only, and CUPS keeps them only while it
keeps job history, so run this soon after printing:

    sudo .venv/bin/python scripts/check_print_ticket.py          # 5 newest jobs
    sudo .venv/bin/python scripts/check_print_ticket.py -n 10
    .venv/bin/python scripts/check_print_ticket.py --file c00042  # a saved copy

ChromIQ's own code, written for #200 (2026-10-04). It reads the file with a
full IPP attribute parser (RFC 8010 section 3), so short values such as
``CNIJIntent2 = 6`` are read like any other.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from workflow.ppd_color import vendor_no_cm_settings_for_queue  # noqa: E402

SPOOL_DIRS = ("/private/var/spool/cups", "/var/spool/cups")
APPLE_KEY = "AP_ColorMatchingMode"
APPLE_OFF = "AP_ApplicationColorMatching"
DOTTED_KEY = "AP.ColorMatchingMode"
#: A control file smaller than this carries no job settings: it is the stub a
#: print dialog leaves when it was opened and cancelled.
STUB_BYTES = 2000
#: Option names that look like colour handling, for the "also in the job" list.
COLOURISH = re.compile(r"colou?r|intent|match|icc|profile|rgb|cm(?![a-z])",
                       re.IGNORECASE)

# IPP value tags whose value is an integer / boolean / text (RFC 8010 3.5.2).
_INT_TAGS = {0x21, 0x23}         # integer, enum
_BOOL_TAG = 0x22


def parse_ipp(data: bytes) -> dict[str, list[str]]:
    """Every attribute in an IPP message, name -> values (as text).

    Layout: version (2), operation/status (2), request-id (4), then attribute
    groups. A byte below 0x10 is a group delimiter (0x03 ends the message);
    anything else is a value tag followed by name-length, name, value-length,
    value. An empty name adds another value to the previous attribute.
    """
    attrs: dict[str, list[str]] = {}
    pos, last = 8, None
    end = len(data)
    while pos < end:
        tag = data[pos]
        pos += 1
        if tag == 0x03:
            break
        if tag < 0x10:
            continue                      # begin a new attribute group
        if pos + 2 > end:
            break
        (nlen,) = struct.unpack(">H", data[pos:pos + 2])
        pos += 2
        name = data[pos:pos + nlen].decode("utf-8", "replace")
        pos += nlen
        if pos + 2 > end:
            break
        (vlen,) = struct.unpack(">H", data[pos:pos + 2])
        pos += 2
        raw = data[pos:pos + vlen]
        pos += vlen
        if tag in _INT_TAGS and vlen == 4:
            value = str(struct.unpack(">i", raw)[0])
        elif tag == _BOOL_TAG and vlen == 1:
            value = "true" if raw[0] else "false"
        else:
            value = raw.decode("utf-8", "replace")
        if name:
            last = name
            attrs.setdefault(name, []).append(value)
        elif last is not None:
            attrs[last].append(value)
    return attrs


def queue_of(attrs: dict[str, list[str]]) -> str | None:
    """The printer queue the job went to, from its printer URI."""
    for key in ("job-printer-uri", "printer-uri"):
        for uri in attrs.get(key, []):
            name = uri.rstrip("/").rsplit("/", 1)[-1]
            if name:
                return name
    return None


def expected_settings(queue: str | None) -> list[tuple[str, str]]:
    """What ChromIQ sends to keep this printer's driver out of colour
    management: Apple's key, then the printer's own option(s) from its PPD."""
    pairs = [(APPLE_KEY, APPLE_OFF)]
    if queue:
        for key, value in vendor_no_cm_settings_for_queue(queue):
            if key != APPLE_KEY:
                pairs.append((key, value))
    return pairs


def report(path: str, data: bytes, ppd_lookup=expected_settings) -> list[str]:
    """The lines printed for one control file."""
    stamp = time.strftime("%Y-%m-%d %H:%M:%S",
                          time.localtime(os.path.getmtime(path))) \
        if os.path.exists(path) else "?"
    head = f"== {os.path.basename(path)}  {stamp}  {len(data)} bytes"
    if len(data) < STUB_BYTES:
        return [head + "  (stub from a cancelled dialog, no job settings)"]
    attrs = parse_ipp(data)
    queue = queue_of(attrs)
    title = (attrs.get("job-name") or ["?"])[0]
    lines = [head, f"   printer queue: {queue or '(not in file)'}   job: {title}"]
    expected = ppd_lookup(queue)
    checked = set()
    for key, want in expected:
        checked.add(key)
        got = attrs.get(key)
        if not got:
            lines.append(f"   MISSING  {key} (should be {want})")
        elif got[0] == want:
            lines.append(f"   ok       {key} = {got[0]}")
        else:
            lines.append(f"   WRONG    {key} = {got[0]} (should be {want})")
    if len(expected) == 1:
        lines.append("   note     no printer-specific colour option known for this "
                     "queue (no PPD found, or none recognised)")
    if DOTTED_KEY in attrs:
        lines.append(f"   !!       {DOTTED_KEY} = {attrs[DOTTED_KEY][0]} is present: "
                     "no driver reads the dotted name")
    others = sorted(k for k in attrs
                    if k not in checked and k != DOTTED_KEY and COLOURISH.search(k))
    for key in others:
        lines.append(f"   also     {key} = {', '.join(attrs[key])}")
    return lines


def control_files(count: int) -> list[str]:
    for spool in SPOOL_DIRS:
        files = glob.glob(os.path.join(spool, "c[0-9]*"))
        if files:
            return sorted(files, key=os.path.getmtime)[-count:]
    return []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("-n", type=int, default=5, help="how many recent jobs (default 5)")
    ap.add_argument("--file", action="append", default=[],
                    help="read this control file instead of the spool (repeatable)")
    args = ap.parse_args(argv)
    paths = args.file or control_files(args.n)
    if not paths:
        if not args.file and os.geteuid() != 0:
            print("The CUPS spool is readable by root only. Run with sudo:\n"
                  "  sudo .venv/bin/python scripts/check_print_ticket.py",
                  file=sys.stderr)
            return 1
        print("No CUPS job control files found (CUPS may have dropped its job "
              "history; print again and run this straight after).")
        return 0
    for path in paths:
        try:
            data = Path(path).read_bytes()
        except PermissionError:
            print(f"== {os.path.basename(path)}: permission denied, run with sudo",
                  file=sys.stderr)
            return 1
        print("\n".join(report(path, data)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
