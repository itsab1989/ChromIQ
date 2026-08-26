"""No help card wastes a sheet — in any of the thirteen languages.

`tests/test_helpcard_blank_letter_sheet.py` asserts this in English. It was
written for a real defect (beta.15: three cards printed a sheet carrying only
the running header, the page number and the colophon) and it locked that defect
down — in one language out of thirteen.

German runs 122 % of English's length, Dutch and Italian 114 %, so a card that
just fits in English need not fit anywhere else. This module asks the same
structural question of every language: **is there a sheet whose body band
carries the colophon and nothing else?**

Today the answer is no, 0 of 1350 sheets — because `ui.pdf_layout.
drop_orphan_tail` pulls that lone line into the footer band. Disable it and 19
such sheets appear, three of them in English. That mutation is what makes this
test worth running; see the control below.

WHY THE CENSUS BELOW IS NOT A GATE. A sheet carrying ONE short line plus the
colophon is nearly as wasteful, and 13 of them exist at the 15 mm margins this
file prints at. They are not gated because **the list is a function of the page
geometry, not of the translations**: re-rendered at 10 mm the set is disjoint
and English acquires an offender (`keyboard_shortcuts/A4`); at 20 mm English has
two (`first_profile/A4`, `getting_started/A4`) and most of the 15 mm list is
gone. A real printer driver does not hand you 15 mm. Gating on that list would
fail on the next margin change while saying nothing about the defect. Nor can
`drop_orphan_tail` help: removing the colophon leaves the orphan line holding
the sheet anyway.

Slow — the language must be set BEFORE `ui.dialogs.welcome_dialog` is imported,
because WORKFLOWS is materialised at import time out of `tr()`. So one
subprocess per language.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_LANGS = ("en", "de", "fr", "sv", "ja", "nl", "es",
          "it", "pt", "no", "pl", "ru", "zh_CN")

#: Rendered in a child process, one language at a time. Prints one JSON line.
_CHILD = r'''
import json, os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, %(root)r)
import core.i18n as i18n
i18n.set_language(%(lang)r)                    # BEFORE the import below
from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from ui.dialogs.welcome_dialog import WORKFLOWS
from core.version import APP_VERSION
sys.path.insert(0, %(tests)r)
import test_helpcard_blank_letter_sheet as H
import ui.pdf_layout as pdf_layout
if %(disable_rule)r:
    pdf_layout.drop_orphan_tail = lambda *a, **k: None
import tempfile, pathlib
tmp = pathlib.Path(tempfile.mkdtemp())
only_colophon, thin = [], []
for wf in WORKFLOWS:
    for size in ("A4", "Letter"):
        pdf, pages, pr = H._print_card(wf["key"], size, tmp)
        for i, body in enumerate(H._body_band_text(pdf, pr)):
            flat = " ".join(body.split())
            if not flat:
                continue
            if flat.startswith("ChromIQ " + APP_VERSION):
                only_colophon.append(f"{wf['key']}/{size} sheet {i+1}/{pages}")
            else:
                rest = flat.split("ChromIQ " + APP_VERSION)[0].strip()
                if rest and len(rest) <= 60:
                    thin.append(f"{wf['key']}/{size} sheet {i+1}/{pages}: {rest[:48]!r}")
print("@@" + json.dumps({"only_colophon": only_colophon, "thin": thin}))
'''


def _render(lang: str, *, disable_rule: bool = False) -> dict:
    code = _CHILD % {"root": str(_ROOT), "tests": str(_ROOT / "tests"),
                     "lang": lang, "disable_rule": disable_rule}
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True, timeout=300, env=env, cwd=str(_ROOT))
    line = next((l for l in out.stdout.splitlines() if l.startswith("@@")), None)
    assert line, f"{lang}: child produced no result\n{out.stdout[-2000:]}\n{out.stderr[-2000:]}"
    return json.loads(line[2:])


# ONE TEST PER LANGUAGE, NOT ONE TEST OVER THIRTEEN. Rendering all thirteen in
# a single test takes ~2 minutes, and `pytest.ini` sets `faulthandler_timeout =
# 90`: the run dumps every thread's traceback to stderr and prints
# "Timeout (0:01:30)!" while nothing is wrong — the test is simply inside
# `subprocess.run`. A release-gate log that says "Timeout!" invites exactly the
# wrong conclusion. Split, each case is ~12 s, and a failure names its language
# instead of hiding in a list.
@pytest.mark.slow
@pytest.mark.parametrize("lang", _LANGS)
def test_no_language_prints_a_sheet_carrying_only_the_colophon(lang):
    res = _render(lang)
    if res["thin"]:
        # A census, NOT a gate — see the module docstring. The list is a
        # function of the page geometry, not of the translations.
        print(f"\nCENSUS [{lang}] {len(res['thin'])} sheet(s) carrying one "
              "short line besides the colophon:")
        for t in res["thin"]:
            print("   ", t)
    assert not res["only_colophon"], (
        f"{lang}: these sheets carry the colophon and nothing else:\n  "
        + "\n  ".join(res["only_colophon"]))


#: Languages that produce a colophon-only sheet once `drop_orphan_tail` is
#: switched off, measured 2026-08-26: en 3, nl 2, pl 2, fr 1, ja 1.
#: NOT every language does — German has none, because its longer text always
#: spills real content onto the last page. The first version of this control
#: asked German and failed, which is the control working: a mutation has to be
#: proven to land in the language you assert it in.
_MUTATION_LANDS_IN = ("en", "nl")


@pytest.mark.slow
def test_the_orphan_rule_is_what_keeps_that_true_in_other_languages():
    """THE CONTROL. Without it the test above passes whether the rule works or
    not — which is exactly how a sibling test in this project stayed green for
    weeks while the behaviour it named was broken.

    Two languages, not thirteen: running the whole matrix twice costs four
    minutes and proves nothing the pair does not.
    """
    for lang in _MUTATION_LANDS_IN:
        res = _render(lang, disable_rule=True)
        assert res["only_colophon"], (
            f"{lang}: disabling drop_orphan_tail produced no colophon-only "
            "sheet, so the assertion in the test above is measuring nothing")
