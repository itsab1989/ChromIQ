"""Guided refinement neither loops on a strip the chart does not have nor
yanks the reader away from a strip the person chose (jctay, forum post
149834, ChromIQ 4.3.11 on Windows, project CP1500-600p).

His log, 2026-10-24 22:12 to 22:13, a refinement list of eleven strips
(7, 12, 13, 20, 24, 27, 28, 32, 39, 41, 46) on a chart rebuilt with 43:

    goto 10   (his click)   -> "Strip 7 is done. Moving on to strip 12…"
    goto 10   (his click)   -> "Strip 12 is done. Moving on to strip 13…"
    goto 10   (his click)   -> "Strip 13 is done. Moving on to strip 20…"
    …
    goto 37   (his click)   -> "Strip 41 is done. Moving on to strip 46…"
    goto 46 -> strip_ready 37 -> goto 46 -> strip_ready 37 -> …  828 times

Nothing had been read in any of those "done" strips, and strip 46 does not
exist on a 43-strip chart: the engine stays where it is when asked for a
strip it does not have, and says nothing else.
"""
from __future__ import annotations

import inspect
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.measure_manager import MeasureManager        # noqa: E402


def _letters(n):
    """Strip names as Argyll letters them: A..Z, AA, AB, ..."""
    out = []
    for i in range(n):
        out.append(chr(65 + i) if i < 26 else "A" + chr(65 + i - 26))
    return out


#: His chart had 43 strips; the list asked for the 46th. Letter-named here
#: (the state machine reads names through the chart's labels, letters by
#: default): strip 37 is "AK", 41 "AO", 46 "AT".
CHART_43 = _letters(43)
S37, S41, S46, S7, S10 = "AK", "AO", "AT", "G", "J"


class _Sig:
    def __init__(self):
        self.count = 0

    def emit(self, *a):
        self.count += 1


class _Engine:
    """The guided state machine against a fake engine that, like the real
    one, stays on the current strip when asked for one it does not have."""
    _guided_step = MeasureManager._guided_step
    _advance_guided_strip = MeasureManager._advance_guided_strip
    _guided_strip_unreachable = MeasureManager._guided_strip_unreachable
    _skip_unreachable_guided_strip = MeasureManager._skip_unreachable_guided_strip
    user_goto_strip = MeasureManager.user_goto_strip

    def __init__(self, strips, chart, at):
        self._guided_strips = list(strips)
        self._guided_idx = 0
        self._guided_state = "idle"
        self._guided_by_patch = False
        self._guided_menu_pending = False
        self._guided_jumps_for = ("", 0)
        self._engine_active = True
        self._labels = None
        self.all_stripes_done = _Sig()
        self.chart = list(chart)
        self.at = at
        self.gotos: list = []
        self.lines: list = []
        self._guided_on_line = self.lines.append

    def goto_strip(self, target):
        self.gotos.append(target)
        if len(self.gotos) > 50:
            raise AssertionError("the guide keeps asking: an endless loop")
        if target in self.chart:
            self.at = target
        # the engine announces where it is, whether it moved or not
        self._guided_step(self.at, self.lines.append)

    def _navigate_toward(self, current, target):
        self.goto_strip(target)


def test_a_strip_the_chart_does_not_have_is_left_out_not_asked_for_for_ever():
    assert S46 not in CHART_43 and S41 in CHART_43
    e = _Engine([S41, S46], CHART_43, at=S37)
    e._guided_step(S37, e.lines.append)             # start: goes to 41
    assert e.at == S41
    e._advance_guided_strip(e.lines.append)         # 41 read, on to 46
    e._guided_step(S41, e.lines.append)             # the menu re-announced
    assert e.gotos.count(S46) <= 3, e.gotos
    assert e._guided_state == "idle_done"
    assert S46 not in e._guided_strips
    assert any("no strip of that name" in l for l in e.lines), e.lines


def test_the_next_strip_on_the_list_is_still_visited_after_one_is_left_out():
    chart = list("ABCDEF")
    e = _Engine(["B", "Z", "D"], chart, at="A")
    e._guided_step("A", e.lines.append)             # to B
    e._advance_guided_strip(e.lines.append)
    e._guided_step("B", e.lines.append)             # Z missing -> on to D
    assert e.at == "D"
    assert e._guided_state == "waiting"
    assert e._guided_strips == ["B", "D"]


def test_an_ordinary_jump_is_never_mistaken_for_an_unreachable_strip():
    chart = list("ABCDEF")
    e = _Engine(["B", "D", "F"], chart, at="A")
    e._guided_step("A", e.lines.append)
    for _ in range(3):
        e._advance_guided_strip(e.lines.append)
        e._guided_step(e.at, e.lines.append)
    assert e._guided_strips == ["B", "D", "F"]
    assert e.gotos == ["B", "D", "F"]
    assert not any("no strip of that name" in l for l in e.lines)


def test_a_click_on_another_strip_hands_the_reader_over():
    e = _Engine([S7, "L", "M"], CHART_43, at=S10)
    e._guided_step(S10, e.lines.append)             # guide takes him to 7
    assert e.at == S7 and e._guided_state == "waiting"
    e.user_goto_strip(S10)                          # he clicks strip 10
    assert e.at == S10, "the reader did not go where he clicked"
    assert e._guided_state == "idle_done"
    assert e.gotos == [S7, S10], (
        "the guide jumped away from the strip he chose: " + repr(e.gotos))
    assert any("You chose strip J yourself" in l for l in e.lines), e.lines


def test_a_click_on_the_strip_the_guide_is_waiting_on_changes_nothing():
    chart = list("ABCDEF")
    e = _Engine(["C", "E"], chart, at="A")
    e._guided_step("A", e.lines.append)
    e.user_goto_strip("C")
    assert e._guided_state == "waiting"
    assert e._guided_strips[e._guided_idx] == "C"


def test_the_preview_click_is_the_persons_choice_and_the_list_is_filtered():
    from ui.tabs import tab_measure
    src = inspect.getsource(tab_measure.TabMeasure._on_preview_strip_clicked)
    assert "user_goto_strip(" in src
    src = inspect.getsource(tab_measure)
    assert "set_guided_strips(\n                self._guided_strips_on_chart()" in src


def test_a_new_list_starts_with_no_jumps_counted():
    """Review of 4.3.14: the jump count is per guided session. A count left
    from a guide the person stopped mid-way must not make the next session
    skip a strip the chart has at its first stray announcement."""
    import types
    m = types.SimpleNamespace(_guided_jumps_for=("C", 2))
    MeasureManager.set_guided_strips(m, ["C", "E"])
    assert m._guided_jumps_for == ("", 0)
    m._guided_jumps_for = ("C", 2)
    MeasureManager.set_guided_patches(m, ["C3"])
    assert m._guided_jumps_for == ("", 0)
    e = _Engine(["C", "E"], list("ABCDEF"), at="A")
    e._guided_jumps_for = ("C", 1)
    e._guided_state = "navigating"
    e.user_goto_strip("B")
    assert e._guided_jumps_for == ("", 0)
