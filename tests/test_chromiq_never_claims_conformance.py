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
    # #182, 2026-09-10: the Fogra credit line, and it is a DENIAL. Fogra's own
    # terms of use say the FOGRAxx designation "may be used solely to identify
    # the respective reference data. Such use does not imply certification,
    # approval or endorsement by Fogra." ChromIQ prints that denial beside
    # every reference set, so the word "certification" appears here only to be
    # refused. Read, and kept.
    "It is not a certification, approval or endorsement by",
)

#: The denials must not merely be legal, they must EXIST. Deleting one would
#: pass a test that only forbids things.
REQUIRED_DENIALS = (
    "can never say that a print conforms to a standard",
    "never says that anything conforms to a standard",
    "it does not certify",
    # The Fogra grant is conditional on this sentence existing, not merely on
    # no claim being made. Deleting the credit line would otherwise pass every
    # other check in this file.
    "It is not a certification, approval or endorsement by",
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
#: TIER ONE: phrases that cannot be innocent in any context, so they are swept
#: over the WHOLE catalogue with no domain filter. These are the ones a
#: translator actually writes, and the first version of this test missed every
#: one of them: an on-screen round planted eighteen literal claims and
#: SEVENTEEN passed. The cause was that the patterns were cognates of the
#: English verbs "conform" and "certify", while every language says it with its
#: own ordinary verb for "meets" or "satisfies".
CLAIM_ALWAYS = {
    "de": r"entspricht\s+(?:der|den)\s+Norm|erfüllt\s+(?:die|den)\s+Norm|normkonform|konform\s+mit",
    "es": r"cumple\s+(?:con\s+)?(?:la\s+)?norma|conforme\s+(?:a|con)\s+(?:la\s+)?norma",
    "fr": r"respecte\s+la\s+norme|conforme\s+(?:à|a)\s+la\s+norme|satisfait\s+(?:à\s+)?la\s+norme",
    "it": r"rispetta\s+(?:la\s+)?norma|conforme\s+alla\s+norma|soddisfa\s+(?:la\s+)?norma",
    "nl": r"voldoet\s+aan\s+de\s+norm|conform\s+de\s+norm",
    "no": r"oppfyller\s+standarden|samsvar\s+med\s+standard|tilfredsstiller\s+standarden",
    "pl": r"spełnia\s+norm|zgodn\w*\s+z\s+norm",
    "pt": r"cumpre\s+(?:a\s+)?norma|conforme\s+(?:a|com)\s+(?:a\s+)?norma|satisfaz\s+(?:a\s+)?norma",
    "ru": r"соответству\w*\s+(?:требованиям\s+)?станд|отвечает\s+требованиям\s+станд",
    "sv": r"uppfyller\s+standard|överensstämmer\s+med\s+standard",
    # Japanese and Chinese say it with the standard's NAME, not a generic word,
    # so requiring 規格 / 标准 nearby let "ISO 12647-8に適合" straight through.
    "ja": r"(?:規格|ISO\s*\d[\d\-:]*)\s*(?:に)?適合|認証",
    "zh_CN": r"符合\s*(?:标准|ISO\s*\d[\d\-:]*)|认证",
}

#: TIER TWO: cognates that ALSO mean something innocent, so they are swept only
#: where the English source is talking about a standard. Swept over the whole
#: catalogue they flagged 66 harmless strings: Italian and Portuguese spell a
#: security certificate with the same stem, Japanese 適合 is how well a profile
#: FITS its own measurements, Norwegian "samsvar" and Swedish "överensstämm"
#: are everyday words for agreeing with something. A check that cries wolf is a
#: check nobody reads.
CLAIM_IN_DOMAIN = {
    "de": r"konform|zertifizier",
    "es": r"conformidad",
    "fr": r"conformité|certifié",
    "it": r"conformità",
    "nl": r"\bconform\b|gecertificeerd",
    "no": r"samsvar|sertifisert",
    "pl": r"certyfikowan",
    "pt": r"conformidade",
    "ru": r"сертифицир",
    "sv": r"överensstämm|certifierad",
    "ja": r"適合|認証",
    # 符合 on its own is the everyday "matches" and appears in a paragraph about
    # ISO 3664 viewing light, which names a standard and so passes the domain
    # filter. Tier one already catches 符合标准 and 符合 ISO, which are the
    # claims; this tier keeps only the unambiguous "certified".
    "zh_CN": r"认证",
}

CLAIM_BY_LANGUAGE = CLAIM_ALWAYS          # the languages this test covers


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
    always = re.compile(CLAIM_ALWAYS[code], re.I)
    in_domain = re.compile(CLAIM_IN_DOMAIN[code], re.I)
    offenders = []
    for source, translated in data.items():
        if source.startswith("@") or not isinstance(translated, str):
            continue
        hit = always.search(translated) or (
            in_domain.search(translated) if DOMAIN.search(source) else None)
        if not hit:
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


# ---- the net's own self-check -------------------------------------------
#: The literal claims an on-screen round planted on 2026-09-10, one per
#: language, of which SEVENTEEN OF EIGHTEEN passed the first version of this
#: test. They are kept here so the net can never silently narrow again: if a
#: pattern is edited and one of these stops being caught, this fails.
_REAL_CLAIMS = {
    "de": "Dieser Druck entspricht der Norm ISO 12647-8.",
    "es": "Esta impresión cumple con la norma ISO 12647-8.",
    "fr": "Cette impression respecte la norme ISO 12647-8.",
    "it": "Questa stampa rispetta la norma ISO 12647-8.",
    "nl": "Deze afdruk voldoet aan de norm ISO 12647-8.",
    "no": "Denne utskriften oppfyller standarden ISO 12647-8.",
    "pl": "Ten wydruk spełnia normę ISO 12647-8.",
    "pt": "Esta impressão cumpre a norma ISO 12647-8.",
    "ru": "Этот отпечаток соответствует требованиям стандарта ISO 12647-8.",
    "sv": "Den här utskriften uppfyller standarden ISO 12647-8.",
    "ja": "この印刷は ISO 12647-8 に適合しています。",
    "zh_CN": "此打印符合 ISO 12647-8 标准。",
}


@pytest.mark.parametrize("code", sorted(_REAL_CLAIMS))
def test_the_net_catches_a_real_claim_in_that_language(code: str):
    """A pattern that catches nothing is a green test guarding a bug."""
    rx = re.compile(CLAIM_ALWAYS[code], re.I)
    assert rx.search(_REAL_CLAIMS[code]), (
        f"[{code}] the sweep does not recognise {_REAL_CLAIMS[code]!r} as a "
        "claim. That is the sentence a translator actually writes.")


@pytest.mark.parametrize("code", sorted(_REAL_CLAIMS))
def test_the_net_leaves_an_innocent_sentence_alone(code: str):
    """The other half. A net that matches everything is no better than one
    that matches nothing, and the first draft flagged 66 innocent strings."""
    innocent = {
        "de": "Das Zertifikat wird in zwei Listen von Windows eingetragen.",
        "es": "El certificado se coloca en dos listas de Windows.",
        "fr": "Le certificat est placé dans deux listes de Windows.",
        "it": "Il certificato viene messo in due elenchi di Windows.",
        "nl": "Het certificaat komt in twee lijsten van Windows.",
        "no": "Profilen passer godt til sine egne målinger.",
        "pl": "Certyfikat trafia do dwóch list systemu Windows.",
        "pt": "O certificado é colocado em duas listas do Windows.",
        "ru": "Профиль хорошо описывает собственные измерения.",
        "sv": "Profilen stämmer väl med sina egna mätningar.",
        "ja": "プロファイルは自身の測定値によく適合しています。",
        "zh_CN": "该特性文件与自身的测量值符合得很好。",
    }[code]
    rx = re.compile(CLAIM_ALWAYS[code], re.I)
    assert not rx.search(innocent), (
        f"[{code}] the sweep calls an innocent sentence a claim: {innocent!r}")
