"""#130 (Knut, 2026-07-28): the "Overview of Main Actions" card.

    *"Call this table 'Overview of Main Actions' and create this as a separate
    help card next to the Getting Started Card. Make sure the card uses the
    table format, like html table, to get the nice look. Also, when there is
    only one action alternative, you do not need to show (a) in front."*

Four requirements, each tested: the **name**, its **place** beside the tour, the
**table** format, and the **lettering only where it earns its place**.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication              # noqa: E402

from ui.main_actions import (ACTION_ROWS, CANNOT_ROWS,  # noqa: E402
                             main_actions_card_subtitle,
                             main_actions_card_title, main_actions_html)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_it_is_called_what_he_called_it():
    assert main_actions_card_title() == "Overview of Main Actions"


def test_it_sits_next_to_the_getting_started_card(qapp):
    from ui.dialogs.welcome_dialog import WORKFLOWS
    assert WORKFLOWS[0]["key"] == "getting_started"
    assert WORKFLOWS[1]["key"] == "main_actions", "it must sit beside the tour"


def test_the_window_knows_how_to_render_it(qapp):
    import inspect

    from ui.dialogs import welcome_dialog
    src = inspect.getsource(welcome_dialog)
    assert '"main_actions"' in src and "main_actions_html" in src


def test_it_really_is_a_table(qapp):
    html = main_actions_html()
    assert html.count("<table") == 2, "the actions, and what cannot be done"
    assert "<th>" in html and "<td>" in html


def test_a_single_route_is_not_lettered(qapp):
    """His words: "when there is only one action alternative, you do not need
    to show (a) in front"."""
    html = main_actions_html()
    for action, routes in ACTION_ROWS:
        if len(routes) != 1:
            continue
        row = html.split(f"<b>{action}</b>", 1)
        assert len(row) == 2, action
        cell = row[1].split("</tr>", 1)[0]
        assert "(a)" not in cell, f"{action} has one route but is lettered"


def test_several_routes_are_lettered(qapp):
    html = main_actions_html()
    multi = [a for a, r in ACTION_ROWS if len(r) > 1]
    assert multi, "the point of the card is that most actions have several"
    for action in multi:
        cell = html.split(f"<b>{action}</b>", 1)[1].split("</tr>", 1)[0]
        assert "(a)" in cell and "(b)" in cell, action


def test_every_action_and_every_route_reaches_the_page(qapp):
    import html as _h
    page = main_actions_html()
    for action, routes in ACTION_ROWS:
        assert _h.escape(action, quote=False) in page, action
        for r in routes:
            assert _h.escape(r, quote=False) in page, r


def test_the_cannot_do_list_is_carried_with_it(qapp):
    """He asked for it to be kept with the actions."""
    import html as _h
    page = main_actions_html()
    assert "What ChromIQ cannot do today" in page
    for what, instead in CANNOT_ROWS:
        assert _h.escape(what, quote=False) in page, what
        assert _h.escape(instead, quote=False) in page, what


def test_printing_through_a_profile_is_recorded_as_a_future_improvement():
    """His ruling: not a feature to build — explain what it means, and note it
    as a possible future improvement."""
    row = next((c for c in CANNOT_ROWS if "Print through a profile" in c[0]), None)
    assert row is not None, "it must appear in the cannot-do list"
    _what, instead = row
    assert "possible future improvement" in instead
    assert "colour management off" in instead, "it must explain WHY"
    assert "the program you normally print from" in instead, \
        "it must say where printing through a profile is actually done"


def test_the_future_improvements_are_marked_as_such():
    marked = [w for w, i in CANNOT_ROWS if "possible future improvement" in i]
    assert len(marked) >= 3, "the ones worth revisiting should say so"


def test_no_bracketed_plural(qapp):
    for text in (main_actions_html(), main_actions_card_title(),
                 main_actions_card_subtitle()):
        assert "(s)" not in text


def test_every_row_string_reaches_the_translation_catalogue():
    """The fault this test was written to catch, and did: strings translated
    only at render time are INVISIBLE to the extractor, so they would silently
    stay English through a translation pass. Every row literal is wrapped in
    tr() where it is defined, so the extractor sees it."""
    import sys
    sys.path.insert(0, "scripts")
    from i18n_extract import extract_keys
    keys = extract_keys()
    missing = []
    for action, routes in ACTION_ROWS:
        for s in [action, *routes]:
            if s not in keys:
                missing.append(s)
    for what, instead in CANNOT_ROWS:
        for s in (what, instead):
            if s not in keys:
                missing.append(s)
    assert not missing, f"never translatable: {missing[:3]}"


# ---- the card icons Knut chose (#130, 2026-07-28) -----------------------
def test_both_new_cards_have_their_own_icon(qapp):
    """He picked B for each: "Getting started: B — Interface map" and
    "Overview of Main Actions: B — Branching routes". Before this, both cards
    fell through to the default and showed nothing."""
    import inspect

    from ui.dialogs.welcome_dialog import WorkflowIcon
    src = inspect.getsource(WorkflowIcon.paintEvent)
    assert 'self._key == "getting_started"' in src
    assert 'self._key == "main_actions"' in src


def test_the_icons_paint_without_error(qapp):
    from PyQt6.QtGui import QImage
    from ui.dialogs.welcome_dialog import WorkflowIcon
    for key in ("getting_started", "main_actions"):
        for mode in ("dark", "light"):
            w = WorkflowIcon(key)
            w.set_appearance(mode)
            img = QImage(96, 96, QImage.Format.Format_ARGB32)
            img.fill(0)
            w.render(img)                      # must not raise
            assert img.width() == 96


def test_each_icon_actually_draws_something(qapp):
    """A key that falls through the if/elif chain paints nothing at all —
    which is exactly what these two cards did before."""
    from PyQt6.QtGui import QImage
    from ui.dialogs.welcome_dialog import WorkflowIcon
    for key in ("getting_started", "main_actions"):
        w = WorkflowIcon(key)
        w.set_appearance("dark")
        img = QImage(96, 96, QImage.Format.Format_ARGB32)
        img.fill(0)
        w.render(img)
        painted = sum(1 for y in range(0, 96, 3) for x in range(0, 96, 3)
                      if img.pixelColor(x, y).alpha() > 0)
        assert painted > 40, f"{key} painted almost nothing ({painted})"


def test_they_use_the_shared_accent(qapp):
    """One magenta accent, like every other card icon."""
    import inspect

    from ui.dialogs.welcome_dialog import WorkflowIcon
    src = inspect.getsource(WorkflowIcon.paintEvent)
    block = src.split('self._key == "getting_started"', 1)[1].split("elif", 2)
    assert "accent" in block[0], "the Getting started icon has no accent"
