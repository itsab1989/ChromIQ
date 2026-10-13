"""4.3.5 beta 2 (Knut, #182 6134781112): "some of the hover-text cards are
very tall, probably causing trouble on lower resolution screens. Above a
certain height the cards should be made wider to prevent too tall hover
text."

THE SIZE RULE (``ui.tiff_preview.card_limits`` and ``_PatchInfoTile._lay_out``):
a card is at most CARD_MAX_SCREEN_HEIGHT of the screen's available height and
never taller than the window it floats on; a taller one is laid out wider
(longer lines, then two columns, three as a last resort), never wider than
CARD_MAX_SCREEN_WIDTH of the screen and the window. A card that fits keeps
its 40 columns, line for line.

The windows are full-height ones, measured: 1280x677 on 1280x800 and
1440x777 on 1440x900, each with the Dock shown (available 1280x705 and
1440x805). Checked with the longest variants in every
catalogue (French makes the tallest cards), today's texts and the proposed
ones (M-PATCH-CARD-PLAIN), and the placement keeps every card inside the
window wherever the pointer is.
"""
from __future__ import annotations

import dataclasses

import pytest
from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QWidget

from workflow import measurement_messages as M

D5 = {"loc": "D5", "exp_rgb": (140, 86, 74), "meas_rgb": (136, 95, 72),
      "exp_lab": (42.6263, 21.9922, 16.8117),
      "meas_lab": (44.4158, 14.8051, 20.0084),
      "de": 8.07, "expected_source": "prediction", "kind": "verification",
      "accurate": True, "colour_range": "red", "range_k": 1,
      "range_locs": ["D5"],
      "nb_compare": lambda loc: (4, 6.44),
      "nb_detail": lambda loc: (4, 6.44, 8.07, 1.63)}
NB = {"n": 4, "further": 6.44, "limit": 5.5}
#: the tallest cards (40 columns: 56 to 62 lines proposed)
LONG = {
    "red_both": {"warn": True, "warn_de": 7.5, "neighbour": NB},
    "yellow_neighbour": {"flag": "confirmed", "prev_de": 6.70,
                         "neighbour": NB},
    "yellow_limit": {"flag": "confirmed", "prev_de": 6.70, "warn": True,
                     "warn_de": 7.5},
    "red_fenced": {"warn": True, "warn_de": 7.5, "fenced": True},
    "unsettled_three_neighbour": {"warn": True, "warn_de": 5.0,
                                  "unsettled": [12.3, 18.4], "neighbour": NB},
    "yellow_peers": {"flag": "confirmed", "peer_locs": ["F3", "H9"],
                     "warn": True, "warn_de": 7.5},
    "red_later_profile": {"expected_source": "estimate_profile_newer",
                          "warn": True, "warn_de": 7.5, "neighbour": NB},
}
#: name: (available width, height; the full-height window's width, height)
SCREENS = {"1280x800": (1280, 705, 1280, 677),
           "1440x900": (1440, 805, 1440, 777)}
#: every catalogue; French makes the tallest cards (64 lines at 40 columns)
LANGS = ["en", "de", "es", "fr", "it", "ja", "nl", "no", "pl", "pt", "ru",
         "sv", "uk", "zh_CN"]

_KEEP: list = []


def _tile(info, max_size=None, mode="both"):
    from ui.tiff_preview import _PatchInfoTile
    host = QWidget()
    _KEEP.append(host)
    tile = _PatchInfoTile(host)
    tile.set_content({**D5, **info}, mode, max_size=max_size)
    return tile


@pytest.fixture
def lang(request):
    from core import i18n
    before = i18n.current_language()
    i18n.set_language(request.param)
    yield request.param
    i18n.set_language(before)


@pytest.fixture(params=[False, True], ids=["today", "proposed"])
def wording(request, monkeypatch):
    if request.param:
        monkeypatch.setattr(M, "M_PATCH_CARD_PLAIN", dataclasses.replace(
            M.M_PATCH_CARD_PLAIN, approved=True))
    return request.param


def test_the_limits():
    from ui.tiff_preview import card_limits, CARD_MAX_SCREEN_HEIGHT
    assert card_limits(1280, 677, 1280, 705) == (768, int(705 * CARD_MAX_SCREEN_HEIGHT))
    # the window decides when it is the smaller
    assert card_limits(400, 300, 2560, 1400) == (396, 296)
    # no screen known: the window alone
    assert card_limits(696, 468, None, None) == (692, 464)


def test_a_card_that_fits_keeps_its_forty_columns(qapp, wording):
    short = {"nb_compare": lambda loc: (1, 0.0)}
    free = _tile(short)
    held = _tile(short, max_size=(2000, 2000))
    assert free._rows == held._rows
    assert (free.width(), free.height()) == (held.width(), held.height())


@pytest.mark.parametrize("lang", LANGS, indirect=True)
@pytest.mark.parametrize("screen", sorted(SCREENS))
@pytest.mark.parametrize("case", sorted(LONG))
def test_the_longest_cards_fit_the_small_screens(qapp, wording, lang, screen,
                                                 case):
    from ui.tiff_preview import card_limits
    aw, ah, pw, ph = SCREENS[screen]
    max_w, max_h = card_limits(pw, ph, aw, ah)
    tile = _tile(LONG[case], max_size=(max_w, max_h))
    assert tile.width() <= max_w, (lang, screen, case, tile.width())
    assert tile.height() <= max_h, (lang, screen, case, tile.height())


@pytest.mark.parametrize("lang", ["en", "de", "ru"], indirect=True)
def test_a_tall_card_gets_wider_not_taller(qapp, lang):
    from ui.tiff_preview import card_limits
    aw, ah, pw, ph = SCREENS["1280x800"]
    tall = _tile(LONG["yellow_neighbour"])
    held = _tile(LONG["yellow_neighbour"], max_size=card_limits(pw, ph, aw, ah))
    assert held.height() < tall.height()
    assert held.width() > tall.width()


@pytest.mark.parametrize("lang", ["en", "de", "ru"], indirect=True)
@pytest.mark.parametrize("case", sorted(LONG))
def test_columns_are_cut_between_sentences(qapp, wording, lang, case):
    """A column starts at a topic (after an empty line, or with the
    separator or a heading) or after a finished sentence, never inside
    one."""
    from ui.tiff_preview import card_limits, _CardBold, _SENTENCE_ENDS
    aw, ah, pw, ph = SCREENS["1280x800"]
    tile = _tile(LONG[case], max_size=card_limits(pw, ph, aw, ah))
    for start, _end, x in tile._spans[1:]:
        first = tile._rows[start][1]
        before = tile._rows[start - 1][1]
        assert (before == "" or first == "─" * 30
                or isinstance(first, _CardBold)
                or before.rstrip().endswith(_SENTENCE_ENDS)), (case, before, first)


def test_the_hand_broken_lines_are_joined_only_when_wider(qapp):
    from ui.tiff_preview import card_limits
    red = {**LONG["red_both"], "expected_source": None, "accurate": False,
           "kind": "estimated"}
    narrow = [t for _s, t in _tile(red)._rows]
    assert "Either a misread, or a colour" in narrow
    assert "this printer and paper cannot reach." in narrow
    aw, ah, pw, ph = SCREENS["1280x800"]
    wide = _tile(red, max_size=card_limits(pw, ph, aw, ah))
    text = " ".join(t for _s, t in wide._rows)
    assert "Either a misread, or a colour this printer and paper" in " ".join(text.split())


def test_a_column_is_drawn(qapp):
    """Paints without error with two columns, light and dark."""
    from ui.tiff_preview import card_limits
    aw, ah, pw, ph = SCREENS["1280x800"]
    tile = _tile(LONG["yellow_neighbour"], max_size=card_limits(pw, ph, aw, ah))
    assert len(tile._spans) >= 2
    for mode in ("light", "dark"):
        tile.set_theme(mode)
        img = tile.grab()
        assert not img.isNull() and img.width() == tile.width()


@pytest.mark.parametrize("wording", [True], indirect=True)
@pytest.mark.parametrize("screen", sorted(SCREENS))
def test_the_card_never_leaves_the_window(qapp, wording, monkeypatch, screen):
    """A preview of the Measure tab's size in a window of the small screens'
    size: hovered at every corner of the preview, the longest card stays
    inside the window, and it floats on the window, not in the preview."""
    from PyQt6.QtWidgets import QHBoxLayout
    from ui import tiff_preview as tp
    aw, ah, ww, wh = SCREENS[screen]
    monkeypatch.setattr(tp, "_card_screen_area", lambda w: (aw, ah))
    win = QWidget()
    _KEEP.append(win)
    win.resize(ww, wh)
    lay = QHBoxLayout(win)
    lay.setContentsMargins(ww - 696 if ww == 1280 else ww - 856, 0, 0, 0)
    pv = tp.TiffPreview()
    lay.addWidget(pv)
    win.show()
    qapp.processEvents()
    pw, ph = pv.width(), pv.height()
    pv._pixmap = QPixmap(10, 10)
    pv._show_patch_tile = True
    pv._patch_info = {pv._current: [(QRect(0, 0, 10, 10),
                                     {**D5, **LONG["yellow_neighbour"]})]}
    monkeypatch.setattr(pv, "_image_px_at", lambda p: (5, 5))
    for x, y in ((5, 5), (pw - 5, 5), (5, ph - 5), (pw - 5, ph - 5),
                 (pw // 2, ph // 2)):
        pv._update_patch_tile(QPoint(x, y))
        assert pv._patch_tile.parentWidget() is win
        g = pv._patch_tile.geometry()
        assert g.left() >= 0 and g.top() >= 0, (x, y, g)
        assert g.right() < ww and g.bottom() < wh, (x, y, g)
    win.hide()
    assert pv._patch_tile.isHidden()
