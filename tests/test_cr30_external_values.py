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
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
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
        if self.p.poll() is None:
            os.killpg(os.getpgid(self.p.pid), signal.SIGKILL)


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
