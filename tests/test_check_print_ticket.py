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


def test_a_cancelled_dialog_stub_is_named_and_skipped(tmp_path):
    lines = cpt.report(str(tmp_path / "c00005"), b"\x02\x00" + b"\x00" * 900, _expect_canon)
    assert len(lines) == 1 and "stub" in lines[0]


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
