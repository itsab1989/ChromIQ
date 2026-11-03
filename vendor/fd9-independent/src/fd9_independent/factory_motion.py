# SPDX-License-Identifier: GPL-3.0-or-later
"""Automatic row sequencing using sensor-calibrated packets and a live model."""

from bisect import bisect_right

from .instrument_model import InstrumentModel
from .motion import RawAcquisition, Phase, failed_on_error


class FactoryRowAcquisition(RawAcquisition):
    def __init__(
        self,
        instrument,
        *,
        enable_experimental_motion=False,
        enable_experimental_model=False
    ):
        if enable_experimental_model is not True:
            raise ValueError("Factory row conversion requires experimental opt-in")
        super().__init__(
            instrument, enable_experimental_motion=enable_experimental_motion
        )
        self.model = None
        self.native_samples = []
        self.completed_native_rows = 0
        self._model_connection = None

    def prepare_model(self):
        if self.phase is not Phase.NEW or self.model is not None:
            raise RuntimeError("Read one model before loading this chart")
        self.model = InstrumentModel.read(self.instrument, allow_experimental=True)
        self._model_connection = self.instrument.socket
        return self.model

    @failed_on_error
    def measure_rows(
        self,
        rows,
        *,
        conditions=("M0", "M1", "M2"),
        seconds_per_row=150,
        on_point=None,
        on_row=None
    ):
        if self.model is None or self._model_connection is not self.instrument.socket:
            raise RuntimeError(
                "Prepare the instrument model on this same connection first"
            )
        if self.phase is not Phase.SCANNED or self.raw_samples or self.native_samples:
            raise RuntimeError("Begin factory rows on one retained pre-scan")
        conditions = tuple(conditions)
        if (
            not conditions
            or len(set(conditions)) != len(conditions)
            or any(c not in ("M0", "M1", "M2") for c in conditions)
        ):
            raise ValueError("Require unique M0/M1/M2 conditions")
        rows = tuple(tuple(row) for row in rows)
        ends = []
        for row in rows:
            ends.append((ends[-1] if ends else 0) + len(row))

        def point_received(count, total):
            sample = self.model.convert(self.raw_samples[-1], conditions)
            self.native_samples.append(sample)
            self.completed_native_rows = bisect_right(ends, count)
            if on_point is not None:
                on_point(count, total)

        super().measure(
            rows,
            seconds_per_row=seconds_per_row,
            on_point=point_received,
            on_row=on_row,
        )
        return tuple(self.native_samples)
