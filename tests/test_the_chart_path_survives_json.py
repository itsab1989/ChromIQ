"""#159 / Windows: the chart path was written into JSON unescaped.

Found on the owner's Windows ARM64 VM. A Windows chart path is
``C:\\Users\\...`` and every backslash begins a JSON escape sequence — ``\\U``
is not one, so the whole `session_start` line is rejected by the parser and
discarded. On EVERY measurement, on that platform, silently: the strip map and
the patch count that ride in that event simply never arrive.

macOS and Linux never showed it because their paths have no backslashes. They
would have shown it for a path containing a quote, which both allow.

⚠ THE SILENCE IS THE POINT. ChromIQ's reader drops a line it cannot parse
without a word — so the symptom is not an error but an absence, and an absence
is what nobody goes looking for. So these tests assert BOTH halves: that the
event arrives parsed, and that no line was dropped on the way.

The helper already had `cq_json_escape` and already used it for the `saved`
event's path, three thousand lines earlier.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, ReplaySession, write_replay_script  # noqa: E402

ARGYLL = Path("/Applications/Argyll/bin")

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not HELPER.exists(),
                       reason="chromiq-chartread helper not built"),
]

#: Names that break unescaped JSON. The backslash is the Windows case — a
#: directory called `Users` under a drive root is the shape of every real
#: Windows path. The quote is the same fault reachable on any platform.
AWKWARD = [
    pytest.param("back\\slash", id="backslash-the-windows-case"),
    pytest.param('quo"te', id="quote-any-platform"),
    pytest.param("both\\and\"quote", id="both"),
]


@pytest.fixture(scope="module")
def chart(tmp_path_factory):
    """One small chart, built once, in an ordinary directory."""
    targen = shutil.which("targen") or str(ARGYLL / "targen")
    if not Path(targen).exists():
        pytest.skip("Argyll targen not available")
    tmp = tmp_path_factory.mktemp("jsonpath")
    base = tmp / "chart"
    subprocess.run([targen, "-v0", "-d2", "-G", "-f30", str(base)],
                   check=True, capture_output=True, cwd=tmp, timeout=300)
    from workflow.layout_engine.chart import build_chart
    build_chart(base.with_suffix(".ti1"), base, instrument="i1", paper="A4",
                randomize=False)
    replay = tmp / "replay.txt"
    write_replay_script(base.with_suffix(".ti2"), replay)
    return base, replay


def _run_from(directory: Path, chart):
    """Copy the chart into *directory* and start a session from there."""
    base, replay = chart
    directory.mkdir(parents=True, exist_ok=True)
    for f in base.parent.glob(base.name + ".*"):
        shutil.copy2(f, directory / f.name)
    shutil.copy2(replay, directory / replay.name)
    return ReplaySession(directory / base.name, directory / replay.name)


class _Session:
    """`_run_from` as a context manager that always reaps.

    The helper sits waiting on stdin for ever, so the plain `finish()` — which
    waits for it to exit — times out on a session nobody navigated to the end.
    Nothing here needs a clean exit code; it needs the process gone.
    """

    def __init__(self, session):
        self.s = session

    def __enter__(self):
        return self.s

    def __exit__(self, *_exc):
        self.s.proc.kill()
        self.s.finish(timeout=5)


@pytest.mark.parametrize("awkward", AWKWARD)
def test_the_session_starts_whatever_the_path_contains(awkward, chart, tmp_path):
    """The event must ARRIVE — parsed, not merely emitted."""
    with _Session(_run_from(tmp_path / awkward, chart)) as s:
        s.wait_event("session_start", timeout=30)
        start = [e for e in s.events if e.get("event") == "session_start"][0]
        assert start["patches"] > 0, "the patch count did not survive"
        assert start["strips"], (
            "the strip map did not survive — the app cannot show progress")


@pytest.mark.parametrize("awkward", AWKWARD)
def test_no_line_is_quietly_dropped(awkward, chart, tmp_path):
    """The reader swallows a line it cannot parse. That silence hid this fault
    for the whole of the Windows session, so it is asserted against directly."""
    with _Session(_run_from(tmp_path / awkward, chart)) as s:
        s.wait_event("session_start", timeout=30)
        unparsed = [ln for ln in s.raw_lines
                    if ln.startswith("{") and _bad(ln)]
        assert unparsed == [], (
            f"the helper emitted JSON nothing can read: {unparsed[:1]}")


def _bad(line):
    try:
        json.loads(line)
        return False
    except json.JSONDecodeError:
        return True


@pytest.mark.parametrize("awkward", AWKWARD)
def test_the_path_it_reports_is_the_path_it_opened(awkward, chart, tmp_path):
    """Escaping must preserve the value, not merely make it parseable —
    stripping the backslashes would parse and be wrong."""
    d = tmp_path / awkward
    with _Session(_run_from(d, chart)) as s:
        s.wait_event("session_start", timeout=30)
        start = [e for e in s.events if e.get("event") == "session_start"][0]
        assert awkward in start["chart"], (
            f"the path came back altered: {start['chart']!r}")
