"""A reading "Was a strip read twice?" asks about is judged only after the
answer, and for the strip the answer gives it (#182, Knut 6094941512, 4.3.4
beta 1).

Knut, on beta 17: strips A and B read, the reader's arrow on C, strip B read
again without clicking B. "Was a strip read twice?" opened, and behind it the
whole of strip C turned red (the second try: yellow). He answered "I read
strip B"; the arrow moved to B, and strip C stayed red:

    "the neighbour check did not take consideration of the warning message
    'Was a strip read twice?', and should have judged the patches AFTER I
    answered that window, not before ... (the message window gives four
    button options, where the outcome should be correctly done depending on
    what is chosen). The test of the neighbour check must be constructed to
    verify all these choices every time this function is verified."

The cause: the engine files the reading under the strip it was positioned on
(C), and ``strip_measured`` reached the tab, which judged and painted it (patch
error limit, strip test, neighbour check, yellow memory, cards, the progress
count), BEFORE ``strip_read_twice`` asked. The answer then only moved the
reader and told the neighbour check to forget; the outlines, the cards and the
judge's memory of the reading stayed.

What holds now, for every way the window can end (the four of them: Re-read
strip C, I read strip B, Keep, it is strip C, and closing the window, which
keeps the reading as Keep does):

* while the window is open nothing of the reading is judged or drawn: the
  preview, the cards, the neighbour check, the yellow memory and the progress
  count are exactly what they were before the swipe;
* "Keep" and closing: the reading is judged as strip C, exactly as a strip C
  read without the question is judged;
* "Re-read strip C" and "I read strip B": the reading is never judged; strip C
  counts as unread (its earlier reading was replaced by this one in the
  engine), so its patches show no reading, and nothing else changes.

Each case is run both on a fresh measurement and on one whose strip C already
had a reading of its own (Knut's: a re-read of a measured verification).
"""
from __future__ import annotations

import copy
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtCore import QRect  # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QPushButton  # noqa: E402

import sys  # noqa: E402
from pathlib import Path  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from test_knut_5956210745_next_strip_after_a_read import (  # noqa: E402
    _feed, _gotos)

STRIPS = ["A", "B", "C", "D"]
PER = 8

#: The four ways the window ends, and what the reader is sent to.
CHOICES = {
    "reread": (0, ["C"]),        # Re-read strip C
    "was_like": (1, ["B"]),      # I read strip B
    "keep": (2, []),             # Keep, it is strip C
    "closed": (None, []),        # the window closed (X, Escape)
}


#: Which test turns strip C red when B's colours are judged as C: the patch
#: error limit (5, no strip test), or the neighbour check alone (the limit
#: out of reach, every read patch a neighbour). Knut saw the neighbour check.
CHECKS = {
    "limit": {},
    "neighbour": {"patch_read_warn_de_estimated": 200.0,
                  "patch_neighbour_radius_estimated": 100.0,
                  "patch_neighbour_limit_estimated": 3.0},
}

#: Every chart type the window can appear on (any chart ChromIQ's engine
#: reads by strips): each is judged with its own column of Preferences ▸
#: Measurement (review R1 of 4.3.4 beta 1: the first version tested only
#: profiling charts with estimated colours; Knut's was a verification).
KINDS = ("estimated", "accurate", "verification", "calibration")


def _for_kind(check: str, kind: str) -> dict:
    """CHECKS[*check*] in *kind*'s own column of the table."""
    from workflow import misread_settings as MS
    out = {MS.PATCH_ERROR_LIMIT_KEYS[kind]: 5.0,
           MS.STRIP_TEST_KEYS[kind]: False}
    if check == "neighbour":
        out.update({MS.PATCH_ERROR_LIMIT_KEYS[kind]: 200.0,
                    MS.NEIGHBOUR_RADIUS_KEYS[kind]: 100.0,
                    MS.NEIGHBOUR_LIMIT_KEYS[kind]: 3.0})
    return out


@pytest.fixture(params=[(c, k) for c in CHECKS for k in KINDS],
                ids=[f"{c}-{k}" for c in CHECKS for k in KINDS])
def checks(request):
    check, kind = request.param
    return {**_for_kind(check, kind), "_kind": kind}


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


class _Settings:
    def __init__(self, extra=None):
        self._d = {"appearance": "dark", "chartread_engine": "chromiq",
                   # A low patch error limit and no strip test, so a
                   # reading filed under the wrong strip is plainly red.
                   "patch_read_warn_de_estimated": 5.0,
                   "patch_strip_test_estimated": False,
                   **dict(extra or {})}

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value):
        self._d[key] = value


def _rgb(s, k):
    i = STRIPS.index(s)
    return ((37 * i + 11 * k) % 100, (53 * i + 29 * k) % 100,
            (71 * i + 7 * k) % 100)


def _exyz(s, k):
    r, g, b = _rgb(s, k)
    return [0.4 * r + 0.35 * g + 0.2 * b + 2, 0.2 * r + 0.7 * g + 0.1 * b + 2,
            0.02 * r + 0.1 * g + 0.9 * b + 2]


def _mxyz(s, k):
    """Strip *s* as the print reads it: close to its expected colour."""
    return [v * 0.98 for v in _exyz(s, k)]


def _de(e, m):
    from workflow.icc_info import xyz_to_lab
    a = xyz_to_lab(tuple(v / 100 for v in e))
    b = xyz_to_lab(tuple(v / 100 for v in m))
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _sread(strip, like=None):
    """The engine's strip_read for *strip*; with *like*, the colours of strip
    *like* swiped while the reader was on *strip*."""
    src = like or strip
    out = []
    for k in range(1, PER + 1):
        e, m = _exyz(strip, k), _mxyz(src, k)
        out.append({"loc": f"{strip}{k}", "exyz": e, "xyz": m,
                    "de": round(_de(e, m), 3)})
    return {"event": "strip_read", "strip": strip, "patches": out}


def _sready(strip):
    return {"event": "strip_ready", "strip": strip, "read": True,
            "all_done": False}


def _chart(tmp):
    tmp.mkdir(parents=True, exist_ok=True)
    rows, sid = [], 1
    for s in STRIPS:
        for k in range(1, PER + 1):
            # strip C ends in a fill-up square (printtarg's SAMPLE_ID 0):
            # never counted, but swiped with the strip
            rows.append((0 if (s, k) == ("C", PER) else sid, f"{s}{k}",
                         _rgb(s, k)))
            sid += 1
    body = "\n".join(f'{i} "{loc}" {r:.1f} {g:.1f} {b:.1f}'
                     for i, loc, (r, g, b) in rows)
    ti2 = tmp / "chart.ti2"
    ti2.write_text(
        'CTI2\n\nORIGINATOR "ChromIQ layout engine"\nNUMBER_OF_FIELDS 5\n'
        "BEGIN_DATA_FORMAT\nSAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B\n"
        f"END_DATA_FORMAT\nNUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n{body}\n"
        "END_DATA\n", encoding="utf-8")
    return ti2


def _tab(tmp, monkeypatch, settings=None):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    settings = dict(settings or {})
    kind = settings.pop("_kind", None)
    s = _Settings(settings)
    t = TabMeasure(ArgyllRunner(s), s)
    if kind is not None:
        # The chart type, as the chart would decide it (a calibration chart,
        # a verification judged against its profile, ...). The real one
        # still runs: reading the chart's facts sets up the yellow memory.
        real_kind = t._chart_kind

        def _kind():
            real_kind()
            return kind
        t._chart_kind = _kind
    mgr = t._manager
    sent: "list[str]" = []
    mgr._runner.write_stdin = sent.append
    monkeypatch.setattr(type(t._runner), "is_running",
                        property(lambda self: True))
    mgr._engine_active = True
    mgr._spot_mode = False
    mgr._is_resume = False
    mgr._chart_was_complete = False
    mgr._guided_state = "disabled"
    ti2 = _chart(tmp)
    _feed(mgr, {"event": "session_start", "chart": str(ti2),
                "strips": [{"strip": x, "read": False} for x in STRIPS]})
    t._ti1_path = ti2.with_suffix(".ti1")
    t._page_stripe_rects = [[QRect(0, 20 * i, 600, 18)
                             for i in range(len(STRIPS))]]
    t._strips_per_page = [len(STRIPS)]
    t._engine_strips = [{"strip": c} for c in STRIPS]
    t._patch_boxes = [{f"{c}{n}": QRect(22 * (n - 1), 20 * i, 20, 18)
                       for i, c in enumerate(STRIPS)
                       for n in range(1, PER + 1)}]
    t._reset_progress(from_files=False)     # learns the fill-up square
    t._sent = sent
    t._session_live = True
    monkeypatch.setattr(t, "_cue_window", lambda *_a: None)
    return t


def _locs(strip):
    return [f"{strip}{k}" for k in range(1, PER + 1)]


def _overlay(tab):
    """{loc: (flag, measured colour)} of every patch the preview draws."""
    by_box = {(b.x(), b.y()): loc for loc, b in tab._patch_boxes[0].items()}
    return {by_box[(it[0].x(), it[0].y())]: (it[3], it[2].name())
            for it in tab._preview._patch_overlay.get(0, [])}


def _cards(tab):
    by_box = {(b.x(), b.y()): loc for loc, b in tab._patch_boxes[0].items()}
    return {by_box[(b.x(), b.y())]: dict(info)
            for b, info in tab._preview._patch_info.get(0, [])}


def _state(tab):
    """Everything the reading could have changed, to compare before and
    after: outlines, cards (their facts, without the callables), the
    neighbour check's readings and findings, the yellow memory, the progress
    count."""
    cards = {loc: {k: v for k, v in info.items() if not callable(v)}
             for loc, info in _cards(tab).items()}
    nc = getattr(tab, "_nb_check", None)
    judge = tab._flag_judge()
    return {
        "overlay": _overlay(tab),
        "cards": repr(sorted(cards.items())),
        "card_locs": sorted(cards),
        "nb_readings": sorted(getattr(nc, "_rows", {}) or {})
        if nc is not None else [],
        "nb_suspects": sorted(nc.suspects()) if nc is not None else [],
        "judge_history": {loc: len(h) for loc, h in
                          getattr(judge, "_history", {}).items()},
        "progress": sorted(tab._progress_locs),
    }


def _answer_with(monkeypatch, choice, seen):
    """Answer the window with *choice*; *seen* gets the state behind it."""
    real = QDialog.exec

    def _exec(dlg):
        if dlg.objectName() != "strip_read_twice_window":
            return real(dlg)
        seen.append(dlg.parent()._state_for_test())
        button = CHOICES[choice][0]
        if button is None:
            dlg.reject()
            return 0
        dlg.findChildren(QPushButton)[button].click()
        return 1
    monkeypatch.setattr(QDialog, "exec", _exec)


def _run(qapp, tab, events):
    _feed(tab._manager, *events)
    for _ in range(6):
        qapp.processEvents()


def _knuts_sequence(qapp, tab, monkeypatch, choice, *, c_read_before):
    """A and B read (and C, when *c_read_before*), the reader on C, strip
    B's colours swiped there. Returns (state before the swipe, state behind
    the window, state after the answer)."""
    tab._state_for_test = lambda: _state(tab)
    events = [_sread("A"), _sready("B"), _sread("B"), _sready("C")]
    if c_read_before:
        events += [_sread("C"), _sready("C")]
    _run(qapp, tab, events)
    before = _state(tab)
    seen: list = []
    _answer_with(monkeypatch, choice, seen)
    tab._sent.clear()
    _run(qapp, tab, [_sread("C", like="B")])
    assert len(seen) == 1, "Was a strip read twice? did not open"
    return before, seen[0], _state(tab)


def _c_judged_alone(qapp, tmp, monkeypatch, c_read_before, checks):
    """The same reading of C judged as C with no question at all: what Keep
    must give. A fresh tab whose read-twice check never fires."""
    tab = _tab(tmp, monkeypatch, checks)
    tab._manager._check_read_twice = lambda *_a, **_k: None
    events = [_sread("A"), _sready("B"), _sread("B"), _sready("C")]
    if c_read_before:
        events += [_sread("C"), _sready("C")]
    _run(qapp, tab, events + [_sread("C", like="B")])
    return _state(tab)


@pytest.mark.parametrize("c_read_before", [False, True],
                         ids=["fresh", "c_read_before"])
@pytest.mark.parametrize("choice", list(CHOICES))
def test_nothing_is_judged_behind_the_window(qapp, tmp_path, monkeypatch,
                                             choice, c_read_before, checks):
    """Behind the open window strip C (and everything else) is exactly as it
    was before the swipe: no outline, no card, no neighbour reading, no
    yellow memory, no progress."""
    tab = _tab(tmp_path, monkeypatch, checks)
    before, behind, _after = _knuts_sequence(
        qapp, tab, monkeypatch, choice, c_read_before=c_read_before)
    assert behind == before


@pytest.mark.parametrize("c_read_before", [False, True],
                         ids=["fresh", "c_read_before"])
@pytest.mark.parametrize("choice", list(CHOICES))
def test_each_answer_judges_the_reading_where_it_puts_it(
        qapp, tmp_path, monkeypatch, choice, c_read_before, checks):
    tab = _tab(tmp_path / "t", monkeypatch, checks)
    before, _behind, after = _knuts_sequence(
        qapp, tab, monkeypatch, choice, c_read_before=c_read_before)
    assert _gotos(type("R", (), {"sent": tab._sent})()) == CHOICES[choice][1]
    c = set(_locs("C"))
    if choice in ("keep", "closed"):
        # Judged as strip C, exactly as if no question had been asked.
        alone = _c_judged_alone(qapp, tmp_path / "alone", monkeypatch,
                                c_read_before, checks)
        assert after == alone
        # B's colours judged against C's expected colours are red (all of
        # them by the limit; 7 of 8 by the neighbour check, whose
        # neighbours may come from strip C itself, Knut 6078174421).
        assert sum(after["overlay"][x][0] is True for x in c) >= PER - 1
        return
    # Re-read strip C / I read strip B: the reading is never judged, and C
    # holds no reading until it is read again.
    assert not c & set(after["overlay"])
    assert not c & set(after["card_locs"])
    assert not c & set(after["nb_readings"])
    assert not c & set(after["nb_suspects"])
    # Progress counts A and B only: C is unread until it is read again.
    assert tab._progress_measured() == 2 * PER
    # Strips A and B are exactly as they were (no outline turned by it).
    for x in _locs("A") + _locs("B"):
        assert after["overlay"][x] == before["overlay"][x]
    # The yellow memory never took this reading as a reading of C.
    for x in c:
        assert after["judge_history"].get(x, 0) == \
            before["judge_history"].get(x, 0)


@pytest.mark.parametrize("choice", ["reread", "was_like"])
def test_reading_c_again_after_the_answer_is_judged_as_a_first_reading(
        qapp, tmp_path, monkeypatch, choice, checks):
    """After "Re-read strip C" or "I read strip B", the next reading of C is
    judged on its own: the set-aside reading (B's colours) is not an earlier
    reading it could agree with or correct (Knut's second try: yellow)."""
    tab = _tab(tmp_path, monkeypatch, checks)
    _knuts_sequence(qapp, tab, monkeypatch, choice, c_read_before=False)
    _run(qapp, tab, [_sread("C")])
    ov = _overlay(tab)
    assert all(ov[x][0] in (False, None, 0) for x in _locs("C")), ov
    # The swipe of B's colours, filed as C, again: red, not yellow.
    tab2 = _tab(tmp_path / "2", monkeypatch, checks)
    _knuts_sequence(qapp, tab2, monkeypatch, choice, c_read_before=False)
    tab2._manager._check_read_twice = lambda *_a, **_k: None
    _run(qapp, tab2, [_sread("C", like="B")])
    assert sum(_overlay(tab2)[x][0] is True for x in _locs("C")) >= PER - 1


def test_a_question_left_open_when_the_session_ends_draws_nothing(
        qapp, tmp_path, monkeypatch):
    """The measurement ends with the window open: the window goes with it
    (Knut, beta 139), and the held reading is not drawn either; the overlay
    is repainted from the file the session wrote."""
    tab = _tab(tmp_path, monkeypatch)
    _run(qapp, tab, [_sread("A"), _sready("B"), _sread("B"), _sready("C")])
    before = _overlay(tab)
    opened = []
    monkeypatch.setattr(QDialog, "exec", lambda dlg: opened.append(dlg) or 0)
    _feed(tab._manager, _sread("C", like="B"))
    tab._session_live = False
    for _ in range(6):
        qapp.processEvents()
    assert opened == []
    assert _overlay(tab) == before


# --- Review R1 of 4.3.4 beta 1: the window on the LAST strip, and a newer
# reading of the strip while the window is open ---------------------------


def _answering(monkeypatch, choice, during=None):
    """Answer "Was a strip read twice?" with *choice*; *during* runs while
    it is open (the instrument can read while a window asks)."""
    real = QDialog.exec

    def _exec(dlg):
        if dlg.objectName() != "strip_read_twice_window":
            return real(dlg)
        if during is not None:
            during()
        button = CHOICES[choice][0]
        if button is None:
            dlg.reject()
            return 0
        dlg.findChildren(QPushButton)[button].click()
        return 1
    monkeypatch.setattr(QDialog, "exec", _exec)


@pytest.mark.parametrize("choice", list(CHOICES))
def test_the_window_on_the_last_strip(qapp, tmp_path, monkeypatch, choice):
    """A, B, C read, the reader on D (the last strip), C's colours swiped
    there, and the engine says every strip is read before the answer. The
    held reading is not a missing one: no "patches still have no reading"
    line, and the finished window comes after Keep (and closing), never
    after Re-read or I read strip C, which leave D to be read again."""
    tab = _tab(tmp_path, monkeypatch)
    _run(qapp, tab, [_sread("A"), _sready("B"), _sread("B"), _sready("C"),
                     _sread("C"), _sready("D")])
    _answering(monkeypatch, choice)
    lines: "list[str]" = []
    monkeypatch.setattr(tab._log, "appendPlainText", lines.append)
    shown: list = []
    monkeypatch.setattr(tab, "_show_all_stripes_done",
                        lambda: shown.append(True))
    _run(qapp, tab, [_sread("D", like="C"),
                     {"event": "strip_ready", "strip": "D", "read": True,
                      "all_done": True}])
    from PyQt6.QtTest import QTest
    QTest.qWait(1200)           # the finished window's sound gap
    assert not [x for x in lines if "no reading" in x], lines
    if choice in ("keep", "closed"):
        assert shown == [True]
        assert tab._unread_patch_count() == 0
    else:
        assert shown == []
        assert tab._unread_patch_count() == PER


@pytest.mark.parametrize("choice", list(CHOICES))
def test_a_newer_reading_while_the_window_is_open(qapp, tmp_path, monkeypatch,
                                                  choice):
    """The window asks about C; before it is answered, C is read properly.
    That reading is the engine's now and the one the file keeps, whatever the
    answer: it is judged as C at once, and the answer about the older one
    never takes it off the screen."""
    tab = _tab(tmp_path, monkeypatch)
    _run(qapp, tab, [_sread("A"), _sready("B"), _sread("B"), _sready("C")])

    def _read_c_properly():
        _feed(tab._manager, _sread("C"))
        for _ in range(4):
            qapp.processEvents()
    _answering(monkeypatch, choice, during=_read_c_properly)
    _run(qapp, tab, [_sread("C", like="B")])
    ov = _overlay(tab)
    assert tab._manager.set_aside_locs() == set()     # the file keeps C
    assert all(x in ov and ov[x][0] in (False, None, 0) for x in _locs("C"))
    assert tab._progress_measured() == 3 * PER - 1    # C's fill-up square
    assert not tab._read_twice_held
