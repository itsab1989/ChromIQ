"""Auto align's refusal on a honeycomb gives advice that can be followed.

Measured on screen on 2026-09-11, on Knut's own CR30 hexagonal chart and on a
rectangular chart of the same 648 colours built by the same engine:

* honeycomb, from the app's own seed and from a hand placement 166 px out: the
  corners move **0.0 px**, `is_placed()` stays False, and the window says so;
* rectangle, same drive: the corners land **0.6 px** from the true block
  corners.

Only the SEARCH stage declines. It returns "not recognised" with **zero**
candidates every time, because it borrows scanin's own recogniser and that hunts
the straight horizontal patch edges a grid of rectangles has, which a hexagon
does not have. The two stages after it are shape-agnostic in practice as well as
in principle: on the same honeycomb the check stage separates a right placement
from a wrong one by 0.969 against 0.514, with the floor at 0.80.

So the refusal is right and safe, and nothing here changes it. What was wrong is
the SENTENCE: the generic wording sends the user to drag the four corners
roughly around the chart and press Auto align again, which narrows the search to
inside them, and a narrower search of a honeycomb finds nothing either. The
advice could not work however carefully it was followed.
"""
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from workflow import measurement_messages as M  # noqa: E402

#: The one ending the honeycomb reaches, and the only one whose advice the
#: shape of a patch invalidates.
SEARCH_FAILED = "not-recognised"


def test_a_honeycomb_gets_its_own_words_for_the_search_failing():
    msg = M.scan_align_refusal(SEARCH_FAILED, hexagonal=True)
    assert msg.id == "M-SCAN-ALIGN-NOT-FOUND-HEX"
    assert msg is not M.scan_align_refusal(SEARCH_FAILED)


def test_the_advice_that_cannot_work_is_gone():
    """The generic message's instruction, named: press it again and it will
    search only inside the corners you dragged. On a honeycomb that is a
    narrower search of something that will not be found at any width."""
    generic = M.scan_align_refusal(SEARCH_FAILED).body
    hexed = M.scan_align_refusal(SEARCH_FAILED, hexagonal=True).body
    assert "press Auto align again" in generic
    assert "press Auto align again" not in hexed
    assert "will not help" in hexed, \
        "the honeycomb wording must say that pressing again cannot help"
    assert "yourself" in hexed, \
        "…and must say what to do instead: place the corners by hand"


def test_the_headline_is_the_one_every_refusal_shares():
    """After a refusal the first thing the user needs to know is that they have
    lost nothing, and that promise is worded once for all six endings."""
    for hexagonal in (False, True):
        assert M.scan_align_refusal(SEARCH_FAILED, hexagonal=hexagonal).title == \
            M.scan_align_refusal("below-floor").title


def test_it_is_a_proposed_message_until_somebody_approves_it():
    """New user-facing text goes to §M-PROPOSED first (CLAUDE.md, Knut #130)."""
    assert "M-SCAN-ALIGN-NOT-FOUND-HEX" in M.PROPOSED
    assert not M.CATALOGUE["M-SCAN-ALIGN-NOT-FOUND-HEX"].approved


def test_the_message_says_nothing_about_a_reason_code():
    body = M.scan_align_refusal(SEARCH_FAILED, hexagonal=True).body
    for code in M.SCAN_ALIGN_REFUSALS:
        assert code not in body


def test_no_em_dash():
    m = M.CATALOGUE["M-SCAN-ALIGN-NOT-FOUND-HEX"]
    assert "—" not in m.body and "—" not in m.title


# ---------------------------------------------------------------------------
# …and every other ending is untouched, on both shapes
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("reason", sorted(M.SCAN_ALIGN_REFUSALS))
def test_every_other_ending_says_the_same_thing_on_both_shapes(reason):
    """THE CHANGE REACHES ONE ENDING AND NO OTHER. A honeycomb that is FOUND
    and then refused for a reason about colour or geometry gets exactly the
    words it got before, because the shape of a patch has nothing to do with
    those."""
    if reason == SEARCH_FAILED:
        return
    assert (M.scan_align_refusal(reason, hexagonal=True)
            is M.scan_align_refusal(reason))


@pytest.mark.parametrize("reason", sorted(M.SCAN_ALIGN_REFUSALS))
def test_a_rectangular_chart_is_byte_identical(reason):
    """The default is False, so a rectangle cannot reach the new wording at
    all. Structural rather than statistical."""
    assert (M.scan_align_refusal(reason)
            is M.scan_align_refusal(reason, hexagonal=False))


def test_the_ladder_s_own_set_of_endings_is_unchanged():
    """The honeycomb wording is a property of the CHART, not a new ending, so
    `scan_placement` and `scan_auto_align` are untouched and the map they are
    checked against still matches them exactly."""
    from workflow.scan_placement import ENDINGS
    assert set(M.SCAN_ALIGN_REFUSALS) == set(ENDINGS) - {"placed"}
    assert "M-SCAN-ALIGN-NOT-FOUND-HEX" not in {
        m.id for m in M.SCAN_ALIGN_REFUSALS.values()}


def test_the_mutation_lands():
    """Take the honeycomb branch out and the tests above must go red.

    A message picker that answered the same way with the flag on and off would
    pass every "is not None" check ever written about it.
    """
    generic = M.scan_align_refusal(SEARCH_FAILED)
    hexed = M.scan_align_refusal(SEARCH_FAILED, hexagonal=True)
    assert generic.id != hexed.id
    assert generic.body != hexed.body
    # …and the two really are different sentences, not the same one reflowed.
    assert "hexagonal" in hexed.body.lower() or "honeycomb" in hexed.body.lower()
    assert "hexagonal" not in generic.body.lower()
    assert "honeycomb" not in generic.body.lower()


# ---------------------------------------------------------------------------
# the window, not just the catalogue
# ---------------------------------------------------------------------------
def test_the_window_asks_the_chart_and_not_the_search():
    """`_auto_align_done` must pass the CHART's shape, because the ladder's
    ending cannot carry it: the same "not recognised" is returned for a
    honeycomb and for a photograph of a desk."""
    import inspect
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    src = inspect.getsource(ScannerProfileDialog._auto_align_done)
    assert "hexagonal=" in src
    assert "_chart_is_hexagonal" in src


def test_the_window_answers_false_when_there_is_no_chart():
    """A refusal can arrive before any chart is loaded, and a standard target
    has no ChromIQ sidecar at all. Both must get the ordinary wording rather
    than an exception inside a slot."""
    from ui.dialogs.scanin_dialog import ScannerProfileDialog

    class _Bare:
        _ti3 = None
    assert ScannerProfileDialog._chart_is_hexagonal(_Bare()) is False

    class _Broken:
        _ti3 = object()          # not a path: the readout must swallow it
    assert ScannerProfileDialog._chart_is_hexagonal(_Broken()) is False
