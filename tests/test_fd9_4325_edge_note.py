"""4.3.25, F6 (report point 8.1): the printer edge note on an FD-9 chart.

A 6.4 mm unprintable edge cuts the FD-9's side marks (5.5 mm in, 3 mm
wide). 4.3.24's note called them "printed text", said the chart could be
printed and advised a text distance the FD-9 greys. The marks are what the
FD-9 finds the sheet by, so the note now says the FD-9 then cannot find the
sheet, and gives advice that can be followed.
"""
from tests._fd9_beta import fd9_beta_on, fd9_windows  # noqa: F401

import pytest

from tests.test_fd9_chart_creation import ti1
from workflow import measurement_messages as MM
from workflow import printer_edges as PE
from workflow.fd9.chart import build_chart, capacity


def _chart(tmp_path, pages=1):
    count = capacity("A4") * (pages - 1) + 40
    src, _ = ti1(tmp_path, rep="RGB", tokens=("R", "G", "B"), count=count)
    r = build_chart(src, tmp_path / "c", paper="A4", dpi=100,
                    randomize=False, sheet_project="P", sheet_run="1")
    return [(p, 0) for p in r.tiff_paths]


@pytest.mark.parametrize("pages", [1, 2])
def test_marks_in_the_edge_are_needed_for_measuring_never_text(tmp_path,
                                                               pages):
    pp = _chart(tmp_path, pages)
    edges = PE.Edges(6.4, 6.4, 6.4, 6.4, "ppd")
    loss = PE.losses_for_chart(pp, edges, (210.0, 297.0))
    assert set(loss.fd9_marks) == {"left", "right"}
    assert "left" not in loss.text and "right" not in loss.text
    note = MM.edge_note("PRO-300", edges, loss)
    for words in ("cannot find the patches", "refuses to measure",
                  "do not print the chart like this", "borderless",
                  "larger sheet of paper", "closer to the edge"):
        assert words in note, words
    assert "on the left, on the right" in note
    # Never the advice for text, and never "you can print it like this".
    assert "Text distance" not in note
    assert "you can print the chart like this" not in note
    assert "—" not in note


def test_a_narrow_edge_that_misses_the_marks_says_nothing_of_them(tmp_path):
    pp = _chart(tmp_path)
    loss = PE.losses_for_chart(pp, PE.Edges(3.0, 3.0, 3.0, 3.0, "ppd"),
                               (210.0, 297.0))
    assert loss.fd9_marks == []


def test_with_the_beta_off_nothing_fd9_is_read(tmp_path):
    pp = _chart(tmp_path)
    from workflow.fd9 import support
    support.set_enabled_for_this_process(False)
    assert PE._fd9_mark_boxes(pp[0][0]) == []
    loss = PE.losses_for_chart(pp, PE.Edges(6.4, 6.4, 6.4, 6.4, "ppd"),
                               (210.0, 297.0))
    assert loss.fd9_marks == []          # 4.3.24's note, as it was
    assert loss.text


# ---- 4.3.25 final review, L1: the page number and the clip border --------
def _chart_with(tmp_path, pages=2, clip=True):
    count = capacity("A4") * (pages - 1) + 40
    src, _ = ti1(tmp_path, rep="RGB", tokens=("R", "G", "B"), count=count)
    r = build_chart(src, tmp_path / "c", paper="A4", dpi=100,
                    randomize=False, sheet_project="P", sheet_run="1",
                    clip_border=clip)
    return [(p, 0) for p in r.tiff_paths]


def test_the_clip_border_in_the_edge_is_an_fd9_part_with_its_own_advice(tmp_path):
    """The band ends 12 mm before the trailing edge; a 13 mm bottom edge
    cuts it and nothing else (the bottom marks end 28 mm in)."""
    pp = _chart_with(tmp_path, pages=2, clip=True)[:1]   # a full sheet
    edges = PE.Edges(left=3.0, top=3.0, right=3.0, bottom=13.0, source="ppd")
    loss = PE.losses_for_chart(pp, edges, (210.0, 297.0))
    assert loss.fd9_clip == ["bottom"]
    assert loss.fd9_marks == [] and loss.fd9_page_label == []
    assert not loss.text, "the clip border was called printed text"
    note = MM.edge_note("PRO-300", edges, loss)
    assert "part of the FD-9 clip border at the bottom" in note
    assert "set “Clip border” to Off" in note
    assert "closer to the edge of the paper" in note
    assert "you can print the chart like this" in note
    # never the text advice, whose control the FD-9 greys
    assert "Text distance" not in note
    assert "page number" not in note
    assert "—" not in note


def test_the_page_number_in_the_edge_is_an_fd9_part_with_its_own_advice(tmp_path):
    """The page number starts 10 mm from the leading edge; an 11 mm top
    edge cuts it and nothing else (the arrow starts 15 mm in)."""
    pp = _chart_with(tmp_path, pages=2, clip=False)
    edges = PE.Edges(left=3.0, top=11.0, right=3.0, bottom=3.0, source="ppd")
    loss = PE.losses_for_chart(pp, edges, (210.0, 297.0))
    assert loss.fd9_page_label == ["top"]
    assert loss.fd9_marks == [] and loss.fd9_clip == []
    assert not loss.text
    note = MM.edge_note("PRO-300", edges, loss)
    assert "the small page number at the top" in note
    assert "has no setting" in note and "closer to the edge" in note
    assert "Clip border" not in note
    assert "Text distance" not in note


def test_both_parts_are_named_with_both_fixes(tmp_path):
    pp = _chart_with(tmp_path, pages=2, clip=True)
    edges = PE.Edges(left=3.0, top=11.0, right=3.0, bottom=13.0, source="ppd")
    loss = PE.losses_for_chart(pp, edges, (210.0, 297.0))
    assert loss.fd9_page_label == ["top"] and loss.fd9_clip == ["bottom"]
    note = MM.edge_note("PRO-300", edges, loss)
    assert ("the small page number at the top; part of the FD-9 clip border "
            "at the bottom") in note
    assert "has no setting" in note and "set “Clip border” to Off" in note


def test_with_the_beta_off_the_page_number_and_clip_are_not_read(tmp_path):
    pp = _chart_with(tmp_path, pages=2, clip=True)
    from workflow.fd9 import support
    support.set_enabled_for_this_process(False)
    assert PE._fd9_furniture_boxes(pp[0][0]) == {}
