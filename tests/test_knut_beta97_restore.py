"""#130 (Knut, 2026-07-29, testing beta.97 on his copy of Demo-Full-RGB).

Three findings, reproduced by running his sequence on his own project:

1. *"pressing Restore Used Chart, I get a warning message (good), but the
   preview is not updated. I have to click NEXT and PREV buttons to get the
   screen to redraw preview."*
2. *"after restore of the chart the options in the Create Chart is not changed
   back to what they were before."*
3. *"If I now select one of the existing verification run dates and Restore Used
   Chart, the run type goes back to profiling. This should NOT happen."*

(3) is a regression from beta.97's own change and is the worst of them: it moved
him off the run he was working on, so he could no longer tell whether the chart
had been replaced at all.

(1) and (3) are fixed here. (2) is confirmed and still open — see the issue.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.tabs.tab_chart import TabChart               # noqa: E402


# ---- 3. the Run-type reset belongs to a project load, and nowhere else ----
def test_the_run_type_reset_is_not_in_the_generic_bar_defaulting():
    """_default_bar_to_current_run runs at the end of EVERY successful
    generation — including the redraw that follows Restore Used Chart. Putting
    the reset there threw him back to Profiling mid-task."""
    src = inspect.getsource(TabChart._default_bar_to_current_run)
    assert "set_run_type" not in src, (
        "the Run-type reset is back in the path every generation takes")


def test_the_reset_has_its_own_method_called_only_from_a_project_load():
    reset = inspect.getsource(TabChart._reset_run_type_for_loaded_project)
    assert 'ctl.set_run_type("profiling")' in reset
    assert 'ctl.set_verification_id("")' in reset

    whole = inspect.getsource(TabChart)
    calls = whole.count("self._reset_run_type_for_loaded_project()")
    assert calls == 1, f"expected exactly one call site, found {calls}"
    assert "_reset_run_type_for_loaded_project()" in inspect.getsource(
        TabChart._load_existing_profile)


def test_restoring_a_chart_never_touches_the_run_type():
    """His words: this should only happen when loading a project."""
    for fn in (TabChart.rebuild_verification_pages,
               TabChart._on_generate_finished,
               TabChart._default_bar_to_current_run):
        assert "set_run_type" not in inspect.getsource(fn), fn.__name__


def test_the_reset_never_breaks_a_load():
    src = inspect.getsource(TabChart._reset_run_type_for_loaded_project)
    assert "except Exception" in src


# ---- 1. the preview must notice a chart whose bytes changed --------------
def test_the_refresh_dedup_is_keyed_on_content_not_only_the_path():
    """Restore Used Chart puts DIFFERENT bytes at the SAME path — same run, same
    stem — so a dedup that compares paths decides the chart is already showing
    and skips the reload. That is why he had to click NEXT and PREV."""
    src = inspect.getsource(TabChart._on_target_changed)
    assert "self._chart_stamp(ti2)" in src
    assert "self._shown_chart_stamp" in src
    assert "if ti2 == self._shown_chart_ti2:" not in src, \
        "the path-only dedup is back"


def test_the_stamp_includes_when_the_chart_was_written(tmp_path):
    ti2 = tmp_path / "c.ti2"
    ti2.write_text("CTI2\n")
    first = TabChart._chart_stamp(ti2)
    assert first[0] == str(ti2)
    assert first[1] is not None

    import os as _os
    st = ti2.stat()
    _os.utime(ti2, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
    assert TabChart._chart_stamp(ti2) != first, \
        "a chart rewritten at the same path must read as a different chart"


def test_the_stamp_survives_a_missing_file(tmp_path):
    stamp = TabChart._chart_stamp(tmp_path / "gone.ti2")
    assert stamp[0].endswith("gone.ti2") and stamp[1] is None


def test_no_chart_clears_both_halves_of_the_marker():
    """Otherwise a stale stamp could match the next chart by accident."""
    src = inspect.getsource(TabChart._on_target_changed)
    i = src.index("self._shown_chart_ti2 = None")
    assert "self._shown_chart_stamp = None" in src[i:i + 200]


def test_every_place_that_records_the_shown_chart_records_its_stamp():
    """A path recorded without its stamp would re-open the same hole.

    Counted by what the line DOES, not by the name of the variable it reads.
    The old form matched the literal ``= ti2``, so a caller whose parameter is
    called ``ti2_path`` scored as an unstamped assignment while its stamp line
    — ``_chart_stamp(ti2_path)`` — did not count at all. It failed on a path
    that records the stamp correctly, which is a test reporting on spelling
    rather than on behaviour.
    """
    whole = inspect.getsource(TabChart)
    assigns = sum(1 for line in whole.splitlines()
                  if line.strip().startswith("self._shown_chart_ti2 = ")
                  and not line.strip().endswith("None"))
    stamps = sum(1 for line in whole.splitlines()
                 if "self._shown_chart_stamp = self._chart_stamp(" in line)
    assert stamps >= assigns - 1, (
        f"{assigns} places record the shown chart but only {stamps} record its "
        f"stamp")
