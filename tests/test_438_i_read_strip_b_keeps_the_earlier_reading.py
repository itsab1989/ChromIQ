""""I read strip B" gives the strip the swipe came off its earlier reading
back (Basti, 2026-10-21), and Build Profile asks before it builds from a
measurement with patches missing.

Knut's run 1 of 2026-10-20 (chromiq.log): strip V read at 16:01. At 16:06
the reader was on V and the swipe was strip U; the engine filed it under V,
over V's good reading. "Was a strip read twice?" asked, Knut answered "I read
strip U", the engine moved the swipe onto U and left V with NOTHING: its
16:01 reading was already gone. At 16:07 the same again. He ended with Save
partial, and the profile was built from 1917 of the chart's 1944 patches with
no word on screen.

Basti's ruling (2026-10-21):

1. When "I read strip B" moves a swipe away from strip A and A had an earlier
   VALID reading, A keeps (gets back) that reading. Only a strip that had no
   valid reading stays unread.
2. Before a profile is built from a measurement with strips or patches
   unread, a window names the strips and the count, with Go back and measure
   (the default) or Build anyway.
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

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, ReplaySession, write_replay_script  # noqa: E402


def _targen():
    t = shutil.which("targen") or "/Applications/Argyll/bin/targen"
    if not Path(t).exists():
        pytest.skip("Argyll targen not available")
    return t


def _chart(tmp_path, n=60):
    base = tmp_path / "chart"
    subprocess.run([_targen(), "-v0", "-d2", "-G", f"-f{n}", str(base)],
                   check=True, capture_output=True, cwd=tmp_path, timeout=120)
    from workflow.layout_engine.chart import build_chart
    build_chart(base.with_suffix(".ti1"), base, instrument="i1", paper="A4",
                randomize=True)
    replay = tmp_path / "replay.txt"
    write_replay_script(base.with_suffix(".ti2"), replay)
    return base, replay


class _Runner:
    is_running = True

    def __init__(self):
        self.sent = []

    def write_stdin(self, text):
        self.sent.append(text)


def _manager():
    from workflow.measure_manager import MeasureManager
    r = _Runner()
    m = MeasureManager(r)
    m._engine_active = True
    m._spot_mode = False
    m._is_resume = False
    m._guided_state = "disabled"
    return m, r


def _feed(m, ev):
    m._handle_engine_line(json.dumps(ev), lambda _l: None)


def _swipe(s, m, **kw):
    i = s.event_index()
    s.send(cmd="swipe", **kw)
    ev = s.wait_event("strip_read", after=i, timeout=60)
    _feed(m, ev)
    ready = s.wait_event("strip_ready", after=i, timeout=60)
    _feed(m, ready)
    return ev


def _goto(s, m, strip):
    i = s.event_index()
    s.send(cmd="goto", strip=strip)
    ready = s.wait_event("strip_ready", after=i, timeout=60)
    _feed(m, ready)
    return ready


def _answer_was_like(s, m, r):
    r.sent.clear()
    m.answer_read_twice("was_like")
    assert len(r.sent) == 1
    cmd = json.loads(r.sent[0])
    i = s.event_index()
    s.proc.stdin.write(r.sent[0])
    s.proc.stdin.flush()
    moved = s.wait_event("strip_filed_as", after=i, timeout=60)
    ready = s.wait_event("strip_ready", after=i, timeout=60)
    _feed(m, moved)
    _feed(m, ready)
    return cmd, moved, ready


def _ti3(base):
    from workflow.ti3_analysis import parse_ti3
    data = parse_ti3(base.with_suffix(".ti3"))
    return dict(zip(list(data.sample_locs), data.xyz.tolist()))


# ---- 1. the real engine, on its replay instrument ------------------------

@pytest.mark.skipif(not HELPER.exists(),
                    reason="chromiq-chartread helper not built")
def test_knuts_run_1_twice_the_strip_keeps_its_earlier_reading(tmp_path):
    """A, B, C read; the reader back on C (read); B's colours swiped there,
    answered "I read strip B" -- twice, as Knut did with V and U. The engine
    moves the swipe onto B and gives C the reading it had before, both times;
    the saved .ti3 holds C's first reading under C."""
    base, replay = _chart(tmp_path)
    m, r = _manager()
    lost = []
    m.earlier_reading_lost.connect(lost.append)
    asked = []
    m.strip_read_twice.connect(lambda s_, like: asked.append((s_, like)))
    s = ReplaySession(base, replay, ["-S"])
    try:
        start = s.wait_event("session_start", timeout=60)
        assert start.get("file_as_keeps_earlier") is True, \
            "this engine cannot give a strip its earlier reading back"
        _feed(m, start)
        a, b, c = [x["strip"] for x in start["strips"][:3]]
        first = {}
        for lab in (a, b, c):
            ev = _swipe(s, m)
            first[ev["strip"]] = {p["loc"]: p["xyz"] for p in ev["patches"]}
        assert set(first) == {a, b, c}
        for round_ in (1, 2):
            _goto(s, m, c)
            ev = _swipe(s, m, **{"as": b})
            assert asked[-1] == (c, b), asked
            assert m.earlier_reading_comes_back(c), \
                f"round {round_}: C had a valid reading before the swipe"
            cmd, moved, ready = _answer_was_like(s, m, r)
            assert cmd == {"cmd": "file_as", "strip": c, "as": b,
                           "earlier": "keep"}
            assert moved.get("restored") is True, moved
            back = {p["loc"]: p["xyz"] for p in moved["from_patches"]}
            for loc, xyz in first[c].items():
                assert back[loc] == pytest.approx(xyz, abs=1e-3), loc
            # The reader stays on C, which is READ again.
            assert ready["strip"] == c and ready["read"] is True
            # The manager: C counts as read, is not set aside, compares as C.
            assert not [x for x in m._unread_locs if x.startswith(c)
                        and x[len(c):].isdigit()]
            assert c not in m._suspect_strips
            assert m.set_aside_strips() == []
        assert lost == []
    finally:
        s.proc.kill()
        s.finish()
    saved = _ti3(base)
    for loc, xyz in first[c].items():
        assert saved[loc] == pytest.approx(xyz, abs=1e-3), loc


@pytest.mark.skipif(not HELPER.exists(),
                    reason="chromiq-chartread helper not built")
def test_a_strip_with_no_earlier_reading_stays_unread(tmp_path):
    """A read; the reader on B (never read); A's colours swiped there, "I
    read strip A": B had nothing to get back, so it is unread, as in 4.3.5,
    and the command does not ask for an earlier reading."""
    base, replay = _chart(tmp_path)
    m, r = _manager()
    s = ReplaySession(base, replay, ["-S"])
    try:
        start = s.wait_event("session_start", timeout=60)
        _feed(m, start)
        a, b = [x["strip"] for x in start["strips"][:2]]
        _swipe(s, m)                    # A
        assert not m.earlier_reading_comes_back(b)
        _swipe(s, m, **{"as": a})       # on B, A's colours
        assert m.read_twice_pending() == (b, a)
        assert not m.earlier_reading_comes_back(b)
        cmd, moved, ready = _answer_was_like(s, m, r)
        assert cmd == {"cmd": "file_as", "strip": b, "as": a}
        assert moved.get("restored") is False
        assert ready["strip"] == b and ready["read"] is False
        assert b in m.set_aside_strips()
    finally:
        s.proc.kill()
        s.finish()
    assert not [x for x in _ti3(base) if x.startswith(b)
                and x[len(b):].isdigit()]


@pytest.mark.skipif(not HELPER.exists(),
                    reason="chromiq-chartread helper not built")
def test_an_old_style_file_as_still_leaves_the_strip_unread(tmp_path):
    """The command without "earlier" (what 4.3.5 to 4.3.8 beta 3 send, and
    what is sent when the strip's reading was not valid) does what it always
    did: the strip it came off is unread."""
    base, replay = _chart(tmp_path)
    s = ReplaySession(base, replay, ["-S"])
    try:
        start = s.wait_event("session_start", timeout=60)
        a, b, c = [x["strip"] for x in start["strips"][:3]]
        for _ in range(3):
            i = s.event_index()
            s.send(cmd="swipe")
            s.wait_event("strip_ready", after=i, timeout=60)
        i = s.event_index()
        s.send(cmd="goto", strip=c)
        s.wait_event("strip_ready", after=i, timeout=60)
        i = s.event_index()
        s.send(cmd="swipe", **{"as": b})
        s.wait_event("strip_ready", after=i, timeout=60)
        i = s.event_index()
        s.send(cmd="file_as", strip=c, **{"as": b})
        moved = s.wait_event("strip_filed_as", after=i, timeout=60)
        ready = s.wait_event("strip_ready", after=i, timeout=60)
        assert moved.get("restored") is not True
        assert ready["strip"] == c and ready["read"] is False
    finally:
        s.proc.kill()
        s.finish()


@pytest.mark.skipif(not HELPER.exists(),
                    reason="chromiq-chartread helper not built")
def test_the_earlier_reading_survives_a_resume(tmp_path):
    """C read in an earlier session (on disk). Resumed; C's reading swiped
    over with B's colours and "I read strip B" answered: C gets back the
    reading the file held."""
    base, replay = _chart(tmp_path)
    s = ReplaySession(base, replay, ["-S"])
    try:
        start = s.wait_event("session_start", timeout=60)
        labels = [x["strip"] for x in start["strips"]]
        for _ in range(3):
            i = s.event_index()
            s.send(cmd="swipe")
            s.wait_event("strip_ready", after=i, timeout=60)
        s.send(cmd="done")
        s.proc.wait(timeout=60)
    finally:
        if s.proc.poll() is None:
            s.proc.kill()
        s.finish()
    a, b, c = labels[:3]
    before = _ti3(base)
    m, r = _manager()
    m._is_resume = True
    s = ReplaySession(base, replay, ["-S", "-r"])
    try:
        start = s.wait_event("session_start", timeout=60)
        _feed(m, start)
        assert m._strip_has_valid_reading(c)
        _goto(s, m, c)
        _swipe(s, m, **{"as": b})
        assert m.read_twice_pending() == (c, b)
        assert m.earlier_reading_comes_back(c)
        cmd, moved, ready = _answer_was_like(s, m, r)
        assert cmd.get("earlier") == "keep" and moved.get("restored") is True
        assert ready["strip"] == c and ready["read"] is True
    finally:
        s.proc.kill()
        s.finish()
    after = _ti3(base)
    for loc, xyz in before.items():
        if loc.startswith(c) and loc[len(c):].isdigit():
            assert after[loc] == pytest.approx(xyz, abs=1e-3), loc


# ---- 2. the manager, without an engine ------------------------------------

def _session(m, strips=("A", "B", "C"), per=3, keeps=True, chart=None):
    m._loc_strip = {f"{s}{k}": s for s in strips for k in range(1, per + 1)}
    m._read_order = list(m._loc_strip)
    ev = {"event": "session_start", "file_as": True,
          "strips": [{"strip": s, "read": False} for s in strips]}
    if keeps:
        ev["file_as_keeps_earlier"] = True
    m._engine_files_as = True
    m._engine_keeps_earlier = keeps
    m._session_strips = ev["strips"]
    m._unread_locs = set(m._loc_strip)


def _read(m, strip, per=3):
    _feed(m, {"event": "strip_read", "strip": strip,
              "patches": [{"loc": f"{strip}{k}"} for k in range(1, per + 1)]})


def test_the_command_asks_for_the_earlier_reading_only_when_it_was_valid():
    m, r = _manager()
    _session(m)
    _read(m, "A")
    _read(m, "C")
    # C read before: its next swipe replaces a valid reading.
    _read(m, "C")
    assert m.earlier_reading_comes_back("C")
    m._read_twice_pending = [("C", "B")]
    m._suspect_strips["C"] = "B"
    m.answer_read_twice("was_like")
    assert json.loads(r.sent[-1]) == {"cmd": "file_as", "strip": "C",
                                      "as": "B", "earlier": "keep"}
    # B never read: nothing to give back.
    r.sent.clear()
    _read(m, "B")
    assert not m.earlier_reading_comes_back("B")
    m._read_twice_pending = [("B", "A")]
    m._suspect_strips["B"] = "A"
    m.answer_read_twice("was_like")
    assert json.loads(r.sent[-1]) == {"cmd": "file_as", "strip": "B",
                                      "as": "A"}


def test_a_reading_already_set_aside_is_never_given_back():
    """C's swipe was B's and was answered Re-read (set aside); the next swipe
    on C is B's again and answered "I read strip B": what the engine holds
    as C's earlier reading is the set-aside one, so nothing is asked back."""
    m, r = _manager()
    _session(m)
    _read(m, "C")
    _read(m, "C")
    m._read_twice_pending = [("C", "B")]
    m._suspect_strips["C"] = "B"
    m.answer_read_twice("reread")
    _read(m, "C")
    m._suspect_strips["C"] = "B"
    m._read_twice_pending = [("C", "B")]
    assert not m.earlier_reading_comes_back("C")
    r.sent.clear()
    m.answer_read_twice("was_like")
    assert "earlier" not in json.loads(r.sent[-1])


def test_an_old_engine_is_never_asked():
    m, r = _manager()
    _session(m, keeps=False)
    _read(m, "C")
    _read(m, "C")
    assert not m.earlier_reading_comes_back("C")


def test_a_held_answer_asks_for_it_when_it_is_sent():
    m, r = _manager()
    _session(m)
    _read(m, "C")
    _read(m, "C")
    m._read_twice_pending = [("C", "B")]
    m._suspect_strips["C"] = "B"
    m._scan_in_progress = True          # mid-swipe: the answer waits
    m.answer_read_twice("was_like")
    assert r.sent == [] and m._held_file_as == [("C", "B")]
    m._scan_in_progress = False
    m._flush_held_file_as()
    assert json.loads(r.sent[-1]).get("earlier") == "keep"


@pytest.mark.parametrize("how", ["refused", "not_restored", "ending"])
def test_when_it_does_not_come_back_the_strip_is_unread(how):
    m, r = _manager()
    _session(m)
    lost = []
    m.earlier_reading_lost.connect(lost.append)
    _read(m, "C")
    _read(m, "C")
    m._read_twice_pending = [("C", "B")]
    m._suspect_strips["C"] = "B"
    if how == "ending":
        m._scan_in_progress = True
        m.answer_read_twice("was_like")
        m._an_ending_is_under_way = lambda: True
        m._scan_in_progress = False
        m._flush_held_file_as()
    else:
        m.answer_read_twice("was_like")
        if how == "refused":
            _feed(m, {"event": "file_as_refused", "strip": "C", "as": "B"})
        else:
            _feed(m, {"event": "strip_filed_as", "strip": "B", "from": "C",
                      "restored": False,
                      "patches": [{"loc": f"B{k}", "xyz": [10, 10, 10]}
                                  for k in (1, 2, 3)]})
    assert lost == ["C"]
    assert "C" in m.set_aside_strips()


def test_when_it_comes_back_the_strip_is_read_and_trusted():
    m, r = _manager()
    _session(m)
    filed = []
    m.strip_filed_as.connect(filed.append)
    _read(m, "C")
    _read(m, "C")
    m._read_twice_pending = [("C", "B")]
    m._suspect_strips["C"] = "B"
    m.answer_read_twice("was_like")
    assert "C" in m.set_aside_strips()      # until the engine says so
    _feed(m, {"event": "strip_filed_as", "strip": "B", "from": "C",
              "restored": True,
              "from_patches": [{"loc": f"C{k}", "xyz": [20, 20, 20]}
                               for k in (1, 2, 3)],
              "patches": [{"loc": f"B{k}", "xyz": [10, 10, 10]}
                          for k in (1, 2, 3)]})
    assert m.set_aside_strips() == []
    assert not {"C1", "C2", "C3"} & m._unread_locs
    assert "C" in m._measured_strips and "C" not in m._suspect_strips
    assert filed[-1]["restored_from"][0]["loc"] == "C1"


# ---- 3. the Measure tab ---------------------------------------------------

def test_the_tab_keeps_the_strip_as_it_was_and_says_so(qapp_, tmp_path,
                                                      monkeypatch):
    """The 4.3.5 harness (test_435), C read before, B's colours swiped on C,
    "I read strip B" with an engine that gives C its reading back: the window
    says C keeps its reading; C's outlines, cards, neighbour readings, yellow
    memory and count are exactly what they were before the swipe."""
    sys.path.insert(0, str(Path(__file__).parent))
    from PyQt6.QtWidgets import QDialog, QLabel, QPushButton

    import test_435_i_read_strip_b_counts_as_b as T
    from test_434b1_read_twice_is_judged_after_the_answer import (
        PER, _locs, _run, _sread, _sready, _state)
    from workflow import measurement_messages as M
    tab = T._filing_tab(tmp_path, monkeypatch)
    tab._manager._engine_keeps_earlier = True
    _run(qapp_, tab, [_sread("A"), _sready("B"), _sread("B"), _sready("C"),
                      _sread("C"), _sready("C")])
    c_first = _sread("C")["patches"]
    before = _state(tab)
    shown = []
    real = QDialog.exec

    def _exec(dlg):
        if dlg.objectName() != "strip_read_twice_window":
            return real(dlg)
        shown.append("\n".join(x.text() for x in dlg.findChildren(QLabel)))
        dlg.findChildren(QPushButton)[1].click()       # I read strip B
        return 1
    monkeypatch.setattr(QDialog, "exec", _exec)
    tab._sent.clear()
    _run(qapp_, tab, [T._swipe("C", "B")])
    cmds = T._commands(tab)
    assert cmds == [{"cmd": "file_as", "strip": "C", "as": "B",
                     "earlier": "keep"}]
    want = M.M_STRIP_READ_TWICE_EARLIER.render(strip="C", like="B")[1]
    assert shown and want in shown[0]
    moved = T._filed_as("B", "C")
    moved["restored"] = True
    moved["from_patches"] = c_first
    T._feed(tab._manager, moved, {"event": "strip_ready", "strip": "C",
                                  "read": True, "all_done": False})
    for _ in range(6):
        qapp_.processEvents()
    after = _state(tab)
    c = set(_locs("C"))
    for loc in c:
        assert after["overlay"].get(loc) == before["overlay"].get(loc), loc
        assert after["judge_history"].get(loc) == \
            before["judge_history"].get(loc), loc
    assert sorted(set(after["nb_readings"]) & c) == \
        sorted(set(before["nb_readings"]) & c)
    assert c <= set(after["progress"])
    assert tab._manager.set_aside_strips() == []
    assert len(c) == PER


@pytest.fixture
def qapp_():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


# ---- 4. Build Profile asks before it builds from an incomplete file -------

def _measured(tmp_path):
    """A chart read completely on the replay instrument, then the .ti3."""
    base, replay = _chart(tmp_path)
    s = ReplaySession(base, replay, ["-S"])
    try:
        start = s.wait_event("session_start", timeout=60)
        labels = [x["strip"] for x in start["strips"]]
        for _ in labels:
            i = s.event_index()
            s.send(cmd="swipe")
            s.wait_event("strip_ready", after=i, timeout=60)
        s.send(cmd="done")
        s.proc.wait(timeout=60)
    finally:
        if s.proc.poll() is None:
            s.proc.kill()
        s.finish()
    return base.with_suffix(".ti3"), labels


@pytest.mark.skipif(not HELPER.exists(),
                    reason="chromiq-chartread helper not built")
def test_missing_readings_names_the_strips(tmp_path):
    from workflow.incomplete_measurement import missing_readings
    from workflow.measurement_state import drop_locations
    ti3, labels = _measured(tmp_path)
    assert missing_readings(ti3) is None            # complete: nothing to say
    v, w = labels[1], labels[2]
    whole = {loc for loc in _ti3(ti3.with_suffix("")) if loc.startswith(v)
             and loc[len(v):].isdigit()}
    drop_locations(ti3, whole | {f"{w}2"})
    gap = missing_readings(ti3)
    assert gap is not None
    assert gap.missing == len(whole) + 1
    assert gap.read == gap.expected - gap.missing
    assert [(g.strip, g.missing) for g in gap.strips] == [(v, len(whole)),
                                                          (w, 1)]
    assert gap.strips[0].total == len(whole)


@pytest.mark.skipif(not HELPER.exists(),
                    reason="chromiq-chartread helper not built")
@pytest.mark.parametrize("button,go", [("Go back and measure", False),
                                       ("Build anyway", True)])
def test_build_profile_asks_and_go_back_builds_nothing(tmp_path, monkeypatch,
                                                       qapp_, button, go):
    from PyQt6.QtWidgets import QMessageBox

    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_profile import TabProfile
    from workflow import measurement_messages as M
    from workflow.measurement_state import drop_locations
    ti3, labels = _measured(tmp_path)
    v = labels[0]
    drop_locations(ti3, {f"{v}{k}" for k in range(1, 40)})
    s = AppSettings()
    tab = TabProfile(ArgyllRunner(s), s)
    seen, asked = [], []
    tab.measure_requested.connect(lambda: asked.append(1))

    def _exec(box):
        seen.append((box.text(), box.informativeText(),
                     box.defaultButton().text()))
        for b in box.buttons():
            if b.text() == button:
                b.click()
        return 0
    monkeypatch.setattr(QMessageBox, "exec", _exec)
    assert tab._confirm_build_from_incomplete(ti3) is go
    assert len(seen) == 1
    title, body, default = seen[0]
    assert title == M.M_BUILD_INCOMPLETE.title
    assert f"Strip {v}:" in body and "Build anyway" in body
    assert default == "Go back and measure"
    assert asked == ([] if go else [1])


def test_every_build_route_asks_first():
    """Build Profile asks before anything is archived or merged, and Run
    printcal before printcal runs."""
    import inspect

    from ui.tabs.tab_profile import TabProfile
    src = inspect.getsource(TabProfile._on_build)
    ask = src.index("self._confirm_build_from_incomplete(")
    for later in ("self._confirm_building_outside_the_selected_run()",
                  "self._confirm_rebuild_over_verifications()",
                  "self._apply_preconditioning_merge(",
                  "self._archive_the_profile_being_replaced(",
                  "self._builder.build("):
        assert ask < src.index(later), later
    src = inspect.getsource(TabProfile._on_printcal_run)
    assert src.index("self._confirm_build_from_incomplete(") < \
        src.index("self._printcal_runner.run(")


def test_the_build_window_names_the_button_the_user_will_see():
    """Review 9 (2026-10-21): M-BUILD-INCOMPLETE(-CAL) told the user to tick
    "Refine / resume existing measurement (-r)" and press "Start
    Measurement", but with that box ticked the button reads "Continue
    Measurement" (TabMeasure._refresh_start_button_label). Every body names
    the label the button really carries then, in every language."""
    from workflow import measurement_messages as M
    tab_src = (Path(__file__).resolve().parents[1] / "ui" / "tabs"
               / "tab_measure.py").read_text(encoding="utf-8")
    assert 'self._start_btn.setText(tr("Continue Measurement"))' in tab_src
    assert 'QCheckBox(tr("Refine / resume existing measurement (-r)")' in tab_src
    bodies = [m.body for m in (M.M_BUILD_INCOMPLETE, M.M_BUILD_INCOMPLETE_CAL)]
    bodies += [m.body_one for m in (M.M_BUILD_INCOMPLETE,
                                    M.M_BUILD_INCOMPLETE_CAL)]
    for body in bodies:
        assert "press Continue Measurement:" in body
        assert "Start Measurement" not in body
    i18n_dir = Path(__file__).resolve().parents[1] / "data" / "i18n"
    for f in sorted(i18n_dir.glob("*.json")):
        cat = json.loads(f.read_text(encoding="utf-8"))
        cont = cat.get("Continue Measurement")
        start = cat.get("Start Measurement")
        for body in bodies:
            got = cat.get(body)
            assert got, f"{f.name}: build-incomplete body not translated"
            assert cont in got, f"{f.name}: does not name {cont!r}"
            assert start not in got, f"{f.name}: still names {start!r}"
