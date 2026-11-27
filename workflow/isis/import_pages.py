"""An i1iSis measurement of a chart of SEVERAL pages (part 1 of the i1iSis
pieces work, the i1iSis chart Beta).

WHAT IS PAIRED, AND BY WHAT. Nothing new: entry ``j`` of i1Profiler's patch
list is the chart patch the order file names (`workflow.isis.export`), page
``j // (C x R)``, by position as on one page. What this module adds are the
CHECKS a measurement of several pages needs before it may be filed, because
the device values in it are i1Profiler's copy of its test chart and prove
nothing about which sheet went through the instrument when:

* R1, every patch once: a file that holds whole pages and lacks others names
  the missing pages; a file that numbers its patches page by page (1 .. C x R
  on every page again) is a form not on record, refused with a request for
  the file;
* R3, i1Profiler's grid when the file records it: C columns, R rows a page,
  P pages (its own saved ``.txf`` writes rows per page); ``NumberPatchPages
  "0"`` says nothing about the pages;
* R4, the places when the file records them: page by page as ChromIQ's
  ``.txf`` writes them, the columns of each page counted from 0 or counted on
  from the page before; any other form is filed only when the colours of
  every page clearly sit on their own patches, else refused with a request
  for the file (nothing is guessed);
* R5, the colours: every page by the one-page judge (`import_check.decide`,
  unchanged, called per page), and the whole chart against every way pages
  can be fed wrongly (swapped, one page twice, the pages in another order),
  each compared with the right way ON THE SAME READINGS by the same misfit
  `import_check.compare` uses. One clearly better: refused, naming the pages.
  Where pages look alike (ramps, grey sets, a repeated patch set) nobody can
  tell: asked, Cancel the default, never filed in silence.

Pages are only told apart by colour; nothing is ever paired by colour.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import import_check as IC

log = logging.getLogger(__name__)

#: How a page-level wrong way is judged: the same limits as a wrong way of
#: one page (`import_check.CLEARLY_RIGHT` / `CLEARLY_WRONG`).
CLEARLY_RIGHT = IC.CLEARLY_RIGHT
CLEARLY_WRONG = IC.CLEARLY_WRONG


@dataclass(frozen=True)
class PagesVerdict:
    """*verdict*: ``import_check.RIGHT`` / ``WRONG`` / ``CANNOT``.

    *why*: for WRONG "pages" (a page holds another page's readings),
    "colours" (a page does not fit its own patches), "places" (places in a
    form not on record, colours not clear), "grid"; for CANNOT the reason
    the person is asked ("pages" when pages cannot be told apart, else the
    one-page judge's). *page* / *other*: the pages named (from 1)."""
    verdict: str
    why: str = ""
    detail: str = ""
    page: int = 0
    other: int = 0


def page_sizes(n: int, rows: int, cols: int, pages: int) -> "list[int]":
    """Entries on each page: C x R on every page but the last."""
    k = rows * cols
    return [max(0, min(k, n - p * k)) for p in range(pages)]


def page_of(j: int, rows: int, cols: int) -> int:
    return j // (rows * cols)


# ---------------------------------------------------------------------------
# R1: which pages a file holds
# ---------------------------------------------------------------------------

def pages_held(entries, n: int, rows: int, cols: int, pages: int
               ) -> "tuple[list[int], list[int]] | None":
    """(pages complete, pages with nothing) from the entries a file holds
    (0-based, each once), when every page is either complete or empty;
    None otherwise (a page part read). Pages from 1."""
    sizes = page_sizes(n, rows, cols, pages)
    got = [0] * pages
    for j in entries:
        if 0 <= j < n:
            got[page_of(j, rows, cols)] += 1
    if any(0 < g < s for g, s in zip(got, sizes)):
        return None
    return ([p + 1 for p in range(pages) if got[p] == sizes[p]],
            [p + 1 for p in range(pages) if got[p] == 0])


def numbered_page_by_page(ids, n: int, rows: int, cols: int,
                          pages: int) -> bool:
    """True when *ids* (the file's SAMPLE_IDs, in file order) are 1 .. C x R
    on every page again: a form of i1Profiler's several-page file that is
    not on record. Never filed by position (it could be any page)."""
    sizes = page_sizes(n, rows, cols, pages)
    want = [str(i + 1) for s in sizes for i in range(s)]
    got = [str(s).strip('"') for s in ids]
    return pages > 1 and len(got) == n and sorted(got) == sorted(want) \
        and len(set(got)) < len(got)


# ---------------------------------------------------------------------------
# R3 / R4: the grid and the places a CxF records
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FileGrid:
    """What an i1Profiler CxF says of its grid: columns, rows (of the first
    page), pages (0: not said), and each Target's (page, row, column) in
    file order, None where a Target has no whole Location."""
    columns: int
    rows: int
    pages: int
    places: tuple
    #: True for a converted copy that says places were recorded but not
    #: which (no picked file to read them from): a form not readable here.
    unread: bool = False


def grid_of_source(source) -> "FileGrid | None":
    """The grid and places of the picked CxF *source*, read as they are (no
    page count assumed); None when it is not a CxF or records no grid."""
    if source is None:
        return None
    from workflow.reference_convert import _CXF_NS, is_cxf
    import xml.etree.ElementTree as ET
    if not is_cxf(Path(str(source))):
        return None
    try:
        root = ET.parse(str(source)).getroot()
    except (ET.ParseError, OSError):
        return None
    attrs = None
    for el in root.iter():
        if el.tag.rsplit("}", 1)[-1] == "CustomAttributes" and (
                el.get("NumberPatchColumns") is not None):
            attrs = el
            break
    if attrs is None:
        return None
    try:
        cols = int(str(attrs.get("NumberPatchColumns")).strip())
        rows = int(str(attrs.get("NumberPatchRows")).strip())
        pages = int(str(attrs.get("NumberPatchPages") or "0").strip() or 0)
    except (TypeError, ValueError):
        return None
    places = []
    for o in root.findall(".//cc:Object", _CXF_NS):
        if o.get("ObjectType") != "Target":
            continue
        tags = {}
        for tc in o.findall("cc:TagCollection", _CXF_NS):
            if tc.get("Name") != "Location":
                continue
            for t in tc.findall("cc:Tag", _CXF_NS):
                tags[t.get("Name")] = t.get("Value")
        try:
            places.append((int(tags["Page"]), int(tags["Row"]),
                           int(tags["Column"])))
        except (KeyError, TypeError, ValueError):
            places.append(None)
    return FileGrid(cols, rows, max(0, pages), tuple(places))


def place_of(j: int, rows: int, cols: int, counted_on: bool
             ) -> "tuple[int, int, int]":
    """(page from 1, row, column) of entry *j* on ChromIQ's pages: column by
    column, page by page; the columns of each page from 0, or counted on."""
    p, q = divmod(j, rows * cols)
    c, r = divmod(q, rows)
    return p + 1, r, (p * cols + c) if counted_on else c


def places_form(places, at, rows: int, cols: int) -> str:
    """"none", "page-local", "counted-on" or "other" for the places of a
    file whose row i is entry ``at[i]``."""
    if not places or all(p is None for p in places):
        return "none"
    if len(places) != len(at) or any(p is None for p in places):
        return "other"
    for form, on in (("page-local", False), ("counted-on", True)):
        if all(tuple(p) == place_of(j, rows, cols, on)
               for p, j in zip(places, at)):
            return form
    return "other"


def grid_differs(file_grid, rows: int, cols: int, pages: int) -> bool:
    """True when the file's grid is not C x R on P pages. Pages 0 (or the
    one-page reading of "0") say nothing."""
    if file_grid is None:
        return False
    if (file_grid.columns, file_grid.rows) != (cols, rows):
        return True
    return file_grid.pages not in (0, pages)


# ---------------------------------------------------------------------------
# R5: the colours
# ---------------------------------------------------------------------------

def page_ways(n: int, rows: int, cols: int, pages: int
              ) -> "dict[str, tuple[np.ndarray, int, int]]":
    """name -> (p, page, other): reading j would really be of entry p[j]
    (-1: no patch there) when the pages went in wrongly. *page* / *other*
    name the first page that holds another page's readings (from 1)."""
    k = rows * cols
    sizes = page_sizes(n, rows, cols, pages)

    def mapping(src_of_page):
        p = np.arange(n)
        for b in range(pages):
            a = src_of_page[b]
            if a == b:
                continue
            for i in range(sizes[b]):
                p[b * k + i] = a * k + i if i < sizes[a] else -1
        return p

    out = {}
    first = lambda m: next(b for b in range(pages) if m[b] != b)  # noqa: E731
    for a in range(pages):
        for b in range(a + 1, pages):
            m = list(range(pages))
            m[a], m[b] = b, a
            out[f"pages {a + 1} and {b + 1} swapped"] = (mapping(m), a + 1,
                                                       b + 1)
    for a in range(pages):
        for b in range(pages):
            if a != b:
                m = list(range(pages))
                m[b] = a
                out[f"page {a + 1} twice, as page {b + 1}"] = (
                    mapping(m), b + 1, a + 1)
    if pages > 2:
        m = list(range(pages))[::-1]
        out["the pages last first"] = (mapping(m), first(m) + 1,
                                       m[first(m)] + 1)
        for s in range(1, pages):
            m = [(b + s) % pages for b in range(pages)]
            out[f"the pages from page {s + 1} on"] = (
                mapping(m), first(m) + 1, m[first(m)] + 1)
    return out


def judge_pages(E, M, rows: int, cols: int, pages: int,
                randomised: bool) -> PagesVerdict:
    """Judge readings *M* (L*a*b*, entry order) of a chart of several pages
    against the expected colours *E*.

    The pages first, over the whole chart (a page of a sorted set read in
    place of another fits ITS page's colours too well to be seen on that page
    alone: only one rising L* for the whole chart shows it); then every page
    by the one-page judge. On a randomised chart a page the one-page judge
    cannot clear is filed, as one page is (G1, review m5); on any other chart
    it is asked."""
    E, M = np.asarray(E, float), np.asarray(M, float)
    n = len(E)
    if n != len(M) or n == 0 or not (np.all(np.isfinite(E))
                                     and np.all(np.isfinite(M))):
        return PagesVerdict(IC.CANNOT, "no-colours")
    worst, name, named = 0.0, "", (0, 0)
    idx = np.arange(n)
    for way, (p, page, other) in page_ways(n, rows, cols, pages).items():
        keep = p >= 0
        # ONE PRINTER FOR THE WHOLE CHART, JUDGED WHERE THE WAYS DIFFER. The
        # fit takes every reading (a sorted page read in place of another
        # fits its own page's colours, never one rising L* over all pages),
        # the distance only the readings this way moves: a short last page
        # read twice moves a tenth of the chart, and over the whole chart
        # its difference would be lost.
        moved = keep & (p != idx)
        if moved.sum() < 6:
            continue
        right = float(np.sqrt(IC._residuals(E[keep], M[keep])[
            moved[keep]].mean()))
        wrong = float(np.sqrt(IC._residuals(E[p[keep]], M[keep])[
            moved[keep]].mean()))
        ratio = right / wrong if wrong > 1e-9 else (
            1.0 if right <= 1e-9 else np.inf)
        if ratio > worst:
            worst, name, named = ratio, way, (page, other)
    detail = f"pages: closest {name} {worst:.2f}"
    if worst >= CLEARLY_WRONG:
        return PagesVerdict(IC.WRONG, "pages", detail, *named)
    ask_pages = worst > CLEARLY_RIGHT
    sizes = page_sizes(n, rows, cols, pages)
    k = rows * cols
    ask, details = "", [detail]
    for q, s in enumerate(sizes):
        if s == 0:
            continue
        sl = slice(q * k, q * k + s)
        v = IC.decide(E[sl], M[sl], rows, -(-s // rows))
        details.append(f"page {q + 1}: {v.verdict} ({v.why or 'agree'}) "
                       f"{v.detail}")
        if v.verdict == IC.WRONG:
            return PagesVerdict(IC.WRONG, "colours", "; ".join(details),
                                q + 1)
        if v.verdict == IC.CANNOT and not randomised and not ask:
            ask = v.why or "similar"
    if ask_pages:
        return PagesVerdict(IC.CANNOT, "pages", "; ".join(details))
    if ask:
        return PagesVerdict(IC.CANNOT, ask, "; ".join(details))
    return PagesVerdict(IC.RIGHT, "", "; ".join(details))


def every_page_right(E, M, rows: int, cols: int, pages: int) -> bool:
    """True when every page's colours clearly sit on their own patches: the
    only way a file whose places are in a form not on record is filed."""
    v = judge_pages(E, M, rows, cols, pages, randomised=False)
    if v.verdict != IC.RIGHT:
        return False
    E, M = np.asarray(E, float), np.asarray(M, float)
    k = rows * cols
    for q, s in enumerate(page_sizes(len(E), rows, cols, pages)):
        sl = slice(q * k, q * k + s)
        if s and IC.decide(E[sl], M[sl], rows, -(-s // rows)).verdict \
                != IC.RIGHT:
            return False
    return True


# ---------------------------------------------------------------------------
# The whole check, for `measurement_import`
# ---------------------------------------------------------------------------

def colours_in_entry_order(measured, at, order, chart_ti2):
    """(E, M) of every entry, or None when the colours cannot be read."""
    from workflow.turned_colour_check import _expected_lab, measured_lab
    n = len(order.sample_ids)
    pos = np.argsort(np.asarray(at))
    xyz = np.asarray(measured.xyz, float)
    rgb = np.asarray(measured.rgb, float)
    if len(xyz) != n or len(rgb) != n or not np.all(np.isfinite(xyz)) \
            or float(xyz[:, 1].max()) <= 0:
        return None
    E = _expected_lab(rgb[pos], Path(chart_ti2), order)
    if E is None or len(E) != n:
        return None
    return E, measured_lab(xyz[pos])


def check(ti3: Path, measured, at, order, chart_ti2, source,
          randomised: bool) -> PagesVerdict:
    """Every check of a COMPLETE measurement of a chart of several pages
    whose readings are entries *at* (row i of the file is entry ``at[i]``;
    R1 and R2 are the caller's)."""
    from workflow.reference_convert import i1p_grid_of
    R, C, P = int(order.rows), int(order.columns), int(order.pages)
    fg = grid_of_source(source)
    if fg is None:
        g = i1p_grid_of(ti3)
        if g is not None:
            fg = FileGrid(g.columns, g.rows, g.pages, (),
                          unread=g.located > 0)
    if grid_differs(fg, R, C, P):
        return PagesVerdict(IC.WRONG, "grid",
                            f"file grid {fg.columns} x {fg.rows} on "
                            f"{fg.pages} pages")
    if fg is not None and fg.unread:
        form = "other"                  # recorded, but not readable here
    else:
        form = places_form(list(fg.places) if fg else [], list(at), R, C)
    colours = colours_in_entry_order(measured, at, order, chart_ti2)
    if colours is None:
        if form == "other":
            return PagesVerdict(IC.WRONG, "places", "no colours")
        return PagesVerdict(IC.CANNOT, "no-colours")
    E, M = colours
    v = judge_pages(E, M, R, C, P, randomised)
    log.info("import: the i1iSis measurement of %d pages (places: %s) was "
             "compared with the chart page by page: %s (%s) %s", P, form,
             v.verdict, v.why or "agree", v.detail)
    if v.verdict == IC.WRONG or form != "other":
        return v
    if every_page_right(E, M, R, C, P):
        return v
    return PagesVerdict(IC.WRONG, "places", v.detail)
