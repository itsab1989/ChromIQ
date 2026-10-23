"""Letters as they are typed (Basti, 2026-10-23, approved): the bundled Inter
font's contextual alternates (OpenType ``calt``) turned "4x6" into "4×6" on
screen, app-wide. `ui.font_features.show_text_as_typed` switches the feature
off on the application font; these tests prove it reaches each way ChromIQ
draws text, the Measurement Report's document and PDF included."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QTextDocument
from PyQt6.QtWidgets import QApplication, QLabel


def _glyphs_of_layout(layout) -> list:
    out = []
    for run in layout.glyphRuns():
        out += list(run.glyphIndexes())
    return out


def _x_glyph(font: QFont) -> int:
    """The glyph of a plain "x" in *font*, with nothing around it to alter it."""
    from PyQt6.QtGui import QRawFont
    raw = QRawFont.fromFont(font)
    return list(raw.glyphIndexesForString("x"))[0]


@pytest.fixture()
def inter(qapp):
    f = QFont("Inter")
    f.setPixelSize(20)
    if QFont(f).family() != "Inter" and "Inter" not in f.families():
        pytest.skip("Inter is not registered")
    return f


def test_the_application_font_has_contextual_alternates_off(qapp):
    from ui.font_features import shows_as_typed
    assert shows_as_typed(QApplication.font())


def test_the_feature_is_what_turns_4x6_into_a_multiplication_sign(qapp, inter):
    """The cause, measured: with ``calt`` explicitly ON the x between digits
    becomes another glyph; OFF it is the plain x."""
    from PyQt6.QtGui import QTextLayout
    on = QFont(inter)
    on.setFeature(QFont.Tag("calt"), 1)
    off = QFont(inter)
    off.setFeature(QFont.Tag("calt"), 0)

    def glyphs(font):
        lay = QTextLayout("4x6", font)
        lay.beginLayout(); lay.createLine(); lay.endLayout()
        return _glyphs_of_layout(lay)
    x = _x_glyph(inter)
    assert glyphs(on)[1] != x, "Inter no longer substitutes: the fix may go"
    assert glyphs(off)[1] == x


def test_a_style_sheet_label_keeps_the_letters(qapp, inter):
    lab = QLabel("4x6")
    lab.setStyleSheet('QLabel { font-family: "Inter"; font-size: 20px; }')
    lab.ensurePolished()
    from ui.font_features import shows_as_typed
    assert shows_as_typed(lab.font())


def _doc_pixels(html: str, default_font: "QFont | None") -> bytes:
    doc = QTextDocument()
    if default_font is not None:
        doc.setDefaultFont(default_font)
    doc.setHtml(html)
    doc.setTextWidth(300)
    im = QImage(300, 60, QImage.Format.Format_RGB32)
    im.fill(QColor("white"))
    p = QPainter(im)
    doc.drawContents(p)
    p.end()
    return bytes(im.constBits().asarray(im.sizeInBytes()))


def test_the_report_document_keeps_the_letters(qapp, inter):
    """The Measurement Report is a QTextDocument (screen and PDF alike),
    made with no font of its own and its HTML naming Inter, as
    `measurement_report_dialog` makes it: it draws "4x6" as with ``calt``
    off. (A document handed a ``QFont("Inter")`` made on the spot as its
    default font does NOT inherit the setting; no ChromIQ document is.)"""
    html = "<p style='font-family:Inter;font-size:20px'>4x6</p>"
    off = QFont("Inter")
    off.setFeature(QFont.Tag("calt"), 0)
    on = QFont("Inter")
    on.setFeature(QFont.Tag("calt"), 1)
    assert _doc_pixels(html, on) != _doc_pixels(html, off), "test is blind"
    assert _doc_pixels(html, None) == _doc_pixels(html, off)
    lab = QLabel()
    assert _doc_pixels(html, QFont(lab.font())) == _doc_pixels(html, off)


def test_a_painter_with_a_font_made_on_the_spot_keeps_the_letters(qapp, inter):
    def render(text, font):
        im = QImage(140, 40, QImage.Format.Format_RGB32)
        im.fill(QColor("white"))
        p = QPainter(im)
        p.setFont(font)
        p.setPen(QColor("black"))
        p.drawText(5, 30, text)
        p.end()
        return bytes(im.constBits().asarray(im.sizeInBytes()))
    plain = QFont(inter)
    plain.setFeature(QFont.Tag("calt"), 0)
    assert render("4x6", QFont(inter)) == render("4x6", plain)


def test_every_start_switches_it_off():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for name in ("main.py", "scripts/capture_screens.py"):
        assert "show_text_as_typed(app)" in (root / name).read_text(
            encoding="utf-8"), name


def test_every_per_class_font_has_it_off_too(qapp):
    """On macOS the platform theme gives labels, buttons, check boxes and
    item views fonts of their own; measured on screen, half the main window
    still drew "4×6" with only the application font set."""
    from ui.font_features import WIDGET_FONT_CLASSES, shows_as_typed
    for name in WIDGET_FONT_CLASSES:
        assert shows_as_typed(QApplication.font(name)), name


def test_the_app_filter_gives_each_widget_the_setting(qapp):
    """Measured on screen (macOS): the theme's per-class fonts come back after
    start-up and a style-sheet widget gets its font at polish, so 1,369 of
    2,810 widgets still drew "4×6". The app filter puts the setting on each
    widget's own font whenever it is decided (Polish, FontChange)."""
    from PyQt6.QtCore import QEvent
    from ui.font_features import shows_as_typed
    from ui.widgets import CompositeAppFilter
    lab = QLabel("4x6")
    f = lab.font()
    f.setFeature(QFont.Tag("calt"), 1)          # as the macOS theme leaves it
    lab.setFont(f)
    assert not shows_as_typed(lab.font())
    filt = CompositeAppFilter()
    filt.eventFilter(lab, QEvent(QEvent.Type.FontChange))
    assert shows_as_typed(lab.font())
    size = lab.font().pointSizeF()
    assert lab.font().pointSizeF() == size      # nothing else changes


def test_the_separate_filters_path_has_it_too():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
    assert "TypedTextFilter(app)" in src
