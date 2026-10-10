"""Beta 10: the red/yellow help says exactly what workflow/patch_flags.py does.

Found by the beta-9 reviewer:

* a re-read confirmation was "never forgotten". The limits never take it away,
  but a later LIVE re-read that is clean or a different colour does
  (``FlagJudge.judge``);
* the hover help's "learned" bullet left out the stand-out condition
  (``STANDOUT_MARGIN_DE``) that Preferences states. Every place now names it,
  against a confirmed patch of the range, in the same words.
"""
from __future__ import annotations

import inspect

from ui.dialogs import settings_dialog
from ui.tabs import tab_measure

LEARNED = ("off in the same way as a confirmed patch of the range, as much or "
           "more, without standing out from its strip much more than that "
           "patch did.")


def _flat(src: str) -> str:
    """The source's string literals, as the reader sees the text, one per
    line. Read with ``ast`` (beta 17): a regex over the quote marks lost its
    place at the first docstring with a quotation in it, and only matched the
    texts after it by the luck of how many quote marks came before."""
    import ast
    return "\n\n".join(n.value for n in ast.walk(ast.parse(src))
                       if isinstance(n, ast.Constant)
                       and isinstance(n.value, str))


def test_no_help_says_a_confirmation_is_never_forgotten():
    for mod in (settings_dialog, tab_measure):
        assert "never forgotten" not in inspect.getsource(mod), mod.__name__


def test_the_limits_help_says_what_ends_a_confirmation():
    limits = tab_measure._OVERLAY_TIP_LIMITS
    assert "kept when you change the limits" in limits
    assert ("It ends only when you read that patch once more and the new "
            "reading is not outlined or gives a different colour.") in limits
    # Preferences carries the same paragraph, word for word (one translation).
    assert limits in _flat(inspect.getsource(settings_dialog))


def test_the_learned_rule_is_the_same_in_the_hover_help_and_preferences():
    assert LEARNED in _flat(inspect.getsource(tab_measure))
    assert LEARNED in _flat(inspect.getsource(settings_dialog))


def test_the_rule_the_help_describes_is_the_one_the_code_runs():
    from workflow import patch_flags
    src = inspect.getsource(patch_flags.FlagJudge.judge)
    # A clean LIVE reading drops the confirmation; a repaint does not.
    assert "if live and self._refs.pop(loc, None) is not None:" in src
    # A different colour on a live re-read drops it too.
    assert "elif live and own is not None:" in src
    # _like answers through _match since the landing waiver (5982600086).
    like = inspect.getsource(patch_flags.FlagJudge._match)
    assert "standout > ref.standout + STANDOUT_MARGIN_DE" in like
