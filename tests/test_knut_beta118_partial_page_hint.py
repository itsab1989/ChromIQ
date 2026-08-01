"""#130 (Knut, 2026-08-01): the "room left on the last page" hint fired on a
chart that had barely used the page at all.

    *"I get message 'Your patch set doesn't quite fill the last page - there's
    space for about 670 more patches'. Simultaneously the total patches count
    below the preview, in chart layout information frame, says 12 patches. The
    page count on the preview is also 1. Targen parameters also says patch count
    of 12. The number in the message is wrong."*

The arithmetic was right and everything else about it was wrong. The sheet did
have room for 670 more; but a 12-patch chart has not *almost* filled its page,
and "add a few more patches to fill the gap" cannot be acted on when the gap is
fifty times the chart.

The old gate was "at least one empty strip", which is as true of an almost-empty
page as an almost-full one. It now also requires the page to be at least half
full, and the window states the page's capacity so the number can be checked
against the patch count already on screen.
"""
from __future__ import annotations

import inspect
import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.tabs.tab_chart import TabChart                      # noqa: E402


def _blank_for(total, per, steps, monkeypatch, tmp_path):
    """Drive the real method with a stubbed geometry, so the decision under
    test is the one in tab_chart and not the engine's.

    A real file on disk, deliberately: an earlier version of this helper passed
    a stand-in object, `Path()` rejected it, and the method's own except-clause
    swallowed the TypeError and returned None — so every "must stay quiet" case
    passed while testing nothing at all.
    """
    from workflow.layout_engine import geometry, instruments, papers
    from workflow.layout_engine.presets import LayoutRecipe

    class _Lay:
        def __init__(self, pages, steps_in_pass):
            self.pages, self.steps_in_pass = pages, steps_in_pass

    monkeypatch.setattr(LayoutRecipe, "from_channels_json",
                        staticmethod(lambda _p: LayoutRecipe()))
    monkeypatch.setattr(instruments, "geom_from_build_kwargs", lambda _k: None)
    monkeypatch.setattr(papers, "dimensions_mm", lambda _p: (210.0, 297.0))
    monkeypatch.setattr(geometry, "patches_per_sheet", lambda *_a: per)
    monkeypatch.setattr(
        geometry, "compute",
        lambda *_a: _Lay(max(1, -(-total // per)) if per else 1, steps))

    ti2 = tmp_path / "c.ti2"
    ti2.write_text(f"CTI2\n\nNUMBER_OF_SETS {total}\n")
    return TabChart._partial_last_page_blank(TabChart.__new__(TabChart), ti2)


# ---- Knut's case ---------------------------------------------------------
def test_a_nearly_empty_page_says_nothing(monkeypatch, tmp_path):
    """12 patches on a sheet that holds 682. The old code offered to help fill
    the remaining 670."""
    assert _blank_for(total=12, per=682, steps=15, monkeypatch=monkeypatch, tmp_path=tmp_path) is None


def test_a_small_chart_on_a_small_capacity_sheet_is_also_quiet(monkeypatch, tmp_path):
    """Same shape of mistake at ordinary sizes: 12 of 63 is not almost-full."""
    assert _blank_for(total=12, per=63, steps=9, monkeypatch=monkeypatch, tmp_path=tmp_path) is None


# ---- the case the hint was built for still works -------------------------
def test_an_almost_full_page_still_offers_to_help(monkeypatch, tmp_path):
    """54 of 63 used, 9 free — exactly one empty strip, which is what the hint
    was written for (#93)."""
    assert _blank_for(total=54, per=63, steps=9, monkeypatch=monkeypatch, tmp_path=tmp_path) == 9


def test_a_page_just_over_half_full_still_counts(monkeypatch, tmp_path):
    """The boundary must not quietly exclude real cases: 32 of 63 is over half,
    so the hint stands."""
    assert _blank_for(total=32, per=63, steps=9, monkeypatch=monkeypatch, tmp_path=tmp_path) == 31


def test_a_page_just_under_half_full_is_quiet(monkeypatch, tmp_path):
    assert _blank_for(total=31, per=63, steps=9, monkeypatch=monkeypatch, tmp_path=tmp_path) is None


def test_a_full_page_says_nothing(monkeypatch, tmp_path):
    assert _blank_for(total=63, per=63, steps=9, monkeypatch=monkeypatch, tmp_path=tmp_path) is None


def test_a_gap_smaller_than_one_strip_says_nothing(monkeypatch, tmp_path):
    """Unchanged behaviour: a few slots short of full is not worth a window."""
    assert _blank_for(total=60, per=63, steps=9, monkeypatch=monkeypatch, tmp_path=tmp_path) is None


def test_the_overflow_page_case_is_measured_on_the_LAST_page(monkeypatch, tmp_path):
    """Two pages, 12 patches spilled onto the second — the second page is the
    one being judged, and it is nearly empty."""
    assert _blank_for(total=75, per=63, steps=9, monkeypatch=monkeypatch, tmp_path=tmp_path) is None


# ---- the threshold is a stated rule, not an accident ---------------------
def test_the_fill_threshold_is_half_a_page():
    assert TabChart._PARTIAL_PAGE_MIN_FILL == 0.5


# ---- the window shows a checkable number --------------------------------
def test_the_message_states_the_page_capacity():
    """Knut could not tell a wrong number from a right one because nothing on
    screen related to it. Both numbers are given now."""
    src = inspect.getsource(TabChart._maybe_warn_partial_last_page)
    assert "_last_page_capacity" in src
    assert "{cap}" in src
    assert re.search(r"\.format\([^)]*cap=", src), \
        "the capacity must actually be substituted, not just named in the text"


def test_capacity_is_reported_for_an_engine_chart(monkeypatch, tmp_path):
    """The number the window quotes has to be the real sheet capacity."""
    from workflow.layout_engine import geometry, instruments, papers
    from workflow.layout_engine.presets import LayoutRecipe
    monkeypatch.setattr(LayoutRecipe, "from_channels_json",
                        staticmethod(lambda _p: LayoutRecipe()))
    monkeypatch.setattr(instruments, "geom_from_build_kwargs", lambda _k: None)
    monkeypatch.setattr(papers, "dimensions_mm", lambda _p: (210.0, 297.0))
    monkeypatch.setattr(geometry, "patches_per_sheet", lambda *_a: 63)
    ti2 = tmp_path / "c.ti2"
    ti2.write_text("CTI2\n")
    assert TabChart._last_page_capacity(TabChart.__new__(TabChart), ti2) == 63


def test_capacity_is_zero_rather_than_an_error_for_a_printtarg_chart(
        monkeypatch, tmp_path):
    """printtarg charts have no engine recipe; the hint is engine-only, so this
    is only reached defensively — it must not raise."""
    from workflow.layout_engine.presets import LayoutRecipe
    monkeypatch.setattr(LayoutRecipe, "from_channels_json",
                        staticmethod(lambda _p: None))
    ti2 = tmp_path / "c.ti2"
    ti2.write_text("CTI2\n")
    assert TabChart._last_page_capacity(TabChart.__new__(TabChart), ti2) == 0


def test_capacity_survives_a_broken_sidecar(monkeypatch, tmp_path):
    from workflow.layout_engine.presets import LayoutRecipe

    def _boom(_p):
        raise ValueError("unreadable")

    monkeypatch.setattr(LayoutRecipe, "from_channels_json", staticmethod(_boom))
    ti2 = tmp_path / "c.ti2"
    ti2.write_text("CTI2\n")
    assert TabChart._last_page_capacity(TabChart.__new__(TabChart), ti2) == 0
