"""A failed test whose teardown blocks must END the run, red and named.

The two silent gate stalls of 2026-11-22: after a failure pytest's
faulthandler plugin and pytest-timeout both cancel their timers, so a blocked
teardown waited for ever. tests/failed_test_watchdog.py re-arms one. Proved
here on a planted project (a failing test whose fixture teardown sleeps 30 s,
`timeout = 3`), run as a subprocess pytest with and without the plugin.
"""
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

PLANTED = textwrap.dedent("""
    import time, pytest

    @pytest.fixture
    def blocked_teardown():
        yield
        time.sleep(30)          # stands for a teardown that never returns

    def test_planted_failure(blocked_teardown):
        assert False, "a failure first"
""")


def _project(tmp_path):
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\nfaulthandler_timeout = 60\ntimeout = 3\n"
        "timeout_method = thread\n", encoding="utf-8")
    (tmp_path / "test_planted.py").write_text(PLANTED, encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(REPO), QT_QPA_PLATFORM="offscreen")
    env.pop("PYTEST_ADDOPTS", None)
    env.pop("PYTEST_XDIST_WORKER", None)
    return env


def _cmd(*extra):
    return [sys.executable, "-m", "pytest", "-p", "no:cacheprovider",
            "-o", "addopts=", "-q", *extra, "test_planted.py"]


@pytest.mark.parametrize("xdist", [[], ["-n", "1"]], ids=["no_xdist", "xdist"])
def test_a_blocked_teardown_after_a_failure_ends_the_run(tmp_path, xdist):
    env = _project(tmp_path)
    t0 = time.monotonic()
    r = subprocess.run(_cmd("-p", "tests.failed_test_watchdog", *xdist),
                       cwd=tmp_path, env=env, capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       timeout=25)
    wall = time.monotonic() - t0
    out = r.stdout + r.stderr
    assert r.returncode != 0, out
    assert wall < 25, f"took {wall:.0f} s, the teardown sleeps 30: {out}"
    assert "Timeout" in out and "blocked_teardown" in out, (
        "the dump does not name the blocked teardown frame:\n" + out)
    if xdist:
        assert "test_planted_failure" in out and "crashed" in out, out


def test_without_the_hook_the_same_teardown_is_unwatched(tmp_path):
    """The control: pytest's own behaviour, which is why the hook exists. If
    this ever ends early, pytest stopped cancelling and the hook can go."""
    env = _project(tmp_path)
    p = subprocess.Popen(_cmd(), cwd=tmp_path, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            p.wait(timeout=10)      # 3 s limit + slack; the teardown takes 30
    finally:
        p.kill()
        p.communicate(timeout=10)
