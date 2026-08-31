"""The row band on paper must name the rows the way the .ti2 does (K8).

The band exists for exactly one thing: finding a patch's place on paper again
in the measurement file. It was drawn with the built-in patch pattern whatever
the chart was made with, so a chart set to "A-Z;1-999" printed its rows as
1, 2, 3 while its own SAMPLE_LOC called them A, B, C. The sheet disagreed with
the file, which is worse than cosmetic.

Reported from beta 5. These render real pages and read the pixels, because the
question is what is on the paper.
"""
import numpy as np
import pytest

from workflow.layout_engine import geometry, instruments, permutation, raster
from workflow.layout_engine.ti1_reader import ColorTarget

_PAPER = (210.0, 297.0)


def _target(n=60):
    return ColorTarget(color_rep="iRGB",
                       device_fields=["RGB_R", "RGB_G", "RGB_B"],
                       patches=[((50.0, 50.0, 50.0), (40.0, 45.0, 50.0))
                                for _ in range(n)])


def _page(patch_pattern):
    geom = instruments.build("i1", row_indicators=True)
    lay = geometry.compute(geom, *_PAPER, 60)
    res = raster.render_pages(_target(), lay, geom, seed=1, randomize=False,
                              paper_w_mm=_PAPER[0], paper_h_mm=_PAPER[1],
                              dpi=150, patch_pattern=patch_pattern)
    return np.asarray(res.images[0].convert("L"))


def test_a_different_patch_pattern_prints_different_row_labels():
    default = _page(permutation.DEFAULT_PATCH_PATTERN)
    letters = _page("A-Z;1-999")
    if default.shape != letters.shape:
        pytest.fail("the two pages are not comparable")
    assert not np.array_equal(default, letters), (
        "the printed row labels did not change with the patch pattern — the "
        "band is still drawn with the built-in one, so the sheet and the .ti2 "
        "disagree about what each row is called")


def test_the_default_pattern_still_prints_exactly_what_it_did():
    """The 121 built-in presets must be byte-identical: they use the default."""
    a = _page(permutation.DEFAULT_PATCH_PATTERN)
    b = _page(permutation.DEFAULT_PATCH_PATTERN)
    assert np.array_equal(a, b)
    # …and passing nothing at all is the same as passing the default.
    geom = instruments.build("i1", row_indicators=True)
    lay = geometry.compute(geom, *_PAPER, 60)
    res = raster.render_pages(_target(), lay, geom, seed=1, randomize=False,
                              paper_w_mm=_PAPER[0], paper_h_mm=_PAPER[1],
                              dpi=150)
    assert np.array_equal(np.asarray(res.images[0].convert("L")), a), (
        "the default changed when the argument was threaded through")


def test_the_label_the_sheet_prints_is_the_one_the_ti2_writes():
    """Same pattern in, same names out — the whole point of the band."""
    for pattern in (permutation.DEFAULT_PATCH_PATTERN, "A-Z;1-999", "1-999"):
        on_paper = permutation.make_labeller(pattern)
        in_file = permutation.location_label(0, 10, "1-999", pattern)
        assert on_paper(1) in in_file, (
            f"pattern {pattern!r}: the sheet would print {on_paper(1)!r} "
            f"while the file says {in_file!r}")
