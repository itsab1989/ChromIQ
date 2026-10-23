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
* the white the instrument needs is kept: around everything printed, the
  blank paper the layout gave is kept up to ``lead_mm(instrument)`` on every
  side (the white before the first patch and after the last one that a strip
  reader starts and ends on, and the white beside the outer strips). If the
  layout gave less than that, none of it may be taken.

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

#: The white a strip reader needs beyond the printed chart, per instrument,
#: from ArgyllCMS printtarg's own geometry (lcar, the leading clear area, and
#: tspa, the trailer): what printtarg leaves before the first and after the
#: last patch of every strip. The larger of the two is used on every side.
_LEAD_MM = {"i1": 10.0, "p3": 20.0, "CM": 25.0}
#: Anything else (a patch-by-patch or whole-sheet reader): the patches only.
_LEAD_OTHER_MM = 5.0


def lead_mm(instrument: "str | None") -> float:
    """The white kept around the patches for *instrument*; for a chart whose
    instrument is not known, the most any instrument needs."""
    if not instrument:
        return max(_LEAD_MM.values())
    return _LEAD_MM.get(str(instrument), _LEAD_OTHER_MM)


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
         content: "Box | None", keep: "Box | None" = None) -> Plan:
    """The decision for one page. *content*: everything printed (the ink),
    None when it could not be read (then only a chart that fits is safe).
    *keep*: the white the instrument needs around it, as a box (see
    :func:`keep_box`); defaults to *content*."""
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
    return Plan(False, True, (xk, yk), cut, over_mm=(ox, oy), shift_mm=shift)


def keep_box(content: Box, chart_mm: "tuple[float, float]",
             instrument: "str | None",
             patches: "Box | None" = None) -> Box:
    """What must stay on the paper: everything printed (*content*), and the
    PATCHES grown on every side by the instrument's white (:func:`lead_mm`),
    never past the chart's own edge (a layout that gave less white than that
    keeps all of it). Without *patches* (none found) the whole content is
    grown, which is the cautious answer."""
    lead = lead_mm(instrument)
    cw, ch = chart_mm
    base = patches if patches is not None else content
    grown = Box(max(0.0, base.left - lead), max(0.0, base.top - lead),
                min(cw, base.right + lead), min(ch, base.bottom + lead))
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


def instrument_of(tiff_path: "str | Path") -> "str | None":
    """The chart's instrument code from its sidecar (``<stem>.channels.json``
    layout recipe), else from the .ti2 beside it; None when unknown."""
    import json
    p = Path(tiff_path)
    import re
    # "<stem>_01.tif" is page 1 of "<stem>": only that page suffix comes off
    # (a name may end in digits of its own, "Progress300")
    stems = [p.stem, re.sub(r"[_-]\d+$", "", p.stem)]
    for st in stems:
        side = p.parent / f"{st}.channels.json"
        if side.is_file():
            try:
                data = json.loads(side.read_text(encoding="utf-8"))
                inst = ((data.get("layout") or {}).get("recipe") or {}).get(
                    "instrument")
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
            for code, words in (("p3", ("i1 Pro 3 Plus", "i1Pro3Plus")),
                                ("CM", ("ColorMunki",)), ("i1", ("i1 Pro", "i1Pro"))):
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
    content = content_box(tiff_path, frame)
    keep = (keep_box(content, chart_mm, instrument_of(tiff_path),
                     patch_box(tiff_path, frame))
            if content is not None else None)
    return plan(chart_mm, paper_mm, content, keep)


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
    no_patches = False
    inst = None
    for path, frame in pages:
        c = content_box(path, frame)
        if c is None:
            return plan(chart_mm, paper_mm, None)
        content = c if content is None else content.union(c)
        pb = patch_box(path, frame)
        if pb is None:
            no_patches = True       # one page unknown: the cautious rule
        else:
            patches = pb if patches is None else patches.union(pb)
        inst = inst or instrument_of(path)
    if content is None:
        return plan(chart_mm, paper_mm, None)
    return plan(chart_mm, paper_mm, content,
                keep_box(content, chart_mm, inst,
                         None if no_patches else patches))


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
