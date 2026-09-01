"""The FIRST click on "Show row indicators" must reach the live preview.

Reported from the app (Basti, 2026-09-01): with "update the preview
automatically" on, the first click did nothing, the second refreshed, the third
refreshed with the labels. Not a race — it repeated after every Guided
generate.

Cause, proved on screen by a challenge round: Qt emits `toggled` BEFORE
`clicked`, and the panel marks "a person chose this" from `clicked`. So the
first `changed` of a click ran while the flag was still False, the tri-state
recipe field returned `None` ("this instrument's own behaviour"), the layout
signature was unchanged, and the auto-preview timer was never armed.

The build, meanwhile, reads the recipe AFTER the click — so one click and
Generate printed row labels the preview had never shown. That is the part that
makes this more than a lagging picture.
"""
import pytest


@pytest.fixture()
def panel(qapp):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    return LayoutOptionsPanel(None)


def _recipe_value(panel):
    from workflow.layout_engine.presets import LayoutRecipe
    return panel.apply_to_recipe(LayoutRecipe()).show_row_indicators


def test_the_first_click_changes_what_the_recipe_says(panel):
    seen = []
    panel.changed.connect(lambda: seen.append(_recipe_value(panel)))
    panel.show_row_indicators.click()
    assert seen, "the panel reported no change at all"
    assert seen[-1] is not None, (
        "after a click the recipe still says 'this instrument's own "
        "behaviour', so nothing downstream can tell the user chose")
    assert _recipe_value(panel) is panel.show_row_indicators.isChecked()


def test_what_the_preview_is_told_matches_what_a_build_would_read(panel):
    """The preview renders from the value carried by `changed`; the build reads
    the recipe afterwards. They must not disagree."""
    during = []
    panel.changed.connect(lambda: during.append(_recipe_value(panel)))
    panel.show_row_indicators.click()
    after = _recipe_value(panel)
    assert during[-1] == after, (
        f"the preview was told {during[-1]!r} while a build would read "
        f"{after!r} — one click then Generate prints a sheet the preview "
        f"never showed")


def test_the_other_boxes_were_never_affected(panel):
    """Only the tri-state box had this fault; the plain ones report at once."""
    for name in ("show_indicators",):
        box = getattr(panel, name, None)
        if box is None:
            continue
        fired = []
        panel.changed.connect(lambda: fired.append(True))
        box.click()
        assert fired, f"{name} reported no change on a click"


@pytest.mark.parametrize("clicks", [1, 2, 3])
def test_every_click_reports_the_state_the_box_is_in(panel, clicks):
    """The reported shape was 'first click swallowed, the rest fine'."""
    for _ in range(clicks):
        panel.show_row_indicators.click()
    assert _recipe_value(panel) is panel.show_row_indicators.isChecked()
