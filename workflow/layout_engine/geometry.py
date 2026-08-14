"""Chart packing math — a faithful port of printtarg.c ``setup_pat``.

Given a resolved :class:`~workflow.layout_engine.instruments.Geom` and a page
size, compute how the patches lay out: steps per pass, passes (rows), strips
and pages, plus the number of padding patches printtarg appends to complete the
final pass.  Verified to reproduce printtarg's reported numbers exactly across
the instrument/paper matrix (see ``tests/test_layout_geometry.py``).

The variable names mirror printtarg.c so the two can be diffed line-for-line.
"""
from __future__ import annotations

from dataclasses import dataclass

from .instruments import Geom


class LayoutError(ValueError):
    """Raised when the page can't hold even a single pass of patches."""


@dataclass(frozen=True)
class Layout:
    steps_in_pass: int      # tpprow — test patches per pass (CGATS STEPS_IN_PASS)
    passes: int             # rows in the (last) strip (CGATS PASSES_IN_STRIPS2)
    strips_per_page: int    # sppage
    rows_in_partial_strip: int  # rppstrip
    patches_per_page: int   # pppage (test patches)
    pages: int              # npages
    padding: int            # extra media patches appended to fill the last pass
    total_patches: int      # input npat + padding
    pprow: int              # raw patches per pass incl. nextrap

    @property
    def fits_one_page(self) -> bool:
        return self.pages <= 1


def compute(geom: Geom, paper_w_mm: float, paper_h_mm: float, npat: int,
            *, scanc: int = 0) -> Layout:
    """Lay *npat* patches out for *geom* on a ``paper_w_mm`` × ``paper_h_mm`` sheet.

    *scanc* bit 2 set ⇒ scan-compatibility first-row extra width (printtarg -s).
    Returns a :class:`Layout`.  Raises :class:`LayoutError` if nothing fits.
    """
    if npat < 1:
        raise LayoutError("need at least one patch")

    pw, ph = paper_w_mm, paper_h_mm
    g = geom

    sxwi = g.pwid / 2.0 if (scanc & 2) else 0.0

    # Imageable width: the per-edge page margins govern where patches start. The
    # clip / notes band lives INSIDE the clip-side margin (the UI bumps that
    # margin to at least the clip-border width), so it is NOT subtracted again
    # here — otherwise it would be double-counted (Knut beta-13, clip-inside-
    # margin; supersedes the old additive lbord model).
    iw = pw - g.margin_l - g.margin_r

    # Available pass length down the sheet (top/bottom margins, floored by the
    # instrument's own leader/trailer requirements). The top label band uses the
    # ACTUAL rendered strip-label + underline height when known (label_band_mm),
    # not just the fixed instrument text height, so a big/rotated indicator or an
    # underline reduces the patch count instead of overlapping the patches; the
    # bottom likewise reserves the sheet-text/stamp block (#93).
    # Effective label band: the actual rendered height when known (≥0; 0 when
    # indicators are off), else the instrument default txhisl. The leader floor
    # (lspa) bakes in the label height, so when the band is smaller/absent it
    # drops by the reclaimed amount — but never below the instrument's physical
    # run-up (border + lcar), which must stay clear (#93).
    txhi = g.txhisl if g.label_band_mm < 0 else g.label_band_mm
    eff_lspa = max(g.border + g.lcar, g.lspa - g.txhisl + txhi)
    if g.margins_are_law:
        # "Use instrument margins" mode (Knut): the patch area is exactly the
        # page-margin box — no hidden leader/trailer/clear-area, no label/text
        # reserve. Labels/text live INSIDE the margins (render-positioned); if a
        # margin is too small they overflow toward the edge and a violation is
        # flagged. Only the hex/stagger overhang (a patch-shape property) reduces
        # the usable length.
        mints = g.margin_t
        minbs = g.margin_b
        arowl = ph - mints - minbs - 2.0 * g.hxeh
    else:
        # Default (printtarg-style): the margins are floored by the instrument's
        # physical leader/trailer + clear-area, and the rendered label/sheet-text
        # band is reserved on top — so furniture reduces the patch count.
        mints = max(g.margin_t + txhi + g.lcar, eff_lspa)
        minbs = max(g.margin_b, g.tspa, g.bottom_reserve_mm)
        arowl = ph - mints - minbs - 2.0 * g.hxeh - g.strip_indicator_gap
    # The physical ruler cap (i1Pro 240 mm jig etc.) applies in patch-first mode —
    # ALSO when "Use instrument margins" makes the margins the law (its "max strip
    # length" must still protect the jig). Only area-first fills past the ruler and
    # flags a too-long strip with a warning, so the cap is keyed on fill_beyond_ruler
    # (area-first), not on margins_are_law (Knut).
    if not g.fill_beyond_ruler and arowl > g.mxrowl:
        arowl = g.mxrowl

    # Patches per pass. n patches need (n-1) between-spacers, plus a leading and
    # trailing spacer when edge spacers are on (printtarg always reserves these).
    # When edge spacers are OFF we reclaim those two end gaps for patches — the
    # instrument's white leader/trailer comes from the clear area + margins, not
    # these gaps — so the engine packs denser than printtarg (#93).
    if (g.plen + g.pspa) <= 0:
        raise LayoutError("degenerate patch length")
    _edge_gaps = 2 if g.edge_spacers else 0
    pprow = int((arowl - (_edge_gaps - 1) * g.pspa) / (g.plen + g.pspa))
    if pprow > g.mxpprow:
        pprow = g.mxpprow
    if pprow < (1 + g.nextrap):
        raise LayoutError(
            f"paper too short: a single pass of patches does not fit "
            f"({arowl:.1f} mm available)"
        )
    tpprow = pprow - g.nextrap

    tidnpat = npat  # no target-ID rows for the RGB path

    # Strip width and strips/rows across the sheet.
    if g.dorspace:
        swid = g.rpstrip * g.rrsp + g.pwid / 2.0
    else:
        swid = (g.rpstrip - 1) * g.rrsp + g.pwid + g.clwi

    avail_w = iw - g.rlwi - sxwi - 2.0 * g.hxew - (g.pglth if g.dopglabel else 0.0)
    sppage = int(avail_w / swid) + 1
    if g.dorspace:
        rppstrip = int((avail_w - swid * (sppage - 1) - g.pwid / 2.0) / g.rrsp)
    else:
        rppstrip = int((avail_w - swid * (sppage - 1) - g.pwid + g.rrsp) / g.rrsp)
    if rppstrip < 0:
        rppstrip = 0
    if rppstrip == 0:                 # last partial strip becomes a full strip
        sppage -= 1
        rppstrip = g.rpstrip
    if sppage <= 0:
        raise LayoutError("not enough width for even one row")

    pppage = tpprow * ((sppage - 1) * g.rpstrip + rppstrip)
    if pppage <= 0:
        raise LayoutError("page holds no patches")
    npages = (tidnpat + pppage - 1) // pppage
    ppstrip = tpprow * g.rpstrip

    rem = tidnpat - (npages - 1) * pppage
    lsppage = (rem + ppstrip - 1) // ppstrip
    rem -= (lsppage - 1) * ppstrip
    lrpstrip = (rem + tpprow - 1) // tpprow
    rem -= (lrpstrip - 1) * tpprow
    lpprow = rem + g.nextrap

    padding = max(0, pprow - lpprow) if g.padlrow else 0

    return Layout(
        steps_in_pass=tpprow,
        passes=lrpstrip,
        strips_per_page=sppage,
        rows_in_partial_strip=rppstrip,
        patches_per_page=pppage,
        pages=npages,
        padding=padding,
        total_patches=npat + padding,
        pprow=pprow,
    )


@dataclass(frozen=True)
class Placement:
    """Millimetre placement parameters for rendering, mirroring printtarg.

    A patch at (pass *p*, position *j* down the pass) occupies the rectangle
    ``(x_of(p), y_of(j), pwid, plen)``; the spacer below it is ``pspa`` tall.
    """
    x0: float            # left of the first pass (mm) = border + lbord
    y0_first: float      # top of the first patch in a pass (mm)
    plen: float
    pwid: float
    pspa: float
    rrsp: float
    steps_in_pass: int
    leader_top: float    # top of the leader area (for the strip label), mm

    def x_of(self, pass_idx: int) -> float:
        return self.x0 + pass_idx * self.rrsp

    def y_of(self, pos: int) -> float:
        return self.y0_first + pos * (self.plen + self.pspa)


def placement(geom: Geom, paper_w_mm: float, paper_h_mm: float, layout: Layout) -> Placement:
    """Resolve mm placement for *layout* on the sheet (single strip per page).

    Reproduces printtarg's vertical-space distribution (``amints``).  Exact for
    the strip-reader instruments that use one strip per page (i1/p3/CM/SS);
    multi-strip instruments (DTP41/51) will gain strip gutters in a later pass.
    """
    g = geom
    ph = paper_h_mm
    pw = paper_w_mm
    # Top/bottom reservations use the independent page margins (floored by the
    # instrument's leader/trailer minimums), matching compute() — previously this
    # used the base `border` while compute used `margin_t`/`margin_b`, so the two
    # disagreed whenever a margin differed from the border. The strip-indicator
    # gap is folded into the top reservation (compute() reserves it too), so the
    # patch block is centred in the space that actually remains and never runs off
    # the usable area (#93).
    # Effective label band (actual indicator+underline height when known) and
    # bottom reserve (sheet text / stamp), matching compute() so capacity and
    # placement agree. The strip labels start flush under the top margin (the band
    # below them is sized to the real label — font / size / rotation / multi-letter
    # — by apply_furniture_reserves); the white leader still sits between the band
    # and the first patch. A user strip_label_offset (applied in raster) nudges
    # the labels from there.
    txhi = g.txhisl if g.label_band_mm < 0 else g.label_band_mm
    eff_lspa = max(g.border + g.lcar, g.lspa - g.txhisl + txhi)
    # Match compute()'s branch: margins-are-law (exact box) vs printtarg-style.
    if g.margins_are_law:
        mints = g.margin_t
        minbs = g.margin_b
    else:
        mints = max(g.margin_t + txhi + g.lcar, eff_lspa) + g.strip_indicator_gap
        minbs = max(g.margin_b, g.tspa, g.bottom_reserve_mm)
    # The strip block carries a leading + trailing spacer only when edge spacers
    # are on; off, those gaps are reclaimed (matching compute()), so the first
    # patch sits at the block top. _lead is the leading gap.
    _lead = g.pspa if g.edge_spacers else 0.0
    _block = (layout.pprow * (g.plen + g.pspa)
              + (g.pspa if g.edge_spacers else -g.pspa))
    # Patch-area alignment within the usable area (#93). The block is positioned
    # in the free span between the top reserve (mints) and bottom reserve (minbs)
    # vertically, and within the imageable width horizontally. The default
    # "center-left" reproduces printtarg's behaviour exactly: vertically centred
    # (fv = 0.5 → amints = mints + 0.5*(slack - minbs)) and left-anchored
    # (fh = 0). top/bottom and center/right shift the block within the slack only
    # — capacity is unchanged.
    fv, fh = _align_fractions(g.patch_area_align)
    slack = ph - mints - _block
    amints = mints + fv * (slack - minbs)
    # Horizontal slack: passes tile from the left of the imageable area; the
    # leftover to the right of the block is distributed by fh.
    n_passes = (layout.patches_per_page // layout.steps_in_pass
                if layout.steps_in_pass else 0)
    block_w = (max(0, n_passes - 1) * g.rrsp + g.pwid) if n_passes else 0.0
    avail_w = (pw - g.margin_l - g.margin_r
               - g.rlwi - 2.0 * g.hxew - (g.pglth if g.dopglabel else 0.0))
    extra_w = max(0.0, avail_w - block_w)
    # The clip / notes band lives inside the clip-side margin now (not added to
    # the patch origin), so patches simply start at the left margin (Knut beta-13,
    # clip-inside-margin). Hex stagger (SpectroScan): patches shift ±¼·width / the
    # apexes overshoot by hxeh, so start the block hxew in from the left and hxeh
    # down from the top (the area reserves 2·hxew / 2·hxeh). Zero for non-hex.
    # rlwi reserves a row-label band on the left (SpectroScan only — it labels the
    # grid 2-D: column letters on top + row numbers down the side, #93 Knut), so
    # the patch block starts after it. avail_w already excludes rlwi.
    # hxeh shifts the block top only for hex patches (their apexes genuinely
    # overshoot upward). The ColorMunki strip stagger (row_stagger_mm) also
    # reserves hxeh, but its overhang is downward-only — printtarg keeps the
    # grid flush at the top and absorbs the whole overhang below, and shifting
    # down here ate 3.3 mm of the CM trailer reserve (verified against
    # printtarg -h: tops 40.4/47.1 mm, trailer stays ≥ tspa 25 mm).
    _hex_shift = g.hxeh if g.row_stagger_mm <= 0 else 0.0
    _y0 = amints + _lead + _hex_shift + g.offset_y
    if g.margins_are_law:
        # Strip labels live in the top margin at the text-edge distance from the
        # PAGE EDGE (Knut: 4 mm), but they must NEVER sit behind the patches. So
        # anchor the label's BOTTOM at the patch-area top (margin_t): when the top
        # margin is too small for the label, the label slides UP toward the page
        # edge (encroaching the 4 mm text-edge if it must) instead of overlapping
        # the patch block — clamped at the page edge. A too-small margin still
        # raises a warning in the inspector (#93, Knut).
        _lab_h = g.label_band_mm if g.label_band_mm >= 0 else g.txhisl
        _ideal_top = g.text_edge_top_mm + g.strip_indicator_gap
        _leader_top = max(0.0, min(_ideal_top, g.margin_t - _lab_h)) + g.offset_y
    else:
        _leader_top = g.margin_t + g.offset_y   # default: flush under the margin
    # A right-side clip: the patches must butt against the clip zone (the
    # instrument grips there), so right-anchor the block and let the horizontal
    # slack fall on the LEFT (non-clip) side. Left-anchoring piled the slack onto
    # the right, widening the right clip beyond its set width (Knut).
    fh_eff = (1.0 if (getattr(g, "clip_side", "left") == "right" and g.lbord > 0)
              else fh)
    return Placement(
        x0=g.margin_l + g.rlwi + fh_eff * extra_w + g.hxew + g.offset_x,
        y0_first=_y0,
        plen=g.plen, pwid=g.pwid, pspa=g.pspa, rrsp=g.rrsp,
        steps_in_pass=layout.steps_in_pass,
        leader_top=_leader_top,
    )


_VFRAC = {"top": 0.0, "center": 0.5, "bottom": 1.0}
_HFRAC = {"left": 0.0, "center": 0.5, "right": 1.0}


def _align_fractions(align: str) -> tuple[float, float]:
    """(vertical, horizontal) slack fractions for a patch-area alignment key
    like ``"top-left"`` / ``"center"`` (the centre). Unknown → center-left."""
    align = (align or "center-left").strip().lower()
    if align == "center":
        vk = hk = "center"
    elif "-" in align:
        vk, hk = align.split("-", 1)
    else:
        vk, hk = "center", align
    return _VFRAC.get(vk, 0.5), _HFRAC.get(hk, 0.0)


def realized_margins_mm(geom: Geom, paper_w_mm: float, paper_h_mm: float,
                        layout: Layout) -> tuple[float, float, float, float]:
    """``(left, right, top, bottom)`` white gap from each page edge to the patch
    area, in mm — the analytic twin of what :mod:`workflow.margin_inspector`
    measures from a rendered page. Used to enforce the user's margin thresholds
    at layout time, before anything is rendered (#93).

    Measured to the patches/spacers block only: the left includes the clip
    border, the top includes the strip-label band, exactly as the inspector
    reports them. The fullest page (page 0) governs.
    """
    place = placement(geom, paper_w_mm, paper_h_mm, layout)
    steps = layout.steps_in_pass
    n_first = min(layout.total_patches, layout.patches_per_page)
    n_passes = (n_first + steps - 1) // steps if steps else 0
    rows0 = min(steps, n_first) if steps else 0
    # Edge spacers (printtarg-style brackets) are drawn one spacer ABOVE the first
    # patch and one BELOW the last (raster.render_pages), so the printed content
    # extends pspa past the patch block on each end. Measure to that content — not
    # the patches — or the strip-length-direction margins under-report and the
    # measured-margin guides sit inside the spacers, which then appear to overflow
    # them (Knut #93/#18). Edge spacers are along the strip axis only, so they
    # affect the top/bottom margins, never left/right.
    _edge = geom.pspa if (geom.edge_spacers and geom.pspa > 0) else 0.0
    left = place.x_of(0)
    top = place.y_of(0) - _edge
    right = paper_w_mm - (place.x_of(max(0, n_passes - 1)) + geom.pwid)
    bottom = paper_h_mm - (place.y_of(max(0, rows0 - 1)) + geom.plen + _edge)
    return (max(0.0, left), max(0.0, right), max(0.0, top), max(0.0, bottom))


# Printer-safe inset for clip-strip content (mm). The clip strip is white space
# the scanner clip grips, so its content can sit closer to the page edge than the
# patch margin — we keep a small safety inset. This makes the clip content (e.g.
# the notes box) the same width regardless of the patch margin, so it isn't
# shrunk by a larger margin (#93, Guided vs Manual). 4 mm is a middle ground
# between the old Manual start (the 6 mm patch margin) and a flush 2 mm edge.
CLIP_CONTENT_INSET_MM = 4.0


def clip_area_mm(geom: Geom, paper_h_mm: float, paper_w_mm: float | None = None
                 ) -> tuple[float, float, float, float] | None:
    """The content-safe rectangle of the clip strip, in mm.

    Returns ``(x, y, w, h)`` for the reserved left band — the whole zone from a
    small printer-safe inset out to the clip-border width (where the first patch
    column begins), running the FULL height of the page (only a small printer-safe
    inset off the top and bottom edges) — or ``None`` when the instrument has no
    clip border.

    The band spans the full clip zone (not just ``lbord`` after the patch
    margin): the patch margin only governs where PATCHES start, but the clip
    strip is white run-up the instrument grips, so its content uses the edge down
    to ``CLIP_CONTENT_INSET_MM``. It also runs the full page height rather than
    being boxed in by the top/bottom patch margins (Knut), so the notes box / logo
    can use the whole strip; only the printer-safe inset keeps it off the edges.
    """
    if geom.lbord <= 0:
        return None
    clip_w = geom.lbord + geom.border          # full reserved zone from the edge
    # Clip content sits this far in from the page edge (the clip-side text-edge
    # distance, default 4 mm; Knut #93), capped so it never eats the whole band.
    inset = min(getattr(geom, "text_edge_clip_mm", CLIP_CONTENT_INSET_MM),
                clip_w * 0.2)
    width = max(0.0, clip_w - inset)
    # Full page height less the printer-safe inset top and bottom (Knut): the
    # clip content is no longer bounded by the patch top/bottom margins.
    v_inset = min(inset, paper_h_mm * 0.1)
    height = max(0.0, paper_h_mm - 2.0 * v_inset)
    # Right-side band: mirror to the far edge (needs the paper width) (#93).
    if getattr(geom, "clip_side", "left") == "right" and paper_w_mm:
        x = paper_w_mm - clip_w
    else:
        x = inset
    return (x, v_inset, width, height)


def clip_area_px(geom: Geom, paper_h_mm: float, dpi: int,
                 paper_w_mm: float | None = None
                 ) -> tuple[int, int, int, int] | None:
    """:func:`clip_area_mm` rounded to whole pixels at *dpi*."""
    area = clip_area_mm(geom, paper_h_mm, paper_w_mm)
    if area is None:
        return None
    mm2px = dpi / 25.4
    return tuple(round(v * mm2px) for v in area)  # type: ignore[return-value]


def strip_rects_px(geom: Geom, paper_w_mm: float, paper_h_mm: float,
                   layout: Layout, dpi: int) -> list[dict]:
    """Exact per-strip (pass) bounding rectangles in pixels, for the measure tab.

    Because the engine *knows* the geometry, the measure-tab highlighter can use
    these directly instead of detecting stripes from the image — a solid,
    guess-free path.  One entry per pass across all pages:
    ``{"page", "pass", "x", "y", "w", "h"}`` (pixel ints, top-left origin).
    """
    mm2px = dpi / 25.4
    place = placement(geom, paper_w_mm, paper_h_mm, layout)
    steps = layout.steps_in_pass
    pppage = layout.patches_per_page
    total = layout.total_patches

    def px(mm: float) -> int:
        return round(mm * mm2px)

    rects: list[dict] = []
    for page in range(layout.pages):
        first = page * pppage
        last = min(total, first + pppage)
        n_passes = (last - first + steps - 1) // steps
        for p in range(n_passes):
            col_n = min(last, first + (p + 1) * steps) - (first + p * steps)
            # THE COLORMUNKI STAGGER MOVES THE WHOLE STRIP DOWN. Every other
            # strip is offset by `row_stagger_mm` — the raster paints it there
            # (raster.py, `_stag`) and patch_rects_px records it — but this
            # function did not, so an odd strip's rectangle ended one stagger
            # ABOVE its own patches: 88 px on an A4 ColorMunki chart at 300 dpi.
            # Everything that asks "where does the chart end" was told the wrong
            # answer, which is why the measure overlay's legend sat on the last
            # patches of the lower strips (Sebastian, 2026-08-13). Same offset,
            # same parity test as the two places that already had it.
            _stag = (px(geom.row_stagger_mm)
                     if (((first // steps) + p) & 1) else 0)
            x = px(place.x_of(p))
            y = px(place.y_of(0)) + _stag
            h = px(place.y_of(col_n - 1) + place.plen) + _stag - y
            rects.append({
                "page": page, "pass": p,
                "x": x, "y": y, "w": px(place.pwid), "h": h,
            })
    return rects


def patch_rects_px(geom: Geom, paper_w_mm: float, paper_h_mm: float,
                   layout: Layout, dpi: int,
                   strip_pattern: str = "A-Z, A-Z",
                   patch_pattern: str = "0-9,@-9,@-9;1-999") -> list[dict]:
    """Exact pixel rectangle of **every** patch slot, with its ``SAMPLE_LOC``.

    Because the engine generates the layout, the position of each patch is known
    exactly — no image detection.  One entry per occupied slot:
    ``{"page","slot","loc","x","y","w","h"}`` in STRIP_THEN_PATCH order.
    """
    from . import permutation  # local import to avoid a cycle

    mm2px = dpi / 25.4
    place = placement(geom, paper_w_mm, paper_h_mm, layout)
    steps = layout.steps_in_pass
    pppage = layout.patches_per_page
    total = layout.total_patches

    def px(mm: float) -> int:
        return round(mm * mm2px)

    # The same test the renderer uses to decide it is drawing hexagons.
    _ss_hex = getattr(geom, "key", "") == "SS" and getattr(geom, "hxew", 0.0) > 0
    out: list[dict] = []
    for page in range(layout.pages):
        first = page * pppage
        last = min(total, first + pppage)
        for wp in range(last - first):
            gslot = first + wp
            p, j = wp // steps, wp % steps
            # Match the renderer's per-strip ColorMunki stagger so click/highlight
            # rects line up with the drawn patches (#93, Knut).
            _stag = (px(geom.row_stagger_mm)
                     if (((first // steps) + p) & 1) else 0)
            loc = permutation.location_label(gslot, steps, strip_pattern, patch_pattern)
            # RECORD THE BOX THE RASTER ACTUALLY PAINTS. It derives each patch's
            # far edge from the SUM — `px(x_of(p) + pwid)` — while this used to
            # round the SIZE on its own, so the recorded box came out up to a
            # pixel smaller than the ink. Everything drawn from this geometry
            # then left a hairline of the real patch showing: measured on a
            # 300 dpi chart, 35 of 60 patches were 1 px short on the right edge
            # and 4 short on the bottom, which is the coloured fringe Sebastian
            # saw around the expected-vs-measured overlay (2026-08-13). Rounding
            # both edges and taking the difference makes the record match the
            # paint exactly — the same rule the overlay already follows on its
            # own side.
            _x0, _y0 = px(place.x_of(p)), px(place.y_of(j)) + _stag
            _x1 = px(place.x_of(p) + place.pwid)
            _y1 = px(place.y_of(j) + place.plen) + _stag
            # SPECTROSCAN HEXAGONS SIT ±¼ WIDTH OFF THEIR SLOT. `raster
            # ._hexagon_points` staggers every hexagon horizontally by the
            # patch's index in the strip, which is what makes the rows
            # interlock like printtarg -h — but the recorded box stayed on the
            # slot, so it described a place no ink is: measured ±21 px on an
            # 84 px patch (Sebastian, 2026-08-13, seen as overlay hexagons
            # sitting over their neighbours). Everything reading this geometry
            # inherited it, the expected-vs-measured overlay and the scanner
            # target's patch boxes alike (workflow/scanin_target.py reads these
            # very rects), so recording the stagger corrects both at once.
            if _ss_hex:
                _dx = round(-(_x1 - _x0) / 4) if j % 2 == 0 else round((_x1 - _x0) / 4)
                _x0 += _dx
                _x1 += _dx
            out.append({
                "page": page, "slot": gslot, "loc": loc,
                "x": _x0, "y": _y0,
                "w": max(1, _x1 - _x0), "h": max(1, _y1 - _y0),
            })
    return out


def spacer_rects_px(geom: Geom, paper_w_mm: float, paper_h_mm: float,
                    layout: Layout, dpi: int) -> list[dict]:
    """Exact pixel rectangle of every inter-patch spacer, with its flat index.

    The flat index matches the one the renderer uses for per-spacer overrides
    (``global_strip * steps_in_pass + position``), so the editor can map a click
    to the spacer the engine will recolour. One entry per spacer:
    ``{"page","flat","x","y","w","h"}``.
    """
    mm2px = dpi / 25.4
    place = placement(geom, paper_w_mm, paper_h_mm, layout)
    steps = layout.steps_in_pass
    pppage = layout.patches_per_page
    total = layout.total_patches
    ppp = pppage // steps if steps else 0

    def px(mm: float) -> int:
        return round(mm * mm2px)

    if px(place.pspa) <= 0 or ppp == 0:
        return []
    out: list[dict] = []
    for page in range(layout.pages):
        first = page * pppage
        last = min(total, first + pppage)
        n_on_page = last - first
        n_passes = (n_on_page + steps - 1) // steps
        for p in range(n_passes):
            global_strip = page * ppp + p
            ncol = min(last, first + (p + 1) * steps) - (first + p * steps)
            x = px(place.x_of(p))
            w = px(place.x_of(p) + place.pwid) - x
            for j in range(ncol - 1):     # a spacer below each patch but the last
                y = px(place.y_of(j)) + px(place.plen)
                out.append({"page": page, "flat": global_strip * steps + j,
                            "x": x, "y": y, "w": w, "h": px(place.pspa)})
    return out


def patches_per_sheet(geom: Geom, paper_w_mm: float, paper_h_mm: float,
                      *, scanc: int = 0) -> int:
    """Max **test** patches that fit on one sheet for *geom* (the calculator).

    Independent of any requested count — uses a large request and reports the
    page capacity (``patches_per_page``).
    """
    return compute(geom, paper_w_mm, paper_h_mm, 100_000, scanc=scanc).patches_per_page


# ---------------------------------------------------------------------------
# Ruler helper markers (#152, Knut)
# ---------------------------------------------------------------------------
def _fill_outward(anchors: list[float], pitch: float, half: float,
                  lo: float, hi: float) -> list[float]:
    """*anchors* continued past both ends at the patch *pitch*, clipped to [lo, hi].

    Knut: *"The rest of the top and bottom edges are then filled with these
    markers till they reach the left and right edges, using the same distance
    between them."* So the spacing outside the patch area is the one the patches
    themselves defined, and the pattern simply continues.

    **The step outside is the pitch, not half the patch** (Knut, 2026-08-14:
    *"You have to dynamically include the spacers as part of the calculation, as
    the spacers can change in the create chart settings."*). One patch of the
    printed rhythm is *start → middle → next start*, and with a spacer in
    between those two gaps are NOT equal: the middle sits ``half`` after the
    start, the next start a full ``pitch`` after it. Repeating a single average
    step drifted against the patches as soon as a spacer was switched on — the
    further from the patch area, the worse. So the whole two-mark pattern is
    tiled at the pitch instead, which stays in step with the patches for any
    spacer width, including zero.

    *anchors* themselves are left exactly as measured, so a layout whose spacers
    are not uniform (edge spacers, an override on one strip) is still precise
    where the patches actually are; only the empty margins beyond them are
    filled with the repeating pattern.
    """
    if not anchors:
        return []
    if pitch <= 0:
        return [a for a in anchors if lo <= a <= hi]
    out = [a for a in anchors if lo <= a <= hi]
    first, last = min(anchors), max(anchors)
    # Below the patch area: keep stepping the pattern down from the first mark.
    base = first - pitch
    while base + half >= lo:
        for v in (base, base + half):
            if lo <= v <= hi:
                out.append(v)
        base -= pitch
    # Above it: the same pattern continuing on from the last mark. `last` is the
    # END of the final patch, which a spacer separates from the next start — so
    # step up from the FIRST start in whole pitches, which is where the next
    # patch would have begun had the page been taller.
    base = first
    while base <= last:
        base += pitch
    while base <= hi:
        for v in (base, base + half):
            if lo <= v <= hi:
                out.append(v)
        base += pitch
    return sorted(set(round(v, 4) for v in out))


def helper_marker_lines_mm(geom: Geom, paper_w_mm: float, paper_h_mm: float,
                           layout: Layout, *, edge_mm: float = 1.0,
                           length_mm: float = 3.0
                           ) -> "list[tuple[float, float, float, float]]":
    """Short dashes along all four page edges, to align a ruler against (#152).

    Returns ``(x0, y0, x1, y1)`` segments in millimetres, for any page size,
    orientation and resolution.

    **Where they sit.** *edge_mm* from the paper edge, *length_mm* long, pointing
    inward — so on A4 portrait with the defaults the left dashes run from x=1 mm
    to x=4 mm, and the right ones from x=206 mm to x=209 mm.

    **What they line up with.**

    * top and bottom step **across** the page with the strips: the start and the
      middle of every strip, plus the end of the last one
    * left and right step **down** the page with the patches: the start and the
      middle of every patch, plus the end of the last one

    Within the patch area the positions are exact, so a spacer between patches
    cannot make them drift. Beyond it the same pattern continues at the pitch
    the patches defined — **spacer included** — out to the page edges. Knut,
    2026-08-14: *"You have to dynamically include the spacers as part of the
    calculation, as the spacers can change in the create chart settings."*
    Nothing here hard-codes a spacer width: the pitch is read back off the
    layout, so whatever Create Chart is set to is what the markers follow.

    **The ColorMunki's staggered strips take the first strip as their
    reference**, which is Knut's ruling (#152): *"the offset strip is always half
    a patch height offset, thus the markers land the correct place if you just
    use the first strip as the reference … Then the whole left and right edge
    with markers will be placed correctly."*

    Hexagonal SpectroScan charts return no markers at all: a honeycomb has no
    rows to line a ruler up with.

    Markers may cross a margin label or the clip-border text. That is accepted —
    Knut, on whether they should ever be skipped to avoid a collision:
    *"overlapping is acceptable. User must adapt settings for the markers,
    margins and clip-border text etc. to look as desired."* Suppressing a marker
    would leave a gap in the very rhythm a ruler is being lined up against,
    which is worse than an overlap the user can move out of the way.
    """
    if getattr(geom, "key", "") == "SS" and getattr(geom, "hxew", 0.0) > 0:
        return []
    if paper_w_mm <= 0 or paper_h_mm <= 0 or length_mm <= 0:
        return []
    edge = max(0.0, float(edge_mm))
    ln = float(length_mm)
    if edge + ln > min(paper_w_mm, paper_h_mm) / 2:
        return []                      # would meet in the middle of the sheet

    place = placement(geom, paper_w_mm, paper_h_mm, layout)
    steps = max(1, layout.steps_in_pass)
    # Passes ACROSS the page, which is not `strips_per_page` (that is 1 for the
    # strip-reader instruments). The renderer derives a patch's pass with
    # `wp // steps` over the patches on the page, so the column count is the
    # same division — see patch_rects_px.
    passes = max(1, layout.patches_per_page // steps)

    # Columns: the start and middle of each strip, plus the last strip's end.
    xs: list[float] = []
    for p in range(passes):
        x = place.x_of(p)
        xs.append(x)
        xs.append(x + place.pwid / 2.0)
    xs.append(place.x_of(passes - 1) + place.pwid)
    # The pitch is measured off the layout itself, so a spacer the user adds in
    # Create Chart moves the fill with it (Knut, 2026-08-14). One strip on the
    # page has no pitch to measure — its own width is then the only rhythm there
    # is, and there is nothing for a spacer to sit between anyway.
    x_pitch = (place.x_of(1) - place.x_of(0)) if passes > 1 else place.pwid
    xs = _fill_outward(xs, x_pitch, place.pwid / 2.0, 0.0, paper_w_mm)

    # Rows: the start and middle of each patch of the FIRST strip, plus the last
    # patch's end. Exact even when a spacer sits between patches.
    ys: list[float] = []
    for j in range(steps):
        y = place.y_of(j)
        ys.append(y)
        ys.append(y + place.plen / 2.0)
    ys.append(place.y_of(steps - 1) + place.plen)
    y_pitch = (place.y_of(1) - place.y_of(0)) if steps > 1 else place.plen
    ys = _fill_outward(ys, y_pitch, place.plen / 2.0, 0.0, paper_h_mm)

    lines: list[tuple[float, float, float, float]] = []
    for x in xs:                        # top and bottom: vertical dashes
        lines.append((x, edge, x, edge + ln))
        lines.append((x, paper_h_mm - edge - ln, x, paper_h_mm - edge))
    for y in ys:                        # left and right: horizontal dashes
        lines.append((edge, y, edge + ln, y))
        lines.append((paper_w_mm - edge - ln, y, paper_w_mm - edge, y))
    return lines
