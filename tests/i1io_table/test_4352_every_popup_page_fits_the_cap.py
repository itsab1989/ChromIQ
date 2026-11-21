"""4.3.52 release (re-review of the table sub-options, SHOULD-2): a table pop-up widens until its
answers fit in one row, up to POPUP_WIDE_MAX_W. Measured ON SCREEN, the widest German page
(row_failed_strip) needed 897 of the then 900 px, so a slightly longer translation would have
stacked its answers again, and only a user would have seen it.

This test measures EVERY answer page of the table window in EVERY language ChromIQ ships and
fails when one needs more than the cap minus a margin, so a too-long translation is caught here.

Which pages: the ones the window's tests showed (tests/data/i1io_table_popup_pages.json), every
``_show`` call in ui/i1io_table_window.py whose answers are literal ``tr()`` texts, and every
confirmation in ``choice_label``. A page id that is literal in the window and covered by none of
these fails the test, so a new page cannot slip past it.

Offscreen fonts are narrower than the screen's, so each button's offscreen width is turned into
its on-screen width by BTN_SCALE and BTN_PAD: a straight line fitted to 184 buttons measured on
screen and offscreen on the same pages (English and German, the fix round's photographs of
2026-11-20, residual within +-20 px per button). For the German row_failed_strip it gives 902 px
where the screen measured 897. Russian row_failed_strip comes out widest, at about 916 px: with
the old cap of 900 its answers were stacked on screen, so the cap is now 1000.

MUTATION, proven red: POPUP_WIDE_MAX_W set back to 900 -> Russian, German, Dutch and others
fail (more than 840 px).
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core import i18n
from core.i18n import tr
from tests.i1io_table.test_window import open_window, settings  # noqa: F401 (the fixture)
from ui import i1io_table_window as W

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "ui" / "i1io_table_window.py"
#: room left under the cap on the screen's scale, for a translation reworded a little later and
#: for a slightly larger system font
MARGIN_PX = 60
#: a button's on-screen width = BTN_SCALE x its offscreen width + BTN_PAD (see the module text;
#: fitted 1.2566 and 19.96, rounded up)
BTN_SCALE, BTN_PAD = 1.26, 20
#: the smallest screen ChromIQ is laid out for; the cap must fit on it with room to spare
SMALL_SCREEN_W = 1280
#: page ids with no answers (nothing to lay out in a row)
NO_ANSWERS = {"countdown"}


def _choice_label_pages() -> "list[tuple[str, list[str]]]":
    """Every confirmation of choice_label(): its kind and the English texts of its answers."""
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "choice_label")
    table = next(n for n in ast.walk(fn) if isinstance(n, ast.Dict))
    pages: "dict[str, list[str]]" = {}
    for k, v in zip(table.keys, table.values):
        kind = k.elts[0].value
        pages.setdefault(kind, []).append(v.args[0].value)
    out = sorted(pages.items())
    # 4.3.54: row_failed_strip shows "Read it patch by patch" OR, on the one page that offers it
    # (the second row of a page the row placement check refused), "Rest patch by patch" in its
    # place (the window's own rule): never both, so its two real pages are measured
    both = dict(out).get("row_failed_strip", [])
    if "Rest patch by patch" in both:
        out = [(k, v) for k, v in out if k != "row_failed_strip"]
        out += [("row_failed_strip", [x for x in both if x != "Rest patch by patch"]),
                ("row_failed_strip", [x for x in both if x != "Read it patch by patch"])]
    return out


def _literal_pages() -> "tuple[list[tuple[str, list[str]]], set[str]]":
    """The ``_show`` calls with a literal page id: those whose answers are all literal tr()
    texts, and the set of every literal page id."""
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    full, ids = [], set()
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "_show" and n.args
                and isinstance(n.args[0], ast.Constant)):
            continue
        ids.add(n.args[0].value)
        if len(n.args) < 4 or not isinstance(n.args[3], (ast.List, ast.Tuple)):
            continue
        labels = []
        for e in n.args[3].elts:
            first = e.elts[0] if isinstance(e, ast.Tuple) else None
            if (isinstance(first, ast.Call) and getattr(first.func, "id", "") == "tr"
                    and isinstance(first.args[0], ast.Constant)):
                labels.append(first.args[0].value)
            else:
                labels = None
                break
        if labels:
            full.append((n.args[0].value, labels))
    return full, ids


def _all_pages() -> "list[tuple[str, list[str]]]":
    data = json.loads((ROOT / "tests" / "data" / "i1io_table_popup_pages.json")
                      .read_text(encoding="utf-8"))["pages"]
    pages = [(p, list(labels)) for p, labels in data]
    literal, _ids = _literal_pages()
    pages += literal + _choice_label_pages()
    seen, out = set(), []
    for p, labels in pages:
        key = (p, tuple(labels))
        if key not in seen:
            seen.add(key)
            out.append((p, labels))
    return out


def _languages() -> "list[str]":
    return [code for code, _name in i18n.available_languages()]


def _on_screen(win) -> int:
    """The width this page's answers need in one row ON SCREEN (see the module text)."""
    off = [max(b.sizeHint().width(), b.minimumSizeHint().width()) for b in win._buttons]
    return round(win._popup_row_need() + sum((BTN_SCALE - 1) * w + BTN_PAD for w in off))


class _Noop:
    def fire(self) -> None:
        pass


def test_every_literal_page_of_the_window_is_measured():
    _literal, ids = _literal_pages()
    measured = {p for p, _l in _all_pages()}
    missing = sorted(ids - measured - NO_ANSWERS)
    assert missing == [], ("pages of the table window this test does not measure; add their "
                           "answers to tests/data/i1io_table_popup_pages.json", missing)


def test_all_thirteen_languages_and_english_are_measured():
    langs = _languages()
    assert "en" in langs and len(langs) >= 14, langs


def test_the_cap_fits_a_small_screen_with_room():
    # _popup_width also caps at the screen's width minus 80; the fixed cap itself must leave
    # room on a 1280 x 800 screen
    assert W.POPUP_WIDE_MAX_W + 80 + 100 <= SMALL_SCREEN_W, W.POPUP_WIDE_MAX_W


def test_every_page_in_every_language_fits_under_the_cap(qtbot, monkeypatch, tmp_path,
                                                         settings):  # noqa: F811
    win, *_ = open_window(qtbot, monkeypatch, tmp_path, settings, asking=False)
    assert win._popups
    pages = _all_pages()
    limit = W.POPUP_WIDE_MAX_W - MARGIN_PX
    too_wide, widest = [], (0, "", "")
    try:
        for code in _languages():
            i18n.set_language(code)
            for page, labels in pages:
                noop = _Noop()
                win._noop = noop
                win._show(page, "Title", "Text.", [(tr(x), noop.fire) for x in labels])
                need = _on_screen(win)
                if need > widest[0]:
                    widest = (need, code, page)
                if need > limit:
                    too_wide.append((code, page, need, [tr(x) for x in labels]))
    finally:
        i18n.set_language("en")
    assert widest[0] > 300, "nothing was measured"
    assert too_wide == [], (f"answers wider than {limit} px (cap {W.POPUP_WIDE_MAX_W} minus "
                            f"{MARGIN_PX}): shorten the translation or raise the cap", too_wide)

