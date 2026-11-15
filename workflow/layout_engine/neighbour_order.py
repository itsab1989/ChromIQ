"""Keep very dark patches away from very light ones along a strip (R7, 4.3.39).

jctay (forum 150236), an i1Pro 3 on a fixed-order chart: strip 12 ran a grey
ramp up to 94 % and then three near-blacks (7/7/8 %), and was refused 15
times out of 15 with the driver's "Reading is inconsistent". The first
readings of the near-black patch still caught light from the almost white
patch before it, just past the instrument's patch-consistency limit. A
randomised chart rarely puts two such patches side by side; a chart in fixed
order can put many there, in the same place on every print.

For a chart in FIXED order this moves the fewest patches needed so that no
near-black patch sits directly next to a near-white one along a strip:

* the patch SET is unchanged, only where some patches sit;
* deterministic: the same chart and options give the same order every time;
* recorded like any layout, through the engine's one slot list (the .ti2,
  the TIFF, the side files and the .cht are all written from it), so every
  reader of the chart agrees where each patch is;
* a chart without such neighbours gets ``None`` back and is written exactly
  as before, byte for byte; randomised charts are never touched.

The thresholds come from the tester's failing pair, the 94 % grey (L* about
97) before the 7/7/8 % near-black (L* about 6), with a margin of about 15 L*
on each side: near-black is L* 20 or below, near-white L* 80 or above, judged
on the chart's own expected colours, relative to its lightest patch.
"""
from __future__ import annotations

from dataclasses import dataclass

#: L* at or below which a patch counts as near-black, and at or above which
#: as near-white (see the module text).
NEAR_BLACK_L = 20.0
NEAR_WHITE_L = 80.0


@dataclass(frozen=True)
class Move:
    """Two patches that swapped places: the canonical patch indices and the
    sheet slots they now sit in."""
    patch_a: int
    patch_b: int
    slot_a: int
    slot_b: int


def lightness(xyz, white_y: float) -> float:
    """CIE L* of *xyz* against a white of luminance *white_y*."""
    y = float(xyz[1]) / float(white_y) if white_y else 0.0
    f = y ** (1 / 3) if y > 216 / 24389 else (24389 / 27 * y + 16) / 116
    return 116 * f - 16


def _kind(lstar: float) -> int:
    """-1 near-black, +1 near-white, 0 neither."""
    if lstar <= NEAR_BLACK_L:
        return -1
    if lstar >= NEAR_WHITE_L:
        return 1
    return 0


def arrange(xyzs, total: int, steps_in_pass: int, movable: int,
            per_page: int = 0) -> "tuple[list[int] | None, list[Move]]":
    """``(slots, moves)`` for a fixed-order chart.

    *xyzs*: the expected XYZ of every patch in canonical order (padding
    included, *total* of them); *movable*: how many of them are real patches
    (the padding after them is the paper white and never moves);
    *steps_in_pass*: patches per strip; *per_page*: patches per page (a
    patch never moves to another sheet). ``slots[i]`` is the sheet slot of
    patch *i* (the identity, apart from the moves), or None when nothing had
    to move. Pairs no swap can clear without making another are left as they
    are (they stay in *unfixed* of :func:`describe`)."""
    n = int(total)
    steps = int(steps_in_pass or 0)
    if n < 2 or steps < 2 or len(xyzs) < n:
        return None, []
    white_y = max((float(x[1]) for x in xyzs[:n]), default=0.0)
    if white_y <= 0:
        return None, []
    kinds = [_kind(lightness(x, white_y)) for x in xyzs[:n]]
    # slot -> patch (start: the identity)
    at = list(range(n))

    def k(slot: int) -> int:
        return kinds[at[slot]]

    def same_strip(a: int, b: int) -> bool:
        return 0 <= a < n and 0 <= b < n and a // steps == b // steps

    def bad_at(slot: int) -> bool:
        """Is *slot* in a near-black / near-white pair with a neighbour?"""
        ks = k(slot)
        if ks == 0:
            return False
        for nb in (slot - 1, slot + 1):
            if same_strip(slot, nb) and k(nb) == -ks:
                return True
        return False

    def can_move(slot: int) -> bool:
        return 0 <= slot < n and at[slot] < movable

    moves: list[Move] = []
    for slot in range(n - 1):
        nxt = slot + 1
        if not same_strip(slot, nxt) or k(slot) * k(nxt) != -1:
            continue
        dark = slot if k(slot) == -1 else nxt
        light = nxt if dark == slot else slot
        away = dark + (dark - light)           # the dark patch's other side
        cands = [away, dark + 2 * (dark - light),
                 dark + steps, dark - steps]
        for c in cands:
            if c < 0 or c >= n or c == light:
                continue
            if c in (away, dark + 2 * (dark - light)) and not same_strip(dark, c):
                continue
            if per_page and dark // per_page != c // per_page:
                continue
            if not (can_move(dark) and can_move(c)):
                continue
            at[dark], at[c] = at[c], at[dark]
            touched = {dark, c, light}
            if any(bad_at(t) for t in touched) or any(
                    bad_at(t) for t in (dark - 1, dark + 1, c - 1, c + 1)
                    if 0 <= t < n):
                at[dark], at[c] = at[c], at[dark]      # undo: not clean
                continue
            moves.append(Move(at[c], at[dark], c, dark))
            break
    if not moves:
        return None, []
    slots = [0] * n
    for s, p in enumerate(at):
        slots[p] = s
    return slots, moves


def remaining_pairs(xyzs, slots, total: int, steps_in_pass: int) -> int:
    """How many near-black / near-white neighbour pairs the order *slots*
    (None: the identity) still has. For the log and the tests."""
    n = int(total)
    steps = int(steps_in_pass or 0)
    if n < 2 or steps < 2:
        return 0
    white_y = max((float(x[1]) for x in xyzs[:n]), default=0.0) or 1.0
    at = list(range(n))
    if slots is not None:
        for p, s in enumerate(slots):
            at[s] = p
    kinds = [_kind(lightness(xyzs[at[s]], white_y)) for s in range(n)]
    return sum(1 for s in range(n - 1)
               if s // steps == (s + 1) // steps and kinds[s] * kinds[s + 1] == -1)
