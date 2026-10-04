"""scripts/check_print_ticket.py reads a CUPS job ticket correctly (#200).

The tickets are built here in IPP encoding (RFC 8010), the format CUPS writes
its control files in, so the parser is held to the format and not to one
printer's file.
"""
import importlib.util
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "check_print_ticket", ROOT / "scripts" / "check_print_ticket.py")
cpt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cpt)


def _attr(tag: int, name: str, value: bytes) -> bytes:
    n = name.encode()
    return bytes([tag]) + struct.pack(">H", len(n)) + n + struct.pack(">H", len(value)) + value


def _ticket(*attrs: bytes, pad: int = 3000) -> bytes:
    body = b"\x02\x00" + b"\x00\x02" + struct.pack(">i", 1)       # version, op, id
    body += b"\x02" + b"".join(attrs)                              # job group
    body += _attr(0x41, "padding-for-a-real-ticket", b"x" * pad)   # real files are ~4-5 KB
    return body + b"\x03"


TEXT, NAME_, URI, INT = 0x41, 0x42, 0x45, 0x21


def _canon(intent: bytes = b"1001", ap: bytes = b"AP_ApplicationColorMatching", *extra):
    return _ticket(
        _attr(URI, "job-printer-uri", b"ipp://localhost/printers/Canon_PRO_300"),
        _attr(NAME_, "job-name", b"chart.tif"),
        _attr(TEXT, "AP_ColorMatchingMode", ap),
        _attr(TEXT, "CNIJIntent2", intent),
        *extra)


def _expect_canon(queue):
    assert queue == "Canon_PRO_300"
    return [("AP_ColorMatchingMode", "AP_ApplicationColorMatching"), ("CNIJIntent2", "1001")]


def test_a_short_value_is_read_like_any_other():
    attrs = cpt.parse_ipp(_canon(intent=b"6"))
    assert attrs["CNIJIntent2"] == ["6"]
    assert cpt.queue_of(attrs) == "Canon_PRO_300"


def test_the_right_settings_read_ok(tmp_path):
    lines = cpt.report(str(tmp_path / "c00001"), _canon(), _expect_canon)
    assert any(l.split() == ["ok", "AP_ColorMatchingMode", "=", "AP_ApplicationColorMatching"] for l in lines)
    assert any(l.split() == ["ok", "CNIJIntent2", "=", "1001"] for l in lines)
    assert not any("WRONG" in l or "MISSING" in l for l in lines)


def test_the_vendors_own_intent_is_caught_when_wrong(tmp_path):
    lines = cpt.report(str(tmp_path / "c00002"), _canon(intent=b"6"), _expect_canon)
    assert any(l.split()[:2] == ["WRONG", "CNIJIntent2"] and "should be 1001" in l for l in lines)


def test_a_missing_key_and_the_dotted_name_are_flagged(tmp_path):
    data = _ticket(
        _attr(URI, "job-printer-uri", b"ipp://localhost/printers/Canon_PRO_300"),
        _attr(TEXT, "AP.ColorMatchingMode", b"AP_ApplicationColorMatching"),
        _attr(TEXT, "CNIJIntent2", b"1001"))
    lines = cpt.report(str(tmp_path / "c00003"), data, _expect_canon)
    assert any(l.split()[:2] == ["MISSING", "AP_ColorMatchingMode"] for l in lines)
    assert any("AP.ColorMatchingMode" in l and "no driver reads" in l for l in lines)


def test_an_unknown_colour_option_is_listed_not_hidden(tmp_path):
    lines = cpt.report(str(tmp_path / "c00004"),
                       _canon(b"1001", b"AP_ApplicationColorMatching",
                              _attr(TEXT, "EPIJ_ColorMode", b"Vivid")),
                       _expect_canon)
    assert any(l.split()[:2] == ["also", "EPIJ_ColorMode"] for l in lines)


def test_a_small_ticket_is_read_not_skipped(tmp_path):
    """An ``lp`` job (ChromIQ's direct route) is well under 2 KB and carries
    every setting; it must never be waved through as a "stub"."""
    data = _ticket(
        _attr(URI, "job-printer-uri", b"ipp://localhost/printers/Canon_PRO_300"),
        _attr(NAME_, "AP_ColorMatchingMode", b"AP_ApplicationColorMatching"),
        _attr(NAME_, "CNIJIntent2", b"6"), pad=0)
    assert len(data) < 1000
    lines = cpt.report(str(tmp_path / "c00005"), data, _expect_canon)
    assert any(l.split()[:2] == ["WRONG", "CNIJIntent2"] for l in lines)


def test_a_file_that_is_not_ipp_says_so(tmp_path):
    lines = cpt.report(str(tmp_path / "c00005"), b"\x00" * 900, _expect_canon)
    assert len(lines) == 1 and "not a CUPS control file" in lines[0]


def test_an_unknown_printer_still_checks_apples_key(tmp_path):
    data = _ticket(_attr(URI, "job-printer-uri", b"ipp://localhost/printers/Other"),
                   _attr(TEXT, "AP_ColorMatchingMode", b"AP_VendorColorMatching"))
    lines = cpt.report(str(tmp_path / "c00006"), data,
                       lambda q: [("AP_ColorMatchingMode", "AP_ApplicationColorMatching")])
    assert any(l.split()[:2] == ["WRONG", "AP_ColorMatchingMode"] for l in lines)
    assert any("no printer-specific colour option known" in l for l in lines)


def test_an_integer_and_an_additional_value_decode(tmp_path):
    data = _ticket(_attr(INT, "copies", struct.pack(">i", 2)),
                   _attr(TEXT, "print-color-mode", b"color"),
                   _attr(TEXT, "", b"monochrome"))
    attrs = cpt.parse_ipp(data)
    assert attrs["copies"] == ["2"]
    assert attrs["print-color-mode"] == ["color", "monochrome"]


# --- the real format: libcups 2.3.4 wrote this file -----------------------
# tests/data/cups_control_file_libcups.bin was produced on macOS 27 by a C
# probe linked against the system libcups: cupsParseOptions + cupsEncodeOptions2
# (what ``lp -o`` does) for the operation and job groups, a media-col
# collection, a no-value and a textWithLanguage attribute, then ippWriteIO with
# no parent (how cupsd saves a job's control file). The expected values are
# what libcups' own ippAttributeString printed for each attribute.

def test_a_file_written_by_libcups_parses_to_what_libcups_says():
    t = cpt.parse_ticket((ROOT / "tests/data/cups_control_file_libcups.bin").read_bytes())
    assert not t.truncated and not t.not_ipp
    assert t.job["AP_ColorMatchingMode"] == ["AP_ApplicationColorMatching"]
    assert t.job["CNIJIntent2"] == ["1001"]          # encoded as a name, not an integer
    assert t.job["copies"] == ["2"]
    assert t.job["orientation-requested"] == ["4"]   # an enum
    assert t.job["MyBool"] == ["true"]
    assert t.job["media-col"] == ["{media-size={x-dimension=21000 y-dimension=29700}}"]
    assert t.job["job-printer-state-message"] == ["(no-value)"]
    assert t.job["job-printer-state-reasons-x"] == ["Hallo"]   # textWithLanguage
    assert t.groups["printer-uri"] == [0x01] and "printer-uri" not in t.job
    assert cpt.queue_of(t.attrs) == "Canon_PRO_300"


def _coll(name: str, *members: bytes) -> bytes:
    return _attr(0x34, name, b"") + b"".join(members) + _attr(0x37, "", b"")


def _member(name: str, tag: int, value: bytes) -> bytes:
    return _attr(0x4A, "", name.encode()) + _attr(tag, "", value)


def test_a_collection_neither_desynchronises_nor_leaks_into_its_neighbours():
    data = _ticket(
        _attr(NAME_, "CNIJIntent2", b"1001"),
        _coll("media-col",
              _attr(0x4A, "", b"media-size"), _attr(0x34, "", b""),
              _member("x-dimension", INT, struct.pack(">i", 21000)),
              _attr(0x37, "", b""),
              _member("media-color", 0x44, b"white")),
        _attr(0x34, "", b""), _member("media-type", 0x44, b"photo"), _attr(0x37, "", b""),
        _attr(NAME_, "AP_ColorMatchingMode", b"AP_ApplicationColorMatching"))
    attrs = cpt.parse_ipp(data)
    assert attrs["CNIJIntent2"] == ["1001"]
    assert attrs["media-col"] == ["{media-size={x-dimension=21000} media-color=white}",
                                  "{media-type=photo}"]
    assert attrs["AP_ColorMatchingMode"] == ["AP_ApplicationColorMatching"]


def test_out_of_band_extension_and_typed_values_decode():
    data = _ticket(
        _attr(0x13, "job-hold-until", b""),
        _attr(0x7F, "ext", struct.pack(">I", 0x41) + b"hello"),
        _attr(0x33, "page-ranges", struct.pack(">ii", 1, 5)),
        _attr(0x32, "printer-resolution", struct.pack(">iib", 600, 600, 3)),
        _attr(0x36, "job-name", struct.pack(">H", 5) + b"de-de" + struct.pack(">H", 3) + b"Tom"),
        _attr(NAME_, "CNIJIntent2", b"1001"))
    attrs = cpt.parse_ipp(data)
    assert attrs["job-hold-until"] == ["(no-value)"]
    assert attrs["ext"] == ["hello"]
    assert attrs["page-ranges"] == ["1-5"]
    assert attrs["printer-resolution"] == ["600x600dpi"]
    assert attrs["job-name"] == ["Tom"]
    assert attrs["CNIJIntent2"] == ["1001"]


def test_a_truncated_file_is_flagged_and_does_not_crash(tmp_path):
    data = _canon()[:-40]
    t = cpt.parse_ticket(data)
    assert t.truncated
    lines = cpt.report(str(tmp_path / "c00007"), data, _expect_canon)
    assert any("ends early" in l for l in lines)


def test_an_option_outside_the_job_group_is_not_counted_as_received(tmp_path):
    """cupsd hands a driver job attributes only; the same key in the
    operation group must not read "ok"."""
    body = b"\x02\x00\x00\x02" + struct.pack(">i", 1)
    body += b"\x01" + _attr(TEXT, "AP_ColorMatchingMode", b"AP_ApplicationColorMatching")
    body += b"\x02" + _attr(URI, "job-printer-uri", b"ipp://localhost/printers/Canon_PRO_300")
    body += _attr(TEXT, "CNIJIntent2", b"1001") + b"\x03"
    lines = cpt.report(str(tmp_path / "c00008"), body, _expect_canon)
    assert any(l.split()[:2] == ["MISSING", "AP_ColorMatchingMode"] and "operation" in l
               for l in lines)
    assert any(l.split() == ["ok", "CNIJIntent2", "=", "1001"] for l in lines)


def test_every_value_must_match_not_only_the_first(tmp_path):
    data = _canon(b"1001", b"AP_ApplicationColorMatching", _attr(TEXT, "", b"6"))
    lines = cpt.report(str(tmp_path / "c00009"), data, _expect_canon)
    assert any(l.split()[:2] == ["WRONG", "CNIJIntent2"] for l in lines)


def test_a_job_with_none_of_the_settings_says_so(tmp_path):
    data = _ticket(_attr(URI, "job-printer-uri", b"ipp://localhost/printers/Canon_PRO_300"))
    lines = cpt.report(str(tmp_path / "c00010"), data, _expect_canon)
    assert any("none of these settings is in the job" in l for l in lines)


def test_queue_names_from_every_uri_form():
    q = lambda uri: cpt.queue_of({"job-printer-uri": [uri]})
    assert q("ipp://localhost/printers/Canon_PRO_300") == "Canon_PRO_300"
    assert q("ipp://mac.local:631/printers/EPSON_ET_8550/") == "EPSON_ET_8550"
    assert q("ipp://localhost/classes/Photo") == "Photo"
    assert q("ipp://localhost/printers/My%20Printer") == "My Printer"
    assert q("ipp://localhost/printers/HP?waitjob=false") == "HP"
    assert cpt.queue_of({"printer-uri": ["ipp://localhost/printers/X"]}) == "X"


def test_epsons_cmat_and_canons_intent_count_as_colourish_and_ordinary_words_do_not():
    for name in ("EPIJ_CMat", "CNIJIntent2", "HPPhotoRGB", "ColorModel",
                 "APCustomColorMatchingProfile", "cupsColorSpace"):
        assert cpt.COLOURISH.search(name), name
    for name in ("copies", "job-uuid", "media-col", "Duplex", "acmeTray"):
        assert not cpt.COLOURISH.search(name), name


def test_an_unreadable_file_is_an_error_not_a_traceback(tmp_path, capsys):
    assert cpt.main(["--file", str(tmp_path / "nope")]) == 1
    assert "cannot read" in capsys.readouterr().err


def test_a_value_type_cupsd_never_hands_to_a_driver_is_not_ok(tmp_path):
    """job.c get_options drops nameWithLanguage values: such a key is in the
    ticket and still never reaches the driver."""
    lang = struct.pack(">H", 5) + b"en-us" + struct.pack(">H", 4) + b"1001"
    data = _canon(b"1001", b"AP_ApplicationColorMatching")
    data = data.replace(_attr(TEXT, "CNIJIntent2", b"1001"), _attr(0x36, "CNIJIntent2", lang))
    lines = cpt.report(str(tmp_path / "c00011"), data, _expect_canon)
    assert any(l.split()[:2] == ["MISSING", "CNIJIntent2"] and "does not hand" in l
               for l in lines)
