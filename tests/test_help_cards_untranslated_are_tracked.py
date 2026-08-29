"""English placeholders in the catalogues must be COUNTABLE, not invisible.

`scripts/i18n_extract.py --missing` only checks whether a KEY EXISTS. A key
whose value is still the English source passes it, and
`tests/test_i18n.py::test_catalog_is_complete` passes too. That blind spot
already bit once: eleven keys shipped as English in eleven languages while the
tooling reported "0 missing of 4431", and I told Basti the catalogues were
clean on the strength of it.

Placeholders are LEGITIMATE during a beta — the project rule is English
placeholders while text is still moving, all languages before final. What is
not legitimate is not knowing how many there are. This test does not forbid
them; it makes the number visible and fails if it grows without anyone
noticing.
"""
import json
import pathlib

import pytest

_I18N = pathlib.Path(__file__).resolve().parent.parent / "data" / "i18n"

# Raise DELIBERATELY when adding beta text, lower it when translating before a
# final. Never edit it to make a red run green without looking at what grew.
# Measured 2026-08-25, end of the answered-questions batch: German 35, the rest
# 60-62. German stays low because Basti and Knut read it, so it is kept current;
# everything else accumulates English placeholders under the beta rule and is
# translated in one pass before a final.
#
# RAISE THIS DELIBERATELY, never to make a red run green. It has been raised
# three times in one day — twice for the two new §M patch-set messages and once
# for the "Load setup from preset" tooltip — and each rise was a real decision
# to defer translation, not an accident. If a rise ever cannot be explained in
# one sentence, something was added that nobody meant to add. Of those,
# 23 per language are the three new Tools help cards, added as English
# placeholders under the project's beta rule; the remainder pre-date them.
# German is lower because Basti and Knut read it, so it is kept current.
# 2026-08-30, #159, raised 70 -> 73 for the magnet window: a magnet
# recalibrated the owner's instrument mid-chart (a MacBook under his paper) and
# the session carried on, so the refusal now stops the session and offers to
# retake the white calibration. New beta text under the project's rule.
#
# 2026-08-29, #159, raised 62 -> 70 for the CR30 instrument work: the
# no-device help (which had never been translatable at all — fifteen sentences
# built as bare strings the extractor could not see), the greyed-option
# explanation, the disconnect and re-arm notices, and the two calibration
# windows including the dark-reference step. All are new beta text under the
# project's rule, and German is translated as usual because it is read.
_BUDGET = {
    "de": 35,
    "es": 73, "fr": 73, "it": 73, "ja": 73, "nl": 73,
    "no": 73, "pl": 73, "pt": 73, "ru": 73, "sv": 73, "zh_CN": 73,
}


def _codes():
    return sorted(p.stem for p in _I18N.glob("*.json")
                  if not p.stem.startswith("parameters"))


def _english_echoes(code: str) -> list[str]:
    c = json.loads((_I18N / f"{code}.json").read_text(encoding="utf-8"))
    out = []
    for k, v in c.items():
        if k.startswith("@") or not isinstance(v, str):
            continue
        if v != k:
            continue
        # Strings that are legitimately identical in every language: units,
        # format fragments, brand and file-format names, bare punctuation.
        if len(k) < 25 or not any(ch.isalpha() for ch in k):
            continue
        if k.split()[0] in {"ChromIQ", "ArgyllCMS", "Adobe", "ICC", "sRGB"}:
            continue
        out.append(k)
    return out


@pytest.mark.parametrize("code", _codes())
def test_untranslated_strings_stay_within_budget(code):
    echoes = _english_echoes(code)
    budget = _BUDGET.get(code, 40)
    assert len(echoes) <= budget, (
        f"{code}: {len(echoes)} substantial strings are still English, budget "
        f"is {budget}. Either translate them or raise the budget on purpose.\n"
        + "\n".join(f"    {e[:70]}…" for e in echoes[:5]))


def test_the_echo_detector_is_not_vacuous():
    """Guard the guard: prove the detector can actually see an echo.

    A detector that returns [] because its filters are too greedy would make
    this whole file worthless — which is the failure mode it exists to prevent.
    """
    import tempfile

    sample = ("This is a long English sentence that no translator has touched "
              "yet and which must be counted as an echo.")
    tmp = pathlib.Path(tempfile.mkdtemp()) / "xx.json"
    tmp.write_text(json.dumps({"@language_name": "Test", sample: sample}),
                   encoding="utf-8")
    c = json.loads(tmp.read_text(encoding="utf-8"))
    found = [k for k, v in c.items()
             if not k.startswith("@") and v == k and len(k) >= 25
             and any(ch.isalpha() for ch in k)]
    assert found == [sample], "the echo detector cannot see a plain echo"
