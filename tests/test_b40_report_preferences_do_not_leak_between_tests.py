"""B8-930 (beta 40): the report window's Preferences never leak from one test
into the next.

`tests/test_g7_reports_across_places.py` failed twice in one full tier and
passed alone: an earlier file on the same worker had left
`report_default_type` at Grey and tone check in the per-worker settings store,
and since K31 a new report starts on that Preferences type. See
`tests/conftest.py::_report_preferences_start_default`.

The two tests below run in this order (one file, one worker): the first
leaves every key changed, the second must find them at their defaults.

MUTATION, proven red: make `_report_preferences_start_default` return at
once (the second test sees the first one's values).
"""
from __future__ import annotations

from tests.conftest import _REPORT_START_KEYS

_CHANGED = {"report_default_type": "t3_grey_and_tone",
            "report_default_show_details": False,
            "compliance_default_set": "chromiq_quick"}


def test_1_a_test_leaves_the_report_preferences_changed():
    from core.settings import AppSettings
    assert set(_CHANGED) == set(_REPORT_START_KEYS)
    s = AppSettings()
    for k, v in _CHANGED.items():
        s.set(k, v)
    assert all(AppSettings().get(k) == v for k, v in _CHANGED.items())


def test_2_the_next_test_starts_on_the_defaults():
    from core.settings import DEFAULTS, AppSettings
    s = AppSettings()
    got = {k: s.get(k) for k in _REPORT_START_KEYS}
    assert got == {k: DEFAULTS[k] for k in _REPORT_START_KEYS}, got


def test_3_the_g7_order_that_failed_now_passes():
    """The order found in the tier, as one subprocess run: k31 then g7."""
    import os
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:xdist", "-o", "addopts=",
         "-q", "-p", "no:cacheprovider",
         "tests/test_k31_report_model.py::"
         "test_new_report_starts_on_preferences_then_the_runs_own_default",
         "tests/test_g7_reports_across_places.py"],
        cwd=root, env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=600)
    tail = "\n".join(r.stdout.splitlines()[-15:])
    assert r.returncode == 0, "the k31-then-g7 order did not finish green:\n" \
        + tail
