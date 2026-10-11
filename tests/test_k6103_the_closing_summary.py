"""Knut, #182 6103148331 (4.3.3 test, item 4): the "All strips read" window.

* "Strip read twice: none found" although he read several strips twice. His
  log (2026-10-10, run 2): every second reading was a deliberate re-read, the
  reader moved back to the strip first (A, L, W, S, P, Z, Y). "Was a strip
  read twice?" looks only for a reading that looks like ANOTHER strip, so it
  rightly found none; the window now names the strips read again on purpose
  and says what the check looked for.
* All summary lines as a bullet list under "Summary:".
"""
from __future__ import annotations

import types

from workflow import measurement_messages as M
from tests.test_neighbour_check_in_the_measure_tab import (  # noqa: F401
    _read_all, _tab, qapp)


def _pace(elapsed=10.0, patches=10):
    return types.SimpleNamespace(patches=patches, mean_seconds=elapsed / patches,
                                 elapsed=elapsed, too_fast=False, marginal=False)


def test_a_strip_read_again_on_purpose_is_named(qapp, tmp_path, monkeypatch):
    tab = _tab(tmp_path)
    _read_all(tab)
    monkeypatch.setattr(type(tab), "_refresh_pace_panel", lambda self, *a, **k: None)
    monkeypatch.setattr("core.measure_pace.measured_phrase", lambda p: "x")
    monkeypatch.setattr("core.measure_pace.strip_limit_fact", lambda c, n: "y")
    tab._pace_times = {}
    tab._strips_read_again = []
    for s in ("A", "B", "C", "A", "L", "A"):
        tab._show_strip_pace(s, _pace(), None)
    lines = tab._misread_summary().splitlines()
    assert M._SUM_READ_AGAIN_ONE.format(list="A") in lines
    tab._show_strip_pace("B", _pace(), None)
    lines = tab._misread_summary().splitlines()
    assert M._SUM_READ_AGAIN.format(n=2, list="A, B") in lines


def test_the_strip_test_says_what_it_looked_for(qapp, tmp_path, monkeypatch):
    tab = _tab(tmp_path)
    _read_all(tab)
    monkeypatch.setattr(type(tab), "_read_twice_was_active", lambda self: True)
    tab._read_twice_log = []
    tab._strips_read_again = ["A", "L"]
    lines = tab._misread_summary().splitlines()
    assert lines[-1] == ("Was a strip read twice? No reading looked like "
                         "another strip.")
    assert lines[-2] == "Strips you read again (2): A, L."
    assert "Strip read twice: none found." not in lines


def test_the_window_shows_a_bullet_list_under_summary(qapp, tmp_path):
    tab = _tab(tmp_path)
    html = tab._summary_html("Total measuring time: 00:01:00\n"
                             "Strip <read> & again: A.")
    assert html.startswith("<b>Summary:</b><ul")
    assert html.count("<li>") == 2
    assert "Strip &lt;read&gt; &amp; again: A." in html
    import inspect
    from ui.tabs import tab_measure
    src = inspect.getsource(tab_measure.TabMeasure)
    assert src.count("_QL(self._summary_html(summary), dlg)") == 2


def test_check_and_refine_gives_the_share_with_one_decimal():
    """Item 5: "4 of 1296 patches (0%)" became "(0.3%)"."""
    from workflow.refine_plan import RefinePlan
    import dataclasses
    fields = {f.name for f in dataclasses.fields(RefinePlan)}
    assert {"n_over", "n_total"} <= fields
    plan = RefinePlan.__new__(RefinePlan)
    plan.n_over, plan.n_total = 4, 1296
    assert plan.pct_over == "0.3"
    plan.n_over = 648
    assert plan.pct_over == "50.0"


# ---- item 2: the help, and "Show patch values on hover" on by default --------

def test_show_patch_values_on_hover_is_on_for_a_new_install(qapp, tmp_path):
    """Knut: "this checkbox should be default ON". A saved choice is kept."""
    tab = _tab(tmp_path)
    tab._load_measure_settings() if hasattr(tab, "_load_measure_settings") else None
    import inspect
    from ui.tabs import tab_measure
    src = inspect.getsource(tab_measure)
    assert 'bool(s.get("measure_patch_tile", True))' in src
    assert 'bool(s.get("manual2_patch_tile", True))' in src
    assert 'bool(data.get("patch_tile", True))' in src
    assert 'patch_tile", False)' not in src


def test_the_help_says_what_the_user_sees_and_what_to_do():
    from ui.dialogs import settings_dialog as sd
    from ui.tabs import tab_measure as tm
    import inspect
    for text in (sd.NEIGHBOUR_CHECK_SETTLE_HELP, tm.MEASURE_OUTLINES_HELP):
        assert "Measure the whole chart first" in text or \
            "measure the whole chart first" in text
        assert "Show patch values on hover" in text
        assert "Preferences ▸ Measurement" in text
        assert "Maximum ΔE00, all patches" in text
        assert "—" not in text
    assert "can also go again" in sd.NEIGHBOUR_CHECK_SETTLE_HELP
    assert "tr(NEIGHBOUR_CHECK_SETTLE_HELP)" in inspect.getsource(sd)
    assert "tr(MEASURE_OUTLINES_HELP)" in inspect.getsource(tm.TabMeasure)
