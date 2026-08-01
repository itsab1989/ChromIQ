"""End-to-end tests for the ChromIQ chart-reading engine (#126).

Every test drives the REAL chromiq-chartread binary through its replay
instrument — the full read_strips decision logic runs, only the USB edge is
scripted. Skipped wholesale when the helper isn't built or Argyll's chart
tools are missing.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, ReplaySession, parse_ti2_rows, write_replay_script  # noqa: E402

ARGYLL = Path("/Applications/Argyll/bin")

pytestmark = pytest.mark.skipif(
    not HELPER.exists(), reason="chromiq-chartread helper not built")


def _make_chart(tmp: Path, name: str = "chart", *, randomised: bool,
                targen_args: list[str] | None = None) -> Path:
    """targen + printtarg a small 2-strip chart; returns the base path."""
    targen = shutil.which("targen") or str(ARGYLL / "targen")
    printtarg = shutil.which("printtarg") or str(ARGYLL / "printtarg")
    if not Path(targen).exists() or not Path(printtarg).exists():
        pytest.skip("Argyll targen/printtarg not available")
    tmp.mkdir(parents=True, exist_ok=True)
    base = tmp / name
    ta = targen_args or ["-d2", "-G", "-e4", "-B4", "-f42"]
    subprocess.run([targen, "-v0", *ta, str(base)], check=True,
                   capture_output=True, cwd=tmp)
    pa = [printtarg, "-v0", "-ii1", "-pA4"]
    if not randomised:
        pa.append("-r")
    subprocess.run([*pa, str(base)], check=True, capture_output=True, cwd=tmp)
    return base


@pytest.fixture()
def fixed_chart(tmp_path: Path) -> tuple[Path, Path]:
    base = _make_chart(tmp_path, randomised=False)
    replay = tmp_path / "replay.txt"
    write_replay_script(base.with_suffix(".ti2"), replay, noise=0.3)
    return base, replay


def _quit(s: ReplaySession) -> None:
    """Quit from the armed strip menu: Esc aborts the read, a second Esc
    answers the give-up prompt (identical to the console key sequence)."""
    idx = s.event_index()
    s.send(cmd="quit")
    try:
        s.wait_event("strip_interrupted", timeout=3, after=idx)
        s.send(cmd="quit")
    except TimeoutError:
        pass                       # already at a prompt — one quit sufficed
    s.finish()


def _read_all_and_finish(s: ReplaySession, n_strips: int) -> None:
    for _ in range(n_strips):
        idx = s.event_index()
        s.send(cmd="swipe")
        s.wait_event("strip_read", after=idx)
        s.wait_event("saved", after=idx)
    s.send(cmd="done")
    s.wait_event("done", timeout=5)


def test_happy_path_full_session(fixed_chart):
    base, replay = fixed_chart
    s = ReplaySession(base, replay)
    ev = s.wait_event("session_start")
    assert [x["strip"] for x in ev["strips"]] == ["A", "B"]
    assert ev["randomised"] is False
    s.wait_event("strip_ready")
    _read_all_and_finish(s, 2)
    assert s.finish() == 0
    ti3 = base.with_suffix(".ti3")
    assert ti3.exists()
    text = ti3.read_text()
    assert text.startswith("CTI3")
    assert 'TARGET_INSTRUMENT "GretagMacbeth i1 Pro"' in text
    assert text.count("\n") > 42          # header + 42 patch rows


def test_strip_read_carries_per_patch_de(fixed_chart):
    base, replay = fixed_chart
    s = ReplaySession(base, replay)
    s.wait_event("strip_ready")
    s.send(cmd="swipe")
    ev = s.wait_event("strip_read")
    assert len(ev["patches"]) == 21
    for p in ev["patches"]:
        assert set(p) >= {"id", "loc", "xyz", "exyz", "de"}
        assert p["de"] < 5.0              # replay noise is tiny
    assert ev["verifiable"] is True
    _quit(s)


def test_coms_failure_saves_before_prompt_and_resume_completes(fixed_chart):
    base, replay = fixed_chart
    ti3 = base.with_suffix(".ti3")
    s = ReplaySession(base, replay)
    s.wait_event("strip_ready")
    s.send(cmd="swipe")
    s.wait_event("saved")
    assert ti3.exists()                   # autosaved after strip A
    idx = s.event_index()
    s.send(cmd="swipe", fault="coms")
    s.wait_event("error", after=idx)
    s.send(cmd="quit")
    s.finish()
    assert ti3.exists(), "readings must survive a dead instrument"

    # Resume: A is on disk, only B left.
    s2 = ReplaySession(base, replay, extra_args=["-r"])
    ev = s2.wait_event("session_start")
    assert [(x["strip"], x["read"]) for x in ev["strips"]] == [
        ("A", True), ("B", False)]
    s2.wait_event("strip_ready")
    idx = s2.event_index()
    s2.send(cmd="swipe")
    s2.wait_event("strip_read", after=idx)
    s2.send(cmd="done")
    s2.wait_event("done", timeout=5)
    assert s2.finish() == 0


def test_goto_jumps_and_allows_remeasure(fixed_chart):
    base, replay = fixed_chart
    s = ReplaySession(base, replay)
    s.wait_event("strip_ready")
    idx = s.event_index()
    s.send(cmd="goto", strip="B")
    # Wait for the strip_ready that names B, not merely the next one: the
    # helper can still be settling the strip it was on, and taking the first
    # event made this pass or fail on timing (2026-08-01, full-suite run).
    ev = s.wait_event("strip_ready", after=idx, strip="B")
    assert ev["strip"] == "B"
    s.send(cmd="swipe")
    assert s.wait_event("strip_read", after=idx, strip="B")["strip"] == "B"
    # jump back to a read strip and measure it again
    idx = s.event_index()
    s.send(cmd="goto", strip="B")
    ev = s.wait_event("strip_ready", after=idx, strip="B")
    assert ev["strip"] == "B" and ev["read"] is True
    _quit(s)


def test_wrong_swipe_on_fixed_order_chart_warns(fixed_chart):
    """F7-R: stock chartread silently accepts this — the engine must warn."""
    base, replay = fixed_chart
    s = ReplaySession(base, replay)
    s.wait_event("strip_ready")
    s.send(cmd="swipe", **{"as": "B"})
    w = s.wait_event("strip_warning")
    assert w["kind"] == "wrong_strip"
    assert (w["read"], w["expected"]) == ("B", "A")
    # retry, then swipe correctly — accepted without warning
    idx = s.event_index()
    s.send(cmd="retry")
    s.wait_event("strip_ready", after=idx)
    s.send(cmd="swipe")
    assert s.wait_event("strip_read", after=idx)["strip"] == "A"
    _quit(s)


def test_reversed_swipe_on_fixed_order_chart_recognised(fixed_chart):
    base, replay = fixed_chart
    s = ReplaySession(base, replay)
    s.wait_event("strip_ready")
    s.send(cmd="swipe", reversed=True)
    ev = s.wait_event("strip_read")
    assert ev["reversed"] is True         # values booked in correct order
    assert ev["worst_de"] < 5.0
    _quit(s)


def test_randomised_chart_correct_swipes_raise_no_warnings(tmp_path):
    """T7 acceptance gate: zero new warnings on randomised charts."""
    base = _make_chart(tmp_path, randomised=True)
    replay = tmp_path / "replay.txt"
    write_replay_script(base.with_suffix(".ti2"), replay, noise=0.3)
    s = ReplaySession(base, replay)
    ev = s.wait_event("session_start")
    assert ev["randomised"] is True
    s.wait_event("strip_ready")
    _read_all_and_finish(s, 2)
    assert s.finish() == 0
    assert not [e for e in s.events if e.get("event") == "strip_warning"]


def test_identical_rows_marked_not_verifiable(tmp_path):
    """When two rows carry (near-)identical expected colours — the worst
    case of an unshuffled chart — the engine must be honest that it cannot
    verify row identity, instead of raising false alarms."""
    base = _make_chart(tmp_path, randomised=False)
    ti2 = base.with_suffix(".ti2")
    # Rewrite row B's expected XYZ to equal row A's, patch for patch —
    # locating the XYZ columns by their DATA_FORMAT field names.
    steps, rows = parse_ti2_rows(ti2)
    text = ti2.read_text(encoding="latin-1")
    lines = text.splitlines(keepends=True)
    fields: list[str] = []
    in_fmt = False
    for ln in lines:
        st = ln.strip()
        if st == "BEGIN_DATA_FORMAT":
            in_fmt = True
        elif st == "END_DATA_FORMAT":
            in_fmt = False
        elif in_fmt:
            fields += st.split()
    ix = fields.index("XYZ_X")
    loc_ix = fields.index("SAMPLE_LOC")
    out, bi = [], 0
    for ln in lines:
        parts = ln.split()
        if len(parts) == len(fields) and parts[loc_ix].startswith('"B'):
            ax, ay, az = rows["A"][bi]
            parts[ix], parts[ix + 1], parts[ix + 2] = (
                f"{ax:.5f}", f"{ay:.5f}", f"{az:.5f}")
            bi += 1
            out.append(" ".join(parts) + " \n")
        else:
            out.append(ln)
    ti2.write_text("".join(out), encoding="latin-1")
    replay = tmp_path / "replay.txt"
    write_replay_script(ti2, replay)
    s = ReplaySession(base, replay)
    ev = s.wait_event("session_start")
    assert all(x["verifiable"] is False for x in ev["strips"]), \
        "identical rows must not claim auto-ID confidence"
    # and a swipe is accepted silently — stock behaviour, no false alarm
    s.wait_event("strip_ready")
    s.send(cmd="swipe")
    sr = s.wait_event("strip_read")
    assert sr["verifiable"] is False
    assert not [e for e in s.events if e.get("event") == "strip_warning"]
    _quit(s)


def test_final_ti3_identical_single_shot_vs_autosave_path(tmp_path):
    """The autosave/rename dance must leave a final file byte-identical to
    a plain uninterrupted session with the same readings."""
    base1 = _make_chart(tmp_path / "a", randomised=False)
    replay1 = tmp_path / "a" / "replay.txt"
    write_replay_script(base1.with_suffix(".ti2"), replay1, noise=0.25)
    s = ReplaySession(base1, replay1)
    s.wait_event("strip_ready")
    _read_all_and_finish(s, 2)
    s.finish()

    base2 = _make_chart(tmp_path / "b", randomised=False)
    replay2 = tmp_path / "b" / "replay.txt"
    write_replay_script(base2.with_suffix(".ti2"), replay2, noise=0.25)
    s2 = ReplaySession(base2, replay2)
    s2.wait_event("strip_ready")
    # strip A, then a coms fault + retry mid-session, then strip B
    idx = s2.event_index()
    s2.send(cmd="swipe")
    s2.wait_event("saved", after=idx)
    idx = s2.event_index()
    s2.send(cmd="swipe", fault="coms")
    s2.wait_event("error", after=idx)
    s2.send(cmd="retry")
    s2.wait_event("strip_ready", after=idx)
    s2.send(cmd="swipe")
    s2.wait_event("strip_read", after=idx)
    s2.send(cmd="done")
    s2.wait_event("done", timeout=5)
    s2.finish()

    t1 = base1.with_suffix(".ti3").read_text().splitlines()
    t2 = base2.with_suffix(".ti3").read_text().splitlines()
    # CREATED timestamps legitimately differ; every other byte must match.
    strip = lambda ls: [l for l in ls if not l.startswith('CREATED')]
    assert strip(t1) == strip(t2)


def test_passthrough_usage_is_stock_chartread():
    """No flags → stock chartread, verified by the usage text."""
    out = subprocess.run([str(HELPER)], capture_output=True, text=True)
    assert "usage: chartread [-options] outfile" in out.stderr + out.stdout
    assert "--json" not in out.stderr + out.stdout   # extensions stay hidden
