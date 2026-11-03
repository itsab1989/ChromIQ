"""Native batch ordering/cleanup tests with invented transport and samples."""
from types import SimpleNamespace
import struct
import unittest
from unittest.mock import patch

from fd9_independent import Instrument, NativeAcquisition
from fd9_independent.motion import Phase
from fd9_independent.protocol import ProtocolError
from test_motion import SocketScript, reply, position, image, spectrum, state, commands


class Reader:
    instances = []
    fail_at = None

    def __init__(self, instrument, **kwargs):
        self.calls = []
        Reader.instances.append(self)

    def after_final_point(self, conditions, **kwargs):
        self.calls.append(tuple(conditions))
        if len(self.calls) == Reader.fail_at:
            raise ProtocolError('Invented native failure')
        return SimpleNamespace(index=len(self.calls))


def setup(rows):
    script = [reply(3), position(-1), reply(1, 7348), reply(0x105), image(400)]
    for row in rows:
        for point in row:
            script += [reply(0x106), spectrum()]
    script += [reply(0x100), state(11), reply(0, 40), state(0, 0),
               reply(0, 40), reply(0x101)]
    socket = SocketScript(script)
    client = Instrument('invented', socket_factory=lambda *_: socket).connect()
    acquisition = NativeAcquisition(client, enable_experimental_motion=True,
                                    enable_experimental_native=True)
    acquisition.phase = Phase.SCANNED
    acquisition.image = {i: b'' for i in range(500)}
    return client, acquisition, socket


class NativeMotionTests(unittest.TestCase):
    def setUp(self):
        Reader.instances = []
        Reader.fail_at = None

    def measure(self, acquisition, rows, **kwargs):
        with patch('fd9_independent.native_motion.NativeReader', Reader), \
                patch('fd9_independent.motion.time.sleep'):
            return acquisition.measure_native(rows, **kwargs)

    def test_multiple_rows_use_final_points_and_single_home_ejection(self):
        rows = [[(100, 200), (200, 200)], [(100, 240), (200, 240)]]
        client, acquisition, socket = setup(rows)
        points, completed = [], []
        result = self.measure(acquisition, rows, on_point=lambda *a: points.append(a),
                              on_row=lambda *a: completed.append(a))
        self.assertEqual([p.index for p in result], [1, 2, 3, 4])
        self.assertEqual(points, [(1, 4), (2, 4), (3, 4), (4, 4)])
        self.assertEqual(completed, [(1, 2), (2, 2)])
        self.assertEqual(len(Reader.instances), 1)
        self.assertEqual(acquisition.phase, Phase.DONE)
        ids = commands(socket.sent)
        self.assertEqual(ids.count(0x105), 1)
        self.assertEqual(ids.count(0x100), 1)
        self.assertEqual(ids.count(0x101), 1)
        line_packets = [p[4:] for p in socket.sent if struct.unpack_from('<I', p, 4)[0] == 0x106]
        self.assertEqual(len(line_packets), 4)
        self.assertTrue(all(struct.unpack_from('<I', p, 28)[0] == 0 for p in line_packets))

    def test_calibration_schedule_is_per_selected_chart_row(self):
        rows = [[(100, 200 + 20 * i), (200, 200 + 20 * i)] for i in range(7)]
        client, acquisition, socket = setup(rows)
        self.measure(acquisition, rows)
        headers = [struct.unpack_from('<9I', p, 4) for p in socket.sent
                   if struct.unpack_from('<I', p, 4)[0] == 0x106]
        self.assertEqual([i for i, h in enumerate(headers) if h[4]], [0, 12])
        self.assertTrue(all(h[7:] == (0, 1) for h in headers))

    def test_no_three_hundred_patch_limit(self):
        rows = [[(100 + 20 * c, 200 + 20 * r) for c in range(50)] for r in range(7)]
        client, acquisition, socket = setup(rows)
        result = self.measure(acquisition, rows)
        self.assertEqual(len(result), 350)
        self.assertEqual(acquisition.completed_native_rows, 7)

    def test_native_failure_keeps_prior_samples_without_homing_or_retry(self):
        rows = [[(100, 200), (200, 200)]]
        client, acquisition, socket = setup(rows)
        Reader.fail_at = 2
        with self.assertRaises(ProtocolError):
            self.measure(acquisition, rows)
        self.assertEqual(len(acquisition.raw_samples), 2)
        self.assertEqual(len(acquisition.native_samples), 1)
        self.assertEqual(acquisition.completed_native_rows, 0)
        self.assertEqual(commands(socket.sent).count(0x106), 2)
        self.assertNotIn(0x100, commands(socket.sent))
        self.assertNotIn(0x101, commands(socket.sent))
        self.assertTrue(socket.closed)

    def test_stop_at_complete_row_preserves_row_marker(self):
        rows = [[(100, 200)], [(100, 240)]]
        client, acquisition, socket = setup(rows)
        def stop(count, total):
            raise RuntimeError('Invented operator stop')
        with self.assertRaises(RuntimeError):
            self.measure(acquisition, rows, on_point=stop)
        self.assertEqual(len(acquisition.native_samples), 1)
        self.assertEqual(acquisition.completed_native_rows, 1)
        self.assertEqual(commands(socket.sent).count(0x106), 1)

    def test_progress_cannot_interleave_another_instrument_request(self):
        rows = [[(100, 200), (200, 200)]]
        client, acquisition, socket = setup(rows)
        with self.assertRaisesRegex(RuntimeError, 'callbacks'):
            self.measure(acquisition, rows, on_point=lambda *_: client.sensor_status())
        self.assertNotIn(0x200, commands(socket.sent))
        self.assertFalse(client._row_callback_rpc_blocked)
        self.assertEqual(len(acquisition.native_samples), 1)

    def test_late_invalid_geometry_is_rejected_before_any_positioning(self):
        rows = [[(100, 200)], [(100, 499)]]
        client, acquisition, socket = setup(rows)
        with self.assertRaises(ValueError):
            self.measure(acquisition, rows)
        self.assertEqual(commands(socket.sent), [3])
        self.assertEqual(Reader.instances, [])

    def test_native_and_motion_opt_ins_are_both_required(self):
        client = Instrument('invented')
        with self.assertRaises(ValueError):
            NativeAcquisition(client, enable_experimental_motion=True)
        with self.assertRaises(ValueError):
            NativeAcquisition(client, enable_experimental_native=True)


if __name__ == '__main__':
    unittest.main()
