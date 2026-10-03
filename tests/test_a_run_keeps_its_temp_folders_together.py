"""Every temp folder a test run makes lies in that run's own folder (dsk2).

Measured 2026-10-02: each ``--runslow`` gate left ~1.3 GB of ``chromiq-*``
folders loose in the system temp folder, held for an hour until the next run's
sweep. ``tests/conftest.py::_enter_the_run_temp`` points ``tempfile`` at one
``chromiq-run-*`` folder per run, which a green run removes as it ends (proved
by hand with a probe file: 0 folders left after a green run, all kept after a
red one).
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def test_tempfile_points_into_this_runs_folder():
    run = Path(tempfile.gettempdir())
    real = Path(os.environ["CHROMIQ_SUITE_REAL_TMP"])
    assert run.name.startswith("chromiq-run-"), run
    assert run.parent == real
    assert str(run) == os.environ["CHROMIQ_SUITE_RUN_TMP"]


def test_a_new_temp_folder_lands_inside_it(tmp_path):
    d = Path(tempfile.mkdtemp(prefix="chromiq-probe-"))
    try:
        assert d.parent == Path(os.environ["CHROMIQ_SUITE_RUN_TMP"])
    finally:
        d.rmdir()



def test_the_caches_that_outlive_a_run_stay_in_the_system_folder():
    """The demo-project cache is placed through _REAL_TEMP, not gettempdir,
    or every run would rebuild it (about two minutes)."""
    src = (Path(__file__).resolve().parent / "conftest.py").read_text(encoding="utf-8")
    assert '_REAL_TEMP / "chromiq-demo-projects-cache"' in src
    assert "root = _REAL_TEMP" in src             # the sweep looks there too
