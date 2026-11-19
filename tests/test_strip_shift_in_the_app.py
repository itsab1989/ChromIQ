"""4.3.50: a strip read one patch out at an END is ASKED about, never refused.

The first 4.3.50 build refused such a strip in the helper, with no way to keep
it, and its review showed correct strips refused on every attempt (a strip
starting white, 33 %, 66 % magenta, 40 times in 40; a patch that did not print
at a strip's end). The app already had an approved check for exactly this, the
"Strip may be misaligned" question with Keep it (workflow/slipped_strip.py,
Basti 2026-10-22 / 2026-10-23), which missed the real case of 2026-11-19 only
because that strip's first reading (L* 83.5) is below the L* 85 its short-slip
rule asks of a paper reading.

So there is ONE check. The shift score (workflow/strip_shift.py) is one of its
finders (`slipped_strip.shift_at_an_end`, asked when the old rules find
nothing), and its finding raises the same question with the same answers. The
helper is 4.3.49's again. These tests hold:

* the real kept misread is asked about now, and only the new finder sees it;
* a finding is a question: the strip is kept and judged as slipped (#210), no
  misread, no Strip Read Failed; Keep it keeps it in one click;
* the words claim only what the score measured;
* the four claims the review found unguarded, re-cast for the question:
  (a) the finding must become the question, not a log line or nothing;
  (b) the other-row guard is computed by the session from the chart;
  (c) the ramp (median) guard decides real cases;
  (d) both ends of the strip as filed are judged;
* the review's adversarial correct strips (tests/data/strip_shift_adversarial
  .json: every one was refused by the first build) are at most asked about,
  never refused, and always keepable.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication              # noqa: E402

from workflow import measurement_messages as M        # noqa: E402
from workflow import slipped_strip as SS              # noqa: E402
from workflow import strip_shift as T                 # noqa: E402

DATA = Path(__file__).parent / "data"
ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _regression():
    return json.loads((DATA / "strip_shift_regression.json").read_text(encoding="utf-8"))["strips"]


def _adversarial():
    return json.loads((DATA / "strip_shift_adversarial.json").read_text(encoding="utf-8"))["strips"]


def _case2():
    return next(s for s in _regression() if s["note"].startswith("case 2"))


def _event(strip, read, exp):
    return {"event": "strip_read", "strip": strip, "reversed": False,
            "worst_de": 0.0, "misaligned": 0,
            "patches": [{"loc": f"{strip}{i + 1}", "xyz": list(r), "exyz": list(e)}
                        for i, (r, e) in enumerate(zip(read, exp))]}


def _manager(paper=None, rows=None):
    from workflow.measure_manager import MeasureManager
    sys.path.insert(0, str(Path(__file__).parent))
    from test_knut_5956210745_next_strip_after_a_read import _Runner
    m = MeasureManager(_Runner())
    m._engine_active = True
    m._guided_state = "disabled"
    m._safenet_on = True
    m._design_paper_xyz = paper
    m._design_xyz_rows = rows or {}
    return m


def _feed(m, ev):
    from test_knut_5956210745_next_strip_after_a_read import _feed as feed
    asked, kept, failed = [], [], []
    m.strip_partly_misaligned.connect(asked.append)
    m.strip_measured.connect(lambda e: kept.append(int(e.get("misaligned") or 0)))
    m.strip_error.connect(failed.append)
    feed(m, ev)
    return asked, kept, failed


# ---- 1. the real case -----------------------------------------------------------

def test_the_kept_misread_of_2026_11_19_is_asked_about_now(qapp):
    """FAILS ON 4.3.49 (no shift finder: nothing asked) and on the first 4.3.50
    build (refused in the helper, never reaching the question). The i1Pro 2
    dual-scan strip: the white run-up read as A1 (L* 83.5), A1 and A2 one
    place on, A3's colour lost."""
    st = _case2()
    m_lab = [SS.xyz_to_lab(x) for x in st["read"]]
    e_lab = [SS.xyz_to_lab(x) for x in st["exp"]]
    assert SS.find_slipped_run(m_lab, e_lab) is None      # the old rules miss it
    assert 83.0 < m_lab[0][0] < 85.0                       # why: below L* 85
    m = _manager(paper=st["paper"])
    asked, kept, failed = _feed(m, _event("A", st["read"], st["exp"]))
    assert failed == [] and kept == [1], "kept, and judged as slipped (#210)"
    assert len(asked) == 1
    f = asked[0]
    assert (f["shift_k"], f["offset"], f["first"], f["last"], f["whole"]) == \
        (3, 1, "A1", "A3", False)
    assert f["best"] < f["base"]


def test_every_real_misread_of_the_fixture_is_asked_and_no_correct_strip(qapp):
    """The first builder's 7 real misreads: 6 were already asked by the old
    rules, the 7th (case 2) by the new finder. Of the 400 correct strips (the
    150 hardest by shift score among them) none is asked."""
    for st in _regression():
        m = _manager(paper=st["paper"])
        asked, kept, failed = _feed(m, _event("A", st["read"], st["exp"]))
        assert failed == [] and len(kept) == 1
        assert len(asked) == (1 if st["label"] == "misread" else 0), st["note"]


# ---- 2. a question, never a refusal -------------------------------------------

def test_the_helper_refuses_nothing_of_the_kind():
    """The helper is 4.3.49's: no shift refusal in read_strips, no build token."""
    src = (ROOT / "native/chartread_helper/chromiq_chartread.c").read_text(encoding="utf-8")
    assert "cq_strip_shift_check" not in src and "moved by one patch" not in src
    assert not (ROOT / "native/chartread_helper/chromiq_shift.c").exists()
    h = (ROOT / "native/chartread_helper/chromiq_ext.h").read_text(encoding="utf-8")
    assert "strip-shift-check" not in h


def _tab(monkeypatch, click=None):
    from PyQt6.QtWidgets import QLabel, QPushButton
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    tab = TabMeasure(ArgyllRunner(s), s)
    seen = {}

    def grab(dlg):
        seen["title"] = dlg.windowTitle()
        seen["labels"] = " ".join(lb.text() for lb in dlg.findChildren(QLabel))
        seen["buttons"] = [b.text() for b in dlg.findChildren(QPushButton)]
        if click:
            next(b for b in dlg.findChildren(QPushButton) if b.text() == click).click()
        return 0
    monkeypatch.setattr(tab, "_exec_measurement_window", grab)
    went = []
    monkeypatch.setattr(tab._manager, "goto_strip", went.append)
    return tab, seen, went


def _finding(k, late=True):
    st = _case2()
    m = _manager(paper=st["paper"])
    if k == 1:
        read, exp = _unprinted_end_strip(late)
    else:
        read, exp = st["read"], st["exp"]
        if not late:
            read, exp = read[::-1], exp[::-1]
    asked, _kept, _failed = _feed(m, _event("C", read, exp))
    assert len(asked) == 1 and asked[0]["shift_k"] == (k if k == 1 else 3)
    return asked[0]


@pytest.mark.parametrize("late", (True, False))
def test_keep_it_keeps_the_reading_in_one_click(qapp, monkeypatch, late):
    tab, seen, went = _tab(monkeypatch, click="Keep it")
    tab._on_strip_partly_misaligned(_finding(3, late))
    assert seen["title"] == "Strip may be misaligned"
    assert seen["buttons"][:2] == ["Re-measure this strip", "Keep it"]
    assert "Stop" in seen["buttons"]
    assert went == [] and "C" in tab._slip_kept_strips
    tab.deleteLater()


def test_re_measure_goes_back_to_the_strip(qapp, monkeypatch):
    tab, _seen, went = _tab(monkeypatch, click="Re-measure this strip")
    tab._on_strip_partly_misaligned(_finding(3))
    assert went == ["C"]
    tab.deleteLater()


# ---- 3. the words ------------------------------------------------------------------

def test_the_words_claim_only_what_the_score_measured(qapp, monkeypatch):
    """Review S3: the first build's text said "the first one looks like the
    white paper" on findings that never tested it."""
    tab, seen, _went = _tab(monkeypatch)
    tab._on_strip_partly_misaligned(_finding(3))
    t = seen["labels"]
    assert M.M_STRIP_ENDS_SHIFTED_LATE.title.format(strip="C") in t
    assert "patches C1 to C3" in t
    assert "came out with the colour of the white paper" not in t
    assert "ChromIQ compared only these readings" in t
    assert "A print whose colours are far from" in t
    tab._on_strip_partly_misaligned(_finding(3, late=False))
    assert M.M_STRIP_ENDS_SHIFTED_EARLY.title.format(strip="C") in seen["labels"]
    tab._on_strip_partly_misaligned(_finding(1))
    t = seen["labels"]
    assert M.M_STRIP_END_PAPER_LATE.title.format(strip="C") in t
    assert "did not print" in t and "Look at patch C1" in t
    tab._on_strip_partly_misaligned(_finding(1, late=False))
    assert M.M_STRIP_END_PAPER_EARLY.title.format(strip="C") in seen["labels"]
    tab.deleteLater()


def test_the_texts_are_proposed_and_have_no_em_dash():
    for m in (M.M_STRIP_ENDS_SHIFTED_LATE, M.M_STRIP_ENDS_SHIFTED_EARLY,
              M.M_STRIP_END_PAPER_LATE, M.M_STRIP_END_PAPER_EARLY):
        assert m.id in M.PROPOSED
        assert "—" not in m.title + m.body
    for gone in ("M_STRIP_FAILED_SHIFTED_START", "M_STRIP_FAILED_SHIFTED_END",
                 "M_STRIP_SHIFT_REFUSED", "M_STRIP_SHIFT_REFUSED_PAPER"):
        assert not hasattr(M, gone)


# ---- 4. the claims the review found unguarded -----------------------------------

def _random_rows(rng, n, count):
    from test_strip_shift import _random_strip
    return [_random_strip(n, rng) for _ in range(count)]


def _print(xyz, rng):
    from test_strip_shift import _print as pr
    return pr(xyz, rng, True)


def test_a_finding_becomes_the_question_not_only_a_log_line(qapp):
    """(a) The first build's verdict could be turned into a warning and
    every test still passed. Here the finding must reach the window AND mark
    the strip, and a correct reading of the same strip must ask nothing."""
    st = _case2()
    m = _manager(paper=st["paper"])
    asked, kept, _f = _feed(m, _event("A", st["read"], st["exp"]))
    assert asked and kept == [1]
    m2 = _manager(paper=st["paper"])
    exp = st["exp"]
    asked2, kept2, _f = _feed(m2, _event("A", exp, exp))
    assert asked2 == [] and kept2 == [0]


def _wrong_strip_case():
    """A strip of the chart swiped in place of another that the score alone
    calls moved, and that the other-row guard spares."""
    rng = np.random.default_rng(4350)
    from test_strip_shift import PAPER_EXP
    for _ in range(4000):
        rows = _random_rows(rng, 6, 10)
        read = _print(rows[3], rng)              # strip D's colours, filed as A
        if SS.shift_at_an_end(read, rows[0], PAPER_EXP, -1.0) is None:
            continue
        other = T.other_rows_best(read, rows[1:])
        if SS.shift_at_an_end(read, rows[0], PAPER_EXP, other) is None:
            return rows, read, PAPER_EXP
    pytest.fail("no wrong strip the guard decides: the score changed")


def test_the_session_computes_the_other_row_guard_from_the_chart(qapp):
    """(b) The first build passed its wrong-strip test with the other-row
    guard never computed. The session must hand the chart's other rows over:
    with them the wrong strip is not asked about, without them it would be."""
    rows, read, paper = _wrong_strip_case()
    labels = "ABCDEFGHIJ"
    m = _manager(paper=paper, rows={labels[i]: r for i, r in enumerate(rows)})
    asked, kept, _f = _feed(m, _event("A", read, rows[0]))
    assert asked == [] and kept == [0]
    m = _manager(paper=paper, rows={})
    asked, _kept, _f = _feed(m, _event("A", read, rows[0]))
    assert len(asked) == 1


def test_the_session_learns_the_rows_and_the_paper_from_the_ti2(qapp, tmp_path):
    from workflow.measure_manager import MeasureManager
    from test_knut_5956210745_next_strip_after_a_read import _Runner
    ti2 = tmp_path / "c.ti2"
    rows = {"A": [(10.0, 11.0, 12.0), (50.0, 52.0, 40.0)],
            "B": [(90.0, 93.0, 80.0), (20.0, 21.0, 22.0)]}
    body = []
    i = 0
    for s, vals in rows.items():
        for j, v in enumerate(vals):
            i += 1
            body.append(f'{i} {s}{j + 1} 10 20 30 {v[0]} {v[1]} {v[2]}')
    ti2.write_text('CTI2\n\nDESCRIPTOR "x"\nORIGINATOR "x"\nNUMBER_OF_FIELDS 8\n'
                   'BEGIN_DATA_FORMAT\nSAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n'
                   'END_DATA_FORMAT\nNUMBER_OF_SETS 4\nBEGIN_DATA\n' + "\n".join(body)
                   + "\nEND_DATA\n", encoding="utf-8")
    m = MeasureManager(_Runner())
    m._read_order = ["A1", "A2", "B1", "B2"]
    m._loc_strip = {"A1": "A", "A2": "A", "B1": "B", "B2": "B"}
    m._learn_measured_strips(str(ti2))
    assert m._design_xyz_rows == rows
    assert m._design_paper_xyz == (90.0, 93.0, 80.0)


def test_the_ramp_guard_decides_real_cases(qapp, monkeypatch):
    """(c) The first build's ramp tests passed with QMIN off. Two correct
    strips of the review's set (a strip starting on a paper-white patch and
    one starting white, 33 %, 66 %) are kept from the question by the
    median guard alone: with QMIN 0 both would be asked about."""
    cases = [st for st in _adversarial() if st["label"] == "ramp_guard"]
    assert len(cases) == 2
    for st in cases:
        assert SS.shift_at_an_end(st["read"], st["exp"], st["paper"], st["other"]) is None
    monkeypatch.setattr(T, "QMIN", 0.0)
    for st in cases:
        assert SS.shift_at_an_end(st["read"], st["exp"], st["paper"], st["other"]) is not None


def test_both_ends_of_the_strip_as_filed_are_judged(qapp):
    """(d) The first build could drop its reversed-read mirror unnoticed.
    The question judges the strip AS FILED (the helper has already turned a
    strip read from its far end round), so a shift at the filed end must be
    found there, with "early" words, and at the start with "late" ones."""
    st = _case2()
    for late in (True, False):
        read, exp = (st["read"], st["exp"]) if late else (st["read"][::-1], st["exp"][::-1])
        m = _manager(paper=st["paper"])
        asked, _k, _f = _feed(m, _event("A", read, exp))
        f = asked[0]
        assert f["offset"] == (1 if late else -1)
        assert (f["first"], f["last"]) == (("A1", "A3") if late else ("A16", "A18"))


# ---- 5. the review's correct strips -----------------------------------------------

def _unprinted_end_strip(late=True):
    """A correct read of a strip whose end patch did not print: the reading
    is the paper's, its design a strong colour."""
    from test_strip_shift import _random_strip
    rng = np.random.default_rng(5)
    exp = _random_strip(10, rng)
    at = 0 if late else 9
    exp[at] = (30.0, 16.0, 4.0)                 # a deep red, far from paper
    read = [tuple(0.9 * v for v in e) for e in exp]
    read[at] = (88.0, 91.0, 76.0)               # nothing printed there
    return read, exp


def test_a_patch_that_did_not_print_is_asked_about_and_kept(qapp, monkeypatch):
    """The review's deterministic case: refused every time by the first
    build, blaming the movement. Now one question, which names both causes,
    and Keep it keeps it."""
    f = _finding(1)
    assert f["first"] == f["last"] == "C1"
    tab, seen, went = _tab(monkeypatch, click="Keep it")
    tab._on_strip_partly_misaligned(f)
    assert "nozzle is blocked" in seen["labels"]
    assert went == [] and "C" in tab._slip_kept_strips
    tab.deleteLater()


def test_the_reviews_correct_strips_are_never_refused_and_at_most_asked(qapp):
    """Every strip in the file was REFUSED by the first build. Now: none is
    refused (no misread, every one kept), the strips starting white, 33 %,
    66 % and the plain-order ink ramps of chart B are not even asked about,
    and of the others (mostly a print with green and blue swapped) at most the
    71 of 158 measured on 2026-11-20 are asked."""
    asked_by = {"reread": 0, "chartB": 0, "adversarial": 0, "ramp_guard": 0}
    for st in _adversarial():
        m = _manager(paper=st["paper"])
        ev = _event("A", st["read"], st["exp"])
        # the other-row figure of the review's harness, as the session would
        # work it out from the chart
        real = SS.shift_in_strip_read
        try:
            SS.shift_in_strip_read = (lambda p, paper, rows, _o=st["other"]:
                                      SS.shift_at_an_end([q["xyz"] for q in p],
                                                         [q["exyz"] for q in p],
                                                         paper, _o))
            asked, kept, failed = _feed(m, ev)
        finally:
            SS.shift_in_strip_read = real
        assert failed == [] and len(kept) == 1, st["note"]
        asked_by[st["label"]] += len(asked)
    assert asked_by["reread"] == asked_by["chartB"] == asked_by["ramp_guard"] == 0
    assert asked_by["adversarial"] <= 71, asked_by
