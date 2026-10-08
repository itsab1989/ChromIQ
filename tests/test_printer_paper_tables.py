"""Beta 15: the direct route sends the paper profile the vendor's own dialog writes.

Until the vendor tests (2026-10-08) ChromIQ matched a medium to a paper profile by
comparing their NAMES. Measured on the real print dialogs of 13 models that was
right 17 times in 69: the PRO-1000/1100/200S profiles are named "_500_", "_510_",
"_S1MkII_", the PRO-100's are codes, the Epson P/R models' are "Epson SC-P900_700
...". The drivers ship the tables their dialogs read, so ChromIQ reads those
(``workflow/ppd_color.py``), falls back to the tables measured and shipped in
``data/printer_paper_profiles.json`` (``scripts/printer_paper_tables.py``), then to
what the user's own dialog prints taught it (``workflow/printer_memory.py``), and
otherwise says it does not know (M-PRINT-PAPER-PROFILE-UNKNOWN).

What is pinned here, each test failing without the change it names:
* the driver tables, read from small copies of the real driver files
  (tests/data/printer_drivers, written by ``printer_paper_tables.py make-fixtures``);
* the profile and keys for every medium measured on a real dialog, for every
  measured model (``DIALOG_MEASURED``, from the vendor tests' result files);
* that the shipped tables agree with the installed drivers, where they are;
* learning, the unknown-model window, the read-back thread and its timeout.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

import pytest

from workflow import ppd_color as pc
from workflow import print_ticket
from workflow.printer_memory import PaperProfileMemory, learn_from_report, memory_path

HERE = Path(__file__).resolve().parent
FIX = HERE / "data" / "printer_drivers"
ROOT = HERE.parent


def _fixture_ppd(name: str) -> str:
    return (FIX / "PPDs" / name).read_text(encoding="latin-1")


@pytest.fixture
def fixture_drivers(monkeypatch):
    """Point the readers at the driver copies, as if installed."""
    monkeypatch.setenv(pc.DRIVER_ROOT_ENV, str(FIX))
    return FIX


@pytest.fixture
def no_drivers(monkeypatch, tmp_path):
    """No driver installed at all (Linux/Windows CI, or a Mac without it)."""
    monkeypatch.setenv(pc.DRIVER_ROOT_ENV, str(tmp_path / "none"))


#: every medium measured on a real print dialog in application colour matching:
#: (model, medium the dialog wrote, paper profile it wrote, quality (Canon) or
#: EPIJ_Mode/EPIJ_CCor (Epson) it wrote). Vendor tests 2026-10-08
#: (dialog/D_*), print fix 2026-10-08 (native/N_psref_*), and this round
#: (dialog_ET8550).
DIALOG_MEASURED = [
    ("Canon PRO-100 series", "0", "1", "10"), ("Canon PRO-100 series", "149", "20", "10"),
    ("Canon PRO-100 series", "150", "1", "10"), ("Canon PRO-100 series", "16", "1", "10"),
    ("Canon PRO-100 series", "163", "22", "10"), ("Canon PRO-100 series", "169", "23", "10"),
    ("Canon PRO-100 series", "18", "1", "10"), ("Canon PRO-100 series", "27", "1", "10"),
    ("Canon PRO-100 series", "28", "2", "10"), ("Canon PRO-100 series", "31", "1", "10"),
    ("Canon PRO-100 series", "32", "1", "10"), ("Canon PRO-100 series", "42", "4", "10"),
    ("Canon PRO-100 series", "45", "5", "5"), ("Canon PRO-100 series", "49", "6", "10"),
    ("Canon PRO-100 series", "50", "8", "10"), ("Canon PRO-100 series", "51", "10", "10"),
    ("Canon PRO-100 series", "54", "1", "10"), ("Canon PRO-100 series", "56", "1", "10"),
    ("Canon PRO-100 series", "58", "11", "5"), ("Canon PRO-100 series", "59", "5", "5"),
    ("Canon PRO-100 series", "61", "12", "5"), ("Canon PRO-100 series", "63", "14", "10"),
    ("Canon PRO-100 series", "64", "12", "5"), ("Canon PRO-100 series", "66", "15", "10"),
    ("Canon PRO-100 series", "67", "17", "10"), ("Canon PRO-100 series", "68", "1", "10"),
    ("Canon PRO-100 series", "69", "18", "10"), ("Canon PRO-100 series", "7", "1", "10"),
    ("Canon PRO-100 series", "8", "1", "10"),
    ("Canon PRO-1000 series", "0", "1", "10"), ("Canon PRO-1000 series", "17448", "11", "10"),
    ("Canon PRO-1000 series", "28", "7", "10"), ("Canon PRO-1000 series", "51", "4", "10"),
    ("Canon PRO-1000 series", "78", "18", "15"),
    ("Canon PRO-1100 series", "158", "11", "5"), ("Canon PRO-1100 series", "165", "10", "5"),
    ("Canon PRO-1100 series", "78", "17", "10"),
    ("Canon PRO-200S series", "150", "6", "10"), ("Canon PRO-200S series", "28", "7", "5"),
    ("Canon PRO-300 series", "0", "1", "10"), ("Canon PRO-300 series", "158", "11", "10"),
    ("Canon PRO-300 series", "162", "1", "5"), ("Canon PRO-300 series", "165", "10", "5"),
    ("Canon PRO-300 series", "51", "3", "10"), ("Canon PRO-300 series", "63", "4", "10"),
    ("Canon PRO-300 series", "7", "1", "10"), ("Canon PRO-300 series", "78", "17", "5"),
    ("EPSON ET-18100 Series", "0", "1", "3/12"), ("EPSON ET-18100 Series", "142", "1", "3/12"),
    ("EPSON ET-18100 Series", "2", "6", "3/12"),
    ("EPSON ET-8550 Series", "0", "1", "3/12"), ("EPSON ET-8550 Series", "12", "6", "3/3"),
    ("EPSON ET-8550 Series", "13", "3", "3/3"), ("EPSON ET-8550 Series", "142", "1", "3/12"),
    ("EPSON ET-8550 Series", "145", "5", "3/3"), ("EPSON ET-8550 Series", "15", "4", "3/3"),
    ("EPSON ET-8550 Series", "159", "1", "3/3"), ("EPSON ET-8550 Series", "160", "1", "3/3"),
    ("EPSON ET-8550 Series", "187", "1", "3/3"), ("EPSON ET-8550 Series", "2", "8", "3/3"),
    ("EPSON ET-8550 Series", "53", "7", "3/3"), ("EPSON ET-8550 Series", "75", "1", "3/3"),
    ("EPSON ET-8550 Series", "92", "2", "3/3"), ("EPSON ET-8550 Series", "93", "1", "3/12"),
    ("EPSON Epson Stylus Photo R2000", "26", "1", "3/3"),
    ("EPSON Epson Stylus Photo R2000", "97", "5", "3/3"),
    ("EPSON Epson Stylus Photo R3000", "12", "3", "3/4"),
    ("EPSON Epson Stylus Photo R3000", "13", "9", "3/4"),
    ("EPSON Epson Stylus Photo R3000", "2", "8", "3/4"),
    ("EPSON SC-P5300 Series", "101", "6", "0/4"), ("EPSON SC-P700 Series", "13", "2", "0/4"),
    ("EPSON SC-P800 Series", "0", "1", "3/4"), ("EPSON SC-P800 Series", "13", "2", "3/4"),
    ("EPSON SC-P800 Series", "1959", "13", "3/4"), ("EPSON SC-P800 Series", "2", "1", "3/4"),
    ("EPSON SC-P900 Series", "13", "2", "0/4"),
]
MEASURED_MODELS = sorted({m for m, *_ in DIALOG_MEASURED})


def _built() -> dict:
    return json.loads((ROOT / "data" / "printer_paper_profiles.json").read_text(
        encoding="utf-8"))["models"]


# ---- 1. the shipped tables carry every dialog measurement ----------------------------
@pytest.mark.parametrize("model,medium,profile,extra", DIALOG_MEASURED)
def test_the_shipped_table_says_what_the_dialog_wrote(model, medium, profile, extra):
    entry = _built()[model]
    row = entry["media"][medium]
    assert row["profile"] == profile
    keys = {**(entry.get("dialog_keys") or {}), **(row.get("keys") or {})}
    if model.startswith("Canon"):
        assert keys.get("CNIJPrintQuality") == extra
    else:
        mode, ccor = extra.split("/")
        assert (keys.get("EPIJ_Mode"), keys.get("EPIJ_CCor")) == (mode, ccor)


def test_every_measured_model_has_a_whole_table():
    """Not only the measured media: every medium of the model's PPD (the
    drivers' own tables, PRO-100 measured on its dialog for all 29)."""
    built = _built()
    sizes = {m: len(built[m]["media"]) for m in MEASURED_MODELS}
    assert sizes["Canon PRO-100 series"] == 29
    assert sizes["Canon PRO-1000 series"] >= 22 and sizes["EPSON SC-P800 Series"] >= 31
    assert all(n >= 13 for n in sizes.values()), sizes


# ---- 2. the mapping, through paper_profile_for, for every measured medium ------------
_FIXTURE_FOR = {
    "Canon PRO-300 series": "Canon_PRO_300_series.ppd",
    "Canon PRO-1000 series": "Canon_PRO_1000_series.ppd",
    "Canon PRO-100 series": "Canon_PRO_100_series.ppd",
    "EPSON ET-8550 Series": "EPSON_ET_8550_Series.ppd",
    "EPSON SC-P900 Series": "EPSON_SC_P900_Series.ppd",
    "EPSON Epson Stylus Photo R3000": "EPSON_Epson_Stylus_Photo_R3000.ppd",
}


def _ppd_text_for_model(model: str) -> str | None:
    if model in _FIXTURE_FOR:
        return _fixture_ppd(_FIXTURE_FOR[model])
    sys.path.insert(0, str(ROOT / "scripts"))
    import printer_paper_tables as ppt
    return ppt.installed_ppd(model)


@pytest.mark.parametrize("model,medium,profile,extra", DIALOG_MEASURED)
def test_the_lp_route_sends_what_the_dialog_wrote(model, medium, profile, extra, no_drivers):
    """Without any driver installed (CI), from the shipped table alone."""
    text = _ppd_text_for_model(model)
    if text is None:
        pytest.skip(f"no PPD for {model} here")
    opt = "CNIJMediaType" if model.startswith("Canon") else "EPIJ_Medi"
    pp = pc.paper_profile_for(text, {opt: medium})
    assert pp.value == profile and pp.known and pp.source == "built-in"
    keys = pp.keys()
    assert keys[pp.option] == profile
    if model == "Canon PRO-100 series":
        # its profile follows the quality the dialog wrote
        assert keys["CNIJPrintQuality"] == extra
    if not model.startswith("Canon"):
        mode, ccor = extra.split("/")
        assert keys.get("EPIJ_CCor") == ccor
        if mode != "0":
            assert keys.get("EPIJ_Mode") == mode
        assert keys["EPIJ_CMat"] == "3" and keys["EPIJ_OSCMProf"] == "1"


@pytest.mark.parametrize("ppd,medium,profile", [
    ("Canon_PRO_300_series.ppd", "51", "3"), ("Canon_PRO_300_series.ppd", "0", "1"),
    ("Canon_PRO_300_series.ppd", "162", "1"), ("Canon_PRO_300_series.ppd", "165", "10"),
    ("Canon_PRO_1000_series.ppd", "28", "7"), ("Canon_PRO_1000_series.ppd", "51", "4"),
    ("Canon_PRO_1000_series.ppd", "78", "18"), ("Canon_PRO_1000_series.ppd", "17448", "11"),
    ("EPSON_ET_8550_Series.ppd", "142", "1"), ("EPSON_ET_8550_Series.ppd", "75", "1"),
    ("EPSON_ET_8550_Series.ppd", "145", "5"), ("EPSON_SC_P900_Series.ppd", "13", "2"),
    ("EPSON_Epson_Stylus_Photo_R3000.ppd", "13", "9"),
    ("EPSON_Epson_Stylus_Photo_R3000.ppd", "2", "8"),
])
def test_the_driver_table_is_read_first(fixture_drivers, ppd, medium, profile):
    """Read from the driver files themselves (copies), source 'driver'. The old
    name rule gave 1 for PRO-1000 Matte/Platinum/Canvas/Baryta, 0 on the
    SC-P900/R3000 and 0 for ET-8550 Letterhead/Stickers (vendor tests)."""
    text = _fixture_ppd(ppd)
    opt = "CNIJMediaType" if ppd.startswith("Canon") else "EPIJ_Medi"
    pp = pc.paper_profile_for(text, {opt: medium})
    assert pp.value == profile and pp.source == "driver"


def test_driver_table_readers(fixture_drivers):
    t = _fixture_ppd("Canon_PRO_1000_series.ppd")
    table = pc.canon_driver_table(t)
    assert table["28"] == "CN_PRO-1000_500_MattePhotoPaper-P.icc"
    assert table["0"] == "CN_IJPrinter_Profile2015.icc"
    e = _fixture_ppd("EPSON_SC_P900_Series.ppd")
    assert pc.epson_ui_type(e) == "NewUI_J"
    assert pc.epson_driver_table(e)["13"] == "2"
    # the PRO-100's database is a binary table: nothing to read
    assert pc.canon_driver_table(_fixture_ppd("Canon_PRO_100_series.ppd")) == {}


def test_epson_rules_are_first_match_with_conditions():
    rules = [([("EPIJ_Ink_", "0")], "0"), ([("EPIJ_Medi", "13")], "3"), ([], "1")]
    assert pc.epson_condition_value(rules, {"EPIJ_Ink_": "1", "EPIJ_Medi": "13"}) == "3"
    assert pc.epson_condition_value(rules, {"EPIJ_Ink_": "0", "EPIJ_Medi": "13"}) == "0"
    assert pc.epson_condition_value(rules, {"EPIJ_Ink_": "1", "EPIJ_Medi": "7"}) == "1"


def test_no_epson_key_the_ppd_does_not_allow(no_drivers):
    """Beta 15 sent EPIJ_CCor=3 and EPIJ_Mode=3 to the SC-P900, whose PPD offers
    CCor 4/6 only and whose dialog writes Mode 0 (vendor tests)."""
    text = _fixture_ppd("EPSON_SC_P900_Series.ppd")
    keys = pc.paper_profile_for(text, {"EPIJ_Medi": "13"}).keys()
    assert keys.get("EPIJ_CCor") in (None, "4")
    assert keys.get("EPIJ_Mode") in (None, "0")
    blocks = {k: {v for v, _ in vals} for k, _l, vals in pc.parse_ppd_options(text)}
    for k, v in keys.items():
        assert v in blocks[k], (k, v)


# ---- 3. the shipped tables against the installed drivers -----------------------------
def test_the_shipped_tables_match_the_installed_drivers():
    """Skipped where no measured model's driver is installed (CI)."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import printer_paper_tables as ppt
    if not any(ppt.installed_ppd(m) for m in ppt.MODELS):
        pytest.skip("no vendor driver installed")
    assert ppt.check() == []


# ---- 4. unknown model --------------------------------------------------------------------
def _unknown_canon() -> str:
    """A PRO-300 PPD renamed to a model no table knows, without its database."""
    t = _fixture_ppd("Canon_PRO_300_series.ppd")
    t = t.replace("Canon PRO-300 series", "Canon PRO-999 series")
    return "\n".join(line for line in t.splitlines()
                     if not line.startswith("*CNIJNameTblPath"))


def test_an_unknown_model_is_not_guessed(fixture_drivers):
    pp = pc.paper_profile_for(_unknown_canon(), {"CNIJMediaType": "51"})
    assert pp is not None and not pp.known and pp.source == "unknown"
    # the dialog route still treats it as a paper-profile printer (works for any)
    assert pp.value == "1" and pp.is_default


def test_a_printer_without_paper_profiles_is_not_a_paper_profile_printer():
    hp = ('*ModelName: "HP DeskJet"\n*OpenUI *ColorModel/Color: PickOne\n'
          '*ColorModel RGB/Color: ""\n*CloseUI: *ColorModel\n')
    assert pc.paper_profile_for(hp) is None


# ---- 5. learning -------------------------------------------------------------------------
def _report(model_ppd: str, carried: dict) -> print_ticket.TicketReport:
    pp = pc.paper_profile_for(model_ppd, carried, honour_profile_option=True)
    return print_ticket.TicketReport(queue="Q", job_id=5, read=True, expected={},
                                     carried=carried, paper_profile=pp)


def test_a_dialog_print_teaches_the_direct_route(tmp_path, fixture_drivers):
    mem = PaperProfileMemory(tmp_path / "m.json")
    text = _unknown_canon()
    assert not pc.paper_profile_for(text, {"CNIJMediaType": "51"}, learned=mem).known
    rep = _report(text, {"AP_ColorMatchingMode": "AP_ApplicationColorMatching",
                         "CNIJMediaType": "51", "CNIJProfileID": "3",
                         "CNIJPrintQuality": "5"})
    assert learn_from_report(rep, mem) is True
    assert learn_from_report(rep, mem) is False      # already known
    pp = pc.paper_profile_for(text, {"CNIJMediaType": "51"}, learned=mem)
    assert pp.known and pp.source == "learned" and pp.value == "3"
    # the tab has no Canon quality control: the dialog's quality goes too
    assert pp.keys()["CNIJPrintQuality"] == "5"
    # another medium is still unknown
    assert not pc.paper_profile_for(text, {"CNIJMediaType": "28"}, learned=mem).known


def test_learning_is_per_quality_where_the_tab_has_one(tmp_path):
    mem = PaperProfileMemory(tmp_path / "m.json")
    mem.record("EPSON XP-1", "Epson", "EPIJ_Medi", "13", "EPIJ_Qual", "303",
               "EPIJProfileSpec", "3", keys={"EPIJ_Qual": "303", "EPIJ_Mode": "3"})
    exact = mem.lookup("EPSON XP-1", "EPIJ_Medi", "13", "EPIJ_Qual", "303")
    assert exact["value"] == "3"
    # another quality: the one value seen is used, at the tab's own quality
    other = mem.lookup("EPSON XP-1", "EPIJ_Medi", "13", "EPIJ_Qual", "304")
    assert other["value"] == "3" and "EPIJ_Qual" not in other["keys"]
    mem.record("EPSON XP-1", "Epson", "EPIJ_Medi", "13", "EPIJ_Qual", "305",
               "EPIJProfileSpec", "4")
    assert mem.lookup("EPSON XP-1", "EPIJ_Medi", "13", "EPIJ_Qual", "304") is None


def test_nothing_is_learned_from_a_job_without_application_matching(tmp_path, fixture_drivers):
    mem = PaperProfileMemory(tmp_path / "m.json")
    rep = _report(_unknown_canon(), {"CNIJMediaType": "51", "CNIJProfileID": "3"})
    assert learn_from_report(rep, mem) is False
    assert not (tmp_path / "m.json").exists()


def test_the_memory_lives_in_the_settings_folder_and_follows_a_sandbox(monkeypatch, tmp_path):
    from workflow.printer_memory import MEMORY_FILE_ENV
    monkeypatch.delenv(MEMORY_FILE_ENV, raising=False)
    monkeypatch.setenv("CHROMIQ_SETTINGS_FILE", str(tmp_path / "drv.ini"))
    assert memory_path() == tmp_path / "drv.printer_paper_profiles.json"
    monkeypatch.delenv("CHROMIQ_SETTINGS_FILE")
    monkeypatch.setenv("CHROMIQ_PRESETS_DIR", str(tmp_path / "prefs" / "presets"))
    assert memory_path() == tmp_path / "prefs" / "printer_paper_profiles.json"


def test_the_memory_is_not_a_per_target_setting():
    """docs/design/per_target_settings.md 1.1: the user's setup stays global;
    the memory is a file of its own, never a run's or a project's."""
    src = (ROOT / "workflow" / "printer_memory.py").read_text(encoding="utf-8")
    assert "per_target_settings.md" in src
    assert "project" not in src.lower().split('"""', 2)[2]


# ---- 6. the read-back: off the GUI thread, with a timeout ---------------------------
def test_the_read_back_runs_on_its_own_thread():
    seen = {}

    def work():
        seen["thread"] = threading.current_thread()
        return print_ticket.TicketReport(queue="Q", job_id=1, read=True, expected={})
    rb = print_ticket.BackgroundReadBack(work, timeout=5)
    for _ in range(100):
        if rb.poll() != "pending":
            break
        time.sleep(0.02)
    assert rb.poll() == "done" and rb.report.read
    assert seen["thread"] is not threading.main_thread()


def test_the_read_back_gives_up_at_its_timeout():
    release = threading.Event()

    def work():
        release.wait(5)
        return None
    rb = print_ticket.BackgroundReadBack(work, timeout=0.2)
    assert rb.poll() == "pending"
    time.sleep(0.3)
    assert rb.poll() == "timeout"
    release.set()


def test_a_failing_read_back_is_reported_not_raised():
    def work():
        raise RuntimeError("cupsd gone")
    rb = print_ticket.BackgroundReadBack(work, timeout=5)
    for _ in range(100):
        if rb.poll() == "done":
            break
        time.sleep(0.02)
    assert rb.report is None and isinstance(rb.error, RuntimeError)


def test_the_tab_never_reads_back_on_the_gui_thread():
    import inspect
    from ui.tabs import tab_print
    lp = inspect.getsource(tab_print.TabPrint._read_back_lp_job)
    assert "_start_read_back(" in lp and "check_job(" not in lp
    native = inspect.getsource(tab_print.TabPrint._print_native)
    assert "_start_read_back(" in native and "read_back(" not in native.replace(
        "_start_read_back(", "")
    npm_src = (ROOT / "workflow" / "native_print_macos.py").read_text(encoding="utf-8")
    body = npm_src[npm_src.index("def print_frames("):]
    assert "check_job(" not in body and "find_job(" not in body


def test_a_timed_out_read_back_says_the_job_was_not_confirmed(qapp, monkeypatch):
    from ui.tabs.tab_print import TabPrint
    from workflow import measurement_messages as MM

    class _Stub:
        _read_backs: list
        status = ""

        def _set_status(self, text):
            self.status = text

        def _report_job_ticket(self, rep):
            raise AssertionError("no report after a timeout")
    stub = _Stub()

    class _RB:
        report = None
        error = None

        def poll(self):
            return "timeout"
    stub._read_backs = [_RB()]

    class _T:
        def stop(self):
            stub.stopped = True
    stub._read_back_timer = _T()
    TabPrint._poll_read_backs(stub)
    assert stub.status == MM._PRINT_JOB_UNREAD and stub.stopped


# ---- 7. the windows ----------------------------------------------------------------------
def test_untagged_only_gets_its_own_window(qapp, monkeypatch):
    """Review 2026-10-08: "other colour settings than ChromIQ asked for" was
    wrong when the only problem is the missing paper profile."""
    from ui.tabs import tab_print
    from workflow import measurement_messages as MM
    shown = []
    monkeypatch.setattr(tab_print, "warn", lambda parent, title, body: shown.append(title))

    class _Stub:
        status = ""

        def _set_status(self, text):
            self.status = text

        def _show_job_not_as_sent(self, rep):
            shown.append("NOT-AS-SENT")
    rep = print_ticket.TicketReport(queue="Q", job_id=3, read=True, expected={},
                                    tag_matches_job=False)
    tab_print.TabPrint._report_job_ticket(_Stub(), rep)
    assert shown == [MM.M_PRINT_JOB_UNTAGGED.title]
    shown.clear()
    rep.mismatches = {"CNIJProfileID": (None, "3")}
    tab_print.TabPrint._report_job_ticket(_Stub(), rep)
    assert shown == ["NOT-AS-SENT"]


def test_unknown_model_window_offers_the_dialog(qapp, monkeypatch, fixture_drivers):
    from PyQt6.QtWidgets import QMessageBox
    from ui.tabs.tab_print import TabPrint
    from workflow import measurement_messages as MM
    pp = pc.paper_profile_for(_unknown_canon(), {"CNIJMediaType": "51"})
    seen = {}

    def fake_exec(box):
        seen["title"] = box.windowTitle()
        seen["text"] = box.text()
        seen["informative"] = box.informativeText()
        seen["buttons"] = [b.text() for b in box.buttons()]
        dialog = next(b for b in box.buttons() if b.text() == MM._PRINT_UNKNOWN_BTN_DIALOG)
        dialog.click()
        return 0
    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    from PyQt6.QtWidgets import QWidget
    parent = QWidget()
    choice = TabPrint._ask_unknown_paper_profile(parent, "Q_PRO999", pp)
    assert choice == "dialog"
    # Qt on macOS shows no title on a message box, so the TITLE is the box's
    # own first line, as in the other §M windows (beta-15 sweep: the window
    # showed no title at all), and the body is its informative text.
    title, _body = MM.M_PRINT_PAPER_PROFILE_UNKNOWN.render(
        printer="Q_PRO999", medium=pp.media_label, profile=pp.label)
    assert seen["text"] == title
    assert title == "ChromIQ does not know this printer\u2019s paper profiles yet"
    body = seen["informative"]
    assert "Q_PRO999" in body and "Photo Paper Pro Platinum" in body
    assert pp.label in body
    assert MM._PRINT_UNKNOWN_BTN_ANYWAY in seen["buttons"]
    parent.deleteLater()


def test_the_direct_route_asks_before_printing_an_unknown_model():
    import inspect
    from ui.tabs.tab_print import TabPrint
    src = inspect.getsource(TabPrint._print_pages)
    i_ask = src.index("_ask_unknown_paper_profile(")
    assert src.index("_unknown_paper_profile(") < i_ask < src.index("_show_preflight(")
    assert "self._print_native(pages, printer=printer)" in src


def test_off_macos_nothing_is_asked(monkeypatch, tmp_path):
    """Linux/Windows keep the beta 14 job: no paper-profile question."""
    from ui.tabs import tab_print
    monkeypatch.setattr(tab_print, "is_macos", lambda: False)
    assert tab_print.TabPrint._unknown_paper_profile(None, "Q", {}, tmp_path / "x.tif") is None


def test_the_built_in_tables_ship_in_the_bundle():
    assert "data/printer_paper_profiles.json" in (ROOT / "ChromIQ.spec").read_text(
        encoding="utf-8")


# ---- 8. review 2 (2026-10-08): quality, the learning store, the windows ---------------
@pytest.mark.parametrize("ppd,medium,quality", [
    # measured on the real dialogs (vendor tests and review 2, dialog_canon/):
    ("Canon_PRO_1000_series.ppd", "78", "15"), ("Canon_PRO_1000_series.ppd", "63", "10"),
    ("Canon_PRO_1000_series.ppd", "0", "10"), ("Canon_PRO_1000_series.ppd", "51", "10"),
    ("Canon_PRO_300_series.ppd", "165", "5"), ("Canon_PRO_300_series.ppd", "162", "5"),
    ("Canon_PRO_300_series.ppd", "63", "10"), ("Canon_PRO_300_series.ppd", "0", "10"),
])
def test_canon_quality_is_the_dialogs_own_for_the_medium(fixture_drivers, ppd, medium, quality):
    """The quality is part of the printer state a profile describes. Before
    review 2 lp sent no quality, so the PPD's 10 printed PRO-1000 Canvas and
    the fine-art papers at quality type 3 where the dialog prints type 4."""
    text = _fixture_ppd(ppd)
    assert pc.canon_driver_qualities(text)[medium] == quality


def test_canon_quality_rule_without_a_shipped_value(fixture_drivers, monkeypatch):
    """A Canon model the shipped tables do not list still gets the dialog's
    quality, from its own media database."""
    monkeypatch.setattr(pc, "built_in_model", lambda model: None)
    pp = pc.paper_profile_for(_fixture_ppd("Canon_PRO_1000_series.ppd"),
                              {"CNIJMediaType": "78"})
    assert pp.source == "driver" and pp.keys()["CNIJPrintQuality"] == "15"


@pytest.mark.parametrize("ppd,medium,quality", [
    # the vendor tests' dialog measurements (EPIJ_Qual the dialog wrote)
    ("EPSON_ET_8550_Series.ppd", "142", "303"), ("EPSON_ET_8550_Series.ppd", "145", "305"),
    ("EPSON_ET_8550_Series.ppd", "75", "305"), ("EPSON_ET_8550_Series.ppd", "13", "305"),
    ("EPSON_Epson_Stylus_Photo_R3000.ppd", "12", "36"),
    ("EPSON_Epson_Stylus_Photo_R3000.ppd", "2", "35"),
])
def test_epson_quality_left_alone_is_the_dialogs_own(fixture_drivers, ppd, medium, quality):
    pp = pc.paper_profile_for(_fixture_ppd(ppd), {"EPIJ_Medi": medium})
    assert pp.keys()["EPIJ_Qual"] == quality


def test_an_epson_quality_the_user_chose_is_kept(fixture_drivers):
    pp = pc.paper_profile_for(_fixture_ppd("EPSON_ET_8550_Series.ppd"),
                              {"EPIJ_Medi": "13", "EPIJ_Qual": "306"})
    assert "EPIJ_Qual" not in pp.keys()   # the tab's own 306 goes, untouched


def test_newui_j_epson_gets_no_guessed_quality(fixture_drivers):
    """SC-P900/P700/P5300 dialogs set quality another way (EPIJ_APri):
    nothing is sent that was not measured."""
    pp = pc.paper_profile_for(_fixture_ppd("EPSON_SC_P900_Series.ppd"), {"EPIJ_Medi": "13"})
    assert "EPIJ_Qual" not in pp.keys()


def test_a_damaged_memory_file_never_stops_a_print(tmp_path, fixture_drivers):
    f = tmp_path / "m.json"
    for raw in ("{", "[]", '{"models": 5}',
                '{"models": {"Canon PRO-999 series": 5, "X": {"k": "bad"},'
                ' "Y": {"k": {"value": 3}}}}'):
        f.write_text(raw, encoding="utf-8")
        mem = PaperProfileMemory(f)
        assert mem.lookup("Canon PRO-999 series", "CNIJMediaType", "51") is None
        pp = pc.paper_profile_for(_unknown_canon(), {"CNIJMediaType": "51"}, learned=mem)
        assert not pp.known
        assert mem.record("Canon PRO-999 series", "Canon IJ", "CNIJMediaType", "51",
                          "CNIJPrintQuality", "10", "CNIJProfileID", "3",
                          label="CN_PRO-300_G1_PhotoPaperProPlatinum.icc")
        assert pc.paper_profile_for(_unknown_canon(), {"CNIJMediaType": "51"},
                                    learned=mem).source == "learned"


def test_a_learned_value_the_driver_now_means_differently_is_not_used(tmp_path,
                                                                      fixture_drivers):
    """A driver update can renumber its paper profiles: the label learned
    with the value must still be the PPD's label for it."""
    mem = PaperProfileMemory(tmp_path / "m.json")
    mem.record("Canon PRO-999 series", "Canon IJ", "CNIJMediaType", "51",
               "CNIJPrintQuality", "10", "CNIJProfileID", "3",
               label="CN_PRO-300_G1_SomethingElse.icc")
    pp = pc.paper_profile_for(_unknown_canon(), {"CNIJMediaType": "51"}, learned=mem)
    assert not pp.known


def test_the_memory_keeps_no_queue_or_path(tmp_path, fixture_drivers):
    mem = PaperProfileMemory(tmp_path / "m.json")
    mem.record("Canon PRO-999 series", "Canon IJ", "CNIJMediaType", "51",
               "CNIJPrintQuality", "10", "CNIJProfileID", "3", label="x.icc",
               queue="Bastis_Drucker_im_Buero")
    raw = (tmp_path / "m.json").read_text(encoding="utf-8")
    assert "Bastis" not in raw and "/Users/" not in raw and "queue" not in raw


def test_several_finished_read_backs_open_one_window_at_a_time(qapp):
    """A report can open a modal window whose event loop fires the poll timer
    again; the second report must wait for the first window to close."""
    from ui.tabs.tab_print import TabPrint
    events = []

    class _RB:
        def __init__(self, name):
            self.report, self.error = name, None

        def poll(self):
            return "done"

    class _T:
        def stop(self):
            events.append("stop")

    class _Stub:
        _read_backs = [_RB("a"), _RB("b")]
        _read_back_timer = _T()

        def _set_status(self, text):
            pass

        def _report_job_ticket(self, rep):
            events.append(f"open {rep}")
            TabPrint._poll_read_backs(self)   # the modal's event loop
            events.append(f"close {rep}")
    TabPrint._poll_read_backs(_Stub())
    assert events[:4] == ["open a", "close a", "open b", "close b"]


def test_print_anyway_does_not_claim_photoshop_state(qapp, monkeypatch, fixture_drivers,
                                                     tmp_path):
    """After "Print Anyway" the confirmation window must not say the printer's
    own processing is "as for prints from Photoshop": nobody knows that there."""
    from ui.tabs.tab_print import TabPrint
    from workflow import measurement_messages as MM
    from workflow.cups_printer import CupsRawPrinter
    pp = pc.paper_profile_for(_unknown_canon(), {"CNIJMediaType": "51"})
    monkeypatch.setattr(CupsRawPrinter, "_reference_paper_profile",
                        staticmethod(lambda tiff, cfg: pp))
    rows = TabPrint._colour_rows(None, "Q", {}, tmp_path / "x.tif")
    names = [r[0] for r in rows]
    assert MM._PRINT_ROW_PAPER_PROFILE in names
    assert MM._PRINT_ROW_PRINTER_COLOUR not in names


def test_the_built_in_tables_ship_on_every_platform():
    for spec in ("ChromIQ.spec", "ChromIQWin.spec", "ChromIQLinux.spec"):
        assert "printer_paper_profiles.json" in (ROOT / spec).read_text(encoding="utf-8")


def test_the_canon_quality_rule_matches_every_dialog_measurement():
    """Every Canon quality measured on a real dialog (shipped as 'dialog'
    entries) is what the media-database rule gives. Skipped where the Canon
    drivers are not installed (CI); here it is the proof of the rule."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import printer_paper_tables as ppt
    checked = 0
    for model, entry in _built().items():
        if not model.startswith("Canon") or model == "Canon PRO-100 series":
            continue
        text = ppt.installed_ppd(model) if model in ppt.MODELS else None
        if text is None:
            continue
        rule = pc.canon_driver_qualities(text)
        for mv, row in entry.get("media", {}).items():
            q = (row.get("keys") or {}).get("CNIJPrintQuality")
            if row.get("from") == "dialog" and q is not None:
                assert rule.get(mv) == q, (model, mv)
                checked += 1
    if not checked:
        pytest.skip("no Canon driver installed")
