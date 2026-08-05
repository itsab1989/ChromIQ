"""Shared guard for tests that assert on real font glyph advances.

A number of tests measure widths — button fits, tree-connector alignment, the
masthead / measurement-target-bar layout — with ``QFontMetrics.horizontalAdvance``
and friends. Those numbers only mean something when the Qt font database holds
real fonts.

Under ``QT_QPA_PLATFORM=offscreen`` that holds on macOS (the offscreen platform
still exposes the system fonts, which is why these tests pass on the release
gate) but NOT on Windows, where the offscreen platform exposes an **empty** font
database: every family requested falls back to a null font, so ``the label is
288px`` and ``uppercase Menlo is wider`` are measured against nothing and the
assertions are meaningless rather than wrong.

So these tests skip cleanly when the fonts they need are not present, instead of
failing on un-measurable numbers. The macOS gate — where the fonts are real —
remains the authority and is unaffected.
"""
from __future__ import annotations

import pytest


def skip_without_fonts() -> None:
    """Skip when this Qt/QPA exposes no real font families at all."""
    from PyQt6.QtGui import QFontDatabase
    if not QFontDatabase.families():
        pytest.skip("this Qt/QPA exposes no font families — glyph-advance "
                    "assertions cannot be measured (offscreen on Windows)")


def skip_without_family(family: str) -> None:
    """Skip when a specific font *family* does not resolve here."""
    from PyQt6.QtGui import QFont, QFontInfo
    skip_without_fonts()
    if QFontInfo(QFont(family)).family().lower() != family.lower():
        pytest.skip(f"font {family!r} is not available in this Qt font database")
