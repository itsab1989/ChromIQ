"""Knut, #182 6123740349 and 6123470301 (4.3.5 beta 2).

1. Six help cards carry FOLDABLE details on how to print the chart on the
   Print Chart tab and why it must be printed that way, per situation.
2. The fold is reachable by keyboard and tells VoiceOver whether it is open.
3. Every new text is in all 13 catalogues.
4. The Calibration Complete windows of the two instruments with no reading
   board (CR30, ColorMunki / i1Studio) gain M-CAL-DONE-UNDERLAY (approved by
   Basti 2026-10-13), which never reaches an i1Pro.
"""
from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt  # noqa: E402

from ui.dialogs import welcome_dialog as W  # noqa: E402

_I18N = Path(__file__).resolve().parent.parent / "data" / "i18n"
_LANGS = ("de", "es", "fr", "it", "ja", "nl", "no", "pl", "pt", "ru", "sv",
          "uk", "zh_CN")

def _approved_module():
    """welcome_dialog as it ships: the print notes are approved (Knut and
    Basti, 2026-10-13, shown since 4.3.5 beta 3)."""
    assert W.PRINT_NOTES_APPROVED is True
    return W


#: The cards Knut named, and the note headings their print steps must carry.
_PROFILING = {W._print_how_note()[0], W._print_raw_note()[0],
              W._route_note()[0], W._printer_kinds_note()[0],
              W._postscript_note()[0], W._cmyk_driver_note()[0]}
_CARDS = {
    "first_profile": _PROFILING | {W._profiling_or_verification_note()[0],
                                   W._inks_note()[0]},
    "two_pass": _PROFILING | {W._precond_note()[0]},
    "improve_existing_profile": _PROFILING | {W._precond_note()[0]},
    "print_chart": _PROFILING | {W._profiling_or_verification_note()[0],
                                 W._inks_note()[0]},
    "verify": {W._print_how_note()[0], W._verify_sources_note()[0],
               W._verify_same_way_note()[0], W._verify_elsewhere_note()[0],
               W._printer_kinds_note()[0], W._postscript_note()[0],
               W._cmyk_driver_note()[0]},
    "printer_from_scan": _PROFILING | {W._scanner_cases_note()[0]},
}

_NOTE_FUNCS = (W._print_how_note, W._print_raw_note, W._precond_note,
               W._profiling_or_verification_note, W._route_note,
               W._printer_kinds_note, W._postscript_note, W._cmyk_driver_note,
               W._inks_note, W._verify_sources_note,
               W._verify_same_way_note, W._verify_elsewhere_note,
               W._scanner_cases_note)


def _print_step_notes(key: str, mod=None) -> "set[str]":
    """Headings of every note under the card's print steps (tab 2)."""
    wf = next(w for w in (mod or W).WORKFLOWS if w["key"] == key)
    out: set[str] = set()
    for step in wf["steps"]:
        if step[0] == 2 and len(step) > 3:
            out |= {h for h, _b in step[3]}
    return out


@pytest.mark.parametrize("key", sorted(_CARDS))
def test_every_named_card_explains_printing_in_folded_notes(key):
    missing = _CARDS[key] - _print_step_notes(key, _approved_module())
    assert not missing, f"{key}: no note {sorted(missing)}"


@pytest.mark.parametrize("key", sorted(_CARDS))
def test_the_approved_notes_are_shown(key):
    """Knut and Basti approved the notes on 2026-10-13: every card shows its
    own, and only the notes its print step needs are folded under it."""
    assert W.PRINT_NOTES_APPROVED is True
    shown = _print_step_notes(key)
    assert _CARDS[key] <= shown, sorted(_CARDS[key] - shown)


def test_the_notes_say_what_the_code_does():
    """Spot checks against the code of this branch, so a later change of
    behaviour cannot leave the cards telling the old story unnoticed."""
    from core import settings as S
    from workflow import measurement_messages as MM
    from workflow import verification_print as vp
    # the macOS print dialog is the default on a Mac (combined review of beta 2)
    assert S.DEFAULTS["use_native_print_dialog"] is (S.is_windows() or S.is_macos())
    route = W._route_note()[1]
    assert "clicking Print opens the macOS print dialog" in route
    assert "switch off" in route
    # every chart that is not RGB is refused by the dialog, not only 5 to 7 inks
    inks = W._inks_note()[1]
    assert "refuses these charts" in inks and "five to seven" not in inks
    verify = W._verify_sources_note()[1]
    assert vp.default_colour_for_run(None) == vp.COLOUR_THROUGH
    assert "the default" in verify
    kinds = W._printer_kinds_note()[1]
    for word in ("Canon", "PostScript", "CMYK"):
        assert word in kinds
    # the PostScript note names the row and both choices as the tab shows them
    label, lines = MM.M_PRINT_PS_FORM_CHOICE.render()
    ps = W._postscript_note()[1]
    assert label in ps
    for choice in lines.split("\n"):
        assert choice in ps
    assert "Preview" in W._cmyk_driver_note()[1]
    reach = next(n for s in next(w for w in W.WORKFLOWS
                                 if w["key"] == "print_chart")["steps"]
                 if len(s) > 3 for n in s[3]
                 if n[0] == "How the sheet reaches the printer")[1]
    assert "raw PostScript" not in reach


def test_no_note_leaves_a_placeholder_or_an_em_dash():
    for f in _NOTE_FUNCS:
        head, body = f()
        assert "{" not in head + body, f.__name__
        assert "—" not in head + body, f.__name__


def _new_keys() -> "list[str]":
    """The English keys of every new text, as tr() looks them up."""
    import ast
    import inspect
    keys: list[str] = []
    for f in _NOTE_FUNCS:
        tree = ast.parse(inspect.getsource(f))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "tr" and node.args
                    and isinstance(node.args[0], ast.Constant)):
                keys.append(node.args[0].value)
    from workflow import measurement_messages as M
    keys += [W._NOTE_A11Y_CLOSED, W._NOTE_A11Y_OPEN,
             M.M_CAL_DONE_UNDERLAY.title, M.M_CAL_DONE_UNDERLAY.body]
    return keys


@pytest.mark.parametrize("lang", _LANGS)
def test_every_new_text_is_translated(lang):
    cat = json.loads((_I18N / f"{lang}.json").read_text(encoding="utf-8"))
    keys = _new_keys()
    assert len(keys) >= 26
    untranslated = [k[:50] for k in keys if not cat.get(k) or cat[k] == k]
    assert not untranslated, untranslated


# ---- the fold ---------------------------------------------------------------
def test_the_fold_is_closed_reachable_by_tab_and_speaks_its_state(qapp):
    note = W.StepNote("Heading", "Body text")
    btn = note.findChild(type(note._btn), "welcome_note_head")
    assert btn is not None
    assert not note.is_open() and note._body.isHidden()
    assert btn.focusPolicy() == Qt.FocusPolicy.StrongFocus
    assert btn.accessibleName() == "Heading"          # no ▶ glyph read out
    closed = btn.accessibleDescription()
    btn.click()
    assert note.is_open() and not note._body.isHidden()
    assert btn.accessibleDescription() != closed
    btn.click()
    assert not note.is_open() and btn.accessibleDescription() == closed


def test_space_opens_the_fold(qapp):
    from PyQt6.QtTest import QTest
    note = W.StepNote("Heading", "Body text")
    note.show()
    note._btn.setFocus()
    QTest.keyClick(note._btn, Qt.Key.Key_Space)
    assert note.is_open()
    note.close()


def test_the_cards_print_their_new_notes(qapp):
    from ui.help_card_print import card_html
    wf = next(w for w in _approved_module().WORKFLOWS if w["key"] == "verify")
    html = card_html(wf)
    assert "Where the chart" in html
    assert "Print it the way its profiling chart was printed" in html


# ---- M-CAL-DONE-UNDERLAY ------------------------------------------------------
def test_the_underlay_tip_is_approved_and_shown_only_without_a_board():
    """Basti, 2026-10-13: approved as the combined review wrote it. MUTATION:
    leave it unapproved and the CR30 / ColorMunki windows lose the paragraph;
    drop the family check and an i1Pro gets it, whose board is white."""
    from ui.ti2_loader import underlay_tip_html
    from workflow import measurement_messages as M
    assert M.M_CAL_DONE_UNDERLAY.approved
    assert M.M_CAL_DONE_UNDERLAY.title == "Lay the chart on a white surface"
    assert M.M_CAL_DONE_UNDERLAY.body.startswith(
        "Before you measure, lay the chart on a white, even surface")
    for fam in ("colormunki", "cr30"):
        tip = underlay_tip_html(fam)
        assert "Lay the chart on a white surface" in tip
        assert "80 to 100 g/m²" in tip
    for fam in ("i1pro", "spectroscan", None):
        assert underlay_tip_html(fam) == ""


def test_the_underlay_tip_is_hidden_while_unapproved(monkeypatch):
    from ui import ti2_loader
    from workflow import measurement_messages as M
    monkeypatch.setattr(M, "M_CAL_DONE_UNDERLAY",
                        dataclasses.replace(M.M_CAL_DONE_UNDERLAY,
                                            approved=False))
    for fam in ("colormunki", "cr30", "i1pro", "spectroscan", None):
        assert ti2_loader.underlay_tip_html(fam) == ""


def test_both_windows_append_the_tip():
    import inspect
    from ui.tabs import tab_measure
    src = inspect.getsource(tab_measure.TabMeasure._on_calibration_done)
    assert "underlay_tip_html(_fam)" in src
    src = inspect.getsource(tab_measure.TabMeasure._show_cr30_measuring_window)
    assert 'underlay_tip_html("cr30")' in src
