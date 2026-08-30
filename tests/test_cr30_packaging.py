"""The CR30 driver's dependencies must reach the PACKAGED app, not just a checkout.

Twice on this branch something worked in a dev checkout and would have been dead
in the artefact: a stale bundled helper binary, and then the driver's own
dependencies. Both were invisible until someone ran the real thing.

`workflow/cr30` imports pyserial and bleak LAZILY so the rest of ChromIQ still
loads without them — which is exactly why PyInstaller cannot find them by static
analysis, and why their absence shows up as a log line rather than a build error.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPEC = (ROOT / "ChromIQ.spec").read_text(errors="replace")
REQS = (ROOT / "requirements.txt").read_text(errors="replace")


def test_requirements_declare_the_driver_dependencies():
    assert re.search(r"^pyserial\b", REQS, re.M), "pyserial missing"
    assert re.search(r"^bleak\b", REQS, re.M), "bleak missing"


def test_the_spec_bundles_them_as_hidden_imports():
    """Lazy imports are invisible to PyInstaller's analysis."""
    for mod in ("'serial'", "'bleak'"):
        assert mod in SPEC, f"{mod} not in ChromIQ.spec hiddenimports"
    assert "'serial.tools.list_ports'" in SPEC, (
        "discovery enumerates ports through serial.tools.list_ports")


def test_the_app_asks_for_bluetooth_permission():
    """macOS refuses CoreBluetooth to an app that does not declare it.

    A dev run inherits Terminal's permission, so this gap is invisible until
    the .app is built — the packaged app simply never sees a CR30 over
    Bluetooth.
    """
    assert "NSBluetoothAlwaysUsageDescription" in SPEC
    m = re.search(r"'NSBluetoothAlwaysUsageDescription':\s*\n?\s*((?:'[^']*'\s*)+)",
                  SPEC)
    assert m, "the key is present but carries no description"
    text = " ".join(re.findall(r"'([^']*)'", m.group(1)))
    assert len(text) > 40, "the prompt text must explain what it is for"
    assert "CR30" in text, "the user should learn which instrument wants this"


def _expected_build_marker() -> bytes:
    """The marker the CURRENT sources define, read from the header."""
    header = (ROOT / "native" / "chartread_helper" / "chromiq_ext.h").read_text()
    m = re.search(r'#define\s+CQ_HELPER_BUILD\s+"([^"]+)"', header)
    assert m, "CQ_HELPER_BUILD has gone from chromiq_ext.h"
    return m.group(1).encode()


def test_the_bundled_helper_is_not_stale():
    """`ChromIQ.spec` bundles native/chromiq-chartread, while the engine prefers
    the CMake build tree — so a stale bundled copy is invisible in a checkout:
    everything a developer runs uses the fresh binary, and only the packaged app
    gets the old one.

    ⚠ THIS TEST USED TO GREP FOR b"CR30", which every build since this branch
    began contains — so it passed over a binary of any age from this branch. It
    could not have caught the committed helper missing the JSON path fix, which
    is a Windows-only fault nobody here can see. It now compares against a
    marker the sources carry and that is bumped whenever the helper changes.
    """
    helper = ROOT / "native" / "chromiq-chartread"
    if not helper.is_file():
        import pytest
        pytest.skip("bundled helper not present")
    blob = helper.read_bytes()
    assert b"CR30" in blob, (
        "the bundled helper predates CR30 support — rebuild it from "
        "native/chartread_helper/build and commit the result")
    want = _expected_build_marker()
    assert want in blob, (
        f"the bundled helper is stale: it does not carry {want!r}. Rebuild "
        "native/chartread_helper/build and copy the result to "
        "native/chromiq-chartread, in the same commit as the source change.")


def test_the_build_marker_is_bumped_when_the_helper_changes():
    """A marker nobody moves is a marker that proves nothing. It carries a date
    so that leaving it alone is visible in review rather than invisible."""
    marker = _expected_build_marker().decode()
    assert re.search(r"\d{4}-\d{2}-\d{2}", marker), (
        "the build marker carries no date, so a stale one cannot be spotted")


# ---- cross-platform, not just macOS ---------------------------------------

def test_the_spec_collects_bleak_backends_for_every_platform():
    """bleak picks its backend AT RUNTIME, so a bare 'bleak' import ships the
    façade and none of the machinery. The build platform is not the run
    platform for a spec that is shared across three of them."""
    assert "_collect_optional('bleak')" in SPEC
    for pkg in ("dbus_fast",                       # Linux, BlueZ over D-Bus
                "winrt.windows.devices.bluetooth", # Windows
                "CoreBluetooth"):                  # macOS
        assert pkg in SPEC, f"{pkg} not collected for its platform"


def test_the_collected_bluetooth_pieces_are_actually_bundled():
    """Collected but not wired into Analysis() would ship nothing."""
    for name in ("_bl_hiddenimports", "_btp_hiddenimports",
                 "_bl_binaries", "_btp_binaries",
                 "_bl_datas", "_btp_datas"):
        assert SPEC.count(name) >= 2, (
            f"{name} is collected but never passed to Analysis()")


def test_a_missing_bluetooth_package_cannot_break_the_build():
    """A Linux-only dependency must not fail a Windows build, and ChromIQ must
    still build with no Bluetooth stack at all — USB is a complete CR30."""
    assert "def _collect_optional(" in SPEC
    assert "except Exception:" in SPEC.split("def _collect_optional(")[1][:200]


def test_the_no_device_message_names_the_platform_specific_fix():
    """Every platform has one gotcha that is invisible in the raw exception."""
    import sys as _sys
    sys_path = str(ROOT)
    if sys_path not in _sys.path:
        _sys.path.insert(0, sys_path)
    from workflow.cr30.measure_bridge import _no_device_help
    text = _no_device_help("usb boom", "ble boom")
    assert "usb boom" in text and "ble boom" in text, "both failures must show"
    assert "phone app" in text, "the CR30 stops advertising while a phone holds it"
    if _sys.platform.startswith("linux"):
        assert "dialout" in text
    elif _sys.platform == "win32":
        assert "Device Manager" in text
    else:
        assert "Privacy & Security" in text
