"""#130 (Knut, 2026-07-27): the patch-set editor must remember what you applied.

His report: he opened **New patch set…**, set the generators up the way he
wanted, added the set and applied it to the chart — then realised he had made
too few patches, went back in, and the window had forgotten everything.

His words, which are the requirement: *"All the last used settings should be
saved when applying, and then reloaded into the editor when opened, so I can go
back to it and change it."*

His log settles where it went wrong. `new_chart_gen` — the app-wide last-used
state — was written exactly **once** in the whole session, at 15:53:42, long
after the work he lost. Applying a design saved nothing: only a sub-dialog's own
OK did, so a design that reached the chart by any other route was forgotten.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                   # noqa: E402
from PyQt6.QtWidgets import QApplication             # noqa: E402

from core.settings import AppSettings                # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def settings(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    return s


RECIPE = {
    "mode": "generate",
    "cb": {"cube": True, "skin": True, "pastel": True, "fill": False},
    "sp": {"cube_n": 9, "skin_n": 4, "pastel_n": 3},
    "instr": "CM", "paper": "A4", "count": 540,
}


class _Editor:
    """The two attributes `_remember_gen_state` actually reads."""

    from ui.dialogs.ti2_relayout_dialog import Ti2RelayoutDialog
    _remember_gen_state = Ti2RelayoutDialog._remember_gen_state

    def __init__(self, settings, recipe):
        self._settings = settings
        self._chart_recipe = recipe


def test_applying_remembers_the_design(settings):
    """The moment the user commits to a design is the moment worth keeping."""
    _Editor(settings, RECIPE)._remember_gen_state()

    assert settings.get("new_chart_gen", None) == RECIPE


def test_it_is_a_copy_not_a_live_reference(settings):
    """A later edit in the editor must not rewrite what was already applied."""
    recipe = dict(RECIPE)
    ed = _Editor(settings, recipe)
    ed._remember_gen_state()

    recipe["count"] = 1
    assert settings.get("new_chart_gen")["count"] == 540


def test_a_chart_with_no_recipe_leaves_the_last_used_state_alone(settings):
    """A loaded foreign chart carries no design of its own; forgetting the
    user's last one because of that would be the same bug again."""
    settings.set("new_chart_gen", RECIPE)

    _Editor(settings, None)._remember_gen_state()

    assert settings.get("new_chart_gen") == RECIPE


def test_it_never_breaks_an_apply(settings):
    """Best-effort by design: an apply must not fail over a remembered setting."""
    class _Exploding:
        def get(self, *_a, **_k):
            return None

        def set(self, *_a, **_k):
            raise RuntimeError("disk full")

    _Editor(_Exploding(), RECIPE)._remember_gen_state()      # must not raise


# ---- the two ends of the round trip ---------------------------------------
def test_the_new_patch_set_window_reads_that_state_back():
    """`_restore_gen_state` is what reopens on the remembered design."""
    import inspect

    from ui.dialogs.ti2_relayout_dialog import _NewChartDialog
    src = inspect.getsource(_NewChartDialog._restore_gen_state)
    assert '"new_chart_gen"' in src and "_apply_gen_state" in src


def test_adding_patches_never_rewrites_the_chart_s_stored_design():
    """Knut's rule, stated 2026-07-27 after I had broken it: "the settings used
    in the NEW PATCH SET window is stored in the chart's json file, and is only
    changed if NEW PATCH SET window is used again with other settings."

    Add has colour-set choices of its own, which follow the last New-patch-set
    settings — but it does not speak for the chart's design, and an earlier
    version of this that folded them in is gone.
    """
    import inspect

    from ui.dialogs.ti2_relayout_dialog import Ti2RelayoutDialog, _AddPatchesDialog
    ed_src = inspect.getsource(Ti2RelayoutDialog)
    assert "merged.update(_added_recipe)" not in ed_src
    assert "self._chart_recipe = merged" not in ed_src

    add_src = inspect.getsource(_AddPatchesDialog._on_add)
    # It still remembers the colour sets for next time — that part is his rule
    # too ("the Add button … shall follow the same settings last used").
    assert '"new_chart_gen"' in add_src
    assert "self.result_recipe" not in add_src


def test_applying_is_what_saves_it():
    import inspect

    from ui.dialogs.ti2_relayout_dialog import Ti2RelayoutDialog
    src = inspect.getsource(Ti2RelayoutDialog)
    assert "self._remember_gen_state()" in src
    # …and it happens where the chart's own copy is written, so the two agree.
    assert src.index("save_editor_meta") < src.index("self._remember_gen_state()")
