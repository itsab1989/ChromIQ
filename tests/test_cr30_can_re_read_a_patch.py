"""#159 (report 14, H7): a patch already measured could never be measured again.

The owner's session of 2026-08-29: readings landed on the wrong patches, and
"after the readings were attached to the wrong patch i clicked the correct one
manually a few times to try to make a reading for them again but this did not
work".

`on_patch_ready` returned on `read: true` whatever the reason, under a comment
saying "re-reading it would need the user to ask" — and clicking the patch IS
the user asking; that is what click-to-jump is for. So the preview highlighted
the patch, the helper waited on it, the screen said read this patch, and no
reader was ever started. He pressed the instrument's button at nothing.

Worse in combination: the wrong-patch fault PUTS a bad colour on a patch and
this made it impossible to correct, so a measurement could be silently corrupted
and then not repaired from inside the app.

Safe to re-arm: the helper accepts a value for whatever patch it is sitting on,
overwrites that row in place and re-saves — nothing appended, nothing
duplicated (chromiq_chartread.c, the xtern spot loop).
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                    # noqa: E402

from tests.test_cr30_measure_bridge import Harness                # noqa: E402


def _ready(h, loc, **kw):
    h.bridge.on_patch_ready({"loc": loc, "read": False,
                             "all_done": False, **kw})
    h.settle()


def test_clicking_an_already_read_patch_arms_it():
    h = Harness()
    rearmed: list = []
    h.bridge.patch_rearmed.connect(rearmed.append)

    # The user clicks A17 in the preview: the tab sends a goto and tells the
    # bridge BEFORE the command goes out.
    h.bridge.note_goto("A17")
    before = len(h.read_calls)
    _ready(h, "A17", read=True)          # the helper: "A17 (Already read)"

    assert len(h.read_calls) > before, (
        "clicking a measured patch started no reader — the button the user is "
        "told to press is connected to nothing")
    assert rearmed == ["A17"], (
        "the re-arm was silent, which looks exactly like the dead session it "
        "replaces")
    assert len(h.sent) == 1, "the new reading was not sent to the helper"


def test_merely_passing_over_a_read_patch_still_skips_it():
    """The other half, and it must not change: traversing a chart must not
    re-measure everything already done."""
    h = Harness()
    rearmed: list = []
    h.bridge.patch_rearmed.connect(rearmed.append)

    _ready(h, "A17", read=True)          # arrived at, not asked for

    assert h.read_calls == [], "traversal re-measured a patch nobody asked for"
    assert rearmed == []
    assert h.sent == []


def test_a_jump_to_an_unread_patch_is_unaffected():
    h = Harness()
    h.bridge.note_goto("B3")
    _ready(h, "B3", read=False)
    assert len(h.read_calls) == 1
    assert len(h.sent) == 1


def test_a_finished_chart_can_still_have_a_patch_corrected():
    """report 15, finding 2: once nothing is unread the helper sets `all_done`
    on EVERY prompt, and returning on that made the re-read unreachable for
    exactly the person who needs it — a completed chart with one patch that
    took the wrong colour, and no way left to fix it."""
    h = Harness()
    rearmed: list = []
    h.bridge.patch_rearmed.connect(rearmed.append)

    h.bridge.note_goto("A17")
    h.bridge.on_patch_ready({"loc": "A17", "read": True, "all_done": True})
    h.settle()

    assert rearmed == ["A17"], (
        "a completed chart cannot have a wrong patch corrected")
    assert len(h.read_calls) == 1
