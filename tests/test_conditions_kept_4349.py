"""4.3.49 (Basti, 2026-11-19): THE OTHER CONDITIONS OF STRIPS ALREADY READ ARE
NEVER THROWN AWAY.

    "i think we should do this because it also touches the way we use check
    and refine. if the tab tells and guides users to remeasure certain strips
    then it would be an annoyance if this then makes them loose the other
    condition files."  ...  "the dual scan agent shall fix any faults it finds
    for the i1pro 3 as well".

Before: ONE strip read without its other conditions (an i1Pro 2 dual strip
without its UV pass, an i1Pro 3 reading the driver gave without them) ended
them for the sitting, no pair matched the main file any more, and the
session-end housekeeping deleted the last one: every strip lost M1 and M2,
and a Continue Measurement could not bring them back (``why: "resume"``).
Reproduced on the 4.3.48 helper and on this branch before the change
(work folder 2026-11-19_dual_continue, paths.txt, S3/S5/S6/P2/P3).

Now (``chromiq_chartread.c`` cq_cond_keep): the record is kept, a patch read
without them is M0 only (its old M1 / M2 cleared, never left beside a new
M0), the files are the complete pair while every read patch has all three
and ``<hash>-Mx.partial.ti3`` while some have not, a Continue takes either
back, and the Measure tab takes the reader to the strips with M0 only.

Every engine test runs the REAL helper through its replay instrument.
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, ReplaySession, parse_ti2_rows  # noqa: E402

from workflow import i1pro3_conditions as ic  # noqa: E402
from workflow.dual_scan import model, storage  # noqa: E402

needs_helper = pytest.mark.skipif(not HELPER.exists(),
                                  reason="chromiq-chartread helper not built")
ROOT = Path(__file__).resolve().parent.parent
C_SRC = ROOT / "native" / "chartread_helper" / "chromiq_chartread.c"


# ------------------------------------------------------------------ charts

def _chart4(tmp: Path):
    from test_chartread_engine import _make_chart
    return _make_chart(tmp, randomised=False,
                       targen_args=["-d2", "-G", "-e4", "-B4", "-f84"])


def _dual_chart(tmp: Path, *, dualcal=True):
    """4 strips (A-D), each also as "<X>~M0": the same strip read again
    without its UV half (and 0.2 % different, as a real re-read is)."""
    import test_i1pro2_dual_scan_engine as E
    base = _chart4(tmp)
    steps, rows = parse_ti2_rows(base.with_suffix(".ti2"))
    tab, cal = E._invented()
    rp = tmp / ("replay.txt" if dualcal else "replay-nodual.txt")
    with rp.open("w", encoding="utf-8") as fp:
        fp.write(f"PATCHES {steps}\n")
        if dualcal:
            fp.write("DUALCAL\n")
            fp.write(f"W {E._vec(cal.white)}\nT {E._vec(cal.uv_tile)}\n")
            fp.write(f"E {E._vec(cal.emis)}\nKA {E._vec(tab.kA[:18])}\n"
                     f"KD {E._vec(tab.kD[:18])}\nCLOCKS 139 139\n")
        for k, letter in enumerate(sorted(rows)):
            m2, g = E._paper([y for (_x, y, _z) in rows[letter]], k + 1)
            L, U, _M1 = model.forward(m2, g, cal, tab, E.S)
            if dualcal:
                fp.write(f"STRIP {letter}\n")
                for i in range(len(rows[letter])):
                    fp.write(f"LAMP {E._vec(L[i])}\nUV {E._vec(U[i])}\n")
                fp.write(f"STRIP {letter}~M0\n")
                for i in range(len(rows[letter])):
                    fp.write(f"LAMP {E._vec(L[i] * 1.002)}\n")
            else:                       # a sitting that cannot read the UV pass
                fp.write(f"STRIP {letter}\n")
                for (x, y, z) in rows[letter]:
                    fp.write(f"{x * 1.003:.4f} {y:.4f} {z:.4f}\n")
    return base, rp


def _i1pro3_chart(tmp: Path):
    from test_i1pro3_conditions_engine import K
    base = _chart4(tmp)
    steps, rows = parse_ti2_rows(base.with_suffix(".ti2"))
    rp = tmp / "replay3.txt"
    with rp.open("w", encoding="utf-8") as fp:
        fp.write(f"PATCHES {steps}\n")
        for letter in sorted(rows):
            for suffix, conds in (("", ("M1", "M2")), ("~M0", ())):
                fp.write(f"STRIP {letter}{suffix}\n")
                f = 1.002 if suffix else 1.0
                for i, (x, y, z) in enumerate(rows[letter]):
                    fp.write(f"{x * f:.4f} {y + 0.001 * i:.4f} {z:.4f}\n")
                for c in conds:
                    fp.write(f"COND {c}\n")
                    for i, (x, y, z) in enumerate(rows[letter]):
                        fp.write(f"{x * K[c]:.4f} {(y + 0.001 * i) * K[c]:.4f} "
                                 f"{z:.4f}\n")
    return base, rp


# ------------------------------------------------------------------ driving

def _dual_args(cdir, resume=False):
    import test_i1pro2_dual_scan_engine as E
    return (["-r"] if resume else []) + E._dual_args(cdir)


def _read(s, *, goto=None, m0=False):
    if goto:
        i = s.event_index()
        s.send(cmd="goto", strip=goto)
        s.wait_event("strip_ready", after=i, strip=goto)
    s.wait_event("strip_ready")
    strip = goto or [e for e in s.events
                     if e.get("event") == "strip_ready"][-1]["strip"]
    i = s.event_index()
    kw = {"as": f"{strip}~M0"} if m0 else {}
    s.send(cmd="swipe", **kw)
    s.wait_event("strip_ready", after=i)


def _done(s, unread=False):
    i = s.event_index()
    s.send(cmd="done")
    if unread:
        s.wait_event("unread_confirm", after=i)
        s.send(cmd="yes")
    s.wait_event("done", timeout=8, after=i)
    s.finish()


def _conds(s):
    return [e for e in s.events if e.get("event") == "conditions"]


def _locs(path) -> "list[str]":
    return ic._locs_of(path)


def _strips(locs) -> "list[str]":
    return ic.strips_of(list(locs))


def _rows(path) -> "dict[str, list[str]]":
    """loc -> the data tokens of the row (to compare values)."""
    text = Path(path).read_text(encoding="latin-1")
    fields = text.split("BEGIN_DATA_FORMAT")[1].split("END_DATA_FORMAT")[0].split()
    data = text.split("\nBEGIN_DATA\n")[1].split("\nEND_DATA")[0]
    li = fields.index("SAMPLE_LOC")
    return {ln.split()[li].strip('"'): ln.split() for ln in data.splitlines()
            if len(ln.split()) == len(fields)}


def _aged_prune(base: Path, cdir: Path):
    old = time.time() - 3600
    for p in cdir.iterdir():
        os.utime(p, (old, old))
    return [p.name for p in ic.prune_pairs(cdir, base.parent)]


def _partial(main: Path, cond: str) -> Path:
    return ic.partial_sibling_path(main, cond)


# ============================================================ the dual scan

@needs_helper
def test_m1_m2_of_strips_already_read_survive_an_end_and_the_session_end(
        tmp_path, monkeypatch):
    """S3 of paths.txt: A with both passes, B without its UV pass (M1/M2
    end), C as M0, stop. Before: no pair in step, the last one pruned."""
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    base, rp = _dual_chart(tmp_path)
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    with ReplaySession(base, rp, extra_args=_dual_args(cdir)) as s:
        _read(s)
        _read(s, m0=True)
        _read(s)
        _done(s, unread=True)
    ev = _conds(s)
    assert ev[1] == {"event": "conditions", "active": False,
                     "why": "dual_uv_pass_missing", "kept": True}
    main = base.with_suffix(".ti3")
    assert _strips(_locs(main)) == ["A", "B", "C"]
    for c in ("M1", "M2"):
        assert ic.condition_file(main, c) is None        # never offered
        p = _partial(main, c)
        assert ic.sibling_in_step(main, p)
        assert _strips(_locs(p)) == ["A"]
    assert _strips(ic.m0_only_locs(main)) == ["B", "C"]
    assert [(x.cond, x.usable) for x in ic.choices_for(main)] == [
        ("M0", True), ("M1", False), ("M2", False)]
    why = ic.no_file_reason(main)
    assert "B, C" in why and "keep their M1 and M2" in why
    assert _aged_prune(base, cdir) == []                  # held: kept
    assert storage.read_dual_record(main).dual


@needs_helper
def test_continue_measurement_completes_the_strips_with_m0_only(tmp_path,
                                                                monkeypatch):
    """B2/B4: the next sitting takes the partial record back, reads D and the
    M0-only strips B and C with both passes: the complete pair again."""
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    base, rp = _dual_chart(tmp_path)
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    main = base.with_suffix(".ti3")
    with ReplaySession(base, rp, extra_args=_dual_args(cdir)) as s:
        _read(s)
        _read(s, m0=True)
        _read(s)
        _done(s, unread=True)
    a_m1 = _rows(_partial(main, "M1"))
    with ReplaySession(base, rp, extra_args=_dual_args(cdir, resume=True)) as s:
        _read(s)                        # D, the strip not read yet
        _read(s, goto="B")
        _read(s, goto="C")
        _done(s)
    ev = _conds(s)
    assert ev[0]["active"] is True and ev[0]["dual"] is True
    assert ev[0].get("partial") is True
    assert len(ev) == 1
    assert ic.m0_only_locs(main) == []
    for c in ("M1", "M2"):
        f = ic.condition_file(main, c)
        assert f is not None and f.name.endswith(f"-{c}.ti3")
        assert _strips(_locs(f)) == ["A", "B", "C", "D"]
    # A's M1 is the one of the first sitting, untouched
    full = _rows(ic.condition_file(main, "M1"))
    assert all(full[loc] == row for loc, row in a_m1.items())
    assert [(x.cond, x.usable) for x in ic.choices_for(main)] == [
        ("M0", True), ("M1", True), ("M2", True)]
    gone = _aged_prune(base, cdir)
    assert gone and all(n.endswith(".partial.ti3") for n in gone)


@needs_helper
def test_a_guided_reread_without_the_uv_pass_keeps_the_others(tmp_path,
                                                              monkeypatch):
    """S5 of paths.txt (Check & Refine's list, a click in the preview): a
    complete dual measurement, B read again without its UV pass. Before:
    every strip's M1/M2 lost. Now: B is M0 only, its OLD M1/M2 gone with
    its old M0, A, C, D keep theirs."""
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    base, rp = _dual_chart(tmp_path)
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    main = base.with_suffix(".ti3")
    with ReplaySession(base, rp, extra_args=_dual_args(cdir)) as s:
        for _ in range(4):
            _read(s)
        _done(s)
    before = _rows(ic.condition_file(main, "M1"))
    with ReplaySession(base, rp, extra_args=_dual_args(cdir, resume=True)) as s:
        _read(s, goto="B", m0=True)
        _done(s)
    assert _conds(s)[-1]["kept"] is True
    p = _partial(main, "M1")
    assert ic.sibling_in_step(main, p)
    after = _rows(p)
    assert _strips(after) == ["A", "C", "D"]              # B: no stale M1
    assert all(before[loc] == row for loc, row in after.items())
    assert _strips(ic.m0_only_locs(main)) == ["B"]
    # the complete pair of the old readings is housekeeping now
    gone = _aged_prune(base, cdir)
    assert gone and not [n for n in gone if n.endswith(".partial.ti3")]


def _hand_partial(main: Path, cdir: Path, strips) -> None:
    """A partial pair for *main* holding the rows of *strips*, written as the
    engine writes one (header keywords, NUMBER_OF_SETS), M1 = M2 = M0 rows."""
    text = main.read_text(encoding="latin-1")
    key = ic.data_block_hash(main)
    head, rest = text.split("BEGIN_DATA_FORMAT", 1)
    fmt, data = rest.split("\nBEGIN_DATA\n", 1)
    data, tail = data.split("\nEND_DATA", 1)
    rows = _rows(main)
    keep = [ln for ln in data.splitlines()
            if any(t.strip('"') in rows and t.strip('"')[:1] in strips
                   for t in ln.split()[:2])]
    fmt = "\n".join(f"NUMBER_OF_SETS {len(keep)}"
                    if ln.startswith("NUMBER_OF_SETS") else ln
                    for ln in fmt.splitlines())
    for c in ("M1", "M2"):
        first, nl, after = head.partition("\n")
        h = (first + nl + f'KEYWORD "MEASUREMENT_CONDITION"\nMEASUREMENT_CONDITION "{c}"\n'
             f'KEYWORD "CHROMIQ_CONDITION_OF"\nCHROMIQ_CONDITION_OF "{key}"\n' + after)
        (cdir / f"{key}-{c}.partial.ti3").write_text(
            h + "BEGIN_DATA_FORMAT" + fmt + "\nBEGIN_DATA\n" + "\n".join(keep)
            + "\nEND_DATA" + tail, encoding="latin-1")


@needs_helper
def test_a_sitting_that_cannot_read_the_uv_pass_keeps_the_record(tmp_path,
                                                                 monkeypatch):
    """B3: a dual measurement continued where the UV pass cannot be read (an
    instrument without the UV light; here the replay without dual data):
    nothing is armed, the record is kept (A's M1 / M2 written again under the
    new readings' name), the strip read now is M0 only, the header stays a
    dual one. The replay has no spectral form without dual data, so the dual
    measurement is made from an XYZ sitting whose header is a dual one."""
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    base, rp_plain = _dual_chart(tmp_path, dualcal=False)
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    main = base.with_suffix(".ti3")
    with ReplaySession(base, rp_plain, extra_args=["-S"]) as s:
        _read(s)
        _read(s)
        _done(s, unread=True)
    text = main.read_text(encoding="latin-1")
    first, nl, after = text.partition("\n")
    main.write_text(first + nl + "".join(
        f'KEYWORD "{k}"\n{k} "{v}"\n' for k, v in (
            ("CHROMIQ_DUAL_SCAN", "i1pro2"), ("CHROMIQ_DUAL_SCALE", "1.1370"),
            ("CHROMIQ_DUAL_SCALE_SOURCE", "standard"),
            ("CHROMIQ_DUAL_WHITE", "instrument"), ("CHROMIQ_DUAL_CHOSEN", "M0")))
        + after, encoding="latin-1")
    _hand_partial(main, cdir, ("A",))
    assert _strips(ic.m0_only_locs(main)) == ["B"]
    a_rows = _rows(_partial(main, "M1"))
    with ReplaySession(base, rp_plain,
                       extra_args=_dual_args(cdir, resume=True)) as s:
        _read(s)                        # C, as M0
        _done(s, unread=True)
    assert _conds(s) == [{"event": "conditions", "active": False,
                          "why": "dual_not_available", "kept": True}]
    assert storage.read_dual_record(main).dual
    p = _partial(main, "M2")
    assert ic.sibling_in_step(main, p) and _strips(_locs(p)) == ["A"]
    def num(rows):
        return {k: [round(float(v), 4) for v in r[2:]] for k, r in rows.items()}
    assert num(_rows(_partial(main, "M1"))) == num(a_rows)   # A's, carried over
    assert _strips(ic.m0_only_locs(main)) == ["B", "C"]


@needs_helper
def test_a_dual_measurement_without_any_pair_continues_with_both_passes(
        tmp_path, monkeypatch):
    """A dual measurement whose M1/M2 were already lost (4.3.48 pruned them):
    Continue reads the rest with both passes and lists every strip read
    before as M0 only, to be completed (it was "M0 only for ever" before)."""
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    base, rp = _dual_chart(tmp_path)
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    main = base.with_suffix(".ti3")
    with ReplaySession(base, rp, extra_args=_dual_args(cdir)) as s:
        _read(s)
        _read(s)
        _done(s, unread=True)
    for p in list(cdir.iterdir()):
        p.unlink()                       # as 4.3.48's housekeeping left it
    assert _strips(ic.m0_only_locs(main)) == ["A", "B"]
    with ReplaySession(base, rp, extra_args=_dual_args(cdir, resume=True)) as s:
        _read(s)
        _done(s, unread=True)
    ev = _conds(s)
    assert ev[0]["active"] is True and ev[0].get("partial") is True
    assert _strips(_locs(_partial(main, "M1"))) == ["C"]
    assert _strips(ic.m0_only_locs(main)) == ["A", "B"]


@needs_helper
def test_a_complete_dual_measurement_reads_and_continues_exactly_as_before(
        tmp_path, monkeypatch):
    """Where nothing ends, nothing changes: the events have no new field and
    no partial file is ever written (S1, S2, S4 of paths.txt)."""
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    base, rp = _dual_chart(tmp_path)
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    main = base.with_suffix(".ti3")
    with ReplaySession(base, rp, extra_args=_dual_args(cdir)) as s:
        _read(s)
        _read(s)
        _done(s, unread=True)
    first = [e for e in _conds(s)]
    with ReplaySession(base, rp, extra_args=_dual_args(cdir, resume=True)) as s:
        _read(s)
        _read(s)
        _read(s, goto="B")
        _done(s)
    for evs in (first, _conds(s)):
        assert len(evs) == 1 and "partial" not in evs[0] and "kept" not in evs[0]
    assert not [p for p in cdir.iterdir() if p.name.endswith(".partial.ti3")]
    assert ic.condition_file(main, "M1") is not None


# ============================================================ the i1Pro 3

def _a3(cdir, resume=False):
    return (["-r"] if resume else []) + ["--condition-dir", str(cdir)]


@needs_helper
def test_i1pro3_a_reread_without_conditions_keeps_the_other_strips(
        tmp_path, monkeypatch):
    """P2 of paths.txt, the same fault on the i1Pro 3 (Basti: fix it too)."""
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro3")
    base, rp = _i1pro3_chart(tmp_path)
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    main = base.with_suffix(".ti3")
    with ReplaySession(base, rp, extra_args=_a3(cdir)) as s:
        for _ in range(4):
            _read(s)
        _done(s)
    with ReplaySession(base, rp, extra_args=_a3(cdir, resume=True)) as s:
        _read(s, goto="B", m0=True)
        _done(s)
    assert _conds(s)[-1] == {"event": "conditions", "active": False,
                             "why": "record", "kept": True}
    assert _strips(_locs(_partial(main, "M1"))) == ["A", "C", "D"]
    assert _strips(ic.m0_only_locs(main)) == ["B"]
    # ...and filled: B read again with its conditions -> the complete pair
    with ReplaySession(base, rp, extra_args=_a3(cdir, resume=True)) as s:
        _read(s, goto="B")
        _done(s)
    assert _conds(s)[0].get("partial") is True
    assert ic.condition_file(main, "M1") is not None
    assert ic.m0_only_locs(main) == []


@needs_helper
def test_i1pro3_an_end_midway_then_continue_keeps_and_completes(
        tmp_path, monkeypatch):
    """P3 of paths.txt: A, B without conditions, stop; Continue C, D and B."""
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro3")
    base, rp = _i1pro3_chart(tmp_path)
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    main = base.with_suffix(".ti3")
    with ReplaySession(base, rp, extra_args=_a3(cdir)) as s:
        _read(s)
        _read(s, m0=True)
        _done(s, unread=True)
    assert _strips(ic.m0_only_locs(main)) == ["B"]
    assert "B" in ic.no_file_reason(main)
    with ReplaySession(base, rp, extra_args=_a3(cdir, resume=True)) as s:
        _read(s)
        _read(s)
        _read(s, goto="B")
        _done(s)
    assert ic.condition_file(main, "M2") is not None


@needs_helper
def test_i1pro3_unchanged_where_it_was_right(tmp_path, monkeypatch):
    """A complete measurement re-read with its conditions: the same events and
    files as before (no partial file, no new field); a measurement made
    without the Beta is continued as before ("resume")."""
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro3")
    base, rp = _i1pro3_chart(tmp_path)
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    with ReplaySession(base, rp, extra_args=_a3(cdir)) as s:
        for _ in range(4):
            _read(s)
        _done(s)
    with ReplaySession(base, rp, extra_args=_a3(cdir, resume=True)) as s:
        _read(s, goto="B")
        _done(s)
    assert _conds(s) == [{"event": "conditions", "active": True,
                          "instrument": "i1pro3", "main": "M0",
                          "extra": ["M1", "M2"]}]
    assert not [p for p in cdir.iterdir() if "partial" in p.name]
    b2, rp2 = _i1pro3_chart(tmp_path / "plain")
    c2 = tmp_path / "plain" / "conditions"
    c2.mkdir()
    with ReplaySession(b2, rp2, extra_args=[]) as s:        # Beta off
        _read(s)
        _done(s, unread=True)
    with ReplaySession(b2, rp2, extra_args=_a3(c2, resume=True)) as s:
        _read(s)
        _done(s, unread=True)
    assert _conds(s) == [{"event": "conditions", "active": False,
                          "why": "resume"}]
    assert list(c2.iterdir()) == []
    assert ic.m0_only_locs(b2.with_suffix(".ti3")) == []


# ============================================================ files, rules

def test_4348_never_reads_or_deletes_a_partial_file():
    """Files written now and read by 4.3.48: a partial pair is not named like
    a pair to its readers (sibling_path, the prune's pattern), so 4.3.48
    offers M0 only and leaves it alone: it fails safe."""
    old_pattern = re.compile(r"^(\d+-[0-9a-f]{8})-M[012]\.ti3$")   # 4.3.48
    assert not old_pattern.match("123-0a0b0c0d-M1.partial.ti3")
    assert ic._PAIR_NAME_RE.match("123-0a0b0c0d-M1.partial.ti3")
    assert ic._PAIR_NAME_RE.match("123-0a0b0c0d-M1.ti3")


def test_a_partial_file_is_pruned_only_when_nothing_holds_it(tmp_path):
    from core.file_manager import Run  # noqa: F401
    run = tmp_path / "run"
    cdir = run / "conditions"
    cdir.mkdir(parents=True)
    main = run / "chart.ti3"
    main.write_text('CTI3\nBEGIN_DATA_FORMAT\nSAMPLE_LOC XYZ_X\nEND_DATA_FORMAT\n'
                    'NUMBER_OF_SETS 1\nBEGIN_DATA\n"A1" 1.0\nEND_DATA\n')
    key = ic.data_block_hash(main)

    def write(name, of, cond):
        (cdir / name).write_text(
            f'CTI3\nKEYWORD "MEASUREMENT_CONDITION"\nMEASUREMENT_CONDITION "{cond}"\n'
            f'KEYWORD "CHROMIQ_CONDITION_OF"\nCHROMIQ_CONDITION_OF "{of}"\n'
            'BEGIN_DATA_FORMAT\nSAMPLE_LOC XYZ_X\nEND_DATA_FORMAT\n'
            'NUMBER_OF_SETS 1\nBEGIN_DATA\n"A1" 2.0\nEND_DATA\n')
    write(f"{key}-M1.partial.ti3", key, "M1")                # held
    write("9-00000000-M1.partial.ti3", "9-00000000", "M1")   # nobody's
    write("8-00000000-M2.partial.ti3", "7-00000000", "M2")   # not ours
    old = time.time() - 3600
    for p in cdir.iterdir():
        os.utime(p, (old, old))
    gone = [p.name for p in ic.prune_pairs(cdir, run)]
    assert gone == ["9-00000000-M1.partial.ti3"]


def test_the_helper_arms_nothing_new_after_an_end():
    """The device side: every decision that arms an instrument asks
    cq_cond_live(), false exactly where cq_cond_active was false after an
    end; the i1Pro 3 is disarmed at an end as before."""
    src = C_SRC.read_text(encoding="utf-8")
    assert "cq_dd_this_strip = cq_dd.on && cq_cond_live()" in src
    assert src.count("if (cq_dd.on && cq_cond_live())") == 2
    assert "cq_dd.on && cq_cond_active" not in src
    lose = src[src.index("static void cq_cond_lose("):]
    lose = lose[:lose.index("\n}\n")]
    assert lose.count("i1pro3_cq_cond_arm(cq_cond_it, 0);") == 2
    arm = src[src.index("static void cq_cond_arm(int on)"):]
    assert arm[:200].count("!cq_cond_live()") == 1
    after = src[src.index("static void cq_cond_after_read("):]
    after = after[:after.index("if ((rv != inst_ok")]
    assert "if (cq_cond_m0only)\n\t\treturn;" in after


def test_the_plan_names_the_strips_and_ended_before_is_only_the_old_header(
        tmp_path, monkeypatch):
    from workflow.dual_scan import session as D
    main = tmp_path / "chart.ti3"
    main.write_text('CTI3\nKEYWORD "CHROMIQ_DUAL_SCAN"\nCHROMIQ_DUAL_SCAN "i1pro2"\n'
                    'BEGIN_DATA_FORMAT\nSAMPLE_LOC XYZ_X\nEND_DATA_FORMAT\n'
                    'NUMBER_OF_SETS 2\nBEGIN_DATA\n"A1" 1.0\n"B1" 1.0\nEND_DATA\n')
    assert D.ended_before(main) is False
    assert D.m0_only_strips(main) == ["A", "B"]


# ============================================================ the Measure tab

class _S(dict):
    def get(self, k, d=None):
        return super().get(k, d)

    def set(self, k, v):
        self[k] = v


def _fill_fake(base: Path, resume: bool, settings):
    from types import SimpleNamespace
    from ui.tabs.tab_measure import TabMeasure
    main = base.with_suffix(".ti3")
    f = SimpleNamespace(
        _settings=settings, _engine_selected=lambda: True,
        _selected_measurement_ti3=lambda: main,
        _strip_of=lambda loc: "".join(c for c in loc if c.isalpha()).upper(),
        _strip_index=lambda s: ord(s[0]) - 65,
        _measurement_to_continue=lambda: main if resume else None,
        _ti1_path=base.with_suffix(".ti2"),
        _chart_file_for=lambda p: base.with_suffix(".ti2"))
    f._fill_main = lambda: TabMeasure._fill_main(f)
    f._fill_strips = lambda main=None: TabMeasure._fill_strips(f, main)
    f._fill_note_text = lambda: TabMeasure._fill_note_text(f)
    return f


@needs_helper
def test_the_measure_tab_offers_and_guides_to_the_strips_with_m0_only(
        tmp_path, monkeypatch, qapp):
    """B4: the note before START names the strips (an offer while "Refine /
    resume" is not ticked, the plan while it is), and Continue Measurement
    takes the reader there with the refinement guide, together with the
    strips not read yet (so the guide ends with the chart complete)."""
    from ui.tabs.tab_measure import TabMeasure
    from workflow import measurement_messages as M
    from workflow.dual_scan import session as D
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    base, rp = _dual_chart(tmp_path)
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    with ReplaySession(base, rp, extra_args=_dual_args(cdir)) as s:
        _read(s)
        _read(s, m0=True)
        _done(s, unread=True)
    on = _S({ic.SETTING: True, D.SETTING: True})
    off = _fill_fake(base, False, on)
    assert TabMeasure._fill_note_text(off) == M.M_DUAL_FILL_OFFER.render(
        strips="B", resume=tr_("Refine / resume existing measurement (-r)"),
        start=tr_("Continue Measurement"))
    res = _fill_fake(base, True, on)
    assert TabMeasure._fill_note_text(res) == M.M_DUAL_CONTINUE_FILL.render(
        strips="B")
    assert TabMeasure._fill_guided_strips(res, []) == ["B", "C", "D"]
    assert TabMeasure._fill_guided_strips(res, ["D", "A"]) == ["A", "B", "C", "D"]
    # the dual scan switched off: Continue is refused, nothing is offered
    no_dual = _fill_fake(base, True, _S({ic.SETTING: True}))
    assert TabMeasure._fill_note_text(no_dual) == ("", "")
    assert TabMeasure._fill_guided_strips(no_dual, ["D"]) == ["D"]


def tr_(s):
    from core.i18n import tr
    return tr(s)


@needs_helper
def test_the_i1pro3_note_names_its_own_conditions(tmp_path, monkeypatch, qapp):
    from ui.tabs.tab_measure import TabMeasure
    from workflow import measurement_messages as M
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro3")
    base, rp = _i1pro3_chart(tmp_path)
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    with ReplaySession(base, rp, extra_args=_a3(cdir)) as s:
        _read(s)
        _read(s, m0=True)
        _done(s, unread=True)
    res = _fill_fake(base, True, _S({ic.SETTING: True}))
    assert TabMeasure._fill_note_text(res) == M.M_COND_CONTINUE_FILL.render(
        strips="B", own="M0", first="M1", second="M2")
    assert TabMeasure._fill_guided_strips(res, []) == ["B", "C", "D"]
