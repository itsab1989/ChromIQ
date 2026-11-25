"""THE TABLE WINDOW ON A CHART IN PIECES (the new i1iO chart layout, step 8): cut first, lay only this
piece, the next piece, the question about the right piece; and a chart of pages keeps every word."""
from __future__ import annotations

import pytest

from tests.i1io_table import bed_sim as B
from tests.i1io_table.test_pieces_measured import chart, four  # noqa: F401  (fixtures)
from tests.i1io_table.test_window import open_window, settings  # noqa: F401  (a fixture)
from ui import i1io_table_window as W
from workflow import measurement_messages as M

STRIP = ["-v", "-c", "1"]
LAID = "The piece is laid, and my hands are away from the table"


def _window(qtbot, monkeypatch, tmp_path, settings, ch, bed, **kw):  # noqa: F811
    sim = B.bed_window_sim(ch, bed)
    stem = str(ch.run.chart_ti2)[:-4]
    out = open_window(qtbot, monkeypatch, tmp_path, settings, sheet=ch.sheet, sim=sim,
                      run=ch.run, args=STRIP + [stem], **kw)
    out[3].script["sheet_laid"] = LAID
    return out


def test_two_pieces_from_the_first_page_to_the_second_aim(qtbot, monkeypatch, tmp_path, settings,
                                                          four):  # noqa: F811
    ch = four
    bed = B.Bed(ch.laid(0))
    win, sim, run, p, saved, finished = _window(qtbot, monkeypatch, tmp_path, settings, ch, bed)
    assert p.drive_until("prepare") == "prepare"
    text = win._text.text()
    assert "Cut the sheet first. Lay only piece 1 on the bed" in text
    assert "with no other paper on the bed, and nothing over the white tile" in text
    assert "This chart has 4 pieces" in text and "for example 1/4" in text
    assert "page" not in text.replace("on a page of its own", "")
    assert p.drive_until("sheet_laid") == "sheet_laid"
    assert win._title.text() == "Is piece 1 on the table?"
    assert win._text.text().startswith("Cut the sheet first. Lay only piece 1")
    assert LAID in p.labels() and f"“{LAID}”" in win._text.text()
    assert p.drive_until("next_page") == "next_page"
    title, body = M.M_I1IO_DRIVE_NEXT_PIECE.render(page=1, next=2)
    assert win._title.text() == title == "Piece 1 is read"
    assert win._text.text().split("\n")[0] in body
    bed.laid = ch.laid(1)
    p.press("Go on")
    assert p.drive_until("sheet_laid") == "sheet_laid"
    assert win._title.text() == "Is piece 2 on the table?"
    assert "Piece 2 of 4: 0 of" in win._state.text()
    win._on_end_pressed()
    p.idle()


@pytest.mark.parametrize("guided", (None, False), ids=("pop-ups", "guidance off"))
def test_another_piece_is_asked_about_as_a_piece(qtbot, monkeypatch, tmp_path, settings,  # noqa: F811
                                                 four, guided):  # noqa: F811
    ch = four
    win, sim, run, p, saved, finished = _window(
        qtbot, monkeypatch, tmp_path, settings, ch, B.Bed(ch.laid(2)), asking=False,
        guided=guided)
    assert p.drive_until("row_identity") == "row_identity"
    assert win._title.text() == "Is the right piece on the table?"
    assert p.labels() == ["It is the right piece, and it was not moved"]
    text = win._text.text()
    assert "do not look like piece 1 of this chart; they look like piece 3." in text
    assert "press “It is the right piece, and it was not moved”" in text and "sheet" not in text.lower()
    from PyQt6.QtWidgets import QPushButton
    texts = [b.text() for b in win.popup().findChildren(QPushButton) if b.isVisible()]
    assert texts.count("End measurement") == 1
    win._on_end_pressed()
    p.idle()


def test_a_chart_of_pages_keeps_every_word(qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    ch = B.build_chart(tmp_path, count=600)
    assert not W.in_pieces(ch.sheet)
    win, sim, run, p, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings, sheet=ch.sheet,
        sim=B.bed_window_sim(ch, B.Bed(ch.laid(0))), run=ch.run,
        args=STRIP + [str(ch.run.chart_ti2)[:-4]])
    assert p.drive_until("prepare") == "prepare"
    assert win._title.text() == M.M_I1IO_DRIVE_PREPARE.title
    assert "Lay page 1 on the table" in win._text.text()
    assert "piece" not in win._text.text().lower()
    assert p.drive_until("sheet_laid") == "sheet_laid"
    assert win._title.text() == "Is page 1 on the table?"
    assert "The page is laid, and my hands are away from the table" in p.labels()
    win._on_end_pressed()
    p.idle()


def test_the_lines_and_the_ending_speak_of_pieces():
    assert W.rows_read_line(3, 4, 2, 8, True) == "Piece 3 of 4: 2 of 8 rows read."
    assert W.rows_read_line(3, 4, 1, 1, True) == "Piece 3 of 4: 1 of 1 row read."
    assert W.rows_read_line(3, 4, 2, 8) == "Page 3 of 4: 2 of 8 rows read."
    rows = [{"page": 1, "strip": "A"}, {"page": 3, "strip": "AB"}]
    assert W.strips_named(rows, 4, True) == "piece 1: A; piece 3: AB"
    assert "piece 3: AB" in W.rows_not_judged_text(rows, 4, True)
    one = M.M_I1IO_DRIVE_PREPARE_PIECES.render(
        page=1, pages=1, corner=M._I1IO_CORNER_MARK)[1]
    assert "Lay only the piece with the chart" in one and "next one" not in one


# ---- "piece" wherever the chart is in pieces ---------------------------------------------------

#: The window's own pages, not the chart's.
NOT_THE_CHARTS = ("on a page of its own", "The next page says how the arm can get home")


def _page_words(text: str) -> "list[str]":
    import re
    for own in NOT_THE_CHARTS:
        text = text.replace(own, "")
    return re.findall(r"[^.\n]*\b[Pp]ages?\b[^.\n]*", text)


def test_every_text_that_speaks_of_a_page_has_a_twin_for_a_piece():
    """Every translated text of the window, read from its source: one that names the chart's page
    stands beside one that names the piece (and the messages have their own)."""
    import ast
    import re
    from pathlib import Path
    tree = ast.parse(Path(W.__file__).read_text(encoding="utf-8"))
    texts = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "tr" and n.args:
            try:
                v = ast.literal_eval(n.args[0])
            except ValueError:
                continue
            if isinstance(v, str):
                texts.add(v)
    pages = [t for t in texts if re.search(r"\b[Pp]ages?\b", re.sub(r"\{\w+\}", "", t))]
    assert len(pages) > 20
    missing = [t for t in pages if not _twin(t, texts)]
    assert missing == []
    for m in (M.M_I1IO_DRIVE_ROW_FAILED, M.M_I1IO_DRIVE_ROW_FAILED_STRIP,
              M.M_I1IO_DRIVE_ROW_FAILED_STRIP_NOT_MOVED,
              M.M_I1IO_DRIVE_ROW_M0_ONLY, M.M_I1IO_DRIVE_ROW_M0_ONLY_STRIP,
              M.M_I1IO_DRIVE_ROW_PLACEMENT_REST, M.M_I1IO_DRIVE_ROW_NOT_IN_PLACE,
              M.M_I1IO_DRIVE_ROW_NOT_IN_PLACE_SPOT):
        twin = M.of_pieces(m)
        assert twin is not m and M.of_pieces(m, False) is m
        assert _page_words(twin.body.replace("{page}", "")) == [] and "piece" in twin.body
        assert "sheet" not in twin.body
    assert M.of_pieces(M.M_I1IO_DRIVE_GO) is M.M_I1IO_DRIVE_GO


def _twin(text: str, texts) -> bool:
    """Whether *text* with "piece" for "page" (placeholders aside) is among *texts*."""
    import re

    def words(t):
        return re.sub(r"\{\w+\}", "{}", t)
    want = words(text)
    for a, b in (("pages", "pieces"), ("page", "piece"), ("Page", "Piece")):
        want = re.sub(rf"\b{a}\b", b, want)
    return want in {words(u) for u in texts}


def test_the_window_never_says_page_on_a_chart_in_pieces(qtbot, monkeypatch, tmp_path, settings,
                                                         four):  # noqa: F811
    """A whole sitting: aims, rows read, a row that fails three times over, the next piece, the
    question, Stop and the ending: every title, text, button, state line and notice."""
    ch = four
    bed = B.Bed(ch.laid(0))
    seen = []
    real = W.TableMeasureWindow._show

    def show(self, page, title, body, buttons, *a, **k):
        made = real(self, page, title, body, buttons, *a, **k)
        seen.extend([title, body, *(b[0] for b in buttons), self._state.text()])
        return made
    monkeypatch.setattr(W.TableMeasureWindow, "_show", show)
    win, sim, run, p, saved, finished = _window(qtbot, monkeypatch, tmp_path, settings, ch, bed)
    win.notice.connect(seen.append)
    states = []
    for name in ("live_state_text", "state_text", "_row_status", "_row_move_text"):
        real_state = getattr(W.TableMeasureWindow, name)
        monkeypatch.setattr(W.TableMeasureWindow, name, lambda self, *a, real_state=real_state: (
            states.append(real_state(self, *a)), states[-1])[1])
    assert p.drive_until("rows") == "rows"
    bed.shift_mm = (11.0, 0.0)                  # (one patch off: the rows are refused)
    p.script["row_failed_strip"] = "Skip it"
    for _ in range(3):
        if p.page() == "go":
            p.press("Go")
        page = p.drive_until(("row_failed_strip", "report_after_step"))
        if page == "row_failed_strip":
            p.press("Skip it")
    bed.shift_mm = (0.0, 0.0)
    assert "row_failed_strip" in win.pages_shown
    assert p.drive_until("next_page") == "next_page"
    assert p.labels() == ["Go on"]                  # one way to end: the footer's
    bed.laid = ch.laid(3)                           # (piece 4 where piece 2 belongs)
    p.press("Go on")
    assert p.drive_until("row_identity") == "row_identity"
    win._on_end_pressed()
    p.idle()
    for _ in range(4):
        if p.page() == "report_after_step":
            p.press("As described, my hands are away")
    seen.append(win._text.text())
    seen.extend(states)
    bad = [w for t in seen for w in _page_words(t)]
    assert bad == [], bad[:5]
    missing = {ln for t in seen for ln in t.split("\n") if ln.startswith("Missing on")}
    assert missing and all("on this piece: row" in ln for ln in missing), missing
    assert any("of piece 1" in t for t in seen), sorted(set(seen))[:40]


def test_every_reason_speaks_of_the_piece():
    import ast
    import inspect
    src = inspect.getsource(W.reason_text)
    ids = {n.value for n in ast.walk(ast.parse(src.strip())) if isinstance(n, ast.Constant)
           and isinstance(n.value, str) and n.value.replace("_", "").isalnum()
           and n.value == n.value.lower()}
    said = 0
    for rid in sorted(ids):
        text = W.reason_text(rid, {}, True)
        assert _page_words(text) == [], (rid, text)
        said += "piece" in text
    assert said >= 8


def test_the_next_page_has_one_way_to_end(qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    """The page version too (the footer's End measurement, where it always is)."""
    from PyQt6.QtWidgets import QPushButton
    ch = B.build_chart(tmp_path, count=600)
    win, sim, run, p, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings, sheet=ch.sheet,
        sim=B.bed_window_sim(ch, B.Bed(ch.laid(0))), run=ch.run,
        args=STRIP + [str(ch.run.chart_ti2)[:-4]])
    assert p.drive_until("next_page") == "next_page"
    assert p.labels() == ["Go on"] and win._title.text() == "Page 1 is read"
    texts = [b.text() for b in win.findChildren(QPushButton) if b.isVisibleTo(win)]
    assert texts.count("End measurement") == 1
    win._on_end_pressed()
    p.idle()
    assert p.page() == "end_of_session"
