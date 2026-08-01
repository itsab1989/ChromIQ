"""#130 A2 (Knut, 2026-07-30, still open on 2026-08-01): Skip Patch does
nothing after a failed read — *"both when the sensor is in the wrong position
and when the reading is inconsistent."*

The two-step protocol for skipping past a failure already existed (#131): at a
retry prompt the acknowledgement has to be spent first, because the helper's
prompt treats **any key that is not Esc/q as "retry"** — so a navigation key
sent there is consumed as a retry and the reader stays where it is.

What was missing is which events mean "a retry prompt is open". Only ``misread``
and ``coms`` set it, and neither of Knut's two cases is either of those:

``read_error``
    The helper's generic ``ierror()`` path, which is where **Wrong Sensor
    Position** lands. It prints the same "any other key to retry" prompt and
    waits on it. Stock chartread reaches the same place through its printed
    text, which did not set the flag either.

``strip_warning``
    The **inconsistent reading**: "Hit Return to use it anyway, any other key to
    retry, Esc or 'q' to give up". Also a retry prompt, also not flagged.

In both, Skip sent a bare navigation command, the prompt ate it as "retry", and
the reader re-armed the same unit — exactly what he saw.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.measure_manager import MeasureManager             # noqa: E402


class _Runner:
    def __init__(self):
        self.out: list[str] = []

    def write_stdin(self, data):
        self.out.append(data)

    def __getattr__(self, _n):
        return lambda *a, **k: None


def _engine_manager(spot=True):
    m = MeasureManager(_Runner())
    m._engine_active = True
    m._spot_mode = spot
    return m


# ---- the two events that were not recognised -----------------------------
@pytest.mark.parametrize("line,case", [
    ('{"event":"error","kind":"read_error","detail":"Wrong Sensor Position"}',
     "the sensor is in the wrong position"),
    ('{"event":"strip_warning","kind":"unexpected","worst_de":42.0}',
     "the reading is inconsistent"),
])
def test_the_prompt_is_recognised_as_open(line, case):
    m = _engine_manager()
    assert m._at_retry_prompt is False
    m._handle_engine_line(line, lambda _l: None)
    assert m._at_retry_prompt is True, \
        f"Skip cannot work when {case} unless the prompt is known to be open"


@pytest.mark.parametrize("line", [
    '{"event":"error","kind":"read_error","detail":"Wrong Sensor Position"}',
    '{"event":"strip_warning","kind":"unexpected","worst_de":42.0}',
])
def test_skip_acknowledges_the_prompt_before_it_navigates(line):
    """The whole bug in one assertion: a bare `forward` here is spent as the
    prompt's "any other key" and the reader never moves."""
    m = _engine_manager()
    m._handle_engine_line(line, lambda _l: None)
    m._runner.out.clear()

    m.skip_current_strip()
    assert m._runner.out == ['{"cmd": "retry"}\n'], m._runner.out
    assert m._pending_post_retry_key == "f"

    # …and the navigation goes out once the menu is listening again.
    m._handle_engine_line(
        '{"event":"spot_ready","id":"1","loc":"A1","read":false,'
        '"all_done":false}', lambda _l: None)
    assert m._runner.out[-1] == '{"cmd": "forward"}\n', m._runner.out
    assert m._pending_post_retry_key is None
    assert m._at_retry_prompt is False


def test_the_acknowledgement_is_r_and_never_return():
    """Return is the spot-mode read trigger. If the acknowledgement ever
    reached the patch menu instead of the prompt, Return would *take a reading*
    on a patch the user asked to skip; 'r' is inert at the menu."""
    from workflow.chartread_engine import KEY_TO_COMMAND
    assert KEY_TO_COMMAND["\r"] == {"cmd": "ok"}
    m = _engine_manager()
    m._handle_engine_line(
        '{"event":"error","kind":"read_error","detail":"x"}', lambda _l: None)
    m._runner.out.clear()
    m.skip_current_strip()
    assert '"cmd": "retry"' in m._runner.out[0]
    assert "ok" not in m._runner.out[0]


# ---- no prompt open: the one-step case must not regress ------------------
def test_skip_at_the_plain_menu_still_sends_one_command():
    """Knut confirmed this case works; the fix must not turn it into two keys,
    which would cost a patch."""
    m = _engine_manager()
    assert m._at_retry_prompt is False
    m.skip_current_strip()
    assert m._runner.out == ['{"cmd": "forward"}\n'], m._runner.out
    assert m._pending_post_retry_key is None


# ---- the user is told what happened --------------------------------------
def test_a_read_error_reaches_the_user():
    """It used to set no flag and raise no signal on the engine path, so a
    wrong sensor position was a silent stall."""
    m = _engine_manager()
    seen = []
    m.generic_instrument_error.connect(lambda msg, detail: seen.append((msg, detail)))
    m._handle_engine_line(
        '{"event":"error","kind":"read_error","detail":"Wrong Sensor Position"}',
        lambda _l: None)
    assert seen and "Wrong Sensor Position" in seen[0][0]


def test_a_read_error_with_no_detail_still_says_something():
    m = _engine_manager()
    seen = []
    m.generic_instrument_error.connect(lambda msg, detail: seen.append(msg))
    m._handle_engine_line('{"event":"error","kind":"read_error"}', lambda _l: None)
    assert seen and seen[0].strip()


# ---- stock chartread reaches the same prompt through printed text --------
def test_stock_chartread_ierror_also_marks_the_prompt_open():
    """The same failure on the non-engine reader arrives as a printed line.
    Both readers must agree, or Skip works on one and not the other."""
    m = MeasureManager(_Runner())
    assert m._at_retry_prompt is False
    m._handle_line("Got 'Wrong Sensor Position' (Sensor is in the wrong "
                   "position) error.", lambda _l: None)
    assert m._at_retry_prompt is True


def test_the_strip_warning_still_reports_its_delta_e():
    """Flagging the prompt must not swallow the number the window shows."""
    m = _engine_manager(spot=False)
    seen = []
    m.unexpected_response.connect(seen.append)
    m._handle_engine_line(
        '{"event":"strip_warning","kind":"unexpected","worst_de":42.0}',
        lambda _l: None)
    assert seen == ["42.00"]


def test_a_wrong_strip_warning_still_names_both_strips():
    m = _engine_manager(spot=False)
    seen = []
    m.wrong_strip.connect(lambda r, e: seen.append((r, e)))
    m._handle_engine_line(
        '{"event":"strip_warning","kind":"wrong_strip","read":"c","expected":"b"}',
        lambda _l: None)
    assert seen == [("C", "B")]
    assert m._at_retry_prompt is True
