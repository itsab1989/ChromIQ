"""Every Barbieri option survives the four places a recipe is kept.

The recipe's dict (presets, Save as Defaults, a target's own settings, the
chart's record in ``channels.json``), the build kwargs (Guided and the
chart's stored kwargs) and Manual's layout panel. Table-driven over every
``barbieri_*`` field (`workflow.layout_engine.presets.
BARBIERI_FIELD_DEFAULTS`), so a field added later without persistence fails
here (`tests/test_layout_presets.py` names this file for them). The fields
are written ONLY for a "B100XY" recipe that differs from the default, so
every other recipe's dict and kwargs are what they were (checklist 3.9)."""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.layout_engine.presets import (BARBIERI_FIELD_DEFAULTS,  # noqa: E402
                                            LayoutRecipe, PresetStore)

#: A value other than the default for every field.
CHANGED = {"barbieri_head": "transmission-0.5",
           "barbieri_check_patches": False, "barbieri_marks": False,
           "barbieri_size": "film_35"}


def test_every_field_has_a_changed_value():
    assert set(CHANGED) == set(BARBIERI_FIELD_DEFAULTS)
    for k, v in CHANGED.items():
        assert v != BARBIERI_FIELD_DEFAULTS[k], k


@pytest.fixture(autouse=True)
def barbieri_on():
    from workflow.barbieri import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    yield
    support._latched = before


def _recipe(**kw):
    r = LayoutRecipe(instrument="B100XY", paper="A4R")
    for k, v in kw.items():
        setattr(r, k, v)
    return r


@pytest.mark.parametrize("field", sorted(BARBIERI_FIELD_DEFAULTS))
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


@pytest.mark.parametrize("field", sorted(BARBIERI_FIELD_DEFAULTS))
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
def test_no_other_recipe_writes_a_barbieri_field(inst):
    r = LayoutRecipe(instrument=inst, paper="A4")
    for k, v in CHANGED.items():
        setattr(r, k, v)        # even if a panel left them set
    assert not [k for k in r.to_dict() if k.startswith("barbieri_")]
    assert not [k for k in r.build_kwargs() if k.startswith("barbieri_")]


def test_a_default_barbieri_recipe_writes_none_of_them():
    r = LayoutRecipe(instrument="B100XY", paper="A4R")
    assert not [k for k in r.to_dict() if k.startswith("barbieri_")]


def test_manuals_panel_shows_and_gives_back_every_option(qapp):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    try:
        r = _recipe(**CHANGED)
        r.patch_w_mm = r.patch_h_mm = 1.2
        p.set_recipe(r)
        qapp.processEvents()
        got = p.get_recipe()
        assert got.instrument == "B100XY"
        for k, v in CHANGED.items():
            assert getattr(got, k) == v, k
        assert (got.patch_w_mm, got.patch_h_mm) == (1.2, 1.2)
        assert got.spacer_mode == "none" and got.layout_mode == "patch_first"
    finally:
        p.deleteLater()
        qapp.processEvents()


def _choose(p, qapp, code):
    i = p.instr.findData(code)
    p.instr.setCurrentIndex(i)
    p.instr.activated.emit(i)
    qapp.processEvents()


def test_choosing_the_barbieri_greys_what_has_no_meaning_and_leaving_gives_it_back(
        qapp):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    from ui.dialogs.barbieri_panel import BARBIERI_GREYED, barbieri_greyed_why
    p = LayoutOptionsPanel(with_selectors=True)
    try:
        _choose(p, qapp, "i1")
        before = {n: getattr(p, n).isEnabled() for n in BARBIERI_GREYED
                  if getattr(p, n, None) is not None}
        _choose(p, qapp, "B100XY")
        for n, why in BARBIERI_GREYED.items():
            c = getattr(p, n, None)
            if c is None:
                continue
            assert not c.isEnabled(), n
            assert c.toolTip().startswith(barbieri_greyed_why()[why][:30]), n
        # the gaps stay open (a pitch from centres allows them)
        assert p.inter_patch.isEnabled() and p.strip_gap.isEnabled()
        r = p.get_recipe()
        assert (r.patch_w_mm, r.layout_mode, r.show_strip_indicators) == (
            6.5, "patch_first", False)
        # a new opening carries its own patch size while it is untouched
        p.barbieri_head.setCurrentIndex(
            p.barbieri_head.findData("transmission-0.5"))
        qapp.processEvents()
        assert p.get_recipe().patch_w_mm == 1.0
        _choose(p, qapp, "i1")
        after = {n: getattr(p, n).isEnabled() for n in before}
        assert after == before
    finally:
        p.deleteLater()
        qapp.processEvents()
