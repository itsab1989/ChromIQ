"""The legend chip makes way for the pause note (Basti, 2026-10-23: "both
labels should not get in each other's way. maybe the measured vs expected
should hide when the other one appears, like when the mouse hovers over it,
and then reappear when the other one is gone").

`TiffPreview.set_legend_suppressed` hides the chip with its own hover fade and
brings it back when cleared; coming back, the pointer still decides. Real
`TiffPreview`, real paint, as tests/test_legend_hover_hide.py.
"""
import pytest

from test_legend_hover_hide import _chip_pixels, preview  # noqa: F401


def test_it_fades_away_for_the_note_and_comes_back(preview, qtbot):  # noqa: F811
    before = _chip_pixels(preview)
    assert before > 200
    preview.set_legend_suppressed(True)
    qtbot.waitUntil(lambda: preview._legend_opacity < 0.02, timeout=2000)
    assert _chip_pixels(preview) < before / 4
    preview.set_legend_suppressed(False)
    qtbot.waitUntil(lambda: preview._legend_opacity > 0.99, timeout=2000)
    assert _chip_pixels(preview) == pytest.approx(before, rel=0.15)


def test_a_pointer_on_the_chip_keeps_it_away_until_it_leaves(preview, qtbot):  # noqa: F811
    preview.set_legend_suppressed(True)
    qtbot.waitUntil(lambda: preview._legend_opacity < 0.02, timeout=2000)
    preview._apply_legend_pointer(preview._legend_rect.center())
    preview.set_legend_suppressed(False)
    qtbot.wait(300)
    assert preview._legend_opacity < 0.02, "it came back under the pointer"
    preview._forget_legend_pointer()
    qtbot.waitUntil(lambda: preview._legend_opacity > 0.99, timeout=2000)


def test_the_pointer_leaving_does_not_bring_it_back_while_held(preview, qtbot):  # noqa: F811
    preview.set_legend_suppressed(True)
    qtbot.waitUntil(lambda: preview._legend_opacity < 0.02, timeout=2000)
    preview._forget_legend_pointer()
    qtbot.wait(300)
    assert preview._legend_opacity < 0.02


def test_hidden_and_shown_again_while_held_it_stays_away(preview, qtbot):  # noqa: F811
    """A tab switch hides the preview; it used to reset the chip to fully
    drawn."""
    preview.set_legend_suppressed(True)
    qtbot.waitUntil(lambda: preview._legend_opacity < 0.02, timeout=2000)
    preview.hide()
    preview.show()
    qtbot.wait(100)
    assert preview._legend_opacity < 0.02
    preview.set_legend_suppressed(False)
    qtbot.waitUntil(lambda: preview._legend_opacity > 0.99, timeout=2000)


def test_the_note_and_the_chip_share_one_look():
    """Basti, 2026-10-23: the note keeps the chip's look; only its panel is
    denser, by measurement (4.5:1 over white paper, ui.see_through)."""
    import inspect
    from ui import pause_note, see_through, tiff_preview
    assert "see_through.paint_halo_text" in inspect.getsource(
        tiff_preview.TiffPreview._paint_legend_chip)
    assert "see_through.paint_halo_text" in inspect.getsource(
        pause_note.PauseNote._paint_into)
    assert see_through.PANEL_ALPHA == 80
    # the lowest alpha whose words reach 4.5:1 over white paper (measured)
    a = see_through.NOTE_PANEL_ALPHA / 255
    bg = 245 * (1 - a) + 20 * a

    def lum(v):
        c = v / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    text = 0.2126 * lum(244) + 0.7152 * lum(242) + 0.0722 * lum(239)
    assert (text + 0.05) / (lum(bg) + 0.05) >= 4.5


def test_crossing_strokes_are_filled_winding():
    """Odd-even (Qt's default) leaves a hole where a glyph's contours
    overlap, and the halo shows through it ("characters with crossing
    lines")."""
    import inspect
    from ui import see_through
    src = inspect.getsource(see_through.paint_halo_text)
    assert "WindingFill" in src and "NoPen" in src
    assert src.index("strokePath") < src.index("fillPath")
