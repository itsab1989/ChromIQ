"""K43 (Knut, #182 5833695633, 2026-09-25): the tone value of a neutral aim.

Knut, asked whether the 30 to 70 % tone row should place a FROM PROFILE GAMUT
chart's neutral aims at ``100 - L*`` or relative to the chart's own white and
black: *"Analyse and simulate, as well as search online for normal practice.
Make a decision based on well founded reasoning from the tests and
simulations, and argue what is the best method and why, and the consequences
of using wrong method."*

Decided (analysis: ``~/Desktop/ChromIQ-beta44-proof/k43/REPORT.md``): the tone
value is measured between the chart's OWN paper (0 %) and its own darkest
neutral aim (100 %), in L*. That is ISO 20654's spot colour tone value for a
neutral colour, and every printing standard measures a tone value between the
paper and the solid; ``100 - L*`` measures it between an L* 100 and an L* 0
that no paper and no ink reach, and on a plain or matte paper (black L* 15 to
28) it judged the shadows as mid-tones. Every other chart is unchanged.

Each test names the mutation it was proved red on.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import measurement_report as MR                      # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

#: The master set's own grey wedge (sRGB steps), as ChromIQ's FROM PROFILE
#: GAMUT module takes it: the L* of each step.
WEDGE = (97.2, 94.4, 91.5, 88.5, 85.6, 82.6, 79.7, 76.7, 73.7, 70.6, 67.6,
         64.5, 61.3, 58.2, 55.0, 51.8, 48.5, 45.2, 41.8, 38.4, 35.0, 31.5,
         27.9, 24.2, 20.5, 16.6, 12.6, 8.3, 3.8)


def _chart(paper: float, black: float, paper_corner: "float | None" = None,
           measured=None):
    """A FROM PROFILE GAMUT chart's grey axis: the wedge steps the paper and
    black can print, the darkest printable standing in for the black, and
    optionally the bare-paper corner (device white) aiming at *paper_corner*.
    *measured* maps an aim L* to the L* the sheet read (default: the aim)."""
    ls = [v for v in WEDGE if black <= v <= paper - 0.5] + [black]
    ids = [str(i + 1) for i in range(len(ls))]
    aims = {sid: (float(v), 0.0, 0.0) for sid, v in zip(ids, ls)}
    # the device values of a neutral aim are the profile's numbers, never
    # R = G = B here, so no device grey axis can answer instead
    rgb = [(min(99.0, v), min(99.0, v) - 1.5, min(99.0, v) - 0.7) for v in ls]
    corners: "set[str]" = set()
    if paper_corner is not None:
        ids.append("W")
        aims["W"] = (float(paper_corner), 0.0, -2.0)
        rgb.append((100.0, 100.0, 100.0))
        corners.add("W")
    lab = [(float(measured(aims[s][0]) if measured else aims[s][0]),
            aims[s][1], aims[s][2]) for s in ids]
    return MR.ramps_block(np.asarray(rgb, float), lab, aims, ids,
                          neutral_aims=aims, corner_ids=corners)


def test_a_plain_papers_shadows_are_not_its_mid_tones():
    """A plain paper (paper L* 92.5, black L* 20.5, as the ET-8550 plain paper
    profiles on this machine print): the shadows just above its black, L* 27
    to L* 40, print 3 L* dark. They are 70 to 90 % of the way from its paper
    to its black, so the mid-tone row does not see them (ΔL* 0, a PASS),
    where ``100 - L*`` counted them as 60 to 73 % and failed the row.

    MUTATION, proven red: ``tv_of`` back to ``100 - L*`` (max ΔL* 3.0)."""
    def shadow_fault(v):
        return v - 3.0 if 27.0 <= v <= 40.0 else v
    b = _chart(92.5, 20.5, paper_corner=92.5, measured=shadow_fault)
    grey = b["axes"]["grey"]
    assert grey["eligible"] and grey["source"] == "neutral_aims"
    assert grey["tone_scale"] == [92.5, 20.5]
    assert grey["max_dl"] == 0.0


def test_its_light_mid_tones_are():
    """…and a fault in its light mid-tones, L* 66 to 72 (29 to 37 % of the
    way), IS in the band, which ``100 - L*`` put only half inside.

    MUTATION, proven red: ``tv_of`` back to ``100 - L*`` (70.6 falls out of
    the band, max ΔL* 2.0 from 67.6 alone, not the 3.0 at 70.6)."""
    def light_fault(v):
        return v + (3.0 if v >= 70.0 else 2.0) if 66.0 <= v <= 72.0 else v
    b = _chart(92.5, 20.5, paper_corner=92.5, measured=light_fault)
    assert b["axes"]["grey"]["max_dl"] == 3.0


def test_the_paper_is_the_charts_own_paper():
    """An absolute chart: its lightest printable neutral aim is L* 91.5, its
    bare-paper corner aims at the profile's paper, L* 96. The scale starts at
    the paper.

    MUTATION, proven red: call `neutral_aim_tone_scale` without the paper
    corners (the scale starts at 91.5)."""
    b = _chart(92.0, 3.8, paper_corner=96.0)
    assert b["axes"]["grey"]["tone_scale"] == [96.0, 3.8]


def test_a_media_relative_chart_starts_at_its_own_white():
    """A media-relative chart carries a neutral aim at L* 100 (the paper in
    its own frame); its scale starts there even when the paper corner aims
    at the profile's absolute paper, L* 95.

    MUTATION, proven red: take the paper corner's L* instead of the lightest
    of it and the neutral aims (``paper = max(paper_ls)``)."""
    b = _chart(100.5, 24.2, paper_corner=95.0)
    assert b["axes"]["grey"]["tone_scale"][0] == 97.2
    b = MR.ramps_block(
        np.asarray([(100, 99, 98), (50, 49, 48), (99.6, 99.6, 99.6)], float),
        [(100.0, 0, 0), (60.0, 0, 0), (95.0, 0, -2)],
        {"1": (100.0, 0, 0), "2": (60.0, 0, 0), "W": (95.0, 0, -2)},
        ["1", "2", "W"],
        neutral_aims={"1": (100.0, 0, 0), "2": (60.0, 0, 0),
                      "W": (95.0, 0, -2)},
        corner_ids={"W"})
    assert b["axes"]["grey"]["tone_scale"] == [100.0, 60.0]


def test_the_tone_value_is_iso_20654s_for_a_neutral():
    """ISO 20654:2017 formulae (1), (7) to (9), computed from CIELAB, for a
    neutral tone on a neutral paper and a neutral solid, equals
    `neutral_aim_tone_value`.

    MUTATION, proven red: a Murray-Davies tone value on CIE Y instead."""
    def sctv(t, p, s):
        def v(lab):
            L, a, b = lab
            return np.array([L + 116 / 500 * a, L, L - 116 / 200 * b])
        return 100 * np.linalg.norm(v(t) - v(p)) / np.linalg.norm(v(s) - v(p))
    scale = MR.neutral_aim_tone_scale([90.0, 55.0, 18.0])
    for L in (80.0, 55.0, 30.0):
        assert MR.neutral_aim_tone_value(L, scale) == pytest.approx(
            sctv((L, 0, 0), (90.0, 0, 0), (18.0, 0, 0)), abs=1e-9)


def test_the_spacing_tolerance_is_given_in_lightness():
    """The N-A sentence says "none lies within {tol} of the lightness L*
    {level}": both numbers are L* on this chart's scale, 4 tone-value points
    being 4 x (92.5 - 20.5) / 100 = 2.9 L*.

    MUTATION, proven red: leave ``spacing_tol_l`` out (the sentence then
    prints 4, a tone-value distance beside an L*)."""
    aims = {"p": (92.5, 0, 0), "k": (20.5, 0, 0),
            "1": (92.5 - 0.72 * 32, 0, 0), "2": (92.5 - 0.72 * 33, 0, 0),
            "3": (92.5 - 0.72 * 60, 0, 0)}
    ids = list(aims)
    b = MR.ramps_block(np.asarray([(40.0, 55.0, 70.0)] * len(ids)),
                       [aims[s] for s in ids], aims, ids, neutral_aims=aims)
    assert b["reason"] == MR.REASON_RAMP_NEUTRAL_AIMS_BUNCHED
    assert b["spacing_tol_l"] == 2.9
    assert b["missing_level"] == pytest.approx(92.5 - 0.72 * 46, abs=0.06)


def test_a_chart_with_one_neutral_level_has_no_scale():
    """One neutral level is not a scale: no tone value, no ramp.

    MUTATION, proven red: return ``(paper, black)`` whatever their distance
    (a ZeroDivisionError)."""
    assert MR.neutral_aim_tone_scale([50.0, 50.0]) is None
    b = _chart(51.0, 50.0)
    assert b["reason"] == MR.REASON_RAMP_TOO_FEW_NEUTRAL_AIMS


#: Where the rule is stated to a reader. None of them may still say the band
#: is "between L* 30 and L* 70" or "100 minus" an L*.
_TEXTS = ("workflow/compliance_sets.py", "ui/dialogs/preset_verification_dialog.py",
          "ui/dialogs/measurement_report_dialog.py", "ui/dialogs/welcome_dialog.py")


def test_no_text_still_states_the_old_rule():
    """MUTATION, proven red: put "between L* 30 and L* 70" back into
    `_R_RAMPS_AIMS`."""
    for rel in _TEXTS:
        text = re.sub(r'"\s*\n\s*"', "", (ROOT / rel).read_text(encoding="utf-8"))
        assert "L* 30 and L* 70" not in text, rel
        assert "L* 70 and L* 30" not in text, rel
        assert "L* 70 down to L* 30" not in text, rel
        assert "100 minus its aim" not in text, rel
    from workflow import compliance_sets as CS
    assert "darkest neutral aim" in CS._R_RAMPS_AIMS
