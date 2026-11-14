"""Every i1iSis option survives the four places a recipe is kept.

The recipe's dict (presets, Save as Defaults, a target's own settings, the
chart's record in ``channels.json``), the build kwargs (Guided and the
chart's stored kwargs) and Manual's layout panel. Table-driven over every
``isis_*`` field (`workflow.layout_engine.presets.ISIS_FIELD_DEFAULTS`), so a
field added later without persistence fails here
(`tests/test_layout_presets.py` names this file for them). The fields are
written ONLY for an "XRISIS" recipe that differs from the default, so every
other recipe's dict and kwargs are what they were (checklist 3.9)."""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.layout_engine.presets import (ISIS_FIELD_DEFAULTS,  # noqa: E402
                                            LayoutRecipe, PresetStore)

#: A value other than the default for every field.
CHANGED = {
    "isis_model": "xl", "isis_header_mm": 56.0, "isis_tight": True,
    "isis_barcode": True, "isis_trailer_mm": 40.0, "isis_arrows": False,
    "isis_outline": False, "isis_corner_labels": False,
    "isis_strip_letters": "bottom", "isis_row_numbers": True,
    "isis_notes_band": True, "isis_notes_place": "trailer",
    "isis_notes_height_mm": 12.0, "isis_align": "center",
}


def test_every_field_has_a_changed_value():
    assert set(CHANGED) == set(ISIS_FIELD_DEFAULTS)
    for k, v in CHANGED.items():
        assert v != ISIS_FIELD_DEFAULTS[k], k


@pytest.fixture(autouse=True)
def isis_on():
    from workflow.isis import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    yield
    support._latched = before


def _recipe(**kw):
    r = LayoutRecipe(instrument="XRISIS", paper="A4")
    for k, v in kw.items():
        setattr(r, k, v)
    return r


@pytest.mark.parametrize("field", sorted(ISIS_FIELD_DEFAULTS))
def test_the_dict_and_a_named_preset(field):
    r = _recipe(**{field: CHANGED[field]})
    d = r.to_dict()
    assert d[field] == CHANGED[field]
    assert getattr(LayoutRecipe.from_dict(json.loads(json.dumps(d))),
                   field) == CHANGED[field]
    store = PresetStore.from_named_dict({"k": d})
    got = PresetStore.from_named_dict(store.as_named_dict())
    assert getattr(LayoutRecipe.from_dict(got.as_named_dict()["k"]),
                   field) == CHANGED[field]


@pytest.mark.parametrize("field", sorted(ISIS_FIELD_DEFAULTS))
def test_the_build_kwargs(field):
    r = _recipe(**{field: CHANGED[field]})
    kw = r.build_kwargs()
    assert kw[field] == CHANGED[field]
    assert getattr(LayoutRecipe.from_build_kwargs(kw), field) == CHANGED[field]


def test_the_charts_record(tmp_path):
    r = _recipe(**CHANGED)
    p = tmp_path / "c.channels.json"
    p.write_text(json.dumps({"layout": {"engine": "chromiq",
                                        "recipe": r.to_dict()}}),
                 encoding="utf-8")
    got = LayoutRecipe.from_channels_json(p)
    for k, v in CHANGED.items():
        assert getattr(got, k) == v, k


@pytest.mark.parametrize("inst", ["i1", "p3", "CM", "SS", "CR30"])
def test_no_other_recipe_writes_an_isis_field(inst):
    r = LayoutRecipe(instrument=inst, paper="A4")
    for k, v in CHANGED.items():
        setattr(r, k, v)        # even if a panel left them set
    assert not [k for k in r.to_dict() if k.startswith("isis_")]
    assert not [k for k in r.build_kwargs() if k.startswith("isis_")]


def test_a_default_isis_recipe_writes_none_of_them():
    r = LayoutRecipe(instrument="XRISIS", paper="A4")
    assert not [k for k in r.to_dict() if k.startswith("isis_")]


def test_manuals_panel_shows_and_gives_back_every_option(qapp):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    try:
        r = _recipe(**CHANGED)
        r.patch_area_align = "center"
        p.set_recipe(r)
        qapp.processEvents()
        got = p.get_recipe()
        assert got.instrument == "XRISIS"
        for k, v in CHANGED.items():
            assert getattr(got, k) == v, k
        assert got.spacer_mode == "none" and got.inter_patch_mm == 0.0
    finally:
        p.deleteLater()
        qapp.processEvents()
