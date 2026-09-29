"""A pre-flight asked for while one is open is asked again (beta 37, round B).

Round B's behaviour note (b): the English drive got no pre-flight on run2 of
the evenness demo while the German one did. The English log shows run3's
window on screen when the driver switched to run2: the switch asked for run2's
pre-flight, met the "never two at once" guard, and was dropped for good.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_the_verification_preflight_fires_for_its_preconditions import (  # noqa: E402,E501
    _ready_tab)


def test_a_request_met_by_an_open_window_is_made_again_when_it_closes(
        qapp, tmp_path, monkeypatch):
    """MUTATION (proved red 2026-09-23): drop `self._preflight_missed = True`
    from the open-window guard in `_show_verification_preflight_now`; the
    request made while the window was open is never made again."""
    tab, ctl, chart = _ready_tab(tmp_path, qapp)
    qapp.processEvents()          # the triggers _ready_tab queued, unseen
    monkeypatch.setattr(type(tab), "isVisible", lambda self: True)
    shown = tab._preflight_key()
    tab._preflight_open = True
    tab._show_verification_preflight_now()        # run3's window is open
    # the reader is now looking at another run's chart
    monkeypatch.setattr(type(tab), "_preflight_key",
                        lambda self: (("P", "run2"), "other.ti2"))
    asked: list = []
    monkeypatch.setattr(type(tab), "_queue_verification_preflight",
                        lambda self: asked.append(True))
    tab._preflight_open = False
    tab._after_preflight_closed(shown)
    assert asked, "the pre-flight asked for while one was open was lost"


def test_but_the_window_just_answered_is_not_shown_twice(
        qapp, tmp_path, monkeypatch):
    """The other half: the English log showed run3's window twice. A request
    for the same run and chart as the one just closed is not made again."""
    tab, ctl, chart = _ready_tab(tmp_path, qapp)
    qapp.processEvents()          # the triggers _ready_tab queued, unseen
    monkeypatch.setattr(type(tab), "isVisible", lambda self: True)
    shown = tab._preflight_key()
    tab._preflight_open = True
    tab._show_verification_preflight_now()
    asked: list = []
    monkeypatch.setattr(type(tab), "_queue_verification_preflight",
                        lambda self: asked.append(True))
    tab._preflight_open = False
    tab._after_preflight_closed(shown)
    assert not asked
