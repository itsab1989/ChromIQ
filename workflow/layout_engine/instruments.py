"""Per-instrument chart geometry, reverse-engineered from ArgyllCMS ``printtarg.c``.

Every constant here was read from ``target/printtarg.c`` (v3.5.0) and then
**verified** against a live ``printtarg`` option matrix: for a 60-patch RGB
``.ti1`` on A4 these reproduce printtarg's reported ``STEPS_IN_PASS`` /
``PASSES_IN_STRIPS2`` / padded patch count exactly (i1 21×3→63, p3 9×7,
ColorMunki 15×4→60, DTP41 25×3→75, DTP51 19×4→76, SpectroScan 39×2,
SpectroScan hex 45×2, A4-landscape 16×4).

A :class:`Geom` carries every value :func:`workflow.layout_engine.geometry`
needs.  Values that depend on patch scale (``-a``), spacer scale (``-A``),
high-density / hex (``-h``), spacers on/off (``-n``), the page margin (``-m``)
or the left clip border (``-L``) are resolved in :func:`build`.

All lengths are millimetres.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace

MAXPPROW = 500          # printtarg.c: absolute max patches per pass/row
MAXROWLEN = 5000.0      # printtarg.c MAXROWLEN — large enough to never bind for sheet sizes

# ---- CR30 physical dimensions, for the Measure tab's aiming help ------------
#
# SOURCED, not assumed -- but NOT equally well sourced, and the difference is
# recorded here rather than smoothed over. Both figures come from CHNSpec's own
# CR-series brochure (the URL is in the manufacturer-contact draft). Only the
# APERTURE has a second, independent source: the owner's own measurement of his
# unit (chromiq-cr30-research, EXPERIMENTS.md, EXP-018). The BODY diameter rests
# on the brochure alone -- "33 mm" appears nowhere in the research repo -- and a
# commit message of mine claimed otherwise. Measure a real unit and this comment
# improves.
#
#     Measure Aperture   4 mm
#     Body               Ø33 mm x 84 mm
#
# ⚠ The 4.45 mm that appears in `docs/cr30_reports/02-design.md` is NOT a rival
# aperture figure. It is the inscribed circle of a hexagonal patch of equal
# area — a CLEARANCE, i.e. how much room a 4 mm aperture has inside that shape.
#
# The aperture is CENTRED in the body. Confirmed by Basti on his own unit,
# 2026-08-30 -- which matters because the overlay draws the two circles
# concentric, and the technique it exists to support ("place it so the same
# neighbours are evenly covered") is only sound if they are. It was an
# assumption until he checked; it is a fact now.
#
# These are drawn ON SCREEN AT SCALE, so they are a factual claim about the
# instrument: change them only against a better source, and say which.
#: Width (mm) of the band reserved to the LEFT of the patch block for the row
#: NUMBERS that `raster.py` draws there. 7.5 mm is the SpectroScan's own value,
#: kept because it is a measured fit for two digits at the instrument text
#: height; every instrument that switches the band on gets the same width.
ROW_LABEL_BAND_MM = 7.5

CR30_BODY_DIAMETER_MM = 33.0
CR30_APERTURE_DIAMETER_MM = 4.0

# Instrument flag (printtarg -i value) -> CGATS TARGET_INSTRUMENT string.
TARGET_INSTRUMENT_NAME: dict[str, str] = {
    "i1": "GretagMacbeth i1 Pro",
    "p3": "GretagMacbeth i1 Pro",      # printtarg stamps the 3+ the same way
    "CM": "X-Rite ColorMunki",
    "41": "X-Rite DTP41",
    "51": "X-Rite DTP51",
    "SS": "GretagMacbeth SpectroScan",
    # ChnSpec CR30 (#159). The HONEST name, by ruling: the device reports "CR30"
    # for itself, so that is what the chart says it is. Consequence, stated here
    # because it is load-bearing: stock ArgyllCMS `chartread` matches
    # TARGET_INSTRUMENT against its own instrument table and will REFUSE a chart
    # named "CR30". A CR30 chart is readable only by ChromIQ's own chartread
    # fork. The UI must say so at chart creation and at measure time.
    "CR30": "CR30",
}

# Instruments ChromIQ never lays out itself (delegated to i1Profiler).
DELEGATED = {"isis"}

def _inch(mm: float) -> float:
    return mm * 25.4


@dataclass(frozen=True)
class Geom:
    """Resolved geometry for one (instrument, scale, spacer, margin) combo."""
    key: str
    plen: float          # patch length along a pass (mm)
    pspa: float          # inter-patch spacer (mm); 0 if spacers off
    tspa: float          # trailer clear space after last patch (mm)
    pwid: float          # patch width (mm)
    rrsp: float          # row-centre to row-centre spacing (mm)
    lspa: float          # leader space before first patch (mm)
    lcar: float          # leading clear area (mm)
    txhisl: float        # strip/column label text height (mm)
    pglth: float         # page-label text height (mm)
    border: float        # base page margin (-m), mm — drives leader/clip-holder
    lbord: float         # extra left clip border (mm); 0 if suppressed (-L) / N/A
    hxeh: float          # hex/stagger extra height (mm)
    hxew: float          # hex extra width (mm)
    clwi: float          # cut-line width (mm)
    rlwi: float          # row-label width (mm)
    mxpprow: int         # max patches per pass
    mxrowl: float        # max pass length (mm)
    rpstrip: int         # rows per whole strip
    nextrap: int         # extra max/min/SID patches per pass (not test patches)
    dorspace: bool       # gutter between rows by rrsp (vs touching)
    dopglabel: bool      # reserve a per-page label column
    padlrow: bool        # pad the final pass up to full length
    target_name: str     # CGATS TARGET_INSTRUMENT
    has_clip_border: bool # whether this instrument supports a left clip border

    # Instrument-specific extra .ti2 keywords (e.g. DTP41 lengths, SS hex flag).
    extra_keywords: tuple[tuple[str, str], ...] = ()

    # Independent page-edge margins (ChromIQ extension); default to `border`
    # via build(); the 6.0 fallback only applies to bare _build_base() Geoms.
    margin_t: float = 6.0
    margin_r: float = 6.0
    margin_b: float = 6.0
    margin_l: float = 6.0
    # §R1.3's floor for the ROW labels: how close to the left page edge they
    # may come. Computed with the band in `raster.apply_row_label_geometry`
    # and carried here so the RENDERER can clamp at the same number — its
    # clamp used to be the page edge, which is what let a three-digit label
    # print 1.4 mm from the paper's edge against a 4 mm limit. 0 = not set.
    row_label_floor: float = 0.0
    strip_indicator_gap: float = 0.0   # gap (mm) between strip label and strip
    offset_x: float = 0.0              # whole-chart offset (mm)
    offset_y: float = 0.0
    # Rendered-furniture reservations (mm), filled in from the recipe + fonts by
    # raster.apply_furniture_reserves() so capacity reflects what's actually
    # drawn. label_band_mm < 0 ⇒ "not computed" → fall back to the instrument
    # label height (txhisl); 0 ⇒ no label at all (indicators off → reclaim the
    # band). bottom_reserve_mm 0 ⇒ no bottom furniture. A bare build() Geom keeps
    # the sentinel so it behaves exactly as before. (#93)
    label_band_mm: float = -1.0   # actual strip-label + underline band height
    bottom_reserve_mm: float = 0.0   # actual bottom sheet-text + stamp height
    # Bracket each strip with a leading + trailing spacer (printtarg parity).
    # When OFF the two end gaps are reclaimed for patches (denser than printtarg).
    edge_spacers: bool = False
    # Where the patch block sits within the usable area (#93). One of
    # "{top,center,bottom}-{left,center,right}" (the middle is plain "center").
    # Default "center-left" reproduces the prior behaviour (vertically centred in
    # the free span, left-anchored). Render-only — capacity is unchanged.
    patch_area_align: str = "center-left"
    # Which page edge the clip border / notes band sits on, "left" or "right"
    # (#93, Knut). The reserved width (lbord) is the same either side, so this
    # only moves the band + shifts the patch block to the other edge — capacity
    # is unchanged.
    clip_side: str = "left"
    # ColorMunki "offset every second strip" (printtarg's rig stagger): shift each
    # odd strip down the page by this much (mm) so the columns interleave like a
    # brick wall (#93, Knut). 0 = no stagger. Render + patch_rects honour it; the
    # hxeh reservation makes room so capacity reflects it.
    row_stagger_mm: float = 0.0
    # Minimum distance (mm) from the PAPER EDGE to the start of text on that side
    # (Knut #93): strip labels (top) and the clip/notes band (clip side) sit this
    # far in from the edge. Independent of the margins; if a margin is too small
    # for the text it overflows toward this line and a violation is flagged.
    text_edge_top_mm: float = 4.0
    text_edge_clip_mm: float = 4.0
    # "Margins are the law" mode (Knut): the patch area is exactly the margin box
    # (no hidden leader/trailer; strip labels live inside the top margin, anchored
    # at the text-edge from the page edge). ON for area-first ("Prioritise chart
    # area…") AND whenever "Use instrument margins" is on — in both cases the
    # margin (e.g. the i1Pro 38 mm minimum) is the whole top furniture zone, so the
    # label band + leader must NOT be reserved on top of it (that double-count
    # pushed patches ~17 mm too far down and pinned labels at the margin — Knut).
    # OFF only for patch-first with user margins (the historical printtarg-style
    # engine). Set in geom_from_build_kwargs.
    margins_are_law: bool = False
    # Fill the margin box even past the instrument's ruler cap (area-first only:
    # the box is the law and a too-long strip is flagged, not shrunk). Patch-first
    # ALWAYS honours the ruler cap, even under margins_are_law, so its "max strip
    # length" still protects the i1Pro jig. Decoupled from margins_are_law (Knut).
    fill_beyond_ruler: bool = False
    # THE chart is a honeycomb. Set by whichever _build_base branch builds
    # hexagons; the SINGLE source of truth for "am I drawing a hexagon", used by
    # the renderer, the recorded patch rects and the ruler helper markers.
    #
    # It exists because those three used to ask `key == "SS"` separately. When
    # the CR30 gained the same option (#159) all three silently kept saying SS,
    # so a CR30 honeycomb reserved the apex overhang, shortened its rows to make
    # room — and was then drawn as squares. The failure was invisible: the sheet
    # paid for hexagons and did not get them. A capability the geometry states
    # about itself cannot be half-registered that way, and any instrument can
    # now offer hexagons simply by building a Geom with this set (Basti,
    # 2026-08-28: "we own the layout engine, so you should be able to add the
    # hex patches to any instrument we want").
    #
    # NOT inferred from hxeh/hxew: the ColorMunki's row stagger sets hxeh
    # without being hexagonal, so those floats answer a different question.
    hexagonal: bool = False
    # Physical strip-length limit of the instrument's ruler/jig (mm); 0 = none
    # (ColorMunki/SpectroScan have no ruler). In area-first the strip is NOT capped
    # to this (the margin box is law — fill it), but a strip longer than the ruler
    # is flagged as a violation so the user knows it won't fit their jig (Knut #93).
    ruler_mm: float = 0.0


def is_hexagonal(geom) -> bool:
    """Whether *geom* is laid out with hexagonal patches — THE single test.

    Reads :attr:`Geom.hexagonal`, which the building branch sets about itself.
    Every gate that behaves differently on a honeycomb must come through here:
    the renderer, the recorded patch rects and the ruler helper markers. They
    disagreeing is not a visible bug, it is a half-patch mis-registration
    between what is drawn and what the app believes it drew.
    """
    return bool(getattr(geom, "hexagonal", False))


def hex_capable(key: str) -> bool:
    """Whether *key* can be laid out with hexagonal patches.

    ASKED OF THE GEOMETRY, not held in a list: an instrument offers hexagons
    exactly when its ``_build_base`` branch honours ``hflag``, so adding the
    shape to a new instrument needs no second registration anywhere and cannot
    be half-done. Anything unbuildable is simply not hex-capable.
    """
    try:
        return bool(build(key, hflag=True).hexagonal)
    except Exception:      # noqa: BLE001 — an unknown key is not a capability
        return False


def hex_capable_instruments() -> "list[str]":
    """Every supported instrument that can be laid out as a honeycomb."""
    return [k for k in supported() if hex_capable(k)]


def supported() -> list[str]:
    return ["i1", "p3", "CM", "41", "51", "SS", "CR30"]


def default_ruler_mm(key: str) -> float:
    """The instrument's built-in strip-length limit (ruler / jig), in mm, or
    0.0 when it has none (ColorMunki and SpectroScan read without a ruler).

    Derived from the engine's own geometry so the Settings display can never
    drift from what the layout actually enforces (Knut). ``key`` is a device
    key (``i1``/``p3``/``CM``/``SS``/…) or a friendly Settings label.
    """
    key = _MARGIN_LABEL_TO_KEY.get(key, key)
    try:
        g = build(key)
    except Exception:
        return 0.0
    return round(float(getattr(g, "ruler_mm", 0.0) or 0.0), 0)


# Friendly Settings labels → device keys.
_MARGIN_LABEL_TO_KEY = {
    "i1Pro": "i1", "i1Pro 3+": "p3", "ColorMunki": "CM", "SpectroScan": "SS",
    "CR30": "CR30",   # friendly label == device key (#159)
}


def build(
    key: str,
    *,
    pscale: float = 1.0,
    sscale: float = 1.0,
    hflag: bool = False,
    density: int = 1,
    spacer_on: bool = True,
    border: float = 6.0,
    margins: tuple[float, float, float, float] | None = None,
    patch_w: float | None = None,
    patch_h: float | None = None,
    spacer_width: float | None = None,
    inter_patch: float | None = None,
    strip_gap: float | None = None,
    max_strip: float | None = None,
    strip_indicator_gap: float | None = None,
    row_indicators: bool | None = None,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
    nolpcbord: bool = False,
    nolimit: bool = False,
    clip_border_width: float = 26.0,
    clip_band: float = 0.0,
    edge_spacers: bool = False,
    patch_area_align: str = "center-left",
    clip_side: str = "left",
    cm_stagger: bool = False,
    text_edge_top: float = 4.0,
    text_edge_clip: float = 4.0,
    margins_are_law: bool = False,
    fill_beyond_ruler: bool = False,
) -> Geom:
    """Resolve :class:`Geom`, applying ChromIQ extensions over the base geometry.

    *margins* = independent ``(top, right, bottom, left)`` page margins in mm
    (default: all = *border*).  *patch_w* / *patch_h* override the patch size in
    mm.  *spacer_width* overrides the inter-patch spacer thickness; *inter_patch*
    adds extra gap between patches; *max_strip* caps the pass length (mm);
    *strip_indicator_gap* is the gap (mm) between the strip label and its strip.
    ``border`` still drives the instrument leader and clip-holder base.
    """
    geom = _build_base(
        key, pscale=pscale, sscale=sscale, hflag=hflag, density=density,
        spacer_on=spacer_on, border=border, nolpcbord=nolpcbord, nolimit=nolimit,
        clip_border_width=clip_border_width, clip_band=clip_band)
    mt, mr, mb, ml = margins if margins else (geom.border,) * 4
    plen, pwid, rrsp = geom.plen, geom.pwid, geom.rrsp
    if patch_h:
        plen = float(patch_h)
    if patch_w:
        ratio = (geom.rrsp / geom.pwid) if geom.pwid else 1.0
        pwid = float(patch_w)
        rrsp = pwid * ratio
    if strip_gap:                       # extra gutter between strips (adds to pitch)
        rrsp += float(strip_gap)
    pspa = geom.pspa
    if spacer_width is not None and geom.pspa > 0:   # only when spacers are on
        pspa = float(spacer_width)
    if inter_patch:
        pspa += float(inter_patch)
    mxrowl = float(max_strip) if max_strip else geom.mxrowl
    sig = geom.strip_indicator_gap if strip_indicator_gap is None \
        else float(strip_indicator_gap)
    # ROW NUMBERS DOWN THE LEFT — the band, and who decides it is there.
    #
    # `rlwi > 0` is the whole switch: raster.py draws a row number against the
    # leftmost strip of each page only where the band is reserved. Until
    # 2026-08-30 that was decided by the instrument alone (7.5 mm for SS and
    # CR30, 0 everywhere else), so the most useful piece of furniture on the
    # sheet — a 2-D A1/B2 coordinate for finding one patch among hundreds — was
    # reachable only by owning one of two devices. Knut asked for it on any
    # chart that wants it.
    #
    # THREE STATES, and None is the one that matters: it means "whatever this
    # instrument has always done", so every recipe written before this existed
    # renders byte-identically. An explicit True/False is a person's answer.
    rlwi = geom.rlwi
    if row_indicators is True:
        rlwi = rlwi or ROW_LABEL_BAND_MM
    elif row_indicators is False:
        rlwi = 0.0
    # ColorMunki "offset every second strip": shift odd strips down by half a
    # patch (printtarg's rig stagger = 0.5·(plen + ½·spacer)) and reserve hxeh =
    # ¼·plen so the overhang stays on the page. Decoupled from density (#93, Knut).
    hxeh = geom.hxeh
    hxew = geom.hxew
    # THE HEX OVERHANG FOLLOWS THE PATCH SIZE.
    #
    # A SpectroScan hexagon pokes plen/6 past its slot top and bottom and ¼·pwid
    # past its sides, and the layout reserves exactly that as hxeh/hxew. Both
    # were computed by `_build_base` from `pscale` and then never revisited when
    # `patch_w`/`patch_h` set the size directly — and hxew was not even passed
    # through the `replace()` below. So a 20 mm hexagon still reserved the 7 mm
    # geometry's 1.75 mm, overhung it by 5 mm, and printed past the margin. Both
    # the Manual patch-size boxes and the area-first grid take this path (#159).
    # Every honeycomb, whichever instrument built it (#159): a resized hexagon
    # that kept its unresized reservation is exactly the bug this block was
    # written for, and it does not care which device is reading the sheet.
    if geom.hexagonal and (patch_w or patch_h):
        hxeh = plen / 6.0
        hxew = 0.25 * pwid
    row_stagger = 0.0
    if key == "CM" and cm_stagger:
        row_stagger = 0.5 * (plen + 0.5 * pspa)
        hxeh = 0.25 * plen
    # Clip / notes band lives INSIDE the clip-side margin (Knut beta-13): raise
    # that margin to at least the clip-border width so the band fits and the patch
    # area starts at the (possibly bumped) margin — no additive double-count. This
    # keeps printtarg parity for the default clip (border + lbord == clip width)
    # while a larger user margin still pushes the patches further in.
    if geom.lbord > 0:
        clip_w = geom.lbord + geom.border
        if (clip_side or "left") == "right":
            mr = max(mr, clip_w)
        else:
            ml = max(ml, clip_w)
    return replace(geom, margin_t=mt, margin_r=mr, margin_b=mb, margin_l=ml,
                   plen=plen, pwid=pwid, rrsp=rrsp, pspa=pspa, mxrowl=mxrowl,
                   hxeh=hxeh, hxew=hxew, row_stagger_mm=row_stagger,
                   strip_indicator_gap=sig, rlwi=rlwi,
                   offset_x=offset_x, offset_y=offset_y,
                   edge_spacers=edge_spacers,
                   patch_area_align=patch_area_align or "center-left",
                   clip_side=clip_side or "left",
                   text_edge_top_mm=float(text_edge_top or 4.0),
                   text_edge_clip_mm=float(text_edge_clip or 4.0),
                   margins_are_law=bool(margins_are_law),
                   fill_beyond_ruler=bool(fill_beyond_ruler))


# Keys of a recipe ``build_kwargs()`` dict that affect the laid-out geometry —
# i.e. every option that can change how many patches fit a page (capacity) or
# where they sit (placement). Keep in lockstep with build()'s keyword args: a
# missing key silently makes capacity ESTIMATES disagree with the actual render
# (clip_border_width once did exactly that — #93). This is the single source of
# truth shared by every capacity calculation.
GEOM_BUILD_KEYS = (
    "hflag", "density", "spacer_on", "pscale", "sscale", "border", "margins",
    "patch_w", "patch_h", "spacer_width", "inter_patch", "strip_gap", "max_strip",
    "strip_indicator_gap", "row_indicators", "offset_x", "offset_y",
    "nolpcbord", "nolimit",
    "clip_border_width", "clip_band", "edge_spacers", "patch_area_align",
    "clip_side", "cm_stagger", "text_edge_top", "text_edge_clip",
)


def geom_from_build_kwargs(kw: dict, thresholds: dict | None = None) -> Geom:
    """Build a :class:`Geom` from a recipe ``build_kwargs()`` dict using every
    geometry-affecting key, so capacity estimates can never silently drift from
    the actual render (#93). Rendered-furniture reservations (label band, bottom
    sheet text / stamp) are applied too — the same step the renderer uses.

    When *thresholds* (a ``{"L","R","T","B": mm}`` minimum-margin dict) is given,
    the page margins are first raised so the realised patch area meets those
    minimums — so both the capacity estimate and the render honour the user's
    margin thresholds from this one chokepoint (#93)."""
    # CM/SS/CR30 have no native clip border, but can still carry a notes/clip
    # band when clip content is on — reserve that band so capacity reflects it
    # (#93). CR30 joined this tuple in #159: the design says its clip band is
    # "off by default, OFFERABLE", and without an entry here the band was
    # silently inert (lbord 0.0, has_clip_border False) while the UI offered it.
    # A CR30 sheet is hand-read for up to half an hour, so a notes band naming
    # the run is worth more here than on any strip chart, not less.
    if (kw.get("instrument") in ("CM", "SS", "CR30")
            and kw.get("clip_content_mode", "off") not in ("off", None)
            and not kw.get("clip_band")):
        kw = {**kw, "clip_band": float(kw.get("clip_border_width") or 26.0)}
    if thresholds:
        from . import margins_fit   # lazy: imports this module
        kw, _notes = margins_fit.clamp_margins_to_thresholds(kw, thresholds)
    # Area-first layout: derive patch_w/patch_h from the target grid, unless the
    # caller already set explicit sizes. Lazy import (it builds geoms via us).
    if kw.get("layout_mode") == "area_first" and not (kw.get("patch_w")
                                                      or kw.get("patch_h")):
        from . import area_fit
        _sz = area_fit.derive_area_patch_size(kw)
        if _sz is not None:
            kw = {**kw, "patch_w": _sz[0], "patch_h": _sz[1]}
    # "Margins are the law" (margin box = exact patch area, labels inside the top
    # margin at the text-edge) applies for area-first AND whenever "Use instrument
    # margins" is on: the instrument margin already IS the whole top furniture zone,
    # so reserving the label band + leader on top of it double-counts and pushes the
    # patches down while pinning labels at the margin (Knut). The ruler cap, though,
    # must still bind in patch-first even under margins_are_law — only area-first
    # fills past the ruler (and warns), so that stays keyed on the layout mode.
    # AN UNTOUCHED BOX FOLLOWS THE STRIP LETTERS, and the derivation lives
    # HERE rather than in the recipe so that saving and reloading cannot turn
    # "this instrument's own behaviour" into an explicit "no". Only the
    # untouched state is derived; an explicit True still prints row labels
    # with the letters off, which is what that combination is for.
    if kw.get("row_indicators") is None and not kw.get("draw_indicators", True):
        kw = {**kw, "row_indicators": False}
    area_first = (kw.get("layout_mode") == "area_first")
    law = area_first or bool(kw.get("use_instrument_margins"))
    geom = build(kw["instrument"], margins_are_law=law, fill_beyond_ruler=area_first,
                 **{k: v for k, v in kw.items() if k in GEOM_BUILD_KEYS})
    from . import raster   # lazy: raster imports this module
    return raster.apply_furniture_reserves(geom, kw)


def _build_base(
    key: str,
    *,
    pscale: float = 1.0,
    sscale: float = 1.0,
    hflag: bool = False,
    density: int = 1,
    spacer_on: bool = True,
    border: float = 6.0,
    nolpcbord: bool = False,
    nolimit: bool = False,
    clip_border_width: float = 26.0,
    clip_band: float = 0.0,
) -> Geom:
    """Resolve :class:`Geom` for *key* with the given options.

    *pscale* = printtarg ``-a`` (patch+spacer scale), *sscale* = ``-A`` (spacer
    scale), *hflag* = ``-h`` (SpectroScan hex), *spacer_on* False = ``-n``,
    *border* = ``-m`` margin, *nolpcbord* True = ``-L``, *nolimit* True = ``-P``.

    *density* (ColorMunki only) is the row-density level: 1 = normal hand-held,
    2 = high (the rig — printtarg ``-h``, exact), 3 = extra-high (a ChromIQ
    extension beyond printtarg's single level; tighter rows pending hardware
    validation, guarded by the 6 mm reliability floor).
    """
    if key == "CM" and hflag and density < 2:
        density = 2   # back-compat: hflag meant "rig" (double density)
    if key in DELEGATED:
        raise ValueError(f"instrument {key!r} is delegated to i1Profiler, not laid out here")
    if key not in TARGET_INSTRUMENT_NAME:
        raise ValueError(f"unknown instrument {key!r}")

    name = TARGET_INSTRUMENT_NAME[key]

    def spacer(base: float) -> float:
        return pscale * sscale * base if spacer_on else 0.0

    # ---- i1Pro family (5 mm and 8 mm apertures) -------------------------
    if key in ("i1", "p3"):
        clip_w = clip_border_width if clip_border_width else 26.0
        lbord = max(0.0, clip_w - border) if not nolpcbord else 0.0
        if key == "i1":                       # 5 mm aperture
            lcar, plen_b, pspa_b, tspa = 10.0, 10.0, 1.0, 10.0
            pwid_b = rrsp_b = 8.0
        else:                                 # p3 = i1Pro 3+ / 8 mm aperture
            lcar, plen_b, pspa_b, tspa = 20.0, 20.0, 2.0, 20.0
            pwid_b = rrsp_b = 16.0
        txhisl = 7.0
        mxrowl = MAXROWLEN if nolimit else (260.0 - lcar - tspa)
        return Geom(
            key=key, plen=pscale * plen_b, pspa=spacer(pspa_b), tspa=tspa,
            pwid=pscale * pwid_b, rrsp=pscale * rrsp_b,
            lspa=border + txhisl + lcar, lcar=lcar, txhisl=txhisl, pglth=5.0,
            border=border, lbord=lbord, hxeh=0.0, hxew=0.0, clwi=0.0, rlwi=0.0,
            mxpprow=MAXPPROW, mxrowl=mxrowl, rpstrip=999, nextrap=0,
            dorspace=False, dopglabel=False,   # page-label column reclaimed (#93)
            padlrow=True, target_name=name,
            has_clip_border=True, ruler_mm=(260.0 - lcar - tspa),
        )

    # Optional notes band for instruments without a native clip border (CM/SS):
    # reserve the same total zone from the edge as the i1Pro clip (#93, Knut).
    _band = max(0.0, clip_band - border) if clip_band > 0 else 0.0

    # ---- X-Rite ColorMunki ---------------------------------------------
    if key == "CM":
        # Extra-high density = a DENSE ColorMunki strip layout with small, still-
        # readable patches. printtarg could only fake this by laying out an i1Pro
        # chart and relabelling the .ti2 — it can't make ColorMunki patches this
        # small. Our engine can, so we define it natively as a ColorMunki geometry
        # (no i1 borrow, #93, Knut): ~10.4 mm patches in 13 mm steps — the same
        # readable size the old i1-trick produced, but ours. It's a fixed maximum-
        # density mode, so the patch size is INDEPENDENT of the patch scale (the
        # "auto" size is the same in Guided and Manual → both fill to the same
        # count); set an explicit patch_w/patch_h to override.
        if density >= 3:
            # Extra-high density = the engine's native dense ColorMunki strip.
            # At the native scale (pscale == 1.0) a patch is 10.4 x 13.0 mm — the
            # readable size printtarg's -ii1 triple-density trick produces at its
            # -a1.3 default. pscale grows/shrinks it from there so a preset can
            # pack denser (the caller converts a printtarg -a to this engine
            # scale: pscale = -a / 1.3; see chart_creator). Only the patch
            # dimensions scale — the spacer and furniture stay fixed, matching
            # printtarg -a (which scales patches, not the -A spacer).
            plen = pscale * 13.0
            pwid = rrsp = pscale * 10.4
            # ColorMunki has no i1-style ruler, so a strip is never length-capped
            # (matches the other CM densities) — the user pointed out a cap is
            # never needed here, so the page height is the only limit.
            txhisl, lcar, tspa = 7.0, 10.0, 10.0
            # The spacer scales with the patch (printtarg's -a scales both), so a
            # denser preset keeps printtarg's proportions; the leader/trailer/
            # text furniture is fixed, as in the i1 layout. Native (pscale 1.0)
            # is 1.3 mm = the i1 spacer at printtarg's -a1.3 default.
            pspa_e = pscale * 1.3
            return Geom(
                key=key, plen=plen, pspa=(pspa_e if spacer_on else 0.0), tspa=tspa,
                pwid=pwid, rrsp=rrsp,
                lspa=border + txhisl + lcar, lcar=lcar, txhisl=txhisl, pglth=5.0,
                border=border, lbord=_band, hxeh=0.0, hxew=0.0, clwi=0.0, rlwi=0.0,
                mxpprow=MAXPPROW, mxrowl=MAXROWLEN, rpstrip=999, nextrap=0,
                dorspace=False, dopglabel=False,   # page-label column reclaimed
                padlrow=True, target_name=name, has_clip_border=_band > 0,
            )
        plen = pscale * 14.0
        if density >= 2:                      # high density (rig) — tighter rows
            # Level 2 = printtarg's exact rig spacing (13.7 mm).
            pwid = rrsp = pscale * 13.7
        else:                                 # normal hand-held
            pwid = rrsp = pscale * 28.0
        # The strip stagger (and its hxeh reservation) is now a separate option
        # (cm_stagger), applied in build() — not tied to density (#93, Knut).
        hxeh = 0.0
        txhisl, lcar = 7.0, 20.0
        return Geom(
            key=key, plen=plen, pspa=spacer(1.0), tspa=25.0, pwid=pwid, rrsp=rrsp,
            lspa=border + 7.0 + 20.0, lcar=lcar, txhisl=txhisl, pglth=5.0,
            border=border, lbord=_band, hxeh=hxeh, hxew=0.0, clwi=0.0, rlwi=0.0,
            mxpprow=MAXPPROW, mxrowl=MAXROWLEN, rpstrip=999, nextrap=0,
            dorspace=False, dopglabel=False,   # page-label column reclaimed (#93)
            padlrow=True, target_name=name,
            has_clip_border=_band > 0,
        )

    # ---- GretagMacbeth SpectroScan (flatbed) ---------------------------
    if key == "SS":
        if hflag:                             # hexagon patches
            plen = pscale * math.sqrt(0.75) * 7.0
            hxeh = (1.0 / 6.0) * plen
            hxew = pscale * 0.25 * 7.0
        else:
            plen = pscale * 7.0
            hxeh = hxew = 0.0
        extra = (("HEXAGON_PATCHES", "True"),) if hflag else ()
        return Geom(
            key=key, plen=plen, pspa=0.0, tspa=0.0, pwid=pscale * 7.0, rrsp=pscale * 7.0,
            lspa=border + 7.0, lcar=0.0, txhisl=5.0, pglth=5.0,
            border=border, lbord=_band, hxeh=hxeh, hxew=hxew, clwi=0.0, rlwi=ROW_LABEL_BAND_MM,
            mxpprow=MAXPPROW, mxrowl=MAXROWLEN, rpstrip=999, nextrap=0,
            dorspace=False, dopglabel=False,   # page-label column reclaimed (#93)
            padlrow=False, target_name=name,
            has_clip_border=_band > 0, extra_keywords=extra,
            hexagonal=bool(hflag),
        )

    # ---- ChnSpec CR30 (hand-placed spot colorimeter) --------------------
    if key == "CR30":
        # A CR30 is placed on ONE patch at a time by hand and triggered by its
        # own button. It never traverses a strip, so every piece of strip
        # furniture below is deliberately zero — but a spot grid is NOT the
        # SpectroScan's grid, and the differences are the whole point of this
        # branch existing instead of an `key in ("SS", "CR30")` alias.
        #
        # Every field, and why:
        #
        # plen / pwid / rrsp = 12 mm square, PROVISIONAL (Basti, 2026-08-28).
        #   Cell size here is set by HAND PLACEMENT UNDER OCCLUSION, not by the
        #   aperture. The CR30's body is a 33 mm OPAQUE disc: the moment it is
        #   set down the patch underneath is invisible, so the user is aiming a
        #   33 mm disc at a target they can no longer see, using the cells
        #   around it. What matters is how far the aim may be off.
        #
        #   12 mm leaves 4.00 mm of clearance all round the 4 mm window, against
        #   3.00 mm at 10 mm. (A hexagon of the same AREA as a 12 mm square
        #   would give 4.45 mm — see the hexagon note below for why this branch
        #   does not use that sizing.)
        #
        #   It also sits ABOVE the only geometry a CR30 has been proven to
        #   read: EXP-SPEC-001a was a ColorMunki extra-high sheet at
        #   10.4 x 13.0 mm (:422-430), 40 patches, 0 misreads. We move away
        #   from the untested edge, not toward it. The minimum was never
        #   measured and will not be, so the safe direction is the generous one.
        #
        #   Capacity stays practical: measured on this branch, A4 patch-first at
        #   the default margins, 345 patches rectangular and 405 hexagonal -
        #   comfortably over the 300-patch working target, at roughly a quarter
        #   of an hour a sheet.
        #
        #   ⚠ NOT a measured minimum, and the UI says so. An earlier version of
        #   this comment claimed 10 mm was "2.5x the aperture, the same
        #   patch:aperture ratio the i1Pro uses". That was WRONG twice over: the
        #   i1Pro's ratio is 10/5 = 2.00 and this one is 12/4 = 3.00, so it was
        #   never a match, and the aperture ratio is not what governs the size
        #   anyway. Removed rather than corrected.
        #
        #   No minimum-patch REFUSAL is enforced for the CR30 (Basti,
        #   2026-08-28: "if no instrument has it now we leave it out and don't
        #   invent something new here"). No instrument models its aperture and
        #   none refuses a size, so a CR30-only floor would be a special case
        #   breaking the rule everywhere else. preflight.MIN_PATCH_MM's 6 mm
        #   warning applies here exactly as it applies to every instrument.
        #
        #   rrsp == pwid, so columns touch: that is the topology of the only
        #   chart a CR30 has been proven to read (EXP-SPEC-001a's columns
        #   touched too).
        #
        # pspa = 1.3 mm, KEPT — the design's "spacers: none" is wrong.
        #   The successful EXP-SPEC-001a read used the CM extra-high geometry,
        #   which sets pspa = pscale * 1.3 (:433). Removing the one geometric
        #   feature present in the only proven layout would be inventing a
        #   geometry, not deriving one. Routed through spacer() so `-n`
        #   (spacer_on False) still turns it off, and so build()'s Manual
        #   "spacer width" box stays live — that box is silently ignored when
        #   pspa == 0 (:218-219), which is what an SS-shaped copy would have
        #   produced.
        #
        # tspa = 0.0, lcar = 0.0 — no run-in, no run-out.
        #   i1 reserves 10 mm and CM 25 mm of clear paper for the instrument to
        #   accelerate onto and off the end of a strip. A hand lifts off. Taken
        #   from SS for the right reason: SS's zeros come from it being a
        #   MOTORISED FLATBED whose head is machine-positioned; ours come from
        #   there being no swipe at all. Same value, different derivation.
        #
        # lspa = border + txhisl — the only thing above the first patch is the
        #   column-label band. (SS uses border + 7.0 against a txhisl of 5.0,
        #   i.e. a 2 mm fudge; we do not copy the fudge.)
        #
        # rlwi = 7.5 — THE reason to take anything from the SpectroScan.
        #   raster.py:1215-1233 draws row NUMBERS down this reserved band, which
        #   together with the column letters gives the sheet a 2-D A1/A2/B1
        #   coordinate. Finding one patch among several hundred, by hand, is the
        #   CR30's entire ergonomic problem; this is the single most useful
        #   piece of furniture on the page and it exists only where rlwi > 0.
        #
        # padlrow = False — do not pad the last column with blank patches. That
        #   exists so a strip reader always traverses a full-length strip; there
        #   is no strip here, and blank patches are paper the user pays for.
        #
        # mxrowl = MAXROWLEN, ruler_mm = 0.0 (default) — no ruler, no jig; the
        #   page is the only limit, as for CM and SS.
        #
        # hxeh/hxew/clwi = 0 — no hexagons, no stagger, no cut lines.
        # rpstrip/nextrap/dorspace/dopglabel — as every non-DTP branch.
        txhisl = 7.0
        # HEXAGONS (-h), offered for the CR30 as for the SpectroScan (Basti,
        # 2026-08-28) - but for a better reason than the SS has. The SS gains
        # only density. The CR30 is a ROUND instrument (33 mm barrel, 4 mm
        # circular aperture), and a round aperture can never reach the corners
        # of a square patch, so on a square grid that paper is spent. Hexagonal
        # cells are the densest packing of equal circles in a plane: 90.69 % of
        # the sheet within reach of a circle against 78.54 % for squares
        # (pi/(2*sqrt(3)) vs pi/4 - computed, not quoted).
        #
        # ⚠ SIZING, and the claim it does or does not support. This branch
        # mirrors the SS one at EQUAL WIDTH ACROSS THE FLATS: the hexagon is
        # 12 mm wide exactly as the square is, so its inradius is 6.000 mm -
        # IDENTICAL to the square's, i.e. the same 4.00 mm clearance round the
        # window - and its area is 124.7 mm² against the square's 144.
        # Measured on A4, patch-first: 345 patches rectangular, 405 hexagonal
        # (+17 %).
        #
        # So at this sizing the honeycomb buys DENSITY at unchanged aperture
        # clearance, plus whatever the six guiding edges are worth to a hand
        # placing a disc it cannot see through. It does NOT buy the 4.45 mm
        # clearance a hexagon of EQUAL AREA to the square would give
        # (flat-to-flat 12.895 mm) - and that hexagon costs capacity instead of
        # gaining it: 350 patches per A4 against the square's 345, i.e. no gain
        # at all. Denser-at-equal-clearance is the better trade of the two, and
        # it is the one shipped. The equal-area variant is a one-line change
        # (the 12.0 in the hflag branch) if hardware ever says otherwise.
        #
        # Shape mechanics: a hexagon of the same width is sqrt(0.75) as tall
        # (the rows interleave), pokes plen/6 past its slot top and bottom and
        # a quarter of its width past each side. hxeh/hxew reserve exactly
        # those two overhangs so the honeycomb cannot print past the margin.
        if hflag:
            plen = pscale * math.sqrt(0.75) * 12.0
            hxeh = plen / 6.0
            hxew = pscale * 0.25 * 12.0
        else:
            plen = pscale * 12.0
            hxeh = hxew = 0.0
        extra = (("HEXAGON_PATCHES", "True"),) if hflag else ()
        # SPACERS: a REAL width here, switched OFF by the recipe, not by a zero.
        #
        # Basti's ruling (2026-08-28) is that a CR30 chart has no spacers by
        # default but the user must be able to turn them on. Those are two
        # different questions and only one of them belongs in the geometry.
        #
        # Writing pspa=0.0 here would answer both at once and answer the second
        # one WRONG: build() only honours the Manual "Spacer size" box when
        # `geom.pspa > 0` (:218-219), so a zero base makes the spacer
        # un-turn-on-able as well as absent. The default therefore lives in
        # presets.default_recipe, which sets spacer_mode="none" for a CR30 -
        # that feeds spacer_on=False into spacer() below, which returns 0.0. Set
        # the Spacers control to Coloured or Black & white and the 1.3 mm base
        # comes back, with its width box live.
        #
        # 1.3 mm because that is what the only hardware-proven CR30 read used:
        # EXP-SPEC-001a was a ColorMunki extra-high sheet, whose branch sets
        # pspa_e = pscale * 1.3 (:433). It is the evidence base for the size,
        # not for whether it is on.
        return Geom(
            key=key, plen=plen, pspa=spacer(1.3), tspa=0.0,
            pwid=pscale * 12.0, rrsp=pscale * 12.0,
            lspa=border + txhisl, lcar=0.0, txhisl=txhisl, pglth=5.0,
            border=border, lbord=_band, hxeh=hxeh, hxew=hxew, clwi=0.0, rlwi=ROW_LABEL_BAND_MM,
            mxpprow=MAXPPROW, mxrowl=MAXROWLEN, rpstrip=999, nextrap=0,
            dorspace=False, dopglabel=False,
            padlrow=False, target_name=name,
            has_clip_border=_band > 0, extra_keywords=extra,
            hexagonal=bool(hflag),
        )

    # ---- X-Rite DTP41 ---------------------------------------------------
    if key == "41":
        plen = pscale * _inch(0.29)
        pspa = spacer(_inch(0.08))
        tspa = 2.0 * (plen + pspa)
        mxrowl = MAXROWLEN if nolimit else _inch(55.0)
        extra = (
            ("PATCH_LENGTH", f"{plen:.6f}"),
            ("GAP_LENGTH", f"{pspa:.6f}"),
            ("TRAILER_LENGTH", f"{tspa:.6f}"),
        )
        return Geom(
            key=key, plen=plen, pspa=pspa, tspa=tspa,
            pwid=_inch(0.5), rrsp=_inch(0.5),
            lspa=_inch(1.5), lcar=_inch(0.5), txhisl=5.0, pglth=5.0,
            border=border, lbord=0.0, hxeh=0.0, hxew=0.0, clwi=0.3, rlwi=0.0,
            mxpprow=100, mxrowl=mxrowl, rpstrip=8, nextrap=0,
            dorspace=False, dopglabel=False,   # page-label column reclaimed (#93)
            padlrow=True, target_name=name,
            has_clip_border=False, extra_keywords=extra, ruler_mm=_inch(55.0),
        )

    # ---- X-Rite DTP51 ---------------------------------------------------
    if key == "51":
        plen = pscale * _inch(0.4)
        pspa = spacer(_inch(0.07))
        mxrowl = MAXROWLEN if nolimit else _inch(40.0)
        return Geom(
            key=key, plen=plen, pspa=pspa, tspa=0.0,
            pwid=_inch(0.4), rrsp=_inch(0.5),
            lspa=_inch(1.2), lcar=_inch(0.25), txhisl=5.0, pglth=5.0,
            border=border, lbord=0.0, hxeh=0.0, hxew=0.0, clwi=0.3, rlwi=0.0,
            mxpprow=72, mxrowl=mxrowl, rpstrip=6, nextrap=2,   # max+min header/trailer
            dorspace=True, dopglabel=False, padlrow=True, target_name=name,
            has_clip_border=False, ruler_mm=_inch(40.0),
        )

    raise ValueError(f"unhandled instrument {key!r}")
