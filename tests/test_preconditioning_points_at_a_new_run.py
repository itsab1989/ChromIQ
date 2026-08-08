"""Choosing "Use as pre-conditioning" must say which run it is about to build.

Basti, 2026-08-08: *"when i choose in build profile or check and refine tabs
pop ups to use a profile as preconditioning it sends me back to create chart.
in the bar it stays at run 1 (overwrite). is this expected and good or should it
choose a new run here?"*

It already chooses a new run — only the bar did not say so. Generating with
pre-conditioning armed runs

    proj.new_run(preconditioning_from=parent)

and the alignment step that would honour the bar's selection is explicitly
skipped for this case (`not cal_target_active and not
self._preconditioning_from_dialog`). So a fresh run is created whatever the bar
shows, while the bar read "Run 1 (overwrite)" — promising a replacement of the
very run the pre-conditioning profile came from.

Two things are pinned here: that the bar is pointed at "New run", and that it is
pointed there **before** the panel is filled. Changing the run selection saves
and reloads the tab's per-run settings, so doing it afterwards would wipe the
pre-conditioning path and tick this method has just set — exactly how a settings
load undid Check & Refine's refinement ticks in beta.197.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.tabs.tab_chart import TabChart                     # noqa: E402


def test_the_bar_is_pointed_at_a_new_run():
    src = inspect.getsource(TabChart.apply_preconditioning)
    assert 'set_profile_run("")' in src, (
        "the run bar is left showing 'Run N (overwrite)' while generating will "
        "actually create a new run — the label promises the opposite"
    )


def test_it_happens_before_the_panel_is_filled():
    """Order matters: a run change reloads the per-run settings."""
    src = inspect.getsource(TabChart.apply_preconditioning)
    assert src.index('set_profile_run("")') < src.index("_guided_precond_path.setText"), (
        "the run is switched after the pre-conditioning path is filled in, so "
        "the settings reload for the new run wipes what was just set"
    )


def test_generating_still_seeds_the_run_from_the_parent():
    """The behaviour the label now describes must still be there.

    If this ever stops creating a run, pointing the bar at 'New run' would
    become the lie instead.
    """
    whole = inspect.getsource(TabChart)
    assert "proj.new_run(preconditioning_from=parent)" in whole, (
        "pre-conditioning no longer seeds a fresh run from the parent"
    )


def test_the_alignment_step_is_still_skipped_for_preconditioning():
    """It must not fall back to honouring the bar and overwrite the parent run."""
    whole = inspect.getsource(TabChart)
    # `_align_current_run_to_target()` is called from more than one place, so
    # match the guard itself rather than the nearest call.
    assert ("if not cal_target_active and not self._preconditioning_from_dialog"
            in whole), (
        "the pre-conditioning build now aligns to the bar's selection, which "
        "would overwrite the run the pre-conditioning profile came from"
    )
