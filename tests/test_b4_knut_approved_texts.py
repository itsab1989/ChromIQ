"""4.3.5 beta 4: the texts Knut approved on 2026-10-13 are live.

Knut, #182 6152691121: "All messages/descriptions are accepted" for the eight
texts of the beta 3 post. Each is approved in the catalogue, shown where the
post said it would be, and the two proposals that text 6 merged are gone.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import measurement_messages as M     # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LANGS = sorted(p.stem for p in (ROOT / "data" / "i18n").glob("*.json"))

APPROVED_BY_KNUT = (
    "M-HELP-COLOUR-VIEW-LEGEND", "M-HELP-COLOUR-VIEW-SEAMS",
    "M-CHART-STRIP-LABELS-CROWDED", "M-PRINT-DIALOG-COLOUR-MATCHING",
    "M-PRINT-PS-ASK-EXPLAINED", "M-PRINT-PS-FORM-CHOICE-EXPLAINED",
    "M-PRINT-PS-FORM-HELP-PROJECT-EXPLAINED", "M-PRINT-PS-FORM-APPLIES-PROJECT",
    "M-PRINT-DIRECT-LIKE-PREVIEW", "M-GAMUT-NO-PROFILE",
)


@pytest.mark.parametrize("mid", APPROVED_BY_KNUT)
def test_each_text_is_approved(mid):
    assert M.CATALOGUE[mid].approved, mid
    assert mid not in M.PROPOSED


def test_the_two_merged_proposals_are_gone():
    for gone in ("M-PRINT-PS-FORM-HELP-EXPLAINED", "M-PRINT-PS-FORM-HELP-PROJECT"):
        assert gone not in M.CATALOGUE
    spec = (ROOT / "docs/design/unified_measurement_management.md").read_text("utf-8")
    for gone in ("M-PRINT-PS-FORM-HELP-EXPLAINED", "M-PRINT-PS-FORM-HELP-PROJECT"):
        assert f"### SUPERSEDED 2026-10-13, never approved as such: {gone} ·" in spec


def test_the_merged_help_is_text_6():
    """The project rule first, then the explained choices and the RGB line."""
    paras = M.M_PRINT_PS_FORM_HELP_PROJECT_EXPLAINED.body.split("\n\n")
    assert M.M_PRINT_PS_FORM_HELP_PROJECT_EXPLAINED.title == \
        "Choose the way you print your photos"
    assert paras[0].endswith("The project’s choice stays as it is.")
    assert "The way chosen at the project’s first print" in paras[0]
    assert [p.split(":")[0] for p in paras[1:3]] == [
        "Send the colours unchanged", "Let the printer adjust the colours"]
    assert paras[2].endswith(
        "This only works while no profile is set for the printer in ColorSync Utility.")
    assert paras[3].startswith("If the print dialog has an RGB colour setting")


def test_the_direct_route_question_is_text_7():
    title, body = M.M_PRINT_DIRECT_LIKE_PREVIEW.render()
    assert title == "This run lets the printer adjust the colours"
    assert body == ("ChromIQ’s own route can only send the colours unchanged. "
                    "Print through the macOS print dialog instead, or print anyway?")
    # buttons unchanged
    assert M._PRINT_LIKE_PREVIEW_BTN_DIALOG == "Use the print dialog"
    assert M._PRINT_LIKE_PREVIEW_BTN_ANYWAY == "Print anyway"


@pytest.mark.parametrize("code", LANGS)
def test_every_language_has_the_merged_help_and_the_renamed_question(code):
    cat = json.loads((ROOT / "data" / "i18n" / f"{code}.json").read_text("utf-8"))
    for m in (M.M_PRINT_PS_FORM_HELP_PROJECT_EXPLAINED, M.M_PRINT_DIRECT_LIKE_PREVIEW):
        assert cat.get(m.body), (code, m.id)
        assert cat.get(m.title), (code, m.id)
    merged = cat[M.M_PRINT_PS_FORM_HELP_PROJECT_EXPLAINED.body].split("\n\n")
    assert len(merged) == 4
    # the second and third paragraphs open with the choices as translated
    choice = cat[M.M_PRINT_PS_FORM_CHOICE_EXPLAINED.body].split("\n")
    for para, ch in zip(merged[1:3], choice):
        stem = ch.split(" (")[0].split("（")[0]
        assert para.startswith(stem[:6]), (code, para[:40], stem)


def test_the_help_card_names_the_choices_as_the_tab_shows_them():
    from ui.dialogs import welcome_dialog as W
    label, a, b = W._ps_choice_labels()
    head, lines = M.M_PRINT_PS_FORM_CHOICE_EXPLAINED.render()
    assert (label, a, b) == (head, *lines.split("\n"))
