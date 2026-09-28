"""The four withdrawn prebuilt page-image bundles, registered for one test.

ChromIQ ships no prebuilt-files preset since 4.3.1: Knut withdrew the last four
"by Pharmacist" page images (#182 5875467209) for charts with a page layout. The
mechanism stays in ``ui/tabs/tab_chart.py`` (``PREBUILT_PRESETS``,
``_apply_prebuilt_preset``, ``_create_prebuilt_target``) and so do its tests,
which now build from the same bundles moved to ``tests/fixtures``.

The keys are the ones the four shipped under until 4.3.0, on purpose: a stored
tick, a stored selection or a project may still name them, and a test that uses
them is also a test of what such a key still does.

``register(monkeypatch)`` puts them back into every registry the tab reads
(``PREBUILT_PRESETS``, ``BUILTIN_PRESET_KEYS``, ``BUILTIN_PRESET_LABELS``,
``BUILTIN_PRESET_GROUPS``, ``PREBUILT_PRESET_NOTES``) for the length of the
test; ``monkeypatch`` takes them out again. The ``prebuilt_bundles`` fixture in
``tests/conftest.py`` does exactly that.
"""
from __future__ import annotations

FIXTURE_ROOT = "tests/fixtures/charts/prebuilt/pharmacist/rgb"

ABW702_KEY = "__chromiq_abw702_builtin__"
TC924_CM_A3_KEY = "__chromiq_tc924_cm_a3_builtin__"
PHOTOCARD600_KEY = "__chromiq_photocard600_builtin__"
PHOTOCARD648_KEY = "__chromiq_photocard648_builtin__"

ABW702_LABEL = "★  ColorMunki · A4-702p-2pages ABW-optimized by Pharmacist  ·  built-in"
TC924_CM_A3_LABEL = "★  ColorMunki · A3-924p-1page TC9.24 by Pharmacist  ·  built-in"
PHOTOCARD600_LABEL = "★  i1Pro · 10x15cm-600p-4pages by Pharmacist  ·  built-in"
PHOTOCARD648_LABEL = "★  i1Pro · 13x18cm-648p-3pages by Pharmacist  ·  built-in"

#: key -> (asset stem, default target name), exactly as 4.3.0 shipped them but
#: for the folder.
PREBUILT = {
    ABW702_KEY: (f"{FIXTURE_ROOT}/colormunki/a4/abw702/abw702",
                 "ColorMunki-A4-702p-2pages-ABW-optimized by Pharmacist"),
    TC924_CM_A3_KEY: (f"{FIXTURE_ROOT}/colormunki/a3/tc924/tc924",
                      "ColorMunki-A3-924p-1page-TC9.24 by Pharmacist"),
    PHOTOCARD600_KEY: (f"{FIXTURE_ROOT}/i1pro/100x150/photocard600/photocard600",
                       "i1Pro-100x150mm-600p-4pages-Portrait by Pharmacist"),
    PHOTOCARD648_KEY: (f"{FIXTURE_ROOT}/i1pro/130x180/photocard648/photocard648",
                       "i1Pro-130x180mm-648p-3pages-Portrait by Pharmacist"),
}

#: (group instrument, combo label, overlay label, key), in 4.3.0's order.
ROWS = [
    ("ColorMunki", ABW702_LABEL, "A4-702p-2pages ABW-optimized by Pharmacist", ABW702_KEY),
    ("ColorMunki", TC924_CM_A3_LABEL, "A3-924p-1page TC9.24 by Pharmacist", TC924_CM_A3_KEY),
    ("i1Pro", PHOTOCARD600_LABEL, "10x15cm-600p-4pages by Pharmacist", PHOTOCARD600_KEY),
    ("i1Pro", PHOTOCARD648_LABEL, "13x18cm-648p-3pages by Pharmacist", PHOTOCARD648_KEY),
]

PHOTOCARD_NOTE = (
    "This sheet is printed almost edge to edge, so a bordered print will\n"
    "trim the crop marks and some of the text at the edges. The patches\n"
    "sit far enough in to be measured either way. If your printer driver\n"
    "can print borderless with expansion turned off, use that; if it\n"
    "cannot, print with borders, because an enlarged chart is worse than\n"
    "trimmed crop marks."
)


def register(monkeypatch) -> dict:
    """Put the four bundles back into the tab's registries for this test."""
    from ui.tabs import tab_chart as TC
    prebuilt = dict(TC.PREBUILT_PRESETS)
    prebuilt.update(PREBUILT)
    monkeypatch.setattr(TC, "PREBUILT_PRESETS", prebuilt)
    monkeypatch.setattr(TC, "BUILTIN_PRESET_KEYS",
                        frozenset(TC.BUILTIN_PRESET_KEYS) | frozenset(PREBUILT))
    monkeypatch.setattr(TC, "BUILTIN_PRESET_LABELS",
                        frozenset(TC.BUILTIN_PRESET_LABELS)
                        | {r[1] for r in ROWS})
    notes = dict(TC.PREBUILT_PRESET_NOTES)
    notes[PHOTOCARD600_KEY] = notes[PHOTOCARD648_KEY] = PHOTOCARD_NOTE
    monkeypatch.setattr(TC, "PREBUILT_PRESET_NOTES", notes)
    groups = []
    for heading, entries in TC.BUILTIN_PRESET_GROUPS:
        mine = [(c, o, k) for g, c, o, k in ROWS
                if TC._group_heading(g) == heading]
        groups.append((heading, mine + list(entries)))
    monkeypatch.setattr(TC, "BUILTIN_PRESET_GROUPS", groups)
    return prebuilt
