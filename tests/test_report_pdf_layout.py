"""PDF pagination of the measurement report (#PDF4 + the orphaned heading).

The real PDFs were checked across six scenarios with a page-level scanner on
2026-08-10 (1/2/4/10 dates, summary-only, profiling) — these tests pin the
pagination helper itself, at the Qt layout level, so the gate catches a
regression without needing a PDF parser.
"""
from PyQt6.QtGui import QTextDocument, QTextTable

from ui.dialogs.measurement_report_dialog import _paginate_tables

BODY_H = 400.0


def _doc(html: str) -> QTextDocument:
    doc = QTextDocument()
    doc.setHtml(html)
    doc.setPageSize(__import__("PyQt6.QtCore", fromlist=["QSizeF"])
                    .QSizeF(500.0, BODY_H))
    return doc


def _rows(n: int) -> str:
    return "".join(f"<tr><td>patch {i}</td><td>{i}.00</td></tr>"
                   for i in range(n))


def _tables(doc: QTextDocument) -> "list[QTextTable]":
    found, stack = [], [doc.rootFrame()]
    while stack:
        for ch in stack.pop().childFrames():
            stack.append(ch)
            if isinstance(ch, QTextTable):
                found.append(ch)
    return found


def _page_of_top(doc: QTextDocument, rect_top: float) -> int:
    return int(rect_top // BODY_H)


def test_straddling_table_moves_with_its_heading(qapp):
    """Filler pushes the heading near the page bottom and its table across the
    boundary: after pagination the heading and the table's top share a page —
    the heading is never left alone at the foot of the previous page."""
    html = ("<p>" + "filler<br>" * 18 + "</p>"
            "<h3>Worst patches</h3>"
            f"<table>{_rows(14)}</table>")
    doc = _doc(html)
    _paginate_tables(doc, BODY_H)
    lay = doc.documentLayout()
    (table,) = _tables(doc)
    t_page = _page_of_top(doc, lay.frameBoundingRect(table).top())
    heading = doc.findBlock(table.firstPosition() - 1)
    assert heading.text().strip() == "Worst patches"
    h_page = _page_of_top(doc, lay.blockBoundingRect(heading).top())
    assert h_page == t_page, (h_page, t_page)


def test_fitting_table_is_left_alone(qapp):
    """A table comfortably inside page 1 gets no break — pagination must not
    push content around when nothing straddles."""
    html = "<h3>Worst patches</h3>" + f"<table>{_rows(4)}</table>"
    doc = _doc(html)
    _paginate_tables(doc, BODY_H)
    lay = doc.documentLayout()
    (table,) = _tables(doc)
    assert _page_of_top(doc, lay.frameBoundingRect(table).top()) == 0
    heading = doc.findBlock(table.firstPosition() - 1)
    assert _page_of_top(doc, lay.blockBoundingRect(heading).top()) == 0


def test_table_taller_than_a_page_still_flows(qapp):
    """A table that cannot fit any page must not loop or jump — it flows, and
    pagination terminates."""
    html = "<h3>Worst patches</h3>" + f"<table>{_rows(80)}</table>"
    doc = _doc(html)
    _paginate_tables(doc, BODY_H)          # must terminate
    assert len(_tables(doc)) == 1


def test_two_straddlers_resolve_independently(qapp):
    """Several sections in sequence: every table ends up on one page with its
    heading, no matter how the earlier pushes shifted the later sections."""
    section = "<h3>Cube corners</h3>" + f"<table>{_rows(12)}</table>"
    html = ("<p>" + "filler<br>" * 10 + "</p>") + section + section + section
    doc = _doc(html)
    _paginate_tables(doc, BODY_H)
    lay = doc.documentLayout()
    for table in _tables(doc):
        r = lay.frameBoundingRect(table)
        if r.height() >= BODY_H - 1:
            continue
        assert int(r.top() // BODY_H) == int((r.bottom() - 1) // BODY_H), \
            "table still straddles a page"
        heading = doc.findBlock(table.firstPosition() - 1)
        if heading.text().strip():
            assert _page_of_top(doc, lay.blockBoundingRect(heading).top()) \
                == _page_of_top(doc, r.top())


def test_wrapped_legend_gets_its_own_rows(qapp):
    """At the PDF grab width the five ΔE labels wrap to two legend rows; at a
    wide window they fit one. The row count is what moves the plot down, so a
    wrapped legend can never be painted across the graph."""
    from PyQt6.QtGui import QColor, QFont, QFontMetricsF
    from ui.dialogs.measurement_report_dialog import _TrendChart
    chart = _TrendChart()
    labels = ["Average ΔE, all patches", "Average ΔE, lowest 95%",
              "Average ΔE, highest 5%", "Maximum ΔE, all patches",
              "Maximum ΔE, lowest 95%"]
    chart._metrics = [(l, QColor("red"), lambda pt: None) for l in labels]
    font = QFont()
    font.setPixelSize(10)
    fm = QFontMetricsF(font)
    narrow = chart._legend_rows(fm, 40.0, 640 - 52.0)
    wide = chart._legend_rows(fm, 40.0, 1600 - 52.0)
    assert narrow >= 2, narrow
    assert wide == 1, wide


def test_trend_chart_paints_at_pdf_width(qapp):
    """Smoke: the PDF-sized grab (640×176, light, two points) renders without
    error with the wrapped legend making room for itself."""
    from PyQt6.QtGui import QColor
    from ui.dialogs.measurement_report_dialog import _TrendChart
    chart = _TrendChart()
    chart.resize(640, 176)
    pts = [{"date": "2026-08-01", "v": 1.0}, {"date": "2026-08-02", "v": 2.0}]
    metrics = [(lbl, QColor("red"), (lambda pt: pt["v"]))
               for lbl in ["Average ΔE, all patches", "Average ΔE, lowest 95%",
                           "Average ΔE, highest 5%", "Maximum ΔE, all patches",
                           "Maximum ΔE, lowest 95%"]]
    chart.set_data(pts, metrics, dark=False, thresholds=(2.0, 3.0))
    img = chart.grab().toImage()
    assert not img.isNull() and img.width() == 640
