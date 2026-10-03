"""The sweep itself must be runnable and must be able to fail.

B8-22 asks for a regression sweep that can be re-run before every beta instead
of improvised. A script nobody can invoke, or one whose checks can only say
PASS, is not that. These run in a second and need no app window:

    QT_QPA_PLATFORM=offscreen pytest tests/test_the_sweep_is_runnable.py -q

They deliberately do NOT drive the window — that is what `run-sweep.sh` is for.
They prove the harness around it is sound.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# NOT `os.environ.setdefault("CHROMIQ_SETTINGS_FILE", ...)` here. A module-level
# line runs at COLLECTION, and under xdist every worker collects every file, so
# it set the variable in every worker for the whole run: every `AppSettings()`
# in every other file then logged "Settings SANDBOXED", and every child process
# a test started shared one fixed `/tmp` ini across all twelve workers and
# across runs (2026-10-03, seen as `test_replacing_a_stored_chart_keeps_the_
# old_one.py` failing only under a loaded run). The sweep needs it only while
# THIS file's tests run, so `_sweep_settings_sandbox` sets it for this module
# and puts back what was there. `tests/test_no_test_file_sets_the_settings_
# file_at_import.py` keeps it that way.

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "scanner_sweep" / "scanner_window_sweep.py"
HERE = SCRIPT.parent
# The sweep lives IN THE REPO, not in a deliverable folder. Commit 162f8dff
# already learned this once: "the auto-align challenge set is reproducible
# from the repo, not from a swept temp folder" — four scripts had lived only
# in /private/tmp, which is swept nightly, and were lost. A regression sweep
# that exists only on somebody's Desktop is the same mistake.
REPO = Path(os.environ.get("CHROMIQ_TREE", str(REPO_ROOT)))


@pytest.fixture(scope="module", autouse=True)
def _sweep_settings_sandbox(tmp_path_factory):
    """The sweep script refuses to import without a sandboxed settings file
    (and `record` names it). Set for this module only, then undone."""
    mp = pytest.MonkeyPatch()
    if not os.environ.get("CHROMIQ_SETTINGS_FILE"):
        mp.setenv("CHROMIQ_SETTINGS_FILE",
                  str(tmp_path_factory.mktemp("sweep-selftest") / "settings.ini"))
    yield
    mp.undo()


@pytest.fixture(scope="module")
def sweep(_sweep_settings_sandbox):
    if not REPO.is_dir():
        pytest.skip(f"{REPO} is not on this machine")
    sys.path.insert(0, str(REPO))
    spec = importlib.util.spec_from_file_location("scanner_window_sweep", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_script_is_where_the_runner_looks_for_it():
    assert SCRIPT.is_file(), f"{SCRIPT} is missing — run-sweep.sh invokes it"
    assert (HERE / "run-sweep.sh").is_file()
    assert os.access(HERE / "run-sweep.sh", os.X_OK), "run-sweep.sh is not executable"


def test_every_check_is_registered_and_callable(sweep):
    assert len(sweep.CHECKS) >= 30, (
        f"only {len(sweep.CHECKS)} checks — the sweep covers the whole window")
    for cid, (name, fn) in sweep.CHECKS.items():
        assert cid.startswith("J") and cid[1:].isdigit(), cid
        assert name and callable(fn), cid


def test_every_check_in_the_README_table_exists(sweep):
    """A table that names a check nobody can run is worse than no table."""
    import re
    readme = (HERE / "README.md").read_text(encoding="utf-8")
    listed = set(re.findall(r"^\| (J\d+) \|", readme, re.M))
    assert listed, "the README's check table is missing"
    missing = listed - set(sweep.CHECKS)
    assert not missing, f"the README names checks that do not exist: {sorted(missing)}"
    unlisted = set(sweep.CHECKS) - listed
    assert not unlisted, f"these checks are not in the README table: {sorted(unlisted)}"


def test_a_check_can_actually_fail(sweep, tmp_path, monkeypatch):
    """The harness must be able to say FAIL, and must say it in the file it
    writes — otherwise a green sweep means nothing."""
    monkeypatch.setattr(sweep, "RESULTS", tmp_path / "r.json")
    monkeypatch.setattr(sweep, "PROGRESS", tmp_path / "p.md")
    monkeypatch.setattr(sweep, "_results", [])
    sweep.record("J99", "a deliberate failure", "FAIL", "the note", "")
    sweep.record("J98", "a deliberate pass", "PASS", "another note", "")
    import json
    rows = {r["id"]: r for r in json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))}
    assert rows["J99"]["status"] == "FAIL" and rows["J98"]["status"] == "PASS"
    table = (tmp_path / "p.md").read_text(encoding="utf-8")
    assert "**FAIL**" in table and "**PASS**" in table
    assert "the note" in table, "the evidence must survive into the table"


def test_the_progress_table_is_rewritten_after_every_single_check(sweep, tmp_path,
                                                                 monkeypatch):
    """This sweep takes a quarter of an hour. A killed run must leave behind
    everything it got to."""
    monkeypatch.setattr(sweep, "RESULTS", tmp_path / "r.json")
    monkeypatch.setattr(sweep, "PROGRESS", tmp_path / "p.md")
    monkeypatch.setattr(sweep, "_results", [])
    sweep.record("J01", "first", "PASS", "one", "")
    assert (tmp_path / "p.md").is_file()
    first = (tmp_path / "p.md").read_text(encoding="utf-8")
    sweep.record("J02", "second", "PASS", "two", "")
    second = (tmp_path / "p.md").read_text(encoding="utf-8")
    assert "J01" in first and "J02" not in first
    assert "J01" in second and "J02" in second


def test_the_cache_probe_can_see_a_stale_cache(sweep):
    """`cache_state` is the sweep's own instrument for the marquee's new
    geometry cache (J26). An instrument that always reads 'coherent' would have
    passed J26 with the cache broken."""
    from PyQt6.QtGui import QImage
    from PyQt6.QtWidgets import QApplication

    from ui.scan_grid_marquee import GridSpec, ScanGridMarquee
    app = QApplication.instance() or QApplication([])          # noqa: F841
    m = ScanGridMarquee()
    m.resize(300, 300)
    m.set_grid(GridSpec([(0.0, 0.0, 0.5, 0.5), (0.5, 0.0, 0.5, 0.5)], aspect=1.0))
    img = QImage(200, 200, QImage.Format.Format_RGB32)
    img.fill(0xFFFFFF)
    m.set_image(img)
    assert sweep.cache_state(m) == "coherent"
    # Change an input the cache depends on WITHOUT going through the setter —
    # exactly the mistake the probe exists to catch.
    m._sample_frac = 0.25
    assert sweep.cache_state(m) == "STALE", (
        "the probe cannot tell a stale cache from a fresh one, so J26 proves "
        "nothing")
