"""4.3.24: the CR30's label in the instrument lists is its short model name,
as the guide asks of every instrument ("FD-9", not "FD-9 (Konica Minolta)"):
no "ChnSpec" in Guided's list, Manual's -i choice, the layout panel,
Preferences > Chart Layout or Tools > Read single patches. The files keep
naming the device as it names itself ("CR30"), and the (i) texts keep the
vendor, where it belongs."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def test_no_list_label_names_the_vendor():
    from data.patch_db import INSTRUMENT_LABELS
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    from ui.dialogs.settings_dialog import SettingsDialog
    assert INSTRUMENT_LABELS["CR30"] == "CR30"
    assert dict(LayoutOptionsPanel.INSTRUMENTS)["CR30"] == "CR30 (patch by patch)"
    assert dict(SettingsDialog._LAYOUT_INSTRUMENTS)["CR30"] == "CR30 (patch by patch)"
    src = (ROOT / "ui" / "dialogs" / "spot_read_dialog.py").read_text(encoding="utf-8")
    assert 'tr("CR30 (ChnSpec)")' not in src and 'tr("CR30")' in src


def test_manual_choice_and_every_overlay_label():
    p = yaml.safe_load((ROOT / "data" / "parameters.yaml").read_text(encoding="utf-8"))
    entry = next(e for e in p["parameters"]["printtarg"] if e["flag"] == "-i")
    labels = dict(zip(entry["choices"], entry["labels"]))
    assert labels["CR30"] == "CR30 (patch by patch)"
    for f in sorted((ROOT / "data" / "i18n").glob("parameters.*.yaml")):
        o = yaml.safe_load(f.read_text(encoding="utf-8"))
        lab = o["parameters"]["printtarg"]["-i"]["labels"]
        assert not any("ChnSpec" in x for x in lab), f.name
        code = f.name.split(".")[1]
        cat = json.loads((ROOT / "data" / "i18n" / f"{code}.json").read_text(encoding="utf-8"))
        assert cat["CR30 (patch by patch)"] in lab, f.name
        assert "CR30 (ChnSpec)" not in cat and cat["CR30"] == "CR30"
