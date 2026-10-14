"""k81 (Knut, #182 6102031563): a chart printed through the macOS print dialog
reaches a PostScript printer without colour management.

Measured on capture queues, 2026-10-11 (report folder
2026-10-11_435_fpg_verify, runs/): drawn through the print view (4.3.4), the
chart reached a generic PostScript queue with a ColorSync profile as
CIEBasedABC and an HP CLJ 5550 queue as CIEBasedDEF, colour spaces the printer
converts with its own colour rendering. An exact-size PDF with DeviceRGB and an
untagged bitmap arrive CIEBased as well (the untagged one converted, 17.9
levels mean). ChromIQ's own PostScript, submitted with the dialog's ticket
(``PMPrinterPrintWithFile``), arrives DeviceRGB, 1,372,807 of 1,372,807 chart
pixels unchanged, with every option the dialog set in the job.
"""
from __future__ import annotations

import inspect
import re
import sys

import numpy as np
import pytest
from PIL import Image

from workflow import native_print_macos as npm
from workflow import print_ticket as pt
from workflow.postscript_generator import PostScriptGenerator

GENERIC_PS = '*ModelName: "Generic PostScript Printer"\n*ColorDevice: True\n'


def _chart(path, colour=(10, 200, 30), size=(60, 40)):
    a = np.zeros((size[1], size[0], 3), np.uint8)
    a[:] = colour
    Image.fromarray(a).save(path, dpi=(100, 100))
    return path


def test_one_page_is_the_direct_routes_postscript_exactly(tmp_path):
    chart = _chart(tmp_path / "c.tif")
    page = (200.0, 300.0)
    assert npm._postscript_for_pages([(chart, 0)], page) == \
        PostScriptGenerator().generate(chart, page_size_pt=page).encode("ascii")


def test_the_postscript_carries_device_rgb_and_no_colour_management(tmp_path):
    data = npm._postscript_for_pages([(_chart(tmp_path / "c.tif"), 0)], None)
    assert b"/DeviceRGB setcolorspace" in data
    assert b"%cupsJobTicket: cups-disable-cmm" in data
    assert b"CIEBased" not in data


def test_several_pages_are_one_document_with_a_page_each(tmp_path):
    a = _chart(tmp_path / "a.tif", (1, 2, 3))
    b = _chart(tmp_path / "b.tif", (4, 5, 6))
    data = npm._postscript_for_pages([(a, 0), (b, 0)], (200.0, 300.0)).decode()
    assert data.startswith("%!PS-Adobe-3.0")
    assert "%%Pages: 2" in data
    assert re.findall(r"^%%Page: (\d) \1$", data, re.M) == ["1", "2"]
    assert data.count("colorimage") == 2 and data.count("showpage") == 2
    assert data.rstrip().endswith("%%EOF") and data.count("%%EOF") == 1


def test_a_later_frame_of_a_multi_page_tiff_is_the_one_sent(tmp_path):
    p = tmp_path / "m.tif"
    frames = [Image.new("RGB", (30, 20), c) for c in ((9, 9, 9), (200, 100, 50))]
    frames[0].save(p, save_all=True, append_images=frames[1:], dpi=(100, 100))
    one = npm._postscript_for_pages([(p, 1)], None)
    single = tmp_path / "f1.tif"
    frames[1].save(single, dpi=(100, 100))
    assert one == npm._postscript_for_pages([(single, 0)], None)


def test_print_frames_sends_a_postscript_printer_its_own_postscript():
    """MUTATION: remove the branch and a PostScript printer gets the chart
    through the print view again, CIEBased."""
    src = inspect.getsource(npm.print_frames)
    # 4.3.5 beta 2: on the form chosen for the run, its own RGB by default
    assert "_is_ps = is_postscript_queue(_ppd_after)" in src
    branch = src.index("if _is_ps and postscript_form == POSTSCRIPT_DEVICE_RGB:")
    assert "return _print_device_rgb_postscript(print_info, pages, locked)" in src[branch:]
    # after ChromIQ's own locks are set, before any re-tag or print view job
    assert src.index("_lock_no_color_management(print_info, after_dialog=True)") < branch
    assert branch < src.index("_destination_rgb_profile(print_info)")
    assert branch < src.index("printOperationWithView_printInfo_")


def test_it_goes_with_the_dialogs_settings_and_page_format():
    src = inspect.getsource(npm._print_device_rgb_postscript)
    assert "PMPrinterPrintWithFile(" in src
    assert '"application/postscript"' in src
    assert "PMPrintSettings" in src and "PMPageFormat" in src


@pytest.fixture
def queue(monkeypatch, tmp_path):
    ppd = tmp_path / "q.ppd"
    ppd.write_text(GENERIC_PS, encoding="utf-8")
    from workflow.print_manager import PrintModule
    monkeypatch.setattr(PrintModule, "find_ppd_path", staticmethod(lambda q: str(ppd)))
    monkeypatch.setattr(npm, "_queue_name", lambda d: "Q")
    monkeypatch.setattr(pt, "find_job", lambda q, since: 50)
    monkeypatch.setattr(
        pt, "check_job",
        lambda q, job, exp, ppd_text=None, tagged_with=None, tagged_icc=None:
        pt.TicketReport(queue=q, job_id=job, read=True, expected=dict(exp),
                        tagged_with=tagged_with))


def test_the_read_back_does_not_call_a_device_rgb_job_untagged(queue):
    """An untagged job with an output intent is reported as converted by
    macOS (B3); a DeviceRGB PostScript job has nothing to tag and was not."""
    sub = npm.Submission("Q", dict(npm._LOCKED_COLOR_SETTINGS), 0.0, b"", None,
                         output_intent="Knut 2026.02.09")
    sub.device_rgb = True
    rep = npm.read_back(sub)
    assert rep.ok and rep.device_rgb
    assert rep.tag_matches_job is None and rep.tagged_intent is None


def _status_of(rep):
    from ui.tabs import tab_print as tp
    seen = {}
    tab = tp.TabPrint.__new__(tp.TabPrint)
    tab._set_status = lambda text: seen.setdefault("status", text)
    tp.TabPrint._report_job_ticket(tab, rep)
    return seen["status"]


def test_the_status_line_says_so_only_while_approved(monkeypatch):
    """Approved by Basti, 2026-10-11: said after a DeviceRGB job, and only
    while approved."""
    from dataclasses import replace
    from workflow import measurement_messages as MM
    assert MM.M_PRINT_JOB_DEVICE_RGB.approved
    rep = pt.TicketReport(queue="Q", job_id=50, read=True, expected={})
    rep.device_rgb = True
    plain = ("Sent as job 50. The printing system confirms it carries "
             "application colour matching.")
    assert _status_of(rep) == plain + " " + MM.M_PRINT_JOB_DEVICE_RGB.body
    rep.device_rgb = False
    assert _status_of(rep) == plain
    rep.device_rgb = True
    monkeypatch.setattr(MM, "M_PRINT_JOB_DEVICE_RGB",
                        replace(MM.M_PRINT_JOB_DEVICE_RGB, approved=False))
    # shown while proposed too (§M, Knut #182 6166519230)
    assert _status_of(rep) == plain + " " + MM.M_PRINT_JOB_DEVICE_RGB.body
