"""Beta 17: the Print Chart help explains what a Canon does on plain paper.

Basti approved the paragraph on 2026-10-09 (drafted in the plain-paper
study, ~/Desktop/ChromIQ-work/2026-10-09_plain_paper_apps/REPORT.md, after
every measured macOS app put the PRO-300 on plain paper into the same printer
state). It stands right after the paragraph that explains the paper types,
on both macOS routes, in every language.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ui.tabs import tab_print as tp

ROOT = Path(__file__).resolve().parent.parent
APPROVED = (
    "On plain paper the Canon driver always uses its own colour processing, "
    "whatever program prints. ChromIQ prints the chart the same way. The "
    "profile therefore fits prints from Photoshop (\"Photoshop manages "
    "colours\"), Preview and other programs where you choose this profile in "
    "the colour settings, as long as you pick Plain Paper and the same print "
    "quality there.")


def test_the_words_are_the_approved_ones():
    assert tp._TT_PLAIN_PAPER == APPROVED


@pytest.mark.parametrize("body", [tp._TT_BODY_PRINT_MACOS_BYPASS,
                                  tp._TT_BODY_PRINT_MACOS_NATIVE])
def test_it_follows_the_paper_type_paragraph(body):
    paras = tp._with_plain_paper(body).split("\n\n")
    i = paras.index(APPROVED)
    assert "paper" in paras[i - 1].lower()
    assert i == 2


def test_the_macos_help_shows_it(qapp, monkeypatch):
    monkeypatch.setattr(tp, "is_windows", lambda: False)
    monkeypatch.setattr(tp, "is_linux", lambda: False)
    monkeypatch.setattr(tp, "is_macos", lambda: True)

    class _Fake:
        _settings = {"use_native_print_dialog": False}
    for native in (False, True):
        _Fake._settings = {"use_native_print_dialog": native}
        _t, body = tp.TabPrint._compute_print_tooltip(_Fake)
        assert APPROVED in body


@pytest.mark.parametrize("code", ["de", "es", "fr", "it", "ja", "nl", "no",
                                  "pl", "pt", "ru", "sv", "uk", "zh_CN"])
def test_it_is_translated(code):
    cat = json.loads((ROOT / "data" / "i18n" / f"{code}.json").read_text(
        encoding="utf-8"))
    assert cat[APPROVED] and cat[APPROVED] != APPROVED
    assert "Canon" in cat[APPROVED] and "Photoshop" in cat[APPROVED]
