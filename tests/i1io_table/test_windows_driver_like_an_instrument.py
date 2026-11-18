"""The i1iO table's Windows driver, helped like any instrument's (release after 4.3.45).

The owner, 2026-11-18: *"why dont we allow to install the driver on windows? the reasoning from
the changelog on this is strange. because the same issue exists with any other xrite instrument
that is held by argylls driver. so nothing special here and it should be allowed to install it
and the app shall help with it."*

What is pinned here (no hardware, no driver is ever installed: every Windows path runs with the
platform patched and `install_winusb` replaced):

1. Preferences > Instrument drivers lists the table, behind the Beta, like an instrument; the
   person's choice is attached only after its install button; Beta off = the very call it
   always made; an x64 ChromIQ on a Windows for ARM computer is not offered an install that
   cannot help it, while the ARM64 build there is offered it like x64 (2026-11-18).
2. START: a table, or the i1Pro 2 in its arm, without the driver gets the offer ("Not now" /
   install), which opens the same window; for the x64 build on an ARM64 PC the truthful message
   naming the ARM64 version instead.
3. The texts: catalogued, proposed, no placeholder left, no em dash, translated.
4. macOS and Linux unchanged.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import core.usb_driver_installer as inst
from tests.i1io_table import job_harness as H
from workflow.i1io.table import job as J
from workflow.i1io.table import usb_system as us

TABLE = ("0971", "2004")
I1PRO = ("0971", "2000")


# ---- 1. the installer: the table behind a flag ---------------------------------------------

ENTRIES = [("VID_0971&PID_2004", [("6&a&0&1", "")]),
           ("VID_0971&PID_2000", [("6&b&0&2", "libusb0")])]


def test_the_table_is_listed_only_when_asked_and_carries_no_choice():
    off = inst.attached_devices(ENTRIES, None)
    assert [(d.vid, d.pid) for d in off] == [I1PRO]
    on = inst.attached_devices(ENTRIES, None, include_table=True)
    assert [(d.vid, d.pid) for d in on] == [TABLE, I1PRO]
    table, pro = on
    assert isinstance(table, inst.TableUsbDevice) and table.name == "X-Rite i1iO 2 table"
    assert not table.has_winusb and pro.has_winusb       # the i1Pro 2 keeps its own entry
    assert getattr(table, "choice", None) is None
    assert inst.install_winusb(table) is inst.InstallAttempt.REFUSED


def test_a_table_with_the_driver_reads_as_installed_and_a_ghost_is_not_listed():
    entries = [("VID_0971&PID_2004", [("6&a&0&1", "libusb0")])]
    got = inst.attached_devices(entries, {"USB\\VID_0971&PID_2004\\6&A&0&1"}, include_table=True)
    assert [(d.vid, d.pid, d.has_winusb) for d in got] == [("0971", "2004", True)]
    # remembered by the registry, not attached: never offered
    assert inst.attached_devices(entries, set(), include_table=True) == []


def test_unbound_targets_re_reads_the_table_only_when_it_was_a_target(monkeypatch):
    calls = []

    def fake(**kw):
        calls.append(kw)
        return [inst.TableUsbDevice("0971", "2004", "X-Rite i1iO 2 table", False),
                inst.UsbDevice("0971", "2000", "GretagMacbeth i1 Pro / i1 Pro 2", False)]
    monkeypatch.setattr(inst, "enumerate_connected", fake)
    pro = inst.UsbDevice("0971", "2000", "GretagMacbeth i1 Pro / i1 Pro 2", False)
    assert [(d.vid, d.pid) for d in inst.unbound_targets([pro])] == [I1PRO]
    assert calls == [{}]                                 # Beta-off shape: no keyword at all
    table = inst.table_device_for(inst.ExplicitTableChoice(inst.TABLE_CHOICE_WORDS))
    got = inst.unbound_targets([table, pro])
    assert calls[-1] == {"include_table": True}
    assert {(d.vid, d.pid) for d in got} == {TABLE, I1PRO}


@pytest.mark.parametrize("machine_arm,process_arm,can", [
    (True, False, False),      # the x64 build under emulation on an ARM PC: cannot
    (True, True, True),        # the ARM64 build on an ARM PC: can (2026-11-18)
    (False, False, True),      # x64 on x64: unchanged
])
def test_the_install_can_help_unless_an_x64_build_runs_on_an_arm_pc(
        monkeypatch, machine_arm, process_arm, can):
    import core.usb_library as ul
    monkeypatch.setattr(ul, "machine_is_arm64", lambda: machine_arm)
    monkeypatch.setattr(ul, "process_is_windows_arm64", lambda: process_arm)
    assert inst.table_driver_can_help() is can
    assert ul.table_drive_impossible_here() is (not can)


# ---- 1b. the Instrument drivers window ----------------------------------------------------

from tests.test_usb_driver_dialog import (  # noqa: E402  (its fixtures and helpers)
    ModalDriver, _button, _ok_button, dialog, qapp_for_driving,  # noqa: F401
)
from ui.dialogs import settings_dialog as sd  # noqa: E402


@pytest.fixture
def on_windows(monkeypatch):
    monkeypatch.setattr(sd, "_sys", SimpleNamespace(platform="win32"))


@pytest.fixture
def beta(monkeypatch):
    from workflow.i1io import support
    state = {"on": True}
    monkeypatch.setattr(support, "i1io_enabled", lambda: state["on"])
    return state


def _hardware(monkeypatch, devices, *, arm64=False, arm64_build=False):
    """The window's hardware, recorded: what enumerate_connected was asked, and what
    install_winusb was handed."""
    import core.resource_path as rp
    import core.usb_library as ul
    asked, installed = [], []

    def enumerate_connected(**kw):
        asked.append(kw)
        if kw.get("include_table"):
            return list(devices)
        return [d for d in devices if not inst.is_table(d.vid, d.pid)]
    monkeypatch.setattr(inst, "enumerate_connected", enumerate_connected)
    monkeypatch.setattr(inst, "unbound_targets", lambda t: [])

    def install(d, **kw):
        installed.append(d)
        return inst.InstallAttempt.INSTALLED
    monkeypatch.setattr(inst, "install_winusb", install)
    monkeypatch.setattr(ul, "machine_is_arm64", lambda: arm64)
    monkeypatch.setattr(ul, "process_is_windows_arm64", lambda: arm64_build)
    monkeypatch.setattr(sd.SettingsDialog, "_serial_states", lambda self: [])

    class _P:
        def exists(self):
            return True
    monkeypatch.setattr(rp, "resource_path", lambda p: _P())
    return asked, installed


def _table(bound=False):
    return inst.TableUsbDevice("0971", "2004", "X-Rite i1iO 2 table", bound)


def _pro(bound=False):
    return inst.UsbDevice("0971", "2000", "GretagMacbeth i1 Pro / i1 Pro 2", bound)


def test_beta_on_the_window_lists_the_table_and_says_what_it_means(
        dialog, on_windows, beta, monkeypatch):
    asked, installed = _hardware(monkeypatch, [_table(), _pro(True)])
    with ModalDriver(lambda w: _button(w, "Close").click()) as drv:
        dialog._show_usb_installer()
    said = drv.text_of(0)
    assert asked == [{"include_table": True}]
    assert "X-Rite i1iO 2 table" in said and "GretagMacbeth i1 Pro / i1 Pro 2" in said
    assert "i1Profiler cannot use the table" in said
    for step in GUIDE_STEPS:
        assert step in said
    assert "install X-Rite's own driver" not in said
    assert installed == []                               # Close installs nothing


def _other(bound=False):
    return inst.UsbDevice("0765", "6008", "X-Rite i1Studio / ColorMunki", bound)


def _press(dialog, label):
    """Open the window, press *label*, acknowledge the outcome; the texts seen."""
    with ModalDriver(lambda w: _button(w, label).click(),
                     lambda w: _ok_button(w).click()) as drv:
        dialog._show_usb_installer()
    assert drv.modal_count == 2
    return drv


def test_the_instruments_button_never_takes_the_table_along(
        dialog, on_windows, beta, monkeypatch):
    """Review 446, W-S1: both driverless; "Install Driver" (the instruments' button) installs
    for the i1Pro 2 and NOT for the table."""
    asked, installed = _hardware(monkeypatch, [_table(), _pro(False)])
    _press(dialog, "Install Driver")
    assert [(d.vid, d.pid) for d in installed] == [I1PRO]
    assert type(installed[0]) is inst.UsbDevice and getattr(installed[0], "choice", None) is None


def test_the_tables_own_button_installs_for_the_table_alone_with_the_choice(
        dialog, on_windows, beta, monkeypatch):
    """Review 446, W-S1: the table is its own explicit choice: its button installs for the
    table only, carrying the person's choice; the driverless i1Pro 2 is left as it is."""
    asked, installed = _hardware(monkeypatch, [_table(), _pro(False)])
    _press(dialog, "Install Driver for the Table")
    assert [(d.vid, d.pid) for d in installed] == [TABLE]
    assert inst._choice_holds(installed[0])                # the person's own press


def test_the_i1pro2_can_get_the_driver_while_the_table_keeps_x_rites(
        dialog, on_windows, beta, monkeypatch):
    """Review 446, W-S1, both directions: the table with the driver and the i1Pro 2 without
    (and the reverse) are still two choices."""
    asked, installed = _hardware(monkeypatch, [_table(True), _pro(False)])
    seen = []

    def look_then_install(w):
        seen.append((_button(w, "Install Driver") is not None,
                     _button(w, "Reinstall Driver for the Table") is not None))
        _button(w, "Install Driver").click()
    with ModalDriver(look_then_install, lambda w: _ok_button(w).click()):
        dialog._show_usb_installer()
    assert seen == [(True, True)]
    assert [(d.vid, d.pid) for d in installed] == [I1PRO]
    installed.clear()
    asked, installed = _hardware(monkeypatch, [_table(False), _pro(True)])
    _press(dialog, "Install Driver for the Table")
    assert [(d.vid, d.pid) for d in installed] == [TABLE]


@pytest.mark.parametrize("order", ["pro_first", "two_instruments_and_the_table"])
def test_each_device_gets_its_own_install_once_and_the_table_only_when_chosen(
        dialog, on_windows, beta, monkeypatch, order):
    """Review 446, planted fault W5b survived because every test listed the table first: with
    the i1Pro 2 listed BEFORE the table (and with two instruments plus the table), each device
    gets exactly one install call of its own, with its own id, and the table only when its own
    button was pressed."""
    listed = ([_pro(), _table()] if order == "pro_first"
              else [_pro(), _other(), _table()])
    instruments = [(d.vid, d.pid) for d in listed if not inst.is_table(d.vid, d.pid)]
    asked, installed = _hardware(monkeypatch, listed)
    _press(dialog, "Install Driver")
    assert [(d.vid, d.pid) for d in installed] == instruments      # once each, no table
    assert not any(inst.is_table(d.vid, d.pid) for d in installed)
    installed.clear()
    _press(dialog, "Install Driver for the Table")
    assert [(d.vid, d.pid) for d in installed] == [TABLE]           # once, its own id
    assert inst._choice_holds(installed[0])


def test_a_table_target_is_built_from_the_listed_table_and_never_from_an_instrument():
    choice = inst.ExplicitTableChoice(inst.TABLE_CHOICE_WORDS)
    t = inst.table_device_for(choice, _table())
    assert (t.vid, t.pid) == TABLE and inst._choice_holds(t)
    with pytest.raises(ValueError):
        inst.table_device_for(inst.ExplicitTableChoice(inst.TABLE_CHOICE_WORDS), _pro())


def test_with_only_the_table_the_window_does_not_call_it_a_colorimeter(
        dialog, on_windows, beta, monkeypatch):
    """Review 446, W-S2: with only the table connected, nothing calls it a colorimeter that
    ArgyllCMS talks to; the table's own section says what is true of it."""
    asked, installed = _hardware(monkeypatch, [_table()])
    seen = []

    def look_then_close(w):
        from PyQt6.QtWidgets import QGroupBox
        seen.append([g.title() for g in w.findChildren(QGroupBox)])
        _button(w, "Close").click()
    with ModalDriver(look_then_close) as drv:
        dialog._show_usb_installer()
    said = drv.text_of(0)
    assert "Connected colorimeter" not in said
    assert "so ArgyllCMS can talk to it" not in said
    assert "Connected table:" in said and "X-Rite i1iO 2 table: driver not installed" in said
    assert "ChromIQ drives the table itself" in said
    assert "The i1iO table (beta)" in seen[0]
    # the certificate disclosure travels with the only install button there is
    assert sd.usb_certificate_notice_line()[len("<br><br>"):][:40] in \
        sd.usb_table_text([_table()], button="x", with_certificate_line=True)
    assert installed == []


def test_beta_off_the_window_is_exactly_as_before(dialog, on_windows, beta, monkeypatch):
    beta["on"] = False
    asked, installed = _hardware(monkeypatch, [_table(), _pro(False)])
    with ModalDriver(lambda w: _button(w, "Install Driver").click(),
                     lambda w: _ok_button(w).click()) as drv:
        dialog._show_usb_installer()
    assert asked == [{}]                                 # the old call, word for word
    assert "i1iO" not in drv.text_of(0)
    assert [(d.vid, d.pid) for d in installed] == [I1PRO]


_BETA_OFF_CASES = {
    "pro_unbound_table_unbound": [(_pro, False), (_table, False)],
    "pro_bound_table_unbound": [(_pro, True), (_table, False)],
    "only_table": [(_table, False)],
    "munki_and_pro_bound": [(lambda b: inst.UsbDevice("0765", "6008",
                                                      "X-Rite i1Studio / ColorMunki", b), True),
                            (_pro, True)],
}


@pytest.mark.parametrize("case", sorted(_BETA_OFF_CASES))
@pytest.mark.parametrize("press", ["first", "close"])
def test_beta_off_the_window_is_byte_identical_to_4_3_45(
        dialog, on_windows, beta, monkeypatch, case, press):
    """Beta off, recorded completely and compared with 4.3.45 itself: every enumerate_connected
    call with its arguments, every modal window's title and text, every device handed to
    install_winusb. The recording `tests/data/instrument_drivers_beta_off_4_3_45.json` was made
    by the review of 2026-11-18 (`probes/test_probe_win_beta_off.py`) in the 4.3.45 tree with the
    same fake hardware."""
    import json
    from pathlib import Path
    beta["on"] = False
    devices = [make(bound) for make, bound in _BETA_OFF_CASES[case]]
    asked, installed = [], []
    _hardware(monkeypatch, devices)

    def enumerate_connected(*a, **kw):
        asked.append([list(a), kw])
        if kw.get("include_table"):
            return list(devices)
        return [d for d in devices if not inst.is_table(d.vid, d.pid)]
    monkeypatch.setattr(inst, "enumerate_connected", enumerate_connected)

    def install(d, **kw):
        installed.append([d.vid, d.pid, d.name, type(d).__name__,
                          bool(getattr(d, "choice", None))])
        return inst.InstallAttempt.INSTALLED
    monkeypatch.setattr(inst, "install_winusb", install)

    def first(w):
        for label in ("Install Driver", "Reinstall Driver"):
            b = _button(w, label)
            if b is not None:
                b.click()
                return
        _button(w, "Close").click()
    steps = (first, lambda w: _ok_button(w).click()) if press == "first" else \
        (lambda w: _button(w, "Close").click(),)
    with ModalDriver(*steps) as drv:
        dialog._show_usb_installer()
    got = json.loads(json.dumps({"asked": asked, "installed": installed, "seen": drv.seen}))
    golden = json.loads((Path(__file__).resolve().parents[1] / "data"
                         / "instrument_drivers_beta_off_4_3_45.json").read_text(encoding="utf-8"))
    assert got == golden[f"{case}__{press}"]


def test_the_x64_build_on_an_arm64_pc_is_not_offered_an_install_for_the_table(
        dialog, on_windows, beta, monkeypatch):
    asked, installed = _hardware(monkeypatch, [_table()], arm64=True)
    buttons = []

    def look_then_close(w):
        buttons.append(_button(w, "Install Driver") or _button(w, "Reinstall Driver"))
        _button(w, "Close").click()
    with ModalDriver(look_then_close) as drv:
        dialog._show_usb_installer()
    said = drv.text_of(0)
    assert "on this Windows for ARM computer it cannot drive the table" in said
    assert "Use the ARM64 version of ChromIQ on this computer" in said
    assert "ChromIQ-Windows-arm64" in said
    assert buttons == [None]                             # no install button at all
    assert installed == []


def test_the_arm64_build_on_an_arm64_pc_lists_the_table_and_offers_its_install(
        dialog, on_windows, beta, monkeypatch):
    """2026-11-18 (the owner: Windows on ARM shall be supported): the ARM64 build on an ARM PC
    lists the table with its own button and installs for it on that button, exactly as x64."""
    asked, installed = _hardware(monkeypatch, [_pro(), _table()], arm64=True, arm64_build=True)
    with ModalDriver(lambda w: _button(w, "Install Driver for the Table").click(),
                     lambda w: _ok_button(w).click()) as drv:
        dialog._show_usb_installer()
    said = drv.text_of(0)
    assert "Windows for ARM" not in said and "Connected table:" in said
    assert [(d.vid, d.pid) for d in installed] == [TABLE]
    assert inst._choice_holds(installed[0])


def test_the_table_text_alone():
    assert sd.usb_table_text([_pro()]) == ""
    assert sd.usb_table_text([SimpleNamespace(name="x", has_winusb=False)]) == ""
    one = sd.usb_table_text([_table()], button="Install Driver for the Table")
    assert one.startswith(sd.tr("<b>Connected table:</b>"))
    assert "i1Profiler cannot use the table" in one
    assert "<b>Install Driver for the Table</b> is for the table alone" in one
    assert sd.usb_table_button_label([], True) is None
    assert sd.usb_table_button_label([_table()], True) == "Install Driver for the Table"
    assert sd.usb_table_button_label([_table(True)], True) == "Reinstall Driver for the Table"
    arm = sd.usb_table_text([], [_table()])
    assert "Windows for ARM" in arm and "i1Profiler cannot use" not in arm


def test_the_window_opens_on_its_own_only_on_windows(monkeypatch):
    built = []
    monkeypatch.setattr(sd, "_sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(sd, "SettingsDialog", lambda *a, **k: built.append(1))
    sd.open_instrument_drivers(object())
    assert built == []


def test_the_window_opens_on_its_own_as_preferences_opens_it(monkeypatch):
    shown = []

    class _Dlg:
        def __init__(self, settings, parent=None):
            self.settings, self.parent = settings, parent

        def _show_usb_installer(self):
            shown.append(self.settings)

        def deleteLater(self):
            shown.append("deleted")
    monkeypatch.setattr(sd, "_sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(sd, "SettingsDialog", _Dlg)
    sd.open_instrument_drivers("S")
    assert shown == ["S", "deleted"]


# ---- 2. START: the job's checks ------------------------------------------------------------

def _pf(table="libusb0", pro="libusb0", arm64=False, system="windows"):
    """*arm64*: the x64 build running on a Windows for ARM PC (`Preflight.x64_on_arm64`)."""
    return us.Preflight(system, {}, us.Check("ok"), us.Check("cannot_tell"), None,
                        us.Check(table), us.Check(pro), arm64)


@pytest.mark.parametrize("state", ["none", "vendor_driver", "cannot_tell"])
def test_an_arm64_pc_gets_the_truthful_message_not_an_offer(state):
    job, sim, _t = H.make_job(preflight=_pf(table=state, arm64=True))
    r = H.Person(job, sim).drive(job.open())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "usb_open_refused")
    assert r.detail["message_id"] == "M-I1IO-DRIVE-USB-NOT-ON-THIS-SYSTEM"
    assert sim.received == []


def test_an_i1pro2_without_the_driver_is_named_before_anything_is_sent():
    opened = []
    job, sim, _t = H.make_job(preflight=_pf(pro="none"))
    job._open_transport = lambda: opened.append(1)
    r = H.Person(job, sim).drive(job.open())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "driver_not_installed_for_instrument")
    assert opened == [] and sim.received == []


def test_the_table_is_named_first_when_both_lack_the_driver():
    job, sim, _t = H.make_job(preflight=_pf(table="none", pro="none"))
    r = H.Person(job, sim).drive(job.open())
    assert r.reason == "driver_not_installed_for_table"


def test_an_i1pro2_without_the_driver_on_an_arm64_pc_gets_the_truthful_message():
    job, sim, _t = H.make_job(preflight=_pf(pro="none", arm64=True))
    r = H.Person(job, sim).drive(job.open())
    assert r.detail["message_id"] == "M-I1IO-DRIVE-USB-NOT-ON-THIS-SYSTEM"


@pytest.mark.parametrize("pro", ["libusb0", "not_seen", "cannot_tell", "not_applicable"])
def test_an_i1pro2_with_the_driver_or_not_seen_is_not_refused_for_its_driver(pro):
    job, sim, _t = H.make_job(preflight=_pf(pro=pro))
    r = H.Person(job, sim).drive(job.open())
    assert r.ok, r.reason


def test_the_i1pro2_driver_is_read_like_the_window_reads_it():
    D = inst.UsbDevice
    check = us.instrument_driver_check
    assert check("macos").state == "not_applicable"
    assert check("linux").state == "not_applicable"
    assert check("windows", lambda: []).state == "not_seen"
    assert check("windows", lambda: [D("0971", "2000", "x", False)]).state == "none"
    assert check("windows", lambda: [D("0971", "2000", "x", True)]).state == "libusb0"

    def boom():
        raise OSError("registry")
    assert check("windows", boom).state == "cannot_tell"
    assert us.x64_build_on_arm64("macos") is False and us.x64_build_on_arm64("linux") is False


def test_the_preflight_records_both_drivers():
    d = _pf(table="none", pro="none", arm64=True).as_dict()
    assert d["table_driver"]["state"] == "none"
    assert d["instrument_driver"]["state"] == "none" and d["x64_on_arm64"] is True


@pytest.mark.parametrize("machine_arm,process_arm,offered", [
    (True, True, True),        # the ARM64 build on an ARM PC: offered, like x64 (2026-11-18)
    (True, False, False),      # the x64 build under emulation on an ARM PC: the truthful message
    (False, False, True),      # x64 on x64: unchanged
])
@pytest.mark.parametrize("table,pro", [("none", "libusb0"), ("libusb0", "none")])
def test_start_decides_by_the_process_not_the_machine(monkeypatch, machine_arm, process_arm,
                                                      offered, table, pro):
    """The preflight's ARM field comes from the PROCESS (`x64_build_on_arm64`), and the job
    offers the install to the ARM64 build exactly as to x64; the x64 build on an ARM PC is
    refused with M-I1IO-DRIVE-USB-NOT-ON-THIS-SYSTEM, which names the ARM64 version."""
    import core.usb_library as ul
    from workflow import measurement_messages as M
    monkeypatch.setattr(ul, "machine_is_arm64", lambda: machine_arm)
    monkeypatch.setattr(ul, "process_is_windows_arm64", lambda: process_arm)
    x64_on_arm = us.x64_build_on_arm64("windows")
    assert x64_on_arm is (machine_arm and not process_arm)
    job, sim, _t = H.make_job(preflight=_pf(table=table, pro=pro, arm64=x64_on_arm))
    r = H.Person(job, sim).drive(job.open())
    if offered:
        assert r.reason in ("driver_not_installed_for_table", "driver_not_installed_for_instrument")
    else:
        assert r.reason == "usb_open_refused"
        assert r.detail["message_id"] == "M-I1IO-DRIVE-USB-NOT-ON-THIS-SYSTEM"
        _t, body = M.M_I1IO_DRIVE_USB_NOT_ON_THIS_SYSTEM.render()
        assert "Use the ARM64 version of ChromIQ on this computer" in body
        assert "ChromIQ-Windows-arm64" in body
    assert sim.received == []


def test_the_download_named_in_the_texts_is_the_one_the_readme_offers():
    """The x64-on-ARM texts name the ARM64 download exactly as README.md does."""
    from pathlib import Path
    readme = (Path(__file__).resolve().parents[2] / "README.md").read_text(encoding="utf-8")
    assert "ChromIQ-Windows-arm64_<version>.zip" in readme


# ---- 2c. Windows lists the devices through cfgmgr32, without a USB library ------------------

PRO_ID = "USB\\VID_0971&PID_2000\\6&1A2B3C&0&1"
PRO_ID_2 = "USB\\VID_0971&PID_2000\\6&4D5E6F&0&3"
TABLE_ID = "USB\\VID_0971&PID_2004\\6&777&0&2"


@pytest.mark.parametrize("ids,state", [
    (None, "cannot_tell"),
    (set(), "no_instrument"),
    ({TABLE_ID}, "no_instrument"),
    ({PRO_ID, TABLE_ID}, "ok"),
    ({PRO_ID, PRO_ID_2, TABLE_ID}, "several_instruments"),          # two instances, same ids
    ({PRO_ID, "USB\\VID_0971&PID_2000&MI_00\\7&AAA&0&0000", TABLE_ID}, "ok"),  # its interface
    ({PRO_ID, TABLE_ID, "USB\\ROOT_HUB30\\5&2B&0&0",
      "USB\\VID_046D&PID_C52B\\5&9&0&4", "USB\\VID_05AC&PID_1234\\1"}, "ok"),  # unrelated
    ({PRO_ID, TABLE_ID, "USB\\VID_0765&PID_6008\\5&1&0&5"}, "other_instrument"),
])
def test_the_windows_list_comes_from_cfgmgr32_instances(ids, state):
    devices = us.list_devices("windows", instance_ids=ids)
    assert us.instrument_check(devices).state == state
    if devices is not None:
        assert all(set(d) == {"vid", "pid", "place", "hub", "interfaces"} for d in devices)


def test_windows_never_asks_a_usb_library_for_the_list(monkeypatch):
    """The ARM64 build has no libusb-1.0: on Windows neither the preflight's nor START's
    instrument check may need one (x64 and ARM64 alike)."""
    import core.usb_driver_installer as installer
    import core.usb_library as ul

    def boom(*a, **k):
        raise AssertionError("a USB library was asked for the Windows list")
    monkeypatch.setattr(ul, "backend", boom)
    monkeypatch.setattr(installer, "present_usb_instance_ids", lambda: {PRO_ID, TABLE_ID})
    assert us.instrument_now("win32").state == "ok"
    monkeypatch.setattr(installer, "present_usb_instance_ids", lambda: None)
    assert us.instrument_now("win32").state == "cannot_tell"


def test_linux_still_lists_through_its_library(monkeypatch):
    import core.usb_library as ul
    asked = []
    monkeypatch.setattr(ul, "backend", lambda: asked.append(1) or None)
    assert us.instrument_now("linux").state == "cannot_tell"     # no backend here
    assert asked == [1]


def test_macos_and_linux_are_not_asked_about_any_driver():
    for system in ("macos", "linux"):
        job, sim, _t = H.make_job(preflight=_pf(table="not_applicable", pro="none",
                                                system=system, arm64=True))
        assert H.Person(job, sim).drive(job.open()).ok


# ---- 2b. START: the table window's offer ---------------------------------------------------

from tests.i1io_table.test_window import open_window, settings  # noqa: E402,F401


@pytest.mark.parametrize("table,pro,title,install", [
    ("none", "libusb0", "The table does not have the driver ChromIQ uses on Windows",
     "Install the driver for the table now"),
    ("vendor_driver", "libusb0", "The table does not have the driver ChromIQ uses on Windows",
     "Install the driver for the table now"),
    ("libusb0", "none", "The i1Pro 2 does not have the driver ChromIQ uses on Windows",
     "Install the driver for the i1Pro 2 now"),
])
def test_start_offers_the_driver_and_the_install_answer_opens_the_window(
        qtbot, monkeypatch, tmp_path, settings, table, pro, title, install):  # noqa: F811
    monkeypatch.setattr(H, "OK_PREFLIGHT", _pf(table=table, pro=pro))
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings)
    assert p.drive_until("driver_offer") == "driver_offer"
    assert p.labels() == ["Not now", install]
    assert win._title.text() == title
    assert sim.sim.received == []
    p.press(install)
    qtbot.waitUntil(lambda: finished == ["install_driver"], timeout=15000)
    assert sim.sim.received == []


def test_not_now_installs_nothing_and_opens_nothing(
        qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    monkeypatch.setattr(H, "OK_PREFLIGHT", _pf(table="none"))
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings)
    assert p.drive_until("driver_offer") == "driver_offer"
    p.press("Not now")
    p.drive_until(("done",))
    p.press("Close")
    assert finished and finished[-1] != "install_driver"
    assert sim.sim.received == []


@pytest.mark.parametrize("problem,title,install", [
    ("table driver none", "The table does not have the driver ChromIQ uses on Windows",
     "Install the driver for the table now"),
    ("no-libusb0-dll", "The table's driver is installed, but ChromIQ could not use it",
     "Install the driver for the table again"),
])
def test_the_open_time_refusal_becomes_the_offer_that_fits(qtbot, monkeypatch, tmp_path,
                                                           settings, problem, title,
                                                           install):  # noqa: F811
    """The opening found the table without the driver: the same offer as before the opening.
    Review 446, W-S3: the registry said libusb0 and the opening found no libusb0.dll: NOT "the
    table does not have the driver" (the window shows it installed), its own words. Never a
    placeholder left."""
    from workflow.i1io.table import session_table as tbl
    monkeypatch.setattr(H, "OK_PREFLIGHT", _pf())
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings)
    job = sim.jobs[0]

    def refuse():
        raise tbl.NotAvailable("M-I1IO-DRIVE-TABLE-DRIVER-NOT-INSTALLED", problem=problem)
    job._open_transport = refuse
    assert p.drive_until(("driver_offer", "open_refused")) == "driver_offer"
    assert win._title.text() == title
    assert "{" not in win._title.text()
    assert p.labels() == ["Not now", install]
    assert sim.sim.received == []
    p.press(install)
    qtbot.waitUntil(lambda: finished == ["install_driver"], timeout=15000)


def test_the_file_missing_offer_agrees_with_what_the_window_will_show():
    """Review 446, W-S3, x64: Windows lists the driver, so the Instrument drivers window shows the
    table "driver installed" with "Reinstall Driver for the Table". The offer says exactly that,
    and does not say the table lacks the driver."""
    from workflow import measurement_messages as M
    window_label = sd.usb_table_button_label([_table(True)], True)
    state = sd.tr("driver installed")
    title, body = M.M_I1IO_DRIVE_TABLE_DRIVER_FILE.render(
        install="Install the driver for the table again", window="Instrument drivers",
        button=window_label)
    assert "\u201c" + window_label + "\u201d" in body
    assert "\u201c" + state + "\u201d" in body
    assert "does not have" not in title + body and "not installed" not in body
    assert "{" not in title + body and "\u2014" not in title + body
    assert not M.M_I1IO_DRIVE_TABLE_DRIVER_FILE.approved
    assert M.M_I1IO_DRIVE_TABLE_DRIVER_FILE.id in M.PROPOSED


def test_the_job_names_the_missing_file_on_x64():
    from workflow.i1io.table import session_table as tbl
    job, sim, _t = H.make_job(preflight=_pf())

    def refuse():
        raise tbl.NotAvailable(tbl.DRIVER_NOT_INSTALLED, problem="no-libusb0-dll")
    job._open_transport = refuse
    r = H.Person(job, sim).drive(job.open())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "driver_file_missing_for_table")
    assert sim.received == []


@pytest.mark.parametrize("problem", ["no-libusb0-dll", "table driver none"])
def test_the_opening_on_an_arm64_pc_never_turns_into_the_offer_in_the_job(problem):
    """Review 446, W-M1, the job's half: the registry said libusb0 and the opening still found the
    table without its driver (or its libusb0.dll missing) on a Windows for ARM computer. The job
    names the truthful message; nothing reached the table."""
    from workflow.i1io.table import session_table as tbl
    job, sim, _t = H.make_job(preflight=_pf(arm64=True))

    def refuse():
        raise tbl.NotAvailable(tbl.DRIVER_NOT_INSTALLED, problem=problem)
    job._open_transport = refuse
    r = H.Person(job, sim).drive(job.open())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "usb_open_refused")
    assert r.detail["message_id"] == "M-I1IO-DRIVE-USB-NOT-ON-THIS-SYSTEM"
    assert sim.received == []


@pytest.mark.parametrize("arm64,step,labels", [
    (True, "open_refused", ["Close"]),
    (False, "driver_offer", None),
])
def test_the_reviewers_arm64_scenario_gets_the_truthful_message_not_the_offer(
        qtbot, monkeypatch, tmp_path, settings, arm64, step, labels):  # noqa: F811
    """Review 446, W-M1, probe `test_probe_win_arm_open.py` as a test: the preflight says libusb0
    in the registry and the machine is ARM64; the opening finds no libusb0.dll. Before the fix
    the window offered "Install the driver for the table now" on ARM."""
    from workflow import measurement_messages as M
    from workflow.i1io.table import session_table as tbl
    monkeypatch.setattr(H, "OK_PREFLIGHT", _pf(arm64=arm64))
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings)
    job = sim.jobs[0]

    def refuse():
        raise tbl.NotAvailable(tbl.DRIVER_NOT_INSTALLED, problem="no-libusb0-dll")
    job._open_transport = refuse
    assert p.drive_until(("driver_offer", "open_refused")) == step
    if arm64:
        assert win._title.text() == M.M_I1IO_DRIVE_USB_NOT_ON_THIS_SYSTEM.title
        assert p.labels() == labels
        assert not any("Install" in x for x in p.labels())
    assert sim.sim.received == []


@pytest.mark.parametrize("reason", ["driver_not_installed_for_table",
                                    "driver_not_installed_for_instrument",
                                    "usb_open_refused"])
def test_every_way_into_the_offer_asks_whether_the_pc_is_arm64_first(
        qtbot, monkeypatch, tmp_path, settings, reason):  # noqa: F811
    """Review 446, W-M1, the window's half: whatever refusal reaches the window (even one a
    future job sends without its own ARM check), a Windows for ARM computer never gets the
    offer."""
    from workflow import measurement_messages as M
    monkeypatch.setattr(H, "OK_PREFLIGHT", _pf())
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings)
    win.job.preflight_seen = _pf(arm64=True)
    detail = {"message_id": "M-I1IO-DRIVE-TABLE-DRIVER-NOT-INSTALLED",
              "problem": "no-libusb0-dll"} if reason == "usb_open_refused" else {}
    win._show_open_refused(SimpleNamespace(detail=detail, reason=reason, step="open"))
    assert win._title.text() == M.M_I1IO_DRIVE_USB_NOT_ON_THIS_SYSTEM.title
    assert p.labels() == ["Close"]


def test_the_measure_tab_opens_the_driver_window_after_the_table_window_let_go(monkeypatch):
    """`_on_table_window_finished("install_driver")` opens the Instrument drivers window
    (Windows only, as Preferences); any other ending does not."""
    import inspect

    from ui.tabs import tab_measure as TM
    src = inspect.getsource(TM.TabMeasure._on_table_window_finished)
    at = src.index('if why == "install_driver":')
    assert "QTimer.singleShot(0, self._open_instrument_drivers)" in src[at:at + 900]
    # after the tab is unlocked again
    assert src.index("self.measurement_active.emit(False)") < at
    opened = []
    monkeypatch.setattr(sd, "open_instrument_drivers", lambda s, p=None: opened.append(s))
    fake = SimpleNamespace(_settings="S", window=lambda: None)
    TM.TabMeasure._open_instrument_drivers(fake)
    assert opened == ["S"]


# ---- 3. the texts ------------------------------------------------------------------------------

#: ArgyllCMS 3.5.0, doc/Installing_MSWindows.html, "Using Argyll drivers with existing OEM
#: drivers", Windows 8, 8.1, 10 & 11, word for word (review 446, W-M2): "Right click on instrument
#: -> Update Driver Software... -> let me pick from a list of device drivers on my computer
#: (Choose either the Argyll driver or another driver from the list) -> Next -> Close"
GUIDE_STEPS = ("Update Driver Software...",
               "let me pick from a list of device drivers on my computer")


def test_the_way_back_is_quoted_from_argyllcms_own_guide():
    """Review 446, W-M2: the menu names the texts quote are the guide's own, word for word. Read
    from the guide itself where ArgyllCMS is installed (this Mac has it; a machine without it
    still checks the texts against the pinned words)."""
    import html
    import re
    from pathlib import Path
    guide = Path("/Applications/Argyll/doc/Installing_MSWindows.html")
    if guide.exists():
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", guide.read_text(
            encoding="windows-1252", errors="replace"))))
        for step in GUIDE_STEPS + ("Hardware and Sound -> Device Manager",
                                   "different physical USB port for each installation"):
            assert step in text, step
    window = sd.usb_table_text([_table()], button="Install Driver for the Table")
    for step in GUIDE_STEPS:
        assert "\u201c" + step + "\u201d" in window
    assert "Control Panel > Hardware and Sound > Device Manager" in window
    assert "ChromIQ has not yet tried these steps with a table" in window
    assert "different USB port for each driver" in window


def test_the_texts_are_proposed_complete_and_say_the_way_back():
    from workflow import measurement_messages as M
    for msg, what in ((M.M_I1IO_DRIVE_TABLE_DRIVER, "the table"),
                      (M.M_I1IO_DRIVE_I1PRO2_DRIVER, "the i1Pro 2")):
        assert not msg.approved and msg.id in M.PROPOSED
        title, body = msg.render(install="Install it", window="Instrument drivers",
                                 button="Its button")
        for text in (title, body):
            assert "{" not in text and "\u2014" not in text
        assert "i1Profiler cannot use " + what in body
        assert "right-click " + what in body
        for step in GUIDE_STEPS:
            assert "\u201c" + step + "\u201d" in body
        assert "ArgyllCMS's installation guide describes the way back for instruments" in body
        assert "install X-Rite's own driver" not in body           # not documented by the guide
        assert "\u201cIts button\u201d" in body
        assert "Nothing was sent to the table" in body
        assert "not offered in this beta" not in body
    _t, table_body = M.M_I1IO_DRIVE_TABLE_DRIVER.render(install="i", window="w", button="b")
    assert "ChromIQ has not yet tried these steps with a table" in table_body


def test_the_german_texts_exist():
    from core import i18n
    from workflow import measurement_messages as M
    cat = i18n._load_catalog("de") if hasattr(i18n, "_load_catalog") else None
    if cat is None:
        import json
        from pathlib import Path
        cat = json.loads((Path(__file__).resolve().parents[2] / "data" / "i18n" / "de.json")
                         .read_text(encoding="utf-8"))
    for msg in (M.M_I1IO_DRIVE_TABLE_DRIVER, M.M_I1IO_DRIVE_I1PRO2_DRIVER):
        assert msg.title in cat and msg.body in cat
    for s in ("Install the driver for the table now", "Install the driver for the i1Pro 2 now"):
        assert s in cat
