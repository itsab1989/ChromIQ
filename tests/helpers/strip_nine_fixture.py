"""A synthetic fixed-order chart on which one strip looks a little like
another row turned round (R1, 4.3.39).

Shaped like a tester's chart (jctay, forum posts 150222 / 150236): 16 strips
of 12 patches, number strips and letter patches ("9A".."9L"), fixed order,
an i1Pro 3. On his chart, strip 9 read forward fitted its own row's design
colours with a mean of 42.6 dE76 and row 13 TURNED ROUND with 40.0, so with
ChromIQ's -S (no wrong-strip prompt) the helper filed strip 9 under row 9 with
row 13's direction: back to front, on every pass, in either direction.

Nothing here comes from his files. The patch colours are a plain RGB cube
and grey ramps of our own, the expected XYZ values an sRGB model; strip 9's
"reading" is made by mixing, in Lab, row 9's design colours with row 13's
design colours turned round, a touch nearer to the latter, so the scores land
where his did (own row forward a little worse than row 13 reversed, own row
reversed far worse). Every other strip reads as designed plus a tiny offset.
"""
from __future__ import annotations

from pathlib import Path

STRIPS = 16
PER = 12
LETTERS = "ABCDEFGHIJKL"
#: How far strip 9's reading leans towards row 13 turned round (0.5 = halfway).
#: 0.52 gives own row forward about 4 % worse than row 13 reversed, as on the
#: tester's chart (42.6 vs 40.0).
LEAN = 0.52
SICK_ROW = 9
LOOKALIKE_ROW = 13
#: How row 13's RGB differs from row 9's turned round.
NUDGE = (14.0, -10.0, 12.0)

_D50 = (96.42, 100.0, 82.49)


def _srgb_to_xyz(r: float, g: float, b: float) -> tuple[float, float, float]:
    def lin(c: float) -> float:
        c /= 100.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    rl, gl, bl = lin(r), lin(g), lin(b)
    # sRGB primaries, Bradford-adapted to D50, as a design model (0..100)
    x = 43.61 * rl + 38.51 * gl + 14.31 * bl
    y = 22.25 * rl + 71.69 * gl + 6.06 * bl
    z = 1.39 * rl + 9.71 * gl + 71.41 * bl
    # a paper white and a printable black, so nothing is exactly 0
    return (0.95 + 0.97 * x, 1.0 + 0.97 * y, 0.8 + 0.97 * z)


def _f(t: float) -> float:
    return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116


def _finv(t: float) -> float:
    return t ** 3 if t ** 3 > 216 / 24389 else (116 * t - 16) / (24389 / 27)


def xyz_to_lab(xyz):
    fx, fy, fz = (_f(v / w) for v, w in zip(xyz, _D50))
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def lab_to_xyz(lab):
    L, a, b = lab
    fy = (L + 16) / 116
    fx = fy + a / 500
    fz = fy - b / 200
    return tuple(w * _finv(t) for w, t in zip(_D50, (fx, fy, fz)))


def de76(a, b) -> float:
    la, lb = xyz_to_lab(a), xyz_to_lab(b)
    return sum((p - q) ** 2 for p, q in zip(la, lb)) ** 0.5


def patch_rgbs() -> list[tuple[float, float, float]]:
    """192 RGB patches in a fixed order: a 5-level cube, then grey ramps and
    a few near-blacks, as an ordinary non-randomised chart would hold."""
    lv = [0.0, 24.7059, 49.8039, 74.902, 100.0]
    out = [(r, g, b) for b in lv for g in lv for r in lv]          # 125
    out += [(v, v, v) for v in (5, 10, 15, 20, 30, 40, 60, 70, 80, 85, 90, 95)]
    out += [(v * 0.9, v, v) for v in range(8, 100, 8)]              # 12
    out += [(v, v * 0.85, v * 0.7) for v in range(8, 100, 8)]       # 12
    out += [(v, v * 0.6, v) for v in range(8, 100, 8)]              # 12
    out += [(50 + v, 50, 50 - v / 2) for v in range(0, 50, 5)]       # 10
    out += [(7, 7, 8), (8, 7, 7), (14, 14, 17)][: 192 - len(out)]
    while len(out) < 192:
        out.append((50.0, 50.0, 50.0))
    out = out[:192]
    # Row 13 is row 9 turned round with its colours nudged: row 13 reversed
    # then sits near row 9, as by chance on the tester's chart.
    nine = out[(SICK_ROW - 1) * PER: SICK_ROW * PER]
    look = [(min(100.0, r + NUDGE[0]), max(0.0, g + NUDGE[1]),
             min(100.0, b + NUDGE[2])) for r, g, b in reversed(nine)]
    out[(LOOKALIKE_ROW - 1) * PER: LOOKALIKE_ROW * PER] = look
    return out


def design() -> dict[int, list[tuple[float, float, float]]]:
    """{strip number: [expected XYZ of each patch, A..L]}."""
    rgbs = patch_rgbs()
    xyz = [_srgb_to_xyz(*c) for c in rgbs]
    return {s: xyz[(s - 1) * PER: s * PER] for s in range(1, STRIPS + 1)}


def reading_of(strip: int) -> list[tuple[float, float, float]]:
    """What the instrument reports for *strip* swiped A -> L."""
    d = design()
    if strip != SICK_ROW:
        return [tuple(v * 1.01 for v in p) for p in d[strip]]
    own = d[SICK_ROW]
    other = list(reversed(d[LOOKALIKE_ROW]))
    out = []
    for p, q in zip(own, other):
        lp, lq = xyz_to_lab(p), xyz_to_lab(q)
        out.append(lab_to_xyz(tuple(a + LEAN * (b - a) for a, b in zip(lp, lq))))
    return out


def scores(strip: int) -> dict[tuple[int, int], float]:
    """The helper's row score (mean dE76, Y-normalised) of strip *strip*'s
    A -> L reading against every row in both directions:
    {(row, reversed): score}. Mirrors chromiq_chartread.c's row loop."""
    d = design()
    vals = reading_of(strip)
    out = {}
    for row, exp in d.items():
        for rev in (0, 1):
            v = list(reversed(vals)) if rev else vals
            ynorm = sum(e[1] for e in exp) / sum(p[1] for p in v)
            out[(row, rev)] = sum(
                de76(tuple(ynorm * c for c in p), e) for p, e in zip(v, exp)
            ) / len(exp)
    return out


def write_chart(base: Path) -> Path:
    """Write <base>.ti2 and return its path."""
    d = design()
    rgbs = patch_rgbs()
    lines = [
        "CTI2   ", "",
        'DESCRIPTOR "Argyll Calibration Target chart information 2"',
        'ORIGINATOR "ChromIQ test fixture (synthetic)"',
        'CREATED "Sun Nov 15 12:00:00 2026"',
        'TARGET_INSTRUMENT "GretagMacbeth i1 Pro"',
        'APPROX_WHITE_POINT "95.050000 100.000000 108.900000"',
        'COLOR_REP "iRGB"',
        'PAPER_SIZE "100.0x150.0"',
        'CHART_ID "424242"',
        f'STEPS_IN_PASS "{PER}"',
        'PASSES_IN_STRIPS2 "9,7"',
        'STRIP_INDEX_PATTERN "0-9,@-9,@-9;1-999"',
        'PATCH_INDEX_PATTERN "A-Z"',
        'INDEX_ORDER "STRIP_THEN_PATCH"',
        "",
        "NUMBER_OF_FIELDS 8",
        "BEGIN_DATA_FORMAT",
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z ",
        "END_DATA_FORMAT", "",
        f"NUMBER_OF_SETS {STRIPS * PER}",
        "BEGIN_DATA",
    ]
    n = 0
    for s in range(1, STRIPS + 1):
        for k in range(PER):
            r, g, b = rgbs[n]
            x, y, z = d[s][k]
            n += 1
            lines.append(f'{n} "{s}{LETTERS[k]}" {r:.5f} {g:.5f} {b:.5f} '
                         f"{x:.5f} {y:.5f} {z:.5f} ")
    lines += ["END_DATA", ""]
    path = base.with_suffix(".ti2")
    path.write_text("\n".join(lines), encoding="latin-1")
    return path


def write_replay(path: Path) -> Path:
    """The replay script: every strip read A -> L."""
    rows = [f"# synthetic strip-9 chart\nPATCHES {PER}"]
    for s in range(1, STRIPS + 1):
        rows.append(f"STRIP {s}")
        rows += [f"{x:.4f} {y:.4f} {z:.4f}" for x, y, z in reading_of(s)]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path
