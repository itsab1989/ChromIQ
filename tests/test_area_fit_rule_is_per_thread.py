"""Another thread's area-first derivation never changes this thread's chart
(review r5 SF-1, 4.3.18).

`area_fit` counted "how deep inside a derivation this thread is" in ONE
integer for the whole process. While the presets window's background thread
("chromiq-preset-layout") was sizing an area-first preset, every other
thread's `old_label_rule_kept` answered False, and
`instruments.geom_from_build_kwargs` then laid out the old label rule's patch
size with the new rule's label geometry. Measured on a SpectroScan area-first
A4 chart: the patch block 2.8 mm to the left (x0 30.28 against 33.08 mm), and
the render hash of `test_row_indicators_without_strip_letters.py` flipped
under load, which is how it was found.

Thread B is HELD inside a real derivation (`_derive_area_patch_size`, patched
to wait on an event) while thread A asks for the same recipe it asked for
with no thread B at all. A must get the same answer, the same placement and
the same pixels.
"""
import hashlib
import threading

import pytest

from workflow.layout_engine import area_fit, geometry, instruments, papers

import test_row_indicators_without_strip_letters as T


def _ss_recipe():
    return T._recipe("SS", "area_first", strips=True, rows=True)


def _answer():
    """(rule kept, x0 of the patch block, render hash) for the SS recipe."""
    r = _ss_recipe()
    kw = r.build_kwargs()
    base = {k: v for k, v in kw.items() if k not in ("patch_w", "patch_h")}
    kept = area_fit.old_label_rule_kept(base)
    g = instruments.geom_from_build_kwargs(kw)
    w, h = papers.dimensions_mm(r.paper)
    lay = geometry.compute(g, w, h, T._N)
    x0 = geometry.placement(g, w, h, lay).x0
    page = T._render(r)[0]
    return kept, round(x0, 4), hashlib.sha256(page.tobytes()).hexdigest()


def test_a_derivation_on_another_thread_changes_nothing_here(monkeypatch):
    area_fit._CACHE.clear()
    alone = _answer()
    assert alone[0] is True, (
        "this SpectroScan recipe no longer keeps the old label rule, so the "
        "test would not see the fault; pick a recipe that does")

    real = area_fit._derive_area_patch_size
    inside, release = threading.Event(), threading.Event()
    holder: "list[threading.Thread]" = []

    def held(kw):
        if holder and threading.current_thread() is holder[0]:
            inside.set()
            assert release.wait(60), "thread B was never released"
        return real(kw)

    monkeypatch.setattr(area_fit, "_derive_area_patch_size", held)

    def b():
        other = T._recipe("CR30", "area_first", strips=True, rows=True)
        other.margin_left = 7.37       # a key nobody else asks for
        area_fit.derive_area_patch_size(other.build_kwargs())

    tb = threading.Thread(target=b, name="held-deriver", daemon=True)
    holder.append(tb)
    tb.start()
    try:
        assert inside.wait(60), "thread B never entered its derivation"
        area_fit._CACHE.clear()          # A must derive for itself, too
        with_b = _answer()
    finally:
        release.set()
        tb.join(60)
    assert not tb.is_alive()
    assert with_b == alone, (
        "a derivation running on ANOTHER thread changed this thread's chart: "
        f"alone {alone[:2]}, with thread B mid-derivation {with_b[:2]}")


def test_inside_a_derivation_the_lookup_is_still_switched_off(monkeypatch):
    """The depth still does its own job on its own thread: a candidate
    geometry built inside a derivation must not ask that derivation for its
    own answer."""
    seen = []
    real = area_fit._derive_area_patch_size

    def probe(kw):
        seen.append(area_fit.old_label_rule_kept(kw))
        return real(kw)

    monkeypatch.setattr(area_fit, "_derive_area_patch_size", probe)
    area_fit._CACHE.clear()
    area_fit.derive_area_patch_size(_ss_recipe().build_kwargs())
    assert seen and not any(seen)
    assert area_fit._depth() == 0


def test_size_and_rule_come_from_one_cache_entry():
    """The size and the rule flag are cached together, so emptying the cache
    between two lookups can never pair one derivation's size with another's
    (or no) flag."""
    area_fit._CACHE.clear()
    kw = _ss_recipe().build_kwargs()
    base = {k: v for k, v in kw.items() if k not in ("patch_w", "patch_h")}
    size = area_fit.derive_area_patch_size(base)
    entry = area_fit._CACHE[area_fit._cache_key(base)]
    assert entry == (size, area_fit.old_label_rule_kept(base))
    area_fit._CACHE.clear()
    assert area_fit.old_label_rule_kept(base) is entry[1]


@pytest.fixture(autouse=True)
def _clean_cache():
    yield
    area_fit._CACHE.clear()
