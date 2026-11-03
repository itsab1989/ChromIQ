"""Stateful queue tests with invented values; no device or vendor fixtures."""
from types import SimpleNamespace
import json
import struct
import unittest
from unittest.mock import patch

from fd9_independent.client import Instrument
from fd9_independent.native import (NativeCondition, NativeReader,
                                    finite_native_request, native_controls)
from fd9_independent.protocol import ProtocolError
from fd9_independent.sensor_data import CachedSensorData, SensorDataUnavailable
from fd9_independent.sensor_status import SensorStatus


def ready(mechanism=5, paper=1, stop=0):
    return struct.pack('<9I', 0x300, 1, 0, 0, stop, mechanism, paper, 0, 0)


class Device(Instrument):
    def __init__(self):
        super().__init__('invented-device')
        self.socket = object()
        self.registered = True
        self.notifications = [ready()]
        self.calls = []
        self.active = False
        self.queue = 0
        self.integrations = 2
        self.busy_polls = 0
        self.never_complete = False
        self.flags = 0
        self.native_failure = False
        self.changed_raw = False
        self.wrong_advance = False
        self.native_count = 2
        self.start_reply = None
        self.stop_reply = None
        self.raw_reads = 0

    def close(self):
        self.calls.append(('close',))
        self.socket = None
        self.registered = False

    def receive_event(self, timeout=None):
        self.calls.append(('event',))
        if not self.notifications:
            raise TimeoutError('Invented notification deadline')
        return self.notifications.pop(0)

    def factory_characterization(self):
        self.calls.append(('factory',))
        return SimpleNamespace(verified_sections_sha256='c' * 64)

    def sensor_status(self):
        self.calls.append(('status',))
        control = 2
        if self.active:
            if self.never_complete or self.busy_polls == 0:
                self.busy_polls += 1
                control = 10
            else:
                self.active = False
                self.queue = 1
        return SensorStatus(control, 0, self.queue, 0, self.flags, 0)

    def _exchange(self, payload, expected):
        self.calls.append(('command', payload))
        assert expected == 0x203
        if payload[4] == 2:
            self.active = True
            self.integrations = struct.unpack_from('<H', payload, 6)[0]
            return self.start_reply or struct.pack('<II2B', 0x203, 0, 0, 0)
        assert payload == struct.pack('<IB', 0x203, 4)
        self.active = False
        self.queue = 0
        return self.stop_reply or struct.pack('<II2B', 0x203, 0, 0, 0)

    def cached_sensor_data(self, selector=0, controls=(1, 0, 0, 0)):
        self.calls.append(('cached', selector, controls))
        assert self.queue == 1
        if selector == 1:
            if self.native_failure:
                raise SensorDataUnavailable(0, 3, 0)
            values = (.2 + controls[1] / 1000,) * 36
            return CachedSensorData(1, controls, values, self.native_count, 1, 0, b'\0' * 3)
        self.raw_reads += 1
        value = .9 if self.changed_raw and self.raw_reads == 2 else .4
        result = CachedSensorData(0, controls, (value,) * 152, self.integrations, 1, 0, b'\0' * 3)
        if controls[0] and not self.wrong_advance:
            self.queue = 0
        return result


class NativeTests(unittest.TestCase):
    def run_reader(self, device, **kwargs):
        with patch('fd9_independent.native.time.sleep'):
            return NativeReader(device, enable_experimental_native=True).after_final_point(**kwargs)

    def test_three_conditions_share_one_entry_and_factory_context(self):
        device = Device()
        result = self.run_reader(device)
        self.assertEqual(result.factory_sections_sha256, 'c' * 64)
        self.assertEqual(result.for_condition('M2').condition, NativeCondition.M2)
        self.assertEqual(result.for_condition('M2').spectrum.wavelengths, tuple(range(380, 731, 10)))
        reads = [c for c in device.calls if c[0] == 'cached']
        self.assertEqual([(r[1], r[2]) for r in reads], [
            (0, (0, 0, 0, 0)), (1, (0, 0, 0, 0)),
            (1, (0, 2, 0, 0)), (1, (0, 160, 0, 0)),
            (0, (0, 0, 0, 0)), (0, (1, 0, 0, 0))])
        self.assertEqual(device.queue, 0)
        self.assertIsNotNone(device.socket)
        commands = [c[1] for c in device.calls if c[0] == 'command']
        self.assertEqual(commands, [bytes.fromhex('0302000002000200')])

    def test_subset_and_repeated_points_use_one_factory_read(self):
        device = Device()
        reader = NativeReader(device, enable_experimental_native=True)
        with patch('fd9_independent.native.time.sleep'):
            result = reader.after_final_point(('M1',))
            with self.assertRaises(ValueError):
                result.for_condition('M0')
            device.notifications.append(ready())
            reader.after_final_point(('M2',))
        self.assertEqual(sum(c[0] == 'factory' for c in device.calls), 1)

    def test_opt_in_condition_and_integration_checks_precede_io(self):
        device = Device()
        with self.assertRaises(ValueError):
            NativeReader(device)
        reader = NativeReader(device, enable_experimental_native=True)
        for conditions in ((), ('M2', 'M2'), ('M3',), (15,)):
            with self.assertRaises(ValueError):
                reader.after_final_point(conditions)
        for count in (0, 1, 3, 66, True, 2.0):
            with self.assertRaises(ValueError):
                reader.after_final_point(integrations=count)
        self.assertEqual(device.calls, [])

    def test_wire_controls_do_not_reuse_sdk_m2_option(self):
        self.assertEqual(native_controls('M2'), (0, 160, 0, 0))
        self.assertEqual(native_controls('M1', advance=True), (1, 2, 0, 0))
        with self.assertRaises(ValueError):
            native_controls('M0', advance=1)
        self.assertEqual(finite_native_request(64), bytes.fromhex('0302000002004000'))

    def test_native_evidence_serializes_without_coefficients_or_profile(self):
        evidence = self.run_reader(Device()).to_dict()
        decoded = json.loads(json.dumps(evidence))
        self.assertEqual(decoded['conversion_source'], 'instrument_firmware')
        self.assertEqual(decoded['basic']['opaque_header_hex'], '000000')
        self.assertEqual(set(decoded['spectra']), {'M0', 'M1', 'M2'})
        self.assertEqual(len(decoded['basic']['values']), 152)
        self.assertNotIn('profile', decoded)

    def test_invalid_deadlines_do_not_close_or_contact_the_device(self):
        device = Device()
        for options in ({'timeout': 0}, {'timeout': 61}, {'ready_timeout': 0}, {'ready_timeout': 31}):
            with self.assertRaises(ValueError):
                self.run_reader(device, **options)
        self.assertEqual(device.calls, [])

    def test_continued_row_callback_is_refused_without_reading_events(self):
        device = Device()
        device._row_callback_rpc_blocked = True
        with self.assertRaisesRegex(RuntimeError, 'continued row'):
            self.run_reader(device)
        self.assertEqual(device.calls, [])

    def test_pending_row_invitation_or_extra_raw_prevents_exposure(self):
        for command in (0x106, 0x305):
            with self.subTest(command=command):
                device = Device()
                device.notifications = [struct.pack('<I', command)]
                with self.assertRaises(ProtocolError):
                    self.run_reader(device)
                self.assertFalse(any(c[0] == 'command' for c in device.calls))
                self.assertIsNone(device.socket)

    def test_paper_absence_cannot_satisfy_ready_barrier(self):
        device = Device()
        device.notifications = [ready(paper=0)]
        with self.assertRaises(TimeoutError):
            self.run_reader(device)
        self.assertFalse(any(c[0] == 'command' for c in device.calls))

    def test_warning_or_nonempty_initial_queue_prevents_start(self):
        for field in ('flags', 'queue'):
            device = Device()
            setattr(device, field, 1)
            with self.assertRaises(ProtocolError):
                self.run_reader(device)
            self.assertFalse(any(c[0] == 'command' for c in device.calls))

    def test_native_failure_does_not_publish_partial_conditions_or_consume(self):
        device = Device()
        device.native_failure = True
        with self.assertRaises(SensorDataUnavailable):
            self.run_reader(device)
        self.assertFalse(any(c[0] == 'cached' and c[2][0] for c in device.calls))
        self.assertIsNone(device.socket)

    def test_changed_entry_or_wrong_condition_header_refuses_advancement(self):
        for field, value in (('changed_raw', True), ('native_count', 4)):
            device = Device()
            setattr(device, field, value)
            with self.assertRaises(ProtocolError):
                self.run_reader(device)
            self.assertFalse(any(c[0] == 'cached' and c[2][0] for c in device.calls))

    def test_wrong_advancement_is_not_retried(self):
        device = Device()
        device.wrong_advance = True
        with self.assertRaisesRegex(ProtocolError, 'exactly once'):
            self.run_reader(device)
        self.assertEqual(sum(c[0] == 'cached' and c[2][0] for c in device.calls), 1)

    def test_timeout_stops_owned_start_and_closes(self):
        device = Device()
        device.never_complete = True
        # Ready deadline, ready loop, acquisition deadline, acquisition timeout,
        # and cleanup stop deadline. The stop itself completes immediately.
        with patch('fd9_independent.native.time.monotonic', side_effect=[0, 0, 0, 1, 1]):
            with self.assertRaises(TimeoutError):
                self.run_reader(device, timeout=.5)
        commands = [c[1] for c in device.calls if c[0] == 'command']
        self.assertEqual(commands, [finite_native_request(), bytes.fromhex('0302000004')])
        self.assertIsNone(device.socket)

    def test_malformed_acknowledgement_does_not_leave_owned_start_running(self):
        device = Device()
        device.start_reply = b'bad'
        with self.assertRaises(ProtocolError):
            self.run_reader(device)
        self.assertFalse(device.active)
        self.assertTrue(any(c == ('command', bytes.fromhex('0302000004')) for c in device.calls))

    def test_interrupt_does_not_send_recovery_into_unfinished_reply(self):
        class Interrupted(Device):
            def _exchange(self, payload, expected):
                super()._exchange(payload, expected)
                raise KeyboardInterrupt()
        device = Interrupted()
        with self.assertRaises(KeyboardInterrupt):
            self.run_reader(device)
        self.assertEqual(sum(c[0] == 'command' for c in device.calls), 1)
        self.assertIsNone(device.socket)

    def test_failed_cleanup_retains_original_failure_and_closes(self):
        device = Device()
        device.start_reply = b'bad'
        device.stop_reply = struct.pack('<II2B', 0x203, 0, 4, 0)
        with self.assertRaisesRegex(RuntimeError, 'Malformed.*cleanup also failed') as error:
            self.run_reader(device)
        self.assertIsInstance(error.exception.__cause__, ProtocolError)
        self.assertIsNone(device.socket)

    def test_reader_cannot_rebind_to_reconnected_instrument(self):
        device = Device()
        reader = NativeReader(device, enable_experimental_native=True)
        with patch('fd9_independent.native.time.sleep'):
            reader.after_final_point()
        before = len(device.calls)
        device.socket = object()
        with self.assertRaisesRegex(RuntimeError, 'different connection'):
            reader.after_final_point()
        self.assertEqual(len(device.calls), before)


if __name__ == '__main__':
    unittest.main()
