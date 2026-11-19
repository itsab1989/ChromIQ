"""4.3.50: the helper REFUSES a strip read one patch out at an end, like a misread.

Through the real helper (``--json --replay``: the real ``read_strips`` code path
on the scripted instrument of ``chromiq_replay.c``). ``{"cmd":"swipe","slip":
"start:3"}`` hands the readings back as ArgyllCMS's patch finder does when it
takes the white run-up before the first patch as patch 1 and falls back into
step three patches later (the kept misread of 2026-11-19); ``"end"`` the white
after the last patch; no k: the whole strip.

What must hold:
* the moved strip is refused with the misread's own event (``error`` /
  ``misread``, ``button_retry``) and a ``shift`` record, BEFORE anything is
  kept: no ``strip_read``, no ``saved``;
* any key but Esc reads the same strip again, and a correct reading of it is
  then kept as always;
* a whole chart read correctly is never refused (on readings that miss the
  design like a real print does);
* ``-S`` (warnings off) switches it off with the other colour warnings;
* "use it anyway" at the wrong-strip question (a strip moved by one often
  fits another row of a randomised chart better) only says which strip it
  is: the shift test still runs on it.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, ReplaySession, parse_ti2_rows  # noqa: E402

from workflow import strip_shift as S  # noqa: E402

ARGYLL = Path("/Applications/Argyll/bin")
PAPER = (93.3, 96.6, 79.9)        # chromiq_replay.c's cq_paper


def _printed(xyz):
    """A plausible print of a design colour (test_210's model): chroma pulled
    a quarter of the way to grey, white and black compressed."""
    x, y, z = xyz
    return (0.82 * (0.75 * x + 0.25 * y * 0.9642) + 1.0,
            0.82 * y + 1.5,
            0.82 * (0.75 * z + 0.25 * y * 0.8249) + 1.0)


def _chart(tmp: Path) -> Path:
    targen = shutil.which("targen") or str(ARGYLL / "targen")
    if not Path(targen).exists() or not Path(HELPER).exists():
        pytest.skip("Argyll targen or the ChromIQ engine helper is unavailable")
    tmp.mkdir(parents=True, exist_ok=True)
    base = tmp / "SH"
    subprocess.run([targen, "-v0", "-d2", "-G", "-f120", str(base)],
                   check=True, capture_output=True, cwd=tmp, timeout=120)
    from workflow.layout_engine.chart import build_chart
    build_chart(base.with_suffix(".ti1"), base, instrument="i1", paper="A4",
                randomize=True, seed=4350, layout_mode="patch_first")
    steps, rows = parse_ti2_rows(base.with_suffix(".ti2"))
    with (tmp / "replay.txt").open("w", encoding="utf-8") as fp:
        fp.write(f"PATCHES {steps}\n")
        for letter in sorted(rows):
            fp.write(f"STRIP {letter}\n")
            for v in rows[letter]:
                fp.write("%.4f %.4f %.4f\n" % _printed(v))
    return base


def _paper_expected(rows):
    return max((v for r in rows.values() for v in r), key=lambda v: v[1])


def _moved(read, k, end):
    r = list(read) if end == 0 else list(read)[::-1]
    k = min(k, len(r))
    out = [PAPER] + r[:k - 1] + r[k:]
    return out if end == 0 else out[::-1]


def _worst_patch(read, exp):
    """The helper's colour check (chromiq_chartread.c, werror): the worst
    patch's CIE76 of the Y-normalised reading."""
    yn = sum(e[1] for e in exp) / sum(r[1] for r in read)
    return max(S._de(S._lab(r, yn), S._lab(e)) for r, e in zip(read, exp))


def _a_strip_the_test_sees(base, k, end):
    """The first strip whose moved reading the colour check KEEPS (worst patch
    under 95, the case this test exists for) and the twin flags (the helper
    must then refuse it), and whose correct reading it does not."""
    _steps, rows = parse_ti2_rows(base.with_suffix(".ti2"))
    paper = _paper_expected(rows)
    for letter in sorted(rows):
        exp = rows[letter]
        read = [_printed(v) for v in exp]
        if S.shift_test(read, exp, paper).flagged:
            continue
        moved = _moved(read, k, end)
        if _worst_patch(moved, exp) < 95.0 and S.shift_test(moved, exp, paper).flagged:
            return letter
    pytest.fail("no strip of the chart shows the shift: the chart changed")


def _session(base, extra=None):
    s = ReplaySession(base, base.parent / "replay.txt", extra_args=extra or [])
    s.wait_event("session_start")
    return s


def _goto(s, letter):
    idx = s.event_index()
    s.send(cmd="goto", strip=letter)
    s.wait_event("strip_ready", strip=letter, after=idx, timeout=10)


def _swipe(s, timeout=10, **kw):
    """Swipe and return the events up to the strip's verdict."""
    idx = s.event_index()
    s.send(cmd="swipe", **kw)
    deadline = time.time() + timeout
    answered = 0
    while time.time() < deadline:
        evs = s.events[idx:]
        for e in evs:
            if e.get("event") in ("strip_read", "error"):
                return evs
        asked = [e for e in evs if e.get("event") == "strip_warning"]
        if len(asked) > answered:
            # the wrong-strip question (a moved strip may fit another row
            # better) or the colour check: "use it anyway", as a person
            # sure of the strip would
            answered = len(asked)
            s.send(cmd="ok")
        time.sleep(0.02)
    raise AssertionError(f"no verdict for the swipe: {s.raw_lines[-12:]}")


def _end(s):
    idx = s.event_index()
    s.send(cmd="done")
    deadline = time.time() + 8
    while time.time() < deadline:
        evs = s.events[idx:]
        if any(e.get("event") == "done" for e in evs):
            break
        if any(e.get("event") == "unread_confirm" for e in evs):
            s.send(cmd="yes")
            idx = s.event_index()
        time.sleep(0.05)
    return s.finish()


@pytest.mark.parametrize("slip,k,end", [("start:3", 3, 0), ("start:6", 6, 0), ("end:3", 3, 1),
                                        ("end:2", 2, 1), ("start:1", 1, 0), ("end:1", 1, 1)])
def test_a_moved_strip_is_refused_then_read_again(tmp_path, slip, k, end):
    base = _chart(tmp_path)
    letter = _a_strip_the_test_sees(base, k, end)
    s = _session(base)
    try:
        s.wait_event("strip_ready")
        _goto(s, letter)
        evs = _swipe(s, slip=slip)
        err = [e for e in evs if e.get("event") == "error"]
        assert err and err[0]["kind"] == "misread", evs
        assert "moved by one patch at the " + ("start" if end == 0 else "end") in err[0]["detail"]
        assert err[0]["shift"]["at"] == ("start" if end == 0 else "end")
        assert err[0]["shift"]["score"] >= err[0]["shift"]["limit"]
        assert "button_retry" in err[0]
        time.sleep(0.3)
        assert not [e for e in s.events if e.get("event") in ("strip_read", "saved")]
        # any key but Esc: the same strip again, read correctly this time
        s.send(cmd="retry")
        s.wait_event("strip_ready", strip=letter, after=s.event_index() - 3, timeout=10)
        evs = _swipe(s)
        ok = [e for e in evs if e.get("event") == "strip_read"]
        assert ok and ok[0]["strip"] == letter, evs
        s.wait_event("saved", timeout=10)
    finally:
        _end(s)


def test_a_chart_read_correctly_is_never_refused(tmp_path):
    base = _chart(tmp_path)
    _steps, rows = parse_ti2_rows(base.with_suffix(".ti2"))
    s = _session(base)
    try:
        s.wait_event("strip_ready")
        for _ in rows:
            idx = s.event_index()
            evs = _swipe(s)
            assert not [e for e in evs if e.get("event") == "error"], evs
            s.wait_event("saved", after=idx, timeout=10)
    finally:
        _end(s)


def test_warnings_off_does_not_switch_it_off(tmp_path):
    """ChromIQ starts the helper with -S by default (its own misread tests
    replace the colour check): a strip moved by one is a wrong reading, not a
    warning to suppress."""
    base = _chart(tmp_path)
    letter = _a_strip_the_test_sees(base, 3, 0)
    s = _session(base, ["-S"])
    try:
        s.wait_event("strip_ready")
        _goto(s, letter)
        evs = _swipe(s, slip="start:3")
        assert [e for e in evs if e.get("event") == "error"], evs
        assert not [e for e in evs if e.get("event") == "strip_read"]
        s.send(cmd="retry")
        s.wait_event("strip_ready", strip=letter, after=s.event_index() - 3, timeout=10)
        evs = _swipe(s)
        assert [e for e in evs if e.get("event") == "strip_read"], evs
    finally:
        _end(s)


def test_a_strip_swiped_in_place_of_another_is_not_refused_as_moved(tmp_path):
    """With -S, every strip of the chart read in the place of strip A: none
    is refused by the shift test (a wrong strip is not a shift)."""
    base = _chart(tmp_path)
    _steps, rows = parse_ti2_rows(base.with_suffix(".ti2"))
    letters = sorted(rows)
    s = _session(base, ["-S"])
    try:
        s.wait_event("strip_ready")
        for other in letters[1:]:
            _goto(s, letters[0])
            evs = _swipe(s, **{"as": other})
            assert not [e for e in evs if e.get("event") == "error"], (other, evs)
    finally:
        _end(s)


def test_esc_at_the_refusal_ends_the_measurement_and_keeps_what_was_read(tmp_path):
    base = _chart(tmp_path)
    letter = _a_strip_the_test_sees(base, 3, 0)
    s = _session(base)
    s.wait_event("strip_ready")
    _goto(s, letter)
    evs = _swipe(s, slip="start:3")
    assert [e for e in evs if e.get("event") == "error"]
    s.send(cmd="quit")
    s.wait_event("aborted", timeout=10)
    s.finish()
