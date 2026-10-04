"""Every help text and hover card tells red and yellow apart (Knut, #182 5980576263).

Knut, 2026-10-04: *"make sure all help text and the hover-over text during
measurements is written so the user understands the difference between the red
and yellow highlighting."*

Red: the reading is far from what it should be and may be a misread, read it
again. Yellow: the error is real (a re-read, similar patches in other strips,
or a colour range that has learned), keep it, do not read it again. The help
also says what the limits do, that the outlines are worked out again when they
change, and that Check & Refine judges on its own.
"""
from __future__ import annotations

import inspect

import pytest

from tests.test_beta8_every_colour_range_learns import _card, qapp  # noqa: F401

READ_AGAIN = "Read it again to find out."
NO_NEED = "No need to read it again."


@pytest.mark.parametrize("flag, peers", [
    ("confirmed", ()),            # by a re-read
    ("confirmed", ("E1",)),       # by similar patches
    ("learned", ()),              # learned from the colour range
])
def test_every_yellow_card_says_there_is_no_need_to_read_it_again(
        qapp, flag, peers):  # noqa: F811
    text = "\n".join(_card(qapp, flag=flag, colour_range="blue", range_k=3,
                           range_locs=("A6", "E1", "L1"), like_loc="A6",
                           prev_de=103.0, peer_locs=peers))
    assert NO_NEED in text and READ_AGAIN not in text, text


def test_the_red_card_says_read_it_again(qapp):  # noqa: F811
    text = "\n".join(_card(qapp, flag="", colour_range="blue", range_k=0))
    assert READ_AGAIN in text and NO_NEED not in text, text


def _source(obj) -> str:
    return inspect.getsource(obj)


def test_the_measure_tab_help_covers_both_colours_the_limits_and_check_refine():
    from ui.tabs import tab_measure as tm
    colours = tm._OVERLAY_TIP_COLOURS
    assert "red outline" in colours and "yellow outline" in colours
    assert "read it again" in colours and "do not read it again" in colours
    limits = tm._OVERLAY_TIP_LIMITS
    assert "worked out again" in limits and "press OK" in limits
    assert "Check & Refine judges on its own" in limits
    src = _source(tm.TabMeasure)
    # The overlay box (Guided and Manual), "What each patch shows", and the
    # hover help each carry them.
    assert src.count("tr(_OVERLAY_TIP_COLOURS)") >= 3
    assert src.count("tr(_OVERLAY_TIP_LIMITS)") >= 3
    assert "confirmed by similar patches: patches in other strips" in src


def test_no_help_still_describes_the_retired_spacing():
    """Beta 9 removed the ΔE 6 spacing between confirmations; the help that
    still said "at least ΔE 6 apart" described a rule that no longer exists."""
    from ui.dialogs import settings_dialog
    from ui.tabs import tab_measure
    for mod in (settings_dialog, tab_measure):
        assert "at least ΔE 6" not in _source(mod), mod.__name__


def test_preferences_help_tells_red_and_yellow_apart():
    from ui.dialogs import settings_dialog
    src = _source(settings_dialog)
    assert '"RED AND YELLOW\\n"' in src
    assert "Check & Refine judges on its own" in src
    assert "YELLOW OUTLINE\\n" not in src


def test_check_and_refine_help_states_its_purpose():
    from ui.tabs import tab_check_refine
    src = _source(tab_check_refine)
    # Guided and Manual each carry it under the threshold's help.
    assert src.count('tr("Check & Refine checks your measurement through the '
                     'profile built "') == 2


def test_getting_started_measure_card_names_both_colours():
    from ui import getting_started
    src = _source(getting_started)
    assert "A patch outlined in red may be a misread: read it again." in src
    assert '"outlined in yellow is confirmed as real: keep it."' in src
