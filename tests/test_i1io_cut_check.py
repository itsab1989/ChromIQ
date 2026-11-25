"""The independent cut check (`scripts/i1io_cut_check.py`): by image analysis alone it measures the
crosses, cut lines and patches of a printed i1iO page and compares them with the side file's
millimetres. It must accept what is to scale and refuse what is not: 1 % too large; the cut line
anywhere else; the patches moved along or across the strips, by a fraction, by a spacer, by a
pitch; a piece left blank; another chart's colours. PDF pages too."""
from __future__ import annotations

import ast
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from scripts import i1io_cut_check as C
from tests.i1io_table import bed_sim as B

DPI = 300


@pytest.fixture(scope="module")
def chart(tmp_path_factory):
    return B.build_chart(tmp_path_factory.mktemp("cut"), count=200, dpi=DPI)


def _save(path, px, dpi=(DPI, DPI)):
    Image.fromarray(px).save(path, dpi=dpi)
    return path


def _side(chart):
    return chart.run.dir / (chart.run.chart_ti2.name[:-4] + ".i1io.json")


def test_it_imports_nothing_of_the_app():
    tree = ast.parse(Path(C.__file__).read_text(encoding="utf-8"))
    names = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not any(n.split(".")[0] in ("workflow", "core", "ui", "data") for n in names)


def test_a_page_as_printed_is_to_scale(chart):
    res = C.check(chart.tiffs[0], _side(chart))
    assert res["ok"], res
    p = res["pieces"][0]
    assert p["cross_error_mm"] < 0.1 and p["patch_edges"] > 150 and p["colour_order"] > 0.99 and p["turned_deg"] == 0.0


def test_one_per_cent_larger_is_refused(chart, tmp_path):
    im = Image.open(chart.tiffs[0]).convert("RGB")
    big = im.resize((int(im.width * 1.01), int(im.height * 1.01)), Image.NEAREST)
    _save(tmp_path / "big.tif", np.asarray(big))
    res = C.check(tmp_path / "big.tif", _side(chart))
    assert not res["ok"]
    assert any("cross distances" in p for p in res["pieces"][0]["problems"])


def _page(chart):
    return np.asarray(Image.open(chart.tiffs[0]).convert("RGB")).copy()


def _px(mm):
    return int(round(mm / 25.4 * DPI))


def _sheet(chart, line_off_mm=0.0, second=None, line=True):
    """Two copies of the page side by side (*second*: the second's picture) with a 0.25 mm grey
    line between them, *line_off_mm* off its place."""
    a = _page(chart)
    b = a if second is None else second
    sh = np.concatenate([a, b], axis=1)
    if line:
        lw = max(1, _px(0.25))
        x = a.shape[1] + _px(line_off_mm)
        sh[:, x - lw // 2: x - lw // 2 + lw] = 153
    return sh


def _block_moved(chart, dx_mm=0.0, dy_mm=0.0):
    """The page with its patches (and nothing else) moved: the crosses, labels and paper stay."""
    a, doc = _page(chart), json.loads(_side(chart).read_text(encoding="utf-8"))
    w, h = doc["patch_mm"]
    cs = [q["centre_mm"] for st in doc["pages"][0]["strips"] for q in st["patches"]]
    x0, x1 = _px(min(c[0] for c in cs) - w / 2), _px(max(c[0] for c in cs) + w / 2)
    y0, y1 = _px(min(c[1] for c in cs) - h / 2), _px(max(c[1] for c in cs) + h / 2)
    block = a[y0:y1, x0:x1].copy()
    a[y0:y1, x0:x1] = 255
    dx, dy = _px(dx_mm), _px(dy_mm)
    a[y0 + dy:y1 + dy, x0 + dx:x1 + dx] = block
    return a


@pytest.mark.parametrize("dx,dy", [
    (0.3, 0.0), (0.5, 0.0), (2.0, 0.0), (3.0, 0.0), (4.0, 0.0), (8.0, 0.0), (-8.0, 0.0),
    (0.0, 0.3), (0.0, 0.5), (0.0, 1.0), (0.0, -1.0), (0.0, 2.0), (0.0, 5.0), (0.0, 11.0),
    (0.0, -11.0)],
    ids=lambda v: str(v))
def test_patches_moved_on_the_page_are_refused(chart, tmp_path, dx, dy):
    """Across the strips and along them, by less than a spacer, by a spacer (1 mm), by a strip
    (8 mm), by a pitch (11 mm)."""
    _save(tmp_path / "p.tif", _block_moved(chart, dx, dy))
    res = C.check(tmp_path / "p.tif", _side(chart))
    assert not res["ok"], (dx, dy)


def test_the_page_put_together_again_is_accepted(chart, tmp_path):
    _save(tmp_path / "p.tif", _block_moved(chart))
    assert C.check(tmp_path / "p.tif", _side(chart))["ok"]


@pytest.mark.parametrize("off", (-5.1, -2.0, -0.4, 0.4, 2.0, 5.0, 5.1))
def test_a_cut_line_in_the_wrong_place_is_refused(chart, tmp_path, off):
    _save(tmp_path / "s.tif", _sheet(chart, line_off_mm=off))
    res = C.check(tmp_path / "s.tif", _side(chart), pages=[1, 1])
    assert not res["ok"]
    assert any("cut line" in p for q in res["pieces"] for p in q["problems"])


def test_no_cut_line_and_a_blank_piece_are_refused(chart, tmp_path):
    _save(tmp_path / "n.tif", _sheet(chart, line=False))
    assert not C.check(tmp_path / "n.tif", _side(chart), pages=[1, 1])["ok"]
    blank = np.full_like(_page(chart), 255)
    _save(tmp_path / "b.tif", _sheet(chart, second=blank))
    res = C.check(tmp_path / "b.tif", _side(chart), pages=[1, 1])
    assert not res["ok"] and "1 pieces with crosses found, 2 pages" in res["problems"][0]
    # a sheet whose last piece is meant to be empty is asked for with one page
    assert C.check(tmp_path / "b.tif", _side(chart), pages=[1])["ok"]


def test_another_charts_colours_are_refused(chart, tmp_path):
    """The same grid, another patch set: to scale, and not this chart."""
    other = B.build_chart(tmp_path, name="Other", colours=B.patch_set(200, seed=99), seed=9,
                          dpi=DPI)
    res = C.check(other.tiffs[0], _side(chart))
    assert not res["ok"]
    assert any("colours" in p for p in res["pieces"][0]["problems"])
    assert C.check(other.tiffs[0], _side(other))["ok"]


def test_a_pdf_page_is_measured_like_the_picture(tmp_path):
    ch = B.build_chart(tmp_path, count=200, dpi=150, export_pdf=True)
    pdf = next(ch.run.dir.glob("*.pdf"))
    res = C.check(pdf, _side(ch), dpi=300.0)
    assert res["ok"], res
    assert res["page_mm"] == pytest.approx([210.0, 297.0], abs=0.2)
    doc = json.loads(_side(ch).read_text(encoding="utf-8"))
    for st in doc["pages"][0]["strips"]:
        for q in st["patches"]:
            q["centre_mm"][0] += 0.5
    (tmp_path / "moved.json").write_text(json.dumps(doc), encoding="utf-8")
    assert not C.check(pdf, tmp_path / "moved.json", dpi=300.0)["ok"]


def test_two_pieces_are_found_by_their_cut_line(chart, tmp_path):
    _save(tmp_path / "s.tif", _sheet(chart))
    res = C.check(tmp_path / "s.tif", _side(chart), pages=[1, 1])
    assert len(res["pieces"]) == 2 and res["ok"], res
    assert len(res["cut_x_mm"]) == 1 and abs(res["cut_x_mm"][0] - 210.0) < 0.15
    assert res["cut_y_mm"] == []


def test_a_turned_piece_is_measured_and_its_turn_said(chart, tmp_path):
    _save(tmp_path / "s.tif", np.rot90(_sheet(chart)).copy())
    res = C.check(tmp_path / "s.tif", _side(chart), pages=[1, 1])
    assert res["ok"], res
    assert {abs(p["turned_deg"]) for p in res["pieces"]} == {90.0}
    assert len(res["cut_y_mm"]) == 1


def test_patches_that_do_not_lie_where_the_side_file_says_are_refused(chart, tmp_path):
    doc = json.loads(_side(chart).read_text(encoding="utf-8"))
    for st in doc["pages"][0]["strips"]:
        for q in st["patches"]:
            q["centre_mm"][1] += 0.3
    (tmp_path / "moved.json").write_text(json.dumps(doc), encoding="utf-8")
    res = C.check(chart.tiffs[0], tmp_path / "moved.json")
    assert not res["ok"]
    assert any("patch edge" in p for p in res["pieces"][0]["problems"])
