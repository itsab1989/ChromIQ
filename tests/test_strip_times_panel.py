"""#131 (Knut, 2026-07-26): the reading times sit under the strips they belong
to, on their sides, so a chart with many strips still has room for every one.

Geometry, not looks: the panel pairs each strip index with the position
provider's CURRENT answer at paint time — stored positions went stale whenever
the preview re-fitted and the times drifted right across the sheet (Sebastian,
2026-08-11) — and it must be tall enough for the longest time it has to draw.
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


def test_positions_come_from_the_provider_at_paint_time(qapp):
    """The strips' centres are asked for FRESH — a stored copy went stale the
    moment the preview re-fitted, and the times drifted right across the
    sheet (Sebastian, 2026-08-11)."""
    panel = StripTimesPanel()
    centres = [80, 240, 400]
    panel.set_position_provider(lambda: centres)
    panel.set_content("", [(0, "6.0 s"), (1, "5.1 s"), (2, "4.8 s")])
    fm = QFontMetrics(panel._time_font())
    assert [x for x, _t, _i, _b in panel._placed_columns(0, fm)] == [80, 240, 400]
    # The preview shrinks — the very next paint must follow, with no refresh.
    centres[:] = [60, 180, 300]
    assert [x for x, _t, _i, _b in panel._placed_columns(0, fm)] == [60, 180, 300]


def test_many_strips_are_all_kept_when_there_is_room(qapp):
    """Thirty-five strips across a landscape page: every one is drawn, since
    the times are on their sides rather than written out in a row."""
    panel = StripTimesPanel()
    fm = QFontMetrics(panel._time_font())
    pitch = fm.height() + 2                      # just enough room for each
    panel.set_position_provider(lambda: [pitch * i for i in range(35)])
    cols = [(i, f"{4 + i % 5}.{i % 10} s") for i in range(35)]
    panel.set_content("Strip reading times, 15 patches:", cols)
    assert len(panel._placed_columns(0, fm)) == 35
    assert not panel.isHidden()


def test_a_tight_preview_staggers_into_two_bands_before_thinning(qapp):
    """When strips sit a little closer than a rotated label is wide, the
    labels split into two staggered bands — every time stays visible, none
    overlap within a band, and the panel asks for the second band's room
    ("for this very small one we still need a solution" — Sebastian,
    2026-08-11)."""
    panel = StripTimesPanel()
    fm = QFontMetrics(panel._time_font())
    pitch = (fm.height() + 1) * 2 // 3           # too tight for one band,
    panel.set_position_provider(                 # roomy for two
        lambda: [pitch * i for i in range(12)])
    panel.set_content("", [(i, f"5.{i} s") for i in range(12)])
    one_band_height = panel.sizeHint().height()
    placed = panel._placed_columns(0, fm)
    assert len(placed) == 12, "staggering must keep EVERY time visible here"
    assert {b for _x, _t, _i, b in placed} == {0, 1}
    for band in (0, 1):
        xs = [x for x, _t, _i, b in placed if b == band]
        assert all(b_ - a >= fm.height() + 1 for a, b_ in zip(xs, xs[1:])), \
            "labels within one band must not overlap"
    assert panel._bands == 2
    assert panel.sizeHint().height() > one_band_height, \
        "the second band needs its own room"


def test_extremely_tight_strips_are_thinned_but_warnings_never_are(qapp):
    """When even two staggered bands cannot host every label, ordinary times
    may be skipped — but a too-fast warning is the whole point of the panel
    and must always be drawn."""
    panel = StripTimesPanel()
    fm = QFontMetrics(panel._time_font())
    pitch = max(2, (fm.height() + 1) // 4)       # far too tight even for two
    panel.set_position_provider(lambda: [pitch * i for i in range(12)])
    cols = [(i, f"5.{i} s", False) for i in range(12)]
    cols[7] = (7, "1.2 s ✕", True)               # the warning, mid-crowd
    panel.set_content("", cols)
    placed = panel._placed_columns(0, fm)
    assert 0 < len(placed) < 12, "too-tight strips must thin, not overlap"
    assert any(t == "1.2 s ✕" for _x, t, _i, _b in placed), \
        "a too-fast warning must never be thinned away"
    for band in (0, 1):
        xs = [x for x, _t, imp, b in placed if b == band and not imp]
        assert all(b_ - a >= fm.height() + 1 for a, b_ in zip(xs, xs[1:])), \
            "the ordinary times that remain must not overlap within a band"


def test_a_strip_index_the_provider_cannot_answer_is_skipped(qapp):
    """Fewer centres than indices (page changed, chart reloaded): the panel
    draws what it can place and never guesses."""
    panel = StripTimesPanel()
    panel.set_position_provider(lambda: [40])
    panel.set_content("", [(0, "5.1 s"), (5, "9.9 s")])
    fm = QFontMetrics(panel._time_font())
    placed = panel._placed_columns(0, fm)
    assert [(x, t) for x, t, _i, _b in placed] == [(40, "5.1 s")]


def test_the_panel_follows_the_preview_it_is_anchored_to(qapp):
    """set_reference_widget installs an event filter so a preview resize
    repaints the times immediately — no measurement event needed."""
    from PyQt6.QtWidgets import QWidget
    ref = QWidget()
    panel = StripTimesPanel()
    panel.set_reference_widget(ref)
    from PyQt6.QtCore import QEvent, QSize
    from PyQt6.QtGui import QResizeEvent
    seen = []
    panel.update = lambda *a: seen.append("update")      # noqa: PLW2901
    panel.eventFilter(ref, QResizeEvent(QSize(10, 10), QSize(20, 20)))
    assert seen == ["update"]


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
            ("Strip reading times, 15 patches:", [(0, "5.1 s")], ""),
            ("Strip reading times, 15 patches:", [(0, "5.1 s"), (1, "9.9 s")],
             "Too fast — read more slowly"),
    ):
        panel = StripTimesPanel()
        panel.set_position_provider(lambda: [30, 90])
        panel.set_content(label, cols, verdict, "#ff6b6b")
        panel.resize(400, max(40, panel.sizeHint().height()))
        pm = QPixmap(panel.size())
        panel.render(pm)          # would raise if the painter were misused
    # …and a provider that raises must never break a paint.
    def broken():
        raise RuntimeError("preview is gone")
    panel = StripTimesPanel()
    panel.set_position_provider(broken)
    panel.set_content("", [(0, "5.1 s")])
    panel.resize(400, max(40, panel.sizeHint().height()))
    panel.render(QPixmap(panel.size()))


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


def test_rotated_time_is_centred_on_its_strip(qapp):
    """The rotated glyph column must be visually centred on the x it was
    given — the old height/3 nudge parked every time ~10px right of its
    strip before widget offsets even started (Sebastian, 2026-08-11)."""
    from PyQt6.QtGui import QFont, QFontMetrics
    fm = QFontMetrics(QFont())
    x = 200
    tx = StripTimesPanel._column_translate_x(x, fm)
    left, right = tx - fm.descent(), tx + fm.ascent()
    centre = (left + right) / 2
    assert abs(centre - x) <= 1, (left, right, centre)
