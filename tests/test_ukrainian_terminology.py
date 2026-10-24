"""Words the Ukrainian review of 4.3.12 took out, so they do not come back.

The Ukrainian catalogue started as a machine translation, and some of its
words had the wrong sense altogether: a spacer was a "прокладка" (a gasket),
Lab was "Лабораторія" (a laboratory), a summary was "Резюме" (a CV), a soft
proof was "Доказ" (evidence in court), a device-link was "посилання" (a web
link). Each was replaced in every string, and the replacements are recorded
in the review's glossary. This test fails if one of the old words is written
again, in `uk.json` or in `parameters.uk.yaml`, and names the agreed word.

Only words with no correct use in ChromIQ's texts are listed. A word that is
right in one place and wrong in another (кошик is the Windows Recycle Bin, but
not the macOS Trash) is not policed here; that is a matter for review.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

I18N = Path(__file__).resolve().parent.parent / "data" / "i18n"

#: old word (a regular expression, matched case-insensitively) -> the agreed one
_REPLACED = {
    r"\bпроклад": "роздільник (spacer)",
    r"\bрозпір": "роздільник (spacer)",
    r"лабораторі": "Lab (the colour space keeps its name)",
    r"\bрезюме\b": "підсумок (summary)",
    r"\bдоказ\w* іншого пристрою": "проба іншого пристрою (proof another device)",
    r"перцептуал": "перцептивний (perceptual)",
    r"багатослівн": "докладний вивід (verbose)",
    r"маджент": "пурпуровий (magenta)",
    r"уподобан": "Налаштування (Preferences)",
    r"рамк\w* кліпу": "поле затискача (clip border)",
    r"чорне поколінн": "генерація чорного (black generation)",
    r"\bбілизн": "білість паперу (paper white)",
    r"посиланн\w* на пристрій": "device-link",
    r"\bрафінуван": "уточнення (refinement)",
    r"\bпробіжк": "запуск (run)",
    r"\bшукач\b": "Finder (a name, not translated)",
}


def _texts():
    cat = json.loads((I18N / "uk.json").read_text(encoding="utf-8"))
    for key, value in cat.items():
        if key == "@plurals":
            for pkey, forms in value.items():
                for form, text in forms.items():
                    if form != "count":
                        yield f"uk.json @plurals {pkey[:50]!r} [{form}]", text
        elif not key.startswith("@"):
            yield f"uk.json {key[:50]!r}", value
    params = yaml.safe_load(
        (I18N / "parameters.uk.yaml").read_text(encoding="utf-8"))
    for tool, flags in params["parameters"].items():
        for flag, fields in flags.items():
            for field, text in fields.items():
                for t in (text if isinstance(text, list) else [text]):
                    yield f"parameters.uk.yaml {tool} {flag} {field}", t


def test_no_replaced_word_is_back():
    bad = []
    for where, text in _texts():
        for pattern, agreed in _REPLACED.items():
            if re.search(pattern, str(text), re.I):
                bad.append(f"{where}: use {agreed}")
    assert not bad, (
        f"{len(bad)} Ukrainian text(s) use a word the 4.3.12 review replaced:"
        "\n  " + "\n  ".join(bad[:10]))


def test_the_check_still_sees_an_old_word():
    """A pattern list that matches nothing proves nothing; check it bites."""
    hits = [p for p in _REPLACED
            if re.search(p, "Масштаб прокладок", re.I)]
    assert hits == [r"\bпроклад"]
