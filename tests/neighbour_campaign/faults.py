"""(2b) The faults Knut listed (#182 5983470377 item 5), each with its ground
truth: which patches it changed, how, and by how much (ΔE*ab against the
same patch without the fault).

Two kinds, and the difference matters for what "caught" means:

* ``target="reading"`` - THE INSTRUMENT read wrong (misreads). The sheet is
  fine; a re-read gives the true colour. These are what the neighbour check
  is for (Knut 5983725218: *"finding and highlighting misreads is the
  focus"*), so a red outline on them is a catch.
* ``target="print"`` - THE SHEET really looks like this (printer, paper, ink,
  laser faults). A re-read gives the same colour again, so a red outline
  there turns yellow on re-read. Reported as "flagged" among the affected
  patches, separately, for Knut to judge; never counted as a catch or as a
  false alarm.

Geometry is real: every patch has its page and centre in mm from the chart's
own layout, and a local fault (a line, a band, a roller mark, a wheel track)
changes a patch by the share of the instrument's aperture window it covers
(i1Pro: 4.5 mm wide, the middle 60 % of the patch along the strip; CR30: an
8 mm circle). The paper feeds portrait, top edge first, so a "horizontal"
line runs across the sheet (constant y) and a "vertical" one along the feed
(constant x); i1Pro strips run along y.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from tests.neighbour_campaign.common import lab_to_xyz, xyz_to_lab

#: A patch counts as affected when the fault moved it at least this far.
AFFECTED_DE = 1.0


@dataclass
class FaultResult:
    affected: dict = field(default_factory=dict)   # loc -> {"how", "de"}
    notes: dict = field(default_factory=dict)


@dataclass
class Ctx:
    """What a fault may look at and change."""
    chart: object
    printer: object
    rng: np.random.Generator
    clean_xyz: np.ndarray       # the printer's colour of every patch, no fault
    print_xyz: np.ndarray       # the sheet as printed (a print fault edits it)
    read_xyz: np.ndarray        # the first pass's readings (a misread edits it)
    instr_noise: float = 0.1

    def noisy(self, xyz):
        """*xyz* read once more by the instrument (its repeatability)."""
        xyz = np.atleast_2d(xyz)
        labs = np.array([xyz_to_lab(v) for v in xyz])
        labs += self.rng.normal(0.0, self.instr_noise / math.sqrt(3), labs.shape)
        return np.array([lab_to_xyz(v) for v in labs])


@dataclass
class Fault:
    name: str
    family: str          # misread | printer | paper | ink | laser | none
    target: str          # "reading" or "print" (see the module docstring)
    modes: tuple         # ("strip",), ("patch",) or both
    text: str
    fn: object = None

    def apply(self, ctx: Ctx) -> FaultResult:
        return self.fn(ctx) if self.fn else FaultResult()


# ---- geometry ---------------------------------------------------------------
def _window(ctx: Ctx, i: int, n: int = 11):
    """Sample points (x, y) in mm of patch *i*'s aperture window."""
    c = ctx.chart
    u = (np.arange(n) + 0.5) / n - 0.5
    if c.mode == "patch":
        d = 8.0
        xs, ys = np.meshgrid(u * d, u * d)
        keep = xs ** 2 + ys ** 2 <= (d / 2) ** 2
        return c.cx[i] + xs[keep], c.cy[i] + ys[keep]
    xs, ys = np.meshgrid(u * min(4.5, c.w[i]), u * 0.6 * c.h[i])
    return c.cx[i] + xs.ravel(), c.cy[i] + ys.ravel()


def coverage(ctx: Ctx, region) -> np.ndarray:
    """The share of each patch's aperture window *region(page, x, y)* covers."""
    out = np.zeros(ctx.chart.n)
    for i in range(ctx.chart.n):
        x, y = _window(ctx, i)
        out[i] = float(np.mean(region(int(ctx.chart.page[i]), x, y)))
    return out


def _periodic(y, y0, period, height):
    return ((y - y0) % period) < height


def _lab(xyz):
    return np.array([xyz_to_lab(v) for v in np.atleast_2d(xyz)])


def _de(a, b) -> np.ndarray:
    return np.linalg.norm(_lab(a) - _lab(b), axis=1)


def _record(ctx: Ctx, before, after, how: str, res: FaultResult,
            idx=None) -> None:
    """Note every patch *after* differs from *before* by AFFECTED_DE or more."""
    d = _de(before, after)
    for i in (range(ctx.chart.n) if idx is None else idx):
        if d[i] >= AFFECTED_DE:
            prev = res.affected.get(ctx.chart.locs[i])
            res.affected[ctx.chart.locs[i]] = {
                "how": how if prev is None else prev["how"] + "+" + how,
                "de": round(float(d[i]), 2)}


def _mix_print(ctx, f, alt, how) -> FaultResult:
    """The sheet where a local fault covers share *f* of the window: the
    aperture averages reflectance, so XYZ mixes linearly."""
    res = FaultResult()
    before = ctx.print_xyz.copy()
    ctx.print_xyz[:] = (1 - f)[:, None] * ctx.print_xyz + f[:, None] * alt
    _record(ctx, before, ctx.print_xyz, how, res)
    res.notes["patches_touched"] = int((f > 0).sum())
    return res


def _rgb_more_ink(rgb, d):
    return np.clip(rgb * (1 - d), 0, 100)


def _rgb_less_ink(rgb, d):
    return np.clip(rgb + d * (100 - rgb), 0, 100)


def _grey(ctx, v):
    return ctx.printer.xyz(np.full((ctx.chart.n, 3), float(v)))


def _paper(ctx):
    return np.tile(ctx.printer.paper_xyz, (ctx.chart.n, 1))


def _H(ctx):
    return ctx.chart.paper_mm[1]


def _W(ctx):
    return ctx.chart.paper_mm[0]


# ---- misreads: the instrument read wrong --------------------------------------
def _middle_strips(ctx, k=1):
    order = ctx.chart.strip_order
    lo, hi = len(order) // 3, max(len(order) // 3 + 1, 2 * len(order) // 3)
    pool = order[lo:hi] or order
    return list(ctx.rng.choice(pool, size=min(k, len(pool)), replace=False))


def _donor(ctx, i, lo=15.0, hi=60.0):
    """A patch of another strip whose colour lies lo..hi ΔE from patch i's."""
    c = ctx.chart
    d = _de(np.tile(ctx.print_xyz[i], (c.n, 1)), ctx.print_xyz)
    ok = [j for j in range(c.n) if c.strips[j] != c.strips[i] and lo <= d[j] <= hi]
    return int(ctx.rng.choice(ok)) if ok else int((i + c.n // 2) % c.n)


def glitch(ctx, count=1, how="glitch") -> FaultResult:
    """A single patch carries another patch's colour (the reader jumped)."""
    res = FaultResult()
    c = ctx.chart
    members = c.strip_members()
    before = ctx.read_xyz.copy()
    for s in _middle_strips(ctx, count):
        m = members[s]
        i = int(ctx.rng.choice(m[1:-1] if len(m) > 2 else m))
        j = _donor(ctx, i)
        ctx.read_xyz[i] = ctx.noisy(ctx.print_xyz[j])[0]
        res.notes.setdefault("pairs", []).append([c.locs[i], c.locs[j]])
    _record(ctx, before, ctx.read_xyz, how, res)
    return res


def out_of_step(ctx) -> FaultResult:
    """From patch k on, the strip's readings are one patch out (a slipped
    strip): each patch carries its successor's colour, the last the paper."""
    res = FaultResult()
    c = ctx.chart
    s = _middle_strips(ctx)[0]
    m = c.strip_members()[s]
    k = int(ctx.rng.integers(len(m) // 4, max(len(m) // 4 + 1, len(m) // 2)))
    before = ctx.read_xyz.copy()
    for a, i in enumerate(m[k:], start=k):
        src = ctx.print_xyz[m[a + 1]] if a + 1 < len(m) else ctx.printer.paper_xyz
        ctx.read_xyz[i] = ctx.noisy(src)[0]
    _record(ctx, before, ctx.read_xyz, "out_of_step", res, m)
    res.notes.update(strip=s, from_patch=c.locs[m[k]])
    return res


def _wrong_strip(ctx, step) -> FaultResult:
    res = FaultResult()
    c = ctx.chart
    order = c.strip_order
    if len(order) < 3:
        res.notes["skipped"] = "fewer than 3 strips"
        return res
    s = _middle_strips(ctx)[0]
    k = order.index(s)
    t = order[max(0, min(len(order) - 1, k + step))]
    ms, mt = c.strip_members()[s], c.strip_members()[t]
    before = ctx.read_xyz.copy()
    for a, i in enumerate(ms):
        src = ctx.print_xyz[mt[a]] if a < len(mt) else ctx.printer.paper_xyz
        ctx.read_xyz[i] = ctx.noisy(src)[0]
    _record(ctx, before, ctx.read_xyz, f"wrong_strip({t})", res, ms)
    res.notes.update(strip=s, read_instead=t)
    return res


def partial_strip(ctx) -> FaultResult:
    """The reader lifted off part-way: from patch k the readings fall to 90 %
    and on to 60 % of the colour's light (it reads further and further away)."""
    res = FaultResult()
    c = ctx.chart
    s = _middle_strips(ctx)[0]
    m = c.strip_members()[s]
    k = int(ctx.rng.integers(int(len(m) * 0.4), max(int(len(m) * 0.4) + 1,
                                                     int(len(m) * 0.7))))
    before = ctx.read_xyz.copy()
    tail = m[k:]
    for a, i in enumerate(tail):
        u = 0.9 - 0.3 * a / max(1, len(tail) - 1)
        ctx.read_xyz[i] = ctx.noisy(ctx.print_xyz[i] * u)[0]
    _record(ctx, before, ctx.read_xyz, "partial_strip", res, m)
    res.notes.update(strip=s, lifted_from=c.locs[m[k]])
    return res


def smudge_aperture(ctx) -> FaultResult:
    """Dirt on the aperture for one patch: 30 % of the window reads dark grey."""
    res = FaultResult()
    c = ctx.chart
    s = _middle_strips(ctx)[0]
    m = c.strip_members()[s]
    i = int(ctx.rng.choice(m))
    before = ctx.read_xyz.copy()
    grey = ctx.printer.xyz(np.array([[20.0, 20.0, 20.0]]))[0]
    ctx.read_xyz[i] = ctx.noisy(0.7 * ctx.print_xyz[i] + 0.3 * grey)[0]
    _record(ctx, before, ctx.read_xyz, "smudge_aperture", res, [i])
    return res


def wrong_patch(ctx) -> FaultResult:
    """Patch by patch: the CR30 was put on the NEIGHBOURING patch on the page."""
    res = FaultResult()
    c = ctx.chart
    before = ctx.read_xyz.copy()
    for s in _middle_strips(ctx, 2):
        m = c.strip_members()[s]
        i = int(ctx.rng.choice(m))
        same = np.nonzero(c.page == c.page[i])[0]
        d = np.hypot(c.cx[same] - c.cx[i], c.cy[same] - c.cy[i])
        d[same == i] = np.inf
        j = int(same[int(np.argmin(d))])
        ctx.read_xyz[i] = ctx.noisy(ctx.print_xyz[j])[0]
        res.notes.setdefault("pairs", []).append([c.locs[i], c.locs[j]])
    _record(ctx, before, ctx.read_xyz, "wrong_patch", res)
    return res


def lifted_spot(ctx) -> FaultResult:
    """Patch by patch: the CR30 was tilted on one patch (reads 75 % light)."""
    res = FaultResult()
    c = ctx.chart
    s = _middle_strips(ctx)[0]
    i = int(ctx.rng.choice(c.strip_members()[s]))
    before = ctx.read_xyz.copy()
    ctx.read_xyz[i] = ctx.noisy(ctx.print_xyz[i] * 0.75)[0]
    _record(ctx, before, ctx.read_xyz, "lifted_spot", res, [i])
    return res


# ---- inkjet printer faults: the sheet --------------------------------------------
def banding(ctx) -> FaultResult:
    """Paper-advance banding: a 2.5 mm darker band (8 % more ink) every
    25.4 mm across the sheet."""
    y0 = float(ctx.rng.uniform(0, 25.4))
    f = coverage(ctx, lambda p, x, y: _periodic(y, y0, 25.4, 2.5))
    alt = ctx.printer.xyz(_rgb_more_ink(ctx.chart.rgb, 0.08))
    return _mix_print(ctx, f, alt, "banding")


def nozzle_lines(ctx) -> FaultResult:
    """A clogged bank of nozzles of ONE ink: a 0.3 mm line without that ink
    every 2.1 mm (one ink missing on 14 % of the area)."""
    ch = int(ctx.rng.integers(0, 3))
    y0 = float(ctx.rng.uniform(0, 2.1))
    f = coverage(ctx, lambda p, x, y: _periodic(y, y0, 2.1, 0.3))
    rgb = ctx.chart.rgb.copy()
    rgb[:, ch] = 100.0
    res = _mix_print(ctx, f, ctx.printer.xyz(rgb), "nozzle_lines")
    res.notes["ink"] = "CMY"[ch]
    return res


def ink_starvation(ctx) -> FaultResult:
    """One ink runs dry: from a point on a page its density falls away (to
    70 % less ink over 80 mm) and stays low on every later page."""
    c = ctx.chart
    ch = int(ctx.rng.integers(0, 3))
    p0 = int(ctx.rng.integers(0, max(1, c.page.max() + 1)))
    y0 = float(ctx.rng.uniform(0.2, 0.6) * _H(ctx))
    t = np.where(c.page > p0, 1.0,
                 np.where(c.page < p0, 0.0, np.clip((c.cy - y0) / 80.0, 0, 1)))
    s = 0.7 * t
    rgb = c.rgb.copy()
    rgb[:, ch] = rgb[:, ch] + s * (100 - rgb[:, ch])
    res = FaultResult()
    before = ctx.print_xyz.copy()
    ctx.print_xyz[:] = ctx.printer.xyz(rgb) * (ctx.print_xyz / np.maximum(
        ctx.clean_xyz, 1e-6))
    _record(ctx, before, ctx.print_xyz, "ink_starvation", res)
    res.notes.update(ink="CMY"[ch], page=p0, from_y_mm=round(y0, 1))
    return res


# ---- paper ---------------------------------------------------------------------------
def _lab_edit(ctx, fn, how) -> FaultResult:
    res = FaultResult()
    before = ctx.print_xyz.copy()
    labs = _lab(ctx.print_xyz)
    new = fn(labs)
    ctx.print_xyz[:] = np.array([lab_to_xyz(v) for v in new])
    _record(ctx, before, ctx.print_xyz, how, res)
    return res


def oba_shift(ctx) -> FaultResult:
    """Brightener: the paper and the light colours read 5 b* bluer (a
    different paper batch, or M1 against M0) - the whole sheet alike."""
    Lp = xyz_to_lab(ctx.printer.paper_xyz)[0]

    def fn(lab):
        w = np.clip((lab[:, 0] - 30) / max(1, Lp - 30), 0, 1)
        lab = lab.copy()
        lab[:, 2] -= 5.0 * w
        return lab
    return _lab_edit(ctx, fn, "oba_shift")


def matte_page(ctx) -> FaultResult:
    """One sheet printed on matte paper where the rest are semi-gloss (the
    last page; a one-page chart is then matte throughout)."""
    from tests.neighbour_campaign.printers import load
    c = ctx.chart
    matte = load("inkjet_matte")
    p = int(c.page.max())
    res = FaultResult()
    before = ctx.print_xyz.copy()
    sel = c.page == p
    ratio = ctx.print_xyz / np.maximum(ctx.clean_xyz, 1e-6)
    ctx.print_xyz[sel] = matte.xyz(c.rgb[sel]) * ratio[sel]
    _record(ctx, before, ctx.print_xyz, "matte_page", res)
    res.notes["page"] = p
    return res


def cockle(ctx) -> FaultResult:
    """Cockled paper: a 60 x 40 mm bulge on one page reads up to 7 % lighter
    or darker (the sheet is nearer or further from the reader)."""
    c = ctx.chart
    p = int(ctx.rng.integers(0, c.page.max() + 1))
    x0 = float(ctx.rng.uniform(0.25, 0.75) * _W(ctx))
    y0 = float(ctx.rng.uniform(0.25, 0.75) * _H(ctx))
    a = float(ctx.rng.choice([-1, 1]) * 0.07)
    bump = np.where(c.page == p, np.exp(-(((c.cx - x0) / 30) ** 2
                                          + ((c.cy - y0) / 20) ** 2)), 0.0)
    res = FaultResult()
    before = ctx.print_xyz.copy()
    ctx.print_xyz[:] = ctx.print_xyz * (1 + a * bump)[:, None]
    _record(ctx, before, ctx.print_xyz, "cockle", res)
    res.notes.update(page=p, centre_mm=[round(x0), round(y0)], gain=a)
    return res


def uneven(ctx) -> FaultResult:
    """Uneven coating: a smooth L* and b* wave over every sheet (±2)."""
    c = ctx.chart
    ph = ctx.rng.uniform(0, 2 * math.pi, 4)

    def fn(lab):
        lab = lab.copy()
        lab[:, 0] += 2.0 * np.sin(c.cx / 70 + ph[0]) * np.cos(c.cy / 90 + ph[1])
        lab[:, 2] += 1.5 * np.sin(c.cy / 60 + ph[2] + c.page)
        return lab
    return _lab_edit(ctx, fn, "uneven")


# ---- ink aging --------------------------------------------------------------------------
def _hue_drift(ctx, strength) -> FaultResult:
    c = ctx.chart
    ch = int(ctx.rng.integers(0, 3))
    amount = (100 - c.rgb[:, ch]) / 100.0 * strength

    def fn(lab):
        lab = lab.copy()
        h = np.arctan2(lab[:, 2], lab[:, 1]) + np.radians(10.0) * amount
        C = np.hypot(lab[:, 1], lab[:, 2]) * (1 - 0.15 * amount)
        lab[:, 1], lab[:, 2] = C * np.cos(h), C * np.sin(h)
        return lab
    res = _lab_edit(ctx, fn, "ink_aging")
    res.notes["ink"] = "CMY"[ch]
    return res


def ink_aging(ctx) -> FaultResult:
    """An aged ink: where it is used, hue turns 10° and chroma drops 15 %
    (in proportion to how much of it a patch carries) - the whole chart."""
    return _hue_drift(ctx, np.ones(ctx.chart.n))


def ink_aging_gradual(ctx) -> FaultResult:
    """The same drift growing through the print, from none on the first
    patch row to full on the last (pages, then down the page)."""
    c = ctx.chart
    t = (c.page + c.cy / _H(ctx)) / (c.page.max() + 1)
    return _hue_drift(ctx, t)


# ---- laser / toner ------------------------------------------------------------------------
def laser_lines_h(ctx) -> FaultResult:
    """A scratched drum: a 0.8 mm dark toner line across the sheet, every
    94.2 mm (the drum's circumference)."""
    y0 = float(ctx.rng.uniform(0, 94.2))
    f = coverage(ctx, lambda p, x, y: _periodic(y, y0, 94.2, 0.8))
    return _mix_print(ctx, f, _grey(ctx, 15), "laser_line_h")


def laser_line_v(ctx) -> FaultResult:
    """A dirty charge wire or developer blade: a 1 mm dark streak along the
    feed, at the same x on every sheet."""
    x0 = float(ctx.rng.uniform(0.2, 0.8) * _W(ctx))
    f = coverage(ctx, lambda p, x, y: np.abs(x - x0) < 0.5)
    res = _mix_print(ctx, f, _grey(ctx, 15), "laser_line_v")
    res.notes["x_mm"] = round(x0, 1)
    return res


def roller_marks(ctx) -> FaultResult:
    """A damaged developer roller: a 4 x 12 mm pale mark (toner missing)
    every 37.7 mm down the sheet, at one place across it."""
    y0 = float(ctx.rng.uniform(0, 37.7))
    x0 = float(ctx.rng.uniform(0.15, 0.85) * _W(ctx))
    f = coverage(ctx, lambda p, x, y: _periodic(y, y0, 37.7, 4.0)
                 & (np.abs(x - x0) < 6.0))
    res = _mix_print(ctx, f, 0.4 * ctx.print_xyz + 0.6 * _paper(ctx),
                     "roller_mark")
    res.notes["x_mm"] = round(x0, 1)
    return res


def transfer_dropouts(ctx) -> FaultResult:
    """Poor transfer: six round pale spots (3 to 6 mm) per sheet where half
    the toner did not transfer."""
    c = ctx.chart
    blobs = {p: [(ctx.rng.uniform(0.1, 0.9) * _W(ctx),
                  ctx.rng.uniform(0.1, 0.9) * _H(ctx),
                  ctx.rng.uniform(3, 6)) for _ in range(6)]
             for p in range(int(c.page.max()) + 1)}

    def region(p, x, y):
        m = np.zeros_like(x, dtype=bool)
        for bx, by, r in blobs[p]:
            m |= (x - bx) ** 2 + (y - by) ** 2 < r * r
        return m
    f = coverage(ctx, region)
    return _mix_print(ctx, f, 0.5 * ctx.print_xyz + 0.5 * _paper(ctx),
                      "transfer_dropout")


def fuser_bands(ctx) -> FaultResult:
    """A fuser (heater) roller fault: a 12 mm band 10 % lighter across the
    sheet every 75.4 mm (the roller's circumference)."""
    y0 = float(ctx.rng.uniform(0, 75.4))
    f = coverage(ctx, lambda p, x, y: _periodic(y, y0, 75.4, 12.0))
    alt = ctx.printer.xyz(_rgb_less_ink(ctx.chart.rgb, 0.10))
    return _mix_print(ctx, f, alt * ctx.print_xyz / np.maximum(ctx.clean_xyz, 1e-6),
                      "fuser_band")


def wheel_smudges(ctx) -> FaultResult:
    """Rubber paper-guide wheels: two narrow (2 mm) dark tracks along the
    feed, a third and two thirds across the sheet, smearing 40 % grey."""
    xs = (_W(ctx) / 3 + float(ctx.rng.uniform(-10, 10)),
          2 * _W(ctx) / 3 + float(ctx.rng.uniform(-10, 10)))
    f = coverage(ctx, lambda p, x, y: (np.abs(x - xs[0]) < 1.0)
                 | (np.abs(x - xs[1]) < 1.0))
    smear = 0.6 * ctx.print_xyz + 0.4 * _grey(ctx, 35)
    res = _mix_print(ctx, f, smear, "wheel_smudge")
    res.notes["x_mm"] = [round(v, 1) for v in xs]
    return res


BOTH = ("strip", "patch")
FAULTS = {f.name: f for f in [
    Fault("none", "none", "print", BOTH, "a clean measurement", None),
    Fault("glitch", "misread", "reading", BOTH, "one patch carries another "
          "patch's colour (15-60 ΔE away)", glitch),
    Fault("glitch3", "misread", "reading", BOTH, "three such patches in "
          "three strips", lambda c: glitch(c, 3)),
    Fault("smudge_aperture", "misread", "reading", BOTH, "dirt on the "
          "aperture for one patch (30 % dark grey)", smudge_aperture),
    Fault("out_of_step", "misread", "reading", ("strip",), "a strip one "
          "patch out from a point on", out_of_step),
    Fault("wrong_strip_prev", "misread", "reading", ("strip",), "the strip "
          "before read again and filed as this one", lambda c: _wrong_strip(c, -1)),
    Fault("wrong_strip_next", "misread", "reading", ("strip",), "the next "
          "strip read and filed as this one", lambda c: _wrong_strip(c, +1)),
    Fault("partial_strip", "misread", "reading", ("strip",), "the reader "
          "lifted part-way along a strip", partial_strip),
    Fault("wrong_patch", "misread", "reading", ("patch",), "the CR30 put on "
          "the neighbouring patch (twice)", wrong_patch),
    Fault("lifted_spot", "misread", "reading", ("patch",), "the CR30 tilted "
          "on one patch", lifted_spot),
    Fault("banding", "printer", "print", BOTH, "inkjet paper-advance banding",
          banding),
    Fault("nozzle_lines", "printer", "print", BOTH, "a clogged nozzle bank "
          "of one ink", nozzle_lines),
    Fault("ink_starvation", "printer", "print", BOTH, "one ink running dry "
          "part-way through", ink_starvation),
    Fault("oba_shift", "paper", "print", BOTH, "brightener shift, whole "
          "sheet", oba_shift),
    Fault("matte_page", "paper", "print", BOTH, "the last sheet on matte "
          "paper", matte_page),
    Fault("cockle", "paper", "print", BOTH, "a cockled bulge on one page",
          cockle),
    Fault("uneven", "paper", "print", BOTH, "uneven coating over the sheet",
          uneven),
    Fault("ink_aging", "ink", "print", BOTH, "one aged ink, whole chart",
          ink_aging),
    Fault("ink_aging_gradual", "ink", "print", BOTH, "an ink drifting "
          "through the print", ink_aging_gradual),
    Fault("laser_lines_h", "laser", "print", BOTH, "drum scratch lines every "
          "94.2 mm", laser_lines_h),
    Fault("laser_line_v", "laser", "print", BOTH, "a streak along the feed",
          laser_line_v),
    Fault("roller_marks", "laser", "print", BOTH, "developer roller marks "
          "every 37.7 mm", roller_marks),
    Fault("transfer_dropouts", "laser", "print", BOTH, "pale transfer "
          "dropouts", transfer_dropouts),
    Fault("fuser_bands", "laser", "print", BOTH, "fuser roller density bands "
          "every 75.4 mm", fuser_bands),
    Fault("wheel_smudges", "laser", "print", BOTH, "paper-guide wheel "
          "tracks", wheel_smudges),
]}
