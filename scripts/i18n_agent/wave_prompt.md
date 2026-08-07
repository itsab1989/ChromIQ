# Translation-wave prompt (one language per agent)

Substitute `{CODE}` and `{LANGUAGE}`, then hand the whole thing to one agent.
Three agents at a time, one language each — they never share a file, so they
cannot collide.

This exists because the guardrails below were each learned by something going
wrong, and hand-writing the prompt per wave is how one of them gets left out.
`prompt_template.md` next to this file is the different job of standing up a
**new** language from nothing; this one tops up an existing catalogue.

---

You are completing the {LANGUAGE} (`{CODE}`) translation catalogue for ChromIQ,
a PyQt6 printer-profiling app, repo at /Users/Basti/develop/ChromIQ.

## Your one file

Edit ONLY `data/i18n/{CODE}.json`. Do not touch any other language, any source
code, `data/i18n/parameters.*.yaml` (already complete for every language), or
anything in `data/i18n/staging/` — those partials are already merged, 120 of
their keys are stale, and re-merging them would undo terminology fixes. There is
a README in that folder explaining it. Do not run git. Do not commit.

## What to do

Fill every PLACEHOLDER — an entry whose value is byte-identical to its key:

```python
import json, pathlib
j = json.loads(pathlib.Path("data/i18n/{CODE}.json").read_text())
ph = [k for k in j if not k.startswith("@") and j[k] == k]
```

**Never overwrite an entry that is already translated.** Only change entries
where value == key.

The volume is concentrated in long texts: the ~287 short labels are about 2.3%
of the work, while ~77 help texts over 500 characters are 45% of it. Do not
rush the long ones — they are what a beginner actually reads.

Some placeholders are CORRECT as they are and must stay identical: tool names
(`targen`, `colprof`, `chartread`, `printtarg`, `scanin`), colour spaces
(`sRGB`, `Adobe RGB (1998)`, `CIE L*a*b*`), units (`mm`, `Hz`, `dpi / ppi`), key
names (`Ctrl`, `Alt`, `Shift`), symbols (`ΔE`, `L*`, `a*`, `b*`, `—`) and
instrument names (`i1Pro 3`). Leaving those identical is the right answer, not a
gap.

## Skip exactly one key

The string starting `"You've unlocked the patch-recipe (targen) settings for
this preset."` is pending a rewording decision. Leave it as a placeholder.

## Style

Extensive, friendly, easy for a beginner, leading with the plain-language
OUTCOME and the PREREQUISITE. **Preserve all information — never shorten or
summarise a long help text.** Use the informal address modern consumer software
uses in {LANGUAGE}.

**THE FILE OUTRANKS ANY GLOSSARY IN THIS BRIEF.** If a term here disagrees with
what the catalogue already uses consistently, follow the catalogue and say so in
your report. This is not hypothetical: the Italian brief said spacer =
*separatore*, carried over from Dutch without checking, when the file had long
since settled spacer = *spaziatore* (44 entries) and reserved *separatore* for
English "separator" (3 entries) — a real distinction between two different
things that the brief would have collapsed.

**Read the translations already in the file and follow them.** The catalogue is
~76% done, so the terminology is already decided — do not invent a second word
for something that has one. German (`data/i18n/de.json`) is the tone reference;
translate from the ENGLISH key, using German only to judge register and length.

## Hard rules

- `{placeholders}` preserved EXACTLY, including specs like `{limit:.1f}`. Never
  translate the text inside braces — `{patches}` is a variable name.
- HTML (`<b>`, `<br>`, `&nbsp;`) preserved exactly. Angle brackets around
  ordinary words — `<chart name>` — are prose the user reads: translate those.
- Log prefixes `[INFO]` `[OK]` `[WARN]` `[ERROR]` stay in English. Every
  language had two strings that translated them and sixteen that did not, so one
  log printed two different tags. Do not reintroduce that.
- CLI flags, file extensions and file-filter patterns `"(*.ti3);;…"` untouched.
- Newlines `\n` preserved — these texts are laid out deliberately.
- Singular and plural are separate keys; translate each naturally, never "(s)".
- SHORT strings (≤24 chars, no newline, no `{`):
  `len(translation) <= len(english)*1.6 + 6`. **Check before writing, not after.**

## File format

`json.dumps(j, ensure_ascii=False, indent=2) + "\n"`, `"@language_name"` first.
**indent=2 is the repo standard** — writing indent=1 once turned 154 real
changes into an 8,186-line diff. Work in batches of ~60–80 keys, merging as you
go, so progress survives an interruption.

## Validate — but DO NOT RUN pytest

`pytest` constructs the real `AppSettings` and writes to the developer's own
preferences. The orchestrator runs the suite.

```bash
source .venv/bin/activate
python scripts/i18n_extract.py --stats {CODE}                              # 100.0%, 0 stale
QT_QPA_PLATFORM=offscreen python scripts/i18n_check_name_widths.py {CODE}  # 0 over budget
python scripts/i18n_verify_batch.py {CODE}                                 # 0 issues
```

`i18n_verify_batch.py` is the acceptance check: HTML parity, placeholder parity,
the length budget, glossary drift and log-prefix consistency.

## Report back

How many you translated, how many you left identical and why, the terminology
you settled on, anything you were unsure about, and the exact output of the
three commands. If you cannot finish, say exactly how many remain — a validated
partial file is fine and expected.
