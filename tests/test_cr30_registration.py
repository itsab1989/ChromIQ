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
    assert g.pwid / 2 - 4.0 / 2 == pytest.approx(4.0), \
        "4.00 mm of clearance all round the CR30's 4 mm window"
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


# ---------------------------------------------------------------------------
# 12. Hexagons that are actually DRAWN
#
# The reason this section exists, in full: the CR30 gained the hexagon option,
# the geometry shortened `plen` and reserved the apex overhang — and the chart
# rendered as SQUARES, because the renderer, the recorded patch rects and the
# ruler helper markers each asked `key == "SS"` on their own. The whole hex
# suite was green throughout, because every test in it was hard-coded to the
# SpectroScan and none of them rendered anything.
#
# So these assert on PIXELS and on RECTS, never on Geom fields alone, and each
# carries a positive control on the identical path.
# ---------------------------------------------------------------------------
def _rgb_target(n: int):
    from workflow.layout_engine.raster import ColorTarget
    return ColorTarget(
        color_rep="iRGB", device_fields=["RGB_R", "RGB_G", "RGB_B"],
        patches=[((float(i * 9 % 100), float(i * 17 % 100), float(i * 5 % 100)),
                  (40.0, 45.0, 50.0)) for i in range(n)])


def _drawn_shapes(inst: str, mode: str, dpi: int = 200) -> "set[str]":
    """The shapes the RENDERER actually put on the page, for the first sheet.

    Asserting on pixels was tried first and cannot answer this: in a honeycomb
    the corners of a patch's slot are filled by its NEIGHBOURS, so "is the
    corner still paper" is False for a correct honeycomb as well as for the bug.
    ``collect_device_geom`` records the exact shape drawn for each patch — the
    only unambiguous evidence, and the same record the vector PDF and the Tier D
    device raster are built from.
    """
    from workflow.layout_engine import raster
    g = instruments.build(inst, hflag=(mode == "hex"))
    lay = geometry.compute(g, A4[0], A4[1], 80)
    res = raster.render_pages(_rgb_target(80), lay, g, seed=1, randomize=False,
                              paper_w_mm=A4[0], paper_h_mm=A4[1], dpi=dpi,
                              collect_device_geom=True)
    assert res.patch_geom, "the render recorded no device geometry at all"
    return {row[0] for row in res.patch_geom[0] if row[0] in ("hex", "rect")}


@pytest.mark.parametrize("inst", ["CR30", "SS"])
def test_a_hex_chart_really_renders_hexagons(inst) -> None:
    """CR30 first, SpectroScan as the positive control on the identical path.

    The bug this replaces: a CR30 honeycomb was laid out as hexagons — plen
    shortened, apex overhang reserved, capacity charged for it — and then DRAWN
    as rectangles, because the renderer asked `key == "SS"` on its own."""
    shapes = _drawn_shapes(inst, "hex")
    assert shapes == {"hex"}, \
        f"{inst}: the honeycomb was drawn as {sorted(shapes)}, not hexagons"
    assert instruments.is_hexagonal(instruments.build(inst, hflag=True))


@pytest.mark.parametrize("inst", ["CR30", "SS"])
def test_a_flat_chart_still_renders_rectangles(inst) -> None:
    """The counterweight: the fix must not turn every chart into a honeycomb."""
    assert _drawn_shapes(inst, "flat") == {"rect"}


@pytest.mark.parametrize("inst", ["i1", "p3", "CM"])
def test_hflag_draws_no_hexagons_on_an_instrument_that_has_none(inst) -> None:
    """`-h` means double density on a ColorMunki, not hexagons. An instrument
    whose geometry does not build a honeycomb must never be drawn as one."""
    assert _drawn_shapes(inst, "hex") == {"rect"}


@pytest.mark.parametrize("inst", ["CR30", "SS"])
def test_the_recorded_rects_carry_the_honeycomb_stagger(inst) -> None:
    """Rects and render must agree. Fixing the renderer alone would leave a
    live half-patch mis-registration in the Measure highlight, the margin
    inspector and scanin_target — which is why they share one predicate."""
    w, h = papers.dimensions_mm("A4")
    r = presets.default_recipe(inst, "A4", mode="hex")
    g = instruments.geom_from_build_kwargs(
        {**r.build_kwargs(), "instrument": inst, "paper": "A4"})
    lay = geometry.compute(g, w, h, 120)
    rects = geometry.patch_rects_px(g, w, h, lay, 150)
    col = [rc for rc in rects if rc["page"] == 0][:8]
    xs = sorted({rc["x"] for rc in col})
    assert len(xs) == 2, \
        f"{inst}: a honeycomb column must alternate x, got {xs}"
    # …and the offset is the quarter-width the renderer draws with.
    assert abs((xs[1] - xs[0]) - round(g.pwid / 2 * 150 / 25.4)) <= 2


@pytest.mark.parametrize("inst", ["CR30", "SS"])
def test_a_flat_chart_has_one_x_per_column(inst) -> None:
    w, h = papers.dimensions_mm("A4")
    r = presets.default_recipe(inst, "A4", mode="flat")
    g = instruments.geom_from_build_kwargs(
        {**r.build_kwargs(), "instrument": inst, "paper": "A4"})
    lay = geometry.compute(g, w, h, 120)
    rects = geometry.patch_rects_px(g, w, h, lay, 150)
    assert len({rc["x"] for rc in rects[:8] if rc["page"] == 0}) == 1


@pytest.mark.parametrize("inst", ["CR30", "SS"])
def test_a_honeycomb_gets_no_ruler_helper_markers(inst) -> None:
    """#152's rule, and it follows the SHAPE, not the instrument: a honeycomb
    has no rows to line a ruler against."""
    w, h = papers.dimensions_mm("A4")
    for mode, expect_markers in (("flat", True), ("hex", False)):
        r = presets.default_recipe(inst, "A4", mode=mode)
        g = instruments.geom_from_build_kwargs(
            {**r.build_kwargs(), "instrument": inst, "paper": "A4"})
        lay = geometry.compute(g, w, h, 120)
        lines = geometry.helper_marker_lines_mm(g, w, h, lay,
                                                edge_mm=2.0, length_mm=4.0)
        assert bool(lines) is expect_markers, f"{inst}/{mode}"


def test_hex_capability_is_asked_of_the_geometry_not_a_list() -> None:
    """A new hex-capable instrument must need no second registration: it offers
    hexagons exactly when its _build_base branch honours hflag (Basti,
    2026-08-28 — "we own the layout engine, so you should be able to add the
    hex patches to any instrument we want")."""
    assert instruments.hex_capable(KEY) and instruments.hex_capable("SS")
    for k in ("i1", "p3", "CM", "41", "51"):
        assert not instruments.hex_capable(k), k
    assert instruments.hex_capable("nonsense") is False
    assert set(instruments.hex_capable_instruments()) == {"SS", KEY}
    # The flag is the single source of truth, and it is on the Geom itself.
    assert instruments.build(KEY, hflag=True).hexagonal is True
    assert instruments.build(KEY).hexagonal is False
    # NOT inferred from the overhang floats: a ColorMunki stagger sets hxeh
    # without being hexagonal.
    cm = instruments.build("CM", cm_stagger=True, patch_h=14.0)
    assert cm.hxeh > 0 and instruments.is_hexagonal(cm) is False


# ---------------------------------------------------------------------------
# 12. Change 0 (#159): the CR30 question must survive a project reopen
#
# TARGET_INSTRUMENT is written by the layout stage into the .ti2 and is NOT in
# the .ti1 at all — but ui/main_window.py hands this tab `run.chart_ti1` when a
# project is opened. Every open-coded read_target_instrument(self._ti1_path)
# therefore read None and silently answered "not a CR30", so the guard below
# was dead on the commonest path. Every test above hands the tab a .ti2, which
# is exactly why none of them caught it.
# ---------------------------------------------------------------------------

def _ti1_with_ti2_sibling(stem: Path, instrument: str) -> Path:
    """A chart pair as the app really writes it: the keyword only in the .ti2.

    Returns the **.ti1**, i.e. what opening a project hands the Measure tab.
    """
    ti1 = stem.with_suffix(".ti1")
    ti1.write_text(
        "CTI1\n\n"
        'DESCRIPTOR "chart"\n'
        'COLOR_REP "RGB"\n\n'
        "NUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n\n"
        "NUMBER_OF_SETS 1\nBEGIN_DATA\n1 100 100 100\nEND_DATA\n",
        encoding="utf-8")
    _ti2_named(stem.with_suffix(".ti2"), instrument)
    return ti1


def test_the_ti1_really_does_not_carry_the_keyword(tmp_path) -> None:
    """The premise, pinned. If a future chart writer starts putting
    TARGET_INSTRUMENT in the .ti1 this test says so, and the resolver below
    becomes belt-and-braces rather than the only thing that works."""
    from ui.ti2_loader import read_target_instrument
    ti1 = _ti1_with_ti2_sibling(tmp_path / "c", "CR30")
    assert read_target_instrument(ti1) is None
    assert read_target_instrument(ti1.with_suffix(".ti2")) == "CR30"


def test_chart_is_cr30_resolves_the_ti2_when_handed_a_ti1(qapp, tmp_path) -> None:
    tab, _ = _measure_tab(tmp_path, "chromiq")
    tab._ti1_path = _ti1_with_ti2_sibling(tmp_path / "c", "CR30")
    assert tab._chart_is_cr30() is True, \
        "opening a project hands the .ti1; the keyword lives in the .ti2"


def test_chart_is_cr30_still_answers_from_a_ti2(qapp, tmp_path) -> None:
    """Boundary: most load paths hand the .ti2 directly, and must be unchanged."""
    tab, _ = _measure_tab(tmp_path, "chromiq")
    tab._ti1_path = _ti2_named(tmp_path / "d.ti2", "CR30")
    assert tab._chart_is_cr30() is True


def test_chart_is_cr30_is_false_for_every_other_chart_and_every_error(
        qapp, tmp_path) -> None:
    tab, _ = _measure_tab(tmp_path, "chromiq")
    tab._ti1_path = _ti1_with_ti2_sibling(tmp_path / "e", "GretagMacbeth i1 Pro")
    assert tab._chart_is_cr30() is False
    # Error cases: never raise, never block.
    tab._ti1_path = None
    assert tab._chart_is_cr30() is False
    tab._ti1_path = tmp_path / "nothing.ti1"          # no sibling .ti2 either
    assert tab._chart_is_cr30() is False
    lone = tmp_path / "lone.ti1"                       # a .ti1 with no .ti2
    lone.write_text("CTI1\n", encoding="utf-8")
    tab._ti1_path = lone
    assert tab._chart_is_cr30() is False


def test_the_stock_chartread_guard_fires_after_a_project_reopen(
        qapp, tmp_path, monkeypatch) -> None:
    """THE BUG. Preferences on ArgyllCMS chartread + a reopened CR30 project:
    before Change 0 the guard read None, returned False, and the measurement
    launched into `Unrecognised chart target instrument 'CR30'`."""
    tab, settings = _measure_tab(tmp_path, "argyll")
    tab._ti1_path = _ti1_with_ti2_sibling(tmp_path / "c", "CR30")
    monkeypatch.setattr(type(tab), "_cr30_stock_reader_window", lambda self: False)
    assert tab._blocked_by_stock_chartread_for_cr30() is True
    assert settings.get("chartread_engine") == "argyll"


def test_the_swipe_arrow_stays_off_after_a_project_reopen(qapp, tmp_path) -> None:
    """A CR30 reads one patch at a time, so there is nothing to swipe. The flag
    is set from _setup_stripe_rects, which used to make the same dead read."""
    tab, _ = _measure_tab(tmp_path, "chromiq")
    seen: list[bool] = []
    tab._preview.set_no_swipe = lambda v: seen.append(v)   # type: ignore[method-assign]
    # _setup_stripe_rects returns early with no pages loaded; one page path is
    # all it needs to reach the flag (the rect detection below it copes with a
    # file that is not there).
    tab._tiff_pages = [tmp_path / "c_01.tif"]
    tab._ti1_path = _ti1_with_ti2_sibling(tmp_path / "c", "CR30")
    tab._setup_stripe_rects()
    assert seen and seen[-1] is True
    seen.clear()
    tab._ti1_path = _ti1_with_ti2_sibling(tmp_path / "f", "GretagMacbeth i1 Pro")
    tab._setup_stripe_rects()
    assert seen and seen[-1] is False, "only a CR30 loses its arrow"


# ---------------------------------------------------------------------------
# 13. Change 0.3/0.4 (#159, finding F5): the SAME unresolved read costs an
#     i1Pro chart its automatic -b. Pre-existing, all instruments, not CR30.
#
# TARGET_INSTRUMENT and printtarg's RANDOM_START are both written by the layout
# stage into the .ti2. Reading them from the .ti1 that a project reopen hands
# this tab returned None and False: no auto -b (the flag that lets a strip be
# swiped either way), a wrong "using Argyll's default strip recognition" log
# line, and the CR30 pace row judged against the i1Pro rate.
# ---------------------------------------------------------------------------

def test_bidir_autodetect_sees_an_i1pro_through_the_ti1(qapp, tmp_path) -> None:
    tab, _ = _measure_tab(tmp_path, "chromiq")
    tab._ti1_path = _ti1_with_ti2_sibling(tmp_path / "c", "GretagMacbeth i1 Pro")
    tab._refresh_bidir_autodetect()
    assert tab._detected_instrument == "GretagMacbeth i1 Pro"
    assert tab._detected_force_bidir is True, \
        "an i1Pro chart must keep its automatic -b after a project reopen"


def test_bidir_autodetect_sees_the_randomisation_through_the_ti1(
        qapp, tmp_path) -> None:
    """RANDOM_START is printtarg's, so it is in the .ti2 only. Read from the
    .ti1 it reported False on a chart that IS randomised."""
    from ui.ti2_loader import is_randomized
    tab, _ = _measure_tab(tmp_path, "chromiq")
    ti1 = _ti1_with_ti2_sibling(tmp_path / "c", "GretagMacbeth i1 Pro")
    ti2 = ti1.with_suffix(".ti2")
    ti2.write_text(ti2.read_text(encoding="utf-8").replace(
        'COLOR_REP "RGB"', 'COLOR_REP "RGB"\nRANDOM_START "17"'), encoding="utf-8")
    assert is_randomized(ti1) is False and is_randomized(ti2) is True, \
        "the premise: the keyword is only in the .ti2"
    tab._ti1_path = ti1
    tab._refresh_bidir_autodetect()
    assert tab._detected_randomized is True


def test_the_pace_key_follows_the_chart_through_the_ti1(qapp, tmp_path) -> None:
    """Without a resolved read the CR30 pace row was judged at the i1Pro rate,
    on a chart that can never produce a strip.

    The discriminator is ``min_samples``: ``defaults_for("cr30")`` is
    ``(100.0, None)`` -> 0, ``defaults_for("i1pro")`` is ``(100.0, 20)``, and
    an unresolved read falls through to the i1Pro entry.
    """
    from core.measure_pace import defaults_for, model_key
    assert model_key("CR30") == "cr30", "the premise, from core.measure_pace"
    assert defaults_for("cr30")[1] is None and defaults_for("i1pro")[1] == 20

    tab, _ = _measure_tab(tmp_path, "chromiq")
    tab._detected_instrument = None       # -x opens no instrument, so nothing reports one
    tab._ti1_path = _ti1_with_ti2_sibling(tmp_path / "c", "CR30")
    assert tab._pace_config().min_samples == 0, \
        "a CR30 chart must not be held to the i1Pro minimum sample count"

    tab._ti1_path = _ti1_with_ti2_sibling(tmp_path / "f", "GretagMacbeth i1 Pro")
    assert tab._pace_config().min_samples == 20, \
        "and an i1Pro chart must still get the i1Pro row"
