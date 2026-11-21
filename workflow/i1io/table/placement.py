# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""4.3.54: THE ROW PLACEMENT CHECK. A veto beside the cut by position; never a value of its own.

WHY (the row placement study of 21 Nov 2026, on the volunteer's recorded rows and on synthetic
rows built from them; work folder 2026-11-21_row_placement_study, ``design.txt``): the released
cut (``scan.cut_by_position``) places a row's readings by TIME only and leaves a clean border of
max(0.5 mm, speed x 18 ms) at each patch edge. The larger errors are not the timing but the
aim points and the print (1 to 2.5 mm at any speed), so that border was too small: on recorded
rows at 82 and 51 mm/s it accepted patches 1.1 and 2.05 dE00 off, and on 1 to 3 of 20
synthetic ChromIQ rows at 61 and 88 mm/s a wrong patch. Its own checks (three readings, one
colour within 0.10) cannot see a window that takes in one or two edge readings.

WHAT THIS DOES (the study's method (d), ``scripts/methods.py`` ``method_cd(mode="d")``, ported):

a. the coarse place: the released time model (the trapezoid of V and A, the first reading at
   FIRST_READING_AFTER_LAMP_S, the motion start MOTION_START_AFTER_LAMP_S);
b. the stability map: reading k is STABLE when k-1, k, k+1 all lie within T of their median,
   T = 0.6 dE00 (median L* >= 30) or 1.2 dE00 (L* < 30): above the single-reading noise
   measured inside clean plateaus of the recorded rows (worst 0.47 / 1.06 dE00);
c. the row fit: the start shifted by dt within +-(12 ms + 3 mm / V) in 1 ms steps and the scale
   by eps within +-2 % in 0.25 % steps; the (dt, eps) that puts every predicted patch centre on
   a stable reading, deepest inside its stable stretch;
d. the row is NOT CONFIRMED when not every patch centre lands on a stable reading, when a place
   half a pitch or more away fits within 2 patches as well, or when the best place lies on the
   bound of (c) (the readings and the timing disagree: the consistency check);
e. per patch its RUN: within +-6.5 mm of its fitted centre, the longest run of consecutive
   readings each within T of the run's median. Not confirmed when the run's centre lies more
   than 2 mm from the fitted centre (unless the run is longer than a patch: a neighbour of the
   same colour), or when fewer than 3 readings remain of it (one dropped at each end, kept
   inside the patch's own extent less half the aperture).

THE VETO (the coordinator's decision of 21 Nov 2026, the study's step 1): the row's VALUES stay
the released cut's, unchanged. The row is accepted only when (a)-(e) confirm it AND every
patch's released window lies inside that patch's run (no reading of the window outside the
stable run) AND the released value lies within VALUE_AGREE_DE00 of the run's own value. Anything
else, any doubt, any exception: NOT confirmed, with the true reason and its numbers. The check
can therefore only make ChromIQ read a row again, never accept a different value.

Nothing here is sent to the table, nothing here changes a speed or a border. Measured on the
recorded rows only; NOTHING OF IT HAS RUN ON A REAL TABLE.
"""
from __future__ import annotations

import bisect
import math
import time

from . import scan as sc

#: THE DEVELOPER SWITCH (no user option): False turns the veto off (the row is then judged by
#: the released checks alone, as in 4.3.53). Default ON.
ROW_PLACEMENT_CHECK = True

#: (b) / (e): a reading belongs to a stable stretch / a run within this dE00 of its median
STABLE_DE00 = 0.6
#: ... and within this below L* 30 (the dark patches' noise)
STABLE_DE00_DARK = 1.2
STABLE_DARK_BELOW_L = 30.0
#: (c): the timing's own bound: 12 ms (the start's spread between recordings, 3.6 ms, times 3)
#: plus 3 mm (the aims' and the print's offsets of a row, up to about 2 mm measured) at the
#: row's speed; and the scale (the aim grid about 1 % short, the speed below 0.4 %)
FIT_DT_S = 0.012
FIT_DX_MM = 3.0
FIT_SCALE = 0.02
FIT_DT_STEP_S = 0.001
FIT_SCALE_STEP = 0.0025
#: (c): a patch centre "on a stable reading" = its reading lies at least this deep in a stable
#: stretch (itself and one neighbour each side stable); depth counted up to FIT_DEPTH_CAP
FIT_HIT_DEPTH = 2
FIT_DEPTH_CAP = 6
#: (d): a rival place at least half a pitch away that puts this many fewer patches on stable
#: readings, or more, makes the fit not unique
UNIQUE_MARGIN = 2
#: (d): the best place this close to the bound counts as ON it (the readings disagree)
BOUND_DT_S = 0.0015
BOUND_SCALE = 0.001
#: (e): where a patch's run is looked for, around its fitted centre
RUN_SEARCH_MM = 6.5
#: (e): one reading dropped at each end of a run
RUN_GUARD = 1
#: (e): a run's centre this far from the fitted centre: not confirmed
PATCH_TOL_MM = 2.0
#: (e): a run longer than (pitch - aperture + this) is a same-coloured neighbour's too
MERGED_EXTRA_MM = 2.0
#: (e): readings a patch must keep
MIN_READINGS = 3
#: THE VETO: the released value and the run's own value may differ by at most this (design.txt
#: section 6, step 1)
VALUE_AGREE_DE00 = 0.5

#: the reasons (``reason`` of :func:`check_row`); every one means NOT confirmed
REASONS = ("check_off", "no_readings", "too_few_readings_for_the_check",
           "readings_not_finite", "edges_do_not_place_every_patch", "edges_not_unique",
           "edges_disagree_with_timing", "patch_without_a_stable_run",
           "patch_run_away_from_its_place", "patch_too_few_clean_readings",
           "window_outside_the_stable_run", "value_disagrees_with_the_stable_run",
           "check_failed")

#: what each reason says, for the detailed table log and the app log (English, a record)
SAYS = {
    "no_readings": "the row has no readings",
    "too_few_readings_for_the_check": "the row has too few readings for the check",
    "readings_not_finite": "a reading is not a number",
    "edges_do_not_place_every_patch":
        "the readings do not show every patch where the timing puts it",
    "edges_not_unique": "two places of the row fit the readings about equally well",
    "edges_disagree_with_timing":
        "the readings and the timing disagree about where the row lies",
    "patch_without_a_stable_run": "a patch shows no stable readings at all",
    "patch_run_away_from_its_place":
        "a patch's stable readings lie away from where the row puts that patch",
    "patch_too_few_clean_readings": "a patch has fewer than 3 clean readings",
    "window_outside_the_stable_run":
        "a patch's window takes in readings outside that patch's stable readings",
    "value_disagrees_with_the_stable_run":
        "a patch's value differs from its stable readings' value",
    "check_failed": "the check could not be made",
}


# ---- the colour of a reading -------------------------------------------------------------------

def _lab(spectra, wavelengths):
    """CIELAB D50 / 2 degree of each spectrum (0..1). The dual scan's own conversion when the
    stream has the instrument's 36 bands at 380-730 nm (the study's), the app's ArgyllCMS method
    otherwise."""
    import numpy as np
    s = np.asarray(spectra, float)
    wl = [float(w) for w in (wavelengths or [])]
    if not wl and s.shape[1] == 36:
        wl = [380.0 + 10.0 * j for j in range(36)]
    if len(wl) == 36 and all(abs(w - (380.0 + 10.0 * j)) < 1e-6 for j, w in enumerate(wl)):
        from workflow.dual_scan.colour import spec_to_lab
        return spec_to_lab(s)
    from workflow.argyll_colorimetry import spectra_to_xyz_like_argyll
    xyz = np.asarray(spectra_to_xyz_like_argyll(s, wl, illuminant="D50", observer="1931_2"),
                     float)
    r = xyz / np.array([96.42, 100.0, 82.49])
    e, k = 216 / 24389, 24389 / 27
    f = np.where(r > e, np.cbrt(r), (k * r + 16) / 116)
    return np.stack([116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]),
                     200 * (f[:, 1] - f[:, 2])], axis=1)


def _de00(a, b):
    from workflow.profile_engine.metrics import delta_e_2000
    return delta_e_2000(a, b)


def _limit(L):
    return STABLE_DE00 if L >= STABLE_DARK_BELOW_L else STABLE_DE00_DARK


# ---- the time model, vectorised ------------------------------------------------------------------

def _positions(plan, t):
    """The arm's place along *plan* (mm) at times *t* (s after its motion started): the
    trapezoid of ``scan.time_at`` inverted (``dual_rows._position_at``), for an array."""
    import numpy as np
    t = np.asarray(t, float)
    V = float(plan.speed)
    ta = plan.A / 1000.0
    L = plan.dist / 10.0
    a = V / ta
    T = plan.move_s
    d_acc = 0.5 * a * ta * ta
    if L < 2 * d_acc:
        th = math.sqrt(L / a)
        r = 2 * th - t
        out = np.where(t <= th, 0.5 * a * t * t, L - 0.5 * a * r * r)
    else:
        r = T - t
        out = np.where(t <= ta, 0.5 * a * t * t,
                       np.where(t <= T - ta, d_acc + (t - ta) * V, L - 0.5 * a * r * r))
    return np.where(t <= 0, 0.0, np.where(t >= T, L, out))


def _pitch(plan) -> float:
    al = sorted(q.along_mm for q in plan.patches)
    d = sorted(b - a for a, b in zip(al, al[1:]) if b - a > 1e-6)
    if not d:
        return 2.0 * max((q.half_mm for q in plan.patches), default=4.0)
    return d[len(d) // 2]


# ---- (b) the stability map ------------------------------------------------------------------------

def _depth(lab):
    """Per reading: how deep it lies inside a stretch of stable readings (0 = not stable)."""
    import numpy as np
    n = len(lab)
    stable = np.zeros(n, bool)
    if n >= 3:
        w = np.stack([lab[:-2], lab[1:-1], lab[2:]], axis=1)          # (n-2, 3, 3)
        med = np.median(w, axis=1)                                     # (n-2, 3)
        d = _de00(w.reshape(-1, 3), np.repeat(med, 3, axis=0)).reshape(-1, 3).max(axis=1)
        lim = np.where(med[:, 0] >= STABLE_DARK_BELOW_L, STABLE_DE00, STABLE_DE00_DARK)
        stable[1:-1] = d <= lim
    left = np.zeros(n, int)
    right = np.zeros(n, int)
    run = 0
    for k in range(n):
        run = run + 1 if stable[k] else 0
        left[k] = run
    run = 0
    for k in range(n - 1, -1, -1):
        run = run + 1 if stable[k] else 0
        right[k] = run
    return np.minimum(left, right)


# ---- (c) the row fit -----------------------------------------------------------------------------

def _fit(plan, n, depth, first_s, motion_s):
    """Every (dt, eps) of the bound, scored as the study's ``global_fit``: (patches whose
    centre reading is stable, the sum of their depths), best first; ties: the most central
    place (see below), the smaller |dt|, the smaller |eps|, the order of the grid."""
    import numpy as np
    V = float(plan.speed)
    b = FIT_DT_S + FIT_DX_MM / V
    dts = np.arange(-b, b + 1e-9, FIT_DT_STEP_S)
    eps = np.arange(-FIT_SCALE, FIT_SCALE + 1e-9, FIT_SCALE_STEP)
    E, D = np.meshgrid(eps, dts, indexing="ij")            # eps outer, dt inner (the study's)
    E, D = E.ravel(), D.ravel()
    cen = np.array([q.along_mm for q in plan.patches], float)
    tau = np.array([sc.time_at(plan, c) for c in cen], float)     # model time of each centre
    # reading k sits at model time (first_s + k R - motion_s - dt) (1 + eps); the reading
    # nearest each centre in PLACE is one of the two around tau / (1 + eps)
    kf = ((tau[None, :] / (1.0 + E[:, None])) + motion_s + D[:, None] - first_s) / sc.READING_S
    k0 = np.clip(np.floor(kf).astype(int), 0, n - 1)
    k1 = np.clip(k0 + 1, 0, n - 1)

    def pos(k):
        return _positions(plan, (first_s + k * sc.READING_S - motion_s - D[:, None])
                          * (1.0 + E[:, None]))
    d0 = np.abs(pos(k0) - cen[None, :])
    d1 = np.abs(pos(k1) - cen[None, :])
    kk = np.where(d1 < d0, k1, k0)
    dep = depth[kk]
    hits = (dep >= FIT_HIT_DEPTH).sum(axis=1)
    deep = np.minimum(dep, FIT_DEPTH_CAP).sum(axis=1)
    # ties (equally many patches, equally deep): the most CENTRAL place of the bound first (the
    # study's prototype took the smallest |dt| first, which on a short row whose centres lie deep
    # in their stretches over a range of places picked a scale ON the bound and called that a
    # disagreement), then the smaller |dt|, the smaller |eps|, the grid's order
    ext = np.maximum(np.abs(D) / b, np.abs(E) / FIT_SCALE)
    order = np.lexsort((np.arange(len(E)), np.abs(E), np.abs(D), np.round(ext, 9), -deep,
                        -hits))
    return D[order], E[order], hits[order], deep[order], b


# ---- (e) a patch's run -----------------------------------------------------------------------------

def _medians_of_prefixes(seg):
    """The per-channel median of seg[:m] for m = 1..len(seg) (np.median's rule)."""
    import numpy as np
    out = np.empty_like(seg)
    cols = [[], [], []]
    for m in range(len(seg)):
        for c in range(3):
            bisect.insort(cols[c], float(seg[m, c]))
        h = (m + 1) // 2
        for c in range(3):
            s = cols[c]
            out[m, c] = s[h] if (m + 1) % 2 else 0.5 * (s[h - 1] + s[h])
    return out


def _greedy(seg, a):
    """The study's run from start *a*: grown one reading at a time while every reading of it
    lies within the limit of the run's median; its length."""
    import numpy as np
    rest = seg[a:]
    m = len(rest)
    if m <= 1:
        return m
    med = _medians_of_prefixes(rest)                         # med[j] = median of rest[:j+1]
    ii, jj = np.tril_indices(m)                              # member jj of prefix ii (jj <= ii)
    d = _de00(rest[jj], med[ii])
    worst = np.full(m, -np.inf)
    np.maximum.at(worst, ii, d)
    lim = np.where(med[:, 0] >= STABLE_DARK_BELOW_L, STABLE_DE00, STABLE_DE00_DARK)
    bad = np.nonzero(worst[1:] > lim[1:])[0]                 # prefixes of length 2..m
    return int(bad[0]) + 1 if len(bad) else m


def _windows_pass(seg, length):
    """Starts whose window of *length* readings lies within the limit of its own median."""
    import numpy as np
    m = len(seg)
    if length <= 1:
        return list(range(m))
    if length > m:
        return []
    w = np.lib.stride_tricks.sliding_window_view(seg, (length, 3))[:, 0]   # (m-L+1, L, 3)
    med = np.median(w, axis=1)
    d = _de00(w.reshape(-1, 3), np.repeat(med, length, axis=0)).reshape(-1, length).max(axis=1)
    lim = np.where(med[:, 0] >= STABLE_DARK_BELOW_L, STABLE_DE00, STABLE_DE00_DARK)
    return [int(i) for i in np.nonzero(d <= lim)[0]]


def longest_run(seg, near: int = 0) -> "tuple[int, int]":
    """(start, length) of the longest run of *seg* (Lab, one row per reading) grown as the
    study's ``Stream.run_around`` grows it from every start (the first such start on a tie).
    Exact, but evaluates a start only when its window of the best length so far passes."""
    m = len(seg)
    if m == 0:
        return 0, 0
    near = min(max(int(near), 0), m - 1)
    best_a, best_n = near, _greedy(seg, near)
    done = {near}
    while True:
        longer = False
        for a in _windows_pass(seg, best_n):
            if a in done:
                continue
            done.add(a)
            g = _greedy(seg, a)
            if g > best_n:
                best_a, best_n, longer = a, g, True
                break
            if g == best_n and a < best_a:
                best_a = a
        if not longer:
            return best_a, best_n


# ---- the check ------------------------------------------------------------------------------------

def _off(reason, **kv) -> dict:
    out = {"confirmed": False, "reason": reason, "says": SAYS.get(reason, reason)}
    out.update(kv)
    return out


def check_row(plan, spec_rows, windows, wavelengths=None,
              first_reading_s: float = sc.FIRST_READING_AFTER_LAMP_S,
              motion_start_s: float = sc.MOTION_START_AFTER_LAMP_S,
              enabled: "bool | None" = None) -> dict:
    """The row placement check of one lamp pass (see the module's text). *windows*: the
    released cut's per-patch readings [(i0, i1)] in the plan's patch order. Returns a record:
    ``confirmed`` (True only when every step confirmed the row), ``reason`` / ``says`` (why not),
    ``patch`` / ``off_mm`` (the patch it is about and by how many mm), the fit (``dt_ms``,
    ``scale_pct``), per patch its run and window, and ``ms`` (the check's own time). Never
    raises: any failure is "not confirmed"."""
    t0 = time.perf_counter()
    on = ROW_PLACEMENT_CHECK if enabled is None else bool(enabled)
    if not on:
        return {"confirmed": True, "reason": "check_off", "says": "the check is switched off",
                "on": False, "ms": 0.0}
    try:
        out = _check(plan, spec_rows, windows, wavelengths, first_reading_s, motion_start_s)
    except Exception as exc:          # noqa: BLE001 - a doubt is never a confirmation
        out = _off("check_failed", error=f"{type(exc).__name__}: {exc}"[:200])
    out["on"] = True
    out["ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
    return out


def _check(plan, spec_rows, windows, wavelengths, first_s, motion_s) -> dict:
    import numpy as np
    n = len(spec_rows)
    np_ = len(plan.patches)
    if n == 0 or np_ == 0:
        return _off("no_readings")
    if n < 3 * np_ or len(windows) != np_:
        return _off("too_few_readings_for_the_check", readings=n)
    spec = np.asarray(spec_rows, float)
    if not np.all(np.isfinite(spec)):
        return _off("readings_not_finite")
    lab = _lab(spec, wavelengths)
    if not np.all(np.isfinite(lab)):
        return _off("readings_not_finite")
    V = float(plan.speed)
    depth = _depth(lab)
    D, E, H, _deep, bound = _fit(plan, n, depth, first_s, motion_s)
    gdt, ge, hits = float(D[0]), float(E[0]), int(H[0])
    fit = {"dt_ms": round(gdt * 1000.0, 1), "scale_pct": round(ge * 100.0, 2),
           "dx_mm": round(gdt * V, 2), "bound_ms": round(bound * 1000.0, 1),
           "patches_on_stable_readings": hits, "patches": np_}
    if hits < np_:
        return _off("edges_do_not_place_every_patch", fit=fit,
                    off_patches=np_ - hits)
    pitch = _pitch(plan)
    far = np.nonzero(np.abs(D - gdt) * V * (1.0 + ge) >= pitch / 2.0)[0]
    if len(far) and int(H[far[0]]) >= hits - UNIQUE_MARGIN:
        k = int(far[0])
        return _off("edges_not_unique", fit=fit,
                    rival={"dt_ms": round(float(D[k]) * 1000.0, 1),
                           "scale_pct": round(float(E[k]) * 100.0, 2),
                           "patches_on_stable_readings": int(H[k])})
    # how far the readings put each patch from where the timing puts it (mm, the largest)
    tau = np.array([sc.time_at(plan, q.along_mm) for q in plan.patches], float)
    moved = np.abs(_positions(plan, tau / (1.0 + ge) + gdt)
                   - np.array([q.along_mm for q in plan.patches], float))
    fit["largest_shift_mm"] = round(float(moved.max()), 2)
    if abs(gdt) >= bound - BOUND_DT_S or abs(ge) >= FIT_SCALE - BOUND_SCALE:
        k = int(np.argmax(moved))
        return _off("edges_disagree_with_timing", fit=fit, patch=plan.patches[k].loc,
                    off_mm=round(float(moved[k]), 2))
    k = np.arange(n)
    pos = _positions(plan, (first_s + k * sc.READING_S - motion_s - gdt) * (1.0 + ge))
    per = []
    worst = None                       # (reason, patch record) of the first failing patch
    for q, (i0, i1) in zip(plan.patches, windows):
        rec = {"loc": q.loc, "window": [int(i0), int(i1)]}
        per.append(rec)
        idx = np.nonzero(np.abs(pos - q.along_mm) <= RUN_SEARCH_MM)[0]
        if not len(idx):
            worst = worst or ("patch_without_a_stable_run", rec)
            continue
        lo = int(idx[0])
        near = int(np.argmin(np.abs(pos[idx] - q.along_mm)))
        a, m = longest_run(lab[lo:int(idx[-1]) + 1], near)
        if m == 0:
            worst = worst or ("patch_without_a_stable_run", rec)
            continue
        ra, rb = lo + a, lo + a + m - 1                # the run, readings ra..rb
        cc = 0.5 * (pos[ra] + pos[rb])
        ext = abs(pos[rb] - pos[ra])
        merged = ext > pitch - plan.aperture_mm + MERGED_EXTRA_MM
        dev = 0.0 if merged else abs(cc - q.along_mm)
        core = np.arange(ra + RUN_GUARD, rb - RUN_GUARD + 1)
        core = core[np.abs(pos[core] - q.along_mm) <= q.half_mm - plan.aperture_mm / 2]
        rec.update(run=[ra, rb + 1], run_mm=round(float(ext), 2), merged=bool(merged),
                   run_off_mm=round(float(abs(cc - q.along_mm)), 2), clean=int(len(core)))
        if dev > PATCH_TOL_MM:
            worst = worst or ("patch_run_away_from_its_place", rec)
            rec["off_mm"] = round(float(dev), 2)
            continue
        if len(core) < MIN_READINGS:
            worst = worst or ("patch_too_few_clean_readings", rec)
            continue
        # THE VETO: the released window inside the run, its value beside the run's own
        if i1 <= i0:
            worst = worst or ("window_outside_the_stable_run", rec)
            rec["off_mm"] = None
            continue
        if i0 < ra or i1 - 1 > rb:
            beyond = max(abs(pos[ra] - pos[min(i0, ra)]), abs(pos[max(i1 - 1, rb)] - pos[rb]))
            rec["outside_readings"] = int(max(0, ra - i0) + max(0, i1 - 1 - rb))
            rec["off_mm"] = round(float(beyond), 2)
            worst = worst or ("window_outside_the_stable_run", rec)
            continue
        dv = float(_de00(_lab(spec[i0:i1].mean(axis=0, keepdims=True), wavelengths),
                         _lab(spec[core].mean(axis=0, keepdims=True), wavelengths))[0])
        rec["value_de00"] = round(dv, 3)
        if dv > VALUE_AGREE_DE00:
            worst = worst or ("value_disagrees_with_the_stable_run", rec)
    # the patch the reason names: the first failing one, or for the veto the one most off
    if worst is not None:
        reason, rec = worst
        if reason == "window_outside_the_stable_run":
            cands = [r for r in per if r.get("outside_readings")]
            if cands:
                rec = max(cands, key=lambda r: r.get("off_mm") or 0.0)
        return _off(reason, fit=fit, patch=rec["loc"], off_mm=rec.get("off_mm"),
                    value_de00=rec.get("value_de00"), per_patch=per,
                    refused_patches=_refused_count(per))
    return {"confirmed": True, "reason": "", "says": "every patch confirmed", "fit": fit,
            "per_patch": per}


def _refused_count(per) -> int:
    n = 0
    for r in per:
        if "run" not in r or r.get("clean", 0) < MIN_READINGS or r.get("outside_readings") \
                or (r.get("value_de00") or 0.0) > VALUE_AGREE_DE00 \
                or ((r.get("off_mm") or 0.0) > PATCH_TOL_MM and not r.get("merged")):
            n += 1
    return n


def summary(res: "dict | None") -> str:
    """One line for the detailed table log and the app log."""
    if not res:
        return "row placement check: not made"
    if not res.get("on", True):
        return "row placement check: off"
    fit = res.get("fit") or {}
    tail = ""
    if fit:
        tail = (f"; the readings put the row {fit.get('dt_ms'):+.1f} ms "
                f"({fit.get('dx_mm'):+.2f} mm) and {fit.get('scale_pct'):+.2f} % from the "
                f"timing (bound {fit.get('bound_ms')} ms)")
    took = f"; {res.get('ms')} ms" if res.get("ms") is not None else ""
    if res.get("confirmed"):
        return f"row placement check: confirmed, every patch{tail}{took}"
    what = res.get("says") or res.get("reason")
    if res.get("patch"):
        what += f": patch {res['patch']}"
        if res.get("off_mm") is not None:
            what += f", by {res['off_mm']:.2f} mm"
        if res.get("value_de00") is not None and res.get("reason") == \
                "value_disagrees_with_the_stable_run":
            what += f", {res['value_de00']:.2f} dE00"
        if res.get("refused_patches"):
            k = res["refused_patches"]
            what += f" ({k} {'patch' if k == 1 else 'patches'} not confirmed)"
    elif res.get("off_mm") is not None:
        what += f", by {res['off_mm']:.2f} mm"
    if res.get("off_patches"):
        k = res["off_patches"]
        what += f" ({k} {'patch' if k == 1 else 'patches'} not on stable readings)"
    return (f"row placement check: NOT confirmed ({res.get('reason')}), the readings do not "
            f"confirm where the patches are in this row: {what}{tail}{took}")
