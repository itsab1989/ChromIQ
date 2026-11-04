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
