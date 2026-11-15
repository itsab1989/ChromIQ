"""What the person switches on is printed, or the build says why not (the
owner, 2026-11-15, on 4.3.38, Manual with the i1iSis family):

* *"in manual i can select strip letters place ... there are none shown at
  all"*: the letters are switched on by the engine's "Show strip
  indicators" (off by default for the i1iSis, as i1Profiler prints none);
  the place only chooses WHERE. The place is now greyed while the box is
  off, with its own help as the tooltip, which names the box.
* *"i can also turn on row indicators though and this has no effect"*: on
  every default A4 chart (28 columns of 6 mm) the row numbers needed 200.4 mm
  of the 200 inside the margins at their full 3 mm, so the chart was not
  widened for them and they were dropped. They are now set smaller first,
  down to the 1.5 mm legibility floor, as the letters are.

For every combination of strip letters x place x row numbers, on a default
A4 and an XL chart: the page carries the letters / numbers where the options
say, inside no keep-out zone, or the build's warnings say why they are not.
"""
from __future__ import annotations

import itertools

import pytest

from workflow.isis import chart as C


@pytest.fixture(autouse=True)
def isis_on():
    from workflow.isis import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    yield
    support._latched = before


SHEETS = {
    "A4 default": (896, 210.0, 297.0, ""),
    "A4 few patches": (300, 210.0, 297.0, ""),
    "XL A3": (1617, 297.0, 420.0, "xl"),
}


@pytest.mark.parametrize("sheet_name", sorted(SHEETS))
@pytest.mark.parametrize("letters,place,rows", list(itertools.product(
    (False, True), ("top", "bottom"), (False, True))))
def test_what_is_switched_on_is_printed(sheet_name, letters, place, rows):
    n, w, h, model = SHEETS[sheet_name]
    _o, g, sheet = C.layout_for(n, w, h, {
        C.COUNT_KEY: n, C.MODEL_KEY: model, "draw_indicators": letters,
        C.LETTERS_KEY: place, "row_indicators": rows})
    for page in range(g.P):
        items, off = C.plan_page(sheet, page, name="labels", title="labels")
        got_letters = [i for i in items if i.role == "strip_letter"]
        got_rows = [i for i in items if i.role == "row_number"]
        assert C.keep_out_violations(sheet, items) == []
        if letters:
            assert len(got_letters) == g.C or "strip_letters" in off
            if got_letters:
                ys = {round(i.box[1], 3) for i in got_letters}
                below_grid = all(y > sheet.y0 + sheet.height / 2 for y in ys)
                assert below_grid == (place == "bottom"), (place, ys)
        else:
            assert not got_letters
        if rows:
            # on these sheets there IS room: printed, not left off
            assert len(got_rows) == g.R, (sheet_name, off)
            assert "row_numbers" not in off
            assert min(i.size for i in got_rows) >= C.LABEL_MIN_MM - 1e-9
        else:
            assert not got_rows


def test_row_numbers_left_off_are_said(tmp_path):
    """Tight margins on A4 leave no room inside 230 mm: left off, and the
    build's warnings (the Create Chart log, M-ISIS-KEEP-OUT) say so."""
    from workflow.layout_engine import chart
    rows = "\n".join(f"{i + 1} {i % 100}.0 {(i * 7) % 100}.0 "
                     f"{(i * 13) % 100}.0" for i in range(896))
    ti1 = tmp_path / "c.ti1"
    ti1.write_text(
        "CTI1\n\nDESCRIPTOR \"t\"\nCOLOR_REP \"RGB\"\n\n"
        "NUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS 896\nBEGIN_DATA\n{rows}\nEND_DATA\n",
        encoding="utf-8")
    res = chart.build_chart(ti1, tmp_path / "tight", instrument="XRISIS",
                            paper="A4", dpi=60, project="tight",
                            isis_tight=True, row_indicators=True)
    assert any(C.keep_out_message("row_numbers") == w for w in res.warnings)


def test_a_chart_whose_numbers_fitted_is_unchanged():
    """Where the numbers fitted at full size (XL on A3), the outline is as
    wide as before: the smaller sizes are tried only when they did not."""
    _o, g, sheet = C.layout_for(1617, 297.0, 420.0, {
        C.COUNT_KEY: 1617, C.MODEL_KEY: "xl", "row_indicators": True})
    items, _off = C.plan_page(sheet, 0, name="x", title="x")
    assert {round(i.size, 2) for i in items if i.role == "row_number"} == {3.0}


def test_the_place_is_greyed_while_the_letters_are_off(qapp):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    try:
        k = p.instr.findData("XRISIS")
        p.instr.setCurrentIndex(k)
        p.instr.activated.emit(k)
        qapp.processEvents()
        assert not p.show_indicators.isChecked()     # the i1iSis default
        assert not p.isis_letters.isEnabled()
        assert "Show strip indicators" in p.isis_letters.toolTip()
        p.show_indicators.setChecked(True)
        assert p.isis_letters.isEnabled()
        assert p.isis_letters.toolTip() == ""
        p.show_indicators.setChecked(False)
        assert not p.isis_letters.isEnabled()
    finally:
        p.deleteLater()
        qapp.processEvents()
