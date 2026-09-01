"""Tests for LayoutRecipe + PresetStore (round-trip persistence, presets)."""
from workflow.layout_engine.presets import (
    LayoutRecipe, PresetStore, default_recipe,
)


def test_mode_and_preset_key():
    assert LayoutRecipe(instrument="i1", clip_border=True).mode() == "clip"
    assert LayoutRecipe(instrument="i1", clip_border=False).mode() == "noclip"
    # ColorMunki: normal + two high-density levels
    assert LayoutRecipe(instrument="CM", cm_density=1).mode() == "freehand"
    assert LayoutRecipe(instrument="CM", cm_density=2).mode() == "high"
    assert LayoutRecipe(instrument="CM", cm_density=3).mode() == "extrahigh"
    assert LayoutRecipe(instrument="SS", hflag=True).mode() == "hex"
    assert LayoutRecipe(instrument="41").mode() == "default"
    assert LayoutRecipe(instrument="i1", paper="A4", clip_border=True).preset_key() == "i1|A4|clip"


def test_recipe_dict_roundtrip():
    r = LayoutRecipe(instrument="CM", paper="A3", hflag=True, seed=123, pscale=0.9)
    r2 = LayoutRecipe.from_dict(r.to_dict())
    assert r2 == r
    # unknown keys ignored (forward-compat)
    r3 = LayoutRecipe.from_dict({**r.to_dict(), "future_field": 1})
    assert r3 == r


def test_build_kwargs_maps_clip_border():
    assert LayoutRecipe(instrument="i1", clip_border=False).build_kwargs()["nolpcbord"] is True
    assert LayoutRecipe(instrument="i1", clip_border=True).build_kwargs()["nolpcbord"] is False
    # clip_border irrelevant for non-i1 -> never suppresses
    assert LayoutRecipe(instrument="CM", clip_border=False).build_kwargs()["nolpcbord"] is False


def test_store_get_set_default_fallback():
    store = PresetStore()
    # nothing stored -> default
    d = store.get("i1", "A4", "clip")
    assert isinstance(d, LayoutRecipe) and d.instrument == "i1" and d.clip_border is True
    # set then get returns stored values (seed dropped from presets)
    store.set(LayoutRecipe(instrument="i1", paper="A4", clip_border=True, pscale=0.8, seed=99))
    got = store.get("i1", "A4", "clip")
    assert got.pscale == 0.8
    assert got.seed is None


def test_all_fields_persist_through_named_dict():
    """Every engine option must survive the file-backed preset path
    (store.set → as_named_dict → from_named_dict → get) so it saves as a default
    / preset like the printtarg options. Presets drop only the per-chart seed."""
    from dataclasses import fields, replace
    full = LayoutRecipe(
        instrument="i1", paper="A4", clip_border=True, dpi=150, randomize=True,
        cm_density=1, spacer_on=True, spacer_mode="bw",
        spacer_palette=["#112233", "#445566"], pscale=0.9, sscale=1.1,
        border=8.0, margin_top=10.0, margin_right=8.0, margin_bottom=12.0,
        margin_left=9.0, patch_w_mm=9.0, patch_h_mm=11.0, spacer_width_mm=2.0,
        inter_patch_mm=1.0, max_strip_mm=200.0, strip_indicator_gap_mm=3.0,
        offset_x_mm=4.0, offset_y_mm=5.0, bit16=True, compression="zlib",
        show_strip_indicators=True, show_row_indicators=False,
        label_style_explicit=True,
        layout_explicit=True,
        indicator_font="Inter", indicator_size_mm=4.0,
        indicator_bold=True, indicator_italic=True, underline_mode="cycle",
        underline_thickness_mm=0.8, underline_gap_mm=1.2, chart_text="{project}",
        chart_text_font="Inter", chart_text_size_mm=3.5, chart_text_bold=True,
        chart_text_italic=True, stamp_command=True, clip_border_width_mm=30.0,
        clip_content_mode="text", clip_text="ID", clip_text_font="Inter",
        clip_image_path="/tmp/logo.png", nolimit=True, strip_pattern="A-Z",
        patch_pattern="1-99",
        # EVERY field has to be set to a NON-DEFAULT value, or the loop below
        # compares a default against a default and passes whether the field
        # travelled or not. The ruler-marker fields were all left at their
        # defaults here, so this test would not have noticed one being dropped —
        # found while adding the two edge switches (#164).
        helper_markers=True, helper_marker_edge_mm=3.5,
        helper_marker_len_mm=5.5, helper_marker_per_patch=6,
        helper_markers_top_bottom=False, helper_markers_sides=False,
        clip_image_rotation=90, clip_image_scale=140.0,
        clip_image_offset_x_mm=2.5, clip_image_offset_y_mm=-3.5,
        clip_flip_180=True, clip_side="right", clip_text_size_mm=4.5,
        text_edge_mm=5.0, text_edge_top_mm=6.0, text_edge_clip_mm=7.0,
        strip_label_offset_mm=-1.5, indicator_rotation=90,
        indicator_align="center", edge_spacers=True,
        patch_area_align="center-right", cm_stagger=True, export_pdf=True,
        hflag=True, use_instrument_margins=False, layout_mode="patch_first",
        area_method="by_grid", area_cols=12, area_rows=18, area_ratio=1.25,
        area_min_patch_mm=6.0, strip_gap_mm=2.5)
    store = PresetStore()
    store.set(full)
    reloaded = PresetStore.from_named_dict(store.as_named_dict())
    got = reloaded.get("i1", "A4", "clip")
    # every field except the deliberately-dropped per-chart seed must match
    for f in fields(LayoutRecipe):
        if f.name == "seed":
            assert got.seed is None
            continue
        assert getattr(got, f.name) == getattr(full, f.name), f.name


def test_the_full_recipe_really_is_full():
    """The round-trip test above is only as good as its sample: a field left at
    its default compares equal whether it survived the trip or not. So the
    sample must differ from a fresh recipe in EVERY field it can.

    Kept honest by naming the exceptions out loud rather than by trusting that
    somebody remembered to extend the literal.
    """
    from dataclasses import fields
    import inspect

    src = inspect.getsource(test_all_fields_persist_through_named_dict)
    default = LayoutRecipe()
    # Fields that legitimately cannot be varied here.
    skip = {
        "seed",                 # deliberately dropped by a preset
        "instrument", "paper",  # the preset KEY — varying them changes the slot
        "clip_border",          # ditto: part of the mode in the key
        "spacer_overrides",     # per-chart click state, not a preset value
    }
    missing = [f.name for f in fields(LayoutRecipe)
               if f.name not in skip and f"{f.name}=" not in src]
    assert not missing, (
        "these recipe fields are never set in the round-trip sample, so a "
        f"dropped one would pass unnoticed: {missing}")


def test_from_channels_json(tmp_path):
    import json
    rec = LayoutRecipe(instrument="i1", paper="A4", clip_border=True,
                       clip_content_mode="branding", underline_mode="cycle",
                       indicator_bold=True)
    ch = tmp_path / "c.channels.json"
    ch.write_text(json.dumps({"layout": {"engine": "chromiq", "seed": 42,
                                         "recipe": rec.to_dict()}}))
    got = LayoutRecipe.from_channels_json(ch)
    assert got is not None
    assert got.clip_content_mode == "branding"
    assert got.underline_mode == "cycle"
    assert got.indicator_bold is True
    assert got.seed == 42                    # build seed carried for reproduction
    # not an engine chart → None
    nb = tmp_path / "nb.channels.json"
    nb.write_text(json.dumps({"layout": {"strips": []}}))
    assert LayoutRecipe.from_channels_json(nb) is None
    assert LayoutRecipe.from_channels_json(tmp_path / "missing.json") is None


def test_store_save_load(tmp_path):
    store = PresetStore.factory_defaults()
    p = tmp_path / "presets.json"
    store.save(p)
    loaded = PresetStore.load(p)
    assert loaded.keys() == store.keys()
    assert "i1|A4|clip" in loaded.keys()
    assert "CM|A4|high" in loaded.keys()


def test_factory_defaults_have_modes():
    f = PresetStore.factory_defaults()
    keys = f.keys()
    assert "i1|A4|noclip" in keys
    assert "SS|A4|hex" in keys
    # ColorMunki gets normal + two high-density presets per paper
    assert "CM|A4|freehand" in keys
    assert "CM|A4|high" in keys
    assert "CM|A4|extrahigh" in keys


def test_default_recipe_mode_application():
    assert default_recipe("i1", "A4", mode="noclip").clip_border is False
    assert default_recipe("CM", "A4", mode="high").cm_density == 2
    assert default_recipe("CM", "A4", mode="extrahigh").cm_density == 3


def test_spectroscan_defaults_to_patch_first():
    """A flatbed reads a fixed grid, so the SpectroScan defaults to patch-first
    (area-first + By-minimum-width collapses it to full-width bands). Other
    instruments keep the generic area-first default."""
    assert default_recipe("SS", "A4").layout_mode == "patch_first"
    assert default_recipe("SS", "A4", mode="hex").layout_mode == "patch_first"
    assert default_recipe("SS", "A4", mode="flat").layout_mode == "patch_first"
    assert default_recipe("i1", "A4").layout_mode == "area_first"
    assert default_recipe("CM", "A4").layout_mode == "area_first"


def test_from_build_kwargs_roundtrip_and_detection():
    """A chart whose channels.json stored build-kwargs (not a recipe) must
    reload faithfully — esp. clip_border (kwargs spell it nolpcbord) (#93)."""
    r = LayoutRecipe(instrument="i1", paper="A4", clip_border=False, border=10.0,
                     pscale=0.95, underline_mode="cycle", cm_density=1,
                     indicator_rotation=90)
    kw = r.build_kwargs()
    assert kw["nolpcbord"] is True              # no-clip → nolpcbord True
    # from_dict auto-detects the kwargs shape and maps it back
    back = LayoutRecipe.from_dict(kw)
    assert back.clip_border is False            # not silently defaulted to True
    assert back.border == 10.0
    assert back.pscale == 0.95
    assert back.underline_mode == "cycle"
    assert back.indicator_rotation == 90
    # a real recipe dict still loads as before (not misdetected)
    assert LayoutRecipe.from_dict(r.to_dict()).clip_border is False
