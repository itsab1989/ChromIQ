"""Portable invented characterization and queue-free numerical conversion."""

import hashlib
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest

from fd9_independent.instrument_model import (
    InstrumentModel,
    model_data_request,
    model_data_reply,
)
from fd9_independent.protocol import RawSpectrum, ProtocolError


def fixture():
    matrix = struct.pack(">400f", *[0.001 * (1 + (i % 3)) for i in range(400)])
    records = []
    for kind in [0, 2, 160] + [23] * 24:
        # Distinct invented illumination shapes; this is not a unit capture.
        values = [(1 + i * 0.01 if kind == 0 else 2 + i * 0.005) for i in range(97)]
        if kind == 160:
            values[:20] = [0.0] * 20
        records.append(struct.pack(">I97f", kind, *values))
    info = struct.pack("<II", 0x216, 0) + bytes((1, 0, 0, 2)) + bytes(36)
    return InstrumentModel(matrix, b"".join(records), info, "a" * 64)


class Device:
    def __init__(self):
        self.registered = True
        self.socket = object()
        self.calls = []
        self.closed = False
        self.version = bytes((1, 0, 0, 2))
        self.pointer = 0x0C034C28
        self.count = 27
        self.model = fixture()
        self.queue = 0
        self.corrupt_echo = False

    def close(self):
        self.closed = True
        self.socket = None

    def sensor_status(self):
        self.calls.append(("status",))
        return SimpleNamespace(
            control_state=2,
            calculation_state=0,
            measurement_sum_count=self.queue,
            fatal_error=0,
            warning=0,
            calibration_result=0,
        )

    def factory_characterization(self):
        self.calls.append(("factory",))
        return SimpleNamespace(verified_sections_sha256="a" * 64)

    def _exchange(self, payload, expected):
        self.calls.append(("request", payload))
        if expected == 0x216:
            return (
                self.model.sensor_info[:8] + self.version + self.model.sensor_info[12:]
            )
        cmd, read, pad, size, address = struct.unpack("<IBBHI", payload)
        assert (cmd, read, pad) == (0x20E, 0, 0)
        if address == 0x0C02E520:
            data = self.pointer.to_bytes(4, "big")
        elif address == 0x0C04C378:
            data = self.count.to_bytes(4, "big")
        elif address == 0x0C02D4F8:
            data = self.model.matrix_bytes
        else:
            data = self.model.condition_bytes[
                address - 0x0C034C28 : address - 0x0C034C28 + size
            ]
        return (
            struct.pack("<IIBBHI", cmd, 0, 0, 0, size, address + int(self.corrupt_echo))
            + data
        )


class Tests(unittest.TestCase):
    def test_reads_only_fixed_spans_without_motion_exposure_or_writes(self):
        device = Device()
        model = InstrumentModel.read(device, allow_experimental=True)
        self.assertEqual(model.model_sha256, device.model.model_sha256)
        requests = [p for kind, *v in device.calls if kind == "request" for p in v]
        self.assertEqual(
            [struct.unpack_from("<I", p)[0] for p in requests], [0x216] + [0x20E] * 5
        )
        self.assertTrue(all(p[4:6] == bytes(2) for p in requests[1:]))
        self.assertFalse(device.closed)

    def test_version_and_idle_checks_precede_memory_reads(self):
        for change, value in [("version", b"bad!"), ("queue", 1)]:
            d = Device()
            setattr(d, change, value)
            with self.assertRaises(ProtocolError):
                InstrumentModel.read(d, allow_experimental=True)
            self.assertTrue(d.closed)
            self.assertFalse(
                any(
                    k == "request" and struct.unpack_from("<I", v[0])[0] == 0x20E
                    for k, *v in d.calls
                )
            )

    def test_no_bulk_reads_after_layout_disagreement(self):
        for change, value in [("pointer", 0), ("pointer", 0x0C000000), ("count", 1000)]:
            d = Device()
            setattr(d, change, value)
            with self.assertRaises(ProtocolError):
                InstrumentModel.read(d, allow_experimental=True)
            sizes = [
                struct.unpack_from("<H", v[0], 6)[0]
                for k, *v in d.calls
                if k == "request" and len(v[0]) == 12
            ]
            self.assertTrue(all(size == 4 for size in sizes))

    def test_request_cannot_address_other_memory_or_select_write(self):
        for address, size in [
            (0, 4),
            (0x0C02D4F8, 32),
            (0x0C02D4F8, 1601),
            (True, 4),
            (0x0C02E520, True),
        ]:
            with self.assertRaises(ValueError):
                model_data_request(address, size)
        d = Device()
        d.corrupt_echo = True
        with self.assertRaises(ProtocolError):
            InstrumentModel.read(d, allow_experimental=True)
        self.assertTrue(d.closed)

    def test_opt_in_and_registration_precede_all_io(self):
        d = Device()
        with self.assertRaises(ValueError):
            InstrumentModel.read(d)
        d.registered = False
        with self.assertRaises(RuntimeError):
            InstrumentModel.read(d, allow_experimental=True)
        self.assertEqual(d.calls, [])

    def test_equal_sources_preserve_neutral_reflectance_and_fluorescence(self):
        model = fixture()
        for value in (0.25, 1.5, 2.1):
            raw = RawSpectrum(
                (4, 1, 0, 0), ((value,) * 38, (value,) * 38, (1.0,) * 38, (1.0,) * 38)
            )
            result = model.convert(raw)
            for mode in ("M0", "M1", "M2"):
                self.assertTrue(
                    all(
                        abs(v - value) < 1e-6 for v in result.for_condition(mode).values
                    )
                )
        self.assertEqual(result.to_dict()["conversion_source"], "instrument_model")
        self.assertNotIn("profile", result.to_dict())

    def test_input_flags_shapes_and_nonfinite_values_are_refused(self):
        model = fixture()
        valid = ((0.4,) * 38,) * 4
        for raw in [
            RawSpectrum((4, 1, 1, 0), valid),
            RawSpectrum((4, 1, 0, 0), ((float("nan"),) * 38,) * 4),
            RawSpectrum((4, 1, 0, 0), ((1.0,) * 37,) * 4),
        ]:
            with self.assertRaises((ValueError, ProtocolError)):
                model.convert(raw)
        with self.assertRaises(ValueError):
            model.convert(RawSpectrum((4, 1, 0, 0), valid), ("M1", "M1"))

    def test_model_rejects_truncation_ambiguous_conditions_and_nonfinite_matrix(self):
        m = fixture()
        for matrix, records in [
            (m.matrix_bytes[:-1], m.condition_bytes),
            (struct.pack(">400f", *([float("nan")] * 400)), m.condition_bytes),
            (m.matrix_bytes, m.condition_bytes[:-392] + m.condition_bytes[:392]),
        ]:
            with self.assertRaises(ValueError):
                InstrumentModel(matrix, records, m.sensor_info, "a" * 64)

    def test_unused_custom_conditions_do_not_change_conversion_identity(self):
        m = fixture()
        data = bytearray(m.condition_bytes)
        struct.pack_into(">f", data, 3 * 392 + 4, 7.0)
        other = InstrumentModel(m.matrix_bytes, bytes(data), m.sensor_info, "a" * 64)
        self.assertEqual(m.model_sha256, other.model_sha256)
        self.assertNotEqual(m.snapshot_sha256, other.snapshot_sha256)
        data = bytearray(m.condition_bytes)
        struct.pack_into(">f", data, 4, 7.0)
        changed = InstrumentModel(m.matrix_bytes, bytes(data), m.sensor_info, "a" * 64)
        self.assertNotEqual(m.model_sha256, changed.model_sha256)

    def test_saved_data_contains_no_claim_of_manufacturer_host_runtime(self):
        m = fixture()
        with tempfile.TemporaryDirectory() as t:
            root = Path(t) / "model"
            m.save(root)
            metadata = json.loads((root / "model.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["model_sha256"], m.model_sha256)
            self.assertEqual(
                metadata["spectral_calculation"], "independent host arithmetic"
            )
            self.assertEqual((root / "matrix.bin").read_bytes(), m.matrix_bytes)


if __name__ == "__main__":
    unittest.main()
