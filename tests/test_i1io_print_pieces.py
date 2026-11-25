"""PRINTING AN i1iO CHART IN PIECES (the new chart layout, step 7b).

The Print tab shows and prints the whole sheets of a chart whose pages are
pieces: only for its whole page set in order, never for images a person chose,
and never sheets that were not checked against the pages. The previews name
the pieces and the sheets.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest
import tifffile
from PyQt6.QtCore import QSettings

from tests.test_i1io_sheets import build
from workflow.i1io import sheets as S
from workflow.i1io import support as U


@pytest.fixture(autouse=True)
def i1io_on():
    before = U._latched
    U.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        U._latched = before


@pytest.fixture
def tab(qtbot, tmp_path, monkeypatch):
    from core.settings import AppSettings
    from ui.tabs.tab_print import TabPrint
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    s.set("use_native_print_dialog", False)
    t = TabPrint(s)
    monkeypatch.setattr(t, "_refresh_printers", lambda *a, **k: None)
    qtbot.addWidget(t)
    t.sent = []
    monkeypatch.setattr(t, "_print_pages", t.sent.append)
    monkeypatch.setattr(t, "_blocked_by_new_run", lambda: False)
    return t


def _note(tab):
    return tab._i1io_load_text()


def _shown(tab):
    return [p for p, _f in tab._preview._pages]


@pytest.mark.parametrize("paper,n,sheets,size", [
    ("A3", 1100, 2, (842, 1191)), ("420x297", 700, 1, (1191, 842)),
    ("A2", 2112, 1, (1191, 1684)), ("Legal", 100, 1, (612, 1008)),
    ("Legal", 900, 2, (612, 1008))])
def test_the_whole_page_set_is_printed_as_its_sheets(tab, tmp_path, paper, n,
                                                     sheets, size):
    from ui.tabs.tab_print import read_tiff_dimensions_points
    r = build(tmp_path, paper=paper, n=n)
    want = S.ensure(r.ti2_path)
    tab.load_tiffs(list(r.tiff_paths))
    assert tab._tiff_pages == want == _shown(tab) and len(want) == sheets
    assert tab._print_all_btn.isEnabled() and tab._print_page_btn.isEnabled()
    assert read_tiff_dimensions_points(tab._tiff_pages[0]) == pytest.approx(
        size, abs=1.5)
    tab._on_print_all()
    tab._on_print_current()
    assert tab.sent == [[(p, 0) for p in want], [(want[0], 0)]]


EXTRAS = {"a copy": "c Kopie.tif", "a copy of a page": "c_01 copy.tif",
          "a sheet copied here": "c-sheet_01.tif", "another chart's": "c2.tif",
          "an old single page": "c.tif", "a page too many": "c_04.tif"}


@pytest.mark.parametrize("what", sorted(EXTRAS))
def test_other_files_beside_the_chart_are_nobodys_pages(tab, tmp_path, what):
    """The folder's list holds whatever lies there; the chart's record says
    which pages it has (REVIEW_7B S1)."""
    import shutil
    r = build(tmp_path, n=1100)
    want = S.ensure(r.ti2_path)
    extra = tmp_path / EXTRAS[what]
    shutil.copy(r.tiff_paths[0], extra)
    for paths in ([extra, *r.tiff_paths], [*r.tiff_paths, extra]):
        tab.load_tiffs(list(paths))
        assert tab._tiff_pages == want
        assert tab._print_all_btn.isEnabled()


@pytest.mark.parametrize("gone", [0, 1, 2])
def test_a_chart_in_pieces_is_its_sheets_or_nothing(tab, tmp_path, gone):
    """Whatever part of its pages is asked for: the sheets, when every page is
    there; and nothing at all when one is not (the middle one too)."""
    r = build(tmp_path, n=1100)
    want = S.ensure(r.ti2_path)
    tab.isVisible = lambda: True
    for some in (r.tiff_paths[:2], r.tiff_paths[1:],
                 list(reversed(r.tiff_paths))):
        tab.load_tiffs(list(some))
        assert tab._tiff_pages == want
    r.tiff_paths[gone].unlink()
    tab.load_tiffs([p for p in r.tiff_paths if p.is_file()])
    assert not tab._print_all_btn.isEnabled()
    assert not tab._print_page_btn.isEnabled()
    assert "cannot be put together" in _note(tab)
    tab._on_print_all()
    tab._on_print_current()
    assert tab.sent == []


def test_by_hand_stays_what_was_chosen(tab, tmp_path):
    """Pieces or one sheet loaded by hand: never swapped, never rebuilt, and
    the sheet is named by its own number (REVIEW_7B S4)."""
    r = build(tmp_path, n=1100)
    sheets = S.ensure(r.ti2_path)
    tab.load_tiffs(list(r.tiff_paths), by_hand=True)
    assert tab._tiff_pages == list(r.tiff_paths)
    assert "grey lines" not in _note(tab)
    tab.load_tiffs([sheets[1]], by_hand=True)
    assert tab._preview._page_label.text() == "Sheet 2 of 2"
    r.tiff_paths[0].unlink()
    tab.show()
    tab._on_print_all()
    tab._on_print_current()
    assert tab.sent == [[(sheets[1], 0)]] * 2
    assert tab._tiff_pages == [sheets[1]]


def test_the_sheet_shown_is_the_sheet_printed(tab, tmp_path):
    """Print current page after a rebuild: the sheet that was shown, not the
    first one (REVIEW_7B S2); its note says its own pieces."""
    from workflow import measurement_messages as M
    r = build(tmp_path, n=1100)
    sheets = S.ensure(r.ti2_path)
    tab.isVisible = lambda: True
    tab.load_tiffs(list(r.tiff_paths))
    assert M._I1IO_PRINT_PIECES[:20].format(n=2)[:16] in _note(tab)
    tab._preview.show_page(1)
    assert _note(tab).startswith(M._I1IO_PRINT_PIECES_ONE)
    tab._preview._go_prev()
    assert "2 pieces" in _note(tab)
    tab._preview._go_next()
    arr = tifffile.imread(str(sheets[0]))
    arr[5, 5] = 9
    tifffile.imwrite(str(sheets[0]), arr, photometric="rgb", software=S.MARK)
    tab._on_print_current()
    assert tab.sent == [[(sheets[1], 0)]]
    assert tab._preview.current_page() == 1
    assert S.fits(S.info(r.ti2_path))


@pytest.mark.parametrize("what", ["one piece now", "no .ti2", "it raises"])
def test_no_sheet_is_sent_unchecked(tab, tmp_path, monkeypatch, what):
    """Sheets are shown, and their chart is not a chart in pieces any more, or
    cannot be asked (REVIEW_7B S3): nothing is sent."""
    r = build(tmp_path, n=1100)
    S.ensure(r.ti2_path)
    tab.isVisible = lambda: True
    tab.load_tiffs(list(r.tiff_paths))
    if what == "one piece now":
        for p in tmp_path.glob("c*"):
            if p.is_file():
                p.unlink()
        build(tmp_path, paper="A4", n=100)
    elif what == "no .ti2":
        r.ti2_path.unlink()
    else:
        monkeypatch.setattr(S, "info", lambda *a: 1 / 0)
    tab._on_print_all()
    tab._on_print_current()
    assert tab.sent == [] and not tab._print_all_btn.isEnabled()
    assert "Nothing can be printed from here" in _note(tab)
    from PyQt6.QtWidgets import QApplication
    assert QApplication.overrideCursor() is None


def test_too_little_room_on_the_disk_is_said(tab, tmp_path, monkeypatch):
    from types import SimpleNamespace
    r = build(tmp_path)
    tab.isVisible = lambda: True
    monkeypatch.setattr(S.shutil, "disk_usage",
                        lambda p: SimpleNamespace(free=1.2e9))
    monkeypatch.setattr(S, "_space_needed", lambda *a: int(3.4e9))
    seen = []
    real = tab._set_status
    monkeypatch.setattr(tab, "_set_status",
                        lambda t: (seen.append(t), real(t)))
    tab.load_tiffs(list(r.tiff_paths))
    assert "about 3.4 GB" in _note(tab) and "1.2 GB are free" in _note(tab)
    assert not tab._print_all_btn.isEnabled()
    from PyQt6.QtWidgets import QApplication
    assert QApplication.overrideCursor() is None
    assert seen[0].startswith("Putting the sheets") and seen[-1] == ""
    monkeypatch.undo()


def test_load_tiff_image_is_by_hand(tab, tmp_path, monkeypatch):
    r = build(tmp_path)
    S.ensure(r.ti2_path)
    monkeypatch.setattr("ui.widgets.open_files_dialog",
                        lambda *a, **k: [str(p) for p in r.tiff_paths])
    tab._on_load_image()
    assert tab._tiff_pages == list(r.tiff_paths)


def test_sheets_that_do_not_fit_wait_for_the_tab(tab, qtbot, tmp_path):
    """A chart drawn in Create Chart on every turn of a knob builds no sheets:
    they are built when the Print tab is looked at, and said."""
    r = build(tmp_path)
    tab.load_tiffs(list(r.tiff_paths))
    assert not (tmp_path / "exports").exists()
    assert tab._tiff_pages == list(r.tiff_paths)
    assert not tab._print_all_btn.isEnabled()
    tab.show()
    qtbot.waitExposed(tab)
    assert tab._tiff_pages == S.info(r.ti2_path).sheet_files
    assert S.fits(S.info(r.ti2_path)) and tab._print_all_btn.isEnabled()
    assert _note(tab).startswith("The sheets to print were not ready")
    assert "Print it at 100 %" in _note(tab)
    # loaded again with everything in place, nothing is said of it
    tab.load_tiffs(list(r.tiff_paths))
    assert _note(tab).startswith("This sheet holds 2 pieces.")


def test_a_sheet_is_checked_before_it_is_printed(tab, tmp_path):
    r = build(tmp_path)
    sheet = S.ensure(r.ti2_path)[0]
    tab.load_tiffs(list(r.tiff_paths))
    tab.isVisible = lambda: True
    page = tifffile.imread(str(r.tiff_paths[0]))
    tifffile.imwrite(str(r.tiff_paths[0]), 255 - page, photometric="rgb",
                     resolution=(72 / 2.54, 72 / 2.54), resolutionunit=3)
    tab._on_print_all()
    assert tab.sent == [[(sheet, 0)]] and S.fits(S.info(r.ti2_path))
    now = tifffile.imread(str(sheet))
    assert np.array_equal(now[:300, :500], np.rot90(255 - page, -1)[:300, :500])
    tifffile.imwrite(str(sheet), now[:100], photometric="rgb",
                     software=S.MARK)
    tab._on_print_current()
    assert tab.sent[1:] == [[(sheet, 0)]] and S.fits(S.info(r.ti2_path))
    del tab.sent[1:]
    # …and one that cannot be put together is not printed at all
    r.tiff_paths[1].unlink()
    tab._on_print_all()
    tab._on_print_current()
    assert len(tab.sent) == 1
    assert not tab._print_all_btn.isEnabled()
    assert "Nothing can be printed from here" in _note(tab)


@pytest.mark.parametrize("how", ["a piece is missing", "the record is damaged"])
def test_never_half_a_sheet(tab, tmp_path, how):
    r = build(tmp_path, n=1100)
    S.ensure(r.ti2_path)
    pages = list(r.tiff_paths)
    if how == "a piece is missing":
        pages.pop().unlink()
    else:
        r.ti2_path.write_text(r.ti2_path.read_text(encoding="utf-8").replace(
            "cut_y=210", "cut_y=200"), encoding="utf-8")
    tab.isVisible = lambda: True
    tab.load_tiffs(pages)
    assert not tab._print_all_btn.isEnabled()
    assert not tab._print_page_btn.isEnabled()
    assert "cannot be put together" in _note(tab)
    tab._on_print_all()
    assert tab.sent == []
    # the next chart is printed as ever
    one = build(tmp_path / "one", paper="A4", n=100)
    tab.load_tiffs(list(one.tiff_paths))
    assert tab._print_all_btn.isEnabled()
    assert "cannot be put together" not in _note(tab)


def test_the_note_of_a_sheet_of_pieces(tab, tmp_path):
    from workflow import measurement_messages as M
    r = build(tmp_path, n=1100)
    S.ensure(r.ti2_path)
    tab.load_tiffs(list(r.tiff_paths))
    assert _note(tab) == " ".join((
        M._I1IO_PRINT_PIECES.format(n=2, example="2/3"),
        M._I1IO_PRINT_LAY_CROSSES))
    for folder, kw, lead, lay in (
            ("one", dict(paper="Legal", n=100), M._I1IO_PRINT_PIECES_ONE,
             M._I1IO_PRINT_LAY_CROSSES),
            ("half", dict(n=100), M._I1IO_PRINT_PIECES_ONE,
             M._I1IO_PRINT_LAY_CROSSES),
            ("patches", dict(n=1000, i1io_crosses=False),
             M._I1IO_PRINT_PIECES.format(n=2, example="2/2"),
             M._I1IO_PRINT_LAY_PATCHES)):
        c = build(tmp_path / folder, **kw)
        S.ensure(c.ti2_path)
        tab.load_tiffs(list(c.tiff_paths))
        assert _note(tab) == lead + " " + lay, folder
    # a one-page chart says what it always said
    c = build(tmp_path / "a4", paper="A4", n=100)
    tab.load_tiffs(list(c.tiff_paths))
    assert _note(tab).startswith("This i1iO chart is shown as it lies")


def test_with_the_beta_off_nothing_is_asked(tab, tmp_path, monkeypatch):
    r = build(tmp_path)
    S.ensure(r.ti2_path)
    U.set_enabled_for_this_process(False)
    monkeypatch.setattr(S, "info", lambda *a: 1 / 0)
    tab.load_tiffs(list(r.tiff_paths))
    assert tab._tiff_pages == list(r.tiff_paths)
    assert tab._print_all_btn.isEnabled() and _note(tab) == ""
    tab._on_print_all()
    assert tab.sent == [[(p, 0) for p in r.tiff_paths]]
    assert U.page_names_for(r.tiff_paths) == []


def test_another_instruments_pages_are_never_asked_about(tab, tmp_path,
                                                         monkeypatch):
    monkeypatch.setattr(S, "info", lambda *a: 1 / 0)
    for k in (1, 2):
        tifffile.imwrite(str(tmp_path / f"x_0{k}.tif"),
                         np.full((60, 40, 3), 255, np.uint8),
                         photometric="rgb")
    (tmp_path / "x.ti2").write_text('CTI2\nTARGET_INSTRUMENT "X-Rite i1 Pro"\n', encoding="utf-8")
    pages = [tmp_path / "x_01.tif", tmp_path / "x_02.tif"]
    tab.load_tiffs(pages)
    assert tab._tiff_pages == pages and tab._print_all_btn.isEnabled()


def test_the_external_route_opens_the_sheets_folder(tab, tmp_path, monkeypatch):
    from workflow import verification_print as vp
    r = build(tmp_path)
    sheets = S.ensure(r.ti2_path)
    tab._current_ti2 = r.ti2_path
    tab.load_tiffs(list(r.tiff_paths))
    opened = []
    monkeypatch.setattr("core.preset_store.reveal_in_file_manager",
                        opened.append)
    monkeypatch.setattr(tab, "_cm_selected_route", lambda: vp.ROUTE_EXTERNAL)
    monkeypatch.setattr(tab, "_cm_selected_colour", lambda: vp.COLOUR_RAW)
    assert tab._apply_verification_colour([(sheets[0], 0)]) is None
    assert opened == [tmp_path / "exports"]
    # a chart whose pages are printed: its own folder, as ever
    one = build(tmp_path / "one", paper="A4", n=60)
    tab._current_ti2 = one.ti2_path
    tab._apply_verification_colour([(one.tiff_paths[0], 0)])
    assert opened[-1] == tmp_path / "one"


# ---- the names in the previews ----------------------------------------------------

def test_the_pieces_and_the_sheets_are_named(qtbot, tmp_path):
    from ui.tiff_preview import TiffPreview
    r = build(tmp_path, n=1100)
    sheets = S.ensure(r.ti2_path)
    pv = TiffPreview()
    qtbot.addWidget(pv)
    pv.load_tiff(list(r.tiff_paths))
    seen = []
    for k in range(3):
        pv._current = k
        pv._update_nav()
        seen.append(pv._page_label.text())
    assert seen == ["Piece 1 of 3: strips A to V, sheet 1",
                    "Piece 2 of 3: strips W to AR, sheet 1",
                    "Piece 3 of 3: strips AS to AT, sheet 2"]
    pv.load_tiff(sheets)
    assert pv._page_label.text() == "Sheet 1 of 2"
    one = build(tmp_path / "two", n=700)
    assert U.page_names_for(one.tiff_paths) == [
        "Piece 1 of 2: strips A to V", "Piece 2 of 2: strips W to AD"]
    a4 = build(tmp_path / "a4", paper="A4", n=100)
    pv.load_tiff(list(a4.tiff_paths))
    assert pv._page_label.text() == "Page 1 / 1"
    # a piece's image is missing: the others keep their names
    (tmp_path / "gone").mkdir()
    gone = build(tmp_path / "gone", n=1100)
    gone.tiff_paths[2].unlink()
    assert U.page_names_for(gone.tiff_paths[:2])[0].startswith(
        "Piece 1 of 3")
    assert pv._filename_lbl.text() == "c"
    pv.load_tiff(sheets)
    assert pv._filename_lbl.text() == "c"       # the chart's name, not a file's
    # in another order, or alone, each keeps its own name
    names = U.page_names_for(r.tiff_paths)
    assert U.page_names_for(list(reversed(r.tiff_paths))) == names[::-1]
    pv.load_tiff([r.tiff_paths[1]])
    assert pv._page_label.text() == names[1]
    assert U.page_names_for([tmp_path / "c_09.tif", *r.tiff_paths]) == []
    # the label keeps the width of the widest name, so no button moves
    pv.load_tiff(list(r.tiff_paths))
    fm = pv._page_label.fontMetrics()
    assert pv._page_label.minimumWidth() >= max(
        fm.horizontalAdvance(v) for v in names)
    # one sheet alone
    two = build(tmp_path / "one", n=700)
    pv.load_tiff(S.ensure(two.ti2_path))
    assert pv._page_label.text() == "Sheet 1 of 1"


def test_a_piece_of_one_strip_and_other_label_patterns(tmp_path):
    r = build(tmp_path, n=528 + 5)
    assert U.page_names_for(r.tiff_paths)[1] == "Piece 2 of 2: strip W"
    for strip, want in ((["A1", "A2"], "A"), (["AS1", "AS2", "AS3"], "AS"),
                        (["1A", "1B"], "1"), (["A7"], "A"), (["A01", "A02"],
                                                             "A"),
                        (["10A", "10B"], "10"), (["1A", "2A"], "A")):
        assert U._strip_name({"patches": [{"loc": v} for v in strip]}) == want


# ---- what the printer leaves white -------------------------------------------------

PPD = """*DefaultPageSize: A4
*PaperDimension A4/A4: "595 842"
*ImageableArea A4/A4: "9.6 14.2 585.4 833.5"
*PaperDimension A3/A3: "842 1191"
*ImageableArea A3/A3: "9.6 14.2 832.4 1182.5"
"""


@pytest.mark.parametrize("paper,n,known", [
    ("A3", 1056, True), ("A2", 2112, False), ("420x594", 2112, False),
    ("230x320", 200, False), ("A4", 100, True)])
def test_the_edge_note_is_about_a_paper_the_printer_has(
        tab, tmp_path, monkeypatch, paper, n, known):
    """A paper the printer does not know (A2 on an A3+ printer) was judged by
    its default paper, and said crosses lie in an edge they are 17 mm from."""
    from workflow import printer_edges as E
    from workflow.layout_engine.papers import dimensions_mm
    monkeypatch.setattr(E, "_query_driver",
                        lambda printer, mm: E.ppd_edges_mm(PPD, mm))
    mm = dimensions_mm(paper)
    edges, page = E.edges_for("P", mm, None)
    assert edges.any() is known
    assert page == pytest.approx(mm, abs=0.5)
    r = build(tmp_path, paper=paper, n=n, dpi=100)
    S.ensure(r.ti2_path)
    monkeypatch.setattr(tab, "_printer_combo", type(
        "C", (), {"currentData": lambda s: "P"})())
    tab.load_tiffs(list(r.tiff_paths))
    assert "crosses" not in tab._edge_note_lbl.text()
    assert "for this paper size" not in tab._edge_note_lbl.text()
    # an edge of one's own is used on every paper, and true: 25 mm
    from workflow import measurement_messages as M
    tab._settings.set(E.OVERRIDE_KEY, '{"P": 25.0}')
    tab.load_tiffs(list(r.tiff_paths))
    said = tab._edge_note_lbl.text()
    assert "crosses" in said
    assert ("along the grey lines as usual" in said) is (
        paper not in ("A4", "230x320"))


def test_the_overhang_of_a_converted_sheet_is_the_sheets_own(tmp_path):
    """The copy in cache/ that a verification prints (REVIEW_7B S5): on paper
    2 mm narrower only the empty margin is left off, as of the sheet."""
    import shutil
    from workflow import overhang as O
    for paper, on in (("330.2x482.6", (328.0, 482.6)), ("A3", (297.0, 418.0))):
        r = build(tmp_path / paper, paper=paper, n=1056, dpi=100)
        sheet = S.ensure(r.ti2_path)[0]
        copy = tmp_path / paper / "cache" / sheet.name
        copy.parent.mkdir()
        shutil.copy(sheet, copy)
        from ui.tabs.tab_print import read_tiff_dimensions_points
        pt = read_tiff_dimensions_points(sheet)
        paper_pt = tuple(v * 72 / 25.4 for v in on)
        a = O.plan_for_chart([(sheet, 0)], pt, paper_pt)
        b = O.plan_for_chart([(copy, 0)], pt, paper_pt)
        assert a == b and a is not None and a.safe, paper


def test_without_a_known_ti2_the_conversion_goes_beside_the_chart(
        tab, tmp_path, monkeypatch):
    from types import SimpleNamespace
    from workflow import verification_print as vp
    r = build(tmp_path)
    sheets = S.ensure(r.ti2_path)
    tab._current_ti2 = None
    seen = []
    monkeypatch.setattr(tab, "_cm_selected_colour", lambda: vp.COLOUR_THROUGH)
    monkeypatch.setattr(tab, "_cm_selected_route", lambda: vp.ROUTE_CHROMIQ)
    monkeypatch.setattr(tab, "_cm_run", lambda: SimpleNamespace(
        built_profile_icc=lambda: tmp_path / "p.icc"))
    monkeypatch.setattr(vp, "convert_pages_through_profile",
                        lambda pages, icc, intent, out, **k: seen.append(
                            Path(out)) or {p: p for p in pages})
    tab._apply_verification_colour([(sheets[0], 0)])
    assert seen == [tmp_path / "cache"]


def test_the_file_guide_lists_the_sheets_with_the_beta_only():
    from ui import file_guide as G

    def names():
        return {row[0] for _title, rows in G._rows(False) for row in rows}
    with_it = names()
    assert "{name}-sheets.json" in with_it
    U.set_enabled_for_this_process(False)
    assert with_it - names() == {"{name}-sheets.json",
                                 "{name}-sheet_01.tif, {name}-sheet_02.tif …"}


# ---- only the chart that was opened (the final review, S1 and A2) --------------------------------

@pytest.mark.parametrize("opened", ["an i1iO chart of one page", "another instrument's chart"])
def test_a_neighbour_chart_is_never_shown_in_its_place(tab, tmp_path, opened):
    """``k*.tif`` finds the pages of ``k-A3`` too: what is shown and sent stays what 4.3.65
    showed, the opened list."""
    from tests.test_i1io_chart import _ti1
    from workflow.layout_engine import chart
    a3 = chart.build_chart(_ti1(tmp_path / "k-A3.ti1", 700), tmp_path / "k-A3",
                           instrument="IO2", paper="A3", dpi=72, seed=1,
                           chart_date="x", i1io_limits=2)
    S.ensure(a3.ti2_path)
    k = chart.build_chart(_ti1(tmp_path / "k.ti1", 60), tmp_path / "k", dpi=72, seed=1,
                          instrument="IO2" if "i1iO" in opened else "CM",
                          paper="A4", chart_date="x")
    both = sorted(tmp_path.glob("k*.tif"))
    assert set(both) == {*k.tiff_paths, *a3.tiff_paths}
    tab.isVisible = lambda: True
    for paths in (both, list(reversed(both))):
        tab.load_tiffs(list(paths))
        assert tab._tiff_pages == paths and tab._print_all_btn.isEnabled()
        tab._on_print_all()
        assert tab.sent.pop() == [(p, 0) for p in paths]
    # the chart in pieces, opened itself, is its sheets
    tab.load_tiffs(list(a3.tiff_paths))
    assert tab._tiff_pages == S.info(a3.ti2_path).sheet_files


def test_sheets_built_under_another_name_while_shown_are_the_ones_sent(tab, tmp_path):
    """A file that is not ours took our sheet's name while the tab showed it: ours is built as
    ``-1``, and that is shown and sent, never the stranger."""
    r = build(tmp_path, n=700)
    (ours,) = S.ensure(r.ti2_path)
    tab.isVisible = lambda: True
    tab.load_tiffs(list(r.tiff_paths))
    assert tab._tiff_pages == [ours]
    arr = tifffile.imread(str(ours))
    ours.unlink()
    tifffile.imwrite(str(ours), arr, photometric="rgb", software="a person's program")
    (now,) = S.ensure(r.ti2_path)
    assert now.name == "c-sheet_01-1.tif" and ours.is_file()
    tab._on_print_all()
    assert tab.sent == [[(now, 0)]] and tab._tiff_pages == [now] == _shown(tab)
