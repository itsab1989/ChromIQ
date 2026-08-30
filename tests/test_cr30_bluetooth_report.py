"""The in-app Bluetooth diagnostic must be safe, honest and sendable.

A CR30 owner on Windows cannot connect and has no error text to give us. This
report is what he runs instead. Three properties matter more than its wording:

* it must never disturb his instrument;
* it must not publish his neighbours' devices, because it is written to be sent
  to a stranger;
* it must not tell him a library is missing when it is there — an earlier
  version did exactly that, because that release of `bleak` defines no
  `__version__`, and it would have sent him to install what he already had.
"""
import asyncio

import pytest

from workflow.cr30 import bluetooth_report as br


def test_it_reports_bleak_as_present(monkeypatch):
    """The import is the test, not the version string."""
    assert "NOT AVAILABLE" not in br._bleak_version()


def test_a_missing_library_is_still_reported(monkeypatch):
    import builtins
    real = builtins.__import__

    def fake(name, *a, **k):
        if name == "bleak":
            raise ImportError("no module named bleak")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake)
    assert "NOT AVAILABLE" in br._bleak_version()


def _run(monkeypatch, devices, accepted=()):
    """Drive the real `collect()` with only the scanner faked."""
    class _Adv:
        def __init__(self, name, uuids, rssi=-50):
            self.local_name, self.service_uuids, self.rssi = name, uuids, rssi

    class _Dev:
        def __init__(self, addr, name):
            self.address, self.name = addr, name

    found = {addr: (_Dev(addr, name), _Adv(name, uuids))
             for addr, name, uuids in devices}

    class _Scanner:
        @staticmethod
        async def discover(timeout=0.0, return_adv=False):
            return found

    import bleak
    monkeypatch.setattr(bleak, "BleakScanner", _Scanner)
    from workflow.cr30 import ble
    monkeypatch.setattr(ble, "discover",
                        lambda *a, **k: asyncio.sleep(0, result=list(accepted)))
    return asyncio.new_event_loop().run_until_complete(br.collect(0.0)).text


FFE0 = "0000ffe0-0000-1000-8000-00805f9b34fb"


def test_a_bystanders_name_is_never_written(monkeypatch):
    """His phone, his television, his neighbours' — none of it helps anyone."""
    text = _run(monkeypatch, [
        ("AA:BB:CC:DD:EE:01", "Someone's iPhone", []),
        ("AA:BB:CC:DD:EE:02", "Living Room TV", ["0000180f-0000-1000-8000-00805f9b34fb"]),
    ])
    assert "iPhone" not in text
    assert "Living Room" not in text
    assert br._REDACTED in text


def test_a_candidate_IS_named(monkeypatch):
    """The one device that might be the instrument must be identifiable, or the
    report cannot be acted on."""
    text = _run(monkeypatch, [("AA:BB:CC:DD:EE:03", "CR30-XYZ", [FFE0])])
    assert "CR30-XYZ" in text
    assert "AA:BB:CC:DD:EE:03" in text


def test_seeing_nothing_says_so_plainly_and_does_not_blame_a_setting(monkeypatch):
    """There is no Bluetooth on/off control on a CR30, so advice to check one
    would send the reader hunting for something that does not exist."""
    text = _run(monkeypatch, [("AA:BB:CC:DD:EE:04", "Someone's iPhone", [])])
    assert "NOTHING" in text
    assert "no Bluetooth on/off setting" in text.lower() or \
           "NO Bluetooth on/off setting" in text
    assert "screen" in text.lower(), "the instrument's own display is the clue"


def test_a_failed_scan_is_a_finding_not_a_crash(monkeypatch):
    class _Boom:
        @staticmethod
        async def discover(timeout=0.0, return_adv=False):
            raise OSError("the adapter is not available")

    import bleak
    monkeypatch.setattr(bleak, "BleakScanner", _Boom)
    text = asyncio.new_event_loop().run_until_complete(br.collect(0.0)).text
    assert "THE SCAN ITSELF FAILED" in text
    assert "OSError" in text


def test_it_opens_no_connection_of_its_own(monkeypatch):
    """The safety property, tested by BEHAVIOUR rather than by grepping.

    A first version of this searched the source for the word "calibrate" — a
    test of the file's shape, not of what it does, and it failed on the
    docstring that promises never to calibrate. What actually matters is that
    this module opens no connection itself: the ONE connection in the whole
    report is made inside `ble.discover(verify=True)`, whose single status
    frame is covered where that code lives. So a `BleakClient` constructed
    here at all is the fault.
    """
    import bleak

    class _Forbidden:
        def __init__(self, *a, **k):
            raise AssertionError(
                "the diagnostic opened its own connection to an instrument")

    monkeypatch.setattr(bleak, "BleakClient", _Forbidden)
    text = _run(monkeypatch, [("AA:BB:CC:DD:EE:05", "CR30-XYZ", [FFE0])])
    assert "ChromIQ's own discovery" in text or "discovery" in text.lower()


# -- the verdict must read the flag, not count the list ---------------------

def test_an_unconfirmed_gadget_is_not_called_an_instrument(monkeypatch):
    """`ble.discover` returns the SHORTLIST, confirmed or not — that is what
    `verify` is for. Counting the list told a user with a hobby module that
    "the instrument is reachable", which is the opposite of the truth in the
    one report whose whole job is to tell those two cases apart."""
    text = _run(monkeypatch,
                [("AA:BB:CC:DD:EE:06", "HM-10", [FFE0])],
                accepted=[{"name": "HM-10", "address": "AA:BB:CC:DD:EE:06",
                           "confirmed": False}])
    assert "CONFIRMED 1" not in text
    assert "reachable over Bluetooth" not in text
    assert "NONE of them" in text
    assert "unconfirmed" in text


def test_a_confirmed_instrument_is_reported_as_reachable(monkeypatch):
    text = _run(monkeypatch,
                [("AA:BB:CC:DD:EE:07", "CR30-XYZ", [FFE0])],
                accepted=[{"name": "CR30-XYZ", "address": "AA:BB:CC:DD:EE:07",
                           "confirmed": True}])
    assert "CONFIRMED 1" in text
    assert "reachable over Bluetooth" in text


def test_an_empty_rescan_is_not_reported_as_a_refusal(monkeypatch):
    """The instrument can fall asleep or be claimed between the two scans. That
    is not ChromIQ refusing it, and saying so sends the reader after the wrong
    thing entirely."""
    text = _run(monkeypatch, [("AA:BB:CC:DD:EE:08", "CR30-XYZ", [FFE0])],
                accepted=[])
    # THIS TEST USED TO ASSERT THE BUG. It required "REFUSED every candidate" —
    # the very wording its own docstring calls wrong — and its guard against
    # "judged and rejected" passed only because that phrase happened to wrap
    # across a line break in the source text. A green test holding the fault in
    # place, in the diagnostic written for the user waiting on it.
    assert "REFUSED" not in text
    assert "nothing was refused" in text.lower()
    assert "went to sleep" in text
    flat = " ".join(text.split())          # defeat the line-wrap loophole
    assert "did not answer as a CR30" not in flat


# -- the repair: only ever a CONFIRMED address ------------------------------

class _Tab:
    """Enough MainWindow for the real repair method to run."""

    def __init__(self, choice):
        from ui.main_window import MainWindow
        self._offer = MainWindow._offer_cr30_bluetooth_repair.__get__(self)
        self.stored = {}
        self._choice = choice

    class _Settings:
        def __init__(self, store): self._store = store
        def set(self, k, v): self._store[k] = v

    @property
    def _settings(self):
        return _Tab._Settings(self.stored)


def _run_repair(monkeypatch, confirmed, choice):
    """Drive the REAL method with only the message box faked."""
    import ui.main_window as mw

    class _Box:
        Icon = type("I", (), {"NoIcon": 0})
        ButtonRole = type("R", (), {"AcceptRole": 0, "DestructiveRole": 1,
                                    "RejectRole": 2})
        StandardButton = type("S", (), {"Ok": 1})

        def __init__(self, *a, **k):
            self._buttons = {}
            self._clicked = None
        def setIcon(self, *a): pass
        def setWindowTitle(self, *a): pass
        def setText(self, *a): pass
        def setInformativeText(self, t): self.informative = t
        def addButton(self, label, role):
            b = object()
            self._buttons[label] = b
            if choice and choice in str(label):
                self._clicked = b
            return b
        def setDefaultButton(self, *a): pass
        def setStandardButtons(self, *a): pass
        def exec(self): return 0
        def clickedButton(self): return self._clicked

    monkeypatch.setattr(mw, "QMessageBox", _Box, raising=False)
    import PyQt6.QtWidgets as qtw
    monkeypatch.setattr(qtw, "QMessageBox", _Box)
    monkeypatch.setattr("ui.widgets.fit_message_box_buttons", lambda *a: None)
    t = _Tab(choice)
    t._offer(confirmed)
    return t.stored


KEY = "cr30_ble_address"


def test_nothing_is_offered_when_nothing_was_confirmed(monkeypatch):
    """The whole safety of this rests on it: an advertiser that did not answer
    as a CR30 must never reach the setting — that is the fault where the next
    frames written to a stranger were calibration commands."""
    assert _run_repair(monkeypatch, [], "Go straight") == {}


def test_accepting_stores_the_confirmed_address(monkeypatch):
    stored = _run_repair(
        monkeypatch,
        [{"name": "CR30", "address": "AA:BB:CC:DD:EE:09", "confirmed": True}],
        "Go straight")
    assert stored.get(KEY) == "AA:BB:CC:DD:EE:09"


def test_it_can_be_undone_from_the_same_window(monkeypatch):
    """A repair the user cannot reverse is a trap, so 'Search normally' clears
    it — and the window says so."""
    stored = _run_repair(
        monkeypatch,
        [{"name": "CR30", "address": "AA:BB:CC:DD:EE:10", "confirmed": True}],
        "Search normally")
    assert stored.get(KEY) == ""


def test_declining_changes_nothing(monkeypatch):
    stored = _run_repair(
        monkeypatch,
        [{"name": "CR30", "address": "AA:BB:CC:DD:EE:11", "confirmed": True}],
        None)
    assert stored == {}


def test_the_offer_still_asks_for_the_report(monkeypatch):
    """A workaround that quietly makes an install work means we never hear about
    the case and the real fault is never fixed."""
    import ui.main_window as mw
    captured = {}

    class _Box:
        Icon = type("I", (), {"NoIcon": 0})
        ButtonRole = type("R", (), {"AcceptRole": 0, "DestructiveRole": 1,
                                    "RejectRole": 2})
        def __init__(self, *a, **k): pass
        def setIcon(self, *a): pass
        def setWindowTitle(self, *a): pass
        def setText(self, *a): pass
        def setInformativeText(self, t): captured["text"] = t
        def addButton(self, *a): return object()
        def setDefaultButton(self, *a): pass
        def exec(self): return 0
        def clickedButton(self): return None

    monkeypatch.setattr(mw, "QMessageBox", _Box, raising=False)
    import PyQt6.QtWidgets as qtw
    monkeypatch.setattr(qtw, "QMessageBox", _Box)
    monkeypatch.setattr("ui.widgets.fit_message_box_buttons", lambda *a: None)
    _Tab(None)._offer([{"name": "CR30", "address": "X", "confirmed": True}])
    assert "send the report" in captured.get("text", "")
