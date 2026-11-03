# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only access to instrument-supplied sensor characterization.

This is distinct from the main-controller 0x0001 block used by the pre-scan.
Only observed sensor record reads are encoded. No EEPROM-writing
operation is exposed and no instrument-specific coefficients are bundled.
"""
from dataclasses import dataclass
import hashlib
import struct

from .protocol import ProtocolError


SENSOR_FACTORY_COMMAND = 0x206
SENSOR_FACTORY_KIND = 7
SENSOR_FACTORY_SIZE = 2512
# Byte lengths are wire-format facts, not calibration coefficients.
RECORD_SIZES = {0: 28, 1: 8000, 2: 8000, 3: 8000, 4: 8000, 5: 8000,
                6: 2240, 7: SENSOR_FACTORY_SIZE, 8: 8000, 9: 3436, 10: 16}


def sensor_factory_request(kind=SENSOR_FACTORY_KIND):
    """Sensor command 6, read flag 0; no data to write."""
    if type(kind) is not int or kind not in RECORD_SIZES:
        raise ValueError('Unsupported sensor factory record kind')
    return struct.pack('<IBB', SENSOR_FACTORY_COMMAND, 0, kind)


@dataclass(frozen=True)
class SensorFactoryRecord:
    raw: bytes
    kind: int = SENSOR_FACTORY_KIND

    def __post_init__(self):
        if type(self.kind) is not int or self.kind not in RECORD_SIZES:
            raise ValueError('Unsupported sensor factory record kind')
        if not isinstance(self.raw, bytes) or len(self.raw) != RECORD_SIZES[self.kind]:
            raise ValueError('Require the complete sensor factory record')

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()

    @classmethod
    def from_reply(cls, reply, kind=SENSOR_FACTORY_KIND):
        sensor_factory_request(kind)
        if len(reply) != 12 + RECORD_SIZES[kind]:
            raise ProtocolError('Sensor factory reply has an unexpected size')
        command, result, sensor_result, received_kind, reserved = struct.unpack_from('<IIBBH', reply)
        if (command, result, sensor_result, received_kind, reserved) != (
            SENSOR_FACTORY_COMMAND, 0, 0, kind, 0
        ):
            raise ProtocolError('Sensor factory request failed or returned another record')
        return cls(bytes(reply[12:]), kind)


@dataclass(frozen=True)
class FactoryCharacterization:
    """Integrity-checked device snapshot, not a spectral conversion model.

    Records 1..6 form one section with a checksum at its end. Record contents
    remain opaque until their coefficient semantics are established. ``sha256``
    identifies the complete snapshot, including records 8 and 9 which have
    changed after normal measurement. ``verified_sections_sha256`` covers only
    checksum-verified sections. Neither hash is a decoded unit identity or a
    spectral calibration certificate.
    """
    records: tuple

    def __post_init__(self):
        records = tuple(self.records)
        if any(not isinstance(r, SensorFactoryRecord) for r in records):
            raise ValueError('Require typed sensor factory records')
        by_kind = {r.kind: r for r in records}
        if len(by_kind) != len(records) or set(by_kind) != set(RECORD_SIZES):
            raise ValueError('Require every sensor factory record exactly once')
        object.__setattr__(self, 'records', tuple(by_kind[k] for k in sorted(by_kind)))
        sections = [(0,), (1, 2, 3, 4, 5, 6), (7,), (10,)]
        for kinds in sections:
            data = b''.join(by_kind[k].raw for k in kinds)
            stored = struct.unpack_from('<I', data, len(data)-4)[0]
            expected = (~sum(data[:-4])) & 0xffffffff
            if stored != expected:
                raise ProtocolError(f'Sensor factory checksum failed for records {kinds}')

    @property
    def sha256(self):
        """Full snapshot fingerprint; may change after ordinary measurement."""
        framed = b''.join(struct.pack('<II', r.kind, len(r.raw))+r.raw for r in self.records)
        return hashlib.sha256(framed).hexdigest()

    @property
    def verified_sections_sha256(self):
        """Fingerprint of checked records, excluding unverified records 8/9.

        Observed unchanged across the controlled acquisitions on one unit.
        Recharacterization or firmware changes may legitimately change it.
        It must not be treated as a serial number or conversion profile.
        """
        framed = b''.join(struct.pack('<II', r.kind, len(r.raw))+r.raw
                          for r in self.records if r.kind not in (8, 9))
        return hashlib.sha256(framed).hexdigest()

    @property
    def primary_data(self):
        """Joined record-1..6 data, with its verified checksum removed."""
        return b''.join(self.records[k].raw for k in range(1, 7))[:-4]
