"""Keep targen's OFPS sampler off a degenerate ink-limit corner (F-10, #182).

ArgyllCMS 3.5.0 targen aborts with

    targen: Error - ofps: assert, node vertex info should be empty on
    add_node2voronoi() entry                       (target/ofps.c:4134)

or, from the same cause, "Failed to re-seed the voronoi after 100 tries",
whenever a FIXED patch sits exactly on a corner of the device cube that lies on
the total-ink-limit plane. Found by the profile-engine research (#182
5985477496) and measured again here against the local targen 3.5.0, 60 fill
patches, -e0 -B0 unless stated:

* the limit has to be a whole multiple of 100, because only then does the
  limit plane pass through cube corners (all channels 0 or 100);
* a fixed-patch option has to put a patch on such a corner at exactly that
  total: single-ink steps (-s) reach 100, the device grey (-g) reaches 300
  (C=M=Y=100, or R=G=B), the cube grids (-m, -M, -b) reach every multiple of
  100, and the device black (-B) reaches 100 x channels;
* the limit has to be below the cube's own maximum (100 x channels): at that
  value it limits nothing and targen copes, except for a one-channel grey
  device, which fails at 100 with any fixed patch;
* only OFPS is affected (no -t/-r/-R/-q/-Q/-i/-I), and only up to four
  channels: five inks and more use another sampler (no failure measured on
  -d6 at 100/200/300 with -s, -m, -M, -b).

Measured failing: -d4 -l300 -g; -d4 -l100 -s; -d4 -l100/-l200 -m/-M/-b;
-d4 -l300 -m2/-M2/-b2; -d2 and -d5 -l100 -s/-m/-M/-b and -l200 -m/-M/-b;
-d0 -l100 with anything. Whether a given corner trips it also depends on the
fill count: -d4 -l300 -m3/-M3/-b3 pass at -f60 and all fail at -f500, so the
rule below covers every corner a fixed patch can reach, not only the ones that
failed at one count. Measured passing: every one of those at limit + 0.1,
and every limit that is not a multiple of 100 (250, 299, 320, ...).

THE NUDGE GOES UP, NOT DOWN. With limit - 0.1 targen drops (or clips) the
fixed patches that sat exactly on the limit, so -g11 -l299.9 makes ten grey
steps instead of eleven and -s11 -l99.9 still fails; with limit + 0.1 every
fixed patch is kept as asked. The full-spread patches may then reach the limit
+ 0.1 points, which is a quarter of one 8-bit level of one channel.

The user's value is never changed: only the argv handed to targen carries the
nudged limit. The chart's own record is put back afterwards by
:func:`restore_recorded_ink_limit`, so the `.ti1` (and from it the `.ti2`, the
`.ti3`, colprof's -l and every report) carries the limit the user chose.

A limit BELOW 100 with single-ink steps (-s) fails for a different reason that
no nudge reaches: targen clips the steps above the limit onto the limit corner
itself. That case is left to targen's own error.
"""
from __future__ import annotations

import re
from pathlib import Path

from core.logger import get_logger

log = get_logger(__name__)

#: How far above the chosen limit targen is asked to go (percentage points).
NUDGE = 0.1

# targen's full-spread selectors other than the default OFPS. With any of them
# OFPS never runs and the corner cannot hurt.
_NON_OFPS = {"-t", "-r", "-R", "-q", "-Q", "-i", "-I"}

_OPT = re.compile(r"^-([lgsmMbBdD])(.*)$")


def _options(argv: list[str]) -> dict[str, list[str]]:
    """targen's single-letter value options that matter here, by letter.

    targen takes a value either glued to its flag (``-l300``) or as the next
    word (``-l 300``); ChromIQ produces both.
    """
    found: dict[str, list[str]] = {}
    i = 0
    while i < len(argv):
        m = _OPT.match(argv[i])
        if m:
            letter, glued = m.group(1), m.group(2)
            if glued:
                found.setdefault(letter, []).append(glued)
            elif i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                found.setdefault(letter, []).append(argv[i + 1])
                i += 1
        i += 1
    return found


def _num(text: str) -> float | None:
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _channels(opts: dict[str, list[str]]) -> int:
    from ui.tiff_preview import resolve_ink_channels
    device = (opts.get("d") or ["2"])[-1]
    extra = " ".join(f"-D{v}" for v in opts.get("D", []))
    return len(resolve_ink_channels(device, extra))


def _corner_totals(opts: dict[str, list[str]], n: int) -> set[int]:
    """The totals (percent) at which a fixed patch sits on a cube corner."""
    def steps(letter: str) -> int:
        v = _num((opts.get(letter) or ["0"])[-1])
        return int(v) if v is not None else 0

    totals: set[int] = set()
    if steps("s") >= 2:
        totals.add(100)
    if steps("g") >= 2:
        totals.add(100 * min(n, 3))
    if max(steps("m"), steps("M"), steps("b")) >= 2:
        totals.update(100 * k for k in range(1, n + 1))
    if steps("B") >= 1:
        totals.add(100 * n)
    return totals


def corner_limit(argv: list[str]) -> float | None:
    """The ink limit in ``argv`` when it would trip targen's corner assert.

    None when there is no -l, when OFPS is not the sampler, or when no fixed
    patch lands on a cube corner at exactly that limit.
    """
    if any(a in _NON_OFPS for a in argv):
        return None
    opts = _options(argv)
    limit = _num((opts.get("l") or [""])[-1])
    if limit is None or limit <= 0 or limit != round(limit) or int(limit) % 100:
        return None
    n = _channels(opts)
    if n > 4:
        return None
    if n == 1:
        return limit if int(limit) == 100 else None
    if int(limit) >= 100 * n:
        return None
    if int(limit) not in _corner_totals(opts, n):
        return None
    return limit


def corner_safe_argv(argv: list[str]) -> tuple[list[str], float | None]:
    """``argv`` with a corner ink limit raised by :data:`NUDGE`.

    Returns the argv to run and the limit the user chose when it was nudged
    (None when the argv is returned unchanged). Logs one line when it nudges.
    """
    limit = corner_limit(argv)
    if limit is None:
        return list(argv), None
    passed = f"{limit + NUDGE:g}"
    out: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "-l" and i + 1 < len(argv):
            out += ["-l", passed]
            i += 2
            continue
        if a.startswith("-l") and len(a) > 2:
            out.append(f"-l{passed}")
        else:
            out.append(a)
        i += 1
    log.info("targen: ink limit %g%% passed as %s%% so a fixed patch is not on "
             "the limit corner (ArgyllCMS 3.5.0 OFPS assert); the chart "
             "records %g%%", limit, passed, limit)
    return out, limit


def restore_recorded_ink_limit(ti1_path: Path, limit: float) -> bool:
    """Put the user's limit back into the ``.ti1``'s ``TOTAL_INK_LIMIT``.

    targen writes the limit it was given, with one decimal. Returns True when
    the file was rewritten.
    """
    path = Path(ti1_path)
    try:
        text = path.read_text(encoding="utf-8", errors="surrogateescape")
    except OSError:
        return False
    new, count = re.subn(r'^(TOTAL_INK_LIMIT\s+)"[\d.]+"',
                         lambda m: f'{m.group(1)}"{limit:.1f}"', text,
                         count=1, flags=re.MULTILINE)
    if not count or new == text:
        return False
    path.write_text(new, encoding="utf-8", errors="surrogateescape")
    return True
