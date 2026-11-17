"""The simulated table behind the Measure tab's table window (test and driver support, not
shipped): ``ui.i1io_table_window.JOB_FACTORY`` replaced by a factory that builds the real
``TableJob`` on the project's table simulator and simulated helper (``reader_sim``), so no USB
device and no instrument is ever opened.

    sim = WindowSim()                       # faults / delays as the tests need
    monkeypatch.setattr(W, "JOB_FACTORY", sim.factory)
"""
from __future__ import annotations

import time

from tests.i1io_table import job_harness as H
from tests.i1io_table import part_c_sim as csim
from tests.i1io_table import reader_sim as RS
from tests.i1io_table import session_sim as ss
from workflow.i1io.table import usb_system as us


class SlowTransport(ss.SimTransport):
    """The simulator's transport, with a wall-clock pause per line (for an on-screen driver that
    must photograph a row while it runs, and for a Stop pressed during it)."""

    def __init__(self, sim, delay_s: float = 0.0):
        super().__init__(sim)
        self.delay_s = float(delay_s)

    def write(self, data, *a, **k):          # noqa: D401 - the transport's own call
        if self.delay_s:
            time.sleep(self.delay_s)
        return super().write(data, *a, **k)


class WindowSim:
    def __init__(self, faults=None, delay_s: float = 0.0, cold: bool = False,
                 app_marker_place=None, press: bool = False, **simkw):
        self.faults = faults
        self.delay_s = delay_s
        self.cold = cold
        self.app_marker_place = app_marker_place
        #: round B: the helper offers the button wait (a simulated one)
        self.press = press
        self.simkw = simkw
        self.jobs: list = []
        self.sim = None
        self.helper = None

    def factory(self, sheet, page, run, stamp, ask):
        from workflow.i1io.table import job as J
        self.sim = csim.CSimTable(part_c=True, aims=list(H.demo_aims(sheet)), cold=self.cold,
                                  **self.simkw)
        self.helper = RS.HelperSim(self.sim, self.faults)
        transport = self.transport = SlowTransport(self.sim, self.delay_s)
        job = J.TableJob(sheet, page, run=run, stamp=stamp,
                         open_transport=lambda: transport,
                         preflight=lambda: H.OK_PREFLIGHT, other_program=lambda: False,
                         ask_after_each_step=ask, reader_factory=self.helper.factory(),
                         helper_check=lambda: None,
                         instrument_check=lambda: us.Check("ok", {"i1pro_devices": 1}),
                         app_marker_place=self.app_marker_place,
                         press_factory=self.helper.press_factory() if self.press else None)
        self.jobs.append(job)
        return job

    def aim(self, mark: int) -> None:
        """The person's hand: the sight on mark *mark* (before pressing Aimed)."""
        self.sim.aim(mark)
