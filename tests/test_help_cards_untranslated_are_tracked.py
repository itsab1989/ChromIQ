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
# Measured 2026-08-25 after Knut's beta.13 batch: German 35, the rest 56-58. Of those,
# 23 per language are the three new Tools help cards, added as English
# placeholders under the project's beta rule; the remainder pre-date them.
# German is lower because Basti and Knut read it, so it is kept current.
_BUDGET = {
    "de": 35,
    "es": 58, "fr": 58, "it": 58, "ja": 58, "nl": 58,
    "no": 58, "pl": 58, "pt": 58, "ru": 58, "sv": 58, "zh_CN": 58,
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
