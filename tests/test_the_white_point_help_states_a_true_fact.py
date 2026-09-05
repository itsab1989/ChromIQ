"""The white-point help in Tools ▸ Build profile with scanner or camera must
not tell the user something ArgyllCMS does not do.

**This is a correction, not a preference.** The shipped tooltip said, of the
manual white-point scale:

    "The white-point scale factor used by 'Manual white-point scale' above.
     1.00 makes no change."

ArgyllCMS `colprof.c:494` sets ``autowpsc = 1`` *before* it ever looks at the
number, and `xfit.c:2753` makes the default scale 1.0 anyway — so ``-u 1`` is
byte-for-byte a bare ``-u``. Built both from a real IT8 scan (2026-09-05):

    colprof -ax -qm -u     ->  wtpt 1.591736 1.624054 1.343185
    colprof -ax -qm -u 1   ->  wtpt 1.591736 1.624054 1.343185   (identical)

The worked example in the same tooltip was inverted too: it offered ``0.90`` as
the way to keep a slightly darker white white, and ``-u 0.9`` measures a white
point of Y **1.461655** — a scan about 44 % darker, the opposite of what the
sentence promised. Knut followed those instructions and built a profile he did
not intend; that is what these assertions exist to stop happening again.

The third fault is the list itself: **two different entries were labelled
``(-u)``** — "Auto-scale to avoid clipping (-u)" and "Manual white-point scale
(-u)". They are the same flag, one of them with a number after it, and a user
comparing the two labels could only conclude they were alternatives.
"""
from __future__ import annotations

import re

import pytest

from ui.dialogs import scanner_colprof as sc


def test_the_help_no_longer_says_a_scale_of_one_changes_nothing():
    """The exact false sentence, and any restatement of it, is gone."""
    body = sc._TIP_WP_SCALE
    assert "1.00 makes no change" not in body
    assert "1,00 makes no change" not in body
    # …and not smuggled back in a different arrangement. Any SENTENCE that
    # puts "1.00" next to "no change" has to be denying the equivalence, not
    # asserting it — this file's own replacement text says "1.00 does not mean
    # 'no change'", which is the sentence we want and the one a crude
    # substring search would also have caught.
    for sentence in re.split(r"(?<=[.!?])\s+", body):
        if "1.00" in sentence and "no change" in sentence.lower():
            assert re.search(r"\b(not|never|n't)\b", sentence, re.I), (
                f"asserts the equivalence again: {sentence!r}")


def test_the_help_says_what_a_scale_of_one_really_is():
    """Removing a falsehood is not enough — the user still has to be told."""
    body = sc._TIP_WP_SCALE
    assert "1.00" in body
    assert "on top of" in body.lower()          # it multiplies the auto scale
    # It must name the option a scale of 1.00 is actually equal to, so the user
    # can tell the two apart, and the option that really does leave white alone.
    assert "Auto-scale to avoid clipping" in body
    assert "Map chart white to white" in body


def test_the_inverted_worked_example_is_gone():
    """0.90 was offered as "keeps a darker white white". Measured, it is 44 %
    darker. If 0.90 is mentioned at all it must be as a warning, not a recipe."""
    body = sc._TIP_WP_SCALE
    if "0.90" in body or "0,90" in body:
        window = body[max(0, body.find("0.90") - 200):body.find("0.90") + 260]
        assert "darker" in window.lower(), (
            "0.90 is named without saying it makes the scan darker")
        assert not re.search(r"0[.,]90[^.]{0,80}still comes out as white", body)


def test_the_bullet_list_agrees_with_the_box_below_it():
    """`_TIP_WP`'s own entry for the manual scale carried the same falsehood in
    shorter form — "you set the scale yourself in the box below"."""
    body = sc._TIP_WP
    assert "you set the scale yourself in the box below" not in body
    manual = body[body.find("• Manual white-point scale"):]
    manual = manual[:manual.find("\n\n")]
    assert manual, "the manual white-point bullet has gone missing"
    assert "1.00" in manual and "Auto-scale" in manual


def test_no_two_white_point_options_are_labelled_with_the_same_flag():
    """Two entries said "(-u)". Whatever the labels become, the parenthesised
    flag has to be unique — it is the only thing distinguishing them at a
    glance."""
    flags = []
    for _key, label in sc.WP_MODE_CHOICES:
        m = re.search(r"\(([^)]*-u[^)]*)\)", label)
        if m:
            flags.append(m.group(1).strip())
    assert flags, "no white-point option names its flag any more"
    assert len(flags) == len(set(flags)), f"duplicate flag labels: {flags}"


def test_the_manual_scale_option_says_it_takes_a_number():
    """`-u` and `-u <scale>` are the same flag; the label has to show that the
    second one is the first WITH a number, not a different mechanism."""
    label = dict(sc.WP_MODE_CHOICES)["scale"]
    assert "-u" in label
    assert label != "Manual white-point scale (-u)"
    assert re.search(r"-u\s+\S", label), (
        f"{label!r} does not show that this option passes a number to -u")


@pytest.mark.parametrize("const", ["_TIP_WP", "_TIP_WP_SCALE"])
def test_the_corrected_bodies_are_still_reachable_by_the_extractor(const):
    """`_green_tip` applies `tr()` to a *parameter*, so these bodies only reach
    the catalogues through `_i18n_tooltip_anchors`. A rewrite that forgot to
    keep them there would ship untranslatable help."""
    import inspect
    src = inspect.getsource(sc._i18n_tooltip_anchors)
    assert f"tr({const})" in src
