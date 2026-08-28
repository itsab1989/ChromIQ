"""#130 beta.140 — one window per failure, and never two at once.

Knut, beta.140, patch-by-patch on the ChromIQ engine with the dial in the wrong
position:

    *"Pressing Retry … Instead of allowing me to continue reading, the window
    'Patch Read Failed' comes … If I now try Retry, the window 'Instrument
    Error' comes again. An infinite loop. This was introduced in last betas."*

and in strip mode:

    *"I can also click the instrument button more times, and this window comes
    on top of previous windows, all at the same time. This should not be
    allowed."*

Both are the same root: nothing said "you have already told them about this".
"""
from __future__ import annotations

import pytest

from workflow.measure_manager import MeasureManager


def _feed(manager, line: str) -> None:
    """One line into the engine handler, the way ArgyllRunner delivers it.

    ``_handle_engine_line(line, on_line)`` — the second argument is the sink
    for prose the helper prints alongside its events, which the log pane owns.
    """
    manager._handle_engine_line(line, lambda _text: None)


class _Runner:
    def __init__(self):
        self.sent = []

    def write_stdin(self, text):
        self.sent.append(text)


@pytest.fixture
def manager(qapp):
    m = MeasureManager.__new__(MeasureManager)
    MeasureManager.__init__(m, _Runner())
    m._engine_active = True
    # The run supplies its own values (chartread -x); see save_partial_and_quit().
    m._external_values = False
    return m


def _errors(manager):
    """(strip_error payloads, generic_instrument_error payloads)."""
    strip, generic = [], []
    manager.strip_error.connect(strip.append)
    manager.generic_instrument_error.connect(lambda a, b: generic.append(a))
    return strip, generic


# ---- the loop ------------------------------------------------------------
def test_the_printed_line_and_its_event_raise_one_window(manager):
    """Knut's exact sequence, from his log: the helper prints the failure, the
    user answers, and then the SAME failure arrives as an event."""
    strip, generic = _errors(manager)

    _feed(manager,
        "Patch read failed due unexpected error :'Wrong Sensor Position' "
        "(Sensor should be in surface position)")
    assert len(generic) == 1, "the printed line did not raise the window"
    assert len(strip) == 0

    _feed(manager,
        '{"event":"error","kind":"misread",'
        '"detail":"Sensor should be in surface position"}')
    assert len(strip) == 0, (
        "the same failure raised a second window — that is the loop")
    assert len(generic) == 1


def test_the_reader_is_still_known_to_be_at_a_retry_prompt(manager):
    """Suppressing the window must not lose the fact that the helper is
    blocked — Skip Patch needs it to send its acknowledgement first."""
    _errors(manager)
    _feed(manager,
        "Patch read failed due unexpected error :'Wrong Sensor Position' "
        "(Sensor should be in surface position)")
    manager._at_retry_prompt = False          # prove the event sets it again
    _feed(manager,
        '{"event":"error","kind":"misread",'
        '"detail":"Sensor should be in surface position"}')
    assert manager._at_retry_prompt is True


def test_a_genuinely_different_misread_still_reaches_the_user(manager):
    """The suppression is for the sensor-position failure already reported —
    a real misread must still open its window."""
    strip, generic = _errors(manager)
    _feed(manager,
        "Patch read failed due unexpected error :'Wrong Sensor Position' "
        "(Sensor should be in surface position)")
    _feed(manager,
        '{"event":"error","kind":"misread","detail":"Not enough patches"}')
    assert strip == ["Not enough patches"]


def test_the_next_failure_after_the_prompt_closes_is_reported(manager):
    """Once the reader is back at a patch, the dial being wrong again is news
    again — silencing it for the rest of the session was beta.136's bug."""
    strip, generic = _errors(manager)
    _feed(manager,
        "Patch read failed due unexpected error :'Wrong Sensor Position' "
        "(Sensor should be in surface position)")
    _feed(manager,
        '{"event":"spot_ready","id":"63","loc":"F2","read":false,'
        '"all_done":false}')
    _feed(manager,
        "Patch read failed due unexpected error :'Wrong Sensor Position' "
        "(Sensor should be in surface position)")
    assert len(generic) == 2


# ---- the stacking --------------------------------------------------------
def test_a_second_window_is_refused_while_one_is_open(qapp):
    """Pressing the instrument button again while the window is up must not
    put another on top of it."""
    import inspect
    from ui.tabs.tab_measure import TabMeasure

    src = inspect.getsource(TabMeasure._on_generic_instrument_error)
    assert "_live_measure_windows" in src, (
        "nothing stops a second Instrument Error window opening on top")
    # …and it must bail out BEFORE building the dialog.
    assert src.index("_live_measure_windows") < src.index("QDialog(")
