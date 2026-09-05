r"""The command line ChromIQ hands wdi-simple, checked against wdi-simple.

WHY THIS FILE EXISTS. `install_winusb()` built its arguments with
`--driver WinUSB`. There is no `--driver` option in libwdi and there never was.
wdi-simple answers an unrecognised long option by printing its usage and
exiting **zero**, and `install_winusb()` returns "exit 0 means success" — so the
app reported successful driver installs while doing nothing at all, for all 28
supported instruments, on every architecture, for as long as the feature had
existed. Proved on 2026-09-05 against a real driverless X-Rite i1Studio:
ChromIQ said the install succeeded and `setupapi.dev.log` recorded nothing, its
last entry being the deliberate driver *removal* 29 minutes earlier.

It survived because **nothing asserted on the command line**. Every existing
test either monkeypatched `install_winusb` whole (`test_usb_driver_dialog.py`)
or exercised the serial-instrument refusal, which returns before the arguments
are built (`test_winusb_never_reaches_a_serial_instrument.py`). The string was
the one part of the module no oracle could see.

WHY THIS IS NOT JUST A RESTATEMENT OF THE SOURCE. A test that reads `--type 1`
in `core/usb_driver_installer.py` and asserts `"--type 1" in args` pins a typo
exactly as firmly as it pins a fix — it would have blessed `--driver WinUSB`
without a murmur. So the oracle here is **wdi-simple's own usage text**, which
comes from libwdi and not from us:

* every option the code emits must appear in that usage text;
* every option the usage text marks as taking a `<value>` must be given one;
* the `--type` number is resolved through the mapping the usage text itself
  prints — `(0=WinUSB, 1=libusb-win32, 2=libusbK, 3=usbser, 4=custom)` — and
  must come out as `libusb-win32`. Renumber libwdi and this still reads right;
  change the 1 to a 0 and it goes red.

WHERE THE ORACLE COMES FROM, AND WHY NOTHING PASSES VACUOUSLY. `wdi_simple.exe`
is not in the source tree — Windows CI fetches it into `assets/`, and a built
app carries it in `_internal/assets/`. So the usage text is checked in at
`tests/golden/wdi_simple_usage.txt`, captured verbatim from the binary, and
**every option check runs from that snapshot on every host, Windows or not.
Nothing above skips.** Only two tests need the binary, and both are about the
snapshot rather than about the code:
`test_the_bundled_binary_still_speaks_the_language_we_recorded` re-runs
`--help` and fails if the live text and the snapshot have parted company, and
`test_argyll_binds_the_driver_ChromIQ_installs` reads Argyll's own `.inf`.
They skip with a reason that names what was not checked.

That split is deliberate. `test_winusb_never_reaches_a_serial_instrument.py`
carries a warning that one of its tests "passes for the wrong reason" on a host
without wdi-simple, because the function it calls bails out early there. Set
`CHROMIQ_WDI_SIMPLE=<path to wdi_simple.exe>` to point the freshness check at a
binary outside the tree.
"""
from __future__ import annotations

import inspect
import os
import re
import subprocess
import sys
from pathlib import Path, PureWindowsPath

import pytest

import core.usb_driver_installer as udi
from core.resource_path import resource_path


# The instrument the bug was proved against, so a failure message names real
# hardware rather than a placeholder.
I1STUDIO = udi.UsbDevice(vid="0765", pid="6008",
                         name="X-Rite i1 Studio", has_winusb=False)

USAGE_SNAPSHOT = Path(__file__).parent / "golden" / "wdi_simple_usage.txt"


# ---------------------------------------------------------------------------
# Reading wdi-simple's usage text
# ---------------------------------------------------------------------------

#: One option definition. The usage text puts them in the left column with at
#: most four leading spaces (`    --filter` and `    --stealth-cert` have no
#: short form); continuation lines are indented 27, so they cannot match.
_OPTION = re.compile(
    r"^ {0,4}(?:-(?P<short>[A-Za-z]), )?--(?P<long>[a-z][a-z0-9-]*)"
    r"(?P<eq>=)?(?P<takes>\s+<[^>]+>)?"
)

#: The driver-type numbering wdi-simple prints under `-t, --type`.
_TYPE_NUMBER = re.compile(r"(\d+)=([A-Za-z0-9_-]+)")


def parse_usage(text: str) -> "dict[str, bool]":
    """``{"--name": True, "--extract": False, …}`` — option → shows a <value>.

    False only means the usage text does not print a ``<value>`` next to it;
    `--timeout` really does take one and does not show it, so a False is never
    read as "this must NOT be given a value".
    """
    options: "dict[str, bool]" = {}
    for line in text.splitlines():
        if line.startswith("#"):
            continue        # the snapshot's provenance header
        m = _OPTION.match(line)
        if m:
            options["--" + m.group("long")] = bool(m.group("takes"))
    return options


def parse_driver_types(text: str) -> "dict[int, str]":
    """``{0: "WinUSB", 1: "libusb-win32", …}`` read out of the usage text."""
    for line in text.splitlines():
        if "=WinUSB" in line:
            return {int(n): name for n, name in _TYPE_NUMBER.findall(line)}
    return {}


def snapshot_text() -> str:
    return USAGE_SNAPSHOT.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Reading the command line the app builds
# ---------------------------------------------------------------------------

def tokenise(cmdline: str) -> "list[str]":
    """Split the way `CommandLineToArgvW` would, for the shapes we emit.

    `install_winusb()` passes ONE string to `ShellExecuteExW`, so the quoting
    is the app's own and has to be undone here rather than assumed away — the
    device names all contain spaces.
    """
    out: "list[str]" = []
    current = ""
    quoted = False
    started = False
    for ch in cmdline:
        if ch == '"':
            quoted = not quoted
            started = True
        elif ch.isspace() and not quoted:
            if started:
                out.append(current)
            current, started = "", False
        else:
            current += ch
            started = True
    if started:
        out.append(current)
    return out


def parse_args(cmdline: str) -> "dict[str, str | None]":
    """``{"--vid": "0x0765", …}``. A flag with no value maps to None."""
    tokens = tokenise(cmdline)
    parsed: "dict[str, str | None]" = {}
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("-"):
            nxt = tokens[i + 1] if i + 1 < len(tokens) else None
            if nxt is not None and not nxt.startswith("-"):
                parsed[token] = nxt
                i += 2
                continue
            parsed[token] = None
        i += 1
    return parsed


# ---------------------------------------------------------------------------
# The oracle has to be worth something before anything is measured against it
# ---------------------------------------------------------------------------

def test_the_usage_snapshot_is_a_usable_oracle() -> None:
    """Everything below is only as good as this file. If the snapshot ever
    parses to nothing — a header-only file, a changed layout, a regex that
    stopped matching — every option check underneath would pass by agreeing
    with an empty set. So the oracle is measured first: it must know a real
    handful of options, it must know the two this fix turns on, and it must
    REJECT something, or it is not answering a question."""
    options = parse_usage(snapshot_text())

    assert len(options) >= 10, (
        f"the usage snapshot parsed to only {len(options)} options "
        f"({sorted(options)}) — the oracle is broken, not the code")
    assert "--type" in options and "--dest" in options
    assert "--driver" not in options, (
        "the snapshot lists a `--driver` option; libwdi has none, so this file "
        "is not wdi-simple's usage text")
    assert "--chromiq-not-an-option" not in options, (
        "the parser accepts anything — it cannot fail, so it cannot guard")

    types = parse_driver_types(snapshot_text())
    assert types.get(0) == "WinUSB" and types.get(1) == "libusb-win32", (
        f"the driver-type numbering did not parse out of the snapshot: {types}")


# ---------------------------------------------------------------------------
# The guard the missing test would have been
# ---------------------------------------------------------------------------

def test_every_option_it_passes_is_one_wdi_simple_accepts() -> None:
    """THE ORIGINAL BUG, and the only test that would have caught it.

    `--driver WinUSB` is a well-formed-looking option that libwdi does not
    have. Nothing about its shape is wrong; the only thing wrong with it is
    that it is not in this list.
    """
    known = parse_usage(snapshot_text())
    emitted = parse_args(udi.wdi_simple_args(I1STUDIO))

    assert emitted, "wdi_simple_args() emitted no options at all"

    unknown = sorted(opt for opt in emitted if opt not in known)
    assert not unknown, (
        f"{unknown} passed to wdi-simple, which has no such option. It answers "
        f"an unrecognised long option by printing its usage and exiting 0, and "
        f"install_winusb() reads exit 0 as a successful driver install — so "
        f"this ships as a feature that silently does nothing. "
        f"wdi-simple accepts: {sorted(known)}")


def test_the_options_that_need_a_value_are_given_one() -> None:
    """`--type` with no number, or `--dest` with no path, is the same class of
    silent nothing: getopt would swallow the following option as the value."""
    known = parse_usage(snapshot_text())
    emitted = parse_args(udi.wdi_simple_args(I1STUDIO))

    starved = sorted(opt for opt, value in emitted.items()
                     if known.get(opt) and value is None)
    assert not starved, (
        f"{starved} take a <value> per wdi-simple's usage and were passed "
        f"without one")


def test_the_driver_type_it_asks_for_is_the_one_argyll_can_talk_to() -> None:
    r"""Not `"--type 1" in args` — that pins the number, and the number is not
    the point. The usage text prints its own numbering, so the assertion is
    made in libwdi's vocabulary: whatever number we send must NAME
    libusb-win32.

    It has to be libusb-win32, and WinUSB is not a milder alternative — it does
    not work at all. ArgyllCMS opens `\\.\libusb0-%04d`, a device object only
    libusb0.sys creates; that format string is the only device path in
    `spotread.exe` and the binary imports no `WinUsb_*` symbol. Argyll's
    changelog dates the switch to V1.5.0 (2013): "No longer using libusb for
    USB access, using native USB access instead. MSWin uses the libusb-win32
    kernel driver." A WinUSB binding would leave the instrument looking healthy
    in Device Manager and invisible to every Argyll tool.
    """
    types = parse_driver_types(snapshot_text())
    emitted = parse_args(udi.wdi_simple_args(I1STUDIO))

    assert "--type" in emitted, "no driver type is requested at all"
    asked = emitted["--type"]
    assert asked is not None and asked.isdigit(), (
        f"--type was given {asked!r}, which is not one of wdi-simple's "
        f"driver-type numbers")

    named = types.get(int(asked))
    assert named == "libusb-win32", (
        f"--type {asked} asks wdi-simple for {named!r}. ChromIQ must install "
        f"libusb-win32: Argyll reaches USB instruments through libusb0.sys and "
        f"nothing else, so any other binding leaves spotread printing "
        f"'** No ports found **'. wdi-simple's numbering: {types}")


def test_the_extraction_directory_is_absolute_and_ours() -> None:
    r"""`--dest` is not optional, though it looks it. wdi-simple's default is
    the RELATIVE path `usb_driver`, so without this the driver package lands
    wherever the elevated process was started from — which this code neither
    chooses nor can predict. On the bench it resolved to a stale x64-only tree
    another tool had left in the user's profile, and the install died two
    different ways (WDI_ERROR_ACCESS from a shell, WDI_ERROR_RESOURCE from the
    app) for that one reason.

    `PureWindowsPath`, not `Path`: the gate also runs on macOS, where
    `Path(r"C:\Windows").is_absolute()` is False and this test would fail for a
    reason that has nothing to do with the app.
    """
    emitted = parse_args(udi.wdi_simple_args(I1STUDIO))

    dest = emitted.get("--dest")
    assert dest, (
        "no --dest: wdi-simple then extracts to the relative path "
        "`usb_driver`, under whatever working directory the elevated process "
        "happens to inherit")
    assert PureWindowsPath(dest).is_absolute(), (
        f"--dest {dest!r} is relative, which is the same failure as omitting "
        f"it — the elevated process resolves it against its own cwd")
    assert PureWindowsPath(dest).name != "usb_driver", (
        "--dest names wdi-simple's own default directory; pick one that says "
        "who put it there")


def test_the_ids_carry_the_0x_prefix_wdi_simple_asks_for() -> None:
    """The usage says "use 0x prefix for hex" for both IDs. Drop it and 0765
    is read as decimal 765 — a device that does not exist, installed onto
    nothing, reported as a success."""
    usage = snapshot_text()
    assert "use 0x prefix for hex" in usage, (
        "wdi-simple no longer documents the 0x prefix; re-read its usage "
        "before trusting this test")

    emitted = parse_args(udi.wdi_simple_args(I1STUDIO))
    for option, expected in (("--vid", I1STUDIO.vid), ("--pid", I1STUDIO.pid)):
        value = emitted.get(option)
        assert value and value.startswith("0x"), (
            f"{option}={value!r} has no 0x prefix; wdi-simple reads it as "
            f"decimal and binds the driver to the wrong device")
        assert int(value, 16) == int(expected, 16), (
            f"{option}={value!r} is not the device's {expected}")


def test_the_device_name_survives_its_spaces() -> None:
    """Every name in `KNOWN_COLORIMETERS` has a space in it, and the arguments
    go to `ShellExecuteExW` as one string, so the quoting is the app's own
    problem. Unquoted, `--name X-Rite i1 Studio` makes `i1` a stray argument
    and the device is registered as "X-Rite"."""
    for (vid, pid), name in udi.KNOWN_COLORIMETERS.items():
        device = udi.UsbDevice(vid=vid, pid=pid, name=name, has_winusb=False)
        emitted = parse_args(udi.wdi_simple_args(device))
        assert emitted.get("--name") == name, (
            f"{name!r} came back out of the command line as "
            f"{emitted.get('--name')!r}")


def test_install_winusb_uses_the_builder_rather_than_a_string_of_its_own() -> None:
    """The tests above are worth nothing if `install_winusb()` goes on building
    its own command line beside them. It must hand `wdi_simple_args()` the
    device and pass the result straight through."""
    src = inspect.getsource(udi.install_winusb)
    assert "wdi_simple_args(device)" in src, (
        "install_winusb() no longer builds its arguments through "
        "wdi_simple_args(), so nothing in this file describes what it sends")
    stray = re.findall(r"--[a-z][a-z0-9-]*", src)
    assert not stray, (
        f"install_winusb() spells out options of its own ({stray}); they are "
        f"outside every check in this file — put them in wdi_simple_args()")


# ---------------------------------------------------------------------------
# Keeping the snapshot honest — these two need something outside the tree
# ---------------------------------------------------------------------------

def wdi_simple_binary() -> "Path | None":
    """The real `wdi_simple.exe`, if this host has one.

    Not in the source tree: `.github/workflows/build-windows.yml` fetches it
    into `assets/` for a Windows build, and a built app carries it under
    `_internal/assets/`. `CHROMIQ_WDI_SIMPLE` overrides both.
    """
    candidates: "list[Path]" = []
    override = os.environ.get("CHROMIQ_WDI_SIMPLE")
    if override:
        candidates.append(Path(override))
    candidates.append(resource_path("assets/wdi_simple.exe"))
    root = Path(__file__).resolve().parent.parent
    candidates.append(
        root / "dist" / "ChromIQ" / "_internal" / "assets" / "wdi_simple.exe")
    for candidate in candidates:
        if candidate.exists() and candidate.stat().st_size > 0:
            return candidate
    return None


def searched_for_the_binary() -> str:
    root = Path(__file__).resolve().parent.parent
    return (f"{resource_path('assets/wdi_simple.exe')}, "
            f"{root / 'dist' / 'ChromIQ' / '_internal' / 'assets' / 'wdi_simple.exe'}"
            f", or $CHROMIQ_WDI_SIMPLE")


def test_the_bundled_binary_still_speaks_the_language_we_recorded() -> None:
    """The snapshot is the oracle every other test here uses, so it must not be
    allowed to become fiction. Where the real binary exists, ask it.

    SKIPS HONESTLY. This is the only test in the file that needs the binary,
    and skipping it does not weaken any of the others: they run against the
    checked-in snapshot on every host. What is lost when this skips is the
    freshness of that snapshot — nothing else.
    """
    if sys.platform != "win32":
        pytest.skip(
            "wdi_simple.exe is a Windows binary and cannot be run here. The "
            "option checks above still ran, against tests/golden/"
            "wdi_simple_usage.txt; only its freshness is unverified.")
    binary = wdi_simple_binary()
    if binary is None:
        pytest.skip(
            f"wdi_simple.exe is not on this host (looked in "
            f"{searched_for_the_binary()}). The option checks above still ran, "
            f"against tests/golden/wdi_simple_usage.txt; only its freshness is "
            f"unverified.")

    # `--help` prints and exits 0 without touching a device. Timed out
    # generously: the gate saturates every core, and a bare TimeoutExpired
    # here would read like a crash.
    result = subprocess.run([str(binary), "--help"],
                            capture_output=True, timeout=120)
    live = result.stdout.decode("utf-8", "replace").replace("\r\n", "\n")

    assert parse_usage(live) == parse_usage(snapshot_text()), (
        f"{binary} no longer offers the options recorded in {USAGE_SNAPSHOT}. "
        f"Re-capture the snapshot and re-read the command line the app "
        f"builds — an option may have been renamed or dropped under it.")
    assert parse_driver_types(live) == parse_driver_types(snapshot_text()), (
        f"{binary} has renumbered its driver types; "
        f"{USAGE_SNAPSHOT} is stale and --type may now name a different "
        f"driver than the one ChromIQ means")


def argyll_usb_inf() -> "Path | None":
    """Argyll's own driver `.inf`, at `<argyll root>/usb/ArgyllCMS.inf`."""
    from tests.argyll_env import argyll_bin_dir
    bin_dir = argyll_bin_dir()
    if bin_dir is None:
        return None
    inf = bin_dir.parent / "usb" / "ArgyllCMS.inf"
    return inf if inf.exists() else None


def test_argyll_binds_the_driver_ChromIQ_installs() -> None:
    """The judgement call, tied to the artefact that decides it.

    ChromIQ's job here is to leave the instrument in the state ArgyllCMS ships
    and tests, and Argyll says what that is in its own `.inf`: one service,
    `libusb0`, for every device it supports. If a future Argyll moved to
    WinUSB, this is the test that would notice — and `--type` would have to
    move with it.

    SKIPS where ArgyllCMS is not installed. Nothing else in this file depends
    on it.
    """
    inf = argyll_usb_inf()
    if inf is None:
        pytest.skip(
            "ArgyllCMS is not installed on this host, so its usb/ArgyllCMS.inf "
            "cannot be read. The driver type is still checked against "
            "wdi-simple's own numbering above; what is unverified here is that "
            "Argyll still binds that driver.")

    text = inf.read_text(encoding="utf-8", errors="replace")

    services = re.findall(r"^\s*AddService\s*=\s*([A-Za-z0-9_]+)", text,
                          re.MULTILINE)
    assert services, f"no AddService line in {inf}"
    assert set(services) == {"libusb0"}, (
        f"{inf} binds {sorted(set(services))}, not libusb0 alone. ChromIQ "
        f"installs libusb-win32 (wdi-simple --type "
        f"{udi.WDI_DRIVER_TYPE}) on the strength of that; re-decide the type "
        f"before this ships.")

    types = parse_driver_types(snapshot_text())
    assert types.get(udi.WDI_DRIVER_TYPE) == "libusb-win32", (
        f"Argyll binds libusb0, but WDI_DRIVER_TYPE="
        f"{udi.WDI_DRIVER_TYPE} asks wdi-simple for "
        f"{types.get(udi.WDI_DRIVER_TYPE)!r}")
