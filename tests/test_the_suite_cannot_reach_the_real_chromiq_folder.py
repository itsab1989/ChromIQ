"""No test may reach the owner's real ~/ChromIQ, whatever settings it holds.

Two fixes had already been made and neither shut the door:

1. `tests/conftest.py::pytest_configure` sandboxes the QSettings store. Its own
   message says why that is not enough: "overriding QSettings alone is not
   enough: custom_output_path then falls back to '', which IS ~/ChromIQ".
2. The same hook then moved `core.settings.DEFAULTS["custom_output_path"]`,
   which covers `AppSettings` and every double built from `DEFAULTS`.

What neither covers is a settings double whose store is its own dict (it
answers "" for a key nobody set), a `settings=None`, and the nineteen places,
in fourteen files, that built `Path.home() / "ChromIQ"` for themselves without
asking the settings at all. Each was an independent door, and the suite could only shut them one
test at a time - which is how the owner's own
`scanner-test-targets/.provisioned.json` came to carry a gate run's timestamp
weeks after fix 2.

`core.platform_paths.default_output_root()` is now the single definition of
that fallback and `CHROMIQ_OUTPUT_ROOT` moves it, so one line in
`pytest_configure` shuts all nineteen at once.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from core.platform_paths import default_output_root

REPO = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# The one definition
# ---------------------------------------------------------------------------

def test_the_default_is_the_home_folder_when_nothing_overrides_it(
        the_real_default_output_root):
    """What the app does on a user's machine. The fixture lifts the suite's
    override for this one test, which is the only way to see it."""
    assert the_real_default_output_root == Path.home() / "ChromIQ"
    assert default_output_root() == Path.home() / "ChromIQ"


def test_the_override_moves_it(monkeypatch, tmp_path):
    monkeypatch.setenv("CHROMIQ_OUTPUT_ROOT", str(tmp_path / "elsewhere"))
    assert default_output_root() == tmp_path / "elsewhere"


def test_the_suite_is_running_with_it_moved():
    """The whole point: inside a test run, the fallback is NOT the real
    folder."""
    assert os.environ.get("CHROMIQ_OUTPUT_ROOT"), (
        "pytest_configure no longer sandboxes the output root")
    assert default_output_root() != Path.home() / "ChromIQ"


# ---------------------------------------------------------------------------
# Nobody builds it by hand any more
# ---------------------------------------------------------------------------

def test_no_module_builds_the_default_root_for_itself():
    """The check that would have found this in the first place.

    One definition means one place the suite has to override. A second one is
    a door nobody knows about until it is found by its damage.
    """
    offenders = []
    for pkg in ("core", "ui", "workflow"):
        for p in sorted((REPO / pkg).rglob("*.py")):
            if p.name == "platform_paths.py":
                continue          # the definition itself
            text = p.read_text(encoding="utf-8", errors="replace")
            for n, line in enumerate(text.splitlines(), 1):
                if 'Path.home() / "ChromIQ"' in line and "``" not in line:
                    offenders.append(f"{p.relative_to(REPO)}:{n}")
    assert not offenders, (
        "these build the default output root by hand instead of calling "
        "core.platform_paths.default_output_root(), so the test suite cannot "
        f"redirect them away from the owner's real projects: {offenders}")


# ---------------------------------------------------------------------------
# The doors that the settings sandbox could never reach
# ---------------------------------------------------------------------------

class _AnEmptyDouble:
    """A settings double of the kind dozens of test files write: its own dict,
    never seeded from DEFAULTS, so every key it was not given answers ""."""

    def __init__(self, **kw):
        self._s = dict(kw)

    def get(self, k, d=None):
        return self._s.get(k, d)


@pytest.mark.parametrize("settings", [None, _AnEmptyDouble(),
                                      _AnEmptyDouble(custom_output_path="")])
def test_the_scanner_targets_folder_is_never_the_real_one(settings):
    """`ScannerProfileDialog` calls `ensure_user_targets_dir(self._settings)`
    unconditionally as it opens, and that both `mkdir`s and copies. With any of
    these three settings objects it used to land in the owner's folder."""
    from workflow.standard_targets import user_targets_dir
    d = user_targets_dir(settings)
    assert Path.home() / "ChromIQ" not in d.parents, (
        f"the scanner tool would provision into the owner's own folder: {d}")


def test_the_file_manager_root_is_never_the_real_one():
    from core.file_manager import FileManager
    from core.settings import AppSettings
    fm = FileManager(AppSettings())
    assert fm.root_dir() != Path.home() / "ChromIQ"


# ---------------------------------------------------------------------------
# The guards this must not have made vacuous
# ---------------------------------------------------------------------------

def test_the_guards_still_watch_the_real_folder():
    """Redirecting the fallback would be worthless if it also moved what the
    guards look at. Both compute the real folder from `Path.home()` itself, so
    a test that writes there still fails even with the override in place."""
    import inspect

    import tests.conftest as ct
    assert ct._REAL_CHROMIQ == Path.home() / "ChromIQ"
    src = inspect.getsource(ct)
    assert '_REAL_CHROMIQ = Path.home() / "ChromIQ"' in src, (
        "the guard now resolves the real folder through the same function the "
        "suite redirects, which would make it watch the sandbox and pass for "
        "ever")


def test_the_guard_would_still_catch_a_write(tmp_path):
    """Not vacuous: drive the guard's own comparison against a folder that DID
    change, and prove it says so. Run against a stand-in, because proving it on
    the real folder would mean writing into it."""
    import tests.conftest as ct

    stand_in = tmp_path / "ChromIQ"
    (stand_in / "a-project").mkdir(parents=True)
    (stand_in / "a-project" / "chart.ti2").write_text("v1", encoding="utf-8")

    real = ct._REAL_CHROMIQ
    try:
        ct._REAL_CHROMIQ = stand_in
        before = ct._real_chromiq_entries()
        (stand_in / "a-project" / "chart.ti2").write_text("v2 - rewritten",
                                                          encoding="utf-8")
        after = ct._real_chromiq_entries()
    finally:
        ct._REAL_CHROMIQ = real

    changed = sorted(k for k in set(after) & set(before)
                     if after[k] != before[k])
    assert changed, ("the recursive fingerprint no longer notices a file "
                     "rewritten inside a folder that already existed - which "
                     "is the exact write it was built for")


# ---------------------------------------------------------------------------
# A test that needs the real default can still have it
# ---------------------------------------------------------------------------

def test_the_opt_in_is_a_licence_to_look_and_not_to_touch(
        the_real_default_output_root):
    """The fixture lifts the redirect. It does not lift the guards - if it did,
    a test could quietly opt out of the whole protection."""
    import tests.conftest as ct
    assert the_real_default_output_root == Path.home() / "ChromIQ"
    assert ct._REAL_CHROMIQ == Path.home() / "ChromIQ"


# ---------------------------------------------------------------------------
# End to end: a subprocess, no conftest, no fixtures
# ---------------------------------------------------------------------------

def test_the_override_works_from_the_environment_alone(tmp_path):
    """Prove it the way a driver script would use it - in a fresh interpreter
    with nothing but the environment variable, so this cannot be passing on
    something the test session happens to have patched."""
    out = subprocess.run(
        [sys.executable, "-c",
         "from core.platform_paths import default_output_root;"
         "print(default_output_root())"],
        cwd=str(REPO), timeout=60, capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "CHROMIQ_OUTPUT_ROOT": str(tmp_path / "sandbox")})
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == str(tmp_path / "sandbox")
