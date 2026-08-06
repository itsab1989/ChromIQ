"""Esc must raise the Confirm Abort window on BOTH readers.

Knut, #130: *"How can I reach the window during measurement session that have
an abort button?"* On the engine — the default reader — he could not. Esc goes
out as ``{"cmd":"quit"}``, the helper registers it as an abort, prints
``Abort ? - Are you sure ? [y/n]`` and emits an ``abort_confirm`` event. Neither
the event nor the prose was dispatched on the engine path, so nothing appeared
and the helper waited at its own prompt.

`docs/design/measurement_exit_strategy.md` Table 1 lists this window for the
engine, so the specification was right and the code was wrong. These tests hold
the two paths level, because one of them working is what hid this for two betas.
"""
import pytest

from core.argyll_runner import ArgyllRunner
from core.settings import AppSettings
from workflow.measure_manager import MeasureManager

#: exactly what the helper prints — chromiq_chartread.c:2945
PROSE = "Abort ? - Are you sure ? [y/n]:"
#: …and the event it emits on the line before it
EVENT = '{"event":"abort_confirm"}'


@pytest.fixture
def manager(qapp):
    return MeasureManager(ArgyllRunner(AppSettings()))


def _emitted(manager, *, engine: bool, line: str) -> bool:
    seen = []
    manager.abort_confirm.connect(lambda: seen.append(True))
    manager._engine_active = engine
    handler = manager._handle_engine_line if engine else manager._handle_line
    handler(line, lambda _l: None)
    return bool(seen)


def test_stock_chartread_raises_it_from_the_printed_prompt(manager):
    assert _emitted(manager, engine=False, line=PROSE)


def test_the_engine_raises_it_from_the_typed_event(manager):
    """The regression. Without the dispatch the helper waits and nothing shows."""
    assert _emitted(manager, engine=True, line=EVENT)


def test_the_helper_really_does_emit_that_event(manager):
    """Guard the contract at its source, not just our half of it.

    A test that only feeds itself the string it expects proves nothing about
    the helper. This reads the C the bundled binary is built from.
    """
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent
           / "native" / "chartread_helper" / "chromiq_chartread.c")
    if not src.is_file():                      # pragma: no cover
        pytest.skip("helper source not in this checkout")
    text = src.read_text(errors="replace")
    assert 'cq_emit_simple("abort_confirm")' in text, (
        "the helper no longer emits abort_confirm — the engine window is "
        "unreachable again")


def test_the_window_is_wired_to_the_signal():
    """`_on_abort_confirm` is useless if nothing connects to it."""
    import inspect

    import ui.tabs.tab_measure as tm
    src = inspect.getsource(tm.TabMeasure)
    assert "self._manager.abort_confirm.connect(self._on_abort_confirm)" in src


def test_the_window_says_what_actually_happens_next():
    """Knut accepted this wording (#130, 2026-08-06).

    The old title, "Stop measuring without saving?", was true on stock
    chartread and false on the engine, where Yes now opens "Keep what you have
    measured so far?" and offers to save. A user reading it carefully would
    think Yes discarded their work.
    """
    import inspect

    import ui.tabs.tab_measure as tm
    src = inspect.getsource(tm.TabMeasure._on_abort_confirm)
    # Comments are not what the user reads, and this one quotes the old title
    # on purpose to explain why it changed.
    code = "\n".join(l for l in src.splitlines()
                     if not l.lstrip().startswith("#"))
    assert "Stop measuring?" in code
    assert "without saving" not in code, (
        "the abort window still claims nothing is saved; on the ChromIQ reader "
        "Yes offers to keep the strips"
    )
    assert "whether to keep the strips you have" in code, (
        "the window no longer says what happens next"
    )
    assert 'tr("Yes — Stop")' in code and 'tr("No — Keep Measuring")' in code


def test_the_no_instrument_window_can_appear_more_than_once():
    """Knut, beta.157: it came "the first few times", then stopped.

    `_no_instrument_shown` guards against the window being raised twice within
    one session — by the timer and again at process exit. It was never cleared,
    so it silently became once per application run and every later session with
    no instrument showed nothing at all.
    """
    import inspect

    import ui.tabs.tab_measure as tm
    src = inspect.getsource(tm.TabMeasure)
    assert src.count("self._no_instrument_shown = False") >= 1, (
        "nothing clears the once-per-session guard, so the window is really "
        "once per application run"
    )
    # …and it is cleared where a session begins, next to the sibling flags.
    start = src[src.index("self._saw_instrument = False"):]
    assert "self._no_instrument_shown = False" in start[:1200], (
        "the guard is not cleared at the start of a session"
    )
