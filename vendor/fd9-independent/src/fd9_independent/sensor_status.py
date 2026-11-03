# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only spectral-sensor status, distinct from controller sheet status.

State and calibration fields remain numeric observations. They do not certify
measurement readiness, calibration validity or an ISO measurement condition.
"""
from dataclasses import dataclass
import struct

from .protocol import ProtocolError

COMMAND = 0x200


def sensor_status_request():
    return struct.pack('<I', COMMAND)


@dataclass(frozen=True)
class SensorStatus:
    control_state: int
    calculation_state: int
    measurement_sum_count: int
    fatal_error: int
    warning: int
    calibration_result: int

    @classmethod
    def from_reply(cls, reply):
        if len(reply) < 8 or struct.unpack_from('<I', reply)[0] != COMMAND:
            raise ProtocolError('Unexpected sensor status reply')
        result = struct.unpack_from('<I', reply, 4)[0]
        if result:
            raise ProtocolError(f'Sensor status command failed: {result}')
        if len(reply) != 24:
            raise ProtocolError('Sensor status has an unexpected size')
        # This payload has no nested result byte. Its first byte is state,
        # unlike cached-data and factory-record responses.
        return cls(*struct.unpack_from('<BBHIII', reply, 8))
