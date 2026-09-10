"""ChromIQ never says a print conforms to, is certified to, or qualifies as
anything, and this sweeps the whole text surface to keep it that way.

**This is not a house style. It is a promise made to a rights holder in
writing**, on 2026-09-09, as part of the permission that lets ChromIQ name and
use their material at all. `docs/design/issue_182_answers.md` records it:

> the promise that ChromIQ never prints that a print "conforms to", "is
> certified to" or "qualifies as" anything. **That promise is now made to a
> third party**, so the rule that the word appears only in denials has to hold
> permanently.

It also happens to be true of the colour science. A limit set named after a
standard holds that standard's published figures applied to *your* chart, which
is not that standard's control strip on that standard's chart. No licence
changes that, so no wording may imply otherwise.

Two tests before this one guarded two specific strings each (`test_compliance_
sets.py`, `test_report_window_limit_controls.py`). Neither swept the surface and
neither read a translation, so a claim written anywhere else, or introduced by a
translator, would have shipped.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import em_dash_check as E                                        # noqa: E402


#: The conformance sense only. `certificate`, `certlm.msc` and `certificates`
#: are Windows driver vocabulary and have nothing to do with this promise; a
#: sweep that catches them teaches its reader to ignore it.
CLAIM = re.compile(
    r"\bconform\w*\b"
    r"|\bcertifi(?:ed|es|cation)\b|\bcertify\b"
    r"|\bqualif(?:ies|y)\s+as\b"
    r"|\bcomplian(?:t|ce)\s+with\b"
    r"|\bcomplies\s+with\b",
    re.I,
)

#: A string may carry a claim word ONLY if it contains one of these. Two are the
#: denials themselves; one is the NAME OF A WINDOWS LIST, which the driver help
#: has to spell exactly as Windows spells it. Anything else is a new claim and
#: has to be read by a human, which is what a failure here asks for.
ALLOWED_CONTEXTS = (
    "Trusted Root Certification Authorities",
    "can never say that a print conforms to a standard",
    "never says that anything conforms to a standard",
    "it does not certify",
)

#: The denials must not merely be legal, they must EXIST. Deleting one would
#: pass a test that only forbids things.
REQUIRED_DENIALS = (
    "can never say that a print conforms to a standard",
    "never says that anything conforms to a standard",
    "it does not certify",
)


#: Where the promise lives: any string that talks about a standard, a limit set
#: or a verdict. Outside it, the cognates above mean ordinary things.
DOMAIN = re.compile(
    r"ISO\s*12647|limit set|\bstandard\b|\bstandards\b|verdict"
    r"|conform|certif|Fogra|GRACoL|Idealliance",
    re.I,
)


def _excerpt(s: str, mm: re.Match, n: int = 90) -> str:
    i = max(0, mm.start() - n)
    return " ".join(s[i:mm.end() + n].split())


# ---- the surface this actually reaches ----------------------------------
def test_the_sweep_reaches_the_dropdown_entries():
    """PIN THE COVERAGE, because the coverage is where this class of test dies.

    Until 2026-09-10 the collector gathered a key that does not exist in
    `data/parameters.yaml` and missed the two that do, so 145 user-facing
    strings, every Create Chart dropdown entry among them, were invisible to
    every check built on it. A sweep that cannot see a surface will report that
    surface clean for ever.
    """
    english = E.english_strings()
    assert "OFPS: optimised farthest point (recommended)" in english, (
        "the sweep no longer reaches data/parameters.yaml `labels`; every check "
        "built on english_strings() has just gone blind to the dropdowns")
    # A caption that exists ONLY under a `name:` key, so this cannot pass on
    # some other surface. The first draft of this assertion looked for a phrase
    # that also appears in a tooltip, and a mutation that blinded `name`
    # entirely still passed it.
    assert "B2A Table Quality" in english, (
        "the sweep no longer reaches data/parameters.yaml `name`; the captions "
        "beside the controls have just gone invisible to every check built on "
        "english_strings()")


# ---- English ------------------------------------------------------------
def test_no_english_string_claims_conformance():
    offenders = []
    for s in E.english_strings():
        if any(ctx in s for ctx in ALLOWED_CONTEXTS):
            continue
        mm = CLAIM.search(s)
        if mm:
            offenders.append(f"[{mm.group(0)}] {_excerpt(s, mm)}")
    assert not offenders, (
        "\n%d user-facing string(s) claim conformance, certification or "
        "qualification. ChromIQ promised a rights holder in writing that it "
        "never does this. If one of these is a DENIAL, add its exact wording to "
        "ALLOWED_CONTEXTS in this file so the next reader can see it was "
        "read.\n\n  %s" % (len(offenders), "\n  ".join(offenders)))


def test_the_denials_are_still_there():
    english = E.english_strings()
    for phrase in REQUIRED_DENIALS:
        assert any(phrase in s for s in english), (
            f"the denial {phrase!r} has gone from the app's text. The promise "
            "is not only that ChromIQ never claims conformance, it is that the "
            "report SAYS SO in its own words.")


# ---- translations -------------------------------------------------------
#: A cognate net, not a semantic proof, and it is documented as such. It catches
#: the word a translator reaches for when the English says "conforms" or
#: "certified". It cannot catch a claim phrased some other way, and a language
#: whose row is empty is not proven clean, it is unswept.
#:
#: IT IS APPLIED ONLY TO THE STANDARDS DOMAIN, and the first draft was not.
#: Swept over the whole catalogue it flagged 66 innocent strings in five
#: languages: Italian and Portuguese "certificato"/"certificado" is the Windows
#: driver's CERTIFICATE, Japanese 適合 is how well a profile FITS its own
#: measurements, Norwegian "samsvar" and Swedish "överensstämm" are everyday
#: words for agreeing with something. A check that cries wolf 66 times is a
#: check nobody reads, and this promise is worth more than that.
CLAIM_BY_LANGUAGE = {
    # Each is the CONFORMANCE sense, not the certificate noun and not the
    # everyday verb for "agrees with". Where a language's word for a security
    # certificate shares the stem (Spanish, Italian and Portuguese
    # "certificado"/"certificato"), the stem is left out entirely rather than
    # patched with exceptions: the Windows driver help legitimately uses it
    # four times in each of those languages.
    "de": r"konform|zertifizier",
    "es": r"conformidad|conforme\s+(?:a|con)\s+(?:la\s+)?norma",
    "fr": r"conformité|conforme\s+(?:à|a)\s+la\s+norme|certifié",
    "it": r"conformità|conforme\s+alla\s+norma",
    "nl": r"\bconform\b|gecertificeerd",
    "no": r"samsvar\s+med\s+standard|sertifisert",
    "pl": r"zgodn(?:y|ość)\s+z\s+norm|certyfikowan",
    "pt": r"conformidade|conforme\s+(?:a|com)\s+(?:a\s+)?norma",
    "ru": r"соответству\w*\s+станд|сертифицир",
    "sv": r"överensstämmer\s+med\s+standard|certifierad",
    "ja": r"規格に適合|認証",
    "zh_CN": r"符合标准|认证",
}


@pytest.mark.parametrize("code", sorted(CLAIM_BY_LANGUAGE))
def test_no_translation_invents_a_claim(code: str):
    """A translation may carry the word only where its English source does.

    The English denials are allowed to be translated as denials. Anywhere else,
    a translator who writes "conforms to the standard" has made ChromIQ break a
    promise in a language nobody on this project reads.
    """
    path = ROOT / "data" / "i18n" / f"{code}.json"
    if not path.exists():                       # a language may be removed
        pytest.skip(f"no catalogue for {code}")
    data = json.loads(path.read_text(encoding="utf-8"))
    rx = re.compile(CLAIM_BY_LANGUAGE[code], re.I)
    offenders = []
    for source, translated in data.items():
        if source.startswith("@") or not isinstance(translated, str):
            continue
        if not DOMAIN.search(source):
            continue
        if not rx.search(translated):
            continue
        if any(ctx in source for ctx in ALLOWED_CONTEXTS):
            continue
        if CLAIM.search(source):
            # the English itself carries the word and was allowed above
            continue
        offenders.append(f"{source[:70]!r} -> {translated[:90]!r}")
    assert not offenders, (
        f"\n[{code}] {len(offenders)} translation(s) claim conformance where "
        f"the English does not:\n  " + "\n  ".join(offenders))
