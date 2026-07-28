"""#131 (Knut, 2026-07-27): Skip Strip, proved against the real helper binary.

He asked for this specifically — *"Analyse thoroughly possible reasons. Test all
candidates … then verify what actually works, and make fix accordingly. Do not
guess arbitrary solutions anymore"* — after two fixes of mine that did not work.

So these tests drive the **real** `chromiq-chartread` through its replay
instrument, fail a strip exactly as he does, and read back which strip the
engine arms next.

What the binary actually does, measured rather than assumed:

======================================  =============================
sent after a strip fails                strip armed next
======================================  =============================
``forward`` alone                       the SAME strip  ← beta.62-64
``ok`` then ``forward``                 the next strip  ← correct
``ok`` then ``next_unread``             the next strip *only while one
                                        is unread*
======================================  =============================

The reason is in the helper: after a failed strip it waits in
``cq_prompt_char()``, where **any key that is not Esc/q means "retry"**. A
navigation command sent there is spent as that "any key", so it reads as retry
and nothing moves. And "next unread" is wrong even at the menu: a strip that has
just failed is itself still unread, so it lands back where it started.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
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


@pytest.fixture(scope="module")
def chart(tmp_path_factory):
    targen = shutil.which("targen") or str(ARGYLL / "targen")
    if not Path(targen).exists():
        pytest.skip("Argyll targen not available")
    tmp = tmp_path_factory.mktemp("skip")
    base = tmp / "chart"
    subprocess.run([targen, "-v0", "-d2", "-G", "-f60", str(base)],
                   check=True, capture_output=True, cwd=tmp)
    from workflow.layout_engine.chart import build_chart
    build_chart(base.with_suffix(".ti1"), base, instrument="i1", paper="A4",
                randomize=False)
    replay = tmp / "replay.txt"
    write_replay_script(base.with_suffix(".ti2"), replay)
    return base, replay


def _armed_after(chart, commands, read_all_first=False):
    """Fail a strip, send *commands*, and return the strip armed at the end."""
    base, replay = chart
    s = ReplaySession(base, replay)
    try:
        s.wait_event("session_start")
        if read_all_first:
            for _ in range(3):
                i = s.event_index()
                s.send(cmd="swipe")
                s.wait_event("strip_read", after=i)
        armed = [e for e in s.events if e.get("event") == "strip_ready"][-1]["strip"]

        i = s.event_index()
        s.send(cmd="swipe", fault="misread")
        s.wait_event("error", after=i)

        i = s.event_index()
        for cmd in commands:
            s.send(**cmd)
            time.sleep(0.4)
        time.sleep(0.6)
        with s._lock:
            readies = [e["strip"] for e in s.events[i:]
                       if e.get("event") == "strip_ready"]
        return armed, (readies[-1] if readies else None)
    finally:
        try:
            s.send(cmd="quit")
            s.proc.wait(timeout=3)
        except Exception:      # noqa: BLE001
            s.proc.kill()


def test_a_navigation_command_alone_does_not_move(chart):
    """beta.62-64 sent exactly this, and Knut saw the arrow stay put."""
    before, after = _armed_after(chart, [{"cmd": "forward"}])
    assert after == before, (
        "if this ever passes, the helper's retry prompt has changed and "
        "skip_current_strip can be simplified")


def test_acknowledge_then_forward_moves_on(chart):
    before, after = _armed_after(chart, [{"cmd": "ok"}, {"cmd": "forward"}])
    assert after != before, f"stayed on {before}"


def test_it_moves_on_a_chart_that_is_already_complete(chart):
    """His second case: refining a finished measurement."""
    before, after = _armed_after(chart, [{"cmd": "ok"}, {"cmd": "forward"}],
                                 read_all_first=True)
    assert after != before, f"stayed on {before}"


def test_the_manager_sends_exactly_that_sequence():
    """The unit-level guard, so the sequence proved above cannot drift."""
    from workflow.measure_manager import MeasureManager

    class _R:
        def __init__(self): self.out = []
        def write_stdin(self, d): self.out.append(d)
        def __getattr__(self, _n): return lambda *a, **k: None

    m = MeasureManager(_R())
    m._engine_active = True
    m.skip_current_strip()

    assert m._runner.out == ['{"cmd": "ok"}\n'], m._runner.out
    assert m._pending_post_retry_key == "f", \
        "'n' (next unread) lands back on the failed strip — it is still unread"


# ---- patch-by-patch mode (Knut, #131 2026-07-28) --------------------------
@pytest.fixture(scope="module")
def spot_session(chart):
    """The same chart, read one patch at a time."""
    base, replay = chart
    s = ReplaySession(base, replay, extra_args=["-p"])
    try:
        s.wait_event("spot_ready")
        yield s
    finally:
        try:
            s.send(cmd="quit")
            s.proc.wait(timeout=3)
        except Exception:      # noqa: BLE001
            s.proc.kill()


def _armed_patch(s):
    with s._lock:
        for e in reversed(s.events):
            if e.get("event") == "spot_ready":
                return e.get("loc")
    return None


def test_forward_alone_moves_the_patch(spot_session):
    """No retry prompt is waiting here, so nothing has to be spent on one."""
    before = _armed_patch(spot_session)
    spot_session.send(cmd="forward")
    time.sleep(0.6)
    assert _armed_patch(spot_session) != before


def test_the_acknowledgement_would_read_the_patch_instead(spot_session):
    """Return is the READ trigger in this mode — which is why sending it as an
    acknowledgement did nothing useful, and why Skip appeared dead."""
    from workflow.chartread_engine import KEY_TO_COMMAND
    assert KEY_TO_COMMAND["\r"] == {"cmd": "ok"}
    # …and the helper maps both "ok" and "read" to the same key.
    import pathlib as _p
    src = (_p.Path(__file__).resolve().parents[1] / "native" /
           "chartread_helper" / "chromiq_json.c").read_text()
    assert 'strcmp(cmd, "read") == 0' in src and "0x0d" in src


def test_the_manager_sends_forward_alone_in_patch_mode():
    from workflow.measure_manager import MeasureManager

    class _R:
        def __init__(self): self.out = []
        def write_stdin(self, d): self.out.append(d)
        def __getattr__(self, _n): return lambda *a, **k: None

    m = MeasureManager(_R())
    m._engine_active = True
    m._spot_mode = True
    m.skip_current_strip()

    assert m._runner.out == ['{"cmd": "forward"}\n'], m._runner.out
    assert m._pending_post_retry_key is None
