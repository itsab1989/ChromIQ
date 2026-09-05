"""A bullet that names a control must name it the way the control reads.

`9c6f7c14` closed nine drifts of exactly this class and its checker only
compared runs a message EMPHASISED or QUOTED (``<b>…</b>``, “…”). This
codebase's house style for a button list in a ``QMessageBox`` is a bullet and
an em-dash — **plain text** — so five live German drifts survived that sweep,
three of them in the §M end-of-measurement window, the one that decides whether
a measurement is kept or thrown away:

    the bullet said        the button read
    Speichern und stoppen  Speichern und beenden
    Verwerfen und stoppen  Verwerfen und beenden
    Weiter messen          Weitermessen

…and two more in the stored-chart window, plus two in Italian and one in Dutch
that nobody had looked for at all. The German user is told to press a button
that is not there, in the two windows where pressing the wrong one costs a
measurement.

So this test looks where that checker could not. It harvests the ACTUAL control
labels from the source — every literal handed to ``tr()`` inside a button or
checkbox constructor — and then, for every bullet in every catalogue message,
requires that the name in the bullet is the same string the control carries in
that same language.

WHAT IT CANNOT SEE, stated plainly so nobody trusts it further than it goes:

* only bullet-shaped mentions (``•  Name — …``). A control named mid-sentence
  in plain prose is still invisible; the emphasis/quote check in
  ``scripts/i18n_extract.py`` covers the emphasised and quoted forms of that,
  and nothing covers the rest.
* Qt's OWN standard buttons — Cancel, OK, Close — come from ``qtbase_<code>.qm``
  and are not in our catalogue at all, so a bullet naming one of them is
  skipped rather than checked.
* it harvests the constructors listed in ``_LABEL_CALLS``. A label built any
  other way (assembled from fragments, set later through ``setText`` on a
  variable) is not harvested, and a bullet naming it is skipped.
* a bullet whose name matches NO harvested control is skipped, not failed —
  plenty of bullets name a choice rather than a button ("Cancel — nothing is
  written"). That is the deliberate hole: this test proves agreement where a
  control is named, never that a name is one.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / "data" / "i18n"

BUL, DASH = "•", "—"
#: "•  Some Button — the rest of the sentence"
BULLET = re.compile("^" + BUL + r"\s+(.+?)\s+" + DASH + r"\s", re.M)

#: Calls whose ``tr("…")`` argument is a control's own on-screen label.
_LABEL_CALLS = {
    "addButton", "QPushButton", "QCheckBox", "QRadioButton", "QToolButton",
    "setButtonText", "addAction", "QAction",
}


def _control_labels() -> "set[str]":
    """Every English label a control in ui/ or workflow/ actually carries."""
    out: "set[str]" = set()
    for base in ("ui", "workflow"):
        for path in sorted((ROOT / base).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:                      # pragma: no cover
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = getattr(node.func, "id", None) or \
                    getattr(node.func, "attr", None)
                if name not in _LABEL_CALLS:
                    continue
                for arg in node.args:
                    if (isinstance(arg, ast.Call)
                            and getattr(arg.func, "id", None) == "tr"
                            and arg.args
                            and isinstance(arg.args[0], ast.Constant)
                            and isinstance(arg.args[0].value, str)):
                        out.add(arg.args[0].value)
    return out


CONTROLS = _control_labels()
LANGS = sorted(p.stem for p in I18N.glob("*.json"))


def _catalogue(code: str) -> "dict[str, str]":
    return json.loads((I18N / f"{code}.json").read_text(encoding="utf-8"))


def test_the_harvest_actually_found_the_controls():
    """A harvest that silently found nothing would make every check below pass.

    Named, not counted: these five are the ones the drift was in.
    """
    assert len(CONTROLS) > 200, len(CONTROLS)
    for label in ("Save and stop", "Discard and stop", "Keep measuring",
                  "Replace stored chart", "Keep stored chart"):
        assert label in CONTROLS, label


def test_there_are_bullets_naming_controls_to_check():
    """…and that the English side of the check is not empty either."""
    en = _catalogue("de")
    named = [k for k in en
             if any(n in CONTROLS for n in BULLET.findall(k))]
    assert len(named) >= 2, named


#: THE BACKLOG THIS TEST FOUND ON ITS FIRST RUN, and did not fix.
#:
#: Twenty-one more of the same fault, in eleven languages, in windows this
#: branch was not asked to touch — Create Chart's patch editor, the build-
#: anyway windows, the Delete window. They are pinned by (language, English
#: control) rather than silenced, so that a NEW one fails immediately while
#: these wait for a translator. Every entry here is a message telling somebody
#: to press a button that is not there.
#:
#: Fixing one = correct the catalogue VALUE so the bullet names the control,
#: and delete its line. The list may only shrink; `test_the_backlog_only_
#: shrinks` is what makes that true.
KNOWN_DRIFTS: "set[tuple[str, str]]" = {
    ('de', 'Add a single colour'),
    ('de', 'Build anyway'),
    ('de', 'Cancel and keep the current chart files'),
    ('de', 'Delete the whole project'),
    ('de', 'Generate colour sets'),
    ('es', 'Delete the whole project'),
    ('it', 'Build here anyway'),
    ('it', 'Delete the whole project'),
    ('ja', 'Generate colour sets'),
    ('nl', 'Build anyway'),
    ('nl', 'Build here anyway'),
    ('no', 'Add a single colour'),
    ('pl', 'Add a single colour'),
    ('pl', 'Build anyway'),
    ('pt', 'Add a single colour'),
    ('pt', 'Delete the whole project'),
    ('pt', 'Generate colour sets'),
    ('ru', 'Generate colour sets'),
    # Latin "OK" where the button carries Cyrillic "ОК" — invisible on paper
    # and a different string to every check we have.
    ('ru', 'OK'),
    ('sv', 'Generate colour sets'),
    ('zh_CN', 'Add a single colour'),
}


def test_the_backlog_only_shrinks():
    """A pinned drift is a debt, not a licence. 21 on 2026-09-05."""
    assert len(KNOWN_DRIFTS) <= 21, (
        "a drift was pinned rather than fixed — correct the catalogue value "
        "so the bullet names the control, instead of adding a line here")


@pytest.mark.parametrize("code", LANGS)
def test_a_bullet_names_its_control_the_way_that_control_reads(code):
    cat = _catalogue(code)
    bad = []
    for key, value in cat.items():
        if key.startswith("@") or BUL not in key:
            continue
        en_names = BULLET.findall(key)
        if not en_names:
            continue
        loc_names = BULLET.findall(value)
        if len(loc_names) != len(en_names):
            # A translation that restructured the list is a separate problem
            # and not this test's to judge.
            continue
        for en_name, loc_name in zip(en_names, loc_names):
            if en_name not in CONTROLS:
                continue                    # not a control we can vouch for
            want = cat.get(en_name)
            if want is None:                # the guard in test_i18n owns this
                continue
            if loc_name != want and (code, en_name) not in KNOWN_DRIFTS:
                bad.append(
                    f"  the bullet says {loc_name!r}, the control reads "
                    f"{want!r}\n    (English control {en_name!r}, in the "
                    f"message beginning {key[:60]!r})")
    assert not bad, (
        f"{code}: a message names a control the user cannot find:\n"
        + "\n".join(bad))
