"""The CMYK+N card's list is a real ``<ol>`` on screen and on paper (#164).

Knut: *"still uses 1) 2) etc for numbered lists, without indent. These
numbered lists shall look on the print and pdf like the other numbered items:
1. 2. 3. etc, with indentation in front, and text belonging to each numbered
item also indented till after the dot of the number, as other help cards do."*

It is the only card written as one prose string instead of `steps` tuples, so
its list was literal characters. Converting at render time rather than
re-cutting the card keeps it as ONE translated key — which is only safe while
every catalogue keeps the marker shape, so that is asserted here too.
"""
import json
import os
import pathlib
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

CATALOGUES = sorted(pathlib.Path("data/i18n").glob("*.json"))


def _body():
    from ui.dialogs.welcome_dialog import _cmyk_n_body
    return _cmyk_n_body()


# ---------------------------------------------------------------------------
# The converter
# ---------------------------------------------------------------------------

def test_the_card_becomes_a_real_ordered_list(qapp):
    from ui.dialogs.welcome_dialog import numbered_prose_html

    html = numbered_prose_html(_body())
    assert html, "the CMYK+N body was not recognised as a numbered list"
    assert html.count("<ol") == 1
    assert html.count("<ul>") == 1, "item 5's sub-points are not a nested list"
    # Six items, plus the three sub-points inside one of them.
    assert html.count("<li>") == 9


@pytest.mark.parametrize("bad,why", [
    ("0) a\n\n1) b", "renumbered from zero"),
    ("１）a\n\n２）b", "full-width digits"),
    ("1) a\n\n3) c", "a marker is missing"),
    ("1) a\n\nprose\n\n2) b", "the items are not contiguous"),
    ("", "empty"),
    ("just prose, no list at all", "no markers"),
])
def test_it_refuses_rather_than_guesses(qapp, bad, why):
    """A translator may renumber or restyle. Half-recognising that would mangle
    the card, so anything but the exact shape falls back to plain prose."""
    from ui.dialogs.welcome_dialog import numbered_prose_html

    assert numbered_prose_html(bad) is None, f"accepted a body that is {why}"


# ---------------------------------------------------------------------------
# The contract the converter rests on
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", CATALOGUES, ids=lambda p: p.stem)
def test_every_translation_keeps_the_list_shape(qapp, path):
    """If this fails, that language's card silently falls back to flat prose.

    Keep the ASCII markers `1)`…`6)` and the three `  • ` sub-points when
    translating this string — the numbers are structure, not wording.
    """
    body = _body()
    val = json.loads(path.read_text(encoding="utf-8")).get(body)
    if val is None:
        pytest.skip("not translated in this catalogue")
    marks = re.findall(r"^\s*(\d+)\)", val, re.M)
    assert marks == ["1", "2", "3", "4", "5", "6"], (
        f"{path.stem}: markers are {marks}, so the card loses its numbered list")
    assert val.count("  • ") == 3, (
        f"{path.stem}: {val.count('  • ')} sub-points, expected 3")


# ---------------------------------------------------------------------------
# Both surfaces
# ---------------------------------------------------------------------------

def test_the_printed_card_numbers_with_dots_and_still_fits_one_page(qapp, tmp_path):
    """`1.` not `1)`, and NOT at the cost of a second sheet holding one line —
    that waste is what Knut objected to elsewhere in the same batch."""
    from PyQt6.QtCore import QMarginsF
    from PyQt6.QtGui import QPageLayout, QPageSize, QPdfWriter
    from PyQt6.QtPdf import QPdfDocument

    from ui.dialogs.welcome_dialog import WORKFLOWS
    from ui.help_card_print import render_card

    wf = next(w for w in WORKFLOWS if w["key"] == "cmyk_n")
    out = tmp_path / "cmyk.pdf"
    writer = QPdfWriter(str(out))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
    pages = render_card(wf, writer)
    del writer

    assert pages == 1, f"the CMYK+N card now takes {pages} pages"
    doc = QPdfDocument(None)
    doc.load(str(out))
    text = " ".join(doc.getAllText(i).text() for i in range(doc.pageCount()))
    assert re.findall(r"\b([1-6])\.\s", text)[:6] == list("123456"), (
        "the printed card does not number its items 1. 2. 3. …")
    # NOT `"1)" not in text` — the prose legitimately says "(tab 1)". What must
    # be gone is a bracket marker at the START of an item.
    from ui.dialogs.welcome_dialog import numbered_prose_html

    html = numbered_prose_html(_body())
    assert not re.search(r"<li><b>\s*\d+\)", html), (
        "an item still opens with a bracket marker")


def test_the_tighter_item_spacing_is_scoped_to_this_card(qapp):
    """The steps cards keep the 10 px they were given in #164."""
    from ui.help_card_print import _PRINT_CSS

    assert "ol.tight li" in _PRINT_CSS, "the tighter rule is not scoped"
    assert re.search(r"^li\s*\{[^}]*margin-bottom:\s*10px", _PRINT_CSS, re.M), (
        "the global list spacing changed — every other card's lists move with it")
