"""The preview's white frame is only the white the sheet does not already have.

printtarg puts ink hard against the sheet edge — measured on a real raster: 0 px
on the left, 9 px on top — which looks wrong against the dark UI, and that is
what the frame is for. A ChromIQ layout-engine chart carries its own paper
border (56 px, 7 mm, same measurement) and was getting the frame on top, so the
preview showed a wider white edge than the sheet has (Basti, 2026-08-22).

The frame is now measured against the image. These pin the cases where measuring
it could go WRONG — every one of which drops the frame on a page that needs it,
which is worse than the fault being fixed.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from PyQt6.QtGui import QColor, QImage, QPainter, QPixmap  # noqa: E402
from PyQt6.QtWidgets import QApplication                    # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def preview(qapp):
    from ui.tiff_preview import TiffPreview
    return TiffPreview()


def page(fill, *, band=0, rim=0, inner=None, w=400, h=560):
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor(*fill))
    p = QPainter(img)
    if inner is not None:
        p.fillRect(rim, rim, w - 2 * rim, h - 2 * rim, QColor(*inner))
    if band:
        p.fillRect(0, 0, w, band, QColor(0, 0, 0))
    p.end()
    return QPixmap.fromImage(img)


# Built inside the test, never at collection: a QPixmap made before the
# QApplication exists aborts the interpreter.
@pytest.mark.parametrize("name,kw", [
    # Reading the corner and trusting it credited this page with 0.027 of blank
    # margin and dropped the frame — ink hard against the edge, the exact case
    # the frame exists for, inverted.
    ("a black band running to the edge", dict(fill=(255, 255, 255), band=40)),
    ("a flat dark full-bleed page", dict(fill=(28, 28, 30))),
    # qGray 244: near enough to white that a loose tolerance called the whole
    # page blank.
    ("a flat (255,255,200) full-bleed", dict(fill=(255, 255, 200))),
    ("a blank page", dict(fill=(255, 255, 255))),
    ("printtarg: ink flush to the left edge",
     dict(fill=(255, 255, 255), rim=0, inner=None)),
])
def test_these_pages_keep_the_whole_frame(preview, name, kw):
    fill = kw.pop("fill")
    preview._measure_own_margin(page(fill, **kw))
    assert preview._own_margin_frac == 0.0, f"{name}: credited with a margin"
    assert preview._border_px(400) == 15, f"{name}: lost its frame"


def test_a_chart_that_brings_its_own_border_does_not_get_a_second(preview):
    """56 px of paper on a 400 px page — the engine chart's real proportion."""
    preview._measure_own_margin(page((255, 255, 255), rim=56, inner=(120, 120, 120)))
    assert preview._own_margin_frac == pytest.approx(56 / 400, abs=0.01)
    assert preview._border_px(400) == 0
    # …but on a small window it is owed the shortfall again: the frame is a
    # DIFFERENCE, not a flag.
    assert preview._border_px(60) > 0


def test_near_white_content_is_not_mistaken_for_paper(preview):
    """A 248-grey field inside a 5 px rim. At a tolerance of 12 this measured a
    quarter of the page as margin and the frame vanished."""
    preview._measure_own_margin(
        page((255, 255, 255), rim=5, inner=(248, 248, 248)))
    # The 5 px rim is real, so a little is rightly credited — the fault being
    # guarded is the frame COLLAPSING: at tol 12 this measured 0.239 and B fell
    # to 0, hiding a chart's ink against the edge.
    assert preview._own_margin_frac < 0.02
    assert preview._border_px(400) >= 10


def test_the_soft_proofs_paper_frame_survives_being_pure_white(preview):
    """There the frame is not padding — it is the simulated paper white around
    the proof, and Basti asked for it to stay. It cannot be recognised by
    COLOUR: `softproof_runner` computes that white from Lab and it clips to
    255,255,255 on a bright stock, which a colour test reads as "no tint"."""
    preview._measure_own_margin(page((255, 255, 255), rim=56, inner=(120, 120, 120)))
    assert preview._border_px(400) == 0                    # plain white: dropped
    preview.set_frame_color(QColor(255, 255, 255))          # the clipped case
    assert preview._border_px(400) == 15
    preview.set_frame_color(QColor(236, 228, 209))          # an ordinary tint
    assert preview._border_px(400) == 15
    preview.set_frame_color(None)                           # back to padding
    assert preview._border_px(400) == 0


def test_the_page_edge_rectangle_stays_inside_the_canvas(preview):
    """#83's remedy: a solid rectangle on the image boundary, so the display
    frame cannot be mistaken for page margin. It was drawn AT the boundary,
    which put its right and bottom edges one pixel past the canvas — invisible
    only while a frame was always there to absorb them."""
    import inspect
    src = inspect.getsource(preview._draw_margin_guides)
    head = src.split("for axis", 1)[0]
    assert "border + 0.5" in head and "disp_w - 1.0" in head, (
        "the page-edge rectangle must be inset half a pen, or it loses two "
        "sides on any chart whose frame is 0")
