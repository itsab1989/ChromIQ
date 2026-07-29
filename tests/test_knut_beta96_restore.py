"""#130 (Knut, 2026-07-29, testing beta.96 on his copy of Demo-Verify-History).

*"I loaded the project, changed to profile run1 and run type verification, then
selected first verification date 2026-01-12_110000. I then tried to click
'Restore Used Chart', which immediately replaced the chart in the verifications
folder, and it was clear that the restored chart was very different from the one
that was in the verifications folder. In this case, why did I not get a warning
that I would overwrite the chart? IF the check deemed them the same, why was the
restored chart looking so different? is this a problem only seen in the demo
files again?"*

Both halves answered by running his exact sequence on his own project and
comparing every file byte for byte.

**No warning: correct.** The snapshot's ``.ti1``, ``.ti2`` and
``.channels.json`` were byte-identical to the live ones, so
``live_differs_from_snapshot`` rightly said there was nothing to overwrite. The
warning is about replacing a *different* chart, and this was the same chart.

**The very different chart: a real bug, and not the demo's.** What changed the
chart was not the restore but the page rebuild that follows it:

* ``rebuild_verification_pages`` restores the chart's own recipe into the
  **Manual** panels — engine toggle, layout recipe, pinned patch count — but
  ``_collect_params()`` reads whichever mode is **on screen**, and the app opens
  in Guided. Every restored setting was discarded and a brand-new chart was laid
  out: ``RANDOM_START`` with a fresh seed where the original was ``CHART_ID``
  fixed-order, 15 patches per pass instead of 16, 60 sets instead of 64.
* And the auto-tag step then upgraded ``CHART_ID`` to ``RANDOM_START`` anyway —
  which chartread reads differently.

That is data integrity, not cosmetics: a verification's ``.ti3`` describes the
sheet that was measured, and the ``.ti2`` beside it had quietly become a
different sheet with nothing said.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.tabs.tab_chart import TabChart, _ChartRebuildGuard   # noqa: E402


# ---- the guard: a redraw may never change the chart ----------------------
def _chart(tmp_path, stem="P-verify"):
    ti1 = tmp_path / f"{stem}.ti1"
    ti2 = tmp_path / f"{stem}.ti2"
    side = tmp_path / f"{stem}.channels.json"
    ti1.write_text("CTI1\nNUMBER_OF_SETS 64\n")
    ti2.write_text('CTI2\nCHART_ID "1875869861"\nSTEPS_IN_PASS "16"\n'
                   "NUMBER_OF_SETS 64\n")
    side.write_text('{"layout": {"seed": 1875869861}}')
    return ti1, ti2, side


def test_a_rebuild_that_relaid_the_chart_is_undone(tmp_path):
    """The exact shape of what happened to him: the rebuild rewrites the .ti2
    with a different layout, and the chart is put back."""
    ti1, ti2, side = _chart(tmp_path)
    guard = _ChartRebuildGuard(ti2)

    ti2.write_text('CTI2\nRANDOM_START "1228950828"\nSTEPS_IN_PASS "15"\n'
                   "NUMBER_OF_SETS 60\n")
    changed = guard.put_back()

    assert changed == [ti2.name]
    assert 'CHART_ID "1875869861"' in ti2.read_text()
    assert "STEPS_IN_PASS \"16\"" in ti2.read_text()


def test_the_auto_tag_alone_is_enough_to_trip_it(tmp_path):
    """One keyword is not cosmetic: chartread keys its auto strip-ID and its
    bidirectional recognition off CHART_ID versus RANDOM_START."""
    _ti1, ti2, _s = _chart(tmp_path)
    guard = _ChartRebuildGuard(ti2)
    ti2.write_text(ti2.read_text().replace("CHART_ID", "RANDOM_START"))

    assert guard.put_back() == [ti2.name]
    assert "CHART_ID" in ti2.read_text()


def test_a_faithful_rebuild_is_left_alone(tmp_path):
    """The guard is a safety net, not a veto: a redraw that reproduced the
    chart exactly must pass through silently."""
    _ti1, ti2, _s = _chart(tmp_path)
    guard = _ChartRebuildGuard(ti2)
    assert guard.put_back() == []


def test_every_defining_file_is_held(tmp_path):
    ti1, ti2, side = _chart(tmp_path)
    guard = _ChartRebuildGuard(ti2)
    for p in (ti1, ti2, side):
        p.write_text("clobbered")
    assert sorted(guard.put_back()) == sorted(p.name for p in (ti1, ti2, side))
    assert "CTI1" in ti1.read_text()
    assert '"seed": 1875869861' in side.read_text()


def test_the_page_images_are_deliberately_not_held(tmp_path):
    """Redrawing them is the whole point of the rebuild."""
    _ti1, ti2, _s = _chart(tmp_path)
    tif = tmp_path / "P-verify.tif"
    tif.write_bytes(b"old")
    guard = _ChartRebuildGuard(ti2)
    tif.write_bytes(b"new page")

    assert guard.put_back() == []
    assert tif.read_bytes() == b"new page"


def test_a_missing_file_is_recreated_not_lost(tmp_path):
    """A rebuild that deletes the chart is the worst case of all."""
    _ti1, ti2, _s = _chart(tmp_path)
    guard = _ChartRebuildGuard(ti2)
    ti2.unlink()
    assert guard.put_back() == [ti2.name]
    assert 'CHART_ID "1875869861"' in ti2.read_text()


def test_holding_never_raises_on_an_unreadable_chart(tmp_path):
    guard = _ChartRebuildGuard(tmp_path / "does-not-exist.ti2")
    assert guard.put_back() == []


# ---- the rebuild must build in the mode it restored into -----------------
def test_the_rebuild_switches_to_the_mode_it_restored_into():
    """The root cause. _restore_chart_settings fills the MANUAL panels;
    _collect_params reads whichever mode is on screen; the app opens Guided."""
    src = inspect.getsource(TabChart.rebuild_verification_pages)
    assert "restored_recipe = self._restore_chart_settings(ti2)" in src
    assert 'self._switch_mode("manual")' in src
    restore_at = src.index("_restore_chart_settings")
    collect_at = src.index("self._collect_params()")
    switch_at = src.index('_switch_mode("manual")')
    assert restore_at < switch_at < collect_at, (
        "the mode must be switched after the recipe is restored and before the "
        "parameters are collected")


def test_the_rebuild_arms_the_guard():
    src = inspect.getsource(TabChart.rebuild_verification_pages)
    assert "_ChartRebuildGuard(ti2)" in src
    assert src.index("_ChartRebuildGuard(ti2)") < src.index(
        "load_ti1_and_generate_preview"), "arm it before the build starts"


def test_the_guard_is_released_after_the_auto_tag():
    """Releasing it earlier put the bytes back and then let the auto-tag
    rewrite them a line later — which is what the first attempt at this fix
    did."""
    src = inspect.getsource(TabChart._on_generate_finished)
    assert "_maybe_autotag_randomised(ti2)" in src
    assert "_release_rebuild_guard()" in src
    assert src.index("_maybe_autotag_randomised(ti2)") < \
        src.index("_release_rebuild_guard()", src.index("_maybe_autotag_randomised(ti2)"))


def test_the_user_is_told_when_the_chart_had_to_be_put_back():
    """Silence would be the same fault in a different coat."""
    src = inspect.getsource(TabChart._release_rebuild_guard)
    assert "put_back()" in src
    assert "appendPlainText" in src
    assert "still matches" in src


# ---- loading a project resets Run type to Profiling ----------------------
def test_loading_a_project_returns_the_run_type_to_profiling():
    """Knut: *"When using the load profile button in create chart, and then
    loading a stored project.json file: Reset Run type to Profiling, so that all
    newly loaded charts start at its profiling data."*

    It lived in _default_bar_to_current_run at first, which every successful
    generation also calls — see test_knut_beta97_restore for what that cost.
    """
    src = inspect.getsource(TabChart._reset_run_type_for_loaded_project)
    assert 'ctl.set_run_type("profiling")' in src
    assert 'ctl.set_verification_id("")' in src


def test_the_reset_is_on_the_path_a_project_load_takes():
    src = inspect.getsource(TabChart._load_existing_profile)
    assert "_default_bar_to_current_run()" in src
