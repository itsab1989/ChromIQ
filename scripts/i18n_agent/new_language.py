#!/usr/bin/env python3
"""Generate the translation-agent prompt for a new ChromIQ language.

Usage:
    python scripts/i18n_agent/new_language.py <code> "<English name>" "<Native name>"
    e.g. python scripts/i18n_agent/new_language.py fr French "Français"

Prints the fully substituted prompt to stdout (pipe it into a file or feed
it to an agent). The agent must produce data/i18n/<code>.json and
data/i18n/parameters.<code>.yaml and self-validate with:

    python scripts/i18n_extract.py --stats <code>                       # 100%, 0 stale
    QT_QPA_PLATFORM=offscreen pytest tests/test_i18n.py -q              # all green
    QT_QPA_PLATFORM=offscreen python scripts/i18n_check_name_widths.py <code>

A partial catalog in data/i18n/staging/<code>.partial.json (if present)
should be used as the starting point instead of translating from scratch.
The tests in tests/test_i18n.py automatically cover any new catalog the
moment the .json lands in data/i18n/ — no test changes needed.
"""
import sys
from pathlib import Path

if len(sys.argv) != 4:
    print(__doc__)
    raise SystemExit(2)

code, langname, native = sys.argv[1:4]
template = (Path(__file__).parent / "prompt_template.md").read_text(encoding="utf-8")
prompt = (template.replace("{CODE}", code)
                  .replace("{LANGNAME}", langname)
                  .replace("{NATIVE}", native))
staging = Path(__file__).resolve().parents[2] / "data" / "i18n" / "staging" / f"{code}.partial.json"
if staging.exists():
    prompt += (f"\n\nHEAD START: a partial catalog already exists at {staging} "
               "— copy it as your staging base, review its entries for "
               "consistency with your glossary, then translate the remaining keys.\n")
print(prompt)
