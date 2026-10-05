"""N-colour point-cloud endpoints for battery v3 (Agent 14's protocol v2.2
proposal N2, folded into protocol v3 section N by Agent 16).

For 5+ ink printers, E1-E4 score where a separation does not live (the
battery's evaluation points are 71-89 % all-inks-on). These endpoints are
index-aligned per-point arrays (fixed seeds), so stats3 tests them like
E1-E4 (paired bootstrap, Holm, measured seed term):

* ``e7``   A2B on 4000 random colours with at most 3 inks on (TAC-scaled)
* ``e7b``  the same with at most 4 inks on
* ``e8``   A2B along every single-ink ramp (33 steps) and every two-ink 9 x 9
           grid inside the ink limit
* ``e9``   colorimetric B2A printed on the truth, for the e7 colours and for
           the in-gamut part of hue circles (L* 30/45/60/75, 50 % and 85 % of
           the truth's chroma there, 2 degree steps)

and the safety facts of v2.2 section 5 (zero tolerance under D-17):
``gross_extrapolation`` = device-cube corners and in-limit two-ink solids
the A2B predicts darker than the truth's black minus 3 L* (F-12).
The full Agent 14 referee (``ncq.evaluate``: purity, switching, extension,
banding, limits) is stored beside them as ``ncq`` headline numbers.
"""
from __future__ import annotations

import itertools

import numpy as np

from benchmarks.research import cmm, colour, gmq, ncq


def _sparse(n, k_on, tac, n_pts=4000, seed=17):
    rng = np.random.default_rng(seed)
    dev = rng.uniform(0, 1, (n_pts, n))
    if k_on < n:
        keep = np.argsort(rng.uniform(size=dev.shape), axis=1) < k_on
        dev = dev * keep
    return gmq._scale_tac(dev, tac)


def points(prof, printer, reader: str, cloud=None) -> dict:
    n, tac = printer.n, printer.tac
    out = {}
    d3 = _sparse(n, 3, tac)
    lab3 = printer.lab_rel(d3)
    out["e7"] = colour.de2000(cmm.a2b(prof, d3, reader), lab3)
    d4 = _sparse(n, 4, tac, seed=18)
    out["e7b"] = colour.de2000(cmm.a2b(prof, d4, reader), printer.lab_rel(d4))
    rows = []
    t = np.linspace(0, 1, 33)
    for i in range(n):
        d = np.zeros((33, n))
        d[:, i] = t
        rows.append(d)
    g = np.linspace(0, 1, 9)
    a, b = np.meshgrid(g, g, indexing="ij")
    for i, j in itertools.combinations(range(n), 2):
        d = np.zeros((81, n))
        d[:, i], d[:, j] = a.ravel(), b.ravel()
        rows.append(d[ncq._tac_ok(d, tac)])
    d8 = np.vstack(rows)
    out["e8"] = colour.de2000(cmm.a2b(prof, d8, reader), printer.lab_rel(d8))
    cloud = gmq.truth_cloud(printer) if cloud is None else cloud
    tab, lb, hb = ncq._chroma_table(cloud)
    hues = np.arange(0.0, 360.0, 2.0)
    circ = []
    for L in (30.0, 45.0, 60.0, 75.0):
        cmax = ncq._max_chroma(tab, lb, hb, L, hues)
        for f in (0.5, 0.85):
            C = f * cmax
            circ.append(np.stack([np.full_like(hues, L), C * np.cos(np.radians(hues)),
                                  C * np.sin(np.radians(hues))], 1))
    circ = np.vstack(circ)
    circ = circ[ncq.in_gamut(circ, cloud)]
    targets = np.vstack([lab3, circ])
    out["e9"] = colour.de2000(printer.lab_rel(cmm.b2a(prof, targets, reader)), targets)
    # F-12 gross extrapolation: corners and in-limit two-ink solids
    corners = np.array(list(itertools.product([0.0, 1.0], repeat=n)))
    two = []
    for i, j in itertools.combinations(range(n), 2):
        d = np.zeros(n)
        d[i] = d[j] = 1.0
        two.append(d)
    probe = np.vstack([corners, np.array(two)[ncq._tac_ok(np.array(two), tac)]])
    black = float(cloud[:, 0].min())
    pl = cmm.a2b(prof, probe, reader)[:, 0]
    out["gross_extrapolation"] = int((pl < black - 3.0).sum())
    return out


def evaluate(prof, printer, reader: str = "argyll", sink: dict | None = None) -> dict:
    """Point endpoints into ``sink`` (npz keys), stats + ncq headline out."""
    cloud = gmq.truth_cloud(printer)
    p = points(prof, printer, reader, cloud)
    res = {"gross_extrapolation": p.pop("gross_extrapolation")}
    for k, v in p.items():
        res[k] = ncq.stats(v)
        if sink is not None:
            sink[k] = v
    return res


def referee(prof, printer, reader: str = "argyll") -> dict:
    """Agent 14's full referee on a printer OBJECT (sealed Z printers are not
    in build_printers), headline numbers only."""
    import benchmarks.research.ncq as N
    orig = N.build_printers
    try:
        N.build_printers = lambda: {printer.id: printer}
        r = N.evaluate(prof, printer.id, reader)
    finally:
        N.build_printers = orig
    h = N.headline(r)
    h["NC6 over limit"] = bool(r.get("NC6_over_limit"))
    return h
