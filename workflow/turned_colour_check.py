"""Is a measurement of the turned i1Profiler chart on another grid still on
its own patches? Judged by its COLOURS (4.3.32, jctay; option 2 of
``ChromIQ-work/2026-11-10_jctay/analysis.md``).

WHY. Since 4.3.19 an ``.mxf`` of the turned chart whose i1Profiler grid is not
the one the how-to note asks for is refused (`i1profiler_turned.
grid_mismatch`, M-IMPORT-TURNED-GRID): read on another grid, every i1Profiler
row lies across the printed strips and the readings belong to other patches,
while the device values still agree on every patch, because i1Profiler copies
them from its test-chart file. But i1Profiler also re-lays FINISHED readings
when its page settings change after measuring, and keeps every reading on its
patch; jctay's files (one CC24 measurement saved on five grids, one 624-patch
measurement on 1, 6, 18 and 52 pages) are exactly that. Nothing in the file
tells the two apart. The colours can: a reading on its own patch has roughly
the colour that patch should have, a reading taken on another patch mostly
does not.

WHAT IS COMPARED. Entry ``j`` of the turned order (its ``SAMPLE_ID`` ``j+1``)
is compared with the colour the chart expects for the patch the order gives
entry ``j``. For an RGB chart that is targen's own no-profile estimate of its
device values (`patch_flags.targen_estimate_xyz`, the estimate targen writes
into the chart); otherwise the chart's own XYZ columns; with neither there is
nothing to judge by. Expected and measured colours are both taken to
L*a*b* against their own white, and the measure is the analysis's: the RANK
agreement (Spearman's correlation) of expected and measured L*, a* and b*
over the whole chart, the lowest of the three. A rank measure needs no model
of the printer: the estimate is an sRGB-like guess, typically 5 to 10 ΔE from
the real print, but it puts the colours in nearly the right ORDER.

ON TOP OF THE SCORE, so that no arrangement passes by accident:
* the chart must be able to tell: enough patches, enough different colours,
  each of L*, a* and b* spread out, and neighbouring patches along a strip
  different enough that a reading one patch away would not look right too
  (a chart sorted by colour cannot tell, and says so);
* no other arrangement of the same readings may fit nearly as well: every
  readings shifted by one patch, one strip or one entry, mirrored either
  way, turned half a turn, transposed, and the two ways i1Profiler's own
  grid in the file would have placed misread readings;
* every printed strip on its own must fit its own patches clearly better than
  its neighbours one patch along (a single strip read one patch out of place
  hardly moves the whole-chart score on a big chart).
Anything the judgement is not clearly sure of is "cannot tell", which refuses
exactly like a clear disagreement. Nothing is paired by colour: the readings
stay paired by the turned order; this only decides whether the file is filed.

THE THRESHOLDS AND THEIR EVIDENCE (`ChromIQ-work/2026-11-11_4332_features/
evidence_judge_exp2.txt`, measured on jctay's two real files, the ET-8550 and
Canon PRO-300 Okt26 sets of 924 and 1224 patches, and subsets of 16 to 96
patches of both, each randomised and sorted by colour, and on deliberately
wrong versions of each):
* right readings scored 0.82 to 0.94 (jctay's CC24 0.888, his 624 0.942);
  one 24-patch subset of the PRO-300 set scored 0.69, and is "cannot tell";
* wrong arrangements scored at most 0.22 there, at most 0.65 in the
  analysis's simulation of wrong grids on a 24-patch chart sorted by colour;
* along each strip, own-patch fit / neighbour fit (median residual ratio):
  right readings at most 0.34 on randomised charts, a strip slipped by one
  patch at least 2.29; sorted charts 0.56 to 1.04 either way, which is why
  they are "cannot tell" before this point is reached.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from core.logger import get_logger

log = get_logger(__name__)

#: The decisions.
AGREE, DISAGREE, UNSURE = "agree", "disagree", "unsure"

#: Fewer patches than this: cannot tell. Twenty patches give a rank
#: correlation whose chance spread (about 0.22 for unrelated colours) is still
#: well under the gap between right and wrong; jctay's CC24 has 24.
MIN_PATCHES = 20
#: Strips (i1Profiler rows) shorter than this cannot be checked one by one.
MIN_STRIP_PATCHES = 3
#: Fewer clearly different expected colours than this (ΔE76 DISTINCT_DE
#: apart): cannot tell. A CC24 has 24.
MIN_DISTINCT = 16
DISTINCT_DE = 5.0
#: Each of expected L*, a*, b* must spread at least this much (standard
#: deviation), or its rank agreement is noise. A CC24 spreads 20 to 30.
MIN_CHANNEL_SPREAD = 5.0
#: The typical expected-colour difference between neighbours along a strip
#: (median ΔE76 of the estimate) must be at least this, or a reading one
#: patch away would look right too. Randomised real charts: 56 to 97, jctay's
#: CC24 49, his 624 75; charts ordered so that each patch is next to its most
#: similar one: 6 to 30.
MIN_NEIGHBOUR_SEPARATION = 25.0
#: If a wrong arrangement makes the chart's EXPECTED colours agree with
#: themselves this well (over the entries it moves), the chart cannot tell
#: that arrangement from the right one. Randomised real charts at most 0.24,
#: jctay's CC24 at most -0.14, his 624 0.0; charts sorted by hue 0.23 to 0.63
#: and by nearest colour 0.64 to 0.97.
MAX_SELF_LIKENESS = 0.30
#: The score: below DISAGREE_BELOW the readings clearly do not follow the
#: chart; from ACCEPT_FROM they clearly do; between: cannot tell. Right
#: readings 0.82 to 0.94, wrong arrangements at most 0.65 (see above).
ACCEPT_FROM = 0.75
DISAGREE_BELOW = 0.40
#: Another arrangement scoring within this of the right one: cannot tell
#: (higher than the right one: disagree). Right readings are 0.6 or more
#: ahead of every other arrangement.
MIN_LEAD = 0.30
#: Per strip, own-patch fit / fit one patch along: above STRIP_CLEAR cannot
#: tell, from STRIP_WRONG the strip fits a neighbour better (disagree).
STRIP_CLEAR = 0.50
STRIP_WRONG = 1.00


@dataclass(frozen=True)
class ColourJudgement:
    """What the colours say. *why* names the rule that decided:
    ``"agree"``, ``"no-colours"``, ``"few-patches"``, ``"similar"``,
    ``"neighbours"``, ``"short-strips"``, ``"low-score"``, ``"between"``,
    ``"other-arrangement"``, ``"strip-unclear"``, ``"strip-wrong"``."""
    verdict: str
    why: str
    score: float = float("nan")
    patches: int = 0
    strip: "int | None" = None       # 0-based i1Profiler row, strip rules only
    detail: str = ""

    @property
    def agrees(self) -> bool:
        return self.verdict == AGREE

    def log_text(self) -> str:
        s = "n/a" if not math.isfinite(self.score) else f"{self.score:.3f}"
        extra = f", row {self.strip + 1}" if self.strip is not None else ""
        return (f"{self.verdict} ({self.why}{extra}); rank agreement {s} over "
                f"{self.patches} patches{'; ' + self.detail if self.detail else ''}")


# ---------------------------------------------------------------------------
# Small maths
# ---------------------------------------------------------------------------

def _lab(xyz: np.ndarray, white) -> np.ndarray:
    t = np.asarray(xyz, float) / np.asarray(white, float)
    t = np.clip(t, 0.0, None)
    f = np.where(t > 216.0 / 24389.0, np.cbrt(t), (24389.0 / 27.0 * t + 16.0) / 116.0)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]),
                     200 * (f[..., 1] - f[..., 2])], -1)


def _ranks(v: np.ndarray) -> np.ndarray:
    """Ranks with ties averaged."""
    v = np.asarray(v, float)
    o = np.argsort(v, kind="mergesort")
    r = np.empty(len(v))
    r[o] = np.arange(len(v), dtype=float)
    sv = v[o]
    i = 0
    while i < len(v):
        k = i
        while k + 1 < len(v) and sv[k + 1] == sv[i]:
            k += 1
        if k > i:
            r[o[i:k + 1]] = (i + k) / 2.0
        i = k + 1
    return r


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 3:
        return float("nan")
    ra, rb = _ranks(a), _ranks(b)
    sa, sb = ra.std(), rb.std()
    if sa == 0 or sb == 0:
        return float("nan")
    return float(((ra - ra.mean()) * (rb - rb.mean())).mean() / (sa * sb))


def _score(E: np.ndarray, M: np.ndarray, p: "np.ndarray | None" = None) -> float:
    """Lowest of the three rank agreements of E[p[j]] with M[j] (j with
    p[j] >= 0); nan when fewer than three pairs or a channel is constant."""
    if p is None:
        e, m = E, M
    else:
        keep = p >= 0
        e, m = E[p[keep]], M[keep]
    vals = [_spearman(e[:, c], m[:, c]) for c in range(3)]
    if any(not math.isfinite(v) for v in vals):
        return float("nan")
    return min(vals)


# ---------------------------------------------------------------------------
# The arrangements a wrong file could have
# ---------------------------------------------------------------------------

def _cell(rows: int, cols: int, n: int, r, c) -> np.ndarray:
    r, c = np.asarray(r), np.asarray(c)
    ok = (r >= 0) & (r < rows) & (c >= 0) & (c < cols)
    j = c * rows + r
    ok &= j < n
    return np.where(ok, j, -1)


def wrong_arrangements(n: int, rows: int, cols: int,
                       file_cols: "int | None" = None
                       ) -> "dict[str, np.ndarray]":
    """Whole-chart ways the readings could sit on other patches: name ->
    p, where p[j] is the entry whose patch entry j's reading would really be
    of (-1: none). Entry j sits on i1Profiler row ``j % rows`` (one printed
    strip), column ``j // rows`` (its place along the strip). Arrangements
    that leave half the entries where they are are not wrong arrangements of
    the whole chart and are left out (a strip slip is checked per strip)."""
    idx = np.arange(n)
    r, c = idx % rows, idx // rows
    out: "dict[str, np.ndarray]" = {}
    for k in (1, 2):
        out[f"entries+{k}"] = np.where(idx + k < n, idx + k, -1)
        out[f"entries-{k}"] = np.where(idx - k >= 0, idx - k, -1)
    out["along+1"] = _cell(rows, cols, n, r, c + 1)
    out["along-1"] = _cell(rows, cols, n, r, c - 1)
    out["strip+1"] = _cell(rows, cols, n, r + 1, c)
    out["strip-1"] = _cell(rows, cols, n, r - 1, c)
    out["mirrored-along"] = _cell(rows, cols, n, r, cols - 1 - c)
    out["mirrored-strips"] = _cell(rows, cols, n, rows - 1 - r, c)
    out["half-turn"] = _cell(rows, cols, n, rows - 1 - r, cols - 1 - c)
    if n == rows * cols:
        out["rows-and-columns-swapped"] = np.array(
            [(j % cols) * rows + (j // cols) for j in range(n)])
    if file_cols and file_cols != cols:
        out.update(_file_grid_arrangements(n, rows, cols, file_cols))
    return {k: v for k, v in out.items()
            if (v >= 0).sum() >= 3 and float((v == idx).mean()) < 0.5}


def _file_grid_arrangements(n: int, rows: int, cols: int, c2: int
                            ) -> "dict[str, np.ndarray]":
    """The two ways a sheet of *rows* strips of *cols* read on i1Profiler's
    grid of *c2* columns would put readings on entries (the analysis's
    `plaus_sim.wrong_grid`): read strip by strip along i1Profiler's rows, or
    patch by patch filling i1Profiler's grid row by row."""
    r2 = -(-n // c2)
    strip = []
    for j in range(n):
        cc2, rr2 = j // r2, j % r2
        k = cc2 * rows + rr2
        strip.append(k if (cc2 < cols and rr2 < rows and k < n) else -1)
    seq = [c * rows + r for r in range(rows) for c in range(cols)
           if c * rows + r < n]
    cells = [cc * r2 + rr for rr in range(r2) for cc in range(c2)
             if cc * r2 + rr < n]
    m = {cell: seq[k] for k, cell in enumerate(cells) if k < len(seq)}
    return {f"grid-{c2}-by-strip": np.array(strip),
            f"grid-{c2}-by-patch": np.array([m.get(j, -1) for j in range(n)])}


def _strip_entries(n: int, rows: int, cols: int, r: int) -> "list[int]":
    return [c * rows + r for c in range(cols) if c * rows + r < n]


# ---------------------------------------------------------------------------
# The judgement
# ---------------------------------------------------------------------------

def _distinct(E: np.ndarray, de: float) -> int:
    reps: "list[np.ndarray]" = []
    for e in E:
        if all(float(np.linalg.norm(e - r)) >= de for r in reps):
            reps.append(e)
            if len(reps) >= MIN_DISTINCT:
                break
    return len(reps)


def judge(expected_lab, measured_lab, rows: int, cols: int,
          file_cols: "int | None" = None) -> ColourJudgement:
    """Judge readings *measured_lab* (entry order of the turned order) against
    *expected_lab* (the same entries), on the order's grid of *rows* rows
    (printed strips) and *cols* columns. *file_cols* is the grid i1Profiler
    wrote into the file, whose own misreading is asked too."""
    E = np.asarray(expected_lab, float)
    M = np.asarray(measured_lab, float)
    n = len(E)
    if n != len(M) or n == 0 or not np.all(np.isfinite(E)) \
            or not np.all(np.isfinite(M)):
        return ColourJudgement(UNSURE, "no-colours", patches=n)
    if n < MIN_PATCHES:
        return ColourJudgement(UNSURE, "few-patches", patches=n)
    spread = E.std(axis=0)
    if _distinct(E, DISTINCT_DE) < MIN_DISTINCT \
            or float(spread.min()) < MIN_CHANNEL_SPREAD:
        return ColourJudgement(UNSURE, "similar", patches=n,
                               detail=f"spread {np.round(spread, 1).tolist()}")
    if cols < MIN_STRIP_PATCHES:
        return ColourJudgement(UNSURE, "short-strips", patches=n)

    # Can this chart tell at all? Neighbours along each strip, and every
    # whole-chart arrangement applied to the chart's own colours.
    seps = []
    for r in range(rows):
        js = _strip_entries(n, rows, cols, r)
        seps += [float(np.linalg.norm(E[a] - E[b])) for a, b in zip(js, js[1:])]
    sep = float(np.median(seps)) if seps else 0.0
    alts = wrong_arrangements(n, rows, cols, file_cols)
    idx = np.arange(n)
    likeness = float("nan")
    for p in alts.values():
        moved = (p >= 0) & (p != idx)
        if moved.sum() >= 3:
            v = _score(E[moved], E[p[moved]])
            if math.isfinite(v) and not (likeness >= v):
                likeness = v
    likeness = -1.0 if not math.isfinite(likeness) else likeness
    if sep < MIN_NEIGHBOUR_SEPARATION or likeness >= MAX_SELF_LIKENESS:
        return ColourJudgement(
            UNSURE, "neighbours", patches=n,
            detail=f"neighbour separation {sep:.1f}, self-likeness {likeness:.2f}")

    s = _score(E, M)
    if not math.isfinite(s):
        return ColourJudgement(UNSURE, "no-colours", patches=n)
    if s < DISAGREE_BELOW:
        return ColourJudgement(DISAGREE, "low-score", s, n)
    if s < ACCEPT_FROM:
        return ColourJudgement(UNSURE, "between", s, n)
    best_name, best = "", -2.0
    for name, p in alts.items():
        v = _score(E, M, p)
        if math.isfinite(v) and v > best:
            best_name, best = name, v
    if best > s:
        return ColourJudgement(DISAGREE, "other-arrangement", s, n,
                               detail=f"{best_name} scores {best:.3f}")
    if best > s - MIN_LEAD:
        return ColourJudgement(UNSURE, "other-arrangement", s, n,
                               detail=f"{best_name} scores {best:.3f}")

    # Strip by strip: does each fit its own patches clearly better than the
    # patches one place along? Residuals of one affine map from expected to
    # measured colour, fitted over the whole chart.
    X = np.hstack([E, np.ones((n, 1))])
    B, *_ = np.linalg.lstsq(X, M, rcond=None)

    def _fit(e: np.ndarray) -> np.ndarray:
        return np.hstack([e, np.ones((len(e), 1))]) @ B
    own_all = np.linalg.norm(M - _fit(E), axis=1)
    worst_r, worst_ratio = None, 0.0
    for r in range(rows):
        js = _strip_entries(n, rows, cols, r)
        if len(js) < MIN_STRIP_PATCHES:
            continue
        own = float(np.median(own_all[js]))
        ratios = []
        for d in (1, -1):
            here = [js[k] for k in range(len(js)) if 0 <= k + d < len(js)]
            there = [js[k + d] for k in range(len(js)) if 0 <= k + d < len(js)]
            alt = float(np.median(np.linalg.norm(M[here] - _fit(E[there]),
                                                 axis=1)))
            ratios.append(own / alt if alt > 0 else math.inf)
        ratio = max(ratios)
        if ratio > worst_ratio:
            worst_r, worst_ratio = r, ratio
    if worst_r is not None and worst_ratio >= STRIP_WRONG:
        return ColourJudgement(DISAGREE, "strip-wrong", s, n, strip=worst_r,
                               detail=f"own/neighbour fit {worst_ratio:.2f}")
    if worst_r is not None and worst_ratio > STRIP_CLEAR:
        return ColourJudgement(UNSURE, "strip-unclear", s, n, strip=worst_r,
                               detail=f"own/neighbour fit {worst_ratio:.2f}")
    return ColourJudgement(
        AGREE, "agree", s, n,
        detail=(f"next best arrangement {best_name} {best:.3f}; worst strip "
                f"own/neighbour fit {worst_ratio:.2f}"))


# ---------------------------------------------------------------------------
# From the files
# ---------------------------------------------------------------------------

def _expected_lab(entries_device: np.ndarray, chart_ti2: Path,
                  order) -> "np.ndarray | None":
    """The colour the chart expects for each entry, as L*a*b* against the
    chart's own white, or None when the chart files cannot say."""
    from workflow.patch_flags import targen_estimate_xyz
    from workflow.ti3_analysis import Ti3ParseError, parse_ti3
    rep = ""
    try:
        from core.text_io import read_text
        for ln in read_text(chart_ti2, lenient=True).splitlines()[:60]:
            if ln.strip().startswith("COLOR_REP"):
                rep = ln.split(None, 1)[1].strip().strip('"').upper()
                break
    except OSError:
        return None
    if rep in ("RGB", "IRGB") and entries_device is not None \
            and len(entries_device) and entries_device.shape[1] == 3:
        xyz = np.array([targen_estimate_xyz(tuple(v)) for v in entries_device])
        white = np.array(targen_estimate_xyz((100.0, 100.0, 100.0)))
        return _lab(xyz, white)
    # Another colour space: the chart's own expected XYZ, by sample id.
    try:
        design = parse_ti3(Path(chart_ti2))
    except (Ti3ParseError, OSError):
        return None
    xyz = np.asarray(design.xyz, float)
    if xyz.size == 0 or not np.all(np.isfinite(xyz)) or float(xyz[:, 1].max()) <= 0:
        return None
    by_id = {sid: i for i, sid in enumerate(design.sample_ids)}
    try:
        rows = [by_id[sid] for sid in order.sample_ids]
    except KeyError:
        return None
    white = xyz[int(np.argmax(xyz[:, 1]))]
    return _lab(xyz[rows], white)


def judge_turned_measurement(ti3_path: "str | Path", order, chart_ti2,
                             file_cols: "int | None" = None
                             ) -> ColourJudgement:
    """Judge the complete turned measurement *ti3_path* (entries numbered
    1..N in the turned order *order*) against the chart *chart_ti2*."""
    from workflow.ti3_analysis import Ti3ParseError, parse_ti3
    try:
        m = parse_ti3(Path(ti3_path))
    except (Ti3ParseError, OSError) as exc:
        log.info("turned grid colour check: measurement unreadable (%s)", exc)
        return ColourJudgement(UNSURE, "no-colours")
    n = len(order.sample_ids)
    try:
        pos = {int(str(s).strip('"')): i for i, s in enumerate(m.sample_ids)}
        rows_in_entry_order = [pos[j + 1] for j in range(n)]
    except (KeyError, ValueError):
        return ColourJudgement(UNSURE, "no-colours", patches=len(m.sample_ids))
    xyz = np.asarray(m.xyz, float)[rows_in_entry_order]
    dev = (np.asarray(m.rgb, float)[rows_in_entry_order]
           if len(m.rgb) else None)
    E = _expected_lab(dev, Path(chart_ti2), order) if chart_ti2 else None
    if E is None or len(E) != n:
        return ColourJudgement(UNSURE, "no-colours", patches=n)
    white = xyz[int(np.argmax(xyz[:, 1]))] if len(xyz) else None
    if white is None or float(white[1]) <= 0:
        return ColourJudgement(UNSURE, "no-colours", patches=n)
    M = _lab(xyz, white)
    return judge(E, M, int(order.rows), int(order.columns), file_cols)
