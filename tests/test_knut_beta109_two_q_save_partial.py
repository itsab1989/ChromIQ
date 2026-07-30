"""#130 (Knut, 2026-07-30): "Save Partial & Quit" sends TWO 'q' commands.

He established the protocol by hand after three wrong theories from me, and asked
the fair question: *"Why is this so difficult? Just analyse how other buttons on
windows during measurement handles the commands on events."* His log settles it:

    Trigger instrument switch or any other key to start:
    q →  Strip read stopped at user request!
         Hit Esc or 'q' to give up, any other key to retry:
    q →  [INFO] Measurement was interrupted — partial readings saved.

The first 'q' stops the armed strip; the second answers the give-up prompt, and
that is what makes chartread write the .ti3 and exit.

The old chain (Return → strip menu → 'd' → "are you sure" → 'y') only worked when
the reader happened to be at the strip menu. From the misread prompt — the case
this button exists for — the Return was spent as "retry" and the session hung.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.measure_manager import MeasureManager      # noqa: E402


class _Runner:
    def __init__(self):
        self.stdin: list[str] = []
        self.is_running = True

    def write_stdin(self, text: str) -> None:
        self.stdin.append(text)


def _manager(*, engine: bool = False):
    m = MeasureManager.__new__(MeasureManager)
    m._runner = _Runner()
    m._engine_active = engine
    m._user_quit = False
    m._save_partial_state = None
    m._pending_post_retry_key = None
    m._guided_state = "disabled"
    m._at_retry_prompt = False
    m.sent_commands = []
    m.send_command = lambda cmd: m.sent_commands.append(cmd)     # type: ignore
    m.interrupted = []
    m.strip_interrupted = type("S", (), {
        "emit": staticmethod(lambda: m.interrupted.append(1))})()
    m.stripe_changed = type("S", (), {"emit": staticmethod(lambda *_a: None)})()
    return m


_GIVE_UP = "Strip read stopped at user request!"


def test_the_first_q_goes_out_when_the_button_is_pressed():
    m = _manager()
    m.send_save_partial_and_quit()
    assert m._runner.stdin == ["q"]
    assert m._save_partial_state == "wait_give_up_prompt"


def test_the_second_q_answers_the_give_up_prompt():
    """This is the one that writes the .ti3 — the step that never happened."""
    m = _manager()
    m.send_save_partial_and_quit()
    m._handle_line(_GIVE_UP, lambda _l: None)

    assert m._runner.stdin == ["q", "q"]
    assert m._save_partial_state is None
    assert m.interrupted == [], \
        "the recovery dialog must not also fire while we are saving"


def test_the_same_prompt_still_raises_the_dialog_when_not_saving():
    """A user-driven interruption is unchanged: the window still appears."""
    m = _manager()
    m._handle_line(_GIVE_UP, lambda _l: None)
    assert m.interrupted == [1]
    assert m._runner.stdin == []


def test_it_works_on_an_engine_session_too():
    """Both keystrokes go out as commands there — the channel fault from
    beta.107 must not come back through this new path."""
    m = _manager(engine=True)
    m.send_save_partial_and_quit()
    m._handle_line(_GIVE_UP, lambda _l: None)

    assert m._runner.stdin == [], "a raw keystroke went to the engine"
    assert m.sent_commands == [{"cmd": "quit"}, {"cmd": "quit"}]


def test_the_old_strip_menu_chain_is_gone():
    """It is what made the button hang from a misread, so it must not linger."""
    src = inspect.getsource(MeasureManager.send_save_partial_and_quit)
    assert "wait_strip_menu" not in src
    assert 'send_key("q")' in src


def test_the_protocol_is_recorded_where_the_code_is():
    """Three wrong theories preceded this; the log lines that settle it belong
    beside the implementation, not only in a commit message."""
    src = inspect.getsource(MeasureManager.send_save_partial_and_quit)
    assert "Strip read stopped at user request" in src
    assert "give-up" in src
