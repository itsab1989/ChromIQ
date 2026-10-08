"""The chart prints in the printer state a Photoshop print gets (beta 15).

Basti, 2026-10-08: *the chart must print in EXACTLY the state the user's later
image prints will be in*, and those come from Photoshop with "Photoshop manages
colours". Measured on macOS 27.0.1 with capture queues (report folder
2026-10-08_print_fix): Photoshop's own ticket key is AP_ColorMatchingMode alone;
the Canon and Epson print dialogs add the medium's paper profile; macOS converts
tagged colour into that profile, so the chart must carry exactly it.

These tests pin, per route and vendor:
* which keys the job carries (lp: built by ChromIQ; dialog: only the Apple key),
* that the chart handed to the print path is tagged with the job's own profile,
* that the "verified" check reads the job back from CUPS, not ChromIQ's own dict.
"""
from __future__ import annotations

import sys
import zlib
from pathlib import Path

import numpy as np
import pytest

import workflow.cups_printer as cups_printer
import workflow.print_ticket as print_ticket
from workflow.cups_printer import (CupsRawPrinter, PrintConfig, job_id_from_lp_output,
                                   write_tagged_tiff)
from workflow.ppd_color import (PAPER_PROFILE_RULES, paper_profile_for)
from workflow.postscript_generator import PdfGenerator

# --- a Canon IJ PPD as the PRO-300 driver 30.10.1 writes it (the parts that matter)
CANON_PPD = """*PPD-Adobe: "4.3"
*cupsICCProfile RGB16.1./CN_IJPrinter_Profile2015.icc: "{dir}/generic.icc"
*cupsICCProfile RGB16.3./CN_PRO-300_G1_PhotoPaperProPlatinum.icc: "{dir}/platinum.icc"
*cupsICCProfile RGB16.6./CN_PRO-300_G1_MattePhotoPaper-P.icc: "{dir}/matte.icc"
*cupsICCProfile RGB16.10./CN_PRO-300_G1_BarytaPhotoPaper-P.icc: "{dir}/baryta.icc"
*OpenUI *CNIJMediaType/Media Type: PickOne
*DefaultCNIJMediaType: 51
*CNIJMediaType 0/Plain Paper: ""
*CNIJMediaType 51/Photo Paper Pro Platinum: ""
*CNIJMediaType 28/Matte Photo Paper: ""
*CNIJMediaType 165/Baryta Photo Paper: ""
*CNIJMediaType 162/Card Stock: ""
*CloseUI: *CNIJMediaType
*OpenUI *CNIJIntent2/Rendering Intent: PickOne
*DefaultCNIJIntent2: 5
*CNIJIntent2 5/Perceptual (Photo): ""
*CNIJIntent2 1001/No Color Correction: ""
*CloseUI: *CNIJIntent2
*cupsICCQualifier2: CNIJProfileID
*OpenUI *CNIJProfileID/ProfileID: PickOne
*DefaultCNIJProfileID: 1
*CNIJProfileID 1/CN_IJPrinter_Profile2015.icc: ""
*CNIJProfileID 3/CN_PRO-300_G1_PhotoPaperProPlatinum.icc: ""
*CNIJProfileID 6/CN_PRO-300_G1_MattePhotoPaper-P.icc: ""
*CNIJProfileID 10/CN_PRO-300_G1_BarytaPhotoPaper-P.icc: ""
*CloseUI: *CNIJProfileID
"""

EPSON_PPD = """*PPD-Adobe: "4.3"
*cupsICCProfile ..1/EPSON ET-8550 L8180 Series Standard: "{dir}/standard.icc"
*cupsICCProfile ..3/EPSON ET-8550 L8180 Series Premium Glossy: "{dir}/premglossy.icc"
*cupsICCProfile ..7/EPSON ET-8550 L8180 Series Velvet Fine Art: "{dir}/velvet.icc"
*cupsICCProfile ..0/sRGB Profile: "{dir}/srgb.icc"
*cupsICCQualifier3: EPIJProfileSpec
*OpenUI *EPIJ_Medi/Media Type: PickOne
*DefaultEPIJ_Medi: 0
*EPIJ_Medi 0/Plain paper: ""
*EPIJ_Medi 13/Epson Premium Glossy: ""
*EPIJ_Medi 53/Velvet Fine Art Paper: ""
*CloseUI: *EPIJ_Medi
*OpenUI *EPIJ_CMat/Color Settings: PickOne
*DefaultEPIJ_CMat: 0
*EPIJ_CMat 0/Manual Settings: ""
*EPIJ_CMat 3/Off (No Color Adjustment): ""
*CloseUI: *EPIJ_CMat
*OpenUI *EPIJProfileSpec/EPSON Profile: PickOne
*DefaultEPIJProfileSpec: 0
*EPIJProfileSpec 0/None: ""
*EPIJProfileSpec 1/EPSON ET-8550 L8180 Series Standard: ""
*EPIJProfileSpec 3/EPSON ET-8550 L8180 Series Premium Glossy: ""
*EPIJProfileSpec 7/EPSON ET-8550 L8180 Series Velvet Fine Art: ""
*CloseUI: *EPIJProfileSpec
"""


def _ppd(tmp_path: Path, text: str) -> str:
    for name in ("generic", "platinum", "matte", "baryta", "standard", "premglossy",
                 "velvet", "srgb"):
        (tmp_path / f"{name}.icc").write_bytes(b"ICC-" + name.encode())
    return text.replace("{dir}", str(tmp_path))


# ---- the vendor facts: what the print dialog writes for each medium ----------
#: (medium, paper profile id) pairs the Canon PRO-300 dialog wrote, measured
CANON_DIALOG = [("0", "1"), ("51", "3"), ("28", "6"), ("165", "10"), ("162", "1")]
#: (medium, EPIJProfileSpec) pairs the ET-8550 dialog wrote, measured
EPSON_DIALOG = [("0", "1"), ("13", "3"), ("53", "7")]


@pytest.mark.parametrize("media,pid", CANON_DIALOG)
def test_canon_medium_selects_the_paper_profile_the_dialog_selects(tmp_path, media, pid):
    pp = paper_profile_for(_ppd(tmp_path, CANON_PPD), {"CNIJMediaType": media})
    assert pp is not None and pp.option == "CNIJProfileID"
    assert pp.value == pid
    assert pp.icc_path and Path(pp.icc_path).exists()
    assert pp.is_default == (pid == "1")


@pytest.mark.parametrize("media,spec", EPSON_DIALOG)
def test_epson_medium_selects_the_profile_the_dialog_selects(tmp_path, media, spec):
    pp = paper_profile_for(_ppd(tmp_path, EPSON_PPD), {"EPIJ_Medi": media})
    assert pp is not None and pp.option == "EPIJProfileSpec"
    assert pp.value == spec
    # qualifier 3 picks the file
    assert Path(pp.icc_path).read_bytes() == {
        "1": b"ICC-standard", "3": b"ICC-premglossy", "7": b"ICC-velvet"}[spec]


def test_a_ppd_without_a_profile_qualifier_is_not_a_reference_vendor():
    hp = "*OpenUI *HPColorMode/Color Mode: PickOne\n*HPColorMode application-managed/Application Managed: \"\"\n*CloseUI: *HPColorMode\n"
    assert paper_profile_for(hp) is None


def test_every_rule_names_its_evidence():
    for rule in PAPER_PROFILE_RULES:
        assert "2026-10-08" in rule.evidence and "macOS 27" in rule.evidence


# ---- lp route: the job carries the reference keys and nothing else ----------
def _rgb_chart(path: Path) -> Path:
    import tifffile
    a = np.zeros((20, 30, 3), np.uint8)
    a[:, :10] = (255, 0, 0)
    a[:, 10:20] = (0, 0, 255)
    a[:, 20:] = (30, 200, 90)
    tifffile.imwrite(str(path), a, photometric="rgb", resolution=(300, 300),
                     resolutionunit="INCH")
    return path


def _capture_lp(monkeypatch):
    sent = {}

    def fake_run(self, cmd):
        doc = Path(cmd[-1])
        sent["cmd"] = cmd
        sent["doc"] = doc.read_bytes()
        sent["suffix"] = doc.suffix
        self.last_job_id = 42
        return 0, ""
    monkeypatch.setattr(CupsRawPrinter, "_run_lp_result", fake_run)
    return sent


@pytest.mark.parametrize("vendor", ["canon", "epson"])
@pytest.mark.parametrize("pdf", [False, True])
def test_lp_reference_job_keys_and_tag(tmp_path, monkeypatch, vendor, pdf):
    text = _ppd(tmp_path, CANON_PPD if vendor == "canon" else EPSON_PPD)
    medium = {"canon": ("CNIJMediaType", "28"), "epson": ("EPIJ_Medi", "13")}[vendor]
    monkeypatch.setattr(cups_printer, "paper_profile_for_queue",
                        lambda q, opts=None: paper_profile_for(text, opts))
    sent = _capture_lp(monkeypatch)
    chart = _rgb_chart(tmp_path / "c.tif")
    pr = CupsRawPrinter()
    codes = []
    pr.print_job_ps(chart, PrintConfig("Q", {medium[0]: medium[1], "PageSize": "A4"}),
                    on_finish=codes.append, page_size_pt=(595.0, 842.0), pdf_fallback=pdf)
    assert codes == [0]
    opts = dict(t.split("=", 1) for t in sent["cmd"][4:-1:2])
    assert opts["AP_ColorMatchingMode"] == "AP_ApplicationColorMatching"
    want_profile = {"canon": ("CNIJProfileID", "6"), "epson": ("EPIJProfileSpec", "3")}[vendor]
    assert opts[want_profile[0]] == want_profile[1]
    # nothing Photoshop does not send
    for k in ("ColorSync", "CNIJIntent2", "cupsColorSpace", "ColorModel", "cupsBitsPerColor"):
        assert k not in opts, k
    if vendor == "epson":
        # what the Epson dialog writes in application colour matching, every medium
        assert opts["EPIJ_CMat"] == "3" and opts["EPIJ_Mode"] == "3"
        assert opts["EPIJ_OSColMat"] == "2" and opts["EPIJ_OSCMProf"] == "1"
    else:
        assert not any(k.startswith("EPIJ") for k in opts)
    icc = Path(pr.last_paper_profile.icc_path).read_bytes()
    if pdf:
        assert sent["suffix"] == ".pdf"
        assert b"/ICCBased" in sent["doc"]
        assert zlib.compress(icc, 6) in sent["doc"]
    else:
        assert sent["suffix"] == ".tif"
        from PIL import Image
        import io
        im = Image.open(io.BytesIO(sent["doc"]))
        assert im.info.get("icc_profile") == icc
        assert np.array_equal(np.asarray(im), np.asarray(Image.open(chart)))
    assert pr.last_expected[want_profile[0]] == want_profile[1]
    assert pr.last_job_id == 42


def test_a_generic_printer_keeps_the_beta14_job(tmp_path, monkeypatch):
    monkeypatch.setattr(cups_printer, "paper_profile_for_queue", lambda q, opts=None: None)
    monkeypatch.setattr(cups_printer, "vendor_no_cm_settings_for_queue",
                        lambda q: [("HPColorMode", "application-managed")])
    cmd = CupsRawPrinter._build_lp_command_ps(Path("/tmp/x.ps"), PrintConfig("HP", {}))
    assert "ColorSync=None" in cmd and "HPColorMode=application-managed" in cmd
    assert "AP_ColorMatchingMode=AP_ApplicationColorMatching" in cmd


def test_a_cmyk_chart_on_a_canon_takes_the_generic_route(tmp_path, monkeypatch):
    import tifffile
    text = _ppd(tmp_path, CANON_PPD)
    monkeypatch.setattr(cups_printer, "paper_profile_for_queue",
                        lambda q, opts=None: paper_profile_for(text, opts))
    p = tmp_path / "k.tif"
    tifffile.imwrite(str(p), np.zeros((4, 4, 4), np.uint8), photometric="separated")
    assert CupsRawPrinter._reference_paper_profile(p, PrintConfig("Q", {})) is None


def test_tagged_tiff_keeps_pixels_and_resolution(tmp_path):
    src = _rgb_chart(tmp_path / "a.tif")
    dst = tmp_path / "b.tif"
    write_tagged_tiff(src, dst, b"PROFILE")
    from PIL import Image
    a, b = Image.open(src), Image.open(dst)
    assert np.array_equal(np.asarray(a), np.asarray(b))
    assert b.info.get("icc_profile") == b"PROFILE"
    assert tuple(round(x) for x in b.info["dpi"]) == (300, 300)


def test_pdf_untagged_stays_device_rgb(tmp_path):
    pdf = PdfGenerator().generate(_rgb_chart(tmp_path / "c.tif"))
    assert b"/DeviceRGB" in pdf and b"/ICCBased" not in pdf


@pytest.mark.parametrize("text,job", [
    ("request id is ChromIQ_Cap_PRO300-91 (1 file(s))", 91),
    ("Anfrage-ID ist Canon_PRO_300_–12 (1 Datei(en))", 12),
    ("", None),
])
def test_job_id_from_lp_output(text, job):
    assert job_id_from_lp_output(text) == job


# ---- the read-back: what CUPS holds, not what ChromIQ wrote -------------------
def _ticket(monkeypatch, attrs):
    monkeypatch.setattr(print_ticket, "read_ticket", lambda j: attrs)


def test_read_back_canon_photo_paper(tmp_path, monkeypatch):
    text = _ppd(tmp_path, CANON_PPD)
    _ticket(monkeypatch, {"AP_ColorMatchingMode": "AP_ApplicationColorMatching",
                          "CNIJMediaType": "28", "CNIJProfileID": "6"})
    rep = print_ticket.check_job("Q", 7, {"AP_ColorMatchingMode": "AP_ApplicationColorMatching",
                                         "CNIJProfileID": "6"}, ppd_text=text)
    assert rep.ok and rep.read
    assert rep.paper_profile.label == "CN_PRO-300_G1_MattePhotoPaper-P.icc"
    assert rep.own_colour_processing == "off"


def test_read_back_canon_beta14_lp_job_is_caught(tmp_path, monkeypatch):
    """What beta 14 sent on photo paper: application mode, no paper profile ->
    the Canon ran its own colour processing although ChromIQ said 'off'."""
    text = _ppd(tmp_path, CANON_PPD)
    _ticket(monkeypatch, {"AP_ColorMatchingMode": "AP_ApplicationColorMatching",
                          "CNIJMediaType": "28", "CNIJIntent2": "1001"})
    rep = print_ticket.check_job("Q", 7, {"AP_ColorMatchingMode": "AP_ApplicationColorMatching",
                                         "CNIJProfileID": "6"}, ppd_text=text)
    assert not rep.ok
    assert rep.mismatches == {"CNIJProfileID": (None, "6")}
    assert rep.own_colour_processing == "on"


def test_read_back_canon_plain_paper_is_the_printers_own_processing(tmp_path, monkeypatch):
    text = _ppd(tmp_path, CANON_PPD)
    _ticket(monkeypatch, {"AP_ColorMatchingMode": "AP_ApplicationColorMatching",
                          "CNIJMediaType": "0", "CNIJProfileID": "1"})
    rep = print_ticket.check_job("Q", 7, {"AP_ColorMatchingMode": "AP_ApplicationColorMatching",
                                         "CNIJProfileID": "1"}, ppd_text=text)
    assert rep.ok and rep.own_colour_processing == "on"


def test_read_back_native_tag_must_be_the_jobs_profile(tmp_path, monkeypatch):
    text = _ppd(tmp_path, CANON_PPD)
    _ticket(monkeypatch, {"AP_ColorMatchingMode": "AP_ApplicationColorMatching",
                          "CNIJMediaType": "51", "CNIJProfileID": "3"})
    desc = {str(tmp_path / "platinum.icc"): "Canon PRO-300/G1 Photo Paper Pro Platinum"}
    good = print_ticket.check_job(
        "Q", 7, {"AP_ColorMatchingMode": "AP_ApplicationColorMatching"}, ppd_text=text,
        tagged_with="Canon PRO-300/G1 Photo Paper Pro Platinum",
        tag_icc_desc_for=desc.get)
    assert good.ok and good.tag_matches_job is True
    bad = print_ticket.check_job(
        "Q", 7, {"AP_ColorMatchingMode": "AP_ApplicationColorMatching"}, ppd_text=text,
        tagged_with="sRGB IEC61966-2.1", tag_icc_desc_for=desc.get)
    assert not bad.ok and bad.tag_matches_job is False


def test_read_back_that_cannot_read_says_so(monkeypatch):
    _ticket(monkeypatch, None)
    rep = print_ticket.check_job("Q", 7, {"AP_ColorMatchingMode": "x"}, retries=1)
    assert not rep.read and not rep.ok


def test_the_native_route_no_longer_reads_back_its_own_dictionary():
    """The beta 14 'verified OFF' check compared ChromIQ's settings with
    themselves. It is gone; print_frames reads the job from CUPS."""
    src = Path(__file__).resolve().parent.parent / "workflow" / "native_print_macos.py"
    text = src.read_text(encoding="utf-8")
    assert "_verify_color_management" not in text
    assert "check_job(" in text and "find_job(" in text


def test_the_native_route_tags_the_chart_between_dialog_and_operation():
    """Order matters: the output profile is only known once the dialog has
    chosen the medium, and the view must carry the tag before the operation
    renders it."""
    src = (Path(__file__).resolve().parent.parent / "workflow" /
           "native_print_macos.py").read_text(encoding="utf-8")
    body = src[src.index("def print_frames("):]
    i_dialog = body.index("runModalWithPrintInfo_")
    i_dest = body.index("_destination_rgb_profile(print_info)")
    i_retag = body.index("_retag_reps(view._reps")
    i_op = body.index("printOperationWithView_printInfo_")
    assert i_dialog < i_dest < i_retag < i_op


# ---- macOS only: the colour space handed to the print path IS the profile ------
mac = pytest.mark.skipif(sys.platform != "darwin", reason="AppKit print path is macOS only")


@mac
def test_retagged_bitmap_carries_the_output_intent_and_its_pixels(tmp_path):
    pytest.importorskip("AppKit")
    import AppKit
    from workflow.native_print_macos import _retag_reps
    srgb = Path("/System/Library/ColorSync/Profiles/sRGB Profile.icc")
    candidates = [p for p in Path("/System/Library/ColorSync/Profiles").glob("*.icc")
                  if "RGB" in p.name and p != srgb]
    if not candidates:
        pytest.skip("no RGB system profile")
    icc = candidates[0].read_bytes()
    rep = AppKit.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, 4, 1, 8, 3, False, False, AppKit.NSDeviceRGBColorSpace, 12, 24)
    raw = bytes([255, 0, 0, 0, 0, 255, 30, 200, 90, 5, 5, 5])
    rep.bitmapData()[:12] = raw
    (tagged,) = _retag_reps([rep], icc)
    assert bytes(tagged.colorSpace().ICCProfileData()) == icc
    assert bytes(tagged.bitmapData()[:12]) == raw


@mac
def test_dialog_route_sets_only_the_apple_key_for_a_canon(tmp_path, monkeypatch):
    pytest.importorskip("AppKit")
    import workflow.native_print_macos as npm
    from workflow.print_manager import PrintModule
    ppd = tmp_path / "Q.ppd"
    ppd.write_text(_ppd(tmp_path, CANON_PPD), encoding="latin-1")
    monkeypatch.setattr(PrintModule, "find_ppd_path", staticmethod(lambda q: str(ppd)))

    class _P:
        def name(self):
            return "Q"

    class _PI:
        def printer(self):
            return _P()
    assert npm._locked_settings_for(_PI()) == {
        "AP_ColorMatchingMode": "AP_ApplicationColorMatching"}


def test_epson_dialog_keys_follow_the_medium():
    """Measured: the ET-8550 dialog writes EPIJ_CCor=3 on photo media and leaves
    the PPD's 12 on plain paper; lp must send the same."""
    rule = next(r for r in PAPER_PROFILE_RULES if r.vendor == "Epson")
    assert rule.dialog_keys_for("13")["EPIJ_CCor"] == "3"
    assert rule.dialog_keys_for("0")["EPIJ_CCor"] == "12"
    assert rule.dialog_keys_for("0")["EPIJ_CMat"] == "3"
