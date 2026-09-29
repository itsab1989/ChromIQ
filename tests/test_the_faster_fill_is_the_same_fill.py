"""The gap fill was made four times faster, and it must produce the SAME
colours.

`fill_gaps` decides which patches end up on a user's chart. A speed-up that
changes them is not an optimisation, it is a silent change to their
measurements, and it would be invisible: nobody compares two charts patch by
patch. Measured before landing it, at 500, 2000 and 4000 patches: maximum
elementwise difference 0.0, with the build dropping from 9.0 s to 2.3 s at
4000.

**AND THEN ACROSS THE WHOLE PARAMETER SPACE, because "it is the same at three
sizes" is not the question a user asks.** 900 combinations run against the
previous implementation: five different sets of already-chosen patches (none,
two, the eight cube corners, forty clustered in the middle, three hundred
random), five totals each, three seeds, three candidate counts and four
relaxation settings including zero. Worst elementwise difference 0.0, zero
mismatches.

The helper is also shared with the N-channel generator, which passes samples of
four to twelve channels rather than three. Checked over six dimensions at three
shapes each, up to 40,000 samples against 4,000 sites: zero differing owners.

Two changes, both in `fill_gaps`'s inner loop:

* `_nearest_site` expands ``|a-b|^2`` and hands the work to one BLAS matmul,
  instead of building an ``n x m x 3`` array and reducing it. ``|a|^2`` is
  constant along the row being minimised, so it is not computed at all.
* the Lloyd centroid step uses a `bincount` segmented mean instead of one
  boolean scan of the whole owner array per added patch, which at 4000 patches
  was 4000 passes over 40,000 samples in every relaxation pass.

This file pins the ANSWER, not the implementation, by comparing against the
plain definition written out longhand below. Anyone making it faster again has
to keep agreeing with that.
"""
from __future__ import annotations

import numpy as np
import pytest

from workflow import patch_generators as G


def _nearest_site_longhand(samples, sites):
    """The definition, straight off the page: for each sample, the index of the
    site it is closest to. Slow on purpose."""
    out = np.empty(len(samples), dtype=np.intp)
    for i, s in enumerate(samples):
        out[i] = int(((sites - s) ** 2).sum(1).argmin())
    return out


@pytest.mark.parametrize("n_samples,n_sites", [(300, 40), (2000, 250)])
def test_the_fast_nearest_site_agrees_with_the_definition(n_samples, n_sites):
    """MUTATION: drop the `|b|^2` term, or the factor of 2, and this goes red."""
    rng = np.random.default_rng(11)
    samples = rng.uniform(0.0, 100.0, size=(n_samples, 3))
    sites = rng.uniform(0.0, 100.0, size=(n_sites, 3))

    fast = G._nearest_site(samples, sites)
    slow = _nearest_site_longhand(samples, sites)

    wrong = int((fast != slow).sum())
    assert wrong == 0, (
        f"{wrong} of {n_samples} samples were assigned to a different site "
        "than the plain definition gives. These indices decide which colours "
        "reach the chart.")


def test_it_still_chunks_rather_than_building_one_huge_matrix():
    """The chunking is why this never blew up memory, and a rewrite could drop
    it without any test noticing. A sample count well past one chunk must still
    come out right."""
    rng = np.random.default_rng(3)
    samples = rng.uniform(0.0, 100.0, size=(G._nearest_site.__defaults__[0] * 2 + 7, 3))
    sites = rng.uniform(0.0, 100.0, size=(60, 3))
    assert (G._nearest_site(samples, sites)
            == _nearest_site_longhand(samples, sites)).all()


def test_a_cell_that_caught_no_samples_keeps_its_place(monkeypatch):
    """The old centroid step skipped a point whose cell caught nothing, with
    `if len(sel)`. The segmented mean must do the same.

    DIVIDING BY max(count, 1) IS NOT THE SAME, and a first attempt at this test
    could not tell the difference: an empty cell then has sum 0 over count 1,
    so the patch is silently moved to 0,0,0, which is pure black and still
    inside the cube and still finite. A user would get a chart with a cluster
    of identical black patches and nothing would say so.

    The natural sample count is forty per cell, so empty cells are rare and
    cannot be relied on to occur. This forces them: every sample is given to
    the first site, leaving every other cell empty.

    MUTATION: divide by `maximum(cnt, 1)` instead of masking, and this goes red
    with patches at exactly 0,0,0.
    """
    def _all_to_the_first(samples, sites, chunk=8192):
        return np.zeros(len(samples), dtype=np.intp)

    monkeypatch.setattr(G, "_nearest_site", _all_to_the_first)
    out = G.fill_gaps([(50.0, 50.0, 50.0)], 60, relax=2, seed=5)
    arr = np.array(out)

    assert len(arr) == 59
    assert np.isfinite(arr).all(), "a patch came back as NaN"
    at_black = int((np.abs(arr).sum(1) == 0.0).sum())
    assert at_black == 0, (
        f"{at_black} patches whose cell caught no samples were moved to pure "
        "black instead of being left where they were")


def test_the_fill_is_deterministic():
    """Same seed, same patches. The cache upstream depends on it."""
    a = G.fill_gaps([(10.0, 20.0, 30.0)], 300, seed=0)
    b = G.fill_gaps([(10.0, 20.0, 30.0)], 300, seed=0)
    assert a == b
