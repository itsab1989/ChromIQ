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
pytestmark = pytest.mark.skipif(
    not BIN.is_file(), reason="needs the built chromiq-chartread helper")

#: The chart these tests read, GENERATED rather than borrowed.
#:
#: This used to be ``pathlib.Path("/Users/Basti/ChromIQ/ttestitest/…")`` with a
#: ``skipif`` on its existence, so on CI, on a second developer's machine, on a
#: fresh clone — or on Basti's own laptop the day he deletes that project —
#: the whole file **skipped in silence**, and the four blockers below went
#: unguarded. It is the only regression guard the ``-x`` path has (finding F7,
#: `docs/cr30_reports/08-measure-wiring-critique.md` §6.4).
#:
#: Six strips of fifteen (A1…F15, 90 patches), which is what the full-read test
#: needs, laid out the way ``printtarg`` writes one: the keywords the helper
#: reads are ``TARGET_INSTRUMENT``, ``STEPS_IN_PASS``, ``PASSES_IN_STRIPS2`` and
#: the ``SAMPLE_LOC`` column. The XYZ columns are the chart's *expectation*,
#: which is what ``spot_ready`` hands back as ``exyz``.
_STRIPS = "ABCDEF"
_STEPS = 15


def _rgb_for(i: int) -> "tuple[float, float, float]":
    """A deterministic spread over the cube — no two patches alike, so a
    mis-paired reading shows up as a wrong colour rather than a coincidence.

    Patch 1 (A1) is a dark saturated blue-violet on purpose. It is the first
    patch the helper offers, and `test_a_wrong_value_is_flagged_not_silently_
    accepted` submits a white reading there and needs it REFUSED. The threshold
    is `WERR_TH 95.0` (`chromiq_chartread.c:71`) on `xyzLabDE`, which is
    chroma-heavy: near-BLACK against that white reading measures only dE 84.7
    and sails through, while this expectation measures ~105 — the same shape as
    the patch printtarg's randomiser happened to put first in the chart this
    fixture replaced. Nothing here may be left to happen.
    """
    if i == 1:
        return (45.0, 0.0, 50.0)
    return (round((i * 37) % 101, 4),
            round((i * 61) % 101, 4),
            round((i * 89) % 101, 4))


def _xyz_for(rgb: "tuple[float, float, float]") -> "tuple[float, float, float]":
    """A crude but monotone RGB->XYZ, adequate for a chart's expected values."""
    r, g, b = (c / 100.0 for c in rgb)
    return (round(41.24 * r + 35.76 * g + 18.05 * b, 5) or 0.00001,
            round(21.26 * r + 71.52 * g + 7.22 * b, 5) or 0.00001,
            round(1.93 * r + 11.92 * g + 95.05 * b, 5) or 0.00001)


def make_ti2(path: pathlib.Path, instrument: str = "CR30") -> pathlib.Path:
    """Write a printtarg-shaped ``.ti2`` naming *instrument*."""
    rows = []
    n = 0
    for step in range(1, _STEPS + 1):
        for strip in _STRIPS:
            n += 1
            rgb = _rgb_for(n)
            xyz = _xyz_for(rgb)
            rows.append(f'{n} "{strip}{step}" '
                        + " ".join(f"{v:.4f}" for v in rgb) + " "
                        + " ".join(f"{v:.5f}" for v in xyz) + " ")
    path.write_text(
        "CTI2   \n\n"
        'DESCRIPTOR "Argyll Calibration Target chart information 2"\n'
        'ORIGINATOR "Argyll printtarg"\n'
        'CREATED "Fri Aug 28 00:00:00 2026"\n'
        f'TARGET_INSTRUMENT "{instrument}"\n'
        'APPROX_WHITE_POINT "95.106486 100.000000 108.844025"\n'
        'COLOR_REP "iRGB"\n'
        'PAPER_SIZE "210.0x297.0"\n'
        'RANDOM_START "54"\n'
        f'STEPS_IN_PASS "{_STEPS}"\n'
        f'PASSES_IN_STRIPS2 "{len(_STRIPS)}"\n'
        'STRIP_INDEX_PATTERN "A-Z, A-Z"\n'
        'PATCH_INDEX_PATTERN "0-9,@-9,@-9;1-999"\n'
        'INDEX_ORDER "STRIP_THEN_PATCH"\n\n'
        "NUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z \n"
        "END_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n"
        + "\n".join(rows) + "\nEND_DATA\n",
        encoding="utf-8")
    return path


class Reader:
    """Drives the helper the way `measure_manager` does: one value per
    `spot_ready`, never ahead of it."""

    def __init__(self, tmp, instrument="CR30"):
        make_ti2(tmp / "n.ti2", instrument)
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
    r.send({"cmd": "goto", "patch": target})
    time.sleep(0.35)
    # Answer with the patch's OWN expected colour, taken from the spot_ready
    # the goto produced. chartread refuses an implausible reading and re-offers
    # the patch (see the test below), which would emit no `patch_read` at all
    # and turn a wrong-patch failure into a timeout — so the value has to suit
    # whichever patch we actually landed on. It still catches the bug: if the
    # goto were lost we would be answering A1 with A1's colour and `loc` would
    # come back "A1" instead of the patch the user clicked.
    x, y, z = r.events("spot_ready")[-1]["exyz"]
    r.send({"cmd": "value", "xyz": f"{x:.4f} {y:.4f} {z:.4f}"})
    deadline = time.time() + 8
    while len(r.events("patch_read")) <= before and time.time() < deadline:
        time.sleep(0.05)
    got = r.events("patch_read")[-1]
    assert got["loc"] == target, (
        f"value landed on {got['loc']!r}, the user clicked {target!r}")


def test_save_and_stop_ends_a_partial_read_and_writes_the_ti3(tmpchart):
    """"Keep what I measured" must actually end the session under -x.

    The engine's Save-Partial is a two-'q' protocol that waits for the give-up
    prompt — and that prompt lives inside the helper's `read_sample` branch,
    which -x never enters because it opens no instrument. Measured before the
    fix: one 'q' went out, `abort_confirm` came back, and the manager sat in
    `wait_give_up_prompt` for ever; the tab's Confirm-Abort →
    Keep-what-you-measured pair became a loop whose only exit was "Discard and
    stop", and the helper was left running.

    The path that DOES write under -x is stock chartread's: 'd' is answered by
    "at least one unread patch, are you sure", and 'y' there saves and exits 0.
    """
    r = tmpchart()
    deadline = time.time() + 8
    while not r.events("spot_ready") and time.time() < deadline:
        time.sleep(0.05)

    sent = 0
    for _ in range(3):
        spots = r.events("spot_ready")
        if not spots or spots[-1].get("all_done"):
            break
        x, y, z = spots[-1]["exyz"]
        before = len(r.events("patch_read"))
        r.send({"cmd": "value", "xyz": f"{x:.4f} {y:.4f} {z:.4f}"})
        sent += 1
        d2 = time.time() + 6
        while len(r.events("patch_read")) <= before and time.time() < d2:
            time.sleep(0.03)
    assert sent >= 2, "could not measure a partial run"

    r.send({"cmd": "done"})
    d2 = time.time() + 8
    while not r.events("unread_confirm") and time.time() < d2:
        time.sleep(0.05)
    assert r.events("unread_confirm"), (
        "finishing early did not ask about the unread patches")
    r.send({"cmd": "yes"})

    d2 = time.time() + 12
    while r.p.poll() is None and time.time() < d2:
        time.sleep(0.1)
    assert r.p.poll() == 0, (
        "save-and-stop did not end the session — this is the wedge returning")

    ti3 = r.tmp / "n.ti3"
    assert ti3.is_file(), "nothing was saved"
    lines = ti3.read_text().splitlines()
    b = next(i for i, l in enumerate(lines) if l.strip() == "BEGIN_DATA")
    e = next(i for i, l in enumerate(lines) if l.strip() == "END_DATA")
    rows = [x for x in lines[b + 1:e] if x.strip()]
    assert len(rows) == sent, f"measured {sent}, saved {len(rows)}"


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


def test_the_fixture_needs_nothing_outside_this_repository(tmp_path):
    """FINDING F7. These tests used to depend on a chart in one person's home
    directory, with a `skipif` on its existence — so everywhere else they
    skipped in silence and the four blockers above went unguarded. The chart is
    now generated; the only thing this file may require is the built helper.
    """
    # The needle is assembled here so this line is not itself a hit.
    home = "/" + "Users" + "/"
    src = pathlib.Path(__file__).read_text(encoding="utf-8")
    code = [ln for ln in src.splitlines()
            if not ln.lstrip().startswith(("#", '"', "*", "home ="))]
    assert not [ln for ln in code if home in ln], \
        "no absolute path into anybody's home outside the comments"
    assert "chromiq-chartread helper" in pytestmark.kwargs["reason"], \
        "the only thing that may make this file skip is the built helper"
    ti2 = make_ti2(tmp_path / "g.ti2", "CR30")
    text = ti2.read_text(encoding="utf-8")
    assert 'TARGET_INSTRUMENT "CR30"' in text
    assert "NUMBER_OF_SETS 90" in text
    for loc in ("A1", "B1", "C2", "D4", "F15"):
        assert f'"{loc}"' in text, f"{loc} is used by a test above"
