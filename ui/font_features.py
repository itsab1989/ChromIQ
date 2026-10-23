"""Letters as they are typed: no contextual alternates in ChromIQ's font.

Basti, 2026-10-23 (approved): the bundled Inter font turns "4x6" into
"4×6" on screen, and "100 x 148 mm" into "100 × 148 mm", by itself. That is
its contextual alternates feature, OpenType ``calt``: measured on Inter
4.x (``assets/fonts``), "4x6" shapes to the glyph of a multiplication sign
in the x's place with ``calt`` on and to the plain "x" with it off, and an
"x" between letters is never touched. A project or paper NAME then reads
differently on screen from what is on disk, and a real "×" in a dimension
can no longer be told from a typed "x". So ``calt`` is switched off for the
whole application, and every text that MEANS a multiplication sign carries
the real character "×" itself.

Set on the application font, it reaches every widget (style sheets that
name "Inter" keep it), every ``QPainter`` text (a ``QFont("Inter")`` made
anywhere resolves the feature against the application font), and every
``QTextDocument`` the app lays out, the Measurement Report and its PDF
included. ``tests/test_text_shows_as_typed.py`` keeps it that way.
"""
from __future__ import annotations

#: The OpenType feature switched off: contextual alternates.
FEATURE = "calt"


def show_text_as_typed(app) -> None:
    """Switch Inter's contextual alternates off for every text *app* draws.
    Call it once, right after the QApplication exists and before any window
    is built (``main()``, ``scripts/capture_screens.build_app``, the test
    suite's QApplication)."""
    from PyQt6.QtGui import QFont
    font = app.font()
    font.setFeature(QFont.Tag(FEATURE), 0)
    app.setFont(font)


def shows_as_typed(font) -> bool:
    """True when *font* draws text exactly as typed (``calt`` off)."""
    from PyQt6.QtGui import QFont
    tag = QFont.Tag(FEATURE)
    return font.isFeatureSet(tag) and font.featureValue(tag) == 0
