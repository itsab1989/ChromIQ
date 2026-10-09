"""Beta 16: the second round of vendor drivers, the Canon quality row, paper feed.

Report folder 2026-10-09_vendor_tests2.  What is pinned here, each test failing
without the change it names:

* the binary media table of the 16.9x Canon drivers (PRO-100, PRO-10S, iP8700,
  iX6800) is read: paper profile per quality, the qualities a paper allows and
  the one the dialog picks.  Beta 15 read nothing from it;
* the Epson models that keep one PDEData.dat per black ink (``Resources/1``,
  ``Resources/2``: Stylus Photo R2400/R2880/2200, SC-P6000 to P9000) are read;
  beta 15 looked for ``Resources/PDEData.dat`` only and found nothing;
* the qualities a paper allows (Canon media database, Epson ``Resolution``
  table), the highest among them, the dialog's standard, and the user's own
  last choice from the learning store: the Print Chart tab's quality row;
* the paper source the Canon dialog moves a paper to (Manual Feed for Baryta,
  fine-art and heavyweight papers) goes on the direct route too;
* every model of the second round has a whole shipped table, and the tables
  agree with the installed drivers (skipped where none is installed);
* measure-dialog never leaves a vendor alert waiting.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from workflow import ppd_color as pc
from workflow.printer_memory import PaperProfileMemory

HERE = Path(__file__).resolve().parent
FIX = HERE / "data" / "printer_drivers"
ROOT = HERE.parent


def _ppd(name: str) -> str:
    return (FIX / "PPDs" / name).read_text(encoding="latin-1")


@pytest.fixture
def fixture_drivers(monkeypatch):
    monkeypatch.setenv(pc.DRIVER_ROOT_ENV, str(FIX))
    return FIX


@pytest.fixture
def no_drivers(monkeypatch, tmp_path):
    monkeypatch.setenv(pc.DRIVER_ROOT_ENV, str(tmp_path / "none"))


def _built() -> dict:
    return json.loads((ROOT / "data" / "printer_paper_profiles.json").read_text(
        encoding="utf-8"))["models"]


def _ppt():
    sys.path.insert(0, str(ROOT / "scripts"))
    import printer_paper_tables as ppt
    return ppt


# ---- 1. the binary Canon media table (16.9x drivers) ------------------------------------
def test_the_binary_canon_table_is_read(fixture_drivers):
    """Beta 15: ``canon_driver_table`` returned {} for these drivers, so the
    PRO-10S, iP8700 and iX6800 were unknown models."""
    t = _ppd("Canon_PRO_10S_series.ppd")
    media = pc.canon_media(t)
    assert set(media) >= {"0", "63", "42", "51", "45", "169", "28"}
    assert media["63"].icc == "Canon PRO-10S series LU3.icc"     # at Normal (10)
    assert media["63"].qualities == ("0", "5", "10")
    assert media["45"].qualities == ("5",) and media["45"].dialog_quality == "5"
    assert media["0"].icc == "CanonIJPrinter2005.icc"             # no record: default
    pp = pc.paper_profile_for(t, {"CNIJMediaType": "63"})
    assert pp.source == "driver" and pp.label == "Canon PRO-10S series LU3.icc"


def test_the_binary_table_profile_follows_the_quality(fixture_drivers):
    """On these drivers the profile depends on the quality: Luster is LU1 at
    Super Fine and Fine, LU3 at Normal.  A chart printed at the photos'
    highest quality must carry the profile of that quality."""
    t = _ppd("Canon_PRO_10S_series.ppd")
    labels = {q: pc.paper_profile_for(t, {"CNIJMediaType": "63", "CNIJPrintQuality": q}).label
              for q in ("0", "5", "10")}
    assert labels == {"0": "Canon PRO-10S series LU1.icc", "5": "Canon PRO-10S series LU1.icc",
                      "10": "Canon PRO-10S series LU3.icc"}


def test_the_binary_table_reproduces_every_pro100_dialog_measurement():
    """All 29 PRO-100 media the round-1 dialog wrote (profile and quality),
    from the installed binary table.  Skipped without the driver."""
    ppt = _ppt()
    text = ppt.installed_ppd("Canon PRO-100 series")
    if text is None or not pc.canon_media(text):
        pytest.skip("no Canon PRO-100 driver installed")
    values = dict(next(v for k, _l, v in pc.parse_ppd_options(text) if k == "CNIJProfileID"))
    for mv, row in _built()["Canon PRO-100 series"]["media"].items():
        m = pc.canon_media(text)[mv]
        assert values[row["profile"]] == m.icc, mv
        assert row["keys"]["CNIJPrintQuality"] == m.dialog_quality, mv


@pytest.mark.parametrize("model", ["Canon PRO-10S series", "Canon iP8700 series",
                                   "Canon iX6800 series"])
def test_the_binary_table_agrees_with_this_rounds_dialogs(model):
    """Every medium measured on the model's real dialog (shipped 'dialog'
    rows): the binary table gives the same profile and quality."""
    ppt = _ppt()
    text = ppt.installed_ppd(model)
    if text is None or not pc.canon_media(text):
        pytest.skip(f"no {model} driver installed")
    values = dict(next(v for k, _l, v in pc.parse_ppd_options(text) if k == "CNIJProfileID"))
    checked = 0
    for mv, row in _built()[model]["media"].items():
        if row.get("from") != "dialog":
            continue
        m = pc.canon_media(text)[mv]
        assert values[row["profile"]] == m.icc, mv
        assert row["keys"].get("CNIJPrintQuality") == m.dialog_quality, mv
        checked += 1
    assert checked >= 10


# ---- 2. Epson: one PDEData.dat per black ink ---------------------------------------------
def test_epson_variant_folders_are_read(fixture_drivers):
    """R2400: Photo Black media in Resources/1, Matte Black media in
    Resources/2.  Beta 15 found no PDEData.dat and knew no profile."""
    t = _ppd("EPSON_Stylus_Photo_R2400.ppd")
    assert [v for v, _p in pc.epson_pde_variants(t)] == ["1", "2"]
    table = pc.epson_driver_table(t)
    assert table["13"] == "11" and table["27"] == "12"     # Photo Black (folder 1)
    assert table["12"] == "2" and table["17"] == "7"        # Matte Black (folder 2)
    assert pc.paper_profile_for(t, {"EPIJ_Medi": "12"}).source == "driver"


def test_a_medium_the_ink_set_folders_disagree_on_is_never_guessed(fixture_drivers, tmp_path):
    """Stylus Photo 2200: Archival Matte is 2 with Photo Black, 3 with Matte
    Black.  The dialog asks the printer; ChromIQ cannot, so it used to take
    the first folder's 2 in silence.  Beta 16 package (Basti, 2026-10-09,
    "never guess"): such a medium is UNKNOWN (the direct route shows
    M-PRINT-PAPER-PROFILE-UNKNOWN), and one dialog print teaches it."""
    t = _ppd("EPSON_Stylus_Photo_2200.ppd")
    assert pc.epson_ink_set_profiles(t, "14") == {"1": "2", "2": "3"}
    assert pc.epson_ink_set_ambiguous(t, "14")
    assert "14" not in pc.epson_driver_table(t)
    pp = pc.paper_profile_for(t, {"EPIJ_Medi": "14"})
    assert pp.source == "unknown" and not pp.known
    # a medium only one folder names is not ambiguous (Premium Semigloss)
    assert not pc.epson_ink_set_ambiguous(t, "15")
    assert pc.paper_profile_for(t, {"EPIJ_Medi": "15"}).source == "driver"
    # the user's own dialog print answers it, with the printer's own edition
    mem = PaperProfileMemory(tmp_path / "m.json")
    mem.record(pc.ppd_model(t), "Epson", "EPIJ_Medi", "14", "EPIJ_Qual", "",
               "EPIJProfileSpec", "3", label=dict(next(
                   v for k, _l, v in pc.parse_ppd_options(t) if k == "EPIJProfileSpec"))["3"],
               keys={})
    pp = pc.paper_profile_for(t, {"EPIJ_Medi": "14"}, learned=mem)
    assert (pp.value, pp.source, pp.known) == ("3", "learned", True)


def test_a_job_read_back_still_names_its_own_profile(fixture_drivers):
    """The ambiguity is about what ChromIQ would SEND; a job read back from
    CUPS carries the profile the dialog chose, and that stays the job's."""
    t = _ppd("EPSON_Stylus_Photo_2200.ppd")
    pp = pc.paper_profile_for(t, {"EPIJ_Medi": "14", "EPIJProfileSpec": "3"},
                              honour_profile_option=True)
    assert (pp.value, pp.source) == ("3", "job")


def test_the_shipped_table_holds_no_ink_set_guess():
    """data/printer_paper_profiles.json carried the SC-P7000/P9000 rows of one
    ink-set edition (and a dialog row measured without a printer to say which
    edition it was).  A built-in row would be used before the learned one, so
    none may stay for a medium whose editions disagree."""
    built = _built()
    for model, mv in (("EPSON SC-P9000 Series", "101"), ("EPSON SC-P9000 Series", "50"),
                      ("EPSON SC-P7000 Series", "101"), ("EPSON Stylus Photo 2200", "14")):
        assert mv not in built[model]["media"], (model, mv)
    # media the editions agree on stay (Standard / plain paper: 1 in both)
    assert built["EPSON SC-P9000 Series"]["media"]["0"]["profile"] == "1"


# ---- 3. the qualities a paper allows -------------------------------------------------------
def test_canon_qualities_include_the_highest(fixture_drivers):
    """Basti, 2026-10-09: PRO-300 Semi-gloss prints at Fine (5) with the
    dialog's Custom slider at the top; its standard is Normal (10)."""
    qc = pc.quality_choices(_ppd("Canon_PRO_300_series.ppd"), {"CNIJMediaType": "42"})
    assert qc.values == ("5", "10") and qc.highest == "5" and qc.standard == "10"
    assert qc.preselect == "10"


def test_the_last_dialog_quality_is_preselected(tmp_path, fixture_drivers):
    mem = PaperProfileMemory(tmp_path / "m.json")
    mem.record("Canon PRO-300 series", "Canon IJ", "CNIJMediaType", "42",
               "CNIJPrintQuality", "5", "CNIJProfileID", "5", label="x.icc",
               keys={"CNIJPrintQuality": "5"})
    qc = pc.quality_choices(_ppd("Canon_PRO_300_series.ppd"), {"CNIJMediaType": "42"},
                            learned=mem)
    assert qc.learned == "5" and qc.preselect == "5"


def test_a_learned_quality_the_paper_does_not_allow_is_not_preselected(tmp_path,
                                                                      fixture_drivers):
    mem = PaperProfileMemory(tmp_path / "m.json")
    mem.record("Canon PRO-300 series", "Canon IJ", "CNIJMediaType", "42",
               "CNIJPrintQuality", "0", "CNIJProfileID", "5", label="x.icc",
               keys={"CNIJPrintQuality": "0"})
    qc = pc.quality_choices(_ppd("Canon_PRO_300_series.ppd"), {"CNIJMediaType": "42"},
                            learned=mem)
    assert qc.learned is None and qc.preselect == "10"


def test_epson_allowed_qualities_match_the_hand_made_et8550_lists(fixture_drivers):
    """The ``Resolution`` table of PDEData.dat gives every list beta 13 copied
    from the ET-8550 dialog by hand, so any Epson model is read the same way."""
    from workflow.print_manager import PrintModule
    t = _ppd("EPSON_ET_8550_Series.ppd")
    for mv, want in PrintModule._EPSON_QUALITY_RULES.items():
        assert set(pc.epson_allowed_qualities(t, mv)) == set(want), mv
    qc = pc.quality_choices(t, {"EPIJ_Medi": "13"})
    assert qc.highest == "306" and qc.standard == "305"


def test_no_quality_choices_without_driver_tables(no_drivers):
    assert pc.quality_choices(_ppd("Canon_PRO_300_series.ppd"), {"CNIJMediaType": "42"}) is None


def test_the_tab_offers_the_canon_quality():
    """Beta 15 matched quality options by label keyword; Canon's is labelled
    just "Quality", so the tab had no Canon quality row at all."""
    from workflow.print_manager import PrintModule
    names = [n for exact, _kw in PrintModule._CATEGORY_SEARCHES for n in exact]
    assert "CNIJPrintQuality" in names
    assert "CNIJPrintQuality" in PrintModule._QUALITY_OPT_NAMES


def test_the_quality_row_follows_the_paper(qapp, monkeypatch, fixture_drivers, tmp_path):
    """The row lists the paper's qualities (no "Printer Default"), marks the
    highest and the standard, preselects, and shows M-PRINT-QUALITY."""
    from PyQt6.QtWidgets import QComboBox, QLabel
    from ui.tabs.tab_print import TabPrint
    from workflow import measurement_messages as MM
    import workflow.printer_memory as pm
    monkeypatch.setenv(pm.MEMORY_FILE_ENV, str(tmp_path / "m.json"))
    monkeypatch.setattr(pc, "ppd_path_for_queue",
                        lambda q: str(FIX / "PPDs" / "Canon_PRO_300_series.ppd"))

    class _Stub:
        pass
    stub = _Stub()
    media, quality, printer = QComboBox(), QComboBox(), QComboBox()
    printer.addItem("Q", "Q")
    media.addItem("Printer Default", "")
    media.addItem("Photo Paper Plus Semi-gloss", "42")
    media.setCurrentIndex(1)
    quality.addItem("Printer Default", "")
    stub._option_combos = {"CNIJMediaType": media, "CNIJPrintQuality": quality}
    stub._printer_combo = printer
    stub._raw_value_pairs = {"CNIJPrintQuality": [
        ("Super Fine", "0"), ("Fine", "5"), ("Normal(Fine)", "10"), ("Normal(Fast)", "15"),
        ("Fast", "20")]}
    stub._quality_note = QLabel()
    stub._quality_choices = None
    stub._update_quality_note = lambda: TabPrint._update_quality_note(stub)
    TabPrint._refresh_quality_row(stub, keep_current=False)
    items = [(quality.itemText(i), quality.itemData(i)) for i in range(quality.count())]
    assert items == [("Fine (highest)", "5"), ("Normal(Fine) (standard)", "10")]
    assert quality.currentData() == "10"
    assert not stub._quality_note.isHidden() or stub._quality_note.text()
    assert MM.M_PRINT_QUALITY.title in stub._quality_note.text()
    assert MM._PRINT_QUALITY_LEARNED not in stub._quality_note.text()
    # after a print through the dialog at Fine, Fine is preselected and said so
    PaperProfileMemory().record("Canon PRO-300 series", "Canon IJ", "CNIJMediaType", "42",
                                "CNIJPrintQuality", "5", "CNIJProfileID", "5",
                                label="x.icc", keys={"CNIJPrintQuality": "5"})
    TabPrint._refresh_quality_row(stub, keep_current=False)
    assert quality.currentData() == "5"
    assert MM._PRINT_QUALITY_LEARNED in stub._quality_note.text()


def test_the_lp_route_sends_the_chosen_quality(fixture_drivers):
    pp = pc.paper_profile_for(_ppd("Canon_PRO_300_series.ppd"),
                              {"CNIJMediaType": "42", "CNIJPrintQuality": "5"})
    assert "CNIJPrintQuality" not in pp.keys()      # the tab's own 5 goes, untouched


# ---- 4. the paper source ------------------------------------------------------------------
def test_canon_baryta_goes_to_manual_feed(fixture_drivers):
    """Measured on 102 media of five models: the dialog moves Baryta, the
    fine-art and the heavyweight papers to Manual Feed (38).  Beta 15 sent
    nothing, so lp printed them from the top feed."""
    t = _ppd("Canon_PRO_300_series.ppd")
    assert pc.paper_profile_for(t, {"CNIJMediaType": "165"}).keys()["CNIJMediaSupply"] == "38"
    assert "CNIJMediaSupply" not in pc.paper_profile_for(t, {"CNIJMediaType": "63"}).keys()


def test_a_paper_source_the_user_chose_is_kept(fixture_drivers):
    t = _ppd("Canon_PRO_300_series.ppd")
    pp = pc.paper_profile_for(t, {"CNIJMediaType": "165", "CNIJMediaSupply": "7"})
    assert "CNIJMediaSupply" not in pp.keys()


def test_the_paper_source_rule_matches_every_dialog_measurement():
    """Every Canon source a real dialog wrote (shipped with the dialog rows)
    is what the media-database rule gives.  Skipped without Canon drivers."""
    ppt = _ppt()
    checked = 0
    for model, entry in _built().items():
        if not model.startswith("Canon"):
            continue
        text = ppt.installed_ppd(model)
        if text is None:
            continue
        for mv, row in entry["media"].items():
            src = (row.get("keys") or {}).get("CNIJMediaSupply")
            if row.get("from") != "dialog" or src is None:
                continue
            rule = pc.canon_driver_source(text, mv)
            if rule is None:          # a binary table: the shipped row says it
                continue
            assert rule == src, (model, mv)
            checked += 1
    if not checked:
        pytest.skip("no Canon driver installed")


# ---- 5. every model of this round ------------------------------------------------------------
ROUND2 = [m for m in _ppt().MODELS if m not in {
    "Canon PRO-300 series", "Canon PRO-310 series", "Canon PRO-200S series",
    "Canon PRO-1000 series", "Canon PRO-1100 series", "Canon PRO-100 series",
    "EPSON ET-8550 Series", "EPSON ET-18100 Series", "EPSON SC-P700 Series",
    "EPSON SC-P900 Series", "EPSON SC-P5300 Series", "EPSON SC-P800 Series",
    "EPSON Epson Stylus Photo R2000", "EPSON Epson Stylus Photo R3000"}]


def test_round_two_lists_every_new_model():
    assert len(ROUND2) >= 30
    for m in ("Canon iP8700 series", "Canon PRO-10S series", "Canon PRO-2100",
              "EPSON XP-15000 Series", "EPSON SC-P600 Series", "EPSON Stylus Photo R2400"):
        assert m in ROUND2


@pytest.mark.parametrize("model", ROUND2)
def test_every_round_two_model_has_a_shipped_table(model):
    """CI has no driver: the shipped table is what the direct route uses there."""
    entry = _built()[model]
    assert entry["media"], model
    assert all(r.get("profile") for r in entry["media"].values())


@pytest.mark.parametrize("model", ROUND2)
def test_round_two_tables_match_the_installed_driver(model):
    """``printer_paper_tables.py check`` for this model; skipped without it."""
    ppt = _ppt()
    text = ppt.installed_ppd(model)
    if text is None:
        pytest.skip(f"{model}: driver not installed")
    built = _built()[model]["media"]
    for mv, row in ppt.driver_media(text).items():
        assert built[mv]["profile"] == row["profile"], (model, mv)


# ---- 6. measure-dialog never leaves a vendor alert waiting ----------------------------------
def test_measure_dialog_answers_or_ends_every_vendor_alert():
    """2026-10-09: the Canon PRO-2100 driver raised its own alert over the
    panel; the timer had pressed Print from inside its own callback, so it
    never ran again, and the alert (drawn by the driver's extension service)
    waited on Basti's screen.  Clicks now go through the run loop, an alert
    inside the probe is answered, one drawn by an extension service ends the
    probe within half a second, and the probe page is A4."""
    import inspect
    ppt = _ppt()
    src = inspect.getsource(ppt)
    driver = src[src.index("class _PanelDriver"):src.index("FIXTURE_MODELS = {")]
    assert "performClick_(None)" not in driver
    assert "_press(" in driver and "ViewBridge" in driver
    assert "REMOTE_ALERT" in inspect.getsource(ppt._run_probe_guarded)
    assert ppt.PROBE_GUARD_S <= 30
    assert "2480, 3508" in inspect.getsource(ppt._make_chart)


# ---- 7. what the Epson dialog writes, worked out from PDEData.dat ----------------------------
@pytest.mark.parametrize("ppd,medium,want", [
    # measured on the real dialogs (vendor tests 2026-10-08 and this round)
    ("EPSON_ET_8550_Series.ppd", "13", {"EPIJ_Mode": "3", "EPIJ_CCor": "3", "EPIJ_Qual": "305"}),
    ("EPSON_ET_8550_Series.ppd", "0", {"EPIJ_Mode": "3", "EPIJ_CCor": "12", "EPIJ_Qual": "303"}),
    ("EPSON_SC_P900_Series.ppd", "13", {"EPIJ_Mode": "0", "EPIJ_APri": "4"}),
    ("EPSON_Stylus_Photo_1400.ppd", "13", {"EPIJ_Mode": "0", "EPIJ_APri": "1", "EPIJ_Qual": "46",
                                          "EPIJ_CCor": "3"}),
    ("EPSON_SC_P6000_Series.ppd", "14", {"EPIJ_MeInSeNm": "2", "EPIJ_MdGropID": "14",
                                         "EPIJ_Qual": "35"}),
    ("EPSON_SC_P6000_Series.ppd", "101", {"EPIJ_MeInSeNm": "1", "EPIJ_Qual": "35"}),
    # the paper configuration of a large-format model (EPIJPaperConfigPreset);
    # thickness, platen gap, suction and roll tension change the printer's
    # own commands (full Epson filter chain, report folder escp/)
    ("EPSON_SC_P6000_Series.ppd", "1950", {"EPIJ_Thck": "1", "EPIJ_PGDt": "4",
                                           "EPIJ_Suct": "4", "EPIJ_RpTn": "2"}),
    ("EPSON_SC_P6000_Series.ppd", "14", {"EPIJ_Thck": "2", "EPIJ_FWea": "1"}),
    ("EPSON_PM_400_Series.ppd", "13", {"EPIJ_Mode": "3", "EPIJ_CCor": "3", "EPIJ_CMat": "0",
                                       "EPIJ_Qual": "305"}),
    ("EPSON_PM_400_Series.ppd", "0", {"EPIJ_CCor": "12", "EPIJ_Qual": "303"}),
])
def test_the_epson_dialog_is_worked_out_from_its_own_data(fixture_drivers, ppd, medium, want):
    """Beta 15 sent EPIJ_Mode 3 to the Stylus Photo 1390/1400, whose dialog
    stays in Automatic mode, the PPD's EPIJ_CCor 12 to an XP-15000 on photo
    paper (its dialog: 3), no black ink to an SC-P6000 on matte paper, and
    knew no quality for an SC-P900."""
    got = pc.epson_dialog_keys(_ppd(ppd), medium)
    assert {k: got.get(k) for k in want} == want


def test_the_direct_route_sends_the_emulated_epson_keys(fixture_drivers):
    keys = pc.paper_profile_for(_ppd("EPSON_Stylus_Photo_1400.ppd"), {"EPIJ_Medi": "13"}).keys()
    assert keys["EPIJ_Mode"] == "0" and keys["EPIJ_Qual"] == "46"
    keys = pc.paper_profile_for(_ppd("EPSON_SC_P6000_Series.ppd"), {"EPIJ_Medi": "14"}).keys()
    assert keys["EPIJ_MeInSeNm"] == "2"


def test_a_chosen_quality_on_an_automatic_epson_switches_to_advanced(fixture_drivers):
    """An automatic Epson dialog prints a chosen quality only in its Advanced
    (custom) mode; the chart then goes the same way."""
    t = _ppd("EPSON_Stylus_Photo_1400.ppd")
    keys = pc.paper_profile_for(t, {"EPIJ_Medi": "13", "EPIJ_Qual": "48"}).keys()
    assert keys["EPIJ_Mode"] == "3" and "EPIJ_APri" not in keys
    keys = pc.paper_profile_for(t, {"EPIJ_Medi": "13", "EPIJ_Qual": "46"}).keys()
    assert keys["EPIJ_Mode"] == "0"


def test_a_picturemate_prints_in_its_dialogs_state(fixture_drivers, monkeypatch):
    """No paper profiles and no "no colour adjustment" on a PictureMate: the
    direct route used to leave Mode 0 (Automatic); its dialog, in application
    colour matching, writes Mode 3, the paper's quality and EPSON Vivid."""
    t = _ppd("EPSON_PM_400_Series.ppd")
    assert pc.paper_profile_for(t, {"EPIJ_Medi": "13"}) is None
    keys = pc.dialog_keys_without_paper_profile(t, {"EPIJ_Medi": "13"})
    assert keys["EPIJ_Mode"] == "3" and keys["EPIJ_CCor"] == "3" and keys["EPIJ_Qual"] == "305"
    assert "EPIJ_Qual" not in pc.dialog_keys_without_paper_profile(
        t, {"EPIJ_Medi": "13", "EPIJ_Qual": "307"})       # the user's own stays
    # and the generic lp route applies them (macOS)
    from workflow import cups_printer as cp
    monkeypatch.setattr(cp.sys, "platform", "darwin")
    monkeypatch.setattr(cp, "vendor_no_cm_settings_for_queue", lambda q: [])
    monkeypatch.setattr(pc, "ppd_path_for_queue",
                        lambda q: str(FIX / "PPDs" / "EPSON_PM_400_Series.ppd"))
    opts = {"EPIJ_Medi": "13"}
    cp.CupsRawPrinter._apply_vendor_no_cm(opts, "PM")
    assert opts["EPIJ_Mode"] == "3" and opts["EPIJ_CCor"] == "3"


def test_a_printer_with_paper_profiles_gets_no_generic_epson_keys(fixture_drivers):
    assert pc.dialog_keys_without_paper_profile(_ppd("EPSON_ET_8550_Series.ppd"),
                                                {"EPIJ_Medi": "13"}) == {}


def test_the_imageprograf_dialog_picks_the_database_default_quality(fixture_drivers):
    """PRO-2100/2600/4100 dialogs wrote the database's default quality (Luster
    15), not the "normal" position the PRO-1000/1100 dialogs use (10)."""
    m = pc.canon_media(_ppd("Canon_PRO_2100.ppd"))
    assert m["63"].dialog_quality == "15"
    assert pc.canon_media(_ppd("Canon_PRO_1000_series.ppd"))["63"].dialog_quality == "10"


def test_every_epson_dialog_measurement_is_reproduced():
    """Each Epson row measured on a real dialog (shipped 'dialog' rows): the
    installed driver's emulation gives the same Mode, CCor, quality and black.
    Skipped without the drivers."""
    ppt = _ppt()
    checked = 0
    for model, entry in _built().items():
        if not model.startswith("EPSON"):
            continue
        text = ppt.installed_ppd(model)
        if text is None:
            continue
        for mv, row in entry["media"].items():
            if row.get("from") != "dialog":
                continue
            emu = pc.epson_dialog_keys(text, mv)
            for k in ("EPIJ_Mode", "EPIJ_CCor", "EPIJ_Qual", "EPIJ_MeInSeNm"):
                if k in row.get("keys", {}) and k in emu:
                    assert row["keys"][k] == emu[k], (model, mv, k)
                    checked += 1
    if not checked:
        pytest.skip("no Epson driver installed")


# ---- 8. the resolution the chart is rasterised at --------------------------------------------
def test_epson_resolution_and_media_type_go_as_the_dialog_sets_them(fixture_drivers):
    """The Epson dialog sets the PPD's own Resolution, MediaType and ColorModel
    from its condition tables.  Beta 15 sent none: the chart reached the Epson
    filter at the PPD's 360x360dpi where the dialog's job has 720x720dpi on
    Premium Glossy, and through the full Epson filter chain the ET-8550's
    stream then differed from the dialog's (ESC/P-R commands and raster);
    with them it is byte-identical (report folder escp/)."""
    keys = pc.paper_profile_for(_ppd("EPSON_ET_8550_Series.ppd"), {"EPIJ_Medi": "13"}).keys()
    assert (keys["Resolution"], keys["MediaType"], keys["ColorModel"]) == (
        "720x720dpi", "13", "RGB")
    plain = pc.paper_profile_for(_ppd("EPSON_ET_8550_Series.ppd"), {"EPIJ_Medi": "0"}).keys()
    assert plain["Resolution"] == "360x360dpi"


@pytest.mark.parametrize("ppd,medium,quality,res", [
    # measured on the real dialogs (this round): 66 of 66 Canon tickets
    ("Canon_PRO_10S_series.ppd", "169", "", "1200x1200dpi"),
    ("Canon_PRO_10S_series.ppd", "63", "", "600x600dpi"),
    ("Canon_PRO_10S_series.ppd", "63", "0", "1200x1200dpi"),   # binary table, Super Fine
    ("Canon_PRO_2100.ppd", "63", "", "600x600dpi"),
    ("Canon_PRO_2100.ppd", "0", "", "300x300dpi"),
])
def test_canon_resolution_goes_as_the_dialog_sets_it(fixture_drivers, ppd, medium, quality, res):
    opts = {"CNIJMediaType": medium}
    if quality:
        opts["CNIJPrintQuality"] = quality
    assert pc.paper_profile_for(_ppd(ppd), opts).keys()["Resolution"] == res


# ---- 9. the DNP dye-sublimation printers -----------------------------------------------------
@pytest.mark.parametrize("ppd,options,profile", [
    ("Dai_Nippon_Printing_DP_DS620.ppd", {}, "DS620(PD)_Natural.icm"),
    ("Dai_Nippon_Printing_DP_DS820.ppd", {}, "DS820(PP)_Classic.icc"),
    ("Dai_Nippon_Printing_DP_DS820.ppd", {"MediaClass": "SD"}, "DS820(SD)_Classic.icc"),
])
def test_a_dnp_job_carries_its_device_profile(ppd, options, profile):
    """The DNP dialog, in application colour matching, tags the job with the
    PPD's device profile for the media class (the same one ColorSync
    registers); the direct route's raw TIFF was converted into it (0 of 21
    chart colours unchanged, white 235,240,235).  The direct route now tags
    the chart with that same profile, as the dialog does."""
    pp = pc.device_profile_without_paper_profiles(_ppd(ppd), options)
    assert pp is not None and pp.label == profile and pp.known
    assert pp.keys() == {}            # no driver key at all, as the dialog
    assert pc.paper_profile_for(_ppd(ppd), options) is None


def test_no_device_profile_route_for_other_printers():
    hp = ('*ModelName: "HP DesignJet Z9"\n*cupsICCProfile RGB../Plain: "/x.icc"\n')
    assert pc.device_profile_without_paper_profiles(hp) is None


def test_the_direct_route_takes_the_dnp_device_profile(monkeypatch, tmp_path):
    from workflow import cups_printer as cp
    monkeypatch.setattr(cp.sys, "platform", "darwin")
    monkeypatch.setattr(pc, "ppd_path_for_queue",
                        lambda q: str(FIX / "PPDs" / "Dai_Nippon_Printing_DP_DS620.ppd"))
    icc = tmp_path / "dnp.icc"
    icc.write_bytes(b"x")
    real = pc.device_profile_without_paper_profiles

    def with_file(text, options=None):
        pp = real(text, options)
        import dataclasses
        return dataclasses.replace(pp, icc_path=str(icc))
    monkeypatch.setattr(pc, "device_profile_without_paper_profiles", with_file)
    monkeypatch.setattr(cp.CupsRawPrinter, "_tiff_n_channels", staticmethod(lambda p: 3))
    pp = cp.CupsRawPrinter._reference_paper_profile(tmp_path / "c.tif",
                                                    cp.PrintConfig(printer_name="DNP", options={}))
    assert pp is not None and pp.rule.vendor == "DNP"


# ---- beta-16 review: what the builder's tests did not pin ------------------------------
def _copy_drivers(tmp_path, monkeypatch):
    import shutil
    root = tmp_path / "drivers"
    shutil.copytree(FIX, root)
    monkeypatch.setenv(pc.DRIVER_ROOT_ENV, str(root))
    pc._canon_media_cached.cache_clear()
    tbl = next(root.glob("Canon/BJPrinter/Resources/Database/CIJPRO10Sseries.db/"
                         "Contents/Resources/cnb_*.tbl"))
    return tbl


@pytest.mark.parametrize("damage", ["truncated", "half", "header only", "zeros", "garbage"])
def test_a_damaged_canon_table_is_an_unknown_model_not_a_crash(tmp_path, monkeypatch, damage):
    """Review: a cut-off cnb_*.tbl decoded 'successfully' with papers whose
    profile records were lost given the default profile as if the driver said
    so, and a short file raised struct.error out of ``canon_media``.  Now a
    table that is not whole is not used at all, and printing goes on."""
    tbl = _copy_drivers(tmp_path, monkeypatch)
    d = tbl.read_bytes()
    tbl.write_bytes({"truncated": d[:-200], "half": d[:len(d) // 2], "header only": d[:0x310],
                     "zeros": bytes(len(d)), "garbage": bytes(range(256)) * (len(d) // 256)}[damage])
    t = _ppd("Canon_PRO_10S_series.ppd")
    assert pc.canon_media(t) == {}
    pp = pc.paper_profile_for(t, {"CNIJMediaType": "63"})
    assert pp is not None and pp.source != "driver"
    assert pc.quality_choices(t, {"CNIJMediaType": "63"}) is None


def test_another_models_canon_table_is_not_read_as_this_ones(tmp_path, monkeypatch):
    """Review: a table that names profiles the PPD does not offer (another
    model's, or a driver update's new layout) is not this driver's table."""
    tbl = _copy_drivers(tmp_path, monkeypatch)
    d = bytearray(tbl.read_bytes())
    d[:] = d.replace(b"Canon PRO-10S series", b"Canon PRO-99X series")
    tbl.write_bytes(bytes(d))
    assert pc.canon_media(_ppd("Canon_PRO_10S_series.ppd")) == {}


@pytest.mark.parametrize("ppd,medium,quality,res", [
    ("EPSON_ET_8550_Series.ppd", "0", "307", "720x720dpi"),    # plain, Best Quality
    ("EPSON_ET_8550_Series.ppd", "0", "302", "180x180dpi"),    # plain, Economy
    ("EPSON_ET_8550_Series.ppd", "13", "308", "360x360dpi"),   # photo paper, Draft
])
def test_the_epson_resolution_follows_the_chosen_quality(fixture_drivers, ppd, medium,
                                                         quality, res):
    """Review: the Epson Resolution table depends on the quality as well as the
    paper.  The direct route sent the resolution of the dialog's OWN quality
    whatever the quality row said (ET-8550 plain paper at Best Quality: 360
    dpi where the dialog writes 720); 623 paper/quality pairs over the
    installed Epson drivers disagreed with the dialog."""
    pp = pc.paper_profile_for(_ppd(ppd), {"EPIJ_Medi": medium, "EPIJ_Qual": quality})
    assert dict(pp.dialog_keys).get("Resolution") == res


def test_a_picturemate_quality_gets_its_own_resolution(fixture_drivers):
    """The same for the PictureMate keys (no paper profiles): plain paper at
    Fine prints at 720 dpi in the dialog, Normal at 360."""
    t = _ppd("EPSON_PM_400_Series.ppd")
    assert pc.dialog_keys_without_paper_profile(t, {"EPIJ_Medi": "0"}).get("Resolution") \
        == "360x360dpi"
    assert pc.dialog_keys_without_paper_profile(
        t, {"EPIJ_Medi": "0", "EPIJ_Qual": "304"}).get("Resolution") == "720x720dpi"


# ---- beta-16 review: a chart larger than the paper is never shrunk in silence -------------
def _a4_tiff(path):
    from PIL import Image
    Image.new("RGB", (2480, 3508), (255, 255, 255)).save(path, format="TIFF", dpi=(300, 300))
    return path


_PAPER_BLOCKS = {
    "EPSON_PM_400_Series.ppd": (
        '*PPD-Adobe: "4.3"\n*ModelName: "EPSON PM-400 Series"\n'
        '*OpenUI *PageSize/Paper Size: PickOne\n*DefaultPageSize: EPPhotoPaperLRoll\n'
        '*PageSize EPKG/10 x 15 cm (4 x 6 in): ""\n*PageSize EPPhotoPaperLRoll/9 x 13 cm: ""\n'
        '*CloseUI: *PageSize\n'
        '*PaperDimension EPKG/10 x 15 cm (4 x 6 in): "288.00 432.00"\n'
        '*PaperDimension EPPhotoPaperLRoll/9 x 13 cm: "252.20 360.00"\n'),
    "Dai_Nippon_Printing_DP_DS620.ppd": (
        '*PPD-Adobe: "4.3"\n*ModelName: "Dai Nippon Printing DP-DS620"\n'
        '*OpenUI *PageSize/Media Size: PickOne\n*DefaultPageSize: dnp6x4\n'
        '*PageSize dnp6x4/6 x 4: ""\n*PageSize dnp6x8/6 x 8: ""\n*CloseUI: *PageSize\n'
        '*PaperDimension dnp6x4/6 x 4: "442.56 297.6"\n'
        '*PaperDimension dnp6x8/6 x 8: "442.56 584.64"\n'),
}


def _small_paper_tab(qapp, tmp_path, monkeypatch, ppd_name, *, preflight):
    from core.settings import AppSettings
    from ui.tabs.tab_print import TabPrint
    s = AppSettings()
    s.set("use_native_print_dialog", False)
    s.set("confirm_before_printing", preflight)
    tab = TabPrint(s)
    # the paper-size block of the installed PPD (the fixtures are trimmed to
    # the colour options): PM-400 default 9 x 13 cm, DS620 default 6 x 4 in
    ppd = tmp_path / ppd_name
    ppd.write_text(_PAPER_BLOCKS[ppd_name], encoding="latin-1")
    monkeypatch.setattr(type(tab._module), "_find_ppd_path", staticmethod(lambda _p: str(ppd)))
    return tab


@pytest.mark.parametrize("ppd_name", ["EPSON_PM_400_Series.ppd", "Dai_Nippon_Printing_DP_DS620.ppd"])
def test_printer_default_paper_is_compared_with_the_chart(qapp, tmp_path, monkeypatch, ppd_name):
    """Measured on screen (capture queues): an A4 chart went to a PM-400 with
    the paper size at "Printer Default" (its 9 x 13 cm) shrunk to fit, and the
    confirmation window said nothing, because nothing was compared.  The
    PPD's default paper is now what the chart is compared with; the job
    itself is unchanged (no page size, no orientation added)."""
    tab = _small_paper_tab(qapp, tmp_path, monkeypatch, ppd_name, preflight=True)
    tif = _a4_tiff(tmp_path / "c.tif")
    orientation, page, mismatch = tab._compute_geometry("Q", {}, tif)
    assert orientation is None and page is None
    assert mismatch and "mismatch" in mismatch
    assert tab._chart_larger_than_page(tif, tab._checked_page_pt)


def test_a_chart_that_fits_is_not_called_too_big(qapp, tmp_path, monkeypatch):
    from ui.tabs.tab_print import TabPrint
    tif = _a4_tiff(tmp_path / "c.tif")
    assert not TabPrint._chart_larger_than_page(tif, (595.0, 842.0))     # A4 on A4
    assert not TabPrint._chart_larger_than_page(tif, (842.0, 1191.0))    # A4 on A3
    assert TabPrint._chart_larger_than_page(tif, (288.0, 432.0))         # A4 on 4 x 6 in


def test_a_too_big_chart_shows_the_confirmation_even_when_it_is_off():
    """The decision in ``_print_pages``: the window that names the mismatch
    shows when the chart would be shrunk, whatever the preflight setting."""
    import inspect
    from ui.tabs.tab_print import TabPrint
    src = inspect.getsource(TabPrint._print_pages)
    assert "_chart_larger_than_page(" in src
    assert 'self._settings.get("confirm_before_printing", True) or too_big' in src
