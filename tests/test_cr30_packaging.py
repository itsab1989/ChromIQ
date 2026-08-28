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
