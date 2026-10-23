"""A chart a little larger than the paper (jctay, forum 149803; Knut 149804;
Basti 2026-10-23: "ideally ... this gets printed without a warning on a
printer like jctay has").

Some 4 x 6 in photo printers take 100 x 148 mm paper (the Japanese postcard
size: Canon SELPHY) where the chart was laid out for 4 x 6 in (101.6 x
152.4 mm). Shrinking the chart to fit would move every patch away from where
the instrument expects it, so ChromIQ NEVER shrinks. This module decides
whether the chart can be printed at exactly 100 % with the part that does not
fit simply left off the paper, and where to put it so that the part left off
is empty margin.

THE RULE (all of it must hold, per page, in the orientation the chart is
printed in):

* the chart is larger than the paper by at most ``MAX_OVERHANG_MM`` and at
  most ``MAX_OVERHANG_FRACTION`` of the paper on each axis. More than that is
  a chart made for another paper, and stays the existing refusal or
  confirmation;
* nothing printed is left off: every pixel that is not paper white
  (patches, spacers, strip letters, notes, the ruler helper marks, stamps)
  stays on the paper with at least ``SAFETY_MM`` to spare for the printer's
  paper feed;
* the white the instrument needs is kept: beyond the PATCHES, the blank
  paper the layout gave is kept up to what ArgyllCMS's printtarg itself
  leaves for that instrument (``keep_box``): along the strips, the white
  before the first patch and after the last one that a strip reader starts
  and ends on; across them, the i1Pro's 26 mm holder-clip border on the
  left. If the layout gave less than that, none of it may be taken;
* ONE printed thing may be cut, and only it: the caption line printtarg
  writes along the chart's edge ("ArgyllCMS - Chart ...", Basti
  2026-10-23). On a 4 x 6 in card it runs from edge to edge, and it is not
  read by any instrument. Found by ``caption_box``; anything that cannot be
  told apart from it with certainty counts as printed content. Likewise the
  ruler helper markers ChromIQ's layout engine can draw along the edges
  (``helper_markers``, Basti 2026-10-23): a visual aid for a person only.

Inside those limits the chart is placed centred when that keeps everything;
otherwise it is moved, as little as possible, towards the side whose margin
is empty, so the cut falls in the empty margin.
"""
from __future__ import annotations

import contextlib
import threading
from dataclasses import dataclass, field
from pathlib import Path

MM_PER_PT = 25.4 / 72.0

#: How much larger than the paper a chart may be, per axis, and still be
#: printed without a question. 4 x 6 in on 100 x 148 mm is 1.6 x 4.4 mm (1.6 %
#: and 2.9 %); A4 on Letter is 18.6 mm (6.3 %), which stays a question.
MAX_OVERHANG_MM = 5.0
MAX_OVERHANG_FRACTION = 0.03
#: What a printer's paper feed may wander, each side: printed content keeps at
#: least this much paper beyond it.
SAFETY_MM = 1.0
#: Below this, there is no overhang at all (rounding of sizes in points).
NO_OVERHANG_MM = 0.3

#: THE WHITE A STRIP READER NEEDS, ALONG THE STRIP, from ArgyllCMS 3.5.0's
#: own printtarg (``target/printtarg.c``, the instrument blocks of
#: ``generate_file``; checked by agent 22 against the 3.5.0 source on
#: 2026-10-23): ``lcar``, "Leading clear area before first patch. Will be
#: white", and ``tspa``, "Clear space after last patch - run off". The
#: larger of the two is kept at BOTH ends of the strips, because a strip can
#: be read in either direction. Keys are ChromIQ's instrument codes ("p3" is
#: printtarg's ``-i 3p``).
#:
#: * i1 (i1Pro, i1Pro 2, i1Pro 3; 5 mm aperture): lcar 10.0, tspa 10.0
#:   (printtarg.c:2158, 2164);
#: * p3 (i1Pro 3 Plus, 8 mm aperture): lcar 20.0, tspa 20.0 (:2171, 2177);
#: * CM (ColorMunki): lcar 20.0, tspa 25.0 (:2217, 2223);
#: * 41 (DTP41): lcar 0.5 in = 12.7, tspa two patch steps, 2 x (0.29 in +
#:   0.08 in) = 18.8 at the default patch size and more with larger patches
#:   (:2034-2040); 25 is kept, which covers patches up to a third larger;
#: * 51 (DTP51): lcar 0.25 in = 6.35, tspa 0 (:2073, 2079);
#: * SS (SpectroScan, an XY table that reads patch by patch): none (:2112,
#:   2122).
_STRIP_WHITE_MM = {"i1": 10.0, "p3": 20.0, "CM": 25.0, "41": 25.0,
                   "51": 6.35}
#: A reader that needs no strip white from printtarg (the SpectroScan, the
#: CR30, which reads one patch at a time): ChromIQ keeps this much all the
#: same. ChromIQ's own number, not ArgyllCMS's.
_LEAD_OTHER_MM = 5.0
#: ACROSS the strips printtarg asks for no instrument white, with one
#: exception: the i1Pro family's holder, which grips the paper on the left
#: ("need this for holder to grip paper and plastic spacer", printtarg.c:
#: 2138-2139, ``lbord = 26.0 - bord``: 26 mm from the paper's left edge to
#: the first strip). Kept on the left whenever the layout gave it.
_HOLDER_CLIP_MM = {"i1": 26.0, "p3": 26.0}
#: A chart whose patches start further left than the holder clip less this
#: has no holder-clip border at all, and needs none kept.
HOLDER_CLIP_TOL_MM = 1.0

#: Kept for callers that ask for one number: the most any instrument needs.
_LEAD_MM = dict(_STRIP_WHITE_MM)


def lead_mm(instrument: "str | None") -> float:
    """The white kept at the ends of the strips for *instrument*; for a chart
    whose instrument is not known, the most any instrument needs."""
    if not instrument:
        return max(_STRIP_WHITE_MM.values())
    return max(_STRIP_WHITE_MM.get(str(instrument), _LEAD_OTHER_MM),
               _LEAD_OTHER_MM)


def white_mm(instrument: "str | None") -> "dict[str, float]":
    """The white kept beyond the patches on each side, in the chart's own
    orientation (its strips run down the page, as printtarg and ChromIQ's
    layout engine lay them): the strip white at the top and the bottom, the
    holder clip on the left. A chart whose instrument is not known keeps
    the most any instrument needs on every side, as before."""
    if not instrument:
        most = max(_STRIP_WHITE_MM.values())
        return {"left": most, "right": most, "top": most, "bottom": most}
    along = lead_mm(instrument)
    return {"left": _HOLDER_CLIP_MM.get(str(instrument), 0.0), "right": 0.0,
            "top": along, "bottom": along}



@dataclass
class Box:
    """A rectangle in mm from the chart's top-left corner."""
    left: float
    top: float
    right: float
    bottom: float

    def union(self, other: "Box | None") -> "Box":
        if other is None:
            return self
        return Box(min(self.left, other.left), min(self.top, other.top),
                   max(self.right, other.right), max(self.bottom, other.bottom))


@dataclass
class Plan:
    """What happens to a chart of *chart* size on a paper of *paper* size."""
    #: the chart fits as it is (no overhang)
    fits: bool
    #: it can be printed at 100 % with only empty margin left off
    safe: bool
    #: where the chart's top-left corner goes, in mm from the paper's
    #: top-left (negative: off the paper)
    offset_mm: "tuple[float, float]" = (0.0, 0.0)
    #: how much of the chart is left off, per side, in mm
    cut_mm: dict = field(default_factory=dict)
    #: why it is not safe: "too_much", "content", "lead", "unknown" or ""
    reason: str = ""
    #: the overhang, per axis, in mm
    over_mm: "tuple[float, float]" = (0.0, 0.0)
    #: how far the chart moves from centred, in mm, in the chart's own
    #: orientation (x to the right, y down): what a print route adds to its
    #: centred placement
    shift_mm: "tuple[float, float]" = (0.0, 0.0)
    #: how much of printtarg's caption line is left off, per side, in mm
    #: (empty when the chart has none, or none of it is left off)
    caption_cut_mm: dict = field(default_factory=dict)

    #: how many ruler helper markers are left off (wholly or in part), per
    #: side of the chart: ``{"top": 12, ...}``; empty when none are
    markers_cut: dict = field(default_factory=dict)

    def caption_cut(self) -> bool:
        return any(v > 0.05 for v in self.caption_cut_mm.values())

    def shift_pt(self) -> "tuple[float, float]":
        return (self.shift_mm[0] / MM_PER_PT, self.shift_mm[1] / MM_PER_PT)

    def describe(self) -> str:
        """For the log: what was left off, and where."""
        c = self.cut_mm
        return (f"left {c.get('left', 0):.1f} mm, right {c.get('right', 0):.1f} "
                f"mm, top {c.get('top', 0):.1f} mm, bottom "
                f"{c.get('bottom', 0):.1f} mm")


def _axis(chart: float, paper: float, lo_keep: float, hi_keep: float):
    """The chart's offset on one axis: centred if that keeps [lo_keep,
    hi_keep] on the paper with SAFETY_MM to spare, else as close to centred
    as keeps it; None when nothing does."""
    centred = (paper - chart) / 2.0
    lo = SAFETY_MM - lo_keep                 # offset >= lo keeps the low side
    hi = paper - SAFETY_MM - hi_keep         # offset <= hi keeps the high side
    if chart <= paper + NO_OVERHANG_MM:
        return centred                       # no overhang on this axis
    if lo > hi + 1e-6:
        return None
    return min(max(centred, lo), hi)


def plan(chart_mm: "tuple[float, float]", paper_mm: "tuple[float, float]",
         content: "Box | None", keep: "Box | None" = None,
         caption: "Box | None" = None, markers: "dict | None" = None) -> Plan:
    """The decision for one page. *content*: everything printed that may not
    be cut (the ink, less printtarg's caption line), None when it could not
    be read (then only a chart that fits is safe). *keep*: the white the
    instrument needs around it, as a box (see :func:`keep_box`); defaults to
    *content*. *caption*: where the caption line is, if there is one: it may
    be cut, and :attr:`Plan.caption_cut_mm` says how much of it is."""
    cw, ch = chart_mm
    pw, ph = paper_mm
    ox, oy = max(0.0, cw - pw), max(0.0, ch - ph)
    if ox <= NO_OVERHANG_MM and oy <= NO_OVERHANG_MM:
        return Plan(True, True, ((pw - cw) / 2.0, (ph - ch) / 2.0),
                    {"left": 0.0, "right": 0.0, "top": 0.0, "bottom": 0.0},
                    over_mm=(ox, oy))
    if (ox > MAX_OVERHANG_MM or oy > MAX_OVERHANG_MM
            or ox > MAX_OVERHANG_FRACTION * pw
            or oy > MAX_OVERHANG_FRACTION * ph):
        return Plan(False, False, reason="too_much", over_mm=(ox, oy))
    if content is None:
        return Plan(False, False, reason="unknown", over_mm=(ox, oy))
    k = keep if keep is not None else content
    x = _axis(cw, pw, content.left, content.right)
    y = _axis(ch, ph, content.top, content.bottom)
    if x is None or y is None:
        return Plan(False, False, reason="content", over_mm=(ox, oy))
    xk = _axis(cw, pw, k.left, k.right)
    yk = _axis(ch, ph, k.top, k.bottom)
    if xk is None or yk is None:
        return Plan(False, False, reason="lead", over_mm=(ox, oy))
    cut = {"left": max(0.0, -xk), "right": max(0.0, xk + cw - pw),
           "top": max(0.0, -yk), "bottom": max(0.0, yk + ch - ph)}
    shift = (xk - (pw - cw) / 2.0, yk - (ph - ch) / 2.0)
    cap_cut = {}
    if caption is not None:
        cap_cut = {"left": max(0.0, -(xk + caption.left)),
                   "right": max(0.0, xk + caption.right - pw),
                   "top": max(0.0, -(yk + caption.top)),
                   "bottom": max(0.0, yk + caption.bottom - ph)}
    marks_cut = {}
    for side, boxes in (markers or {}).items():
        n = sum(1 for b in boxes
                if xk + b.left < 0 or xk + b.right > pw
                or yk + b.top < 0 or yk + b.bottom > ph)
        if n:
            marks_cut[side] = n
    return Plan(False, True, (xk, yk), cut, over_mm=(ox, oy), shift_mm=shift,
                caption_cut_mm=cap_cut, markers_cut=marks_cut)


def keep_box(content: Box, chart_mm: "tuple[float, float]",
             instrument: "str | None",
             patches: "Box | None" = None) -> Box:
    """What must stay on the paper: everything printed (*content*), and the
    PATCHES grown by the instrument's white on each side (:func:`white_mm`),
    never past the chart's own edge (a layout that gave less white than that
    keeps all of it). Without *patches* (none found) the whole content is
    grown by the most any instrument needs on every side, which is the
    cautious answer."""
    cw, ch = chart_mm
    if patches is None:
        # which way the strips run is not known either: the strip white on
        # every side (the most any instrument needs, when it is not known)
        lead = lead_mm(instrument)
        w = {"left": lead, "right": lead, "top": lead, "bottom": lead}
        base = content
    else:
        w = white_mm(instrument)
        base = patches
        if w["left"] and base.left < w["left"] - HOLDER_CLIP_TOL_MM:
            # the layout has no holder-clip border (printtarg -L, ChromIQ's
            # "clip border" off): such a chart is read without the holder
            w = dict(w, left=0.0)
    grown = Box(max(0.0, base.left - w["left"]), max(0.0, base.top - w["top"]),
                min(cw, base.right + w["right"]),
                min(ch, base.bottom + w["bottom"]))
    return grown.union(content)


# ---------------------------------------------------------------------------
# reading a chart page
# ---------------------------------------------------------------------------
#: A pixel is printed content when any channel is below this (of 255): paper
#: white is 255, and the palest spacer or patch ChromIQ prints is far below.
INK_BELOW = 250


def _ink_mm(tiff_path: "str | Path", frame: int = 0):
    """(ink mask, mm per pixel) for one page, None when it is not RGB/grey."""
    import numpy as np
    from PIL import Image
    with Image.open(str(tiff_path)) as im:
        n = getattr(im, "n_frames", 1)
        im.seek(min(max(0, int(frame)), n - 1))
        if im.mode not in ("RGB", "L", "I;16", "I;16B", "RGBA"):
            return None
        dpi = im.info.get("dpi", (0, 0))[0] or 0
        arr = np.asarray(im.convert("RGB"))
    if not dpi:
        from workflow.page_geometry import read_tiff_dimensions_points
        w_pt, _h = read_tiff_dimensions_points(Path(tiff_path))
        dpi = arr.shape[1] / (w_pt / 72.0)
    return arr.min(axis=2) < INK_BELOW, 25.4 / float(dpi)


def content_box(tiff_path: "str | Path", frame: int = 0) -> "Box | None":
    """Everything printed on one page of a chart, in mm from its top-left,
    or None when the page cannot be read as RGB or grey (a chart in other
    inks is never placed off-centre on a guess: it keeps the old rule)."""
    try:
        import numpy as np
        got = _ink_mm(tiff_path, frame)
        if got is None:
            return None
        ink, mm = got
        rows = np.where(ink.any(axis=1))[0]
        cols = np.where(ink.any(axis=0))[0]
        if not len(rows):
            return Box(0.0, 0.0, 0.0, 0.0)
        return Box(float(cols[0]) * mm, float(rows[0]) * mm,
                   float(cols[-1] + 1) * mm, float(rows[-1] + 1) * mm)
    except Exception:          # noqa: BLE001 - unreadable: the old rule
        return None


#: A run of ink at least this long (mm) in one pixel row or column is part of
#: a PATCH: patches sit edge to edge in a strip, and the smallest ChromIQ
#: lays out is several millimetres. Letters, numbers and ruler ticks are far
#: shorter runs.
PATCH_RUN_MM = 5.0
#: ...and such rows (or columns) side by side over at least this many mm: a
#: line drawn across the page (a clip-band edge) is a long run, but thin.
PATCH_BAND_MM = 3.0


def _long_run(line, need: int) -> bool:
    import numpy as np
    if need <= 0 or not line.any():
        return False
    d = np.diff(np.concatenate(([0], line.astype(np.int8), [0])))
    starts, ends = np.where(d == 1)[0], np.where(d == -1)[0]
    return bool(((ends - starts) >= need).any())


def _bands(flags, need: int):
    """First and last index of the bands of True at least *need* long."""
    import numpy as np
    d = np.diff(np.concatenate(([0], flags.astype(np.int8), [0])))
    starts, ends = np.where(d == 1)[0], np.where(d == -1)[0]
    keep = [(a, b) for a, b in zip(starts, ends) if b - a >= need]
    if not keep:
        return None
    return keep[0][0], keep[-1][1]


def patch_box(tiff_path: "str | Path", frame: int = 0) -> "Box | None":
    """Where the PATCHES of one page are, in mm from its top-left: the rows
    and columns that carry a long run of ink, over a band of some width.
    None when no patch area is found (or the page cannot be read). Labels,
    notes and ruler marks are not patches: they need no white beside them for
    the instrument, so the lead is measured from the patches only."""
    try:
        import numpy as np
        got = _ink_mm(tiff_path, frame)
        if got is None:
            return None
        ink, mm = got
        run = int(round(PATCH_RUN_MM / mm))
        band = int(round(PATCH_BAND_MM / mm))
        rows = np.array([_long_run(r, run) for r in ink])
        rb = _bands(rows, band)
        if rb is None:
            return None
        sub = ink[rb[0]:rb[1]]
        cols = np.array([_long_run(c, run) for c in sub.T])
        cb = _bands(cols, band)
        if cb is None:
            return None
        return Box(float(cb[0]) * mm, float(rb[0]) * mm,
                   float(cb[1]) * mm, float(rb[1]) * mm)
    except Exception:          # noqa: BLE001 - unreadable: the old rule
        return None


#: PRINTTARG'S CAPTION LINE ("ArgyllCMS - Chart \"<name>\" (Chart ID <n>)
#: <date>", printtarg.c:3735) is drawn down the page just after the last
#: strip: ``vstring(tro, x + pglth, y1, pglth, y2 - y1, label)`` with
#: ``pglth = 5.0`` (printtarg.c:2805), i.e. in a 5 mm column that starts
#: where the last strip ends. Its length follows the chart's name and the
#: date, so on a 4 x 6 in card it can run from edge to edge. Basti,
#: 2026-10-23: it may be cut, and nothing else may. These say where it may
#: start and end, counted from the patches' right edge, with room for
#: rounding at 150 to 300 dpi.
CAPTION_START_MAX_MM = 1.5
CAPTION_END_MAX_MM = 6.5
#: Gaps inside the caption's column (between strokes of a letter) are
#: bridged up to this; a wider gap ends it.
CAPTION_GAP_MM = 1.0
#: printtarg writes the caption for every instrument but the DTP51
#: (``dopglabel = 0``, printtarg.c:2067). A chart whose instrument is not
#: known can still carry one.
_NO_CAPTION_INSTRUMENTS = {"51"}


def _stems(p: Path) -> "list[str]":
    import re
    # "<stem>_01.tif" is page 1 of "<stem>": only that page suffix comes off
    # (a name may end in digits of its own, "Progress300")
    return list(dict.fromkeys([p.stem, re.sub(r"[_-]\d+$", "", p.stem)]))


def made_by_printtarg(tiff_path: "str | Path") -> bool:
    """True when the chart beside *tiff_path* was laid out by ArgyllCMS's
    printtarg: its .ti2 says ``ORIGINATOR "Argyll printtarg"`` and its
    sidecar does not carry ChromIQ's layout engine. Only such a chart has
    printtarg's caption line."""
    import json
    p = Path(tiff_path)
    for st in _stems(p):
        side = p.parent / f"{st}.channels.json"
        if side.is_file():
            try:
                lay = json.loads(side.read_text(encoding="utf-8")).get("layout")
            except Exception:  # noqa: BLE001
                lay = None
            if isinstance(lay, dict) and lay.get("engine"):
                return False
    for st in _stems(p):
        ti2 = p.parent / f"{st}.ti2"
        if ti2.is_file():
            try:
                head = ti2.read_text(encoding="utf-8", errors="replace")[:2000]
            except OSError:
                continue
            return 'ORIGINATOR "Argyll printtarg"' in head
    return False


def caption_box(tiff_path: "str | Path", frame: int = 0,
                patches: "Box | None" = None) -> "Box | None":
    """Where printtarg's caption line is on one page, in mm, or None.

    Found only on a chart printtarg laid out (:func:`made_by_printtarg`),
    and only where printtarg puts it: a column of ink that starts within
    ``CAPTION_START_MAX_MM`` of the patches' right edge and ends within
    ``CAPTION_END_MAX_MM`` of it. Anything further right (ChromIQ's own
    notes or settings stamp, a mark) is not part of it and stays content.
    None whenever that cannot be said with certainty: the caller then keeps
    all of it."""
    try:
        import numpy as np
        if not made_by_printtarg(tiff_path):
            return None
        if instrument_of(tiff_path) in _NO_CAPTION_INSTRUMENTS:
            return None
        if patches is None:
            patches = patch_box(tiff_path, frame)
        if patches is None:
            return None
        got = _ink_mm(tiff_path, frame)
        if got is None:
            return None
        ink, mm = got
        x0 = int(np.ceil(patches.right / mm))
        cols = ink[:, x0:].any(axis=0)
        xs = np.where(cols)[0]
        if not len(xs):
            return None
        gap = max(1, int(round(CAPTION_GAP_MM / mm)))
        start = end = int(xs[0])
        for x in xs[1:]:
            if x - end > gap:
                break
            end = int(x)
        left = (x0 + start) * mm
        right = (x0 + end + 1) * mm
        if left - patches.right > CAPTION_START_MAX_MM:
            return None
        if right - patches.right > CAPTION_END_MAX_MM:
            return None
        band = ink[:, x0 + start:x0 + end + 1]
        rows = np.where(band.any(axis=1))[0]
        return Box(left, float(rows[0]) * mm, right, float(rows[-1] + 1) * mm)
    except Exception:          # noqa: BLE001 - unreadable: keep everything
        return None


#: THE RULER HELPER MARKERS (#152, Knut) may be cut too (Basti, 2026-10-23,
#: through the orchestrator): the short dashes ChromIQ's layout engine can
#: draw along the page edges, ``helper_marker_edge`` mm from the edge and
#: ``helper_marker_len`` mm long, pointing inward
#: (`layout_engine.geometry.helper_marker_lines_mm`). They are purely a
#: visual aid for a person lining a ruler up; no instrument or tool reads
#: them. What the engine draws, and what each is for:
#:
#: * patches and spacers: read by the instrument -- never cut;
#: * strip letters and their underline, row numbers (SpectroScan): a person
#:   needs them to find the strip -- never cut;
#: * the sheet text, the settings stamp, the clip-border notes, the
#:   wordmark: the chart's own record -- never cut;
#: * the ruler helper markers: a visual aid only -- MAY be cut.
#:
#: The engine prints no scanner fiducials (scanin is given the corners by
#: hand, ``cht_writer``), and nothing here touches an i1iSis chart (its
#: layout is i1Profiler's, ``instruments.DELEGATED``). A dash is recognised
#: only as the engine draws it: a straight run the marker length long, at
#: most ``MARKER_WIDTH_MAX_MM`` thick, starting the marker distance from its
#: edge, with nothing else beside it in its band. A dash that crosses other
#: ink (the help text allows them to overlap the clip-border notes) is not
#: recognised and stays content.
MARKER_WIDTH_MAX_MM = 0.6
MARKER_TOL_MM = 0.6


def _recipe_of(tiff_path: "str | Path") -> "dict | None":
    import json
    p = Path(tiff_path)
    for st in _stems(p):
        side = p.parent / f"{st}.channels.json"
        if side.is_file():
            try:
                lay = json.loads(side.read_text(encoding="utf-8")).get("layout")
            except Exception:  # noqa: BLE001
                return None
            if isinstance(lay, dict) and isinstance(lay.get("recipe"), dict):
                return lay["recipe"]
    return None


def _dashes_in_band(band, mm: float, edge_mm: float, len_mm: float):
    """The columns of *band* (rows run from the paper edge inward) that are
    helper-marker dashes: a list of (first column, last column + 1)."""
    import numpy as np
    cols = np.where(band.any(axis=0))[0]
    out = []
    if not len(cols):
        return out
    groups = []
    start = prev = int(cols[0])
    for c in cols[1:]:
        c = int(c)
        if c != prev + 1:
            groups.append((start, prev + 1))
            start = c
        prev = c
    groups.append((start, prev + 1))
    for a, b in groups:
        if (b - a) * mm > MARKER_WIDTH_MAX_MM:
            continue
        rows = np.where(band[:, a:b].any(axis=1))[0]
        r0, r1 = int(rows[0]), int(rows[-1]) + 1
        if len(rows) != r1 - r0:            # one unbroken run, nothing else
            continue
        if abs(r0 * mm - edge_mm) > MARKER_TOL_MM:
            continue
        if abs((r1 - r0) * mm - len_mm) > MARKER_TOL_MM:
            continue
        out.append((a, b))
    return out


def helper_markers(tiff_path: "str | Path", frame: int = 0):
    """The ruler helper markers on one page: ``{side: [Box, ...]}`` in mm,
    for the sides they are on; ``{}`` when the chart has none, is not a
    layout-engine chart, or none can be recognised."""
    try:
        rec = _recipe_of(tiff_path)
        if not rec or not rec.get("helper_markers"):
            return {}
        # the recipe as the sidecar keeps it (LayoutRecipe: "_mm" names),
        # or as build kwargs spell them
        edge = float(rec.get("helper_marker_edge_mm")
                     or rec.get("helper_marker_edge") or 2.0)
        length = float(rec.get("helper_marker_len_mm")
                       or rec.get("helper_marker_len") or 2.0)
        got = _ink_mm(tiff_path, frame)
        if got is None:
            return {}
        ink, mm = got
        h, w = ink.shape
        depth = int(round((edge + length + MARKER_TOL_MM) / mm))
        found: dict = {}
        if rec.get("helper_markers_top_bottom", True):
            top = ink[:depth, :]
            found["top"] = [Box(a * mm, edge, b * mm, edge + length)
                            for a, b in _dashes_in_band(top, mm, edge, length)]
            bot = ink[h - depth:, :][::-1, :]
            found["bottom"] = [Box(a * mm, h * mm - edge - length, b * mm,
                                   h * mm - edge)
                               for a, b in _dashes_in_band(bot, mm, edge, length)]
        if rec.get("helper_markers_sides", True):
            left = ink[:, :depth].T
            found["left"] = [Box(edge, a * mm, edge + length, b * mm)
                             for a, b in _dashes_in_band(left, mm, edge, length)]
            right = ink[:, w - depth:][:, ::-1].T
            found["right"] = [Box(w * mm - edge - length, a * mm,
                                  w * mm - edge, b * mm)
                              for a, b in _dashes_in_band(right, mm, edge, length)]
        return {k: v for k, v in found.items() if v}
    except Exception:          # noqa: BLE001 - unreadable: keep everything
        return {}


def printed_box(tiff_path: "str | Path", frame: int = 0,
                caption: "Box | None" = None,
                markers: "dict | None" = None) -> "Box | None":
    """What may not be cut on one page: everything printed (as
    :func:`content_box`) less printtarg's caption line *caption* and the
    ruler helper markers *markers* (:func:`helper_markers`)."""
    if caption is None and not markers:
        return content_box(tiff_path, frame)
    try:
        import numpy as np
        got = _ink_mm(tiff_path, frame)
        if got is None:
            return None
        ink, mm = got
        ink = ink.copy()
        if caption is not None:
            x0 = int(round(caption.left / mm))
            x1 = int(round(caption.right / mm))
            ink[:, x0:x1] = False
        h, w = ink.shape
        for boxes in (markers or {}).values():
            for b in boxes:
                # the dash's own pixels, with a pixel of slack for rounding
                x0 = max(0, int(np.floor(b.left / mm)) - 1)
                x1 = min(w, int(np.ceil(b.right / mm)) + 1)
                y0 = max(0, int(np.floor(b.top / mm)) - 1)
                y1 = min(h, int(np.ceil(b.bottom / mm)) + 1)
                ink[y0:y1, x0:x1] = False
        rows = np.where(ink.any(axis=1))[0]
        cols = np.where(ink.any(axis=0))[0]
        if not len(rows):
            return Box(0.0, 0.0, 0.0, 0.0)
        return Box(float(cols[0]) * mm, float(rows[0]) * mm,
                   float(cols[-1] + 1) * mm, float(rows[-1] + 1) * mm)
    except Exception:          # noqa: BLE001 - unreadable: the old rule
        return None


def instrument_of(tiff_path: "str | Path") -> "str | None":
    """The chart's instrument code from its sidecar (``<stem>.channels.json``
    layout recipe), else from the .ti2 beside it; None when unknown."""
    import json
    p = Path(tiff_path)
    stems = _stems(p)
    for st in stems:
        side = p.parent / f"{st}.channels.json"
        if side.is_file():
            try:
                data = json.loads(side.read_text(encoding="utf-8"))
                inst = ((data.get("layout") or {}).get("recipe") or {}).get(
                    "instrument")
                if inst:
                    return str(inst)
                # a printtarg chart ChromIQ made: the Create Chart settings
                # it was made with travel in the sidecar (K2), printtarg's
                # "-i" among them, by ChromIQ's own code ("p3" for -i 3p)
                rec = (data.get("create_chart_settings") or {}).get(
                    "printtarg-i")
                inst = rec.get("value") if isinstance(rec, dict) else None
                if inst:
                    return str(inst)
            except Exception:  # noqa: BLE001
                pass
    for st in stems:
        ti2 = p.parent / f"{st}.ti2"
        if ti2.is_file():
            try:
                text = ti2.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            # printtarg names the instrument by ArgyllCMS's own table
            # (spectro/insttypes.c inst_name): "GretagMacbeth i1 Pro" for
            # BOTH -i i1 and -i 3p (printtarg.c:3341 makes 3p an i1Pro with a
            # modifier), so such a chart is taken as the one that needs more
            # white, the i1Pro 3 Plus. A chart cut too little is still read;
            # one cut too much is not.
            for code, words in (("CM", ("ColorMunki",)),
                                ("41", ("DTP41",)), ("51", ("DTP51",)),
                                ("SS", ("SpectroScan",)),
                                ("p3", ("i1 Pro", "i1Pro"))):
                if any(w in text for w in words):
                    return code
    return None


def plan_for_page(tiff_path: "str | Path", frame: int,
                  chart_pt: "tuple[float, float]",
                  paper_pt: "tuple[float, float]") -> Plan:
    """:func:`plan` for one page of a chart file, sizes in points, in the
    orientation they are given in (the caller turns the page first)."""
    chart_mm = (chart_pt[0] * MM_PER_PT, chart_pt[1] * MM_PER_PT)
    paper_mm = (paper_pt[0] * MM_PER_PT, paper_pt[1] * MM_PER_PT)
    patches = patch_box(tiff_path, frame)
    caption = caption_box(tiff_path, frame, patches)
    markers = helper_markers(tiff_path, frame)
    content = printed_box(tiff_path, frame, caption, markers)
    keep = (keep_box(content, chart_mm, instrument_of(tiff_path), patches)
            if content is not None else None)
    return plan(chart_mm, paper_mm, content, keep, caption, markers)


def paper_like_chart(chart_pt: "tuple[float, float]",
                     paper_pt: "tuple[float, float]") -> "tuple[float, float]":
    """The paper turned to lie the way the chart does (portrait for a
    portrait chart), as the PostScript route lays a page and as a chart a
    little larger than its paper is compared."""
    pw, ph = paper_pt
    if (chart_pt[0] > chart_pt[1]) != (pw > ph):
        return (ph, pw)
    return (pw, ph)


def plan_for_chart(pages, chart_pt: "tuple[float, float]",
                   paper_pt: "tuple[float, float]") -> Plan:
    """One plan for every page of a chart (the pages share a size and are
    placed alike): the pages' contents joined, the paper turned like the
    chart. *pages*: [(tiff path, frame)]."""
    chart_mm = (chart_pt[0] * MM_PER_PT, chart_pt[1] * MM_PER_PT)
    pp = paper_like_chart(chart_pt, paper_pt)
    paper_mm = (pp[0] * MM_PER_PT, pp[1] * MM_PER_PT)
    content = None
    patches = None
    caption = None
    markers: dict = {}
    no_patches = False
    inst = None
    for path, frame in pages:
        pb = patch_box(path, frame)
        cap = caption_box(path, frame, pb)
        mk = helper_markers(path, frame)
        for side, boxes in mk.items():
            # one plan for every page: a side's dashes are counted per page
            markers.setdefault(side, []).extend(boxes)
        c = printed_box(path, frame, cap, mk)
        if c is None:
            return plan(chart_mm, paper_mm, None)
        content = c if content is None else content.union(c)
        if cap is not None:
            caption = cap if caption is None else caption.union(cap)
        if pb is None:
            no_patches = True       # one page unknown: the cautious rule
        else:
            patches = pb if patches is None else patches.union(pb)
        inst = inst or instrument_of(path)
    if content is None:
        return plan(chart_mm, paper_mm, None)
    return plan(chart_mm, paper_mm, content,
                keep_box(content, chart_mm, inst,
                         None if no_patches else patches), caption, markers)


# ---------------------------------------------------------------------------
# the placement a print in progress uses
# ---------------------------------------------------------------------------
_PLACEMENT = threading.local()


@contextlib.contextmanager
def placed(shift_pt: "tuple[float, float] | None"):
    """While this is open, ChromIQ's PostScript and exact-size PDF place the
    chart *shift_pt* (x right, y down, in the chart's own orientation) away
    from centred on the page: what :class:`Plan` asks for. Every print route
    that writes the page itself goes through those two generators, so one
    setting at the print button reaches all of them."""
    old = getattr(_PLACEMENT, "shift", None)
    _PLACEMENT.shift = tuple(shift_pt) if shift_pt else None
    try:
        yield
    finally:
        _PLACEMENT.shift = old


def current_shift_pt() -> "tuple[float, float]":
    return getattr(_PLACEMENT, "shift", None) or (0.0, 0.0)
