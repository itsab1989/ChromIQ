"""Beta 2 · a chart naming no instrument was described by Argyll as an i1 Pro.

Driven on screen 2026-08-30 while proving that ChromIQ's instrument choice
follows the chart. With a chart carrying no `TARGET_INSTRUMENT`:

* ArgyllCMS's own log line claims **"chart is for GretagMacbeth i1 Pro"** — its
  internal default when a chart is silent, not anything in the file. The file
  was checked and names nothing.
* ChromIQ passed that line straight through, and its own announcement branch was
  `if instr:` — silent for exactly this case. So nothing corrected it.

The harm is small but real and of a kind this project cares about: the user is
told something about their own chart that is not true, and could choose hardware
to match it. Charts that DO name an instrument have always announced it.
"""
from __future__ import annotations

import inspect
import re

from ui.tabs.tab_measure import TabMeasure


def _announcement_source() -> str:
    """The block that logs the "Chart instrument:" line.

    Bounded by the NEXT `def` rather than a character count — a fixed window
    broke twice this week the moment a comment above it grew, which measures
    the source's shape instead of the code's behaviour.
    """
    whole = inspect.getsource(TabMeasure)
    i = whole.index('"Chart instrument: {label}."')
    end = whole.index("\n    def ", i)
    block = whole[i:end]
    # Join adjacent string literals, so a sentence the source wraps across two
    # lines is still one sentence here. Without this the test matches the line
    # breaks rather than the words, and fails on reflowing alone.
    return re.sub(r'"\s*\n\s*"', "", block)


def test_the_silent_case_is_no_longer_silent():
    src = _announcement_source()
    i = src.index("else:")
    assert "does not name one" in src[i:], (
        "a chart that names no instrument still says nothing, so Argyll's "
        "default speaks for it")


def test_it_names_the_wrong_claim_the_user_will_see():
    """Pre-empting Argyll's line is the whole point: we cannot stop it being
    printed, so the honest move is to say first what it means."""
    src = _announcement_source()
    assert "GretagMacbeth i1 Pro" in src, (
        "the note does not mention the claim it exists to correct, so a user "
        "reading Argyll's line has nothing to connect it to")
    assert "its own assumption" in src or "not something written" in src, (
        "it does not say the claim is Argyll's assumption rather than a fact "
        "about the chart")


def test_it_says_what_chromiq_will_actually_do():
    """A correction that leaves the user wondering what happens next is half a
    message."""
    src = _announcement_source()
    assert "whichever instrument you have connected" in src


def test_a_named_instrument_still_announces_itself():
    """The fix must not swallow the case that already worked."""
    src = _announcement_source()
    assert '"Chart instrument: {label}."' in src
    assert '"Chart instrument: {label} → {detail}."' in src
