"""Area-first layout: size the patches to fill a target grid in the usable area.

The default engine layout is *patch-first* — you set the patch size and it fits
as many as possible, so the block rarely reaches the far margin. *Area-first*
(Knut's request, #93) flips it: you say how many strips (columns) and/or patches
per strip (rows) you want, and the engine derives the patch size so the grid
fills the usable area exactly. Patch size becomes the result, not the input.

This is a pre-process on the build-kwargs: it derives ``patch_w`` / ``patch_h``
and lets the normal patch-first geometry place them — so the capacity estimate
and the render stay in lock-step (they share the derived sizes), and instrument
constraints (clip border, label band, spacers, cut lines) are honoured because
the derivation measures a real provisional geometry.
"""
from __future__ import annotations

import math

from . import geometry, instruments, papers

_MIN_PATCH_MM = 1.0       # floor so a too-dense grid can't go degenerate


def _usable(geom, w_mm: float, h_mm: float) -> tuple[float, float]:
    """(usable_width, usable_pass_length) in mm for the patch block.

    Area-first is "margins are the law" (Knut #93): the usable patch area is
    exactly the margin box — no hidden leader/trailer/label-band reserve (strip
    labels live inside the top margin) and no instrument ruler cap (the box is
    filled even past the ruler; a violation warns). This mirrors
    geometry.compute()'s law branch so the derived patch size fills the same area
    the renderer places into. The clip / notes band lives inside the clip-side
    margin (build() floors that margin to the clip width), so it is not
    subtracted again here.
    """
    g = geom
    iw = w_mm - g.margin_l - g.margin_r
    # §R1.4 — the band lives inside the left margin now (see
    # `raster.apply_row_label_geometry`), so it is not taken off the patch area
    # here either. This was the third site of the same subtraction, and the one
    # that had no guard at all: switching row indicators on made the block stop
    # 7.45 mm short of the right margin while still starting at the left one.
    avail_w = iw - 2.0 * g.hxew - (g.pglth if g.dopglabel else 0.0)
    arowl = h_mm - g.margin_t - g.margin_b - 2.0 * g.hxeh
    return max(0.0, avail_w), max(0.0, arowl)


def _fit_columns(base: dict, w_mm: float, h_mm: float, cols: int,
                 max_pw: float) -> float | None:
    """Largest patch width (mm) at which exactly *cols* strips still fit across
    the page — so the strips span the usable width. Binary search over the real
    geometry (pitch / cut-line / clip-border overhead make a closed form
    instrument-specific)."""
    def strips(pw: float) -> int:
        # Columns across the page = passes = patches_per_page / steps_in_pass
        # (strips_per_page is 1 for the single-strip instruments).
        try:
            # …under the area-first law, like every other geometry derived
            # from `base` — see `_as_area_first`. Without this the binary
            # search below counts columns in a box 7.5 mm narrower than the
            # one the renderer will actually use.
            g = _as_area_first(
                instruments.geom_from_build_kwargs({**base, "patch_w": pw}))
            lay = geometry.compute(g, w_mm, h_mm, 100_000)
            return (lay.patches_per_page // lay.steps_in_pass
                    if lay.steps_in_pass else 0)
        except geometry.LayoutError:
            return 0

    if strips(_MIN_PATCH_MM) < cols:
        return None                       # can't fit that many even at the floor
    lo, hi = _MIN_PATCH_MM, max(_MIN_PATCH_MM, max_pw)
    for _ in range(40):
        mid = (lo + hi) / 2.0
        if strips(mid) >= cols:
            lo = mid                      # still fits → patches can grow
        else:
            hi = mid
    return lo


def _as_area_first(geom):
    """The provisional geometry, told which law it is actually under.

    `geom_from_build_kwargs` sets `margins_are_law` and `fill_beyond_ruler`
    from the layout mode, and this module deliberately hands it "patch_first"
    to get an automatic patch size without recursing. Both flags then come out
    wrong for the recipe being derived.
    """
    import dataclasses
    try:
        return dataclasses.replace(geom, margins_are_law=True,
                                   fill_beyond_ruler=True)
    except Exception:          # noqa: BLE001 — never lose a layout over it
        return geom


def derive_area_patch_size(kw: dict) -> tuple[float, float] | None:
    """``(patch_w_mm, patch_h_mm)`` for an area-first recipe, or None when it
    doesn't apply (patch-first, or no target given). The caller sets these into
    the build-kwargs and runs the normal patch-first pipeline."""
    if kw.get("layout_mode") != "area_first":
        return None
    cols = int(kw.get("area_cols") or 0)
    rows = int(kw.get("area_rows") or 0)
    ratio = float(kw.get("area_ratio") or 0.0)     # height : width
    # A HEXAGON'S PROPORTIONS ARE NOT THE USER'S TO CHOOSE.
    #
    # area_first sizes patches to fill the page from a height:width ratio the
    # user sets. For a honeycomb that ratio is fixed by geometry: the slot must
    # be `pwid * sqrt(3)/2` so the apexes (which overhang by plen/6 at each end)
    # interlock with the rows above and below. Ignoring it drew STRETCHED
    # hexagons -- measured +17 % on a SpectroScan and +20 % on a CR30 -- and
    # because the interlock pitch was then wrong the patch count DROPPED (SS
    # -8.5 %, CR30 -4.5 %) while the "hexagon patches" checkbox promised more.
    #
    # Pre-existing: the SpectroScan has shipped this way. Fixed rather than
    # papered over on Basti's ruling (2026-08-28).
    #
    # `hflag` alone is not the test: on a ColorMunki it means DENSITY, not
    # hexagons. `hex_capable` asks the geometry whether the flag makes a
    # honeycomb, which is the same single source of truth `is_hexagonal` uses.
    if kw.get("hflag") and instruments.hex_capable(str(kw.get("instrument") or "")):
        ratio = math.sqrt(3) / 2.0
    min_w = float(kw.get("area_min_patch") or 0.0)
    # The calculation method selects which inputs drive the grid: "by_width" uses
    # the minimum width + height%, "by_grid" uses explicit columns + rows (#93).
    method = kw.get("area_method") or "by_width"
    if method == "by_grid":
        min_w = 0.0
    else:
        cols = rows = 0
    # Both methods always fill the box now (Knut): "Minimum patch width = auto"
    # is not "don't fill" — it means "use the instrument's natural width as the
    # minimum, then grow to fill", exactly like a typed value. (by_grid likewise
    # always fills.) So area-first never falls back to the loose patch-first size.
    try:
        w_mm, h_mm = papers.dimensions_mm(kw.get("paper", "A4"))
    except Exception:
        return None
    # Provisional geometry (patch-first, auto patch size) for the usable area
    # and the spacer pitch the row formula needs.
    #
    # PATCH-FIRST FOR THE SIZE, AREA-FIRST FOR THE LAW. The mode is flipped so
    # that `geom_from_build_kwargs` resolves an automatic patch size instead of
    # calling back into this function -- but it also DERIVES the two law flags
    # from that same mode, so the provisional geometry came out saying "honour
    # the ruler cap, reserve the row-label band" for a recipe whose whole rule
    # is the opposite. That is why area-first stopped 7.45 mm short of the
    # right margin with row indicators on, and why the guard added to
    # `_usable` first changed nothing: every geometry reaching it, here and in
    # `_cols_at`, had the flag switched off.
    #
    # `_as_area_first` puts the two flags back on every geometry derived from
    # `base`, so the calculation and the render agree about what the box is.
    base = {**kw, "layout_mode": "patch_first"}
    base.pop("patch_w", None)
    base.pop("patch_h", None)
    try:
        geom = _as_area_first(instruments.geom_from_build_kwargs(base))
    except Exception:
        return None
    avail_w, arowl = _usable(geom, w_mm, h_mm)
    if avail_w <= 0 or arowl <= 0:
        return None

    # "Reasonable" default patch size an auto dimension aims for: the instrument's
    # natural patch geometry — the patch dimensions the device was designed to read
    # (its aperture and the along-strip spacing). Knut #93: this is a sufficient
    # auto target on its own, so there's no separate user-facing size table; the
    # area_default_w/h kwargs only let a caller override it for tests. An auto
    # dimension is sized toward this rather than whatever falls out of the page.
    default_w = float(kw.get("area_default_w") or 0.0) or geom.pwid
    default_h = float(kw.get("area_default_h") or 0.0) or geom.plen

    ec = 1.0 if geom.edge_spacers else -1.0     # geometry.compute()'s edge term

    def _rows_filling(n: int) -> float:
        # Invert compute()'s pprow so exactly n patches fill arowl.
        return (arowl - ec * geom.pspa) / max(1, n) - geom.pspa

    def _max_rows_at(height: float) -> int:
        return max(1, int((arowl - ec * geom.pspa) / (height + geom.pspa)))

    def _rows_filling_fit(n: int) -> float:
        # _rows_filling gives the height that EXACTLY fills n rows, but float
        # rounding can leave compute() one row short on the boundary (e.g. n=15 →
        # 15.6000000001 → int(249/16.6)=14). Nudge the height down until n rows
        # are guaranteed to fit, so a pinned/derived row count never loses a row.
        h = _rows_filling(n)
        for _ in range(40):
            if _max_rows_at(h) >= n:
                break
            h -= 0.01
        return h

    def _cols_at(width: float) -> int:
        # Columns a chart with this patch width would lay out across the page.
        try:
            g = _as_area_first(
                instruments.geom_from_build_kwargs({**base, "patch_w": width}))
            lay = geometry.compute(g, w_mm, h_mm, 100_000)
            return (lay.patches_per_page // lay.steps_in_pass
                    if lay.steps_in_pass else 0)
        except geometry.LayoutError:
            return 0

    # Resolve a column target (pinned, or the most that fit at the minimum width)
    # and a row target (pinned, or the most that fit at the minimum height), then
    # SIZE the patches to fill — Knut's "min size + ratio, grow to fill" path,
    # and the explicit-count path, share this fill step.
    # ratio is HEIGHT:WIDTH (height = width * ratio); 0 = square. (The panel
    # shows it as "minimum patch height, % of width".)
    pw = ph = None
    if method != "by_grid":                         # --- by_width: min width + % ---
        # "auto" (no minimum typed) uses the instrument's natural width as the
        # minimum, so it still grows to fill the box (Knut: the label says
        # "minimum", so it's a floor that grows, never a fixed under-fill).
        if min_w <= 0:
            min_w = default_w
        # Default fill: fit as many strips as possible at the minimum, grow the
        # patch width so they span the box, then set the height from the GROWN
        # width via the height-% (the % references the stretched width, Knut) and
        # grow it to fill the usable height — so a full chart fills both axes and
        # keeps the requested patch aspect.
        c = _cols_at(min_w)
        if c > 0:
            pw = _fit_columns(base, w_mm, h_mm, c, max_pw=avail_w)
        h_min = (pw * ratio) if (pw is not None and ratio > 0) else (
            (min_w * ratio) if ratio > 0 else (pw or min_w))
        ph = max(_MIN_PATCH_MM, _rows_filling_fit(_max_rows_at(h_min)))
        # If the chart's patch count is below one page's capacity, grow the
        # patches so they fill the area — the box is law (Knut). The height-% is a
        # MINIMUM: the patch height is never below width × % (`_floor_ph`); if a
        # grid would make it shorter, fewer/taller rows are used and the count
        # overflows to more pages. The grow is only used when it keeps the SAME
        # page count as the plain min-fill (never adds a page just to grow).
        target = int(kw.get("area_target_count") or 0)

        def _floor_ph(pw_v: float) -> float:
            """Height that fills the most rows while staying ≥ the width-% floor."""
            fl = pw_v * ratio if (pw_v and ratio > 0) else _MIN_PATCH_MM
            return max(_MIN_PATCH_MM, _rows_filling_fit(_max_rows_at(fl)))

        # Min-fill already respects the floor; clamp once more for safety.
        if pw is not None:
            ph = max(ph or 0.0, _floor_ph(pw))
        if target > 0 and pw is not None and ph is not None:
            cmax = _cols_at(min_w) or 1
            # When the count FITS ON ONE PAGE, grow the patches so they fill it:
            # try every column count from the max (smallest, min-width patches) down,
            # fill the width with that many strips, then fill the height with exactly
            # the rows the count needs — but never shorter than the width-% floor
            # (cap the rows at the floor). Among the column counts that hold the whole
            # count on a single page, pick the BIGGEST patch (most filled). This
            # fills near-capacity counts a coarser column-only grow would leave
            # gapped, while honouring the floor. A count that does NOT fit one page
            # keeps the min-fill size and overflows to more pages, last page partial
            # (Knut: overflow, not shrink — and don't shrink-to-balance either).
            best = None                                # (-pw, pw, ph)
            for cols in range(cmax, 0, -1):
                if cols > target:                      # no empty trailing columns
                    continue
                _pw = _fit_columns(base, w_mm, h_mm, cols, max_pw=avail_w)
                if not _pw:
                    continue
                rows_need = max(1, math.ceil(target / cols))
                rows_floor = _max_rows_at(_pw * ratio) if ratio > 0 else rows_need
                if cols * rows_floor < target:         # can't hold it on one page
                    continue                           #   at the floor → skip (grow
                rows = rows_need                       #   would force a 2nd page)
                _ph = _rows_filling(rows)
                # compute() can fall a row short on float rounding; nudge until the
                # rows are guaranteed, so the grid doesn't spill onto a stray page.
                for _ in range(40):
                    if _max_rows_at(_ph) >= rows:
                        break
                    _ph -= 0.02
                _ph = max(_MIN_PATCH_MM, _ph)
                if best is None or -_pw < best[0]:
                    best = (-_pw, _pw, _ph)
            if best is not None:
                pw, ph = best[1], best[2]
    else:                                           # --- by_grid: columns / rows ---
        # Pinned dimensions size their patches to fill exactly that many; an "auto"
        # dimension picks a count that gives a REASONABLE patch size — the ratio-
        # linked size when the other dimension is pinned (so the shape is kept),
        # otherwise the instrument's NATURAL patch size (its built-in width/height,
        # the per-instrument "default size" reference) — then fills to that count
        # (Knut #93). Columns first, so rows-auto can use the resolved width.
        if rows > 0:
            ph = max(_MIN_PATCH_MM, _rows_filling_fit(rows))
        if cols > 0:
            pw = _fit_columns(base, w_mm, h_mm, cols, max_pw=avail_w)
        if cols <= 0:                               # columns auto → fill the width
            target_w = (ph / ratio) if (ph is not None and ratio > 0) else default_w
            c = _cols_at(target_w)
            if c > 0:
                pw = _fit_columns(base, w_mm, h_mm, c, max_pw=avail_w)
        if rows <= 0:                               # rows auto → fill the height
            target_h = (pw * ratio) if (pw is not None and ratio > 0) else default_h
            ph = max(_MIN_PATCH_MM, _rows_filling_fit(_max_rows_at(target_h)))

    if pw is None and ph is not None:
        pw = ph / ratio if ratio > 0 else ph
    if ph is None and pw is not None:
        # Columns pinned, rows on "auto": area-first should FILL the page, so grow
        # the patch height until the last row reaches the bottom margin, using the
        # ratio/square height only as a floor — otherwise square patches leave a
        # gap at the bottom (#93, Knut beta-13).
        base_h = pw * ratio if ratio > 0 else pw
        ph = max(_MIN_PATCH_MM, base_h, _rows_filling_fit(_max_rows_at(base_h)))
    if pw is None or ph is None or pw <= 0 or ph <= 0:
        return None
    # A HONEYCOMB'S HEIGHT IS DERIVED, NEVER GROWN.
    #
    # The ratio set above is only a FLOOR for the solver: `_rows_filling_fit`
    # then grows the height to fill the page, which for a hexagon re-stretches
    # the very proportion the ratio was there to fix. Snapping here is what
    # makes the constraint absolute, whichever solver path ran. Hexagons
    # interlock, so a height that does not divide the page exactly simply ends
    # the last row early -- there is nothing to gain by stretching it.
    if pw and kw.get("hflag") and instruments.hex_capable(
            str(kw.get("instrument") or "")):
        ph = pw * math.sqrt(3) / 2.0
    # Floor to 0.01 mm so rounding can't nudge the patch over the boundary and
    # drop the column/row we just fitted.
    return (math.floor(pw * 100) / 100.0, math.floor(ph * 100) / 100.0)
