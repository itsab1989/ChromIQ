You are translating the ChromIQ printer-profiling app (PyQt6, repo at /Users/Basti/develop/ChromIQ) into {LANGNAME} (code "{CODE}"). German is already done and is your reference for conventions.

PRODUCE EXACTLY TWO FILES (do not touch anything else, do not commit):
1. data/i18n/{CODE}.json — translation catalog. Keys = the EXACT English source strings (the same keys as data/i18n/de.json — copy the key set from there). First entry: "@language_name": "{NATIVE}". Translate from the ENGLISH key; use the German VALUE only as a reference for tone, terminology choices and how lengths were handled.
2. data/i18n/parameters.{CODE}.yaml — overlay translating data/parameters.yaml. Mirror the exact structure of data/i18n/parameters.de.yaml ({tool: {"-flag": {name, tooltip_title, tooltip_body, labels?}}}). Every parameter must have name/tooltip_title/tooltip_body (when present in source); every labels list must have exactly the same number of entries as the source.

STYLE (hard requirement from the app's author): ChromIQ's texts are extensive, friendly and easy to understand — written for beginners, leading with plain-language outcomes and concrete prerequisites. PRESERVE ALL INFORMATION; never shorten or summarize the long tooltips/help texts. Use the informal address that modern consumer software uses in {LANGNAME} (German uses Du-Form). Be consistent: define your terminology once (equivalents for patch→(German used "Messfeld"), strip/stripe→("Streifen"), spacer→("Trennfeld"), chart, target, measurement, instrument="Messgerät" etc.) and stick to it everywhere. Keep established technical terms (ICC, gamut, RGB, ΔE, OFPS, tool names like targen/printtarg/chartread/colprof) untranslated where the colour-management community does.

HARD RULES:
- {placeholders} must be preserved EXACTLY, including format specs like {limit:.1f} — they are part of the key and verified by tests.
- "&&" stays "&&" (Qt escape). HTML markup (<b>, <br>, &nbsp;, <span style=…>) preserved exactly.
- CLI flags (-d, -G, printtarg -i…), file extensions, file-filter patterns like "(*.ti3);;…" stay untouched; translate only the descriptive words in filters.
- Singular/plural keys are separate full sentences ("1 patch selected." vs "{n} patches selected.") — translate each naturally.
- EVERY bracketed log tag stays in English, not just the common four: [INFO]/[OK]/[WARNING]/[ERROR]/[NOTE]/[STOPPED]/[BUSY]/[Report]/[Engine]. One log that prints [ERROR] beside [WARNUNG] looks broken.
- The dash is your language's dash. German, Norwegian and Polish take the en dash (–) with spaces; Japanese, Chinese and Russian take the em dash (—). Do not convert a language onto another language's dash, even if told to: measure your own catalogue first.
- SHORT strings (≤24 chars, no newline, no {) are buttons/labels: your translation must satisfy len ≤ len(english)*1.6 + 6 (CI-enforced). Choose compact native wordings, never ugly abbreviations.
- Parameter NAMES in the yaml must fit a 190px label column (tighter for expert rows). After writing the yaml, run the checker and shorten any offender (keep tooltip_title at full length — only the name needs to be compact).

WORKFLOW (do it in batches; write the json by merging part-files so no single write is huge):
1. Read data/i18n/de.json (keys + German reference) and data/parameters.yaml + data/i18n/parameters.de.yaml.
2. Translate the catalog in batches of ~60-80 keys; merge each batch into data/i18n/{CODE}.json (sorted keys, "@language_name" first, ensure_ascii=False, indent=1).
3. Write parameters.{CODE}.yaml.
4. VALIDATE — all of these must pass before you finish:
   source .venv/bin/activate
   python scripts/i18n_extract.py --stats {CODE}        # must say 100.0% and 0 stale
   QT_QPA_PLATFORM=offscreen pytest tests/test_i18n.py -q   # all pass
   QT_QPA_PLATFORM=offscreen python scripts/i18n_check_name_widths.py {CODE}  # 0 over budget
   python -c "import yaml; yaml.safe_load(open('data/i18n/parameters.{CODE}.yaml'))"
5. Fix anything that fails. Report: counts, the terminology glossary you chose, and any judgment calls.
