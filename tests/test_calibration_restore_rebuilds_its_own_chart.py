"""Restoring a calibration chart must rebuild the CALIBRATION's chart.

Knut, #130 beta.159, marked "Bad fault":

    created chart with 60 patches, wrote text in Calibration Chart notes field.
    Made measurement, so that chart is saved to chart/ folder. Created new chart
    with 110 patches and a new chart note. Now clicked "restore used chart" A
    chart was restored, but the targen Total Patch Count changed tom 110 to 750
    and the resulting chart was 10 pager long.

750 was neither the stored 60 nor the on-screen 110: it was the patch count of
the selected **profile run's** chart. `rebuild_verification_pages` asked
"verification, or else the run?" — it was written when there were two run types
— so with Calibration selected it redrew the wrong target's chart over the files
`restore_slot` had just put back correctly.
"""
import ast
import inspect
import textwrap

import pytest


def _method_source() -> str:
    import ui.tabs.tab_chart as tc
    return inspect.getsource(tc.TabChart.rebuild_verification_pages)


def test_it_asks_whether_the_target_is_a_calibration():
    src = _method_source()
    assert "is_calibration()" in src, (
        "the rebuild still knows only two run types, so a calibration restore "
        "redraws the selected profile run's chart"
    )


def test_the_calibration_branch_uses_the_calibration_s_own_files():
    src = _method_source()
    fn = ast.parse(textwrap.dedent(src)).body[0]
    branch = next(
        (n for n in ast.walk(fn)
         if isinstance(n, ast.If) and isinstance(n.test, ast.Name)
         and n.test.id == "calibration"),
        None)
    assert branch is not None, "there is no `if calibration:` branch"
    taken = ast.unparse(ast.Module(body=branch.body, type_ignores=[]))
    assert "cal.ti1" in taken and "cal.ti2" in taken, (
        f"the calibration branch does not take its own chart:\n{taken}"
    )
    assert "proj.run(" not in taken, (
        f"the calibration branch reaches for a run's chart:\n{taken}"
    )


def test_a_calibration_does_not_move_the_current_run():
    """`set_current_run` is meaningless for a target that is not under runs/."""
    src = _method_source()
    assert "run_id is not None and proj.current_run()" in src, (
        "the rebuild would call set_current_run(None) for a calibration"
    )


def test_the_calibration_class_really_has_those_paths():
    """Guard the attribute names the branch depends on.

    `Calibration` exposes `.ti1`/`.ti2`; `Run` uses `.chart_ti1`/`.chart_ti2`.
    Using the run's names here would raise inside the `except` that swallows
    everything, and the restore would silently do nothing at all.
    """
    from core.file_manager import Calibration

    for name in ("ti1", "ti2", "stem", "dir", "snapshot_dir"):
        assert hasattr(Calibration, name), f"Calibration has no {name}"
    assert not hasattr(Calibration, "chart_ti1"), (
        "Calibration grew chart_ti1 — check which name the rebuild should use"
    )


def test_the_docstring_no_longer_claims_two_run_types():
    src = _method_source()
    assert "either" not in src.split('"""')[1].lower() or "three" in src.lower(), (
        "the docstring still says the rebuild covers 'either' run type"
    )
