"""4.3.5: the macOS dialog route on a queue whose driver takes CMYK raster.

Review R3 and B5 (4.3.4 beta 1) measured on capture queues that on such a
queue (the CUPS sample HP DeskJet driver) macOS converts the chart from its own
tag into CMYK and ignores an RGB profile assigned to the printer in ColorSync,
so ChromIQ's re-tag made the printed colours depend on the assigned profile
(review R1: a CMYK profile assigned there IS used for the conversion). Basti
chose (2026-10-10, B5's option 3) to leave the chart untagged there, on
condition that the detection is accurate and nothing else changes. So:

* the detector (``ppd_color.raster_colour``) is STRICT: CMYK only when every
  print-data filter takes ``application/vnd.cups-raster`` and every colour
  space the job's own choices set is CMY/YMC/CMYK/YMCK/KCMY/KCMYcm. The cases
  below are lines of the real PPDs it was run over (report folder
  ``2026-10-10_435_B1``, ``runs/detector_table.txt``, 46 PPDs);
* a CMYK raster job is not re-tagged and gets no M-PRINT-JOB-UNTAGGED window,
  but only if the job READ BACK from CUPS is CMYK raster too;
* M-PRINT-CMYK-RASTER-ROUTE was APPROVED by Basti (2026-10-10, B2) with his
  own last sentences, and is shown on a CMYK raster queue.
"""
from __future__ import annotations

import dataclasses
import inspect
import sys

import pytest

from workflow import measurement_messages as MM
from workflow import native_print_macos as npm
from workflow import print_ticket as pt
from workflow.ppd_color import CUPS_CMYK_SPACES, cmyk_raster_space, raster_colour

_HEAD = '*PPD-Adobe: "4.3"\n'

#: the CUPS sample HP DeskJet (``ppdc sample.drv``): its "RGB" choice is CMY
DESKJET = _HEAD + (
    '*cupsFilter: "application/vnd.cups-raster 50 rastertohp"\n'
    '*OpenUI *ColorModel/Color Mode: PickOne\n'
    '*DefaultColorModel: CMYK\n'
    '*ColorModel Gray/Grayscale: "<</cupsColorSpace 3/cupsColorOrder 0/cupsCompression 2>>setpagedevice"\n'
    '*ColorModel RGB/Color: "<</cupsColorSpace 4/cupsColorOrder 1/cupsCompression 2>>setpagedevice"\n'
    '*ColorModel CMYK/CMYK: "<</cupsColorSpace 8/cupsColorOrder 1/cupsCompression 2>>setpagedevice"\n'
    '*CloseUI: *ColorModel\n'
    '*fr.ColorModel CMYK/CMYK: ""\n')
#: Gutenprint 5.3.3, Stylus Photo R2400: RGB by default, CMYK on request
GUTENPRINT = _HEAD + (
    '*cupsFilter:\t"application/vnd.cups-raster 100 rastertogutenprint.5.3"\n'
    '*cupsFilter:\t"application/vnd.cups-command 33 commandtoepson"\n'
    '*cupsICCProfile CMYK../Color:\t"/System/Library/ColorSync/Profiles/Generic CMYK Profile.icc"\n'
    '*OpenUI *ColorModel/Color Model: PickOne\n'
    '*DefaultColorModel: RGB\n'
    '*ColorModel Gray/Grayscale:\t"<</cupsColorSpace 0/cupsColorOrder 0>>setpagedevice"\n'
    '*ColorModel Black/Inverted Grayscale:\t"<</cupsColorSpace 3/cupsColorOrder 0>>setpagedevice"\n'
    '*ColorModel RGB/RGB Color:\t"<</cupsColorSpace 1/cupsColorOrder 0>>setpagedevice"\n'
    '*ColorModel CMY/CMY Color:\t"<</cupsColorSpace 4/cupsColorOrder 0>>setpagedevice"\n'
    '*ColorModel CMYK/CMYK:\t"<</cupsColorSpace 6/cupsColorOrder 0>>setpagedevice"\n'
    '*ColorModel KCMY/KCMY:\t"<</cupsColorSpace 8/cupsColorOrder 0>>setpagedevice"\n'
    '*CloseUI: *ColorModel\n')
#: Canon PRO-300 (Basti's printer): 16-bit RGB raster
CANON = _HEAD + (
    '*cupsFilter: "application/vnd.cups-raster 0 /Library/Printers/Canon/x/Raster2CanonIJ2S"\n'
    '*cupsFilter: "application/vnd.cups-command 0 /Library/Printers/Canon/x/Command2CanonIJ2"\n'
    '*DefaultColorModel: RGB16\n'
    '*ColorModel RGB16/RGB 16-bit: "<</cupsColorOrder 0/cupsColorSpace 1/cupsCompression 0/cupsBitsPerColor 16>>setpagedevice"\n')
#: Epson ET-8550 / SC-P600: every choice is RGB raster
EPSON = _HEAD + (
    '*cupsFilter: "application/vnd.cups-raster 0 /Library/Printers/EPSON/x/rastertoescpII"\n'
    '*DefaultColorModel: RGB\n'
    '*ColorModel RGB/RGB: "<</cupsBitsPerColor 8/cupsColorOrder 0/cupsColorSpace 1>>setpagedevice"\n'
    '*ColorModel Mono/Gray: "<</cupsBitsPerColor 8/cupsColorOrder 0/cupsColorSpace 1>>setpagedevice"\n')
#: Brother MFC-9460CDN: the colour space sits on BRResolution and BROutput
BROTHER = _HEAD + (
    '*cupsFilter: "application/vnd.cups-raster 0 rastertobrother4150"\n'
    '*DefaultBRResolution: 600dpi\n'
    '*BRResolution 600dpi/Normal (600 x 600dpi): \t"<</HWResolution [600 600]/cupsColorOrder 0/cupsColorSpace 1/cupsBitsPerColor 8>> setpagedevice"\n'
    '*DefaultBROutput: Print\n'
    '*BROutput Print/Print: ""\n'
    '*BROutput FAX/Send Fax: "<</HWResolution [200 200]/cupsColorOrder 0/cupsColorSpace 3/cupsBitsPerColor 1 >> setpagedevice"\n')
GENERIC_PS = _HEAD + '*ModelName: "Generic PostScript Printer"\n*DefaultColorSpace: CMYK\n'
HP_POSTSCRIPT = _HEAD + '*cupsFilter: "application/vnd.cups-postscript 0 hpPostProcessing"\n*DefaultColorModel: CMYK\n'
#: HP Photosmart Pro B9100: its driver takes PDF
HP_PDF = _HEAD + ('*cupsFilter: "application/pdf 100 Inkjet"\n*DefaultColorModel: RGB\n'
                  '*ColorModel RGB/Color: "<</cupsColorOrder 0/cupsColorSpace 1/cupsBitsPerColor 8>>setpagedevice"\n')
#: macOS's IPP Everywhere PPD (``lpadmin -m everywhere``)
EVERYWHERE = _HEAD + (
    '*cupsFilter2: "application/vnd.cups-pdf application/pdf 10 -"\n'
    '*cupsFilter2: "image/urf image/urf 100 -"\n'
    '*DefaultColorModel: RGB\n'
    '*ColorModel RGB: "<</cupsColorSpace 19/cupsBitsPerColor 8/cupsColorOrder 0/cupsCompression 0>>setpagedevice"\n')


@pytest.mark.parametrize("text,settings,expected", [
    (DESKJET, {}, "KCMY"),
    (DESKJET, {"ColorModel": "CMYK"}, "KCMY"),
    (DESKJET, {"ColorModel": "RGB"}, "CMY"),          # the name says RGB, the raster is CMY
    (DESKJET, {"ColorModel": "Gray"}, None),
    (GUTENPRINT, {}, None),                           # RGB by default
    (GUTENPRINT, {"ColorModel": "RGB"}, None),
    (GUTENPRINT, {"ColorModel": "CMYK"}, "CMYK"),
    (GUTENPRINT, {"ColorModel": "KCMY"}, "KCMY"),
    (GUTENPRINT, {"ColorModel": "CMY"}, "CMY"),
    (GUTENPRINT, {"ColorModel": "Gray"}, None),
    (GUTENPRINT, {"ColorModel": "Black"}, None),
    (CANON, {}, None),
    (EPSON, {"ColorModel": "Mono"}, None),
    (BROTHER, {}, None),
    (BROTHER, {"BROutput": "FAX"}, None),
    (GENERIC_PS, {}, None),                           # *DefaultColorSpace: CMYK is no raster
    (HP_POSTSCRIPT, {}, None),
    (HP_PDF, {}, None),
    (EVERYWHERE, {}, None),
    (None, {}, None),
])
def test_only_a_declared_cmyk_raster_job_is_cmyk(text, settings, expected):
    """MUTATION: accept any raster filter without looking at the colour space,
    and the Canon, Epson, Brother and Gutenprint-RGB rows go red; read the
    choice's NAME instead of its cupsColorSpace, and DeskJet "RGB" does."""
    assert cmyk_raster_space(text, settings) == expected


def test_the_families_are_the_ones_named():
    assert set(CUPS_CMYK_SPACES.values()) == {"CMY", "YMC", "CMYK", "YMCK", "KCMY", "KCMYcm"}


@pytest.mark.parametrize("space", [2, 10, 11, 17, 19, 32, 48, 62])
def test_rgba_gold_silver_icc_and_devicen_spaces_are_not_cmyk(space):
    text = _HEAD + ('*cupsFilter: "application/vnd.cups-raster 0 x"\n*DefaultColorModel: X\n'
                    f'*ColorModel X/X: "<</cupsColorSpace {space}>>setpagedevice"\n')
    assert cmyk_raster_space(text) is None


def test_a_second_route_beside_the_raster_one_is_not_cmyk():
    """CUPS may take the cheaper PDF route: what the driver gets is unknown."""
    text = DESKJET.replace('*cupsFilter: "application/vnd.cups-raster 50 rastertohp"\n',
                           '*cupsFilter: "application/vnd.cups-raster 50 rastertohp"\n'
                           '*cupsFilter: "application/pdf 0 pdftovendor"\n')
    assert cmyk_raster_space(text) is None


def test_a_command_filter_does_not_count():
    assert cmyk_raster_space(GUTENPRINT, {"ColorModel": "CMYK"}) == "CMYK"


def test_a_choice_the_ppd_does_not_have_is_not_cmyk():
    assert cmyk_raster_space(DESKJET, {"ColorModel": "Photo"}) is None


def test_no_default_and_no_job_value_is_not_cmyk():
    assert cmyk_raster_space(DESKJET.replace("*DefaultColorModel: CMYK\n", "")) is None


def test_an_lpoptions_value_that_is_not_cmyk_makes_it_unsure(monkeypatch, tmp_path):
    """CUPS may apply the user's lpoptions to a job that does not carry the
    option, so either value counts: Gray beside the CMYK default is not CMYK."""
    home = tmp_path / "home"
    (home / ".cups").mkdir(parents=True)
    (home / ".cups" / "lpoptions").write_text("Dest DJ ColorModel=Gray\n", encoding="utf-8")
    monkeypatch.setattr("pathlib.Path.home", lambda: home)
    assert raster_colour(DESKJET, {}, "DJ").cmyk is None
    assert raster_colour(DESKJET, {}, "OTHER").cmyk == "KCMY"
    assert raster_colour(DESKJET, {"ColorModel": "CMYK"}, "DJ").cmyk == "KCMY"


def test_macos_saying_another_colour_model_vetoes_it():
    key = "com_apple_print_PrintSettings_PMColorSpaceModel"
    assert npm.cmyk_raster_job(DESKJET, {key: 3}, None) == "KCMY"
    assert npm.cmyk_raster_job(DESKJET, {}, None) == "KCMY"
    assert npm.cmyk_raster_job(DESKJET, {key: 2}, None) is None
    assert npm.cmyk_raster_job(
        GUTENPRINT, {"com.apple.print.PrintSettings.PMColorSpaceModel..n.": "3",
                     "ColorModel": "CMYK"}, None) == "CMYK"


# ---- print_frames: no re-tag on a CMYK raster job ---------------------------
def test_print_frames_leaves_a_cmyk_raster_job_untagged():
    """The decision is made from the options AFTER the dialog, and the re-tag
    is skipped for it; nothing else in the route changes."""
    src = inspect.getsource(npm.print_frames)
    after = src[src.index("runModalWithPrintInfo_"):]
    decide = after.index("cmyk = cmyk_raster_job(")
    assert decide < after.index("_retag_reps(view._reps, dest_icc)")
    assert "if cmyk and dest_icc:" in after
    assert "last_submission.cmyk_raster = cmyk" in after


# ---- read_back: no window for a CMYK raster job, if the job really is one ---
@pytest.fixture
def queue(monkeypatch, tmp_path):
    def use(text, job_options):
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
                            tagged_with=tagged_with, options=dict(job_options)))
    return use


def _untagged(cmyk):
    sub = npm.Submission("Q", dict(npm._LOCKED_COLOR_SETTINGS), 0.0, b"", None,
                         output_intent="Knut 2026.02.09")
    sub.cmyk_raster = cmyk
    return sub


def test_a_cmyk_raster_job_gets_no_untagged_window(queue):
    """MUTATION: drop `and not rep.cmyk_raster` from read_back and this goes
    red: M-PRINT-JOB-UNTAGGED would say the chart may not print with its own
    colours, on a queue where the tag was left off on purpose."""
    queue(GUTENPRINT, {"ColorModel": "CMYK"})
    rep = npm.read_back(_untagged("CMYK"))
    assert rep.ok and rep.cmyk_raster == "CMYK" and rep.tag_matches_job is None


def test_the_job_read_back_decides_not_the_dialog(queue):
    """The options after the dialog said CMYK, the job in CUPS says RGB: the
    chart went untagged on a job macOS converts with the queue's profile, so
    the window says so, as before 4.3.5."""
    queue(GUTENPRINT, {"ColorModel": "RGB"})
    rep = npm.read_back(_untagged("CMYK"))
    assert rep.cmyk_raster is None and rep.tag_matches_job is False and not rep.ok


def test_an_untagged_job_that_was_not_cmyk_still_gets_the_window(queue):
    queue(DESKJET, {})
    rep = npm.read_back(_untagged(None))
    assert rep.tag_matches_job is False and not rep.ok


def test_the_job_options_are_read_back():
    import workflow.print_ticket as mod
    src = inspect.getsource(mod.check_job)
    assert "rep.options = " in src


# ---- the Print Chart tab's notice: the hint in place of the wrong claims ---
# Basti, 2026-10-10: on a CMYK raster queue M-PRINT-CMYK-RASTER-ROUTE takes the
# place of the notice's sentences promising the paper profile is attached so
# macOS does not change the colours, and of "This works with any printer";
# everything else stays. Review R1 found one statement of the hint untrue (a
# CMYK profile set in ColorSync DOES change the conversion) and corrected it;
# B2 put in Basti's last sentences, checked each, and switched it on.
@pytest.fixture
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(sys.argv[:1])


WRONG_HERE = ("it attaches the paper profile of the medium you chose to the chart",
              "so macOS does not change its colours",
              "the paper profile follows it",
              "This works with any printer")


def _notice(monkeypatch, *, approved, queue_cmyk=True):
    from ui.tabs import tab_print as tp
    if approved:
        monkeypatch.setattr(MM, "M_PRINT_CMYK_RASTER_ROUTE", dataclasses.replace(
            MM.M_PRINT_CMYK_RASTER_ROUTE, approved=True))
    monkeypatch.setattr(tp, "_queue_cmyk_raster", lambda q: "KCMY" if queue_cmyk else None)
    tab = tp.TabPrint.__new__(tp.TabPrint)
    return tp.TabPrint._macos_dialog_notice(tab)


def test_the_hint_is_approved_and_said_after_the_dialog_not_in_the_notice(qapp, monkeypatch):
    """B2: Basti approved the hint with his own last sentences ("approved if
    true", every statement checked). Basti, 2026-10-13: the printer is chosen
    only IN the dialog, so the hint is no longer put in the notice from the
    printer the dialog opens on; a CMYK raster job gets it after the dialog,
    once per run (``_tell_cmyk_raster_once``,
    test_435b2_postscript_asked_after_the_dialog)."""
    from ui.tabs import tab_print as tp
    assert MM.M_PRINT_CMYK_RASTER_ROUTE.approved
    assert "M-PRINT-CMYK-RASTER-ROUTE" not in MM.PROPOSED
    assert MM.M_PRINT_CMYK_RASTER_ROUTE.title not in _notice(monkeypatch, approved=True)
    src = inspect.getsource(tp.TabPrint._print_native)
    assert "self._tell_cmyk_raster_once(" in src
    assert "M_PRINT_CMYK_RASTER_ROUTE" in inspect.getsource(tp.TabPrint._tell_cmyk_raster_once)


def test_bastis_last_sentences_replace_the_old_two():
    """MUTATION: put back "ChromIQ sends the chart as it is, without attaching
    a profile." and this goes red."""
    body = MM.M_PRINT_CMYK_RASTER_ROUTE.body
    assert "without attaching a profile" not in body
    assert "by this same route" not in body
    assert body.endswith(
        "macOS treats the chart’s numbers as sRGB colours when it converts "
        "them to CMYK. Your photos must reach it the same way, or the profile "
        "will not fit them. In Photoshop, do not print with “Photoshop "
        "Manages Colors” and this profile. Instead use Edit > Convert to "
        "Profile with this profile, then Edit > Assign Profile > Don’t Color "
        "Manage This Document, and print with “Printer Manages Colors”. "
        "In Preview, set Colour Matching to ColorSync in the print dialog. Keep "
        "the same profile set for this printer in ColorSync Utility.")


def test_the_corrected_hint_says_a_cmyk_profile_changes_the_conversion():
    """MUTATION: put back "the profile set for this printer in ColorSync
    Utility does not change that" and this goes red. Measured (R1): a CMYK
    profile assigned in ColorSync changes the raster; RGB profiles do not."""
    body = MM.M_PRINT_CMYK_RASTER_ROUTE.body
    assert "does not change that" not in body
    assert "A CMYK profile set for this printer in ColorSync Utility changes that conversion" in body
    assert "an RGB profile set there does not" in body


def test_no_printer_gets_the_wrong_claims_before_the_dialog(qapp, monkeypatch):
    """The paper-profile sentences are untrue on a CMYK raster printer (and on
    a PostScript one), and before the dialog nobody knows the printer, so the
    notice is the approved one without them, the same for every queue."""
    text = _notice(monkeypatch, approved=True)
    for wrong in WRONG_HERE:
        assert wrong not in text, wrong
    assert _notice(monkeypatch, approved=True, queue_cmyk=False) == text
    paras = text.split("\n\n")
    assert len(paras) == 5
    assert paras[0].startswith("\u26a0  You are printing via the macOS printer dialog.")
    assert paras[1] == ("ChromIQ asks for application colour matching, as Photoshop does. "
                        "Afterwards the Print Chart tab says what the printing system holds "
                        "for the job.")
    # why the dialog shows a colour profile (M-PRINT-DIALOG-COLOUR-MATCHING,
    # approved by Knut, #182 6152691121, 4.3.5 beta 4)
    from workflow import measurement_messages as MM
    assert paras[2] == MM.M_PRINT_DIALOG_COLOUR_MATCHING.render()[1]
    assert paras[3].startswith("Prefer no dialog at all?")
    assert paras[4].startswith("Allow pigment inks")


@pytest.mark.parametrize("code", ["de", "es", "fr", "it", "ja", "nl", "no", "pl", "pt",
                                  "ru", "sv", "uk", "zh_CN"])
def test_every_language_can_be_cut_the_same_way(code):
    """The notice is cut by its paragraphs, so every translation must keep five;
    the kept sentences are that language's own first and last sentence of the
    second paragraph, word for word."""
    import json
    from pathlib import Path
    from ui.tabs import tab_print as tp
    src = inspect.getsource(tp.TabPrint._macos_dialog_notice)
    d = json.loads((Path(tp.__file__).resolve().parents[2] / "data" / "i18n" / f"{code}.json")
                   .read_text(encoding="utf-8"))
    key = next(k for k in d if k.startswith("\u26a0  You are printing via the macOS printer dialog."))
    paras = d[key].split("\n\n")
    assert len(paras) == 5
    kept = d["ChromIQ asks for application colour matching, as Photoshop does. "
             "Afterwards the Print Chart tab says what the printing system holds for the job."]
    sep = "" if code in ("ja", "zh_CN") else " "
    first, _, rest = kept.partition("\u3002" if not sep else ". ")
    assert paras[1].startswith(first)
    assert paras[1].endswith(rest)
    assert "paras[3], paras[4]" in src


def test_the_tab_rewords_the_notice_with_the_route_and_on_show():
    from ui.tabs import tab_print as tp
    assert "self._macos_dialog_notice()" in inspect.getsource(tp.TabPrint._set_native_mode)
    assert "self._update_cmyk_route_note()" in inspect.getsource(tp.TabPrint.showEvent)
    assert "self._macos_dialog_notice()" in inspect.getsource(tp.TabPrint._update_cmyk_route_note)


@pytest.mark.parametrize("opt", ["Print-Mode", "HP.Mode", "EPIJ_Mode"])
def test_an_rgb_option_with_any_keyword_beside_a_cmyk_colour_model_is_not_cmyk(opt):
    """Review R1: option keywords may carry a hyphen or a dot. An RGB colour
    space set by such an option was skipped and the job read as CMYK."""
    text = DESKJET + (f'*OpenUI *{opt}/Mode: PickOne\n*Default{opt}: Photo\n'
                      f'*{opt} Photo/Photo: "<</cupsColorSpace 1>>setpagedevice"\n'
                      f'*CloseUI: *{opt}\n')
    assert cmyk_raster_space(text) is None


def test_a_localised_line_is_not_an_option():
    text = DESKJET + '*de.ColorModel CMYK/Farbe: "<</cupsColorSpace 1>>setpagedevice"\n'
    assert cmyk_raster_space(text) == "KCMY"


def test_the_tab_judges_the_queue_by_its_default_colour_mode(tmp_path, monkeypatch):
    from ui.tabs import tab_print as tp
    from workflow.print_manager import PrintModule
    for text, want in ((DESKJET, "KCMY"), (GUTENPRINT, None), (CANON, None)):
        ppd = tmp_path / "q.ppd"
        ppd.write_text(text, encoding="utf-8")
        monkeypatch.setattr(PrintModule, "find_ppd_path", staticmethod(lambda q: str(ppd)))
        assert tp._queue_cmyk_raster("nobody_has_this_queue") == want
