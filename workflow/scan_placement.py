"""Put the reading grid on the patches — one operation, in three steps.

WHY THIS IS ONE OPERATION AND NOT TWO BUTTONS.
Until beta 8 the scanner window offered "Auto align" and "Fit to the patches"
side by side, and Basti's objection was the right one: *"i don't want to have
two options where one is useless."* They are not useless — measured over 290
starting placements on ten conditions and five targets (beta 8, agent O), there
are **139 cases only the search can recover and 30 only the fit can** — but
they are not two things to CHOOSE between either. One SEARCHES the whole
picture for the chart and can only ever answer with a rectangle; the other
REFINES a placement that is already nearly right, through all eight degrees of
freedom a quad has, and can reach no further than three quarters of a patch.
A search and a refinement are the two halves of one job, and the user should
not have to know which half they need:

    ================  ==============  =============  ==============
    design            ends ON the     applied a placement that
                      patches         was still wrong
    ================  ==============  =============  ==============
    search alone      196/290 (68 %)  0
    refinement alone   87/290 (30 %)  41 of 118 applied
    press both         226/290 (78 %) 11
    **this module**   **244/290**     **0 of 233 applied**
    ================  ==============  =============  ==============

THE ORDER IS LOAD-BEARING, AND SO IS WHERE THE GATE SITS.
Search, then refine, then check — and the check is asked about the placement
that is about to be applied, not about the search's raw answer. The worry that
made this worth measuring is real: the refinement optimises "how flat does each
sample box look", and :func:`~workflow.scan_auto_align.seating_drift` measures
"how far would each box have to move to sit on flat colour", which is close to
the same quantity, so a refinement could in principle polish a wrong placement
until the gate stopped seeing it. Over 35 photographs — five targets at eight
tilts — that happened **0 times**, and **9** placements the old order threw away
came back correct. What stops it is not the gate, it is
:data:`~workflow.photo_fit.CLAMP_PITCHES`: an answer nine tenths of a patch out
needs more than 0.75 of a pitch of correction, the refinement refuses to move
that far, and the drift stays where the gate can still see it. **That clamp
must not be raised while these two are chained.**

WHAT HAPPENS WHEN A STEP DECLINES.
Neither step is required to answer, and the operation carries on either way:

* the search declines → **the user's own four corners are the working
  placement** and the refinement runs from them. This is not a nicety; without
  it the merged operation loses every small-offset photograph, because the
  search answers `no-better` about a placement the user already made and the
  refinement would never run at all.
* the refinement declines → **the search's answer is the working placement**
  and it goes to the gate as it is. Measured, this is the MAJORITY outcome —
  175 of the 290 cells — and in 155 of them the gate accepts and the grid lands
  on the patches. Refusing everything here would throw away 53 % of the sweep;
  and in the 20 where the gate refuses instead, the search's answer would have
  been wrong in 20 of 20.
* both decline → nothing is applied and the corners are left exactly where the
  user put them.

WHAT IT NEVER DOES.
It never applies a placement no check has seen. Every answer that reaches the
grid has passed :func:`~workflow.scan_auto_align.border_agreement` (which sees
a grid slid onto the neighbouring patch) and
:func:`~workflow.scan_auto_align.seating_drift` (which sees a photographed
sheet's keystone) on the exact corners about to be set, and carries a reference
agreement measured at those same corners rather than at the answer the search
gave before the refinement moved it.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

from core.logger import get_logger
from workflow.scan_auto_align import AGREEMENT_FLOOR

log = get_logger(__name__)

__all__ = ["PlacementResult", "place_grid", "search_region_for",
           "seated_verdict", "is_seated", "ENDINGS"]

#: The fraction of each patch the REFINEMENT judges a placement on, which is
#: deliberately not the fraction the read uses. A small centred box stays
#: inside its patch under a misplacement that a large one already overhangs, so
#: judging through the read's own 60 % box makes the judgement blind exactly
#: where it matters. 0.90 is the largest that still leaves a margin on a patch
#: with a slightly soft printed edge, and it changes nothing about what is read.
FIT_SAMPLE_AREA = 0.90

#: Every way this operation can end, as the machine-readable strings the log
#: and the tests use. They are NEVER shown to anybody: the user is told what
#: happened in the picture and what to do about it, and
#: :func:`workflow.measurement_messages.scan_place_message` is the only place
#: the two meet.
#:
#: Note what is not here: there is no ending that says which of the three steps
#: declined. A user does not know there are steps, and "the fit stage was
#: refused" is a sentence that tells them nothing they can act on.
ENDINGS = (
    "placed",              # the grid was moved onto the patches
    "not-seated",          # an answer was found and the picture refused it
    "not-recognised",      # the chart was not found in the picture at all
    "below-floor",         # found, and it does not match this reference
    "no-usable-candidate",  # found something, and this chart does not fit it
    "ambiguous-orientation",  # the chart reads the same more than one way up
    "no-chart-geometry",   # the chart file records no patch positions
    "no-better",           # nothing better than the user's own corners
    "too-far",             # the best placement is further than it may move
)

#: Search reasons that carry a diagnosis of their own — something about the
#: picture or about the files that the user can act on, and that no amount of
#: dragging the corners would change. When the search ends on one of these the
#: operation speaks with it, whatever the refinement went on to say.
#:
#: ``no-better`` is deliberately NOT in this set. It is the one search reason
#: that carries no diagnosis at all — it says only "your own placement scored
#: as well as mine" — so when it is all the search has to offer, the
#: refinement's reason is the only information there is.
_DIAGNOSTIC_SEARCH_REASONS = ("ambiguous-orientation", "below-floor",
                              "no-usable-candidate", "not-recognised",
                              "no-chart-geometry")

#: Refinement reasons that mean "the best placement I can see is further away
#: than I am allowed to move".
_TOO_FAR_REASONS = ("too-far-to-fit", "grid-outside-the-image")


def search_region_for(corners: "Sequence[tuple[float, float]] | None",
                      image_size: tuple[int, int],
                      ) -> "tuple[float, float, float, float] | None":
    """The rectangle the search may narrow itself to, or ``None``.

    Basti: *"the user can then limit the area"* — and deliberately with no
    second mode and no second gesture. If the corners have been put somewhere
    deliberate, which means anything covering less than 70 % of the sheet (the
    untouched opening rectangle covers more), the same recogniser runs again on
    a crop around them. It is the same search on a smaller picture, so it
    cannot be less safe; it only removes what was never the chart.

    It lives here rather than in the window so that the window and every
    measurement of the window run the same arithmetic.
    """
    if not corners or not image_size or not image_size[0] or not image_size[1]:
        return None
    xs = [p[0] for p in corners]
    ys = [p[1] for p in corners]
    area = (max(xs) - min(xs)) * (max(ys) - min(ys))
    if not (0 < area < 0.70 * image_size[0] * image_size[1]):
        return None
    pad = 0.06 * max(max(xs) - min(xs), max(ys) - min(ys))
    return (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)


@dataclass
class PlacementResult:
    """Where the grid should go, and everything the log needs to say why."""

    corners: list[tuple[float, float]] | None = None
    #: which of :data:`ENDINGS` this was
    ending: str = ""
    #: reference agreement measured AT THE CORNERS ABOVE, not at the search's
    #: raw answer -- the refinement may have moved it since
    rho: float | None = None
    #: agreement where the user's corners were, when there were any
    rho_before: float | None = None
    #: seating drift of the placement that was checked, in patch pitches
    drift: float | None = None
    #: how far the refinement moved the worst corner, in patch pitches
    moved: float = 0.0
    #: did the search find a usable answer, and did the refinement move it --
    #: for the log only. Neither ever reaches a window.
    found: bool = False
    fitted: bool = False
    find_reason: str = ""
    fit_reason: str = ""
    candidates: int = 0
    log_tail: str = ""
    rejected: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.corners is not None


def _ending(find_reason: str, fit_reason: str) -> str:
    """The ending, when neither step produced a placement to check.

    The search's reason wins whenever it is a diagnosis; otherwise the
    refinement's is the only thing there is to say.
    """
    if find_reason in _DIAGNOSTIC_SEARCH_REASONS:
        return find_reason
    if fit_reason in _TOO_FAR_REASONS:
        return "too-far"
    return "no-better"


def seated_verdict(scan: Path, boxes: Sequence,
                   corners: Sequence[tuple[float, float]],
                   ) -> "tuple[bool, float | None]":
    """``(is the grid on the patches, the seating drift)``, from the PICTURE.

    Two checks, because they see different faults and either one alone passes
    the other silently:

    * :func:`~workflow.scan_auto_align.border_agreement` sees a grid slid a
      whole patch onto its neighbours. Nothing measured INSIDE the sample boxes
      can — every box still sits squarely on flat colour — but the chart's own
      outer boundary walks off the printed block onto bare paper.
    * :func:`~workflow.scan_auto_align.seating_drift` sees a photographed
      sheet's keystone, which no rotated rectangle fits and no rank correlation
      notices, because the patches keep their brightness ORDER while sliding
      onto their neighbours.

    Measured over the 118 placements the old ungated "Fit to the patches"
    button applied in beta 8's 290-cell capture sweep, 41 ended more than a
    quarter of a patch pitch from the truth: these two refuse **41 of the 41**
    and 2 of the 77 correct ones.

    A check that cannot be made is not evidence of a fault. An exception here
    accepts and says so in the log, the same rule
    :func:`~workflow.scan_auto_align.auto_align` applies to its own drift.
    """
    from workflow.scan_auto_align import (SEATING_DRIFT_LIMIT,
                                          border_agreement, seating_drift)
    quad = [tuple(c) for c in corners]
    try:
        if border_agreement(scan, boxes, quad) is False:
            log.info("placement refused: the grid's edges are not the chart's")
            return False, None
        drift = seating_drift(scan, boxes, quad)
    except Exception:  # noqa: BLE001 — a safety check must not become a crash
        log.warning("could not check where the placed grid sits", exc_info=True)
        return True, None
    if drift is not None and drift > SEATING_DRIFT_LIMIT:
        log.info("placement refused: the patches do not sit where this grid "
                 "puts them (drift %.3f pitch)", drift)
        return False, drift
    return True, drift


def is_seated(scan: Path, boxes: Sequence,
              corners: Sequence[tuple[float, float]]) -> bool:
    """Is this placement on the patches? :func:`seated_verdict` without the
    number, for callers that only want the verdict."""
    return seated_verdict(scan, boxes, corners)[0]


def place_grid(scanin_exe: str | Path,
               scan: Path,
               cht: Path,
               cie: Path,
               boxes: Sequence,
               expected_y: dict[str, float],
               image_size: tuple[int, int],
               current_corners: Sequence[tuple[float, float]] | None = None,
               sample_frac: float = 0.6,
               fit_sample_frac: float = FIT_SAMPLE_AREA,
               floor: float = AGREEMENT_FLOOR,
               search_region: "tuple[float, float, float, float] | None" = None,
               timeout: int = 300,
               runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
               ) -> PlacementResult:
    """Search, refine, check — and return the corners only if the check passed.

    *current_corners* are the four corners on screen. They are used for three
    separate things and it is worth keeping them apart: as the placement the
    search must beat before it is worth moving anything, as the fallback the
    refinement starts from when the search declines, and (through
    *search_region*, which the caller computes) as a hint about where in the
    picture to look.
    """
    from workflow.photo_fit import refine_corners
    from workflow.scan_auto_align import auto_align, reference_agreement_at

    start = [tuple(c) for c in current_corners] if current_corners else None

    # ---- 1. the search, with the drift gate SUSPENDED --------------------
    # It is asked once at the end instead, of the placement that is actually
    # about to be applied. See the module docstring.
    found = auto_align(scanin_exe, scan, cht, cie, boxes, expected_y,
                       image_size, current_corners=current_corners,
                       sample_frac=sample_frac, drift_limit=float("inf"),
                       timeout=timeout, runner=runner)
    if not found.ok and search_region is not None:
        narrowed = auto_align(scanin_exe, scan, cht, cie, boxes, expected_y,
                              image_size, current_corners=current_corners,
                              sample_frac=sample_frac,
                              drift_limit=float("inf"),
                              search_region=search_region, timeout=timeout,
                              runner=runner)
        if narrowed.ok:
            found = narrowed

    res = PlacementResult(found=bool(found.ok), find_reason=found.reason,
                          rho_before=found.rho_before,
                          candidates=found.candidates,
                          log_tail=found.log_tail,
                          rejected=list(found.rejected))

    working = ([tuple(p) for p in found.corners] if found.ok else start)
    if working is None:
        # No answer and nowhere to refine from — the user has not placed a
        # grid at all. There is nothing to check and nothing to apply.
        res.ending = _ending(found.reason, "")
        return res

    # ---- 2. the refinement, from whichever placement that is -------------
    fit = refine_corners(scan, boxes, working, sample_frac=fit_sample_frac)
    res.fit_reason = fit.reason
    res.fitted = bool(fit.ok)
    res.moved = float(fit.moved_pitch or 0.0)
    candidate = [tuple(p) for p in fit.corners] if fit.ok else working

    if not (found.ok or fit.ok):
        # Both steps declined. Nothing has been proposed, so there is nothing
        # to submit to a check and nothing to apply.
        res.ending = _ending(found.reason, fit.reason)
        return res

    # ---- 3. the two picture checks, on the placement about to be applied --
    seated, drift = seated_verdict(scan, boxes, candidate)
    res.drift = drift
    if not seated:
        res.ending = "not-seated"
        return res

    # ---- 4. and the colour check, at the same corners ---------------------
    # The number the window shows must be a number about the corners the window
    # is about to set. The search's own `rho` is measured BEFORE the refinement
    # moves anything, so quoting it would describe a placement that no longer
    # exists -- and where the search declined altogether there is no `rho` at
    # all, so the refinement's answer would reach the grid with nothing having
    # asked whether it looks like this chart. Measured over 290 starting
    # placements: 59 of the 233 that were applied came from the refinement
    # alone, and the floor refuses 0 of the 233 (the lowest agreement among
    # them is 0.978), so this costs nothing and closes that hole.
    #
    # An agreement that cannot be measured at all is a refusal here rather than
    # a shrug, and deliberately so: it means the reference's sample ids do not
    # pair with this chart's, which is exactly what M-SCAN-ALIGN-NO-MATCH tells
    # the user to go and look at -- and it is also the only state in which the
    # window could otherwise claim an agreement it never measured.
    rho = None
    try:
        rho = reference_agreement_at(scan, boxes, candidate, expected_y,
                                     sample_frac)
    except Exception:  # noqa: BLE001
        log.warning("could not measure the agreement at the placed grid",
                    exc_info=True)
    res.rho = rho
    if rho is None or rho < floor:
        res.rejected.append(
            "the placement does not agree with this chart's reference "
            f"({'not measurable' if rho is None else format(rho, '.3f')})")
        res.ending = "below-floor"
        return res

    res.corners = candidate
    res.ending = "placed"
    return res
