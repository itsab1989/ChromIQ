"""#130 (Knut, 2026-07-30): "Restore Used Chart" must not offer a restore that
would do nothing.

    *"When the current chart is identical to the chart inside chart/ folder, are
    there any reasons or cases where it is needed to be active and available to
    use? For me it is confusing that the button is active and when I press
    'Restore Used Chart' seemingly nothing happens … then the 'Restore Used
    Chart' could be disabled / greyed with a tool-tip 'Currently loaded chart
    files are already identical to stored files in chart-folder. There is no
    need to restore the chart files.'"*

He is right that there is no such case: restoring a copy of what is already
loaded copies the files over themselves. A button that produces no visible
effect reads as a broken button.
"""
from __future__ import annotations

import os
import types

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.verify_chart_snapshot import snapshot_matches_live  # noqa: E402


def _slot(tmp_path, live_names, stored):
    live_dir = tmp_path / "live"; live_dir.mkdir(exist_ok=True)
    snap = tmp_path / "chart"; snap.mkdir(exist_ok=True)
    live = []
    for name, body in live_names.items():
        f = live_dir / name
        f.write_text(body)
        live.append(f)
    for name, body in stored.items():
        (snap / name).write_text(body)
    return types.SimpleNamespace(snapshot_dir=snap, files_to_copy=lambda: live)


def test_identical_files_need_no_restore(tmp_path):
    slot = _slot(tmp_path, {"a.ti1": "one", "a.ti2": "two"},
                 {"a.ti1": "one", "a.ti2": "two"})
    assert snapshot_matches_live(slot) is True


def test_different_contents_still_need_one(tmp_path):
    slot = _slot(tmp_path, {"a.ti1": "one"}, {"a.ti1": "CHANGED"})
    assert snapshot_matches_live(slot) is False


def test_a_missing_file_still_needs_one(tmp_path):
    slot = _slot(tmp_path, {"a.ti1": "one", "a.ti2": "two"}, {"a.ti1": "one"})
    assert snapshot_matches_live(slot) is False


def test_an_extra_stored_file_still_needs_one(tmp_path):
    """The stale .cht case: an extra file means the two are not the same chart."""
    slot = _slot(tmp_path, {"a.ti1": "one"},
                 {"a.ti1": "one", "old.cht": "left behind"})
    assert snapshot_matches_live(slot) is False


def test_no_stored_chart_is_not_a_match(tmp_path):
    live_dir = tmp_path / "live"; live_dir.mkdir()
    f = live_dir / "a.ti1"; f.write_text("one")
    slot = types.SimpleNamespace(snapshot_dir=tmp_path / "chart",
                                 files_to_copy=lambda: [f])
    assert snapshot_matches_live(slot) is False


def test_nothing_loaded_is_not_a_match(tmp_path):
    snap = tmp_path / "chart"; snap.mkdir()
    slot = types.SimpleNamespace(snapshot_dir=snap, files_to_copy=lambda: [])
    assert snapshot_matches_live(slot) is False


def test_the_button_uses_his_exact_tooltip_wording(tmp_path):
    """He wrote the sentence himself; quoting it back is the least surprising
    thing the tooltip can say."""
    import sys
    sys.path.insert(0, ".")
    from scripts.i18n_extract import extract_keys
    # The literal is split across source lines, so searching the file text
    # cannot see it; the extractor joins the pieces the way Python does.
    assert ("Currently loaded chart files are already identical to stored "
            "files in chart-folder. There is no need to restore the chart "
            "files.") in extract_keys()


def test_both_run_types_are_covered(tmp_path):
    """*"either in runs/runN/chart/ or runs/runN/verifications chart/"* — he
    asked for both, and the profiling branch alone would have looked done."""
    import inspect
    from ui.measurement_target_bar import MeasurementTargetController
    src = inspect.getsource(MeasurementTargetController)
    assert src.count("snapshot_matches_live(") == 2
