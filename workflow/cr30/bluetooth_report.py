"""A Bluetooth diagnostic the user can run from inside ChromIQ.

WHY IT LIVES IN THE APP AND NOT ONLY IN A SCRIPT. Most people meet ChromIQ as a
bundled application: `bleak` and its per-platform backend are inside that bundle
(`ChromIQ.spec`), where a system `python` cannot see them. Asking such a user to
install Python and pip a library, to diagnose a feature they already own, is a
wall — and it would test a DIFFERENT bleak from the one that is failing. This
runs the app's own stack, which is the one under suspicion.

It answers, in order, the three questions a "it will not connect" report cannot:

  1. does this computer's Bluetooth work at all, and what does it see;
  2. is anything advertising the service a CR30 offers;
  3. does ChromIQ's OWN discovery accept it -- the same call the Measure tab
     makes, so a difference between 2 and 3 is a ChromIQ problem and not a
     driver one.

It never sends a calibration command and never asks an instrument to measure.
Stage 3 sends the one status frame `ble.discover(verify=True)` already sends.
"""
from __future__ import annotations

import datetime
import platform
import sys

#: Names of devices that are NOT candidates are redacted. A scan is a list of
#: what is switched on around somebody -- their phone, their television, their
#: neighbours' -- and this file is written to be sent to a stranger.
_REDACTED = "(named device, hidden)"


def _bleak_version() -> str:
    try:
        import bleak                                    # noqa: F401
    except ImportError as exc:
        return f"NOT AVAILABLE ({exc})"
    try:
        from importlib.metadata import version
        return version("bleak")
    except Exception:                                   # noqa: BLE001
        # Some releases define no __version__ and ship no metadata under that
        # name. Importing is the test; the number is a nicety, and reporting
        # "not installed" because a version string is missing sends the reader
        # to fix something that is not broken.
        return "present (version unknown)"


class Report:
    """What the diagnostic found: the text to send, and what it CONFIRMED.

    The confirmed list is separate from the text on purpose. It is what makes a
    repair possible -- an address here has answered as a CR30, not merely
    advertised the right service -- and the difference between those two is the
    whole reason `ble.discover` takes a `verify` flag.
    """

    def __init__(self, text: str = "", confirmed: "list | None" = None) -> None:
        self.text = text
        self.confirmed = list(confirmed or [])


async def collect(scan_seconds: float = 20.0) -> "Report":
    """Run the three stages and return the report."""
    out: list[str] = []
    found_confirmed: list = []

    def say(line: str = "") -> None:
        out.append(line)

    say("ChromIQ — CR30 Bluetooth report")
    say("=" * 62)
    say(f"when    : {datetime.datetime.now().isoformat(timespec='seconds')}")
    say(f"system  : {platform.system()} {platform.release()} "
        f"({platform.machine()})")
    say(f"python  : {sys.version.split()[0]}")
    say(f"bleak   : {_bleak_version()}")
    try:
        from core.version import APP_VERSION
        say(f"ChromIQ : {APP_VERSION}")
    except Exception:                                   # noqa: BLE001
        pass
    say("")

    # ---- 1. can this machine scan at all? ------------------------------
    say("1. What this computer's Bluetooth can see")
    say("-" * 62)
    try:
        from bleak import BleakScanner
        found = await BleakScanner.discover(timeout=scan_seconds,
                                            return_adv=True)
    except Exception as exc:                            # noqa: BLE001
        say(f"THE SCAN ITSELF FAILED: {type(exc).__name__}: {exc}")
        say("")
        say("This is a finding, not a dead end: Bluetooth could not be started")
        say("at all, so nothing about the instrument is in question yet. Check")
        say("that Bluetooth is switched on for this computer, and that ChromIQ")
        say("is allowed to use it — on macOS that is a permission prompt, on")
        say("Windows a privacy setting.")
        return Report("\n".join(out), found_confirmed)

    items = list(found.items()) if isinstance(found, dict) else [
        (d.address, (d, None)) for d in found]
    candidates: list[tuple[str, str]] = []
    say(f"{len(items)} Bluetooth LE device(s) visible in {scan_seconds:.0f} s:")
    for addr, pair in items:
        dev, adv = pair if isinstance(pair, tuple) else (pair, None)
        uuids = [str(u) for u in (getattr(adv, "service_uuids", None) or [])]
        name = (getattr(adv, "local_name", None)
                or getattr(dev, "name", None) or "(no name)")
        rssi = getattr(adv, "rssi", None)
        if any(u.lower().startswith("0000ffe0") for u in uuids):
            say(f"  {name:26s} {addr}  rssi={rssi}   <-- offers the CR30's service")
            say(f"      services: {', '.join(uuids)}")
            candidates.append((name, str(addr)))
        else:
            shown = _REDACTED if name != "(no name)" else "(no name)"
            say(f"  {shown:26s} …{str(addr)[-6:]}  rssi={rssi}  "
                f"services={len(uuids)}")
    say("")

    # ---- 2. anything that could be an instrument? ----------------------
    say("2. Is anything advertising the CR30's service")
    say("-" * 62)
    if not candidates:
        say("NOTHING. That is the most useful line in this report.")
        say("")
        say("Your computer never saw a device offering the service ChromIQ")
        say("looks for, so the problem is before ChromIQ rather than inside it.")
        say("")
        say("There is NO Bluetooth on/off setting on a CR30 — it is on from the")
        say("moment it leaves the box — so this is not a setting anybody got")
        say("wrong. The likely causes, in order:")
        say("  * the instrument is asleep. Press its button once and run this")
        say("    again straight away.")
        say("  * something else is holding it. It accepts ONE connection at a")
        say("    time and stops advertising while the phone app, or another")
        say("    computer, has it.")
        say("  * this computer's Bluetooth is off, or ChromIQ is not permitted")
        say("    to use it.")
        say("")
        say("WATCH THE INSTRUMENT'S OWN SCREEN while this runs: an indicator")
        say("appears there when a computer asks to connect. If nothing ever")
        say("shows on the display, the request is not reaching the instrument.")
        return Report("\n".join(out), found_confirmed)
    say(f"{len(candidates)} device(s) could be a CR30 (the service is generic —")
    say("hobby Bluetooth-to-serial modules use it too, so this is a shortlist).")
    say("")

    # ---- 3. does ChromIQ's own discovery accept it? --------------------
    say("3. What ChromIQ's own discovery makes of them")
    say("-" * 62)
    say("This is the same call the Measure tab makes. It connects and asks each")
    say("candidate for its wavelength range; a CR30 answers 400 nm, 10 nm steps,")
    say("31 bands. Nothing here can make an instrument measure or calibrate.")
    say("")
    try:
        from . import ble
        accepted = await ble.discover(timeout=15.0, verify=True)
    except Exception as exc:                            # noqa: BLE001
        say(f"DISCOVERY RAISED: {type(exc).__name__}: {exc}")
        say("")
        say("Something was advertising, but ChromIQ could not complete its")
        say("check. That points at ChromIQ or at the connection, NOT at a")
        say("missing instrument — please send this report.")
        return Report("\n".join(out), found_confirmed)

    # READ THE CONFIRMED FLAG, DO NOT JUST COUNT THE LIST. `ble.discover`
    # returns candidates whether or not the protocol check confirmed them --
    # the shortlist and the identification are different things, which is the
    # whole reason `verify=True` exists. Counting the list told a user with an
    # UNCONFIRMED hobby gadget that "the instrument is reachable", and told a
    # user whose instrument merely fell asleep between the two scans that
    # ChromIQ had "REFUSED" it. Both are the opposite of the truth, in a report
    # whose only job is to say which of those two things happened.
    confirmed = [c for c in accepted if c.get("confirmed")]
    found_confirmed = confirmed
    if accepted and not confirmed:
        say(f"{len(accepted)} device(s) advertise the service, and NONE of them")
        say("answered as a CR30 when asked.")
        say("")
        say("So something nearby is using the same generic Bluetooth service --")
        say("hobby modules do -- or an instrument is there and did not answer")
        say("the way ChromIQ expects. The second would be OUR bug. Either way")
        say("this report is worth sending; it is the case we cannot tell apart")
        say("from here.")
        for c in accepted:
            say(f"  unconfirmed: {c}")
    elif not accepted:
        # NOT A REFUSAL. An empty list here means ChromIQ's own scan, twenty
        # seconds after the first one, saw nothing advertising at all -- so
        # nothing was asked and nothing was refused. Saying "REFUSED" sent the
        # reader after a rejection that never happened. The likely sequence is
        # much duller and much more actionable: the device went to sleep, or
        # something claimed it, between the two scans.
        say("Something was advertising a moment ago, and by the time ChromIQ")
        say("looked again it was gone.")
        say("")
        say("Nothing was refused here — there was simply nothing left to ask.")
        say("Between the two scans, about twenty seconds apart, the device")
        say("stopped advertising. The two usual reasons:")
        say("  * it went to sleep. Press the instrument's button to wake it and")
        say("    run this again straight away.")
        say("  * something claimed it — the phone app, or another computer. A")
        say("    CR30 accepts one connection at a time and stops advertising")
        say("    while it is held.")
        say("")
        say("If you press the button and run this again immediately and it")
        say("still happens, please send the report: an instrument that will not")
        say("stay visible long enough to be asked is worth us knowing about.")
    else:
        say(f"ChromIQ CONFIRMED {len(confirmed)} instrument(s):")
        for c in confirmed:
            say(f"  {c}")
        say("")
        say("So the instrument is reachable over Bluetooth from this computer.")
        say("If measuring still fails, the problem is later than the connection")
        say("and this report is still worth sending.")
    return Report("\n".join(out), found_confirmed)
