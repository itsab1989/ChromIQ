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


def test_a_medium_in_both_black_ink_folders_takes_the_first(fixture_drivers):
    """Stylus Photo 2200: Archival Matte is 2 with Photo Black, 3 with Matte
    Black; the dialog (no printer to ask) writes the Photo Black one."""
    t = _ppd("EPSON_Stylus_Photo_2200.ppd")
    assert pc.epson_variant_for(t, "14") == "1"
    assert pc.epson_driver_table(t)["14"] == "2"


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
