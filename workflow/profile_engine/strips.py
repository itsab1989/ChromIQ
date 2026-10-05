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
2. A stiff fit of the whole chart; every patch's ΔE2000 residual.
3. A strip is SUSPECT when the MEDIAN residual of its patches is above
   ``max(MIN_DE, median + K_SCALE x 1.4826 MAD)`` of the chart: more than
   half of the strip is grossly off at once. An isolated misread or a hard
   colour region never moves a strip's median; a random layout puts a
   strip's patches all over colour space.
3b. OUT OF STEP (chartread's own off-by-one check, with the model in place
   of the expected values): a strip whose median residual is merely raised
   is judged on a fit that has NOT seen it, and is suspect when its
   readings fit at least twice as well shifted one patch early or late. An
   ordered strip (a ramp; printtarg -r) is the only data in its region, so
   a fit that saw it follows it.
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

SHIFT_TEST = True
SHIFT_MIN_DE = 1.0    # an out-of-step strip must be off by this much as read
SHIFT_RATIO = 0.5     # ... and fit at least twice as well shifted by one
MAX_LEAVE_OUT = 8     # strips per round judged on a fit without them

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


def _shifted(pred, lab, rows):
    """Median residual of a strip as read, and read one patch early / late
    (Argyll's chartread explores the same off-by-one, ``spectro/chartread.c``):
    a strip read out of step fits far better shifted back."""
    from workflow.profile_engine.metrics import delta_e_2000
    p, r = pred[rows], lab[rows]
    as_read = float(np.median(delta_e_2000(p, r)))
    early = float(np.median(delta_e_2000(p[1:], r[:-1])))
    late = float(np.median(delta_e_2000(p[:-1], r[1:])))
    return as_read, min(early, late)


def detect(meas, *, grid: int, lam: float) -> StripVerdict:
    """Suspect strips of ``meas`` (see the module text)."""
    ids = strip_ids(meas.sample_locs)
    if ids is None:
        return StripVerdict(note="no strip locations")
    device, lab = meas.device, meas.lab_relative
    n = len(device)
    sizes = np.bincount(ids)
    judged = [g for g in range(len(sizes)) if sizes[g] >= MIN_STRIP]
    from workflow.profile_engine.metrics import delta_e_2000
    order = _patch_order(meas.sample_locs, ids)
    keep = np.ones(n, bool)
    suspects: set = set()
    res = None
    for _ in range(MAX_ROUNDS):
        pred = _predict(device, lab, keep, grid, lam)
        res = delta_e_2000(pred, lab)
        r_in = res[keep]
        med = float(np.median(r_in))
        s = 1.4826 * float(np.median(np.abs(r_in - med)))
        thr = max(MIN_DE, med + K_SCALE * s)
        new = set()
        loo = []
        for g in judged:
            rows = order[g]
            m_g = float(np.median(res[rows]))
            if m_g > thr:
                new.add(g)
                continue
            # out of step: shifted back by one patch it fits much better.
            # Judged on a fit that has NOT seen the strip: an ordered strip
            # (printtarg -r: a ramp read one patch late) is the only data in
            # its region, so a fit that saw it follows it (masking).
            if SHIFT_TEST:
                as_read, shifted = _shifted(pred, lab, rows)
                if as_read > med + 2.0 * s:
                    if shifted < SHIFT_RATIO * as_read:
                        new.add(g)
                    else:
                        loo.append((as_read, g))
        loo.sort(reverse=True)
        for _, g in loo[:MAX_LEAVE_OUT]:
            rows = order[g]
            k2 = keep.copy()
            k2[rows] = False
            p2 = _predict(device, lab, k2, grid, lam)
            as_read, shifted = _shifted(p2, lab, rows)
            # only the shift decides here: a CLEAN ordered ramp left out is
            # extrapolated badly too (X1 seed 0, grey ramp: 4.1 dE00 left
            # out) but does not fit better shifted (4.4)
            if as_read > SHIFT_MIN_DE and shifted < SHIFT_RATIO * as_read:
                new.add(g)
        if new == suspects:
            break
        suspects = new
        keep = ~np.isin(ids, sorted(suspects))
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
        info.append((names[g], int(len(r)), float(np.median(r)), float(r.min()),
                     float(r.max())))
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
