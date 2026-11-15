"""4.3.39 integration, addition (ii): "Show row indicators" is on for an
i1iSis chart, but the sheet has no room for the row numbers (they go right of
the right diamonds, inside the outline, and the chart already takes all the
width it may). Branch fix/isis-notes-band said it only in the Create Chart
log, with the marker-zone sentence ("Room for text: the first 12 mm ..."),
which names nothing that makes room for the numbers. Now one text,
M-ISIS-ROW-NUMBERS-NO-ROOM, in the log and as a note on the panel's
"i1iSis chart (Beta)" group, saying what makes room. The side file records
whether the numbers were printed, only while the option is on.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from workflow.isis import chart as C


@pytest.fixture(autouse=True)
def isis_on():
    from workflow.isis import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    yield
    support._latched = before


def _ti1(tmp_path: Path, n: int = 896) -> Path:
    rows = "\n".join(f"{i + 1} {i % 100}.0 {(i * 7) % 100}.0 "
                     f"{(i * 13) % 100}.0" for i in range(n))
    ti1 = tmp_path / "c.ti1"
    ti1.write_text(
        "CTI1\n\nDESCRIPTOR \"t\"\nCOLOR_REP \"RGB\"\n\n"
        "NUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {n}\nBEGIN_DATA\n{rows}\nEND_DATA\n",
        encoding="utf-8")
    return ti1


def _side(base: Path) -> dict:
    return json.loads(Path(str(base) + ".isis.json").read_text("utf-8"))


def test_no_room_is_said_with_what_makes_room_and_recorded(tmp_path):
    from workflow import measurement_messages as M
    from workflow.layout_engine import chart
    ti1 = _ti1(tmp_path)
    res = chart.build_chart(ti1, tmp_path / "tight", instrument="XRISIS",
                            paper="A4", dpi=60, project="tight",
                            isis_tight=True, row_indicators=True)
    text = M.isis_row_numbers_no_room_text()
    assert text in res.warnings
    assert "Tight margins" in text and "wider paper" in text
    # not the marker-zone sentence, which names nothing that helps here
    assert "Room for text" not in text
    assert _side(tmp_path / "tight")["row_numbers"] == "left_off"


def test_where_there_is_room_nothing_is_said(tmp_path):
    from workflow.layout_engine import chart
    ti1 = _ti1(tmp_path)
    res = chart.build_chart(ti1, tmp_path / "roomy", instrument="XRISIS",
                            paper="A4", dpi=60, project="roomy",
                            row_indicators=True)
    assert not res.warnings
    assert _side(tmp_path / "roomy")["row_numbers"] == "printed"


def test_the_side_file_is_as_before_while_the_option_is_off(tmp_path):
    from workflow.layout_engine import chart
    chart.build_chart(_ti1(tmp_path), tmp_path / "off", instrument="XRISIS",
                      paper="A4", dpi=60, project="off")
    assert "row_numbers" not in _side(tmp_path / "off")


@pytest.mark.parametrize("label,tight,paper,margins,room", [
    ("A4 tight: no room", True, (210.0, 297.0), None, False),
    ("tight margins off", False, (210.0, 297.0), None, True),
    ("wider side margins", True, (210.0, 297.0), (5, 10, 5, 10), True),
    ("wider paper (A3)", True, (297.0, 420.0), None, True),
])
def test_what_the_text_advises_really_makes_room(label, tight, paper,
                                                 margins, room):
    """Each remedy the note names, measured on the A4 tight case that has
    no room: switching tight margins off, wider page margins, wider paper."""
    opts = {C.COUNT_KEY: 896, "row_indicators": True, C.TIGHT_KEY: tight}
    if margins:
        opts["margins"] = margins
    _o, _g, sheet = C.layout_for(896, paper[0], paper[1], opts)
    items, off = C.plan_page(sheet, 0, name="x", title="x")
    printed = any(i.role == "row_number" for i in items)
    assert printed == room, (label, off)


def test_the_panel_shows_and_hides_the_note(qapp):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    try:
        assert not p.isis_row_note.isVisibleTo(p)
        p.isis_row_numbers_note("no room")
        assert p.isis_row_note.text() == "⚠ no room"
        assert not p.isis_row_note.isHidden()
        p.isis_row_numbers_note(None)
        assert p.isis_row_note.isHidden()
    finally:
        p.deleteLater()
        qapp.processEvents()


def test_the_tab_reads_the_chart_in_the_preview(tmp_path):
    from ui.tabs.tab_chart import TabChart
    from workflow import measurement_messages as M
    from workflow.layout_engine import chart
    ti1 = _ti1(tmp_path)
    chart.build_chart(ti1, tmp_path / "tight", instrument="XRISIS",
                      paper="A4", dpi=60, project="tight", isis_tight=True,
                      row_indicators=True)
    chart.build_chart(ti1, tmp_path / "roomy", instrument="XRISIS",
                      paper="A4", dpi=60, project="roomy",
                      row_indicators=True)
    said = []
    panel = SimpleNamespace(_isis_support=True,
                            isis_row_numbers_note=said.append)
    for stem in ("tight", "roomy", None):
        fake = SimpleNamespace(
            _manual_layout_panel=panel,
            _margin_ti2=(tmp_path / f"{stem}.ti2") if stem else None)
        TabChart._refresh_isis_row_numbers_note(fake)
    assert said == [M.isis_row_numbers_no_room_text(), None, None]
    # with the Beta off the panel is never asked
    off = SimpleNamespace(_isis_support=False,
                          isis_row_numbers_note=said.append)
    TabChart._refresh_isis_row_numbers_note(SimpleNamespace(
        _manual_layout_panel=off, _margin_ti2=tmp_path / "tight.ti2"))
    assert len(said) == 3
