"""What a CR30 says about itself: model, serial, internal id, versions.

Beta 17 (Basti, 2026-10-09): log it at every connect, so a bug report can say
which unit and which firmware it came from, and mark it when the firmware is
not the one ChromIQ was tested with. NOTHING about it goes on screen: there is
no way for an owner to update the firmware, so a note would only worry people.

Two sources, one shape (docs/cr30_reports/56_device_info_and_vendor_protocol.md):

* **USB** -- the identity query ChromIQ already sends (`AA 0A 00..03`), parsed
  by :mod:`.identity`. Nothing new is sent.
* **Bluetooth** -- the vendor app's read-only device-info command `BB 12 01`,
  whose 200-byte reply was read from Basti's unit on 2026-10-09 in 0.3 s
  (`scripts/cr30_devinfo.py`). Offsets as the vendor app decodes them:
  code u16 LE @5, internal id @7, model @37, serial @67, software @97,
  hardware @127; byte-sum checksum last.

Pure decoding: no I/O, no Qt, no bleak. The one exception is
:func:`remember_last` / :func:`last_connected`, which keep the last unit's
details in the settings so the CR30 Bluetooth report can name it.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field

log = logging.getLogger(__name__)

#: The firmware ChromIQ's CR30 support was built and tested against (Basti's
#: unit, 2026-10-09). Over USB it arrives in two halves, `V11.3.` and the
#: build `0.0.20231219`; over Bluetooth as one string.
TESTED_SOFTWARE = "V11.3.0.0.20231219"
TESTED_HARDWARE = "V10.0.0.0"

#: Length of the `BB 12 01` reply, checksum included.
BLE_REPLY_LEN = 200
BLE_REPLY_HDR = b"\xbb\x12"

#: Where the last connected unit's details are kept for a bug report.
LAST_DEVICE_KEY = "cr30_last_device_info"


@dataclass
class DeviceInfo:
    transport: str = ""
    model: str = ""
    serial: str = ""
    internal_id: str = ""
    software: str = ""
    hardware: str = ""
    device_code: "int | None" = None
    #: Where each field came from, for a report that has to be believed.
    source: str = ""
    when: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def tested_firmware(self) -> bool:
        """True when the software version is the one ChromIQ was tested with.

        An unknown version is NOT reported as different: only a version the
        unit actually stated can differ from anything.
        """
        return not self.software or _norm(self.software) == _norm(TESTED_SOFTWARE)

    def summary(self) -> str:
        """One line for the log and the report. English, like the log."""
        via = {"usb": "USB", "ble": "Bluetooth"}.get(self.transport,
                                                    self.transport or "?")
        return (f"CR30 connected over {via}: model {self.model or '?'}, "
                f"serial {self.serial or '?'}, internal id "
                f"{self.internal_id or '?'}, software {self.software or '?'}, "
                f"hardware {self.hardware or '?'}")


def _norm(v: str) -> str:
    return "".join(str(v or "").split()).rstrip(".").upper()


def _text(b: bytes) -> str:
    nul = b.find(b"\x00")
    raw = b if nul < 0 else b[:nul]
    # Printable ASCII only: the protocol's fields are ASCII by definition, so
    # anything else is padding or damage, and it is dropped, never guessed at.
    return bytes(c for c in raw if 32 <= c < 127).decode("ascii").strip()


def from_identity(ident, transport: str = "usb") -> DeviceInfo:
    """Build from the USB identity :mod:`.identity` already parses.

    `version_a` is `V11.3.` and `build` is `0.0.20231219`; together they are
    the software version the Bluetooth reply states in one piece (doc 56 §1),
    so they are joined here and the two transports compare alike.
    """
    va = (getattr(ident, "version_a", "") or "").strip()
    build = (getattr(ident, "build", "") or "").strip()
    if va and build:
        software = va + build if va.endswith(".") else f"{va}.{build}"
    else:
        software = va or build
    code = None
    raw0 = (getattr(ident, "raw", {}) or {}).get(0)
    if raw0:
        try:
            b = bytes.fromhex(raw0)
            code = b[7] | (b[8] << 8)
        except (ValueError, IndexError):
            code = None
    return DeviceInfo(
        transport=transport,
        model=(getattr(ident, "model", "") or "").strip(),
        serial=(getattr(ident, "second_id", "") or "").strip(),
        internal_id=(getattr(ident, "device_id", "") or "").strip(),
        software=software,
        hardware=(getattr(ident, "version_b", "") or "").strip(),
        device_code=code,
        source="USB identity AA 0A 00..03")


class DeviceInfoError(ValueError):
    """A `BB 12 01` reply that cannot be trusted."""


def ble_reply_complete(buf: bytes) -> bool:
    """Is a whole, checksummed `BB 12 01` reply in *buf*? Never raises."""
    try:
        return _find_reply(bytes(buf)) is not None
    except Exception:            # noqa: BLE001 — a predicate, never a fault
        return False


def _find_reply(buf: bytes) -> "bytes | None":
    """The first complete reply in *buf*, looked for by its header so that a
    straggler in front of it (a 10-byte `bb 01` hello) cannot shift the
    offsets. None when there is none yet."""
    i = buf.find(BLE_REPLY_HDR)
    while i >= 0:
        w = buf[i:i + BLE_REPLY_LEN]
        if len(w) == BLE_REPLY_LEN and (sum(w[:-1]) & 0xFF) == w[-1]:
            return w
        i = buf.find(BLE_REPLY_HDR, i + 1)
    return None


def parse_ble_reply(buf: bytes) -> DeviceInfo:
    """Decode a `BB 12 01` reply, or raise :class:`DeviceInfoError`."""
    w = _find_reply(bytes(buf))
    if w is None:
        raise DeviceInfoError(
            f"no complete device-info reply in {len(buf)} bytes")
    return DeviceInfo(
        transport="ble",
        device_code=w[5] | (w[6] << 8),
        internal_id=_text(w[7:37]),
        model=_text(w[37:67]),
        serial=_text(w[67:97]),
        software=_text(w[97:127]),
        hardware=_text(w[127:157]),
        source="Bluetooth device info BB 12 01",
        extra={"neutral": w[159] == 1})


def build_ble_reply(*, code: int = 793, internal_id: str = "PT694D01E7",
                    model: str = "CR30", serial: str = "CM454M0223",
                    software: str = TESTED_SOFTWARE,
                    hardware: str = TESTED_HARDWARE) -> bytes:
    """A reply shaped the way the vendor app decodes it. For simulated
    transports and tests: it is built from the decoder's offsets, not read
    from a device."""
    d = bytearray(BLE_REPLY_LEN)
    d[0:5] = bytes([0xBB, 0x12, 0x01, 0x56, 0x00])
    d[5:7] = int(code).to_bytes(2, "little")
    for off, s in ((7, internal_id), (37, model), (67, serial),
                   (97, software), (127, hardware)):
        b = s.encode("ascii")[:29]
        d[off:off + len(b)] = b
    d[-1] = sum(d[:-1]) & 0xFF
    return bytes(d)


def log_connect(info: DeviceInfo) -> None:
    """The line a bug report needs, and the mark when the firmware is new."""
    log.info("%s", info.summary())
    if not info.tested_firmware:
        log.warning("CR30: this unit's software version %s is not the one "
                    "ChromIQ was tested with (%s). Readings are taken the "
                    "same way; if something behaves oddly, mention this line "
                    "in the report.", info.software, TESTED_SOFTWARE)


def remember_last(info: DeviceInfo) -> None:
    """Keep the last connected unit's details for the Bluetooth report."""
    try:
        import datetime
        from core.settings import AppSettings
        d = asdict(info)
        d["when"] = datetime.datetime.now().isoformat(timespec="seconds")
        AppSettings().set(LAST_DEVICE_KEY, json.dumps(d))
    except Exception:            # noqa: BLE001 — never fail an open over it
        log.debug("could not remember the CR30's details", exc_info=True)


def last_connected() -> "DeviceInfo | None":
    """The last unit ChromIQ connected to on this computer, if any."""
    try:
        from core.settings import AppSettings
        raw = str(AppSettings().get(LAST_DEVICE_KEY, "") or "")
        if not raw:
            return None
        d = json.loads(raw)
        if not isinstance(d, dict):
            return None
        known = {k: d[k] for k in DeviceInfo.__dataclass_fields__ if k in d}
        return DeviceInfo(**known)
    except Exception:            # noqa: BLE001 — a report line, never a fault
        log.debug("could not read the last CR30's details", exc_info=True)
        return None


def report_lines() -> "list[str]":
    """The block the CR30 Bluetooth report opens with."""
    info = last_connected()
    if info is None:
        return ["last CR30 : none connected on this computer yet"]
    via = {"usb": "USB", "ble": "Bluetooth"}.get(info.transport,
                                                info.transport or "?")
    lines = [f"last CR30 : connected {info.when or '?'} over {via}",
             f"  model    : {info.model or '?'}",
             f"  serial   : {info.serial or '?'}",
             f"  internal : {info.internal_id or '?'}",
             f"  software : {info.software or '?'}"
             + ("" if info.tested_firmware
                else f"  (ChromIQ was tested with {TESTED_SOFTWARE})"),
             f"  hardware : {info.hardware or '?'}"]
    return lines
