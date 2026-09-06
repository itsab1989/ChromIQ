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
    from _fontcheck import skip_without_fonts
    skip_without_fonts()                 # page breaks pivot on real line heights
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
    """A legend too narrow for its five ΔE labels takes more than one row; a
    wide one takes exactly one. The row count is what moves the plot down, so a
    wrapped legend can never be painted across the graph.

    THE NARROW WIDTH IS MEASURED, NOT ASSUMED, AND THAT IS THE CHANGE HERE.
    This asked for two rows at the 640 px PDF grab width, a figure taken on the
    Windows offscreen gate with an EMPTY font database, where every glyph is a
    box of `pixelSize` and five labels could not possibly fit. With ChromIQ's
    own fonts registered the same five labels measure 82 + 84 + 84 + 90 + 92 =
    **432 px** at `pixelSize(10)` and fit the 588 px the PDF grab leaves on ONE
    row — so `narrow >= 2` failed on `assert 1 >= 2` at a width where the app
    is behaving correctly. Measured on this tree, 2026-09-06, rows against the
    available width: 200 → 5, 260 → 3, 340 → 2, 560 → 2, 600 → 1.

    The wrapping threshold therefore moves with the font, and pinning a pixel
    figure to it pins the font. Every width below is derived from the labels
    themselves, so each assertion says what it means on any metrics. That
    includes the last pair: the 640 px PDF grab width was pinned here too,
    and it is a Windows figure that fails on macOS for exactly the reason
    this paragraph gives. See the note beside it.
    """
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
    # Half of what the five labels' own glyphs need: whatever the font, that
    # cannot be one row.
    too_narrow = sum(fm.horizontalAdvance(l) for l in labels) / 2.0
    narrow = chart._legend_rows(fm, 40.0, too_narrow)
    wide = chart._legend_rows(fm, 40.0, 1600 - 52.0)
    assert narrow >= 2, (narrow, too_narrow)
    assert wide == 1, wide
    # …and the plot really is pushed down by the extra rows, which is the whole
    # point of counting them.
    assert chart._legend_rows(fm, 40.0, too_narrow / 2.0) > narrow
    # AND THE WIDTH AT WHICH IT STOPS WRAPPING IS THE LABELS' OWN WIDTH.
    # This line used to pin the 588 px the PDF grab leaves and assert ONE
    # row there, which is the pixel figure the docstring above says must not
    # be pinned, three lines after saying it. `QFont()` with no family asked
    # for resolves to whatever the platform calls its default sans, and the
    # five labels are 432 px of that on the Windows machine the figure was
    # taken on and 621 px of Helvetica here, so 588 px holds one row there
    # and two here. Measured on macOS 2026-09-06, with and without the
    # bundled fonts registered: identical either way, 119.5 + 123.6 + 121.3
    # + 126.2 + 130.3 = 621 px of advances, 755 px with the chips, 2 rows.
    #
    # So the threshold is asserted where it actually is: at exactly the
    # width the labels and their chips need, and one pixel below it. That is
    # the property the pinned figure was reaching for, it is stronger than
    # the pin, and it holds in any font.
    needed = 4.0 + sum(26 + fm.horizontalAdvance(l) for l in labels)
    assert chart._legend_rows(fm, 40.0, needed + 0.5) == 1, needed
    assert chart._legend_rows(fm, 40.0, needed - 1.0) == 2, needed


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
    # LOGICAL width, not the image's own. QWidget.grab() renders at the screen's
    # devicePixelRatio, so on a 200%-scale display (and on any Retina Mac) this
    # is a 1280 px image describing the same 640 px chart — asserting the raw
    # width read "1280 == 640" and failed on a correct render. The widget was
    # resized in logical pixels, so that is what has to be checked back
    # (2026-08-22, Windows 200% display; same confusion as _brightest() in
    # test_disabled_controls_look_disabled.py).
    assert not img.isNull()
    assert img.width() / (img.devicePixelRatio() or 1.0) == 640, (
        f"chart grabbed {img.width()} px at ratio {img.devicePixelRatio()} — "
        f"that is not a 640 px wide chart")
