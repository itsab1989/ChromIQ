"""Beta 12: Japanese and Simplified Chinese named the pre-conditioning profile
two ways at once.

The Create Chart field said 前処理プロファイル / 预处理配置文件 while the
button beside it, the parameter overlay (targen -c) and the beta-11 texts said
プレコンディショニング / 预调节. One concept, one word: the term the rest of
each catalogue and the ArgyllCMS parameter overlay already used is kept.

The rejected words still have a legitimate use for a different idea (the input
shaper's generic "pre-processing step", a "no conversion needed" note), so the
check is scoped to strings whose English source is about pre-conditioning.
"""
import json
import re
from pathlib import Path

import pytest

I18N = Path(__file__).resolve().parent.parent / "data" / "i18n"

# language -> (kept term, rejected term)
TERMS = {
    "ja": ("プレコンディショニング", "前処理"),
    "zh_CN": ("预调节", "预处理"),
}

_ABOUT_PRECONDITIONING = re.compile(r"pre-?conditioning", re.I)


def _preconditioning_entries(lang):
    cat = json.loads((I18N / f"{lang}.json").read_text(encoding="utf-8"))
    for key, value in cat.items():
        if key.startswith("@") or not isinstance(value, str):
            continue
        # The input shaper's "pre-conditioning step" is generic pre-processing,
        # not the profile; it keeps its own word.
        if "shaper" in key:
            continue
        if _ABOUT_PRECONDITIONING.search(key):
            yield key, value


@pytest.mark.parametrize("lang", sorted(TERMS))
def test_no_preconditioning_string_uses_the_rejected_term(lang):
    kept, rejected = TERMS[lang]
    offenders = [k[:70] for k, v in _preconditioning_entries(lang) if rejected in v]
    assert not offenders, (
        f"{lang}: these pre-conditioning strings say {rejected!r}; "
        f"the catalogue's term is {kept!r}: {offenders}"
    )


@pytest.mark.parametrize("lang", sorted(TERMS))
def test_the_field_and_the_button_use_the_same_word(lang):
    kept, _ = TERMS[lang]
    cat = json.loads((I18N / f"{lang}.json").read_text(encoding="utf-8"))
    for key in (
        "Preconditioning profile",
        "Preconditioning profile (optional):",
        "Choose preconditioning profile",
        "Select pre-conditioning profile",
        "Use as pre-conditioning profile",
        "← Use as Pre-conditioning",
    ):
        assert kept in cat[key], (lang, key, cat[key])


@pytest.mark.parametrize("lang", sorted(TERMS))
def test_the_parameter_overlay_agrees(lang):
    kept, rejected = TERMS[lang]
    text = (I18N / f"parameters.{lang}.yaml").read_text(encoding="utf-8")
    assert kept in text
    # The overlay's only use of the rejected word is the input shaper line.
    for line in text.splitlines():
        if rejected in line:
            assert "cLUT" in line, line
