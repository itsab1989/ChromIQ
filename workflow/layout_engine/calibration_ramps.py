"""Each ink's calibration ramp on its own strip (#182, Knut 5965186237).

``targen -s N`` with nothing else (the calibration knobs: ``-f0 -e0 -B0``)
writes ONE shared paper white and then each channel's ramp of N-1 steps,
channel after channel: 3N-2 patches for RGB, 4N-3 for CMYK. Laid out in that
order the ramps ran across the strips, so on Knut's 20-per-strip chart the last
patch of the magenta strip was the first yellow step and the yellow strip ended
on two fill-up whites.

Knut approved the layout (5965186237, Q3 "yes" to 5964724199):

* every ink's ramp STARTS ITS OWN STRIP, with its own paper white first;
* a ramp longer than a strip continues on the next one, and the next ramp
  still starts a fresh strip;
* where a ramp ends part-way down a strip, the rest of that strip is paper
  white. ``printcal`` averages every patch whose device values are all "no
  ink" into one white point and weights it by the count
  (``printcal.c`` 1293-1325, 1386-1395, 1487), so the extra whites help.

This module only REARRANGES a patch list. It knows nothing of pages: the strip
length (``STEPS_IN_PASS``) comes from whoever lays the chart out, the engine in
``chart.build_chart`` or printtarg's own ``.ti2`` on the printtarg path
(``ChartCreator``). It never touches a chart that is not a pure single-channel
ramp set straight from targen, so a profiling chart, a user's patch set, or a
calibration chart with ``-e`` / ``-B`` / ``-g`` added under the override, keeps
its rows exactly as they were.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

#: Device values closer than this are the same value. targen writes four to
#: six significant digits; a ramp step is never closer than 0.1 %.
_EPS = 1e-4

_NON_DEVICE = ("SAMPLE_ID", "SAMPLE_LOC", "INDEX", "SAMPLE_NAME")


@dataclass(frozen=True)
class RampSet:
    """A chart that is nothing but single-channel ramps from one white."""
    #: Row index (0-based, in file order) of every paper-white row.
    whites: tuple[int, ...]
    #: One entry per channel, in the order the channels appear: the row
    #: indices of that channel's steps, in file order. Never empty.
    ramps: tuple[tuple[int, ...], ...]
    #: Total rows in the table.
    n_rows: int

    @property
    def is_targen_order(self) -> bool:
        """Exactly targen's own shape: one white, first, then the ramps."""
        return self.whites == (0,)


def _is_device_field(name: str) -> bool:
    if name in _NON_DEVICE:
        return False
    return not name.startswith(("XYZ_", "LAB_", "SPEC_", "STDEV", "D_"))


def find_ramps(rows: "list[tuple[float, ...]]") -> "RampSet | None":
    """The ramp structure of *rows* (device values only), or None.

    A ramp set is: a first row that is paper white (every channel at 0, or
    every channel at 100 for an additive device: whichever the first row is),
    and every other row either that same white or the white with exactly ONE
    channel changed, the changed channel forming one contiguous block per
    channel (whites may sit between or inside the blocks, which is what an
    arranged chart looks like). Anything else, a black, a grey, a two-ink
    patch, a channel that comes back after another one, is not a ramp set.
    """
    if len(rows) < 2:
        return None
    base = rows[0]
    n = len(base)
    if n < 1 or any(len(r) != n for r in rows):
        return None
    if not (all(abs(v) < _EPS for v in base)
            or all(abs(v - 100.0) < _EPS for v in base)):
        return None
    whites: list[int] = []
    blocks: list[tuple[int, list[int]]] = []     # (channel, row indices)
    seen: set[int] = set()
    for i, r in enumerate(rows):
        diff = [c for c in range(n) if abs(r[c] - base[c]) >= _EPS]
        if not diff:
            whites.append(i)
            continue
        if len(diff) != 1:
            return None
        ch = diff[0]
        if blocks and blocks[-1][0] == ch:
            blocks[-1][1].append(i)
            continue
        if ch in seen:
            return None          # a channel that comes back: not one ramp each
        seen.add(ch)
        blocks.append((ch, [i]))
    if not blocks:
        return None
    return RampSet(whites=tuple(whites),
                   ramps=tuple(tuple(b) for _, b in blocks),
                   n_rows=len(rows))


def arranged_order(ramps: RampSet, steps_in_pass: int,
                   total: "int | None" = None) -> "list[int] | None":
    """Row indices of the arranged chart, a white's index repeated where a
    white is placed; None when *ramps* must be left as it is.

    Each ramp is its white plus its steps, and every ramp but the last is
    padded with whites to a whole number of strips, so the next one starts a
    strip. The LAST ramp is not padded here: the layout fills the last strip
    with paper white as it always has (printtarg's ``padlrow``, mirrored by the
    engine), and that fill-up is reported as such.

    *total*, when given, is the row count `settle` found the layout agrees
    with: the last ramp's last strip is then filled with paper white up to it
    (never past the end of that strip).
    """
    if not ramps.is_targen_order or steps_in_pass < 1:
        return None
    white = ramps.whites[0]
    order: list[int] = []
    for k, steps in enumerate(ramps.ramps):
        block = [white, *steps]
        if k < len(ramps.ramps) - 1:
            rem = len(block) % steps_in_pass
            if rem:
                block += [white] * (steps_in_pass - rem)
        order += block
    if total is not None and total > len(order):
        order += [white] * (total - len(order))
    return order


def arranged_count(ramp_lengths: "list[int]", steps_in_pass: int) -> int:
    """How many rows `arranged_order` makes for ramps of these step counts
    (each WITHOUT its white), so an estimate can ask without a file."""
    total = 0
    for k, steps in enumerate(ramp_lengths):
        block = 1 + int(steps)
        if k < len(ramp_lengths) - 1 and steps_in_pass >= 1:
            rem = block % steps_in_pass
            if rem:
                block += steps_in_pass - rem
        total += block
    return total


def settle(count_for_steps, steps_for_count, first_count: int,
           *, tries: int = 8) -> "tuple[int, int] | None":
    """``(count, steps_in_pass)`` that agree with each other, or None.

    The strip length can depend on the patch count (area-first sizes the
    patches to FILL the box with exactly that many), and the count depends on
    the strip length. "Agree" means the layout of *count* patches really has
    strips of *steps_in_pass*: ``steps_for_count(count) == steps_in_pass``.
    Arranged for one strip length and laid out with another, every ramp after
    the first starts part-way down a strip and the whites added to separate
    them land in the middle of the next ink (review of 7386afd8, 2026-10-03:
    the default i1Pro A4 calibration chart, 20 steps, arranged for 9 and laid
    out on 10).

    For each strip length tried, the count is the arranged count or, failing
    that, the arranged count with the LAST strip filled further with paper
    white, which is what the layout itself would print there. Starting from the
    chart as targen wrote it, the strip length the layout gives that count is
    tried next. None when no strip length agrees: the caller then leaves
    targen's own order, which is the chart as it was before.
    """
    seen: set[int] = set()
    try:
        steps = int(steps_for_count(first_count))
    except Exception:          # noqa: BLE001 — no layout, nothing to arrange
        return None
    for _ in range(tries):
        if steps < 1 or steps in seen:
            break
        seen.add(steps)
        count = int(count_for_steps(steps))
        full = -(-count // steps) * steps        # the end of the last strip
        for n in (count, full, *range(count + 1, full)):
            if steps_for_count(n) == steps:
                return n, steps
        steps = int(steps_for_count(count))
    return None


# --------------------------------------------------------------------------
# .ti1 text
# --------------------------------------------------------------------------

_FMT_RE = re.compile(r"^BEGIN_DATA_FORMAT\s*$(.*?)^END_DATA_FORMAT\s*$",
                     re.S | re.M)
_DATA_RE = re.compile(r"^BEGIN_DATA\s*$\n?(.*?)^END_DATA\s*$", re.S | re.M)


def _first_table(text: str):
    fmt = _FMT_RE.search(text)
    data = _DATA_RE.search(text)
    if not fmt or not data or data.start() < fmt.end():
        return None
    fields = fmt.group(1).split()
    lines = [ln for ln in data.group(1).splitlines() if ln.strip()]
    return fields, data, lines


def ramps_in_ti1_text(text: str) -> "RampSet | None":
    """`find_ramps` on the first table of a .ti1's text."""
    got = _first_table(text)
    if got is None:
        return None
    fields, _data, lines = got
    dev = [i for i, f in enumerate(fields) if _is_device_field(f)]
    if not dev:
        return None
    rows = []
    try:
        for ln in lines:
            toks = ln.split()
            if len(toks) < len(fields):
                return None
            rows.append(tuple(float(toks[i]) for i in dev))
    except ValueError:
        return None
    return find_ramps(rows)


def ramps_in_ti1(path: "str | Path") -> "RampSet | None":
    try:
        text = Path(path).read_text(encoding="latin-1")
    except OSError:
        return None
    return ramps_in_ti1_text(text)


def rewrite_ti1_text(text: str, order: "list[int]") -> str:
    """*text* with its first table's rows put in *order* (indices into the
    current rows, repeats allowed) and SAMPLE_ID renumbered 1..n.

    Every other line is kept byte for byte: the header (``SINGLE_DIM_STEPS``
    still says N), and targen's ``DENSITY_EXTREME_VALUES`` and
    ``DEVICE_COMBINATION_VALUES`` tables, whose INDEX column is their own and
    refers to nothing in the main table.
    """
    got = _first_table(text)
    if got is None:
        raise ValueError("no patch table in .ti1")
    fields, data, lines = got
    sid = fields.index("SAMPLE_ID") if "SAMPLE_ID" in fields else None
    out = []
    for n, idx in enumerate(order, 1):
        toks = lines[idx].split()
        if sid is not None:
            toks[sid] = str(n)
        out.append(" ".join(toks) + " ")
    body = "\n".join(out) + "\n"
    new = text[:data.start(1)] + body + text[data.end(1):]
    # NUMBER_OF_SETS of the FIRST table only: the last one before its data.
    head = new[:data.start(1)]
    m = None
    for m in re.finditer(r"^NUMBER_OF_SETS\s+\d+\s*$", head, re.M):
        pass
    if m is not None:
        new = (new[:m.start()] + f"NUMBER_OF_SETS {len(order)}"
               + new[m.end():])
    return new


def arrange_ti1(path: "str | Path", steps_in_pass: int,
                total: "int | None" = None) -> "int | None":
    """Rewrite the .ti1 at *path* so each ramp starts a strip of
    *steps_in_pass* patches (and, with *total*, the last strip is filled with
    paper white up to that count, see `arranged_order`). Returns the new row
    count, or None when the file is not a pure targen ramp set (and is then
    left untouched)."""
    p = Path(path)
    text = p.read_text(encoding="latin-1")
    ramps = ramps_in_ti1_text(text)
    if ramps is None:
        return None
    order = arranged_order(ramps, steps_in_pass, total)
    if order is None:
        return None
    if order == list(range(ramps.n_rows)):
        return ramps.n_rows
    p.write_text(rewrite_ti1_text(text, order), encoding="latin-1")
    return len(order)
