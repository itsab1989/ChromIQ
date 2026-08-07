#!/usr/bin/env python3
"""Accept (or reject) a batch of translation work, one language at a time.

Written for the pre-GA translation pass, where most of the text is produced in
large batches and the failure modes are quiet ones: a dropped `<b>`, a lost
`{count}`, a log line that says `[FOUT]` where the line above it says
`[ERROR]`. `tests/test_i18n.py` already guards completeness, stale keys,
`{placeholder}` parity and the short-label length budget. This covers what it
does not, and prints progress while it is at it.

    python scripts/i18n_verify_batch.py            # every language
    python scripts/i18n_verify_batch.py fr es      # just these

Exit code is non-zero if any language has a hard failure, so it can gate a
commit.

**What is deliberately NOT checked: newline parity.** A translation legitimately
re-wraps — 2 manual breaks becoming 3 is a sentence that got longer, not damage.
Measured across the catalogues it fires 18–53 times per language, essentially
all of it benign, and a check that noisy trains people to ignore it.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / "data" / "i18n"

#: Real Qt markup. Angle brackets around ordinary words — "<chart name>",
#: "<your text>" — are prose placeholders the user reads, and translating them
#: is correct, so they must not be mistaken for tags. Matching only known HTML
#: element names is what separates the two.
_HTML = re.compile(
    r"</?(?:b|i|u|br|p|span|div|font|sub|sup|small|big|hr|ul|ol|li|table|tr|td|th|a|code|pre)"
    r"(?:\s[^>]*)?/?>", re.I)

_BRACE = re.compile(r"\{[^}]*\}")
_LOGP = re.compile(r"\[(?:INFO|OK|WARN|ERROR)\]")
_QUOTED = re.compile(r"'[^'\n]{0,80}'|\"[^\"\n]{0,80}\"|„[^“”\n]{0,80}[“”]")
#: Terms a language has already settled on. The English word appearing inside a
#: translation means the glossary drifted — which is how Dutch ended up with
#: both "meetveld" and "patches" in the same catalogue. Only languages with a
#: recorded decision are listed; an empty glossary simply skips the check.
#:
#: **A generic version of this was tried and does not work — do not rebuild it.**
#: The idea was to need no hand-written glossary: count, per language, the
#: translations still carrying each English term, and flag whichever language
#: keeps it far more often than its peers. Measured, it is mostly false
#: positives, because languages legitimately differ in what they borrow:
#: German keeps "Chart" as its own term (577 strings), Dutch keeps "run",
#: four languages keep "preset" — and cognates defeat it outright, with
#: French "page" flagged 118 times for being the French word. Drift can only
#: be judged against a decision somebody actually made, which is why this
#: table is short and hand-written.
_GLOSSARY = {
    "nl": {"patch": "meetveld", "patches": "meetvelden",
           "spacer": "scheidingslijn", "spacers": "scheidingslijnen",
           "chart": "kaart", "charts": "kaarten"},
    "de": {"patch": "Messfeld", "patches": "Messfelder",
           "spacer": "Trennfeld", "spacers": "Trennfelder"},
}


def check(code: str) -> "tuple[dict, list[str]]":
    path = I18N / f"{code}.json"
    j = json.loads(path.read_text())
    pairs = [(k, v) for k, v in j.items() if not k.startswith("@")]
    done = [(k, v) for k, v in pairs if v != k]
    placeholders = [k for k, v in pairs if v == k]

    fails: list[str] = []

    def note(rule, k, extra):
        fails.append(f"[{rule}] {k[:70]!r}\n        {extra}")

    glossary = _GLOSSARY.get(code, {})
    for k, v in done:
        # Brace contents are format placeholders — "{patches}" is a variable
        # name the code fills in, not a word anyone reads, and translating it
        # would break str.format. Strip them before looking for English terms,
        # or the check reports its own opposite.
        # Quoted English is deliberate and must not be flagged: a gloss for
        # the reader („patches“), or ArgyllCMS's own error text quoted verbatim
        # ('not enough patches read') which the user will see in English no
        # matter what language the interface is in.
        v_prose = _QUOTED.sub(" ", _BRACE.sub(" ", v))
        for english, agreed in glossary.items():
            if re.search(rf"\b{re.escape(english)}\b", v_prose, re.I):
                note("glossary", k,
                     f"the translation still contains the English \u201c{english}\u201d; "
                     f"this language settled on \u201c{agreed}\u201d")
                break
        if _HTML.findall(k.lower()) != _HTML.findall(v.lower()):
            # KNOWN ACCEPTABLE: Japanese and Chinese mark a UI element's name
            # with corner brackets 「…」 where English uses <i>…</i>. That is the
            # right typographic convention in those languages, not a dropped
            # tag, so do NOT "fix" it by forcing the italics back in. It is
            # still reported, because the alternative is a check that silently
            # accepts a genuinely lost tag.
            note("html", k, f"tags {_HTML.findall(k)} -> {_HTML.findall(v)}")
        # SET, not multiset: English repeating {side} twice while the
        # translation says it once is a better sentence, not a lost value —
        # str.format is happy either way. Comparing counts flagged exactly
        # that, in every language.
        if set(_BRACE.findall(k)) != set(_BRACE.findall(v)):
            note("placeholder", k, f"{_BRACE.findall(k)} -> {_BRACE.findall(v)}")
        if len(k) <= 24 and "\n" not in k and "{" not in k:
            budget = int(len(k) * 1.6 + 6)
            if len(v) > budget:
                note("too-long", k, f"{len(v)} chars, budget {budget}: {v!r}")

    # Log prefixes must be handled the SAME way throughout one language. Either
    # all kept in English or all translated — a log that mixes [ERROR] and
    # [FOUT] line by line looks broken. (Project rule: keep them as-is.)
    kept = sum(1 for k, v in done if _LOGP.search(k) and _LOGP.search(v))
    changed = sum(1 for k, v in done if _LOGP.search(k) and not _LOGP.search(v))
    if kept and changed:
        fails.append(f"[log-prefix] inconsistent: {kept} keep the English prefix, "
                     f"{changed} translate it. Pick one — the project rule is to keep "
                     f"[INFO]/[OK]/[WARN]/[ERROR] as they are.")

    stats = {"total": len(pairs), "translated": len(done),
             "placeholders": len(placeholders),
             "chars_left": sum(len(k) for k in placeholders)}
    return stats, fails


def main(argv: "list[str]") -> int:
    codes = argv or sorted(p.stem for p in I18N.glob("*.json")
                           if not p.name.startswith("parameters"))
    worst = 0
    print(f"{'lang':6} {'done':>6}/{'total':<6} {'left':>6} {'chars left':>11}  {'issues':>6}")
    print("-" * 56)
    detail: dict[str, list[str]] = {}
    for code in codes:
        stats, fails = check(code)
        detail[code] = fails
        pct = 100 * stats["translated"] / stats["total"]
        print(f"{code:6} {stats['translated']:6}/{stats['total']:<6} "
              f"{stats['placeholders']:6} {stats['chars_left']:11,}  "
              f"{len(fails):6}   {pct:5.1f}%")
        worst = max(worst, len(fails))
    for code, fails in detail.items():
        if fails:
            print(f"\n=== {code}: {len(fails)} issue(s) ===")
            for f in fails[:25]:
                print("  " + f)
            if len(fails) > 25:
                print(f"  … and {len(fails) - 25} more")
    return 1 if worst else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
