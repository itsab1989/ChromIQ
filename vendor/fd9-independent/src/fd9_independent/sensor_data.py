# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded reads of the spectral sensor's cached data.

These commands retrieve data; they do not initiate exposure, calibration or
transport motion. Numeric controls are not ISO-condition names. The separate
NativeReader maps the tested controls and checks same-entry acquisition; callers
must not infer a condition from the output shape alone.
"""
from dataclasses import dataclass
import math
import struct

from .protocol import ProtocolError

COMMAND = 0x205


class SensorDataUnavailable(RuntimeError):
    def __init__(self, main_result, sensor_result=None, detail=None):
        self.main_result = main_result
        self.sensor_result = sensor_result
        self.detail = detail
        super().__init__(f'Sensor data unavailable: main={main_result}, sensor={sensor_result}, detail={detail}')


def cached_data_request(selector=0, controls=(1, 0, 0, 0)):
    if type(selector) is not int or selector not in (0, 1):
        raise ValueError('Only basic and native spectral reads are supported')
    controls = tuple(controls)
    if len(controls) != 4 or any(type(v) is not int or not 0 <= v <= 255 for v in controls):
        raise ValueError('Require four explicit byte-valued sensor controls')
    if selector == 0 and controls[1:] != (0, 0, 0):
        raise ValueError('Basic read cannot carry spectral-only controls')
    arguments = bytes((selector,) + (controls[:1] if selector == 0 else controls))
    return struct.pack('<I', COMMAND) + arguments


@dataclass(frozen=True)
class CachedSensorData:
    selector: int
    controls: tuple
    values: tuple
    sum_count: int
    data_count: int
    measurement_flags: int
    opaque_header: bytes

    @classmethod
    def from_reply(cls, reply, selector=0, controls=(1, 0, 0, 0)):
        cached_data_request(selector, controls)
        if len(reply) < 8 or struct.unpack_from('<I', reply)[0] != COMMAND:
            raise ProtocolError('Unexpected cached sensor reply')
        main_result = struct.unpack_from('<I', reply, 4)[0]
        if main_result:
            raise SensorDataUnavailable(main_result)
        if len(reply) < 9:
            raise ProtocolError('Missing cached sensor result')
        if reply[8]:
            raise SensorDataUnavailable(0, reply[8], reply[9] if len(reply) > 9 else None)
        count = 152 if selector == 0 else 36
        if len(reply) != 20 + 4 * count:
            raise ProtocolError('Cached sensor data has an unexpected size')
        sums, data_count, flags = struct.unpack_from('<HHI', reply, 12)
        if flags:
            raise SensorDataUnavailable(0, 0, flags)
        values = struct.unpack_from(f'<{count}f', reply, 20)
        if not all(math.isfinite(v) for v in values):
            raise ProtocolError('Non-finite cached sensor data')
        return cls(selector, tuple(controls), values, sums, data_count, flags, bytes(reply[9:12]))
