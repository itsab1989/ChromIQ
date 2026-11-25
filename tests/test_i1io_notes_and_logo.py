"""`{logo}` AND THE CHART NOTES ON AN i1iO CHART (Basti's ruling, 25 November
2026): both in the name line, on every piece, drawn by the engine's own code;
they cost no patch, and a chart of an earlier ChromIQ is drawn as it was."""
from __future__ import annotations

import json
from dataclasses import replace

import numpy as np
import pytest
from PIL import Image

from workflow.i1io import chart as C
from workflow.i1io import pieces as P
from workflow.layout_engine import raster

SEP = C.TEXT_SEP


@pytest.fixture(autouse=True)
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


def _build(out, paper="A4", n=60, text="", notes="", dpi=150, rep="RGB",
           limits=2, **kw):
    from tests.test_i1io_chart import _ti1
    from workflow.layout_engine import chart
    from workflow.layout_engine.presets import default_recipe
    out.mkdir(parents=True, exist_ok=True)
    r = replace(default_recipe("IO2", paper), chart_text=text)
    k = r.build_kwargs()
    if limits != 2:
        k.pop("i1io_limits")
    k.update(dpi=dpi, seed=1, chart_date="x", project="Proof", **kw)
    if notes:
        k["i1io_notes"] = notes
    res = chart.build_chart(_ti1(out / "c.ti1", n, rep), out / "c", **k)
    side = json.loads((out / "c.i1io.json").read_text("utf-8"))
    return res, side


def _texts(side):
    return [p["text_line"]["text"] for p in side["pages"]]


def _image(path, frame=0):
    with Image.open(path) as im:
        im.seek(frame)
        return np.asarray(im.convert("RGB"))


def _find(page, tile):
    """Every place *tile* (H x W x 3) stands in *page*, pixel for pixel."""
    h, w = tile.shape[:2]
    out = []
    first = tile[h // 2, w // 2]
    ys, xs = np.where((page == first).all(axis=2))
    for y, x in zip(ys, xs):
        a, b = y - h // 2, x - w // 2
        if a < 0 or b < 0 or a + h > page.shape[0] or b + w > page.shape[1]:
            continue
        if np.array_equal(page[a:a + h, b:b + w], tile):
            out.append((b, a))
    return out


def _turned_logo(font_px):
    font = C._font(font_px, "Inter")[0]
    im, _base = raster.logo_tile(raster._cap_px(font))
    white = Image.new("RGB", im.size, (255, 255, 255))
    white.paste(im.convert("RGB"), (0, 0), im)
    return np.asarray(white.transpose(Image.Transpose.ROTATE_90))


def _text_px(dpi):
    font = C._font(200, "Inter")[0]
    return max(1, int(round(200 * (C.TEXT_CAP_MM * dpi / 25.4)
                            / C._cap_mm(font, 1.0))))


# ---- the logo ------------------------------------------------------------------------

@pytest.mark.parametrize("paper,n", [("A4", 60), ("A2", 2112)])
def test_the_logo_drawn_is_the_engines_own_turned(tmp_path, paper, n):
    """Pixel for pixel the engine's tile, a quarter turn: upright on the table
    (the sheet lies turned clockwise); on every piece, in text and notes."""
    res, side = _build(tmp_path, paper, n, text="from {logo}",
                       notes="made by {logo} now")
    tile = _turned_logo(_text_px(150))
    assert len(res.tiff_paths) == len(side["pages"])
    for k, t in enumerate(res.tiff_paths):
        page = _image(t)
        found = _find(page, tile)
        assert len(found) == 2, k
        # both on one line, on the text's own baseline
        assert len({x for x, _y in found}) == 1
        font = C._font(_text_px(150), "Inter")[0]
        base_x = side["pages"][k]["aim_points"][1]["page_mm"][0] \
            + C._cap_mm(font, 150 / 25.4) / 2.0
        base = raster.logo_tile(raster._cap_px(font))[1]
        assert found[0][0] + base == round(base_x * 150 / 25.4)
        assert f"from {{logo}}{SEP}made by {{logo}} now" in _texts(side)[k]


@pytest.mark.parametrize("crosses", (True, False))
def test_logo_and_notes_cost_no_patch(tmp_path, crosses):
    a, sa = _build(tmp_path / "a", n=528, i1io_crosses=crosses)
    b, sb = _build(tmp_path / "b", n=528, text="{logo}", notes="n " * 80,
                   i1io_crosses=crosses)
    assert a.layout == b.layout
    assert [p["strips"] for p in sa["pages"]] == \
        [p["strips"] for p in sb["pages"]]
    pa, pb = _image(a.tiff_paths[0]), _image(b.tiff_paths[0])
    s = 150 / 25.4
    w, h = sa["patch_mm"]
    for st in sa["pages"][0]["strips"]:
        for q in st["patches"]:
            x, y = q["centre_mm"]
            box = (slice(int((y - h / 2) * s), int((y + h / 2) * s)),
                   slice(int((x - w / 2) * s), int((x + w / 2) * s)))
            assert np.array_equal(pa[box], pb[box]), q["loc"]
    # …and nothing but the name line changed
    diff = np.argwhere((pa != pb).any(axis=2))
    if crosses:
        col = sa["pages"][0]["text_column_mm"]
        assert diff[:, 1].min() >= col[0] * s - 2
        assert diff[:, 1].max() <= col[2] * s + 2


def test_a_chart_without_them_is_what_it_was(tmp_path):
    a, sa = _build(tmp_path / "a")
    b, sb = _build(tmp_path / "b", notes="")
    assert np.array_equal(_image(a.tiff_paths[0]), _image(b.tiff_paths[0]))
    assert sa == sb


def test_an_earlier_chart_is_drawn_again_as_it_was_printed(tmp_path):
    """No marker: no notes, no `{logo}`, its separator gone with it."""
    plain, sp = _build(tmp_path / "p", text="a, b", limits=0)
    old, so = _build(tmp_path / "o", text="a, {logo}, b", notes="notes {logo}",
                     limits=0)
    assert _texts(so) == _texts(sp) == ["Proof" + SEP + "a, b"]
    assert np.array_equal(_image(plain.tiff_paths[0]),
                          _image(old.tiff_paths[0]))


def test_a_line_too_small_leaves_the_logo_out_and_says_so(tmp_path,
                                                          monkeypatch):
    """At 50 dpi 3 mm capitals are 6 pixels: the logo needs 8. Its separator
    goes with it, and the log names the line."""
    said = []
    monkeypatch.setattr(raster.log, "info",
                        lambda t, *a: said.append(t % a if a else t))
    a, _s = _build(tmp_path / "a", text="a, {logo}, b", dpi=50)
    assert [x for x in said if "{logo} left out of the line" in x]
    drawn = []
    real = raster.logo_tile
    monkeypatch.setattr(raster, "logo_tile",
                        lambda cap: drawn.append(cap) or real(cap))
    _build(tmp_path / "b", text="a, {logo}, b", dpi=50)
    assert drawn and all(real(c) is None for c in drawn)


# ---- the notes -----------------------------------------------------------------------

def test_the_notes_are_the_last_part_with_the_pages_values(tmp_path):
    res, side = _build(tmp_path, "A3", 4 * 528, text="S",
                       notes="{page}, sheet {sheet}, {patchcount}, {project}")
    assert _texts(side) == [
        f"{k}/4{SEP}Proof{SEP}S{SEP}page {k}/4, sheet {(k + 1) // 2}/2, "
        "528 patches, Proof" for k in (1, 2, 3, 4)]


def test_a_long_note_is_shortened_first_and_never_inside_the_logo(tmp_path):
    for i in range(0, 40, 3):
        note = "x" * i + " {logo} " * 12 + "the end"
        res, side = _build(tmp_path / str(i), text="SHEET TEXT", notes=note,
                           dpi=100)
        text = _texts(side)[0]
        assert text.startswith(f"Proof{SEP}SHEET TEXT{SEP}")
        assert text.endswith("…")
        body = text.replace("{logo}", "")
        assert "{" not in body and "}" not in body, text


def test_shortening_goes_notes_then_text_then_name_and_the_number_last(tmp_path):
    long = "w" * 400
    _r, side = _build(tmp_path / "a", "A3", 600, text=long, notes="NOTE")
    t = _texts(side)[0]
    assert t.startswith(f"1/2{SEP}Proof{SEP}www") and "NOTE" not in t
    assert _texts(side)[1].startswith("2/2")


@pytest.mark.parametrize("n", range(0, 60))
def test_a_cut_never_ends_inside_a_logo(n):
    t = "ab {logo} cd {logo}{logo} e"
    cut = C._upto(t, n)
    assert t.startswith(cut) and len(cut) <= n
    assert "{" not in cut.replace("{logo}", "")
    assert C._upto("abc", n) == "abc"[:n]


def test_the_creator_hands_the_notes_on_for_the_i1io_only():
    import sys
    sys.path.insert(0, "tests")
    import _i1io_baseline as base
    from workflow.chart_creator import ChartParams
    for manual in (True, False):
        from workflow.layout_engine import presets
        for inst in ("IO2", "i1"):
            rec = presets.default_recipe(inst, "A4") if manual else None
            kw = base._creator()._engine_kwargs(ChartParams(
                instrument=inst, paper="A4", is_manual=manual,
                layout_recipe=rec, chart_notes="  a note {logo} "))
            assert kw.get("i1io_notes") == (
                "a note {logo}" if inst == "IO2" else None)


def test_the_stampers_notes_are_the_engines_line():
    """`stamp_lines` (every other chart) prints what it printed."""
    f = raster.notes_line
    assert f(" a ", None) == "a" and f("a {logo}, b", None) == "a, b"
    assert f("{page} {logo} {x}", {"page": "page 1/2"}) == "page 1/2 {logo} {x}"
    assert f("", {}) == ""


# ---- inks, 16 bit, PDF -----------------------------------------------------------------

@pytest.mark.parametrize("kw", [{"rep": "CMYK"}, {"bit16": True},
                                {"export_pdf": True}],
                         ids=("CMYK", "16 bit", "PDF"))
def test_inks_and_the_pdf_hold_them_too(tmp_path, kw):
    a, _s = _build(tmp_path / "a", **kw)
    b, side = _build(tmp_path / "b", text="{logo}", notes="a note", **kw)
    assert _texts(side)[0] == f"Proof{SEP}{{logo}}{SEP}a note"
    with Image.open(a.tiff_paths[0]) as x, Image.open(b.tiff_paths[0]) as y:
        assert x.size == y.size and x.mode == y.mode
        if kw.get("rep") == "CMYK":
            assert x.tag_v2.get(262) == y.tag_v2.get(262) == 5     # separated
    if kw.get("export_pdf"):
        assert b.pdf_path.stat().st_size > a.pdf_path.stat().st_size
        import pypdfium2
        doc = pypdfium2.PdfDocument(str(b.pdf_path))
        px = np.asarray(doc[0].render(scale=150 / 72).to_pil().convert("RGB"))
        pink = np.abs(px.astype(int) - (255, 69, 115)).max(axis=2) < 40
        plain = pypdfium2.PdfDocument(str(a.pdf_path))
        qx = np.asarray(plain[0].render(scale=150 / 72).to_pil()
                        .convert("RGB"))
        was = np.abs(qx.astype(int) - (255, 69, 115)).max(axis=2) < 40
        assert pink.sum() > was.sum()          # the second wordmark's IQ


def test_other_charts_are_untouched(tmp_path):
    """`i1io_notes` is an i1iO's: another instrument's chart ignores it."""
    from tests.test_i1io_chart import _ti1
    from workflow.layout_engine import chart
    got = []
    for k, kw in enumerate(({}, {"i1io_notes": "x"})):
        d = tmp_path / str(k)
        d.mkdir()
        r = chart.build_chart(_ti1(d / "c.ti1", 60), d / "c", instrument="i1",
                              paper="A4", dpi=72, seed=1, chart_date="x", **kw)
        got.append(_image(r.tiff_paths[0]))
    assert np.array_equal(*got)
    assert P.plan_of({"instrument": "i1", "paper": "A3"}) is None


# ---- the review of step 6b (REVIEW_5b_6) ----------------------------------------------

BREAKS = {"a line break": "first\nsecond", "windows": "first\r\nsecond",
          "old mac": "first\rsecond", "a tab": "first\tsecond",
          "nul": "first\x00second", "with blanks": "first  \n  second",
          "unicode": "first\u2028second", "a paragraph": "first\n\n\nsecond",
          "bell": "first\x07\x1b second"}


@pytest.mark.parametrize("what", sorted(BREAKS))
def test_a_line_break_is_one_space(what):
    typed = BREAKS[what]
    assert C.one_line(typed) == "first second"
    ctx = {C.NOTES_CTX: typed, C.LOGO_CTX: True}
    assert C.page_note(0, 1, ctx) == "first second"
    assert C.page_line_parts("P", 0, 1, typed, ctx) == ("P", "first second")


@pytest.mark.parametrize("language", ["en", "de"])
@pytest.mark.parametrize("crosses", [True, False])
@pytest.mark.parametrize("paper,n", [("A4", 60), ("A3", 600)])
def test_a_line_break_never_stops_generate(tmp_path, paper, n, crosses,
                                           language):
    from core import i18n
    before = i18n.current_language()
    i18n.set_language(language)
    try:
        for where in ({"notes": "a\nb"}, {"text": "a\r\nb"},
                      {"notes": "c\n\td\x00", "text": "a\nb"}):
            _res, side = _build(tmp_path / "x", paper, n, dpi=72,
                                i1io_crosses=crosses, **where)
            for k, t in enumerate(_texts(side), 1):
                assert "Proof" in t and not any(ord(c) < 32 for c in t)
                assert (f"{k}/2" in t) is (paper == "A3")
                if crosses:
                    assert "a b" in t
    finally:
        i18n.set_language(before)


def test_a_pasted_line_break_stays_stored_as_it_was(qtbot):
    """The notes box keeps a pasted break, and what is stored keeps it too:
    only the printed line has a space there."""
    from PyQt6.QtWidgets import QApplication, QLineEdit
    from types import SimpleNamespace
    from workflow.chart_creator import ChartCreator
    e = QLineEdit()
    qtbot.addWidget(e)
    QApplication.clipboard().setText("a\nb")
    e.paste()
    kw = {}
    params = SimpleNamespace(instrument="IO2", chart_notes=e.text())
    ChartCreator._add_i1io_notes(kw, params)
    assert kw["i1io_notes"] == params.chart_notes == e.text()
    assert C.page_note(0, 1, {C.NOTES_CTX: "a\nb", C.LOGO_CTX: True}) == "a b"


@pytest.mark.parametrize("size", [0.0, 3.0, 4.0, 6.0])
@pytest.mark.parametrize("note", ["a note", "x" * 130, "word " * 400])
def test_a_note_never_changes_the_rest_of_the_line(size, note):
    """The notes are the first thing shortened: the sheet text keeps the size
    and the words it has without them, and so does the wordmark."""
    style = C.SheetTextStyle(family="Inter", bold=True, size_mm=size) \
        if size else None
    w, h = 210.0, 297.0
    from workflow.layout_engine import geometry, instruments
    kw = {"instrument": "IO2", "paper": "A4", "i1io_limits": 2}
    g = instruments.geom_from_build_kwargs(kw)
    lay = geometry.compute(g, w, h, 1000)

    def plan(n, crosses):
        return C.line_plan(g, lay, w, h, 0, name="Proof",
                           sheet_text="My sheet text", dpi=150, style=style,
                           crosses=crosses, text_ctx={C.NOTES_CTX: n,
                                                      C.LOGO_CTX: True})
    for crosses in (True, False):
        a, b = plan("", crosses), plan(note, crosses)
        assert b["text"].startswith(a["text"])
        assert a["text_size_px"] == b["text_size_px"]
        assert (a["wordmark"] or {}).get("size_mm") == (
            b["wordmark"] or {}).get("size_mm")
        if b["note"]:
            pa, pb = a.get("parts"), b["parts"]
            if pa:
                assert [p["size_px"] for p in pa] == [
                    p["size_px"] for p in pb[:-1]]
                assert [p["text"] for p in pa] == [p["text"] for p in pb[:-1]]
                assert pb[-1]["size_px"] <= pa[-1]["size_px"]
            lo, hi = b["group"]
            assert lo >= 0 and hi <= h
            # still centred where it was, and where the parts say
            assert sum(b["group"]) == pytest.approx(sum(a["group"]), abs=0.01)
            ys = [p["y"] for p in pb]
            assert ys == sorted(ys, reverse=True) and max(ys) <= hi + 1e-6


def test_the_note_is_no_larger_than_the_text_and_never_outlives_it():
    style = C.SheetTextStyle(family="Inter", bold=True, size_mm=3.0)
    plan = C.styled_line_plan(210.0, 297.0, "P", "text", 150, style)
    plan["parts"][-1]["size_px"] = 9
    kw = dict(room=250.0, mid_y=148.5, top_y=270.0, up=5.0, down=5.0,
              style=style)
    got = C.add_note(dict(plan, parts=[dict(p) for p in plan["parts"]]),
                     "a note", 150, **kw)
    assert got["note"] == "a note" and got["parts"][-1]["size_px"] == 9
    # a part before it was shortened or left off: no note
    got = C.add_note(dict(plan), "a note", 150,
                     before=("P", "another text"), **kw)
    assert got["note"] == "" and got["text"] == plan["text"]
    assert not got["note_whole"]


def test_the_note_stands_where_the_line_ends(tmp_path):
    """The pen of the note starts where the text before it stops: drawn in
    parts, the line is the one run of text it would be."""
    _r, one = _build(tmp_path / "t", text="My text  ·  a note", dpi=300)
    _r, two = _build(tmp_path / "n", text="My text", notes="a note", dpi=300)
    assert _texts(one) == _texts(two)
    a, b = _image(tmp_path / "t" / "c.tif"), _image(tmp_path / "n" / "c.tif")
    assert (a != b).any(axis=2).sum() < 200         # (a pixel's rounding)


def test_a_long_note_costs_no_time():
    """A note has no limit: what is measured does not grow with it."""
    from workflow.layout_engine import geometry, instruments
    g = instruments.geom_from_build_kwargs(
        {"instrument": "IO2", "paper": "A4", "i1io_limits": 2})
    lay = geometry.compute(g, 210.0, 297.0, 500)
    calls = []
    real = C._tlen
    C._tlen = lambda *a: calls.append(1) or real(*a)
    try:
        C.line_plan(g, lay, 210.0, 297.0, 0, name="P", dpi=300,
                    text_ctx={C.NOTES_CTX: "word " * 4000, C.LOGO_CTX: True})
    finally:
        C._tlen = real
    assert len(calls) < 60


def test_a_note_that_does_not_print_whole_is_said(tmp_path):
    from workflow import measurement_messages as M
    for k, (notes, want) in enumerate((
            ("a note", None), ("word " * 100, M._I1IO_NOTE_SHORTENED))):
        res, side = _build(tmp_path / str(k), notes=notes, n=60)
        assert (want in res.notes) is (want is not None)
        if want is None:
            assert not any("chart notes" in v for v in res.notes)
    # no room at all: a long name
    res, side = _build(tmp_path / "l", notes="hello", text="word " * 100)
    assert M._I1IO_NOTE_LEFT_OFF in res.notes
    assert "hello" not in _texts(side)[0]
    # "Measured from Preview" says the same before anything is built
    from workflow.layout_engine.presets import default_recipe
    kw = default_recipe("IO2", "A4").build_kwargs()
    for notes, want in (("a note", None),
                        ("word " * 100, M._I1IO_NOTE_SHORTENED)):
        _s, warn = C.preview_checks({**kw, "area_target_count": 60,
                                     "i1io_notes": notes})
        assert [v for v in warn if "chart notes" in v] == (
            [want] if want else [])


def test_an_i1io_chart_gets_no_right_edge_notice(qtbot, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs import tab_chart
    from workflow.layout_engine.presets import default_recipe
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "i.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "p"))
    s.set("use_chromiq_layout_engine", True)
    tab = tab_chart.TabChart(ArgyllRunner(s), FileManager(s), s)
    qtbot.addWidget(tab)
    tab._switch_mode("manual")
    from workflow.layout_engine import chart
    from tests.test_i1io_chart import _ti1
    for inst, edge, line in (("IO2", False, True), ("i1", True, False)):
        k = default_recipe(inst, "A4").build_kwargs()
        k.update(dpi=72, seed=1)
        r = chart.build_chart(_ti1(tmp_path / f"{inst}.ti1", 200),
                              tmp_path / inst, **k)
        (tmp_path / f"{inst}.channels.json").write_text(json.dumps(
            {"layout": {"engine": "chromiq",
                        "recipe": default_recipe(inst, "A4").to_dict()}}), encoding="utf-8")
        tab._margin_tiffs, tab._margin_ti2 = r.tiff_paths, r.ti2_path
        tab._manual_layout_panel.set_recipe(
            replace(default_recipe(inst, "A4"), dpi=72))
        tab._manual_chart_notes_edit.setText("a very long note " * 30)
        warns, _over = tab._engine_text_notes(None)
        said = " ".join(warns)
        assert ("down the right edge" in said) is edge, inst
        assert ("line with the chart's name" in said) is line, inst


def test_the_lines_own_keys_are_no_placeholders(tmp_path):
    _r, side = _build(tmp_path, notes="x {_logo} {_pages} {_notes} {patchcount} y")
    assert "x {_logo} {_pages} {_notes} 72 patches y" in _texts(side)[0]


def test_a_clip_borders_text_has_the_pieces_own_values(tmp_path):
    """The review's survivor X4: the clip border of piece 2 says piece 2."""
    import numpy as np
    from workflow.layout_engine import chart  # noqa: F401
    kw = dict(dpi=150, i1io_clip_border=True, clip_content_mode="text",
              clip_border_width=18.0)
    texts = {}
    _r, side = _build(tmp_path / "n", "A3", 1150, **kw)
    n, per = len(side["pages"]), sum(
        len(st["patches"]) for st in side["pages"][0]["strips"])
    last = sum(len(st["patches"]) for st in side["pages"][-1]["strips"])
    assert n == 3
    for t in ("sheet {sheet} count {patchcount}",
              f"sheet 2/2 count {last} patches",
              f"sheet 1/2 count {per} patches"):
        _r, _side = _build(tmp_path / f"t{len(texts)}",
                           "A3", 1150, clip_text=t, **kw)
        texts[t] = [_image(p) for p in _r.tiff_paths]
    ours = texts["sheet {sheet} count {patchcount}"]
    assert np.array_equal(ours[2], texts[f"sheet 2/2 count {last} patches"][2])
    assert np.array_equal(ours[0], texts[f"sheet 1/2 count {per} patches"][0])
    assert not np.array_equal(ours[0], ours[1])
    assert not np.array_equal(
        ours[0], texts[f"sheet 2/2 count {last} patches"][0])
