"""X-Rite i1Pro 3: keep M0, M1 and M2 from every scan (Preferences > Beta,
2026-11-15) in the REAL chromiq-chartread, through its replay instrument
(CHROMIQ_REPLAY_INSTRUMENT=i1pro3, COND blocks in the script).

* without --condition-dir: not one "conditions" event, no condition file, and
  the main .ti3 is byte for byte (CREATED aside) the one written with it on;
* with it: the two other conditions in <dir>/<hash>-M1.ti3 / -M2.ti3, named
  by the main file's data block hash (the Python and C hashes agree), each
  patch's values those of the same patch under that condition, also after a
  reversed swipe, "Turn this strip round", "I read strip B" and a resume;
  only the newest pair of the session stays;
* anything that cannot keep them in step ends them for the session, with the
  reason, and the main measurement is never affected.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import (HELPER, ReplaySession, parse_ti2_rows)  # noqa: E402

from workflow.i1pro3_conditions import data_block_hash  # noqa: E402

needs_helper = pytest.mark.skipif(not HELPER.exists(),
                                  reason="chromiq-chartread helper not built")

K = {"M1": 1.02, "M2": 0.97}


def _chart(tmp: Path, conds=("M1", "M2")):
    from test_chartread_engine import _make_chart
    base = _make_chart(tmp, randomised=False)
    steps, rows = parse_ti2_rows(base.with_suffix(".ti2"))
    rp = tmp / "replay.txt"
    with rp.open("w", encoding="utf-8") as fp:
        fp.write(f"PATCHES {steps}\n")
        for letter in sorted(rows):
            fp.write(f"STRIP {letter}\n")
            for i, (x, y, z) in enumerate(rows[letter]):
                fp.write(f"{x:.4f} {y + 0.001 * i:.4f} {z:.4f}\n")
            for c in conds:
                fp.write(f"COND {c}\n")
                for i, (x, y, z) in enumerate(rows[letter]):
                    fp.write(f"{x * K[c]:.4f} {(y + 0.001 * i) * K[c]:.4f} "
                             f"{z:.4f}\n")
    return base, rp, rows


def _rows(path: Path) -> "dict[str, list[float]]":
    text = path.read_text(encoding="latin-1")
    fields = text.split("BEGIN_DATA_FORMAT")[1].split("END_DATA_FORMAT")[0].split()
    data = text.split("\nBEGIN_DATA\n")[1].split("\nEND_DATA")[0]
    li, xi = fields.index("SAMPLE_LOC"), fields.index("XYZ_X")
    out = {}
    for ln in data.splitlines():
        t = ln.split()
        if len(t) == len(fields):
            out[t[li].strip('"')] = [float(v) for v in t[xi:xi + 3]]
    return out


def _swipe(s, **kw):
    s.wait_event("strip_ready")
    i = s.event_index()
    s.send(cmd="swipe", **kw)
    s.wait_event("strip_ready", after=i)


def _done(s, unread=False):
    i = s.event_index()
    s.send(cmd="done")
    if unread:          # "At least one unread patch, are you sure?"
        s.wait_event("unread_confirm", after=i)
        s.send(cmd="yes")
    s.wait_event("done", timeout=8, after=i)
    s.finish()


def _pair(base: Path, cdir: Path):
    h = data_block_hash(base.with_suffix(".ti3"))
    return h, cdir / f"{h}-M1.ti3", cdir / f"{h}-M2.ti3"


def _check_in_step(base, cdir):
    h, m1, m2 = _pair(base, cdir)
    main = _rows(base.with_suffix(".ti3"))
    assert main
    for c, f in (("M1", m1), ("M2", m2)):
        assert f.is_file(), sorted(p.name for p in cdir.iterdir())
        text = f.read_text(encoding="latin-1")
        assert f'MEASUREMENT_CONDITION "{c}"' in text
        assert f'CHROMIQ_CONDITION_OF "{h}"' in text
        assert ('INSTRUMENT_FILTER "UVCUT"' in text) == (c == "M2")
        rows = _rows(f)
        assert set(rows) == set(main)
        for loc, xyz in main.items():
            assert rows[loc][1] == pytest.approx(xyz[1] * K[c], abs=2e-3), loc
            assert rows[loc][2] == pytest.approx(xyz[2], abs=2e-3), loc
    return h


@needs_helper
def test_off_writes_nothing_new_and_the_main_file_is_the_same(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro3")
    texts = []
    for on in (False, True):
        d = tmp_path / ("on" if on else "off")
        d.mkdir()
        base, rp, _ = _chart(d)
        cdir = d / "conditions"
        cdir.mkdir()
        args = ["--condition-dir", str(cdir)] if on else []
        with ReplaySession(base, rp, extra_args=args) as s:
            _swipe(s)
            _swipe(s, reversed=True)
            _done(s)
        ev = [e for e in s.events if e.get("event") == "conditions"]
        if on:
            assert ev and ev[0]["active"] is True
            assert ev[0]["main"] == "M0" and ev[0]["extra"] == ["M1", "M2"]
            _check_in_step(base, cdir)
        else:
            assert ev == [] and list(cdir.iterdir()) == []
        texts.append("\n".join(ln for ln in base.with_suffix(".ti3").read_text(
            encoding="latin-1").splitlines() if not ln.startswith("CREATED")))
    assert texts[0] == texts[1]


@needs_helper
def test_only_the_newest_pair_of_the_session_stays(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro3")
    base, rp, _ = _chart(tmp_path)
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    keep = cdir / "0-00000000-M1.ti3"     # a pair that was there at Start
    keep.write_text("an earlier session's file\n", encoding="utf-8")
    with ReplaySession(base, rp, extra_args=["--condition-dir", str(cdir)]) as s:
        for _ in range(3):
            _swipe(s)
        _done(s)
    h = _check_in_step(base, cdir)
    names = sorted(p.name for p in cdir.iterdir())
    assert names == sorted([keep.name, f"{h}-M1.ti3", f"{h}-M2.ti3"])


@needs_helper
def test_turn_and_file_as_keep_the_three_in_step(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro3")
    base, rp, rows = _chart(tmp_path)
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    a, b = sorted(rows)[:2]
    with ReplaySession(base, rp, extra_args=["-S", "-B", "--condition-dir",
                                             str(cdir)]) as s:
        _swipe(s, reversed=True)                # filed back to front (-B)
        i = s.event_index()
        s.send(cmd="turn", strip=a)
        s.wait_event("strip_turned", after=i)
        _swipe(s, **{"as": a})                  # strip A read again, on B
        i = s.event_index()
        s.send(cmd="file_as", strip=b, **{"as": a})
        s.wait_event("strip_filed_as", after=i)
        _swipe(s)                               # and B itself
        _done(s)
    _check_in_step(base, cdir)
    assert not [e for e in s.events if e.get("event") == "conditions"
                and e.get("active") is False]


@needs_helper
def test_a_resume_brings_the_pair_back_and_goes_on(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro3")
    base, rp, _ = _chart(tmp_path)
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    args = ["--condition-dir", str(cdir)]
    with ReplaySession(base, rp, extra_args=args) as s:
        _swipe(s)
        _done(s, unread=True)
    first = _check_in_step(base, cdir)
    with ReplaySession(base, rp, extra_args=["-r"] + args) as s:
        _swipe(s)
        _done(s)
    assert [e for e in s.events if e.get("event") == "conditions"][0]["active"]
    second = _check_in_step(base, cdir)
    assert second != first
    # the pair the resumed session found at Start is left alone (a Discard
    # would bring its main file back)
    assert (cdir / f"{first}-M1.ti3").is_file()


@needs_helper
def test_a_resume_onto_a_main_without_its_pair_ends_them(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro3")
    base, rp, _ = _chart(tmp_path)
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    with ReplaySession(base, rp, extra_args=[]) as s:     # measured with it off
        _swipe(s)
        _done(s, unread=True)
    before = base.with_suffix(".ti3").read_bytes()
    with ReplaySession(base, rp, extra_args=["-r", "--condition-dir",
                                             str(cdir)]) as s:
        _swipe(s)
        _done(s)
    ev = [e for e in s.events if e.get("event") == "conditions"]
    assert ev == [{"event": "conditions", "active": False, "why": "resume"}]
    assert list(cdir.iterdir()) == []
    assert base.with_suffix(".ti3").read_bytes() != before   # measured on


@pytest.mark.parametrize("inst,args,why", [
    ("i1pro", [], "instrument"),             # the replay's default model
    ("i1pro2", [], "instrument"),
    ("i1pro3", ["-F", "p"], "filter"),       # the polariser is its own path
])
@needs_helper
def test_where_it_does_not_apply_it_says_why(tmp_path, monkeypatch, inst, args, why):
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", inst)
    base, rp, _ = _chart(tmp_path)
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    with ReplaySession(base, rp, extra_args=args + ["--condition-dir",
                                                    str(cdir)]) as s:
        _swipe(s)
        _done(s, unread=True)
    ev = [e for e in s.events if e.get("event") == "conditions"]
    assert ev == [{"event": "conditions", "active": False, "why": why}]
    assert list(cdir.iterdir()) == []


@needs_helper
def test_a_script_without_the_conditions_record_ends_them(tmp_path, monkeypatch):
    """A reading that came without its two other results (here: a script
    whose strips have no COND block) ends them; the main file is today's."""
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro3")
    base, rp, _ = _chart(tmp_path, conds=("M1",))     # M2 missing
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    with ReplaySession(base, rp, extra_args=["--condition-dir", str(cdir)]) as s:
        _swipe(s)
        _swipe(s)
        _done(s)
    ev = [e for e in s.events if e.get("event") == "conditions"]
    assert ev[0]["active"] is True
    assert ev[1] == {"event": "conditions", "active": False, "why": "record"}
    assert len(ev) == 2
    assert list(cdir.iterdir()) == []
    assert len(_rows(base.with_suffix(".ti3"))) > 0


@needs_helper
def test_a_folder_it_cannot_write_ends_them_and_the_main_file_is_kept(
        tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro3")
    base, rp, _ = _chart(tmp_path)
    missing = tmp_path / "no-such-folder"
    with ReplaySession(base, rp, extra_args=["--condition-dir", str(missing)]) as s:
        _swipe(s)
        _swipe(s)
        _done(s)
    ev = [e for e in s.events if e.get("event") == "conditions"]
    assert ev[-1] == {"event": "conditions", "active": False, "why": "write"}
    assert not [e for e in s.events if e.get("kind") == "autosave_rename"]
    assert len(_rows(base.with_suffix(".ti3"))) > 0


@needs_helper
def test_with_the_ruler_check_both_work(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro3")
    base, rp, _ = _chart(tmp_path)
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    with ReplaySession(base, rp, extra_args=["--ruler", "--condition-dir",
                                             str(cdir)]) as s:
        _swipe(s, ruler="clean")
        _swipe(s, ruler="partial", reversed=True)
        _done(s)
    assert len([e for e in s.events if e.get("event") == "ruler_strip"]) == 2
    _check_in_step(base, cdir)


@needs_helper
def test_the_caps_say_it():
    import json
    import subprocess
    out = subprocess.run([str(HELPER), "--caps"], capture_output=True,
                         text=True, encoding="utf-8", timeout=30).stdout
    assert "i1pro3_conditions" in json.loads(out.strip().splitlines()[-1])["caps"]
