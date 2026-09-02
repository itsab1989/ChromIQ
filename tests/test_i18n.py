"""Language support: catalog loading, fallback, overlay merge, hygiene.

The German catalog itself is also validated here (completeness against
the tr() call sites, placeholder integrity, parameters overlay coverage)
so a future string change that forgets the translation fails CI instead
of silently showing mixed-language UI.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

from core import i18n

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from i18n_extract import extract_keys  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_language():
    # i18n state is module-global — never leak a language into other tests.
    yield
    i18n.set_language("en")


# ----------------------------------------------------------------------
# Core behaviour
# ----------------------------------------------------------------------

def test_english_is_passthrough():
    i18n.set_language("en")
    assert i18n.tr("Build Profile") == "Build Profile"
    assert i18n.current_language() == "en"


def test_german_translates_known_string():
    i18n.set_language("de")
    assert i18n.current_language() == "de"
    assert i18n.tr("Cancel") == "Abbrechen"


def test_unknown_string_falls_through_untranslated():
    i18n.set_language("de")
    assert i18n.tr("zz-not-a-real-source-string") == "zz-not-a-real-source-string"


def test_unknown_language_falls_back_to_english():
    i18n.set_language("xx")
    assert i18n.current_language() == "en"
    assert i18n.tr("Cancel") == "Cancel"


def test_available_languages_lists_english_and_german():
    langs = dict(i18n.available_languages())
    assert langs["en"] == "English"
    assert langs["de"] == "Deutsch"


# ----------------------------------------------------------------------
# German catalog hygiene
# ----------------------------------------------------------------------

def _catalog_codes() -> list[str]:
    return sorted(p.stem for p in (ROOT / "data" / "i18n").glob("*.json"))


def _load_catalog(code: str) -> dict[str, str]:
    with open(ROOT / "data" / "i18n" / f"{code}.json", encoding="utf-8") as f:
        return {k: v for k, v in json.load(f).items() if not k.startswith("@")}


@pytest.mark.parametrize("code", _catalog_codes())
def test_catalog_is_complete(code):
    missing = sorted(extract_keys() - set(_load_catalog(code)))
    assert not missing, f"[{code}] {len(missing)} untranslated, e.g. {missing[:5]}"


@pytest.mark.parametrize("code", _catalog_codes())
def test_catalog_has_no_stale_keys(code):
    stale = sorted(set(_load_catalog(code)) - extract_keys())
    assert not stale, f"[{code}] {len(stale)} stale keys, e.g. {stale[:5]}"


@pytest.mark.parametrize("code", _catalog_codes())
def test_placeholders_match_source(code):
    bad = i18n.check_placeholders(_load_catalog(code))
    assert not bad, f"[{code}] placeholder mismatch in: {bad[:5]}"


@pytest.mark.parametrize("code", _catalog_codes())
def test_short_labels_stay_compact(code):
    """Button/label-sized strings must not balloon in translation
    (clipping). Short English strings are the ones that end up on buttons
    and tab labels; allow modest growth plus a small constant."""
    offenders = []
    for src, dst in _load_catalog(code).items():
        if "\n" in src or len(src) > 24 or "{" in src:
            continue
        if len(dst) > int(len(src) * 1.6) + 6:
            offenders.append((src, dst))
    assert not offenders, f"[{code}] over-long short labels: {offenders}"


# ----------------------------------------------------------------------
# parameters.yaml overlay
# ----------------------------------------------------------------------

def _load_params() -> dict:
    with open(ROOT / "data" / "parameters.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)["parameters"]


def _overlay_codes() -> list[str]:
    return sorted(p.suffixes[0].lstrip(".")
                  for p in (ROOT / "data" / "i18n").glob("parameters.*.yaml"))


@pytest.mark.parametrize("code", _overlay_codes())
def test_parameters_overlay_covers_every_parameter(code):
    overlay = yaml.safe_load(
        (ROOT / "data" / "i18n" / f"parameters.{code}.yaml").read_text(encoding="utf-8")
    )["parameters"]
    problems = []
    for tool, defs in _load_params().items():
        for p in defs:
            entry = overlay.get(tool, {}).get(p["flag"])
            if entry is None:
                problems.append(f"{tool} {p['flag']}: no overlay entry")
                continue
            for field in ("name", "tooltip_title", "tooltip_body"):
                if field in p and field not in entry:
                    problems.append(f"{tool} {p['flag']}: missing {field}")
            if "labels" in p and len(entry.get("labels", [])) != len(p["labels"]):
                problems.append(f"{tool} {p['flag']}: label count mismatch")
    assert not problems, problems


def test_translate_parameters_merges_german():
    i18n.set_language("de")
    params = i18n.translate_parameters(_load_params())
    d = next(p for p in params["targen"] if p["flag"] == "-d")
    assert d["name"] == "Gerätetyp"
    assert len(d["labels"]) == 16


def test_translate_parameters_is_noop_for_english():
    i18n.set_language("en")
    params = _load_params()
    translated = i18n.translate_parameters(params)
    d = next(p for p in translated["targen"] if p["flag"] == "-d")
    assert d["name"] == "Device Type"


def test_label_count_mismatch_keeps_english_labels(tmp_path, monkeypatch):
    """A stale overlay with the wrong number of labels must be ignored
    for that list — labels and choices may never desynchronise."""
    i18n.set_language("de")
    params = {"targen": [{"flag": "-d", "name": "Device Type",
                          "labels": ["a", "b", "c"]}]}
    monkeypatch.setattr(
        i18n, "_load_parameters_overlay",
        lambda code: {"targen": {"-d": {"name": "Gerätetyp",
                                        "labels": ["nur", "zwei"]}}},
    )
    out = i18n.translate_parameters(params)
    assert out["targen"][0]["name"] == "Gerätetyp"
    assert out["targen"][0]["labels"] == ["a", "b", "c"]


def test_qt_fallback_translates_norwegian_buttons(qapp):
    """PyQt6 ships no qtbase_nb.qm — the JSON fallback in data/i18n/qt/
    must still translate Qt's standard dialog buttons for Norwegian."""
    from PyQt6.QtCore import QCoreApplication
    i18n.set_language("no")
    i18n.install_qt_translator(qapp)
    try:
        assert QCoreApplication.translate("QPlatformTheme", "Cancel") == "Avbryt"
        assert QCoreApplication.translate("QPlatformTheme", "Close") == "Lukk"
    finally:
        if i18n._qt_translator is not None:
            qapp.removeTranslator(i18n._qt_translator)
            i18n._qt_translator = None


# ---- the message catalogue is translatable at all ------------------------
def test_the_message_catalogue_reaches_the_translations():
    """The §M catalogue hands its strings to ``tr()`` as ``tr(self.body)`` —
    an attribute, not a literal — so the extractor cannot find them by walking
    the source. It reads them from the module instead.

    Without that the whole catalogue silently dropped out: 4009 keys became
    3966, and every window in the Measurement Management model would have shown
    English in every language while every test stayed green.
    """
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from i18n_extract import extract_keys

    from workflow.measurement_messages import CATALOGUE

    keys = extract_keys()
    for mid, msg in sorted(CATALOGUE.items()):
        assert msg.title in keys, f"{mid}: headline is not translatable"
        assert msg.body in keys, f"{mid}: body is not translatable"
        if msg.body_one:
            assert msg.body_one in keys, f"{mid}: singular body is not translatable"


def test_the_catalogue_is_actually_translated_into_german():
    from core.i18n import tr, set_language
    from workflow.measurement_messages import CATALOGUE

    set_language("de")
    try:
        for mid, msg in sorted(CATALOGUE.items()):
            assert tr(msg.title) != msg.title, f"{mid}: headline still English"
    finally:
        set_language("en")


# ---------------------------------------------------------------------------
# A value that is identical to its key is INVISIBLE to every other check here
# ---------------------------------------------------------------------------
#
# `test_catalog_is_complete` only asks whether the KEY exists, and the
# untranslated-budget test in `test_help_cards_untranslated_are_tracked.py`
# only counts strings of 25 characters or more. So a SHORT string whose value
# is still the English source is seen by nothing at all — which is how renaming
# the import button from "File it here" to "File it in Run 2" silently threw
# away twelve working translations and was reported as fixed after German alone
# had been restored (found by a challenge round, 2026-09-01).
#
# A value equal to its key is NOT always untranslated: "Adobe RGB (1998)",
# "Alt", " Hz" and "-{flag}" are the same word in German, and forbidding that
# outright would be wrong. So the NUMBER is tracked instead, and any rise has
# to be looked at.
#
# RAISE THESE DELIBERATELY, never to make a red run green. A rise means either
# a genuinely identical new string (fine, say so here) or a translation that
# has just been lost (not fine). Measured 2026-09-01, 4716 keys.
# 2026-09-01, +1 for the eleven: the guided-refinement window's "there is no
# chart to check this against" message is new (the no-chart guard used to
# protect one of the two roads into the import and now protects both). German
# carries it; the rest hold the English source under the beta rule. The two
# renamed file-name strings were CARRIED, not re-Englished, so they cost
# nothing here.
#
# 2026-09-01, +4 for the eleven and -1 for German: Check & Refine became a
# real import door, which is four new strings (the third answer, its log
# line and the two window bodies). German carries all four, which also
# cleared one older placeholder it shared wording with.
# 2026-09-02, +1 for German only: the Neutral appearance's combo entry. The
# German for the theme IS "Neutral" — it is the same word, in the same sense,
# and inventing a different one to satisfy a counter would be the wrong way
# round. Every other language names it differently (Neutro, Neutre, Nøytral,
# ニュートラル, 中性色, …), so no other count moves. The tooltip that lists the
# four appearances is translated in all twelve and is not identical anywhere.
# 2026-09-02, +8 for the eleven and +1 for German: the calibration-replacement
# wording Basti approved that day, after his option-3 ruling made the old
# sentence false. Eight keys, and only ONE of them moves German — "{folder}",
# which is a bare placeholder and is the same in every language. German carries
# a real translation of the other seven, which is why its SUBSTANTIAL count
# (the other budget, in test_help_cards_untranslated_are_tracked.py) does not
# move at all.
#
# THE ELEVEN DELIBERATELY DID NOT CARRY THEIR OLD TRANSLATIONS ACROSS, and that
# is the whole reason this rises by eight rather than by two. Five of the eight
# keys are rewordings of keys that already had translations — but they were
# reworded because the ruling made what they said UNTRUE ("moves the one you
# have" became "moves the calibration you have measured"). Carrying the old
# text across would have left eleven languages quietly asserting the thing the
# whole exercise existed to stop asserting, which is worse than English. The
# two keys that changed by PUNCTUATION only (an em dash became a comma) were
# carried, and cost nothing here.
# 2026-09-02, #159, +1 for German and +3 for the other eleven: Tools ▸ Read
# single patches can now read a CR30, and it brought nine strings with it.
# German carries all nine. The eleven carry eight — including the CR30's
# spot-reading instruction, whose SIBLINGS in the same function are translated
# everywhere, so leaving that one in English would have been conspicuous in a
# way the §M messages are not. Two are identical to their key:
#
#   •  "CR30 (ChnSpec)" is the product's name, identical in all twelve, German
#      included. That is German's +1.
#   •  M-INSTRUMENT-BUSY's body is PROPOSED wording (§M-PROPOSED). Translating
#      a sentence nobody has approved is the churn behind "translate before the
#      final, not during a beta", and the whole M-CR30-* family already sits in
#      English in these eleven for the same reason.
_IDENTICAL_TO_KEY = {
    "de": 152,
    "es": 272, "fr": 292, "it": 284, "ja": 261, "nl": 301,
    "no": 285, "pl": 276, "pt": 276, "ru": 248, "sv": 289, "zh_CN": 254,
}


@pytest.mark.parametrize("code", _catalog_codes())
def test_untranslated_values_do_not_creep_in_unseen(code):
    cat = _load_catalog(code)
    same = sorted(k for k, v in cat.items()
                  if v == k and not k.startswith("@"))
    allowed = _IDENTICAL_TO_KEY.get(code)
    if allowed is None:
        pytest.skip(f"no recorded count for {code}")
    assert len(same) <= allowed, (
        f"[{code}] {len(same)} values are identical to their key, and "
        f"{allowed} were recorded. Something was renamed and lost its "
        f"translation, or a new string arrived untranslated. Newest few: "
        f"{same[-3:]}"
    )


def test_the_import_button_is_translated_everywhere(_=None):
    """The specific loss, pinned: it is short enough to hide from every count.

    Renaming a button is the easiest way to lose twelve translations at once,
    because the new key simply is not in any catalogue and the old one goes
    stale unnoticed.
    """
    keys = ("File it in {run}", "File it in a new run",
            "File it in the selected run")
    for code in _catalog_codes():
        cat = _load_catalog(code)
        for k in keys:
            assert k in cat, f"[{code}] the import button lost its key {k!r}"
            assert cat[k] != k, (
                f"[{code}] the import button is still English: {k!r}")
