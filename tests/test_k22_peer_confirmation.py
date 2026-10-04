"""Similar patches confirm each other (Knut, #182 5979886227; beta 9).

*"When separate similar patches get the same reading, then that should count
as a confirmation too ... three of these confirmations of separate patches
with similar colors is enough to learn that the color group has trouble with
being reproduced by the printer."* Built as variant B of the k22 challenge
(``~/Desktop/ChromIQ-work/2026-10-04_beta9/k22_challenge/CHALLENGE.md``):

* two FLAGGED patches read in DIFFERENT strips, expected colours less than
  ΔE*ab 6 apart and errors within ΔE*ab 10 of each other, confirm each other
  (the same yellow as a re-read);
* a range learns at three confirmed patches, re-read and peer in any mix,
  with no ΔE 6 spacing;
* peers are worked out afresh from the readings and the current limit; a
  learned patch never confirms anything;
* a re-read confirmation is lost only to a LIVE clean reading, never to a
  repaint at a higher limit;
* Preferences OK and showing the tab judge the outlines again;
* the memory file stores peers as ``peer``, never loaded back as references;
  Check & Refine leaves them out too (one switch).
"""
from __future__ import annotations

import inspect
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from workflow import confirmed_patches as cp  # noqa: E402
from workflow import patch_flags as pf  # noqa: E402

SHIFT = (5.0, -20.0, 25.0)            # a printer falling short of a blue
BLUE = (33.0, 21.0, -61.0)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def _read(j, loc, exp, shift=SHIFT, *, strip, flagged=True, live=True,
          standout=None):
    m = _add(exp, shift)
    return j.judge(loc, exp, m, pf._norm(shift), flagged, strip=strip,
                   live=live, standout=standout)


# ---- the rule --------------------------------------------------------------------
def test_two_similar_patches_in_different_strips_confirm_each_other():
    j = pf.FlagJudge()
    assert _read(j, "A1", BLUE, strip="A").flag is pf.FLAG_RED
    near = _add(BLUE, (3.0, 2.0, -3.0))                  # ΔE 4.7 apart
    v = _read(j, "F7", near, _add(SHIFT, (4.0, 3.0, -5.0)), strip="F")
    assert v.flag == pf.FLAG_CONFIRMED and v.peer_locs == ("A1",)
    assert v.prev_de is None
    changed = j.rejudge()                                # A1 turns too
    assert changed["A1"].flag == pf.FLAG_CONFIRMED
    assert changed["A1"].peer_locs == ("F7",)
    assert j.confirmed == []                             # no re-read reference


def test_the_same_pair_in_one_strip_stays_red():
    """One strip is one pass of the reader: a smudge can make several of its
    patches wrong alike."""
    j = pf.FlagJudge()
    _read(j, "A1", BLUE, strip="A")
    assert _read(j, "A2", _add(BLUE, (1, 1, 1)), strip="A").flag is pf.FLAG_RED
    j.rejudge()
    assert j._verdicts["A1"].flag is pf.FLAG_RED
    assert j._verdicts["A2"].flag is pf.FLAG_RED
    assert j.peers_of("A1") == []


def test_no_strip_no_peer():
    j = pf.FlagJudge()
    _read(j, "A1", BLUE, strip=None)
    assert _read(j, "F1", BLUE, strip=None).flag is pf.FLAG_RED


@pytest.mark.parametrize("d_exp, d_shift, peers", [
    (5.99, 0.0, True),
    (6.0, 0.0, False),                  # expected colours 6 apart: not similar
    (0.0, 10.0, True),                  # errors exactly 10 apart: alike
    (0.0, 10.01, False),
])
def test_the_boundaries(d_exp, d_shift, peers):
    assert pf.PEER_EXPECTED_DE == 6.0
    assert pf.PEER_SHIFT_DE == pf.SHIFT_TOLERANCE_DE == 10.0
    j = pf.FlagJudge()
    _read(j, "A1", BLUE, strip="A")
    other = _add(BLUE, (d_exp, 0.0, 0.0))
    # the measured colour moves with the expected one, plus d_shift
    v = _read(j, "B1", other, _add(SHIFT, (0.0, d_shift, 0.0)), strip="B")
    assert (v.flag == pf.FLAG_CONFIRMED) is peers


def test_an_unflagged_patch_confirms_nothing():
    j = pf.FlagJudge()
    _read(j, "A1", BLUE, strip="A", flagged=False)
    assert _read(j, "B1", BLUE, strip="B").flag is pf.FLAG_RED


# ---- learning --------------------------------------------------------------------
MAGENTA = {"F13": (61.0, 94.3, -78.5), "AV17": (61.2, 93.6, -78.1),
           "BA13": (58.9, 92.4, -81.9), "BM13": (61.1, 94.0, -78.3)}


def test_knuts_four_magenta_corner_patches_teach_their_range():
    """Beta 8 said these four count as one (all within ΔE 4.7). Knut
    5979886227: wrong. Read once each, in four strips, they confirm each
    other and the range learns; a fifth magenta off the same way, farther,
    is learned."""
    j = pf.FlagJudge(device_ranges={**{k: "magenta" for k in MAGENTA},
                                    "X1": "magenta"})
    shift = (-8.0, -30.0, 20.0)
    for loc, lab in MAGENTA.items():
        _read(j, loc, lab, shift, strip=loc.rstrip("0123456789"))
    j.rejudge()
    assert j.range_status("magenta") == (3, ("F13", "AV17", "BA13", "BM13"))
    for loc in MAGENTA:
        assert j._verdicts[loc].flag == pf.FLAG_CONFIRMED, loc
    far = (52.0, 85.0, -70.0)
    v = _read(j, "X1", far, tuple(1.6 * s for s in shift), strip="X")
    assert v.flag == pf.FLAG_LEARNED and v.like_loc


def test_a_reread_and_a_pair_of_peers_learn_together():
    j = pf.FlagJudge()
    for _ in range(2):
        _read(j, "A1", (30.0, 20.0, -60.0), strip="A")    # re-read: confirmed
    _read(j, "C1", (45.0, 20.0, -60.0), strip="C")
    _read(j, "D1", (47.0, 20.0, -60.0), strip="D")        # C1 and D1 peers
    j.rejudge()
    k, locs = j.range_status("blue")
    assert (k, locs) == (3, ("A1", "C1", "D1"))
    assert j.confirmed == ["A1"]
    v = _read(j, "Z9", (38.0, 21.0, -61.0), (7.0, -28.0, 35.0), strip="Z")
    assert v.flag == pf.FLAG_LEARNED


def test_a_learned_patch_never_makes_a_peer():
    """Peers come from raw readings, never from a verdict: a patch learned
    from the range does not make a red patch near it yellow."""
    j = pf.FlagJudge()
    for n, e in enumerate([(30.0, 20.0, -60.0), (37.0, 20.0, -60.0),
                           (44.0, 20.0, -60.0)], 1):
        for _ in range(2):
            _read(j, f"X{n}", e, strip="X")
    long = tuple(1.6 * s for s in SHIFT)
    learned = _read(j, "L1", (51.0, 20.0, -60.0), long, strip="L")
    assert learned.flag == pf.FLAG_LEARNED and learned.peer_locs == ()
    # a misread near L1's colour, in another strip, off another way
    v = _read(j, "M1", (52.0, 21.0, -60.0), (20.0, 40.0, 30.0), strip="M")
    assert v.flag is pf.FLAG_RED and v.peer_locs == ()
    assert j.export()["L1"] == {"kind": "learned", "like": "X3"}
    assert "M1" not in j.export()


# ---- the limit decides what is shown, not what exists ----------------------------
def _paint(j, readings, limit, *, live=False):
    """A repaint at *limit*: every patch judged, then the batch rejudged."""
    out = {}
    for loc, exp, shift, strip in readings:
        de = pf._norm(shift)
        out[loc] = j.judge(loc, exp, _add(exp, shift), de, de >= limit,
                           strip=strip, live=live)
    out.update(j.rejudge())
    return {k: v.flag for k, v in out.items()}


def test_lowering_the_limit_adds_a_partner_and_raising_it_takes_it_away():
    j = pf.FlagJudge()
    big = tuple(2.0 * s for s in SHIFT)                   # ΔE 64.8
    smaller = _add(big, (0.0, 4.0, -4.0))                 # ΔE 59.3, alike
    readings = [("A1", BLUE, big, "A"), ("F1", BLUE, smaller, "F")]
    assert _paint(j, readings, 62.0) == {"A1": pf.FLAG_RED,
                                         "F1": pf.FLAG_NONE}
    assert _paint(j, readings, 50.0) == {"A1": pf.FLAG_CONFIRMED,
                                         "F1": pf.FLAG_CONFIRMED}
    assert _paint(j, readings, 62.0) == {"A1": pf.FLAG_RED,
                                         "F1": pf.FLAG_NONE}


def test_a_reread_confirmation_survives_a_raised_limit():
    """The defect the challenge found: a repaint at a higher limit judged the
    patch clean and threw its re-read confirmation away, for good."""
    j = pf.FlagJudge()
    for _ in range(2):
        _read(j, "A1", BLUE, strip="A")                   # confirmed live
    assert j.confirmed == ["A1"]
    de = pf._norm(SHIFT)
    assert j.judge("A1", BLUE, _add(BLUE, SHIFT), de, False, strip="A",
                   live=False).flag is pf.FLAG_NONE       # limit raised
    assert j.confirmed == ["A1"]                          # still a fact
    assert j.export()["A1"]["kind"] == "confirmed"        # and still written
    v = j.judge("A1", BLUE, _add(BLUE, SHIFT), de, True, strip="A", live=False)
    assert v.flag == pf.FLAG_CONFIRMED and v.prev_de is not None
    # ...while hidden it teaches nothing
    j.judge("A1", BLUE, _add(BLUE, SHIFT), de, False, strip="A", live=False)
    assert j.range_status("blue") == (0, ())
    # a LIVE clean reading still takes it away
    j.judge("A1", BLUE, BLUE, 0.0, False, strip="A", live=True)
    assert j.confirmed == []


# ---- the memory file and Check & Refine -------------------------------------------
def test_a_peer_is_written_as_peer_and_never_loaded_as_a_reference(tmp_path):
    j = pf.FlagJudge()
    _read(j, "A1", BLUE, strip="A")
    _read(j, "F1", BLUE, strip="F")
    out = j.export()
    assert out["A1"] == {"kind": "peer", "with": ["F1"]}
    assert out["F1"] == {"kind": "peer", "with": ["A1"]}
    ti3 = tmp_path / "m.ti3"
    ti3.write_text("CTI3\n", encoding="utf-8")
    cp.write(ti3, out, "strip")
    data = cp.load(ti3)
    assert data["patches"]["A1"] == {"kind": "peer", "with": ["F1"]}
    k = pf.FlagJudge()
    assert k.load(data["patches"]) == 0 and k.confirmed == []


def test_clean_entry_keeps_the_peer_kind():
    assert cp._clean_entry({"kind": "peer", "with": ["B2", 7]}) == {
        "kind": "peer", "with": ["B2", "7"]}
    assert cp._clean_entry({"kind": "peer", "with": "B2"}) is None


def test_check_and_refine_leaves_out_peers_behind_one_switch(tmp_path,
                                                             monkeypatch):
    ti3 = tmp_path / "m.ti3"
    ti3.write_text("CTI3\n", encoding="utf-8")
    cp.write(ti3, {"A1": {"kind": "peer", "with": ["F1"]},
                   "F1": {"kind": "peer", "with": ["A1"]},
                   "C3": {"kind": "learned", "like": "A1"}}, "strip")
    assert cp.CHECK_REFINE_LEAVES_OUT_PEERS is True
    assert cp.confirmed_locations(ti3) == {"A1", "F1"}
    monkeypatch.setattr(cp, "CHECK_REFINE_LEAVES_OUT_PEERS", False)
    assert cp.confirmed_locations(ti3) == set()


# ---- on the fly: Preferences OK and showing the tab ------------------------------
class _StandIn:
    def __init__(self, live=False, ti3="m.ti3"):
        self._session_live = live
        self._ti3 = ti3
        self.repaints = 0

    def _existing_ti3_for_chart(self):
        return self._ti3

    def _repaint_overlay_from_disk(self):
        self.repaints += 1


def test_refresh_patch_flags_repaints_only_outside_a_session():
    from ui.tabs.tab_measure import TabMeasure
    t = _StandIn()
    TabMeasure.refresh_patch_flags(t)
    assert t.repaints == 1
    t = _StandIn(live=True)
    TabMeasure.refresh_patch_flags(t)
    assert t.repaints == 0
    t = _StandIn(ti3=None)
    TabMeasure.refresh_patch_flags(t)
    assert t.repaints == 0


def test_preferences_ok_and_show_event_ask_for_it():
    from ui.main_window import MainWindow
    from ui.tabs.tab_measure import TabMeasure
    show = inspect.getsource(TabMeasure.showEvent)
    assert "QTimer.singleShot(0, self.refresh_patch_flags)" in show
    src = inspect.getsource(MainWindow)
    i = src.index("self._tab_measure.refresh_progress_setting()")
    assert "self._tab_measure.refresh_patch_flags()" in src[i:i + 600]


def test_a_preferences_change_repaints_knuts_strips(qapp, tmp_path):
    """On a real tab painted from Knut's file: lowering the limit and asking
    for the refresh flags more patches, and his blues of strips A, F and O
    confirm each other without a single re-read."""
    from tests.test_k182_k3_k4_overlay_and_memory import (
        _flags, _tab, _write_ti3)
    tab = _tab(tmp_path)
    _write_ti3(tmp_path)
    cb = tab._overlay_cb if tab._current_mode() == "guided" else tab._m_overlay_cb
    cb.blockSignals(True)
    cb.setChecked(True)
    cb.blockSignals(False)
    tab.refresh_patch_flags()
    at95 = _flags(tab)
    red95 = {k for k, v in at95.items() if v is True}
    yellow95 = {k for k, v in at95.items() if pf.is_yellow(v)}
    assert yellow95 and {"A23", "O9"} <= yellow95
    tab._settings.set(pf.ESTIMATED_KEY, 30.0)
    tab.refresh_patch_flags()
    at30 = _flags(tab)
    flagged30 = {k for k, v in at30.items() if v}
    assert len(flagged30) > len(red95 | yellow95)
    tab._settings.set(pf.ESTIMATED_KEY, 95.0)
    tab.refresh_patch_flags()
    assert {k: v for k, v in _flags(tab).items() if v} == {
        k: v for k, v in at95.items() if v}


def test_check_and_refine_reads_the_peers_of_the_current_limit(qapp, tmp_path):
    """k22 review: Check & Refine leaves out what the memory file calls
    confirmed, and its peers were worked out at the session's limit. After a
    limit change the file follows the preview, so Check & Refine never offers
    a patch the card says to keep, nor leaves out one it no longer confirms."""
    from tests.test_k182_k3_k4_overlay_and_memory import (
        _flags, _tab, _write_ti3)
    tab = _tab(tmp_path)
    ti3 = _write_ti3(tmp_path)
    cb = tab._overlay_cb if tab._current_mode() == "guided" else tab._m_overlay_cb
    cb.blockSignals(True)
    cb.setChecked(True)
    cb.blockSignals(False)

    def peers_on_screen():
        j = tab._flag_judge()
        return {loc for loc, v in _flags(tab).items()
                if pf.is_yellow(v) and j.peers_of(loc)}

    tab.refresh_patch_flags()
    ti3 = getattr(tab, "_memory_for", None) or ti3
    at95 = peers_on_screen()
    assert at95 and at95 <= cp.confirmed_locations(ti3)
    # A higher limit than any patch's error: nothing flagged, so nothing is
    # confirmed by similar patches, on screen or in the file.
    tab._settings.set(pf.ESTIMATED_KEY, 500.0)
    tab.refresh_patch_flags()
    assert peers_on_screen() == set()
    assert not (at95 & cp.confirmed_locations(ti3))
    # And back: the file follows again.
    tab._settings.set(pf.ESTIMATED_KEY, 95.0)
    tab.refresh_patch_flags()
    assert peers_on_screen() == at95
    assert at95 <= cp.confirmed_locations(ti3)


def test_refresh_rewrites_the_memory_only_after_reading_it_back():
    """The judge on hand may be another chart's, or empty, when the overlay
    was not painted: then nothing is written over the file."""
    src = inspect.getsource(
        __import__("ui.tabs.tab_measure", fromlist=["TabMeasure"])
        .TabMeasure.refresh_patch_flags)
    assert '"_memory_loads", 0) != loads' in src
