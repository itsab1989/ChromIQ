import struct
import unittest

from fd9_independent import Instrument, ProtocolError
from fd9_independent.sensor_status import SensorStatus, sensor_status_request
from test_candidate import FakeSocket, frame


def reply(control=7, calculation=9, count=341, fatal=0x1234,
          warning=0x5678, calibration=0xABCDEF01):
    return struct.pack('<IIBBHIII', 0x200, 0, control, calculation,
                       count, fatal, warning, calibration)


class SensorStatusTests(unittest.TestCase):
    def test_state_is_not_a_nested_sensor_error(self):
        status = SensorStatus.from_reply(reply())
        self.assertEqual(status, SensorStatus(7, 9, 341, 0x1234, 0x5678, 0xABCDEF01))
        self.assertEqual(sensor_status_request(), struct.pack('<I', 0x200))

    def test_only_registration_and_status_are_sent(self):
        sock = FakeSocket(frame(struct.pack('<II', 3, 0)) + frame(reply()), fragment=3)
        with Instrument('test', socket_factory=lambda *_: sock) as instrument:
            self.assertEqual(instrument.sensor_status().measurement_sum_count, 341)
        self.assertEqual(len(sock.sent), 2)
        self.assertEqual(sock.sent[1], b'\0\0\4\0' + sensor_status_request())
        self.assertTrue(sock.closed)

    def test_status_requires_registration(self):
        with self.assertRaises(RuntimeError):Instrument('test').sensor_status()

    def test_wrong_command_results_and_lengths_are_rejected(self):
        for bad in (b'', b'\0'*4, struct.pack('<II',0x200,0),
                    reply()[:-1], reply()+b'\0',
                    struct.pack('<II',0x201,0)+reply()[8:],
                    struct.pack('<II',0x200,201)):
            with self.subTest(payload=bad), self.assertRaises(ProtocolError):
                SensorStatus.from_reply(bad)

    def test_malformed_status_disconnects_without_retry(self):
        sock = FakeSocket(frame(struct.pack('<II',3,0))+frame(reply()[:-1]))
        instrument = Instrument('test',socket_factory=lambda *_:sock).connect()
        with self.assertRaises(ProtocolError):instrument.sensor_status()
        self.assertTrue(sock.closed)
        self.assertFalse(instrument.registered)
        self.assertEqual(len(sock.sent),2)


if __name__ == '__main__':unittest.main()
