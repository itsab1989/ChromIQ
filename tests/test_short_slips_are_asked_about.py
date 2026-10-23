"""Short slips: one to three patches read one patch out of place (agent 19's
study, approved by Basti 2026-10-23).

jctay's verification of 2026-10-22 held eight slips of only two or three
patches at the start of a strip, and nothing asked about them: the slip check
(`workflow.slipped_strip`) asks for runs of four or more, because two or three
patches can match their neighbours by chance. Agent 19 measured two shapes
that carry a fingerprint a chance match does not:

* "bs", AT AN END of the strip: the first patch read the white paper although
  its own colour is not paper-like, and the next one to three readings each
  carry the colour of the patch before them (mirrored at the end), with a
  stricter test when that run is one patch;
* "c", IN THE MIDDLE: two or three patches with patches read in step on both
  sides, and a duplicated reading where the slip begins.

These tests hold the shipped check to that, on REAL readings (Basti's ET-8550
verification read through its own chart, as the slip tests before them), and
the texts to what is true for such a slip: one patch is not "patches X to X"
and has no "average", a slip inside the strip was not caused by "the white
paper in front of the first patch", and a slip up to the strip's end is not
"in step again" afterwards.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).parent))

import test_149786_part_of_a_strip_slipped as base      # noqa: E402
from workflow import measurement_messages as M          # noqa: E402
from workflow import slipped_strip as ss                # noqa: E402
from workflow.slipped_strip import (find_slipped_run,   # noqa: E402
                                    slipped_run_in_strip_read)


def _strip(label):
    return base._strips()[label]


def _meas(strip):
    return [mx for _l, mx, _e in strip]


def _start(strip, k):
    """The reader started on the paper: paper, then patches 1..k-1 one late,
    patch k-1's colour lost, in step again from patch k on (k spoiled)."""
    m = _meas(strip)
    return [base._paper()] + m[:k - 1] + m[k:]


def _end(strip, k):
    """The mirror: the last k patches spoiled, the last one read the paper."""
    m = _meas(strip)
    n = len(m)
    return m[:n - k] + m[n - k + 1:] + [base._paper()]


def _middle(strip, k, late):
    """Inside the strip: one patch read twice and, k readings later, one
    boundary missed (late), or the other way round (early)."""
    m = _meas(strip)
    a = len(m) // 2 - k // 2
    if late:
        return m[:a] + m[a - 1:a - 1 + k] + m[a + k:]
    return m[:a] + m[a + 1:a + 1 + k] + m[a + k:]


def _find(label, meas):
    strip = _strip(label)
    return slipped_run_in_strip_read(
        base._event(label, strip, meas)["patches"])


def _loc(label, pos):
    return _strip(label)[pos][0]


# ---- 1. the check finds them -------------------------------------------------

def test_two_patches_at_the_start_are_found():
    """FAILS ON 4.3.10 BEFORE THE SHORT RULES: K1 read the paper, K2 and K3
    carry K1's and K2's colours, K4 on is in step again."""
    run = _find("K", _start(_strip("K"), 3))
    assert run is not None
    assert (run.offset, run.kind, run.reversed) == (1, "start", False)
    assert (run.first, run.last, run.run_first, run.run_last) == (0, 2, 1, 2)
    assert run.lead == 0 and run.lead_paper
    assert not run.single
    assert run.shifted_de00 < run.base_de00


def test_one_patch_after_the_paper_is_found_with_the_stricter_test():
    """K1 read the paper and only K2 carries K1's colour: a run of one."""
    run = _find("K", _start(_strip("K"), 2))
    assert run is not None
    assert (run.offset, run.kind, run.first, run.last) == (1, "start", 0, 1)
    assert run.single and run.run_first == run.run_last == 1


def test_the_one_patch_case_asks_for_a_far_clearer_fit():
    """The same one-patch shape that only just passes the ordinary
    thresholds is not enough: the paper patch must miss by SMOOTH_TRIGGER_DE
    and the patch must fit at SMOOTH_RATIO."""
    exp = [(30.0, 60.0, 40.0), (60.0, -50.0, 30.0), (40.0, 20.0, -60.0),
           (70.0, 10.0, 70.0), (25.0, -30.0, -30.0), (55.0, 50.0, -20.0)]
    def strip(t):
        meas = list(exp)
        meas[0] = (95.0, 0.0, -2.0)                   # the paper
        # patch 1 carries patch 0's colour, t of the way to its own
        meas[1] = tuple(a + t * (b - a) for a, b in zip(exp[0], exp[1]))
        return meas
    loose = strip(0.3)        # fits at 0.43 of its own miss: below RATIO 0.5
    assert ss._de(loose[1], exp[0]) <= ss.RATIO * ss._de(loose[1], exp[1])
    assert ss._de(loose[1], exp[0]) > ss.SMOOTH_RATIO * ss._de(loose[1], exp[1])
    assert find_slipped_run(loose, exp) is None
    clear = find_slipped_run(strip(0.1), exp)    # 0.11 of its own miss
    assert clear is not None and clear.kind == "start" and clear.single


def test_the_mirror_at_the_end_of_a_strip_is_found():
    for k, single in ((2, True), (3, False)):
        run = _find("K", _end(_strip("K"), k))
        assert run is not None, k
        assert (run.offset, run.kind, run.reversed) == (-1, "end", False)
        assert (run.first, run.last) == (14 - k, 13)
        assert run.lead == 13 and run.lead_paper
        assert run.run_last == 12 and run.single is single


@pytest.mark.parametrize("k", (2, 3))
def test_a_short_slip_in_the_middle_is_found_late(k):
    """FAILS BEFORE: Z's patch 5 read twice (its reading filed again under
    patch 6), then one boundary missed k readings later."""
    run = _find("Z", _middle(_strip("Z"), k, late=True))
    assert run is not None
    assert (run.offset, run.kind) == (1, "middle")
    a = 7 - k // 2
    assert (run.first, run.last) == (a, a + k - 1)
    assert run.twice == a - 1                  # the patch just before it
    assert run.lead is None and not run.lead_paper


@pytest.mark.parametrize("k", (2, 3))
def test_a_short_slip_in_the_middle_is_found_early(k):
    run = _find("Z", _middle(_strip("Z"), k, late=False))
    assert run is not None
    assert (run.offset, run.kind) == (-1, "middle")
    a = 7 - k // 2
    assert (run.first, run.last) == (a, a + k - 1)
    assert run.twice == a + k                  # the patch just after it


# ---- 2. ... and stays quiet where it must --------------------------------------

def test_a_short_run_without_the_fingerprint_is_still_not_a_slip():
    """Three patches inside a strip that carry their neighbours' colours,
    but no patch was read twice and none read the paper: as before, two or
    three patches can match by chance, so nothing is said."""
    exp = [(50.0 + 30 * (i % 2), 40.0 * ((i * 7) % 3 - 1), 0.0)
           for i in range(10)]
    # readings 3..5 carry the colours of 2..4, but reading 2 is its own
    # colour plus a clear printing difference, not reading 3's twin
    meas = list(exp)
    meas[3:6] = exp[2:5]
    meas[2] = (exp[2][0] - 9.0, exp[2][1] + 9.0, 9.0)
    meas[1] = (exp[1][0] - 9.0, exp[1][1], -9.0)
    assert find_slipped_run(meas, exp) is None


def test_every_honest_strip_of_the_real_verification_stays_quiet():
    for label, strip in base._strips().items():
        assert _find(label, _meas(strip)) is None, label


def test_a_ramp_with_one_patch_after_the_paper_stays_quiet():
    """A calibration ramp / "Preserve Patch Order": neighbours one step
    apart. A print one step darker than the design is no slip."""
    ramp = [(20.0 + 6.0 * i, 0.0, 0.0) for i in range(14)]
    meas = [(95.0, 0.5, -3.0)] + [(v[0] - 6.0, 0.0, 0.0) for v in ramp[1:]]
    assert find_slipped_run(meas, ramp) is None


def test_runs_of_four_or_more_and_back_to_front_are_unchanged():
    """The search for four or more runs first and alone decides when it
    finds something: jctay's own slip is named as before, with no kind of a
    short slip, and the strip filed back to front is still reversed."""
    run = _find("K", base._slip(_strip("K"), 8))
    assert (run.first, run.last, run.run_first, run.run_last) == (0, 7, 1, 7)
    assert run.kind == "start" and not run.single and run.twice is None
    rev = _find("K", base._reversed_whole_slip(_strip("K")))
    assert rev is not None and rev.reversed and rev.kind == ""


def test_short_rules_use_the_study_parameters():
    """The numbers agent 19 measured, word for word."""
    assert (ss.SHORT_MAX, ss.SHORT_NEIGHBOUR_SHARE, ss.TWICE_DE,
            ss.TWICE_SHARE) == (3, 0.5, 6.0, 0.3)
    assert (ss.TRIGGER_DE, ss.RATIO, ss.GOOD_DE, ss.MIN_NEIGHBOUR_DE,
            ss.SMOOTH_Q, ss.SMOOTH_TRIGGER_DE, ss.SMOOTH_RATIO, ss.MIN_RUN) \
        == (12.0, 0.5, 35.0, 12.0, 0.6, 25.0, 0.3, 4)


# ---- 3. the session asks, with the same switch --------------------------------

def test_the_session_asks_about_a_short_slip_and_says_where_it_sits(qapp):
    from test_knut_5956210745_next_strip_after_a_read import _feed
    m = base._manager()
    m._safenet_on = True
    asked, judged = [], []
    m.strip_partly_misaligned.connect(lambda *a: asked.append(a[0]))
    m.strip_measured.connect(lambda ev: judged.append(int(ev["misaligned"])))
    strip = _strip("Z")
    _feed(m, base._event("Z", strip, _middle(strip, 2, late=True)))
    assert judged == [1]
    assert len(asked) == 1
    f = asked[0]
    assert (f["kind"], f["first"], f["last"], f["twice"], f["single"],
            f["lead"]) == ("middle", "Z7", "Z8", "Z6", False, None)


def test_off_when_the_warning_is_off(qapp):
    m = base._manager()
    m._safenet_on = False
    strip = _strip("K")
    ev = base._event("K", strip, _start(strip, 3))
    assert m._check_part_of_strip_slipped(ev, ev["patches"]) is None
    assert ev["misaligned"] == 0


# ---- 4. the words are true for a short slip -----------------------------------

def _asked(qapp, monkeypatch, finding):
    from PyQt6.QtWidgets import QLabel
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    tab = TabMeasure(ArgyllRunner(s), s)
    seen = {}

    def grab(dlg):
        seen["text"] = " ".join(lb.text() for lb in dlg.findChildren(QLabel))
        return 0
    monkeypatch.setattr(tab, "_exec_measurement_window", grab)
    tab._on_strip_partly_misaligned(finding)
    tab.deleteLater()
    return seen["text"]


def _finding(**kw):
    f = {"strip": "5", "offset": 1, "reversed": False, "whole": False,
         "first": "5B", "last": "5B", "lead": "5A", "lead_paper": True,
         "base": 30.04, "best": 2.11, "kind": "start", "twice": None,
         "single": True}
    f.update(kw)
    return f


def test_one_patch_is_one_patch(qapp, monkeypatch):
    text = _asked(qapp, monkeypatch, _finding())
    assert "Patch 5A came out with the colour of the white paper." in text
    assert "Patch 5B of strip 5 came out with the colour of the patch just " \
           "before it" in text
    assert "Patches" not in text and "On average" not in text
    assert "first two patches of the strip" in text
    assert "{" not in text


def test_one_patch_at_the_end(qapp, monkeypatch):
    text = _asked(qapp, monkeypatch, _finding(
        offset=-1, first="5L", last="5L", lead="5M", kind="end"))
    assert "Patch 5M came out with the colour of the white paper." in text
    assert "Patch 5L of strip 5 came out with the colour of the patch just " \
           "after it" in text
    assert "white paper after the last patch for a patch of its own" in text
    assert "last two patches of the strip" in text


def test_a_slip_up_to_the_end_is_not_in_step_again(qapp, monkeypatch):
    text = _asked(qapp, monkeypatch, _finding(
        offset=-1, first="5K", last="5L", lead="5M", kind="end",
        single=False))
    assert "Patches 5K to 5L of strip 5" in text
    assert "in step again" not in text
    assert "the last patch of the strip gets the reading of the paper" in text


def test_a_slip_inside_the_strip_names_the_patch_read_twice(qapp, monkeypatch):
    late = _asked(qapp, monkeypatch, _finding(
        first="5G", last="5H", lead=None, lead_paper=False, kind="middle",
        twice="5F", single=False))
    assert "Patches 5G to 5H of strip 5" in late
    assert "white paper" not in late.split("Readings filed")[0]
    assert "reads one patch twice: the reading filed under patch 5G is " \
           "almost the same as the reading of patch 5F just before it" in late
    early = _asked(qapp, monkeypatch, _finding(
        offset=-1, first="5G", last="5H", lead=None, lead_paper=False,
        kind="middle", twice="5I", single=False))
    assert "the reading filed under patch 5H is almost the same as the " \
           "reading of patch 5I just after it" in early
    assert "a mark, or the white paper" not in early


def test_two_patches_at_the_start_keep_the_existing_words(qapp, monkeypatch):
    """Every sentence of M-STRIP-PART-SLIPPED-LATE holds for them."""
    text = _asked(qapp, monkeypatch, _finding(last="5C", single=False))
    _t, body = M.M_STRIP_PART_SLIPPED_LATE.render(
        strip="5", first="5B", last="5C", base="30.0", best="2.1",
        lead_line=M.slip_lead_line("5A", True), remeasure="Re-measure this "
        "strip", keep="Keep it", stop="Stop")
    assert body.split("\n\n")[1] in text


def test_the_report_says_one_patch_for_one_patch(qapp):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    html = MeasurementReportDialog._shifted_strips_html(None, {
        "shifted_strips": [{
            "strip": "5", "offset": 1, "reversed": False, "single": True,
            "run_first": "5B", "run_last": "5B", "first": "5A", "last": "5B",
            "lead": "5A", "lead_paper": True, "kind": "start",
            "base_de00": 30.0, "shifted_de00": 2.1}]})
    assert "The reading of patch 5B matches the expected colour of the " \
           "patch just before it" in html
    assert "patches 5B to 5B" not in html and "on average" not in html
    assert "these two patches" in html


def test_the_report_keeps_its_words_for_two_or_three(qapp):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    html = MeasurementReportDialog._shifted_strips_html(None, {
        "shifted_strips": [{
            "strip": "5", "offset": 1, "reversed": False, "single": False,
            "run_first": "5G", "run_last": "5H", "first": "5G", "last": "5H",
            "lead": None, "lead_paper": False, "kind": "middle",
            "base_de00": 30.0, "shifted_de00": 2.1}]})
    assert "The readings of patches 5G to 5H match" in html


def test_the_stored_measurement_names_a_short_slip_in_the_report(tmp_path):
    """The report's own check (`shifted_strips`) over a stored measurement
    with two patches of strip K slipped at its start."""
    from workflow.measurement_report import build_report
    ti3 = base._copy(tmp_path)
    strip = _strip("K")
    base._write_readings(ti3, strip, _start(strip, 3))
    found = build_report(ti3).get("shifted_strips") or []
    k = [s for s in found if s["strip"] == "K"]
    assert k, found
    assert (k[0]["run_first"], k[0]["run_last"], k[0]["lead"],
            k[0]["kind"], k[0]["single"]) == ("K2", "K3", "K1", "start", False)
