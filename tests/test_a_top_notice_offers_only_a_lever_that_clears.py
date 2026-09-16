"""The "Prioritise patch size" strip-letter notice offered a dead lever.

Round 1 of beta 19 taught this sentence to fire in the layout it describes
(B8-241). Nobody had driven its SECOND HALF there, and the second half was

    "Lower “Label offset” under “Strip letters only” by about {over} mm,
     or use a smaller label size."

The first is exact. The second cannot work at any typed size, because in this
one layout the PATCH BLOCK's own top reserve contains the label band
(`geometry.placement`: ``mints = margin_t + txhi + lcar``), so shrinking the
type lifts the patch area by very nearly as much as it lifts the letters' ink.
What is left over is the "Label offset", which the band does not contain.

**DRIVEN ON SCREEN**, i1Pro / A4 / "Prioritise patch size" with "Use instrument
margins" off, top margin 10 mm, the strip-letter Size box walked from 20 pt to
1 pt (the smallest it accepts before "auto"), the chart regenerated at every
step and every figure taken off the rendered TIFF
(`~/Desktop/ChromIQ-beta18-proof/beta19-round-2/q6.json`, `q7.json`):

| Label offset | at 20 pt | at 1 pt | warning cleared? |
|---|---|---|---|
| 11 (the smallest that warns at all) | 1.9 mm on the patches | 0.3 mm | **no** |
| 12 | 2.9 | 1.3 | **no** |
| 16 | 6.9 | 5.3 | **no** |
| 24 | 14.9 | 13.3 | **no** |

The whole travel of the box is worth 1.6 mm at every offset, and the panel
stays red at the bottom of it. A reader who took the offer made their strip
letters illegible and still had letter ink on the first row of patches.

In "Prioritise chart area" the same offer is real: 8 pt clears a 4.3 mm
collision there, measured the same way (`q5.json`). So only the one wording
changes, and this file pins both halves of that. B8-243.
"""
from __future__ import annotations

import inspect
import os
import textwrap

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.layout_engine import geometry, instruments        # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe         # noqa: E402

_PAPER = (210.0, 297.0)


def _geom(**kw):
    r = LayoutRecipe()
    r.instrument, r.paper, r.dpi = "i1", "A4", 300
    r.use_instrument_margins = False
    r.margin_top = r.margin_bottom = r.margin_left = r.margin_right = 10.0
    r.text_edge_top_mm = 8.0
    r.show_strip_indicators = True
    for k, v in kw.items():
        setattr(r, k, v)
    return instruments.geom_from_build_kwargs(r.build_kwargs())


def _patch_top_mm(g, npat: int = 400):
    """Where `placement` puts the first patch row, from the paper's top."""
    layout = geometry.compute(g, *_PAPER, npat)
    return geometry.placement(g, *_PAPER, layout).y0_first


# ------------------------------------------------- the mechanism, not the text
@pytest.mark.parametrize("small_pt,big_pt", ((1.0, 20.0), (6.0, 14.0)))
def test_a_smaller_label_lifts_the_patch_area_with_the_letters(small_pt, big_pt):
    """In "Prioritise patch size" the size box is not a remedy.

    The letters' ink and the patch block move UP together when the type
    shrinks, so the collision between them barely changes. Measured on screen
    the whole box was worth 1.6 mm; this asserts the mechanism that makes it
    so, which is that the patch block follows the band by most of the way.

    MUTATION: take `txhi` out of `placement`'s patch-first ``mints`` and this
    goes red, because the patch block then stops following the label band.
    """
    def _state(pt):
        g = _geom(layout_mode="patch_first",
                  indicator_size_mm=pt * 25.4 / 72.0,
                  strip_label_offset_mm=12.0)
        return (_patch_top_mm(g),
                geometry.strip_label_leader_top_mm(g) + float(g.label_ink_reach_mm))

    top_s, ink_s = _state(small_pt)
    top_b, ink_b = _state(big_pt)
    ink_gain = ink_b - ink_s                  # how far the ink rose
    top_gain = top_b - top_s                  # how far the patch block rose
    assert ink_gain > 0.5, "the size box did not move the letters' ink at all"
    assert top_gain >= 0.6 * ink_gain, (
        f"{small_pt} pt vs {big_pt} pt: the letters' ink rose {ink_gain:.3f} mm "
        f"and the patch area only {top_gain:.3f} mm, so a smaller label size "
        f"WOULD be a remedy here and the message may offer it again")


def test_prioritise_chart_area_really_does_give_the_size_box_its_travel():
    """The other half, so the fix cannot be swept across both wordings.

    With the margins as law the patch block does not follow the band at all,
    so every millimetre the type loses is a millimetre off the collision, and
    "or use a smaller label size" stays in the area-first sentence.
    """
    def _state(pt):
        g = _geom(layout_mode="area_first",
                  indicator_size_mm=pt * 25.4 / 72.0)
        return (_patch_top_mm(g),
                geometry.strip_label_leader_top_mm(g) + float(g.label_ink_reach_mm))

    top_s, ink_s = _state(6.0)
    top_b, ink_b = _state(20.0)
    assert ink_b - ink_s > 1.0
    assert abs(top_b - top_s) < 0.2, (
        "the patch block moved with the label band under “Prioritise chart "
        "area”, where the margin is supposed to be the law")


# -------------------------------------------------------------- the sentences
def _sentences() -> "list[str]":
    """Every `tr("...")` literal in `_engine_text_notes`, joined.

    Parsed rather than sliced out of the text, because these sentences are
    written across a dozen implicitly concatenated lines and a marker can fall
    on a line break.
    """
    import ast
    from ui.tabs import tab_chart
    src = inspect.getsource(tab_chart.TabChart._engine_text_notes)
    tree = ast.parse(textwrap.dedent(src))
    out = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "tr" and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)):
            out.append(node.args[0].value)
    return out


_TOP_EDGE = "⚠ The strip letters are printed over the patches."


def _wording(marker: str) -> str:
    """The one TOP-EDGE sentence that carries *marker*.

    Three of them start with the same clause and differ only in which control
    they blame, so the subject is matched first and the marker second.
    """
    hits = [s for s in _sentences()
            if s.startswith(_TOP_EDGE) and marker in s]
    assert len(hits) == 1, f"{marker!r} matched {len(hits)} top-edge sentences"
    return hits[0]


def test_the_patch_first_sentence_does_not_offer_the_size_box():
    """MUTATION: put ", or use a smaller label size" back into that one
    sentence and this goes red."""
    said = _wording("Prioritise patch size")
    assert "Lower “Label offset”" in said, (
        "the one remedy that was measured to clear this is gone")
    assert "or use a smaller label size" not in said, (
        "the “Prioritise patch size” notice offers the label size as a remedy "
        "again, and no typed size clears the collision in that layout "
        "(B8-243)")


def test_it_still_says_which_two_controls_do_nothing_there():
    """The reader has to be told, or they reach for them anyway."""
    said = _wording("Prioritise patch size")
    assert "Text distance from edge (mm)" in said
    assert "smaller label size lifts the patch area" in said, (
        "the sentence no longer says why a smaller label size will not help")


@pytest.mark.parametrize("marker", ("by “T” under", "the ruler helper markers"))
def test_the_area_first_sentences_keep_the_offer(marker):
    """Both margins-are-law wordings keep it, because there it works."""
    said = _wording(marker)
    assert "or use a smaller label size" in said, (
        f"{marker}: a working remedy was swept out of the wrong sentence")
