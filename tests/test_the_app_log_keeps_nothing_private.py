"""A0 (4.3.50): the app log's privacy filter scrubs EVERY line at the handler.

The app log is the one file a tester sends. These are adversarial lines: the
account name inside an ordinary word must survive, unicode names, Windows and
Linux homes, serial numbers in every shape ArgyllCMS prints them, and a filter
fault must never raise or drop a line."""
from __future__ import annotations

import logging

import pytest

from core import log_privacy as lp


@pytest.fixture
def ident():
    lp.reset_for_tests(homes=["/Users/basti", "C:\\Users\\basti"], names=["basti"],
                       phrases=["Sebastian Muster"], hosts=["Bastis-Mac-mini"],
                       printers=["Bastis_Epson_ET8550", "EPSON_SC_P900"])
    yield
    lp.reset_for_tests()


def S(line):
    return lp.safe_scrub(line)


def test_own_home_becomes_tilde(ident):
    assert S("Settings loaded from /Users/basti/Library/Preferences/com.chromiq.ChromIQ.plist") \
        == "Settings loaded from ~/Library/Preferences/com.chromiq.ChromIQ.plist"
    assert S("Run: /Users/basti/ChromIQ/Test/runs/run1") == "Run: ~/ChromIQ/Test/runs/run1"
    assert S("argv=['/Users/basti/develop/ChromIQ/main.py']") == "argv=['~/develop/ChromIQ/main.py']"
    assert S("C:\\Users\\basti\\ChromIQ\\x.ti3") == "~\\ChromIQ\\x.ti3"


def test_a_folder_that_only_starts_like_the_home_is_someone_else(ident):
    assert S("/Users/basti2/x") == "/Users/<user>/x"


def test_the_name_inside_an_ordinary_word_is_not_mangled(ident):
    # "basti_y" is a JOINED form since M2 (an underscore joins a device or
    # queue name) and is scrubbed below; a letter or digit still does not join
    line = "bastion of the bastille: Bastian_x xbasti basti2 Sebastiano Musterhaus"
    assert S(line) == line


def test_the_name_as_a_whole_word_is_replaced(ident):
    assert S("user basti started") == "user <user> started"
    assert S("owner=Basti.") == "owner=<user>."
    assert S("Sebastian Muster printed") == "<user> printed"


def test_other_homes(ident):
    assert S("/Users/anna/x and /home/jürgen/y") == "/Users/<user>/x and /home/<user>/y"
    assert S(r"C:\Users\Jürgen Groß\Documents\a.ti3") == r"C:\Users\<user>\Documents\a.ti3"
    assert S("C:/Users/olaf/AppData") == "C:/Users/<user>/AppData"
    assert S("/Users/Shared/ChromIQ and C:\\Users\\Public\\x") == \
        "/Users/Shared/ChromIQ and C:\\Users\\Public\\x"
    # a name with a space ends at a separator, and never eats the words after it
    assert S("C:\\Users\\ann was here") == "C:\\Users\\<user> was here"


def test_unicode_account_name():
    lp.reset_for_tests(homes=["/Users/jürgen"], names=["jürgen", "Søren"])
    try:
        assert S("/Users/jürgen/ChromIQ") == "~/ChromIQ"
        assert S("by Søren, not Sørensen") == "by <user>, not Sørensen"
        assert S("by JÜRGEN") == "by <user>"
    finally:
        lp.reset_for_tests()


def test_a_short_name_is_never_replaced_as_a_word():
    lp.reset_for_tests(homes=["/Users/al"], names=["al"])
    try:
        assert S("al dente total /Users/al/x") == "al dente total ~/x"
    finally:
        lp.reset_for_tests()


def test_computer_name(ident):
    assert S("ipp://Bastis-Mac-mini.local:631/printers/x") == "ipp://<computer>:631/printers/x"


@pytest.mark.parametrize("line,prefix", [
    ("Serial Number:     1234567", "Serial Number:     "),
    ("Serial Number:     001234", "Serial Number:     "),
    ("Serial number = 1234567", "Serial number = "),
    (" Serial number:       'AB12CD'", " Serial number:       '"),
    (" Spectrometer serial number: 12345", " Spectrometer serial number: "),
    ('{"serial": "X1234"}', '{"serial": "'),
    ('{"serial_no":98765}', '{"serial_no":'),
])
def test_serial_numbers_become_a_stable_hash(ident, line, prefix):
    out = S(line)
    assert out.startswith(prefix + "<sn:")
    assert not any(ch.isdigit() for ch in out[len(prefix) + 12:].strip("'\"}"))
    assert S(line) == out  # stable


def test_same_serial_same_hash_different_serial_different_hash(ident):
    a1 = S("Serial Number: 1234567").split()[-1]
    a2 = S("found ~/Library/Application Support/ArgyllCMS/.i1p_1234567.cal")
    b = S("Serial Number: 7654321").split()[-1]
    assert a1 in a2 and a1 != b
    assert "1234567" not in a2
    assert S(".i1p3_222.cal .mk_ABC9.cal").count("<sn:") == 2


def test_chip_id_mac_uuid_long_hex(ident):
    assert "a1-b2c3d4" not in S("Chip ID:           a1-b2c3d4e5f6a7b8")
    assert "<sn:" in S("CR30 at AA:BB:CC:11:22:33 connected")
    assert "<sn:" in S("peripheral 3F2504E0-4F89-11D3-9A0C-0305E82C3301")
    memory = "ab" * 88
    assert memory not in S("answer " + memory) and "176 digits" in S("answer " + memory)
    sha = "a" * 64
    assert sha in S("sha256 " + sha)  # a file's SHA-256 is kept


def test_ordinary_lines_survive_unchanged(ident):
    for line in ["serial port scan skipped", "Failed to parse serial number",
                 "strip A attempt 2: kept, dE 1.23 limit 3.00", "12:34:56 2026-11-20",
                 "chartread -v -c 1 -H Test", "printer=EPSON_SC_P900 -o raw"]:
        assert S(line) == line


def test_a_printer_queue_with_the_account_name_is_hashed(ident):
    out = S("CUPS print: lp -d Bastis_Epson_ET8550 -o raw /tmp/x.ps")
    assert "Bastis" not in out and "<printer:" in out
    assert "EPSON_SC_P900" in S("lp -d EPSON_SC_P900")
    lp.note_printer_names(["Canon_PRO-300"])  # no account name: never replaced
    assert "Canon_PRO-300" in S("lp -d Canon_PRO-300")


def test_the_filter_never_raises_and_never_drops(ident, monkeypatch):
    def boom(_t):
        raise RuntimeError("x")
    monkeypatch.setattr(lp, "scrub", boom)
    out = lp.safe_scrub("/Users/basti/x line")
    assert out.startswith("[scrub failed]") and "line" in out


def test_the_formatter_scrubs_message_args_and_traceback(ident):
    fmt = lp.ScrubbingFormatter("%(message)s")
    try:
        raise ValueError("/Users/basti/secret")
    except ValueError:
        import sys
        rec = logging.LogRecord("x", logging.ERROR, __file__, 1, "path %s", ("/Users/basti/a",),
                                sys.exc_info())
    out = fmt.format(rec)
    assert "/Users/basti" not in out and "~/a" in out and "~/secret" in out
    bad = logging.LogRecord("x", logging.INFO, __file__, 1, "two %s %s", ("one",), None)
    assert fmt.format(bad)  # a bad %-format still writes a line


def test_the_app_log_handler_uses_the_filter():
    src = open(lp.__file__.replace("log_privacy.py", "logger.py"), encoding="utf-8").read()
    assert "ScrubbingFormatter" in src


def test_cost_per_line_is_small(ident):
    import time
    line = ("2026-11-20 10:00:00 [INFO] workflow.measure_manager: Run: /Users/basti/x/bin/chartread "
            "-v -c 1 /Users/basti/ChromIQ/T/runs/run1/T [cwd=/Users/basti/ChromIQ/T/runs/run1]")
    t = time.perf_counter()
    for _ in range(2000):
        lp.scrub(line)
    per = (time.perf_counter() - t) / 2000
    assert per < 0.002, per


def test_a_short_computer_name_that_is_a_word_survives(monkeypatch):
    import socket
    monkeypatch.setattr(socket, "gethostname", lambda: "Mac.fritz.box")
    lp.reset_for_tests()
    try:
        assert S("a Mac at Mac.fritz.box") == "a Mac at <computer>"
    finally:
        monkeypatch.undo()
        lp.reset_for_tests()


def test_the_real_identity_of_this_machine_is_scrubbed():
    import getpass
    import os
    lp.reset_for_tests()
    home = os.path.expanduser("~")
    out = S(f"Settings loaded from {home}/Library/Preferences/x.plist")
    assert home not in out and out.endswith("~/Library/Preferences/x.plist")
    user = getpass.getuser()
    if len(user) >= 3:
        assert user not in S(f"by {user} today").split()


# --- M1 (review of 20 Nov): serials by what they are, and the CR30 call site ---

@pytest.mark.parametrize("line,raw", [
    # the CR30's connect line as 4.3.50's first branch wrote it (USB and BLE)
    ("CR30 connected over USB: model CR30, serial 12345678, internal id AB12CD34, "
     "software V11.3.0.0.20231219, hardware V10.0.0.0", ["12345678", "AB12CD34"]),
    ("CR30 connected over Bluetooth: model CR30, serial CM454M0223, internal id "
     "PT694D01E7, software V11.3.0.0.20231219", ["CM454M0223", "PT694D01E7"]),
    # ArgyllCMS's white-reference prompt (instappsup.c) and other S/N shapes
    ("Place the instrument on its reflective white reference S/N 1234567,", ["1234567"]),
    ("SN: 7654321 found", ["7654321"]),
    ("i1pro3_getchipid: returning 01-23456789ABCDEF", ["23456789ABCDEF"]),
    ("USB serial string: XR1234567", ["XR1234567"]),
    ("<cc:MeasurementDeviceSerialNumber>1234567</cc:MeasurementDeviceSerialNumber>",
     ["1234567"]),
    ('<Device SerialNumber="A1234B"/>', ["A1234B"]),
    # specbos prints two digits too (the module text promised it)
    (" Spectrometer serial number: 12", [" 12"]),
    # the CR30 names itself by its id string
    ("CR30 BLE: the connected unit calls itself CM454M0223", ["CM454M0223"]),
    ("CR30: magnet guard armed with the learned tile signature of unit CM454M0223",
     ["CM454M0223"]),
])
def test_serials_are_caught_by_what_they_are(ident, line, raw):
    out = S(line)
    for r in raw:
        assert r not in out, out
    assert "<sn:" in out
    assert S(out) == out  # a tag is never tagged again


def test_words_near_serial_shapes_survive(ident):
    for line in ["serial port 2 skipped", "serial 2 ports", "units mm", "unit A",
                 "SNR 12.3", "the sn of it", "Serial number", "chip select",
                 "internal error 5"]:
        assert S(line) == line, line


def test_the_cr30_connect_line_never_formats_the_raw_serial(caplog):
    from workflow.cr30 import device_info as D
    info = D.DeviceInfo(transport="usb", model="CR30", serial="12345678",
                        internal_id="AB12CD34", software=D.TESTED_SOFTWARE)
    assert "12345678" in info.summary()          # the report keeps it
    assert "12345678" not in info.summary(for_log=True)
    assert "AB12CD34" not in info.summary(for_log=True)
    with caplog.at_level(logging.INFO):
        D.log_connect(info)
    said = " ".join(r.getMessage() for r in caplog.records)
    assert "12345678" not in said and "AB12CD34" not in said and "<sn:" in said


def test_settings_that_name_a_device_are_written_without_their_value(caplog):
    from core.settings import UNLOGGED_VALUE_KEYS, AppSettings
    s = AppSettings()
    with caplog.at_level(logging.DEBUG, logger="core.settings"):
        for key in UNLOGGED_VALUE_KEYS - {"log_privacy_salt"}:
            s.set(key, '{"serial": "CM454M0223", "address": "AA:BB:CC:11:22:33"}')
    said = " ".join(r.getMessage() for r in caplog.records)
    assert "CM454M0223" not in said and "AA:BB" not in said
    assert "cr30_last_device_info" in said


# --- M2 (review of 20 Nov): names built from the owner's first name or account name ---

@pytest.mark.parametrize("line,expect", [
    ("Sebastians AirPods", "<user>s AirPods"),
    ("Sebastian's iPhone", "<user>'s iPhone"),
    ("Sebastian\u2019s iPhone", "<user>\u2019s iPhone"),
    ("/dev/cu.Sebastian-iPhone", "/dev/cu.<user>-iPhone"),
    ("'bastis AirPods Pro'", "'<user>s AirPods Pro'"),
    ("/dev/cu.bastis-AirPods", "/dev/cu.<user>s-AirPods"),
    ("Printer bastis_Epson_ET8550", "Printer <user>s_Epson_ET8550"),
    ("basti_test project", "<user>_test project"),
    ("by Muster", "by <user>"),
])
def test_possessive_and_joined_forms_are_scrubbed(ident, line, expect):
    assert S(line) == expect


def test_the_paired_ports_line_counts_and_never_names(caplog, monkeypatch):
    from core import argyll_env as E
    monkeypatch.setattr(E, "_LOGGED", set())
    monkeypatch.setattr(E, "argyll_serial_exclusion_ports",
                        lambda: ["/dev/cu.Bastis-AirPods", "/dev/cu.Sebastians-iPhone"])
    with caplog.at_level(logging.DEBUG, logger=E.log.name):
        E.serial_exclusion_value("/dev/cu.mine", platform="darwin")
    said = " ".join(r.getMessage() for r in caplog.records)
    assert "AirPods" not in said and "iPhone" not in said and "Bastis" not in said
    assert "4 port(s) skipped" in said and "2 paired or Bluetooth port(s)" in said
    assert "/dev/cu.Bluetooth-Incoming-Port" in said  # the fixed one is named
    assert "1 from the user's own" in said


# --- S5: the short hash is keyed with a random per-install salt ---

def test_the_salt_is_made_once_and_kept(caplog):
    from core import settings as cs
    with caplog.at_level(logging.DEBUG):
        v1 = cs.log_privacy_salt()
        v2 = cs.log_privacy_salt()
    assert v1 == v2 and len(v1) >= 16
    assert v1 not in " ".join(r.getMessage() for r in caplog.records)
    assert cs.LOG_PRIVACY_SALT_KEY in cs.UNLOGGED_VALUE_KEYS


def test_the_serial_hash_is_keyed_with_the_salt_not_the_account(monkeypatch):
    from core import settings as cs
    monkeypatch.setattr(cs, "log_privacy_salt", lambda: "a" * 32)
    lp.reset_for_tests(homes=["/Users/basti"], names=["basti"])
    a = lp.device_tag("1234567")
    # the same install: the same code, whoever the account is (no longer the key)
    lp.reset_for_tests(homes=["/Users/other"], names=["other"])
    assert lp.device_tag("1234567") == a
    # knowing the account and host names is no help: the key is not made from them
    import hashlib
    import hmac
    guess = hmac.new("/Users/basti\x00basti\x00chromiq-log".encode(), b"1234567",
                     hashlib.sha256).hexdigest()[:8]
    assert guess not in a
    # another install (another salt): another code
    monkeypatch.setattr(cs, "log_privacy_salt", lambda: "b" * 32)
    lp.reset_for_tests(homes=["/Users/basti"], names=["basti"])
    assert lp.device_tag("1234567") != a
    lp.reset_for_tests()


def test_the_table_reach_salt_never_reaches_the_log(caplog):
    """S10 (found on screen): settings.set logged the reach record with %r,
    salt and table keys in it; reach.py promises the salt never leaves the
    settings file."""
    from core.settings import AppSettings
    rec = '{"salt": "b39d28f5aa11", "tables": {"f0874b8c203e1383": {"v": 2}}}'
    with caplog.at_level(logging.DEBUG, logger="core.settings"):
        AppSettings().set("i1io_table_reach", rec)
    said = " ".join(r.getMessage() for r in caplog.records)
    assert "b39d28f5" not in said and "f0874b8c" not in said
    assert "i1io_table_reach" in said
