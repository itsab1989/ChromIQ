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


class _NoExpectedColours:
    """The simulated readers read colours of their own, not the chart's, so the row identity
    check must have no expected colours (it would ask about every row, and be right): whatever
    the window hands the job is not taken. The bed (bed_sim) reads the sheet and takes it."""

    @staticmethod
    def of(base):
        class SimJob(base):
            expected_lab = property(lambda self: None, lambda self, v: None)
            expected_why = property(lambda self: "the simulated readers read colours of their own",
                                    lambda self, v: None)
        SimJob.__name__ = base.__name__
        return SimJob


class WindowSim:
    #: True: the readings come from the sheet on the bed (bed_sim.BedWindowSim)
    reads_the_sheet = False

    def __init__(self, faults=None, delay_s: float = 0.0, cold: bool = False,
                 app_marker_place=None, press: bool = False, aims=None, **simkw):
        self.faults = faults
        #: 4.3.49: the person's aims (p1 readings) instead of the sheet's demo aims, e.g. the
        #: volunteer's real ones of 19 Nov 2026
        self.aims = list(aims) if aims else None
        #: 4.3.49: faults put into the simulated table as soon as it exists ((kind, cid), ...)
        self.table_faults = list(simkw.pop("table_faults", ()) or ())
        #: 4.3.49: where the tables' reaches are kept (default: 4.3.48's target area for every
        #: table, job_harness.store_like_4348; the reach's own tests and drivers pass theirs)
        self.reach_store = simkw.pop("reach_store", None)
        self.delay_s = delay_s
        self.cold = cold
        self.app_marker_place = app_marker_place
        #: round B: the helper offers the button wait (a simulated one)
        self.press = press
        # a real table holds its white tile's values (the D-4b default reads them): a white
        # tile as the simulated helper reads it at rest, so the factors are 1
        simkw.setdefault("stored_tile", tuple([0.88] * 36))
        self.simkw = simkw
        self.jobs: list = []
        #: 4.3.52: the report after each step (None: it follows the guidance). The window tests
        #: written for the quiet mode before 4.3.52 (every question asked, in pop-ups, no
        #: report) set it False with the guidance ON (test_window.open_window, asking=False):
        #: the app no longer builds that mode, but every page it can still show is shown that
        #: way, so those tests keep proving the pop-ups
        self.report_switch = None
        self.sim = None
        self.helper = None

    def factory(self, sheet, page, run, stamp, guided, extra_logging=True, consent_version=0):
        from workflow.i1io.table import job as J
        self.sim = csim.CSimTable(part_c=True, aims=self.aims or list(H.demo_aims(sheet)),
                                  cold=self.cold,
                                  **self.simkw)
        for kind, cid in self.table_faults:
            self.sim.inject(kind, cid)
        self.helper = RS.HelperSim(self.sim, self.faults)
        transport = self.transport = SlowTransport(self.sim, self.delay_s)
        cls = J.TableJob if self.reads_the_sheet else _NoExpectedColours.of(J.TableJob)
        job = cls(sheet, page, run=run, stamp=stamp,
                         open_transport=lambda: transport,
                         preflight=lambda: H.OK_PREFLIGHT, other_program=lambda: False,
                         guided=guided, ask_after_each_step=self.report_switch,
                         extra_logging=extra_logging,
                         consent_version=consent_version,
                         reader_factory=self.helper.factory(),
                         helper_check=lambda: None,
                         instrument_check=lambda: us.Check("ok", {"i1pro_devices": 1}),
                         app_marker_place=self.app_marker_place,
                         press_factory=self.helper.press_factory() if self.press else None,
                         scan_factory=self.helper.scan_factory(),
                         reach_store=(self.reach_store if self.reach_store is not None
                                      else H.store_like_4348()))
        self.helper.job = job
        self.jobs.append(job)
        return job

    def aim(self, mark: int) -> None:
        """The person's hand: the sight on mark *mark* (before pressing Aimed)."""
        self.sim.aim(mark)
