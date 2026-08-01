"""#130 (Knut, beta.114 and beta.115): "Restore Used Chart" did nothing at all.

    *"The chart files in run1/ folder are identical to those in chart/ folder,
    but 'Restore Used Chart' button is active, so I click it. Same chart is in
    preview. Nothing happened, and the cht file in chart/ folder was not copied
    to runs/run1/ folder, but should have been copied."*

Reproduced against his own `Second-Project-R.zip`, which **cleared** the layer I
suspected: `restore_slot` copies the `.cht` correctly and sees the two charts as
different. The click simply never reached it — the handler returned silently
when the run could not be resolved.

Two faults follow, and both are fixed here:

1. A control that can do nothing without saying why. Whatever the cause
   underneath, silence is wrong: it now explains and points at the bar.
2. `.DS_Store` was being stored and restored as part of the chart — found only
   because his real project had been opened in Finder, which every real project
   has been.
"""
from __future__ import annotations

import inspect
import os
import types

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.verify_chart_snapshot import (slot_snapshot_files,   # noqa: E402
                                            snapshot_matches_live)


def _slot(tmp_path, names):
    snap = tmp_path / "chart"; snap.mkdir(exist_ok=True)
    for n in names:
        (snap / n).write_text("x")
    live = tmp_path / "live"; live.mkdir(exist_ok=True)
    return types.SimpleNamespace(snapshot_dir=snap,
                                 files_to_copy=lambda: [],
                                 live_files=lambda: [])


# ---- the operating system's leftovers are not part of the chart ----------
def test_ds_store_is_not_a_chart_file(tmp_path):
    """His project carried one, and it was being restored into the run."""
    slot = _slot(tmp_path, [".DS_Store", "P.ti1", "P.ti2"])
    assert [p.name for p in slot_snapshot_files(slot)] == ["P.ti1", "P.ti2"]


def test_every_dot_file_is_excluded_not_just_that_one(tmp_path):
    """Fixing the one name he happened to have would leave the next one."""
    slot = _slot(tmp_path, [".DS_Store", "._P.ti1", ".hidden", "P.ti2"])
    assert [p.name for p in slot_snapshot_files(slot)] == ["P.ti2"]


def test_a_chart_of_only_dot_files_counts_as_no_chart(tmp_path):
    slot = _slot(tmp_path, [".DS_Store"])
    assert slot_snapshot_files(slot) == []


def test_a_stray_dot_file_no_longer_makes_charts_look_different(tmp_path):
    """It also skewed the comparison that greys the button out."""
    snap = tmp_path / "chart"; snap.mkdir()
    live_dir = tmp_path / "live"; live_dir.mkdir()
    for d in (snap, live_dir):
        (d / "P.ti1").write_text("same")
    (snap / ".DS_Store").write_text("junk")
    slot = types.SimpleNamespace(
        snapshot_dir=snap, files_to_copy=lambda: [live_dir / "P.ti1"])
    assert snapshot_matches_live(slot) is True


# ---- the button never fails silently -------------------------------------
def test_a_restore_that_cannot_run_says_so(qapp=None):
    """*"Nothing happened"* — no chart, no message. Silence is the bug."""
    from ui.measurement_target_bar import MeasurementTargetBar
    src = inspect.getsource(MeasurementTargetBar._on_restore_clicked)
    none_branch = src.index("if result is None:")
    assert "QMessageBox.information" in src[none_branch:none_branch + 400]


def test_that_message_tells_the_user_what_to_do(qapp=None):
    import sys
    sys.path.insert(0, ".")
    from scripts.i18n_extract import extract_keys
    assert ("ChromIQ could not work out which run's stored chart to put back, "
            "so nothing has been changed.\n\n"
            "This usually means the Profile run or Verification date selection "
            "has moved on since the button was last enabled. Pick the run you "
            "want in the bar and try again — your files are exactly as they "
            "were.") in extract_keys()
