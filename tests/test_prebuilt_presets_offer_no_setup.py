"""The ready-made "by Pharmacist" charts are absent from "Load setup from
preset", and the tooltip now says so.

Knut asked why they were not listed. They arrived as finished patch-set files
with no design behind them, so there is no setup to load — but nothing on
screen said that, and a list that silently omits nine charts reads as a fault.
Basti chose a sentence in the tooltip over listing them greyed, on the grounds
that nine permanently dead entries make the list worse.
"""
import pytest

pytestmark = pytest.mark.usefixtures("qapp")


def test_no_prebuilt_chart_offers_a_setup_to_load():
    """The invariant the sentence describes. If a prebuilt chart ever DOES
    carry a recipe this must fail, because the tooltip would then be lying."""
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

    assert "by Pharmacist" in tip, (
        "the tooltip does not mention the charts it leaves out")
    assert "already laid out" in tip or "no setup" in tip.lower(), (
        "the tooltip does not say WHY they are absent")
    assert "Presets" in tip, "it does not say where to find them instead"
    for rotting in (" nine ", " ten ", " eight "):
        assert rotting not in tip, (
            f"the tooltip hard-codes a count ({rotting.strip()!r}); it would be "
            "silently wrong the day a chart is added or removed")
