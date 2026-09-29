"""The ready-made "by Pharmacist" charts are absent from "Load setup from
preset", and the tooltip now says so.

Knut asked why they were not listed. They arrived as finished patch-set files
with no design behind them, so there is no setup to load — but nothing on
screen said that, and a list that silently omits eleven charts reads as a fault.
Basti chose a sentence in the tooltip over listing them greyed, on the grounds
that eleven permanently dead entries make the list worse.

B8-1702 (4.3.2): since 4.3.1 thirteen of the fourteen "by Pharmacist" charts
carry a design and ARE listed, so a sentence naming them as absent was false.
It now names what is absent: a preset with a layout but no editor setup
(Knut, #182 5879221943).
"""
import pytest

pytestmark = pytest.mark.usefixtures("qapp")


def test_no_prebuilt_chart_offers_a_setup_to_load(prebuilt_bundles):
    """The invariant the sentence describes. If a prebuilt chart ever DOES
    carry a recipe this must fail, because the tooltip would then be lying.
    None ships since 4.3.1, so it is held on the four withdrawn bundles."""
    from ui.tabs.tab_chart import PREBUILT_PRESETS, builtin_recipe_choices

    names = {v[1] for v in PREBUILT_PRESETS.values()}
    assert names, "no prebuilt presets found — this test would prove nothing"
    overlap = set(builtin_recipe_choices()) & names
    assert not overlap, (
        f"a ready-made chart now offers a setup to load: {sorted(overlap)}. "
        "Either it should be listed, or the tooltip's explanation is wrong.")


def test_the_tooltip_explains_the_absence():
    """Named elements only: "Presets" is a real QGroupBox label on the Create
    Chart tab, so it can be quoted. The count is deliberately NOT in the
    sentence — "nine" would rot the day a tenth chart is added.

    Read from the CATALOGUE of translatable strings rather than by scanning
    source text, which found an unrelated comment with the same words.
    """
    import json
    import pathlib as _p

    en = _p.Path(__file__).resolve().parent.parent / "data" / "i18n" / "de.json"
    keys = json.loads(en.read_text(encoding="utf-8"))
    tip = next((k for k in keys
                if k.startswith("Load the full New-chart setup")), None)
    assert tip, "the 'Load setup from preset' tooltip is not a translatable string"

    assert "by Pharmacist" not in tip, (
        "the tooltip says the by Pharmacist charts are not listed, and since "
        "4.3.1 all but one of them are (B8-1702)")
    assert "layout but no editor setup" in tip, (
        "the tooltip does not say which presets it leaves out")
    assert "no setup behind it" in tip, (
        "the tooltip does not say WHY they are absent")
    assert "Presets" in tip, "it does not say where to find them instead"
    for rotting in (" nine ", " ten ", " eight "):
        assert rotting not in tip, (
            f"the tooltip hard-codes a count ({rotting.strip()!r}); it would be "
            "silently wrong the day a chart is added or removed")


def test_a_preset_with_a_layout_and_no_editor_setup_is_what_is_absent():
    """B8-1702: what the tooltip's last paragraph claims. The one built-in
    whose row says "Layout, but no editor setup" (the TC3.00 Target by
    Pharmacist) has no setup to load, and the other "by Pharmacist" built-ins,
    which the old sentence called absent, do."""
    from ui.tabs.tab_chart import KNUT_PRESETS, builtin_preset_recipe
    layout_only = [p for p in KNUT_PRESETS if p.layout_only]
    assert layout_only, "no layout-only preset, so this test proves nothing"
    for p in layout_only:
        assert builtin_preset_recipe(p.key) is None, p.name
    listed = [p for p in KNUT_PRESETS
              if "Pharmacist" in p.name and not p.layout_only]
    assert listed
    for p in listed:
        assert builtin_preset_recipe(p.key) is not None, p.name


def test_the_tooltip_does_not_say_the_list_is_empty_while_built_ins_fill_it(qapp):
    """The middle paragraph said the list "stays empty (just "None") until you
    save one". The built-in presets that carry a setup are listed first, with a
    ★, so on a fresh install the list is never empty (found with B8-1702)."""
    import json
    import pathlib as _p
    from ui.dialogs.ti2_relayout_dialog import _NewChartDialog

    de = _p.Path(__file__).resolve().parent.parent / "data" / "i18n" / "de.json"
    tip = next(k for k in json.loads(de.read_text(encoding="utf-8"))
               if k.startswith("Load the full New-chart setup"))
    assert "stays empty" not in tip, tip
    assert "built-in ones, marked ★" in tip, tip
    listed = _NewChartDialog._available_preset_recipes(
        type("S", (), {"_settings": None})())
    assert any(n.startswith("★ ") for n in listed), (
        "no built-in preset is offered, so the tooltip's claim is false")


def test_every_translation_calls_a_preset_by_its_own_catalogue_word():
    """Challenge round 4.3.2: each paragraph of the English help speaks of
    presets, and each translation must use the word its catalogue gives
    "Preset" everywhere else. The Ukrainian one called them "попереднім
    налаштуванням" in the first paragraph and "стилі" (styles) in the
    rewritten second, and only "Пресет" in the third, so the one list the
    help is about had three names in one tooltip."""
    import json
    import pathlib as _p

    root = _p.Path(__file__).resolve().parent.parent / "data" / "i18n"
    checked = 0
    for f in sorted(root.glob("*.json")):
        cat = json.loads(f.read_text(encoding="utf-8"))
        key = next((k for k in cat if k.startswith("Load the full New-chart setup")),
                   None)
        if key is None or not cat.get("Preset"):
            continue
        word = cat["Preset"].lower()[:5]
        paras = cat[key].lower().split("\n\n")
        assert len(paras) == len(key.split("\n\n")), f.name
        for i, para in enumerate(paras, 1):
            assert word in para, (
                f"{f.name}: paragraph {i} of the Load setup help does not call a "
                f"preset {cat['Preset']!r}: {para!r}")
        checked += 1
    assert checked >= 13, checked
