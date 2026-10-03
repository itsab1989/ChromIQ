"""#182 (d): a swatch's two grey side bars are equal, on screen and in the PDF.

Basti, 2026-10-01 (grey_bars.png): the bar left of a colour patch is thinner
than the bar right of it. Measured 3 : 10 : 4 px on screen (dpr 2) and in the
app's PDFs (2.25 : 7.5 : 3.0 pt): the swatch was spans of non-breaking spaces,
whose backgrounds Qt rounds OUT to whole pixels and paints left bar, colour,
right bar, each over the one before. It is now a table of three cells, the
bars `SWATCH_EDGE_PX` each, and the colour `SWATCH_COLOUR_PX`, twice the old
10 px (Basti, 2026-10-02: "like twice the width").

Measured here exactly as a reader sees it: the swatch drawn by QTextDocument
at eight sub-pixel positions, at dpr 1 and 2, and through QPdfWriter at the
report's 96 dpi (rasterised with PyMuPDF), counting each run of pixels.

MUTATIONS, each proved red (MUTATIONS.md of H_impl_182):
* the old span `_swatch` back: every symmetry test red;
* `SWATCH_COLOUR_PX = 10` (the old width): the width test red;
* the paper-white line with the swatch inline again (a `<div>`): the
  no-swatch-inside-a-line test red.
"""
from __future__ import annotations

import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication  # noqa: E402

_COLOUR = "#d9534f"
_PREFIXES = ["", "i", "ii", "l", "W", "Wi", "x.", "Mm"]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _doc(body: str):
    from PyQt6.QtGui import QTextDocument
    fam = QApplication.font().family().replace("'", "")
    d = QTextDocument()
    d.setDocumentMargin(0)
    d.setHtml(f"<div style=\"font-family:'{fam}';font-size:12px\">"
              f"<table cellspacing='0' cellpadding='0'><tr>"
              f"<td>{body}</td></tr></table></div>")
    return d


def _runs(row, edge, col):
    out, cur, n = [], None, 0
    for c in row + [None]:
        k = "E" if c == edge else ("C" if c == col else ".")
        if k == cur:
            n += 1
        else:
            if cur in ("E", "C"):
                out.append((cur, n))
            cur, n = k, 1
    return out


def _raster(body: str, dpr: int, edge: str):
    from PyQt6.QtGui import QColor, QImage, QPainter
    d = _doc(body)
    w, h = int(d.size().width()) + 2, int(d.size().height()) + 2
    img = QImage(w * dpr, h * dpr, QImage.Format.Format_RGB32)
    img.setDevicePixelRatio(dpr)
    img.fill(0xFFFFFFFF)
    p = QPainter(img)
    d.drawContents(p)
    p.end()
    e = QColor(edge).rgb() & 0xFFFFFF
    c = QColor(_COLOUR).rgb() & 0xFFFFFF
    for y in range(img.height()):
        r = _runs([img.pixel(x, y) & 0xFFFFFF for x in range(img.width())], e, c)
        if [k for k, _n in r] == ["E", "C", "E"]:
            return [n for _k, n in r]
    return None


def _pdf(body: str, path, edge: str):
    import pymupdf
    from PyQt6.QtCore import QMarginsF
    from PyQt6.QtGui import QColor, QPageSize, QPainter, QPdfWriter
    d = _doc(body)
    wr = QPdfWriter(str(path))
    wr.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    wr.setPageMargins(QMarginsF(15, 15, 15, 15))
    wr.setResolution(96)
    p = QPainter(wr)
    d.drawContents(p)
    p.end()
    pm = pymupdf.open(str(path))[0].get_pixmap(dpi=96 * 4)
    e, c = QColor(edge), QColor(_COLOUR)
    ev, cv = (e.red(), e.green(), e.blue()), (c.red(), c.green(), c.blue())
    for y in range(min(pm.height, 400)):
        row = [pm.pixel(x, y)[:3] for x in range(min(pm.width, 600))]
        r = _runs(row, ev, cv)
        if [k for k, _n in r] == ["E", "C", "E"]:
            return [n / 4 for _k, n in r]
    return None


@pytest.mark.parametrize("dpr", [1, 2])
def test_the_bars_are_equal_on_screen_at_every_position(qapp, dpr):
    from ui.dialogs import measurement_report_dialog as M
    for palette in ("light", "dark"):
        M._C.clear()
        M._C.update(M._REPORTS[palette])
        edge = M._C["swatch_edge"]
        seen = set()
        for pre in _PREFIXES:
            got = _raster(f"<span>{pre}</span>" + M._swatch(_COLOUR), dpr, edge)
            assert got is not None, (palette, pre, "no swatch drawn")
            seen.add(tuple(got))
            left, _col, right = got
            assert left == right, (palette, dpr, pre, got)
        assert seen == {(M.SWATCH_EDGE_PX * dpr, M.SWATCH_COLOUR_PX * dpr,
                         M.SWATCH_EDGE_PX * dpr)}, seen
    M._C.clear()
    M._C.update(M._LIGHT_REPORT)


def test_the_bars_are_equal_in_the_pdf(qapp, tmp_path):
    from ui.dialogs import measurement_report_dialog as M
    M._C.clear()
    M._C.update(M._LIGHT_REPORT)
    for i, pre in enumerate(_PREFIXES):
        got = _pdf(f"<span>{pre}</span>" + M._swatch(_COLOUR),
                   tmp_path / f"s{i}.pdf", M._C["swatch_edge"])
        assert got is not None, pre
        assert got[0] == got[2], (pre, got)
        assert got == [M.SWATCH_EDGE_PX, M.SWATCH_COLOUR_PX,
                       M.SWATCH_EDGE_PX], (pre, got)


def test_the_colour_is_twice_the_old_width():
    from ui.dialogs import measurement_report_dialog as M
    assert M.SWATCH_COLOUR_PX == 20
    assert M.SWATCH_EDGE_PX == 3


def test_no_swatch_sits_inside_a_line_of_text(qapp, tmp_path):
    """The paper-white and darkest-black lines: the swatch is a table, so it
    must be the whole content of a cell, never part of a `<div>` of text
    (inline, Qt breaks it onto a line of its own, +30 px per line)."""
    from PyQt6.QtCore import QSettings

    from core.settings import AppSettings
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    st = AppSettings()
    st._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    st.set("custom_output_path", str(tmp_path))
    dlg = MeasurementReportDialog(st, None)
    try:
        rep = {"schema": 7, "created": "2026-09-11T10:00:00",
               "_origin_dir": str(tmp_path),
               "paper_white": {"hex": "#f4f4f0", "loc": "A1",
                               "lab": [96.1, 0.2, -1.3]},
               "max_black": {"hex": "#202020", "loc": "B2",
                                 "lab": [12.0, 0.1, 0.4]},
               "corners": [{"name": "R", "present": True, "hex": "#c81e1e",
                            "expected_hex": "#e02020", "de": 3.4,
                            "loc": "C3"}],
               "worst_patches": [{"loc": "D4", "expected_hex": "#102030",
                                  "measured_hex": "#112233", "de": 2.0}]}
        html = dlg._run_detail_html(rep)
    finally:
        dlg.close()
    swatches = re.findall(r"<table cellspacing='0' cellpadding='0'><tr>"
                          r"<td width='\d+' bgcolor=", html)
    assert len(swatches) >= 6, (len(swatches), html[:400])
    for m in re.finditer(r"(.{0,80})<table cellspacing='0' cellpadding='0'>"
                         r"<tr><td width='\d+' bgcolor=", html):
        before = m.group(1)
        assert re.search(r"<td[^>]*>\s*$", before), (
            "a swatch inside a line of text: " + before)
    assert "White" in html and "Black" in html
