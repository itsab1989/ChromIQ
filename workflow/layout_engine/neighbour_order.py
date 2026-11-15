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
on the chart's own expected colours against the PAPER: the white point the
patch set names (targen's APPROX_WHITE_POINT), else Y = 100, never the
lightest patch (on a shadow-only set an L* 41 grey is no near-white).

Two patches with a drawn spacer between them are not neighbours (the caller
passes no work then). The search (review of 4.3.39): for each pair, the
patch to move is tried at every other place on the same page, nearest first
(the same strip before any other), the dark one before the light one, and a
swap is taken only when it leaves fewer such pairs around both places and
clears this one; a pair is left only when no swap on the page can do that.
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


def white_y_of_ti1(ti1_path) -> float:
    """The paper's luminance the patch set names (APPROX_WHITE_POINT's Y,
    targen writes it), else 100: expected XYZ in a .ti1 are relative to it."""
    try:
        import re
        from pathlib import Path
        head = Path(ti1_path).read_text(encoding="latin-1", errors="replace")
        head = head[:head.find("BEGIN_DATA")] if "BEGIN_DATA" in head else head
        m = re.search(r'APPROX_WHITE_POINT\s+"?\s*([-\d.eE+]+)\s+([-\d.eE+]+)', head)
        if m and float(m.group(2)) > 0:
            return float(m.group(2))
    except (OSError, ValueError):
        pass
    return 100.0


def arrange(xyzs, total: int, steps_in_pass: int, movable: int,
            per_page: int = 0, white_y: float = 100.0
            ) -> "tuple[list[int] | None, list[Move]]":
    """``(slots, moves)`` for a fixed-order chart.

    *xyzs*: the expected XYZ of every patch in canonical order (padding
    included, *total* of them); *movable*: how many of them are real patches
    (the padding after them is the paper white and never moves);
    *steps_in_pass*: patches per strip; *per_page*: patches per page (a
    patch never moves to another sheet); *white_y*: the paper's Y.
    ``slots[i]`` is the sheet slot of patch *i*, or None when nothing had to
    move. A pair is left only when no swap on its page clears it."""
    n = int(total)
    steps = int(steps_in_pass or 0)
    if n < 2 or steps < 2 or len(xyzs) < n or not white_y or white_y <= 0:
        return None, []
    kinds = [_kind(lightness(x, white_y)) for x in xyzs[:n]]
    if not (any(k < 0 for k in kinds) and any(k > 0 for k in kinds)):
        return None, []
    at = list(range(n))                     # slot -> patch

    def bad_edge(a: int) -> bool:           # slots a and a+1
        return (0 <= a and a + 1 < n and a // steps == (a + 1) // steps
                and kinds[at[a]] * kinds[at[a + 1]] == -1)

    def local(slots) -> int:
        edges = set()
        for t in slots:
            edges.add(t - 1)
            edges.add(t)
        return sum(1 for e in edges if bad_edge(e))

    def page(s: int) -> int:
        return s // per_page if per_page else 0

    def candidates(src: int):
        pg, strip, pos = page(src), src // steps, src % steps
        cs = [c for c in range(n) if c != src and at[c] < movable
              and page(c) == pg]
        cs.sort(key=lambda c: (c // steps != strip,
                               abs(c // steps - strip), abs(c % steps - pos),
                               c))
        return cs

    moves: "list[Move]" = []
    unfixable: "set[tuple[int, int]]" = set()
    for _guard in range(4 * n):
        edge = next((e for e in range(n - 1) if bad_edge(e)
                     and (at[e], at[e + 1]) not in unfixable), None)
        if edge is None:
            break
        dark, light = ((edge, edge + 1) if kinds[at[edge]] < 0
                       else (edge + 1, edge))
        done = False
        for src in (dark, light):
            if at[src] >= movable:
                continue
            for c in candidates(src):
                if c in (dark, light):
                    continue
                before = local((src, c))
                at[src], at[c] = at[c], at[src]
                if not bad_edge(edge) and local((src, c)) < before:
                    moves.append(Move(at[c], at[src], c, src))
                    done = True
                    break
                at[src], at[c] = at[c], at[src]
            if done:
                break
        if not done:
            unfixable.add((at[edge], at[edge + 1]))
    if not moves:
        return None, []
    slots = [0] * n
    for s_, p_ in enumerate(at):
        slots[p_] = s_
    if slots == list(range(n)):
        return None, []
    return slots, moves


def remaining_pairs(xyzs, slots, total: int, steps_in_pass: int,
                    white_y: float = 100.0) -> int:
    """How many near-black / near-white neighbour pairs the order *slots*
    (None: the identity) still has. For the log and the tests."""
    n = int(total)
    steps = int(steps_in_pass or 0)
    if n < 2 or steps < 2 or not white_y:
        return 0
    at = list(range(n))
    if slots is not None:
        for p, s in enumerate(slots):
            at[s] = p
    kinds = [_kind(lightness(xyzs[at[s]], white_y)) for s in range(n)]
    return sum(1 for s in range(n - 1)
               if s // steps == (s + 1) // steps and kinds[s] * kinds[s + 1] == -1)


#: Two neighbouring patches closer than this (CIE76, on the chart's expected
#: colours) give a strip reader almost no colour change to find the edge
#: between them. ChromIQ's own choice, not an ArgyllCMS number: identical
#: patches (targen's whites, its blacks, the paper-white fill-up) are 0.
ALIKE_DE = 3.0


def _lab(xyz, white_y: float = 100.0):
    wx, wy, wz = 96.42 * white_y / 100.0, white_y, 82.49 * white_y / 100.0

    def f(t):
        return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116
    fx, fy, fz = f(xyz[0] / wx), f(xyz[1] / wy), f(xyz[2] / wz)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def alike_pairs_in_ti2(ti2) -> "int | None":
    """How many pairs of neighbouring patches along a strip of the chart
    *ti2* are identical or nearly so (closer than ALIKE_DE), in the order the
    chart file records (randomised or not). Owner's question, 2026-11-15: on
    a chart WITHOUT spacers nothing separates such a pair, so the instrument
    cannot tell where one ends and the other begins. Said, never moved (R7
    moves only dark / light pairs). None when the file cannot be read."""
    try:
        from pathlib import Path
        from workflow.layout_engine.labels import labels_for_chart
        cl = labels_for_chart(ti2)
        text = Path(ti2).read_text(encoding="latin-1", errors="replace")
        fields, rows, on, fmt = [], {}, False, False
        for ln in text.splitlines():
            t = ln.strip()
            if t == "BEGIN_DATA_FORMAT":
                fmt = True
                continue
            if t == "END_DATA_FORMAT":
                fmt = False
                continue
            if fmt:
                fields += t.split()
                continue
            if t == "BEGIN_DATA":
                on = True
                continue
            if t == "END_DATA":
                break
            if on and t:
                rec = dict(zip(fields, t.split()))
                sp = cl.split(rec["SAMPLE_LOC"].strip('"'))
                if sp is not None:
                    rows[sp] = (float(rec["XYZ_X"]), float(rec["XYZ_Y"]),
                                float(rec["XYZ_Z"]))
    except (OSError, KeyError, ValueError):
        return None
    n = 0
    for (s_, p_), xyz in rows.items():
        nxt = rows.get((s_, p_ + 1))
        if nxt is None:
            continue
        a, b = _lab(xyz), _lab(nxt)
        if sum((u - v) ** 2 for u, v in zip(a, b)) ** 0.5 < ALIKE_DE:
            n += 1
    return n
