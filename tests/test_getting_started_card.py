"""#130 (Knut, 2026-07-28): the Getting Started card.

His brief, and the order it dictates:

    *"make suggested text for a new 'Getting Started' help card, listing all
    basic and normal actions, with alternative ways to achieve the goals. The
    help card must start by identifying the main areas of the user interface,
    what they are called and where they are and what they are used for."*

So three requirements, each tested here: it **starts** with the interface areas,
it covers the **normal actions**, and it gives the **alternative routes** — which
is the part the survey behind this card found users never discover, because
almost every action has two or three ways to reach it.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication              # noqa: E402

import core.i18n as I                                 # noqa: E402
from ui.getting_started import (getting_started_body,  # noqa: E402
                                getting_started_card_subtitle,
                                getting_started_card_title,
                                getting_started_html)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ---- it starts with the interface --------------------------------------
def test_the_interface_comes_first(qapp):
    """"The help card must start by identifying the main areas.""" ""
    html = getting_started_html()
    areas = html.index("Finding your way around")
    steps = html.index("Your first profile")
    assert areas < steps, "the tour must come before the walkthrough"


@pytest.mark.parametrize("area", [
    "Masthead", "Profile-run bar", "Location being edited", "The five tabs",
    "Options panel", "Preview", "Log", "Tools",
])
def test_every_area_is_named(qapp, area):
    assert area in getting_started_html(), f"{area} is not introduced"


def test_each_area_says_where_it_is_and_what_it_does(qapp):
    """His three questions per area: what it is called, where it is, what it
    is used for — so the table needs all three columns filled."""
    from ui.getting_started import _areas
    for name, where, what in _areas():
        assert name and where and what, name
        assert len(what) > 30, f"{name}: 'what it is for' is too thin"


# ---- the five steps ------------------------------------------------------
@pytest.mark.parametrize("step", [
    "1. Create Chart", "2. Print Chart", "3. Measure", "4. Build Profile",
    "5. Check &amp; Refine",       # the card is HTML — & is escaped
])
def test_every_step_is_covered(qapp, step):
    assert step in getting_started_html()


def test_the_print_step_warns_about_colour_management(qapp):
    """The single most common way a first profile goes wrong."""
    html = getting_started_html()
    assert "Colour management must be OFF" in html


# ---- the alternative routes ---------------------------------------------
@pytest.mark.parametrize("action", [
    "Open an existing chart", "Open a project",
    "Put a chart into a particular run",
    "Add to a measurement instead of replacing it",
    "Bring in a measurement from another program", "Check a profile",
    "Read a few patches without a chart", "Find your files",
])
def test_the_alternative_routes_are_listed(qapp, action):
    assert action in getting_started_html(), f"{action} has no entry"


def test_each_alternative_really_gives_more_than_one_route(qapp):
    """The point of the section: it must name at least two ways, or it is not
    an alternative."""
    from ui.getting_started import _alternatives
    # Two entries honestly have only one route. They earn their place in the
    # section by being things users ask for and cannot find, not by having an
    # alternative — and naming them here means a NEW entry that quietly has
    # only one route still fails this test.
    single_by_design = {"Read a few patches without a chart"}
    single = []
    for title, body in _alternatives():
        if title in single_by_design:
            continue
        # More than one control named: either two "▸" paths, or an explicit
        # alternative. "Or" starting a sentence counts — splitting a long list
        # of routes into separate sentences is easier to read than chaining
        # them with commas, and says exactly the same thing.
        alt = (" or " in body) or (". Or " in body) or body.startswith("Or ")
        if body.count("▸") < 2 and not alt:
            single.append(title)
    assert not single, f"only one route given for: {single}"


# ---- what is kept, what is not ------------------------------------------
def test_it_says_replacing_keeps_a_copy_and_deleting_does_not(qapp):
    html = getting_started_html()
    assert "“old” folder" in html
    assert "permanent" in html
    assert "nothing goes to the Trash" in html.replace("Trash", "Trash")


def test_it_names_the_measurement_as_the_irreplaceable_part(qapp):
    assert "real ink on real paper" in getting_started_html()


# ---- the card is actually shown -----------------------------------------
def test_the_card_is_registered_first(qapp):
    from ui.dialogs.welcome_dialog import WORKFLOWS
    assert WORKFLOWS[0]["key"] == "getting_started", (
        "a first run should meet the tour before the specialised cards")
    assert WORKFLOWS[0]["kind"] == "getting_started"


def test_the_window_knows_how_to_render_it(qapp):
    import inspect

    from ui.dialogs import welcome_dialog
    src = inspect.getsource(welcome_dialog)
    assert '"getting_started"' in src
    # Rendered section by section since Knut's beta.4 index request — each
    # chapter its own widget so the index links can scroll to it.
    assert "getting_started_sections" in src
    assert "_on_gs_index_link" in src


def test_the_title_and_subtitle_say_what_it_is(qapp):
    assert "Getting started" in getting_started_card_title()
    sub = getting_started_card_subtitle()
    assert len(sub) > 40 and "." in sub


# ---- house rules ---------------------------------------------------------
def test_no_bracketed_plural_anywhere(qapp):
    for text in (getting_started_html(), getting_started_body(),
                 getting_started_card_title(), getting_started_card_subtitle()):
        assert "(s)" not in text


def test_the_plain_text_form_carries_the_same_sections(qapp):
    body = getting_started_body()
    for heading in ("Finding your way around", "Your first profile",
                    "More than one way to do most things",
                    "Trying again, and what is kept"):
        assert heading in body, heading


def test_every_string_goes_through_the_catalogue(qapp):
    """Each paragraph is its own tr() key, so the card translates a piece at a
    time — a wall of text as one key is unusable for a translator."""
    import inspect

    import ui.getting_started as gs
    src = inspect.getsource(gs)
    assert src.count("tr(") > 25, "the card should be many small keys"


def test_it_survives_a_language_switch(qapp):
    """A missing translation must fall back to English, never raise."""
    for lang in ("de", "nl", "en"):
        I.set_language(lang)
        try:
            assert getting_started_html()
            assert getting_started_body()
        finally:
            I.set_language("en")


def test_workflow_diagram_chapter_sits_between_tour_and_steps():
    """Knut's example-workflow diagram (2026-08-12): its chapter goes after
    "Finding your way around" and before "Your first profile" — his exact
    placement — and the SVG it needs ships with the app."""
    from ui.getting_started import _chapters, getting_started_sections
    keys = [k for k, _t in _chapters()]
    assert keys.index("workflow") == keys.index("areas") + 1
    assert keys.index("workflow") == keys.index("steps") - 1
    html = dict((k, h) for k, h in getting_started_sections() if k)
    assert "runs/" in html["workflow"]          # the folder-tag explanation
    from core.resource_path import resource_path
    from pathlib import Path
    from PyQt6.QtSvg import QSvgRenderer
    # One diagram per language (scripts/make_workflow_diagram.py), English
    # as the fallback — every catalogue language must have its file, valid
    # and translated (spot-checked: no untranslated tab label left behind).
    langs = ["en", "de", "es", "fr", "it", "ja", "nl", "no", "pl", "pt",
             "ru", "sv", "zh_CN"]
    for lang in langs:
        svg = Path(resource_path(f"assets/help/workflow/{lang}.svg"))
        assert svg.is_file() and svg.stat().st_size > 10_000, lang
        assert QSvgRenderer(str(svg)).isValid(), lang
    de = Path(resource_path("assets/help/workflow/de.svg")).read_text()
    assert "erstellen" in de and ">Create <" not in de
    assert "runs/" in de                     # folder names stay literal
    assert "Legende:" in de                  # the truncated legend, repaired
    en = Path(resource_path("assets/help/workflow/en.svg")).read_text()
    assert "Legend:" in en and "&#x2026;" not in en
