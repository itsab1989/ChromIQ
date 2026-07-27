"""#131 (Knut, 2026-07-26): the reading times sit under the strips they belong
to, on their sides, so a chart with many strips still has room for every one.

Geometry, not looks: the panel is given x positions and must keep them, and it
must be tall enough for the longest time it has to draw.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtGui import QFontMetrics                  # noqa: E402
from PyQt6.QtWidgets import QApplication              # noqa: E402

from ui.strip_times_panel import StripTimesPanel      # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_it_stays_out_of_the_way_until_there_is_something_to_say(qapp):
    panel = StripTimesPanel()
    assert panel.isHidden()
    assert panel.sizeHint().height() == 0


def test_it_grows_tall_enough_for_the_longest_time_on_its_side(qapp):
    """Rotated text needs the text's WIDTH as the panel's height."""
    panel = StripTimesPanel()
    panel.set_content("Strip reading times, 15 patches:",
                      [(10, "5.1 s"), (40, "12.4 s")])
    longest = max(QFontMetrics(panel._time_font()).horizontalAdvance(t)
                  for t in ("5.1 s", "12.4 s"))
    assert panel.sizeHint().height() >= longest + panel.PAD_TOP


def test_the_verdict_is_no_longer_this_panel_s_business(qapp):
    """It moved out into a label of its own beneath the frame (Knut, #131
    2026-07-27): inside the panel it was drawn, and drawing is the first thing a
    squeezed layout loses. A label with a minimum height cannot be lost."""
    panel = StripTimesPanel()
    panel.set_content("", [(30, "5.1 s")], "Too fast", "#ff6b6b")
    without = StripTimesPanel()
    without.set_content("", [(30, "5.1 s")])
    assert panel.sizeHint() == without.sizeHint(), \
        "the verdict must not change how tall this panel is any more"


def test_the_columns_keep_the_positions_they_were_given(qapp):
    """They are the strips' own centres — the panel must not re-space them, or
    the times would sit under the wrong strips."""
    panel = StripTimesPanel()
    panel.set_content("", [(120, "5.1 s"), (37, "6.0 s"), (240, "4.8 s")])
    assert [x for x, _t in panel._columns] == [120, 37, 240]


def test_many_strips_are_all_kept(qapp):
    """Thirty-five strips across a landscape page: every one is drawn, since
    the times are on their sides rather than written out in a row."""
    panel = StripTimesPanel()
    cols = [(20 * i, f"{4 + i % 5}.{i % 10} s") for i in range(35)]
    panel.set_content("Strip reading times, 15 patches:", cols)
    assert len(panel._columns) == 35
    assert not panel.isHidden()


def test_clearing_hides_it_again(qapp):
    panel = StripTimesPanel()
    panel.set_content("x", [(10, "5.1 s")], "verdict")
    panel.clear()
    assert panel.isHidden()
    assert panel._columns == [] and panel._verdict == ""


def test_it_paints_without_error_in_every_state(qapp):
    """Painting is exercised for real — a rotated-text mistake shows up here."""
    from PyQt6.QtGui import QPixmap
    for label, cols, verdict in (
            ("", [], ""),
            ("Strip reading times, 15 patches:", [(30, "5.1 s")], ""),
            ("Strip reading times, 15 patches:", [(30, "5.1 s"), (90, "9.9 s")],
             "Too fast — read more slowly"),
    ):
        panel = StripTimesPanel()
        panel.set_content(label, cols, verdict, "#ff6b6b")
        panel.resize(400, max(40, panel.sizeHint().height()))
        pm = QPixmap(panel.size())
        panel.render(pm)          # would raise if the painter were misused


@pytest.mark.parametrize("cols,verdict", [
    ([(30, "5.1 s")], ""),
    ([(30, "5.1 s"), (80, "12.4 s ✕")], "Too fast — read more slowly"),
    ([(20 * i, f"{i}.{i} s") for i in range(30)],
     "Too fast — read more slowly · 140 ms per patch (aim for 600 ms or more)"),
])
def test_the_panel_always_asks_for_enough_room_to_draw_what_it_draws(
        qapp, cols, verdict):
    """The invariant behind a clipped verdict line: the height requested must
    cover the rotated times, the gap and the verdict — whatever the font."""
    from PyQt6.QtGui import QFontMetrics
    panel = StripTimesPanel()
    panel.set_content("Strip reading times, 15 patches:", cols, verdict, "#ff6b6b")
    needed = panel.PAD_TOP + panel._times_height() + panel.PAD_BOTTOM
    assert panel.sizeHint().height() >= needed, (
        f"asks for {panel.sizeHint().height()}px but draws down to {needed}px")


def test_the_panel_forces_the_room_it_needs(qapp):
    """A layout can squeeze a widget to its minimum, and the verdict line was
    what vanished — twice. The minimum is now what the panel actually draws."""
    panel = StripTimesPanel()
    panel.set_content("Strip reading times:\n(15 patches)",
                      [(30, "5.1 s"), (90, "9.9 s")],
                      "Too fast — read more slowly", "#ff6b6b")
    assert panel.minimumHeight() == panel.sizeHint().height()
    assert panel.minimumHeight() > 0


def test_a_two_line_label_is_kept_as_two_lines(qapp):
    panel = StripTimesPanel()
    panel.set_content("Strip reading times:\n(15 patches)", [(30, "5.1 s")])
    assert "\n" in panel._label
    panel.resize(400, panel.sizeHint().height())
    from PyQt6.QtGui import QPixmap
    panel.render(QPixmap(panel.size()))        # both lines must paint cleanly
