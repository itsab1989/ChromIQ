"""The patch-set generator must not build the same colour set twice.

Basti, 2026-09-11: *"this takes long when doing it the first time and opening
the same window after this setting was applied once it now loads it with the
same settings and thus the user waits until the same set was built again."*

MEASURED ON SCREEN (cocoa, this machine, "Ensure unique colours" on and "Fill
remaining gaps" to 4000): opening the New chart window ran
``_build_generated_program`` **eight times**, each one ~6 s, each one producing
the identical 4000 patches -- **48.0 s of waiting for a set the app had already
built**. With the cache in front of it: **0.41 s**, and the patches are byte
identical (logs/program_4000_PREFIX.json vs _POSTFIX.json).

This file pins BOTH directions, because the dangerous half is the second one:

* an unchanged generator state must be served from the cache, and
* ANY change to a generator setting must rebuild, or the user would be looking
  at controls that no longer describe the patches they will get.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")
from pathlib import Path  # noqa: E402

from PyQt6.QtWidgets import QApplication  # noqa: E402

from ui.dialogs import ti2_relayout_dialog as T  # noqa: E402
from ui.dialogs.ti2_relayout_dialog import _NewChartDialog  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _FakeSettings:
    def __init__(self):
        self.d = {}

    def get(self, k, default=None):
        return self.d.get(k, default)

    def set(self, k, v):
        self.d[k] = v


#: Every colour-set tick, so a test can strip the panel down to one generator.
_SET_CHECKS = ("cube", "corners", "spirals", "skin", "blues", "greens",
               "sunrises", "flamingos", "neutral", "nearneutral", "edges",
               "hs", "pastel", "image", "whiteblack")


def _dialog(settings, target=90):
    """A New-chart window set to Basti's repro, but small enough for a test:
    Generate colour sets, Ensure unique colours ON, Fill remaining gaps ->
    ``target`` patches, every other colour set off."""
    dlg = _NewChartDialog(Path("/x"), settings)
    dlg._mode_generate.setChecked(True)
    for name in _SET_CHECKS:
        getattr(dlg, f"_gen_{name}").setChecked(False)
    dlg._gen_unique.setChecked(True)
    dlg._gen_fill.setChecked(True)
    dlg._gen_fill_unit_patches.setChecked(True)
    dlg._gen_fill_to.setValue(target)
    return dlg


class _Counter:
    """Counts how often the REAL build runs, leaving its behaviour alone."""

    def __init__(self, monkeypatch):
        self.n = 0
        real = _NewChartDialog._build_generated_program_uncached

        def counted(inner_self):
            self.n += 1
            return real(inner_self)

        monkeypatch.setattr(
            _NewChartDialog, "_build_generated_program_uncached", counted)

    def reset(self) -> None:
        """Ignore the builds a window does while it is being SET UP: opening
        one walks through intermediate states on its way to the one the test
        cares about, and each of those is a different, legitimate build."""
        self.n = 0


@pytest.fixture(autouse=True)
def _empty_cache():
    """Every test starts with an empty cache; none leaks into the next."""
    T._PROGRAM_CACHE.clear()
    yield
    T._PROGRAM_CACHE.clear()


def test_an_unchanged_generator_state_is_built_once(qapp, monkeypatch):
    """Asking twice for the same settings runs the generators once."""
    c = _Counter(monkeypatch)
    dlg = _dialog(_FakeSettings())
    c.reset()
    first = dlg._build_generated_program()
    after_first = c.n
    second = dlg._build_generated_program()
    assert after_first == 1, "the first ask must actually build"
    assert c.n == 1, f"the second ask rebuilt ({c.n} builds, expected 1)"
    assert first == second
    assert len(first) == 90


def test_reopening_the_window_does_not_rebuild(qapp, monkeypatch):
    """The reported fault: a second window with the same settings must not
    repeat the work of the first."""
    s = _FakeSettings()
    c = _Counter(monkeypatch)
    dlg = _dialog(s)
    c.reset()
    first = dlg._build_generated_program()
    assert c.n == 1
    dlg._save_gen_state()                      # what pressing Create does

    reopened = _NewChartDialog(Path("/x"), s)  # restores the saved state
    reopened._mode_generate.setChecked(True)
    before_ask = c.n
    again = reopened._build_generated_program()

    assert c.n == before_ask, (
        "the reopened window rebuilt the set it was reopened with "
        f"({c.n - before_ask} extra builds)")
    assert again == first


def test_changing_a_setting_rebuilds(qapp, monkeypatch):
    """The direction that must NOT be cached away: the patches have to follow
    the controls. A cache keyed on too little would hand back a set that no
    longer matches what the window says."""
    c = _Counter(monkeypatch)
    dlg = _dialog(_FakeSettings(), target=90)
    c.reset()
    before = dlg._build_generated_program()
    dlg._gen_fill_to.setValue(60)
    c.reset()
    after = dlg._build_generated_program()
    assert c.n == 1, f"the changed fill target did not rebuild ({c.n} builds)"
    assert len(before) == 90 and len(after) == 60
    assert before != after


def test_ticking_a_colour_set_rebuilds(qapp, monkeypatch):
    """Not only the fill spin: a colour-set tick must reach the key too."""
    c = _Counter(monkeypatch)
    dlg = _dialog(_FakeSettings(), target=90)
    c.reset()
    before = dlg._build_generated_program()
    dlg._gen_neutral.setChecked(True)
    c.reset()
    after = dlg._build_generated_program()
    assert c.n == 1, f"ticking a colour set did not rebuild ({c.n} builds)"
    assert before != after


def test_the_cache_key_names_the_resolved_fill_target(qapp):
    """'Fill to N pages' multiplies by the layout engine's capacity per page,
    which no widget in ``_collect_gen_state`` describes. The key therefore
    carries the RESOLVED patch count, so two states that collect identically
    but fill to different totals cannot share an entry."""
    dlg = _dialog(_FakeSettings(), target=90)
    key_a = dlg._generator_cache_key()
    assert 90 in key_a, "the resolved fill target is not in the key"
    dlg._gen_fill_to.setValue(91)
    assert dlg._generator_cache_key() != key_a


def test_the_cache_is_bounded(qapp):
    """A user sweeping a spin box must not grow the cache without limit."""
    dlg = _dialog(_FakeSettings(), target=40)
    for n in range(40, 40 + T._PROGRAM_CACHE_MAX + 4):
        dlg._gen_fill_to.setValue(n)
        dlg._build_generated_program()
    assert len(T._PROGRAM_CACHE) <= T._PROGRAM_CACHE_MAX


# ---------------------------------------------------------------------------
# What the cache got wrong, found by a challenge round driving the real window
# ---------------------------------------------------------------------------
def test_a_second_window_does_not_serve_the_first_windows_photo(qapp, tmp_path):
    """BLOCKER: THE WINDOW HANDED YOU ANOTHER PHOTO'S COLOURS.

    `_gen_image_serial` counted images PER WINDOW and started at 0 in each,
    while the cache is process-wide. So the first photo loaded in window 2
    keyed identically to the first photo loaded in window 1, and window 2 was
    served window 1's palette while its own button showed the new filename.
    Driven on screen: same key, wrong colours, no warning of any kind.

    The digest of the decoded pixels is the photo's real identity. Two
    different pictures cannot collide, and reloading the SAME picture still
    hits, which is what the cache exists for.

    MUTATION: key on a per-window counter again and this goes red.
    """
    import numpy as np

    from ui.dialogs.ti2_relayout_dialog import _NewChartDialog as D

    class _Fake:
        _gen_image_px = None

    a, b = _Fake(), _Fake()
    a._gen_image_px = np.array([[10, 20, 30], [40, 50, 60]], dtype=np.uint8)
    b._gen_image_px = np.array([[90, 80, 70], [60, 50, 40]], dtype=np.uint8)

    da = D._gen_image_digest(a)
    db = D._gen_image_digest(b)
    assert da and db, "a loaded photo must have an identity"
    assert da != db, (
        "two different photos share a cache identity, so one window's palette "
        "can be served to another")

    # …and the same picture keeps its identity, or the cache never hits
    c = _Fake()
    c._gen_image_px = np.array([[10, 20, 30], [40, 50, 60]], dtype=np.uint8)
    assert D._gen_image_digest(c) == da, (
        "reloading the same photo missed the cache, which throws the whole "
        "point of it away")
    assert D._gen_image_digest(_Fake()) == "", "no photo is not a photo"


def test_the_out_of_gamut_note_survives_a_cache_hit(qapp, tmp_path):
    """BLOCKER: A WARNING THAT APPEARS ONLY THE FIRST TIME.

    The build produces two things and the cache kept one. `nch_moved_note` is
    written inside the builder, so skipping the builder skipped the sentence
    saying how many look-based colours lay outside the printer's gamut and were
    moved. Driven: window 1 said 350 of 966 were moved; window 2, identical
    settings and identical patches, said nothing.

    Its absence reads as good news, which is why this is worse than never
    showing it.

    MUTATION: cache the program alone again and this goes red.
    """
    import ui.dialogs.ti2_relayout_dialog as M

    M._PROGRAM_CACHE.clear()

    class _Fake:
        nch_moved_note = ""
        _key = ("k",)

        def _generator_cache_key(self):
            return self._key

        def _build_generated_program_uncached(self):
            self.nch_moved_note = "350 of 966 were moved"
            return [(1.0, 2.0, 3.0)]

    first = _Fake()
    prog = M._NewChartDialog._build_generated_program(first)
    assert prog == [(1.0, 2.0, 3.0)]
    assert first.nch_moved_note, "the premise failed"

    second = _Fake()

    def _must_not_run(self):
        raise AssertionError("the cache missed, so this proves nothing")

    second._build_generated_program_uncached = _must_not_run.__get__(second)
    again = M._NewChartDialog._build_generated_program(second)

    assert again == [(1.0, 2.0, 3.0)], "the cache did not serve the program"
    assert second.nch_moved_note == "350 of 966 were moved", (
        "the second window lost the out-of-gamut warning, and its absence "
        "reads as good news")


def test_a_different_argyll_is_a_different_program(qapp, tmp_path):
    """Several generators shell out to `targen`, so the same settings against a
    different ArgyllCMS are a different set of patches. The path was not in the
    key, and a window pointed at a directory with no targen returned the
    previously cached patches and looked healthy.

    MUTATION: drop the Argyll path from the key and this goes red.
    """
    from ui.dialogs.ti2_relayout_dialog import _NewChartDialog as D

    class _Fake:
        def __init__(self, path):
            self._settings = {"argyll_path": path}

    class _S(dict):
        def get(self, k, d=None):
            return dict.get(self, k, d)

    a, b = _Fake(_S()), _Fake(_S())
    a._settings = _S({"argyll_path": "/Applications/Argyll/bin"})
    b._settings = _S({"argyll_path": "/somewhere/else/bin"})
    assert D._argyll_key(a) != D._argyll_key(b), (
        "two different ArgyllCMS installations share a cache identity")


def test_the_KEY_itself_tells_two_photos_apart(qapp, tmp_path):
    """AND THE KEY MUST USE IT, which the test above does not prove.

    Measured: swapping the key back to the per-window counter left that test
    green, because it exercised `_gen_image_digest` in isolation. A digest
    nothing consults is decoration. This drives `_generator_cache_key` itself.

    MUTATION: put `_gen_image_serial` back in the key and this goes red.
    """
    import numpy as np

    from ui.dialogs.ti2_relayout_dialog import _NewChartDialog as D

    class _S(dict):
        def get(self, k, d=None):
            return dict.get(self, k, d)

    class _Fake:
        _existing_patches = ()
        _gen_image_serial = 1          # identical in both, as it really was

        def __init__(self, px):
            self._gen_image_px = px
            self._settings = _S({"argyll_path": "/Applications/Argyll/bin"})

        def _collect_gen_state(self):
            return {"same": "settings"}

        def _nch_state(self):
            return 0

        def _effective_fill_target(self):
            return 4000

    # the two methods under test are the real ones, not stand-ins
    _Fake._gen_image_digest = D._gen_image_digest
    _Fake._argyll_key = D._argyll_key

    a = _Fake(np.array([[10, 20, 30]], dtype=np.uint8))
    b = _Fake(np.array([[90, 80, 70]], dtype=np.uint8))

    ka = D._generator_cache_key(a)
    kb = D._generator_cache_key(b)
    assert ka is not None and kb is not None, "the key refused to build"
    assert ka != kb, (
        "two windows with different photos and every control identical produce "
        "the same cache key, so one is served the other's palette")

    same = _Fake(np.array([[10, 20, 30]], dtype=np.uint8))
    assert D._generator_cache_key(same) == ka, (
        "the same photo missed the cache, which throws the speed away")
