"""N-channel (device-space) patch generators + spacing helpers (#72 Tier C).

The RGB generators in :mod:`workflow.patch_generators` stay textually
untouched (their behaviour is load-bearing for every RGB chart); this module
holds the multi-ink counterparts, all dimension-generic:

* **N-native sets** (work with no profile, state 2): per-ink ramps, ink-pair
  overprints, the device-centred near-neutral grey-balance rings (the G7-style
  construct — the RGB ``near_neutrals()`` output mapped by naive inversion),
  the device neutral ramp, and white/black anchors (ink white = all-0).
* **Spacing utilities** in N-D: dedupe / min-distance / gap-fill / counts, all
  using absolute Euclidean distance in device-% over every channel with the
  same 2.0 threshold as RGB (#72 appendix E: patch distinctness is a
  per-channel device-resolution question — 2 % of ink is 2 % of ink whether
  the device has 3 channels or 7; diagonal-relative scaling was rejected).

Channel convention: device tuples are 0..100 in the chart's canonical
colorant order — C, M, Y first and K fourth for every CMYK-based ink set
(guaranteed by ``ti2_relayout.color_rep_for_inks``); extra inks follow.

All maths follows the issue's worked appendix (rev 2.3) verbatim; the ring
clamp geometry and count identities are verified there against a real profile.
"""
from __future__ import annotations

import itertools
import math

from workflow.patch_generators import near_neutrals, neutral_ramp


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, float(v)))


# ---------------------------------------------------------------------------
# N-native sets (state 2 — no profile needed)
# ---------------------------------------------------------------------------

def ramp_levels(steps: int, top: float = 100.0,
                spacing: str = "linear") -> list[float]:
    """The ``steps`` tone values of a single-ink ramp, ``top`` included.

    ``"linear"``: ``i·top/steps`` (the original spacing). ``"light"``:
    ``top·(i/steps)^1.5``, which puts about half the steps below 40 % like
    the professional ECG / FOGRA55 ramps (1 2 3 5 10 20 30 40 48 55 …):
    dot gain bends hardest in the light tones (agent 18, s1).
    """
    steps = int(steps)
    top = float(top)
    if spacing == "light":
        return [top * (i / steps) ** 1.5 for i in range(1, steps + 1)]
    return [i * top / steps for i in range(1, steps + 1)]


def per_ink_ramps(n_inks: int, steps: int,
                  ink_limit: float = 300.0,
                  spacing: str = "linear") -> list[tuple[float, ...]]:
    """``steps`` tones of each ink alone: ``v_i = i·top/steps, i = 1…steps``
    with ``top = min(100, ink_limit)`` — the UI allows limits below 100 %,
    and a single-ink patch must honour them like every other set.
    ``spacing="light"`` uses :func:`ramp_levels`' denser light tones.

    The top endpoint is deliberately included; the cross-set dedupe absorbs
    overlap with white/black and the pair-ramp ends (#72 appendix F).
    """
    n_inks, steps = int(n_inks), int(steps)
    top = min(100.0, float(ink_limit))
    levels = ramp_levels(steps, top, spacing)
    out: list[tuple[float, ...]] = []
    for ink in range(n_inks):
        for v in levels:
            row = [0.0] * n_inks
            row[ink] = v
            out.append(tuple(row))
    return out


def per_ink_ramps_count(n_inks: int, steps: int) -> int:
    return max(0, int(n_inks)) * max(0, int(steps))


def ink_pair_overprints(n_inks: int, steps: int,
                        ink_limit: float = 300.0) -> list[tuple[float, ...]]:
    """Two-ink overprint ramps for every ink pair: both inks at
    ``v_i = i·min(100, L/2)/steps`` — the ``L/2`` cap keeps every pair patch
    inside the ink limit *by construction* (no post-clamp; it only bites for
    limits under 200 %). ``C(n_inks, 2) × steps`` patches (#72 appendix F).
    """
    n_inks, steps = int(n_inks), int(steps)
    vmax = min(100.0, float(ink_limit) / 2.0)
    out: list[tuple[float, ...]] = []
    for a, b in itertools.combinations(range(n_inks), 2):
        for i in range(1, steps + 1):
            row = [0.0] * n_inks
            row[a] = row[b] = i * vmax / steps
            out.append(tuple(row))
    return out


def ink_pair_overprints_count(n_inks: int, steps: int) -> int:
    n = max(0, int(n_inks))
    return (n * (n - 1) // 2) * max(0, int(steps))


def ink_triple_overprints(n_inks: int, steps: int,
                          ink_limit: float = 300.0) -> list[tuple[float, ...]]:
    """Three-ink overprint ramps for every ink triple: each ink at
    ``v_i = i·min(100, L/3)/steps`` — the ``L/3`` cap keeps every triple
    patch inside the ink limit *by construction*, exactly like the pair
    set's ``L/2``. The systematic three-ink counterpart to the pairs: the
    dark composite region (CMY, CMK, … overprints) that neither pairs nor
    statistical coverage sample deliberately — where GCR/black-generation
    behaviour lives. ``C(n_inks, 3) × steps`` patches; the count grows
    quickly with many inks, so small step counts are the intended use.
    """
    n_inks, steps = int(n_inks), int(steps)
    vmax = min(100.0, float(ink_limit) / 3.0)
    out: list[tuple[float, ...]] = []
    for a, b, c in itertools.combinations(range(n_inks), 3):
        for i in range(1, steps + 1):
            row = [0.0] * n_inks
            row[a] = row[b] = row[c] = i * vmax / steps
            out.append(tuple(row))
    return out


def ink_triple_overprints_count(n_inks: int, steps: int) -> int:
    n = max(0, int(n_inks))
    return (n * (n - 1) * (n - 2) // 6) * max(0, int(steps))


def rich_black_ramp(steps: int, k_levels: int, n_channels: int,
                    k_index: int | None = 3,
                    ink_limit: float = 300.0) -> list[tuple[float, ...]]:
    """Neutral CMY ramp × K-substitution grid — the "rich black" set.

    For each K level ``K_j = j·min(100, L/2)/k_levels`` and each CMY step
    ``i``, equal CMY at ``i·min(100, (L − K_j)/3)/steps``: dark neutrals
    built from colour ink plus increasing black — exactly the region the
    profile's black generation (colprof -k / the engine's GCR) has to
    resolve, sampled systematically instead of statistically. Inside the
    ink limit by construction (K ≤ L/2 and CMY fills at most the rest).
    Returns ``[]`` for K-less ink sets (there is no substitution axis).
    """
    steps, k_levels = int(steps), int(k_levels)
    if k_index is None or not 0 <= k_index < n_channels or n_channels < 4:
        return []
    limit = float(ink_limit)
    k_top = min(100.0, limit / 2.0)
    out: list[tuple[float, ...]] = []
    for j in range(1, k_levels + 1):
        k_val = j * k_top / k_levels
        cmy_top = min(100.0, max(0.0, (limit - k_val)) / 3.0)
        for i in range(1, steps + 1):
            v = i * cmy_top / steps
            row = [0.0] * n_channels
            row[0] = row[1] = row[2] = v
            row[k_index] = k_val
            out.append(tuple(row))
    return out


def rich_black_ramp_count(steps: int, k_levels: int,
                          n_channels: int = 4,
                          k_index: int | None = 3) -> int:
    if k_index is None or n_channels < 4:
        return 0
    return max(0, int(steps)) * max(0, int(k_levels))


def project_ink_limit(patches, ink_limit: float) -> list[tuple[float, ...]]:
    """Euclidean projection of each patch onto ``{0 ≤ v ≤ 100, Σv ≤ L}``.

    The same simplex projection the profile engine uses for its TAC
    (subtract a common amount from the inks that stay positive) —
    implemented locally so this module stays dependency-free for the
    standalone chromiq-patches vendoring. Patches under the limit pass
    through unchanged.
    """
    limit = float(ink_limit)
    out: list[tuple[float, ...]] = []
    for p in patches:
        vals = [_clamp(v) for v in p]
        if sum(vals) <= limit:
            out.append(tuple(vals))
            continue
        u = sorted(vals, reverse=True)
        css = 0.0
        theta = 0.0
        for k, uk in enumerate(u, start=1):
            css += uk
            t = (css - limit) / k
            if uk - t > 0:
                theta = t
            else:
                break
        out.append(tuple(max(0.0, v - theta) for v in vals))
    return out


def _invert_rgb_to_cmy(rgb: tuple[float, float, float], n_channels: int,
                       ink_limit: float) -> tuple[float, ...]:
    """Naive inversion ``(C,M,Y) = (100−R, 100−G, 100−B)``, K/extras 0, then
    the ink-limit clamp that **shifts along the grey axis** (#72 appendix A):
    ``t = max(0, (C+M+Y−L)/3)`` subtracted from each channel. The shift vector
    is parallel to (1,1,1), so the perpendicular (ring) component — the whole
    point of the rings — is preserved exactly; uniform scaling would shrink
    it and was rejected analytically.
    """
    c, m, y = (100.0 - rgb[0], 100.0 - rgb[1], 100.0 - rgb[2])
    t = max(0.0, (c + m + y - float(ink_limit)) / 3.0)
    row = [0.0] * n_channels
    row[0], row[1], row[2] = c - t, m - t, y - t
    return tuple(row)


def near_neutrals_device(steps: int, offset: float, rings: int,
                         n_channels: int,
                         ink_limit: float = 300.0) -> list[tuple[float, ...]]:
    """Device-centred near-neutral grey-balance rings (state 2, #72).

    Runs the RGB :func:`near_neutrals` generator **unchanged** and maps each
    patch onto the equal-CMY axis by naive inversion — rings of CMY
    combinations around the device's grey balance, exactly the construct
    G7-style P2P charts use. No profile needed: the rings' job is to *bracket*
    the grey-balance region; the measurement finds the true neutral inside.
    K stays 0 (the K ramp is covered by per-ink ramps) and light inks stay 0
    (deliberate v1 simplification, noted in the issue).
    """
    if n_channels < 3:
        raise ValueError("near_neutrals_device needs a CMY-based ink set")
    return [_invert_rgb_to_cmy(p, n_channels, ink_limit)
            for p in near_neutrals(steps, offset, rings)]


# count identity verified in the issue (288 == 288): the adapter is 1:1, so
# the RGB count function stays authoritative — re-exported for symmetry.
from workflow.patch_generators import near_neutrals_count as near_neutrals_device_count  # noqa: E402,F401


def near_neutrals_device_recentred(steps: int, offset: float, rings: int,
                                   n_channels: int, centers: dict,
                                   ink_limit: float = 300.0
                                   ) -> list[tuple[float, ...]]:
    """The grey-balance rings re-centred on the printer's ACTUAL neutral.

    Same ring geometry as :func:`near_neutrals_device`; each patch's
    naive equal-CMY centre is replaced by the profile-measured device
    neutral for its grey level (``centers``: grey value 0–100 → device
    tuple, computed by the caller through the preconditioning profile).
    The ring *offsets* stay in device space, so the bracket geometry the
    set exists for is preserved exactly — only the aim point moves.
    Grey levels without a centre fall back to the naive inversion, and
    every patch gets the grey-axis ink-limit shift.
    """
    if n_channels < 3:
        raise ValueError("near_neutrals_device_recentred needs CMY inks")
    out: list[tuple[float, ...]] = []
    for rgb in near_neutrals(steps, offset, rings):
        grey = round((rgb[0] + rgb[1] + rgb[2]) / 3.0, 2)
        naive = _invert_rgb_to_cmy(rgb, n_channels, 1e9)      # unclamped
        centre = centers.get(grey)
        if centre is None:
            out.append(_invert_rgb_to_cmy(rgb, n_channels, ink_limit))
            continue
        # The rounded grey is both the dict key and the naive-centre input,
        # so centre − naive_centre is exactly the profile's correction.
        naive_centre = _invert_rgb_to_cmy((grey, grey, grey),
                                          n_channels, 1e9)
        row = [_clamp(c + (nv - nc)) for c, nv, nc in
               zip(centre, naive, naive_centre)]
        # Into the limit by the simplex projection: the excess comes back
        # from the inks that are ON. (Dividing it over every channel, as
        # before, left 36 of 162 rings over the limit when the profile's
        # neutral carried K and extra channels were 0; agent 18 R4.)
        out.extend(project_ink_limit([row], float(ink_limit)))
    return out


def ring_grey_levels(steps: int, offset: float, rings: int) -> list[float]:
    """The distinct grey levels (0–100, rounded to the centres-dict key)
    the ring set uses — what the caller feeds through the profile."""
    seen: list[float] = []
    for rgb in near_neutrals(steps, offset, rings):
        g = round((rgb[0] + rgb[1] + rgb[2]) / 3.0, 2)
        if g not in seen:
            seen.append(g)
    return seen


def neutral_ramp_device(steps: int, n_channels: int,
                        ink_limit: float = 300.0) -> list[tuple[float, ...]]:
    """The pure grey ramp as equal-CMY device steps (naive inversion of the
    RGB :func:`neutral_ramp`, same grey-axis ink-limit clamp)."""
    if n_channels < 3:
        raise ValueError("neutral_ramp_device needs a CMY-based ink set")
    return [_invert_rgb_to_cmy(p, n_channels, ink_limit)
            for p in neutral_ramp(steps)]


from workflow.patch_generators import neutral_ramp_count as neutral_ramp_device_count  # noqa: E402,F401


def _device_anchors(n_channels: int, k_index: int | None,
                    ink_limit: float) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """(white, black) anchor tuples: ink white = all zeros (bare paper);
    black = K alone at 100 (never composite, #72 appendix F). K-less ink
    sets fall back to equal CMY at ``min(100, limit/3)`` (appendix H)."""
    white = tuple([0.0] * n_channels)
    if k_index is not None and 0 <= k_index < n_channels:
        row = [0.0] * n_channels
        row[k_index] = min(100.0, float(ink_limit))
        return white, tuple(row)
    v = min(100.0, float(ink_limit) / 3.0)
    return white, tuple([v if i < 3 else 0.0 for i in range(n_channels)])


def white_black_device(count: int, n_channels: int, k_index: int | None = 3,
                       have_white: int = 0, have_black: int = 0,
                       ink_limit: float = 300.0) -> list[tuple[float, ...]]:
    """Paper-white and maximum-black anchors in ink space (#72 appendix F/H).

    Ink white = **all zeros** (bare paper); black = the K ink alone at 100
    (never composite in v1 — composite black is the ink-pair/coverage sets'
    job). ``k_index None`` (a K-less ink set, e.g. plain CMY) falls back to
    equal CMY inside the ink limit.
    """
    count = max(0, int(count))
    whites = max(0, count - max(0, int(have_white)))
    blacks = max(0, count - max(0, int(have_black)))
    white, black = _device_anchors(n_channels, k_index, ink_limit)
    return [white] * whites + [black] * blacks


def white_black_device_count(count: int = 1, have_white: int = 0,
                             have_black: int = 0) -> int:
    count = max(0, int(count))
    return (max(0, count - max(0, int(have_white)))
            + max(0, count - max(0, int(have_black))))


def count_white_black_device(patches, n_channels: int,
                             k_index: int | None = 3,
                             quantum: float = 0.5,
                             ink_limit: float = 300.0) -> tuple[int, int]:
    """``(white, black)`` anchors already present, on the dedupe grid —
    the device-space twin of ``count_white_black`` (white = all-0 ink)."""
    white, black = _device_anchors(n_channels, k_index, ink_limit)
    wk = _key(white, quantum)
    bk = _key(black, quantum)
    w = b = 0
    for p in patches:
        k = _key(p, quantum)
        if k == wk:
            w += 1
        elif k == bk:
            b += 1
    return w, b


# ---------------------------------------------------------------------------
# Spacing utilities in N-D (appendix E: absolute 2.0 device-% Euclidean)
# ---------------------------------------------------------------------------

def _key(p, quantum: float) -> tuple[int, ...]:
    return tuple(int(round(_clamp(c) / quantum)) for c in p)


def deduplicate_nd(patches, quantum: float = 0.5,
                   step: float = 1.0) -> list[tuple[float, ...]]:
    """N-D twin of ``patch_generators.deduplicate``: collisions on the
    ``quantum`` grid are nudged apart along rotating channels, order
    preserved, values clamped to 0..100."""
    seen: set[tuple[int, ...]] = set()
    out: list[tuple[float, ...]] = []
    for p in patches:
        q = [_clamp(v) for v in p]
        n = len(q)
        key = _key(q, quantum)
        tries = 0
        while key in seen and tries < 600:
            ch = tries % n
            delta = step * (1 + tries // n)
            base = q[ch]
            q[ch] = _clamp(base + delta if base + delta <= 100.0 else base - delta)
            key = _key(q, quantum)
            tries += 1
        seen.add(key)
        out.append(tuple(q))
    return out


def _min_d2_brute(q, kept) -> float:
    best = 1e18
    for k in kept:
        d2 = sum((a - b) ** 2 for a, b in zip(q, k))
        if d2 < best:
            best = d2
    return best


def _nudge_dirs(n: int) -> list[tuple[float, ...]]:
    """Deterministic search directions in N-D: ± each axis, then ± diagonals
    of every axis pair — 2n + 4·C(n,2) directions (the 3-D twin's 26-neighbour
    dart-search, generalised without the 3^n blow-up)."""
    dirs: list[tuple[float, ...]] = []
    for i in range(n):
        for s in (1.0, -1.0):
            d = [0.0] * n
            d[i] = s
            dirs.append(tuple(d))
    for i, j in itertools.combinations(range(n), 2):
        for si in (1.0, -1.0):
            for sj in (1.0, -1.0):
                d = [0.0] * n
                d[i], d[j] = si, sj
                dirs.append(tuple(d))
    return dirs


def enforce_min_distance_nd(patches, min_dist: float = 2.0, existing=None,
                            ink_limit: float | None = None):
    """N-D twin of ``patch_generators.enforce_min_distance`` (order and count
    preserved; earlier points never disturbed). Brute-force neighbour test —
    the generator panel's programs are a few thousand patches, well within
    budget for the N-channel path.

    A patch is only ever nudged along the inks it already has ON, so a ramp
    step stays a single-ink patch and a pair grid patch keeps its two inks,
    and with ``ink_limit`` every nudged patch is projected back into the
    limit (agent 18 R3: nudging along every axis switched inks on in 107 of
    827 patches and left 77 over a 320 % limit). Paper white and single-ink
    patches (ramp steps) are never moved: they are deliberate."""
    if not patches:
        return []
    if min_dist <= 0:
        return [tuple(_clamp(v) for v in p) for p in patches]
    md2 = min_dist * min_dist
    kept: list[tuple[float, ...]] = [
        tuple(_clamp(v) for v in q) for q in (existing or [])]
    n = len(patches[0])
    dirs_all = _nudge_dirs(n)
    out: list[tuple[float, ...]] = []
    for p in patches:
        q = tuple(_clamp(v) for v in p)
        on = {i for i, v in enumerate(q) if v > 0.0}
        if len(on) <= 1 or _min_d2_brute(q, kept) >= md2:
            # paper white and single-ink ramp steps are deliberate (the
            # light-step ramps sit 1.4 / 4.0 / 7.4 % apart at 17 steps and
            # must keep their values; challenge M6): never moved
            kept.append(q)
            out.append(q)
            continue
        dirs = [d for d in dirs_all
                if all(c == 0.0 or i in on for i, c in enumerate(d))]
        best_q, best_d2, found = q, _min_d2_brute(q, kept), None
        for rmul in (1.0, 1.5, 2.0, 2.6):
            radius = min_dist * rmul
            for d in dirs:
                ln = math.sqrt(sum(c * c for c in d))
                cand = tuple(_clamp(q[i] + d[i] / ln * radius)
                             for i in range(n))
                if any(cand[i] <= 0.0 for i in on):
                    continue                    # never switch an ink off
                if ink_limit is not None and sum(cand) > float(ink_limit):
                    cand = project_ink_limit([cand], float(ink_limit))[0]
                    if any(cand[i] <= 0.0 for i in on):
                        continue
                d2 = _min_d2_brute(cand, kept)
                if d2 >= md2:
                    found = cand
                    break
                if d2 > best_d2:
                    best_d2, best_q = d2, cand
            if found:
                break
        qf = found if found is not None else best_q
        kept.append(qf)
        out.append(qf)
    return out


def count_too_close_nd(existing, new, min_dist: float = 2.0) -> int:
    """How many of ``new`` sit within ``min_dist`` of any ``existing`` point."""
    if min_dist <= 0 or not existing:
        return 0
    md2 = min_dist * min_dist
    kept = [tuple(_clamp(v) for v in q) for q in existing]
    return sum(1 for p in new
               if _min_d2_brute(tuple(_clamp(v) for v in p), kept) < md2)


def drop_too_close_nd(existing, new, min_dist: float = 2.0):
    """Only the ``new`` points at least ``min_dist`` clear of ``existing``."""
    if min_dist <= 0 or not existing:
        return [tuple(_clamp(v) for v in p) for p in new]
    md2 = min_dist * min_dist
    kept = [tuple(_clamp(v) for v in q) for q in existing]
    return [tuple(_clamp(v) for v in p) for p in new
            if _min_d2_brute(tuple(_clamp(v) for v in p), kept) >= md2]


def _project_rows_np(a, limit: float):
    """Vectorised :func:`project_ink_limit` for numpy arrays (rows 0–100)."""
    import numpy as np
    a = np.clip(a, 0.0, 100.0)
    over = a.sum(1) > limit
    if not over.any():
        return a
    sub = a[over]
    u = np.sort(sub, axis=1)[:, ::-1]
    css = np.cumsum(u, axis=1) - limit
    ks = np.arange(1, sub.shape[1] + 1)[None, :]
    rho = (u - css / ks > 0).sum(1)
    theta = css[np.arange(len(sub)), rho - 1] / rho
    a[over] = np.maximum(sub - theta[:, None], 0.0)
    return a


def fill_gaps_nd(existing, total: int, n_channels: int | None = None,
                 candidates: int = 12, seed: int = 0,
                 relax: int = 4,
                 ink_limit: float | None = None) -> list[tuple[float, ...]]:
    """N-D twin of ``patch_generators.fill_gaps`` (blue-noise seed + Lloyd
    relaxation in device space). Geometrically fine but perceptually blind in
    ink space — the issue recommends targen coverage for large N-channel
    fills; this is the small top-up fallback (e.g. the live Pages fill).

    ``ink_limit``: candidates AND the Lloyd relaxation samples are
    Euclidean-projected onto the limit simplex, so no fill patch can
    exceed the total ink limit (the projection folds the infeasible
    volume onto the limit face — extra weight exactly where the gamut
    boundary lives, which suits a gap filler). The feasible set is
    convex, so the relaxation means stay inside it too.
    """
    import numpy as np

    total = int(total)
    pts = [tuple(float(v) for v in p) for p in existing]
    n = n_channels or (len(pts[0]) if pts else 3)
    n_add = total - len(pts)
    if n_add <= 0:
        return []
    rng = np.random.default_rng(seed)
    fixed = np.array(pts, dtype=float) if pts else np.empty((0, n))

    arr = fixed.copy()
    added = np.empty((n_add, n), dtype=float)
    for i in range(n_add):
        cand = rng.uniform(0.0, 100.0, size=(max(1, candidates), n))
        if ink_limit is not None:
            cand = _project_rows_np(cand, float(ink_limit))
        if len(arr):
            d2 = ((cand[:, None, :] - arr[None, :, :]) ** 2).sum(2).min(axis=1)
            pick = cand[int(np.argmax(d2))]
        else:
            pick = cand[0]
        added[i] = pick
        arr = np.vstack([arr, pick[None, :]])

    base = len(fixed)
    passes = int(relax) if n_add <= 4000 else max(1, int(relax) * 4000 // n_add)
    if relax > 0 and n_add:
        from workflow.patch_generators import _nearest_site
        n_s = min(40000, max(3000, 40 * n_add))
        for _ in range(passes):
            sites = np.vstack([fixed, added]) if base else added
            samp = rng.uniform(0.0, 100.0, size=(n_s, n))
            if ink_limit is not None:
                samp = _project_rows_np(samp, float(ink_limit))
            owner = _nearest_site(samp, sites)
            for j in range(n_add):
                sel = samp[owner == base + j]
                if len(sel):
                    added[j] = sel.mean(0)

    return [tuple(float(v) for v in row) for row in added]


# ---------------------------------------------------------------------------
# Separation-focused sets for 3+ inks (agent 18, D-16; design v2 after the
# challenge, Validation/agent18-design-challenge.md)
# ---------------------------------------------------------------------------
#
# Professional expanded-gamut (ECG) charts (IDEAlliance ECG 2019, X-Rite ECG
# 4200, Fogra ECG-7C = FOGRA55) are not a space-filling cloud: they are small
# factorial grids on INK SUBSETS - single-ink ramps with dense light tones,
# every two-ink overprint as a grid, CMYK as the main four-ink subset, then
# the subsets in which an extra ink replaces its complementary process ink
# (ISO/TS 21328), complementary pairs sampled about a third as densely, and
# 5-10 % of patches with 5+ inks. That is where a separation puts its
# colours, so that is where the profile needs measurements. The functions
# below take the chart's ink CODES (ChromIQ codes, canonical order).
#
# Ink FAMILIES: a light or medium ink belongs to its parent's family (c, lc
# and mc are one hue channel), because a light-ink separation hands over from
# the light to the dark ink along one hue; the "inks per patch" cap counts
# families, not physical inks. White ink ("w") is not a colorant of a colour
# separation and is left out of every set here.

# an extra ink -> the process ink on the opposite side of the hue circle
# (the default when no measured hues are known)
_COMPLEMENT: dict[str, str] = {"o": "c", "r": "c", "g": "m", "v": "y", "b": "y"}
# a light / medium ink -> its full-strength parent
_LIGHT_PARENT: dict[str, str] = {
    "lc": "c", "lm": "m", "ly": "y", "lk": "k",
    "mc": "c", "mm": "m", "my": "y", "mk": "k", "llk": "k"}
_PROCESS = ("c", "m", "y")
_NOT_A_COLORANT = ("w",)


def ink_family(code: str) -> str:
    """The hue channel an ink belongs to (a light ink's parent)."""
    return _LIGHT_PARENT.get(code, code)


def complementary_pairs(inks, hues=None, min_angle: float = 150.0,
                        min_chroma: float = 20.0) -> set:
    """Index pairs of inks on opposite sides of the hue circle.

    ``hues``: optional ``{index: (hue_deg, chroma)}`` of the measured solids
    (a preconditioning profile, or the benchmark's truth printer); then the
    rule is the referee's: both chromatic and at least ``min_angle`` apart.
    Without it, ink letters decide (C+O, C+R, M+G, Y+V, Y+B). Either way
    two PROCESS inks (C, M, Y) are never complementary: they are what every
    separation mixes. Light inks follow their parent; K and white never pair."""
    inks = list(inks)
    fam = [ink_family(c) for c in inks]
    out = set()
    for i, j in itertools.combinations(range(len(inks)), 2):
        a, b = fam[i], fam[j]
        if a == b or "k" in (a, b) or a in _NOT_A_COLORANT or b in _NOT_A_COLORANT:
            continue
        if a in _PROCESS and b in _PROCESS:
            continue
        if hues is not None and i in hues and j in hues:
            (hi, ci), (hj, cj) = hues[i], hues[j]
            if ci < min_chroma or cj < min_chroma:
                continue
            if abs((hi - hj + 180.0) % 360.0 - 180.0) >= min_angle:
                out.add(frozenset((i, j)))
        elif _COMPLEMENT.get(a) == b or _COMPLEMENT.get(b) == a:
            out.add(frozenset((i, j)))
    return out


def is_complementary(a: str, b: str) -> bool:
    """Letter rule only (see :func:`complementary_pairs` for measured hues)."""
    a, b = ink_family(a), ink_family(b)
    return _COMPLEMENT.get(a) == b or _COMPLEMENT.get(b) == a


def is_light_pair(a: str, b: str) -> bool:
    """True for a light/medium ink and its own parent (c+lc, k+lk, ...)."""
    return a != b and ink_family(a) == ink_family(b)


def _scale_into_limit(row: list[float], limit: float) -> list[float]:
    """Scale every ink by the same factor so the total meets ``limit``:
    unlike the simplex projection this keeps the patch's ink COUNT (a
    two-ink grid patch stays a two-ink patch)."""
    tot = sum(row)
    if tot <= limit or tot <= 0.0:
        return row
    f = limit / tot
    return [v * f for v in row]


def pair_grid_levels(levels: int) -> list[float]:
    """Per-ink values of a ``levels`` x ``levels`` pair grid, light-spaced like
    the ramps (2 -> 35 100; 3 -> 19 54 100; 5 -> 9 25 46 72 100): light
    two-ink overprints are sampled, the solid is included, no zero."""
    return ramp_levels(max(1, int(levels)), 100.0, "light")


# a light ink with its own dark parent: the hand-over region (dark ink
# from 0 to 20 % under a light ink) is where a light-ink separation lives
_HANDOVER_LIGHT = (25.0, 50.0, 75.0, 100.0)
_HANDOVER_DARK = (5.0, 10.0, 20.0, 40.0, 70.0, 100.0)


def _pair_values(i, j, inks, levels, comp):
    a, b = inks[i], inks[j]
    if frozenset((i, j)) in comp:
        lv = pair_grid_levels(max(1, min(levels, 2)))      # coarse: 35 100
        return [(x, y) for x in lv for y in lv]
    if is_light_pair(a, b):
        light_first = a in _LIGHT_PARENT
        out = []
        for lv in _HANDOVER_LIGHT:
            for dv in _HANDOVER_DARK:
                out.append((lv, dv) if light_first else (dv, lv))
        return out
    if a in _PROCESS and b in _PROCESS:
        lv = pair_grid_levels(levels + 2)                   # CM CY MY: densest
    else:
        lv = pair_grid_levels(levels)
    return [(x, y) for x in lv for y in lv]


def ink_pair_grids(inks, levels: int = 3, ink_limit: float = 300.0,
                   comp=None) -> list[tuple[float, ...]]:
    """Every pair of inks as a small two-ink GRID (not the diagonal that
    :func:`ink_pair_overprints` samples), light-spaced levels: ``levels`` per
    ink, process pairs (C M Y) ``levels + 2`` like the ECG charts' 8 x 8,
    complementary pairs 2 x 2, a light ink with its own parent the hand-over
    grid (dark ink 5-100 % under the light ink). Grid points over the ink
    limit are scaled down (both inks by the same factor), so every patch has
    exactly two inks. ``comp``: :func:`complementary_pairs` (default: letters)."""
    inks = list(inks)
    n = len(inks)
    limit = float(ink_limit)
    comp = complementary_pairs(inks) if comp is None else comp
    out: list[tuple[float, ...]] = []
    for i, j in itertools.combinations(range(n), 2):
        if inks[i] in _NOT_A_COLORANT or inks[j] in _NOT_A_COLORANT:
            continue
        for a, b in _pair_values(i, j, inks, levels, comp):
            row = [0.0] * n
            row[i], row[j] = min(a, limit), min(b, limit)
            out.append(tuple(_scale_into_limit(row, limit)))
    return out


def ink_pair_grids_count(inks, levels: int = 3, comp=None) -> int:
    inks = list(inks)
    comp = complementary_pairs(inks) if comp is None else comp
    return sum(len(_pair_values(i, j, inks, levels, comp))
               for i, j in itertools.combinations(range(len(inks)), 2)
               if inks[i] not in _NOT_A_COLORANT and inks[j] not in _NOT_A_COLORANT)


def subset_weight(subset, inks=None, comp=None, comp_weight: float = 0.5) -> float:
    """How often :func:`separation_fill_nd` draws an ink subset.

    ``subset``: ink codes, or indices into ``inks``. A subset holding a
    complementary pair (:func:`complementary_pairs`) weighs ``comp_weight``
    (sampled, because full separations do use such pairs, but less: the ECG
    charts sample them about a third as densely; ChromIQ's own engine puts
    complementary inks together in 55-80 % of a hue circle, so 0.5 is the
    default); every other subset 1."""
    if inks is None:
        codes = list(subset)
        idx = list(range(len(codes)))
        comp = complementary_pairs(codes) if comp is None else comp
    else:
        idx = list(subset)
        comp = complementary_pairs(inks) if comp is None else comp
    if any(frozenset(p) in comp for p in itertools.combinations(idx, 2)):
        return float(comp_weight)
    return 1.0


def _family_subsets(inks, size):
    """Ink-index subsets with ``size`` hue FAMILIES (white left out). A
    family with a light ink contributes its dark ink, its light ink, or both
    (the hand-over), so a CMYKcm chart gets 5-6 physical inks where a
    light-ink separation lays them."""
    fams: dict[str, list[int]] = {}
    for i, c in enumerate(inks):
        if c in _NOT_A_COLORANT:
            continue
        fams.setdefault(ink_family(c), []).append(i)
    names = list(fams)
    out = []
    for combo in itertools.combinations(names, size):
        choices = []
        for f in combo:
            members = fams[f]
            opts = [(m,) for m in members]
            if len(members) > 1:
                opts.append(tuple(members))
            choices.append(opts)
        for pick in itertools.product(*choices):
            out.append(tuple(sorted(i for part in pick for i in part)))
    return out


def _onto_face(cand, sub, lim):
    """Raise the chosen inks by a common amount (each capped at 100 %) until
    the total reaches ``lim``: a point on the ink-limit face with the same
    inks on (the caller only asks when the inks can reach the limit)."""
    import numpy as np
    out = cand.copy()
    for r in range(len(out)):
        v = out[r, sub]
        if v.sum() >= lim:
            continue
        lo_t, hi_t = 0.0, 100.0
        for _ in range(40):
            t = 0.5 * (lo_t + hi_t)
            if np.minimum(v + t, 100.0).sum() < lim:
                lo_t = t
            else:
                hi_t = t
        out[r, sub] = np.minimum(v + hi_t, 100.0)
    return out


def separation_fill_nd(existing, total: int, inks,
                       ink_limit: float | None = None,
                       max_inks: int = 4, share3: float = 0.5,
                       share5: float = 0.08, comp=None,
                       comp_weight: float = 0.5, face_share: float = 0.15,
                       min_ink: float = 5.0, candidates: int = 12,
                       seed: int = 0) -> list[tuple[float, ...]]:
    """Top the chart up to ``total`` patches where separations live, instead
    of :func:`fill_gaps_nd`'s all-ink cloud.

    For each new patch: a size in hue FAMILIES (3 with probability
    ``share3``, else ``max_inks``; with ``share5`` of the fill, 5 or more
    families, so the dense interior that deep saturated darks need is not
    starved; never more than the chart has), an ink subset drawn by
    :func:`subset_weight`, ``candidates`` random points inside that subset
    (every chosen ink at least ``min_ink`` %, so the ink count is exact),
    scaled into the ink limit, and ``face_share`` of the patches pushed onto
    the ink-limit face (scaled UP to the limit where the inks allow it): the
    shadows of a separation run along that face. The candidate farthest from
    every patch so far is kept (blue noise, as :func:`fill_gaps_nd`).
    Deterministic for a seed."""
    import numpy as np

    inks = list(inks)
    n = len(inks)
    total = int(total)
    pts = [tuple(float(v) for v in p) for p in existing]
    n_add = total - len(pts)
    if n_add <= 0 or n < 2:
        return []
    comp = complementary_pairs(inks) if comp is None else comp
    n_fam = len({ink_family(c) for c in inks if c not in _NOT_A_COLORANT})
    if n_fam < 2:
        return []
    top = max(2, min(int(max_inks), n_fam))
    sizes = sorted({min(3, top), top})
    p_size = [float(share3), 1.0 - float(share3)] if len(sizes) == 2 else [1.0]
    big = list(range(top + 1, n_fam + 1))
    s5 = float(share5) if big else 0.0
    groups = [(sizes, [w * (1.0 - s5) for w in p_size])]
    if s5 > 0:
        groups.append((big, [s5 / len(big)] * len(big)))
    all_sizes = [s for g in groups for s in g[0]]
    all_p = np.array([w for g in groups for w in g[1]], float)
    all_p = all_p / all_p.sum()
    subsets, weights = {}, {}
    for s in all_sizes:
        subs = _family_subsets(inks, s)
        w = np.array([subset_weight(sub, inks, comp, comp_weight) for sub in subs])
        subsets[s], weights[s] = subs, w / w.sum()
    rng = np.random.default_rng(seed)
    arr = np.array(pts, dtype=float) if pts else np.empty((0, n))
    added: list[tuple[float, ...]] = []
    lo = float(min_ink)
    for _ in range(n_add):
        s = all_sizes[int(rng.choice(len(all_sizes), p=all_p))]
        sub = subsets[s][int(rng.choice(len(subsets[s]), p=weights[s]))]
        cand = np.zeros((max(1, candidates), n))
        cand[:, list(sub)] = rng.uniform(lo, 100.0, size=(len(cand), len(sub)))
        if ink_limit is not None:
            lim = float(ink_limit)
            tot = cand.sum(1, keepdims=True)
            # only subsets that can reach the limit go onto its face (three
            # inks cannot reach 352 %; pushing them would just repeat the
            # 3-ink solid overprint)
            if 100.0 * len(sub) > lim and rng.uniform() < face_share:
                cand = _onto_face(cand, list(sub), lim)
                tot = cand.sum(1, keepdims=True)
            cand = np.where(tot > lim, cand * (lim / tot), cand)
        if len(arr):
            d2 = ((cand[:, None, :] - arr[None, :, :]) ** 2).sum(2).min(axis=1)
            pick = cand[int(np.argmax(d2))]
        else:
            pick = cand[0]
        added.append(tuple(float(v) for v in pick))
        arr = np.vstack([arr, pick[None, :]])
    return added
