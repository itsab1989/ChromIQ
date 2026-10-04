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
``CNIJIntent2 = 6`` are read like any other. The layout was checked against
libcups 2.3.4 itself: a ticket encoded by ``cupsEncodeOptions2`` (as ``lp -o``
does) and written by ``ippWriteIO`` with no parent (as cupsd saves a job)
parses to the values ``ippAttributeString`` prints. Every file is parsed, small
ones too: a job sent with ``lp`` (ChromIQ's direct route) can be well under
1 KB and still carry every setting. cupsd writes no control file at all for a
job on a temporary (driverless, auto-created) queue.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import struct
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from workflow.ppd_color import vendor_no_cm_settings_for_queue  # noqa: E402

SPOOL_DIRS = ("/private/var/spool/cups", "/var/spool/cups")
APPLE_KEY = "AP_ColorMatchingMode"
APPLE_OFF = "AP_ApplicationColorMatching"
DOTTED_KEY = "AP.ColorMatchingMode"
#: Option names that look like colour handling, for the "also in the job" list.
#: ``CM`` counts in capitals anywhere (Epson ``EPIJ_CMat``), in lower case only
#: as a word end, so "cm" inside an ordinary word does not.
COLOURISH = re.compile(r"(?i:colou?r|intent|match|icc|profile|rgb|cm(?![a-z]))|CM")

#: The IPP group a printer driver's options travel in. cupsd builds a filter's
#: option string (scheduler/job.c, get_options) from attributes in the JOB
#: group only, and skips these value types there: no-value, mimeMediaType,
#: name/textWithLanguage, uri (but job-uuid), uriScheme and collections. A key
#: outside the job group, or of one of those types, never reaches the driver.
#: Read from the CUPS source, not measured on a printed job.
JOB_GROUP = 0x02
_NOT_HANDED_TO_DRIVER = {0x13, 0x49, 0x35, 0x36, 0x45, 0x46, 0x34}
_GROUP_NAMES = {0x01: "operation", 0x02: "job", 0x04: "printer",
                0x05: "unsupported", 0x06: "subscription",
                0x07: "event-notification", 0x09: "document"}
_OUT_OF_BAND = {0x10: "(unsupported)", 0x12: "(unknown)", 0x13: "(no-value)",
                0x15: "(not-settable)", 0x16: "(delete-attribute)",
                0x17: "(admin-define)"}
_BEG_COLLECTION, _END_COLLECTION, _MEMBER_NAME = 0x34, 0x37, 0x4A
_EXTENSION = 0x7F


class Ticket:
    """One parsed control file.

    ``attrs``: name -> values (as text) over every group; ``job``: the same
    for the job group alone; ``groups``: name -> the groups it appeared in.
    ``truncated``: the file ended inside an attribute or before the
    end-of-attributes tag.
    """

    def __init__(self) -> None:
        self.attrs: dict[str, list[str]] = {}
        self.job: dict[str, list[str]] = {}
        self.job_tag: dict[str, int] = {}
        self.groups: dict[str, list[int]] = {}
        self.truncated = False
        self.not_ipp = False

    def job_values(self, name: str) -> list[str] | None:
        """*name*'s values if it is a job attribute, the only kind a driver
        is handed; None otherwise."""
        return self.job.get(name)


def _decode(tag: int, raw: bytes) -> str:
    """One IPP value as text (RFC 8010 section 3.9)."""
    if tag in _OUT_OF_BAND or 0x10 <= tag <= 0x1F:
        return _OUT_OF_BAND.get(tag, f"(out-of-band 0x{tag:02x})")
    if tag in (0x21, 0x23) and len(raw) == 4:             # integer, enum
        return str(struct.unpack(">i", raw)[0])
    if tag == 0x22 and len(raw) == 1:                     # boolean
        return "true" if raw[0] else "false"
    if tag == 0x33 and len(raw) == 8:                     # rangeOfInteger
        lo, hi = struct.unpack(">ii", raw)
        return f"{lo}-{hi}"
    if tag == 0x32 and len(raw) == 9:                     # resolution
        x, y, unit = struct.unpack(">iib", raw)
        return f"{x}x{y}{'dpi' if unit == 3 else 'dpcm'}"
    if tag == 0x31 and len(raw) == 11:                    # dateTime
        y, mo, d, h, mi, sec = struct.unpack(">HBBBBB", raw[:7])
        return f"{y:04d}-{mo:02d}-{d:02d} {h:02d}:{mi:02d}:{sec:02d}"
    if tag in (0x35, 0x36) and len(raw) >= 4:             # text/nameWithLanguage
        (llen,) = struct.unpack(">H", raw[:2])
        text = raw[4 + llen:]
        return text.decode("utf-8", "replace")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:                            # octetString etc.
        return "0x" + raw.hex()


def parse_ticket(data: bytes) -> Ticket:
    """Parse a CUPS control file: an IPP message as ``ippWriteIO`` writes it
    with no parent, i.e. version (2), operation (2), request-id (4), then
    attribute groups and the end-of-attributes tag (RFC 8010 section 3.1).

    A tag below 0x10 starts a group (0x03 ends the message); any other tag
    is a value: name-length, name, value-length, value. An empty name adds a
    value to the attribute before it. A collection (0x34 ... 0x37, members
    named by 0x4A values) is read whole and kept as one ``{name=value ...}``
    value, so its members never land on the attribute before or after it.
    """
    t = Ticket()
    if len(data) < 9 or data[0] not in (1, 2):
        t.not_ipp = True
        return t
    pos, end, group, last = 8, len(data), 0, None
    stack: list[list[str]] = []      # open collections, innermost last
    member: list[str | None] = []    # pending member name per open collection
    coll_name = ""                   # name of the top-level collection being read
    while True:
        if pos >= end:
            t.truncated = True
            break
        tag = data[pos]
        pos += 1
        if tag == 0x03:
            break
        if tag < 0x10:
            group, last = tag, None
            continue
        if pos + 2 > end:
            t.truncated = True
            break
        (nlen,) = struct.unpack(">H", data[pos:pos + 2])
        name = data[pos + 2:pos + 2 + nlen].decode("utf-8", "replace")
        pos += 2 + nlen
        if pos + 2 > end:
            t.truncated = True
            break
        (vlen,) = struct.unpack(">H", data[pos:pos + 2])
        raw = data[pos + 2:pos + 2 + vlen]
        pos += 2 + vlen
        if len(raw) < vlen:
            t.truncated = True
            break
        if tag == _EXTENSION and len(raw) >= 4:
            tag, raw = struct.unpack(">I", raw[:4])[0], raw[4:]
        if stack:                                   # inside a collection
            if tag == _MEMBER_NAME:
                member[-1] = raw.decode("utf-8", "replace")
                continue
            if tag == _END_COLLECTION:
                body = "{" + " ".join(stack.pop()) + "}"
                member.pop()
                value = body
                if stack:
                    stack[-1].append(f"{member[-1]}={value}")
                    continue
                name = coll_name                    # finished: store below
            elif tag == _BEG_COLLECTION:
                stack.append([])
                member.append(None)
                continue
            else:
                stack[-1].append(f"{member[-1]}={_decode(tag, raw)}")
                continue
        elif tag == _BEG_COLLECTION:
            coll_name = name
            stack.append([])
            member.append(None)
            continue
        else:
            value = _decode(tag, raw)
        if name:
            last = name
            if group not in t.groups.setdefault(name, []):
                t.groups[name].append(group)
            t.attrs.setdefault(name, []).append(value)
            if group == JOB_GROUP:
                t.job.setdefault(name, []).append(value)
                t.job_tag.setdefault(name, tag)
        elif last is not None:
            t.attrs[last].append(value)
            if group == JOB_GROUP:
                t.job[last].append(value)
    if stack:
        t.truncated = True
    return t


def parse_ipp(data: bytes) -> dict[str, list[str]]:
    """Every attribute in the control file, name -> values (as text)."""
    return parse_ticket(data).attrs


def queue_of(attrs: dict[str, list[str]]) -> str | None:
    """The printer queue the job went to, from its printer URI
    (``ipp://host:631/printers/<queue>``, or ``/classes/<class>``)."""
    for key in ("job-printer-uri", "printer-uri"):
        for uri in attrs.get(key, []):
            path = urllib.parse.urlsplit(uri).path.rstrip("/")
            name = urllib.parse.unquote(path.rsplit("/", 1)[-1])
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
    t = parse_ticket(data)
    if t.not_ipp:
        return [head + "  (not a CUPS control file: no IPP header)"]
    attrs = t.attrs
    queue = queue_of(attrs)
    title = (attrs.get("job-name") or ["?"])[0]
    lines = [head, f"   printer queue: {queue or '(not in file)'}   job: {title}"]
    if t.truncated:
        lines.append("   !!       the file ends early (truncated or still being "
                     "written); what follows may be incomplete")
    expected = ppd_lookup(queue)
    checked, found = set(), 0
    for key, want in expected:
        checked.add(key)
        got = t.job_values(key)
        if got is None and key in attrs:
            where = ", ".join(_GROUP_NAMES.get(g, hex(g)) for g in t.groups[key])
            lines.append(f"   MISSING  {key} (should be {want}): present only as "
                         f"a {where} attribute, which no driver is handed")
            found += 1
        elif got is not None and t.job_tag.get(key) in _NOT_HANDED_TO_DRIVER:
            lines.append(f"   MISSING  {key} = {', '.join(got)} (should be {want}): "
                         f"its IPP type (0x{t.job_tag[key]:02x}) is one cupsd "
                         "does not hand to a driver")
            found += 1
        elif not got:
            lines.append(f"   MISSING  {key} (should be {want})")
        elif got == [want]:
            lines.append(f"   ok       {key} = {want}")
            found += 1
        else:
            lines.append(f"   WRONG    {key} = {', '.join(got)} (should be {want})")
            found += 1
    if not found:
        lines.append("   note     none of these settings is in the job at all: it "
                     "was not printed by ChromIQ, or they were lost on the way")
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
        except OSError as exc:
            print(f"== {path}: cannot read it ({exc.strerror})", file=sys.stderr)
            return 1
        print("\n".join(report(path, data)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
