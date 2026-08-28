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


def test_the_bundled_helper_is_not_stale():
    """`ChromIQ.spec` bundles native/chromiq-chartread, while the engine prefers
    the CMake build tree — so a stale bundled copy is invisible in a checkout.
    It must at least know the instruments this branch added."""
    helper = ROOT / "native" / "chromiq-chartread"
    if not helper.is_file():
        import pytest
        pytest.skip("bundled helper not present")
    blob = helper.read_bytes()
    assert b"CR30" in blob, (
        "the bundled helper predates CR30 support — rebuild it from "
        "native/chartread_helper/build and commit the result")


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
