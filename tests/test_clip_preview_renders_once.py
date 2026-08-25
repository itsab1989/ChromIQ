"""The clip-strip preview must be drawn ONCE per load, and never be stale.

Rebuilding the clip preview runs the layout-engine geometry solver and rasterises
the strip — ~65 ms a call. Loading a recipe sets every field in turn, and each
field change used to redraw it: `set_recipe()` alone cost 1.9 s and threw 29 of
its 30 redraws away, which is what made opening Preferences take ~1.9 s on
screen. `_refresh_clip_preview` now returns early while a load is in progress
(`_loading`) or while a caller has explicitly suspended it
(`_suspend_clip_preview`).

That is only safe as long as every one of those windows ENDS with a redraw. A
stale preview — showing the previous recipe's band after a new one is loaded —
is a worse bug than the slow build this avoids, so the tests below check the
result, not the mechanism: after any load, the preview must equal what a fresh
render produces.
"""
from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication

from ui.dialogs.layout_options_panel import LayoutOptionsPanel
from workflow.layout_engine.presets import default_recipe


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _state(panel):
    """Everything the user can see of the preview."""
    pm = panel.clip_preview.pixmap()
    return (panel.clip_dims_label.text(),
            None if pm is None or pm.isNull() else (pm.width(), pm.height(),
                                                    pm.toImage().sizeInBytes()),
            panel.clip_preview.height())


def _forced_render(panel):
    """A render that CANNOT be skipped.

    `_refresh_clip_preview` starts with the two guards these tests exist to
    police (`_loading`, `_suspend_clip_preview`), so calling it plain reproduces
    a stranded panel's stale state instead of exposing it. Clear both first.
    """
    panel._loading = False
    panel._suspend_clip_preview = False
    panel._refresh_clip_preview()


def _count_effective_renders(monkeypatch):
    """Count redraws that actually do work (not the ones that return early)."""
    box = {"n": 0}
    orig = LayoutOptionsPanel._refresh_clip_preview

    def counting(self):
        skipped = (getattr(self, "_loading", False)
                   or getattr(self, "_suspend_clip_preview", False))
        if not skipped:
            box["n"] += 1
        return orig(self)

    monkeypatch.setattr(LayoutOptionsPanel, "_refresh_clip_preview", counting)
    return box


@pytest.mark.parametrize("inst,paper,mode", [
    ("i1", "A4", "clip"),
    ("i1", "Letter", "noclip"),
    ("CM", "A4", "freehand"),
    ("CM", "A3", "high"),
    ("SS", "A4", "flat"),
])
def test_a_loaded_recipe_is_never_shown_stale(app, inst, paper, mode):
    """After set_recipe the preview equals a fresh render of the same recipe.

    This is the invariant the early-return depends on. If someone adds a fourth
    `_loading` window that does not end in an `_emit()`, this fails.
    """
    p = LayoutOptionsPanel(with_selectors=True)
    # Load something visibly different first, so a stale preview would show.
    p.set_recipe(default_recipe("i1", "A4", mode="clip"))
    p.set_recipe(default_recipe(inst, paper, mode=mode))
    after_load = _state(p)
    _forced_render(p)                  # a render that cannot be skipped
    assert _state(p) == after_load


def test_set_recipe_draws_the_preview_exactly_once(app, monkeypatch):
    """The whole point: one redraw per load, not thirty."""
    p = LayoutOptionsPanel(with_selectors=True)
    p.set_recipe(default_recipe("i1", "A4", mode="clip"))
    box = _count_effective_renders(monkeypatch)
    p.set_recipe(default_recipe("CM", "A4", mode="freehand"))
    assert box["n"] == 1, f"set_recipe redrew the clip preview {box['n']}x"


def test_opening_preferences_draws_the_preview_once(app, monkeypatch, tmp_path):
    """Building Preferences' Chart Layout tab must cost one redraw, not ~12."""
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog

    box = _count_effective_renders(monkeypatch)
    dlg = SettingsDialog(AppSettings(), None)
    assert box["n"] == 1, (
        f"building Preferences redrew the clip preview {box['n']}x — the "
        "suspension in _build_chart_layout_tab is not covering the build")
    dlg.deleteLater()


def test_an_emptied_preview_forgets_the_last_band(app):
    """The empty preview's height must not depend on what you looked at before.

    `setFixedHeight` pins minimum == maximum for good and `clear()` only drops
    the pixmap, so an emptied preview used to keep the height of whichever band
    was drawn in it last — 25 px after one recipe, 18 px after another, with
    nothing in it either time.
    """
    p = LayoutOptionsPanel(with_selectors=True)
    p.set_recipe(default_recipe("i1", "A4", mode="clip"))
    i = p.clip_content_mode.findData("notes")
    p.clip_content_mode.setCurrentIndex(i)
    p._refresh_clip_preview()
    drawn_h = p.clip_preview.height()

    p._clear_clip_preview()
    empty_after_notes = p.clip_preview.height()

    q = LayoutOptionsPanel(with_selectors=True)
    q._clear_clip_preview()
    empty_never_drawn = q.clip_preview.height()

    assert empty_after_notes == empty_never_drawn, (
        f"emptied preview is {empty_after_notes} px after drawing a band but "
        f"{empty_never_drawn} px when nothing was ever drawn")
    assert empty_after_notes >= 90, "the designed 90 px empty box was not restored"
    assert drawn_h > 0


def test_resume_always_leaves_the_preview_live(app):
    """A suspended panel that is resumed redraws, and stays live afterwards."""
    p = LayoutOptionsPanel(with_selectors=True, defer_clip_preview=True)
    p.set_recipe(default_recipe("i1", "A4", mode="clip"))
    i = p.clip_content_mode.findData("notes")
    p.clip_content_mode.setCurrentIndex(i)
    assert p.clip_preview.pixmap() is None or p.clip_preview.pixmap().isNull(), \
        "a deferred panel drew the preview anyway"
    p.resume_clip_preview()
    live = _state(p)
    assert live[1] is not None, "resume did not draw the preview at all"
    _forced_render(p)
    assert _state(p) == live, "resume left the panel suspended or stale"


def test_preferences_resumes_the_panel_even_if_the_build_fails(app, monkeypatch):
    """A failure while populating must not leave the preview dead for good.

    The suspension is released in a `finally:` precisely so a panel is never
    stranded showing a preview that will not update again.
    """
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog

    made: list = []
    orig_init = LayoutOptionsPanel.__init__

    def capture(self, *a, **kw):
        made.append(self)
        return orig_init(self, *a, **kw)

    def explode(self):
        raise RuntimeError("populating blew up")

    monkeypatch.setattr(LayoutOptionsPanel, "__init__", capture)
    monkeypatch.setattr(SettingsDialog, "_preselect_layout_combo", explode)
    with pytest.raises(RuntimeError):
        SettingsDialog(AppSettings(), None)

    monkeypatch.undo()
    assert made, "no LayoutOptionsPanel was built — the test proves nothing"
    panel = made[-1]
    assert getattr(panel, "_suspend_clip_preview", False) is False, (
        "the build failed and left the panel suspended: its clip preview would "
        "never redraw again")


def test_a_half_done_load_does_not_kill_the_panel(app):
    """A recipe that blows up mid-load must leave the panel usable.

    `_set_recipe_impl` clears `_loading` on its last line only, so a raise part
    way through left it True for ever — and both the clip preview and the
    `changed` signal are gated on it, so the preview froze on the PREVIOUS
    recipe and the panel went silent. A preset file with a null `dpi` is enough
    (`QSpinBox.setValue(None)` raises TypeError), and the layout editor catches
    that exception and carries on, so the user would be left designing against
    a picture of the chart they had open before.
    """
    p = LayoutOptionsPanel(with_selectors=True)
    p.set_recipe(default_recipe("i1", "A4", mode="clip"))
    before = _state(p)

    orig = LayoutOptionsPanel._set_recipe_impl

    def blow_up(self, r):
        orig(self, r)
        raise RuntimeError("half-done load")

    LayoutOptionsPanel._set_recipe_impl = blow_up
    try:
        with pytest.raises(RuntimeError):
            p.set_recipe(default_recipe("CM", "A4", mode="freehand"))
    finally:
        LayoutOptionsPanel._set_recipe_impl = orig

    assert p._loading is False, "a failed load left the panel stuck in _loading"

    # The panel must still respond: load a different recipe and see it arrive.
    p.set_recipe(default_recipe("i1", "Letter", mode="clip"))
    after = _state(p)
    assert after != before, "the panel stopped updating after a failed load"
    _forced_render(p)
    assert _state(p) == after, "the preview is stale after a failed load"
