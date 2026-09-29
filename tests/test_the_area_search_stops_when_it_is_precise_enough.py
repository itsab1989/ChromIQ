"""Selecting a scanner preset took eleven and a half seconds, and it was arithmetic.

Knut, 2026-09-13:

    "all the scanner presets are very very slow to load (probably due to the
     number of patches) and every single click of change, like altering a margin
     number, takes a long time. I think this was not a problem some time ago...
     The sluggishness does not happen to other large charts, like the red river
     charts or other charts with more than 3000 patches."

He is right that it is not the patch count. Profiled, seeding one built-in in a
real tab:

    Scanner A4-3430p       11,723 ms     17,794 calls to `strips()`
    Red River A4-2052p        190 ms        369
    CR30 A4-1350p             262 ms        369

The scanner family is the only one laid out `by_width` with no column count, so
`derive_area_patch_size` tries every column count a 4 mm minimum allows and each
try binary-searches the patch width over a real provisional geometry. Three
things were wrong with that, none of them the search itself:

* the same answer was computed EIGHT TIMES for one click, because selecting a
  preset refreshes the command preview and the layout estimate several times
  over and each refresh asks again. The function is pure in its kwargs;
* every candidate column count started its own search on the same interval, so
  the probes repeated;
* each search ran a fixed FORTY halvings, resolving the patch width to 3e-10 mm
  on a 300 mm interval. One pixel at 1200 dpi is 0.021 mm.

Measured after: **544 ms**, and the everyday tier itself went from 174 s to
119 s.
"""
from __future__ import annotations

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from workflow.layout_engine import area_fit  # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe  # noqa: E402


def _kw(slug: str) -> dict:
    import ui.tabs.tab_chart as tc
    p = next(x for x in tc.KNUT_PRESETS if x.slug == slug)
    return dict(LayoutRecipe.from_dict(p.layout_recipe).build_kwargs(),
                area_target_count=int(p.patches or 0))


_SCANNER = "scanner_a4_3430p_1page_landscape"


def test_the_resolution_is_far_finer_than_the_pixel_it_becomes():
    """0.0001 mm is 0.005 px at 1200 dpi, which is the finest ChromIQ offers."""
    assert area_fit._FIT_RESOLUTION_MM == pytest.approx(1e-4)
    px_at_1200 = 25.4 / 1200.0
    assert area_fit._FIT_RESOLUTION_MM < px_at_1200 / 100.0


def test_stopping_early_gives_the_same_answer_as_grinding_on(monkeypatch):
    """The claim the speed-up rests on, checked rather than argued.

    A resolution a thousand times finer must produce the same patch size. It
    was also checked over all 147 recipe-carrying built-ins when the change was
    made, which is too slow for the everyday tier; three charts of different
    shapes stand in here.
    """
    import ui.tabs.tab_chart as tc

    slugs = [_SCANNER,
             "cr30_a4_450p_1page_portrait_w11_0mm_hexagonal_straight",
             "redriver_i1_a4_2052p_4pages"]
    have = {p.slug for p in tc.KNUT_PRESETS}
    slugs = [s for s in slugs if s in have]
    assert len(slugs) >= 2, f"the sample charts are gone: {slugs}"

    for slug in slugs:
        kw = _kw(slug)
        area_fit._CACHE.clear()
        coarse = area_fit.derive_area_patch_size(dict(kw))
        monkeypatch.setattr(area_fit, "_FIT_RESOLUTION_MM", 1e-7)
        area_fit._CACHE.clear()
        fine = area_fit.derive_area_patch_size(dict(kw))
        monkeypatch.undo()
        assert coarse == fine, (
            f"{slug}: stopping at {area_fit._FIT_RESOLUTION_MM} mm gives "
            f"{coarse} where a thousand times finer gives {fine}")


def test_the_answer_is_remembered_and_is_the_same_answer():
    kw = _kw(_SCANNER)
    area_fit._CACHE.clear()
    first = area_fit.derive_area_patch_size(dict(kw))
    t0 = time.perf_counter()
    again = area_fit.derive_area_patch_size(dict(kw))
    warm = time.perf_counter() - t0
    assert again == first
    assert warm < 0.005, (
        f"the second call took {warm * 1000:.1f} ms; it is not being remembered")


def test_the_memory_cannot_hand_one_chart_another_chart_s_size():
    """A cache keyed on less than the whole of the kwargs is a wrong answer.

    Written first as "move a margin and the answer must change", and that was
    the wrong question: on this chart a 12 mm move leaves the derived size at
    (3.99, 4.04), because a 4 mm minimum on a 297 mm sheet lands in the same
    place. Whether the two recipes SHARE AN ENTRY is the property, and it is
    the key that decides it.
    """
    kw = _kw(_SCANNER)
    moved = dict(kw)
    moved["margin_l"] = float(kw.get("margin_l") or 0.0) + 12.0
    assert area_fit._cache_key(kw) != area_fit._cache_key(moved), (
        "two recipes differing in a margin produce the same cache key")

    # …and a paper change, which does move the answer, really is recomputed.
    other = dict(kw, paper="A3")
    area_fit._CACHE.clear()
    a = area_fit.derive_area_patch_size(dict(kw))
    b = area_fit.derive_area_patch_size(other)
    assert a != b, ("A4 and A3 came out identical; the cache is answering for "
                    "the wrong sheet")
    assert area_fit.derive_area_patch_size(dict(kw)) == a


def test_a_recipe_the_key_cannot_describe_is_simply_not_cached():
    """Never guess: an unserialisable kwarg must miss, not collide."""
    kw = _kw(_SCANNER)
    kw["something_new"] = object()
    assert area_fit._cache_key(kw) is None
    area_fit._CACHE.clear()
    out = area_fit.derive_area_patch_size(kw)
    assert out is not None
    assert not area_fit._CACHE, "an unserialisable recipe was cached anyway"


def test_the_search_does_not_grind_past_the_resolution(monkeypatch):
    """The MECHANISM, counted, because a wall-clock bound is too slack to see it.

    Written as a timing test first and the mutation that deletes the early
    stop walked straight through it: forty halvings is 1.66 s and the bound was
    4 s. Each halving is one provisional geometry, so counting those is exact
    and machine-independent.
    """
    from workflow.layout_engine import instruments

    def _count(res):
        n = {"v": 0}
        real = instruments.geom_from_build_kwargs

        def spy(kw, *a, **k):
            n["v"] += 1
            return real(kw, *a, **k)

        monkeypatch.setattr(instruments, "geom_from_build_kwargs", spy)
        monkeypatch.setattr(area_fit, "_FIT_RESOLUTION_MM", res)
        area_fit._CACHE.clear()
        area_fit.derive_area_patch_size(_kw(_SCANNER))
        monkeypatch.undo()
        return n["v"]

    stopped = _count(1e-4)
    ground = _count(1e-12)          # what forty halvings comes to
    assert stopped < ground * 0.7, (
        f"stopping at the resolution built {stopped} geometries and grinding "
        f"on builds {ground}; the early stop is not doing anything")


def test_the_slow_family_is_no_longer_slow():
    """The user-visible number, on the chart he named.

    Generous against the 544 ms measured, because a loaded gate runs this on a
    busy machine; the point is that it is not eleven seconds.
    """
    kw = _kw(_SCANNER)
    area_fit._CACHE.clear()
    t0 = time.perf_counter()
    area_fit.derive_area_patch_size(kw)
    took = time.perf_counter() - t0
    assert took < 4.0, (
        f"deriving the scanner chart's patch size took {took:.1f} s; it was "
        "1.66 s before the search was bounded and 0.54 s after")
