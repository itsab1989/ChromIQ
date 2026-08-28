"""The CR30 (#159), registered end to end — geometry, presets, chart creation,
identity and the guards that keep the honest name honest.

Every number asserted here was measured on this branch, not quoted from the
design: the design document and its critique disagree on several of them (the
spacer, the layout mode, whether the clip band is offerable), and where they do,
what the code actually computes is the only thing worth pinning.
"""
from __future__ import annotations

import math
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.layout_engine import geometry, instruments, papers, presets

KEY = "CR30"
A4 = papers.dimensions_mm("A4")


def _geom(**kw):
    """A Geom the way the app builds one — through the recipe, not by hand."""
    r = presets.default_recipe(KEY, "A4", mode=kw.pop("mode", None))
    for k, v in kw.items():
        setattr(r, k, v)
    return instruments.geom_from_build_kwargs(
        {**r.build_kwargs(), "instrument": KEY, "paper": "A4"})


def _cap(g) -> int:
    return geometry.compute(g, A4[0], A4[1], 5000).patches_per_page


# ---------------------------------------------------------------------------
# 1. Geometry — the branch, and every claim its comment makes
# ---------------------------------------------------------------------------
def test_the_instrument_is_registered_everywhere_the_engine_looks() -> None:
    assert instruments.TARGET_INSTRUMENT_NAME[KEY] == "CR30", \
        "the honest name: the device reports CR30 for itself (#159 ruling)"
    assert KEY in instruments.supported()
    assert instruments._MARGIN_LABEL_TO_KEY["CR30"] == KEY
    assert KEY not in instruments.DELEGATED, \
        "a CR30 chart is laid out here, not by i1Profiler"


def test_the_base_geometry_is_a_hand_placed_spot_grid() -> None:
    g = instruments.build(KEY)
    # The provisional cell: 12 mm square, columns touching. Sized for a BLIND
    # hand placement (a 33 mm opaque body hides the patch), not from the 4 mm
    # aperture — it leaves 4.00 mm of clearance all round the window.
    assert (g.plen, g.pwid, g.rrsp) == (12.0, 12.0, 12.0)
    assert g.pwid / 2 - instruments.APERTURE_MM[KEY] / 2 == pytest.approx(4.0)
    # No swipe: no run-in, no run-out, no jig.
    assert g.lcar == 0.0 and g.tspa == 0.0
    assert g.ruler_mm == 0.0 and g.mxrowl == instruments.MAXROWLEN
    assert instruments.default_ruler_mm(KEY) == 0.0
    # The row-number band is the whole reason anything was taken from the
    # SpectroScan: raster.py draws row numbers only where rlwi > 0.
    assert g.rlwi == 7.5
    # No strip to pad out with blanks.
    assert g.padlrow is False
    # No hexagons, no stagger, no cut lines, no page-label column.
    assert (g.hxeh, g.hxew, g.clwi) == (0.0, 0.0, 0.0)
    assert g.dorspace is False and g.dopglabel is False


def test_an_unknown_instrument_key_still_raises() -> None:
    """The CR30 branch must not have turned the dispatch into a fall-through."""
    with pytest.raises(ValueError):
        instruments.build("CR31")
    with pytest.raises(ValueError):
        instruments.build("isis")      # DELEGATED, and still refused


# ---------------------------------------------------------------------------
# 2. Spacers — OFF by default, and STILL turnable on (Basti, 2026-08-28)
# ---------------------------------------------------------------------------
def test_spacers_are_off_by_default() -> None:
    assert presets.default_recipe(KEY, "A4").spacer_mode == "none"
    assert _geom().pspa == 0.0


def test_the_spacer_can_be_turned_on_and_then_sized() -> None:
    """The trap this test exists for: build() honours the Manual "Spacer size"
    box only while ``geom.pspa > 0`` (instruments.py:218-219). A geometry that
    defaulted the spacer to a literal 0.0 would be off AND un-turn-on-able —
    which is exactly what the ruling forbids."""
    assert _geom(spacer_mode="colored").pspa == pytest.approx(1.3), \
        "turning spacers on restores the base width from EXP-SPEC-001a"
    assert _geom(spacer_mode="colored", spacer_width_mm=2.5).pspa == pytest.approx(2.5), \
        "the Spacer size box must be LIVE once spacers are on"
    assert _geom(spacer_mode="bw", spacer_width_mm=0.8).pspa == pytest.approx(0.8)
    # …and off again means off, whatever the width box says.
    assert _geom(spacer_mode="none", spacer_width_mm=2.5).pspa == 0.0


def test_the_base_width_survives_in_the_geometry_so_the_control_can_live() -> None:
    """Stated directly: _build_base must NOT hard-zero the spacer."""
    assert instruments.build(KEY, spacer_on=True).pspa == pytest.approx(1.3)
    assert instruments.build(KEY, spacer_on=False).pspa == 0.0


# ---------------------------------------------------------------------------
# 3. Hexagons (Basti, 2026-08-28) — offered in every Create Chart module
# ---------------------------------------------------------------------------
def test_hexagons_change_the_shape_and_stamp_the_keyword() -> None:
    g = instruments.build(KEY, hflag=True)
    assert g.plen == pytest.approx(math.sqrt(0.75) * 12.0), \
        "a hexagon of the same width is sqrt(3)/2 as tall — the rows interleave"
    assert g.pwid == 12.0, "same width across the flats as the square"
    assert g.hxeh == pytest.approx(g.plen / 6.0), "apex overhang, reserved"
    assert g.hxew == pytest.approx(3.0), "quarter-width side overhang, reserved"
    assert ("HEXAGON_PATCHES", "True") in g.extra_keywords
    # …and the flat chart says nothing of the sort.
    assert instruments.build(KEY).extra_keywords == ()


def test_a_resized_hexagon_recomputes_its_overhang() -> None:
    """build() recomputed the hex overhang for the SpectroScan only; a CR30
    hexagon resized by the Manual patch boxes would otherwise keep the 10 mm
    geometry's reservation and print past the margin."""
    g = instruments.build(KEY, hflag=True, patch_w=20.0, patch_h=18.0)
    assert g.hxew == pytest.approx(0.25 * 20.0)
    assert g.hxeh == pytest.approx(18.0 / 6.0)


def test_the_honeycomb_is_denser_at_the_same_aperture_clearance() -> None:
    """The claim the help text makes, checked against what is actually built:
    the hexagon keeps the square's inradius (so a 4 mm round aperture has the
    same room) and spends less paper per patch."""
    sq, hexg = instruments.build(KEY), instruments.build(KEY, hflag=True)
    assert sq.pwid / 2 == hexg.pwid / 2, "same clearance around the aperture"
    hex_area = 2 * math.sqrt(3) * (hexg.pwid / 2) ** 2
    assert hex_area < sq.pwid * sq.plen, "less paper per patch"
    assert _cap(_geom(mode="hex")) > _cap(_geom(mode="flat"))


def test_hexagons_reach_every_create_chart_module() -> None:
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel as P
    from workflow.chart_creator import ChartCreator, ChartParams
    from workflow.hex_support import recipe_is_hexagonal

    # Manual / editor: the shape selector really offers both.
    assert dict(P.modes_for(KEY)).keys() == {"flat", "hex"}
    assert P.mode_label_for(KEY) == P.mode_label_for("SS"), \
        "the control does the same job as the SpectroScan's, so it says so"
    assert KEY in dict(P.INSTRUMENTS)
    # Guided: the shared -h checkbox carries it.
    kw = ChartCreator._engine_build_kwargs(
        object.__new__(ChartCreator),
        ChartParams(instrument=KEY, paper="A4", double_density=True))
    assert kw["hflag"] is True
    # Everything downstream (measure overlay, strip highlight, scanner sample
    # cap) keys off this one predicate.
    assert recipe_is_hexagonal(presets.default_recipe(KEY, "A4", mode="hex"))
    assert not recipe_is_hexagonal(presets.default_recipe(KEY, "A4", mode="flat"))
    assert not recipe_is_hexagonal(presets.default_recipe("CM", "A4"))


# ---------------------------------------------------------------------------
# 4. The clip / notes band — "off by default, offerable" made true
# ---------------------------------------------------------------------------
def test_the_notes_band_is_off_by_default_but_really_offerable() -> None:
    off = _geom()
    assert off.lbord == 0.0 and off.has_clip_border is False
    on = _geom(clip_content_mode="notes")
    assert on.lbord > 0.0 and on.has_clip_border is True, \
        "without the CR30 in the CM/SS band gate this was silently inert"
    assert _cap(on) < _cap(off), "the band costs patches, so capacity must see it"


# ---------------------------------------------------------------------------
# 5. Layout mode — the patch size must not float
# ---------------------------------------------------------------------------
def test_patch_first_is_the_default_and_keeps_the_ruled_patch_size() -> None:
    r = presets.default_recipe(KEY, "A4")
    assert r.layout_mode == "patch_first"
    assert (_geom().pwid, _geom().plen) == (12.0, 12.0)


def test_area_first_would_float_the_patch_which_is_why_it_is_not_the_default() -> None:
    g = _geom(layout_mode="area_first")
    assert (g.pwid, g.plen) != (12.0, 12.0), \
        "area-first sizes patches to fill the page — the reason patch-first wins"


@pytest.mark.parametrize("paper", ["A4", "A3", "Letter"])
def test_capacity_is_computable_and_sane_on_every_paper(paper: str) -> None:
    r = presets.default_recipe(KEY, paper)
    g = instruments.geom_from_build_kwargs(
        {**r.build_kwargs(), "instrument": KEY, "paper": paper})
    w, h = papers.dimensions_mm(paper)
    n = geometry.compute(g, w, h, 5000).patches_per_page
    assert 100 < n < 2000, f"{paper}: {n} patches/sheet is not a plausible grid"
    assert KEY not in papers.ENGINE_EXCLUDED_PAPERS, \
        "a hand-placed device has no mechanism to be limited by a paper size"


# ---------------------------------------------------------------------------
# 6. Presets
# ---------------------------------------------------------------------------
def test_rectangular_is_the_default_shape() -> None:
    """Basti, 2026-08-28: hexagons are OFFERED, not imposed."""
    r = presets.default_recipe(KEY, "A4")
    assert r.hflag is False and r.mode() == "flat"
    assert instruments.build(KEY).extra_keywords == ()


# ---------------------------------------------------------------------------
# 3b. The aperture floor — refused at layout time, not discovered on paper
#     (#159: "Patch smaller than the aperture -> refused at layout time")
# ---------------------------------------------------------------------------
def test_the_floor_and_the_aperture_are_declared() -> None:
    assert instruments.APERTURE_MM[KEY] == 4.0
    assert instruments.minimum_patch_mm(KEY) == 6.0
    assert instruments.minimum_patch_mm("i1") == 0.0, \
        "only instruments with a declared floor are refused; others still warn"


@pytest.mark.parametrize("mm,phrase", [
    (2.0, "smaller than"),      # below the 4 mm window: physically impossible
    (3.9, "smaller than"),
    (4.0, "too small"),         # readable in principle, unplaceable in practice
    (5.9, "too small"),
])
def test_a_patch_below_the_floor_is_refused_with_a_reason(mm, phrase) -> None:
    msg = instruments.patch_size_error(KEY, mm, mm)
    assert msg and phrase in msg and "6 mm" in msg
    assert "aperture" not in msg.lower(), "plain language, not instrument jargon"


@pytest.mark.parametrize("mm", [6.0, 8.0, 12.0, 30.0])
def test_a_patch_at_or_above_the_floor_is_allowed(mm) -> None:
    assert instruments.patch_size_error(KEY, mm, mm) is None


def test_the_floor_applies_to_the_SHORTER_side_of_a_rectangle() -> None:
    assert instruments.patch_size_error(KEY, 20.0, 3.0) is not None
    assert instruments.patch_size_error(KEY, 3.0, 20.0) is not None
    assert instruments.patch_size_error(KEY, 20.0, 6.0) is None


def test_auto_sizing_is_not_mistaken_for_a_tiny_patch() -> None:
    """0 means "auto" throughout the recipe, not "zero millimetres"."""
    assert instruments.patch_size_error(KEY, 0.0, 0.0) is None


def test_chart_creation_refuses_the_chart_rather_than_printing_it() -> None:
    """The refusal has to be on the path a chart actually takes — and it must
    reach the user, not be swallowed into a fallback that does not exist."""
    from workflow.chart_creator import ChartParams
    r = presets.default_recipe(KEY, "A4")
    r.patch_w_mm = r.patch_h_mm = 3.0
    p = ChartParams(instrument=KEY, paper="A4", layout_recipe=r)
    c = _creator()
    with pytest.raises(ValueError, match="smaller than"):
        c._engine_kwargs(p)
    with pytest.raises(ValueError, match="smaller than"):
        c._engine_total_patches(p)      # must NOT quietly return None
    # a legal size on the same path builds normally
    r.patch_w_mm = r.patch_h_mm = 12.0
    assert c._engine_total_patches(p) > 0


def test_the_preflight_badge_uses_the_instruments_own_floor() -> None:
    from workflow.layout_engine import preflight
    g = instruments.build(KEY, patch_w=5.0, patch_h=5.0)
    lay = geometry.compute(g, A4[0], A4[1], 10)
    rep = preflight.check(g, lay)
    assert not rep.ok and any("6.0 mm" in e for e in rep.errors)
    ok = preflight.check(instruments.build(KEY),
                         geometry.compute(instruments.build(KEY), A4[0], A4[1], 10))
    assert ok.ok


def test_the_preset_vocabulary_is_the_shape_choice() -> None:
    assert KEY in presets.SUPPORTED_INSTRUMENTS
    assert presets.default_recipe(KEY, "A4", mode="hex").mode() == "hex"
    assert presets.default_recipe(KEY, "A4", mode="flat").mode() == "flat"
    keys = set(presets.PresetStore.factory_defaults()._presets)
    assert {"CR30|A4|flat", "CR30|A4|hex"} <= keys


def test_a_recipe_round_trips_through_its_dict_form() -> None:
    r = presets.default_recipe(KEY, "A4", mode="hex")
    r.spacer_mode = "colored"
    back = presets.LayoutRecipe.from_dict(r.to_dict())
    assert (back.instrument, back.hflag, back.spacer_mode, back.layout_mode) == \
           (KEY, True, "colored", "patch_first")


def test_no_edge_spacers_because_there_is_no_strip_to_bracket() -> None:
    assert presets.default_recipe(KEY, "A4").build_kwargs()["edge_spacers"] is False


# ---------------------------------------------------------------------------
# 7. Engine-only: printtarg must be UNREACHABLE, not merely discouraged
# ---------------------------------------------------------------------------
class _Settings:
    """The hostile case: the layout engine is switched OFF in Preferences."""

    def __init__(self, **kw):
        self._d = {"use_chromiq_layout_engine": False, **kw}

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value):
        self._d[key] = value


class _StemOnlyFileManager:
    def chart_stem(self, *, cal_target: bool) -> str:
        return "chart"


def _creator(**kw):
    from workflow.chart_creator import ChartCreator
    c = object.__new__(ChartCreator)
    c._settings = _Settings(**kw)
    c._file_mgr = _StemOnlyFileManager()
    return c


@pytest.mark.parametrize("params_kw", [
    {"is_manual": False},                                     # Guided
    {"is_manual": True},                                      # Manual, engine off
    {"is_manual": True, "chromiq_clip_style": True},          # legacy clip flag
    {"is_manual": True, "left_clip_info": True},              # the other one
])
def test_a_cr30_chart_always_takes_the_engine(params_kw) -> None:
    from workflow.chart_creator import ChartParams
    p = ChartParams(instrument=KEY, paper="A4", **params_kw)
    assert _creator()._should_use_engine(p) is True
    # …and the same params on a strip instrument still honour the setting,
    # so the CR30 rule is a rule and not a global override.
    q = ChartParams(instrument="i1", paper="A4", **params_kw)
    assert _creator()._should_use_engine(q) is (params_kw.get("is_manual") is False)


def test_printtarg_refuses_to_build_an_argv_for_a_cr30() -> None:
    from workflow.chart_creator import ENGINE_ONLY_INSTRUMENTS, ChartParams
    assert KEY in ENGINE_ONLY_INSTRUMENTS
    with pytest.raises(ValueError, match="ChromIQ layout engine only"):
        _creator()._build_printtarg_args(ChartParams(instrument=KEY, paper="A4"))
    # the guard is specific: every other instrument still builds its argv
    args = _creator()._build_printtarg_args(ChartParams(instrument="i1", paper="A4"))
    assert "-ii1" in args


def test_the_cr30_is_not_hidden_from_guided_the_way_an_isis_is() -> None:
    from data.patch_db import EXTERNAL_INSTRUMENTS, INSTRUMENT_LABELS
    assert KEY in INSTRUMENT_LABELS, "the Guided combo is built from this dict"
    assert KEY not in EXTERNAL_INSTRUMENTS, \
        "EXTERNAL_INSTRUMENTS hides its members from Guided; the CR30 belongs there"


def test_guided_gets_no_spacers_and_manual_keeps_its_own_control() -> None:
    from workflow.chart_creator import ChartCreator, ChartParams
    build = ChartCreator._engine_build_kwargs
    guided = build(object.__new__(ChartCreator),
                   ChartParams(instrument=KEY, paper="A4", is_manual=False))
    assert guided["spacer_on"] is False and guided["spacer_mode"] == "none"
    manual = build(object.__new__(ChartCreator),
                   ChartParams(instrument=KEY, paper="A4", is_manual=True))
    assert manual["spacer_on"] is True, \
        "Manual keeps the -n checkbox; only Guided is forced"
    # the patch size is pinned on this path too
    assert guided["layout_mode"] == "patch_first"


# ---------------------------------------------------------------------------
# 8. Identity: the .ti2 chain, and what the honest name costs
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("hexagonal", [False, True])
def test_the_ti2_carries_the_honest_name(tmp_path: Path, hexagonal: bool) -> None:
    from ui.ti2_loader import is_cr30, read_target_instrument
    from workflow.layout_engine import ti2_writer
    g = instruments.build(KEY, hflag=hexagonal)
    # (device tuple, XYZ) per ti2_writer's canonical form
    patches = [((100.0, 100.0, 100.0), (95.0, 100.0, 108.0)),
               ((50.0, 50.0, 50.0), (20.0, 21.0, 23.0)),
               ((0.0, 0.0, 0.0), (0.3, 0.3, 0.3))]
    out = ti2_writer.write_ti2(
        tmp_path / "c.ti2", patches, ["RGB_R", "RGB_G", "RGB_B"],
        geometry.compute(g, A4[0], A4[1], len(patches)), g,
        seed=1, paper_w_mm=A4[0], paper_h_mm=A4[1])
    assert read_target_instrument(out) == "CR30", \
        "the honest name, and the only thing that identifies the chart"
    assert is_cr30(read_target_instrument(out))
    # The hex flag has to survive into the file too, or every downstream
    # consumer of HEXAGON_PATCHES sees a rectangular chart.
    assert ('HEXAGON_PATCHES "True"' in out.read_text()) is hexagonal


@pytest.mark.parametrize("name,expected", [
    ("CR30", True), ("ChnSpec CR30", True), ("cr30", True),
    ("X-Rite ColorMunki", False), ("GretagMacbeth i1 Pro", False),
    ("", False), (None, False),
])
def test_is_cr30(name, expected) -> None:
    from ui.ti2_loader import is_cr30
    assert is_cr30(name) is expected


def test_the_instrument_family_and_the_registry() -> None:
    from ui.ti2_loader import (KNOWN_INSTRUMENTS, disable_bidir_for_instrument,
                               force_bidir_for_instrument, instrument_family)
    assert instrument_family("CR30") == "cr30"
    assert "CR30" in KNOWN_INSTRUMENTS, \
        "otherwise the Measure tab refuses every CR30 chart outright"
    # A spot device never swipes, so neither bidirectional flag may be forced.
    assert force_bidir_for_instrument("CR30") is False
    assert disable_bidir_for_instrument("CR30") is False


def test_the_wrong_device_warning_can_see_a_cr30_in_both_directions() -> None:
    """It needs INSTRUMENT_MODEL_WORDS *and* the hand-maintained tuple in
    instrument_family_of — an entry in only one of them is silently blind."""
    from data.patch_db import instrument_family_of, instrument_mismatch
    assert instrument_family_of("ChnSpec CR30") == KEY
    assert instrument_mismatch(KEY, "X-Rite ColorMunki") is not None
    assert instrument_mismatch("CM", "CR30 v1.2") is not None
    assert instrument_mismatch(KEY, "CR30") is None


def test_a_relayout_keeps_the_chart_a_cr30_chart() -> None:
    from workflow.ti2_relayout import instrument_to_flag
    assert instrument_to_flag("CR30") == KEY
    assert instrument_to_flag("X-Rite ColorMunki") == "CM"
    assert instrument_to_flag(None) == "i1"      # unchanged safe default


# ---------------------------------------------------------------------------
# 9. Profiling options that need spectra must be gated off
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name,spectral,gated", [
    ("CR30", False, True),                    # no spectra, LED illuminant
    ("CR30", True, True),                     # …still gated on the instrument
    ("X-Rite ColorMunki", True, True),        # unchanged behaviour
    ("GretagMacbeth i1 Pro", True, False),    # unchanged behaviour
    ("GretagMacbeth i1 Pro", False, True),    # no spectra to compute FWA from
])
def test_fwa_illuminant_and_observer_are_gated(name, spectral, gated) -> None:
    from ui.ti2_loader import spectral_options_unavailable
    assert spectral_options_unavailable(name, spectral) is gated


# ---------------------------------------------------------------------------
# 10. Pace and margins — no i1Pro figures may be applied to a CR30
# ---------------------------------------------------------------------------
def test_the_pace_row_exists_and_raises_no_warning() -> None:
    from core.measure_pace import (defaults_for, estimate_patches_for,
                                   explanation_for, model_key)
    assert model_key("CR30") == "cr30" and model_key("ChnSpec CR30") == "cr30"
    hz, min_samples = defaults_for("cr30")
    assert min_samples is None, "no swipe, so no pace warning — shown as Off"
    assert defaults_for("cr30") != defaults_for(None), \
        "the whole point of the row: never fall back to the i1Pro's (100, 20)"
    assert estimate_patches_for("cr30") is None      # shown as N/A
    title, body = explanation_for("cr30")
    assert "CR30" in title and body


def test_the_margin_inspector_no_longer_judges_a_cr30_as_an_i1pro() -> None:
    from core.settings import THRESHOLD_INSTR_LABEL
    from ui.tabs.tab_chart import _MARGIN_INSTR_LABEL
    assert _MARGIN_INSTR_LABEL.get(KEY) == "CR30", \
        "an unregistered flag falls back to 'i1Pro' and its 38 mm top margin"
    assert THRESHOLD_INSTR_LABEL[KEY] == "CR30"
    from ui.dialogs.settings_dialog import SettingsDialog
    assert "CR30" in SettingsDialog._MARGIN_INSTRUMENTS, \
        "the label must be selectable, or no thresholds can ever be set"


def test_no_thresholds_are_seeded_which_is_honest_not_missing() -> None:
    """No aperture or positioning data exists for a CR30, so nothing is
    checked. That is deliberate, not an omission — the SpectroScan sits in
    exactly the same position, in the picker with no seed rows behind it."""
    from core.settings import _MARGIN_SEED, thresholds_for_combo
    assert not [k for k in _MARGIN_SEED if k.startswith("CR30")]
    assert thresholds_for_combo(dict(_MARGIN_SEED), KEY, *A4) is None
    # …and the same is true of the SpectroScan, which is the precedent.
    assert thresholds_for_combo(dict(_MARGIN_SEED), "SS", *A4) is None


# ---------------------------------------------------------------------------
# 11. The Measure tab: two guards, one honest answer each
#
# Adding "CR30" to KNOWN_INSTRUMENTS was unavoidable — without it the general
# guard refuses every CR30 measurement outright. But it also silences that
# guard's claim ("ArgyllCMS does not know this one") for the one case where it
# is STILL true: stock chartread selected in Preferences. These tests pin the
# split: the general guard asks whether ChromIQ knows the name, the CR30 guard
# asks whether the selected reader can use it.
# ---------------------------------------------------------------------------
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _ti2_named(path: Path, instrument: str) -> Path:
    path.write_text(
        "CTI2\n\n"
        'DESCRIPTOR "chart"\n'
        'COLOR_REP "RGB"\n'
        f'TARGET_INSTRUMENT "{instrument}"\n\n'
        "NUMBER_OF_FIELDS 5\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n\n"
        "NUMBER_OF_SETS 1\nBEGIN_DATA\n1 A1 100 100 100\nEND_DATA\n",
        encoding="utf-8")
    return path


def _measure_tab(tmp_path: Path, engine: str):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("chartread_engine", engine)
    return TabMeasure(ArgyllRunner(s), s), s


def test_a_cr30_chart_is_not_refused_by_the_unknown_name_guard(qapp, tmp_path) -> None:
    """The general guard must pass a CR30 chart — it is a name ChromIQ knows.
    If this ever fails, every CR30 measurement is refused before it starts."""
    tab, _ = _measure_tab(tmp_path, "chromiq")
    tab._ti1_path = _ti2_named(tmp_path / "c.ti2", "CR30")
    assert tab._blocked_by_unusable_target_instrument() is False


def test_the_cr30_guard_stands_aside_when_chromiqs_own_reader_is_selected(
        qapp, tmp_path) -> None:
    tab, _ = _measure_tab(tmp_path, "chromiq")
    tab._ti1_path = _ti2_named(tmp_path / "c.ti2", "CR30")
    assert tab._blocked_by_stock_chartread_for_cr30() is False


def test_the_cr30_guard_ignores_every_other_chart(qapp, tmp_path) -> None:
    """Stock chartread is the RIGHT reader for these, so the guard must be
    silent — otherwise it would block the instruments that do work."""
    tab, _ = _measure_tab(tmp_path, "argyll")
    for name in ("GretagMacbeth i1 Pro", "X-Rite ColorMunki",
                 "GretagMacbeth SpectroScan"):
        tab._ti1_path = _ti2_named(tmp_path / f"{name[:4]}.ti2", name)
        assert tab._blocked_by_stock_chartread_for_cr30() is False, name


def test_a_cr30_chart_on_stock_chartread_is_blocked_when_the_user_declines(
        qapp, tmp_path, monkeypatch) -> None:
    tab, settings = _measure_tab(tmp_path, "argyll")
    tab._ti1_path = _ti2_named(tmp_path / "c.ti2", "CR30")
    monkeypatch.setattr(type(tab), "_cr30_stock_reader_window", lambda self: False)
    assert tab._blocked_by_stock_chartread_for_cr30() is True, \
        "a measurement that cannot succeed must not begin"
    assert settings.get("chartread_engine") == "argyll", \
        "declining must not change the user's setting behind their back"


def test_accepting_the_switch_lets_the_measurement_proceed(
        qapp, tmp_path, monkeypatch) -> None:
    tab, settings = _measure_tab(tmp_path, "argyll")
    tab._ti1_path = _ti2_named(tmp_path / "c.ti2", "CR30")
    monkeypatch.setattr(type(tab), "_cr30_stock_reader_window", lambda self: True)
    assert tab._blocked_by_stock_chartread_for_cr30() is False
    assert settings.get("chartread_engine") == "chromiq", \
        "the window offers the switch, so it has to actually make it"


def test_a_missing_or_unreadable_chart_never_blocks(qapp, tmp_path) -> None:
    """Boundary: this guard runs before anything is armed and must never be
    the thing that stops a measurement for a reason of its own."""
    tab, _ = _measure_tab(tmp_path, "argyll")
    tab._ti1_path = None
    assert tab._blocked_by_stock_chartread_for_cr30() is False
    tab._ti1_path = tmp_path / "does-not-exist.ti2"
    assert tab._blocked_by_stock_chartread_for_cr30() is False
    empty = tmp_path / "empty.ti2"
    empty.write_text("", encoding="utf-8")
    tab._ti1_path = empty
    assert tab._blocked_by_stock_chartread_for_cr30() is False


def test_the_window_says_what_the_model_says_and_nothing_else() -> None:
    from workflow import measurement_messages as M
    assert "M-CR30-STOCK-READER" in M.CATALOGUE
    msg = M.CATALOGUE["M-CR30-STOCK-READER"]
    assert msg.approved is False, "new wording waits for review (§M-PROPOSED)"
    assert "M-CR30-STOCK-READER" in M.PROPOSED
    title, body = msg.render()
    assert title and body and "{" not in body


def test_a_near_miss_name_can_be_repaired_to_the_cr30(qapp, tmp_path) -> None:
    """"ChnSpec CR30" is not a name ChromIQ matches, so the general guard fires
    — and the repair must recognise the family rather than giving up."""
    tab, _ = _measure_tab(tmp_path, "chromiq")
    ti2 = _ti2_named(tmp_path / "c.ti2", "ChnSpec CR30")
    tab._ti1_path = ti2
    assert tab._repair_target_instrument(ti2, "ChnSpec CR30") is True
    from ui.ti2_loader import read_target_instrument
    assert read_target_instrument(ti2) == "CR30"
