""""I read strip B" counts the reading as strip B, and the reader stays on the
strip that was due (#182, Knut 6102031563, 4.3.5).

Knut, answering question 1 of 6099862394 ("After 'I read strip B', the
set-aside reading is not painted onto B; the reader moves to B and your next
reading of B counts. Is that what you want?"):

    "No... When I specify that I read strip B, then the values I read should
    be counted as strip B values and judged in the neighbour check for the
    strip B values ... I should not need to read it again, and then focus can
    stay at unread strip I was supposed to read (in this case strip C, but the
    reading focus arrows could have been on any other strip, f.ex. F ...). If
    I would have clicked "Keep it, its strip C", then the values should be
    counted as strip C values and judged in the neighbour check for the strip
    C values, and then jump to the next unread strip D."

How it is built: the measuring engine (chromiq-chartread) files every reading
under the strip it is positioned on, so the reading lives in the engine as
strip C. The answer sends ``{"cmd":"file_as","strip":"C","as":"B"}``; the
engine moves the values onto B (replacing B's earlier reading, spectra
included, in the saved .ti3 too), leaves C unread and puts the reader on C. Its
``strip_filed_as`` event carries the reading under B's locations and B's
expected colours, and the Measure tab judges it exactly as a reading of B
taken with the reader on B.

Every way the window ends is proved here on every chart type it can appear on
(Knut, 6094941512: "The test of the neighbour check must be constructed to
verify all these choices every time this function is verified"):

* "I read strip B": counted and judged as B (patch error limit, strip test,
  neighbour check, outlines, cards, counts, the saved .ti3), C unread, the
  reader on C;
* "Keep, it is strip C" and closing the window: counted and judged as C, the
  reader on to the next unread strip (the engine's own move);
* "Re-read strip C": as before, the reading is set aside, never judged, C is
  unread and the reader goes back to C.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QPushButton  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from test_434b1_read_twice_is_judged_after_the_answer import (  # noqa: E402
    CHECKS, KINDS, PER, _cards, _de, _exyz, _for_kind, _locs, _mxyz,
    _overlay, _run, _sread, _sready, _state, _tab)
from test_knut_5956210745_next_strip_after_a_read import (  # noqa: E402
    _feed)

#: The four ways the window ends: the button's place in the row.
BUTTONS = {"reread": 0, "was_like": 1, "keep": 2, "closed": None}


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(params=[(c, k) for c in CHECKS for k in KINDS],
                ids=[f"{c}-{k}" for c in CHECKS for k in KINDS])
def checks(request):
    check, kind = request.param
    return {**_for_kind(check, kind), "_kind": kind}


def _filing_tab(tmp, monkeypatch, settings=None):
    """The 4.3.4 harness, with an engine that understands file_as (its
    session_start says so, as chromiq-chartread's does since 4.3.5)."""
    tab = _tab(tmp, monkeypatch, settings)
    mgr = tab._manager
    ti2 = Path(str(tab._ti1_path)).with_suffix(".ti2")
    from test_434b1_read_twice_is_judged_after_the_answer import STRIPS
    _feed(mgr, {"event": "session_start", "chart": str(ti2), "file_as": True,
                "strips": [{"strip": x, "read": False} for x in STRIPS]})
    tab._reset_progress(from_files=False)
    return tab


def _swipe(strip, like, scale=0.99):
    """Strip *like*'s colours swiped with the reader on *strip* (a second
    reading of *like*, a little different from its first)."""
    ev = _sread(strip, like=like)
    for p in ev["patches"]:
        p["xyz"] = [v * scale for v in p["xyz"]]
        p["de"] = round(_de(p["exyz"], p["xyz"]), 3)
    return ev


def _filed_as(like, strip, scale=0.99):
    """What the engine answers file_as with: the same values, under *like*'s
    locations and *like*'s expected colours (chromiq_chartread.c,
    cq_emit_strip_filed_as)."""
    out = []
    for k in range(1, PER + 1):
        e = _exyz(like, k)
        m = [v * scale for v in _mxyz(like, k)]
        out.append({"loc": f"{like}{k}", "exyz": e, "xyz": m,
                    "de": round(_de(e, m), 2)})
    return {"event": "strip_filed_as", "strip": like, "from": strip,
            "patches": out}


def _engine_answers(tab):
    """Feed the engine's reply to every file_as the manager sent."""
    for raw in list(tab._sent):
        cmd = json.loads(raw)
        if cmd.get("cmd") == "file_as":
            _feed(tab._manager, _filed_as(cmd["as"], cmd["strip"]),
                  {"event": "strip_ready", "strip": cmd["strip"],
                   "read": False, "all_done": False})


def _answer(monkeypatch, choice):
    real = QDialog.exec

    def _exec(dlg):
        if dlg.objectName() != "strip_read_twice_window":
            return real(dlg)
        button = BUTTONS[choice]
        if button is None:
            dlg.reject()
            return 0
        dlg.findChildren(QPushButton)[button].click()
        return 1
    monkeypatch.setattr(QDialog, "exec", _exec)


def _commands(tab):
    return [json.loads(x) for x in tab._sent]


def _knuts(qapp, tab, monkeypatch, choice, *, c_read_before=False):
    """A and B read (and C), the reader on C, B's colours swiped there."""
    events = [_sread("A"), _sready("B"), _sread("B"), _sready("C")]
    if c_read_before:
        events += [_sread("C"), _sready("C")]
    _run(qapp, tab, events)
    _answer(monkeypatch, choice)
    tab._sent.clear()
    _run(qapp, tab, [_swipe("C", "B")])
    sent = _commands(tab)
    _engine_answers(tab)
    for _ in range(6):
        qapp.processEvents()
    return sent


def _b_read_on_b(qapp, tmp, monkeypatch, checks, c_read_before):
    """The same second reading of B taken with the reader on B: what "I read
    strip B" must give strip B."""
    tab = _filing_tab(tmp, monkeypatch, checks)
    events = [_sread("A"), _sready("B"), _sread("B"), _sready("C")]
    if c_read_before:
        events += [_sread("C"), _sready("C")]
    _run(qapp, tab, events)
    ev = _filed_as("B", "C")
    ev["event"] = "strip_read"
    del ev["from"]
    tab._manager._check_read_twice = lambda *_a, **_k: None
    _run(qapp, tab, [_sready("B"), ev])
    return tab


@pytest.mark.parametrize("c_read_before", [False, True],
                         ids=["fresh", "c_read_before"])
def test_i_read_strip_b_judges_the_reading_as_b(qapp, tmp_path, monkeypatch,
                                                checks, c_read_before):
    tab = _filing_tab(tmp_path / "t", monkeypatch, checks)
    sent = _knuts(qapp, tab, monkeypatch, "was_like",
                  c_read_before=c_read_before)
    # ONE command: the engine files the reading as B and stays on C. No
    # goto to B (4.3.4) and none anywhere else.
    assert sent == [{"cmd": "file_as", "strip": "C", "as": "B"}]
    after = _state(tab)
    ref = _state(_b_read_on_b(qapp, tmp_path / "ref", monkeypatch, checks,
                              c_read_before))
    b, c = set(_locs("B")), set(_locs("C"))
    # Strip B: outlines, cards, neighbour readings and findings, the yellow
    # memory, exactly as the same reading taken with the reader on B.
    for loc in b:
        assert after["overlay"][loc] == ref["overlay"][loc], loc
        assert after["judge_history"].get(loc) == \
            ref["judge_history"].get(loc), loc
    assert sorted(set(after["nb_readings"]) & b) == \
        sorted(set(ref["nb_readings"]) & b)
    assert sorted(set(after["nb_suspects"]) & b) == \
        sorted(set(ref["nb_suspects"]) & b)
    cards, ref_cards = _cards(tab), _cards(_b_read_on_b(
        qapp, tmp_path / "ref2", monkeypatch, checks, c_read_before))
    for loc in b:
        got = {k: v for k, v in cards[loc].items() if not callable(v)}
        want = {k: v for k, v in ref_cards[loc].items() if not callable(v)}
        assert got == want, loc
    # B's colours judged against B's own expected colours are not red.
    assert not any(after["overlay"][x][0] is True for x in b)
    # Strip C holds no reading and is unread; nothing of the swipe is C's.
    assert not c & set(after["overlay"])
    assert not c & set(after["card_locs"])
    assert not c & set(after["nb_readings"])
    assert tab._progress_measured() == 2 * PER
    # C counts as unread (C8 is a fill-up square, never counted)
    assert {f"C{k}" for k in range(1, PER)} <= tab._manager._unread_locs


@pytest.mark.parametrize("choice", ["keep", "closed"])
def test_keep_and_closing_count_it_as_c_and_move_on(qapp, tmp_path,
                                                    monkeypatch, checks,
                                                    choice):
    """"Keep, it is strip C" (and closing the window): judged as C, nothing
    sent, so the engine's own move to the next unread strip (D) stands."""
    tab = _filing_tab(tmp_path, monkeypatch, checks)
    sent = _knuts(qapp, tab, monkeypatch, choice)
    assert sent == []
    ov = _overlay(tab)
    # B's colours against C's expected colours: red (by the limit, or by the
    # neighbour check, which may take neighbours from C itself: 7 of 8).
    assert sum(ov[x][0] is True for x in _locs("C")) >= PER - 1
    assert tab._manager.set_aside_locs() == set()


def test_reread_is_unchanged(qapp, tmp_path, monkeypatch, checks):
    """"Re-read strip C": the reading is set aside unjudged, C is unread and
    the reader goes back to C, whose next reading replaces it."""
    tab = _filing_tab(tmp_path, monkeypatch, checks)
    sent = _knuts(qapp, tab, monkeypatch, "reread")
    assert sent == [{"cmd": "goto", "strip": "C"}]
    assert not set(_locs("C")) & set(_overlay(tab))
    assert tab._manager.set_aside_locs() == {f"C{k}" for k in range(1, PER)}


def test_the_closing_summary_says_counted_as_b(qapp, tmp_path, monkeypatch):
    from workflow import measurement_messages as M
    tab = _filing_tab(tmp_path, monkeypatch)
    _knuts(qapp, tab, monkeypatch, "was_like")
    assert tab._read_twice_log == [("C", "B", "was_like")]
    assert M._SUM_TWICE_WAS_LIKE.format(strip="C", like="B") == \
        "C (like B, counted as B)"


def test_an_engine_without_file_as_keeps_the_old_way(qapp, tmp_path,
                                                     monkeypatch):
    """A helper that does not announce file_as (built before 4.3.5) is never
    sent it: the reading is set aside and the reader goes to B, as 4.3.4."""
    tab = _tab(tmp_path, monkeypatch)
    _run(qapp, tab, [_sread("A"), _sready("B"), _sread("B"), _sready("C")])
    _answer(monkeypatch, "was_like")
    tab._sent.clear()
    _run(qapp, tab, [_swipe("C", "B")])
    assert _commands(tab) == [{"cmd": "goto", "strip": "B"}]


def test_a_refused_file_as_leaves_the_reading_set_aside(qapp, tmp_path,
                                                        monkeypatch):
    tab = _filing_tab(tmp_path, monkeypatch)
    _run(qapp, tab, [_sread("A"), _sready("B"), _sread("B"), _sready("C")])
    _answer(monkeypatch, "was_like")
    _run(qapp, tab, [_swipe("C", "B")])
    before = _overlay(tab)
    _feed(tab._manager, {"event": "file_as_refused", "strip": "C",
                         "as": "B"})
    assert _overlay(tab) == before
    assert tab._manager.set_aside_locs() == {f"C{k}" for k in range(1, PER)}


# ---- the window's words ---------------------------------------------------


def test_the_window_says_what_i_read_strip_b_does():
    from workflow import measurement_messages as M
    _title, body = M.M_STRIP_READ_TWICE.render(strip="C", like="B")
    assert ("I read strip B: this reading is counted as strip B and replaces "
            "its earlier reading. The reader stays on strip C, which still "
            "has to be measured.") in body
    assert "the reader goes to strip B" not in body


# ---- the real engine, on its replay instrument ------------------------------

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, ReplaySession, write_replay_script  # noqa: E402


@pytest.mark.slow
@pytest.mark.skipif(not HELPER.exists(),
                    reason="chromiq-chartread helper not built")
def test_the_engine_files_the_reading_as_b_and_saves_it_there(tmp_path):
    """chromiq-chartread itself, -S as ChromIQ runs it: B's colours swiped
    with the reader on C, then the manager's answer to "I read strip B"
    forwarded to the engine. The engine moves the reading to B, the reader
    stays on C (unread), and the saved .ti3 holds the reading under B and
    nothing under C."""
    from workflow.measure_manager import MeasureManager
    from workflow.ti3_analysis import parse_ti3
    targen = shutil.which("targen") or "/Applications/Argyll/bin/targen"
    if not Path(targen).exists():
        pytest.skip("Argyll targen not available")
    base = tmp_path / "chart"
    subprocess.run([targen, "-v0", "-d2", "-G", "-f60", str(base)],
                   check=True, capture_output=True, cwd=tmp_path, timeout=120)
    from workflow.layout_engine.chart import build_chart
    build_chart(base.with_suffix(".ti1"), base, instrument="i1", paper="A4",
                randomize=True)
    replay = tmp_path / "replay.txt"
    write_replay_script(base.with_suffix(".ti2"), replay)

    class _Runner:
        is_running = True

        def __init__(self):
            self.sent = []

        def write_stdin(self, text):
            self.sent.append(text)
    r = _Runner()
    m = MeasureManager(r)
    m._engine_active = True
    m._spot_mode = False
    m._is_resume = False
    m._guided_state = "disabled"
    asked, filed = [], []
    m.strip_read_twice.connect(lambda s, like: asked.append((s, like)))
    m.strip_filed_as.connect(filed.append)
    s = ReplaySession(base, replay, ["-S"])
    try:
        start = s.wait_event("session_start", timeout=60)
        assert start.get("file_as") is True
        _feed(m, start)
        labels = [x["strip"] for x in start["strips"]]
        a, b, c = labels[:3]
        for k, lab in enumerate((a, b, c)):
            i = s.event_index()
            s.send(cmd="swipe", **({"as": b} if k == 2 else {}))
            ev = s.wait_event("strip_read", after=i, timeout=60)
            _feed(m, ev)
            s.wait_event("strip_ready", after=i, timeout=60)
        assert asked == [(c, b)]
        swiped = {p["loc"]: p["xyz"] for p in ev["patches"]}
        r.sent.clear()
        m.answer_read_twice("was_like")
        assert [json.loads(x) for x in r.sent] == [
            {"cmd": "file_as", "strip": c, "as": b}]
        i = s.event_index()
        s.proc.stdin.write(r.sent[0])
        s.proc.stdin.flush()
        moved = s.wait_event("strip_filed_as", after=i, timeout=60)
        ready = s.wait_event("strip_ready", after=i, timeout=60)
        _feed(m, moved)
        # The reader stays on C, which is unread again.
        assert ready["strip"] == c and ready["read"] is False
        # The reading, now under B's locations.
        assert filed and filed[0]["strip"] == b
        got = [p["xyz"] for p in moved["patches"]]
        want = [swiped[f"{c}{n}"] for n in range(1, len(got) + 1)
                if f"{c}{n}" in swiped]
        assert got[:len(want)] == want
        assert all(p["loc"].startswith(b) for p in moved["patches"])
    finally:
        s.proc.kill()
        s.finish()
    data = parse_ti3(base.with_suffix(".ti3"))
    locs = list(data.sample_locs)
    assert not [x for x in locs if x.startswith(c)]
    by_loc = dict(zip(locs, data.xyz.tolist()))
    for p in moved["patches"]:
        if p["loc"] in by_loc:
            assert by_loc[p["loc"]] == pytest.approx(p["xyz"], abs=1e-3)


# ---- the engine takes file_as only at its strip menu (review of fd8415715) --
#
# An instrument reads while "Was a strip read twice?" is open, so when the
# answer comes the engine can be mid-swipe or at a question (a misread's
# retry, an unexpected response, "Done?"). There chromiq-chartread consumes
# the command and drops it (cq_wait_char), measured on the replay instrument:
# no strip_filed_as, no file_as_refused, the reading still under C and B's
# old reading kept, while the window had said "counted as strip B". The
# manager holds the answer and sends it at the next strip menu.

def _bare_manager():
    from workflow.measure_manager import MeasureManager

    class _R:
        is_running = True

        def __init__(self):
            self.sent = []

        def write_stdin(self, text):
            self.sent.append(text)
    r = _R()
    m = MeasureManager(r)
    m._engine_active = True
    m._spot_mode = False
    m._guided_state = "disabled"
    m._engine_files_as = True
    return m, r


@pytest.mark.parametrize("question", [
    {"event": "error", "kind": "misread", "detail": "x"},
    {"event": "strip_warning", "kind": "unexpected_response",
     "worst_de": 40.0},
    {"event": "scan_started"},
])
def test_file_as_waits_for_the_strip_menu(question):
    m, r = _bare_manager()
    _feed(m, {"event": "strip_ready", "strip": "D", "read": False,
              "all_done": False}, question)
    m._read_twice_pending = [("C", "B")]
    m.answer_read_twice("was_like")
    assert not [x for x in r.sent if '"file_as"' in x], \
        "sent while the engine could not take it"
    _feed(m, {"event": "strip_ready", "strip": "D", "read": False,
              "all_done": False})
    assert [json.loads(x) for x in r.sent if '"file_as"' in x] == [
        {"cmd": "file_as", "strip": "C", "as": "B"}]


def test_a_held_file_as_waits_while_that_menu_takes_another_key():
    m, r = _bare_manager()
    _feed(m, {"event": "strip_ready", "strip": "D", "read": False,
              "all_done": False},
          {"event": "error", "kind": "misread", "detail": "x"})
    m._read_twice_pending = [("C", "B")]
    m.answer_read_twice("was_like")
    m._pending_post_retry_key = "n"     # this menu answers with a key first
    _feed(m, {"event": "strip_ready", "strip": "D", "read": False,
              "all_done": False})
    assert not [x for x in r.sent if '"file_as"' in x]
    _feed(m, {"event": "strip_ready", "strip": "E", "read": False,
              "all_done": False})
    assert [json.loads(x) for x in r.sent if '"file_as"' in x] == [
        {"cmd": "file_as", "strip": "C", "as": "B"}]


@pytest.mark.slow
@pytest.mark.skipif(not HELPER.exists(),
                    reason="chromiq-chartread helper not built")
def test_the_engine_files_it_after_a_misread_of_the_next_strip(tmp_path):
    """The real engine: B's colours swiped on C, then D misread while the
    window is open, then "I read strip B". The manager waits for the menu
    the misread's retry brings, and the engine moves the reading to B."""
    from workflow.measure_manager import MeasureManager
    from workflow.ti3_analysis import parse_ti3
    targen = shutil.which("targen") or "/Applications/Argyll/bin/targen"
    if not Path(targen).exists():
        pytest.skip("Argyll targen not available")
    base = tmp_path / "chart"
    subprocess.run([targen, "-v0", "-d2", "-G", "-f100", str(base)],
                   check=True, capture_output=True, cwd=tmp_path, timeout=120)
    from workflow.layout_engine.chart import build_chart
    build_chart(base.with_suffix(".ti1"), base, instrument="i1", paper="A4",
                randomize=True)
    replay = tmp_path / "replay.txt"
    write_replay_script(base.with_suffix(".ti2"), replay)

    class _Runner:
        is_running = True

        def __init__(self, s):
            self.s = s
            self.sent = []

        def write_stdin(self, text):        # straight to the engine
            self.sent.append(text)
            self.s.proc.stdin.write(text)
            self.s.proc.stdin.flush()
    s = ReplaySession(base, replay, ["-S"])
    r = _Runner(s)
    m = MeasureManager(r)
    m._engine_active = True
    m._spot_mode = False
    m._is_resume = False
    m._guided_state = "disabled"
    asked = []
    m.strip_read_twice.connect(lambda st, like: asked.append((st, like)))
    try:
        start = s.wait_event("session_start", timeout=60)
        _feed(m, start)
        a, b, c, d = [x["strip"] for x in start["strips"]][:4]
        for k in range(3):
            i = s.event_index()
            s.send(cmd="swipe", **({"as": b} if k == 2 else {}))
            _feed(m, s.wait_event("strip_read", after=i, timeout=60))
            _feed(m, s.wait_event("strip_ready", after=i, timeout=60))
        assert asked == [(c, b)]
        # D swiped while the window is open, and misread.
        i = s.event_index()
        s.send(cmd="swipe", fault="misread")
        _feed(m, s.wait_event("error", after=i, timeout=60))
        m.answer_read_twice("was_like")
        assert not [x for x in r.sent if '"file_as"' in x]
        # The misread's retry: the engine is back at its menu.
        i = s.event_index()
        s.send(cmd="retry")
        _feed(m, s.wait_event("strip_ready", after=i, timeout=60))
        moved = s.wait_event("strip_filed_as", after=i, timeout=60)
        ready = s.wait_event("strip_ready", after=i, strip=c, timeout=60)
        assert moved["strip"] == b and moved["from"] == c
        assert ready["read"] is False
    finally:
        s.proc.kill()
        s.finish()
    locs = list(parse_ti3(base.with_suffix(".ti3")).sample_locs)
    assert not [x for x in locs if x.startswith(c)]
    assert len([x for x in locs if x.startswith(b)]) > 0
