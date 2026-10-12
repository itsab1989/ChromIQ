"""4.3.5 beta 2: how a PostScript printer gets the chart through the macOS
print dialog is a choice per run, and the combined review's three small items
on that route.

Basti, 2026-10-12, on beta 1 (k81 sends every RGB chart to a PostScript
printer as ChromIQ's own PostScript, DeviceRGB): *"personally i think giving
the user the choice here is better because what if he then wants to make use
of the profile he created just to notice the app he wants to print from does
not support postscript and thus the profile does not match"*.

Measured on capture queues (report folder 2026-10-12_b2_postscript): Photoshop
writes its own PostScript; with "Photoshop Manages Colors" and the printer
profile it sends DeviceRGB with the profile's values (k81's form); with
"Printer Manages Colors" CIEBasedABC (sRGB), or CIEBasedDEF from a document's
own profile. Preview goes through macOS: CIEBasedABC (sRGB), or CIEBasedDEF
with a ColorSync profile set (4.3.4's form). So: "its own RGB" (default) and
"as macOS sends it", kept in the run's meta.json, the same for its
verification charts.

Combined review of 4.3.5: (a) the dialog route's notice promises a paper
profile on a PostScript printer, which gets none; (b) the Through notice
promises "nothing between here and the paper changes the colours" where the
driver takes CMYK raster; (c) a paper the PostScript PPD does not list went as
a job whose ticket said Letter while the PostScript asked for A3; (d) the
PostScript job had no title or application name in the print queue.
"""
from __future__ import annotations

import inspect
import os
from dataclasses import replace
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.file_manager import FileManager, Project        # noqa: E402
from core.measurement_target import (                     # noqa: E402
    RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION)
from core.settings import AppSettings                     # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402
from workflow import measurement_messages as MM           # noqa: E402
from workflow import native_print_macos as npm            # noqa: E402
from workflow import ppd_color                            # noqa: E402

GENERIC_PS = (  # the generic PostScript PPD's papers, with its trailing spaces
    '*ModelName: "Generic PostScript Printer"\n'
    '*PaperDimension Letter/US Letter: "612 792 "\n'
    '*PaperDimension A4: "595 842 "\n')
CUSTOM_PS = GENERIC_PS + (
    '*CustomPageSize True: "pop pop pop setpagedevice"\n'
    '*ParamCustomPageSize Width: 1 points 216 867\n'
    '*ParamCustomPageSize Height: 2 points 360 1332\n')
A3 = (841.68, 1190.16)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ---- (c) the paper check ---------------------------------------------------
def test_a_paper_the_ppd_lists_is_taken_either_way_round():
    assert npm.ppd_takes_paper(GENERIC_PS, 595.2, 841.8)
    assert npm.ppd_takes_paper(GENERIC_PS, 842, 595)


def test_a3_is_not_a_paper_of_the_generic_postscript_ppd():
    """MUTATION: read *PaperDimension with the Canon rule's pattern (no space
    before the quote) and A4 is refused too; drop the check and A3 passes."""
    assert not npm.ppd_takes_paper(GENERIC_PS, *A3)


def test_a_custom_page_size_takes_what_fits_its_ranges():
    assert npm.ppd_takes_paper(CUSTOM_PS, *A3)
    assert npm.ppd_takes_paper(CUSTOM_PS, 500, 700)
    assert not npm.ppd_takes_paper(CUSTOM_PS, 2000, 3000)


def test_without_a_ppd_nothing_is_refused():
    assert npm.ppd_takes_paper(None, *A3)


def test_the_refusal_names_the_paper_in_millimetres():
    assert npm.PaperNotOnPrinter("Q", *A3).size_mm == "297 × 420 mm"


def test_the_check_comes_before_the_postscript_is_sent():
    src = inspect.getsource(npm.print_frames)
    check = src.index("ppd_takes_paper(_ppd_after, _w, _h)")
    assert "raise PaperNotOnPrinter(_disp, _w, _h)" in src[check:check + 900]
    assert check < src.index("return _print_device_rgb_postscript(print_info, pages, locked)")


def test_the_tab_refuses_only_once_the_window_is_approved():
    from ui.tabs import tab_print
    src = inspect.getsource(tab_print.TabPrint._print_native)
    assert "refuse_unlisted_paper=_MM.M_PRINT_PS_PAPER_NOT_LISTED.approved" in src
    assert "except PaperNotOnPrinter" in src
    assert not MM.M_PRINT_PS_PAPER_NOT_LISTED.approved


# ---- the form, in print_frames ----------------------------------------------
def test_print_frames_takes_the_form_with_its_own_rgb_as_default():
    sig = inspect.signature(npm.print_frames)
    assert sig.parameters["postscript_form"].default == ppd_color.POSTSCRIPT_DEVICE_RGB
    assert ppd_color.DEFAULT_POSTSCRIPT_FORM == ppd_color.POSTSCRIPT_DEVICE_RGB


def test_as_macos_sends_it_a_postscript_printer_goes_the_4_3_4_way():
    """MUTATION: drop ``postscript_form`` from the branch and "as macOS sends
    it" still goes DeviceRGB."""
    src = inspect.getsource(npm.print_frames)
    branch = src.index("if _is_ps and postscript_form == POSTSCRIPT_DEVICE_RGB:")
    # every other case goes on to the print view, which macOS hands a
    # PostScript printer as CIEBased (4.3.4)
    assert branch < src.index("printOperationWithView_printInfo_")
    assert "last_submission.postscript_form = POSTSCRIPT_AS_MACOS if _is_ps else None" in src


# ---- (d) the job's title and application -----------------------------------
def test_the_job_title_is_the_charts_file_name():
    assert npm.job_title([(Path("/x/run1/test.tif"), 0)]) == "test.tif"


@pytest.mark.skipif(not getattr(npm, "_PM_PAPER_OK", False), reason="macOS PrintCore")
def test_the_job_is_named_in_its_print_settings():
    """MUTATION: drop ``_name_the_job`` and the job keeps no name."""
    import AppKit
    pi = AppKit.NSPrintInfo.sharedPrintInfo().copy()
    npm._name_the_job(pi, "test.tif", "ChromIQ")
    ps = dict(pi.printSettings())     # NSPrintInfo shows "." as "_"
    assert ps.get("com_apple_print_JobInfo_PMJobName") == "test.tif"
    assert ps.get("com_apple_print_JobInfo_PMApplicationName") == "ChromIQ"


def test_the_postscript_job_is_named_before_it_is_sent():
    src = inspect.getsource(npm._print_device_rgb_postscript)
    assert src.index('_name_the_job(print_info, job_title(pages), "ChromIQ")') \
        < src.index("PMPrinterPrintWithFile(")
    assert '(Path(job_title(pages)).stem + ".ps")' in src


# ---- the tab: the choice per run --------------------------------------------
def _env(tmp_path, run_type=RUN_TYPE_PROFILING):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path))
    s.set("use_native_print_dialog", True)
    fm = FileManager(s)
    Project.create(tmp_path / "P", "P").current_run().ensure_dir()
    fm.set_target_name("P")
    ctl = MeasurementTargetController(fm)
    ctl.set_profile_run("run1")
    ctl.set_run_type(run_type)
    return s, fm, ctl


@pytest.fixture
def ps_dialog(monkeypatch):
    """The macOS dialog opens on a PostScript queue (no CMYK raster)."""
    from ui.tabs import tab_print as tp
    monkeypatch.setattr(tp, "_dialog_printer", lambda: ("PSQ", "PS Printer"))
    monkeypatch.setattr(tp, "_queue_is_postscript", lambda q: q == "PSQ")
    monkeypatch.setattr(tp, "_queue_cmyk_raster", lambda q: None)
    monkeypatch.setattr(tp, "is_macos", lambda: True)
    return tp


def _tab(s, ctl):
    from ui.tabs.tab_print import TabPrint
    tab = TabPrint(s)
    tab.set_target_controller(ctl)
    tab._update_colour_row_visible()   # as a target change does
    return tab


def test_a_run_with_nothing_stored_gets_its_own_rgb(qapp, tmp_path):
    s, fm, ctl = _env(tmp_path)
    assert _tab(s, ctl)._ps_form() == ppd_color.POSTSCRIPT_DEVICE_RGB


def test_the_choice_is_kept_in_the_runs_meta(qapp, tmp_path, ps_dialog):
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    tab._ps_macos_rb.setChecked(True)
    run = fm.project().run("run1")
    assert run.load_meta().print_settings["postscript"] == ppd_color.POSTSCRIPT_AS_MACOS
    assert _tab(s, ctl)._ps_form() == ppd_color.POSTSCRIPT_AS_MACOS


def test_a_verification_chart_follows_its_runs_choice(qapp, tmp_path, ps_dialog):
    """MUTATION: keep the choice in the verification target's own store and
    the verification sheet goes the other way than the profiling chart."""
    s, fm, ctl = _env(tmp_path)
    first = _tab(s, ctl)
    first._ps_macos_rb.setChecked(True)
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab = _tab(s, ctl)
    assert tab._ps_form() == ppd_color.POSTSCRIPT_AS_MACOS
    # and a change made on the verification target is the run's
    tab._ps_device_rb.setChecked(True)
    run = fm.project().run("run1")
    assert run.load_meta().print_settings["postscript"] == ppd_color.POSTSCRIPT_DEVICE_RGB
    assert not (run.verifications_dir / "meta.json").exists() or \
        "postscript" not in (run.verifications_dir / "meta.json").read_text(encoding="utf-8")


def test_the_row_is_hidden_until_its_words_are_approved(qapp, tmp_path, ps_dialog, monkeypatch):
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    tab._tiff_pages = [tmp_path / "p.tif"]
    tab._update_ps_form_row()
    assert tab._ps_form_row.isHidden()
    monkeypatch.setattr(MM, "M_PRINT_PS_FORM_CHOICE",
                        replace(MM.M_PRINT_PS_FORM_CHOICE, approved=True))
    tab._update_ps_form_row()
    assert not tab._ps_form_row.isHidden()
    # not on the direct route, and not for a printer that is not PostScript
    s.set("use_native_print_dialog", False)
    tab._update_ps_form_row()
    assert tab._ps_form_row.isHidden()
    s.set("use_native_print_dialog", True)
    monkeypatch.setattr(ps_dialog, "_dialog_printer", lambda: ("INKJET", "Inkjet"))
    tab._update_ps_form_row()
    assert tab._ps_form_row.isHidden()


def test_the_print_goes_with_the_runs_form(qapp, tmp_path, ps_dialog, monkeypatch):
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    tab._ps_macos_rb.setChecked(True)
    seen = {}

    def fake(pages, printer=None, postscript_form=None, refuse_unlisted_paper=None):
        seen.update(form=postscript_form, refuse=refuse_unlisted_paper)
        return False
    monkeypatch.setattr(npm, "print_frames", fake)
    monkeypatch.setattr("sys.platform", "darwin")
    tab._commit_print_record = lambda submitted: None
    tab._print_native([(tmp_path / "p.tif", 0)])
    assert seen == {"form": ppd_color.POSTSCRIPT_AS_MACOS, "refuse": False}


def test_a_refused_paper_is_said_and_not_recorded(qapp, tmp_path, ps_dialog, monkeypatch):
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    monkeypatch.setattr(MM, "M_PRINT_PS_PAPER_NOT_LISTED",
                        replace(MM.M_PRINT_PS_PAPER_NOT_LISTED, approved=True))

    def fake(pages, printer=None, postscript_form=None, refuse_unlisted_paper=None):
        assert refuse_unlisted_paper is True
        raise npm.PaperNotOnPrinter("PS Printer", *A3)
    monkeypatch.setattr(npm, "print_frames", fake)
    monkeypatch.setattr("sys.platform", "darwin")
    shown, recorded = [], []
    from ui.tabs import tab_print as tp
    monkeypatch.setattr(tp.QMessageBox, "warning", lambda parent, t, b: shown.append((t, b)))
    tab._commit_print_record = recorded.append
    tab._print_native([(tmp_path / "p.tif", 0)])
    assert shown == [MM.M_PRINT_PS_PAPER_NOT_LISTED.render(
        size="297 × 420 mm", printer="PS Printer")]
    assert recorded == [False]


# ---- (a) the notice on a PostScript printer --------------------------------
def test_the_notice_is_unchanged_until_approved(qapp, tmp_path, ps_dialog):
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    assert "This works with any printer" in tab._macos_dialog_notice()


@pytest.mark.parametrize("form,msg", [
    (ppd_color.POSTSCRIPT_DEVICE_RGB, "M_PRINT_PS_ROUTE_OWN_RGB"),
    (ppd_color.POSTSCRIPT_AS_MACOS, "M_PRINT_PS_ROUTE_AS_MACOS")])
def test_on_a_postscript_printer_the_notice_says_what_the_form_does(
        qapp, tmp_path, ps_dialog, monkeypatch, form, msg):
    """MUTATION: leave the PostScript branch out and the notice keeps
    promising a paper profile that a PostScript printer never gets."""
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    (tab._ps_device_rb if form == ppd_color.POSTSCRIPT_DEVICE_RGB
     else tab._ps_macos_rb).setChecked(True)
    for name in ("M_PRINT_PS_ROUTE_OWN_RGB", "M_PRINT_PS_ROUTE_AS_MACOS"):
        monkeypatch.setattr(MM, name, replace(getattr(MM, name), approved=True))
    text = tab._macos_dialog_notice()
    title, body = getattr(MM, msg).render(printer="PS Printer")
    assert f"{title}\n{body}" in text
    assert "This works with any printer" not in text
    assert "attaches the paper profile" not in text


# ---- (b) the Through notice -------------------------------------------------
def test_the_through_notice_drops_its_promise_only_where_it_is_untrue(
        qapp, tmp_path, ps_dialog, monkeypatch):
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    assert not tab._colours_converted_on_the_way()     # PostScript, own RGB
    tab._ps_macos_rb.setChecked(True)
    assert tab._colours_converted_on_the_way()         # PostScript, as macOS
    tab._ps_device_rb.setChecked(True)
    monkeypatch.setattr(ps_dialog, "_queue_cmyk_raster", lambda q: "KCMY")
    assert tab._colours_converted_on_the_way()         # CMYK raster, dialog
    s.set("use_native_print_dialog", False)
    tab._printer_combo.clear()
    tab._printer_combo.addItem("Q", "Q")
    assert tab._colours_converted_on_the_way()         # CMYK raster, direct
    monkeypatch.setattr(ps_dialog, "_queue_cmyk_raster", lambda q: None)
    assert not tab._colours_converted_on_the_way()


def test_the_variant_is_the_approved_notice_less_one_sentence():
    from ui.tabs import tab_print as tp
    full, short = tp._CM_NOTICE_THROUGH, tp._CM_NOTICE_THROUGH_CONVERTED_ON_THE_WAY
    gone = ("The printer’s own colour adjustment stays switched off, so nothing "
            "between here and the paper changes the colours.")
    assert gone in full and gone not in short
    assert full.replace(" " + gone, "") == short


def test_the_colour_row_uses_the_variant_where_colours_change():
    from ui.tabs import tab_print as tp
    src = inspect.getsource(tp.TabPrint._update_colour_row_visible)
    assert "if through and self._colours_converted_on_the_way():" in src
    assert "_CM_NOTICE_THROUGH_CONVERTED_ON_THE_WAY" in src


# ---- the verification note on "as macOS sends it" ---------------------------
def test_the_verification_note_drops_its_postscript_promises_as_macos(
        qapp, tmp_path, ps_dialog):
    """M-PRINT-VERIFY-PS-EARLIER says both routes send a PostScript printer
    its own RGB, and -DIALOG-AS-IS / -THROUGH that it goes as the printer's
    own RGB: untrue for a run that chose "as macOS sends it"."""
    s, fm, ctl = _env(tmp_path, RUN_TYPE_VERIFICATION)
    tab = _tab(s, ctl)
    tab._tiff_pages = [tmp_path / "p.tif"]
    tab._update_verify_route_note(native=True)
    shown = tab._verify_route_lbl.text()
    assert MM.M_PRINT_VERIFY_PS_EARLIER.body.split(":")[0][:40] in shown
    tab._ps_macos_rb.setChecked(True)
    tab._update_verify_route_note(native=True)
    shown = tab._verify_route_lbl.text()
    assert "own RGB" not in shown
