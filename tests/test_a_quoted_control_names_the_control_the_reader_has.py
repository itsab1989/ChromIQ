"""A help card that quotes a control must quote the control the reader HAS.

The 4.2.0 translation pass turned up `ui/file_guide.py`'s `cal/old/` row, which
tells you that printcal's “Re-calibrate” and “Verify” modes compare against an
earlier `.cal`. Both are real controls: the Mode combo of Create Calibration
File offers `Re-calibrate  (refine existing .cal)` and
`Verify  (check against existing .cal)`. **Ten of the twelve catalogues left
those two words in English**, so a German reader was told, in German, to look
for a control that reads `Nachkalibrieren` on screen, and a Russian one for
`Перекалибровать`. Confirmed in a running window before it was fixed.

Nothing caught it, and nothing could: the quotation lives inside a 577-character
help string, so `--missing` and `--stale` see a fully translated key, and the
budget counters see a value that is not identical to its key. This file is the
check that was missing.

**The rule.** Take every phrase an English string quotes in ChromIQ's own curly
quotes. If that phrase names a control the app actually has, and a language
translates that control, then that language's version of the help string must
not still be quoting the English word.

Three deliberate limits, because a checker that cries wolf gets switched off:

* **Curly quotes only.** ChromIQ quotes its own controls with `“ ”` (and each
  language's own marks). Straight `"` is used for the printer driver's words —
  `"No Color Management"`, `"Color Options"`, `"Off"` — which must stay exactly
  as the driver spells them, in every language. Including straight quotes turned
  those into six false alarms.
* **A quoted phrase must be quoted in the translation too.** Matching the bare
  substring made French `« Calibration du projet »` look like an untranslated
  `“Calibration”`, and German prose using the loanword *Presets* look like the
  `Presets` label. Both are fine; neither is this fault.
* **Capitalised, three characters or more.** `“chart”`, `“run”`, `“white”` and
  `“patches”` are ordinary words this app also happens to have as keys, and
  they are quoted in prose all over the help. 131 hits become 24 real ones.

What this cannot see: a label named in running prose without quotation marks,
and a quotation of a `data/parameters.yaml` row (those live in a separate
`parameters.<code>.yaml` overlay, not in the `.json` catalogue). The German
`„Single Channel Steps“` fault was of the second kind and was fixed by hand.
"""
from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
I18N = ROOT / "data" / "i18n"

#: ChromIQ's own quotation marks, and the ones its catalogues use. Straight `"`
#: is deliberately absent: see the module docstring.
OPEN = "“„«‘"
CLOSE = "”“»’"
QUOTED = re.compile(f"[{OPEN}{CLOSE}]\\s*([^{OPEN}{CLOSE}\n]{{2,60}}?)\\s*"
                    f"[{CLOSE}{OPEN}]")

#: Quotations this repo has already been bitten by. Each must keep resolving to
#: a real control, so renaming the control fails here rather than silently
#: leaving the help card pointing at a name nobody can find.
PINNED = {
    "Re-calibrate": "Re-calibrate  (refine existing .cal)",
    "Verify": "Verify",
    "New run": "New run",
    "Side": "Side:",
    "Off": "Off",
    "Also save scanner-profiling files for this chart":
        "Also save scanner-profiling files for this chart",
}


def _codes():
    return sorted(p.stem for p in I18N.glob("*.json")
                  if not p.stem.startswith("parameters"))


def _catalogue(code):
    return json.loads((I18N / f"{code}.json").read_text(encoding="utf-8"))


def _quotations(text):
    return set(QUOTED.findall(text))


def _control_key(phrase, keys):
    """The catalogue key this quotation names, if the app has one.

    A control is quoted by its NAME, while the key can carry an aligned
    parenthetical (`Re-calibrate  (refine existing .cal)`) or a row colon
    (`Side:`). One candidate or none; an ambiguous prefix names nothing.
    """
    if phrase in keys:
        return phrase
    for suffix in ("  (", " (", ":"):
        found = [k for k in keys
                 if k.startswith(phrase + suffix) and len(k) < len(phrase) + 45]
        if len(found) == 1:
            return found[0]
    return None


def _offenders(catalogues):
    english = set(catalogues["de"])
    out = []
    for key in english:
        if key.startswith("@"):
            continue
        for phrase in _quotations(key):
            if len(phrase) < 3 or not phrase[:1].isupper():
                continue
            control = _control_key(phrase, english)
            if control is None or len(control) > 60:
                continue
            for code, cat in catalogues.items():
                label = cat.get(control, control)
                if phrase.lower() in label.lower():
                    continue                  # this language keeps it English
                if phrase in _quotations(cat.get(key, "")):
                    out.append((code, phrase, label, key))
    return sorted(out)


def test_no_translation_quotes_a_control_by_its_english_name():
    catalogues = {code: _catalogue(code) for code in _codes()}
    bad = _offenders(catalogues)
    assert not bad, (
        f"\n{len(bad)} help string(s) quote a control by its ENGLISH name in a "
        f"language that renames it:\n\n"
        + "\n".join(f"  [{code}] quotes “{phrase}”, but the control reads "
                    f"“{label}”\n      in: {key[:80]}…"
                    for code, phrase, label, key in bad[:10])
        + (f"\n  … and {len(bad) - 10} more" if len(bad) > 10 else "")
        + "\n\nTake the word from the control's own catalogue entry, so the "
          "help and the window cannot drift apart. If the quotation is the "
          "printer driver's own wording rather than a ChromIQ control, put it "
          "in straight quotes, which is what the rest of the app does.")


def test_every_pinned_quotation_still_names_a_real_control():
    """A rename must not turn a help card into a wild-goose chase.

    Renaming `Re-calibrate  (refine existing .cal)` would leave the folder
    guide quoting a control that no longer exists, in twelve languages at
    once, and the test above would go quietly green because there would be
    no control left to compare against.
    """
    english = set(_catalogue("de"))
    missing = {}
    for phrase, control in PINNED.items():
        found = _control_key(phrase, english)
        if found != control:
            missing[phrase] = found
    assert not missing, (
        "\n" + "\n".join(
            f"  “{p}” used to name {PINNED[p]!r}; it now resolves to {f!r}"
            for p, f in missing.items())
        + "\n\nA control was renamed. Update every help string that quotes it, "
          "in all twelve catalogues, and then update PINNED here.")


def test_the_detector_can_actually_see_the_fault_it_was_written_for():
    """Guard the guard, on the exact string that started this.

    Without this, tightening the quotation rules until nothing fires would
    look like success. It is run against a doctored copy of the catalogues, in
    memory, so it proves the detector rather than the data.
    """
    catalogues = {code: _catalogue(code) for code in _codes()}
    assert not _offenders(catalogues), "the real catalogues should be clean"

    guide = next(k for k in catalogues["de"]
                 if k.startswith("Earlier calibrations.")
                 and "printcal" in k)
    assert "“Re-calibrate”" in guide, \
        "the folder guide no longer quotes “Re-calibrate” — re-aim this test"

    doctored = {code: dict(cat) for code, cat in catalogues.items()}
    doctored["de"][guide] = doctored["de"][guide].replace(
        "„Nachkalibrieren“", "„Re-calibrate“")
    found = _offenders(doctored)
    assert [(c, p) for c, p, _l, _k in found] == [("de", "Re-calibrate")], (
        f"the detector did not see the very fault it exists for; it found "
        f"{found!r}")
