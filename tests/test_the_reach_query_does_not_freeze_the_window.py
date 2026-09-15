"""A tester, v4.3.0-beta.16: "if there is a valid icc profile in the project,
selecting this [From profile gamut] causes it to hang".

It did, and the window really did stop: the reach query asks xicclu for all
5,960 master colours on the GUI thread, xicclu is single-threaded, and measured
on real profiles that cost 0.5 s to 7.4 s with nothing on screen to say so.

Two things fixed it and both are guarded here.

* **The same question, over more than one process.** xicclu answers one stdin
  line per output line and nothing carries between lines, so N processes over N
  slices return exactly what one process over all of them returns. The flags,
  the profile and the intent are untouched: `-fif` is still `-fif`, because
  `-fb` disagrees with it about which colours are printable (2,896 in gamut
  against 3,838) and that is Knut's call, not a speed decision.
* **The margin is a threshold, not a question.** It is applied to the answer,
  so changing it cannot change the round trip, and re-asking xicclu for it
  spent seconds re-deriving numbers that could not have moved.
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from core.resource_path import argyll_binary
from workflow import gamut_target as G
from workflow import xicclu_runner as X

_XICCLU = argyll_binary("xicclu")


# --------------------------------------------------------------------------
# A fake that behaves like xicclu: one output line per input line, and an
# answer that depends on the INPUT, so a mis-ordered or mis-sliced batch is
# visible in the values rather than only in the count.
# --------------------------------------------------------------------------
def _echoing_xicclu(calls: list):
    def run(cmd, **kw):
        raw = kw.get("input") or b""
        if isinstance(raw, bytes):
            raw = raw.decode()
        lines = [ln for ln in raw.splitlines() if ln.strip()]
        calls.append({"cmd": cmd, "rows": len(lines), "first": lines[0] if lines else ""})
        out = []
        for ln in lines:
            v = [float(t) for t in ln.split()]
            # a deterministic, input-dependent answer on the 0..1 wire scale
            out.append(f"{ln} [Lab] -> Lut -> "
                       + " ".join(f"{(x % 100) / 100.0:.6f}" for x in v)
                       + " [RGB]")
        return subprocess.CompletedProcess(cmd, 0, stdout="\n".join(out) + "\n",
                                           stderr="")
    return run


def _profile(tmp_path: Path) -> Path:
    p = tmp_path / "p.icc"
    p.write_bytes(b"not really an icc, the fake never opens it")
    (tmp_path / _XICCLU).touch()
    return p


def _rows(n: int) -> list[str]:
    return [f"{i}.000000 {i + 1}.000000 {i + 2}.000000" for i in range(n)]


@pytest.fixture(autouse=True)
def _forget_the_round_trip():
    """The memo is a module global; no test may inherit another's."""
    G.clear_round_trip_cache()
    yield
    G.clear_round_trip_cache()


# ---- the split is the same question ---------------------------------------

def test_splitting_the_batch_returns_exactly_the_serial_answer(tmp_path, monkeypatch):
    """Value by value, not just row count."""
    prof = _profile(tmp_path)
    calls: list = []
    fake = _echoing_xicclu(calls)

    lines = _rows(4000)
    serial = X._run_xicclu_once(tmp_path, ["-fif", "-ia", "-pl"], prof, lines, fake)
    calls.clear()

    # `runner is subprocess.run` is what unlocks the split, so the fake has to
    # BE subprocess.run for this call.
    monkeypatch.setattr(subprocess, "run", fake)
    split = X._run_xicclu(tmp_path, ["-fif", "-ia", "-pl"], prof, lines,
                          subprocess.run)

    assert len(calls) > 1, "4000 rows were not split at all"
    assert split == serial, "the split batch disagrees with the serial one"
    assert sum(c["rows"] for c in calls) == len(lines)


def test_the_split_keeps_the_rows_in_order(tmp_path, monkeypatch):
    """A reach answer is matched to its colour by POSITION; shuffling the
    slices would pair every patch with somebody else's verdict."""
    prof = _profile(tmp_path)
    calls: list = []
    fake = _echoing_xicclu(calls)
    monkeypatch.setattr(subprocess, "run", fake)

    lines = _rows(3000)
    out = X._run_xicclu(tmp_path, ["-fif", "-ia", "-pl"], prof, lines,
                        subprocess.run)
    assert len(out) == 3000
    for i, vals in enumerate(out):
        # `_run_xicclu` hands back what xicclu printed, on the 0..1 wire scale;
        # the ×100 belongs to the callers above it.
        assert vals[0] == pytest.approx((i % 100) / 100.0, abs=1e-9), (
            f"row {i} carries another row's answer")


def test_an_injected_runner_is_never_split(tmp_path):
    """A test's fake stands in for the process. Calling it once per slice
    would change what every existing test sees."""
    prof = _profile(tmp_path)
    calls: list = []
    fake = _echoing_xicclu(calls)
    X._run_xicclu(tmp_path, ["-fif", "-ia", "-pl"], prof, _rows(9999), fake)
    assert len(calls) == 1, (
        "an injected runner was split across processes; every test that counts "
        "its fake's calls would start lying")


def test_a_small_batch_is_not_worth_a_second_process(tmp_path, monkeypatch):
    """A process costs ~0.08 s to start and a row ~0.5 ms, so slicing 60 rows
    spends more time starting than looking anything up."""
    prof = _profile(tmp_path)
    calls: list = []
    fake = _echoing_xicclu(calls)
    monkeypatch.setattr(subprocess, "run", fake)
    X._run_xicclu(tmp_path, ["-fif", "-ia", "-pl"], prof, _rows(60),
                  subprocess.run)
    assert len(calls) == 1


def test_every_slice_falls_back_to_icclu_together(tmp_path, monkeypatch):
    """ADVERSARY ROUND 2.

    `_run_xicclu` falls back to `icclu` when xicclu's reverse machinery refuses
    the profile (5+ device channels, ArgyllCMS 3.5.0). Split, EVERY slice makes
    that decision on its own, so a batch could in principle come back half
    inverted one way and half the other. It cannot: the refusal depends on the
    profile, not on the rows, so every slice takes the same branch — and this
    is what says so.
    """
    prof = _profile(tmp_path)
    (tmp_path / argyll_binary("icclu")).touch()
    seen = {"xicclu": 0, "icclu": 0}
    echo = _echoing_xicclu([])

    def run(cmd, **kw):
        # BY NAME, exactly. "xicclu".endswith("icclu") is True, and telling the
        # two apart that way quietly sent every call down the icclu branch and
        # made this test pass without the fallback ever running.
        if Path(cmd[0]).name == argyll_binary("xicclu"):
            seen["xicclu"] += 1
            return subprocess.CompletedProcess(
                cmd, 1, stdout="",
                stderr="xicclu: Error - rev_set_lchw can't handle di = 6")
        seen["icclu"] += 1
        return echo(cmd, **kw)

    monkeypatch.setattr(subprocess, "run", run)
    lines = _rows(3000)
    out = X._run_xicclu(tmp_path, ["-fif", "-ia", "-pl"], prof, lines,
                        subprocess.run)
    assert len(out) == 3000
    assert seen["icclu"] == seen["xicclu"] > 1, (
        "some slices fell back to icclu and others did not")
    for i, vals in enumerate(out):
        assert vals[0] == pytest.approx((i % 100) / 100.0, abs=1e-9)


def test_a_failing_slice_raises_once_and_waits_for_the_rest(tmp_path, monkeypatch):
    """ADVERSARY ROUND 4: a profile xicclu cannot read.

    Split, the failure happens in a worker thread, so the question is whether
    it still reaches the caller as one `XiccluError` and whether the other
    processes are waited for rather than abandoned. Measured against a real
    corrupt profile too: `GamutTargetError` in 0.23 s with no xicclu left
    running.
    """
    prof = _profile(tmp_path)
    started, finished = [], []

    def run(cmd, **kw):
        started.append(1)
        time.sleep(0.02)
        finished.append(1)
        return subprocess.CompletedProcess(
            cmd, 1, stdout="", stderr="xicclu: Error - File not readable")

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(X.XiccluError):
        X._run_xicclu(tmp_path, ["-fif", "-ia", "-pl"], prof, _rows(3000),
                      subprocess.run)
    assert started and len(finished) == len(started), (
        "the pool was abandoned with processes still going")


def test_the_worker_count_is_bounded_by_the_rows_and_the_cores():
    assert X._split_workers(0) == 1
    assert X._split_workers(X._SPLIT_MIN_ROWS_PER_PROCESS - 1) == 1
    assert X._split_workers(X._SPLIT_MIN_ROWS_PER_PROCESS * 2) == 2
    huge = X._split_workers(10_000_000)
    import os
    assert huge <= (os.cpu_count() or 1), "more processes than cores"
    assert huge >= 1


# ---- the margin is a threshold, not a question ----------------------------

def _stub_round_trip(monkeypatch, calls):
    """Count the round trips `select_gamut_targets` really makes."""
    real = G._round_trip

    def counting(labs, profile, bin_dir, letter, runner):
        calls.append({"letter": letter, "n": len(labs)})
        return real(labs, profile, bin_dir, letter, runner)
    monkeypatch.setattr(G, "_round_trip", counting)


def test_changing_only_the_margin_does_not_ask_the_profile_again(tmp_path, monkeypatch):
    """Measured before the fix: a Margin change cost a full re-query, 0.5 s on
    the fastest profile to hand and 5.6 s on the slowest."""
    prof = _profile(tmp_path)
    calls: list = []
    fake = _echoing_xicclu(calls)
    monkeypatch.setattr(subprocess, "run", fake)

    labs = [(float(i % 100), 0.0, 0.0) for i in range(300)]
    a = G._round_trip(labs, prof, tmp_path, "a", subprocess.run)
    n_after_first = len(calls)
    assert n_after_first > 0
    b = G._round_trip(labs, prof, tmp_path, "a", subprocess.run)
    assert len(calls) == n_after_first, (
        "the same profile, intent and colours were asked twice")
    assert a == b


def test_a_different_intent_is_a_different_question(tmp_path, monkeypatch):
    """The memo must not answer for an intent it was never asked about."""
    prof = _profile(tmp_path)
    calls: list = []
    fake = _echoing_xicclu(calls)
    monkeypatch.setattr(subprocess, "run", fake)

    labs = [(float(i % 100), 0.0, 0.0) for i in range(300)]
    G._round_trip(labs, prof, tmp_path, "a", subprocess.run)
    n = len(calls)
    G._round_trip(labs, prof, tmp_path, "r", subprocess.run)
    assert len(calls) > n, "a relative-intent question was answered with the "\
                           "absolute-intent answer"


def test_two_different_colour_sets_of_the_same_length_do_not_collide(
        tmp_path, monkeypatch):
    """`flags_in_gamut` is handed an ARBITRARY list by the measurement report,
    so a key that said only how many colours there were would hand one set of
    colours the answer computed for a different set of the same length."""
    prof = _profile(tmp_path)
    calls: list = []
    fake = _echoing_xicclu(calls)
    monkeypatch.setattr(subprocess, "run", fake)

    first = [(float(i % 100), 0.0, 0.0) for i in range(300)]
    second = [(float(i % 100), 1.0, 2.0) for i in range(300)]
    a = G._round_trip(first, prof, tmp_path, "a", subprocess.run)
    b = G._round_trip(second, prof, tmp_path, "a", subprocess.run)
    assert len(first) == len(second)
    assert a != b, ("two different colour sets of the same length were given "
                    "the same answer")


def test_a_rebuilt_profile_is_read_again(tmp_path, monkeypatch):
    """Build a profile again to the same path and the reach must be re-asked."""
    prof = _profile(tmp_path)
    calls: list = []
    fake = _echoing_xicclu(calls)
    monkeypatch.setattr(subprocess, "run", fake)

    labs = [(float(i % 100), 0.0, 0.0) for i in range(300)]
    G._round_trip(labs, prof, tmp_path, "a", subprocess.run)
    n = len(calls)
    import os
    prof.write_bytes(b"a different profile, written to the same name")
    st = prof.stat()
    os.utime(prof, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
    G._round_trip(labs, prof, tmp_path, "a", subprocess.run)
    assert len(calls) > n, "a rebuilt profile was answered from the old one"


def test_a_profile_copied_over_another_is_not_answered_from_the_old_one(
        tmp_path, monkeypatch):
    """ADVERSARY ROUND 1 found this one.

    `shutil.copy2` PRESERVES the modification time, and ChromIQ really does
    copy an ICC onto a run's own profile path that way: `ui/ti2_loader.py`
    imports a measurement and puts the profile lying beside it at
    `run.profile_icc`. So path + size + mtime can describe two different
    profiles, and keying the memo on those would have printed a chart built
    from the colours of a profile the user had replaced.
    """
    import os
    prof = _profile(tmp_path)
    prof.write_bytes(b"the first profile, of exactly the same length......")
    stamp = prof.stat()

    calls: list = []
    fake = _echoing_xicclu(calls)
    monkeypatch.setattr(subprocess, "run", fake)
    labs = [(float(i % 100), 0.0, 0.0) for i in range(300)]
    G._round_trip(labs, prof, tmp_path, "a", subprocess.run)
    n = len(calls)

    # What `shutil.copy2` leaves behind: the same path, the same size, and a
    # modification time carried over from the source rather than set to now.
    # Here the carried-over stamp happens to equal the one already seen, which
    # is the case a path+size+mtime key cannot tell apart.
    prof.write_bytes(b"A DIFFERENT PROFILE, of exactly the same length....")
    os.utime(prof, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert prof.stat().st_size == stamp.st_size
    assert prof.stat().st_mtime_ns == stamp.st_mtime_ns

    G._round_trip(labs, prof, tmp_path, "a", subprocess.run)
    assert len(calls) > n, (
        "a profile copied over another was answered from the old one's "
        "round trip")


def test_two_profiles_with_the_same_bytes_in_two_places_stay_apart(
        tmp_path, monkeypatch):
    """ADVERSARY ROUND 1 found this the hard way, by breaking
    `test_gamut_target.py`.

    A test may stub `backward_device`/`forward_lab` instead of injecting a
    runner, and then the runner IS the real `subprocess.run`, so the memo is
    live. Every one of those tests writes the same three-byte stand-in
    `p.icc`, so a key made of the CONTENTS alone had them all share one
    answer. The key carries the path as well.
    """
    calls: list = []
    fake = _echoing_xicclu(calls)
    monkeypatch.setattr(subprocess, "run", fake)
    (tmp_path / _XICCLU).touch()
    labs = [(float(i % 100), 0.0, 0.0) for i in range(300)]

    a = tmp_path / "a.icc"
    b = tmp_path / "b.icc"
    a.write_bytes(b"icc")
    b.write_bytes(b"icc")               # the same bytes, a different file
    G._round_trip(labs, a, tmp_path, "a", subprocess.run)
    n = len(calls)
    G._round_trip(labs, b, tmp_path, "a", subprocess.run)
    assert len(calls) > n, (
        "two profiles in two places shared one remembered answer")


def test_the_memo_is_bounded(tmp_path, monkeypatch):
    """Each entry holds two rows per master colour; they cannot pile up."""
    calls: list = []
    fake = _echoing_xicclu(calls)
    monkeypatch.setattr(subprocess, "run", fake)
    labs = [(float(i % 100), 0.0, 0.0) for i in range(300)]
    for i in range(G._ROUND_TRIP_CACHE_MAX + 4):
        p = tmp_path / f"p{i}.icc"
        p.write_bytes(b"x" * (i + 1))
        (tmp_path / _XICCLU).touch()
        G._round_trip(labs, p, tmp_path, "a", subprocess.run)
    assert len(G._ROUND_TRIP_CACHE) <= G._ROUND_TRIP_CACHE_MAX


def test_an_injected_runner_is_never_remembered(tmp_path):
    """A fake's answers are the test's business, not the next test's."""
    prof = _profile(tmp_path)
    calls: list = []
    fake = _echoing_xicclu(calls)
    labs = [(float(i % 100), 0.0, 0.0) for i in range(300)]
    G._round_trip(labs, prof, tmp_path, "a", fake)
    assert not G._ROUND_TRIP_CACHE, (
        "an injected runner's answer was remembered; it would leak into "
        "whatever ran next")
