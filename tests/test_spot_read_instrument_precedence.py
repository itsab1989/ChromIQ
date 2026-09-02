"""What is connected NOW beats what was connected once.

The owner, 2026-09-03, an hour after the rule that caused it was merged:

    "had my colormunki connected via usb and set to detect automatically. it
     defaulted to the cr30 via blutooth and did not leave me a choice. maybe
     because the cr30 was still connected from before?"

`cr30_is_remembered_over_bluetooth()` reads `cr30_ble_address`, an address
stored at some point in the past that nothing ever clears. On his Mac it is set
(`FFB32AD2-...`), so `"cr30" if (on_usb or over_bt) else "argyll"` could never
return "argyll" again, whatever was plugged in — and that broke his stated
requirement for the whole feature:

    "supporting the cr30 should not affect the other supported instruments so
     i should be able to still use my colormunki for example"

**The truth table below is the fix, one test per row**, so that a later change
to the precedence cannot pass quietly. Both complaints are legitimate — the
rule was itself the fix for a Bluetooth-only CR30 that automatic could not
find — so every row is pinned, not just the one that was reported.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from PyQt6.QtCore import QSettings

from core.settings import AppSettings
from core.argyll_runner import ArgyllRunner


@pytest.fixture
def dialog(qapp, tmp_path):
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    dlg = SpotReadDialog(ArgyllRunner(s), s, None)
    yield dlg
    dlg.deleteLater()


def _evidence(monkeypatch, *, argyll, cr30_usb, cr30_bt):
    """Set the three pieces of evidence the decision is made from."""
    import ui.dialogs.spot_read_dialog as mod
    monkeypatch.setattr(mod, "argyll_is_attached", lambda: argyll)
    monkeypatch.setattr(mod, "cr30_is_probably_attached", lambda: cr30_usb)
    monkeypatch.setattr(mod, "cr30_is_remembered_over_bluetooth", lambda: cr30_bt)


# ----------------------------------------------------------------------
# THE TRUTH TABLE. One test per row.
#
#   ArgyllCMS attached now | CR30 on USB now | CR30 remembered over BT | reader
#   -----------------------|-----------------|-------------------------|-------
#   no                     | yes             | no                      | cr30
#   no                     | no              | yes                     | cr30
#   no                     | yes             | yes                     | cr30
#   YES                    | no              | no                      | argyll
#   YES                    | no              | YES                     | argyll   <- his case
#   YES                    | yes             | no                      | argyll
#   YES                    | yes             | yes                     | argyll
#   no                     | no              | no                      | argyll
#   unknown host           | no              | yes                     | cr30
#   unknown host           | no              | no                      | argyll
# ----------------------------------------------------------------------
def test_row_cr30_on_usb_alone(dialog, monkeypatch):
    """A CR30 on USB must still be found. That is the first thing this feature
    was built to do."""
    _evidence(monkeypatch, argyll=False, cr30_usb=True, cr30_bt=False)
    assert dialog._chosen_reader() == "cr30"


def test_row_cr30_remembered_over_bluetooth_alone(dialog, monkeypatch):
    """A Bluetooth-only CR30 must still be found. This is the fault the
    remembered address was added for an hour before the regression, and
    re-breaking it would be failure of a different kind."""
    _evidence(monkeypatch, argyll=False, cr30_usb=False, cr30_bt=True)
    assert dialog._chosen_reader() == "cr30"


def test_row_a_cr30_on_usb_that_is_also_remembered(dialog, monkeypatch):
    _evidence(monkeypatch, argyll=False, cr30_usb=True, cr30_bt=True)
    assert dialog._chosen_reader() == "cr30"


def test_row_colormunki_on_usb_alone(dialog, monkeypatch):
    _evidence(monkeypatch, argyll=True, cr30_usb=False, cr30_bt=False)
    assert dialog._chosen_reader() == "argyll"


def test_row_colormunki_on_usb_with_a_cr30_remembered(dialog, monkeypatch):
    """HIS CASE, AND THE REGRESSION. An address stored at some point in the
    past must never outrank an instrument physically present."""
    _evidence(monkeypatch, argyll=True, cr30_usb=False, cr30_bt=True)
    assert dialog._chosen_reader() == "argyll"


def test_row_both_live_goes_to_the_argyllcms_instrument(dialog, monkeypatch):
    """The tie-break, and it is a decision rather than an accident of order.

    "Supporting the cr30 should not affect the other supported instruments":
    a CR30 left plugged in from yesterday must not take his ColorMunki away.
    It costs a CR30 owner one click in the row that names the reader, and the
    choice is remembered.
    """
    _evidence(monkeypatch, argyll=True, cr30_usb=True, cr30_bt=False)
    assert dialog._chosen_reader() == "argyll"


def test_row_everything_at_once_still_goes_to_argyllcms(dialog, monkeypatch):
    _evidence(monkeypatch, argyll=True, cr30_usb=True, cr30_bt=True)
    assert dialog._chosen_reader() == "argyll"


def test_row_nothing_at_all(dialog, monkeypatch):
    _evidence(monkeypatch, argyll=False, cr30_usb=False, cr30_bt=False)
    assert dialog._chosen_reader() == "argyll"


def test_row_an_unreadable_host_does_not_contradict_the_bluetooth_memory(
        dialog, monkeypatch):
    """`None` is "I could not look", not "nothing is attached".

    A host whose USB list cannot be read has produced no evidence, so it may
    not overrule anything: the behaviour there is exactly what it was before
    this check existed.
    """
    _evidence(monkeypatch, argyll=None, cr30_usb=False, cr30_bt=True)
    assert dialog._chosen_reader() == "cr30"


def test_row_an_unreadable_host_with_no_cr30_evidence_is_still_argyll(
        dialog, monkeypatch):
    _evidence(monkeypatch, argyll=None, cr30_usb=False, cr30_bt=False)
    assert dialog._chosen_reader() == "argyll"


# ----------------------------------------------------------------------
# An explicit choice always wins — every row of the table, twice
# ----------------------------------------------------------------------
@pytest.mark.parametrize("argyll", [True, False, None])
@pytest.mark.parametrize("cr30_usb", [True, False])
@pytest.mark.parametrize("cr30_bt", [True, False])
def test_any_argyllcms_instrument_chosen_by_hand_beats_every_detection(
        dialog, monkeypatch, argyll, cr30_usb, cr30_bt):
    _evidence(monkeypatch, argyll=argyll, cr30_usb=cr30_usb, cr30_bt=cr30_bt)
    dialog._instrument.setCurrentIndex(1)          # Any ArgyllCMS instrument
    assert dialog._chosen_reader() == "argyll"


@pytest.mark.parametrize("argyll", [True, False, None])
@pytest.mark.parametrize("cr30_usb", [True, False])
@pytest.mark.parametrize("cr30_bt", [True, False])
def test_the_cr30_chosen_by_hand_beats_every_detection(
        dialog, monkeypatch, argyll, cr30_usb, cr30_bt):
    _evidence(monkeypatch, argyll=argyll, cr30_usb=cr30_usb, cr30_bt=cr30_bt)
    dialog._instrument.setCurrentIndex(2)          # CR30 (ChnSpec)
    assert dialog._chosen_reader() == "cr30"


# ----------------------------------------------------------------------
# "Is an ArgyllCMS instrument attached?" — the new question
# ----------------------------------------------------------------------
def test_no_ch340_bridge_is_ever_an_instrument():
    """An Arduino answers to `1A86:7523`, and so does a 3D printer and a CNC
    controller. It is the CR30's serial bridge, never an ArgyllCMS device."""
    from core.argyll_instruments import ARGYLL_USB_IDS, CH34X_IDS, match
    assert match(*CH34X_IDS) is None
    assert not any(vid == CH34X_IDS[0] for vid, _pid in ARGYLL_USB_IDS)


def test_the_id_table_is_argylls_own_eight_vendors():
    """`inst_usb_match()` in `spectro/insttypes.c` matches eight vendor ids."""
    from core.argyll_instruments import ARGYLL_USB_IDS
    vendors = {vid for vid, _pid in ARGYLL_USB_IDS}
    assert vendors == {0x04DB, 0x0670, 0x0765, 0x085C, 0x0971,
                       0x2457, 0x04D8, 0x273F}
    # The owner's own instrument, which is what the regression was about.
    assert ARGYLL_USB_IDS[(0x0765, 0x6008)] == "ColorMunki i1Studio"


_ARGYLL_SRC = Path.home() / "Downloads/Argyll_V3.5.0_orig/spectro/insttypes.c"


@pytest.mark.skipif(not _ARGYLL_SRC.exists(),
                    reason="the ArgyllCMS source tree is not on this machine")
def test_the_id_table_still_matches_argylls_source():
    """Read `inst_usb_match()` and compare, so an Argyll upgrade that adds an
    instrument fails here instead of going unnoticed."""
    import re
    from core.argyll_instruments import ARGYLL_USB_IDS
    text = _ARGYLL_SRC.read_text(encoding="utf-8", errors="replace")
    body = text.split("instType inst_usb_match(", 1)[1].split("\n}", 1)[0]
    pairs: set = set()
    vendor = None
    for line in body.splitlines():
        m = re.search(r"idVendor == 0x([0-9A-Fa-f]{4})", line)
        if m:
            vendor = int(m.group(1), 16)
        for m in re.finditer(r"idProduct == 0x([0-9A-Fa-f]{4})", line):
            pid = int(m.group(1), 16)
            # The two ColorHug lines name their own vendor on the same line.
            own = re.search(r"idVendor == 0x([0-9A-Fa-f]{4})\s*&&\s*"
                            r"idProduct == 0x" + m.group(1), line)
            pairs.add((int(own.group(1), 16) if own else vendor, pid))
    assert pairs == set(ARGYLL_USB_IDS), (
        f"only in Argyll: {sorted(pairs - set(ARGYLL_USB_IDS))}; "
        f"only in ChromIQ: {sorted(set(ARGYLL_USB_IDS) - pairs)}")


def test_nothing_is_opened_and_spotread_is_never_launched():
    """The wall of usage text in his log came from launching `spotread` to find
    out what was attached. Asking the OS costs 17 ms and takes no device."""
    import io
    import tokenize
    from core import argyll_instruments as mod
    # The CODE, with every comment and docstring removed — the prose above
    # names `spotread` repeatedly, and it is the calls that matter.
    src = inspect.getsource(mod)
    code = "".join(
        tok.string + " " for tok in
        tokenize.generate_tokens(io.StringIO(src).readline)
        if tok.type not in (tokenize.COMMENT, tokenize.STRING))
    for forbidden in ("spotread", "chartread", "open_usb", "open_ble",
                      "connect", "DeviceReader"):
        assert forbidden not in code, forbidden
    # …and it does not reach for the CR30 driver either.
    assert "cr30" not in code.lower()


def test_the_ioreg_reading_finds_a_colormunki_and_leaves_the_ch340_alone():
    """Real `ioreg -p IOUSB -l` output, captured on the owner's Mac 2026-09-03
    with both instruments plugged in."""
    from core.argyll_instruments import _parse_ioreg, UsbDevice
    sample = """
+-o Root  <class IORegistryEntry, id 0x100000100, retain 36>
  +-o AppleT8122USBXHCI@01000000  <class AppleT8122USBXHCI, id 0x1000004f4>
  | +-o CH554_CDC@01100000  <class IOUSBHostDevice, id 0x101b13759>
  |       "idProduct" = 29987
  |       "USB Product Name" = "CH554_CDC"
  |       "idVendor" = 6790
  +-o AppleT8122USBXHCI@02000000  <class AppleT8122USBXHCI, id 0x100000450>
    +-o i1Studio@02100000  <class IOUSBHostDevice, id 0x101b13723>
          "idProduct" = 24584
          "USB Product Name" = "i1Studio"
          "idVendor" = 1893
"""
    assert _parse_ioreg(sample) == (
        UsbDevice(0x1A86, 0x7523, "CH554_CDC"),
        UsbDevice(0x0765, 0x6008, "i1Studio"),
    )


def test_an_empty_device_list_and_an_unreadable_one_are_different_answers():
    """`()` is evidence. `None` is the absence of evidence. Collapsing them is
    the whole mistake this change undoes, one level down."""
    from core import argyll_instruments as mod
    original = mod.usb_devices
    try:
        mod.usb_devices = lambda: ()
        assert mod.attached_instruments() == ()
        assert mod.any_attached() is False
        mod.usb_devices = lambda: None
        assert mod.attached_instruments() is None
        assert mod.any_attached() is None
        mod.usb_devices = lambda: (mod.UsbDevice(0x0765, 0x6008, "i1Studio"),)
        assert mod.attached_instruments() == ("ColorMunki i1Studio",)
        assert mod.any_attached() is True
    finally:
        mod.usb_devices = original


def test_the_linux_reading_is_sysfs_and_present_only(tmp_path):
    from core.argyll_instruments import _linux_usb_devices, UsbDevice
    dev = tmp_path / "1-1"
    dev.mkdir()
    (dev / "idVendor").write_text("0765\n", encoding="utf-8")
    (dev / "idProduct").write_text("6008\n", encoding="utf-8")
    (dev / "product").write_text("i1Studio\n", encoding="utf-8")
    iface = tmp_path / "1-1:1.0"      # an interface has no ids and is skipped
    iface.mkdir()
    assert _linux_usb_devices(str(tmp_path)) == (
        UsbDevice(0x0765, 0x6008, "i1Studio"),)
    assert _linux_usb_devices(str(tmp_path / "nope")) is None


def test_the_windows_reading_parses_present_device_instance_ids():
    from core.argyll_instruments import _parse_windows_ids, UsbDevice
    assert _parse_windows_ids([
        r"USB\VID_0765&PID_6008\5&1234ABCD&0&2",
        r"USB\VID_1A86&PID_7523\6&DEADBEEF&0&1",
        r"USB\ROOT_HUB30\4&2A1B3C4D&0",
    ]) == (UsbDevice(0x0765, 0x6008, ""), UsbDevice(0x1A86, 0x7523, ""))


def test_the_windows_reading_does_not_use_the_registry_enum_key():
    """`HKLM\\SYSTEM\\CurrentControlSet\\Enum\\USB` lists every device the
    machine has EVER seen — the same "remembered, not present" mistake, one
    layer down. cfgmgr32's PRESENT filter is the question actually being asked.
    """
    from core import argyll_instruments as mod
    src = inspect.getsource(mod._windows_usb_devices)
    assert "CM_GETIDLIST_FILTER_PRESENT" in src
    assert "winreg" not in src


# ----------------------------------------------------------------------
# "did not leave me a choice" — the window says which reader it settled on
# ----------------------------------------------------------------------
def test_the_window_names_the_reader_automatic_settled_on(dialog, monkeypatch):
    _evidence(monkeypatch, argyll=True, cr30_usb=False, cr30_bt=True)
    dialog._instrument.setCurrentIndex(0)
    dialog._refresh_auto_choice()
    assert dialog._auto_choice.isVisible() or dialog._auto_choice.text()
    assert "ArgyllCMS" in dialog._auto_choice.text()

    _evidence(monkeypatch, argyll=False, cr30_usb=False, cr30_bt=True)
    dialog._refresh_auto_choice()
    assert "CR30" in dialog._auto_choice.text()


def test_the_name_it_shows_is_one_of_the_combos_own_entries(dialog,
                                                            monkeypatch):
    """No new wording is invented for this: the label points at an entry that
    is already in the dropdown and already translated."""
    from ui.dialogs.spot_read_dialog import _instrument_labels
    _evidence(monkeypatch, argyll=False, cr30_usb=True, cr30_bt=False)
    dialog._instrument.setCurrentIndex(0)
    dialog._refresh_auto_choice()
    shown = dialog._auto_choice.text().lstrip("→ ").strip()
    assert shown in _instrument_labels()


def test_the_row_says_nothing_when_the_reader_was_chosen_by_hand(dialog,
                                                                 monkeypatch):
    """The combo already names it; an arrow repeating it would read as a
    second, different answer."""
    _evidence(monkeypatch, argyll=True, cr30_usb=True, cr30_bt=True)
    for index in (1, 2):
        dialog._instrument.setCurrentIndex(index)
        dialog._refresh_auto_choice()
        assert dialog._auto_choice.text() == ""


def test_the_name_follows_the_cable(dialog, monkeypatch):
    """He can plug the ColorMunki in with this window open. A label that went
    stale would be worse than no label at all."""
    dialog._instrument.setCurrentIndex(0)
    _evidence(monkeypatch, argyll=False, cr30_usb=False, cr30_bt=True)
    dialog._refresh_auto_choice()
    assert "CR30" in dialog._auto_choice.text()
    _evidence(monkeypatch, argyll=True, cr30_usb=False, cr30_bt=True)
    dialog._refresh_auto_choice()
    assert "ArgyllCMS" in dialog._auto_choice.text()


def test_the_reader_is_never_probed_while_a_session_owns_the_instrument(
        dialog, monkeypatch):
    asked = []
    import ui.dialogs.spot_read_dialog as mod
    monkeypatch.setattr(mod, "argyll_is_attached",
                        lambda: asked.append("argyll") or False)
    dialog._instrument.setCurrentIndex(0)
    dialog._set_session_running(True)
    asked.clear()
    dialog._refresh_auto_choice()
    assert asked == [], "the device list was read under a running session"


def test_the_decision_and_its_evidence_reach_the_log(dialog, monkeypatch,
                                                     caplog):
    """His log of the failed session records the spotread launch and nothing
    about WHY, so the first question anybody asked of it could not be answered
    from the file."""
    _evidence(monkeypatch, argyll=True, cr30_usb=False, cr30_bt=True)
    dialog._instrument.setCurrentIndex(0)
    with caplog.at_level("INFO", logger="ui.dialogs.spot_read_dialog"):
        assert dialog._chosen_reader() == "argyll"
    text = caplog.text
    assert "ArgyllCMS instrument attached now: True" in text
    assert "CR30 on USB now: False" in text
    assert "Bluetooth before: True" in text


# ----------------------------------------------------------------------
# The USB look, after the node number disproved the old rule
# ----------------------------------------------------------------------
def test_a_cr30_that_moved_to_another_usb_port_is_still_found(monkeypatch):
    """MEASURED ON HIS MAC, 2026-09-03: `cr30_usb_port` remembered
    `/dev/cu.usbserial-10` while the instrument was answering on
    `/dev/cu.usbserial-110`. A `cu.usbserial-*` node number is not stable
    across replugs, so the strict comparison had quietly stopped recognising
    the CR30 on USB at all."""
    from ui.dialogs import spot_read_dialog as mod
    from workflow.cr30.discovery import Candidate
    from workflow.cr30.measure_bridge import DeviceReader
    monkeypatch.setattr("workflow.cr30.discovery.candidates",
                        lambda **kw: [Candidate("/dev/cu.usbserial-110",
                                                0x1A86, 0x7523, "CH554_CDC")])
    monkeypatch.setattr(DeviceReader, "_remembered",
                        staticmethod(lambda k: "/dev/cu.usbserial-10"))
    assert mod.cr30_is_probably_attached() is True


def test_a_ch340_on_a_machine_that_never_used_a_cr30_is_not_one(monkeypatch):
    """The other half, unchanged and load-bearing: with nothing remembered, a
    CH340 bridge is an Arduino as far as ChromIQ is concerned."""
    from ui.dialogs import spot_read_dialog as mod
    from workflow.cr30.discovery import Candidate
    from workflow.cr30.measure_bridge import DeviceReader
    monkeypatch.setattr("workflow.cr30.discovery.candidates",
                        lambda **kw: [Candidate("/dev/cu.usbserial-99",
                                                0x1A86, 0x7523, "CH554_CDC")])
    monkeypatch.setattr(DeviceReader, "_remembered", staticmethod(lambda k: None))
    assert mod.cr30_is_probably_attached() is False


def test_no_candidate_present_means_no_cr30_on_usb(monkeypatch):
    from ui.dialogs import spot_read_dialog as mod
    from workflow.cr30.measure_bridge import DeviceReader
    monkeypatch.setattr("workflow.cr30.discovery.candidates", lambda **kw: [])
    monkeypatch.setattr(DeviceReader, "_remembered",
                        staticmethod(lambda k: "/dev/cu.usbserial-10"))
    assert mod.cr30_is_probably_attached() is False


def test_a_remembered_cr30_choice_greys_what_it_cannot_do(qapp, tmp_path):
    """FOUND WHILE PHOTOGRAPHING THE ROW, and it predates this branch.

    `setCurrentIndex` in the constructor runs before `currentIndexChanged` is
    connected, so a window REOPENED with "CR30 (ChnSpec)" remembered came up
    offering Mode and Skip initial calibration. Both are ArgyllCMS's, both go
    nowhere for a CR30 — a reflective-only instrument that calibrates its own
    way — and that is how somebody comes to believe they measured a display.
    """
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("spot_read_instrument", "cr30")
    dlg = SpotReadDialog(ArgyllRunner(s), s, None)
    try:
        assert dlg._instrument.currentText().startswith("CR30")
        assert not dlg._mode.isEnabled()
        assert not dlg._skip_cal.isEnabled()
    finally:
        dlg.deleteLater()
