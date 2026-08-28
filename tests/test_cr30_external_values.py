"""The external-values (-x) reading path, driven exactly as ChromIQ drives it.

Runs the REAL chromiq-chartread binary with no instrument attached, so these
tests need no hardware and no CR30.

They pin four fixes (#159), each of which was a blocker:

 A1  `-x` and `--json` were mutually exclusive. In JSON mode stdin belongs to the
     command reader thread, so `-x`'s own con_fgets could never succeed: it
     returned immediately, the loop `continue`d and spun. Measured on the
     unpatched binary: **32 million lines and 3.5 million spot_ready events in
     six seconds.** A non-Argyll instrument backend was therefore impossible.
 A2  Aborting an `-x` session segfaulted: `it` is only created inside
     `if (xtern == 0)`, so it is NULL on this path, and several exits called
     `it->del(it)` unguarded.
 A3  The `.ti3` claimed `TARGET_INSTRUMENT "Unknown Instrument"`, which made
     ChromIQ offer FWA on a measurement with no spectral data at all.
 A4  An honest `CR30` name was fatal in our own fork too.
"""
import json
import os
import pathlib
import shutil
import signal
import subprocess
import threading
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
BIN = ROOT / "native" / "chartread_helper" / "build" / "chromiq-chartread"
SRC_TI2 = pathlib.Path("/Users/Basti/ChromIQ/ttestitest/ttestitest.ti2")

pytestmark = pytest.mark.skipif(
    not BIN.is_file() or not SRC_TI2.is_file(),
    reason="needs the built helper and a real .ti2")


class Reader:
    """Drives the helper the way `measure_manager` does: one value per
    `spot_ready`, never ahead of it."""

    def __init__(self, tmp, instrument="CR30"):
        ti2 = tmp / "n.ti2"
        ti2.write_text(SRC_TI2.read_text().replace(
            'TARGET_INSTRUMENT "X-Rite ColorMunki"',
            f'TARGET_INSTRUMENT "{instrument}"'))
        self.tmp = tmp
        self.ev, self.raw, self._lock = [], [], threading.Lock()
        self.p = subprocess.Popen(
            [str(BIN), "-xx", "--json", "n"], cwd=tmp,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1, start_new_session=True)
        self._pump_thread = threading.Thread(target=self._pump, daemon=True)
        self._pump_thread.start()

    def _pump(self):
        try:
            self._pump_lines()
        except (ValueError, OSError):      # pipe closed under us: teardown
            pass

    def _pump_lines(self):
        for line in self.p.stdout:
            line = line.strip()
            with self._lock:
                self.raw.append(line)
                if line.startswith("{"):
                    try:
                        self.ev.append(json.loads(line))
                    except ValueError:
                        pass

    def events(self, name):
        with self._lock:
            return [e for e in self.ev if e.get("event") == name]

    def send(self, obj):
        """Tolerant of the helper having already exited — once the last patch
        is read it can finish on its own, and a write then hits a closed pipe."""
        try:
            self.p.stdin.write(json.dumps(obj) + "\n")
            self.p.stdin.flush()
        except (BrokenPipeError, ValueError, OSError):
            pass

    def kill(self):
        """Tear down without leaking a BrokenPipeError.

        The helper often exits on its own once the chart is finished, so the
        pipes must be closed explicitly rather than left for the garbage
        collector — an unraisable BrokenPipeError at teardown is reported by
        pytest as an ERROR on an otherwise passing test, which is exactly the
        noise that hides a real failure later.
        """
        # ORDER MATTERS. Killing first ends the pump thread's iterator on its
        # own; closing stdout while that thread is still inside it turns the
        # BrokenPipeError into a ValueError and pytest still reports an
        # unraisable warning. So: kill, reap, JOIN the reader, and only then
        # close. An earlier attempt at this fix closed first and did nothing.
        if self.p.poll() is None:
            try:
                os.killpg(os.getpgid(self.p.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        try:
            self.p.wait(timeout=5)
        except Exception:                       # noqa: BLE001 — teardown only
            pass
        self._pump_thread.join(timeout=5)
        for pipe in (self.p.stdin, self.p.stdout, self.p.stderr):
            try:
                if pipe is not None and not pipe.closed:
                    pipe.close()
            except (BrokenPipeError, OSError, ValueError):
                pass


@pytest.fixture
def tmpchart(tmp_path):
    r = None

    def make(instrument="CR30"):
        nonlocal r
        r = Reader(tmp_path, instrument)
        return r
    yield make
    if r:
        r.kill()


def test_A1_json_mode_does_not_spin(tmpchart):
    """The whole reading path depends on this not looping."""
    r = tmpchart()
    time.sleep(3.0)
    spots = r.events("spot_ready")
    assert r.p.poll() is None, "helper exited instead of waiting for a value"
    assert len(spots) <= 3, (
        f"{len(spots)} spot_ready events in 3 s — the -x/--json spin is back")


def test_A4_an_honest_CR30_chart_is_accepted(tmpchart):
    r = tmpchart("CR30")
    time.sleep(2.0)
    assert r.events("session_start"), "CR30 chart rejected: " + " | ".join(r.raw[:4])


def test_a_refused_chart_says_why_on_the_event_stream(tmpchart):
    """Without `-x` the helper must explain itself in MACHINE-READABLE form.

    `measure_manager` falls back to stock chartread when the engine exits
    non-zero having emitted no event, and then reports "unknown error" — because
    the reason only ever reached stderr. Stock chartread cannot know the name
    `CR30` either, so that fallback fails a second time and more confusingly.
    This event is what lets the GUI report the real reason and suppress a
    fallback that could never work.
    """
    import subprocess
    tmp = tmpchart().tmp                      # reuse the fixture's chart
    r = subprocess.run([str(BIN), "--json", "n"], cwd=tmp,
                       capture_output=True, text=True, timeout=60)
    assert r.returncode != 0
    events = [json.loads(l) for l in (r.stdout or "").splitlines()
              if l.strip().startswith("{")]
    refused = [e for e in events if e.get("kind") == "chart_refused"]
    assert refused, f"no chart_refused event; stdout was {r.stdout!r}"
    assert refused[0]["instrument"] == "CR30"
    assert "-x" in refused[0]["detail"]


def test_an_unknown_instrument_is_still_fatal(tmpchart):
    """The gate must stay strict — only named external instruments pass."""
    r = tmpchart("Totally Made Up 9000")
    time.sleep(2.0)
    assert not r.events("session_start")
    assert r.p.poll() is not None, "should have exited"


def test_full_read_writes_a_usable_ti3(tmpchart):
    """A1+A2+A3 together: read patches, finish cleanly, write a correct .ti3."""
    r = tmpchart()
    seen, sent = 0, 0
    # Read the WHOLE chart. Finishing with patches still unread takes a
    # different confirmation branch, which is not what this test is about.
    deadline = time.time() + 120
    while time.time() < deadline:
        spots = r.events("spot_ready")
        if r.p.poll() is not None:      # finished by itself
            break
        if len(spots) <= seen:
            time.sleep(0.03)
            continue
        s = spots[-1]
        seen = len(spots)
        if s.get("all_done"):
            break
        if s.get("read"):            # already recorded -> move on, do not re-send
            r.send({"cmd": "next_unread"})
            continue
        x, y, z = s["exyz"]          # the chart's own expectation -> plausible
        r.send({"cmd": "value", "xyz": f"{x:.4f} {y:.4f} {z:.4f}"})
        sent += 1
    # Finish: "done" asks whether to save, "yes" confirms. Wait for the process
    # to actually exit rather than sleeping a guessed amount — the save is
    # asynchronous with respect to our writes.
    r.send({"cmd": "done"})
    time.sleep(0.6)
    r.send({"cmd": "yes"})
    deadline = time.time() + 15
    while r.p.poll() is None and time.time() < deadline:
        time.sleep(0.1)
        if time.time() - deadline > -13:      # nudge once if it is still asking
            r.send({"cmd": "yes"})
            time.sleep(0.4)

    assert r.p.poll() == 0, (
        f"helper did not exit cleanly (A2 was a SIGSEGV); "
        f"last output: {' | '.join(r.raw[-4:])}")
    reads = r.events("patch_read")
    assert sent >= 80, f"only {sent} patches read; the chart has 90"
    assert len(reads) == sent, f"sent {sent} values, {len(reads)} recorded"

    ti3 = r.tmp / "n.ti3"
    assert ti3.is_file()
    lines = ti3.read_text().splitlines()
    # NB anchor on whole lines: END_DATA_FORMAT precedes BEGIN_DATA, so a naive
    # index("END_DATA") slices backwards and silently finds nothing.
    b = next(i for i, l in enumerate(lines) if l.strip() == "BEGIN_DATA")
    e = next(i for i, l in enumerate(lines) if l.strip() == "END_DATA")
    rows = [r_ for r_ in lines[b + 1:e] if r_.strip()]
    assert len(rows) == sent

    assert any('TARGET_INSTRUMENT "CR30"' in l for l in lines), \
        "A3: the .ti3 must name the chart's instrument, not 'Unknown Instrument'"
    assert not any("SPEC_" in l for l in lines), \
        "-x is colorimetric only; spectral columns would be a false claim"
    assert any('DEVICE_CLASS "OUTPUT"' in l for l in lines)


def _drive(r, seq, settle=0.35):
    """Send a sequence, waiting for the read to register between steps."""
    for obj in seq:
        r.send(obj)
        time.sleep(settle)


def test_two_values_in_a_row_are_both_recorded(tmpchart):
    """The line channel is a QUEUE, not a single slot.

    It was one buffer, overwritten unconditionally, so a second command
    arriving before the read loop woke up destroyed the first. Measured then:
    two values back to back produced ONE patch_read and the first value
    vanished with no event and no error — wrong colour in the .ti3, no trace.
    """
    r = tmpchart()
    deadline = time.time() + 8
    while not r.events("spot_ready") and time.time() < deadline:
        time.sleep(0.05)
    before = len(r.events("patch_read"))
    r.send({"cmd": "value", "xyz": "20 20 20"})
    r.send({"cmd": "value", "xyz": "10 10 10"})     # no wait: that is the point
    deadline = time.time() + 8
    while len(r.events("patch_read")) < before + 2 and time.time() < deadline:
        time.sleep(0.05)
    got = r.events("patch_read")[before:]
    assert len(got) == 2, f"{len(got)} of 2 values recorded — the queue lost one"
    assert [round(v) for v in got[0]["xyz"]] == [20, 20, 20]
    assert [round(v) for v in got[1]["xyz"]] == [10, 10, 10]


@pytest.mark.parametrize("target", ["B1", "C2", "A1"])
def test_a_goto_lands_the_value_on_the_clicked_patch(tmpchart, target):
    """Click-to-jump must put the reading where the user clicked.

    The Measure tab advertises "click any patch to jump straight to it". The
    goto label does NOT travel on the line queue — the read loop takes it from
    `cq_goto_target`, which only the instrument path's uicallback used to fill.
    On the -x path it was never filled, so the jump silently did nothing and the
    next value landed on whatever patch happened to be current: B1's colour
    written into A3.
    """
    r = tmpchart()
    deadline = time.time() + 8
    while not r.events("spot_ready") and time.time() < deadline:
        time.sleep(0.05)
    before = len(r.events("patch_read"))
    _drive(r, [{"cmd": "goto", "patch": target},
               {"cmd": "value", "xyz": "55 55 55"}])
    deadline = time.time() + 8
    while len(r.events("patch_read")) <= before and time.time() < deadline:
        time.sleep(0.05)
    got = r.events("patch_read")[-1]
    assert got["loc"] == target, (
        f"value landed on {got['loc']!r}, the user clicked {target!r}")


def test_a_wrong_value_is_flagged_not_silently_accepted(tmpchart):
    """chartread checks each reading against the chart's expectation.

    Free safety net for a CR30: a magnet-gated reading returns a fixed
    near-white constant, so submitting it for a dark patch produces a large
    delta E and the patch is re-offered instead of being accepted.
    """
    r = tmpchart()
    deadline = time.time() + 8
    while not r.events("spot_ready") and time.time() < deadline:
        time.sleep(0.05)
    first = r.events("spot_ready")[-1]
    x, y, z = first["exyz"]
    assert y < 60, "fixture patch should be dark enough for this to be a big miss"
    r.send({"cmd": "value", "xyz": "96.42 100.00 82.52"})   # a white reading
    time.sleep(1.5)
    assert any("unexpected response" in l for l in r.raw), \
        "an implausible reading was accepted without comment"
    again = r.events("spot_ready")[-1]
    assert again["id"] == first["id"], "the patch should be re-offered"
