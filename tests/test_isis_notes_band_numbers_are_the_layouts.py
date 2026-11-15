"""Every number the i1iSis notes band prints is the FINAL layout's, for the
page it is printed on (the owner, 2026-11-15, on 4.3.38: Create Chart said
896 patches everywhere, 32 patches per strip, 28 strips, while the band on
the sheet said "560 patches" and "strips on page: 32").

The band was handed no patch count, so it printed the notes design's SAMPLE
value (560), and it printed the ROWS as "strips". These tests build real
charts through `build_chart`, catch the values the band is drawn from and
read its text through `raster.notes_rows`, the one function the renderer
sets its rows with, then compare each number with what the Create Chart
panel reads: the .ti2's NUMBER_OF_SETS, STEPS_IN_PASS and passes per page.
"""
from __future__ import annotations

import re
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


#: name: (patches, paper, model, place, extra build_chart kwargs)
CASES = {
    # the owner's case: Guided, A4 portrait, one page, band in the header
    "guided A4, header (the report)": (896, "A4", "", "header", {}),
    "guided A4, trailer": (896, "A4", "", "trailer", {}),
    "two pages, header": (957, "A4", "", "header", {}),
    "two pages, trailer": (957, "A4", "", "trailer", {}),
    "manual 8 mm, two pages": (957, "A4", "", "header",
                               {"patch_w": 8.0, "patch_h": 8.0}),
    "XL A3, header": (1617, "A3", "xl", "header", {}),
    "XL A3, trailer, two pages": (2400, "A3", "xl", "trailer", {}),
    "XL, empty columns on the last page": (100, "Letter", "xl", "header",
                                           {"patch_w": 20.0,
                                            "patch_h": 20.0}),
}


def _rows(raster, ctx):
    """The band's rows for *ctx*, as the renderer sets them. Up to 4.3.38
    the renderer built them inline (same format, no `notes_rows`), which is
    reproduced here so this test fails on the old NUMBERS, not on a name."""
    if hasattr(raster, "notes_rows"):
        return raster.notes_rows(raster.notes_context(ctx))
    c = dict(raster._notes_sample_ctx())
    c.update({k: str(v) for k, v in ctx.items() if v not in (None, "")})
    return (f"{c['count']} patches  ·  {c['instrument']}  ·  {c['paper']}  ·  "
            f"colour management: OFF",
            f"{c['page']}  ·  strips on page: {c['strips']}", [],
            [("text", f"profile name: {c['project']}")])


def _band_texts(monkeypatch, tmp_path, n, paper, model, place, extra):
    from workflow.layout_engine import chart, raster
    seen: list[dict] = []
    real = C.band_image

    def spy(box, dpi, **kw):
        seen.append(dict(kw.get("ctx") or {}))
        return real(box, dpi, **kw)

    monkeypatch.setattr(C, "band_image", spy)
    ti1 = _ti1(tmp_path / "c.ti1", n)
    chart.build_chart(ti1, tmp_path / "band", instrument="XRISIS",
                      paper=paper, dpi=60, project="isistest",
                      isis_model=model, isis_notes_band=True,
                      isis_notes_place=place, **extra)
    ti2 = (tmp_path / "band.ti2").read_text(encoding="utf-8")
    rows = [_rows(raster, c) for c in seen]
    return ti2, rows


def _panel_numbers(ti2_path: Path):
    """What the Create Chart panel reads (`TabChart._update_layout_info`)."""
    from core.strip_utils import parse_passes_per_page
    txt = ti2_path.read_text(encoding="utf-8")
    total = int(re.search(r"NUMBER_OF_SETS\s+(\d+)", txt).group(1))
    per_strip = int(re.search(r'STEPS_IN_PASS\s+"?(\d+)"?', txt).group(1))
    return total, per_strip, parse_passes_per_page(ti2_path) or []


@pytest.mark.parametrize("case", sorted(CASES))
def test_every_number_in_the_band_is_the_final_layouts(case, monkeypatch,
                                                       tmp_path):
    n, paper, model, place, extra = CASES[case]
    _ti2, rows = _band_texts(monkeypatch, tmp_path, n, paper, model, place,
                             extra)
    total, per_strip, passes = _panel_numbers(tmp_path / "band.ti2")
    assert rows, "no notes band was drawn"
    assert len(rows) == len(passes), (case, len(rows), passes)
    instrument = "i1iSis XL" if model == "xl" else "i1iSis"
    for page, (left1, right1, row2, row3) in enumerate(rows):
        printed = f"{left1}  {right1}"
        assert left1.startswith(f"{total} patches  ·  {instrument}  ·  "), \
            (case, page, left1)
        assert f"page {page + 1}/{len(passes)}" in right1, (case, page, right1)
        assert f"strips on page: {passes[page]}" in right1, \
            (case, page, right1, passes)
        assert f"patches per strip: {per_strip}" in right1, \
            (case, page, right1)
        # no number in row 1 that is not one of the layout's
        allowed = {str(total), str(page + 1), str(len(passes)),
                   str(passes[page]), str(per_strip)}
        # (the paper's own name may carry digits: "A4 portrait")
        paper_name = left1.split("  ·  ")[2]
        stray = [x for x in re.findall(r"\d+", printed.replace(paper_name, ""))
                 if x not in allowed and x != "1"]
        assert not stray, (case, page, printed, stray)
        assert "XRISIS" not in printed
        assert ("text", "profile name: isistest") in row3


def test_the_band_without_a_layout_uses_the_sheets_grid():
    """`band_numbers` without the engine's layout gives the same values from
    the sheet's own grid (the grid `build_chart` proves equal to it)."""
    _o, g, sheet = C.layout_for(896, 210, 297, {C.COUNT_KEY: 896,
                                                C.BAND_KEY: True})
    got = C.band_numbers(sheet, 0)
    assert got["count"] == "896"
    assert got["strips"] == str(g.C)
    assert got["per_strip"] == str(g.R)
    assert got["page"] == f"page 1/{g.P}"


def test_the_clip_border_notes_are_unchanged_without_per_strip():
    """The engine's own clip-border notes (i1Pro / i1iO charts) are given no
    `per_strip`, and print exactly what they printed before."""
    from workflow.layout_engine import raster
    c = raster.notes_context({"count": 560, "strips": 12, "page": "page 1/2"})
    _l, right1, _r2, _r3 = raster.notes_rows(c)
    assert right1 == "page 1/2  ·  strips on page: 12"
