"""Whole-strip misreads: found as a block and left out of the build (Agent 22).

Research token ``a22-strip`` (Maximum accuracy only). Findings:
``ProfileEngineResearch/Findings/agent22-01-misread-robust.md``.

**What a strip misread is.** A strip-reading instrument reads one strip (one
pass) at a time; when it loses the patch separators, or the wrong strip or
sheet is read, EVERY patch of that pass gets a wrong reading (Basti's real
ColorMunki re-reads: strip D, 15 patches, 8 to 57 dE00 off, none of them the
neighbour's reading). ArgyllCMS's chartread looks at a strip as a block for
the same reason (``spectro/chartread.c``: mean dE of the whole strip against
every strip's expected values). Its warning can be overridden, ChromIQ's own
flags (patch limit, strip test, neighbour check) are flags the user can
save past, and imported measurements never meet them, so the readings can
still reach the build.

**Why the per-patch robust fit is not enough.** ``accuracy.py`` already
down-weights or rejects patches against a stiff scan (Huber, rejection at
8 robust scales). That is an M-estimator on a scan that has SEEN the misread
strip: the strip pulls the scan towards itself and inflates the robust
scale (0.66 -> 0.93-1.11 dE00 with three strips on the battery), so some of
its patches keep a partial weight, the threshold loosens for every patch,
and the earlier steps (ramp curves, the cross-validated smoothing, the GP's
hyperparameters, the colprof oracle for the perceptual tables) see the
misread rows at full weight.

**The rule (a group-deletion diagnostic, the textbook answer to masking).**

1. The strips are read from SAMPLE_LOC (``A1``, ``AB12``: the letters name
   the strip, ``INDEX_ORDER "STRIP_THEN_PATCH"``, every printtarg chart).
   Without such locations nothing happens.
2. Every patch's ΔE2000 residual from a stiff fit (12 strips or more: one
   fit of the whole chart; fewer strips: each strip from a fit WITHOUT it,
   because a sparse chart's fit interpolates its own misreads; then the
   worst strip is suspect when its median residual is 3 times the other
   strips' typical one, and this is repeated without it).
3. A strip is SUSPECT when the MEDIAN residual of its patches is above
   ``max(MIN_DE, median + K_SCALE x 1.4826 MAD)`` of the chart: more than
   half of the strip is grossly off at once. An isolated misread or a hard
   colour region never moves a strip's median; a random layout puts a
   strip's patches all over colour space.
3b. Out-of-step strips over ORDERED rows (printtarg -r, a ramp read one
   patch late) are not looked for: every rule tried (Argyll's off-by-one
   shift, judged on a fit without the strip) also took clean grey ramps
   (Findings agent22-01 s5), and ChromIQ's charts are randomised.
4. The suspects are left out, the stiff fit is made again, and EVERY strip
   is judged again against the new fit: a strip that now fits is taken back
   (add-back), a strip the first fit had masked is found. Repeated until
   nothing changes (at most ``MAX_ROUNDS``).
5. Guards: never more than ``MAX_SHARE`` of the chart (then something else
   is wrong, e.g. the wrong chart, and nothing is dropped); the chart's
   paper white and darkest patch are never dropped when no other copy of
   them survives.

On a chart without a suspect strip the build is byte-identical to the build
without the token: nothing in the pipeline changes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

MIN_DE = 3.0          # a strip's median residual must exceed this (dE00) ...
K_SCALE = 5.0         # ... and the chart median + 5 robust sigmas
MIN_STRIP = 4         # shorter strips are not judged
MAX_SHARE = 0.25      # never drop more than this share of the chart
MAX_ROUNDS = 4

DENSE_STRIPS = 12     # from this many strips on, one fit judges them all
SPARSE_RATIO = 3.0    # fewer strips: the worst must be 3x the others' error
ORDER_RATIO = 0.5     # an ordered strip: consecutive patches this much closer
LEVERAGE = 2.0        # left out, a patch farther than 2x the chart's typical
                      # nearest-neighbour distance from the rest is not judged

_LOC_RE = re.compile(r"^([A-Za-z]+)(\d+)$")


def _patch_order(sample_locs, ids):
    """Rows of each strip in patch order (the digits of SAMPLE_LOC)."""
    num = np.array([int(_LOC_RE.match(str(l).strip()).group(2))
                    for l in sample_locs])
    out = {}
    for g in np.unique(ids):
        rows = np.flatnonzero(ids == g)
        out[int(g)] = rows[np.argsort(num[rows], kind="stable")]
    return out


def strip_ids(sample_locs) -> np.ndarray | None:
    """Strip index per row from SAMPLE_LOC (letters = strip), or None."""
    if not sample_locs:
        return None
    names = []
    for loc in sample_locs:
        m = _LOC_RE.match(str(loc).strip())
        if m is None:
            return None
        names.append(m.group(1).upper())
    uniq = {n: i for i, n in enumerate(dict.fromkeys(names))}
    ids = np.array([uniq[n] for n in names], int)
    sizes = np.bincount(ids)
    if len(sizes) < 3 or np.median(sizes) < MIN_STRIP:
        return None
    return ids


@dataclass
class StripVerdict:
    dropped_rows: np.ndarray = field(default_factory=lambda: np.array([], int))
    strips: list = field(default_factory=list)   # [(name, n, med_de, min_de, max_de)]
    note: str = ""


def _predict(device, lab, keep, grid, lam):
    from workflow.profile_engine.forward_model import fit_forward_model
    m = fit_forward_model(device[keep], lab[keep], grid=grid, lam=lam,
                          curve_rounds=1, cg_iters=350, cg_rtol=1e-12)
    return m.predict(device)


def _ordered(device, order, judged):
    """Strips whose patches run in order through device space (a ramp:
    printtarg -r, or a chart laid out by hand): consecutive patches much
    closer than two random patches of the chart. Left out, such a strip
    takes its whole region with it, so it is never judged that way (the
    battery's September chart at 120 patches: every 11-step ramp strip
    looked misread when left out)."""
    rng = np.random.default_rng(7)
    a, b = rng.integers(0, len(device), (2, 2000))
    typical = float(np.median(np.linalg.norm(device[a] - device[b], axis=1)))
    out = set()
    for g in judged:
        d = device[order[g]]
        step = float(np.median(np.linalg.norm(np.diff(d, axis=0), axis=1)))
        if step < ORDER_RATIO * typical:
            out.add(g)
    return out


def _layout_random(meas) -> bool:
    """True when the chart's patches were placed at random by printtarg:
    the RANDOM_START keyword, in the .ti3 itself or in the chart's .ti2
    beside it (or one or two folders up, the run folder). A sparse chart
    laid out in order holds whole regions in one strip, and a strip left
    out of the fit then looks misread (Findings agent22-01 s5b)."""
    from pathlib import Path
    if "RANDOM_START" in (meas.keywords or {}):
        return True
    try:
        p = Path(meas.path)
    except TypeError:
        return False
    for d in (p.parent, p.parent.parent, p.parent.parent.parent):
        for c in [d / (p.stem + ".ti2")] + sorted(d.glob("*.ti2"))[:4]:
            try:
                if c.is_file() and "RANDOM_START" in c.read_text(
                        encoding="utf-8", errors="replace")[:4000]:
                    return True
            except OSError:
                continue
    return False


def _loso_residuals(device, lab, ids, keep, judged, order, grid, lam):
    """Each strip's residuals from a fit of every OTHER kept strip; an
    ordered strip's from the fit of all kept strips (it stays in)."""
    from workflow.profile_engine.metrics import delta_e_2000
    res = np.zeros(len(device))
    ordered = _ordered(device, order, judged)
    seen = None
    d2 = ((device[:, None, :] - device[None, :, :]) ** 2).sum(-1)
    np.fill_diagonal(d2, np.inf)
    nn_typ = float(np.median(np.sqrt(d2.min(1))))
    for g in judged:
        rows = order[g]
        if g in ordered:
            if seen is None:
                seen = delta_e_2000(_predict(device, lab, keep, grid, lam), lab)
            res[rows] = seen[rows]
            continue
        k2 = keep.copy()
        k2[rows] = False
        r = delta_e_2000(_predict(device, lab, k2, grid, lam)[rows], lab[rows])
        # a patch with no other patch near it (a device corner, the only
        # sample of its region) is extrapolated when its strip is left out,
        # misread or not: judge the strip by the patches the rest of the
        # chart can predict (the battery's 120-patch chart: a strip of the
        # 16 cube corners looked misread when left out)
        nn = np.sqrt(((device[rows][:, None, :] - device[k2][None, :, :]) ** 2
                      ).sum(-1)).min(1)
        ok = nn <= LEVERAGE * nn_typ
        if ok.sum() >= MIN_STRIP:
            r = np.where(ok, r, np.nan)
        else:
            if seen is None:
                seen = delta_e_2000(_predict(device, lab, keep, grid, lam), lab)
            r = seen[rows]
        res[rows] = r
    return res


def detect(meas, *, grid: int, lam: float) -> StripVerdict:
    """Suspect strips of ``meas`` (see the module text)."""
    ids = strip_ids(meas.sample_locs)
    if ids is None:
        return StripVerdict(note="no strip locations")
    device, lab = meas.device, meas.lab_relative
    n = len(device)
    sizes = np.bincount(ids)
    judged = [g for g in range(len(sizes)) if sizes[g] >= MIN_STRIP]
    order = _patch_order(meas.sample_locs, ids)
    keep = np.ones(n, bool)
    suspects: set = set()
    res = None
    if len(judged) >= DENSE_STRIPS:
        # many strips: one fit of the chart, the patch-level threshold
        from workflow.profile_engine.metrics import delta_e_2000
        for _ in range(MAX_ROUNDS):
            res = delta_e_2000(_predict(device, lab, keep, grid, lam), lab)
            r_in = res[keep]
            med = float(np.median(r_in))
            s = 1.4826 * float(np.median(np.abs(r_in - med)))
            thr = max(MIN_DE, med + K_SCALE * s)
            new = {g for g in judged if float(np.median(res[order[g]])) > thr}
            if new == suspects:
                break
            suspects = new
            keep = ~np.isin(ids, sorted(suspects))
    elif _layout_random(meas):
        # few strips (a one-page chart): a fit of the chart interpolates its
        # own misreads, so each strip is predicted by a fit WITHOUT it, and
        # the worst strip is compared with the others' typical error; the
        # worst one out at a time, until none stands out
        while True:
            res = _loso_residuals(device, lab, ids, keep, judged, order,
                                  grid, lam)
            live = [g for g in judged if g not in suspects]
            if len(live) < 3:
                break
            m = {g: float(np.nanmedian(res[order[g]])) for g in live}
            worst = max(m, key=m.get)
            rest = float(np.median([v for g, v in m.items() if g != worst]))
            if m[worst] > max(MIN_DE, SPARSE_RATIO * rest):
                suspects.add(worst)
                keep = ~np.isin(ids, sorted(suspects))
            else:
                break
    if not suspects:
        return StripVerdict()
    rows = np.flatnonzero(np.isin(ids, sorted(suspects)))
    if len(rows) > MAX_SHARE * n:
        return StripVerdict(note=f"{len(suspects)} strips looked misread "
                                 f"({len(rows)} of {n} patches): too many to "
                                 f"leave out, kept")
    # never lose the only paper white / darkest patch
    ink = device.sum(1) if not meas.is_additive else (1.0 - device).sum(1)
    for corner in (np.flatnonzero(ink <= ink.min() + 1e-9),
                   np.flatnonzero(ink >= ink.max() - 1e-9)):
        if np.isin(corner, rows).all():
            rows = np.setdiff1d(rows, corner)
    names = {i: re.match(_LOC_RE, meas.sample_locs[int(np.flatnonzero(ids == i)[0])]
                         ).group(1).upper() for i in suspects}
    info = []
    for g in sorted(suspects):
        r = res[order[g]]
        info.append((names[g], int(len(r)), float(np.nanmedian(r)), float(np.nanmin(r)),
                     float(np.nanmax(r))))
    return StripVerdict(dropped_rows=rows, strips=info)


def without_rows(meas, rows, workdir):
    """A copy of ``meas`` read from a .ti3 without ``rows`` (data lines in
    the file's order), written in ``workdir``; the original text is kept as
    the measurement the profile records."""
    from pathlib import Path
    from workflow.profile_engine.ti3_data import read_ti3
    drop = set(int(r) for r in rows)
    lines = meas.text.splitlines()
    out, data, row = [], False, 0
    for ln in lines:
        s = ln.strip()
        if s.startswith("NUMBER_OF_SETS"):
            ln = f"NUMBER_OF_SETS {len(meas.device) - len(drop)}"
        elif s == "BEGIN_DATA":
            data = True
        elif s == "END_DATA":
            data = False
        elif data and s:
            row += 1
            if row - 1 in drop:
                continue
        out.append(ln)
    p = Path(workdir) / Path(meas.path).name
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    new = read_ti3(p)
    new.text = meas.text
    return new
