"""One button places the grid: it searches, it reshapes, and THEN it checks.

**What this file exists for (B8-42).** The scanner window shipped two buttons
for one job — "Auto align", which hands the picture to ArgyllCMS's recogniser
and can only ever answer with a rotated RECTANGLE, and "Fit to the patches",
which reshapes the four corners the user already placed through all eight
degrees of freedom a quad has but cannot reach further than three quarters of a
patch. Basti: *"i don't want to have two options where one is useless."*

Neither was useless and neither was a subset of the other — measured over 290
starting placements on ten conditions and five targets, 139 cases only the
search recovers and 30 only the reshaping does — but choosing between them was
never the user's job. Measured on the same 290 cells, driving the shipped
module:

===========================================  ==============  ================
design                                       ends ON the     applied a
                                             patches         placement still
                                                             wrong
===========================================  ==============  ================
search alone                                 196/290 (68 %)  0
reshaping alone                               87/290 (30 %)  41 of 118
press both, as beta 7 shipped                226/290 (78 %)  11
**one button: search, reshape, then check**  **244/290**     **0 of 233**
===========================================  ==============  ================

Three things decide whether that is safe, and each has a test below:

* the drift gate is **suspended for the search and asked once at the end**, of
  the placement that is actually about to be applied. A gate in the middle
  throws away the very answer the reshaping exists to rescue;
* when the reshaping declines, the search's answer is **applied**, not
  discarded. That is the majority outcome — 175 of the 290 cells — and refusing
  everything there would throw away 155 correct placements;
* nothing reaches the grid without passing both picture checks AND the
  reference agreement, measured at the corners about to be set.

And two things decide whether it is honest: one press undoes the whole
operation rather than a stage the user never saw, and no ending tells them
which half of it declined.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication                        # noqa: E402

from core.settings import DEFAULTS                              # noqa: E402
from core.text_io import read_text                              # noqa: E402
from workflow import measurement_messages as M                  # noqa: E402
from workflow.cht_parser import parse_cht                       # noqa: E402
from workflow.photo_fit import RefineResult, patch_pitch_px     # noqa: E402
from workflow.scan_auto_align import AutoAlignResult            # noqa: E402
from workflow.scan_placement import (ENDINGS, place_grid,       # noqa: E402
                                     search_region_for)
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
    """The app's own demo scan of a bundled target, its EXACT four corners
    (straight from the generator that draws it) and its patch pitch."""
    d = tmp_path_factory.mktemp("one-button")
    tif, cie = make_test_scan(CHT, d)
    text = read_text(CHT, lenient=True)
    boxes = parse_cht(text).patches
    _sc, px0, py0, pw, ph, W, H, _sr, _sh = demo_scan_layout(text, boxes)
    truth = [(px0, py0), (px0 + pw, py0), (px0 + pw, py0 + ph), (px0, py0 + ph)]
    bbox = (min(b.x1 for b in boxes), min(b.y1 for b in boxes),
            max(b.x2 for b in boxes), max(b.y2 for b in boxes))
    from workflow.scan_auto_align import expected_luminance
    expected = expected_luminance(text, cie, chart_ids=[b.name for b in boxes])
    return dict(tif=tif, cie=cie, cht=CHT, boxes=boxes, truth=truth,
                pitch=patch_pitch_px(boxes, truth, bbox), size=(W, H),
                expected=expected)


def _shift(quad, dx, dy):
    return [(x + dx, y + dy) for x, y in quad]


def _grown(quad, by_px):
    cx = sum(x for x, _ in quad) / 4.0
    cy = sum(y for _, y in quad) / 4.0
    far = max(((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 for x, y in quad)
    k = 1.0 + by_px / far
    return [(cx + (x - cx) * k, cy + (y - cy) * k) for x, y in quad]


def _worst(a, b):
    return max(((x - u) ** 2 + (y - v) ** 2) ** 0.5
               for (x, y), (u, v) in zip(a, b))


def _run(demo, start, monkeypatch, answer=None, **kw):
    """`place_grid` with the recogniser replaced by *answer* — everything else,
    including the reshaping and all three checks, is the shipped code.

    The recogniser is replaced rather than run because it needs ArgyllCMS and
    because these tests are about what happens AROUND it; the cases where it
    really runs are the 290-cell sweep and the on-screen runs in
    ``19-one-align-button/``.
    """
    import workflow.scan_auto_align as AA
    if answer is not None:
        monkeypatch.setattr(AA, "auto_align", lambda *a, **k: answer)
    return place_grid("scanin-not-run", demo["tif"], demo["cht"], demo["cie"],
                      demo["boxes"], demo["expected"], demo["size"],
                      current_corners=start, **kw)


# ------------------------------------------------------- the two halves join
def test_the_reshaping_starts_from_the_users_corners_when_the_search_declines(
        demo, monkeypatch):
    """Without this fallback the merged button loses every case where the
    recogniser declines about a placement the user has already made — which is
    the commonest thing that happens on a flatbed scan half a patch out."""
    seen = {}
    import workflow.photo_fit as PF
    real = PF.refine_corners

    def spy(scan, boxes, corners, **kw):
        seen["from"] = [tuple(c) for c in corners]
        return real(scan, boxes, corners, **kw)

    monkeypatch.setattr(PF, "refine_corners", spy)
    start = _grown(demo["truth"], 0.30 * demo["pitch"])
    r = _run(demo, start, monkeypatch,
             answer=AutoAlignResult(reason="no-better"))
    assert seen["from"] == [tuple(c) for c in start], (
        "the reshaping did not start from the corners the user placed")
    assert r.ok and r.ending == "placed"
    assert _worst(r.corners, demo["truth"]) < 0.25 * demo["pitch"]


def test_the_search_answer_is_applied_when_the_reshaping_declines(
        demo, monkeypatch):
    """Q3, and it is the MAJORITY outcome: in 175 of 290 measured cells the
    search answers and the reshaping finds nothing better. Refusing everything
    there would throw away 155 correct placements — 53 % of the sweep — and the
    20 it would have been right to refuse are refused by the gate anyway."""
    import workflow.photo_fit as PF
    monkeypatch.setattr(PF, "refine_corners",
                        lambda *a, **k: RefineResult(reason="already-the-best-fit"))
    r = _run(demo, _shift(demo["truth"], 3.0 * demo["pitch"], 0.0), monkeypatch,
             answer=AutoAlignResult(corners=list(demo["truth"]), rho=0.99))
    assert r.ok, f"the search's own answer was thrown away: {r.ending}"
    assert r.ending == "placed"
    assert [tuple(c) for c in r.corners] == [tuple(c) for c in demo["truth"]]


def test_nothing_is_applied_when_both_halves_decline(demo, monkeypatch):
    """…and the corners come back untouched, not half-placed."""
    import workflow.photo_fit as PF
    monkeypatch.setattr(PF, "refine_corners",
                        lambda *a, **k: RefineResult(reason="too-far-to-fit"))
    start = _shift(demo["truth"], 2.0 * demo["pitch"], 0.0)
    r = _run(demo, start, monkeypatch,
             answer=AutoAlignResult(reason="no-better"))
    assert not r.ok and r.corners is None
    assert r.ending == "too-far"


# ------------------------------------------------------------- the gate LAST
def test_the_drift_gate_is_suspended_for_the_search_and_asked_once_at_the_end(
        demo, monkeypatch):
    """The order is the whole safety argument. A drift gate applied to the
    search's RAW answer throws away the placement the reshaping exists to
    rescue — measured over 35 photographs, that order rescues 9 cases and is
    defeated 0 times, because the 0.75-pitch clamp keeps an answer that is
    nearly a patch out from ever being polished into an accepted one."""
    import workflow.scan_auto_align as AA
    limits = []

    def fake(*a, **k):
        limits.append(k.get("drift_limit"))
        return AutoAlignResult(corners=list(demo["truth"]), rho=0.99)

    monkeypatch.setattr(AA, "auto_align", fake)
    asked = []
    real_drift = AA.seating_drift
    monkeypatch.setattr(AA, "seating_drift",
                        lambda scan, boxes, corners, *a, **k: (
                            asked.append([tuple(c) for c in corners])
                            or real_drift(scan, boxes, corners, *a, **k)))
    r = _run(demo, list(demo["truth"]), monkeypatch)
    assert limits and all(v == float("inf") for v in limits), (
        f"the search applied a drift gate of its own: {limits}")
    assert len(asked) == 1, "the drift was not asked exactly once, at the end"
    assert r.ok


def test_the_gate_sees_the_placement_that_is_about_to_be_applied(
        demo, monkeypatch):
    """Not the search's raw answer. The reshaping moves the corners after the
    search has spoken, so a check asked before it is a check of a placement
    that no longer exists."""
    import workflow.photo_fit as PF
    import workflow.scan_auto_align as AA
    moved = _grown(demo["truth"], 0.20 * demo["pitch"])
    monkeypatch.setattr(PF, "refine_corners",
                        lambda *a, **k: RefineResult(corners=list(moved),
                                                     moved_pitch=0.2))
    saw = []
    monkeypatch.setattr(AA, "border_agreement",
                        lambda scan, boxes, corners, *a, **k: (
                            saw.append([tuple(c) for c in corners]) or True))
    monkeypatch.setattr(AA, "seating_drift", lambda *a, **k: 0.0)
    _run(demo, list(demo["truth"]), monkeypatch,
         answer=AutoAlignResult(corners=list(demo["truth"]), rho=0.99))
    assert saw, "the picture check was never asked"
    assert saw[0] == [tuple(c) for c in moved], (
        "the check was asked about the search's answer, not about the "
        "placement that is going on screen")


def test_a_placement_the_picture_refuses_is_not_applied(demo, monkeypatch):
    """The end of the whole argument: a grid one whole patch out reads every
    patch as its neighbour and looks perfect from inside the sample boxes."""
    import workflow.photo_fit as PF
    slid = _shift(demo["truth"], demo["pitch"], 0.0)
    monkeypatch.setattr(PF, "refine_corners",
                        lambda *a, **k: RefineResult(corners=list(slid),
                                                     moved_pitch=0.5))
    r = _run(demo, list(demo["truth"]), monkeypatch,
             answer=AutoAlignResult(reason="no-better"))
    assert not r.ok and r.ending == "not-seated"


def test_the_true_placement_is_applied(demo, monkeypatch):
    """The control. Checks that refuse the right answer are not checks."""
    r = _run(demo, list(demo["truth"]), monkeypatch,
             answer=AutoAlignResult(corners=list(demo["truth"]), rho=0.99))
    assert r.ok and r.ending == "placed"


# ----------------------------------------------------- the number on screen
def test_the_agreement_shown_is_measured_at_the_corners_that_are_set(
        demo, monkeypatch):
    """The window quotes an agreement beside its own sentence "anything below
    0.80 is refused". The search's own score is measured BEFORE the reshaping
    moves anything, so quoting it would describe a placement that no longer
    exists."""
    import workflow.photo_fit as PF
    import workflow.scan_auto_align as AA
    moved = _grown(demo["truth"], 0.20 * demo["pitch"])
    monkeypatch.setattr(PF, "refine_corners",
                        lambda *a, **k: RefineResult(corners=list(moved),
                                                     moved_pitch=0.2))
    at = []
    monkeypatch.setattr(AA, "reference_agreement_at",
                        lambda scan, boxes, corners, *a, **k: (
                            at.append([tuple(c) for c in corners]) or 0.93))
    r = _run(demo, list(demo["truth"]), monkeypatch,
             answer=AutoAlignResult(corners=list(demo["truth"]), rho=0.42))
    assert at and at[-1] == [tuple(c) for c in moved]
    assert r.rho == 0.93, "the window would quote the search's stale score"


def test_a_placement_that_cannot_be_scored_against_the_reference_is_refused(
        demo, monkeypatch):
    """Both halves of one rule. The floor makes the sentence on screen true —
    over 233 applied placements the lowest agreement measured was 0.978, so it
    costs nothing — and it closes the one hole the merged operation would
    otherwise open: 59 of those 233 came from the reshaping alone, where
    nothing had asked whether the placement looks like this chart at all.

    An agreement that cannot be measured at all is refused too, because that
    means the reference's sample ids do not pair with this chart's — which is
    exactly what its message tells the user to go and look at, and because the
    window must never quote a number it did not measure."""
    import workflow.scan_auto_align as AA
    monkeypatch.setattr(AA, "reference_agreement_at", lambda *a, **k: 0.79)
    r = _run(demo, list(demo["truth"]), monkeypatch,
             answer=AutoAlignResult(corners=list(demo["truth"]), rho=0.99))
    assert not r.ok and r.ending == "below-floor"
    monkeypatch.setattr(AA, "reference_agreement_at", lambda *a, **k: None)
    r = _run(demo, list(demo["truth"]), monkeypatch,
             answer=AutoAlignResult(corners=list(demo["truth"]), rho=0.99))
    assert not r.ok and r.ending == "below-floor"


# --------------------------------------------------------------- the words
def test_every_ending_has_words_and_none_of_them_names_a_stage():
    """Basti's rule, and the reason the endings are not simply the two
    modules' reason codes concatenated: **a user must never be told which
    internal step failed.** They do not know there are steps, and "the fit
    stage was refused" is a sentence nobody can act on."""
    assert set(ENDINGS) - {"placed"} == set(M.SCAN_ALIGN_REFUSALS)
    banned = ("stage", "step one", "step two", "first pass", "second pass",
              "recogniser", "homography", "seating drift", "rho",
              "border agreement", "auto_align", "refine_corners",
              "photo_fit", "clamp_pitches")
    for ending in ENDINGS:
        msg = (M.M_SCAN_ALIGN_DONE if ending == "placed"
               else M.scan_align_refusal(ending))
        title, body = msg.render(ref_row="Target reference data",
                                 chart_row="Target type", rho="0.98")
        low = (title + " " + body).lower()
        for word in banned:
            assert word not in low, f"{ending} names {word!r}: {title}"


def test_every_refusal_says_what_to_do_next():
    """Friendly and extensive, written for a beginner: an ending that only says
    "no" leaves the user with a button that did nothing and no idea why."""
    for ending in ENDINGS:
        if ending == "placed":
            continue
        _t, body = M.scan_align_refusal(ending).render(
            ref_row="Target reference data", chart_row="Target type")
        low = body.lower()
        assert any(w in low for w in ("drag", "press", "check ", "scan the",
                                      "place the", "photograph it")), \
            f"{ending} tells the user nothing to do:\n{body}"
        assert len(body) > 120, f"{ending} is too thin to help anyone:\n{body}"


def test_no_ending_promises_the_grid_is_right():
    """The one claim no part of this operation can make. A grid exactly one
    patch out is identical, to everything measured inside the sample boxes, to
    the right answer — so an ending that says "the grid is on the patches"
    without a check having said so is a claim, not a fact."""
    for ending in ENDINGS:
        if ending == "placed":
            continue
        title, _b = M.scan_align_refusal(ending).render(
            ref_row="r", chart_row="c")
        assert "already on the patches" not in title.lower()
        assert "is on the patches" not in title.lower()


# --------------------------------------------------------------- the window
@pytest.fixture(scope="module")
def dlg(_app, tmp_path_factory):
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    d = ScannerProfileDialog(object(),
                             _FakeSettings(tmp_path_factory.mktemp("one-win")))
    d._mode_standard.click()
    cb = d._target_combo
    idx = [i for i in range(cb.count()) if cb.itemData(i) == "SpyderChecker"]
    assert idx, "the bundled SpyderChecker target is not in the combo"
    cb.setCurrentIndex(idx[0])
    d._reveal_target_files()                 # the real "Try with a demo scan"
    yield d
    d.deleteLater()


def _press(dlg, corners, monkeypatch, answer):
    import workflow.scan_auto_align as AA
    monkeypatch.setattr(AA, "auto_align", lambda *a, **k: answer)
    dlg._marquee.set_corners([tuple(c) for c in corners])
    dlg._capture_current_corners()
    mark = len(dlg._log.toPlainText())
    dlg._on_auto_align()
    app = QApplication.instance()
    deadline = time.monotonic() + 120.0
    while dlg._align_thread is not None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    app.processEvents()
    assert dlg._align_thread is None, "the placement never finished"
    return (dlg._log.toPlainText()[mark:],
            [tuple(c) for c in dlg._marquee.corners_image_px()])


def _window_truth(dlg):
    text = read_text(dlg._std_cht, lenient=True)
    boxes = parse_cht(text).patches
    _sc, px0, py0, pw, ph, _W, _H, _sr, _sh = demo_scan_layout(text, boxes)
    truth = [(px0, py0), (px0 + pw, py0), (px0 + pw, py0 + ph), (px0, py0 + ph)]
    bbox = (min(b.x1 for b in boxes), min(b.y1 for b in boxes),
            max(b.x2 for b in boxes), max(b.y2 for b in boxes))
    return truth, patch_pitch_px(boxes, truth, bbox)


def test_one_press_undoes_the_whole_operation_and_not_a_stage(dlg, monkeypatch):
    """Q1. The operation has three steps and the user pressed one button, so
    the undo returns the placement they were LOOKING AT when they pressed it —
    never the search's raw answer from between the steps, which was never on
    screen and which they could not name if it were."""
    from core.i18n import tr
    truth, pitch = _window_truth(dlg)
    start = _grown(truth, 0.30 * pitch)
    said, after = _press(dlg, start, monkeypatch,
                         AutoAlignResult(reason="no-better"))
    assert M.M_SCAN_ALIGN_DONE.title in said
    assert _worst(after, start) > 1.0, "nothing moved, so this proves nothing"
    assert dlg._auto_align_btn.text() == tr("Undo auto align")
    dlg._on_auto_align()
    back = [tuple(c) for c in dlg._marquee.corners_image_px()]
    for (ax, ay), (bx, by) in zip(back, start):
        assert abs(ax - bx) < 1e-6 and abs(ay - by) < 1e-6, (
            "the undo did not return the placement the user could see")
    assert dlg._auto_align_btn.text() == tr("Auto align")


def test_the_window_has_one_placement_button_and_it_runs_the_whole_operation(
        dlg):
    """Two controls for one job is what B8-42 removed. The separate button's
    slot, its helper methods and its own five messages are gone with it."""
    import inspect

    import ui.dialogs.scanin_dialog as sd
    assert not hasattr(dlg, "_fit_patches_btn")
    assert not hasattr(sd.ScannerProfileDialog, "_on_fit_patches")
    src = inspect.getsource(sd.ScannerProfileDialog._on_auto_align)
    assert "place_grid(" in src
    for gone in ("M_SCAN_FIT_DONE", "M_SCAN_FIT_NO_BETTER",
                 "M_SCAN_FIT_NOTHING", "M_SCAN_FIT_NOT_SEATED",
                 "scan_fit_refusal"):
        assert not hasattr(M, gone), f"{gone} was retired and is back"


def test_the_button_block_never_decides_how_narrow_the_window_can_be(dlg):
    """Removing or moving a button must not cost this window width.

    THE ROWS ARE READ OFF THE LAYOUT, NOT LISTED HERE. The previous version of
    this test wrote the four rows down as a list of lists, so the next
    rearrangement (beta 8, AGENT-S: four rows of six buttons became three of
    two) made it fail for describing the old shape rather than for anything
    being wrong. Its INTENT — the block must not get wider — is kept, and
    sharpened into the constraint that actually binds.

    Two claims:

    * the block's worst line is no wider than the 288 px the 2 + 2 + 1 + 1
      block needed at ITS worst (German). Measured over all thirteen
      catalogues, this one's worst is 269 px (Spanish) and 202 in English,
      which is the language this test runs in;
    * and the load-bearing one: that line still fits inside the width the
      right pane ALREADY needs for its other rows. `showEvent` pins the pane
      at `max(360, right_pane.minimumSizeHint().width()) + _PANE_GAP`, and
      that minimum is the pane's widest row — the diagnostic/fiducial checkbox
      grid, or the marquee's own 360 px floor. A block wider than every other
      row in the pane is a block that has widened the WINDOW, in every
      language at once, and the block's own worst line never says so.
    """
    from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout
    btns = {dlg._rotate_btn, dlg._auto_align_btn, dlg._reset_btn,
            dlg._reset_grid_btn, dlg._check_align_btn, dlg._popout_btn}
    for b in btns:
        assert isinstance(b, QPushButton)
        b.ensurePolished()

    block = None
    for lay in dlg.findChildren(QVBoxLayout):
        rows, found = [], set()
        for i in range(lay.count()):
            row = lay.itemAt(i).layout()
            if not isinstance(row, QHBoxLayout):
                continue
            widgets = [row.itemAt(j).widget() for j in range(row.count())]
            widgets = [w for w in widgets if w in btns]
            if widgets:
                rows.append(widgets)
                found |= set(widgets)
        if found == btns:
            block, block_rows = lay, rows
            break
    assert block is not None, "the six preview buttons are not in one block"

    worst = max(sum(b.sizeHint().width() for b in row) + 6 * (len(row) - 1)
                for row in block_rows)
    assert worst <= 288, (
        f"the button block's worst line is {worst} px, wider than the "
        f"2 + 2 + 1 + 1 block it replaces needed at its worst")

    # …and the pane's own floor, read off every OTHER row in the right column.
    col = dlg._right_pane_w.layout()
    other = 360                                   # the marquee's own minimum
    for i in range(col.count()):
        it = col.itemAt(i)
        if it.layout() is block:
            continue
        if it.widget() is not None:
            other = max(other, it.widget().minimumSizeHint().width())
        elif it.layout() is not None:
            other = max(other, it.layout().totalMinimumSize().width())
    assert worst <= other, (
        f"the button block needs {worst} px and the widest other row in the "
        f"pane needs {other} px — the block is now what sets this window's "
        f"minimum width, in every language at once")
