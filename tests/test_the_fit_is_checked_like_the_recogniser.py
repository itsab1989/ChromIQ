"""The fit's own answer is submitted to the checks the recogniser's answer is.

**The fault this file exists for.** "Auto align" submits every placement it
finds to two checks that look at the PICTURE rather than at its own score:
:func:`~workflow.scan_auto_align.border_agreement`, which sees a grid slid onto
the neighbouring patch, and :func:`~workflow.scan_auto_align.seating_drift`,
which sees a keystone. "Fit to the patches" ran **neither** — and its own two
refusal messages already said why that mattered, in its own words: *"a grid a
whole patch out reads every patch as its neighbour and looks just as even."*

It is the same objective on both sides that makes the check necessary. The fit
MOVES the sample boxes onto flatter colour, and the neighbouring patch is flat
colour too, so from far enough out the fit walks towards the wrong squares and
every measure taken inside the boxes improves as it goes. Measured (beta 8,
agent O) over the 118 fits the button actually applied in a 290-cell capture
sweep across ten cases and five targets: **41 ended more than a quarter of a
patch pitch from the truth**, and these two checks refuse **41 of those 41**
while refusing 2 of the 77 correct ones. Driven on screen on Knut's own Wolf
Faust scan from one patch pitch out, the unchecked button moved the grid to
**one and a half** pitches out and said "The grid was fitted to the patches".

Everything below is measured against the app's OWN demo scan, whose truth comes
from the generator that draws it (``demo_scan_layout``) rather than from any
arithmetic repeated here.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication                        # noqa: E402

from core.settings import DEFAULTS                              # noqa: E402
from core.text_io import read_text                              # noqa: E402
from workflow import measurement_messages as M                  # noqa: E402
from workflow.cht_parser import parse_cht                       # noqa: E402
from workflow.photo_fit import patch_pitch_px                   # noqa: E402
from workflow.standard_targets import (demo_scan_layout,        # noqa: E402
                                       make_test_scan)

CHT = Path(__file__).resolve().parent.parent / "data" / "scanner_targets" / \
    "SpyderChecker.cht"


class _FakeSettings:
    """DEFAULTS with a hermetic output root — ``custom_output_path`` defaults
    to "", and "" means the developer's real ``~/ChromIQ``."""

    def __init__(self, root):
        self._store = {**DEFAULTS, "custom_output_path": str(root)}

    def get(self, key, default=None):
        return self._store.get(key, default)

    def set(self, key, value):
        self._store[key] = value


@pytest.fixture(scope="module")
def _app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    """A demo scan of a bundled target, its four TRUE corners, and its pitch."""
    d = tmp_path_factory.mktemp("fit-gate")
    tif, cie = make_test_scan(CHT, d)
    text = read_text(CHT, lenient=True)
    boxes = parse_cht(text).patches
    _sc, px0, py0, pw, ph, _W, _H, _sr, _sh = demo_scan_layout(text, boxes)
    truth = [(px0, py0), (px0 + pw, py0), (px0 + pw, py0 + ph), (px0, py0 + ph)]
    bbox = (min(b.x1 for b in boxes), min(b.y1 for b in boxes),
            max(b.x2 for b in boxes), max(b.y2 for b in boxes))
    return tif, cie, boxes, truth, patch_pitch_px(boxes, truth, bbox)


def _seated(scan, boxes, quad):
    """The shipped gate, called for real: a copy of it here would test the copy.

    It lives in `workflow.scan_placement` since B8-42 merged the two placement
    buttons — the same two checks, asked once, of whatever placement the merged
    operation is about to apply."""
    from workflow.scan_placement import is_seated
    return is_seated(scan, boxes, quad)


def _shift(quad, dx, dy):
    return [(x + dx, y + dy) for x, y in quad]


def _grown(quad, by_px):
    """The quad scaled about its own centre until its worst corner has moved
    *by_px* — a wrong SHAPE rather than a wrong position, which is the other
    half of what a hand does."""
    cx = sum(x for x, _ in quad) / 4.0
    cy = sum(y for _, y in quad) / 4.0
    far = max(((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 for x, y in quad)
    k = 1.0 + by_px / far
    return [(cx + (x - cx) * k, cy + (y - cy) * k) for x, y in quad]


# --------------------------------------------------------------- the check
def test_the_true_placement_survives_the_check(demo):
    """The control. A gate that refuses the right answer is not a gate."""
    tif, _cie, boxes, truth, _p = demo
    assert _seated(tif, boxes, truth) is True


def test_a_grid_walked_onto_the_neighbouring_patch_is_refused(demo):
    """The fault, in the shape it actually takes: one whole patch pitch, where
    every box sits squarely on flat colour and every within-box measure says
    the placement is perfect."""
    tif, _cie, boxes, truth, pitch = demo
    assert _seated(tif, boxes, _shift(truth, pitch, 0.0)) is False


def test_both_of_the_recognisers_picture_checks_are_asked(demo, monkeypatch):
    """Not one of them. They see different faults — a slide and a shear — and
    a gate wired to only one of them passes the other silently.

    This is also the mutation proof for the two calls: with either check
    forced to its refusing answer the gate must refuse, so neither call can be
    deleted without turning this red."""
    import workflow.scan_auto_align as AA
    tif, _cie, boxes, truth, _p = demo
    assert _seated(tif, boxes, truth) is True          # baseline: accepted

    monkeypatch.setattr(AA, "border_agreement", lambda *a, **k: False)
    assert _seated(tif, boxes, truth) is False
    monkeypatch.undo()

    monkeypatch.setattr(AA, "seating_drift",
                        lambda *a, **k: AA.SEATING_DRIFT_LIMIT * 2.0)
    assert _seated(tif, boxes, truth) is False


def test_the_limit_is_the_recognisers_own_and_not_a_second_number(demo,
                                                                  monkeypatch):
    """One threshold, in one place. A drift just under the shipped limit is
    accepted and one just over it is refused, so the gate cannot drift away
    from Auto align's own by having a copy of the number."""
    import workflow.scan_auto_align as AA
    tif, _cie, boxes, truth, _p = demo
    monkeypatch.setattr(AA, "seating_drift",
                        lambda *a, **k: AA.SEATING_DRIFT_LIMIT * 0.99)
    assert _seated(tif, boxes, truth) is True
    monkeypatch.setattr(AA, "seating_drift",
                        lambda *a, **k: AA.SEATING_DRIFT_LIMIT * 1.01)
    assert _seated(tif, boxes, truth) is False


def test_a_check_that_cannot_run_is_not_evidence_of_a_fault(demo, monkeypatch):
    """The same rule ``auto_align`` applies to its own drift measurement: a
    safety check that raises is a check that said nothing, not a refusal."""
    import workflow.scan_auto_align as AA
    tif, _cie, boxes, truth, _p = demo

    def _boom(*a, **k):
        raise RuntimeError("no")

    monkeypatch.setattr(AA, "seating_drift", _boom)
    assert _seated(tif, boxes, truth) is True


# ------------------------------------------------------------- the window
@pytest.fixture(scope="module")
def dlg(_app, tmp_path_factory):
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    d = ScannerProfileDialog(object(),
                             _FakeSettings(tmp_path_factory.mktemp("fit-win")))
    d._mode_standard.click()
    cb = d._target_combo
    idx = [i for i in range(cb.count()) if cb.itemData(i) == "SpyderChecker"]
    assert idx, "the bundled SpyderChecker target is not in the combo"
    cb.setCurrentIndex(idx[0])
    d._reveal_target_files()                 # the real "Try with a demo scan"
    yield d
    d.deleteLater()


def _truth_and_pitch(dlg):
    """From the ``.cht`` THE DIALOG loaded, not from a copy of it."""
    text = read_text(dlg._std_cht, lenient=True)
    boxes = parse_cht(text).patches
    _sc, px0, py0, pw, ph, _W, _H, _sr, _sh = demo_scan_layout(text, boxes)
    truth = [(px0, py0), (px0 + pw, py0), (px0 + pw, py0 + ph), (px0, py0 + ph)]
    bbox = (min(b.x1 for b in boxes), min(b.y1 for b in boxes),
            max(b.x2 for b in boxes), max(b.y2 for b in boxes))
    return truth, patch_pitch_px(boxes, truth, bbox)


def _press_fit(dlg, corners, monkeypatch):
    """Press the real button with the SEARCH declining, so what is exercised is
    the second half of the merged operation: reshape the corners the user
    placed, then submit the answer to the checks.

    Only the recogniser is replaced, and only so that this file needs no
    ArgyllCMS: the window, the slot, its worker thread, `place_grid`, the fit,
    both picture checks and the reference agreement are all the shipped ones.
    """
    import workflow.scan_auto_align as AA
    from PyQt6.QtWidgets import QApplication
    monkeypatch.setattr(AA, "auto_align",
                        lambda *a, **k: AA.AutoAlignResult(reason="no-better"))
    dlg._marquee.set_corners([tuple(c) for c in corners])
    dlg._capture_current_corners()
    mark = len(dlg._log.toPlainText())
    dlg._on_auto_align()
    app = QApplication.instance()
    import time
    deadline = time.monotonic() + 120.0
    while dlg._align_thread is not None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    app.processEvents()
    assert dlg._align_thread is None, "the placement never finished"
    return (dlg._log.toPlainText()[mark:],
            [tuple(c) for c in dlg._marquee.corners_image_px()])


def test_the_window_leaves_the_corners_alone_when_the_check_refuses(dlg, monkeypatch):
    """The whole point, at the button. The grid is one patch out, the fit is
    happy to move it, and nothing moves."""
    truth, pitch = _truth_and_pitch(dlg)
    # 0.85 of a pitch, NOT a whole one: at exactly one pitch the fit answers
    # "already the best fit" and never reaches the gate at all (that state has
    # its own test in test_photograph_path.py). Just under a pitch is where it
    # is willing to move, and where it moves the WRONG WAY -- measured, this
    # start ends 0.97 of a pitch out, reading the neighbouring column.
    start = _shift(truth, 0.85 * pitch, 0.0)
    said, after = _press_fit(dlg, start, monkeypatch)
    assert M.M_SCAN_ALIGN_NOT_SEATED.title in said
    assert M.M_SCAN_ALIGN_NOT_SEATED.body.split("\n")[0][:60] in said
    for (ax, ay), (bx, by) in zip(after, start):
        assert abs(ax - bx) < 0.51 and abs(ay - by) < 0.51


def test_the_window_still_applies_a_fit_that_survives_the_check(dlg, monkeypatch):
    """And the control at the button: a grid a third of a patch too big is
    still reshaped onto the patches, and still says so."""
    truth, pitch = _truth_and_pitch(dlg)
    start = _grown(truth, 0.30 * pitch)
    said, after = _press_fit(dlg, start, monkeypatch)
    assert M.M_SCAN_ALIGN_DONE.title in said
    assert M.M_SCAN_ALIGN_NOT_SEATED.body.split("\n")[0][:60] not in said
    moved = max(abs(ax - bx) + abs(ay - by)
                for (ax, ay), (bx, by) in zip(after, start))
    assert moved > 1.0, "the fit applied nothing, so this proves nothing"


# ------------------------------------------------------------- the words
def test_the_refusal_has_words_of_its_own_and_is_not_approved_yet():
    """A new state needs its own sentence, and a sentence nobody has reviewed
    must say so — ``tests/test_message_catalogue.py`` enforces the rest."""
    from tests.test_message_catalogue import AWAITING_APPROVAL
    m = M.M_SCAN_ALIGN_NOT_SEATED
    assert m.id in M.CATALOGUE and m.approved is False
    assert m.id in AWAITING_APPROVAL
    assert M.scan_align_refusal("not-seated") is m
    # "the check refused what was found" and "there was nothing better to find"
    # are different facts and ask for different next steps, so they may not
    # share a body.
    assert m.body != M.M_SCAN_ALIGN_NO_BETTER.body
    # …and it may not name an internal stage. The user does not know there are
    # stages (B8-42), so no ending may tell them which one declined.
    low = (m.title + " " + m.body).lower()
    for jargon in ("stage", "step one", "step two", "recogniser", "fit stage",
                   "homography", "seating drift", "border agreement"):
        assert jargon not in low, f"the refusal names an internal stage: {jargon}"


def test_every_reason_the_fit_can_end_on_has_words_of_its_own():
    """Including the new one. A reason with no entry falls back to the "too
    far" wording, which would be the wrong thing to say here — so the set is
    pinned rather than trusted."""
    import inspect

    from workflow import photo_fit
    from workflow.scan_placement import ENDINGS, _ending
    src = inspect.getsource(photo_fit.refine_corners)
    reasons = set()
    for line in src.splitlines():
        if "reason=" in line and '"' in line:
            reasons.add(line.split('reason="')[1].split('"')[0])
    assert reasons, "no refusal reasons found in the fit at all"
    # Every reason the reshaping can return must land on an ending the merged
    # button has words for — with the search silent, which is the only way any
    # of them can reach a user.
    for r in reasons:
        end = _ending("no-better", r)
        assert end in ENDINGS, f"{r} maps to an ending that does not exist: {end}"
        assert end in M.SCAN_ALIGN_REFUSALS, f"{r} has no words: {end}"
    # …and so must every ending, whichever half produced it.
    assert set(ENDINGS) - {"placed"} == set(M.SCAN_ALIGN_REFUSALS)
