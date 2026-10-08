"""Beta 15 follow-up: the approved neighbour-check line keeps the card narrow.

k43, approved by Knut in #182 6059912998 (answer 5): "Checked again after each
strip: a patch can turn red later, when patches near it in colour are read".
Broken only at the comma, its first half was the widest line on the red card
and made it about 500 px wide in every language (beta 15 review B). The card
breaks its lines by hand, so the sentence is now broken at the colon too: the
words are unchanged, and no part of it is noticeably wider than the card's
other lines.
"""
from __future__ import annotations

import pytest

from tests.test_neighbour_check_in_the_measure_tab import (  # noqa: F401
    _info, _read_all, _tab, qapp)
from workflow import measurement_messages as M

LATER = (M._CARD_NB_LATER_1, M._CARD_NB_LATER_1B, M._CARD_NB_LATER_2)


@pytest.fixture(autouse=True)
def _restore_the_ui_language():
    import core.i18n as i18n
    previous = getattr(i18n, "_language", "en")
    try:
        yield
    finally:
        i18n.set_language(previous)


def test_the_words_are_the_approved_ones():
    assert " ".join(LATER).rstrip(".") == M.NB_CHECKED_AGAIN


@pytest.mark.parametrize("lang", ["en", "de", "ru", "uk", "pl"])
def test_the_approved_line_is_not_the_cards_widest(qapp, tmp_path, lang):
    import core.i18n as i18n
    from PyQt6.QtGui import QFontMetrics
    from PyQt6.QtWidgets import QWidget
    from ui.tiff_preview import _PatchInfoTile

    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55})
    info = _info(tab, "D6")
    assert info["neighbour"]
    i18n.set_language(lang)
    host = QWidget()
    tile = _PatchInfoTile(host)
    tile.set_content(info, "both")
    fm = QFontMetrics(tile._font)
    later = [i18n.tr(s) for s in LATER]
    texts = [t for _sw, t in tile._rows]
    i = texts.index(later[0])
    assert texts[i:i + 3] == later
    others = [t for t in texts if t not in later]
    widest_other = max(fm.horizontalAdvance(t) for t in others)
    widest_later = max(fm.horizontalAdvance(t) for t in later)
    # 5 % of air: the Ukrainian third line, translated and unchanged since
    # beta 15, is 7 px (2 %) wider than the card's other lines; before the
    # break at the colon the first line was about 40 % wider.
    assert widest_later <= widest_other * 1.05, (
        lang, widest_later, widest_other,
        max(later, key=fm.horizontalAdvance))
