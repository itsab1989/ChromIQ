"""B5, 2026-10-10 (4.3.4 beta 1): Basti's two approved printing texts switched
on, where they are true and nowhere else, and the Epson's own colour matching
chosen in the macOS print dialog's Color Matching panel.

* M-PRINT-VERIFY-ROUTE (approved, "text approved"): the Print Chart tab, macOS,
  a verification run with a chart loaded, both routes; its second paragraph
  (about the macOS print dialog) only while the dialog route is on.
* M-PRINT-JOB-TAGGED-INTENT (approved, wording unchanged): the status line on a
  PostScript queue ONLY. Review R3 measured it true there (1,372,807 of
  1,372,807 chart pixels unchanged) and untrue on a generic CMYK raster queue,
  where macOS converts from the chart's tag and ignores the job's profile.
* Epson: choosing the Epson option instead of ColorSync in the Color Matching
  panel put EPIJ_OSColMat=1 on the job (R3, and again in B5 with the lock
  withheld), and the status line still confirmed it. The dialog route now sets
  it back to 2 after the dialog and reads it back: measured on an ET-8550
  capture queue, the job then carries 2 and its raster is byte-identical to the
  job with the panel left alone
  (~/Desktop/ChromIQ-work/2026-10-10_434b1_B5/runs/e_inprinter_fix, _ctl).
"""
from __future__ import annotations

import sys

import pytest

from workflow import measurement_messages as MM
from workflow import native_print_macos as npm
from workflow import print_ticket as pt
from workflow.ppd_color import dialog_route_colour_locks, is_postscript_queue

from tests.test_print_like_photoshop import CANON_PPD, EPSON_PPD, _ppd

#: Basti's approved English, as he wrote it (straight apostrophes; the
#: catalogue writes the typographic one, as every approved text does)
APPROVED_VERIFY_ROUTE = (
    "Print this chart on the same printer, paper, media type and quality as the "
    "profiling chart this profile was made from, and by the same route (the macOS "
    "print dialog, or straight to the printer). The profile describes the printer "
    "only in that state.\n\nLeave the colour settings in the macOS print dialog as "
    "they are, including its Color Matching panel. When macOS prints the job with "
    "a Canon or Epson paper profile, or with a profile set for a PostScript "
    "printer in ColorSync Utility, ChromIQ gives the chart that same profile after "
    "you close the dialog, so macOS does not change the chart's colours.\n\nOn a "
    "PostScript printer the two routes do not reach the printer in the same form: "
    "the dialog sends the chart's colour values marked as sRGB, which the printer "
    "converts with its own colour rendering, and the direct route sends them as "
    "the printer's own RGB. Print the profiling chart and its verification charts "
    "the same way.")
APPROVED_EPSON_RESET = (
    "In the Color Matching panel the Epson colour matching was chosen instead "
    "of ColorSync. ChromIQ set it back to ColorSync, as a print from Photoshop "
    "is sent, so the job is the same as with the panel left alone.")
APPROVED_TAGGED_INTENT = (
    "The chart went with the profile macOS prints this job with ({profile}) "
    "attached, so macOS leaves its colours unchanged.")

GENERIC_PS = ('*PPD-Adobe: "4.3"\n*ModelName: "Generic PostScript Printer"\n'
              '*ColorDevice: True\n')
#: the CUPS sample HP DeskJet raster PPD R3 measured (CMYK by default)
SAMPLE_RASTER = ('*PPD-Adobe: "4.3"\n*ModelName: "HP DeskJet Series"\n'
                 '*cupsFilter: "application/vnd.cups-raster 0 rastertohp"\n'
                 '*DefaultColorModel: CMYK\n')


# ---- the two texts are approved, in Basti's words ---------------------------
def test_the_verification_route_text_is_bastis_word_for_word():
    m = MM.M_PRINT_VERIFY_ROUTE
    assert m.approved and m.title == "Printing a verification chart"
    assert m.body.replace("’", "'") == APPROVED_VERIFY_ROUTE
    assert "M-PRINT-VERIFY-ROUTE" not in MM.PROPOSED


def test_the_tagged_intent_text_is_unchanged_and_approved():
    m = MM.M_PRINT_JOB_TAGGED_INTENT
    assert m.approved and m.body == APPROVED_TAGGED_INTENT
    assert "M-PRINT-JOB-TAGGED-INTENT" not in MM.PROPOSED


def test_the_epson_texts_are_approved_in_their_proposed_words():
    """Basti, 2026-10-10 ("text approved"): both Epson texts exactly as B5
    proposed them; they left §M-PROPOSED and are shown (see the tests at the
    end of this file for where)."""
    for mid in ("M-PRINT-JOB-EPSON-MATCHING-RESET", "M-PRINT-JOB-EPSON-MATCHING"):
        assert mid not in MM.PROPOSED and MM.CATALOGUE[mid].approved
    assert MM.M_PRINT_JOB_EPSON_MATCHING_RESET.body == APPROVED_EPSON_RESET
    assert MM.M_PRINT_JOB_EPSON_MATCHING.title == (
        "The Epson driver may change this chart\u2019s colours")


# ---- which queue is a PostScript queue -------------------------------------
@pytest.mark.parametrize("text,expected", [
    (GENERIC_PS, True),                                              # Knut's HP CLJ5550
    (GENERIC_PS + '*cupsFilter: "application/vnd.cups-postscript 0 hpps"\n', True),
    (SAMPLE_RASTER, False),                                          # R3's raster queue
    ('*cupsFilter: "application/vnd.cups-raster 100 rastertogutenprint.5.3"\n', False),
    ('*cupsFilter2: "application/vnd.cups-pdf application/pdf 10 -"\n', False),
    ('*cupsFilter2: "image/urf image/urf 100 -"\n', False),
    (GENERIC_PS + '*cupsFilter: "application/vnd.cups-postscript 0 a"\n'
     '*cupsFilter: "application/vnd.cups-raster 0 b"\n', False),
    # R5: a filter for CUPS command files (cleaning, nozzle check) is not one
    # for print data; a PostScript PPD with one is still a PostScript queue,
    # and the Canon IJ / Epson PPDs, which carry one too, still are not
    (GENERIC_PS + '*cupsFilter: "application/vnd.cups-postscript 0 hpps"\n'
     '*cupsFilter: "application/vnd.cups-command 0 commandtops"\n', True),
    (GENERIC_PS + '*cupsFilter2: "application/vnd.cups-command application/postscript 0 commandtops"\n', True),
    ('*cupsFilter: "application/vnd.cups-raster 0 Raster2CanonIJ2S"\n'
     '*cupsFilter: "application/vnd.cups-command 0 Command2CanonIJ2"\n', False),
    (None, False), ("", False),
])
def test_a_postscript_queue_is_one_whose_ppd_takes_postscript(text, expected):
    assert is_postscript_queue(text) is expected


# ---- read_back: the tagged-intent sentence on PostScript queues only -------
@pytest.fixture
def queue(monkeypatch, tmp_path):
    """read_back against a queue whose PPD is *text*; CUPS is not asked."""
    def use(text):
        ppd = tmp_path / "q.ppd"
        ppd.write_text(text, encoding="utf-8")
        from workflow.print_manager import PrintModule
        monkeypatch.setattr(PrintModule, "find_ppd_path", staticmethod(lambda q: str(ppd)))
        monkeypatch.setattr(npm, "_queue_name", lambda d: "Q")
        monkeypatch.setattr(pt, "find_job", lambda q, since: 50)
        monkeypatch.setattr(
            pt, "check_job",
            lambda q, job, exp, ppd_text=None, tagged_with=None, tagged_icc=None:
            pt.TicketReport(queue=q, job_id=job, read=True, expected=dict(exp),
                            tagged_with=tagged_with))
    return use


def _sub(tagged: bytes):
    return npm.Submission("Q", dict(npm._LOCKED_COLOR_SETTINGS), 0.0, tagged,
                          "Knut 2026.02.09" if tagged else None,
                          output_intent="Knut 2026.02.09")


def test_a_postscript_queue_names_the_profile_the_chart_went_with(queue):
    """MUTATION: drop `is_postscript_queue(...)` from read_back's condition and
    the raster test below goes red; drop the whole block and this one does."""
    queue(GENERIC_PS)
    rep = npm.read_back(_sub(b"icc"))
    assert rep.ok and rep.tagged_intent == "Knut 2026.02.09"


def test_a_raster_queue_never_gets_the_sentence(queue):
    """R3: on the CUPS sample HP DeskJet (CMYK raster) with a ColorSync
    profile, macOS converts from the chart's tag: the sentence is untrue."""
    queue(SAMPLE_RASTER)
    rep = npm.read_back(_sub(b"icc"))
    assert rep.tagged_intent is None


def test_an_untagged_chart_never_gets_the_sentence(queue):
    queue(GENERIC_PS)
    rep = npm.read_back(_sub(b""))
    assert rep.tagged_intent is None and not rep.ok      # M-PRINT-JOB-UNTAGGED


def _status_of(rep):
    from ui.tabs import tab_print as tp
    seen = {}
    tab = tp.TabPrint.__new__(tp.TabPrint)
    tab._set_status = lambda text: seen.setdefault("status", text)
    tp.TabPrint._report_job_ticket(tab, rep)
    return seen["status"]


def test_the_status_line_says_it_after_line_2():
    rep = pt.TicketReport(queue="Q", job_id=50, read=True, expected={})
    rep.tagged_intent = "Knut 2026.02.09"
    assert _status_of(rep) == (
        "Sent as job 50. The printing system confirms it carries application "
        "colour matching. The chart went with the profile macOS prints this job "
        "with (Knut 2026.02.09) attached, so macOS leaves its colours unchanged.")


def test_without_it_the_status_line_is_line_2_alone():
    rep = pt.TicketReport(queue="Q", job_id=50, read=True, expected={})
    assert _status_of(rep) == (
        "Sent as job 50. The printing system confirms it carries application "
        "colour matching.")


# ---- the Print Chart tab: what a verification print needs ------------------
class _Target:
    def __init__(self, verification):
        self._v = verification

    def is_verification(self):
        return self._v


class _Ctl:
    def __init__(self, verification):
        self.target = _Target(verification)


def _note(qapp, monkeypatch, *, verification=True, pages=True, native=True, mac=True):
    from PyQt6.QtWidgets import QLabel
    from ui.tabs import tab_print as tp
    monkeypatch.setattr(tp, "is_macos", lambda: mac)
    tab = tp.TabPrint.__new__(tp.TabPrint)
    tab._verify_route_lbl = QLabel()
    tab._target_ctl = _Ctl(verification)
    tab._tiff_pages = [("p", 0)] if pages else []
    tab._settings = {"use_native_print_dialog": native}
    tp.TabPrint._update_verify_route_note(tab)
    lbl = tab._verify_route_lbl
    return (not lbl.isHidden()), lbl.text()


@pytest.fixture
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(sys.argv[:1])


def test_a_verification_on_the_dialog_route_gets_all_three_paragraphs(qapp, monkeypatch):
    shown, text = _note(qapp, monkeypatch)
    assert shown
    assert "<b>Printing a verification chart</b>" in text
    assert "Print this chart on the same printer" in text
    assert "including its Color Matching panel" in text
    assert "On a PostScript printer the two routes" in text


def test_the_direct_route_leaves_out_the_dialog_paragraph(qapp, monkeypatch):
    """Paragraphs 1 and 3 are about which route to print by; paragraph 2 is
    about the macOS print dialog, which this route does not open."""
    shown, text = _note(qapp, monkeypatch, native=False)
    assert shown
    assert "Print this chart on the same printer" in text
    assert "On a PostScript printer the two routes" in text
    assert "Color Matching panel" not in text


@pytest.mark.parametrize("kw", [dict(verification=False), dict(pages=False),
                                dict(mac=False)])
def test_nowhere_else(qapp, monkeypatch, kw):
    """A profiling or calibration run, no chart, or not macOS: hidden."""
    shown, _text = _note(qapp, monkeypatch, **kw)
    assert not shown


def test_the_tab_updates_it_with_the_run_type_and_the_route():
    import inspect
    from ui.tabs import tab_print as tp
    assert "self._update_verify_route_note()" in inspect.getsource(
        tp.TabPrint._update_colour_row_visible)
    assert "self._update_verify_route_note(native=enabled)" in inspect.getsource(
        tp.TabPrint._set_native_mode)


# ---- Epson colour matching set back after the dialog -----------------------
def test_only_the_epson_has_a_key_to_set_back(tmp_path):
    assert dialog_route_colour_locks(_ppd(tmp_path, EPSON_PPD)) == {"EPIJ_OSColMat": "2"}
    assert dialog_route_colour_locks(_ppd(tmp_path, CANON_PPD)) == {}
    assert dialog_route_colour_locks(GENERIC_PS) == {}


def test_not_when_the_ppd_does_not_offer_the_value(tmp_path):
    """The PM-400's PPD offers EPIJ_OSColMat 0 alone."""
    text = _ppd(tmp_path, EPSON_PPD).replace(
        '*EPIJ_OSColMat 2/Off: ""\n', "")
    assert dialog_route_colour_locks(text) == {}


class _FakePrintInfo:
    def __init__(self, settings):
        self._s = settings

    def printer(self):
        class _P:
            def name(self):
                return "Q"
        return _P()

    def printSettings(self):  # noqa: N802
        return self._s


@pytest.fixture
def epson_queue(monkeypatch, tmp_path):
    ppd = tmp_path / "Q.ppd"
    ppd.write_text(_ppd(tmp_path, EPSON_PPD), encoding="latin-1")
    from workflow.print_manager import PrintModule
    monkeypatch.setattr(PrintModule, "find_ppd_path", staticmethod(lambda q: str(ppd)))


def test_the_epson_key_is_locked_after_the_dialog_not_before(epson_queue):
    """Before the dialog the panel shows what the user had; after it, the
    job is set to what a Photoshop print carries.
    MUTATION: drop the `after_dialog` update in `_locked_settings_for` and
    this goes red."""
    pi = _FakePrintInfo({})
    assert npm._locked_settings_for(pi) == {
        "AP_ColorMatchingMode": "AP_ApplicationColorMatching"}
    assert npm._locked_settings_for(pi, after_dialog=True) == {
        "AP_ColorMatchingMode": "AP_ApplicationColorMatching", "EPIJ_OSColMat": "2"}


@pytest.mark.skipif(sys.platform != "darwin", reason="PyObjC is macOS only")
def test_the_dialogs_epson_choice_is_set_back_and_remembered(epson_queue, monkeypatch):
    """What the measured run did: the panel wrote 1, ChromIQ set 2 and kept
    the fact for the read-back (and, once approved, the status line)."""
    pytest.importorskip("objc")
    monkeypatch.setattr(npm, "_PRINTCORE_OK", False)
    settings = {"EPIJ_OSColMat": "1"}
    locked = npm._lock_no_color_management(_FakePrintInfo(settings), after_dialog=True)
    assert settings["EPIJ_OSColMat"] == "2" and locked["EPIJ_OSColMat"] == "2"
    assert npm.last_reset_by_chromiq == {"EPIJ_OSColMat": ("1", "2")}
    # the panel left alone: nothing to report
    npm._lock_no_color_management(_FakePrintInfo({"EPIJ_OSColMat": "2"}), after_dialog=True)
    assert npm.last_reset_by_chromiq == {}


def test_print_frames_locks_after_the_dialog_and_keeps_the_reset():
    import inspect
    src = inspect.getsource(npm.print_frames)
    after = src[src.index("runModalWithPrintInfo_"):]
    assert "_lock_no_color_management(print_info, after_dialog=True)" in after
    assert "last_submission.reset_by_chromiq = dict(last_reset_by_chromiq)" in src


def test_a_job_that_still_carries_the_epson_choice_is_not_confirmed(tmp_path, monkeypatch):
    """The read-back compares every key the dialog route set: if the job
    still carries 1, the status line does not say "confirms"."""
    text = _ppd(tmp_path, EPSON_PPD)
    monkeypatch.setattr(pt, "read_ticket", lambda j: {
        "AP_ColorMatchingMode": "AP_ApplicationColorMatching",
        "EPIJ_Medi": "0", "EPIJProfileSpec": "1", "EPIJ_OSColMat": "1"})
    rep = pt.check_job("Q", 7, {"AP_ColorMatchingMode": "AP_ApplicationColorMatching",
                                "EPIJ_OSColMat": "2"}, ppd_text=text)
    assert not rep.ok and rep.mismatches == {"EPIJ_OSColMat": ("1", "2")}


# ---- the two approved Epson texts, shown exactly then (driver round) -------
def _shown(rep, monkeypatch):
    """(status line, window title or None) for *rep* on the Print Chart tab."""
    from ui.tabs import tab_print as tp
    seen = {"window": None}
    monkeypatch.setattr(tp, "warn", lambda parent, title, body: seen.update(window=(title, body)))
    tab = tp.TabPrint.__new__(tp.TabPrint)
    tab._set_status = lambda text: seen.update(status=text)
    tp.TabPrint._report_job_ticket(tab, rep)
    return seen["status"], seen["window"]


def _epson_rep(**kw):
    return pt.TicketReport(queue="Q", job_id=7, read=True,
                           expected={"EPIJ_OSColMat": "2"}, **kw)


def test_the_reset_sentence_follows_the_status_line_when_chromiq_set_it_back(monkeypatch):
    """MUTATION: drop the `_reset_vendors(rep) == {"Epson"}` block in
    `_report_job_ticket` and this goes red."""
    rep = _epson_rep(reset_by_chromiq={"EPIJ_OSColMat": ("1", "2")})
    status, window = _shown(rep, monkeypatch)
    assert window is None
    assert status == ("Sent as job 7. The printing system confirms it carries "
                      "application colour matching. " + APPROVED_EPSON_RESET)


def test_no_reset_sentence_when_the_panel_was_left_alone(monkeypatch):
    status, window = _shown(_epson_rep(), monkeypatch)
    assert APPROVED_EPSON_RESET not in status and window is None


def test_no_epson_sentence_for_a_key_no_epson_rule_sets_back(monkeypatch):
    """The sentence names Epson: a set-back of any other key never shows it."""
    rep = _epson_rep(reset_by_chromiq={"SomeOtherKey": ("1", "2")})
    status, _window = _shown(rep, monkeypatch)
    assert APPROVED_EPSON_RESET not in status


def test_the_epson_window_when_the_job_still_carries_the_epson_choice(monkeypatch):
    """MUTATION: drop the Epson branch of `_show_job_not_as_sent` and this
    shows M-PRINT-JOB-NOT-AS-SENT instead."""
    rep = _epson_rep(mismatches={"EPIJ_OSColMat": ("1", "2")})
    status, window = _shown(rep, monkeypatch)
    assert window == MM.M_PRINT_JOB_EPSON_MATCHING.render()
    assert status == MM.M_PRINT_JOB_EPSON_MATCHING.title


def test_with_other_differences_too_every_key_is_listed(monkeypatch):
    rep = _epson_rep(mismatches={"EPIJ_OSColMat": ("1", "2"),
                                 "AP_ColorMatchingMode": ("x", "AP_ApplicationColorMatching")})
    _status, window = _shown(rep, monkeypatch)
    assert window[0] == MM.M_PRINT_JOB_NOT_AS_SENT.title
    assert "EPIJ_OSColMat: 1" in window[1] and "AP_ColorMatchingMode: x" in window[1]


# ---- the driver round (2026-10-10): who else writes a key ------------------
#: Trimmed from the PPDs measured in ~/Desktop/ChromIQ-work/
#: 2026-10-10_434b1_drivers: the colour options each driver's PPD offers.
_BROTHER_9460 = ('*PPD-Adobe: "4.3"\n*APSupportsCustomColorMatching: True\n'
                 '*APCustomColorMatchingName name/Brother Color: ""\n'
                 '*OpenUI *BRColorMatching/Color Mode: PickOne\n*DefaultBRColorMatching: Normal\n'
                 '*BRColorMatching Normal/Normal: ""\n*BRColorMatching Vivid/Vivid: ""\n'
                 '*BRColorMatching None/None: ""\n*CloseUI: *BRColorMatching\n')
_HP_B9100 = ('*PPD-Adobe: "4.3"\n*APSupportsCustomColorMatching: True\n'
             '*APCustomColorMatchingProfile: sRGB\n'
             '*OpenUI *HPColorMode/Color: PickOne\n*DefaultHPColorMode: colorsmart\n'
             '*HPColorMode colorsmart/ColorSmart: ""\n'
             '*HPColorMode application-managed/Application Managed Colors: ""\n'
             '*CloseUI: *HPColorMode\n')


@pytest.mark.parametrize("text", [_BROTHER_9460, _HP_B9100, GENERIC_PS])
def test_no_other_driver_has_a_key_to_set_back(text):
    """Measured on screen: Brother's "Brother Color", HP's and Gutenprint's
    vendor matching and the Canon PIXMA/PRO-100 "Canon colour matching" wrote
    only AP_ColorMatchingMode=AP_VendorColorMatching, which ChromIQ locks on
    every queue; the job and its data were identical to the untouched one's.
    Only the Epson rule sets a driver key back."""
    assert dialog_route_colour_locks(text) == {}


def test_the_lock_names_its_vendor_and_nothing_else():
    from workflow.ppd_color import dialog_route_lock_vendor
    assert dialog_route_lock_vendor("EPIJ_OSColMat") == "Epson"
    assert dialog_route_lock_vendor("BRColorMatching") is None
    assert dialog_route_lock_vendor("AP_ColorMatchingMode") is None
