"""New text a user reads does not use an em dash.

Basti's rule, 2026-09-06. The em dash (—) reads as machine-written: it is
overused by language models, and a person typing by hand usually reaches for a
comma, a colon, or a full stop. Those are also easier to read, so the rule costs
nothing.

Three things this file is careful about.

**It does not touch what already ships.** 1,225 of the app's 5,114 English
strings carry an em dash today, and rewriting them wholesale was explicitly not
asked for. They are frozen in `tests/data/em_dash_baseline.json`, and only text
that is NEW or MODIFIED has to be clean. Edit a grandfathered string for any
reason and it stops matching the baseline, so it gets cleaned then. The folder
tidies itself at the pace the code is touched, with no sweep.

**The baseline is a set of exact strings, not a count.** CLAUDE.md records what
a count-shaped ratchet cost the last time: German's 22 untranslated sentences
sat inside 13 slots of slack and nobody saw them. A number cannot tell you which
string it is standing in for.

**The en dash (–) is left alone.** It appears in 41 strings and it is the
correct dash in German and Norwegian, where the Halbgeviertstrich does the job
the em dash does in English. A rule against "long dashes" would make the
translations wrong, so only U+2014 is caught.

What this file cannot do: judge whether text is clear, friendly or complete. No
test can, and pretending otherwise would be the green-check-guarding-the-problem
pattern this repo has already been bitten by. Those stay a matter of review.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import em_dash_check as E                                        # noqa: E402

#: A ceiling, not a proof. `--freeze` refuses to overwrite an existing baseline
#: and there is no "add the failures" mode, so the ordinary way to launder new
#: text into the grandfathered set does not exist. This catches the clumsy way:
#: regenerating the file wholesale. It may only ever be lowered.
BASELINE_CEILING = 1225


def _excerpt(s: str, n: int = 110) -> str:
    flat = " ".join(s.split())
    return flat[:n] + ("…" if len(flat) > n else "")


def test_no_new_english_ui_text_uses_an_em_dash():
    english = E.english_strings()
    baseline = set(E.load_baseline()["english"])
    allowed = E.load_allowed()

    new = sorted(s for s in english
                 if E.EM in s and s not in baseline and s not in allowed)
    assert not new, (
        f"\n{len(new)} new or modified user-facing string(s) use an em dash "
        f"(—):\n\n"
        + "\n".join(f"  [{english[s]}]\n    {_excerpt(s)}" for s in new[:12])
        + (f"\n  … and {len(new) - 12} more" if len(new) > 12 else "")
        + "\n\nRewrite the SENTENCE. Do not just drop a comma in where the "
          "dash was: an em dash is often doing work, and swapping the "
          "punctuation without re-reading the result is how a clear line "
          "becomes a comma splice. If the sentence leans on the break, make "
          "it two sentences. A colon works when what follows explains what "
          "came before; brackets work when it is an aside.\n\n"
          "Do NOT do this with a scripted find-and-replace across many "
          "strings at once. Every one of these is read by a user and "
          "translated into twelve languages.\n\n"
          "If a string here is one you only MOVED or reindented, it counts as "
          "modified, so clean the dash while you are in there.\n\n"
          "If the em dash is genuinely unavoidable, add the string to "
          "tests/data/em_dash_allowed.json with a one-line reason. Do not add "
          "it to the baseline: the baseline is what shipped before the rule, "
          "and it only shrinks.")


#: Languages whose own punctuation uses U+2014, so the rule below cannot apply
#: to them. Chinese writes the 破折号 as `——` and Japanese uses `—`; there is no
#: other character for the job, and the "machine-written" tell this rule exists
#: to catch is an ENGLISH habit. This is the same reasoning that leaves the en
#: dash alone for German and Norwegian, and it was learned the same way: the
#: first sweep mechanically turned every em dash in these two catalogues into an
#: en dash, which put `––` into Chinese, where it is not punctuation at all.
_EM_DASH_IS_NATIVE = {"ja", "zh_CN"}


def test_no_translation_adds_an_em_dash_the_english_does_not_have():
    """A translator may keep an em dash the English has. Adding one it does not
    have puts the tell into a language nobody on this project reads closely.

    Two languages are exempt, and the exemption is the point rather than a hole:
    see `_EM_DASH_IS_NATIVE`. A rule that forces a language out of its own
    punctuation is a worse defect than the one it is preventing.
    """
    added = [(lang, key) for lang, key in E.translations_adding_an_em_dash()
             if lang not in _EM_DASH_IS_NATIVE]
    frozen = {tuple(t) for t in E.load_baseline()["translations"]}
    new = sorted((lang, key) for lang, key in added
                 if (lang, E.key_id(key)) not in frozen)
    assert not new, (
        f"\n{len(new)} translation(s) use an em dash where the English source "
        f"string does not:\n\n"
        + "\n".join(f"  {lang}: {_excerpt(key, 90)}" for lang, key in new[:12])
        + (f"\n  … and {len(new) - 12} more" if len(new) > 12 else "")
        + "\n\nUse the dash the language actually uses. German and Norwegian "
          "take the en dash (–) with spaces around it; the em dash is an "
          "English convention and reads as machine-written in both.")


def test_every_allowlisted_em_dash_says_why():
    """An allowlist with no reasons is a baseline with extra steps."""
    bad = []
    for text, reason in E.load_allowed().items():
        if not isinstance(reason, str) or len(reason.strip()) < 25:
            bad.append(f"{_excerpt(text, 60)!r}: reason too thin "
                       f"({reason!r})")
    assert not bad, (
        "\n  " + "\n  ".join(bad)
        + "\n\nSay what makes the em dash unavoidable in this particular "
          "string. 'Reads better' is not a reason — a comma reads better "
          "still.")


def test_the_baseline_only_ever_shrinks():
    baseline = E.load_baseline()
    english = baseline["english"]
    assert len(english) <= BASELINE_CEILING, (
        f"the em-dash baseline has grown to {len(english)} entries, over the "
        f"ceiling of {BASELINE_CEILING}. It holds the text that shipped before "
        f"the rule existed; new text does not belong in it. If text was "
        f"legitimately cleaned up, run `python scripts/em_dash_check.py "
        f"--prune` and LOWER the ceiling in this file.")
    assert len(set(english)) == len(english), \
        "the baseline has duplicate entries — regenerate it with --prune"
    overlap = set(english) & set(E.load_allowed())
    assert not overlap, (
        f"{len(overlap)} string(s) are in both the baseline and the allowlist. "
        f"A string is either grandfathered or deliberately excepted, not both.")


def test_no_string_carries_the_punctuation_a_careless_dash_swap_leaves():
    """The rewrite is a judgement nothing can check. Its worst failure is not.

    Removing an em dash by substituting punctuation, rather than by rewriting
    the sentence, leaves a small family of tell-tale marks: a doubled comma
    where the dash sat next to one already, a space before a comma, a doubled
    colon. This does not judge whether a sentence reads well, which no test
    can. It catches the specific wreckage of doing the substitution without
    looking at the result, which is a thing that has actually happened here.

    All four patterns measure ZERO across the app's 5,114 strings today, so
    there is nothing to grandfather and no ratchet to rot.
    """
    import re
    patterns = {
        ",,": r",,",
        "comma space comma": r", ,",
        "space before a comma": r"\S ,",
        "doubled colon": r"(?<!:)::(?!:)",
    }
    bad = []
    for text, where in E.english_strings().items():
        for name, pat in patterns.items():
            if re.search(pat, text):
                bad.append(f"[{where}] {name}: {_excerpt(text, 90)}")
    assert not bad, (
        "\n  " + "\n  ".join(bad[:12])
        + (f"\n  … and {len(bad) - 12} more" if len(bad) > 12 else "")
        + "\n\nThis usually means punctuation was substituted into a sentence "
          "instead of the sentence being rewritten. Read the line aloud and "
          "fix the sentence, not the symptom.")
