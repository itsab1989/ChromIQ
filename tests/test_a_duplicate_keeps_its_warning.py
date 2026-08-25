"""Duplicating a run must carry the facts that describe the files it copies.

`Run.DUPLICATE_GROUPS` copies the stored chart snapshot (`chart/**/*`) AND the
measurement (`{stem}.ti3`) together, then writes a FRESH `RunMeta` carrying only
a handful of fields. `chart_snapshot_stale` therefore landed back on its default
`False` — so a run whose stored chart no longer matches its measurement produced
a duplicate that claimed it did.

That flag has a live consumer: the Restore-Used-Chart button's tooltip
(`ui/measurement_target_bar.py:387`), which otherwise warns *"it is from an
earlier measurement — the measurement now in this run was taken with a different
chart."* Losing it means the user is offered a chart that does not describe the
measurement sitting beside it, with nothing saying so.
"""
from __future__ import annotations

import pytest

from core.file_manager import Project, RunMeta


@pytest.fixture
def project(tmp_path):
    return Project.create(tmp_path / "Demo-Duplicate-Warning",
                          "Demo-Duplicate-Warning")


def _make_run_with_a_stale_chart(project):
    run = project.current_run() or project.new_run()
    meta = run.load_meta()
    meta.chart_snapshot_stale = True
    meta.instrument = "i1"
    meta.paper = "A4"
    meta.description = "measured on Tuesday"
    run.save_meta(meta)
    return run


def test_the_duplicate_keeps_the_stale_chart_warning(project):
    src = _make_run_with_a_stale_chart(project)
    dup = project.duplicate_run(src)

    assert dup.load_meta().chart_snapshot_stale is True, (
        "the duplicate lost the 'this chart does not match this measurement' "
        "warning while copying BOTH the chart and the measurement")


def test_a_clean_run_stays_clean_when_duplicated(project):
    """The control: the flag is carried, not forced on."""
    src = project.current_run() or project.new_run()
    meta = src.load_meta()
    meta.chart_snapshot_stale = False
    src.save_meta(meta)

    dup = project.duplicate_run(src)
    assert dup.load_meta().chart_snapshot_stale is False, (
        "duplicating a run with a matching chart wrongly marked it stale")


def test_the_flag_is_a_real_field_with_a_false_default():
    """Guard the assumption the test above rests on.

    If `chart_snapshot_stale` ever stopped defaulting to False, the first test
    could pass without the fix — so state the default here rather than trust it.
    """
    assert RunMeta().chart_snapshot_stale is False
