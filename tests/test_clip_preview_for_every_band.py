"""The clip preview has to work wherever the band does (#164, Knut).

*"When I try the clip-border content… the Preview does not know anything when I
have text defined. I used one of my colormunki presets … One more thing about
the clip-border content: the 'Clip area' shows only '-' (a long dash). Choose
any of my presets for colormunki to see."*

The ColorMunki and the SpectroScan have no native clip border, but they carry an
optional notes band the moment clip content is switched on — the renderer
reserves it, and the panel deliberately shows the content group for them (#93).
Only the panel's own preview disagreed: it built its geometry for i1/p3 and
answered "no band" for everything else, so the band was printed onto the sheet
while the panel showed an empty box and a dash.

The second cause has nothing to do with the instrument: the preview invented
``border=min(margins)`` instead of using the recipe's own border, and that
collapses the reserved width to zero — "no clip area" — whenever the margins
reach the clip width. That one bites an i1 as readily as a ColorMunki.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def panel(qapp):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    p._expert_frame.set_collapsed(False)
    return p


def _select(panel, instrument: str) -> None:
    panel.instr.setCurrentIndex(panel.instr.findData(instrument))


@pytest.mark.parametrize("instrument", ["CM", "SS"])
@pytest.mark.parametrize("content", ["text", "branding", "notes", "image"])
def test_the_band_is_measured_and_drawn_for_a_notes_instrument(
        panel, instrument, content):
    _select(panel, instrument)
    panel.clip_content_mode.setCurrentIndex(
        panel.clip_content_mode.findData(content))
    if content in ("text", "branding"):
        panel.clip_text.setPlainText("Knut Larsson\nEpson P900")
    panel._refresh_clip_preview()

    assert panel.clip_dims_label.text() not in ("—", "-", ""), (
        f"{instrument}/{content}: the clip area is still an em dash")
    pix = panel.clip_preview.pixmap()
    assert pix is not None and not pix.isNull(), (
        f"{instrument}/{content}: the preview box is empty")


@pytest.mark.parametrize("instrument", ["i1", "p3"])
def test_the_clip_instruments_still_work(panel, instrument):
    _select(panel, instrument)
    panel.mode.setCurrentIndex(panel.mode.findData("clip"))
    panel.clip_content_mode.setCurrentIndex(
        panel.clip_content_mode.findData("notes"))
    panel._refresh_clip_preview()
    assert panel.clip_dims_label.text() not in ("—", "-", "")


def test_wide_margins_no_longer_erase_the_clip_area(panel):
    """`border=min(margins)` was the panel's own invention. Push the margins out
    to the clip width and the reserved band collapsed to nothing, so an i1 in
    clip mode reported "no clip area" while still printing one."""
    _select(panel, "i1")
    panel.mode.setCurrentIndex(panel.mode.findData("clip"))
    panel.clip_content_mode.setCurrentIndex(
        panel.clip_content_mode.findData("notes"))
    panel.clip_width.setValue(26.0)
    for k in ("t", "r", "b", "l"):
        panel.margins[k].setValue(26.0)
    panel._refresh_clip_preview()
    assert panel.clip_dims_label.text() not in ("—", "-", "")


def test_no_band_still_means_no_preview(panel):
    """Turning the content off is the one case that SHOULD read as nothing —
    the band is not reserved, so there is no area to report."""
    _select(panel, "CM")
    panel.clip_content_mode.setCurrentIndex(panel.clip_content_mode.findData("off"))
    panel._refresh_clip_preview()
    assert panel.clip_dims_label.text() in ("—", "-", "")


def test_the_export_template_button_is_alive_for_a_notes_instrument(panel):
    """`Export template` sits behind the same guard, so it silently did nothing
    on a ColorMunki. Prove the geometry it needs now exists."""
    _select(panel, "CM")
    panel.clip_content_mode.setCurrentIndex(
        panel.clip_content_mode.findData("notes"))
    assert panel._clip_geom_and_height() is not None


def test_the_branding_can_be_placed_like_an_image(panel):
    """*"For Imported image option, then there are fields to position the image.
    Why are those options not available for ChromIQ branding?"* — they are now,
    and they are the same recipe fields."""
    _select(panel, "i1")
    panel.mode.setCurrentIndex(panel.mode.findData("clip"))
    panel.clip_content_mode.setCurrentIndex(
        panel.clip_content_mode.findData("branding"))
    panel._sync_clip_content_enabled()
    # isVisibleTo, not isVisible: the panel is never shown under pytest, so
    # `isVisible()` is False for every widget and the old form of this assertion
    # was vacuously true — it passed against a build that still hid these rows
    # for branding, which is the whole point of the change.
    for w in (panel._clip_image_fit_row or []):
        assert w.isVisibleTo(panel), "the fit row is still image-only"
    for w in (panel._clip_image_move_row or []):
        assert w.isVisibleTo(panel), "the move row is still image-only"
    assert panel.clip_image_offx.isEnabled()
    assert panel.clip_image_scale.isEnabled()
    # Rotation is an image-only transform: the branding always reads up the
    # strip, and "Flip 180°" is how it is turned the other way.
    assert not panel.clip_image_rotation.isEnabled()

    panel.clip_image_offy.setValue(12.0)
    r = panel.get_recipe()
    assert r.clip_content_mode == "branding"
    assert abs(r.clip_image_offset_y_mm - 12.0) < 1e-6


def test_the_branding_render_honours_the_placement():
    """And the renderer must actually move it — a control the sheet ignores is
    worse than no control."""
    import numpy as np

    from workflow.layout_engine import raster
    kw = dict(width_px=260, height_px=1200, dpi=300, text="Knut\nP900")
    plain = np.asarray(raster.render_clip_strip("branding", **kw))
    moved = np.asarray(raster.render_clip_strip(
        "branding", image_offset_y_mm=15.0, **kw))
    bigger = np.asarray(raster.render_clip_strip(
        "branding", image_scale=160.0, **kw))
    assert not np.array_equal(plain, moved), "moving the branding did nothing"
    assert not np.array_equal(plain, bigger), "scaling the branding did nothing"
    # …and the untouched defaults must render exactly as they did before, or
    # every chart already made with branding changes.
    same = np.asarray(raster.render_clip_strip(
        "branding", image_scale=100.0, image_offset_x_mm=0.0,
        image_offset_y_mm=0.0, **kw))
    assert np.array_equal(plain, same)
