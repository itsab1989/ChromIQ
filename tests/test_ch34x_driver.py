"""#159 Windows: the CH34x driver helper, and the traps that are already measured.

Every test here corresponds to something that was **observed on the owner's
Windows 11 ARM64 machine**, not to something that might in principle go wrong.
The whole file runs with no network, no elevation, no hardware and no
`QApplication`, on macOS, Linux and Windows alike.

The traps, and the test that pins each one:

| trap | test |
|---|---|
| a driverless CH340 reports `Status OK` / `CM_PROB_NONE` | `test_a_driverless_bridge_is_still_reported` |
| a second, working CH340 hides a broken one | `test_two_bridges_are_judged_one_at_a_time`, `test_a_working_second_device_cannot_disguise_a_failure` |
| the registry keeps phantom instances | `test_presence_uses_the_cfgmgr32_present_filter` |
| `[Manufacturer] = NT,NTamd64,NTia64` (3.5.2019.1) | `test_bare_NT_is_refused_on_arm64` + `test_the_same_line_is_accepted_on_x64` |
| `WIN 9X/` declares NTARM64 and ships no `CH341M64.sys` | `test_a_declared_architecture_whose_binary_is_absent_is_refused` |
| three byte-identical INFs, one poisoned | `test_the_real_three_inf_layout_picks_a_complete_folder` |
| the INF is GBK, `read_text()` raises | `test_the_inf_is_read_as_bytes`, `test_read_text_would_have_raised` |
| the `.CAT` is not in the folder | `test_a_missing_catalogue_is_refused` |
| `platform.machine()` lies in an emulated process | `test_machine_arch_reads_the_machine_wide_registry_value` |
| `OSArchitecture` is localised | `test_a_localised_architecture_string_is_refused_not_guessed` |
| HTTP 200 with a JSON error body | `test_a_json_error_body_is_not_a_zip` |
| no `Content-Length` | `test_the_byte_cap_stops_an_endless_body`, `test_the_deadline_stops_a_dribbling_server` |
| zip-slip into a folder handed to an elevated process | `test_zip_slip_is_refused` and friends |
| `WIN 1X` contains a space | `test_a_path_with_a_space_is_quoted` |
| pnputil's output is German | `test_no_pnputil_output_is_ever_parsed` |
| pnputil 3010 / 1223 / 5 / 259 collapsed into one sentence | `test_every_exit_code_gets_its_own_answer` |
| `WaitForSingleObject`'s result discarded (`STILL_ACTIVE` read as failure) | `test_the_wait_result_is_not_discarded` |
| "Roll Back Driver" is greyed out for a device that never had one | `test_the_failure_message_does_not_send_the_user_to_roll_back_driver` |
"""
from __future__ import annotations

import ast
import inspect
import io
import struct
import sys
import types
import zipfile
from pathlib import Path

import pytest

import core.ch34x_driver as ch
import core.usb_driver_installer as inst


def executable_source(module) -> str:
    """The module's source with every docstring and comment removed.

    The forbidden-token tests below have to look at what the code DOES, not at
    the prose explaining why it does not do the other thing: this module's
    docstrings name `Get-AuthenticodeSignature`, `platform.machine()`,
    `OSArchitecture` and `stdout` precisely in order to say that none of them is
    used. `ast.unparse` drops comments, and the docstrings are stripped here.
    """
    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            if ast.get_docstring(node, clean=False) is not None:
                node.body = node.body[1:]
    return ast.unparse(tree)


def test_the_docstring_stripper_actually_strips():
    """Guarding the guard: if this stopped working every forbidden-token test
    below would pass for free."""
    code = executable_source(ch)
    assert "Get-AuthenticodeSignature" in inspect.getsource(ch)
    assert "Get-AuthenticodeSignature" not in code
    assert "def inspect_package" in code


# ---------------------------------------------------------------------------
# The contract the UI half is coding against
# ---------------------------------------------------------------------------
def test_the_interface_is_exactly_what_was_agreed():
    """Renaming or re-shaping any of this breaks the other half of the feature."""
    for name in ("CH34X_IDS", "Status", "DeviceState", "devices", "machine_arch",
                 "PackageVerdict", "inspect_package", "download_package",
                 "install", "verify_bound",
                 "Outcome", "Reason", "DriverResult", "describe_exit_code"):
        assert hasattr(ch, name), f"the agreed interface is missing {name}"

    assert {s.name for s in ch.Status} == {"NO_DEVICE", "WORKING", "NO_DRIVER"}
    assert {o.name for o in ch.Outcome} == {
        "OK", "REBOOT_REQUIRED", "USER_CANCELLED", "ACCESS_DENIED", "NO_OP",
        "FAILED"}
    assert [f for f in ch.DriverResult.__dataclass_fields__] == [
        "outcome", "reason", "code", "path", "name", "count", "detail"]
    assert [f for f in ch.DeviceState.__dataclass_fields__] == [
        "instance_id", "vid", "pid", "port", "status"]
    assert [f for f in ch.PackageVerdict.__dataclass_fields__] == [
        "ok", "inf_path", "reason", "arch_section", "service_binary"]


def test_this_module_composes_no_user_facing_prose():
    """**THE FAULT THIS WHOLE INTERFACE EXISTS TO PREVENT.**

    Every entry point used to return `(bool, str)` where the `str` was an
    English paragraph the dialog printed verbatim. Three things came out of
    that, all of them visible to a user: a window that contradicted itself on
    exit 3010, English paragraphs inside the German window, and the dialog
    telling "cancelled" from "failed" by string-matching this module's prose.

    A sentence here is a sentence that cannot be translated: this module has no
    `tr()` and is not in any catalogue. So the results carry an `Outcome`, a
    `Reason` and values — and nothing else.
    """
    import dataclasses
    for entry in (ch.describe_exit_code(0), ch.describe_exit_code(3010),
                  ch.describe_exit_code(5), ch.describe_exit_code(99)):
        assert isinstance(entry, ch.DriverResult)
        for field in dataclasses.fields(entry):
            value = getattr(entry, field.name)
            if isinstance(value, str):
                assert " " not in value, (
                    f"{field.name} carries prose: {value!r}")


def test_measurement_in_progress_is_not_ours_to_provide():
    """The contract gives that one to the UI half; two of them would disagree."""
    assert not hasattr(ch, "measurement_in_progress")


# ---------------------------------------------------------------------------
# One ID list, not two
# ---------------------------------------------------------------------------
def test_the_match_list_and_the_winusb_exclusion_are_literally_one_list():
    """They cannot drift, because there is only one of them.

    If they could, the direction of the drift is a serial instrument handed to
    WinUSB, which does not install a driver — it removes a COM port.
    """
    assert ch.CH34X_IDS == frozenset(inst.VENDOR_SERIAL_DEVICES)
    for vid, pid in ch.CH34X_IDS:
        assert inst.is_vendor_serial(vid, pid)


def test_the_whole_ch34x_family_is_covered_not_just_the_cr30s_chip():
    """Read from WCH's own [ControlFlags]. Four of these used to be missing."""
    for pair in [("1a86", "7523"), ("1a86", "5523"), ("1a86", "7522"),
                 ("1a86", "e523"), ("4348", "5523")]:
        assert pair in ch.CH34X_IDS, f"{pair} is a CH34x bridge and is not listed"


def test_the_ids_are_lower_case_hex():
    for vid, pid in ch.CH34X_IDS:
        assert vid == vid.lower() and pid == pid.lower()
        assert len(vid) == 4 and len(pid) == 4
        int(vid, 16), int(pid, 16)


def test_cr30_discovery_was_not_widened():
    """Contract decision 7: `workflow/cr30/discovery.py` IS NOT TOUCHED.

    Widening it changes what ChromIQ tries to *open as a CR30* on every
    platform, which is a CR30 behaviour change riding in a Windows driver
    change. The six IDs apply to driver-help matching and the WinUSB exclusion
    only.
    """
    from workflow.cr30 import discovery
    assert discovery.CH34X_VID == 0x1A86
    assert discovery.CH34X_PID == 0x7523


# ---------------------------------------------------------------------------
# Presence and per-instance state
# ---------------------------------------------------------------------------
def _fake_devices(monkeypatch, table: dict[str, str | None]):
    monkeypatch.setattr(ch, "_present_usb_instance_ids", lambda: list(table))
    monkeypatch.setattr(ch, "_port_for_instance", lambda i: table[i])


CR30 = r"USB\VID_1A86&PID_7523\7&3b74c78&0&1"
OTHER = r"USB\VID_1A86&PID_7523\7&aaaaaaa&0&2"
CH341 = r"USB\VID_4348&PID_5523\6&bbbbbbb&0&1"
MOUSE = r"USB\VID_046D&PID_C077\6&ccccccc&0&1"


def test_a_driverless_bridge_is_still_reported(monkeypatch):
    """THE trap. On this machine a CH340 with no driver, no class and no service
    reported `Status: OK` and `CM_PROB_NONE`, so a gate keyed on a problem code
    stays silent for the only user this feature exists for.
    """
    _fake_devices(monkeypatch, {CR30: None})
    got = ch.devices()
    assert len(got) == 1
    assert got[0].status is ch.Status.NO_DRIVER
    assert got[0].port is None
    assert got[0].vid == "1a86" and got[0].pid == "7523"


def test_a_bound_bridge_is_reported_as_working(monkeypatch):
    _fake_devices(monkeypatch, {CR30: "COM5"})
    assert ch.devices()[0].status is ch.Status.WORKING
    assert ch.devices()[0].port == "COM5"


def test_two_bridges_are_judged_one_at_a_time(monkeypatch):
    """An Arduino on COM3 and a driverless CR30. `len(candidates()) > 0` would
    say "it already works" and offer nothing while the instrument stays dark.
    """
    _fake_devices(monkeypatch, {OTHER: "COM3", CR30: None})
    by_id = {d.instance_id: d for d in ch.devices()}
    assert by_id[OTHER].status is ch.Status.WORKING
    assert by_id[CR30].status is ch.Status.NO_DRIVER


def test_devices_that_are_not_ch34x_are_ignored(monkeypatch):
    _fake_devices(monkeypatch, {MOUSE: None, CH341: "COM9"})
    got = ch.devices()
    assert [d.instance_id for d in got] == [CH341]


def test_presence_uses_the_cfgmgr32_present_filter():
    """A plain registry walk returns phantoms. On this machine
    `…\\Enum\\USB\\VID_1A86&PID_7523` holds a ghost still carrying `COM3`;
    cfgmgr32 with the PRESENT filter returns only the live instance.
    """
    src = inspect.getsource(ch._present_usb_instance_ids)
    assert "CM_GETIDLIST_FILTER_PRESENT = 0x00000100" in src, (
        "the constant's VALUE is the guard; a zero here silently returns "
        "phantoms alongside the live device")
    assert "CM_GETIDLIST_FILTER_ENUMERATOR = 0x00000001" in src
    assert "CM_GETIDLIST_FILTER_ENUMERATOR | CM_GETIDLIST_FILTER_PRESENT" in src
    assert "CM_Get_Device_ID_ListW" in src


def test_no_problem_code_is_ever_consulted():
    """`pnputil /enum-devices /problem 28` returns WORKING devices here."""
    code = executable_source(ch)
    for forbidden in ("CM_PROB", "ProblemCode", "/problem",
                      "CM_Get_DevNode_Status"):
        assert forbidden not in code, (
            f"{forbidden} is used; presence must not depend on a problem code")


@pytest.mark.parametrize("hwid,expect", [
    (r"USB\VID_1A86&PID_7523\7&x", ("1a86", "7523")),
    (r"USB\VID_4348&PID_5523&REV_0250", ("4348", "5523")),
    (r"USB\VID_1a86&PID_e523", ("1a86", "e523")),
    (r"USB", None),
    (r"USB\NOTHING", None),
])
def test_hardware_ids_parse_including_the_rev_qualified_one(hwid, expect):
    """The sixth "ID" in WCH's [ControlFlags] is the fifth with a REV suffix."""
    assert ch._vid_pid_from_instance_id(hwid) == expect


# ---------------------------------------------------------------------------
# Machine architecture
# ---------------------------------------------------------------------------
class _FakeKey:
    def __init__(self, values):
        self.values = values

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake_winreg(monkeypatch, value, opened: list):
    module = types.SimpleNamespace(
        HKEY_LOCAL_MACHINE=object(),
        OpenKey=lambda root, path: (opened.append(path), _FakeKey(value))[1],
        QueryValueEx=lambda key, name: (key.values[name], 1),
    )
    monkeypatch.setitem(sys.modules, "winreg", module)
    monkeypatch.setattr(sys, "platform", "win32")


@pytest.mark.parametrize("raw,expect", [
    ("ARM64", "ARM64"), ("AMD64", "AMD64"), ("x86", "X86"),
    ("EM64T", "AMD64"), ("  arm64  ", "ARM64"),
])
def test_machine_arch_reads_the_machine_wide_registry_value(monkeypatch, raw, expect):
    """NOT `platform.machine()`: ChromIQ ships an x64 build too, and running it
    under emulation on this ARM64 machine reports `AMD64` — so the gate would
    look for `NTamd64`, find it in 3.5.2019.1, and green-light the package that
    broke the machine.
    """
    opened: list[str] = []
    _fake_winreg(monkeypatch, {"PROCESSOR_ARCHITECTURE": raw}, opened)
    assert ch.machine_arch() == expect
    assert opened == [
        "SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment"], (
        "the PROCESS environment variable is wrong in an emulated process; the "
        "machine-wide registry value is the one that is right")


def test_a_localised_architecture_string_is_refused_not_guessed(monkeypatch):
    """`Win32_OperatingSystem.OSArchitecture` reads `64-Bit-ARM-Prozessor` on
    this German machine. Anything unrecognised must refuse, never assume x64.
    """
    _fake_winreg(monkeypatch, {"PROCESSOR_ARCHITECTURE": "64-Bit-ARM-Prozessor"}, [])
    assert ch.machine_arch() == ""


def test_the_module_never_calls_platform_machine_or_osarchitecture():
    code = executable_source(ch)
    assert "platform.machine" not in code
    assert "OSArchitecture" not in code
    assert "Win32_OperatingSystem" not in code
    assert "PROCESSOR_ARCHITECTURE" in code


# ---------------------------------------------------------------------------
# INF fixtures
# ---------------------------------------------------------------------------
_INF_TEMPLATE = """; CH341SER.INF -- shaped like WCH's real one
[Version]
Signature   = "$Chicago$"
Class       = Ports
ClassGuid   = {{4D36E978-E325-11CE-BFC1-08002BE10318}}
Provider    = %WinChipHead%
DriverVer   = 02/11/2026, 4.0.2026.02
CatalogFile = {catalog}
PnpLockDown = 1

[ControlFlags]
ExcludeFromSelect = USB\\VID_1A86&PID_7523

[Manufacturer]
%WinChipHead% = {manufacturer}

[WinChipHead.NT]
%d% = CH341SER_Install.NT, USB\\VID_1A86&PID_7523

[WinChipHead.NTamd64]
%d% = CH341SER_Inst.NTamd64, USB\\VID_1A86&PID_7523

[WinChipHead.NTia64]
%d% = CH341SER_Inst.NTia64, USB\\VID_1A86&PID_7523

[WinChipHead.NTARM64]
%d% = CH341SER_Inst.NTARM64, USB\\VID_1A86&PID_7523
%d% = CH341SER_Inst.NTARM64, USB\\VID_4348&PID_5523&REV_0250

[CH341SER_Install.NT]
CopyFiles = CH341SER.NT.CopyFiles.SYS

[CH341SER_Inst.NTamd64]
CopyFiles = CH341SER.NT.CopyFiles.SYSA64, CH341SER.CopyFiles.DLLA64

[CH341SER_Inst.NTia64]
CopyFiles = CH341SER.NT.CopyFiles.SYS

[CH341SER_Inst.NTARM64]
CopyFiles = CH341SER.NT.CopyFiles.SYSM64,\\
            CH341SER.CopyFiles.DLLA64

[CH341SER.NT.CopyFiles.SYS]
CH341SER.SYS, , , 2

[CH341SER.NT.CopyFiles.SYSA64]
CH341S64.SYS, , , 2

[CH341SER.NT.CopyFiles.SYSM64]
{sysm64}

[CH341SER.CopyFiles.DLLA64]
CH341PTA64.DLL, , , 2

[CH341SER_Install.NT.Services]
AddService = CH341SER, 2, CH341SER.Service

[CH341SER_Inst.NTamd64.Services]
AddService = CH341SER_A64, 2, CH341SER.ServiceA64

[CH341SER_Inst.NTia64.Services]
AddService = CH341SER, 2, CH341SER.Service

[CH341SER_Inst.NTARM64.Services]
AddService = CH341SER_M64, 2, CH341SER.ServiceM64

[CH341SER.Service]
ServiceBinary = %10%\\System32\\Drivers\\CH341SER.SYS

[CH341SER.ServiceA64]
ServiceBinary = %10%\\System32\\Drivers\\CH341S64.SYS

[CH341SER.ServiceM64]
ServiceBinary = %10%\\System32\\Drivers\\CH341M64.SYS

[Strings]
WinChipHead = "wch.cn"
d = "USB-SERIAL CH340"
"""


def make_package(
    folder: Path,
    *,
    manufacturer: str = "WinChipHead,NT,NTamd64,NTARM64",
    files: tuple[str, ...] = ("CH341M64.SYS", "CH341S64.SYS", "CH341SER.SYS",
                              "CH341PTA64.DLL"),
    catalog: str | None = "CH341SER.CAT",
    sysm64: str = "CH341M64.SYS, , , 2",
    inf_name: str = "CH341SER.INF",
    inf_prefix: bytes = b"",
) -> Path:
    """Write a folder shaped like a real WCH driver package."""
    folder.mkdir(parents=True, exist_ok=True)
    text = _INF_TEMPLATE.format(
        manufacturer=manufacturer, catalog=catalog or "CH341SER.CAT",
        sysm64=sysm64)
    (folder / inf_name).write_bytes(inf_prefix + text.encode("ascii"))
    for name in files:
        (folder / name).write_bytes(b"\x4d\x5a" + name.encode() * 8)
    if catalog:
        (folder / catalog).write_bytes(b"\x30\x82" + b"catalogue")
    return folder / inf_name


@pytest.fixture
def arm64(monkeypatch):
    """This machine is ARM64 and every catalogue check passes.

    The catalogue check has its own tests; stubbing it here keeps every other
    test about the rule it is actually testing, and lets the whole file run on
    macOS and Linux.
    """
    monkeypatch.setattr(ch, "machine_arch", lambda: "ARM64")
    monkeypatch.setattr(ch, "verify_catalog", lambda cat, files: (True, "ok"))


# ---------------------------------------------------------------------------
# The architecture gate
# ---------------------------------------------------------------------------
def test_a_complete_arm64_package_is_accepted(tmp_path, arm64):
    make_package(tmp_path / "pkg")
    verdict = ch.inspect_package(tmp_path / "pkg")
    assert verdict.ok, verdict.reason
    assert verdict.arch_section == "CH341SER_Inst.NTARM64"
    assert verdict.service_binary == "CH341M64.SYS"
    assert verdict.inf_path == tmp_path / "pkg" / "CH341SER.INF"


def test_bare_NT_is_refused_on_arm64(tmp_path, arm64):
    """3.5.2019.1's [Manufacturer] is exactly this. It is WHQL-signed, it
    declares a section this gate could match, and it is the package that left
    the owner's instrument dark for five days.
    """
    make_package(tmp_path / "pkg", manufacturer="WinChipHead,NT,NTamd64,NTia64")
    verdict = ch.inspect_package(tmp_path / "pkg")
    assert not verdict.ok
    assert "NTARM64" in verdict.reason
    assert verdict.arch_section is None


def test_the_same_line_is_accepted_on_x64(tmp_path, monkeypatch):
    """The gate must reject bare NT, not reject 3.5 everywhere: on an x64
    machine `NTamd64` is present and genuinely correct.
    """
    monkeypatch.setattr(ch, "machine_arch", lambda: "AMD64")
    monkeypatch.setattr(ch, "verify_catalog", lambda cat, files: (True, "ok"))
    make_package(tmp_path / "pkg", manufacturer="WinChipHead,NT,NTamd64,NTia64")
    verdict = ch.inspect_package(tmp_path / "pkg")
    assert verdict.ok, verdict.reason
    assert verdict.arch_section == "CH341SER_Inst.NTamd64"
    assert verdict.service_binary == "CH341S64.SYS"


def test_an_NT_only_package_is_refused_everywhere(tmp_path, arm64):
    make_package(tmp_path / "pkg", manufacturer="WinChipHead,NT")
    assert not ch.inspect_package(tmp_path / "pkg").ok


def test_a_32_bit_machine_is_refused_rather_than_falling_back_to_NT(
        tmp_path, monkeypatch):
    monkeypatch.setattr(ch, "machine_arch", lambda: "X86")
    make_package(tmp_path / "pkg")
    verdict = ch.inspect_package(tmp_path / "pkg")
    assert not verdict.ok
    assert "32-bit" in verdict.reason


def test_an_unknown_architecture_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(ch, "machine_arch", lambda: "")
    make_package(tmp_path / "pkg")
    assert not ch.inspect_package(tmp_path / "pkg").ok


def test_a_driver_for_other_hardware_is_refused(tmp_path, arm64):
    inf = make_package(tmp_path / "pkg")
    raw = inf.read_bytes().replace(b"VID_1A86&PID_7523", b"VID_0403&PID_6001")
    raw = raw.replace(b"VID_4348&PID_5523&REV_0250", b"VID_0403&PID_6015")
    inf.write_bytes(raw)
    verdict = ch.inspect_package(tmp_path / "pkg")
    assert not verdict.ok
    assert "other hardware" in verdict.reason


# ---------------------------------------------------------------------------
# "The file it names must be here" — the rule that kills both traps
# ---------------------------------------------------------------------------
def test_a_declared_architecture_whose_binary_is_absent_is_refused(
        tmp_path, arm64):
    """`WIN 9X/` in today's genuine download declares NTARM64 thirteen times and
    contains no `CH341M64.sys`. Pointing pnputil at it reproduces the original
    bug with a current, correctly signed package.
    """
    make_package(tmp_path / "win9x",
                 files=("CH341SER.SYS", "CH341PTA64.DLL"), catalog=None)
    verdict = ch.inspect_package(tmp_path / "win9x")
    assert not verdict.ok
    assert "CH341M64.SYS" in verdict.reason
    assert "incomplete" in verdict.reason


def test_the_service_binary_must_be_present_even_when_copyfiles_is_silent(
        tmp_path, arm64):
    """A separate rule from the CopyFiles one, and it needs its own case.

    In WCH's real INF the ServiceBinary is also in CopyFiles, so the two rules
    overlap and the CopyFiles check masks this one. An INF whose install
    section copies only the DLL, while its .Services section still starts a
    driver binary that is not in the folder, stages successfully and never
    binds — the original bug exactly.
    """
    folder = tmp_path / "pkg"
    make_package(folder, files=("CH341PTA64.DLL",))
    inf = folder / "CH341SER.INF"
    inf.write_bytes(inf.read_bytes().replace(
        b"CH341M64.SYS, , , 2", b"; nothing is copied for ARM64"))
    verdict = ch.inspect_package(folder)
    assert not verdict.ok
    assert "CH341M64.SYS" in verdict.reason
    assert verdict.service_binary == "CH341M64.SYS"


def test_a_missing_copied_dll_is_refused(tmp_path, arm64):
    make_package(tmp_path / "pkg", files=("CH341M64.SYS",))
    verdict = ch.inspect_package(tmp_path / "pkg")
    assert not verdict.ok
    assert "CH341PTA64.DLL" in verdict.reason


def test_a_missing_catalogue_is_refused(tmp_path, arm64):
    """The 'lonely INF' case. `Get-AuthenticodeSignature` calls this folder
    Valid, because it resolves against the SYSTEM catalogue database.
    """
    make_package(tmp_path / "pkg", catalog=None)
    verdict = ch.inspect_package(tmp_path / "pkg")
    assert not verdict.ok
    assert "CH341SER.CAT" in verdict.reason


def test_the_copyfiles_source_name_wins_over_the_destination(tmp_path, arm64):
    """`dest, source, , flags` — taking field 0 asks for the wrong file."""
    make_package(tmp_path / "pkg",
                 sysm64="RENAMED.SYS, CH341M64.SYS, , 2",
                 files=("CH341M64.SYS", "CH341PTA64.DLL"))
    assert ch.inspect_package(tmp_path / "pkg").ok


def test_the_at_form_of_copyfiles_is_understood(tmp_path, arm64):
    inf = make_package(tmp_path / "pkg")
    raw = inf.read_bytes().replace(
        b"CopyFiles = CH341SER.NT.CopyFiles.SYSM64,\\\r\n",
        b"CopyFiles = @CH341M64.SYS,\\\r\n").replace(
        b"CopyFiles = CH341SER.NT.CopyFiles.SYSM64,\\\n",
        b"CopyFiles = @CH341M64.SYS,\\\n")
    inf.write_bytes(raw)
    assert ch.inspect_package(tmp_path / "pkg").ok


def test_a_folder_with_no_inf_is_refused(tmp_path, arm64):
    (tmp_path / "empty").mkdir()
    verdict = ch.inspect_package(tmp_path / "empty")
    assert not verdict.ok
    assert ".inf" in verdict.reason


def test_a_path_that_is_not_a_folder_is_refused(tmp_path, arm64):
    assert not ch.inspect_package(tmp_path / "nope").ok


# ---------------------------------------------------------------------------
# Which INF, out of three
# ---------------------------------------------------------------------------
def _real_layout(root: Path) -> None:
    """Today's archive: a complete root, a complete `WIN 1X`, a poisoned
    `WIN 9X` — and all three INFs byte-identical."""
    make_package(root)
    make_package(root / "WIN 1X")
    make_package(root / "WIN 9X",
                 files=("CH341SER.SYS", "CH341PTA64.DLL"), catalog=None)


def test_the_real_three_inf_layout_picks_a_complete_folder(tmp_path, arm64):
    _real_layout(tmp_path / "CH341SER")
    verdict = ch.inspect_package(tmp_path / "CH341SER")
    assert verdict.ok, verdict.reason
    assert "WIN 9X" not in str(verdict.inf_path), (
        "the WIN 9X copy declares NTARM64 and ships no ARM64 binary")


def test_the_choice_is_not_merely_the_first_inf_found(tmp_path, arm64):
    """Root incomplete, `WIN 1X` complete. A `glob`, an `rglob`, "first match"
    or any sort that reaches the root first lands on the wrong one.
    """
    root = tmp_path / "CH341SER"
    make_package(root, files=("CH341SER.SYS", "CH341PTA64.DLL"), catalog=None)
    make_package(root / "WIN 1X")
    verdict = ch.inspect_package(root)
    assert verdict.ok, verdict.reason
    assert verdict.inf_path.parent.name == "WIN 1X"


def test_a_tree_with_only_the_poisoned_folder_is_refused(tmp_path, arm64):
    root = tmp_path / "CH341SER"
    make_package(root / "WIN 9X",
                 files=("CH341SER.SYS", "CH341PTA64.DLL"), catalog=None)
    verdict = ch.inspect_package(root)
    assert not verdict.ok
    assert "CH341M64.SYS" in verdict.reason


def test_the_choice_is_deterministic(tmp_path, arm64):
    for _ in range(4):
        _real_layout(tmp_path / "CH341SER")
    first = ch.inspect_package(tmp_path / "CH341SER").inf_path
    for _ in range(3):
        assert ch.inspect_package(tmp_path / "CH341SER").inf_path == first


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------
#: GBK Chinese, plus 0x81 — which is undefined in cp1252 as well as invalid
#: UTF-8, so this fixture raises under BOTH the Windows gate's PYTHONUTF8=1 and
#: the German machine default.
_GBK = b"; \xb0\xb2\xd7\xb0DLL\xca\xc7\xbf\xc9\xd1\xa1\xb5\xc4 \x81\r\n"


def test_the_inf_is_read_as_bytes(tmp_path, arm64):
    make_package(tmp_path / "pkg", inf_prefix=_GBK)
    verdict = ch.inspect_package(tmp_path / "pkg")
    assert verdict.ok, verdict.reason


def test_read_text_would_have_raised(tmp_path):
    """Why `_read_inf_text` exists at all. `Path.read_text()` raises under
    `PYTHONUTF8=1`, which this repo's Windows gate sets, and under cp1252.
    """
    path = tmp_path / "CH341SER.INF"
    path.write_bytes(_GBK + b"[Version]\r\n")
    with pytest.raises(UnicodeDecodeError):
        path.read_text(encoding="utf-8")
    with pytest.raises(UnicodeDecodeError):
        path.read_text(encoding="cp1252")
    assert "[Version]" in ch._read_inf_text(path)


def test_an_absurdly_large_inf_is_refused(tmp_path, arm64):
    folder = tmp_path / "pkg"
    make_package(folder)
    (folder / "CH341SER.INF").write_bytes(b"x" * (ch._MAX_INF_BYTES + 1))
    assert not ch.inspect_package(folder).ok


def test_a_utf8_bom_does_not_confuse_the_parser(tmp_path, arm64):
    make_package(tmp_path / "pkg", inf_prefix=b"\xef\xbb\xbf")
    assert ch.inspect_package(tmp_path / "pkg").ok


# ---------------------------------------------------------------------------
# The catalogue check is reached, and its verdict is obeyed
# ---------------------------------------------------------------------------
def test_the_catalogue_in_the_folder_is_what_gets_verified(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(ch, "machine_arch", lambda: "ARM64")
    monkeypatch.setattr(ch, "verify_catalog",
                        lambda cat, files: (seen.update(cat=cat, files=files),
                                            (True, "ok"))[1])
    make_package(tmp_path / "pkg")
    assert ch.inspect_package(tmp_path / "pkg").ok
    assert seen["cat"] == tmp_path / "pkg" / "CH341SER.CAT"
    names = {p.name.upper() for p in seen["files"]}
    assert "CH341SER.INF" in names, "the INF itself must be covered"
    assert "CH341M64.SYS" in names, "the driver binary must be covered"
    assert "CH341PTA64.DLL" in names, "everything CopyFiles names is covered"


def test_a_failed_catalogue_check_refuses_the_package(tmp_path, monkeypatch):
    monkeypatch.setattr(ch, "machine_arch", lambda: "ARM64")
    monkeypatch.setattr(ch, "verify_catalog",
                        lambda cat, files: (False, "it has been altered"))
    make_package(tmp_path / "pkg")
    verdict = ch.inspect_package(tmp_path / "pkg")
    assert not verdict.ok
    assert "altered" in verdict.reason


def test_get_authenticode_signature_is_never_used():
    """It returns `Valid` for an INF alone in an empty folder, and it INVERTS on
    a machine that has never installed the driver — which is this feature's
    user.
    """
    code = executable_source(ch)
    assert "Get-AuthenticodeSignature" not in code
    assert "powershell" not in code.lower()
    assert "WinVerifyTrust" in code


def test_the_catalogue_check_names_the_driver_verify_policy():
    src = inspect.getsource(ch._win_verify_catalog)
    assert "0xF750E6C3" in src, "DRIVER_ACTION_VERIFY, not GENERIC_VERIFY_V2"
    assert "WTD_SAFER_FLAG" in src, (
        "the measured trap must stay documented: WTD_SAFER_FLAG turns a valid "
        "Microsoft-countersigned catalogue into TRUST_E_NOSIGNATURE here")
    assert "data.dwProvFlags = WTD_CACHE_ONLY_URL_RETRIEVAL" in src


def test_verify_catalog_refuses_off_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    ok, why = ch.verify_catalog(tmp_path / "x.cat", [])
    assert not ok and "Windows" in why


# ---------------------------------------------------------------------------
# The download gate — everything BEFORE verification
# ---------------------------------------------------------------------------
class _Reader:
    """A fake HTTP body. `chunks` may be an iterable or an endless generator."""

    def __init__(self, chunks):
        self._chunks = iter(chunks)
        self.closed = False
        self.reads = 0

    def read(self, _n):
        self.reads += 1
        return next(self._chunks, b"")

    def close(self):
        self.closed = True


_SPRING_ERROR = (b'{"code":500,"message":"org.springframework.web.bind.'
                 b'MissingServletRequestParameterException: Required request '
                 b'parameter \'id\' is not present"}')


def test_a_json_error_body_is_not_a_zip(tmp_path):
    """The endpoint answers a malformed request with HTTP 200, Content-Type
    application/json and a Java exception. "The request succeeded" proves
    nothing about what arrived.
    """
    got = ch.stream_to_file(_Reader([_SPRING_ERROR]), tmp_path / "a.part")
    assert not got.ok
    assert got.reason is ch.Reason.NOT_A_ZIP


def test_a_body_that_is_not_a_zip_is_abandoned_at_once(tmp_path):
    """The magic check must abort mid-transfer, not merely disbelieve the
    finished file: a WAF interstitial or a captive portal can stream for ever,
    and there is no `Content-Length` to warn us.
    """
    def endless_html():
        yield b"<!DOCTYPE html><html><body>Sign in"
        while True:
            yield b"x" * 65536

    reader = _Reader(endless_html())
    got = ch.stream_to_file(reader, tmp_path / "a.part")
    assert not got.ok and got.reason is ch.Reason.NOT_A_ZIP
    assert reader.reads == 1, (
        "the body was still being read after the first two bytes disproved it")
    assert (tmp_path / "a.part").stat().st_size == 0


def test_an_html_page_is_not_a_zip(tmp_path):
    got = ch.stream_to_file(
        _Reader([b"<!DOCTYPE html><html><body>Sign in"]), tmp_path / "a.part")
    assert not got.ok and got.reason is ch.Reason.NOT_A_ZIP


def test_an_empty_body_is_not_a_zip(tmp_path):
    got = ch.stream_to_file(_Reader([]), tmp_path / "a.part")
    assert not got.ok and got.reason is ch.Reason.EMPTY_RESPONSE


def test_the_byte_cap_stops_an_endless_body(tmp_path):
    """There is no `Content-Length` to pre-flight, so the only possible size
    limit is one that aborts mid-transfer.

    ⚠ THE FAKE CLOCK IS A SAFETY BELT, NOT DECORATION. Deleting the cap and
    running this test filled this machine's disk with a 17 GB `a.part` before
    the real 120-second deadline expired — the guard's absence is a genuine
    denial of service, which is the point, but a test must not be the thing
    that demonstrates it. With the clock, a missing cap trips the deadline
    after a megabyte or so and the test still goes red, on the wrong message.
    """
    clock = iter(range(0, 10_000))

    def endless():
        yield b"PK\x03\x04"
        while True:
            yield b"\0" * 65536

    got = ch.stream_to_file(_Reader(endless()), tmp_path / "a.part",
                            max_bytes=256 * 1024, deadline_s=20,
                            now=lambda: next(clock))
    assert not got.ok
    assert got.reason is ch.Reason.DOWNLOAD_TOO_BIG, (
        "the cap must stop it before the deadline does")
    assert (tmp_path / "a.part").stat().st_size <= 256 * 1024 + 65536


def test_the_deadline_stops_a_dribbling_server(tmp_path):
    """`timeout=10` on `urlopen` is a SOCKET timeout: a server sending one byte
    every nine seconds never trips it. The deadline is total elapsed time.
    """
    clock = iter(range(0, 10_000, 7))

    def endless():
        yield b"PK\x03\x04"
        while True:
            yield b"\0"

    got = ch.stream_to_file(_Reader(endless()), tmp_path / "a.part",
                            deadline_s=30, now=lambda: next(clock))
    assert not got.ok
    assert got.reason is ch.Reason.DOWNLOAD_TOO_SLOW


def test_a_real_looking_zip_streams_through(tmp_path):
    payload = _zip_bytes({"CH341SER/CH341SER.INF": b"[Version]"})
    got = ch.stream_to_file(_Reader([payload[:10], payload[10:]]),
                            tmp_path / "a.part")
    assert got.ok, got
    assert got.reason is ch.Reason.DOWNLOADED and got.count == len(payload)
    assert (tmp_path / "a.part").read_bytes() == payload


def test_progress_is_reported(tmp_path):
    seen: list[int] = []
    ch.stream_to_file(_Reader([b"PK\x03\x04", b"abcd"]), tmp_path / "a.part",
                      progress=seen.append)
    assert seen == [4, 8]


# ---------------------------------------------------------------------------
# Archive shape and zip-slip
# ---------------------------------------------------------------------------
def _zip_bytes(entries: dict[str, bytes], *, symlink: str | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        for name, data in entries.items():
            info = zipfile.ZipInfo(name)
            if name == symlink:
                info.external_attr = (0xA1FF << 16)
            archive.writestr(info, data)
    return buf.getvalue()


def _write_zip(tmp_path: Path, entries, **kw) -> Path:
    path = tmp_path / "pkg.zip"
    path.write_bytes(_zip_bytes(entries, **kw))
    return path


def test_a_good_archive_unpacks(tmp_path):
    src = _write_zip(tmp_path, {"CH341SER/CH341SER.INF": b"[Version]",
                                "CH341SER/WIN 1X/CH341SER.INF": b"[Version]"})
    got = ch.unpack_archive(src, tmp_path / "out")
    assert got.ok, got
    assert got.reason is ch.Reason.UNPACKED
    assert (tmp_path / "out" / "CH341SER" / "WIN 1X" / "CH341SER.INF").is_file()


@pytest.mark.parametrize("name", [
    "../evil.inf",
    "CH341SER/../../evil.inf",
    "/etc/evil.inf",
    "\\windows\\evil.inf",
    "C:\\windows\\evil.inf",
])
def test_zip_slip_is_refused(tmp_path, name):
    """This tree is about to be handed to an ELEVATED process, so a violation
    aborts the whole archive rather than being silently rewritten.
    """
    src = _write_zip(tmp_path, {name: b"x", "CH341SER/CH341SER.INF": b"y"})
    got = ch.unpack_archive(src, tmp_path / "out")
    assert not got.ok, f"{name} was accepted"
    assert got.reason in (ch.Reason.ARCHIVE_UNSAFE_PATH,
                          ch.Reason.ARCHIVE_ESCAPES)
    assert not (tmp_path / "out").exists() or not list(
        (tmp_path / "out").rglob("evil.inf"))


def test_a_symlink_entry_is_refused(tmp_path):
    src = _write_zip(tmp_path, {"CH341SER/link": b"/etc/passwd"},
                     symlink="CH341SER/link")
    got = ch.unpack_archive(src, tmp_path / "out")
    assert not got.ok
    assert got.reason is ch.Reason.ARCHIVE_SYMLINK
    assert got.name == "CH341SER/link", (
        "the offending entry has to reach the window that names it")


def test_too_many_entries_is_refused(tmp_path):
    src = _write_zip(tmp_path, {f"f{i}.txt": b"x"
                                for i in range(ch._MAX_ENTRIES + 5)})
    got = ch.unpack_archive(src, tmp_path / "out")
    assert not got.ok
    assert got.reason is ch.Reason.ARCHIVE_TOO_MANY_ENTRIES
    assert got.count == ch._MAX_ENTRIES + 5


def test_an_over_large_expansion_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(ch, "_MAX_UNPACKED_BYTES", 1024)
    src = _write_zip(tmp_path, {"big.bin": b"\0" * 4096})
    got = ch.unpack_archive(src, tmp_path / "out")
    assert not got.ok and got.reason is ch.Reason.ARCHIVE_TOO_BIG


def test_a_truncated_zip_is_refused(tmp_path):
    payload = _zip_bytes({"CH341SER/CH341SER.INF": b"[Version]" * 50})
    path = tmp_path / "pkg.zip"
    path.write_bytes(payload[: len(payload) // 2])
    got = ch.unpack_archive(path, tmp_path / "out")
    assert not got.ok and got.reason is ch.Reason.ARCHIVE_UNREADABLE


def test_a_corrupt_member_is_caught_by_testzip(tmp_path):
    """A truncated ZIP has valid magic; only `testzip()` sees a bad CRC."""
    payload = bytearray(_zip_bytes({"CH341SER/a.sys": b"AAAAAAAAAAAAAAAAAAAA"}))
    index = payload.index(b"AAAAAAAAAAAAAAAAAAAA")
    payload[index:index + 4] = b"BBBB"
    path = tmp_path / "pkg.zip"
    path.write_bytes(bytes(payload))
    got = ch.unpack_archive(path, tmp_path / "out")
    assert not got.ok and got.reason is ch.Reason.ARCHIVE_DAMAGED
    assert got.name == "CH341SER/a.sys"


def test_an_empty_archive_is_refused(tmp_path):
    src = _write_zip(tmp_path, {})
    got = ch.unpack_archive(src, tmp_path / "out")
    assert not got.ok and got.reason is ch.Reason.ARCHIVE_EMPTY


# ---------------------------------------------------------------------------
# download_package as a whole
# ---------------------------------------------------------------------------
def test_download_package_unpacks_and_leaves_the_folder(tmp_path, monkeypatch):
    payload = _zip_bytes({"CH341SER/CH341SER.INF": b"[Version]",
                          "CH341SER/CH341SER.CAT": b"cat"})
    monkeypatch.setattr(ch, "_open_url", lambda url: _Reader([payload]))
    got = ch.download_package(tmp_path / "dl")
    assert got.ok, got
    assert got.reason is ch.Reason.PACKAGE_READY
    assert (got.path / "CH341SER" / "CH341SER.INF").is_file()
    assert not (tmp_path / "dl" / "CH341SER.zip.part").exists()


def test_download_package_promises_only_what_it_checked(tmp_path, monkeypatch):
    """No `Content-Length`, no `ETag`, no `Last-Modified`, no checksum, no
    versioned URL. ChromIQ can say "we checked what arrived" and never "we know
    what we asked for".

    `PACKAGE_READY` is named for exactly that and is NOT `PACKAGE_VERIFIED`:
    the promise the window makes lives in `ui/dialogs/settings_dialog.py`,
    where it can be translated, and this result carries only the folder to
    point `inspect_package` at.
    """
    payload = _zip_bytes({"CH341SER/CH341SER.INF": b"[Version]"})
    monkeypatch.setattr(ch, "_open_url", lambda url: _Reader([payload]))
    got = ch.download_package(tmp_path / "dl")
    assert got.reason is ch.Reason.PACKAGE_READY
    assert got.path is not None and got.path.is_dir()


def test_a_failed_download_leaves_nothing_behind(tmp_path, monkeypatch):
    monkeypatch.setattr(ch, "_open_url", lambda url: _Reader([_SPRING_ERROR]))
    got = ch.download_package(tmp_path / "dl")
    assert not got.ok and got.path is None
    assert got.reason is ch.Reason.NOT_A_ZIP
    assert list((tmp_path / "dl").iterdir()) == []


def test_a_stale_extraction_is_removed_not_replaced(tmp_path, monkeypatch):
    """`os.replace` cannot replace a DIRECTORY on Windows — this project has
    been bitten by exactly that once already, in the demo-project cache.
    """
    stale = tmp_path / "dl" / "package"
    stale.mkdir(parents=True)
    (stale / "leftover.txt").write_text("old", encoding="utf-8")
    payload = _zip_bytes({"CH341SER/CH341SER.INF": b"[Version]"})
    monkeypatch.setattr(ch, "_open_url", lambda url: _Reader([payload]))
    got = ch.download_package(tmp_path / "dl")
    assert got.ok, got
    assert not (got.path / "leftover.txt").exists()


def test_a_tls_failure_says_why_and_offers_the_manual_route(tmp_path, monkeypatch):
    """certifi's bundle excludes a corporate MITM root, which lives in the
    Windows store — so this fails on exactly the networks where fetching it in a
    browser is also awkward. It must say so, not "network unreachable".
    """
    def boom(url):
        raise OSError("CERTIFICATE_VERIFY_FAILED: unable to get local issuer")

    monkeypatch.setattr(ch, "_open_url", boom)
    got = ch.download_package(tmp_path / "dl")
    assert not got.ok
    assert got.reason is ch.Reason.TLS_UNTRUSTED, (
        "a MITM proxy must not be reported as an unreachable network")
    assert "CERTIFICATE_VERIFY_FAILED" in got.detail


def test_a_network_failure_is_told_apart_from_an_inspected_connection(
        tmp_path, monkeypatch):
    """Both offer the do-it-yourself route; only one of them is worth telling
    the user their network is the reason."""
    def boom(url):
        raise OSError("getaddrinfo failed")

    monkeypatch.setattr(ch, "_open_url", boom)
    got = ch.download_package(tmp_path / "dl")
    assert not got.ok
    assert got.reason is ch.Reason.UNREACHABLE
    assert "getaddrinfo" in got.detail


def test_the_updater_fetch_helper_is_not_reused():
    """`_fetch` reads an unbounded body into memory and `json.loads` it. Its
    TLS context and User-Agent are what is worth sharing.
    """
    assert "_fetch" not in executable_source(ch)
    assert ch._USER_AGENT == "ChromIQ-update-check"
    assert "certifi" in inspect.getsource(ch._tls_context)


# ---------------------------------------------------------------------------
# pnputil: exit codes only
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("code,outcome,reason", [
    (0, "OK", "DRIVER_ACCEPTED"),
    (3010, "REBOOT_REQUIRED", "REBOOT_TO_FINISH"),
    (1223, "USER_CANCELLED", "CANCELLED_AT_PROMPT"),
    (5, "ACCESS_DENIED", "NO_PERMISSION"),
    (2, "FAILED", "PACKAGE_UNREADABLE"),
    (87, "FAILED", "PACKAGE_INVALID"),
    (259, "NO_OP", "NOTHING_TO_APPLY"),
    (12345, "FAILED", "UNKNOWN_EXIT"),
])
def test_every_exit_code_gets_its_own_answer(code, outcome, reason):
    """Five states used to collapse into "failed or was cancelled", and then
    into a `(bool, str)` where 3010's `True` sent the flow off to look for a COM
    port that could not be there yet."""
    got = ch.describe_exit_code(code)
    assert got.outcome is getattr(ch.Outcome, outcome)
    assert got.reason is getattr(ch.Reason, reason)
    assert got.code == code


def test_the_exit_code_answers_are_all_different():
    reasons = [ch.describe_exit_code(c).reason
               for c in (0, 3010, 1223, 5, 2, 87, 259)]
    assert len(set(reasons)) == len(reasons)


def test_only_exit_zero_is_a_plain_success():
    """`bool(result)` is `Outcome.OK` and nothing else. 3010 being truthy is
    what put the restart sentence under "there is still no COM port"."""
    assert bool(ch.describe_exit_code(0))
    for code in (3010, 1223, 5, 2, 87, 259, 12345):
        assert not ch.describe_exit_code(code), code


def test_no_pnputil_output_is_ever_parsed():
    """It is German on the owner's machine and 10.0.26200 has no
    `/format json`; the published `oem` name is not stable either — it moved
    from oem10 to oem9 during one experiment.
    """
    code = executable_source(ch)
    for forbidden in ("stdout", "communicate", "check_output", "subprocess",
                      "/format", "Veröffentlichter"):
        assert forbidden not in code, (
            f"{forbidden} appears; pnputil output must not be read")


def test_nothing_ever_removes_a_driver():
    code = executable_source(ch)
    for forbidden in ("delete-driver", "/uninstall", "remove-device",
                      "/force", "DIF_REMOVE"):
        assert forbidden not in code, (
            f"{forbidden} appears; ChromIQ only ever adds")
    assert "/add-driver" in code


# ---------------------------------------------------------------------------
# install()
# ---------------------------------------------------------------------------
@pytest.fixture
def windows_install(monkeypatch, tmp_path):
    """Everything install() needs, with the elevation itself captured."""
    calls: list[tuple[Path, str]] = []
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(ch, "_pnputil_path", lambda: Path(r"C:\Windows\System32\pnputil.exe"))
    monkeypatch.setattr(
        ch, "_run_elevated",
        lambda tool, params, **kw: (
            calls.append((tool, params)),
            ch.DriverResult(ch.Outcome.OK, ch.Reason.DRIVER_ACCEPTED, code=0),
        )[1])
    return calls


def test_a_path_with_a_space_is_quoted(tmp_path, monkeypatch, windows_install):
    """WCH's working folder is called `WIN 1X`. This exact bug — an unquoted
    path with a space — left the owner's instrument driverless once, and the
    pattern install() is modelled on interpolates its arguments unquoted.
    """
    inf = make_package(tmp_path / "CH341SER" / "WIN 1X")
    monkeypatch.setattr(ch, "inspect_package",
                        lambda folder: ch.PackageVerdict(
                            True, inf, "fine", "CH341SER_Inst.NTARM64",
                            "CH341M64.SYS"))
    got = ch.install(inf)
    assert got.ok, got
    (_tool, params), = windows_install
    assert params == f'/add-driver "{inf}" /install'
    assert "WIN 1X" in params
    assert f'"{inf}"' in params, "the path must be quoted as ONE argument"


def test_the_package_is_re_verified_immediately_before_elevating(
        tmp_path, monkeypatch, windows_install):
    """The staging folder is user-writable; the gap between "we checked it" and
    "an administrator reads it" is the whole TOCTOU window.
    """
    inf = make_package(tmp_path / "pkg")
    monkeypatch.setattr(ch, "inspect_package",
                        lambda folder: ch.PackageVerdict(
                            False, inf, "it changed under us", None, None))
    got = ch.install(inf)
    assert not got.ok
    assert got.reason is ch.Reason.PACKAGE_REJECTED
    assert "it changed under us" in got.detail, (
        "the verdict's own words have to reach the window that quotes them")
    assert windows_install == [], "nothing may be elevated after a failed re-check"


def test_installing_an_inf_the_check_did_not_approve_is_refused(
        tmp_path, monkeypatch, windows_install):
    """The folder may contain three INFs and only one of them is usable."""
    good = make_package(tmp_path / "pkg" / "WIN 1X")
    bad = make_package(tmp_path / "pkg" / "WIN 9X",
                       files=("CH341SER.SYS",), catalog=None)
    monkeypatch.setattr(ch, "inspect_package",
                        lambda folder: ch.PackageVerdict(
                            True, good, "fine", "x", "y"))
    got = ch.install(bad)
    assert not got.ok
    assert got.reason is ch.Reason.INF_MISMATCH
    assert windows_install == []


def test_a_quotation_mark_in_the_path_is_refused(tmp_path, monkeypatch,
                                                 windows_install):
    """One `"` in a folder name would end the quoted argument early and hand
    pnputil something else entirely.
    """
    got = ch.install(tmp_path / 'we"ird' / "CH341SER.INF")
    assert not got.ok
    assert got.reason is ch.Reason.PATH_HAS_QUOTE
    assert windows_install == []


def test_a_vanished_inf_is_refused(tmp_path, monkeypatch, windows_install):
    got = ch.install(tmp_path / "gone" / "CH341SER.INF")
    assert not got.ok
    assert got.reason is ch.Reason.INF_MISSING
    assert windows_install == []


def test_install_refuses_off_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    got = ch.install(tmp_path / "x.inf")
    assert not got.ok and got.reason is ch.Reason.NOT_WINDOWS


def test_elevation_is_shellexecuteexw_not_powershell():
    src = inspect.getsource(ch._run_elevated)
    assert "ShellExecuteExW" in src
    assert 'sei.lpVerb = "runas"' in src
    assert "Start-Process" not in src


def test_the_wait_result_is_not_discarded():
    """The pattern this is modelled on throws away `WaitForSingleObject`'s
    return value, then reads `STILL_ACTIVE` (259) as an exit code — reporting
    failure and sending the user to Roll Back Driver while the install is
    mid-flight.
    """
    src = inspect.getsource(ch._run_elevated)
    assert "wait = kernel32.WaitForSingleObject" in src
    assert "WAIT_TIMEOUT" in src
    assert "wait != WAIT_OBJECT_0" in src


def test_the_three_elevation_refusals_are_three_different_outcomes():
    """`ConsentPromptBehaviorUser = 0` — a normal managed-desktop setting —
    means ShellExecuteExW fails with NO PROMPT AT ALL. "Failed or was
    cancelled" describes three different situations, and they used to be told
    apart by three different English sentences.
    """
    src = inspect.getsource(ch._run_elevated)
    assert "ERROR_CANCELLED" in src and "ERROR_ACCESS_DENIED" in src
    assert "Reason.CANCELLED_AT_PROMPT" in src
    assert "Reason.ELEVATION_REFUSED" in src
    assert "Reason.ELEVATION_FAILED" in src


# ---------------------------------------------------------------------------
# verify_bound — the only success test
# ---------------------------------------------------------------------------
def test_a_port_appearing_for_an_unbound_instance_is_success(monkeypatch):
    before = [ch.DeviceState(CR30, "1a86", "7523", None, ch.Status.NO_DRIVER)]
    _fake_devices(monkeypatch, {CR30: "COM5"})
    got = ch.verify_bound(before)
    assert got.ok
    assert got.reason is ch.Reason.PORT_APPEARED
    assert got.name == "COM5", "the window has to be able to name the port"


def test_a_port_that_was_already_there_is_not_success(monkeypatch):
    """`pnputil` can exit 0 having only STAGED a package while the device stays
    on the incumbent driver. The port was already there, so "a COM port exists"
    would report success for a no-op.
    """
    before = [ch.DeviceState(CR30, "1a86", "7523", "COM5", ch.Status.WORKING)]
    _fake_devices(monkeypatch, {CR30: "COM5"})
    got = ch.verify_bound(before)
    assert not got.ok
    assert got.reason is ch.Reason.NOTHING_TO_CHECK
    assert got.outcome is ch.Outcome.NO_OP, (
        "nothing to judge is not the same as a failed install")
    assert got.name == "COM5"


def test_a_working_second_device_cannot_disguise_a_failure(monkeypatch):
    """An Arduino on COM3 and a driverless CR30 — the case where the feature
    would otherwise be silent, confident and wrong.
    """
    before = [
        ch.DeviceState(OTHER, "1a86", "7523", "COM3", ch.Status.WORKING),
        ch.DeviceState(CR30, "1a86", "7523", None, ch.Status.NO_DRIVER),
    ]
    _fake_devices(monkeypatch, {OTHER: "COM3", CR30: None})
    got = ch.verify_bound(before)
    assert not got.ok
    assert got.reason is ch.Reason.STILL_NO_PORT


def test_it_still_fails_when_the_driver_installed_but_did_not_bind(monkeypatch):
    """The original bug: a driver can install and not bind."""
    before = [ch.DeviceState(CR30, "1a86", "7523", None, ch.Status.NO_DRIVER)]
    _fake_devices(monkeypatch, {CR30: None})
    got = ch.verify_bound(before)
    assert not got.ok
    assert got.outcome is ch.Outcome.FAILED
    assert got.reason is ch.Reason.STILL_NO_PORT


def test_unplugged_mid_flow_says_so_rather_than_claiming_failure(monkeypatch):
    before = [ch.DeviceState(CR30, "1a86", "7523", None, ch.Status.NO_DRIVER)]
    _fake_devices(monkeypatch, {})
    got = ch.verify_bound(before)
    assert not got.ok
    assert got.reason is ch.Reason.UNPLUGGED_MID_FLOW
    assert got.outcome is ch.Outcome.NO_OP, (
        "an adapter that left is not a driver that failed")


def test_nothing_attached_at_all(monkeypatch):
    _fake_devices(monkeypatch, {})
    got = ch.verify_bound([])
    assert not got.ok
    assert got.reason is ch.Reason.NOTHING_ATTACHED
    assert got.outcome is ch.Outcome.NO_OP


def test_the_failure_message_does_not_send_the_user_to_roll_back_driver():
    """Roll Back Driver is GREYED OUT for a device that never had a driver, and
    that device is this feature's entire user.
    """
    from ui.dialogs import settings_dialog as sd
    text, _ = sd.serial_outcome_text(stage="not_bound", folder="F")
    assert "Roll Back" in text, (
        "the dead end must be named, so nobody chases it")
    assert "will not help" in text


def test_no_message_ever_claims_a_cr30_is_attached():
    """`1a86:7523` is a generic bridge inside millions of unrelated products."""
    for line in inspect.getsource(ch).splitlines():
        if "CR30 is attached" in line or "CR30 is connected" in line:
            assert "NEVER" in line or "never" in line, line


# ---------------------------------------------------------------------------
# Off Windows
# ---------------------------------------------------------------------------
def test_every_entry_point_is_safe_off_windows(monkeypatch, tmp_path):
    """The module must import and behave on macOS and Linux; nothing may reach
    `ctypes.windll`.
    """
    monkeypatch.setattr(sys, "platform", "darwin")
    assert ch.devices() == []
    assert ch.machine_arch() == ""
    assert ch._port_for_instance(CR30) is None
    assert ch._present_usb_instance_ids() == []
    assert not ch.install(tmp_path / "x.inf").ok
    assert not ch.verify_catalog(tmp_path / "x.cat", [])[0]
    verdict = ch.inspect_package(tmp_path)
    assert not verdict.ok


def test_windows_only_calls_are_lazy():
    """A top-level `ctypes.windll` would break the import on every other OS."""
    src = inspect.getsource(ch)
    top_level = [line for line in src.splitlines()
                 if line.startswith(("import ", "from "))]
    assert not any("ctypes" in line for line in top_level)
    assert not any("winreg" in line for line in top_level)
    assert not any("certifi" in line for line in top_level)
