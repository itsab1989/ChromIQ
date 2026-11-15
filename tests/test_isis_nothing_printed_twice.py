"""Nothing on an i1iSis sheet is printed twice (the owner, 2026-11-15:
*"when the clipborder is turned on the information included in it don't
need to double on the chart ... the wordmark, the name and the page
count"*).

The name line at the top (name · page · small wordmark) leaves out what the
notes band on the SAME page already prints legibly:

* the notes design: its wordmark, and its "profile name" and "page x/y"
  when its text is set at `BAND_TEXT_MIN_MM` or more (the default 24 mm band
  is; a 12 mm band is not, so the name line keeps them);
* "branding": the wordmark only (it has no name or page);
* plain text or an image: nothing.

For every content x position x pages x model: the chart's name, its page
number and the wordmark are each on the page exactly once, and the bar and
the diamonds are where they are with the full name line.
"""
from __future__ import annotations

import itertools
from pathlib import Path

import pytest

from workflow.isis import chart as C


@pytest.fixture(autouse=True)
def isis_on():
    from workflow.isis import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    yield
    support._latched = before


def _ti1(path: Path, n: int) -> Path:
    rows = "\n".join(f"{i + 1} {i % 100:.1f} {(i * 7) % 100:.1f} "
                     f"{(i * 13) % 100:.1f}" for i in range(n))
    path.write_text(
        "CTI1\n\nDESCRIPTOR \"t\"\nCOLOR_REP \"RGB\"\n\n"
        "NUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {n}\nBEGIN_DATA\n{rows}\nEND_DATA\n",
        encoding="utf-8")
    return path


def _build(monkeypatch, tmp_path, *, n, paper, model, place, content,
           height=None, sheet_text=""):
    """Build a real chart; return per page (band ctx, band shows, the
    planned items, the items with the full name line)."""
    from PIL import Image
    from workflow.layout_engine import chart
    pages: dict = {}
    real_band, real_plan = C.band_image, C.plan_page

    def band_spy(box, dpi, **kw):
        pages.setdefault("_ctx", []).append(dict(kw.get("ctx") or {}))
        return real_band(box, dpi, **kw)

    def plan_spy(sheet, page, **kw):
        got = real_plan(sheet, page, **kw)
        full = real_plan(sheet, page, **{**kw, "band_shows": frozenset()})
        pages[page] = (kw.get("band_shows") or frozenset(), got[0], full[0],
                       kw.get("name"))
        return got

    monkeypatch.setattr(C, "band_image", band_spy)
    monkeypatch.setattr(C, "plan_page", plan_spy)
    extra = {}
    if content == "image":
        img = tmp_path / "logo.png"
        Image.new("RGB", (60, 20), (200, 30, 30)).save(img)
        extra["clip_image_path"] = str(img)
    if content == "text":
        extra["clip_text"] = "a line of my own"
    if height is not None:
        extra["isis_notes_height_mm"] = height
    chart.build_chart(_ti1(tmp_path / "c.ti1", n), tmp_path / "chart",
                      instrument="XRISIS", paper=paper, dpi=60,
                      project="Band Test", isis_model=model,
                      isis_notes_band=True, isis_notes_place=place,
                      clip_content_mode=content, chart_text=sheet_text,
                      **extra)
    ctxs = pages.pop("_ctx", [])
    return pages, ctxs


SHEETS = {"A4, 1 page": (896, "A4", ""), "A4, 2 pages": (1792, "A4", ""),
          "XL A3, 1 page": (1617, "A3", "xl"),
          "XL A3, 2 pages": (3300, "A3", "xl")}


@pytest.mark.parametrize("sheet_name", sorted(SHEETS))
@pytest.mark.parametrize("content,place", list(itertools.product(
    ("notes", "branding", "text", "image"), ("header", "trailer"))))
def test_nothing_twice_and_nothing_lost(monkeypatch, tmp_path, sheet_name,
                                        content, place):
    n, paper, model = SHEETS[sheet_name]
    pages, ctxs = _build(monkeypatch, tmp_path, n=n, paper=paper,
                         model=model, place=place, content=content)
    assert pages and len(ctxs) == len(pages)
    for page, (shows, items, full, name) in sorted(pages.items()):
        ctx = ctxs[page]
        line = " ".join(i.text for i in items if i.role == "name_line")
        wordmarks = [i for i in items if i.role == "wordmark"]
        page_txt = f"page {page + 1}/{len(pages)}"
        # what the band holds, by its content
        if content == "notes":
            assert shows == {"wordmark", "name", "page"}
            assert ctx["page"] == page_txt and ctx["project"] == name
        elif content == "branding":
            assert shows == {"wordmark"}
        else:
            assert shows == frozenset()
        # the name and the page: exactly once on the page
        assert (name in line) + ("name" in shows) == 1, (line, shows)
        assert (page_txt in line) + ("page" in shows) == 1, (line, shows)
        assert len(wordmarks) + ("wordmark" in shows) == 1
        # and nothing the instrument looks at has moved
        def where(its, role):
            return [i.box for i in its if i.role == role]
        for role in ("bar", "diamond", "arrow", "outline", "corner",
                     "notes_band", "barcode"):
            assert where(items, role) == where(full, role), role
        assert C.keep_out_violations(
            _sheet_of(n, paper, model, place), items) == []


def _sheet_of(n, paper, model, place):
    from workflow.layout_engine import papers
    w, h = papers.dimensions_mm(paper)
    return C.layout_for(n, w, h, {C.COUNT_KEY: n, C.MODEL_KEY: model,
                                  C.BAND_KEY: True,
                                  C.BAND_PLACE_KEY: place})[2]


def test_a_small_band_keeps_the_name_and_page_in_the_name_line(
        monkeypatch, tmp_path):
    """A 12 mm band sets its text well under the legibility floor: only its
    wordmark counts, the name line keeps the name and the page."""
    pages, _c = _build(monkeypatch, tmp_path, n=896, paper="A4", model="",
                       place="header", content="notes", height=12)
    shows, items, _full, name = pages[0]
    assert shows == {"wordmark"}
    line = " ".join(i.text for i in items if i.role == "name_line")
    assert name in line and "page 1/1" in line
    assert not [i for i in items if i.role == "wordmark"]


def test_the_sheet_text_stays(monkeypatch, tmp_path):
    """Manual's "Sheet text" is not in the band: the name line keeps it."""
    pages, _c = _build(monkeypatch, tmp_path, n=300, paper="A4", model="",
                       place="header", content="notes",
                       sheet_text="my note")
    _shows, items, _full, name = pages[0]
    line = " ".join(i.text for i in items if i.role == "name_line")
    assert "my note" in line and name not in line


def test_without_a_band_the_name_line_is_whole():
    _o, _g, sheet = C.layout_for(896, 210, 297, {C.COUNT_KEY: 896})
    assert C.band_shows(None, {}, (0, 0, 100, 24), 300, "x") == frozenset()
    a = C.plan_page(sheet, 0, name="x", title="x")
    b = C.plan_page(sheet, 0, name="x", title="x", band_shows=frozenset())
    assert [(i.role, i.box, i.text) for i in a[0]] == \
        [(i.role, i.box, i.text) for i in b[0]]
