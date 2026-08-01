"""#130 (Knut, 2026-08-01): "Save Partial & Quit" saved nothing on stock
ArgyllCMS chartread.

He read a whole strip, provoked a misread, chose Save Partial & Quit, and got::

    [INFO] Measurement stopped — no measurement (.ti3) file was created.

    "No ti3 file was saved, even though I had read one strip, thus the Save
     Partial and Quit did not work as expected. … Did the save button use the q
     command to quit without saving? or d, which would quite and save?"

His question is the answer. The two-'q' protocol is **the ChromIQ engine's**: its
helper calls ``cq_write_ti3_atomic()`` before giving up — *"never lose
readings"*, a ChromIQ extension. Stock chartread has no such call.
``spectro/chartread.c:1654`` treats ``q`` at a misread prompt as give-up and
``return -1``, so the file is never written; the readings die with the process.

On stock chartread the path that DOES write is the strip menu's "done" question:
retry back to the menu, ``d``, then ``y`` to "Are you sure [y/n]". Save Partial
now sends that chain there, one prompt at a time, and keeps the two-'q' protocol
for the engine.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.measure_manager import MeasureManager          # noqa: E402


class _Runner:
    def __init__(self):
        self.out: list[str] = []

    def write_stdin(self, data):
        self.out.append(data)

    def __getattr__(self, _n):
        return lambda *a, **k: None


def _mgr(engine: bool, at_prompt: bool = False):
    m = MeasureManager(_Runner())
    m._engine_active = engine
    m._at_retry_prompt = at_prompt
    return m


# ---- the engine keeps its protocol --------------------------------------
def test_the_engine_still_sends_two_q():
    """Its helper writes the file atomically before giving up, so this works —
    and it is the sequence Knut established by hand."""
    m = _mgr(engine=True, at_prompt=True)
    m.send_save_partial_and_quit()
    # The engine speaks JSON commands rather than raw keys.
    assert m._runner.out == ['{"cmd": "quit"}\n']
    m._handle_line("Strip read stopped at user request!", lambda _l: None)
    assert m._runner.out == ['{"cmd": "quit"}\n', '{"cmd": "quit"}\n']


# ---- stock chartread gets the chain that actually saves ------------------
def test_stock_chartread_never_sends_q():
    """'q' there exits without writing — the exact fault he reported."""
    m = _mgr(engine=False, at_prompt=True)
    m.send_save_partial_and_quit()
    assert "q" not in m._runner.out, \
        "'q' on stock chartread quits WITHOUT saving (chartread.c:1654)"
    assert '{"cmd": "quit"}\n' not in m._runner.out


def test_stock_from_a_failure_prompt_retries_then_saves():
    m = _mgr(engine=False, at_prompt=True)
    m.send_save_partial_and_quit()
    assert m._runner.out == ["r"], "first leave the retry prompt"

    # chartread returns to the strip menu…
    m._handle_line("Ready to read strip pass A", lambda _l: None)
    assert m._runner.out[-1] == "d", "'d' at the menu raises the saving question"

    # …and the question is answered for him — he already chose Save Partial.
    m._handle_line("Done ? - At least one unread patch (49, A4), "
                   "Are you sure [y/n]: ", lambda _l: None)
    assert m._runner.out[-1] == "y"
    assert m.save_partial_in_progress is False


def test_stock_at_the_menu_goes_straight_to_done():
    """No failure prompt to leave, so no retry key is spent."""
    m = _mgr(engine=False, at_prompt=False)
    m.send_save_partial_and_quit()
    assert m._runner.out == ["d"]
    m._handle_line("Done ? - Are you sure [y/n]: ", lambda _l: None)
    assert m._runner.out == ["d", "y"]


def test_the_unread_question_is_still_the_users_when_not_saving():
    """Outside a Save-Partial the same prompt must reach the user's dialog —
    answering it silently would decide for them."""
    m = _mgr(engine=False)
    seen = []
    m.unread_confirm.connect(seen.append)
    m._handle_line("Done ? - At least one unread patch (12, B3), "
                   "Are you sure [y/n]: ", lambda _l: None)
    assert seen and "12" in seen[0]
    assert m._runner.out == [], "nothing may be sent on the user's behalf here"


def test_the_menu_line_is_told_from_ordinary_strip_chatter():
    """_STRIP_MENU_RE must mean "sitting at the menu", not any line that
    mentions a strip — otherwise 'd' goes out mid-scan."""
    from workflow.measure_manager import _STRIP_MENU_RE
    assert _STRIP_MENU_RE.search("Ready to read strip pass A")
    assert not _STRIP_MENU_RE.search("Scanning strip 'A01'")
    assert not _STRIP_MENU_RE.search(" Strip read OK")


def test_a_stock_save_does_not_answer_the_menu_twice():
    """The state clears on the first menu line; a second must not send 'd'
    again, which would raise the question after the file was already written."""
    m = _mgr(engine=False, at_prompt=True)
    m.send_save_partial_and_quit()
    m._handle_line("Ready to read strip pass A", lambda _l: None)
    m._handle_line("Ready to read strip pass B", lambda _l: None)
    assert m._runner.out.count("d") == 1
