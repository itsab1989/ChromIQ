# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in native batch acquisition, using explicit pre-scan geometry.

Twenty-one final-point readings over seven rows completed on one FD-9,
including calibration renewal. Full-chart GUI and live stop/resume validation
remain pending for this native path.
The established profile-based RawAcquisition flow is unchanged.
"""
import struct
import time

from .motion import RawAcquisition, Phase, failed_on_error, line_command
from .native import NativeCondition, NativeReader
from .protocol import RawSpectrum


class NativeAcquisition(RawAcquisition):
    def __init__(self, instrument, *, enable_experimental_motion=False,
                 enable_experimental_native=False):
        if enable_experimental_native is not True:
            raise ValueError('Native batch acquisition requires explicit experimental opt-in')
        super().__init__(instrument, enable_experimental_motion=enable_experimental_motion)
        self.native_samples = []
        self.completed_native_rows = 0

    @failed_on_error
    def measure_native(self, rows, *, conditions=('M0', 'M1', 'M2'),
                       seconds_per_point=30, native_timeout=15,
                       on_point=None, on_row=None):
        """Acquire all requested conditions at each explicit point before moving.

        Every positioning row is final (more=False), permitting native sensor
        RPCs between positions. Calibrate at the first point of each sixth
        selected chart row, matching the existing raw acquisition schedule.
        Progress callbacks are passive; native results are appended before a
        callback so cancellation/failure preserves completed measurements.
        Homing and ejection occur once, through the enclosing raw workflow.
        """
        if self.phase != Phase.SCANNED or self.raw_samples or self.native_samples:
            raise RuntimeError('Begin one native batch on a retained pre-scan')
        conditions = tuple(NativeCondition(value) for value in conditions)
        if not conditions or len(set(conditions)) != len(conditions):
            raise ValueError('Require unique native measurement conditions')
        if not 1 <= seconds_per_point <= 300 or not 0 < native_timeout <= 60:
            raise ValueError('Point and native deadlines exceed their bounds')
        rows = tuple(tuple(tuple(point) for point in row) for row in rows)
        if not 1 <= len(rows) <= 128:
            raise ValueError('Explicit native geometry supports 1..128 rows')
        # Validate all geometry before the first positioning or exposure request.
        for row in rows:
            line_command(row, False, False)
        if not self.image or any(not 12 < p[1] < len(self.image) - 13 for row in rows for p in row):
            raise ValueError('Native points must fit the complete pre-scan image')
        if any(min(p[1] for p in rows[i]) >= min(p[1] for p in rows[i + 1])
               for i in range(len(rows) - 1)):
            raise ValueError('Native rows must follow forward acquisition order')
        plan = [(point, row_index, column_index == len(row) - 1,
                 row_index % 6 == 0 and column_index == 0)
                for row_index, row in enumerate(rows)
                for column_index, point in enumerate(row)]
        reader = NativeReader(self.instrument, enable_experimental_native=True)

        def progress(callback, *args):
            if callback is None:
                return
            old = self.instrument._row_callback_rpc_blocked
            self.instrument._row_callback_rpc_blocked = True
            try:
                callback(*args)
            finally:
                self.instrument._row_callback_rpc_blocked = old

        def remaining_points(count, total):
            if (count, total) != (1, 1):
                raise RuntimeError('Unexpected initial positioning count')
            for index, (point, row_index, last_in_row, calibrate) in enumerate(plan):
                if index:
                    self._reply(line_command([point], calibrate, False), 0x106, 8)
                    deadline = time.monotonic() + seconds_per_point
                    while True:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise TimeoutError('Native positioning point did not arrive; no retry')
                        message = self._event(remaining)
                        if struct.unpack_from('<I', message)[0] == 0x305:
                            self.raw_samples.append(RawSpectrum.decode(message))
                            break
                result = reader.after_final_point(conditions, timeout=native_timeout)
                self.native_samples.append(result)
                if last_in_row:
                    self.completed_native_rows = row_index + 1
                progress(on_point, len(self.native_samples), len(plan))
                if last_in_row:
                    progress(on_row, self.completed_native_rows, len(rows))

        super().measure([[plan[0][0]]], seconds_per_row=seconds_per_point,
                        on_row=remaining_points)
        return tuple(self.native_samples)
