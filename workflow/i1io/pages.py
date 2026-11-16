"""An i1iO chart of SEVERAL pages, measured with i1Profiler's "Measure Chart"
one sheet at a time (the i1iO table Beta, 2026-11-16).

WHAT CHANGES AGAINST ONE PAGE. i1Profiler saves one file per sheet, and the
file does not say which sheet it was (every reading is tagged ``Page 1``,
``NumberPatchPages "0"``). So the page is worked out here, never typed:

* the candidates are the chart's pages whose grid (columns x rows) is the
  file's grid;
* each candidate is judged by the one-page net of
  `workflow.i1io.measure_chart` against THAT page's patches, unchanged;
* exactly one passing candidate is the page; two or more are asked about
  (the person picks the page); none is a refusal (`match_file`).

THE PARTIAL STATE. A page that came in is stored as its own filed copy,
``runs/runN/pages/pageK.ti3`` (`Run.i1io_page_ti3`), written to a temporary
name and moved into place in one step. The run's measurement
(`Run.measurement_ti3`) is not written while a page is missing, so nothing
that reads a run's measurement can take a part for the whole. When the last
page is in, the pages are merged (`merge_pages`) into ONE converted copy,
which then goes down the ordinary filing path of the Measure tab's import.

Nothing here runs unless the i1iO Beta is on, the run's chart is an i1iO
chart with its side file, and that side file has more than one page
(`applies`). Nothing here reads a setting.
"""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from core.logger import get_logger

log = get_logger(__name__)

#: Header keywords of a stored page (and, for PAGES, of the merged file).
PAGE_KEYWORD = "CHROMIQ_I1IO_PAGE"
CHART_SHA_KEYWORD = "CHROMIQ_I1IO_CHART_SHA256"
SOURCE_KEYWORD = "CHROMIQ_I1IO_SOURCE"
DEVICE_KEYWORD = "CHROMIQ_I1IO_DEVICE"
PAGES_KEYWORD = "CHROMIQ_I1IO_PAGES"

#: Refusal codes that NAME a mistake on the page they were judged against
#: (a sheet turned, aimed off, one strip out of place, read off the
#: patches): when exactly one candidate page says one of these and the others
#: only say "these are not my colours", that page's reason is the one to give.
NAMED_CODES = frozenset(("turned", "strip", "beside", "paper"))


# ---------------------------------------------------------------------------
# Where it applies
# ---------------------------------------------------------------------------

def page_count(chart_ti2) -> int:
    """The number of pages the chart's side file records (1 when it cannot
    say)."""
    from .measure_chart import read_side
    side = read_side(chart_ti2)
    if side is None:
        return 1
    try:
        return max(1, int(side.get("page_count")
                          or len(side.get("pages") or []) or 1))
    except (TypeError, ValueError):
        return 1


def applies(chart_ti2) -> bool:
    """True only for the Beta's multi-page case: the Beta on, an i1iO chart
    with its side file (`measurement_import.i1io_route_applies`, which reads
    the switch first), and more than one page."""
    if chart_ti2 is None:
        return False
    from workflow.measurement_import import i1io_route_applies
    if not i1io_route_applies(Path(str(chart_ti2))):
        return False
    return page_count(chart_ti2) > 1


def chart_sha256(chart_ti2) -> str:
    try:
        return hashlib.sha256(Path(str(chart_ti2)).read_bytes()).hexdigest()
    except OSError:
        return ""


def file_sha256(path) -> str:
    try:
        return hashlib.sha256(Path(str(path)).read_bytes()).hexdigest()
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# Which page is this file?
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Match:
    """What `match_file` decided. *kind*: "one" (the page is *page*, its
    verdict *verdict*), "choose" (several pages pass: *choices*, the person
    picks one), "refuse" (*reason*). *verdicts*: every candidate's verdict."""
    kind: str
    page: int = 0
    verdict: object = None
    choices: tuple = ()
    reason: str = ""
    verdicts: dict = field(default_factory=dict)


def page_grids(side: dict) -> "dict[int, object]":
    """{page: Grid} of every page of the side file."""
    from .measure_chart import measure_chart_grid
    out = {}
    n = len(side.get("pages") or [])
    for p in range(1, n + 1):
        g = measure_chart_grid(side, p)
        if g is not None:
            out[p] = g
    return out


def match_file(source, converted_ti3, chart_ti2) -> "Match | None":
    """Match the picked CxF *source* (converted copy *converted_ti3*) to a
    page of the multi-page i1iO chart *chart_ti2*. None when the file is not
    a Measure Chart measurement at all (the ordinary import judges it)."""
    from workflow import measurement_messages as MM
    from . import measure_chart as MC
    f = MC.read_file(source)
    side = MC.read_side(chart_ti2)
    if f is None or side is None or not f.target_cells:
        return None
    grids = page_grids(side)
    cands = [p for p, g in sorted(grids.items())
             if (g.columns, g.rows) == (f.columns, f.rows)]
    if not cands:
        # still None when it is no Measure Chart file (real device values)
        probe = MC.assess_file(source, converted_ti3, chart_ti2,
                               page=min(grids) if grids else 1)
        if probe is None:
            return None
        if not probe.ok and probe.code in ("side",):
            return Match("refuse", reason=probe.reason)
        return Match("refuse", reason=MM.i1io_pages_reason(
            "no-grid", got_cols=f.columns or 0, got_rows=f.rows or 0,
            grids=[(p, g.columns, g.rows) for p, g in sorted(grids.items())]))
    verdicts = {}
    for p in cands:
        v = MC.assess_file(source, converted_ti3, chart_ti2, page=p)
        if v is None:
            return None
        verdicts[p] = v
    passing = [p for p in cands if verdicts[p].ok]
    log.info("i1iO Measure Chart, several pages: %s has the grid of page(s) "
             "%s; passes on %s (%s)", Path(str(source)).name, cands, passing,
             ", ".join(f"page {p}: {verdicts[p].code}" for p in cands))
    if len(passing) == 1:
        p = passing[0]
        return Match("one", page=p, verdict=verdicts[p], verdicts=verdicts)
    if len(passing) > 1:
        return Match("choose", choices=tuple(passing), verdicts=verdicts)
    # nothing passed
    codes = {verdicts[p].code for p in cands}
    if len(cands) == 1 or len(codes) == 1:
        p = cands[0]
        return Match("refuse", page=p if len(cands) == 1 else 0,
                     reason=(MM.i1io_pages_reason(
                         "on-page", page=p, reason=verdicts[p].reason)
                         if len(cands) == 1 else verdicts[p].reason),
                     verdicts=verdicts)
    named = [p for p in cands if verdicts[p].code in NAMED_CODES]
    if len(named) == 1:
        p = named[0]
        return Match("refuse", page=p, reason=MM.i1io_pages_reason(
            "on-page", page=p, reason=verdicts[p].reason), verdicts=verdicts)
    return Match("refuse", reason=MM.i1io_pages_reason(
        "none", pages=cands), verdicts=verdicts)


def page_names(chart_ti2, page: int) -> dict:
    """{"page", "pages", "cols", "rows", "p1", "p2", "p3", "first", "last"}:
    what a person reads on a page's sheet (the corner patches by their
    printed names, its strips' first and last names)."""
    from .measure_chart import read_side
    side = read_side(chart_ti2) or {}
    g = page_grids(side).get(page)
    if g is None:
        return {"page": page, "pages": page_count(chart_ti2)}
    return {"page": page, "pages": page_count(chart_ti2),
            "cols": g.columns, "rows": g.rows, "p1": g.aim[0],
            "p2": g.aim[1], "p3": g.aim[2],
            "labelled": bool(side.get("labels_printed", True))}


# ---------------------------------------------------------------------------
# The stored pages
# ---------------------------------------------------------------------------

def _keywords(path) -> dict:
    """The header keywords of a CGATS file (values unquoted)."""
    out = {}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for n, line in enumerate(fh):
                s = line.strip()
                if s == "BEGIN_DATA_FORMAT" or n > 400:
                    break
                m = re.match(r'^([A-Z_0-9]+)\s+"([^"]*)"\s*$', s)
                if m and m.group(1) != "KEYWORD":
                    out[m.group(1)] = m.group(2)
    except OSError:
        pass
    return out


@dataclass(frozen=True)
class StoredPage:
    page: int
    path: Path
    condition: str
    instrument: str
    device: str
    source_name: str
    source_sha: str
    current: bool          # made from the run's chart as it is now


@dataclass(frozen=True)
class PagesState:
    total: int
    filled: dict           # page -> StoredPage (current ones only)
    stale: tuple = ()      # paths of pages made from an earlier chart

    @property
    def missing(self) -> "list[int]":
        return [p for p in range(1, self.total + 1) if p not in self.filled]

    @property
    def complete(self) -> bool:
        return self.total > 1 and not self.missing

    @property
    def any(self) -> bool:
        return bool(self.filled)


_PAGE_RE = re.compile(r"^page(\d+)$")


def pages_state(run, chart_ti2) -> PagesState:
    """What the run holds of the chart's pages (`Run.i1io_pages_dir`). A page
    file whose chart checksum is not the run's chart now is *stale*: made
    from an earlier chart, not counted."""
    total = page_count(chart_ti2)
    d = run.i1io_pages_dir
    filled, stale = {}, []
    if not d.is_dir():
        return PagesState(total, filled, ())
    sha = chart_sha256(chart_ti2)
    for f in sorted(d.glob("page*.ti3")):
        m = _PAGE_RE.match(f.stem)
        if not m:
            continue
        k = int(m.group(1))
        kw = _keywords(f)
        cur = bool(sha) and kw.get(CHART_SHA_KEYWORD) == sha and 1 <= k <= total
        src = kw.get(SOURCE_KEYWORD, "")
        name, _, ssha = src.rpartition(" sha256=")
        sp = StoredPage(k, f, kw.get("MEASUREMENT_CONDITION", "").upper(),
                        kw.get("CHROMIQ_I1P_INSTRUMENT", ""),
                        kw.get(DEVICE_KEYWORD, ""), name or src, ssha, cur)
        if cur:
            filled[k] = sp
        else:
            stale.append(f)
    return PagesState(total, filled, tuple(stale))


def device_of(source) -> str:
    """A short checksum of the instrument's serial number in the CxF
    *source* ("" when it does not say): enough to tell two instruments apart
    without keeping the serial itself."""
    import xml.etree.ElementTree as ET
    try:
        root = ET.parse(str(source)).getroot()
    except (ET.ParseError, OSError):
        return ""
    for el in root.iter():
        if el.tag.rsplit("}", 1)[-1] == "CustomAttributes":
            s = (el.get("MeasurementDeviceSerialNumber") or "").strip()
            if s:
                return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]
    return ""


@dataclass(frozen=True)
class Facts:
    """The measuring facts of one page's file that must agree across pages."""
    condition: str
    instrument: str
    device: str


def facts_of(converted_ti3, source) -> Facts:
    kw = _keywords(converted_ti3)
    return Facts(kw.get("MEASUREMENT_CONDITION", "").upper(),
                 kw.get("CHROMIQ_I1P_INSTRUMENT", ""), device_of(source))


def mismatch(a: Facts, b: Facts) -> str:
    """"condition", "instrument" or "" when *a* and *b* may be one
    measurement. The serial checksum is compared only where both say one."""
    if a.condition != b.condition:
        return "condition"
    if a.instrument != b.instrument:
        return "instrument"
    if a.device and b.device and a.device != b.device:
        return "instrument"
    return ""


def stored_facts(sp: StoredPage) -> Facts:
    return Facts(sp.condition, sp.instrument, sp.device)


def _insert_keywords(text: str, pairs) -> str:
    lines = text.splitlines()
    at = 1 if lines and lines[0].strip().startswith("CTI3") else 0
    add = []
    for k, v in pairs:
        add += [f'KEYWORD "{k}"', f'{k} "{v}"']
    lines[at:at] = add
    return "\n".join(lines) + "\n"


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def store_page(run, chart_ti2, page: int, filed_ti3, source,
               total: int) -> Path:
    """Store the filed copy *filed_ti3* of one page as the run's page *page*
    (`Run.i1io_page_ti3`), in one step. A page file already there, and any
    page made from an earlier chart, is moved to the run's ``old/`` first
    (`Run.archive_to_old`). Returns the stored path."""
    dst = run.i1io_page_ti3(page)
    st = pages_state(run, chart_ti2)
    old = [p for p in (dst,) if p.exists()] + list(st.stale)
    if old:
        run.archive_to_old(old)
    text = Path(str(filed_ti3)).read_text(encoding="utf-8")
    text = _insert_keywords(text, [
        (PAGE_KEYWORD, f"{page} of {total}"),
        (CHART_SHA_KEYWORD, chart_sha256(chart_ti2)),
        (SOURCE_KEYWORD, f"{Path(str(source)).name} sha256="
                         f"{file_sha256(source)}"),
        (DEVICE_KEYWORD, device_of(source)),
    ])
    _atomic_write(dst, text)
    log.info("i1iO Measure Chart: page %d of %d stored as %s", page, total,
             dst)
    return dst


def _chart_order(chart_ti2) -> "list[str]":
    from core.text_io import read_text
    from workflow.measurement_pairing import _first_table
    t = _first_table(read_text(Path(str(chart_ti2)), lenient=True))
    if t is None or "SAMPLE_ID" not in t[0]:
        return []
    i = t[0].index("SAMPLE_ID")
    return [ln.split()[i].strip('"') for ln in t[1]]


_DROP_KEYS = (PAGE_KEYWORD, SOURCE_KEYWORD, "CHROMIQ_PAIRED_BY_I1IO_GRID",
              "CHROMIQ_I1IO_GRID_COLOURS")


def merge_pages(run, chart_ti2, out_ti3) -> int:
    """Merge every stored page of the run into ONE measurement at *out_ti3*
    (the converted copy the import then files), in the chart's order.
    Returns the rows written; 0 when the pages do not make one whole
    measurement of this chart (a page missing or made from another chart,
    their fields, condition or instrument differ, a patch missing or twice):
    nothing is written then."""
    from core.text_io import read_text
    from workflow.measurement_pairing import _first_table
    from .measure_chart import side_file_for
    st = pages_state(run, chart_ti2)
    if not st.complete:
        return 0
    order = _chart_order(chart_ti2)
    if not order:
        return 0
    pages = [st.filled[p] for p in range(1, st.total + 1)]
    f0 = stored_facts(pages[0])
    if any(mismatch(f0, stored_facts(sp)) for sp in pages[1:]):
        return 0
    fields, rows_by_id, head, colours = None, {}, None, []
    for sp in pages:
        text = read_text(sp.path, lenient=True)
        t = _first_table(text)
        if t is None:
            return 0
        flds, rows = t
        if fields is None:
            fields = flds
            head = text
        elif flds != fields:
            return 0
        if "SAMPLE_ID" not in flds:
            return 0
        si = flds.index("SAMPLE_ID")
        for ln in rows:
            sid = ln.split()[si].strip('"')
            if sid in rows_by_id:
                return 0
            rows_by_id[sid] = ln
        colours.append(f"page {sp.page} "
                       + _keywords(sp.path).get("CHROMIQ_I1IO_GRID_COLOURS",
                                                "n/a"))
    if set(rows_by_id) != set(order) or len(rows_by_id) != len(order):
        return 0
    # the header of page 1 without its page-only keywords
    out = []
    for ln in head.splitlines():
        s = ln.strip()
        if s.startswith("NUMBER_OF_FIELDS"):
            break
        m = re.match(r'^KEYWORD\s+"([^"]+)"', s)
        if m and m.group(1) in _DROP_KEYS:
            continue
        m = re.match(r'^([A-Z_0-9]+)\s+"', s)
        if m and m.group(1) in _DROP_KEYS:
            continue
        out.append(ln)
    text = "\n".join(out).rstrip("\n") + "\n\n" + (
        f"NUMBER_OF_FIELDS {len(fields)}\nBEGIN_DATA_FORMAT\n"
        + " ".join(fields) + " \nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {len(order)}\nBEGIN_DATA\n"
        + "\n".join(rows_by_id[s] for s in order) + "\nEND_DATA\n")
    text = _insert_keywords(text, [
        ("CHROMIQ_PAIRED_BY_I1IO_GRID",
         f"{side_file_for(chart_ti2).name} pages 1-{st.total}"),
        ("CHROMIQ_I1IO_GRID_COLOURS", "; ".join(colours)),
        (PAGES_KEYWORD, str(st.total)),
    ])
    _atomic_write(Path(str(out_ti3)), text)
    log.info("i1iO Measure Chart: %d pages merged into %s (%d readings)",
             st.total, out_ti3, len(order))
    return len(order)
