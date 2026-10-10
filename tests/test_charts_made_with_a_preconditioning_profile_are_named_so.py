"""Charts whose expected colours are accurate are named for what made them.

Knut, #182 5984174575: the charts whose file carries ArgyllCMS's
``ACCURATE_EXPECTED_VALUES`` are charts made with a PRE-CONDITIONING PROFILE
(``targen -c``). Beta 11 called them "a chart made from a profile", which
reads like a FROM PROFILE GAMUT chart, a different thing that never carries
the keyword. This keeps the wrong name out of every user-facing string and
keeps the right one, in every catalogue, on the places that name them: since
beta 17 the Preferences ▸ Measurement table's column (Knut 6078174421:
"Profiling charts made with a pre-conditioning profile"), the defaults line,
the limits help paragraph (Preferences and the Measure tab) and the hover
card's chart-type phrase.

FROM PROFILE GAMUT ("built from the profile's gamut") and "a verification
judged against its profile" are different charts and keep their names.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

LANGS = ["de", "es", "fr", "it", "ja", "nl", "no", "pl", "pt", "ru", "sv",
         "uk", "zh_CN"]

#: "a chart made from a profile" and its variants, but not "built from the
#: profile's gamut" (FROM PROFILE GAMUT) nor "judged against its profile".
_WRONG = re.compile(
    r"\b(?:chart|charts|target|targets)\s+(?:made|generated|created)\s+"
    r"(?:from|with)\s+(?:a|the|its|your)\s+profile\b(?!'s)", re.I)

#: The strings that name these charts (beta 17).
CARD = "profiling charts made with a pre-conditioning profile"
LABEL = "Profiling charts made with a pre-conditioning profile"
DEFAULT = ("**Default:** ΔE*ab 95 on profiling charts with estimated colours, "
           "20 on profiling charts made with a pre-conditioning profile, 5 on "
           "verification charts and 95 on calibration charts")

#: How each catalogue already renders "pre-conditioning profile" (its
#: "Select pre-conditioning profile" and kin), stem only.
TERM = {
    "de": "Vorkonditionierungs-Profil", "es": "perfil de preacondicionamiento",
    "fr": "profil de préconditionnement", "it": "profilo di precondizionamento",
    "ja": "プレコンディショニングプロファイル", "nl": "voorconditioneringsprofiel",
    "no": "forkondisjoneringsprofil", "pl": "profilem wstępnym",
    "pt": "perfil de pré-condicionamento", "ru": "профилем предобработки",
    "sv": "förkonditioneringsprofil",
    "uk": "профілем попереднього кондиціонування", "zh_CN": "预调节配置文件",
}


def _limits_help() -> str:
    from ui.dialogs.settings_dialog import LIMITS_PURPOSE_HELP
    return LIMITS_PURPOSE_HELP


def test_no_user_facing_string_says_made_from_a_profile():
    from i18n_extract import extract_keys
    bad = sorted(k for k in extract_keys() if _WRONG.search(k))
    assert not bad, bad


def test_the_four_places_use_the_term():
    from i18n_extract import extract_keys
    keys = extract_keys()
    for k in (CARD, LABEL, DEFAULT):
        assert k in keys, k
    help_ = _limits_help()
    assert help_ in keys
    assert ("  • Profiling charts made with a pre-conditioning profile, "
            "default 20:") in help_


def test_the_measure_tab_shows_the_same_paragraph():
    from ui.dialogs.settings_dialog import LIMITS_PURPOSE_HELP as a
    from ui.tabs.tab_measure import LIMITS_PURPOSE_HELP as b
    assert a == b


def test_every_catalogue_renders_the_term_as_it_already_does():
    help_ = _limits_help()
    for code in LANGS:
        cat = json.loads((ROOT / "data" / "i18n" / f"{code}.json")
                         .read_text(encoding="utf-8"))
        term = TERM[code]
        # the stem, case-insensitive, so a capitalised or inflected form passes
        stem = term[:-3].lower()
        for key in (CARD, LABEL, DEFAULT, help_):
            assert key in cat, (code, key[:50])
            assert stem in cat[key].lower(), (code, key[:50], cat[key][:120])


def test_from_profile_gamut_keeps_its_name():
    """The correction must not reach the other chart that uses a profile."""
    from i18n_extract import extract_keys
    keys = extract_keys()
    assert any("built from the profile's gamut" in k for k in keys)
    assert "Verification charts" in keys
