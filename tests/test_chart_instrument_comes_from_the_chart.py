"""The instrument-mismatch warning must describe the CHART, not a preference.

Found on 2026-08-08 during the first real measurement this project has ever
driven — a real ColorMunki, a real printed chart. Basti loaded a chart he had
made for that ColorMunki and was told:

    This chart was made for a different instrument
    The chart you are about to measure was laid out for:
        i1Pro / i1Pro 2 / i1Pro 3
    but the instrument connected is:
        ColorMunki / i1Studio / ColorChecker Studio

He was right and the app was wrong. `tab_measure` asked
``settings.get("chart_instrument")`` — an application-wide preference that
defaults to ``"i1"`` (`core/settings.py`) — so for anyone who had never set it,
every chart claimed to be an i1Pro chart. The sheet's own ``.ti2`` said
``TARGET_INSTRUMENT "X-Rite ColorMunki"`` the whole time.

It is not a cosmetic fault. The window says reading the chart "will usually
misread, skip strips, or fail to find the patches at all" and defaults to
Cancel, so it talks a user out of a measurement that would have worked, and
into reprinting a chart that was already correct.

**Why no test caught it:** the demo package measures with Argyll's ``fakeread``,
which never contradicts the chart it was handed. Reproducing this needs a chart
and a connected device that genuinely disagree — so these tests build that
disagreement out of the two pure functions the decision rests on, and assert on
the reading logic rather than on the dialog.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from data.patch_db import instrument_family_of, instrument_mismatch  # noqa: E402
from ui.ti2_loader import read_target_instrument                      # noqa: E402

_CM = 'TARGET_INSTRUMENT "X-Rite ColorMunki"\n'
_I1 = 'TARGET_INSTRUMENT "GretagMacbeth i1 Pro"\n'


def _chart(tmp_path, stem="chart", ti2_body=_CM, ti1_body=""):
    """A .ti1 the tab would load, with its .ti2 sibling beside it."""
    ti1 = tmp_path / f"{stem}.ti1"
    ti1.write_text("CTI1\n" + ti1_body)
    if ti2_body is not None:
        (tmp_path / f"{stem}.ti2").write_text("CTI2\n" + ti2_body)
    return ti1


def test_a_ti1_does_not_carry_the_instrument(tmp_path):
    """The premise: printtarg writes TARGET_INSTRUMENT into the .ti2, not the .ti1.

    This is why reading the file the tab loaded is not sufficient on its own,
    and why the fix has to look at the sibling.
    """
    ti1 = _chart(tmp_path)
    assert read_target_instrument(ti1) is None
    assert read_target_instrument(tmp_path / "chart.ti2") == "X-Rite ColorMunki"


def test_the_chart_decides_not_the_preference(tmp_path):
    """A ColorMunki chart read with a ColorMunki must not warn.

    The exact case that misfired: with the preference at its "i1" default the
    comparison produced a warning naming an instrument the chart has nothing to
    do with.
    """
    _chart(tmp_path)
    from_chart = instrument_family_of(read_target_instrument(tmp_path / "chart.ti2"))
    assert from_chart == "CM"
    assert instrument_mismatch(from_chart, "X-Rite ColorMunki") is None

    # what the old code did, kept as the contrast that makes the point
    assert instrument_mismatch("i1", "X-Rite ColorMunki") is not None


def test_a_real_mismatch_still_warns(tmp_path):
    """Reading the chart must not silence the warning that matters."""
    _chart(tmp_path, ti2_body=_CM)
    from_chart = instrument_family_of(read_target_instrument(tmp_path / "chart.ti2"))
    pair = instrument_mismatch(from_chart, "GretagMacbeth i1 Pro")
    assert pair is not None
    chart_label, found_label = pair
    assert "ColorMunki" in chart_label
    assert "i1Pro" in found_label


def test_the_helper_prefers_the_ti2_and_falls_back(tmp_path):
    """_chart_instrument_code reads the sibling, and answers None when nothing does."""
    from ui.tabs.tab_measure import TabMeasure

    class _Stub:
        """Only what the helper touches — building a real tab is not the point."""
        _ti1_path = None
        _chart_instrument_code = TabMeasure._chart_instrument_code

    stub = _Stub()
    stub._ti1_path = _chart(tmp_path, stem="withti2")
    assert stub._chart_instrument_code() == "CM"

    # a chart whose .ti2 records nothing: the helper must not invent an answer,
    # so the caller can fall back to the preference
    stub._ti1_path = _chart(tmp_path, stem="bare", ti2_body="")
    assert stub._chart_instrument_code() is None

    # no chart loaded at all
    stub._ti1_path = None
    assert stub._chart_instrument_code() is None


def test_an_i1_chart_read_with_an_i1_is_silent(tmp_path):
    """The mirror case, so the fix is not just 'ColorMunki always passes'."""
    _chart(tmp_path, stem="i1chart", ti2_body=_I1)
    code = instrument_family_of(read_target_instrument(tmp_path / "i1chart.ti2"))
    assert code == "i1"
    assert instrument_mismatch(code, "GretagMacbeth i1 Pro") is None
    assert instrument_mismatch(code, "X-Rite ColorMunki") is not None


def test_the_warning_actually_asks_the_chart_first():
    """The call site must consult the chart before the preference.

    **This test exists because the other five did not catch the bug.** Reverting
    the fix — putting `settings.get("chart_instrument")` back as the only source
    — left every one of them green: they exercise the helper and the two pure
    functions, and the helper is still perfectly correct while nothing calls it.
    A green suite around an unreachable fix is the same shape as beta.160, where
    an abort window was "fixed" for two releases without ever being reachable.

    Structural, deliberately. The behavioural route is a modal the check raises
    with `exec()`, which blocks a headless run; asserting on the source is worth
    more than asserting on nothing.
    """
    import inspect

    from ui.tabs.tab_measure import TabMeasure

    src = inspect.getsource(TabMeasure)
    idx = src.find("instrument_mismatch(chart_code, model)")
    assert idx > 0, "the mismatch call has moved — update this test"
    window = src[max(0, idx - 1200):idx]
    assert "_chart_instrument_code()" in window, (
        "the instrument-mismatch check no longer reads the chart. It is back to "
        'trusting settings.get("chart_instrument"), whose default is "i1", so '
        "every chart will again claim to be an i1Pro chart for any user who has "
        "not set that preference."
    )
