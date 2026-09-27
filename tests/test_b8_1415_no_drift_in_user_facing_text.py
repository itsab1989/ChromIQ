"""B8-1415: no text a user reads says "drift", in English or in German.

Knut, #182 5849392788: *"The word drift is not used at all ... Use the word
"Change" instead of "Drift"."* K59 applied that to the Measurement Report and
its help, B8-1396 to Create Chart's FROM PROFILE GAMUT help. Sixteen texts
elsewhere still said it: "Inspect a measurement" ("how far the greys drifted
away from truly neutral", "Inks and paper can drift over time"), the Getting
Started card ("printheads drift"), the grey-balance generator's help ("where a
printer drifts first"), the Accuracy, black-generation, out-of-gamut and
calibration helps, the placement-agreement and strip-outlier helps, the -S and
-N texts, "Verify against reference" and its 3D map, "Reset grid", and three
tooltips in `data/parameters.yaml` (-m, -r, -T). They now say "change",
"changed", "moved away from", "slid" or "slipped", whichever is the meaning.

This test holds the rule over EVERY surface a user reads, not over those
sixteen: the `tr()` literals and the §M catalogue and the parameter texts the
em-dash rule already collects (`scripts/em_dash_check.py::english_strings`),
the help texts `core/measure_windows.py` hands to `tr()` through `_esc()` (which
`i18n_extract` cannot see, so they are not in any catalogue), the German
catalogue's values and the German parameter overlay.

NOT covered, on purpose, and none of it is user-facing text: code comments and
docstrings, identifiers (`raw_drift`, `seating_drift`, the `chromiq_drift_`
temp-file prefix), and the diagnostic log lines of the scan placement
(`workflow/scan_auto_align.py`, `workflow/scan_placement.py`,
`workflow/hex_block_search.py`, `ui/dialogs/scanin_dialog.py`), which go to
the application log in English and never through `tr()`. The other twelve
languages are held by B8-1472 below, each by ITS word for drift: "drift" is
an ordinary word in Dutch, Norwegian and Swedish ("operation"), so the
English substring rule would be wrong there.

An exception, if one is ever needed (ArgyllCMS's own words quoted to the user,
say), goes into `ALLOWED` with the reason. There is none today.

Mutations (each run red): M1415-a "drifted" back into the "Inspect a
measurement" cast help; M1415-b "driften" back into a German value; M1415-c
"drift" back into the -r tooltip in `data/parameters.yaml`; M1415-d
"Drift-Artefakte" back into the German overlay; M1415-e "drifted" back into
the measurement-windows help (`_esc`); M1415-f the German of the cast help
left on the old key.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import em_dash_check as E                                        # noqa: E402

DRIFT = re.compile(r"drift", re.IGNORECASE)

#: {exact text: why it may say drift}. Empty: nothing a user reads needs it.
ALLOWED: "dict[str, str]" = {}

#: The call names whose first literal argument is user-facing English. `tr`
#: is what `i18n_extract` sweeps already; `_esc` is `core/measure_windows.py`'s
#: `html.escape(tr(text))`, which it does not.
_WRAPPERS = {"tr", "_esc"}


def _excerpt(s: str, n: int = 100) -> str:
    m = DRIFT.search(s)
    start = max(0, (m.start() if m else 0) - 50)
    flat = " ".join(s[start:start + n].split())
    return ("…" if start else "") + flat + "…"


def _wrapped_literals() -> "dict[str, str]":
    out: dict[str, str] = {}
    files = [ROOT / "main.py"]
    for d in ("ui", "core", "workflow"):
        files += sorted((ROOT / d).rglob("*.py"))
    for f in files:
        if "__pycache__" in f.parts:
            continue
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in _WRAPPERS and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                out.setdefault(node.args[0].value,
                               f"{f.relative_to(ROOT)}:{node.lineno}")
    return out


def english_texts() -> "dict[str, str]":
    texts = dict(E.english_strings())
    for s, where in _wrapped_literals().items():
        texts.setdefault(s, where)
    return texts


def _yaml_texts(path: Path) -> "list[tuple[str, str]]":
    out = []

    def walk(node, where):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{where}/{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{where}[{i}]")
        elif isinstance(node, str):
            out.append((node, where))

    walk(yaml.safe_load(path.read_text(encoding="utf-8")), path.name)
    return out


def german_texts() -> "dict[str, str]":
    de = json.loads((ROOT / "data/i18n/de.json").read_text(encoding="utf-8"))
    texts = {v: f"de.json value of {k[:50]!r}" for k, v in de.items()
             if not k.startswith("@") and isinstance(v, str)}
    for s, where in _yaml_texts(ROOT / "data/i18n/parameters.de.yaml"):
        texts.setdefault(s, where)
    return texts


def _offenders(texts: "dict[str, str]") -> "list[str]":
    return sorted(f"[{where}] {_excerpt(s)}" for s, where in texts.items()
                  if DRIFT.search(s) and s not in ALLOWED)


def test_no_english_text_a_user_reads_says_drift():
    bad = _offenders(english_texts())
    assert not bad, (
        f"\n{len(bad)} user-facing English text(s) say drift:\n  "
        + "\n  ".join(bad[:15])
        + "\n\nKnut, #182 5849392788: \"The word drift is not used at all\". "
          "Say change / changed, or \"move away from\" where that is the "
          "meaning (B8-1415).")


def test_no_german_text_a_user_reads_says_drift():
    bad = _offenders(german_texts())
    assert not bad, (
        f"\n{len(bad)} German text(s) say Drift or driften:\n  "
        + "\n  ".join(bad[:15])
        + "\n\nSay \"verändern\" / \"Veränderung\", or \"sich entfernen\" "
          "(B8-1415).")


# --- B8-1472: every other language, in its own word for drift ---------------
#
# Challenge 2 of beta 45, F4: the -r tooltip still said "drift-artefacten",
# "drift-artefakter" and "driftartefakter" in the Dutch, Norwegian and Swedish
# overlays, and its Spanish, French, Italian, Portuguese, Polish, Russian,
# Ukrainian, Japanese and Chinese said the same in their own words. A plain
# "drift" substring is wrong outside English and German (Norwegian
# "framdrift" is progress, "bedrift" a company; Spanish "deriva la misma
# referencia" is "derives"), so each language has the pattern of ITS word
# for the drift of a reading, measured over every value of its catalogue and
# every text of its overlay.
_DRIFT_WORD = {
    "nl": r"\bdrift",
    "no": r"\bdrift",
    "sv": r"\bdrift",
    "es": r"\b(?:de|la|una) deriva\b",
    "pt": r"\b(?:de|da|a|uma) deriva\b|\bderivar para\b",
    "it": r"\b(?:da|di|la|una) deriva\b",
    "fr": r"\b(?:de|des|la|une) dérives?\b",
    "pl": r"dryf",
    "ru": r"дрейф",
    "uk": r"дрейф",
    "ja": r"ドリフト",
    "zh_CN": r"漂移",
}


def _language_texts(code: str) -> "dict[str, str]":
    cat = _catalogue(code)
    texts = {v: f"{code}.json value of {k[:50]!r}" for k, v in cat.items()
             if not k.startswith("@") and isinstance(v, str)}
    for s, where in _yaml_texts(ROOT / f"data/i18n/parameters.{code}.yaml"):
        texts.setdefault(s, where)
    return texts


def test_every_language_has_a_drift_word():
    """A language added later must name its word, or say why it has none."""
    codes = {p.stem for p in (ROOT / "data/i18n").glob("*.json")}
    assert codes - {"en", "de"} <= set(_DRIFT_WORD), sorted(
        codes - {"en", "de"} - set(_DRIFT_WORD))


@pytest.mark.parametrize("code", sorted(_DRIFT_WORD))
def test_no_translation_says_drift_in_its_own_word(code):
    rx = re.compile(_DRIFT_WORD[code], re.IGNORECASE)
    bad = sorted(f"[{where}] {' '.join(s[max(0, m.start() - 50):m.end() + 50].split())}"
                 for s, where in _language_texts(code).items()
                 for m in [rx.search(s)] if m)
    assert not bad, (f"\n{len(bad)} {code} text(s) say drift:\n  "
                     + "\n  ".join(bad[:15]))


def test_the_r_tooltip_says_what_the_english_says_in_every_language():
    """The text F4 found: no overlay keeps the old drift sentence, and each
    carries a translation of "readings that change slowly during a
    measurement" (or the English)."""
    slow = {"nl": "langzaam", "no": "langsomt", "sv": "långsamt",
            "es": "lentamente", "fr": "lentement", "it": "lentamente",
            "pt": "lentamente", "pl": "powoli", "ru": "медленно",
            "uk": "повільно", "ja": "ゆっくり", "zh_CN": "缓慢",
            "de": "langsam"}
    for code, word in slow.items():
        doc = yaml.safe_load((ROOT / f"data/i18n/parameters.{code}.yaml")
                             .read_text(encoding="utf-8"))
        body = doc["parameters"]["printtarg"]["-r"]["tooltip_body"]
        assert word in body or "change slowly" in body, (code, body[:160])


def test_the_collector_sees_the_surfaces_it_claims():
    """A rule over a surface its collector cannot see is not enforced. Each
    surface this file names contributes a text we know is there."""
    en = english_texts()
    assert any(s.startswith("On average, how far the greys moved away from "
                            "truly neutral") for s in en), "tr() literals"
    assert any("whose instrument slid off the strip" in s for s in en), \
        "the measurement-windows help (core/measure_windows.py)"
    assert any("randomises patch positions" in s for s in en), \
        "data/parameters.yaml"
    de = german_texts()
    assert any("von echt neutral entfernt haben" in s for s in de), \
        "de.json values"
    assert any("Feldpositionen" in s for s in de), "parameters.de.yaml"


def test_every_allowed_drift_says_why_and_still_exists():
    en, de = english_texts(), german_texts()
    for text, reason in ALLOWED.items():
        assert isinstance(reason, str) and len(reason.strip()) >= 25, text
        assert text in en or text in de, f"stale allowance: {text[:60]!r}"


# --- the texts B8-1415 names, and their German ------------------------------

_NAMED = {
    "cast": ("On average, how far the greys moved away from truly neutral",
             "von echt neutral entfernt haben"),
    "measured_on": ("When the chart was read. Inks and paper can change over "
                    "time", "mit der Zeit verändern"),
    "getting_started": ("Ink ages, paper batches differ, printheads change. A "
                        "check tells you", "Druckköpfe verändern sich. Eine "
                        "Prüfung sagt dir"),
    "grey_balance": ("where a printer's output changes first",
                     "dort verändert sich das Ergebnis eines Druckers zuerst"),
}


def _catalogue(code: str) -> dict:
    return json.loads((ROOT / f"data/i18n/{code}.json").read_text(
        encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(_NAMED))
def test_the_named_text_says_change_and_german_is_by_hand(name):
    english_part, german_part = _NAMED[name]
    en = [s for s in english_texts() if english_part in s]
    assert len(en) == 1, f"{name}: {len(en)} texts carry {english_part!r}"
    text = en[0]
    assert "—" not in text, f"{name}: the English carries an em dash"
    de = _catalogue("de")
    assert text in de, f"{name}: no German for the new key"
    assert de[text] != text, f"{name}: the German carries the English"
    assert german_part in de[text], f"{name}: {de[text][:120]!r}"
    assert "—" not in de[text], f"{name}: the German carries an em dash"
    for path in sorted((ROOT / "data/i18n").glob("*.json")):
        assert text in _catalogue(path.stem), f"{path.name}: {name} missing"
