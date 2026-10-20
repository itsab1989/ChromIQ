"""#205 independent review: what a Windows PostScript driver's PPD choices do in
ChromIQ's raw job.

Measured on the Windows 11 ARM64 bench (report folder
``2026-10-20_205_windows_direct_print/07_review``, REVIEW.md 1, 2 and 6):

1. Microsoft's HP DesignJet T1300ps / Z3200ps data file ``hpips3t.ppd`` is a
   stub, ``*Include: "hpips3.PPD"``, and Media Type and Paper Source live in
   the included file. Read alone, the tab offered neither.
2. The Xerox v4 PPDs and the Microsoft PS Class Driver's write every choice as
   ``featurebegin{...}featurecleanup``, procedures of PSCRIPT5's own prolog that
   a raw job does not carry. Inside ChromIQ's ``stopped`` the ``undefined`` was
   swallowed and the choice never applied: Ghostscript read no /MediaType.
3. The spooler failure window showed ``[Errno 1801] OpenPrinter('...'): `` in
   front of Windows' sentence.

These run on every platform (the spooler is never reached).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from workflow import win_raw_printer as wrp
from workflow import win_spooler
from workflow.cups_printer import PrintConfig
from workflow.print_manager import PrintModule

STUB_PPD = """*PPD-Adobe: "4.3"
*Include: "inc_main.PPD"
*ModelName: "HP DesignJet T1300ps"
*OpenUI *PageSize: PickOne
*OrderDependency: 40 AnySetup *PageSize
*DefaultPageSize: A4
*PageSize A4/A4: "<< /PageSize [595 842] >> setpagedevice"
*PageSize Letter/Letter: "<< /PageSize [612 792] >> setpagedevice"
*CloseUI: *PageSize
"""

INCLUDED_PPD = """*OpenUI *MediaType: PickOne
*OrderDependency: 50.0 AnySetup *MediaType
*DefaultMediaType: Any
*MediaType Any/Any: ""
*MediaType Coated/Coated Paper: "/HPDict /ProcSet findresource /SetMediaId get (1100) exch exec"
*MediaType Plain/Plain Paper: "/HPDict /ProcSet findresource /SetMediaId get (1000) exch exec"
*CloseUI: *MediaType
"""

# as the Xerox v4 PPDs Windows ships write their choices (xrOFPScv12.PPD)
FEATUREBEGIN_PPD = """*PPD-Adobe: "4.3"
*OpenUI *MediaType/Media Type: PickOne
*OrderDependency: 45 DocumentSetup *MediaType
*DefaultMediaType: Plain
*MediaType Plain/Plain Paper: "featurebegin{<< /MediaType (stationery) >> setpagedevice}featurecleanup"
*MediaType HeavyPlain/Heavy Plain: "featurebegin{<< /MediaType (stationery-heavyweight) >> setpagedevice}featurecleanup"
*CloseUI: *MediaType
"""

PS = "%!PS-Adobe-3.0\n%%LanguageLevel: 3\n%%EndComments\n\nBODY\nshowpage\n%%EOF\n"


def _stub_with_include(tmp_path: Path) -> Path:
    (tmp_path / "inc_main.PPD").write_text(INCLUDED_PPD, encoding="latin-1")
    stub = tmp_path / "stub.ppd"
    stub.write_text(STUB_PPD, encoding="latin-1")
    return stub


def _rgb_tiff(path: Path) -> Path:
    import tifffile
    tifffile.imwrite(str(path), np.full((8, 8, 3), 128, np.uint8), photometric="rgb",
                     resolution=(300, 300), resolutionunit=2)
    return path


# ---- 1. *Include ----------------------------------------------------------------

def test_an_included_ppds_options_are_offered(tmp_path, monkeypatch):
    stub = _stub_with_include(tmp_path)
    monkeypatch.setattr(PrintModule, "_find_ppd_path", staticmethod(lambda p: str(stub)))
    all_opts, labels = PrintModule._windows_ppd_options("HP DJ T1300ps")
    assert set(all_opts) == {"PageSize", "MediaType"}
    assert all_opts["MediaType"] == ("Media Type", ["Any", "Coated", "Plain"])
    assert labels["MediaType"]["Coated"] == "Coated Paper"


def test_an_included_choice_goes_into_the_job(tmp_path, monkeypatch):
    stub = _stub_with_include(tmp_path)
    monkeypatch.setattr(win_spooler, "ppd_path", lambda p: str(stub))
    data = wrp.WindowsRawPrinter.job_bytes(
        _rgb_tiff(tmp_path / "c.tif"),
        PrintConfig(printer_name="HP DJ T1300ps", options={"MediaType": "Coated"}))
    assert b"%%BeginFeature: *MediaType Coated\n/HPDict /ProcSet findresource " \
           b"/SetMediaId get (1100) exch exec\n%%EndFeature" in data


def test_a_missing_or_looping_include_is_left_out(tmp_path):
    stub = tmp_path / "stub.ppd"
    stub.write_text(STUB_PPD.replace("inc_main.PPD", "not_there.PPD"), encoding="latin-1")
    assert set(wrp.ppd_options(wrp.read_ppd(stub))) == {"PageSize"}
    loop = tmp_path / "loop.ppd"
    loop.write_text('*Include: "loop.ppd"\n' + STUB_PPD.split("\n", 2)[2], encoding="latin-1")
    assert set(wrp.ppd_options(wrp.read_ppd(loop))) == {"PageSize"}     # it ends


# ---- 2. featurebegin / featurecleanup -------------------------------------------

def test_a_featurebegin_choice_gets_the_procedures_it_needs():
    out = wrp.with_features(PS, FEATUREBEGIN_PPD, {"MediaType": "HeavyPlain"})
    setup = out[out.index("%%BeginSetup"):out.index("%%EndSetup")]
    assert setup.index("/featurebegin where") < setup.index("%%BeginFeature")
    # still inside the protection that keeps an unknown feature from ending the job
    assert "featurecleanup\n%%EndFeature\n} stopped cleartomark" in setup


def test_a_plain_choice_gets_no_extra_procedures():
    out = wrp.with_features(PS, FEATUREBEGIN_PPD.replace(
        "featurebegin{", "").replace("}featurecleanup", ""), {"MediaType": "HeavyPlain"})
    assert "featurebegin" not in out


def _ghostscript() -> "str | None":
    return shutil.which("gswin64c") or shutil.which("gs")


@pytest.mark.skipif(_ghostscript() is None, reason="needs Ghostscript")
def test_ghostscript_applies_a_featurebegin_choice(tmp_path):
    ps = ("%!PS-Adobe-3.0\n%%LanguageLevel: 3\n%%EndComments\n\n"
          "currentpagedevice dup /MediaType known {/MediaType get} {pop (absent)} "
          "ifelse print\nshowpage\n%%EOF\n")
    job = tmp_path / "job.ps"
    job.write_text(wrp.with_features(ps, FEATUREBEGIN_PPD, {"MediaType": "HeavyPlain"}),
                   encoding="latin-1")
    r = subprocess.run([_ghostscript(), "-q", "-dSAFER", "-dBATCH", "-dNOPAUSE",
                        "-sDEVICE=nullpage", str(job)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == "stationery-heavyweight"


# ---- 3. the reason in the failure window is Windows' own sentence -------------------

def test_the_failure_window_gets_windows_sentence_alone(tmp_path, monkeypatch):
    import ctypes
    # ctypes.get_last_error exists only on Windows; the gate runs on macOS too
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 1801, raising=False)
    monkeypatch.setattr(ctypes, "FormatError",
                        lambda code=None: "Der Druckername ist unzulässig.  ",
                        raising=False)
    err = win_spooler._error("OpenPrinter('Office Laser')")
    assert "OpenPrinter" in str(err)                      # the log keeps it all

    def _refused(*_a, **_k):
        raise err

    monkeypatch.setattr(win_spooler, "submit", _refused)
    monkeypatch.setattr(win_spooler, "ppd_path", lambda p: None)
    pr = wrp.WindowsRawPrinter()
    codes = []
    pr.print_job_ps(_rgb_tiff(tmp_path / "c.tif"),
                    PrintConfig(printer_name="Office Laser", options={}),
                    on_finish=codes.append)
    assert codes == [-1]
    assert pr.last_error == "Der Druckername ist unzulässig."
