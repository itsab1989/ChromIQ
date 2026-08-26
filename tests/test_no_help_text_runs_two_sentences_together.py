"""No user-facing string may run two sentences together.

Every one of these came from re-wrapping a long help text across Python string
continuations: the trailing space that separated two sentences sat at the end of
a line and was silently dropped, leaving

    "…the classic cause of mis-recognised strips and bad data.Click “Start
     Measurement” and follow the strip-by-strip prompts."

on screen. It happened THREE times in one afternoon while rewriting the help
cards, and each time it was found by a translator or by reading the extractor's
output — never by a test, and never by looking at the source, where the two
halves sit on different lines and look fine.

The check runs over the extracted catalogue keys, which is what the user
actually reads, not over the source text.
"""
from __future__ import annotations

import re





def _english_keys() -> list[str]:
    """Every English source string the app can show, taken from a real
    catalogue's keys (the key IS the English text)."""
    import json
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent / "data" / "i18n" / "de.json"
    return [k for k in json.loads(p.read_text(encoding="utf-8"))
            if not k.startswith("@")]


#: A word character, a full stop, then an immediate capital — with no space.
#: Abbreviations and file extensions are excluded by requiring at least two
#: letters before the stop and a lower-case letter directly before it.
_RUN_ON = re.compile(r"[a-z]{2}\.[A-Z][a-z]")

#: Things that legitimately look like a run-on.
_ALLOWED = (
    ".ti1", ".ti2", ".ti3", ".icc", ".icm", ".cal", ".cht", ".cie", ".txt",
    ".json", ".yaml", ".tif", ".tiff", ".pdf", ".ps", ".mxf", ".pxf", ".gam",
    ".py", ".app", ".exe", ".dmg", ".zip", "e.g.", "i.e.", "etc.",
)


def test_no_english_string_runs_a_sentence_into_the_next():
    offenders = []
    for key in _english_keys():
        for m in _RUN_ON.finditer(key):
            frag = key[max(0, m.start() - 6):m.end() + 6]
            if any(a in frag.lower() for a in _ALLOWED):
                continue
            offenders.append(f"…{frag}…")
    assert not offenders, (
        "these strings run two sentences together with no space:\n  "
        + "\n  ".join(sorted(set(offenders))))


def test_this_check_can_see_a_run_on():
    """Proof the pattern matches the real defect, and not merely nothing."""
    bad = "the classic cause of mis-recognised strips and bad data.Click here"
    assert _RUN_ON.search(bad), "the pattern misses the exact bug it was written for"
    good = "the classic cause of mis-recognised strips and bad data. Click here"
    assert not _RUN_ON.search(good)
    assert not _RUN_ON.search("Load the .ti3 measurement"), "false positive on a file extension"


# --------------------------------------------------------------------------
# The stronger guard: catch the CAUSE, not one of its symptoms.
#
# The check above reads the finished English strings and looks for a sentence
# boundary with no space. That misses every dropped space that is not at a
# sentence boundary — a word run into the next word reads as a typo and would
# sail through. The defect is not really "a missing full-stop space"; it is
# "two adjacent string literals on different lines with no space at the join",
# which is what re-wrapping a long tr() call produces.
#
# Measured over ui/, core/ and workflow/: 0 false positives.
# --------------------------------------------------------------------------
import ast
import io
import tokenize
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_DIRS = ("ui", "core", "workflow")


def _joins_without_a_space(path: Path):
    """Yield (line, left_tail, right_head) for every implicit concatenation
    INSIDE A tr() CALL that spans a line break with no space at the join.

    Scoped to `tr(` deliberately. Applied to every string in the tree it fires
    on regex alternations (`(?:a|b)` split across lines), on CSS
    (`font-weight:bold;` + `margin-top:4px`) and on HTML (`</p>` + `<ul>`) —
    all correct joins. Only translated prose is read by a human as a sentence.
    """
    src = path.read_text(encoding="utf-8")
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, IndentationError):
        return
    depth = 0            # paren depth inside the current tr(...) call, 0 = outside
    armed = False        # saw NAME 'tr', waiting for its '('
    prev = None
    for t in toks:
        if t.type == tokenize.NAME and t.string == "tr" and depth == 0:
            armed = True
            continue
        if t.type == tokenize.OP:
            if t.string == "(":
                if armed:
                    depth = 1
                    armed = False
                    prev = None
                elif depth:
                    depth += 1
            elif t.string == ")" and depth:
                depth -= 1
                if depth == 0:
                    prev = None
            if depth == 0:
                armed = False
            continue
        armed = False
        if not depth:
            continue
        if t.type == tokenize.STRING:
            if (prev is not None
                    and t.start[0] > prev.end[0]
                    and not prev.string.lstrip("rbuf").startswith(('"""', "\'\'\'"))
                    and not t.string.lstrip("rbuf").startswith(('"""', "\'\'\'"))):
                try:
                    left, right = ast.literal_eval(prev.string), ast.literal_eval(t.string)
                except Exception:                        # noqa: BLE001
                    prev = t
                    continue
                if (left and right and not left[-1].isspace()
                        and not right[0].isspace()
                        # A join is deliberate when the left side ends in
                        # markup or an opening/hyphenating character: an HTML
                        # tag (`<br><br>`, `</pre>`) already supplies the break.
                        and left[-1] not in "-(\u2014/[{<>|"
                        and right[0] not in ")]},.;:!?|<>"):
                    yield t.start[0], left[-14:], right[:14]
            prev = t
        elif t.type not in (tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT,
                            tokenize.INDENT, tokenize.DEDENT):
            prev = None


def test_no_wrapped_string_loses_the_space_at_its_join():
    offenders = []
    for d in _DIRS:
        for f in sorted((_ROOT / d).rglob("*.py")):
            for line, left, right in _joins_without_a_space(f):
                offenders.append(f"{f.relative_to(_ROOT)}:{line}  …{left}|{right}…")
    assert not offenders, (
        "these wrapped strings join with no space, so the two halves run "
        "together on screen:\n  " + "\n  ".join(offenders))


def test_the_join_check_fires_on_the_real_defect(tmp_path):
    """Control. Without this, a check that finds nothing looks identical to a
    check that cannot find anything."""
    bad = tmp_path / "bad.py"
    bad.write_text(
        'x = tr("the classic cause of mis-recognised strips and bad data."\n'
        '       "Click “Start Measurement” and follow the prompts.")\n',
        encoding="utf-8")
    assert list(_joins_without_a_space(bad)), "the check misses the real defect"

    good = tmp_path / "good.py"
    good.write_text(
        'x = tr("the classic cause of mis-recognised strips and bad data. "\n'
        '       "Click “Start Measurement” and follow the prompts.")\n',
        encoding="utf-8")
    assert not list(_joins_without_a_space(good)), "false positive on a correct join"
