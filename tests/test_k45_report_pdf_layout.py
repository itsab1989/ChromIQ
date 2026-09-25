"""K45 (Knut, #182 5834422633): three layout points of the Measurement
Report's PDF.

1. *"How to read this report"*: when its last line or two spill onto a page
   of their own, the text in its coloured frame gives up at most 0.2 pt, and
   only when that really brings them back (`ui.pdf_layout.
   tighten_to_close_a_page`).
2. The Colour accuracy graph describes every limit line under it, naming
   every row the line is the limit for, and a judged row neither of its grey
   lines stands for gets one of its own; the window shows the same sentences
   under the graph in front.
3. "For information (no limit applies)" starts a fresh page unless the colour
   section in front of it already ran over a page boundary
   (`ui.pdf_layout.break_before_unless_overflowed`).

Every test names the mutation it was proved red against.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSizeF                           # noqa: E402
from PyQt6.QtGui import QFont, QTextDocument, QTextTable  # noqa: E402

from ui import pdf_layout as P                            # noqa: E402
import ui.dialogs.measurement_report_dialog as mrd        # noqa: E402
from workflow.compliance_sets import Limit, effective_limits   # noqa: E402
from tests.test_trend_graphs_for_judged_metrics import (  # noqa: E402
    _export, _open, qapp)                                 # noqa: F401

BODY_H = 600.0
_BREAK = "page-break-before:always;"


def _doc(html: str) -> QTextDocument:
    doc = QTextDocument()
    doc.setHtml(html)
    doc.setPageSize(QSizeF(500.0, BODY_H))
    return doc


def _first_table(doc) -> QTextTable:
    stack = [doc.rootFrame()]
    while stack:
        for ch in stack.pop().childFrames():
            if isinstance(ch, QTextTable):
                return ch
            stack.append(ch)
    raise AssertionError("no table")


_WORDS = ("the printed sheet is compared with the chart's design colours "
          "and every number names its own unit so a reader can follow it "
          "without knowing the vocabulary of colour management ").split()


def _panel(words: int) -> str:
    """A heading on a page of its own, its frame holding *words* words of
    running text in paragraphs of forty, then a section that starts a page of
    its own: the report's shape."""
    seq = [_WORDS[i % len(_WORDS)] for i in range(words)]
    paras = "".join("<p style='font-size:12px'>" + " ".join(seq[i:i + 40])
                    + "</p>" for i in range(0, len(seq), 40))
    return (f"<div style='{_BREAK}font-size:20px'>How to read</div>"
            "<table cellpadding='12' width='100%'><tr><td "
            "style='background:#eee'>" + paras + "</td></tr></table>"
            f"<div style='{_BREAK}font-size:20px'>Report Results</div>"
            "<p>results</p>")


def _spills(words: int) -> bool:
    doc = _doc(_panel(words))
    first, last = P.frame_text_pages(doc, _first_table(doc), BODY_H)
    return last != first


def _lines_that_fit_one_page() -> int:
    """The most words the frame holds and still ends on its first page,
    measured on this machine's fonts."""
    lo, hi = 40, 4000
    assert not _spills(lo) and _spills(hi)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        lo, hi = (mid, hi) if not _spills(mid) else (lo, mid)
    return lo


def _one_line_over() -> int:
    """Words that spill exactly ONE line onto the next page."""
    fit = _lines_that_fit_one_page()
    n = fit + 1
    while True:
        doc = _doc(_panel(n))
        lay = P.settled_layout(doc)
        table = _first_table(doc)
        _f, last = P.frame_text_pages(doc, table, BODY_H)
        lines = 0
        block = doc.findBlock(table.firstPosition())
        while block.isValid() and block.position() <= table.lastPosition():
            top = lay.blockBoundingRect(block).top()
            bl = block.layout()
            lines += sum(1 for i in range(bl.lineCount())
                         if int((top + bl.lineAt(i).y()) // BODY_H) == last)
            block = block.next()
        if lines >= 1:
            assert lines == 1, lines
            return n
        n += 1


# ---------------------------------------------------------------------------
# 1. "How to read this report"
# ---------------------------------------------------------------------------
def test_a_one_line_spill_is_tightened_back_and_saves_the_sheet(qapp):
    """The frame spills ONE line; at most 0.2 pt brings it back, the frame
    then ends on its first page and the document is a sheet shorter.

    MUTATION, proven red: `TIGHTEN_STEPS_PT = ()` (nothing is tried: the
    spill stays)."""
    doc = _doc(_panel(_one_line_over()))
    panel = _first_table(doc)
    before = P.pages_that_carry_something(doc, BODY_H)
    assert P.frame_text_pages(doc, panel, BODY_H)[1] \
        == P.frame_text_pages(doc, panel, BODY_H)[0] + 1
    step = P.tighten_to_close_a_page(doc, panel, BODY_H, 9.0)
    assert step in (0.1, 0.2), step
    first, last = P.frame_text_pages(doc, panel, BODY_H)
    assert first == last
    assert P.pages_that_carry_something(doc, BODY_H) == before - 1


def test_never_more_than_two_tenths_of_a_point(qapp):
    """The steps are Knut's, and the space the text is set in is exactly
    that of 9 pt text made at most 0.2 pt smaller.

    MUTATION, proven red: `TIGHTEN_STEPS_PT = (0.1, 0.2, 0.5)`; or the factor
    taken as ``(text_pt - 2 * step) / text_pt``."""
    assert P.TIGHTEN_STEPS_PT == (0.1, 0.2)
    doc = _doc(_panel(_one_line_over()))
    panel = _first_table(doc)
    step = P.tighten_to_close_a_page(doc, panel, BODY_H, 9.0)
    assert step is not None
    cell = panel.cellAt(0, 0)
    block = cell.firstCursorPosition().block()
    it = block.begin()
    frag = it.fragment()
    fmt = frag.charFormat()
    assert fmt.fontLetterSpacingType() == QFont.SpacingType.PercentageSpacing
    assert fmt.fontLetterSpacing() == pytest.approx(100 * (9.0 - step) / 9.0)
    assert fmt.fontLetterSpacing() >= 100 * 8.8 / 9.0 - 1e-6
    assert block.blockFormat().lineHeight() == pytest.approx(
        100 * (9.0 - step) / 9.0)


def test_a_spill_that_will_not_fit_is_left_exactly_as_it_was(qapp):
    """Several lines over: 0.2 pt cannot bring them back, so nothing is
    changed at all, not even the step that was tried.

    MUTATION, proven red: drop the ``doc.undo()`` (the tried step stays in
    the document although it saved nothing)."""
    fit = _lines_that_fit_one_page()
    doc = _doc(_panel(fit + 200))
    panel = _first_table(doc)
    before = P.pages_that_carry_something(doc, BODY_H)
    assert P.tighten_to_close_a_page(doc, panel, BODY_H, 9.0) is None
    assert P.pages_that_carry_something(doc, BODY_H) == before
    fmt = panel.cellAt(0, 0).firstCursorPosition().block().begin() \
        .fragment().charFormat()
    assert fmt.fontLetterSpacing() in (0.0, 100.0)


def test_a_frame_that_fits_is_not_touched(qapp):
    """MUTATION, proven red: drop the ``pages[0] == pages[1]`` early return
    AND the page-count condition together, so any step that keeps the frame
    on one page is accepted (either alone is caught by the other)."""
    doc = _doc(_panel(60))
    panel = _first_table(doc)
    assert P.tighten_to_close_a_page(doc, panel, BODY_H, 9.0) is None
    fmt = panel.cellAt(0, 0).firstCursorPosition().block().begin() \
        .fragment().charFormat()
    assert fmt.fontLetterSpacing() in (0.0, 100.0)


def test_the_report_finds_its_how_to_read_frame(qapp):
    """The frame the export tightens is the one under the heading.

    MUTATION, proven red: `_how_to_read_frame` returning the first table of
    the document."""
    html = ("<table><tr><td>scope</td></tr></table>"
            + f"<div style='{_BREAK}'>" + mrd.tr("How to read this report")
            + "</div><p style='font-size:8px'>&nbsp;</p>"
            "<table><tr><td>the guide</td></tr></table>")
    doc = _doc(html)
    frame = mrd._how_to_read_frame(doc)
    assert frame is not None
    assert "the guide" in frame.cellAt(0, 0).firstCursorPosition().block() \
        .text()


# ---------------------------------------------------------------------------
# 3. "For information (no limit applies)"
# ---------------------------------------------------------------------------
HEAD = "For information (no limit applies)"
SECTION = "Colour accuracy (ΔE00 against the chart's design)"


def _measurement(section_lines: int, first: bool = False) -> str:
    rows = "".join(f"<tr><td>row {i}</td><td>1.0</td></tr>"
                   for i in range(section_lines))
    brk = "" if first else _BREAK
    return (f"<h3 style='{brk}'>Measurement</h3><p>intro</p>"
            f"<div>{SECTION}</div><table>{rows}</table><p>a note</p>"
            f"<div>{HEAD}</div><p>white and black</p>")


def _page_of(doc, text) -> "list[int]":
    lay = P.settled_layout(doc)
    out, block = [], doc.begin()
    while block.isValid():
        if block.text().strip() == text:
            out.append(P._line_page(lay, block, BODY_H))
        block = block.next()
    return out


def test_for_information_starts_a_fresh_page(qapp):
    """A colour section on one page: the heading after it moves to the top
    of the next.

    MUTATION, proven red: `break_before_unless_overflowed` returning before
    it sets the break."""
    doc = _doc(_measurement(5, first=True) + _measurement(5))
    assert _page_of(doc, HEAD) == [0, 1]
    assert len(P.break_before_unless_overflowed(doc, HEAD, SECTION,
                                                BODY_H)) == 2
    assert _page_of(doc, HEAD) == [1, 3]
    assert _page_of(doc, SECTION) == [0, 2]


def test_no_break_when_the_colour_section_already_ran_over(qapp):
    """A colour section that crosses onto the next page: the heading follows
    it there, with no page of its own.

    MUTATION, proven red: drop the ``!= end_page`` test (the heading is
    pushed to a third page)."""
    doc = _doc(_measurement(60, first=True))
    sec, = _page_of(doc, SECTION)
    head, = _page_of(doc, HEAD)
    assert head == sec + 1
    assert P.break_before_unless_overflowed(doc, HEAD, SECTION, BODY_H) == []
    assert _page_of(doc, HEAD) == [head]


def _pdf_spans(path):
    pymupdf = pytest.importorskip("pymupdf")
    doc = pymupdf.open(str(path))
    pages = []
    for page in doc:
        spans = []
        for b in page.get_text("dict")["blocks"]:
            for line in b.get("lines", []):
                for s in line["spans"]:
                    if s["text"].strip():
                        spans.append((s["bbox"][1], s["size"],
                                      s["text"].strip()))
        pages.append(sorted(spans))
    return pages


def test_the_saved_pdf_starts_every_for_information_on_a_fresh_page(
        qapp, tmp_path, monkeypatch):
    """The real export: every "For information" HEADING (the 12 pt one of the
    detailed data, not the row group of a table) is the first line of its
    page's body, unless its measurement's colour heading is on an earlier
    page.

    MUTATION, proven red: the `break_before_unless_overflowed` call taken
    out of `_export_pdf`; or the page rules not started again from the clean
    document (no ``doc.undo()`` loop): "Worst patches" goes to a page of its
    own."""
    dlg = _open(tmp_path, qapp, effective_limits("chromiq_default", {}))
    try:
        dlg._detail_check.setChecked(True)
        dlg._refresh()
        _export(dlg, tmp_path, monkeypatch)
        pages = _pdf_spans(tmp_path / "out.pdf")
        head, sec = mrd.tr(HEAD), mrd.tr(SECTION)
        seen = 0
        last_section_page = None
        for n, spans in enumerate(pages):
            body = [s for s in spans if s[0] > 68]      # below the header band
            for k, (y, size, text) in enumerate(body):
                if text == sec:
                    last_section_page = n
                if text == head and size > 11:
                    seen += 1
                    first_on_page = k == 0
                    overflowed = (last_section_page is not None
                                  and last_section_page < n)
                    assert first_on_page or overflowed, (
                        f"page {n + 1}: '{text}' is not at the top of its "
                        f"page and its colour section did not run over: "
                        f"{[t for _y, _s, t in body[:4]]}")
        assert seen >= 3, seen
        # …AND WHAT FOLLOWS IT COMES ALONG. The page rules start again from
        # the clean document once the breaks are set; a break they had set
        # before, for the old layout, sent "Worst patches" alone to a third
        # sheet (the first drive of this change). On this fixture the whole
        # section fits one page, so it is on the heading's page.
        worst = mrd.tr("Worst patches")
        heads = [n for n, sp in enumerate(pages)
                 for _y, size, t in sp if t == head and size > 11]
        worsts = [n for n, sp in enumerate(pages)
                  for _y, _s, t in sp if t == worst]
        assert worsts and worsts == heads, (heads, worsts)
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# 2. The Colour accuracy graph describes every limit it has
# ---------------------------------------------------------------------------
_FIVE = ("all_de00_avg", "best95_de00_avg", "worst5_de00_avg",
         "all_de00_max", "all_de00_p95")


def test_the_accuracy_key_names_every_row_its_lines_limit(qapp, tmp_path,
                                                         monkeypatch):
    """ChromIQ default limits all five plotted rows, the three averages at
    2.0 and the two maxima at 3.0: the Avg and Max sentences name all five,
    in the PDF key under the graph.

    MUTATION, proven red: `_accuracy_line_plan` naming only the pair's own
    row in the pair's sentences (the other three then come back as extra
    lines drawn on top of the pair)."""
    dlg = _open(tmp_path, qapp, effective_limits("chromiq_default", {}))
    try:
        if not dlg._trend_de.has_trend():
            pytest.skip("no trend on this fixture")
        notes = dlg._trend_extras(dlg._trend_de)["line_notes"]
        runs = dlg._document_runs_for_graphs()
        # ONE Avg line and ONE Max line: a row at the pair's own number is
        # named by that line, never given a second line on top of it
        assert dlg._accuracy_line_plan()[1] == []
        assert len(notes) == 2 and all(notes), notes
        for rid in _FIVE:
            name = dlg._row_name(rid, runs)
            assert any(name in n for n in notes), (rid, notes)
        _sizes, html_ = _export(dlg, tmp_path, monkeypatch)
        key = html_[html_.find("chart://0"):html_.find("chart://1")]
        for rid in _FIVE:
            assert mrd.html.escape(dlg._row_name(rid, runs)) in key, rid
    finally:
        dlg.deleteLater()


def test_a_judged_row_no_grey_line_stands_for_gets_its_own(qapp, tmp_path):
    """The ISO shape: no limit on the all-patch maximum, 5.0 on the 95th
    percentile. That row is plotted and judged, so it gets a grey "P95" line
    and a sentence.

    MUTATION, proven red: `_accuracy_line_plan` returning no ``extra``."""
    lim = dict(effective_limits("chromiq_default", {}))
    lim["all_de00_max"] = Limit.none()
    lim["all_de00_p95"] = Limit.value(5.0)
    dlg = _open(tmp_path, qapp, lim)
    try:
        pair, extra = dlg._accuracy_line_plan()
        assert pair[1] == ""                       # no Max line
        assert [(v, w) for v, w, _n in extra] == [(5.0, mrd.tr("P95"))]
        plan = [e for e in dlg._trend_plan() if e[0] is dlg._trend_de][0]
        assert plan[7] == [(5.0, mrd.tr("P95"), None)]
        texts = [t for k, _c, t in dlg._trend_de.descriptions()
                 if k == "line"]
        assert any(t.startswith(mrd.tr("P95")) for t in texts), texts
    finally:
        dlg.deleteLater()


def test_the_window_shows_the_key_under_the_graph_in_front(qapp, tmp_path):
    """Under the tab in front, the same sentences the PDF prints under that
    graph; a graph with no limit shows none.

    MUTATION, proven red: drop `_refresh_trend_key` from `_update_trends`
    (the key stays empty); or drop its ``has_trend()`` test (a graph of one
    date, which draws no line, keeps a key)."""
    dlg = _open(tmp_path, qapp, effective_limits("chromiq_default", {}))
    try:
        if not dlg._trend_de.has_trend():
            pytest.skip("no trend on this fixture")
        tabs = dlg._trend_tabs
        tabs.setCurrentIndex(tabs.indexOf(dlg._trend_de))
        text = dlg._trend_key.text()
        for _k, _c, line in dlg._trend_de.descriptions():
            assert mrd.html.escape(line) in text
        assert not dlg._trend_key.isHidden()
        tabs.setCurrentIndex(tabs.indexOf(dlg._trend_black))
        assert dlg._trend_key.isHidden()
        # a graph of one date draws no line, so it has no key either
        tabs.setCurrentIndex(tabs.indexOf(dlg._trend_de))
        assert not dlg._trend_key.isHidden()
        dlg._trend_de._series = dlg._trend_de._series[:1]
        dlg._refresh_trend_key()
        assert dlg._trend_key.isHidden()
    finally:
        dlg.deleteLater()


def test_the_window_key_takes_nothing_from_the_graphs(qapp, tmp_path):
    """The key asks for its lines only as its preferred height: the window's
    need, which the height ladder squeezes the graphs to meet, is the same
    with it shown as without. Measured on screen before this held: at
    1400 x 980 the Colour accuracy graph went from 110 px to 60 px.

    MUTATION, proven red: `_layout_need` without the key's ``spare`` taken
    off; or `_TrendKey` without its zero `minimumSizeHint`."""
    dlg = _open(tmp_path, qapp, effective_limits("chromiq_default", {}))
    try:
        if not dlg._trend_de.has_trend():
            pytest.skip("no trend on this fixture")
        dlg.resize(1400, 900)
        tabs = dlg._trend_tabs
        tabs.setCurrentIndex(tabs.indexOf(dlg._trend_de))
        key = dlg._trend_key
        assert not key.isHidden() and key.sizeHint().height() > 20
        assert key.minimumSizeHint().height() == 0
        with_key = dlg._layout_need()
        key.setVisible(False)
        without = dlg._layout_need()
        assert with_key == without, (with_key, without)
    finally:
        dlg.deleteLater()
