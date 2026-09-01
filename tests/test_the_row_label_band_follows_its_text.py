"""§R1.2 — the band follows the label's TEXT SIZE, not a fixed 7.5 mm.

`docs/design/row_label_geometry.md`, Knut's own words: *"Their position follows
'Text distance to edge' and the Clip setting — it is not a fixed 7.5 mm,
because the label text size varies."*

This is the headline rule of that design, and a challenge round found it had NO
test: putting the constant back gave bands of 7.50 mm for every size and page
counts of 345 where the real ones were 345/368/322, and the whole suite stayed
green.
"""
import pytest

from workflow.layout_engine import geometry, instruments, papers
from workflow.layout_engine.presets import LayoutRecipe

_PT = 25.4 / 72.0


def _geom(pt: float = 0.0, *, instrument="i1", clip=False):
    r = LayoutRecipe()
    r.instrument, r.paper, r.layout_mode = instrument, "A4", "patch_first"
    r.show_row_indicators, r.show_strip_indicators = True, True
    r.clip_border = clip
    r.margin_top = r.margin_right = r.margin_bottom = r.margin_left = 6.0
    if pt:
        r.indicator_size_mm = pt * _PT
    return instruments.geom_from_build_kwargs(r.build_kwargs())


def test_a_bigger_label_reserves_a_wider_band():
    small, large = _geom(8.0).rlwi, _geom(16.0).rlwi
    assert large > small + 1.0, (
        f"8 pt reserved {small:.2f} mm and 16 pt {large:.2f} mm — the band is "
        f"not following the text size, which is §R1.2's whole point")


def test_the_band_is_not_a_constant():
    bands = {pt: round(_geom(pt).rlwi, 2) for pt in (6.0, 8.0, 12.0, 16.0, 24.0)}
    assert len(set(bands.values())) >= 4, (
        f"the band barely moves with the text size: {bands}")
    assert 7.5 not in set(bands.values()) or len(set(bands.values())) > 1, (
        "every size produced the old fixed 7.5 mm")


def test_the_page_count_moves_with_it():
    """A wider band means a wider margin, which means fewer patches."""
    w_mm, h_mm = papers.dimensions_mm("A4")
    counts = {pt: geometry.patches_per_sheet(_geom(pt), w_mm, h_mm)
              for pt in (8.0, 16.0, 24.0)}
    assert len(set(counts.values())) > 1, (
        f"the sheet holds the same number of patches at every label size: "
        f"{counts}")
    assert counts[8.0] > counts[24.0], (
        f"bigger labels did not cost patch area: {counts}")


def test_the_distance_to_edge_moves_the_margin():
    """§R1.2's other half: the position follows "Text distance to edge"."""
    def margin(edge_mm):
        r = LayoutRecipe()
        r.instrument, r.paper, r.layout_mode = "i1", "A4", "patch_first"
        r.show_row_indicators, r.show_strip_indicators = True, True
        r.clip_border = False
        r.text_edge_clip_mm = edge_mm
        r.margin_top = r.margin_right = r.margin_bottom = r.margin_left = 6.0
        return instruments.geom_from_build_kwargs(r.build_kwargs()).margin_l

    near, far = margin(2.0), margin(15.0)
    assert far > near + 10.0, (
        f"a 2 mm and a 15 mm text distance gave {near:.2f} and {far:.2f} mm — "
        f"identical positions were exactly the fault §R1.2 describes")


@pytest.mark.parametrize("instrument", ["i1", "CM", "SS", "CR30"])
def test_it_holds_for_every_instrument(instrument):
    small, large = _geom(8.0, instrument=instrument).rlwi, \
        _geom(24.0, instrument=instrument).rlwi
    assert large > small, f"{instrument}: {small:.2f} vs {large:.2f} mm"
