"""Row batching contract: no per-point request, sensor exposure or readback."""

import struct, unittest
from unittest.mock import patch
from fd9_independent import Instrument, FactoryRowAcquisition
from fd9_independent.motion import Phase
from test_motion import SocketScript, reply, position, image, state, commands
from test_instrument_model import fixture


def spectrum(column):
    return struct.pack("<I4H", 0x305, 4, column, 0, 0) + struct.pack(
        "<152f", *([0.75] * 76 + [1.0] * 76)
    )


def setup(rows):
    script = [reply(3), position(-1), reply(1, 7348), reply(0x105), image(400)]
    for row in rows:
        script.extend([reply(0x106)] + [spectrum(c + 1) for c, _ in enumerate(row)])
    script.extend(
        [reply(0x100), state(11), reply(0, 40), state(0, 0), reply(0, 40), reply(0x101)]
    )
    socket = SocketScript(script)
    client = Instrument("invented", socket_factory=lambda *_: socket).connect()
    acq = FactoryRowAcquisition(
        client, enable_experimental_motion=True, enable_experimental_model=True
    )
    acq.model = fixture()
    acq._model_connection = client.socket
    acq.phase = Phase.SCANNED
    acq.image = {i: b"" for i in range(500)}
    return client, acq, socket


class Tests(unittest.TestCase):
    def test_alternating_rows_keep_batching_calibration_and_final_ejection(self):
        rows = [[(100 + 30*c, 200 + 30*r) for c in range(4)] for r in range(7)]
        rows = [list(reversed(row)) if r % 2 else row for r, row in enumerate(rows)]
        client, acq, socket = setup(rows)
        with patch("fd9_independent.motion.time.sleep"):
            got = acq.measure_rows(rows)
        self.assertEqual(len(got), 28)
        self.assertEqual(acq.completed_native_rows, 7)
        lines = [p[4:] for p in socket.sent if struct.unpack_from('<I', p, 4)[0] == 0x106]
        for r, payload in enumerate(lines):
            header = struct.unpack_from('<9I', payload)
            self.assertEqual(header[4], int(r % 6 == 0))
            self.assertEqual(header[7], int(r < 6))
            self.assertEqual([struct.unpack_from('<2f', payload, 36+16*c)
                              for c in range(4)], rows[r])
        ids = commands(socket.sent)
        self.assertEqual(ids.count(0x106), 7)
        self.assertEqual(ids.count(0x100), 1)
        self.assertEqual(ids.count(0x101), 1)
        self.assertNotIn(0x203, ids)
        self.assertNotIn(0x205, ids)

    def test_stop_within_descending_row_keeps_completed_rows_without_ejection(self):
        rows = [[(100,200),(200,200)],[(200,240),(100,240)]]
        client, acq, socket = setup(rows)
        def stop(count, total):
            if count == 3:
                raise InterruptedError('Invented stop during descending row')
        with self.assertRaises(InterruptedError):
            acq.measure_rows(rows, on_point=stop)
        self.assertEqual(len(acq.native_samples), 3)
        self.assertEqual(acq.completed_native_rows, 1)
        self.assertEqual(commands(socket.sent).count(0x106), 2)
        self.assertNotIn(0x101, commands(socket.sent))
        self.assertTrue(socket.closed)

    def test_twenty_columns_use_one_command_per_row_with_all_conditions(self):
        rows = [[(100 + 30 * c, 200 + 30 * r) for c in range(20)] for r in range(7)]
        client, acq, socket = setup(rows)
        points = []
        with patch("fd9_independent.motion.time.sleep"):
            got = acq.measure_rows(rows, on_point=lambda *args: points.append(args))
        self.assertEqual(len(got), 140)
        self.assertEqual(acq.completed_native_rows, 7)
        self.assertEqual(points, [(n, 140) for n in range(1, 141)])
        ids = commands(socket.sent)
        self.assertEqual(ids.count(0x106), 7)
        self.assertNotIn(0x203, ids)
        self.assertNotIn(0x205, ids)
        self.assertNotIn(0x200, ids)
        self.assertEqual(ids.count(0x100), 1)
        self.assertEqual(ids.count(0x101), 1)
        lines = [
            struct.unpack_from("<9I", p, 4)
            for p in socket.sent
            if struct.unpack_from("<I", p, 4)[0] == 0x106
        ]
        self.assertEqual([i for i, p in enumerate(lines) if p[4]], [0, 6])
        self.assertEqual([p[7] for p in lines], [1] * 6 + [0])
        self.assertTrue(all(p[8] == 20 for p in lines))

    def test_stop_at_row_boundary_keeps_complete_marker_and_closes(self):
        client, acq, socket = setup(
            [[(100, 200), (200, 200)], [(100, 240), (200, 240)]]
        )

        def stop(count, total):
            if count == 2:
                raise RuntimeError("Invented operator stop")

        with self.assertRaises(RuntimeError):
            acq.measure_rows(
                [[(100, 200), (200, 200)], [(100, 240), (200, 240)]], on_point=stop
            )
        self.assertEqual(len(acq.native_samples), 2)
        self.assertEqual(acq.completed_native_rows, 1)
        self.assertEqual(commands(socket.sent).count(0x106), 1)
        self.assertNotIn(0x101, commands(socket.sent))
        self.assertTrue(socket.closed)

    def test_progress_cannot_issue_another_device_command(self):
        rows = [[(100, 200), (200, 200)]]
        client, acq, socket = setup(rows)
        with self.assertRaisesRegex(RuntimeError, "callbacks"):
            acq.measure_rows(rows, on_point=lambda *_: client.status())
        self.assertEqual(len(acq.native_samples), 1)
        self.assertNotIn(0, commands(socket.sent))

    def test_model_must_belong_to_same_connection(self):
        rows = [[(100, 200)]]
        client, acq, socket = setup(rows)
        acq._model_connection = object()
        with self.assertRaises(RuntimeError):
            acq.measure_rows(rows)
        self.assertEqual(commands(socket.sent), [3])


if __name__ == "__main__":
    unittest.main()
