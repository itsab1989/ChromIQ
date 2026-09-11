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
