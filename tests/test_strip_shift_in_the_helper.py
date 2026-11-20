"""4.3.50: a strip read one patch out at an end, through the REAL helper.

The helper is 4.3.49's (the first 4.3.50 build refused such a strip in
read_strips; the review sent the finding to the "Strip may be misaligned"
question instead, tests/test_strip_shift_in_the_app.py). Through the real
``read_strips`` code path on the scripted instrument (``--json --replay``),
with the moved readings written into the replay script itself (a script strip
swiped with ``"as"``), so nothing in the helper had to learn to move them:

* a moved strip is KEPT by the helper (a strip_read, no misread), and its
  event's patches are what the app's question is asked from: the shift finder
  finds it there, with the chart's own rows and paper;
* read again (Re-measure = goto + a new swipe) the new reading replaces it in
  the .ti3, and a correct reading asks nothing;
* read from its far end, the helper files it turned round, so a run-up taken
  at the start of the MOVEMENT shows at the strip's filed END and is found
  there;
* the i1Pro 2 dual scan: a moved strip read again leaves no UV pass pending
  and pairs nothing old with anything new: the main file and M1 / M2 hold the
  second reading's pair, patch by patch, and the next strip reads as always.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("PyQt6")
sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, ReplaySession, parse_ti2_rows  # noqa: E402

from workflow import slipped_strip as SS  # noqa: E402

ARGYLL = Path("/Applications/Argyll/bin")
PAPER_READ = (88.6, 91.8, 76.0)       # a paper as an instrument reads it


def _printed(xyz):
    """A plausible print of a design colour (test_210's model)."""
    x, y, z = xyz
    return (0.82 * (0.75 * x + 0.25 * y * 0.9642) + 1.0,
            0.82 * y + 1.5,
            0.82 * (0.75 * z + 0.25 * y * 0.8249) + 1.0)


def _moved(read, k, at_end):
    r = list(read) if not at_end else list(read)[::-1]
    out = [PAPER_READ] + r[:k - 1] + r[k:]
    return out if not at_end else out[::-1]


def _chart(tmp: Path):
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
    return base


def _script(base: Path, extra: dict) -> Path:
    steps, rows = parse_ti2_rows(base.with_suffix(".ti2"))
    rp = base.parent / "replay.txt"
    with rp.open("w", encoding="utf-8") as fp:
        fp.write(f"PATCHES {steps}\n")
        for letter in sorted(rows):
            fp.write(f"STRIP {letter}\n")
            for v in rows[letter]:
                fp.write("%.4f %.4f %.4f\n" % _printed(v))
        for label, vals in extra.items():
            fp.write(f"STRIP {label}\n")
            for v in vals:
                fp.write("%.4f %.4f %.4f\n" % tuple(v))
    return rp


def _ask(base: Path, ev: dict):
    """What the app's check makes of a strip_read event: the shift finder
    with the chart's other rows and paper, as MeasureManager hands them."""
    _steps, rows = parse_ti2_rows(base.with_suffix(".ti2"))
    strip = ev["strip"]
    paper = max((v for r in rows.values() for v in r), key=lambda v: v[1])
    old = SS.slipped_run_in_strip_read(ev["patches"])
    if old is not None:
        return old
    return SS.shift_in_strip_read(ev["patches"], paper,
                                  [r for s, r in rows.items() if s != strip])


def _a_strip_it_finds(base: Path, k: int, at_end: bool):
    _steps, rows = parse_ti2_rows(base.with_suffix(".ti2"))
    paper = max((v for r in rows.values() for v in r), key=lambda v: v[1])
    for letter in sorted(rows):
        exp = rows[letter]
        read = [_printed(v) for v in exp]
        others = [r for s, r in rows.items() if s != letter]
        if SS.shift_at_an_end(read, exp, paper, -1.0) is not None:
            continue
        mv = _moved(read, k, at_end)
        from workflow.strip_shift import other_rows_best
        if SS.shift_at_an_end(mv, exp, paper, other_rows_best(mv, others)) is not None:
            return letter, mv
    pytest.fail("no strip of the chart shows the shift: the chart changed")


def _session(base, rp, extra=None):
    s = ReplaySession(base, rp, extra_args=["-S"] + (extra or []))
    s.wait_event("session_start")
    return s


def _goto(s, letter):
    idx = s.event_index()
    s.send(cmd="goto", strip=letter)
    s.wait_event("strip_ready", strip=letter, after=idx, timeout=10)


def _swipe(s, timeout=10, **kw):
    """Swipe and return the strip's verdict: its strip_read or error."""
    idx = s.event_index()
    s.send(cmd="swipe", **kw)
    deadline = time.time() + timeout
    answered = 0
    while time.time() < deadline:
        evs = s.events[idx:]
        for e in evs:
            if e.get("event") in ("strip_read", "error"):
                return e
        asked = [e for e in evs if e.get("event") == "strip_warning"]
        if len(asked) > answered:
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


def _ti3_rows(base: Path):
    t = base.with_suffix(".ti3").read_text(encoding="latin-1")
    f = t.split("BEGIN_DATA_FORMAT")[1].split("END_DATA_FORMAT")[0].split()
    body = t.split("\nBEGIN_DATA\n")[1].split("\nEND_DATA")[0].splitlines()
    li, xi = f.index("SAMPLE_LOC"), f.index("XYZ_X")
    return {r.split()[li].strip('"'): tuple(float(v) for v in r.split()[xi:xi + 3])
            for r in body if r.strip()}


@pytest.mark.parametrize("k,at_end", [(3, False), (2, False), (3, True), (1, False)])
def test_a_moved_strip_is_kept_asked_about_and_read_again(tmp_path, k, at_end):
    """The helper keeps it (no misread, no refusal), the question is asked
    from its strip_read, Re-measure reads it again and the correct reading
    replaces it and asks nothing."""
    base = _chart(tmp_path)
    letter, mv = _a_strip_it_finds(base, k, at_end)
    rp = _script(base, {"ZS": mv})
    s = _session(base, rp)
    _goto(s, letter)
    ev = _swipe(s, **{"as": "ZS"})
    assert ev["event"] == "strip_read", ev            # kept, not refused
    found = _ask(base, ev)
    assert found is not None
    assert found.offset == (-1 if at_end else 1)
    _goto(s, letter)                                   # "Re-measure this strip"
    ev2 = _swipe(s)
    assert ev2["event"] == "strip_read" and _ask(base, ev2) is None
    _end(s)
    _steps, rows = parse_ti2_rows(base.with_suffix(".ti2"))
    got = _ti3_rows(base)
    for i, v in enumerate(rows[letter]):
        assert np.allclose(got[f"{letter}{i + 1}"], _printed(v), atol=0.01)


def test_kept_as_it_is_when_the_person_keeps_it(tmp_path):
    base = _chart(tmp_path)
    letter, mv = _a_strip_it_finds(base, 3, False)
    s = _session(base, _script(base, {"ZS": mv}))
    _goto(s, letter)
    assert _swipe(s, **{"as": "ZS"})["event"] == "strip_read"
    _end(s)
    got = _ti3_rows(base)
    for i, v in enumerate(mv):
        assert np.allclose(got[f"{letter}{i + 1}"], v, atol=0.01)


def test_read_from_its_far_end_it_is_found_at_the_filed_end(tmp_path):
    """The mirror (review S2 d): the run-up taken at the start of a movement
    from the strip's far end lands at its last patches as filed; the helper
    turns the strip round, and the question finds it at that end."""
    base = _chart(tmp_path)
    letter, mv = _a_strip_it_finds(base, 3, True)       # moved at the filed end
    s = _session(base, _script(base, {"ZS": mv}))
    _goto(s, letter)
    ev = _swipe(s, **{"as": "ZS", "reversed": True})    # read from the far end
    assert ev["event"] == "strip_read" and ev["reversed"] is True
    found = _ask(base, ev)
    assert found is not None and found.offset == -1 and found.last == len(mv) - 1
    _end(s)


def test_a_chart_read_correctly_asks_nothing(tmp_path):
    base = _chart(tmp_path)
    _steps, rows = parse_ti2_rows(base.with_suffix(".ti2"))
    s = _session(base, _script(base, {}))
    for letter in sorted(rows):
        _goto(s, letter)
        ev = _swipe(s)
        assert ev["event"] == "strip_read"
        assert _ask(base, ev) is None, letter
    _end(s)


# ---- the i1Pro 2 dual scan --------------------------------------------------------

def _spectra_for(xyzs):
    """Smooth reflectances 380..730 nm whose D50 / 2 degree XYZ is close to
    each of *xyzs* (three broad bands, clipped), for an invented print."""
    from workflow.dual_scan import colour as C
    W, M = C._weights()
    A = W @ M                                           # 3 x 36
    wl = C.WL10
    B = np.stack([np.exp(-0.5 * ((wl - c) / 45.0) ** 2) for c in (450, 545, 615)], axis=1)
    out = []
    for x in xyzs:
        c = np.linalg.solve(A @ B, np.asarray(x, float))
        out.append(np.clip(B @ c, 0.01, 0.97))
    return np.array(out)


def _dual_chart(tmp: Path):
    sys.path.insert(0, str(Path(__file__).parent))
    from test_i1pro2_dual_scan_engine import _invented, _vec, S
    from workflow.dual_scan import model
    base = _chart(tmp)
    steps, rows = parse_ti2_rows(base.with_suffix(".ti2"))
    tab, cal = _invented()
    paper = max((v for r in rows.values() for v in r), key=lambda v: v[1])
    truth, spec = {}, {}
    for letter in sorted(rows):
        m2 = _spectra_for([_printed(v) for v in rows[letter]])
        g = np.zeros_like(m2)
        L, U, M1 = model.forward(m2, g, cal, tab, S)
        truth[letter], spec[letter] = (L, M1, m2), (L, U)
    return base, rows, paper, tab, cal, truth, spec, steps, _vec


def _write_dual(base, steps, cal, tab, spec, extra, vec):
    rp = base.parent / "replay.txt"
    with rp.open("w", encoding="utf-8") as fp:
        fp.write(f"PATCHES {steps}\nDUALCAL\n")
        fp.write(f"W {vec(cal.white)}\nT {vec(cal.uv_tile)}\nE {vec(cal.emis)}\n"
                 f"KA {vec(tab.kA[:18])}\nKD {vec(tab.kD[:18])}\nCLOCKS 139 139\n")
        for letter, (L, U) in list(spec.items()) + list(extra.items()):
            fp.write(f"STRIP {letter}\n")
            for i in range(len(L)):
                fp.write(f"LAMP {vec(L[i])}\nUV {vec(U[i])}\n")
    return rp


def test_the_dual_scan_read_again_pairs_only_the_new_reading(tmp_path, monkeypatch):
    """The review could check this only by reading the code. A moved dual
    strip is kept, asked about from its lamp pass, then read again: the main
    file and M1 / M2 hold the SECOND reading's pair for every patch (nothing
    of the first pass 2 paired with the new pass 1, no UV pass left pending),
    and the next strip is read as always."""
    if not HELPER.exists():
        pytest.skip("chromiq-chartread helper not built")
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    sys.path.insert(0, str(Path(__file__).parent))
    from test_i1pro2_dual_scan_engine import _check, _dual_args
    base, rows, paper, tab, cal, truth, spec, steps, vec = _dual_chart(tmp_path)
    letters = sorted(rows)
    # the first strip, its lamp and UV passes moved: the white paper (no
    # brightener) read as patch 1, patches 1 and 2 one place on, 3 lost
    from workflow.dual_scan import model
    from test_i1pro2_dual_scan_engine import S
    letter = letters[0]
    L, U = spec[letter]
    pL = np.full(36, 0.9)
    pU = model.forward(pL[None, :], np.zeros((1, 36)), cal, tab, S)[1][0]
    mL = np.vstack([pL, L[:2], L[3:]])
    mU = np.vstack([pU, U[:2], U[3:]])
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    rp = _write_dual(base, steps, cal, tab, spec, {"ZD": (mL, mU)}, vec)
    with ReplaySession(base, rp, extra_args=_dual_args(cdir)) as s:
        s.wait_event("session_start")
        _goto(s, letter)
        ev = _swipe(s, **{"as": "ZD"})
        assert ev["event"] == "strip_read", ev        # kept, never refused
        assert _ask(base, ev) is not None              # asked from the lamp pass
        first = [p["xyz"] for p in ev["patches"]]
        _goto(s, letter)                               # Re-measure this strip
        ev2 = _swipe(s)
        assert ev2["event"] == "strip_read"
        assert not np.allclose(first[0], ev2["patches"][0]["xyz"], atol=0.5)
        for other in letters:
            if other != letter:
                _goto(s, other)
                assert _swipe(s)["event"] == "strip_read"
        _end(s)
    _check(base, cdir, truth)
