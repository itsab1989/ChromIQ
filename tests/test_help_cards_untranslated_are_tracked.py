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
# 2026-08-30, beta 2, raised 92 -> 93: a chart naming no instrument now says
# so, because ArgyllCMS otherwise claims it is for a GretagMacbeth i1 Pro --
# its own default, not anything in the file. One string.
#
# 2026-08-30, #159, raised 86 -> 92: a dark reference that does not read as
# dark now opens a window offering to retake it (Basti: a failure must not
# hide in a log panel he keeps closed), and both calibration texts were
# corrected to stop claiming the read-back checks what the user pointed at —
# hardware says it does not: white paper read back 0.004 %.
#
# 2026-08-30, #159, raised 83 -> 86: a lost Bluetooth link is now told apart
# from a refused calibration. The owner's CR30 powered itself off mid-session
# and ChromIQ said 'the measurement can go ahead' over a dead link, quoting
# bleak's 'Service Discovery has not been performed yet' as the reason.
#
# 2026-08-30, #159, raised 80 -> 83: the measure panel's advice line now says
# what a CR30 owner actually does ("rest it on the patch and press its button"
# rather than "scan each strip"), and a re-arm that finds nothing outstanding
# says so instead of going quiet. Three strings.
#
# 2026-08-30, #159, raised 76 -> 80 for the windows the owner asked for: a
# pop-up for a vanished instrument ("if this is an important message this
# should be in a pop up windows with benefitial options"), and a real Cancel on
# the black-calibration window, whose close button used to mean "skip". Four
# strings; the two revised message bodies replace keys already counted, and
# German is translated as usual because it is read.
#
# 2026-08-30, #159, raised 75 -> 76 for the sentence that says the measurement
# is still stopped after a magnet, when the user declines to end it. One string.
#
# 2026-08-30, #159, raised 73 -> 75 for the read-failure window: a refused
# reading was announced only in the log, where Basti did not see it, so it now
# opens a window that closes itself when the reading arrives. Two new strings,
# German translated as usual because it is read.
#
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
# Raised from 93 on 2026-08-30, deliberately, for the CR30's
# learned-tile step and its keyboard-trigger refusal (#159, both §M-PROPOSED).
# Their wording is not approved yet, and this project does not translate a
# message before it is agreed -- translating it twice is the waste that rule
# exists to prevent. German is translated as usual, which is why its budget
# does not move.
#
# 97 is the highest ACTUAL count across the twelve, not an estimate: the old 93
# was a uniform ceiling and the real figures sat below it by different amounts,
# so a uniform "+2" under-shot for some languages and passed for others.
# 2026-08-31, #159, raised 110 -> 115: the learn-the-white-tile window was
# rebuilt after Basti's own Bluetooth session -- it now listens while it is
# open, counts the presses as they land, and names the count the OPEN
# TRANSPORT needs (one over USB, two over Bluetooth), which is two message
# bodies plus three live-progress lines. Five strings. German is translated,
# as always.
# 2026-08-31, #159, raised 115 -> 116: a tile learn that failed for any
# reason other than being declined said nothing at all -- thirty-four seconds
# of a feature failing left no trace in the log, which is why the first
# explanation of it was wrong. It now says how many readings it took and why
# they were not enough. Two substantial strings.
#
# 2026-09-01, #159, raised 117 -> 122: the beta-5 challenge round. The import
# window's accept button now NAMES the run it will file into ("File it in
# Run 2") because "File it here" read as the run already on screen; the row
# indicator checkbox and its warnings say "row indicators" rather than "row
# numbers", which stopped being true when the band started following the
# chart's own patch pattern; and the import path's user-facing em dashes are
# gone at Basti's request. Where a key was only REWORDED, the existing
# translation was carried across rather than dropped back to English -- 19 of
# the 32 new keys kept their German. Five substantial strings are new.
#
# 2026-09-01, raised 122 -> 125: the verification round found the K8
# rename had never reached German (the checkbox still said
# "Zeilennummern", the very misnomer the rename cured, in the language
# the reporter reads) and that the import button's translations were
# lost when it was renamed. German now carries all of them; the other
# eleven hold three more English placeholders, from repairing the comma
# splices the em-dash removal left behind.
_BUDGET = {
    "de": 35,
    "es": 125, "fr": 125, "it": 125, "ja": 125, "nl": 125,
    "no": 125, "pl": 125, "pt": 125, "ru": 125, "sv": 125, "zh_CN": 125,
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
