# SPDX-License-Identifier: GPL-3.0-or-later
"""Factory-calibrated row conversion with numerical data read from the FD-9.

All numerical response matrices and illuminants come from the connected unit.
No manufacturer code, firmware image, extracted table or fitted profile is
included. The sensor applies unit calibration before delivering the four-block
packet. Newly authored host arithmetic solves the published two-source radiance
factor equation using the instrument-supplied emission/excitation model.

The read-only model layout is established for sensor version 1.0.0.2. Other
versions fail before a data-memory request. No general memory reader/writer is
exposed; only the fixed, bounded model-data spans below can be requested.
"""

from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import struct
from types import MappingProxyType

from .protocol import ProtocolError, RawSpectrum
from .spectral import Curve

_VERSION = bytes((1, 0, 0, 2))
_MATRIX = (0x0C02D4F8, 1600)
_POINTER = (0x0C02E520, 4)
_COUNT = (0x0C04C378, 4)
_RECORD_BASE = 0x0C034C28
_RECORD_COUNT = 27
_RECORD_SIZE = 392
_RECORD_BYTES = _RECORD_COUNT * _RECORD_SIZE
_RECORD_SPANS = ((_RECORD_BASE, 8000), (_RECORD_BASE + 8000, _RECORD_BYTES - 8000))
_SPANS = frozenset((_MATRIX, _POINTER, _COUNT) + _RECORD_SPANS)
_CONTROLS = {"M0": 0, "M1": 2, "M2": 160}
_BANDS = tuple(range(380, 731, 10))


def model_data_request(address, size):
    """Serialize only established read-only model spans; never a write flag."""
    if (
        type(address) is not int
        or type(size) is not int
        or (address, size) not in _SPANS
    ):
        raise ValueError("Only fixed version-bounded model-data reads are supported")
    return struct.pack("<IBBHI", 0x20E, 0, 0, size, address)


def model_data_reply(reply, address, size):
    model_data_request(address, size)
    if (
        len(reply) != size + 16
        or struct.unpack_from("<II", reply) != (0x20E, 0)
        or struct.unpack_from("<BBHI", reply, 8) != (0, 0, size, address)
    ):
        raise ProtocolError(
            "Instrument model read failed or echoed a different data span"
        )
    return bytes(reply[16:])


def _single(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


@dataclass(frozen=True)
class ModelSpectrum:
    condition: str
    values: tuple

    @property
    def spectrum(self):
        return Curve(_BANDS, self.values)


@dataclass(frozen=True)
class FactoryMeasurement:
    raw_header: tuple
    spectra: tuple
    factory_sections_sha256: str
    model_sha256: str

    def for_condition(self, condition):
        for spectrum in self.spectra:
            if spectrum.condition == condition:
                return spectrum
        raise ValueError("This condition was not calculated")

    def to_dict(self):
        return {
            "conversion_source": "instrument_model",
            "factory_sections_sha256": self.factory_sections_sha256,
            "model_sha256": self.model_sha256,
            "raw_header": list(self.raw_header),
            "wavelengths_nm": list(_BANDS),
            "spectra": {s.condition: {"values": list(s.values)} for s in self.spectra},
        }


@dataclass(frozen=True)
class InstrumentModel:
    matrix_bytes: bytes
    condition_bytes: bytes
    sensor_info: bytes
    factory_sections_sha256: str
    _matrix: tuple = field(init=False, repr=False)
    _curves: object = field(init=False, repr=False)
    _target_responses: object = field(init=False, repr=False)

    def __post_init__(self):
        if (
            not isinstance(self.sensor_info, bytes)
            or len(self.sensor_info) != 48
            or struct.unpack_from("<II", self.sensor_info) != (0x216, 0)
            or self.sensor_info[8:12] != _VERSION
        ):
            raise ValueError("Unsupported sensor model version; expected 1.0.0.2")
        if (
            not isinstance(self.matrix_bytes, bytes)
            or len(self.matrix_bytes) != 1600
            or not isinstance(self.condition_bytes, bytes)
            or len(self.condition_bytes) != _RECORD_BYTES
        ):
            raise ValueError("Incomplete instrument model data")
        digest = self.factory_sections_sha256
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
        ):
            raise ValueError("Require verified sensor factory provenance")
        matrix = struct.unpack(">400f", self.matrix_bytes)
        if not all(math.isfinite(v) for v in matrix) or not any(matrix):
            raise ValueError("Invalid emission/excitation response matrix")
        curves = {}
        for start in range(0, _RECORD_BYTES, _RECORD_SIZE):
            kind = struct.unpack_from(">I", self.condition_bytes, start)[0]
            values = struct.unpack_from(">97f", self.condition_bytes, start + 4)
            if kind in _CONTROLS.values():
                if kind in curves:
                    raise ValueError("Ambiguous instrument condition records")
                if not all(math.isfinite(v) and v >= 0 for v in values):
                    raise ValueError("Invalid instrument illuminant values")
                if kind != 160 and any(v <= 0 for v in values[20:63]):
                    raise ValueError(
                        "Illuminant does not cover the fluorescence output interval"
                    )
                curves[kind] = values
        if set(curves) != set(_CONTROLS.values()):
            raise ValueError("Instrument model lacks M0, M1 or M2")
        object.__setattr__(self, "_matrix", matrix)
        object.__setattr__(self, "_curves", MappingProxyType(curves))
        targets = {
            mode: self._response(curves[control][::2], 300)
            for mode, control in _CONTROLS.items()
        }
        object.__setattr__(self, "_target_responses", MappingProxyType(targets))

    @property
    def model_sha256(self):
        # Only the three used conditions bind conversion. Unused custom
        # illuminant slots can legitimately change in another application.
        selected = b"".join(
            struct.pack(">I97f", control, *self._curves[control])
            for control in _CONTROLS.values()
        )
        return hashlib.sha256(_VERSION + self.matrix_bytes + selected).hexdigest()

    @property
    def snapshot_sha256(self):
        return hashlib.sha256(self.matrix_bytes + self.condition_bytes).hexdigest()

    @classmethod
    def read(cls, instrument, *, allow_experimental=False):
        if allow_experimental is not True:
            raise ValueError("Instrument model reads require experimental opt-in")
        if not instrument.registered:
            raise RuntimeError("Register before reading the instrument model")
        try:
            state = instrument.sensor_status()
            if (
                (
                    state.control_state,
                    state.calculation_state,
                    state.measurement_sum_count,
                )
                != (2, 0, 0)
                or state.fatal_error
                or state.warning
                or state.calibration_result
            ):
                raise ProtocolError(
                    "Read the model only from an idle empty sensor with clear flags"
                )
            info = instrument._exchange(struct.pack("<I", 0x216), 0x216)
            if (
                len(info) != 48
                or struct.unpack_from("<II", info) != (0x216, 0)
                or info[8:12] != _VERSION
            ):
                raise ProtocolError(
                    "Sensor model version is not supported; no memory reads sent"
                )

            def read_span(span):
                return model_data_reply(
                    instrument._exchange(model_data_request(*span), 0x20E), *span
                )

            if (
                int.from_bytes(read_span(_POINTER), "big") != _RECORD_BASE
                or int.from_bytes(read_span(_COUNT), "big") != _RECORD_COUNT
            ):
                raise ProtocolError(
                    "Unsupported model-data layout; no bulk model reads sent"
                )
            matrix = read_span(_MATRIX)
            conditions = b"".join(read_span(span) for span in _RECORD_SPANS)
            factory = instrument.factory_characterization()
            return cls(
                matrix, conditions, bytes(info), factory.verified_sections_sha256
            )
        except BaseException:
            instrument.close()
            raise

    def save(self, directory):
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=False)
        for name, data in (
            ("matrix.bin", self.matrix_bytes),
            ("conditions.bin", self.condition_bytes),
            ("sensor-info.bin", self.sensor_info),
        ):
            (root / name).write_bytes(data)
        (root / "model.json").write_text(
            json.dumps(
                {
                    "data_source": "connected instrument; no bundled numerical data",
                    "sensor_version": list(_VERSION),
                    "factory_sections_sha256": self.factory_sections_sha256,
                    "model_sha256": self.model_sha256,
                    "snapshot_sha256": self.snapshot_sha256,
                    "spectral_calculation": "independent host arithmetic",
                    "unit_calibration": "sensor firmware before raw delivery",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _response(self, power, start_nm):
        """Discrete excitation integral divided by power at the emission band.

        The device supplies the 25-by-16 emission/excitation response model.
        Source/target grids are 10 nm for this quadrature; absent source UV
        samples are zero. No response curve or table is inferred from a chart.
        """
        result = [0.0] * 38

        def at(nm):
            index = (nm - start_nm) // 10
            return power[index] if 0 <= index < len(power) else 0.0

        for row in range(25):
            integral = 0.0
            for column in range(16):
                term = _single(
                    _single(self._matrix[row * 16 + column] * 10.0)
                    * at(300 + 10 * column)
                )
                integral = _single(integral + term)
            denominator = at(370 + 10 * row)
            result[row + 1] = _single(integral / denominator) if denominator else 0.0
        return tuple(result)

    def convert(self, raw, conditions=("M0", "M1", "M2")):
        """Convert a factory-calibrated 0x305 packet; no hardware I/O."""
        conditions = tuple(conditions)
        if (
            not conditions
            or len(set(conditions)) != len(conditions)
            or any(c not in _CONTROLS for c in conditions)
        ):
            raise ValueError("Require unique M0/M1/M2 conditions")
        if (
            not isinstance(raw, RawSpectrum)
            or len(raw.blocks) != 4
            or any(len(b) != 38 for b in raw.blocks)
        ):
            raise ValueError("Require a decoded four-block instrument spectrum")
        if not all(
            type(v) in (float, int) and math.isfinite(v) for b in raw.blocks for v in b
        ):
            raise ValueError("Instrument spectrum must contain finite numbers")
        if len(raw.header) != 4 or raw.header[2:] != (0, 0):
            raise ProtocolError("Raw measurement header reports unsupported flags")
        sample0, sample1, source0, source1 = raw.blocks
        response0 = self._response(source0, 360)
        response1 = self._response(source1, 360)
        spectra = []
        for condition in conditions:
            target = self._target_responses[condition]
            output = []
            for band in range(2, 38):
                wavelength = 360 + 10 * band
                if wavelength < 400:
                    value = sample1[band]
                elif wavelength > 610:
                    value = _single(_single(sample0[band] + sample1[band]) * 0.5)
                else:
                    contrast = _single(response1[band] - response0[band])
                    fraction = (
                        _single(_single(target[band] - response0[band]) / contrast)
                        if abs(contrast) >= 1e-7
                        else 0.5
                    )
                    value = _single(
                        _single(_single(1.0 - fraction) * sample0[band])
                        + _single(fraction * sample1[band])
                    )
                output.append(value)
            # Established sensor reporting conventions at the UV-cut edge and
            # last band; values above unity are preserved for fluorescence.
            output[-1] = _single(_single(output[-2] - output[-3]) + output[-2])
            if condition == "M2":
                output[:2] = [output[2]] * 2
            output = tuple(max(_single(0.0001), v) for v in output)
            if not all(math.isfinite(v) for v in output):
                raise ValueError("Non-finite factory-model conversion")
            spectra.append(ModelSpectrum(condition, output))
        return FactoryMeasurement(
            tuple(raw.header),
            tuple(spectra),
            self.factory_sections_sha256,
            self.model_sha256,
        )
