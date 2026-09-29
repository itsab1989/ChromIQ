# -*- coding: utf-8 -*-
"""Correct the Ukrainian strings whose current wording means something else.

Each entry is (key, was, now, why). "why" is the control the string labels,
established by reading the call site, plus what the other twelve catalogues do,
which were checked and are correct on every one of these.
"""
import json, pathlib, sys

FIXES = [
 # -- position words. The call sites are the four page margins
 #    (settings_dialog "L"/"R"/"T"/"B") and the index alignment and clip side
 #    in layout_options_panel. Every other language uses a position word;
 #    "Left" was already correct as an adverb, so the other three match it.
 ("Right",  "правильно", "Праворуч",  "the RIGHT page margin, not 'correctly'"),
 ("Top",    "Топ",       "Зверху",    "the top margin, not 'top-rated'"),
 ("Bottom", "Дно",       "Знизу",     "the bottom margin, not a sea bed"),

 # -- tab_chart gamut margin combo: 'Stay safely inside' / 'Use the full
 #    printable range'. A reserve left inside the gamut, not a profit margin.
 ("Margin", "Маржа", "Запас", "the gamut margin, not a financial margin"),

 # -- the appearance combo. Dark and Neutral are already masculine adjectives
 #    there, so Light matches them rather than standing as a bare noun.
 ("Light", "світло", "Світлий", "the Light THEME, beside Темний and Нейтральний"),

 # -- tools_dialogs RUN_LABEL, a button beside Average / Merge / Convert, so
 #    an imperative verb. Every other language has a verb here.
 ("Run", "бігти", "Запустити", "the Run BUTTON, not 'to run' on foot"),

 # -- a measurement strip. 'Газа' is gauze, the fabric.
 ("Strip", "Газа", "Смуга", "a measurement strip; the rest of the catalogue already says смуга"),

 # -- 'Гамма' is GAMMA, a different thing ChromIQ also has. The transliterated
 #    term is what de, fr, it, nl, no and pl use.
 ("Gamut", "Гамма", "Гамут", "colour gamut, not gamma"),
 ("Colorimetric gamut (-nP / -nS):", "Колориметрична гамма (-nP / -nS):",
  "Колориметричний гамут (-nP / -nS):", "same: gamut, not gamma"),

 # -- tools_dialogs RUN_LABEL for the verification tool: check, not confirm.
 ("Verify", "Підтвердити", "Перевірити", "verify a print against its profile"),

 # -- scanin_dialog page label: the printed target itself. ru says Мишень.
 ("Target", "Цільова", "Мішень", "the printed target; 'Цільова' is a dangling adjective"),

 # -- 'Предустановки' is Russian orthography. The singular is already Пресет.
 ("Presets", "Предустановки", "Пресети", "matches the existing Пресет"),

 # -- keyboard card. 'Космос' is outer space; and the Latin R key became
 #    Cyrillic Er, so the card named a key that is not on the keyboard.
 ("Space  ·  R", "Пробіл · Р", "Пробіл · R", "the Latin R key"),
 ("Space  ·  {enter}", "Космос · {enter}", "Пробіл · {enter}", "the SPACE BAR, not outer space"),
 ("Enter", "Введіть", "Введення", "the Enter key as a noun, like ru Ввод and de Eingabe"),
 ("Key", "ключ", "Клавіша", "a keyboard key, not a door key"),
 ("Shortcut", "Ярлик", "Комбінація клавіш", "a key combination, not a desktop icon"),

 # -- the measurement engine. 'двигун' is a motor.
 ("Which engine", "Який двигун", "Який рушій", "the measurement engine"),
 ("Both engines", "Обидва двигуни", "Обидва рушії", "the measurement engine"),
 ("ChromIQ engine", "Двигун ChromIQ", "Рушій ChromIQ", "the measurement engine"),

 # -- a Preferences tab title left in English.
 ("Licences", "Licences", "Ліцензії", "was never translated"),

 # -- the two mode switches. Every other language uses an adjective; these
 #    were nouns, and the wrong nouns: a manager, and an instruction booklet.
 ("GUIDED", "КЕРІВНИК", "ПОКРОКОВИЙ", "guided mode, matching ru ПОШАГОВЫЙ"),
 ("MANUAL", "ІНСТРУКЦІЯ", "РУЧНИЙ", "manual mode, matching ru РУЧНОЙ"),

 # -- the welcome subtitle: informal 'ти' AND a feminine verb, so a male user
 #    read a sentence addressed to a woman. The only string of 6,016 using ти.
 ("What would you like to do?", "Що б ти хотіла зробити?", "Що б ви хотіли зробити?",
  "formal ви and gender-neutral, like every other string"),

 # -- 'Тотальні' is the wrong sense of total.
 ("Total patches", "Тотальні патчі", "Усього патчів", "a count, not 'totalitarian'"),

 # -- the app's central noun, spelled патч everywhere else in this catalogue.
 ("Patch set", "Набір латок", "Набір патчів", "patch, not a cloth patch"),

 # -- lowercase where the English capitalises a control label.
 ("Save", "зберегти", "Зберегти", "a button label"),
 ("Fast", "швидко", "Швидко", "an option label"),
 ("Resolution", "роздільна здатність", "Роздільна здатність", "a field label"),
 ("Scale", "масштаб", "Масштаб", "a field label"),
]

p = pathlib.Path("data/i18n/uk.json")
d = json.loads(p.read_text(encoding="utf-8"))
applied, skipped = [], []
for key, was, now, why in FIXES:
    cur = d.get(key)
    if cur is None:
        skipped.append((key, "ABSENT", why)); continue
    if cur != was:
        skipped.append((key, f"expected {was!r} found {cur!r}", why)); continue
    d[key] = now
    applied.append((key, was, now, why))

if "--apply" in sys.argv:
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print(f"{len(applied)} applied, {len(skipped)} skipped\n")
for k, w, n, why in applied:
    print(f"  {k!r}\n      {w!r} -> {n!r}   ({why})")
if skipped:
    print("\nSKIPPED:")
    for k, r, why in skipped:
        print(f"  {k!r}: {r}")
