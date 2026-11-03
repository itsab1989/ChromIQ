# SPDX-License-Identifier: GPL-3.0-or-later
"""Experimental factory/native spectra, calculated inside the instrument.

This module serializes observed protocol fields. It contains no host spectral
conversion algorithm, manufacturer library, reference profile or numerical
characterization table. M0/M1/M2 have been compared on white and colored samples
on one owned FD-9, including two successive positions without ejection.

The demonstrated acquisition starts after a final, ordinary one-point row.
It preserves a fresh finite-acquisition queue entry while reading every
requested condition, then consumes that entry once. It does not position,
home or eject the sheet. Seven-row native transport and calibration renewal have passed on one unit.
"""
from dataclasses import dataclass
from enum import Enum
import struct
import time

from .client import Instrument
from .protocol import ProtocolError, SheetStatus
from .sensor_data import CachedSensorData, SensorDataUnavailable
from .spectral import Curve


class NativeCondition(str, Enum):
    M0 = 'M0'
    M1 = 'M1'
    M2 = 'M2'


# Device protocol values; the host SDK's public M2 option 15 is not a wire value.
_CONDITION_CONTROLS = {NativeCondition.M0: 0, NativeCondition.M1: 2,
                       NativeCondition.M2: 160}
_BANDS = tuple(range(380, 731, 10))


def finite_native_request(integrations=2):
    if type(integrations) is not int or not 2 <= integrations <= 64 or integrations % 2:
        raise ValueError('Require an even integration count in 2..64; only 2 is hardware tested')
    return struct.pack('<IBBH', 0x203, 2, 0, integrations)


def native_controls(condition, *, advance=False):
    if type(advance) is not bool:
        raise ValueError('Advance must be an explicit boolean')
    return (int(advance), _CONDITION_CONTROLS[NativeCondition(condition)], 0, 0)


@dataclass(frozen=True)
class NativeSpectrum:
    condition: NativeCondition
    values: tuple
    sum_count: int
    data_count: int
    measurement_flags: int

    @property
    def spectrum(self):
        return Curve(_BANDS, self.values)


@dataclass(frozen=True)
class NativeMeasurement:
    basic: CachedSensorData
    spectra: tuple
    factory_sections_sha256: str
    host: str
    port: int

    def to_dict(self):
        """JSON-safe evidence; no external profile or factory coefficients."""
        return {
            'conversion_source': 'instrument_firmware',
            'host': self.host, 'port': self.port,
            'factory_sections_sha256': self.factory_sections_sha256,
            'wavelengths_nm': list(_BANDS),
            'basic': {
                'values': list(self.basic.values),
                'sum_count': self.basic.sum_count,
                'data_count': self.basic.data_count,
                'measurement_flags': self.basic.measurement_flags,
                'opaque_header_hex': self.basic.opaque_header.hex(),
            },
            'spectra': {
                item.condition.value: {
                    'values': list(item.values), 'sum_count': item.sum_count,
                    'data_count': item.data_count,
                    'measurement_flags': item.measurement_flags,
                } for item in self.spectra
            },
        }

    def for_condition(self, condition):
        condition = NativeCondition(condition)
        for result in self.spectra:
            if result.condition == condition:
                return result
        raise ValueError('This condition was not acquired')


def wait_final_point_ready(instrument, timeout=5):
    """Consume a fresh ready notification after the final ordinary raw point.

    Call immediately after receiving that point, before any other diagnostic.
    A next-row invitation or additional raw point invalidates this barrier.
    Sensor idle and paper-path readiness are separate states.
    """
    if not 0 < timeout <= 30:
        raise ValueError('Final-point readiness deadline must be in 0..30 seconds')
    if instrument._row_callback_rpc_blocked:
        raise RuntimeError('Native reads cannot interrupt a continued row sequence')
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('No fresh final-point ready notification')
        message = instrument.receive_event(remaining)
        command = struct.unpack_from('<I', message)[0]
        if command in (0x106, 0x305):
            raise ProtocolError('Continued or additional points pending; native acquisition refused')
        if command == 0x300:
            status = SheetStatus.decode(message)
            if status.stop or status.fatal:
                raise ProtocolError('Controller stopped; native acquisition refused')
            if status.mechanism == 5 and status.paper == 1:
                return status


class NativeReader:
    """One-session, opt-in reader for the demonstrated final-point sequence.

    Factory records are checked once on the same connection and never applied
    again on the host. All spectral calculation uses the device's factory
    characterization. An error closes the session after a bounded, owned-start
    stop attempt when the connection and cancellation state permit it.
    """
    def __init__(self, instrument, *, enable_experimental_native=False):
        if enable_experimental_native is not True:
            raise ValueError('Native acquisition requires explicit experimental opt-in')
        if not isinstance(instrument, Instrument):
            raise TypeError('Use an independent Instrument session')
        self.instrument = instrument
        self._connection = None
        self._factory_digest = None
        self.last_status = None

    def _status(self):
        state = self.instrument.sensor_status()
        self.last_status = state
        if state.fatal_error or state.warning or state.calibration_result:
            raise ProtocolError('Sensor reports warning, fatal or calibration-result flags')
        return state

    def _sensor_command(self, payload):
        reply = self.instrument._exchange(payload, 0x203)
        if len(reply) != 10 or struct.unpack_from('<II', reply) != (0x203, 0):
            raise ProtocolError('Malformed or unsuccessful native sensor command')
        if reply[8]:
            raise SensorDataUnavailable(0, reply[8], reply[9])

    def _stop_owned_start(self):
        client = self.instrument
        if client.socket is None or (client.cancelled is not None and client.cancelled()):
            return
        state = self._status()
        if state.control_state not in (10, 11, 12):
            return
        self._sensor_command(struct.pack('<IB', 0x203, 4))
        deadline = time.monotonic() + 3
        while True:
            state = self._status()
            if (state.control_state, state.calculation_state) == (2, 0):
                return
            if time.monotonic() >= deadline:
                raise TimeoutError('Native sensor stop did not return to idle')
            time.sleep(.1)

    def after_final_point(self, conditions=('M0', 'M1', 'M2'), *, integrations=2,
                          ready_timeout=5, timeout=15):
        conditions = tuple(NativeCondition(value) for value in conditions)
        if not conditions or len(set(conditions)) != len(conditions):
            raise ValueError('Require unique native measurement conditions')
        request = finite_native_request(integrations)
        if not 0 < timeout <= 60:
            raise ValueError('Native acquisition deadline must be in 0..60 seconds')
        if not 0 < ready_timeout <= 30:
            raise ValueError('Final-point readiness deadline must be in 0..30 seconds')
        client = self.instrument
        if not client.registered:
            raise RuntimeError('Register before acquiring native spectra')
        if self._connection is not None and self._connection is not client.socket:
            raise RuntimeError('Native reader belongs to a different connection')
        if client._row_callback_rpc_blocked:
            raise RuntimeError('Native reads cannot interrupt a continued row sequence')
        started = False
        try:
            wait_final_point_ready(client, ready_timeout)
            if self._factory_digest is None:
                snapshot = client.factory_characterization()
                self._factory_digest = snapshot.verified_sections_sha256
                self._connection = client.socket
            state = self._status()
            if (state.control_state, state.calculation_state, state.measurement_sum_count) != (2, 0, 0):
                raise ProtocolError('Expected idle sensor and empty queue before native acquisition')
            # Mark ownership before sending: a malformed acknowledgement can
            # still follow a successfully started exposure.
            started = True
            self._sensor_command(request)
            deadline = time.monotonic() + timeout
            while True:
                state = self._status()
                if state.measurement_sum_count > 1:
                    raise ProtocolError('Single native acquisition produced multiple queue entries')
                if (state.control_state, state.calculation_state, state.measurement_sum_count) == (2, 0, 1):
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError('Native acquisition did not complete')
                time.sleep(.2)
            basic = client.cached_sensor_data(0, (0, 0, 0, 0))
            if basic.sum_count != integrations or basic.data_count != 1:
                raise ProtocolError('Native acquisition returned unexpected integration/data counts')
            spectra = []
            for condition in conditions:
                data = client.cached_sensor_data(1, native_controls(condition))
                if (data.sum_count, data.data_count) != (basic.sum_count, basic.data_count):
                    raise ProtocolError('Native conditions do not describe the same raw entry')
                spectra.append(NativeSpectrum(condition, data.values, data.sum_count,
                                               data.data_count, data.measurement_flags))
            if client.cached_sensor_data(0, (0, 0, 0, 0)) != basic:
                raise ProtocolError('Raw entry changed across native peeks')
            if self._status().measurement_sum_count != 1:
                raise ProtocolError('Native peeks changed queue count')
            advanced = client.cached_sensor_data(0, (1, 0, 0, 0))
            if (advanced.values, advanced.sum_count, advanced.data_count,
                advanced.measurement_flags, advanced.opaque_header) != (
                    basic.values, basic.sum_count, basic.data_count,
                    basic.measurement_flags, basic.opaque_header):
                raise ProtocolError('Advancing read returned another raw entry')
            state = self._status()
            if (state.control_state, state.calculation_state, state.measurement_sum_count) != (2, 0, 0):
                raise ProtocolError('Native entry was not consumed exactly once')
            started = False
            return NativeMeasurement(basic, tuple(spectra), self._factory_digest,
                                     client.host, client.port)
        except Exception as error:
            try:
                if started:
                    self._stop_owned_start()
            except Exception as stop_error:
                raise RuntimeError(f'{error}; native sensor cleanup also failed: {stop_error}') from error
            finally:
                client.close()
            raise
        except BaseException:
            # An interrupt can arrive inside a transport receive, leaving an
            # unfinished reply. Never send a recovery RPC into that stream.
            client.close()
            raise
